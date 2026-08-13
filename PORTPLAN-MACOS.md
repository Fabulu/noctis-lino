# Porting the L.in.oleum toolchain to macOS (Linux bootstrap)

## Goal

Run the Noctis IV port (`work/vhgame.txt`) as native macOS binaries, with the
Linoleum compiler and runtime themselves ported to macOS — bootstrapped
entirely through Linux, no Windows anywhere in the chain.

## Architecture recap (what must move)

L.in.oleum is not a VM — it is a native cross-compiler with a runtime template
attached to every binary.

- `main/lib/gen/compiler.txt` — the compiler, itself written in L.in.oleum
  (WPL-licensed, never modified; the repo patches a copy at
  `patched/compiler114m.txt`). It reads a **CPU pack** and a **SYS pack** at
  runtime and emits a raw binary:
  `[RTM executable][initialized workspace][machine code]`.
- **CPU pack** (`main/cpu/i386.bin`, 6241 patterns, 48-byte aligned): a
  data-only table mapping every L.in.oleum instruction x operand-class x
  register combo onto raw machine code. Patterns are opcode bytes interleaved
  with ISMO placeholders (`D1.4` = workspace displacement, `L3R4` = relative
  code address, `I2.4` = immediate). The compiler is CPU-agnostic — the pack
  *is* the code generator.
- **SYS pack** (`main/sys/win32.bin` / `linux.bin`): a `makertmp`
  concatenation of 8 RTM variants (selected by the `modularextensions`
  director). Each RTM is a real native executable (PE/ELF) whose `main()`
  re-reads its own file, loads workspace+code, and jumps in; `isokernel.s`
  bridges L.in.oleum registers to C isocalls (A=eax, B=ebx, C=ecx, D=edx,
  E=esi, X=ebp, workspace-base=edi). Full RTM source for one platform is in
  `src/linoleum_linux32/` (GPLv2, X11).

The game (`work/vhgame.txt`) and iGUI are pure L.in.oleum and ride on top of
the display/pointer/keyboard isocalls — no source changes needed there.

## Core blocker

Every existing artifact is i386 32-bit — the compiler binaries, the CPU pack,
the RTMs, `work/vhgame.exe`. Modern macOS cannot run 32-bit x86 at all, and
Rosetta 2 translates x86_64 only, not i386. So a real macOS port must change
the code target before anything else.

## Target ISA decision

- **x86_64 first**: runs natively on Intel Macs and on Apple Silicon via
  Rosetta 2 (verified working on the M4 dev box). The pack is a mechanical
  extension of the existing i386 pack (REX prefixes, 64-bit base register),
  far less risk, and an x86_64 Linux VM can build and test it end-to-end.
- **arm64 later**: no Rosetta dependency, best long-term, but a from-scratch
  AArch64 code generator — substantially more effort. Keep x86_64 as fallback.

## Why Linux, not Windows, for the bootstrap

- The compiler program is OS-independent i386 data: verified identical between
  the PE and ELF builds (`main/compiler.exe` and `main/linux_compiler.bin`
  share code size 19307 / entry 18524; only the RTM differs).
- The Linux RTM is rebuildable from in-repo GPL source
  (`src/linoleum_linux32/`). The shipped `linux_compiler.bin` segfaults because
  it carries an *old* RTM build (~26 KB of byte diffs vs `main/sys/linux.bin`);
  rebuilding from current source is the fix.
- Windows is actively bad on Apple Silicon: 32-bit PE under Wine-on-ARM is
  unsupported, a Windows VM needs licensing, and it buys nothing — the compiler
  program it carries is extractable anyway.

## Phases

### Phase 0 — Environment

- Linux x86_64 VM via the installed `qemu-system-x86_64` (Debian or Alpine),
  with i386 multilib userland (`gcc -m32`, `libc6-dev-i386`,
  `libx11-dev:i386`). x86_64 is the right VM shape: it runs the i386 seed
  compiler and becomes the native dev/test box for the x86_64 CPU pack.
- Headless display for the GUI RTM: either `Xvfb`, or (better) patch the RTM
  source so `lino_display_init` is optional when `lfb_w/h = 0` —
  `compiler114m.exe` already declares `lfb_w=0, lfb_h=0`, so a headless
  compiler needs no X at all.

### Phase 1 — Bootstrap a headless i386 Linux compiler

1. Rebuild the Linux RTM from `src/linoleum_linux32/` -> `rtm01.bin`. Fix
   whatever the 2006 C code trips on against a modern kernel/glibc.
2. Pack `main/sys/linux.bin` via `main/lib/ppkh/makertmp.txt` logic (or a
   small Python packer — format is `n, offsets, sizes, variants`).
3. Splice the seed compiler: extract `compiler114m.exe[18432:]` (headless
   "Universal Compiler", no GUI assets, file size == `physappsize`), append to
   the rebuilt RTM, patch LNLMINIT (`physwsentry` = RTM size, ws/code/entry
   from the PE). Result: a headless i386 Linux compiler.
4. Verify against known vectors: compile `work/mulcheck.txt`,
   `work/galaxy.txt`, `work/mulall.txt` for `--sys:linux`; compare against the
   repo's documented outputs and `verify_mul.py` / `tests/run_all.py`
   expectations.

### Phase 2 — x86_64 CPU pack (core work)

1. Enumerate semantics: extend `tools/packtool.py` to decode all 6241 i386
   patterns and map each to its ip-record (`vector packed ip records` in
   `compiler.txt`, 609 records) + operand class.
2. Generate the pack: emit REX-correct, 64-bit-base (`rdi`) equivalents;
   32-bit operands (unit = 32); the 25 register combos per (reg,reg) block
   generated from a register-encoding table, exactly as `tools/genmul.py` /
   `tools/genfp.py` already do. The 8-ISMO uniformity keeps this bounded.
   Subtlety: byte-register encoding differs (ah vs spl/bpl/sil/dil) and
   `pusha/popa` do not exist in 64-bit mode.
3. x86_64 `isokernel.s` with matching register map (A=eax ... E=esi, X=ebp,
   ws=rdi) + System V stack alignment.
4. Self-host proof: compile the compiler program to x86_64 *Linux* with the
   new pack -> x86_64 Linux compiler; have it recompile itself.
5. Validate with gcc oracles: run the repo's math/float/galaxy suites against
   exact arithmetic (the repo already tests this way), byte-exact galaxy hash,
   `*%` contract tests (`tests/test_mulsplit.py`).

### Phase 3 — macOS x86_64 sys pack

1. Adapt the RTM (`linoleum_linux32` -> `linoleum_macos`): display/input/sound
   via SDL2 (Homebrew) or Cocoa; file/time/process/sockets already POSIX;
   globalK -> NSUserDefaults/file; clipboard -> NSPasteboard (or stub).
2. Build `rtm01..08` with clang -> `main/sys/macos.bin`.
3. Cross-compile from the Linux VM: `compiler --sys:macos --cpu:x86_64` on the
   compiler source and `work/vhgame.txt` -> x86_64 Mach-O binaries.
4. Run on the M4 via Rosetta (verified working). RTM self-executes appended
   code from its own file — ad-hoc sign / relaxed hardened-runtime for the
   initial build.
5. Port `lino_build.ps1` -> shell/Makefile, adapt `tests/run_all.py`, add a
   macOS launcher.

### Phase 4 — arm64 (after x86_64 ships)

From-scratch AArch64 CPU pack + arm64 `isokernel` + native RTM; keep x86_64 as
the fallback path.

## Key risks

- 2006 Linux RTM may need porting fixes on a modern kernel/X11 — full source
  is in-repo; that is the point of Phase 1.
- x86_64 REX/byte-register encoding subtleties — contained by oracle-based
  validation (Phase 2.5).
- macOS code-exec restrictions on the self-loading RTM — mitigate with
  signing/`MAP_JIT` (matters most for the arm64 phase).
- Licensing: WPL forbids modifying `compiler.txt` / `i386.bin` — we *generate
  new* packs and patch a copy of the compiler source (existing
  `patched/compiler114m.txt` precedent); the new RTM is new GPL code modeled
  on `linoleum_linux32`.

## First milestone

Set up the VM, rebuild the Linux RTM, splice the seed compiler, and prove it
reproduces the repo's known test vectors for `--sys:linux`. That single step
validates the whole bootstrap theory before any CPU-pack work begins.
