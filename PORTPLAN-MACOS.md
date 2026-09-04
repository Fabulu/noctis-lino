# macOS x86_64 and arm64 port status

## Goal and current boundary

Both macOS targets are complete at the stable technical release boundary. The
shared Noctis IV Lino program is compiled separately into thin x86_64 and arm64
Mach-O games, hosted by Cocoa and AudioToolbox, assembled as Finder
applications, ad-hoc signed, and tested end to end on Apple Silicon. The x86_64
app runs on Intel directly and on Apple Silicon through Rosetta 2; the arm64 app
runs natively on Apple Silicon.

The compiler bootstrap remains Linux-hosted. Windows is not part of the macOS
build chain:

```text
protected i386 Linux compiler
  -> compiler114m bootstrap and byte-identical self-hosting fixpoint
  -> x64 or AArch64 CPU pack + matching macOS SYS pack
  -> x86_64 or arm64 Noctis-IV.game (plus headless NIVTEST where applicable)
  -> Apple package, signature, archive, checksum, and provenance
```

L.in.oleum is a native cross-compiler, not a VM. Each output has this historical
shape:

```text
[Mach-O runtime][initialized Lino workspace][Lino machine code][stock/compiler tail]
```

The CPU pack is the code generator. The SYS pack supplies the platform runtime.
Ordinary game source remains portable Lino; Cocoa, AudioToolbox, filesystem,
memory-mapping, and signing concerns stay below the language boundary.

## Completed phases

### Linux bootstrap and x86_64 code generation

- Current Linux hosts run the protected i386 compiler with its required 32-bit
  glibc/X11 dependencies and an explicit `setarch -X` executable-heap boundary.
- `compiler114m` is bootstrapped from tracked source and must reach a
  byte-identical self-hosting fixpoint before it can compile a release output.
- The x64 CPU pack implements the Lino instruction surface while retaining the
  32-bit unit and address model. Its auditor covers every floating branch and
  verifies the flag-preserving stack restores required under Rosetta.
- The Linux build scripts bind each output to the complete runtime prefix,
  compiler, CPU/SYS packs, source inputs, and intentional historical trailer by
  SHA-256 provenance.

### macOS x86_64 runtime

- `src/linoleum_macos64` supplies a thin x86_64 Mach-O runtime with a macOS 10.15
  deployment target.
- The Cocoa host provides a resizable native window, aspect-correct logical
  pointer mapping, fullscreen, keyboard/text input, clipboard access, and stable
  immutable framebuffer snapshots.
- AudioToolbox AudioQueue output provides stereo signed 16-bit PCM at 44.1 kHz.
- Runtime code, workspace, and IsoKernel-visible buffers are mapped below the
  Lino 32-bit address ceiling without destructive `MAP_FIXED` replacement.
  Workspace growth maps, copies, clears, and unmaps explicitly.
- GlobalK data uses `~/Library/Application Support/Linoleum/GlobalK`, retains a
  read fallback for the historical `~/linoleum/.k` location, and writes through
  same-directory temporary files plus `fsync` and atomic rename.
- A separate headless build runs NIVGEN and other deterministic console jobs
  without linking Cocoa or AudioToolbox.

### Native macOS arm64 runtime

- `src/linoleum_macos_aarch64` supplies the thin arm64 runtime and compiler-owned
  AArch64 target used by the stable Apple-Silicon package, with a macOS 11.0
  deployment target and the normal 4-GiB `__PAGEZERO`.
- Lino registers occupy x19 through x25 while Darwin's x18 remains reserved.
  Full-width runtime, code-origin, and scalar-helper pointers cross the 32-bit
  Lino workspace through checked communication slots; generated procedure values
  remain code-relative.
- Workspace remains read/write and non-executable. Code is writable only while
  loading, its instruction cache is cleared, and it is sealed read/execute before
  entry. Growth remaps safely and republishes every full-width pointer.
- The shared Cocoa services provide resizing, fullscreen, logical pointer and
  keyboard input, files, captures, focus handling, and graceful save/quit.
  AudioQueue supplies the historical PCM ABI, and checked GlobalK storage covers
  the optional iGUI coordination path.
- Hosted Apple-Silicon execution proves the compiler-owned fixture and complete
  Noctis game above 4 GiB, first Cocoa retrace, GlobalK and audio metadata, and
  raw plus freshly extracted package save/quit behavior.

### Finder applications and mutable state

The package has this boundary:

```text
Noctis IV.app/
  Contents/MacOS/Noctis-IV       Finder-safe launcher
  Contents/MacOS/Noctis-IV.game  compiled Lino game
  Contents/Resources/            immutable assets and evidence
```

The launcher installs runtime data under:

```text
~/Library/Application Support/Noctis IV
```

An absolute `NOCTIS_DATA_DIR` override exists for automation. Immutable assets
are repaired when missing or byte-different. Existing regular `STARMAP.BIN` and
`GUIDE.BIN` files are preserved because they contain player additions. Mutable
seed paths that are directories, symlinks, or other non-regular objects are
rejected. Window close and AppKit Quit repeatedly inject complete Escape
press/release intervals until the game reaches its normal save-and-shutdown
path; they do not terminate around Lino cleanup.

### Mach-O normalization and signing

The historical compiler appends Lino bytes after the runtime's original
`__LINKEDIT` segment. Apple `codesign --strict` correctly rejects that layout
because bytes exist outside every segment. Packaging therefore performs one
narrow normalization before signing:

1. parse the complete thin little-endian x86_64 or arm64 Mach-O and the unique
   `LNLMInit` paragraph;
2. require `__LINKEDIT` to end at the original runtime boundary and to be the
   final file-backed and virtual-memory segment;
3. require the target's exact page geometry and a zero-filled 16-byte
   load-command slot (4 KiB for x86_64, 16 KiB for arm64);
4. extend only `__LINKEDIT.filesize` and page-aligned `__LINKEDIT.vmsize` over
   the complete unsigned historical file; and
5. prove that no other byte changed.

Ad-hoc codesign then adds one `LC_CODE_SIGNATURE` and appends its signature.
Post-sign validation requires the signature and `__LINKEDIT` to end at EOF and
proves byte-exact preservation of the complete appended Lino payload. The nested
game and outer app signatures are checked before and after ZIP extraction.

This is ad-hoc signing, not Developer ID signing or notarization. Hardened
runtime is not enabled because the historical self-loading execution model
requires an executable-memory entitlement that is not currently available.
Users may therefore need to approve the first launch in macOS Privacy & Security.

## Release verification

The release graph keeps compiler and runtime provenance explicit across its hosts:

1. macOS hosts build the exact x86_64 and arm64 runtime inputs and record the
   actual Xcode, SDK, compiler, deployment target, host, and runtime hashes.
2. Ubuntu verifies transferred provenance, reaches the compiler fixpoint, audits
   the selected CPU pack, and compiles each production game from the same tracked
   Lino closure.
3. Apple Silicon runs the x86_64 production sector through Rosetta and requires
   all seven authoritative NIVGEN hashes; the native graph executes the
   compiler-owned AArch64 fixture and full Noctis game with all runtime pointers
   above 4 GiB.
4. Each package normalizes and signs its app, verifies its non-signature
   manifest, extracts the ZIP, re-verifies signatures and manifest, exercises
   launcher repair/preservation/rejection behavior, reaches a real Cocoa retrace,
   and exits through the normal Escape path with a nonempty `CURRENT.LIN`.
5. Stable publication waits for Windows and both Mac graphs, then publishes one
   ZIP, checksum, and provenance record per platform: exactly nine assets. Mac
   provenance binds the source, compiler, runtime, original and normalized
   images, unchanged Lino payload, signed executable, launcher, manifest,
   architecture, deployment target, bundle identity, and archive.

The exact Rosetta fixture is:

```text
surf=390A2CCB  atmo=114562E8  pal=26961E4A
hm=97022FD7    oc=22913F4E    stex=0D52F001  sky=1E308D29
```

The first complete development x86_64 archive passed these gates at commit
`9fbc1e62870e62f34f98775a8dd01e6af5894957` and was independently downloaded
and audited. Beta 22 then published the first public x86_64 Mac archive. Beta 24
added the independently compiled native arm64 package and expanded tagged
publication to all nine Windows/x86_64/arm64 assets.

Stable `v1.0.0` completed both architecture paths at commit
`38c638af1f2af628b0bd90205d429573e8ce3aa6`. A final 2026-09-04 audit freshly
downloaded all nine actual release assets. The x86_64 archive (20 files, 17
manifest records) has SHA-256
`73bed850987b963ecd6339bff0417595f0d3282ffb9074e959cfb8c4e0efe79e`;
the arm64 archive (18 files, 15 manifest records) has SHA-256
`561e925bae6ec035e61206371140b7038add8f026bb4ca39ed9b3c92185272f0`.
Both passed safe extraction, complete manifests, thin architecture and bundle
metadata, every CodeDirectory and CodeResources slot, nested-game cdhashes,
ad-hoc/non-hardened flags, exact final signature/`__LINKEDIT` geometry, and
reconstruction of the provenance-bound unsigned compiler output. Shared game
data remained byte-identical to the Windows package.

## Remaining macOS work

### Distribution hardening

Developer ID signing, notarization, and hardened-runtime distribution require
appropriate Apple credentials plus a defensible executable-memory entitlement.
They must be added without changing or concealing the historical self-loading
boundary. Until then, release notes must continue to say that the app is ad-hoc
signed and not notarized.

### Additional coverage

The x86_64 end-to-end application smoke runs on Apple Silicon through Rosetta 2,
while Intel CI builds the Cocoa and headless runtimes. A direct Intel package
play smoke would add host breadth. Native arm64 product execution and package
save/quit are already required on Apple Silicon, but additional hardware and
audio-device breadth would strengthen that evidence; neither substitutes for
the Rosetta numerical checks.
