/*
 * Minimal macOS AArch64 Linoleum runtime bridge.
 * Copyright (C) 2004-2006 Peterpaul Klein Haneveld
 * Copyright (C) 2026 Linoleum contributors
 *
 * This program is free software; you can redistribute it and/or modify it
 * under the terms of the GNU General Public License as published by the Free
 * Software Foundation; either version 2 of the License, or (at your option)
 * any later version.
 */

#define _DARWIN_C_SOURCE

#include <errno.h>
#include <fcntl.h>
#include <inttypes.h>
#include <limits.h>
#include <mach-o/loader.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <sys/time.h>
#include <sys/types.h>
#include <time.h>
#include <unistd.h>

#include "rtm.h"

#ifndef MAP_ANONYMOUS
#define MAP_ANONYMOUS MAP_ANON
#endif

struct init_block {
    unsigned char marker[8];
    struct LNLMINIT paragraph;
    unsigned char end_marker[8];
};

typedef uint32_t (*float_unary_proc_t)(uint32_t, uint32_t);
typedef uint32_t (*float_binary_proc_t)(uint32_t, uint32_t, uint32_t);

_Static_assert(sizeof(struct init_block) == 112,
               "initialization block layout changed");
_Static_assert(sizeof(proc_t) == sizeof(uintptr_t),
               "AArch64 function pointers must fit uintptr_t");
_Static_assert(sizeof(float_unary_proc_t) == sizeof(uintptr_t),
               "AArch64 helper pointers must fit uintptr_t");
_Static_assert(sizeof(float_binary_proc_t) == sizeof(uintptr_t),
               "AArch64 helper pointers must fit uintptr_t");
_Static_assert(sizeof(size_t) == 8,
               "the AArch64 runtime requires a 64-bit size type");

/* The appender patches this paragraph in the copied runtime before adding the
 * initialized workspace and code payload. Keep both markers literal and unique. */
__attribute__((used, aligned(4)))
struct init_block ipData = {
    {'L', 'N', 'L', 'M', 'I', 'n', 'i', 't'},
    {
        {'m', 'a', 'c', 'O', 'S', ' ', 'A', 'A', 'r', 'c', 'h', '6', '4', 0},
        0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0
    },
    {'L', 'N', 'L', 'M', 'I', 'e', 'n', 'd'}
};

unit *pWorkspace;
unit *pUIWorkspace;
unit current_ramtop;
proc_t pCodeEntry;
int isostatus;
unit aAtExit;
unit bAtExit;
unit cAtExit;
unit dAtExit;
unit eAtExit;
unit xAtExit;
const unit FAIL = INT32_C(0x6661696c);
const unit DONE = INT32_C(0x646f6e65);
struct LNLMINIT *IParagraph = &ipData.paragraph;
char dmsStockFilename[32768];
char **environment;
bool cocoaSmokeMode;
bool cocoaQuitSmokeMode;
bool cocoaQuitSmokeTriggered;

static void *pCode;
static size_t pCodeMapBytes;
static size_t pWorkspaceMapBytes;
static size_t systemPageSize;
static bool soundInitializationAttempted;
static bool displayInitialized;

static void report_error(const char *message)
{
    fprintf(stderr, "MACOS_AARCH64_RUNTIME_ERROR: %s\n", message);
}

static bool checked_add_size(size_t left, size_t right, size_t *result)
{
    if (left > SIZE_MAX - right)
        return false;
    *result = left + right;
    return true;
}

static bool checked_unit_bytes(unit count, size_t *bytes)
{
    if (count <= 0)
        return false;
    *bytes = (size_t) (uint32_t) count * sizeof(unit);
    return true;
}

static bool checked_map_bytes(size_t payload_bytes, size_t *map_bytes)
{
    size_t rounded;

    if (systemPageSize == 0 || payload_bytes == 0)
        return false;
    if (!checked_add_size(payload_bytes, systemPageSize - 1, &rounded))
        return false;
    *map_bytes = (rounded / systemPageSize) * systemPageSize;
    return *map_bytes != 0;
}

static void *map_units(unit count, int protection, size_t *map_bytes)
{
    size_t payload_bytes;
    void *mapping;

    if (!checked_unit_bytes(count, &payload_bytes) ||
        !checked_map_bytes(payload_bytes, map_bytes)) {
        errno = EOVERFLOW;
        return MAP_FAILED;
    }
    mapping = mmap(NULL, *map_bytes, protection,
                   MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    if (mapping != MAP_FAILED)
        memset(mapping, 0, *map_bytes);
    return mapping;
}

static bool read_exact_at(int descriptor, void *destination, size_t size,
                          off_t offset)
{
    unsigned char *cursor = destination;
    size_t completed = 0;

    while (completed < size) {
        size_t remaining = size - completed;
        size_t request = remaining > (size_t) SSIZE_MAX ?
                         (size_t) SSIZE_MAX : remaining;
        ssize_t received = pread(descriptor, cursor + completed, request,
                                 offset + (off_t) completed);
        if (received == 0)
            return false;
        if (received < 0) {
            if (errno == EINTR)
                continue;
            return false;
        }
        completed += (size_t) received;
    }
    return true;
}

static bool validate_macho_suffix(int descriptor, size_t file_size,
                                  size_t application_size,
                                  const char **reason)
{
    struct mach_header_64 header;
    struct linkedit_data_command signature = {0};
    unsigned char *commands = NULL;
    size_t commands_end;
    size_t offset = 0;
    unsigned int signatures = 0;
    bool valid = false;

#define MACH_REJECT(message) do { *reason = (message); goto cleanup; } while (0)

    if (!read_exact_at(descriptor, &header, sizeof(header), 0))
        MACH_REJECT("Mach-O header is truncated");
    if (header.magic != MH_MAGIC_64 || header.cputype != CPU_TYPE_ARM64 ||
        header.filetype != MH_EXECUTE)
        MACH_REJECT("stock file is not a thin arm64 Mach-O executable");
    if (!checked_add_size(sizeof(header), (size_t) header.sizeofcmds,
                          &commands_end) || commands_end > application_size)
        MACH_REJECT("Mach-O load commands exceed the runtime prefix");

    commands = malloc((size_t) header.sizeofcmds);
    if (commands == NULL)
        MACH_REJECT("cannot allocate Mach-O load-command buffer");
    if (!read_exact_at(descriptor, commands, (size_t) header.sizeofcmds,
                       (off_t) sizeof(header)))
        MACH_REJECT("Mach-O load commands are truncated");

    for (uint32_t index = 0; index < header.ncmds; ++index) {
        struct load_command command;

        if (offset > (size_t) header.sizeofcmds ||
            (size_t) header.sizeofcmds - offset < sizeof(command))
            MACH_REJECT("Mach-O load-command table is malformed");
        memcpy(&command, commands + offset, sizeof(command));
        if (command.cmdsize < sizeof(command) ||
            command.cmdsize > (size_t) header.sizeofcmds - offset)
            MACH_REJECT("Mach-O load command has an invalid size");
        if (command.cmd == LC_CODE_SIGNATURE) {
            if (command.cmdsize != sizeof(signature) || signatures != 0)
                MACH_REJECT("Mach-O has an invalid code-signature command");
            memcpy(&signature, commands + offset, sizeof(signature));
            ++signatures;
        }
        offset += command.cmdsize;
    }
    if (offset != (size_t) header.sizeofcmds)
        MACH_REJECT("Mach-O load-command count does not cover its table");

    if (signatures == 0) {
        valid = true;
        goto cleanup;
    }
    if (signatures != 1 || signature.datasize == 0 ||
        (size_t) signature.dataoff < application_size ||
        (size_t) signature.dataoff > file_size ||
        (size_t) signature.datasize != file_size - (size_t) signature.dataoff)
        MACH_REJECT("stock-file code signature is not the exact final suffix");

    valid = true;

cleanup:
    free(commands);
#undef MACH_REJECT
    return valid;
}

static bool validate_image(int descriptor, size_t file_size,
                           size_t *workspace_bytes,
                           size_t *code_bytes, size_t *entry_bytes,
                           size_t *code_offset, const char **reason)
{
    int64_t minimum_ramtop;
    size_t expected_size;

#define REJECT(message) do { *reason = (message); return false; } while (0)

    if (IParagraph->app_ws_size <= 0)
        REJECT("initialized workspace size must be positive");
    if (IParagraph->app_code_size <= 0)
        REJECT("code size must be positive");
    if (IParagraph->app_code_entry < 0 ||
        IParagraph->app_code_entry >= IParagraph->app_code_size)
        REJECT("code entry is outside the code payload");
    if (IParagraph->physwsentry <= 0 || IParagraph->physappsize <= 0)
        REJECT("physical payload offsets must be positive");
    if ((uintmax_t) file_size > (uintmax_t) INT32_MAX ||
        (size_t) (uint32_t) IParagraph->physappsize > file_size)
        REJECT("physical application size exceeds the stock file");

    minimum_ramtop = (int64_t) IParagraph->app_ws_size +
                     ARM64_UI_REQUIRED_UNITS;
    if (minimum_ramtop > INT32_MAX ||
        IParagraph->default_ramtop < minimum_ramtop)
        REJECT("RAMtop leaves no room for the complete service workspace");

    if (!checked_unit_bytes(IParagraph->app_ws_size, workspace_bytes) ||
        !checked_unit_bytes(IParagraph->app_code_size, code_bytes))
        REJECT("payload unit count overflows the host size type");
    if (!checked_unit_bytes(IParagraph->app_code_entry + 1, entry_bytes))
        REJECT("code entry byte offset overflows the host size type");
    *entry_bytes -= sizeof(unit);

    expected_size = (size_t) (uint32_t) IParagraph->physwsentry;
    if (!checked_add_size(expected_size, *workspace_bytes, code_offset) ||
        !checked_add_size(*code_offset, *code_bytes, &expected_size))
        REJECT("stock-file payload range overflows the host size type");
    if (expected_size != (size_t) (uint32_t) IParagraph->physappsize)
        REJECT("workspace and code payload do not exactly fill the application");
    if (!validate_macho_suffix(descriptor, file_size, expected_size, reason))
        return false;

#undef REJECT
    return true;
}

enum {
    FLOAT_UNARY_SINE = 1,
    FLOAT_UNARY_COSINE = 2
};

static uint32_t apply_float_unary(uint32_t bits, uint32_t operation)
{
    const uint32_t magnitude = bits & UINT32_C(0x7FFFFFFF);
    float input;
    float output;
    uint32_t result;

    if (operation != FLOAT_UNARY_SINE && operation != FLOAT_UNARY_COSINE)
        return bits;
    if (magnitude >= UINT32_C(0x5F000000) &&
        magnitude < UINT32_C(0x7F800000))
        return bits;
    if (magnitude == UINT32_C(0x7F800000))
        return UINT32_C(0xFFC00000);
    if (magnitude > UINT32_C(0x7F800000))
        return bits | UINT32_C(0x00400000);

    memcpy(&input, &bits, sizeof(input));
    switch (operation) {
    case FLOAT_UNARY_SINE:
        output = sinf(input);
        break;
    case FLOAT_UNARY_COSINE:
        output = cosf(input);
        break;
    default:
        return bits;
    }
    memcpy(&result, &output, sizeof(result));
    return result;
}

enum {
    FLOAT_BINARY_PARTIAL_REMAINDER = 1,
    FLOAT_BINARY_PARTIAL_ARCTANGENT = 2
};

static float apply_float_partial_remainder(float left, float right)
{
    if (isfinite(left) && isfinite(right) &&
        left != 0.0f && right != 0.0f) {
        const int exponent_difference =
            ilogbf(fabsf(left)) - ilogbf(fabsf(right));

        /* One measured x87 FPREM selects N = 32 + (D mod 32). */
        if (exponent_difference >= 64) {
            const int reduction_width =
                32 + exponent_difference % 32;
            const double scaled_right =
                scalbn((double) right,
                       exponent_difference - reduction_width);

            return (float) fmod((double) left, scaled_right);
        }
    }
    return fmodf(left, right);
}

static uint32_t apply_float_binary(uint32_t left_bits, uint32_t right_bits,
                                   uint32_t operation)
{
    const uint32_t left_magnitude = left_bits & UINT32_C(0x7FFFFFFF);
    const uint32_t right_magnitude = right_bits & UINT32_C(0x7FFFFFFF);
    float left;
    float right;
    float output;
    uint32_t result;

    if (operation != FLOAT_BINARY_PARTIAL_REMAINDER &&
        operation != FLOAT_BINARY_PARTIAL_ARCTANGENT)
        return left_bits;
    if (right_magnitude > UINT32_C(0x7F800000))
        return right_bits | UINT32_C(0x00400000);
    if (left_magnitude > UINT32_C(0x7F800000))
        return left_bits | UINT32_C(0x00400000);
    if (operation == FLOAT_BINARY_PARTIAL_REMAINDER) {
        if (right_magnitude == 0 ||
            left_magnitude == UINT32_C(0x7F800000))
            return UINT32_C(0xFFC00000);
        if (right_magnitude == UINT32_C(0x7F800000))
            return left_bits;
    }

    memcpy(&left, &left_bits, sizeof(left));
    memcpy(&right, &right_bits, sizeof(right));
    switch (operation) {
    case FLOAT_BINARY_PARTIAL_REMAINDER:
        output = apply_float_partial_remainder(left, right);
        break;
    case FLOAT_BINARY_PARTIAL_ARCTANGENT:
        output = atan2f(right, left);
        break;
    default:
        return left_bits;
    }
    memcpy(&result, &output, sizeof(result));
    return result;
}

static uintptr_t function_address(proc_t function)
{
    uintptr_t address = 0;

    memcpy(&address, &function, sizeof(address));
    return address;
}

static uintptr_t float_unary_address(float_unary_proc_t function)
{
    uintptr_t address = 0;

    memcpy(&address, &function, sizeof(address));
    return address;
}

static uintptr_t float_binary_address(float_binary_proc_t function)
{
    uintptr_t address = 0;

    memcpy(&address, &function, sizeof(address));
    return address;
}

static void set_code_entry(size_t entry_bytes)
{
    uintptr_t address = (uintptr_t) pCode + entry_bytes;

    memcpy(&pCodeEntry, &address, sizeof(pCodeEntry));
}

static void store_u32(unit *destination, uint32_t value)
{
    memcpy(destination, &value, sizeof(value));
}

static void store_pointer_pair(unit *low, unit *high, uintptr_t address)
{
    store_u32(low, (uint32_t) (address & UINT32_MAX));
    store_u32(high, (uint32_t) (address >> 32));
}

static void publish_runtime_pointers(void)
{
    proc_t entry = isokernel;
    float_unary_proc_t float_unary = apply_float_unary;
    float_binary_proc_t float_binary = apply_float_binary;

    store_pointer_pair(&pUIWorkspace[ARM64_UI_ISOKERNEL_LO],
                       &pUIWorkspace[ARM64_UI_ISOKERNEL_HI],
                       function_address(entry));
    store_pointer_pair(&pUIWorkspace[ARM64_UI_CODE_ORIGIN_LO],
                       &pUIWorkspace[ARM64_UI_CODE_ORIGIN_HI],
                       (uintptr_t) pCode);
    store_pointer_pair(&pUIWorkspace[ARM64_UI_FLOAT_UNARY_LO],
                       &pUIWorkspace[ARM64_UI_FLOAT_UNARY_HI],
                       float_unary_address(float_unary));
    store_pointer_pair(&pUIWorkspace[ARM64_UI_FLOAT_BINARY_LO],
                       &pUIWorkspace[ARM64_UI_FLOAT_BINARY_HI],
                       float_binary_address(float_binary));
}

static void release_mappings(void)
{
    if (pCode != NULL) {
        (void) munmap(pCode, pCodeMapBytes);
        pCode = NULL;
        pCodeMapBytes = 0;
    }
    if (pWorkspace != NULL) {
        (void) munmap(pWorkspace, pWorkspaceMapBytes);
        pWorkspace = NULL;
        pUIWorkspace = NULL;
        pWorkspaceMapBytes = 0;
    }
}

static bool krnl_system_time_command(unit command)
{
    struct timeval now;
    struct tm split;
    time_t seconds;

    switch (command) {
    case IDLE:
        return true;
    case READTIME:
    case READUTCTIME:
        if (gettimeofday(&now, NULL) != 0)
            return false;
        seconds = now.tv_sec;
        if ((command == READTIME ? localtime_r(&seconds, &split) :
                                   gmtime_r(&seconds, &split)) == NULL)
            return false;
        pUIWorkspace[mm_SYStimeYear] = split.tm_year;
        pUIWorkspace[mm_SYStimeMonth] = split.tm_mon;
        pUIWorkspace[mm_SYStimeDay] = split.tm_mday;
        pUIWorkspace[mm_SYStimeDayOfWeek] = split.tm_wday;
        pUIWorkspace[mm_SYStimeHour] = split.tm_hour;
        pUIWorkspace[mm_SYStimeMinute] = split.tm_min;
        pUIWorkspace[mm_SYStimeSecond] = split.tm_sec;
        pUIWorkspace[mm_SYStimeMilliSeconds] = (unit) (now.tv_usec / 1000);
        return true;
    case READCOUNTS: {
        uint64_t counts;

        if (gettimeofday(&now, NULL) != 0)
            return false;
        counts = (uint64_t) now.tv_sec * UINT64_C(1000000) +
                 (uint64_t) now.tv_usec;
        store_u32(&pUIWorkspace[mm_SYStimeCounts], (uint32_t) counts);
        pUIWorkspace[mm_CountsPerMillisecond] = 1000;
        return true;
    }
    default:
        return false;
    }
}

static bool krnl_process_command(unit command)
{
    struct timespec request;
    struct timespec remainder;
    unit milliseconds;

    if (command == IDLE)
        return true;
    if (command != _SLEEP)
        return false;

    milliseconds = pUIWorkspace[mm_SleepTimeout];
    if (milliseconds < 0)
        return false;
    request.tv_sec = milliseconds / 1000;
    request.tv_nsec = (long) (milliseconds % 1000) * 1000000L;
    while (nanosleep(&request, &remainder) != 0) {
        if (errno != EINTR)
            return false;
        request = remainder;
    }
    return true;
}

static bool workspace_range_is_valid(unit origin, uint32_t units)
{
    uint64_t end;

    if (origin < 0 || current_ramtop < 0)
        return false;
    end = (uint64_t) (uint32_t) origin + (uint64_t) units;
    return end <= (uint64_t) (uint32_t) current_ramtop;
}

static bool krnl_checked_globalK_command(GlobalKCommand command)
{
    bool data_required;
    bool result;

    switch (command) {
    case IDLE:
        return true;
    case KREAD:
    case KWRITE:
        data_required = true;
        break;
    case KDESTROY:
        data_required = false;
        break;
    default:
        pUIWorkspace[mm_GlobalKCommand] = IDLE;
        return false;
    }

    if (!workspace_range_is_valid(pUIWorkspace[mm_GlobalKName], 24) ||
        (data_required &&
         !workspace_range_is_valid(pUIWorkspace[mm_GlobalKData], 255))) {
        pUIWorkspace[mm_GlobalKCommand] = IDLE;
        return false;
    }

    result = krnlGlobalKCommand(command);
    pUIWorkspace[mm_GlobalKCommand] = IDLE;
    return result;
}

static void reject_unsupported_command(int slot)
{
    if (pUIWorkspace[slot] != IDLE)
        ++isostatus;
}

static void clear_service_commands(void)
{
    pUIWorkspace[mm_DisplayCommand] = IDLE;
    pUIWorkspace[mm_PCMdataCommand] = IDLE;
    pUIWorkspace[mm_ConsoleCommand] = IDLE;
    pUIWorkspace[mm_PointerCommand] = IDLE;
    pUIWorkspace[mm_FileCommand] = IDLE;
    pUIWorkspace[mm_SYStimeCommand] = IDLE;
    pUIWorkspace[mm_APDCommand] = IDLE;
    pUIWorkspace[mm_PrinterCommand] = IDLE;
    pUIWorkspace[mm_ProcessCommand] = IDLE;
    pUIWorkspace[mm_NetCommand] = IDLE;
    pUIWorkspace[mm_GlobalKCommand] = IDLE;
    pUIWorkspace[mm_ClipCommand] = IDLE;
}

void ISOKRNLCALL(void)
{
    unit requested_ramtop;
    int64_t minimum_ramtop;

    handle_pending_events();
    isostatus = 0;
    requested_ramtop = pUIWorkspace[mm_ProcessRAMtop];
    minimum_ramtop = (int64_t) IParagraph->app_ws_size +
                     ARM64_UI_REQUIRED_UNITS;
    if (requested_ramtop < minimum_ramtop) {
        pUIWorkspace[mm_ProcessRAMtop] = current_ramtop;
        isostatus = 1;
        clear_service_commands();
        return;
    }

    if (requested_ramtop != current_ramtop) {
        unit old_ramtop = current_ramtop;
        unit copy_ramtop = old_ramtop < requested_ramtop ?
                           old_ramtop : requested_ramtop;
        unit *old_workspace = pWorkspace;
        size_t old_map_bytes = pWorkspaceMapBytes;
        size_t new_map_bytes = 0;
        unit *new_workspace = map_units(requested_ramtop,
                                        PROT_READ | PROT_WRITE,
                                        &new_map_bytes);

        if (new_workspace == MAP_FAILED) {
            pUIWorkspace[mm_ProcessRAMtop] = current_ramtop;
            isostatus = 1;
            clear_service_commands();
            return;
        }

        memcpy(new_workspace, old_workspace,
               (size_t) (uint32_t) copy_ramtop * sizeof(unit));
        if (requested_ramtop > old_ramtop) {
            memset(&new_workspace[old_ramtop], 0,
                   (size_t) (uint32_t) (requested_ramtop - old_ramtop) *
                   sizeof(unit));
        }

        pWorkspace = new_workspace;
        pWorkspaceMapBytes = new_map_bytes;
        pUIWorkspace = &pWorkspace[IParagraph->app_ws_size];
        current_ramtop = requested_ramtop;
        pUIWorkspace[mm_ProcessRAMtop] = requested_ramtop;
        publish_runtime_pointers();
        if (displayInitialized) {
            unit origin = pUIWorkspace[mm_DisplayOrigin];

            if (origin < 0 || origin >= current_ramtop ||
                !lino_display_set_origin(&pWorkspace[origin]))
                ++isostatus;
        }

        if (munmap(old_workspace, old_map_bytes) != 0)
            ++isostatus;
    }

    if (!krnlPointerCommand((PointerCommand) pUIWorkspace[mm_PointerCommand]))
        ++isostatus;
    if (!krnlDisplayCommand((DisplayCommand) pUIWorkspace[mm_DisplayCommand]))
        ++isostatus;
    if (!krnlPCMdataCommand(
            (PCMdataCommand) pUIWorkspace[mm_PCMdataCommand]))
        ++isostatus;
    if (!krnlConsoleCommand((ConsoleCommand) pUIWorkspace[mm_ConsoleCommand]))
        ++isostatus;
    if (!krnlFileCommand((FileCommand) pUIWorkspace[mm_FileCommand]))
        ++isostatus;
    if (!krnl_system_time_command(pUIWorkspace[mm_SYStimeCommand]))
        ++isostatus;
    if (!krnl_process_command(pUIWorkspace[mm_ProcessCommand]))
        ++isostatus;
    if (!krnl_checked_globalK_command(
            (GlobalKCommand) pUIWorkspace[mm_GlobalKCommand]))
        ++isostatus;

    reject_unsupported_command(mm_APDCommand);
    reject_unsupported_command(mm_PrinterCommand);
    reject_unsupported_command(mm_NetCommand);
    reject_unsupported_command(mm_ClipCommand);
    clear_service_commands();
}

static bool parse_runtime_options(int argc, char **argv)
{
    for (int index = 1; index < argc; ++index) {
        if (strcmp(argv[index], "--cocoa-smoke") == 0) {
            if (cocoaQuitSmokeMode)
                return false;
            cocoaSmokeMode = true;
        } else if (strcmp(argv[index], "--cocoa-quit-smoke") == 0) {
            if (cocoaSmokeMode)
                return false;
            cocoaQuitSmokeMode = true;
        } else {
            return false;
        }
    }
    return true;
}

int main(int argc, char **argv, char **env)
{
    struct stat status;
    const char *validation_reason = NULL;
    long page_size;
    size_t file_size;
    size_t workspace_bytes = 0;
    size_t code_bytes = 0;
    size_t entry_bytes = 0;
    size_t code_offset = 0;
    uintptr_t code_address;
    uintptr_t workspace_address;
    uintptr_t isokernel_address;
    int descriptor = -1;
    int result = EXIT_FAILURE;

    environment = env;
    if (argc < 1 || argv[0] == NULL ||
        realpath(argv[0], dmsStockFilename) == NULL) {
        report_error("cannot resolve the stock-file path");
        return EXIT_FAILURE;
    }
    if (!parse_runtime_options(argc, argv)) {
        report_error("only one Cocoa smoke switch and an empty application command line are supported");
        return EXIT_FAILURE;
    }

    page_size = sysconf(_SC_PAGESIZE);
    if (page_size <= 0) {
        report_error("cannot determine the system page size");
        return EXIT_FAILURE;
    }
    systemPageSize = (size_t) page_size;

    descriptor = open(dmsStockFilename, O_RDONLY | O_CLOEXEC);
    if (descriptor < 0 || fstat(descriptor, &status) != 0 || status.st_size < 0) {
        report_error("cannot inspect the stock file");
        goto cleanup;
    }
    if ((uintmax_t) status.st_size > SIZE_MAX) {
        report_error("stock file is too large for this host");
        goto cleanup;
    }
    file_size = (size_t) status.st_size;

    if (!validate_image(descriptor, file_size, &workspace_bytes, &code_bytes,
                        &entry_bytes, &code_offset, &validation_reason)) {
        report_error(validation_reason);
        goto cleanup;
    }

    pCode = map_units(IParagraph->app_code_size,
                      PROT_READ | PROT_WRITE, &pCodeMapBytes);
    pWorkspace = map_units(IParagraph->default_ramtop,
                           PROT_READ | PROT_WRITE, &pWorkspaceMapBytes);
    if (pCode == MAP_FAILED || pWorkspace == MAP_FAILED) {
        if (pCode == MAP_FAILED)
            pCode = NULL;
        if (pWorkspace == MAP_FAILED)
            pWorkspace = NULL;
        report_error("cannot allocate code or workspace mapping");
        goto cleanup;
    }

    if (!read_exact_at(descriptor, pWorkspace, workspace_bytes,
                       (off_t) IParagraph->physwsentry) ||
        !read_exact_at(descriptor, pCode, code_bytes, (off_t) code_offset)) {
        report_error("cannot read the complete appended payload");
        goto cleanup;
    }
    if (close(descriptor) != 0) {
        descriptor = -1;
        report_error("cannot close the stock file");
        goto cleanup;
    }
    descriptor = -1;

    __builtin___clear_cache((char *) pCode, (char *) pCode + code_bytes);
    if (mprotect(pCode, pCodeMapBytes, PROT_READ | PROT_EXEC) != 0) {
        report_error("cannot seal the code mapping read/execute");
        goto cleanup;
    }

    current_ramtop = IParagraph->default_ramtop;
    pUIWorkspace = &pWorkspace[IParagraph->app_ws_size];
    pUIWorkspace[mm_ProcessISOcall] = 0;
    pUIWorkspace[mm_ProcessRAMtop] = current_ramtop;
    pUIWorkspace[mm_ProcessPriority] = IParagraph->app_code_pri;
    /* Slots 4-11 contain full-width ARM pointers, so this slice deliberately
     * exposes only an empty Lino application command line in slot 3. */
    pUIWorkspace[mm_ProcessCommandLine] = 0;
    pUIWorkspace[mm_CountsPerMillisecond] = 1000;
    pUIWorkspace[mm_PCMdataStatus] = 0;
    pUIWorkspace[mm_PointerMode] = IParagraph->pointermode;
    publish_runtime_pointers();
    soundInitializationAttempted = true;
    (void) lino_sound_init();
    set_code_entry(entry_bytes);

    if (IParagraph->lfb_w_atstartup > 0 &&
        IParagraph->lfb_h_atstartup > 0) {
        if (!lino_display_init(IParagraph->lfb_x_atstartup,
                               IParagraph->lfb_y_atstartup,
                               IParagraph->lfb_w_atstartup,
                               IParagraph->lfb_h_atstartup, NULL) ||
            !initPointerCommand()) {
            (void) lino_display_close();
            report_error("cannot initialize the Cocoa display or pointer");
            goto cleanup;
        }
        displayInitialized = true;
    }

    linoleum();

    code_address = (uintptr_t) pCode;
    workspace_address = (uintptr_t) pWorkspace;
    isokernel_address = function_address(isokernel);
    printf("MACOS_AARCH64_RUNTIME_RESULT status=%d A=%08" PRIX32
           " B=%08" PRIX32 " C=%08" PRIX32 " D=%08" PRIX32
           " E=%08" PRIX32 " X=%08" PRIX32
           " code=%016" PRIXPTR " workspace=%016" PRIXPTR
           " isokernel=%016" PRIXPTR " ramtop=%08" PRIX32 "\n",
           isostatus, (uint32_t) aAtExit, (uint32_t) bAtExit,
           (uint32_t) cAtExit, (uint32_t) dAtExit, (uint32_t) eAtExit,
           (uint32_t) xAtExit, code_address, workspace_address,
           isokernel_address, (uint32_t) current_ramtop);
    result = xAtExit == FAIL ? EXIT_FAILURE : EXIT_SUCCESS;

cleanup:
    if (descriptor >= 0)
        (void) close(descriptor);
    if (soundInitializationAttempted) {
        if (!lino_sound_close())
            result = EXIT_FAILURE;
        soundInitializationAttempted = false;
    }
    if (displayInitialized) {
        if (!lino_display_close())
            result = EXIT_FAILURE;
        displayInitialized = false;
    }
    release_mappings();
    if (cocoaQuitSmokeMode) {
        if (!cocoaQuitSmokeTriggered || xAtExit == FAIL ||
            result != EXIT_SUCCESS) {
            fprintf(stderr,
                    "COCOA_QUIT_SMOKE_FAILED: graceful shutdown was not completed\n");
            return EXIT_FAILURE;
        }
        printf("COCOA_QUIT_SMOKE_OK: Cocoa quit used the Lino shutdown path\n");
        fflush(stdout);
    }
    return result;
}
