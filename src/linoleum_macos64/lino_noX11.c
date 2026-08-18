/*
 *	Headless (no X11) stubs for the macOS 64-bit RTM build.
 *	Used when building without XQuartz. The display is a no-op that
 *	always "succeeds", so programs that initialize a display but never
 *	render (hash tests, etc.) run to completion. Rendering programs
 *	still need the real X11 build.
 */

#include "rtm.h"
#include "lino_display.h"
#include "lino_event.h"
#include "lino_mouse.h"

bool krnlDisplayCommand(DisplayCommand command)
{
	(void) command;
	return true;
}

bool lino_display_init(unit x, unit y, unit w, unit h, void *data)
{
	(void) x;
	(void) y;
	(void) w;
	(void) h;
	(void) data;
	return true;
}

bool lino_display_retrace(void)
{
	return true;
}

bool lino_display_retrace_region(unit * region)
{
	(void) region;
	return true;
}

bool lino_display_move(unit x, unit y)
{
	(void) x;
	(void) y;
	return true;
}

bool lino_display_resize(unit w, unit h)
{
	(void) w;
	(void) h;
	return true;
}

bool lino_display_set_origin(void *data)
{
	(void) data;
	return true;
}

bool lino_display_close(void)
{
	return true;
}

void lino_display_check_position(unit * x, unit * y)
{
	(void) x;
	(void) y;
}

void handle_pending_events(void)
{
}

bool initPointerCommand(void)
{
	return true;
}

bool krnlPointerCommand(PointerCommand command)
{
	(void) command;
	return true;
}

bool krnlClipCommand(ClipCommand command)
{
	(void) command;
	return true;
}
