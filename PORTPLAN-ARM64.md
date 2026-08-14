# Porting the L.in.oleum toolchain to native Apple Silicon (arm64)

## Goal

Run the Noctis IV port (`work/vhgame.txt`) as **native arm64** macOS binaries
on the M4 Pro — no Rosetta 2, no XQuartz (the Cocoa display layer is
architecture-independent and is reused as-is).

Current state: x86_64 macOS works end-to-end under Rosetta 2 with the native
Cocoa window (`src/linoleum_macos64/`, verified playable).

## Why arm64 is a different kind of job than x86_64

The x86_64 port translated the i386 CPU pack to x86_64, which shares x87 and
the general register/stack model. AArch64 changes the whole execution model:

- **No x87 FPU.** The game's float math (Wave 7a primitives, `fp/*`, `suseed`,
  `surng`, the whole terrain renderer) runs on the x87 stack via ISMOs
  (`D2.4`/`L*R4` = fld/fstp/fadd/fmul/...). AArch64 has VFP/NEON instead. The
  x87 stack must be **emulated** (a software 8-deep FPU stack with per-ISMO
  helpers) or mapped to FP registers with a register allocator. Software
  emulation first for correctness; performance later.
- **Different register map.** x86_64: A=rax B=rbx C=rcx D=rdx E=rsi X=rbp
  WS=rdi. AArch64: pick 7 general registers for A..E, X, WS with a stable
  calling convention, and a temp set for the translated code's scratch.
- **4-byte stack model.** L.in.oleum pushes/pops 4-byte units on the real
  stack; AArch64 keeps the stack 16-byte aligned. The push/pop ISMOs must
  preserve alignment (e.g. 4-byte slots under a 16-byte frame, or a dedicated
  software stack).
- **Memory operands.** `[WS + disp]` addressing has a limited immediate range
  on AArch64 (`add`/`ldr` with scaled offsets); far displacements need
  address synthesis (base + scaled register or `add` of a register-built
  offset).
- **Division.** x86 div/idiv helpers translate to AArch64 `udiv`/`sdiv`
  (which lack the div-mod pair, so `%` needs a second multiply-subtract).

## Validation strategy

Every phase must leave a **deterministic, cross-architecture-identical**
checkpoint:

1. **Headless smoke test** (`--headless`): prints the in-game time. Initially
   validates that the RTM + toolchain build and run on arm64. Later upgraded
   to read the game's own computed `VHGutcsecs` so it exercises translated
   code.
2. **Byte-identical suite** (the real codegen test): `galaxy`, `galaxy2`,
   `mulcheck` (16-bit `*'`), `ft2` produce files that must match the x86_64
   outputs exactly, under `qemu-aarch64-static` in the i686 container and
   natively on the M4.
3. **Full game**: vhgame compiles and runs natively arm64.

## Phases

### Phase 1 — arm64 toolchain + RTM (validated by headless)
- Install/verify `aarch64-linux-gnu-gcc` + `qemu-aarch64-static` in the
  container (mirrors how the x86_64 Linux RTM was built and tested).
- Port `isokernel.s` to AArch64 (SysV ABI: x0–x7 args, x29 frame, x30 LR,
  16-byte stack alignment), keeping the L.in.oleum register map.
- Port `rtm.c` low-4GB workspace allocation for arm64 (arm64 address space is
  different; the 4-byte pointer constraint no longer binds the same way, but
  the code must still be consistent).
- Build the arm64 Linux RTM, splice a headless-validated program, run under
  `qemu-aarch64-static`: `--headless` must print the epoc/triads.
- Build the arm64 **macOS** RTM with `clang -arch arm64` + Cocoa.

### Phase 2 — AArch64 CPU pack (validated by byte-identical suite)
- New translator (`translate_pack_arm64.py`) mapping the i386m pack's 6483
  patterns to AArch64.
- Register map, stack model, memory operands, x87 emulation (software FPU
  stack), div/mod helpers.
- Validate: galaxy/galaxy2/mulcheck/ft2 byte-identical under qemu-aarch64.

### Phase 3 — native vhgame on Apple Silicon
- Splice the arm64 macOS RTM + game; run natively on the M4 (no Rosetta).
- Verify playability + headless output matches x86_64.

## CRITICAL FINDING: the 4GB __PAGEZERO breaks the 32-bit pointer model

macOS arm64 enforces a **fixed 4GB `__PAGEZERO`**:
- `-Wl,-pagezero_size` **malforms the Mach-O** (any non-default value, even for a
  trivial hello — the binary SIGKILLs / dyld rejects it). This is a hard arm64
  constraint, unlike x86_64 where the flag is honored.
- `MAP_FIXED` at a low address fails with `EPERM` (cannot override `__PAGEZERO`).

L.in.oleum stores `pCode` and the isocall target as 32-bit `unit`s, which
requires the code below 4GB. That is **impossible on arm64**.

**Required redesign (affects the RTM and the CPU pack):**
1. Drop the low-4GB mmap; allocate code/workspace at normal 64-bit addresses.
2. The **isocall** must use a 64-bit isokernel address (held in a workspace
   slot as two units, or a code literal) instead of `[pCode + 32-bit-offset]`.
3. `mm_ProcessOrigin` / `mm_ProcessISOcall` become 64-bit (two units) or are
   repurposed.
4. Workspace *offsets* (32-bit displacements relative to WS=x25) are unaffected
   and stay 32-bit.

The pattern translation (register map, stack model, literal-pool slots, x87
emulation) is unchanged in concept; the isocall pattern and the RTM allocation
are the arm64-specific deltas.

## Key technical challenges (in order of risk)

1. **x87 emulation** — every float ISMO must round-trip through a software
   FPU stack; must match x87 semantics (80-bit extended precision, rounding).
2. **Pattern coverage** — 6483 patterns; the div/mul64 helpers and
   pusha/popa emulation need arm64 equivalents.
3. **Stack alignment** — the 4-byte stack model vs AArch64's 16-byte rule.
4. **Performance** — software x87 will be slow; acceptable for correctness
   first, optimize later (or move hot float paths to VFP).

## Container setup (validation harness)

- i686 finch VM (as today): cross `aarch64-linux-gnu-gcc`, `qemu-aarch64-static`.
- Run arm64 exes: `qemu-aarch64-static -L /usr/aarch64-linux-gnu ./prog.exe`.
- Reference outputs: the existing x86_64 test files (`t1/*.bin`).

## Reference material
- `src/linoleum_macos64/` — working x86_64 macOS RTM (Cocoa display).
- `tools/packtool.py`, `translate_pack.py` — pack decode + x86_64 translator.
- `PORTPLAN-MACOS.md` — the x86_64 port roadmap (many notes carry over).
