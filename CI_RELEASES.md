# CI and tagged releases

## Current release boundary

Beta 21 was the first release whose Windows executable was compiled from tagged
Lino source on a GitHub-hosted runner. Beta 22 added the public macOS x86_64
Finder application, Beta 24 added the separately compiled native
Apple-Silicon application, and Beta 26 completed the compatibility and
verification prerelease line. `v1.0.0` is the first stable release boundary.
The same tagged graph publishes exactly nine generated assets only after all
three platform packages pass:

```text
Noctis-IV-windows-x86.zip
Noctis-IV-windows-x86.zip.sha256
Noctis-IV-windows-x86.provenance.txt
Noctis-IV-macos-x86_64.zip
Noctis-IV-macos-x86_64.zip.sha256
Noctis-IV-macos-x86_64.provenance.txt
Noctis-IV-macos-arm64.zip
Noctis-IV-macos-arm64.zip.sha256
Noctis-IV-macos-arm64.provenance.txt
```

CI does not repackage a committed `work/vhgame.exe` and does not depend on a
self-hosted desktop for either release executable. The protected historical
Linux compiler remains the trust anchor. On current Linux it loads its Lino
application into heap memory and jumps to it, so the build invokes the unchanged
binary through `setarch -X`, restoring the executable-heap process personality
expected by the historical runtime. It then:

1. compiles `main/lib/gen/compiler114m.txt` with the protected compiler and
   protected i386 CPU pack;
2. uses that generated compiler and the target i386m CPU pack for the first
   self-host generation;
3. uses the first i386m generation for a second i386m self-host generation and
   requires those last two outputs to be byte-identical; and
4. uses that fixpoint compiler to build the production target.

The compatibility boundary and 32-bit glibc/X11 dependencies belong only to the
compiler host. They do not alter the protected compiler, Lino source, or release
executables.

All shipping targets consume the same tracked `work/vhgame.txt` /
`work/vhnivgen.txt` closure from `work/` and `main/lib`. A target may select a
different compiler CPU/SYS pack, generated format, runtime, or ABI, but may not
replace or shadow gameplay, renderer, floating-point, library, or other Lino
`.txt` source. The native-closure gate rejects both target-source trees and
alternate production source roots.

## Workflow roles

- `.github/workflows/windows-release.yml` runs on pull requests and master
  pushes. Windows runs the focused gameplay regression, Ubuntu builds the
  extended compiler and production PE from source, and a fresh Windows job
  verifies and packages the transferred PE. The result is the
  `Noctis-IV-windows-x86-snapshot` Actions artifact.
- `.github/workflows/macos-runtime.yml` builds Cocoa and headless x86_64 runtimes
  on Intel macOS. It verifies architecture, macOS 10.15 deployment target,
  expected framework linkage, a hosted x87 `123Fh`/`133Fh` control-word probe,
  package-tool syntax, focused Mach-O normalization tests, and the mutable
  seed-asset set.
- `.github/workflows/macos-rosetta-nivgen.yml` builds both unsigned x86_64
  runtimes on Apple Silicon, records actual toolchain/runtime provenance,
  cross-compiles the production NIVTEST image and game on Ubuntu, and returns to
  Apple Silicon for exact Rosetta and package validation. It uploads a
  development macOS ZIP, checksum, and provenance artifact only after every
  gate below succeeds.
- `.github/workflows/macos-aarch64-runtime.yml` is both the ordinary native
  Apple-Silicon product gate and a reusable tagged package job. It builds a thin
  arm64 runtime on macOS 15, compiles the fixture and full game through the
  compiler-owned AArch64 target, finalizes and signs the exact Mach-O payload,
  runs raw and extracted-package retrace/save/quit smokes, and retains the
  publishable ZIP, checksum, and provenance files.
- `.github/workflows/tagged-release.yml` repeats the protected-source regression,
  Windows source build/package, x86_64 macOS build/package, and native arm64
  product graph for every pushed `v*` tag. Publication needs all three platform
  package jobs, so no partial public release is created when one fails. Exact
  semver tags such as `v1.0.0` create stable releases; supported beta tags retain
  GitHub's prerelease classification.
- `.github/workflows/source-release.yml` remains an optional independent build
  through the historical Win32 compiler on an interactive `lino-gui` runner.
  It is useful as a second compiler-host comparison, but it is not required for
  hosted release production and is not the provenance authority.

Linux dependency installation is shared by the source-build workflows. Mirror
requests and package-manager locks have finite timeouts and retries, and compile
jobs have a 30-minute outer bound rather than occupying a runner indefinitely.

## Windows build and package gates

`build/compile_vhgame_linux.sh` writes
`build/windows-build.provenance.txt` on the Ubuntu host that consumed the bytes.
This prevents a later Windows checkout from substituting CRLF-converted hashes
for the actual inputs. The record hashes canonical `work/vhgame.txt` directly as
`source_sha256` and binds:

- commit, target, root game source, and compile script;
- Linux dependency installer and protected bootstrap compiler;
- extended compiler source, `bits` and `bytes` libraries, and bootstrap script;
- bootstrap i386/Linux and target i386m/Win32 packs;
- generated fixpoint compiler; and
- final i386 PE.

The package job requires every field, verifies the downloaded compiler and PE,
and copies the record unchanged. Before archiving, both ordinary master CI and
the tagged workflow copy the assembled package, invoke `Play Noctis IV.cmd`
from an unrelated working directory on a private inactive desktop, require the
real game's first-frame sentinel and window, quit through the normal save path,
and require exit status zero plus identical package-local v18 `CURRENT.LIN` and
`CURRENT.BAK`. The caller directory and original package must remain unchanged.
The ZIP contains `MANIFEST.sha256` for every payload file. The adjacent checksum
covers the archive itself.

## macOS build and package gates

The macOS build deliberately crosses three hosted environments:

1. **Apple Silicon runtime build.** Build unsigned headless and Cocoa x86_64
   RTMs with a macOS 10.15 deployment target. Record source-tree, runtime,
   toolchain, SDK, host, and commit provenance.
2. **Ubuntu compilation.** Verify each transferred runtime record, bootstrap the
   fixpoint compiler, audit the x64 pack, and compile dedicated NIVTEST and game
   Mach-O outputs. Bind the compiler, packs, scripts, runtimes, source graph,
   complete RTM prefix, output, and intentional historical tail by SHA-256.
3. **Rosetta exactness.** Compile and execute an x86_64 host probe that perturbs
   the x87 control word to `123Fh`, loads `133Fh`, reads both states, and restores
   the incoming word. Then run one production sector through the headless output
   and require all seven authoritative Windows/NIV+ hashes. A runnable process
   alone is not sufficient.
4. **Mach-O normalization.** Parse the thin x86_64 runtime and `LNLMInit`, require
   the original `__LINKEDIT` boundary and spare zero-filled load-command slot,
   and extend only `__LINKEDIT.filesize` and page-aligned `vmsize` over the exact
   appended Lino image before signing.
5. **Signing and structural proof.** Ad-hoc sign the nested game and app. Require
   one `LC_CODE_SIGNATURE`, signature and `__LINKEDIT` termination at EOF,
   unchanged initialization bounds, and byte-exact preservation of the complete
   appended Lino payload. Verify strict nested signatures.
6. **Archive proof.** Write the non-signature app manifest, create the ZIP,
   extract it into a clean directory, and re-verify its manifest, architecture,
   deployment target, framework linkage, plist identity, and strict signatures.
7. **Launcher and Cocoa proof.** Exercise immutable-resource installation and
   repair, preservation of regular mutable `STARMAP.BIN`/`GUIDE.BIN`, rejection
   of non-regular mutable paths, the first actual Cocoa retrace, and AppKit Quit
   through the game's normal Escape/save path. Graceful exit must produce a
   nonempty `CURRENT.LIN`.

The package provenance binds the build records plus the package and launcher
sources, original compiler output, normalized unsigned executable, complete
appended Lino payload, signed executable, manifest, NIVTEST executable/result,
archive, release label, signing mode, deployment target, and pinned external
validation reference. The app is ad-hoc signed, not notarized, and does not claim
a hardened runtime.

### Native Apple-Silicon package

The arm64 route uses no CPU pack. Linux bootstraps the same extended compiler to
its byte-identical i386m fixpoint, then `compiler114m.txt` emits AArch64 words
from compiler IR for the packed native Darwin SYS. The macOS 15 job requires a
thin arm64 image, the normal 4-GiB `__PAGEZERO`, macOS 11.0 deployment target,
complete 32,947-unit service workspace, full-width runtime pointers, and exact
physical workspace/code/stockfile boundaries.

The checked finalizer may extend only `__LINKEDIT` over the appended Lino image,
rounds its VM geometry to 16 KiB, preserves the stock resource suffix, and
allows only the exact ad-hoc signature suffix beyond the recorded application
boundary. Native execution covers the deterministic compiler fixture, checked
GlobalK storage, AudioQueue metadata, the full game's first Cocoa retrace, and
raw plus extracted-package graceful save/quit paths. Package provenance binds
the compiler and source inputs, unsigned and signed executables, preserved Lino
payload, launcher, manifest, architecture, deployment target, bundle identity,
release label, and archive.

## Independent release download audit

A workflow is not considered fully audited merely because it is green. After
publication, download all nine public assets into an empty directory and verify:

- each adjacent checksum has the expected syntax, filename, and archive hash;
- none of the three ZIPs has duplicate, absolute, escaping, symlink, or unexpected paths;
- every internal manifest entry exists exactly once and hashes correctly;
- packaged executables match their provenance records and target architectures;
- the Windows PE and both macOS Mach-O headers have the expected section/segment shape;
- both macOS nested signatures remain strict-valid after public download and
  extraction;
- each signed game retains the exact normalized geometry and appended Lino
  payload recorded by package provenance; and
- release assets correspond to the immutable tagged commit.

Beta 22 completed that public download audit at commit
`ccd7aecdcd4a9692b5c9890268e810f877598b7d`. The Windows archive contained the
expected 14 files and a four-section i386 PE. The Mac archive contained the
expected 20 files; reverse-normalizing the downloaded signed game reproduced
both its recorded normalized hash and original compiler-output hash, while the
complete appended Lino payload and 7/7 NIVGEN record remained exact.

Beta 24 completed the corresponding nine-asset audit at immutable commit
`6cf96146cb21842fa23031d58d5ae5d4e7b26c99`. Tagged run 32595409634 passed every
Windows, x86_64/Rosetta, and native arm64 build, execution, package, and
publication job. A fresh public download then matched all GitHub asset digests
and adjacent checksums; rejected duplicate, absolute, escaping, and symlink ZIP
paths; verified every internal manifest; identified the i386 PE and thin x86_64
and arm64 Mach-O binaries; matched both bundle versions to the tag; and bound all
three provenance records to the tagged commit. The native archive is 23,156,821
bytes with SHA-256
`afa87dae1b4444b1ed4abd3160f3b0f46206540b1fa975f0c9dc604a4abeed47`; its
finalized game also passed the independent exact-signature-suffix validator.

Beta 25 completed the nine-asset public download audit at immutable commit
`70516af7f5d06ea45b3d4f36a75084b9f7a19942`. Tagged run 33329557511 and release
379374071 completed on 2026-08-30. A new empty-directory download matched all
nine GitHub asset digests, all three adjacent checksums, exact safe ZIP
inventories, every internal manifest, the i386 PE32 and thin x86_64/arm64 Mach-O
shapes, bundle identities, deployment targets, and all three provenance records.
The audit also verified every macOS CodeDirectory code-slot hash, ad-hoc/no-
hardened-runtime flags, CodeResources SHA-1/SHA-256 maps and nested-game cdhash requirements,
exact-final-suffix signature/`__LINKEDIT` geometry, the x86_64 appended-Lino
payload hash, the arm64 finalizer contract, and one shared committed Lino source
plus byte-identical game data across the three archives. The archive SHA-256
values are `838c615c7c941bfe953be97221d4367d2d01a39265cdbd34f1d7ecc5f78e52f5`
(Windows x86), `1772dac9e18f1fbafb004c739073dc543eb84961f684bf30f1917024f8115b5b`
(macOS x86_64), and `9981a693b45035375d20a7904e7744d9eb0f1d48f396af9cb52264d5b531abfb`
(macOS arm64).

Beta 26 completed the nine-asset public download audit at immutable commit
`0131fd22c684113ef42cc82f210ba9379477fa68`. Tagged run 33654619311 and release
381412392 completed on 2026-09-02. A fresh empty-directory download matched all
nine GitHub asset digests and all three adjacent checksums, rejected unsafe or
unexpected ZIP inventories, verified every internal manifest, and identified the
i386 PE32 and thin x86_64/arm64 Mach-O binaries. The independent audit also
verified the macOS CodeDirectory slots, signing flags, CodeResources maps and
nested-game cdhash requirements, exact signature/`__LINKEDIT` suffix geometry,
appended Lino payloads, bundle identities and deployment targets, all three
provenance records, one shared committed `work/vhgame.txt`, and byte-identical
game data across platforms. The archive SHA-256 values are
`3af3f3c0ffdc22d26fce89a81c7d2fc15798958ac168b8d03be1a6ed3001dba5`
(Windows x86), `70e4882cdc23bd9ee30f9599631022c43953a9dcc5b64ceba48026a5269f3f3c`
(macOS x86_64), and `74917e8ef2f8bfd93cd8a8f24941a3630bff9ab472216bd1424b92f1910e1719`
(macOS arm64).

GitHub's own Actions/release-asset digest is additional evidence, not a
replacement for the adjacent checksums and internal manifests.

## Creating a stable release

Require green master Windows, Intel-macOS runtime, Apple-Silicon Rosetta
package, and native Apple-Silicon product workflows. Run all three private-
desktop acceptance phases against the exact candidate, review the unique
`## v1.0.0` section in `RELEASE_NOTES.md`, and confirm that it identifies ad-hoc
macOS signing and the lack of notarization. Then create the annotated stable tag
once:

```sh
python tools/release_notes_for_tag.py v1.0.0
git tag -a v1.0.0 -m "Noctis IV Lino v1.0.0"
git push origin v1.0.0
```

An exact semver tag creates a normal GitHub release without `--prerelease`.
Supported beta tags still create prereleases. The tag launches all three complete
build graphs and publishes only after all jobs pass. The publication step requires
exactly the nine canonical assets listed above. If a release already exists for
the tag, a manual rerun preserves its body and replaces only those nine generated
assets; unexpected remote assets stop the rerun rather than being deleted.

Do not move or recreate `v1.0.0` to hide a failure. Fix forward with a new
version. Download all nine public assets into an empty directory and complete the
independent audit before calling the release verified.

Historical beta tags use the corresponding `## Beta N` section and an annotated
tag such as `v0.1.0-beta.26`; Beta 9 through Beta 26 extraction remains covered.

## Optional interactive Windows runner

The optional `source-release.yml` path requires a dedicated Windows 10 or 11 VM
or spare machine with no unrelated credentials or personal files. Register a
current GitHub Actions runner with the `lino-gui` label, launch `run.cmd` from a
logged-in desktop session, and do not install it as a service. The workflow
rejects Session 0 because the historical Win32 compiler initializes a graphical
host and remains resident after writing its output.

Public-repository pull requests never run on this self-hosted machine. The job
has read-only repository permissions, does not persist checkout credentials, and
only uploads an Actions artifact. No self-hosted runner is required for normal
CI or tagged releases.

Official security references:

- [Adding a self-hosted runner](https://docs.github.com/en/actions/how-tos/manage-runners/self-hosted-runners/add-runners)
- [Secure use of self-hosted runners](https://docs.github.com/en/actions/reference/security/secure-use)
