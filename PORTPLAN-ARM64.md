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
## ISOCALL mechanism (reverse-engineered, the arm64 delta)

The compiler emits every `isocall;` as the SAME three shared pack patterns:

    mov X, [WS + iso_off]    ; x64: 8b af <disp32>   (X=ebp, WS=rdi)
    add X, [WS + 0]          ; x64: 03 2f            (mm_ProcessOrigin = slot 0)
    call X                   ; x64: ff d5            (call rbp)

Verified in compiled x64 output (bare `isocall;` program), ending with the
DONE pattern (`bd 656e6f64; c3`):

    8b af 04 00 00 00   mov ebp,[rdi+4]      ; X = [WS+iso_off]
    03 2f               add ebp,[rdi]        ; X += [WS+0] (pCode)
    ff d5               call rbp             ; call isokernel

The RTM sets:
    pWorkspace[mm_ProcessOrigin]  = (unit)pCode;                  (slot 0)
    pUIWorkspace[mm_ProcessISOcall] = (uint32)(isokernelP-pCode); (slot 1)

So X = (isokernel-pCode) + pCode = isokernel, as a 32-bit value. This works
because on x86_64 BOTH pCode (low MAP_FIXED mmap at 0x10000000) AND the RTM
(isokernel at ~0x40xxxx, ELF loads at 0x400000; Mach-O __TEXT at 64MB via
-pagezero_size) live below 4GB.

On arm64 macOS neither can be below 4GB (fixed 4GB __PAGEZERO; kernel SIGKILLs
shrunk-pagezero binaries), so the 32-bit X can never equal isokernel.

### ARM64 ISOCALL DESIGN - load-time patch

1. translate_pack_arm64.py must emit the isocall sequence as a FIXED byte
   pattern (deterministic register/scratch usage):
       ldr w24,[x25,#iso_off]        ; mov X,[WS+iso_off]
       ldr w9,[x25,#0]               ; add X,[WS+0] operand
       add w24,w24,w9
       blr x24                       ; call X
2. The RTM (rtm.c, arm64 build), after loading the code, SCANS for this
   pattern and replaces each occurrence with a direct 64-bit call to the
   runtime isokernel address (ASLR-safe, same 16-byte size):
       movz x24, #isok&0xffff
       movk x24, #(isok>>16)&0xffff, lsl #16
       movk x24, #(isok>>32)&0xffff, lsl #32
       blr x24
   The scan key is the fixed bytes of `ldr w24,[x25,#ISO_OFF]` + the following
   ldr/add/blr; ISO_OFF (mm_ProcessISOcall byte offset) is a constant, so the
   encoding is identical at every isocall site in every program.

The code section is RW (mmap), so patching in place works. The patch is done
once at startup before pCodeEntry runs.

Required new patterns in translate_pack_arm64.py (currently returning None):
   - mov X,[WS+disp32]  (nonzero disp; ldr w24,[x25,#disp] when disp<=0xfff,
     else add x9,x25,#imm via movz/movk then ldr)
   - add X,[WS+disp32]  (ldr operand + add)
   - call X             (blr x24)
## linoleum() x30 bug (FIXED, validated)

`linoleum()` in isokernel.s did `blr x9` into the application but never
saved x30 (the return-to-main link).  The game's final `ret` therefore
jumped back to linoleum's post-blr address forever.  The saved/restored
pair was `stp/ldp x25,x29` — x30 was missing.  Fixed to `stp/ldp x25,x30`.
This was invisible in earlier validation because every arm64 test used
`--headless`, which exits in main() BEFORE linoleum() runs.  Validated: a
bare programme (DONE pattern) now completes ("linoleum returned").

## arm64 isocall: three stacked bugs (FIXED, validated on a bare isocall)

1. The arm64 translation places the pack token AFTER the emitted code
   (unlike x86's inline disp32).  The isocall ends in `call X`, so when
   isokernel returned, execution fell into the trailing token bytes (`udf`).
2. `blr` clobbers x30, so the game's final `ret` looped back into the
   isocall (x86 pushes return addresses on the stack; arm64 uses x30).
3. On macOS the 32-bit computed target can't reach isokernel (>4GB).

The load-time patch in rtm.c replaces each isocall site (28 code + 4 token
bytes, signature = fixed `adr x9,#28; ldr w9,[x9]; add x9,x25,x9;
ldr w24,[x9]; ldr w9,[x25]; add w24,w24,w9; blr x24`) with 32 bytes:

    movz x24,isok&0xffff; movk x24,(isok>>16)&0xffff,lsl#16;
    movk x24,(isok>>32)&0xffff,lsl#32; stp x29,x30,[sp,#-16]!;
    blr x24; ldp x29,x30,[sp],#16; b #8; nop

which preserves the link register and skips the token.  `pCodeSize` is in
UNITS — the scan length is `pCodeSize * sizeof(unit)`.

## Validation status (arm64, qemu-aarch64 Linux)

- trivial (DONE only): completes.  bare `isocall;` program: completes.
- galaxy / galaxy2 / mulcheck: SEGFAULT — their code contains UNTRANSLATED
  x86 patterns (e.g. `c7 87 ...` = mov dword [edi+imm], imm).  The pack
  translation is at ~462/6483 patterns; every pattern a program uses must be
  translated before it can run.  This is the remaining bulk of the work:
  jumps (jcc/loops), call/ret forms, x87 (fld/fstp/fadd/fmul), div helpers,
  pusha/popa, complex [mem] forms.

## Commit notes
- src/linoleum_aarch64/isokernel.s: linoleum preserves x30.
- src/linoleum_aarch64/rtm.c: pCodeEntry non-truncating on arm64;
  arm64_patch_isocalls() load-time rewrite.
- translate_pack_arm64.py: B.build() token-offset bug (adr pointed 8 bytes
  early — corrupts every token-using load); parse_mem has_disp via modrm
  mod==10 (capstone collapses [base+0] to [base]); call reg -> blr;
  no-disp [mem] loads; isocall pattern 150 translates.

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
