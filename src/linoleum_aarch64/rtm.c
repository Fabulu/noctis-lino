/*
 *	linoleum_linux32 Linoleum Run-Time Module for linux 32-bit systems
 *	Copyright (C) 2004-2006 Peterpaul Klein Haneveld
 *
 *	This program is free software ;  you can redistribute it and/or
 *	modify it under the terms of the GNU General Public License
 *	as published by the Free Software Foundation ;  either version 2
 *	of the License, or (at your option) any later version.
 *
 *	This program is distributed in the hope that it will be useful,
 *	but WITHOUT ANY WARRANTY;  without even the implied warranty of
 *	MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 *	GNU General Public License for more details.
 *
 *	You should have received a copy of the GNU General Public License
 *	along with this program	;  if not, write to the Free Software
 *	Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
 */

/* This is an RTM for linoleum in C. */

/*
 * Run-Time Module for linoleum for linux.
 * This application sets up the environment for exectuting
 * linoleum applications. You can then compile linoleum
 * applications using the normal linoleum compiler, but
 * setting the option: --sys:linux (instead of win32).
 */

/* local includes */
#include "rtm.h"
#include "isokernel.h"
#include "lino_file.h"
#include "lino_socket.h"
#include "lino_display.h"
#include "lino_event.h"
#include "lino_mouse.h"
#include "lino_globalK.h"
#include <sys/mman.h>

/* 
 * compiler communication paragraph/initialization paragraph 
 * The compiler uses this section to communicate some initialization parameters
 * to the application. The data in the initialization paragraph are as specified
 * in the struct LNLMINIT, which is declared in the file rtm.h.
 */
unsigned char ipData[] = {
	'L', 'N', 'L', 'M', 'I', 'n', 'i', 't', 'L', '.', 'I', 'N', '.', 'O',
	'L', 'E', 'U', 'M', ' ', 'r', 'u', 'n', 't', 'i', 'm', 'e', 0, 0, 0,
	0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
	0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 3, 0, 0,
	0, 1, 0, 16, 0, 1, 0, 16, 0, 0, 1, 0, 0, 192, 0, 0, 0, 0, 0, 0, 0,
	0, 0, 0, 0, 0, 0, 0, 0, 'L', 'N', 'L', 'M', 'I', 'e', 'n', 'd'
};

/* declarations */

/* pointer to initialization paragraph */
struct LNLMINIT *IParagraph;

/* pointer for code area */
unit *pCode;
int pCodeSize;
/* pointer to code entry */
typedef void (*proc_t) (void);
proc_t pCodeEntry;
/* pointer for application workspace */
unit *pWorkspace;
int pWorkspaceSize;
/* pointer to uninitialized workspace */
unit *pUIWorkspace;

unit current_ramtop;

/* file group */
char dmsStockFilename[32768];	/* Name of THIS executable file. */
char dmsParameters[32768];	/* Parameters following THIS exe file name. */
FILE *openFile;
size_t readBytes;

char **environment;

/* declaration section for isokernel */
/* return status of isocalls */
int isostatus;
/* variable to hold the stack pointer during isokernel calls */
#if defined(__x86_64__) || defined(__aarch64__)
void *sAtEntry;
#else
unit sAtEntry;
#endif
/* variable to hold registers after execution */
unit aAtExit, bAtExit, cAtExit, dAtExit, eAtExit, xAtExit;

#if defined(__x86_64__) || defined(__aarch64__)
/* next address for low (<4GB) mmap of the code/workspace sections */
static uintptr_t pNextLowBase = 0x10000000;
#endif

/* codes used for failing or ending subroutines in linoleum */
const unit FAIL = 0x6661696C;	/* "FAIL" */
const unit DONE = 0x646F6E65;	/* "DONE" */

#if defined(__aarch64__)
/* The arm64 CPU pack translates the compiler's isocall (pack pattern 150)
 * to a fixed 28-byte sequence:
 *     adr x9,#28; ldr w9,[x9]; add x9,x25,x9; ldr w24,[x9];
 *     ldr w9,[x25]; add w24,w24,w9; blr x24
 * followed by a 4-byte token (the iso slot byte offset).  On macOS the RTM
 * (and therefore isokernel) is loaded above 4GB, so the 32-bit computed
 * target can never reach it.  Also, because the token is trailing data and
 * the blr clobbers the link register, the unpatched sequence would both
 * fall into the token and corrupt x30 (breaking the game's final ret).
 * Replace each occurrence (28 code + 4 token bytes) with a direct 64-bit
 * call that preserves the link register across the isokernel call:
 *     movz x24,lo; movk x24,mid,lsl#16; movk x24,hi,lsl#32;
 *     stp x29,x30,[sp,#-16]!; blr x24; ldp x29,x30,[sp],#16;
 *     b #8; nop                      (32 bytes, works at any load address)
 */
static void arm64_patch_isocalls(void)
{
	static const unsigned char sig[28] = {
		0xe9, 0x00, 0x00, 0x10, 0x29, 0x01, 0x40, 0xb9,
		0x29, 0x03, 0x09, 0x8b, 0x38, 0x01, 0x40, 0xb9,
		0x29, 0x03, 0x40, 0xb9, 0x18, 0x03, 0x09, 0x0b,
		0x00, 0x03, 0x3f, 0xd6
	};
	uintptr_t isok = (uintptr_t) isokernel;
	uint32_t w[8];
	w[0] = 0xd2800000u | (((uint32_t) isok & 0xffffu) << 5) | 24u;
	w[1] = 0xf2800000u | (1u << 21) | ((((uint32_t) isok >> 16) & 0xffffu) << 5) | 24u;
	w[2] = 0xf2800000u | (2u << 21) | ((((uint32_t) (isok >> 32)) & 0xffffu) << 5) | 24u;
	w[3] = 0xa9bf7bfdu;	/* stp x29, x30, [sp, #-16]! */
	w[4] = 0xd63f0300u;	/* blr x24 */
	w[5] = 0xa8c17bfdu;	/* ldp x29, x30, [sp], #16 */
	w[6] = 0x14000002u;	/* b #8 (skip the trailing 4-byte token) */
	w[7] = 0xd503201fu;	/* nop */
	int found = 0;
	int codebytes = pCodeSize * sizeof(unit);
	for (int i = 0; i + 32 <= codebytes; i++) {
		if (memcmp((char *) pCode + i, sig, 28) == 0) {
			memcpy((char *) pCode + i, w, 32);
			found++;
		}
	}
	if (found > 0) {
		__builtin___clear_cache((char *) pCode, (char *) pCode + codebytes);
		fprintf(stderr, "DBG arm64: patched %d isocall(s)\n", found);
	}
}
#endif

/*******************************************************************************
 * Sets up the Linoleum environment and handles execution to the linoleum 
 * program.
 ******************************************************************************/
/* the program */
int main(int argc, char **argv, char **env)
{
	int i, toAdd, parameterLen;
	proc_t isokernelP;

	environment = env;
	/* headless mode: report the in-game time and exit, exactly as the
	 * cartography page does (vhgame.txt "VHG onboard cartography
	 * information"): VHGutcsecs = UTC seconds since 1984-01-01, shown as
	 * "epoc <year> triads <g1>,<g2>,<g3>" where year = secs/1e9 + 6011
	 * and the triads are the seconds split into 3-digit groups. */
	for (i = 1; i < argc; i++) {
		if (strcmp(argv[i], "--headless") == 0) {
			struct tm t0;
			time_t e1984, now = time(NULL);
			long epoch;
			memset(&t0, 0, sizeof t0);
			t0.tm_year = 84;
			t0.tm_mon = 0;
			t0.tm_mday = 1;
			e1984 = timegm(&t0);
			epoch = (long) (now - e1984);
			printf("epoc %ld triads %ld,%ld,%03ld\n",
			       epoch / 1000000000L + 6011,
			       (epoch / 1000000L) % 1000,
			       (epoch / 1000L) % 1000,
			       epoch % 1000L);
			return 0;
		}
	}

	/* initialize IParagraph */
	IParagraph = (struct LNLMINIT *) &ipData[8];
	/* check the size of the application name */
	if (strlen(argv[0]) >= 32768)
		programError("ERROR: Application name too long.");
	/* read application name into: dmsStockFilename */
	/* translate the references to a real path */
	realpath(argv[0], dmsStockFilename);

	/* - reads commandline parameters into: dmsParameters */
	dmsParameters[0] = '\0';
	parameterLen = 0;
	for (i = 1; i < argc; i++) {
		/* check if there are spaces in the current entry */
		if (strchr(argv[i], ' ') == NULL) {
			/* just insert string */
			toAdd = strlen(argv[i]);
			if ((parameterLen + toAdd + 1) >= 32768)
				programError
				    ("ERROR: Too many commandline parameters.");

			strcpy(&dmsParameters[parameterLen], argv[i]);
			parameterLen += toAdd;
			strcpy(&dmsParameters[parameterLen], " ");
			parameterLen++;
		} else {
			/* surround string by quotes */
			toAdd = strlen(argv[i]);
			if ((parameterLen + toAdd + 3) >= 32768)
				programError
				    ("ERROR: Too many commandline parameters.");

			strcat(&dmsParameters[parameterLen], "\"");
			parameterLen++;
			strcat(&dmsParameters[parameterLen], argv[i]);
			parameterLen += toAdd;
			strcat(&dmsParameters[parameterLen], "\" ");
			parameterLen++;
		}
	}
	/* terminate the parameter string if necessary */
	if (parameterLen > 0)
		dmsParameters[--parameterLen] = '\0';

	/* allocate and initialize L.IN.OLEUM code area */
	fprintf(stderr,"DBG code_size=%u ramtop=%u physws=%u appwssz=%u appcodesz=%u entry=%u\n", IParagraph->app_code_size, IParagraph->default_ramtop, IParagraph->physwsentry, IParagraph->app_ws_size, IParagraph->app_code_size, IParagraph->app_code_entry);
	init_section(&pCode, IParagraph->app_code_size, "code");
	fprintf(stderr,"DBG pCode=%p\n", (void*)pCode);
	/* allocate and initialize application workspace */
	init_section(&pWorkspace, IParagraph->default_ramtop, "workspace");
	current_ramtop = IParagraph->default_ramtop;

	/* open stockfile for reading */
	openFile = fopen(dmsStockFilename, "r");
	if (!openFile)
		programError("ERROR: Failed to open Stockfile");

	fprintf(stderr,"DBG stock=%s\n", dmsStockFilename);
	/* read the initialised workspace */
	read_section(&pWorkspace,
		     IParagraph->physwsentry,
		     IParagraph->app_ws_size, "workspace");
	/* set pointer to uninitialized workspace */
	pUIWorkspace = &pWorkspace[IParagraph->app_ws_size];
	/* read the code section */
	read_section(&pCode,
		     (IParagraph->app_ws_size * sizeof(unit)) +
		     IParagraph->physwsentry, IParagraph->app_code_size,
		     "code");
	/* set pointer to application start address */
#ifdef __aarch64__
	/* pCode may live above 4GB (macOS arm64), so do not truncate. */
	pCodeEntry = (proc_t) & pCode[IParagraph->app_code_entry];
#else
	pCodeEntry = (proc_t) (unit) & pCode[IParagraph->app_code_entry];
#endif

	/* close file handle */
	fclose(openFile);

#if defined(__aarch64__)
	/* rewrite isocalls to call isokernel directly (macOS loads >4GB) */
	arm64_patch_isocalls();
#endif

	/* transfer commandline parameters */
	btrsstring(&pUIWorkspace[mm_ProcessCommandLine], dmsParameters);

	/* initialize rest of workspace */
	isokernelP = isokernel;
	fprintf(stderr,"DBG ws loaded, pUIWs=%p\n", (void*)pUIWorkspace);
	fprintf(stderr,"DBG isokernelP=%p pCode=%p\n", (void*)isokernelP, (void*)pCode);
	pWorkspace[mm_ProcessOrigin] = (unit) pCode;
	pUIWorkspace[mm_ProcessISOcall] = ((unit) isokernelP - (unit) pCode);
	pUIWorkspace[mm_ProcessRAMtop] = IParagraph->default_ramtop;
	pUIWorkspace[mm_ProcessPriority] = IParagraph->app_code_pri;

	/* setup isokernel */
	PRINT("initializing ISOKERNEL...\n");
	if ((IParagraph->lfb_w_atstartup > 0) &&
	    (IParagraph->lfb_h_atstartup > 0)) {
		assert(lino_display_init(IParagraph->lfb_x_atstartup,
					 IParagraph->lfb_y_atstartup,
					 IParagraph->lfb_w_atstartup,
					 IParagraph->lfb_h_atstartup, NULL));
		assert(initPointerCommand());
	}
	assert(initNetCommand());

	PRINT1("%s: run main linoleum program.\n", __func__);
	fprintf(stderr,"DBG calling linoleum, isocall offset=%u\n", pUIWorkspace[mm_ProcessISOcall]);

	linoleum();
	fprintf(stderr,"DBG linoleum returned\n");
	if (xAtExit == FAIL) {
		int size = 256, n, result;
		char *arguments = malloc(size);
		while (1) {
			n = snprintf(arguments,
				     size,
				     "xmessage -center \"%s\n\nRegisters after execution.\nA: %d\nB: %d\nC: %d\nD: %d\nE: %d\nX: %d\n\"",
				     dmsStockFilename,
				     (int) aAtExit,
				     (int) bAtExit,
				     (int) cAtExit,
				     (int) dAtExit,
				     (int) eAtExit, (int) xAtExit);
			if (n > -1 && n < size)
				break;
			if (n > -1)
				size = n + 1;
			else
				size *= 2;

			arguments = realloc(arguments, size);
		}
		result = system(arguments);
		free(arguments);
		if (result != 0) {
			printf(dmsStockFilename);
			printf("Registers after execution.\n");
			printf("A: %d\n", (int) aAtExit);
			printf("B: %d\n", (int) bAtExit);
			printf("C: %d\n", (int) cAtExit);
			printf("D: %d\n", (int) dAtExit);
			printf("E: %d\n", (int) eAtExit);
			printf("X: %d\n", (int) xAtExit);
		}
	}

	/* break down isokernel */
	PRINT("Clear remaining isokernel stuff\n");
	if ((IParagraph->lfb_w_atstartup > 0) &&
	    (IParagraph->lfb_h_atstartup > 0)) {
		lino_display_close();
	}

	/* DUMP compiled code for analysis */
	{
		printf("DBG dump: pCodeSize=%d pWorkspaceSize=%d\n", pCodeSize, pWorkspaceSize);
		FILE *f = fopen("/workspace/dump_code.bin", "wb");
		if (f) { fwrite(pCode, 1, pCodeSize, f); fclose(f); }
		f = fopen("/workspace/dump_ws.bin", "wb");
		if (f) { fwrite(pWorkspace, 4, pWorkspaceSize, f); fclose(f); }
	}

	/* free allocated memory */
	free_section(pCode, pCodeSize);
	free_section(pWorkspace, pWorkspaceSize);

	/* terminate program */
	return (0);
}


/**
 * outputs error message and terminates program
 * @param e error message to output
 */
void programError(char *e)
{
	/* print error message to output */
	printf("%s\n", e);
	/* free memory allocated for code section if present */
	if (pCode != NULL) {
		free_section(pCode, pCodeSize);
		pCode = NULL;
	}
	/* free memory allocated for workspace if present */
	if (pWorkspace != NULL) {
		free_section(pWorkspace, pWorkspaceSize);
		pWorkspace = NULL;
		pUIWorkspace = NULL;
	}
	/* terminate the application */
	exit(1);
}

/**
 * This function handles all isokernel calls
 */
void ISOKRNLCALL(void)
{
	assert(pWorkspace != NULL && pCode != NULL);

	PRINT1("%s: isocall.\n", __func__);

	handle_pending_events();

	/* handle all commands */
	isostatus = 0;

	/* check if size of workspace must be set to default_ramtop */
	if (pUIWorkspace[mm_ProcessRAMtop] < IParagraph->default_ramtop) {
		pUIWorkspace[mm_ProcessRAMtop] = IParagraph->default_ramtop;
	}

	/* check if the workspace needs to be resized */
	if (current_ramtop != pUIWorkspace[mm_ProcessRAMtop]) {
		unit *new_workspace;

		/* resize the workspace */
		if ((new_workspace =
		     (unit *) realloc((void *) pWorkspace,
				      pUIWorkspace[mm_ProcessRAMtop] *
				      sizeof(unit)))) {
			pWorkspace = new_workspace;
			pUIWorkspace = &pWorkspace[IParagraph->app_ws_size];
			current_ramtop = pUIWorkspace[mm_ProcessRAMtop];
			lino_display_set_origin(&pWorkspace
						[pUIWorkspace
						 [mm_DisplayOrigin]]);
			/* clear the new bytes if any */
			if (pUIWorkspace[mm_ProcessRAMtop] > current_ramtop) {
				memset(&pWorkspace[current_ramtop], 0,
				       (pUIWorkspace[mm_ProcessRAMtop] -
					current_ramtop) * sizeof(unit));
			}
		} else {
			isostatus++;
		}
	}

	if (!krnlPointerCommand(pUIWorkspace[mm_PointerCommand]))
		isostatus++;
	if (!krnlAPDCommand(pUIWorkspace[mm_APDCommand]))
		isostatus++;
	if (!krnlDisplayCommand(pUIWorkspace[mm_DisplayCommand]))
		isostatus++;
	if (!krnlPCMdataCommand(pUIWorkspace[mm_PCMdataCommand]))
		isostatus++;
	if (!krnlConsoleCommand(pUIWorkspace[mm_ConsoleCommand]))
		isostatus++;
	if (!krnlFileCommand(pUIWorkspace[mm_FileCommand]))
		isostatus++;
	if (!krnlSYStimeCommand(pUIWorkspace[mm_SYStimeCommand]))
		isostatus++;
	if (!krnlPrinterCommand(pUIWorkspace[mm_PrinterCommand]))
		isostatus++;
	if (!krnlProcessCommand(pUIWorkspace[mm_ProcessCommand]))
		isostatus++;
#ifdef pr_network
	if (!krnlNetCommand(pUIWorkspace[mm_NetCommand]))
		isostatus++;
#endif
	if (!krnlGlobalKCommand(pUIWorkspace[mm_GlobalKCommand]))
		isostatus++;
	if (!krnlClipCommand(pUIWorkspace[mm_ClipCommand]))
		isostatus++;


	/* clear all command codes */
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

	if (isostatus > 0) {
		PRINT("ISOKRNLCALL failed.\n");
	} else {
		PRINT("ISOKRNLCALL ok.\n");
	}

}

/* The Isokernel calls section/ */


/**
 * handles all time commands.
 * @return false when errors, true otherwise
 */
bool krnlSYStimeCommand(SYStimeCommand command)
{
	bool result = true;

	struct tm *sTime;
	struct timeb currTime;

	if (command != IDLE) {
		PRINT1("SYStime Command: %u\n", command);
	}

	switch (command) {
	case IDLE:
		break;
	case READTIME:
		ftime(&currTime);
		sTime = localtime(&currTime.time);
		pUIWorkspace[mm_SYStimeYear] = sTime->tm_year;
		pUIWorkspace[mm_SYStimeMonth] = sTime->tm_mon;
		pUIWorkspace[mm_SYStimeDay] = sTime->tm_mday;
		pUIWorkspace[mm_SYStimeDayOfWeek] = sTime->tm_wday;
		pUIWorkspace[mm_SYStimeHour] = sTime->tm_hour;
		pUIWorkspace[mm_SYStimeMinute] = sTime->tm_min;
		pUIWorkspace[mm_SYStimeSecond] = sTime->tm_sec;
		pUIWorkspace[mm_SYStimeMilliSeconds] = currTime.millitm;
		break;
	case READUTCTIME:
		ftime(&currTime);
		sTime = gmtime(&currTime.time);
		pUIWorkspace[mm_SYStimeYear] = sTime->tm_year;
		pUIWorkspace[mm_SYStimeMonth] = sTime->tm_mon;
		pUIWorkspace[mm_SYStimeDay] = sTime->tm_mday;
		pUIWorkspace[mm_SYStimeDayOfWeek] = sTime->tm_wday;
		pUIWorkspace[mm_SYStimeHour] = sTime->tm_hour;
		pUIWorkspace[mm_SYStimeMinute] = sTime->tm_min;
		pUIWorkspace[mm_SYStimeSecond] = sTime->tm_sec;
		pUIWorkspace[mm_SYStimeMilliSeconds] = currTime.millitm;
		break;
	case READCOUNTS:
/* 		clock_t counts = clock(); */
/* 		if (counts != -1) { */
/* 			pUIWorkspace[mm_SYStimeCounts] = counts; */
/* 			pUIWorkspace[mm_CountsPerMillisecond] = */
/* 			    (unit) CLOCKS_PER_SEC / 1000; */
/* 		} else { */
/* 			PRINTERROR("clock"); */
/* 			result = false; */
/* 		} */

		/* The use of gettimeofday is better than clock, because
		 * clock depends on the number of clock ticks spend for 
		 * this application.
		 */
		{
			struct timeval tv;
			if (gettimeofday(&tv, NULL) != -1) {
				pUIWorkspace[mm_SYStimeCounts] =
				    tv.tv_sec * 1000000 + tv.tv_usec;
				pUIWorkspace[mm_CountsPerMillisecond] = 1000;
			} else {
				PRINTERROR("gettimeofday");
				result = false;
			}
		}
		break;
	default:
		result = false;
		break;
	}

	return result;
}

/**
 * handles all process commands.
 * @return false when errors, true otherwise
 */
bool krnlProcessCommand(ProcessCommand command)
{
	if (command != IDLE) {
		PRINT1("Process Command: %u\n", command);
	}

	switch (command) {
	case IDLE:
		break;
	case FAILPROCESS:
#if defined(__x86_64__)
		__asm__("movl FAIL(%rip), %eax\n\t"
			"movl %eax, xAtExit(%rip)\n\t"
			"movq sAtEntry(%rip), %rsp\n\t"
			"popq %rdi\n\t"
			"popq %rsi\n\t"
			"popq %rbx\n\t"
			"popq %rbp\n\t"
			"ret\n");
#elif defined(__aarch64__)
		__asm__("adrp x9, FAIL\n\t"
			"ldr w9, [x9, #:lo12:FAIL]\n\t"
			"adrp x10, xAtExit\n\t"
			"str w9, [x10, #:lo12:xAtExit]\n\t"
			"adrp x9, sAtEntry\n\t"
			"ldr x9, [x9, #:lo12:sAtEntry]\n\t"
			"mov sp, x9\n\t"
			"ldp x25, x29, [sp], #16\n\t"
			"ldp x23, x24, [sp], #16\n\t"
			"ldp x21, x22, [sp], #16\n\t"
			"ldp x19, x20, [sp], #16\n\t"
			"ret\n");
#else
		__asm__("\tpushl FAIL\n"
			"\tpopl xAtExit\n"
			"\tmovl sAtEntry, %esp\n"
			"\tpopl %ebp\n"
			"\tret\n");
#endif
		break;
	case ENDPROCESS:
#if defined(__x86_64__)
		__asm__("movl DONE(%rip), %eax\n\t"
			"movl %eax, xAtExit(%rip)\n\t"
			"movq sAtEntry(%rip), %rsp\n\t"
			"popq %rdi\n\t"
			"popq %rsi\n\t"
			"popq %rbx\n\t"
			"popq %rbp\n\t"
			"ret\n");
#elif defined(__aarch64__)
		__asm__("adrp x9, DONE\n\t"
			"ldr w9, [x9, #:lo12:DONE]\n\t"
			"adrp x10, xAtExit\n\t"
			"str w9, [x10, #:lo12:xAtExit]\n\t"
			"adrp x9, sAtEntry\n\t"
			"ldr x9, [x9, #:lo12:sAtEntry]\n\t"
			"mov sp, x9\n\t"
			"ldp x25, x29, [sp], #16\n\t"
			"ldp x23, x24, [sp], #16\n\t"
			"ldp x21, x22, [sp], #16\n\t"
			"ldp x19, x20, [sp], #16\n\t"
			"ret\n");
#else
		__asm__("\tpushl DONE\n"
			"\tpopl xAtExit\n"
			"\tmovl	sAtEntry, %esp\n"
			"\tpopl %ebp\n"
			"\tret\n");
#endif
		break;
	case _SLEEP:{
/* 		usleep(pUIWorkspace[mm_SleepTimeout] * 1000); */
			struct timespec req, rem;
			req.tv_sec = pUIWorkspace[mm_SleepTimeout] / 1000;
			req.tv_nsec =
			    (pUIWorkspace[mm_SleepTimeout] % 1000) * 1000000;
			while (nanosleep(&req, &rem) == -1) {
				req = rem;
			}
			break;
		}
	default:
		return false;
		break;
	}

	return true;
}


/**
 * handles all APD commands.
 * @return false when errors, true otherwise
 */
bool krnlAPDCommand(APDCommand command)
{
	if (command != IDLE) {
		PRINT1("APD Command: %u\n", command);
		return false;
	}
	return true;
}

/**
 * handles all printer commands.
 * @return false when errors, true otherwise
 */
bool krnlPrinterCommand(PrinterCommand command)
{
	if (command != IDLE) {
		PRINT1("Printer Command: %u\n", command);
		return false;
	}
	return true;
}


/**
 * Initialize a certain section, pWorkspace or pCode
 * @param size The size of the section
 * @param section Pointer to the section pointer
 * @param section Name of the section
 */
void init_section(unit ** section, int size, const char *section_name)
{
	if (size != 0) {
#if defined(__x86_64__) || defined(__aarch64__)
		/* The L.IN.OLEUM code addresses code and workspace with 32-bit
		 * values (pWorkspace[mm_ProcessOrigin] = (unit)pCode, plus
		 * lea ebp,[ebp+eax] jumps), so both must live below 4GB. */
		size_t len = (size_t) size * sizeof(unit);
		len = (len + 0xFFF) & ~(size_t) 0xFFF;
		*section = (unit *) mmap((void *) pNextLowBase, len,
					  PROT_READ | PROT_WRITE | PROT_EXEC,
					  MAP_PRIVATE | MAP_ANONYMOUS | MAP_FIXED,
					  -1, 0);
		if (*section == MAP_FAILED) {
			perror("mmap low");
			*section = (unit *) mmap(NULL, len,
						  PROT_READ | PROT_WRITE |
						  PROT_EXEC,
						  MAP_PRIVATE | MAP_ANONYMOUS, -1,
						  0);
		}
		pNextLowBase += len;
#else
		*section = (unit *) mmap(NULL, size * sizeof(unit),
					  PROT_READ | PROT_WRITE | PROT_EXEC,
					  MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
#endif
		if (*section == MAP_FAILED) {
			perror("mmap");
			printf
			    ("ERROR: Failed to allocate memory for %s section.",
			     section_name);
			programError("");
		} else {
			memset(*section, '\0', size * sizeof(unit));
			if (section == &pCode)
				pCodeSize = size;
			else if (section == &pWorkspace)
				pWorkspaceSize = size;
		}
	} else {
		printf("ERROR: Empty %s section.", section_name);
		programError("");
	}
}

void free_section(unit * section, int size)
{
	if (section != NULL && size > 0)
		munmap(section, size * sizeof(unit));
}

void
read_section(unit ** section, int position, int size, const char *section_name)
{
	/* set file pointer */
	if (fseek(openFile, position, SEEK_SET) == -1) {
		fclose(openFile);
		printf("ERROR: %s section not found.", section_name);
		programError("");
	}
	/* read initialized workspace */
	readBytes =
	    fread(*section, sizeof(char), size * sizeof(unit), openFile);
	if (readBytes != size * sizeof(unit)) {
		fclose(openFile);
		printf("ERROR: Failed to read %s section.", section_name);
		programError("");
	}
}
