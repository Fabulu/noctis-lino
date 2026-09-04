# Native macOS AArch64 Linoleum runtime

This directory contains the checked runtime for running compiler-owned AArch64
Lino code natively on Apple Silicon. Its stable product boundary links the
shared Cocoa display, input, console, and file services and runs full Noctis
through first retrace and graceful Lino shutdown. The Finder-safe native app package
adds an arm64 launcher, safe per-user data staging, an internal manifest, exact
signature validation, and archive checksum/provenance. The shared AudioQueue service
publishes the historical stereo 16-bit/44.1 kHz PCM ABI and remains optional when
no output device is available. Checked GlobalK dispatch supports iGUI's optional
sleepy-window coordination with 24-unit names, 255-unit values, and per-user atomic
storage. Networking and clipboard integration remain optional service gaps not
reached by the shipping Noctis closure; product retrace, save, quit, package, and
public-download gates are complete.

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

The native app is built by `tools/package_noctis_macos_aarch64.py` from a
finalized game and its recorded build provenance. It emits
`Noctis-IV-macos-arm64.zip`, its SHA-256 file, and package provenance; the hosted
Apple-Silicon gate extracts the archive independently and exercises both first
retrace and graceful shutdown through the launcher.

The immutable stable `v1.0.0` native archive was independently downloaded after
publication. Its SHA-256 is
`561e925bae6ec035e61206371140b7038add8f026bb4ca39ed9b3c92185272f0`;
its exact 18-file inventory and 15-record internal manifest, safe extraction,
thin arm64 structure, bundle version 1.0.0/build 24, complete nested signatures,
16-KiB `__LINKEDIT` geometry, provenance-bound reconstructed unsigned compiler
output, and byte-identical shared game data all passed.

Remaining work is additional hardware/audio-device breadth and optional runtime
services only when a shipping Lino feature makes them reachable. It is not a
missing native port or release-package boundary.
