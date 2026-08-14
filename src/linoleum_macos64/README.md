# linoleum_macos64 - macOS x86_64 (Mach-O) Run-Time Module

Port of the L.in.oleum runtime so compiled programs run natively on macOS
x86_64 (Apple Silicon via Rosetta 2). The display layer is **native Cocoa**
(`lino_cocoa.m`) — no XQuartz required.

## What changed vs linoleum_linux32

- `isokernel.s` — Mach-O x86_64 assembly: `_`-prefixed globals, no
  `.type/.size/.note.GNU-stack`. Register map unchanged (A=rax B=rbx C=rcx
  D=rdx E=rsi X=rbp WS=rdi, 4-byte stack model).
- `rtm.c` — inline-asm symbols use explicit `_` under `__APPLE__` (clang
  does not mangle inline-asm identifiers); FAIL handler prints instead of
  `xmessage`; `MAP_ANONYMOUS` falls back to `MAP_ANON`; the workspace/code
  low-4GB mmap relies on `-Wl,-pagezero_size` at link time (macOS default
  `__PAGEZERO` is 4GB and would block the MAP_FIXED base at 0x10000000).
- `rtm.c` — **initializes `mm_CountsPerMillisecond = 1000` at startup.**
  The game's TK tick engine reads it during `TK seed`, which runs before the
  first READ COUNTS isocall; without an early value the tick period becomes
  zero counts and the main loop spins forever (no frames, no input).
- `lino_cocoa.m` — **native Cocoa display/event/mouse/clipboard layer**
  replacing the X11 files. Creates an `NSApplication` + `NSWindow` (manual
  event pump from `handle_pending_events`), blits the game's framebuffer
  (32-bit BGRX units, zero-copy via `kCGBitmapByteOrder32Little`) with a
  flipped CTM draw, feeds `NSEvent` key/mouse input into the same key-state
  table / console buffer / mouse state, and uses `NSPasteboard` for the
  clipboard. `lino_mouse_update_position` mirrors `XQueryPointer` by setting
  `MP_INSIGHT` while the cursor is over the window — iGUI only hands the
  pointer to the client (and thus enables right-drag mouse-look) when
  `PD IN SIGHT` is set.
- `lino_file.c` — `readdir`-based directory listing under `__APPLE__`
  (raw `getdents64` on Linux for qemu-user), minimal `wordexp` replacement.
- `rtm.h` — `_POSIX_C_SOURCE` and hand-rolled `snprintf/realpath/truncate`
  prototypes disabled on macOS; `free_section` prototype added.
- `lino_noX11.c` — headless display stubs for builds without a window layer
  (deterministic console programs only).
- `lino_xdisplay.c`, `lino_xevent.c`, `lino_mouse.c`, `lino_xclip.c` — the
  former X11 layer, retained as an alternative (requires XQuartz).

## Build

Requires clang only (no XQuartz).

```sh
./build.sh            # Cocoa display layer, links -framework Cocoa
```

`build.sh` produces `rtm01.bin` (Mach-O x86_64). Pack it as a sys pack
variant[0] (relative-offset header: `<I` count + 8×offsets + 8×sizes, 68
bytes, variant[0] at offset 68) and splice with the compiler's
`--sys:<name>` option to produce native macOS executables.

## Verified

galaxy, galaxy2, mulcheck (16-bit `*'`), ft2 all produce byte-identical
output to the Linux x86_64 builds. vhgame runs and is playable under
Rosetta with the native Cocoa window: WASD moves, arrows look,
right-click-drag looks around, menu clicks work, ESC exits.
