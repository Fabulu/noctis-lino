# macOS x86_64 port status and ARM64 plan

## Goal and current boundary

The first macOS target is complete at the technical release boundary: the
Noctis IV Lino program is compiled into a native x86_64 Mach-O, hosted by Cocoa
and AudioToolbox, assembled as a Finder application, ad-hoc signed, and tested
end to end on Apple Silicon through Rosetta 2. The same x86_64 runtime builds on
Intel macOS. Native ARM64 remains a separate future port.

The compiler bootstrap remains Linux-hosted. Windows is not part of the macOS
build chain:

```text
protected i386 Linux compiler
  -> compiler114m bootstrap and byte-identical self-hosting fixpoint
  -> x64 CPU pack + macOS SYS pack
  -> Noctis-IV.game and headless nivtest Mach-O images
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

### Finder application and mutable state

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

1. parse the complete thin little-endian x86_64 Mach-O and the unique
   `LNLMInit` paragraph;
2. require `__LINKEDIT` to end at the original runtime boundary and to be the
   final file-backed and virtual-memory segment;
3. require 4 KiB page geometry and a zero-filled 16-byte load-command slot;
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

The release graph deliberately spans three hosts:

1. Apple Silicon builds unsigned headless and Cocoa x86_64 runtimes and records
   the actual Xcode, SDK, compiler, deployment target, host, and runtime hashes.
2. Ubuntu verifies that provenance, reaches the compiler fixpoint, and compiles
   the production game and dedicated NIVTEST image.
3. Apple Silicon verifies transferred provenance, runs the production sector
   through Rosetta, and requires all seven authoritative hashes.
4. Packaging normalizes and signs the app, verifies its non-signature manifest,
   extracts the ZIP, re-verifies signatures and manifest, exercises launcher
   repair/preservation/rejection behavior, reaches the first real Cocoa retrace,
   and exits through the normal Escape path with a nonempty `CURRENT.LIN`.
5. The release publishes the ZIP beside an archive checksum and a provenance
   record binding the source build, runtimes, compiler, original executable,
   normalized executable, unchanged Lino payload, signed executable, launcher,
   manifest, NIVTEST evidence, and archive.

The exact Rosetta fixture is:

```text
surf=390A2CCB  atmo=114562E8  pal=26961E4A
hm=97022FD7    oc=22913F4E    stex=0D52F001  sky=1E308D29
```

The first complete development archive passed these gates at commit
`9fbc1e62870e62f34f98775a8dd01e6af5894957` and was independently downloaded
and audited. A development Actions artifact is evidence, not a public release;
only a successful tagged workflow creates public release assets.

## Remaining macOS work

### Native ARM64

ARM64 requires a new AArch64 CPU pack, an ARM64 IsoKernel register bridge, and an
ARM64 runtime. It must reproduce the same language-level arithmetic, conversion,
branch, status, and consumer-boundary behavior before it can replace the x86_64
fallback. Rosetta 2 remains the supported Apple Silicon route until that work is
complete.

### Distribution hardening

Developer ID signing, notarization, and hardened-runtime distribution require
appropriate Apple credentials plus a defensible executable-memory entitlement.
They must be added without changing or concealing the historical self-loading
boundary. Until then, release notes must continue to say that the app is ad-hoc
signed and not notarized.

### Additional coverage

The end-to-end application smoke currently runs on Apple Silicon through Rosetta
2, while Intel CI builds the Cocoa and headless runtimes. A direct Intel package
play smoke would add host breadth. It is not a substitute for Rosetta numerical
checks or for future native ARM64 exactness.
