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
0-3 retain their historical layout; AArch64 reserves four previously unused
slots:

| UI unit | Value |
|---|---|
| 4 | isokernel address bits 0-31 |
| 5 | isokernel address bits 32-63 |
| 6 | code-origin address bits 0-31 |
| 7 | code-origin address bits 32-63 |

An AArch64 call loads and combines UI units 4 and 5, saves `x30` in a
16-byte-aligned frame, and uses `blr`. The isokernel preserves A-E, returns DONE
or FAIL in X, and reloads WS from `pWorkspace` after C because RAMtop growth may
replace the mapping. No legacy 32-bit pointer or code-relative delta is written.

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
indirect forms.

Stack push/pop, unit-count SP adjustment, and immediate-relative stack
load/store cover every canonical immediate, register, direct-workspace, and
indirect-workspace form. One abstract 32-bit Lino stack unit occupies one
16-byte physical SP slot, so arbitrary adjustments and nested generated calls
preserve the AArch64 ABI's alignment while stack-relative values remain 32-bit.

Scalar binary32 negation, magnitude, addition, subtraction, multiplication, and
division move raw IEEE-754 bits between W registers and S0/S1, execute one
single-precision operation, and move the rounded binary32 result back. Register,
direct-workspace, and indirect-workspace left operands are covered; binary right
operands may be immediate, register, direct, or indirect, with the same
source-first loads and memory writeback as the integer slice. The executed fixture
includes ordinary values, the minimum subnormal, overflow to infinity, and signed
zero. This does not yet claim x87-compatible conversions, comparisons, square
root, transcendental operations, exception state, or NaN payload handling.

The slice also covers unconditional/status branches, internal calls, `leave`,
`end`, `fail`, `nop`, and the full-width isocall ABI. It does not yet cover the
remaining floating-point/x87 semantics, display, input, audio, files, sockets,
timing, process commands, Cocoa, Mach-O packaging, signing, or Noctis
integration. Wider instruction coverage and runtime services remain separate
milestones.
