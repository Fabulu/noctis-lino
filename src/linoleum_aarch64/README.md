# Linux AArch64 runtime bridge

This directory contains the first executable AArch64 foundation for Linoleum and
a minimal compiler-owned target for its integer ABI and ordinary scalar binary32
arithmetic. It loads checked appended images, enters hand- or compiler-generated
AArch64 code, and supports a no-service isocall plus safe RAMtop relocation. It is
deliberately not a full RTM; it is not yet a native macOS or Noctis runtime.

The register mapping and the Apple-Silicon `__PAGEZERO` investigation originated
in [PR #10](https://github.com/bammf1/linoleum/pull/10) by Joris van de Donk. The
implementation here is reconstructed around a full-width pointer ABI and does
not retain that prototype's low-address mappings, executable workspace, runtime
code patching, or unsafe growth path.

## ABI checkpoint

Generated code owns these registers:

| Lino register | AArch64 register |
|---|---|
| A | `x19` / `w19` |
| B | `x20` / `w20` |
| C | `x21` / `w21` |
| D | `x22` / `w22` |
| E | `x23` / `w23` |
| X | `x24` / `w24` |
| WS | `x25` |

`x9`-`x17` are temporary registers. `x18` is always reserved because Darwin owns
it. Generated code must not claim the host's remaining callee-saved registers.
The bridge saves and restores `x19`-`x25`, `x29`, and `x30`, and keeps SP aligned
to 16 bytes at every C boundary.

The historical workspace and UI workspace still contain 32-bit units. UI slots
0-3 retain their historical layout; AArch64 reserves eight previously unused
slots:

| UI unit | Value |
|---|---|
| 4 | isokernel address bits 0-31 |
| 5 | isokernel address bits 32-63 |
| 6 | code-origin address bits 0-31 |
| 7 | code-origin address bits 32-63 |
| 8 | scalar-unary helper address bits 0-31 |
| 9 | scalar-unary helper address bits 32-63 |
| 10 | scalar-binary helper address bits 0-31 |
| 11 | scalar-binary helper address bits 32-63 |

An AArch64 call loads and combines UI units 4 and 5, saves `x30` in a
16-byte-aligned frame, and uses `blr`. The isokernel preserves A-E, returns DONE
or FAIL in X, and reloads WS from `pWorkspace` after C because RAMtop growth may
replace the mapping. No legacy 32-bit pointer or code-relative delta is written.
Generated sine and cosine calls reconstruct the separate full-width unary helper
from UI units 8 and 9 and cross the same aligned AAPCS boundary with raw binary32
bits in `w0`; partial remainder and partial arctangent use the binary helper in
units 10 and 11 with raw left/right bits in `w0`/`w1`. All Lino registers and
`x25` remain callee-saved.

## Image and memory contract

The runtime retains the 96-byte `LNLMINIT` paragraph used by existing appenders:
an eight-byte `LNLMInit` marker, 40-byte app name, fourteen little-endian signed
32-bit fields, and the `LNLMIend` marker. The initialized workspace follows the
runtime at `physwsentry`; AArch64 code follows that workspace. The loader requires
positive sizes, an in-range code entry, enough RAMtop for all communication
slots, exact physical boundaries, and a stock-file size representable by the
historical paragraph before it maps code.

Code is RW only while loading and becomes RX before entry. Workspace is always
RW and non-executable. Resizing maps a replacement, copies the surviving units,
zeros every added unit, publishes refreshed full-width pointers, and then unmaps
the old page-rounded region. Mappings use normal 64-bit addresses and never
require `MAP_FIXED` or a below-4-GB allocation.

## Build and test

On an AArch64 Linux host or a machine with the cross toolchain:

```sh
./src/linoleum_aarch64/build.sh
python3 tests/test_aarch64_runtime.py --require-execution -v
```

The default compiler is `aarch64-linux-gnu-gcc`; set `CC`, `BUILD_DIR`, or
`OUTPUT` to override it. The result is a static non-PIE Linux ELF so
`qemu-aarch64` can execute it without a guest sysroot. The required-execution
test bootstraps `compiler114m.txt` to its Linux fixpoint, packs this runtime as
an AArch64 SYS target, compiles a real Lino source with `--cpu:aarch64`, and
executes that compiler-produced image. Programmatically encoded fixtures remain
independent ABI and malformed-image oracles; no generated executable is tracked.

## Deliberate omissions

The compiler-owned AArch64 emitter covers fixed-width 32-bit integer moves and
both direct and canonical indirect workspace loads/stores. Indirect operands use
A-E as a 32-bit workspace-unit index plus a fixed unit displacement, scale the
effective index by four from `x25`, and leave the pointer register unchanged.
Wrapping addition, subtraction, low-word multiplication, signed/unsigned
division and remainder, bitwise operations, logical/arithmetic shifts, variable
rotates, bitwise inversion, wrapping negation, and wrapping signed magnitude
accept their canonical register, direct-workspace, and indirect-workspace forms;
binary right operands may be immediate, register, direct, or indirect. Memory
left operands are written back. Equality, signed/unsigned comparisons, and
bit-test branches accept the same binary input combinations without writeback.
Source operands are loaded before memory destinations, including aliasing
indirect forms. Tracked q73 value exchange covers all 121 register, direct, and
canonical indirect operand pairs. Both old memory values are loaded before the
first write, the right effective index is recomputed for its writeback, and an
indirect address is fixed before changing an aliased pointer register such as
`A <> [A]`.

Tracked q69/q70 split division also covers all 121 pairs. It captures both old
values and any memory indexes, uses `UDIV` or `SDIV` plus `MSUB`, writes the
quotient to the left operand and the remainder to the right, and preserves the
tracked alias ordering: one aliased register retains the quotient while one
aliased memory cell retains the later remainder. The generated image exercises
all nine register/direct/indirect class pairs, both pointer-alias directions,
and positive, negative, and high-bit unsigned cases. Division by zero and signed
`0x80000000 / -1` still differ from the trapped x86 behavior and are not claimed
compatible.

The tracked x64 pack continues beyond the i386 pack's q73 endpoint with q74/q75
split multiplication. AArch64 supports those 121-pair unsigned and signed forms
through the same captured-value/address path, using `UMULL` or `SMULL`, returning
the low product to the left and high product to the right. Aliased registers keep
the final low half and aliased memory keeps the later high half, as in the x64
records. The generated image executes high-bit unsigned and negative signed
products, register and memory destinations, both pointer-alias directions, and
both alias write orders.

Stack push/pop, unit-count SP adjustment, and immediate-relative stack
load/store cover every canonical immediate, register, direct-workspace, and
indirect-workspace form. One abstract 32-bit Lino stack unit occupies one
16-byte physical SP slot, so arbitrary adjustments and nested generated calls
preserve the AArch64 ABI's alignment while stack-relative values remain 32-bit.
Tracked q71/q72 mirror the eight-slot `PUSHA`/`POPA` layout as
A,C,D,B,saved-SP,X,E,WS. They reserve 128 aligned physical bytes, retain WS as a
full-width pointer, and deliberately ignore the saved-SP slot while restoring.
The generated image rewrites the exposed stack slots before pop-all, then proves
A-E and the DONE value in X were restored and direct workspace access still uses
the restored WS.

Scalar binary32 negation, magnitude, addition, subtraction, multiplication, and
division move raw IEEE-754 bits between W registers and S0/S1, execute one
single-precision operation, and move the rounded binary32 result back. Register,
direct-workspace, and indirect-workspace left operands are covered; binary right
operands may be immediate, register, direct, or indirect, with the same
source-first loads and memory writeback as the integer slice. The executed fixture
includes ordinary values, the minimum subnormal, overflow to infinity, and signed
zero. For tracked q47, the emitter also recognizes zero divided by zero and
infinity divided by infinity after ignoring operand signs, and replaces those
masked-invalid results with the x87 real-indefinite bits `0xFFC00000`. Register,
direct, and indirect execution cover `0/0`, positive infinity divided by negative
infinity, and negative zero divided by zero; finite nonzero division by zero
continues to use the native signed-infinity result.

Signed conversion instructions cover register, direct, and indirect sources and
destinations. `SCVTF` plus binary32 writeback matches the historical `FILD`/`FSTP`
boundary under round-to-nearest, including 16,777,217 rounding to 16,777,216;
`FCVTNS` matches in-range round-to-nearest `FISTP`, including positive and
negative half-way values. A raw-input range repair maps positive and negative
out-of-range values, infinities, and NaNs to the masked-x87 integer-indefinite
value `0x80000000`, while retaining the valid `-2^31` boundary. The generated
image executes same-register quiet-NaN conversion, direct overflow, indirect
infinity, the largest valid positive binary32 input, and a negative out-of-range
input. Floating exception flags and traps remain outside this compatibility
boundary.

All six floating comparisons use `FCMP` after raw bit transfers. Their branches
retain the tracked x87 `FCOMP`/`FSTSW`/`SAHF` unordered behavior: equality, lower,
and lower-or-equal accept an unordered quiet-NaN comparison, while inequality,
greater, and greater-or-equal reject it. The generated-image fixture executes both
ordered and unordered cases.

Scalar square root uses `FSQRT S0,S0` between the same raw W/S transfers and
binary32 writeback. Register, direct, and indirect forms execute exact-square,
minimum-subnormal, and negative-zero cases in the generated image. A raw-input
repair additionally maps negative finite values and negative infinity to the
masked-x87 real-indefinite bits `0xFFC00000` without changing negative zero; the
fixture executes `sqrt(-1)`, `sqrt(-infinity)`, and indirect `sqrt(-4)`.
Signaling-NaN behavior, ordinary NaN payload equivalence, and floating exception
state remain open.

Tracked q29/q30 records load a binary32 operand, execute x87 `FSIN` or `FCOS`,
and spill once to binary32. AArch64 has no scalar trigonometric instruction, so
the emitter passes the raw bits and an operation tag through the full-width
runtime helper; the Linux bridge applies `sinf` or `cosf` and returns raw bits.
The compiler-produced image executes sine and cosine of 1.0, sine of negative
zero, and cosine of zero across register, direct, and indirect writeback forms.
This is bounded ordinary-value coverage, not a claim that libm reproduces x87
range reduction, large-argument C2 behavior, NaN payloads, or exception state.

Tracked q66/q67 records load the right operand before the left, then execute one
x87 `FPREM` or `FPATAN`. The binary helper therefore applies `fmodf(left, right)`
for bounded cases where `FPREM` completes in one step, or
`atan2f(right, left)` to retain the observed `FPATAN` operand order. Register,
direct, and indirect writeback executes positive and negative remainders plus
first-quadrant, axis, and zero-angle arctangents. Large exponent differences
that make x87 `FPREM` return a partial result, exceptional divisors, signed-zero
quadrants, NaNs, and exact exception-state compatibility remain open.

The slice also covers unconditional/status branches, internal calls, `leave`,
`end`, `fail`, `nop`, and the full-width isocall ABI. It does not yet cover the
remaining floating-point/x87 semantics, display, input, audio, files, sockets,
timing, process commands, Cocoa, Mach-O packaging, signing, or Noctis
integration. Wider instruction coverage and runtime services remain separate
milestones.
