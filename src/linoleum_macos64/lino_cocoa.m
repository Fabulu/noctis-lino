/*
 *	lino_cocoa.m - native Cocoa display/event/mouse/clipboard layer
 *	for the linoleum_macos64 RTM. Replaces the X11 layer, so the
 *	runtime needs no XQuartz.
 *
 *	The game renders into a 32-bit-per-pixel framebuffer (units, little
 *	endian 0x00RRGGBB => bytes [B,G,R,0]) living in the workspace at
 *	[Display Origin]. Each RETRACE blits it into an NSWindow's content
 *	view. A custom NSView receives key/mouse events and feeds them into
 *	the same key-state table / console buffer / mouse state the X11
 *	layer used.
 */

#include <Cocoa/Cocoa.h>
#include <stdbool.h>
#include <stdint.h>
#include <string.h>
#include "rtm.h"
#include "lino_display.h"
#include "lino_event.h"
#include "lino_mouse.h"
#include "lino_keyboard.h"
#include "lino_luck.h"
#include "lino_file.h"

#define LINO_BITMAP_INFO (kCGBitmapByteOrder32Little | \
    kCGImageAlphaNoneSkipFirst)

@class LinoView;
@class LinoAppDelegate;

/* ------------------------------------------------------------------ */
/* shared state                                                        */
/* ------------------------------------------------------------------ */

static NSApplication *app;
static NSAutoreleasePool *cocoaPool;
static LinoAppDelegate *appDelegate;
static NSWindow *win;
static LinoView *view;		/* forward-declared below */
static void *fb;		/* framebuffer pointer (workspace) */
static int fb_w, fb_h;
static bool display_visible;
static bool quitRequested;
static bool quitKeyInjected;
static unsigned long retraceCount;
static unsigned long quitKeyReleaseRetrace;
static uint8_t pressedKeys[128];
static CGImageRef currentImage;

/* ------------------------------------------------------------------ */
/* forward declarations                                                */
/* ------------------------------------------------------------------ */

static void lino_cocoa_key_event(NSEvent *event, int down);
static void lino_cocoa_mouse_event(NSEvent *event, int kind);
static void lino_cocoa_set_mouse(NSPoint point);
static void lino_cocoa_create_menu(void);
static void lino_cocoa_request_quit(void);
static void lino_cocoa_release_keys(void);
static bool lino_cocoa_verify_pixel_layout(void);

/* ------------------------------------------------------------------ */
/* application lifecycle                                               */
/* ------------------------------------------------------------------ */

@interface LinoAppDelegate : NSObject <NSApplicationDelegate,
    NSWindowDelegate>
@end

@implementation LinoAppDelegate

- (NSApplicationTerminateReply)applicationShouldTerminate:
    (NSApplication *)sender
{
	(void) sender;
	lino_cocoa_request_quit();
	return NSTerminateCancel;
}

- (BOOL)applicationShouldTerminateAfterLastWindowClosed:
    (NSApplication *)sender
{
	(void) sender;
	return NO;
}

- (BOOL)windowShouldClose:(NSWindow *)sender
{
	(void) sender;
	lino_cocoa_request_quit();
	return NO;
}

- (void)applicationDidResignActive:(NSNotification *)notification
{
	(void) notification;
	lino_cocoa_release_keys();
}

@end

static void lino_cocoa_request_quit(void)
{
	quitRequested = true;
}

static void lino_cocoa_release_keys(void)
{
	if (quitKeyInjected) {
		quitRequested = true;
		quitKeyInjected = false;
	}
	memset(pressedKeys, 0, sizeof pressedKeys);
	if (pUIWorkspace != NULL)
		memset(&pUIWorkspace[mm_ConsoleOrigin], 0,
		    (KEY_UNCLASSIFIED + 1) * sizeof *pUIWorkspace);
}

static void lino_cocoa_create_menu(void)
{
	NSString *appName = [NSString stringWithUTF8String:
	    (const char *) IParagraph->appname];
	NSMenu *mainMenu = [[[NSMenu alloc] initWithTitle:@""] autorelease];
	NSMenuItem *appItem = [[[NSMenuItem alloc] initWithTitle:@""
	    action:nil keyEquivalent:@""] autorelease];
	NSMenu *appMenu = [[[NSMenu alloc] initWithTitle:appName] autorelease];
	NSString *quitTitle = [@"Quit " stringByAppendingString:appName];
	NSMenuItem *quitItem = [[[NSMenuItem alloc] initWithTitle:quitTitle
	    action:@selector(terminate:) keyEquivalent:@"q"] autorelease];

	[appMenu addItem:quitItem];
	[appItem setSubmenu:appMenu];
	[mainMenu addItem:appItem];
	[app setMainMenu:mainMenu];
}

/* ------------------------------------------------------------------ */
/* the content view                                                    */
/* ------------------------------------------------------------------ */

@interface LinoView : NSView
@end

@implementation LinoView

- (BOOL)acceptsFirstResponder
{
	return YES;
}

- (BOOL)isFlipped
{
	return YES;
}

- (BOOL)isOpaque
{
	return YES;
}

- (void)drawRect:(NSRect)dirtyRect
{
	if (currentImage != NULL) {
		CGContextRef ctx =
		    (CGContextRef) [[NSGraphicsContext currentContext]
		    graphicsPort];
		/* the view is flipped (top-left origin); CGContextDrawImage
		 * draws the first image row at the top of its coordinate
		 * space, so flip the CTM to keep row 0 on top */
		CGContextSaveGState(ctx);
		CGContextTranslateCTM(ctx, 0, self.bounds.size.height);
		CGContextScaleCTM(ctx, 1, -1);
		CGContextDrawImage(ctx, self.bounds, currentImage);
		CGContextRestoreGState(ctx);
	}
}

- (void)keyDown:(NSEvent *)event
{
	lino_cocoa_key_event(event, 1);
}

- (void)keyUp:(NSEvent *)event
{
	lino_cocoa_key_event(event, 0);
}

- (void)flagsChanged:(NSEvent *)event
{
	NSEventModifierFlags f = [event modifierFlags];
	pUIWorkspace[mm_ConsoleOrigin + KEY_SHIFT] =
	    (f & NSEventModifierFlagShift) ? 1 : 0;
	pUIWorkspace[mm_ConsoleOrigin + KEY_CONTROL] =
	    (f & NSEventModifierFlagControl) ? 1 : 0;
	pUIWorkspace[mm_ConsoleOrigin + KEY_ALTERNATE] =
	    (f & NSEventModifierFlagOption) ? 1 : 0;
}

- (void)mouseDown:(NSEvent *)event
{
	lm.button |= LEFT_BUTTON_PRESSED;
	lino_cocoa_mouse_event(event, 0);
}

- (void)rightMouseDown:(NSEvent *)event
{
	lm.button |= MIDDLE_BUTTON_PRESSED;
	lino_cocoa_mouse_event(event, 0);
}

- (void)mouseUp:(NSEvent *)event
{
	lm.button &= LEFT_BUTTON_RELEASED;
	lino_cocoa_mouse_event(event, 0);
}

- (void)rightMouseUp:(NSEvent *)event
{
	lm.button &= MIDDLE_BUTTON_RELEASED;
	lino_cocoa_mouse_event(event, 0);
}

- (void)otherMouseDown:(NSEvent *)event
{
	lm.button |= RIGHT_BUTTON_PRESSED;
	lino_cocoa_mouse_event(event, 0);
}

- (void)otherMouseUp:(NSEvent *)event
{
	lm.button &= RIGHT_BUTTON_RELEASED;
	lino_cocoa_mouse_event(event, 0);
}

- (void)mouseMoved:(NSEvent *)event
{
	lino_cocoa_mouse_event(event, 0);
}

- (void)mouseDragged:(NSEvent *)event
{
	lino_cocoa_mouse_event(event, 0);
}

- (void)rightMouseDragged:(NSEvent *)event
{
	lino_cocoa_mouse_event(event, 0);
}

@end

/* ------------------------------------------------------------------ */
/* keyboard mapping                                                    */
/* ------------------------------------------------------------------ */

/* map a macOS virtual keycode to a L.in.oleum KEY_* index, or -1 */
static int lino_cocoa_keycode_to_key(unsigned short kc)
{
	switch (kc) {
	case 53: return KEY_ESCAPE;	/* Esc */
	case 36: return KEY_RETURN;	/* Return */
	case 76: return KEY_RETURN;	/* KP Enter */
	case 48: return KEY_TAB;
	case 51: return KEY_BACKSPACE;
	case 117: return KEY_DELETE;	/* Forward Delete */
	case 115: return KEY_HOME;
	case 119: return KEY_END;
	case 116: return KEY_PGUP;
	case 121: return KEY_PGDN;
	case 123: return KEY_LEFT;
	case 124: return KEY_RIGHT;
	case 125: return KEY_DOWN;
	case 126: return KEY_UP;
	case 49: return KEY_SPACE_BAR;
	case 122: return KEY_F1;
	case 120: return KEY_F2;
	case 99: return KEY_F3;
	case 118: return KEY_F4;
	case 96: return KEY_F5;
	case 97: return KEY_F6;
	case 98: return KEY_F7;
	case 100: return KEY_F8;
	case 101: return KEY_F9;
	case 109: return KEY_F10;
	case 103: return KEY_F11;
	case 111: return KEY_F12;
	case 105: return KEY_F13;
	case 107: return KEY_F14;
	case 113: return KEY_F15;
	case 106: return KEY_F16;
	case 64: return KEY_F17;
	case 79: return KEY_F18;
	case 80: return KEY_F19;
	case 90: return KEY_F20;
	/* numeric keypad */
	case 82: return KEY_0N;
	case 83: return KEY_1N;
	case 84: return KEY_2N;
	case 85: return KEY_3N;
	case 86: return KEY_4N;
	case 87: return KEY_5N;
	case 88: return KEY_6N;
	case 89: return KEY_7N;
	case 91: return KEY_8N;
	case 92: return KEY_9N;
	case 65: return KEY_DOT;	/* KP . */
	case 67: return KEY_ASTERISK;	/* KP * */
	case 69: return KEY_PLUS;	/* KP + */
	case 78: return KEY_MINUS;	/* KP - */
	case 75: return KEY_SLASH;	/* KP / */
	default: return -1;
	}
}

static void lino_cocoa_key_event(NSEvent *event, int down)
{
	NSString *base_chars = [event charactersIgnoringModifiers];
	NSString *chars = [event characters];
	unichar base = (base_chars != nil && [base_chars length] > 0) ?
	    [base_chars characterAtIndex:0] : 0;
	unichar c = (chars != nil && [chars length] > 0) ?
	    [chars characterAtIndex:0] : 0;
	unsigned short keycode = [event keyCode];
	int key = lino_cocoa_keycode_to_key(keycode);

	/* Standard punctuation has the same KEY_* state as its keypad alias.
	 * charactersIgnoringModifiers preserves Shift while removing Control. */
	if (key < 0) {
		switch (base) {
		case '/': key = KEY_SLASH; break;
		case '*': key = KEY_ASTERISK; break;
		case '-': key = KEY_MINUS; break;
		case '+': key = KEY_PLUS; break;
		case '.': key = KEY_DOT; break;
		default: break;
		}
	}

	/* Alphabetic / digit state follows the base key, not Shift or Control. */
	if (key < 0 && base != 0) {
		if (base >= 'A' && base <= 'Z')
			key = KEY_A + (base - 'A');
		else if (base >= 'a' && base <= 'z')
			key = KEY_A + (base - 'a');
		else if (base >= '0' && base <= '9')
			key = KEY_0 + (base - '0');
	}

	if (keycode < sizeof pressedKeys) {
		if (down) {
			if (pressedKeys[keycode] != 0)
				key = pressedKeys[keycode] - 1;
			else if (key >= 0)
				pressedKeys[keycode] = (uint8_t) (key + 1);
		} else if (pressedKeys[keycode] != 0) {
			key = pressedKeys[keycode] - 1;
			pressedKeys[keycode] = 0;
		}
	}

	if (key >= 0)
		pUIWorkspace[mm_ConsoleOrigin + key] = down ? 1 : 0;

	if (down && c != 0) {
		char b = (char) c;
		if (b == '\r')
			b = '\n';
		lino_buffer_add(b);
	}
}

/* ------------------------------------------------------------------ */
/* mouse                                                               */
/* ------------------------------------------------------------------ */

lino_mouse lm;
lino_mouse prev;
unit current_mode;

static void lino_cocoa_mouse_event(NSEvent *event, int kind)
{
	(void) kind;
	NSPoint p = [view convertPoint:[event locationInWindow] fromView:nil];
	lino_cocoa_set_mouse(p);
}

static void lino_cocoa_set_mouse(NSPoint point)
{
	NSRect bounds = [view bounds];
	CGFloat local_x;
	CGFloat local_y;
	if (bounds.size.width <= 0 || bounds.size.height <= 0 ||
	    fb_w <= 0 || fb_h <= 0) {
		lm.x = -1;
		lm.y = -1;
		return;
	}
	/* Cocoa may resize the host window without changing the logical Lino
	 * framebuffer. Map pointer coordinates through the same scaling used by
	 * drawRect so iGUI hit targets and game mouse-look remain aligned. */
	local_x = point.x - bounds.origin.x;
	local_y = point.y - bounds.origin.y;
	if (local_x < 0)
		lm.x = -1;
	else if (local_x >= bounds.size.width)
		lm.x = fb_w;
	else
		lm.x = (int) (local_x * fb_w / bounds.size.width);
	if (local_y < 0)
		lm.y = -1;
	else if (local_y >= bounds.size.height)
		lm.y = fb_h;
	else
		lm.y = (int) (local_y * fb_h / bounds.size.height);
}

lino_mouse *lino_mouse_update_position(void)
{
	if (win != nil) {
		NSPoint p =
		    [view convertPoint:[win mouseLocationOutsideOfEventStream]
		     fromView:nil];
		lino_cocoa_set_mouse(p);
	}
	/* the iGUI grants the client the pointer only while it is over the
	 * window (PD IN SIGHT): mirror the X11 XQueryPointer result */
	if (lm.x >= 0 && lm.x < fb_w && lm.y >= 0 && lm.y < fb_h)
		pUIWorkspace[mm_PointerStatus] |= MP_INSIGHT;
	else
		pUIWorkspace[mm_PointerStatus] &= ~MP_INSIGHT;
	return &lm;
}

bool initPointerCommand(void)
{
	pUIWorkspace[mm_PointerStatus] = MP_PRESENT;
	current_mode = pUIWorkspace[mm_PointerMode];
	if (current_mode != MP_BYDELTA && current_mode != MP_BYCOORDINATE)
		return false;
	lino_mouse_update_position();
	return true;
}

bool krnlPointerCommand(PointerCommand command)
{
	switch (command) {
	case IDLE:
		break;
	case READPOINTER:
		prev = lm;
		pUIWorkspace[mm_PointerStatus] = MP_PRESENT;
		lino_mouse_update_position();
		/* publish the absolute pointer position: the game's mouse
		 * look reads [Pointer X/Y Coordinate] directly */
		pUIWorkspace[mm_PointerXCoordinate] = lm.x;
		pUIWorkspace[mm_PointerYCoordinate] = lm.y;
		if (lm.button & LEFT_BUTTON_PRESSED)
			pUIWorkspace[mm_PointerStatus] |= MP_LBUTTONDOWN;
		if (lm.button & MIDDLE_BUTTON_PRESSED)
			pUIWorkspace[mm_PointerStatus] |= MP_RBUTTONDOWN;
		if (lm.button & RIGHT_BUTTON_PRESSED)
			pUIWorkspace[mm_PointerStatus] |= MP_MBUTTONDOWN;
		switch (pUIWorkspace[mm_PointerMode]) {
		case MP_BYDELTA:
			pUIWorkspace[mm_PointerDeltaX] = lm.x - prev.x;
			pUIWorkspace[mm_PointerDeltaY] = lm.y - prev.y;
			/* warp the cursor back to the window centre */
			if (win != nil) {
				NSRect wf = [win frame];
				NSScreen *s = [NSScreen mainScreen];
				CGFloat sh = (s != nil) ? s.frame.size.height : 0;
				CGPoint c = CGPointMake(NSMidX(wf),
							sh - NSMidY(wf));
				CGWarpMouseCursorPosition(c);
			}
			lm = prev;
			break;
		case MP_BYCOORDINATE:
			pUIWorkspace[mm_PointerDeltaX] = lm.x;
			pUIWorkspace[mm_PointerDeltaY] = lm.y;
			break;
		default:
			return false;
		}
		break;
	default:
		return false;
	}
	return true;
}

static bool lino_cocoa_verify_pixel_layout(void)
{
	uint32_t source = 0x00112233;
	uint32_t destination = 0;
	CGDataProviderRef provider = NULL;
	CGColorSpaceRef colorSpace = NULL;
	CGImageRef image = NULL;
	CGContextRef context = NULL;
	bool result = false;

	provider = CGDataProviderCreateWithData(NULL, &source,
	    sizeof source, NULL);
	colorSpace = CGColorSpaceCreateDeviceRGB();
	if (provider == NULL || colorSpace == NULL)
		goto done;
	image = CGImageCreate(1, 1, 8, 32, sizeof source, colorSpace,
	    LINO_BITMAP_INFO, provider, NULL, false, kCGRenderingIntentDefault);
	if (image == NULL)
		goto done;
	context = CGBitmapContextCreate(&destination, 1, 1, 8,
	    sizeof destination, colorSpace,
	    kCGBitmapByteOrder32Little | kCGImageAlphaPremultipliedFirst);
	if (context == NULL)
		goto done;
	CGContextSetBlendMode(context, kCGBlendModeCopy);
	CGContextDrawImage(context, CGRectMake(0, 0, 1, 1), image);
	result = destination == 0xff112233;

done:
	if (context != NULL)
		CGContextRelease(context);
	if (image != NULL)
		CGImageRelease(image);
	if (colorSpace != NULL)
		CGColorSpaceRelease(colorSpace);
	if (provider != NULL)
		CGDataProviderRelease(provider);
	return result;
}

/* ------------------------------------------------------------------ */
/* display                                                             */
/* ------------------------------------------------------------------ */

bool krnlDisplayCommand(DisplayCommand command)
{
	bool result = true;

	if (win == nil) {
		PRINT1("%s: Display isn't initialized.", __func__);
		return result;
	}

	/* check if other display origin is set */
	if (fb != (void *) &pWorkspace[pUIWorkspace[mm_DisplayOrigin]]) {
		lino_display_set_origin
		    (&pWorkspace[pUIWorkspace[mm_DisplayOrigin]]);
	}
	if (fb_w != pUIWorkspace[mm_DisplayWidth] ||
	    fb_h != pUIWorkspace[mm_DisplayHeight]) {
		lino_display_resize(pUIWorkspace[mm_DisplayWidth],
				    pUIWorkspace[mm_DisplayHeight]);
	}
	if (win != nil &&
	    (pUIWorkspace[mm_DisplayXPosition] != 0 ||
	     pUIWorkspace[mm_DisplayYPosition] != 0)) {
		lino_display_move(pUIWorkspace[mm_DisplayXPosition],
				  pUIWorkspace[mm_DisplayYPosition]);
	}

	switch (command) {
	case IDLE:
		break;
	case RETRACE:
		switch (pUIWorkspace[mm_DisplayLiveRegion]) {
		case WHOLEDISPLAY:
			if (lino_display_retrace() == false)
				result = false;
			break;
		case VOIDREGION:
			pUIWorkspace[mm_DisplayLiveRegion] = WHOLEDISPLAY;
			break;
		default:
			if (!lino_display_retrace_region
			    (&pWorkspace[pUIWorkspace[mm_DisplayLiveRegion]]))
				result = false;
			pUIWorkspace[mm_DisplayLiveRegion] = WHOLEDISPLAY;
			break;
		}
		break;
	case SETCOOPERATIVEMODE:
		if (pUIWorkspace[mm_DisplayStatus] & EXCLUSIVE) {
			[win toggleFullScreen:nil];
			pUIWorkspace[mm_DisplayStatus] &= ~EXCLUSIVE;
		}
		break;
	case SETEXCLUSIVEMODE:
		if (!(pUIWorkspace[mm_DisplayStatus] & EXCLUSIVE)) {
			[win toggleFullScreen:nil];
			pUIWorkspace[mm_DisplayStatus] |= EXCLUSIVE;
		}
		break;
	default:
		result = false;
		break;
	}
	return result;
}

bool lino_display_init(unit x, unit y, unit w, unit h, void *data)
{
	PRINT1("%s: Initializing display...\n", __func__);

	display_visible = false;
	quitRequested = false;
	quitKeyInjected = false;
	retraceCount = 0;
	quitKeyReleaseRetrace = 0;
	memset(pressedKeys, 0, sizeof pressedKeys);
	fb = data;
	fb_w = (int) w;
	fb_h = (int) h;
	if (!lino_cocoa_verify_pixel_layout()) {
		fprintf(stderr, "Cocoa framebuffer pixel-layout self-test failed\n");
		return false;
	}

	cocoaPool = [[NSAutoreleasePool alloc] init];
	app = [NSApplication sharedApplication];
	appDelegate = [[LinoAppDelegate alloc] init];
	[app setDelegate:appDelegate];
	[app setActivationPolicy:NSApplicationActivationPolicyRegular];
	lino_cocoa_create_menu();
	[app finishLaunching];
	[app activateIgnoringOtherApps:YES];

	win = [[NSWindow alloc]
	    initWithContentRect:NSMakeRect(0, 0, (CGFloat) w, (CGFloat) h)
	    styleMask:(NSWindowStyleMaskTitled | NSWindowStyleMaskClosable |
		     NSWindowStyleMaskMiniaturizable |
		     NSWindowStyleMaskResizable)
	    backing:NSBackingStoreBuffered
	    defer:NO];
	if (win == nil)
		return false;
	[win setReleasedWhenClosed:NO];
	[win setDelegate:appDelegate];
	[win setTitle:
	    [NSString stringWithUTF8String:(const char *)IParagraph->appname]];
	[win setAcceptsMouseMovedEvents:YES];
	[win setCollectionBehavior:NSWindowCollectionBehaviorFullScreenPrimary];
	/* iGUI owns fullscreen state and preserves its prior logical dimensions.
	 * Hide the native zoom control so an out-of-band transition cannot leave
	 * Display Status and iGUI's restore bookkeeping disagreeing. */
	[[win standardWindowButton:NSWindowZoomButton] setHidden:YES];

	view = [[LinoView alloc] initWithFrame:NSMakeRect(0, 0,
							 (CGFloat) w,
							 (CGFloat) h)];
	[win setContentView:view];
	[win setContentSize:NSMakeSize((CGFloat) w, (CGFloat) h)];
	{
		NSTrackingArea *ta = [[NSTrackingArea alloc]
		    initWithRect:NSZeroRect
		    options:(NSTrackingMouseMoved |
			     NSTrackingMouseEnteredAndExited |
			     NSTrackingActiveInKeyWindow |
			     NSTrackingInVisibleRect)
		    owner:view userInfo:nil];
		[view addTrackingArea:ta];
		[ta release];
	}
	[win makeFirstResponder:view];
	[win makeKeyAndOrderFront:nil];

	/* workspace display parameters */
	pUIWorkspace[mm_DisplayWidth] = w;
	pUIWorkspace[mm_DisplayHeight] = h;
	{
		NSScreen *s = [NSScreen mainScreen];
		pUIWorkspace[mm_DisplayPhysicalWidth] =
		    (unit) (s != nil ? s.frame.size.width : 0);
		pUIWorkspace[mm_DisplayPhysicalHeight] =
		    (unit) (s != nil ? s.frame.size.height : 0);
	}
	pUIWorkspace[mm_DisplayStatus] = ACTIVE;

	lino_display_resize(w, h);
	lino_display_move(x, y);

	PRINT1("%s: Initializing display done.\n", __func__);
	return true;
}

bool lino_display_retrace(void)
{
	if (!display_visible || fb == NULL)
		return true;
	if (fb_w <= 0 || fb_h <= 0)
		return true;

	size_t imageBytes = (size_t) fb_w * fb_h * 4;
	CFDataRef snapshot = CFDataCreate(kCFAllocatorDefault,
	    (const UInt8 *) fb, (CFIndex) imageBytes);
	if (snapshot == NULL)
		return true;
	CGDataProviderRef prov = CGDataProviderCreateWithCFData(snapshot);
	CFRelease(snapshot);
	if (prov == NULL)
		return true;
	CGColorSpaceRef colorSpace = CGColorSpaceCreateDeviceRGB();
	if (colorSpace == NULL) {
		CGDataProviderRelease(prov);
		return true;
	}
	CGImageRef img = CGImageCreate((size_t) fb_w, (size_t) fb_h,
				      8, 32, (size_t) fb_w * 4,
				      colorSpace,
				      LINO_BITMAP_INFO,
				      prov, NULL, false,
				      kCGRenderingIntentDefault);
	CGColorSpaceRelease(colorSpace);
	CGDataProviderRelease(prov);
	if (img == NULL)
		return true;

	if (currentImage != NULL)
		CGImageRelease(currentImage);
	currentImage = img;
	[view setNeedsDisplay:YES];
	[view display];		/* synchronous redraw (no run loop running) */
	[win flushWindow];	/* push the backing store to the screen */
	retraceCount++;
	if (quitKeyInjected && retraceCount >= quitKeyReleaseRetrace) {
		pUIWorkspace[mm_ConsoleOrigin + KEY_ESCAPE] = 0;
		quitKeyInjected = false;
	}
	if (cocoaSmokeMode) {
		printf("COCOA_SMOKE_OK: first Cocoa retrace completed\n");
		fflush(stdout);
		exit(EXIT_SUCCESS);
	}
	if (cocoaQuitSmokeMode && !cocoaQuitSmokeTriggered) {
		cocoaQuitSmokeTriggered = true;
		lino_cocoa_request_quit();
	}
	return true;
}

bool lino_display_retrace_region(unit * region)
{
	/* partial retrace: the whole framebuffer is redrawn anyway */
	return lino_display_retrace();
}

void lino_display_check_position(unit * x, unit * y)
{
	if (*x == MIDDLE) {
		NSScreen *s = [NSScreen mainScreen];
		if (s != nil)
			*x = (unit) ((s.frame.size.width - fb_w) / 2);
	}
	if (*y == MIDDLE) {
		NSScreen *s = [NSScreen mainScreen];
		if (s != nil)
			*y = (unit) ((s.frame.size.height - fb_h) / 2);
	}
}

bool lino_display_move(unit x, unit y)
{
	if (win == nil)
		return true;
	lino_display_check_position(&x, &y);
	/* AppKit origin is bottom-left; L.in.oleum is top-left */
	NSScreen *s = [NSScreen mainScreen];
	CGFloat sh = (s != nil) ? s.frame.size.height : 0;
	NSRect f = [win frame];
	f.origin.x = (CGFloat) x;
	f.origin.y = sh - (CGFloat) (y + fb_h);
	[win setFrame:f display:YES];
	return true;
}

bool lino_display_set_origin(void *data)
{
	fb = data;
	return true;
}

bool lino_display_resize(unit w, unit h)
{
	if (w <= 0 || h <= 0) {
		display_visible = false;
		return true;
	}
	fb_w = (int) w;
	fb_h = (int) h;
	if (win != nil) {
		[win setContentSize:NSMakeSize((CGFloat) w, (CGFloat) h)];
		[view setFrame:NSMakeRect(0, 0, (CGFloat) w, (CGFloat) h)];
	}
	if (!display_visible) {
		display_visible = true;
		if (win != nil) {
			[win orderFront:nil];
			[win makeKeyAndOrderFront:nil];
			[win makeFirstResponder:view];
		}
	}
	return true;
}

bool lino_display_close(void)
{
	if (currentImage != NULL) {
		CGImageRelease(currentImage);
		currentImage = NULL;
	}
	if (app != nil)
		[app setDelegate:nil];
	if (win != nil) {
		[win setDelegate:nil];
		[win close];
		[win release];
		win = nil;
	}
	if (view != nil) {
		[view release];
		view = nil;
	}
	if (appDelegate != nil) {
		[appDelegate release];
		appDelegate = nil;
	}
	app = nil;
	if (cocoaPool != nil) {
		[cocoaPool drain];
		cocoaPool = nil;
	}
	return true;
}

/* ------------------------------------------------------------------ */
/* events                                                              */
/* ------------------------------------------------------------------ */

void handle_pending_events(void)
{
	if (app == nil)
		return;
	NSAutoreleasePool *eventPool = [[NSAutoreleasePool alloc] init];
	NSEvent *event;
	while ((event = [app nextEventMatchingMask:NSEventMaskAny
			    untilDate:[NSDate distantPast]
			    inMode:NSDefaultRunLoopMode
			    dequeue:YES]) != nil) {
		[app sendEvent:event];
	}
	/* Closing the window or choosing Quit must follow the game's normal Escape
	 * save-and-shutdown path rather than letting AppKit terminate the process. */
	if (quitRequested) {
		if (pUIWorkspace[mm_ConsoleOrigin + KEY_ESCAPE] == 0) {
			pUIWorkspace[mm_ConsoleOrigin + KEY_ESCAPE] = 1;
			quitKeyInjected = true;
			quitKeyReleaseRetrace = retraceCount + 2;
		}
		quitRequested = false;
	}
	[eventPool drain];
}

/* ------------------------------------------------------------------ */
/* clipboard                                                           */
/* ------------------------------------------------------------------ */

bool krnlClipCommand(ClipCommand command)
{
	bool result = true;

	if (command != IDLE)
		PRINT1("Clip Command: %u\n", command);

	switch (command) {
	case IDLE:
		break;
	case GETCLIPSIZE: {
		NSPasteboard *pb = [NSPasteboard generalPasteboard];
		NSString *str = [pb stringForType:NSPasteboardTypeString];
		if (str == nil) {
			result = false;
			break;
		}
		pUIWorkspace[mm_ClipSize] =
		    (unit) [str lengthOfBytesUsingEncoding:
			    NSASCIIStringEncoding];
		break;
	}
	case READCLIP: {
		NSPasteboard *pb = [NSPasteboard generalPasteboard];
		NSString *str = [pb stringForType:NSPasteboardTypeString];
		if (str == nil) {
			result = false;
			break;
		}
		btrsstring(&pWorkspace[pUIWorkspace[mm_ClipString]],
			   [str UTF8String]);
		break;
	}
	case WRITECLIP: {
		NSPasteboard *pb = [NSPasteboard generalPasteboard];
		const char *str = (const char *)
		    &pWorkspace[pUIWorkspace[mm_ClipString]];
		[pb clearContents];
		[pb setString:[NSString stringWithUTF8String:str]
		    forType:NSPasteboardTypeString];
		break;
	}
	default:
		result = false;
		break;
	}

	if (!result)
		pUIWorkspace[mm_ClipSize] = 0;

	return result;
}
