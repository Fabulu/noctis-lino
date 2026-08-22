# Native macOS AArch64 Linoleum runtime

This directory contains the checked runtime for running compiler-owned AArch64
Lino code natively on Apple Silicon. Its current product checkpoint links the
shared Cocoa display, input, console, and file services and runs full Noctis
through first retrace and graceful Lino shutdown. Audio, networking, GlobalK,
clipboard integration, final app packaging, and product-level playtests remain
deferred.

The register ABI matches the Linux bridge:

- A through E: `x19` through `x23`
- X: `x24`
- workspace: `x25`
- emitter temporaries: `x9` through `x17`
- `x18`: always reserved for Darwin

`unit` and `LNLMINIT` retain their 32-bit and 96-byte disk layouts. UI slots 4
through 11 carry full-width isokernel, code-origin, scalar-unary helper, and
scalar-binary helper pointers. The runtime maps workspace read/write, maps code
read/write only while loading, clears the instruction cache, and then seals code
read/execute. RAMtop changes use a fresh mapping, preserve the common prefix,
zero growth, republish every pointer, and reload `x25` after the C boundary.

The runtime accepts an unsigned compiler-appended image with opaque stockfile
resources after `physappsize`, or the same image followed by one exact ad-hoc
code-signature suffix. It rejects malformed Mach-O load commands, bytes after
the signature, invalid Lino bounds, and a workspace that cannot hold the full
32,947-unit service ABI before executing generated code. Release or CI images
must be finalized and ad-hoc signed after the compiler appends the Lino payload
and stockfile resources.

Build on Apple Silicon (or with an Apple arm64 SDK):

```sh
./src/linoleum_macos_aarch64/build.sh
```

The output is a thin, unsigned arm64 RTM with the normal 4 GiB `__PAGEZERO`.
There is no low-address ABI, fixed mapping, RWX mapping, runtime scanner, or x86
unwind path.

Joris van de Donk's PR #10 first established the A=x19 through WS=x25 mapping
and identified Apple Silicon's 4 GiB `__PAGEZERO` as incompatible with the old
truncated-pointer runtime. This implementation preserves that investigation's
credit while reconstructing the loader and bridge around checked full-width
pointers and W^X mappings.

Open work after this checkpoint includes native audio and remaining optional
services, application packaging, and product-level playtests.
