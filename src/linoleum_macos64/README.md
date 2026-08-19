# linoleum_macos64 - macOS x86_64 run-time module

This directory ports the L.in.oleum runtime to a thin x86_64 Mach-O. The normal
build uses native Cocoa and AudioToolbox with no XQuartz dependency. Apple
Silicon executes the same image through Rosetta 2; native ARM64 is a separate
unfinished port.

## Runtime boundary

Lino retains its historical 32-bit unit, pointer, and workspace model even though
the host process is x86_64. `isokernel.s` uses the established register map
(A=rax, B=rbx, C=rcx, D=rdx, E=rsi, X=rbp, WS=rdi) and the four-byte Lino stack
model. Runtime mappings exposed to Lino must therefore remain below 4 GB.

`rtm.c` reserves code and workspace in checked low-address mappings. It rejects
an out-of-range result rather than truncating it, does not replace unknown
mappings with unsafe `MAP_FIXED`, and grows workspace by mapping a replacement,
copying live bytes, clearing the new area, and unmapping the old allocation.
The link uses a reduced `__PAGEZERO`, and runtime fallback hints begin well above
the signed image's mapped segments.

The host initializes `mm_CountsPerMillisecond` before Lino startup. The game's
`TK seed` reads that value before its first READ COUNTS isocall; leaving it zero
would collapse the tick period and spin the main loop.

## Native services

- `lino_cocoa.m` creates the application, menu, window, event pump, display,
  pointer, keyboard/text, clipboard, and fullscreen behavior. Logical pointer
  coordinates remain aligned with the aspect-fitted Lino display.
- Framebuffer words are `0x00RRGGBB`. CoreGraphics uses little-endian
  `kCGImageAlphaNoneSkipFirst`, and a one-pixel startup check proves that
  `0x00112233` displays as `0xff112233`.
- Cocoa draws immutable `CFData` framebuffer snapshots. AppKit therefore cannot
  retain mutable or unmapped workspace memory across a remap.
- Focus loss clears key and modifier state. Physical punctuation aliases,
  Control combinations, and actual text characters reach the Lino console.
- Window close and AppKit Quit stay active through fullscreen or modal exits and
  pulse complete Escape press/release intervals until the game reaches its
  normal save-and-shutdown path.
- `lino_sound.c` uses AudioQueue stereo signed packed 16-bit PCM at 44,100 Hz
  with three 16,384-byte buffers. Native sample snapshots protect callbacks from
  workspace remapping; callback and teardown errors are checked and published
  safely.
- `lino_globalK.c` stores data in
  `~/Library/Application Support/Linoleum/GlobalK`, reads the historical
  `~/linoleum/.k` location as a fallback, and performs same-directory atomic
  writes. Reads complete into a temporary bounded buffer before updating live
  workspace state.
- `lino_file.c` uses the macOS directory APIs and a bounded word-expansion
  replacement rather than Linux `getdents64`.
- `lino_noX11.c` supplies a headless backend for NIVGEN and console programs.
  A headless image does not link Cocoa or AudioToolbox.

The old X11 source files remain as historical alternatives, but the supported
windowed build is Cocoa.

## Build

The only direct build requirement is Apple clang and the macOS SDK:

```sh
./build.sh             # Cocoa + AudioToolbox runtime
HEADLESS=1 ./build.sh  # deterministic no-display runtime
```

Both commands produce `rtm01.bin`, an unsigned x86_64 Mach-O with a macOS 10.15
deployment target. The runtime must remain unsigned while the compiler appends
the initialized workspace and machine code.

Pack the RTM as a macOS SYS variant (relative-offset header: `<I` count, eight
offsets, eight sizes, then variants) and compile with the x64 CPU pack. The
hosted production path is automated by:

```text
build/compile_nivtest_linux.sh
build/compile_noctis_macos_linux.sh
.github/workflows/macos-rosetta-nivgen.yml
```

Those scripts verify runtime provenance, bootstrap a byte-identical compiler
fixpoint, audit the CPU pack, and bind every compiler/runtime/source/output hash.

## Packaging and signing

A compiled Lino image includes intentional bytes beyond the runtime's original
`__LINKEDIT` segment. `tools/package_noctis_macos.py` strictly parses the Mach-O
and `LNLMInit`, extends only `__LINKEDIT.filesize` and page-aligned `vmsize` over
the complete unsigned image, proves every other byte unchanged, and then invokes
Apple ad-hoc codesign. Post-sign validation requires one `LC_CODE_SIGNATURE`,
the signature and `__LINKEDIT` ending at EOF, unchanged Lino bounds, and the
complete appended payload hash.

The nested game and outer app are ad-hoc signed, not Developer ID signed or
notarized. Hardened runtime is not enabled. This keeps the current historical
self-loading boundary explicit rather than claiming a distribution property it
does not have.

## Verification status

Hosted checks establish the following:

- Cocoa and headless RTMs build on Intel macOS with the intended architecture,
  deployment target, and framework boundaries.
- Apple Silicon builds both RTMs, Ubuntu cross-compiles the production NIVTEST
  and game images, and Rosetta 2 matches all seven authoritative production
  hashes.
- The packaged app survives strict signature checks before and after ZIP
  extraction, reaches its first real Cocoa retrace, and follows AppKit Quit
  through normal Lino save/cleanup to a nonempty `CURRENT.LIN`.
- Launcher tests verify immutable-resource repair, regular mutable database
  preservation, and rejection of non-regular mutable paths.

The x86_64 app is the current Intel target and the Rosetta 2 fallback for Apple
Silicon. Native ARM64 and Developer ID/notarized distribution remain future
work; see `PORTPLAN-MACOS.md` at the repository root.

## Headless invocation

`--headless` is accepted by a headless build and removed from the application
command line before Lino starts. Passing it to a Cocoa build fails explicitly
instead of pretending that a GUI game ran headlessly.

```sh
HEADLESS=1 ./build.sh
# After packing and compiling with the x64 CPU pack:
./nivtest --headless json
```
