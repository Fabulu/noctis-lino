#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>

#include "fp64_helper.h"

struct pair64_32 {
    uint64_t input;
    uint32_t output;
};

struct pair32_64 {
    uint32_t input;
    uint64_t output;
};

struct pair64_64 {
    uint64_t input;
    uint64_t output;
};

struct binary64_vector {
    uint64_t left;
    uint64_t right;
    uint32_t operation;
    uint64_t output;
};

static const struct binary64_vector arithmetic_vectors[] = {
    {UINT64_C(0xFFF8000000012345), UINT64_C(0x7FF8000000012345),
     FLOAT_BINARY64_SUM, UINT64_C(0x7FF8000000012345)},
    {UINT64_C(0x7FF8000000012345), UINT64_C(0xFFF8000000012345),
     FLOAT_BINARY64_SUM, UINT64_C(0x7FF8000000012345)}
};

static const struct pair64_32 nearest_vectors[] = {
    {UINT64_C(0x8000000000000000), UINT32_C(0x00000000)},
    {UINT64_C(0x000FFFFFFFFFFFFF), UINT32_C(0x00000000)},
    {UINT64_C(0x3FE0000000000000), UINT32_C(0x00000000)},
    {UINT64_C(0x3FE0000000000001), UINT32_C(0x00000001)},
    {UINT64_C(0x3FF8000000000000), UINT32_C(0x00000002)},
    {UINT64_C(0x4004000000000000), UINT32_C(0x00000002)},
    {UINT64_C(0xBFF8000000000000), UINT32_C(0xFFFFFFFE)},
    {UINT64_C(0x41DFFFFFFFC00000), UINT32_C(0x7FFFFFFF)},
    {UINT64_C(0x41DFFFFFFFE00000), UINT32_C(0x80000000)},
    {UINT64_C(0xC1E0000000000000), UINT32_C(0x80000000)},
    {UINT64_C(0x7FF0000000000000), UINT32_C(0x80000000)},
    {UINT64_C(0x7FF0000000000001), UINT32_C(0x80000000)}
};

static const struct pair32_64 from_int_vectors[] = {
    {UINT32_C(0x00000000), UINT64_C(0x0000000000000000)},
    {UINT32_C(0x00000001), UINT64_C(0x3FF0000000000000)},
    {UINT32_C(0xFFFFFFFF), UINT64_C(0xBFF0000000000000)},
    {UINT32_C(0x01000001), UINT64_C(0x4170000010000000)},
    {UINT32_C(0x7FFFFFFF), UINT64_C(0x41DFFFFFFFC00000)},
    {UINT32_C(0x80000000), UINT64_C(0xC1E0000000000000)}
};

static const struct pair64_64 narrow_vectors[] = {
    {UINT64_C(0x8000000000000000), UINT64_C(0x8000000000000000)},
    {UINT64_C(0x3FF0000010000000), UINT64_C(0x3FF0000000000000)},
    {UINT64_C(0x3FF0000030000000), UINT64_C(0x3FF0000040000000)},
    {UINT64_C(0x3690000000000000), UINT64_C(0x0000000000000000)},
    {UINT64_C(0xB690000000000000), UINT64_C(0x8000000000000000)},
    {UINT64_C(0x3690000000000001), UINT64_C(0x36A0000000000000)},
    {UINT64_C(0x380FFFFFDFFFFFFF), UINT64_C(0x380FFFFFC0000000)},
    {UINT64_C(0x380FFFFFE0000000), UINT64_C(0x3810000000000000)},
    {UINT64_C(0x47EFFFFFEFFFFFFF), UINT64_C(0x47EFFFFFE0000000)},
    {UINT64_C(0x47EFFFFFF0000000), UINT64_C(0x7FF0000000000000)},
    {UINT64_C(0xFFF0000000000000), UINT64_C(0xFFF0000000000000)},
    {UINT64_C(0x7FF0000000000001), UINT64_C(0x7FF8000000000000)},
    {UINT64_C(0x7FF123456789ABCD), UINT64_C(0x7FF9234560000000)},
    {UINT64_C(0xFFFABCDE12345678), UINT64_C(0xFFFABCDE00000000)}
};

static uint64_t random_bits(void)
{
    static uint64_t state = UINT64_C(0xD1B54A32D192ED03);

    state ^= state << 13;
    state ^= state >> 7;
    state ^= state << 17;
    return state;
}

static int check_edges(void)
{
    unsigned i;

    for (i = 0; i < sizeof arithmetic_vectors / sizeof arithmetic_vectors[0]; i++) {
        const uint64_t actual = apply_binary64(
            arithmetic_vectors[i].left, arithmetic_vectors[i].right,
            arithmetic_vectors[i].operation);
        if (actual != arithmetic_vectors[i].output) {
            fprintf(stderr,
                    "arithmetic vector %u: %016" PRIX64 " != %016" PRIX64 "\n",
                    i, actual, arithmetic_vectors[i].output);
            return 1;
        }
    }
    for (i = 0; i < sizeof nearest_vectors / sizeof nearest_vectors[0]; i++) {
        const uint32_t actual = (uint32_t) apply_binary64(
            nearest_vectors[i].input, 0, FLOAT_BINARY64_NEAREST_INT32);
        if (actual != nearest_vectors[i].output) {
            fprintf(stderr, "nearest vector %u: %08" PRIX32 " != %08" PRIX32 "\n",
                    i, actual, nearest_vectors[i].output);
            return 1;
        }
    }
    for (i = 0; i < sizeof from_int_vectors / sizeof from_int_vectors[0]; i++) {
        const uint64_t actual = apply_binary64(
            from_int_vectors[i].input, 0, FLOAT_BINARY64_FROM_INT32);
        if (actual != from_int_vectors[i].output) {
            fprintf(stderr, "from-int vector %u: %016" PRIX64 " != %016" PRIX64 "\n",
                    i, actual, from_int_vectors[i].output);
            return 1;
        }
    }
    for (i = 0; i < sizeof narrow_vectors / sizeof narrow_vectors[0]; i++) {
        const uint64_t actual = apply_binary64(
            narrow_vectors[i].input, 0, FLOAT_BINARY64_NARROW_BINARY32);
        if (actual != narrow_vectors[i].output) {
            fprintf(stderr, "narrow vector %u: %016" PRIX64 " != %016" PRIX64 "\n",
                    i, actual, narrow_vectors[i].output);
            return 1;
        }
    }
    return 0;
}

#if defined(__i386__) || defined(__x86_64__)
static uint64_t x87_binary64(uint64_t left, uint64_t right, uint32_t operation)
{
    uint64_t output;

    switch (operation) {
    case FLOAT_BINARY64_SUM:
        __asm__ volatile ("fldl %1; faddl %2; fstpl %0; fnclex"
                          : "=m" (output) : "m" (left), "m" (right) : "st");
        break;
    case FLOAT_BINARY64_DIFFERENCE:
        __asm__ volatile ("fldl %1; fsubl %2; fstpl %0; fnclex"
                          : "=m" (output) : "m" (left), "m" (right) : "st");
        break;
    case FLOAT_BINARY64_PRODUCT:
        __asm__ volatile ("fldl %1; fmull %2; fstpl %0; fnclex"
                          : "=m" (output) : "m" (left), "m" (right) : "st");
        break;
    case FLOAT_BINARY64_QUOTIENT:
        __asm__ volatile ("fldl %1; fdivl %2; fstpl %0; fnclex"
                          : "=m" (output) : "m" (left), "m" (right) : "st");
        break;
    default:
        output = left;
        break;
    }
    return output;
}

static uint32_t x87_nearest_int32(uint64_t input)
{
    uint32_t output;

    __asm__ volatile ("fldl %1; fistpl %0; fnclex"
                      : "=m" (output) : "m" (input) : "st");
    return output;
}

static uint64_t x87_from_int32(uint32_t input)
{
    uint64_t output;

    __asm__ volatile ("fildl %1; fstpl %0"
                      : "=m" (output) : "m" (input) : "st");
    return output;
}

static uint64_t x87_narrow_binary32(uint64_t input)
{
    uint32_t temporary;
    uint64_t output;

    __asm__ volatile ("fldl %2; fstps %1; flds %1; fstpl %0; fnclex"
                      : "=m" (output), "+m" (temporary)
                      : "m" (input) : "st");
    return output;
}

static int check_x87(void)
{
    uint16_t old_control;
    const uint16_t exact_control = UINT16_C(0x133F);
    unsigned i;

    __asm__ volatile ("fnstcw %0" : "=m" (old_control));
    __asm__ volatile ("fldcw %0" : : "m" (exact_control));
    for (i = 0; i < 200000U; i++) {
        const uint64_t input = random_bits();
        const uint64_t right = random_bits();
        const uint32_t operation = FLOAT_BINARY64_SUM + i % 4U;
        const uint64_t binary = apply_binary64(input, right, operation);
        const uint64_t want_binary = x87_binary64(input, right, operation);
        const uint32_t nearest = (uint32_t) apply_binary64(
            input, 0, FLOAT_BINARY64_NEAREST_INT32);
        const uint64_t from_int = apply_binary64(
            (uint32_t) input, 0, FLOAT_BINARY64_FROM_INT32);
        const uint64_t narrow = apply_binary64(
            input, 0, FLOAT_BINARY64_NARROW_BINARY32);
        const uint32_t want_nearest = x87_nearest_int32(input);
        const uint64_t want_from_int = x87_from_int32((uint32_t) input);
        const uint64_t want_narrow = x87_narrow_binary32(input);

        if (binary != want_binary) {
            fprintf(stderr,
                    "x87 arithmetic case %u operation %" PRIu32
                    " inputs %016" PRIX64 "/%016" PRIX64
                    " output %016" PRIX64 "/%016" PRIX64 "\n",
                    i, operation, input, right, binary, want_binary);
            __asm__ volatile ("fldcw %0" : : "m" (old_control));
            return 1;
        }
        if (nearest != want_nearest || from_int != want_from_int ||
            narrow != want_narrow) {
            fprintf(stderr,
                    "x87 case %u input %016" PRIX64
                    " nearest %08" PRIX32 "/%08" PRIX32
                    " from-int %016" PRIX64 "/%016" PRIX64
                    " narrow %016" PRIX64 "/%016" PRIX64 "\n",
                    i, input, nearest, want_nearest,
                    from_int, want_from_int, narrow, want_narrow);
            __asm__ volatile ("fldcw %0" : : "m" (old_control));
            return 1;
        }
    }
    __asm__ volatile ("fldcw %0" : : "m" (old_control));
    return 0;
}
#else
static int check_x87(void)
{
    (void) random_bits;
    return 0;
}
#endif

int main(void)
{
    if (check_edges() != 0 || check_x87() != 0)
        return 1;
    puts("fp64 conversion helper: all checks passed");
    return 0;
}
