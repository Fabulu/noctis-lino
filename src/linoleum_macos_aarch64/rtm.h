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

#ifndef LINOLEUM_MACOS_AARCH64_RTM_H
#define LINOLEUM_MACOS_AARCH64_RTM_H

#include <stddef.h>
#include <stdint.h>

#include "../linoleum_macos64/lino_types.h"
#include "../linoleum_macos64/lino_kernel.h"

typedef void (*proc_t)(void);

struct LNLMINIT {
    unsigned char appname[40];
    unit app_ws_size;
    unit app_code_size;
    unit app_code_entry;
    unit physwsentry;
    unit physappsize;
    unit default_ramtop;
    unit app_code_pri;
    unit lfb_x_atstartup;
    unit lfb_y_atstartup;
    unit lfb_w_atstartup;
    unit lfb_h_atstartup;
    unit pointermode;
    unit testflags;
    unit displaymode;
};

_Static_assert(sizeof(unit) == 4, "Linoleum units must remain 32-bit");
_Static_assert(sizeof(struct LNLMINIT) == 96,
               "LNLMINIT must retain its historical disk layout");
_Static_assert(offsetof(struct LNLMINIT, app_ws_size) == 40,
               "LNLMINIT workspace offset changed");
_Static_assert(offsetof(struct LNLMINIT, physwsentry) == 52,
               "LNLMINIT payload offset changed");
_Static_assert(offsetof(struct LNLMINIT, displaymode) == 92,
               "LNLMINIT tail offset changed");

/* Historical slots 0-3 retain their existing meaning. AArch64 owns eight
 * formerly unused UI communication units for full-width runtime pointers. */
enum {
    ARM64_UI_ISOKERNEL_LO = 4,
    ARM64_UI_ISOKERNEL_HI = 5,
    ARM64_UI_CODE_ORIGIN_LO = 6,
    ARM64_UI_CODE_ORIGIN_HI = 7,
    ARM64_UI_FLOAT_UNARY_LO = 8,
    ARM64_UI_FLOAT_UNARY_HI = 9,
    ARM64_UI_FLOAT_BINARY_LO = 10,
    ARM64_UI_FLOAT_BINARY_HI = 11,
    ARM64_UI_REQUIRED_UNITS = 32947
};

extern unit *pWorkspace;
extern unit *pUIWorkspace;
extern unit current_ramtop;
extern proc_t pCodeEntry;
extern int isostatus;
extern unit aAtExit;
extern unit bAtExit;
extern unit cAtExit;
extern unit dAtExit;
extern unit eAtExit;
extern unit xAtExit;
extern const unit FAIL;
extern const unit DONE;

/* Shared architecture-neutral macOS services use these runtime globals. */
extern struct LNLMINIT *IParagraph;
extern char dmsStockFilename[32768];
extern char **environment;
extern bool cocoaSmokeMode;
extern bool cocoaQuitSmokeMode;
extern bool cocoaQuitSmokeTriggered;

bool krnlConsoleCommand(ConsoleCommand command);
bool krnlFileCommand(FileCommand command);
bool krnlDisplayCommand(DisplayCommand command);
bool krnlPointerCommand(PointerCommand command);
bool initPointerCommand(void);
bool lino_display_init(unit x, unit y, unit width, unit height, void *data);
bool lino_display_set_origin(void *data);
bool lino_display_close(void);
void handle_pending_events(void);

void ISOKRNLCALL(void);
void isokernel(void);
void linoleum(void);

#endif
