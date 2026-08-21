# CI and tagged releases

## Current release boundary

Beta 21 was the first release whose Windows executable was compiled from tagged
Lino source on a GitHub-hosted runner. Beta 22 is the first dual-platform
release and the first public macOS x86_64 Finder application. Its tagged graph
published six generated assets only after both platform packages passed:

```text
Noctis-IV-windows-x86.zip
Noctis-IV-windows-x86.zip.sha256
Noctis-IV-windows-x86.provenance.txt
Noctis-IV-macos-x86_64.zip
Noctis-IV-macos-x86_64.zip.sha256
Noctis-IV-macos-x86_64.provenance.txt
```

CI does not repackage a committed `work/vhgame.exe` and does not depend on a
self-hosted desktop for either release executable. The protected historical
Linux compiler remains the trust anchor. On current Linux it loads its Lino
application into heap memory and jumps to it, so the build invokes the unchanged
binary through `setarch -X`, restoring the executable-heap process personality
expected by the historical runtime. It then:

1. compiles `main/lib/gen/compiler114m.txt` with the protected compiler and
   protected i386 CPU pack;
2. uses the generated compiler and target CPU pack to rebuild itself;
3. requires a byte-identical self-hosting fixpoint; and
4. uses that fixpoint compiler to build the production target.

The compatibility boundary and 32-bit glibc/X11 dependencies belong only to the
compiler host. They do not alter the protected compiler, Lino source, or release
executables.

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
- `.github/workflows/tagged-release.yml` repeats the protected-source regression,
  Windows source build/package, and the complete macOS build/package graph for
  every pushed `v*` tag. Publication needs both platform package jobs, so no
  partial public release is created when either side fails.
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
for the actual inputs. The record binds:

- commit, target, root game source, and compile script;
- Linux dependency installer and protected bootstrap compiler;
- extended compiler source, `bits` and `bytes` libraries, and bootstrap script;
- bootstrap i386/Linux and target i386m/Win32 packs;
- generated fixpoint compiler; and
- final i386 PE.

The package job requires every field, verifies the downloaded compiler and PE,
and copies the record unchanged. The ZIP contains `MANIFEST.sha256` for every
payload file. The adjacent checksum covers the archive itself.

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

## Independent release download audit

A workflow is not considered fully audited merely because it is green. After
publication, download all six public assets into an empty directory and verify:

- each adjacent checksum has the expected syntax, filename, and archive hash;
- neither ZIP has duplicate, absolute, escaping, symlink, or unexpected paths;
- every internal manifest entry exists exactly once and hashes correctly;
- packaged executables match their provenance records and target architectures;
- Windows PE and macOS Mach-O headers have the expected section/segment shape;
- the macOS nested signatures remain strict-valid after public download and
  extraction;
- the signed game retains the exact normalized geometry and appended Lino
  payload recorded by package provenance; and
- release assets correspond to the immutable tagged commit.

Beta 22 completed that public download audit at commit
`ccd7aecdcd4a9692b5c9890268e810f877598b7d`. The Windows archive contained the
expected 14 files and a four-section i386 PE. The Mac archive contained the
expected 20 files; reverse-normalizing the downloaded signed game reproduced
both its recorded normalized hash and original compiler-output hash, while the
complete appended Lino payload and 7/7 NIVGEN record remained exact.

GitHub's own Actions/release-asset digest is additional evidence, not a
replacement for the adjacent checksums and internal manifests.

## Creating a prerelease

Require green master Windows, Intel-macOS runtime, and Apple-Silicon Rosetta
package workflows. Review `RELEASE_NOTES.md`, confirm that it identifies ad-hoc
macOS signing and the lack of notarization, then create the next annotated beta
tag (beta 23 after the published beta 22):

```sh
git tag -a v0.1.0-beta.23 -m "Noctis IV Lino beta 23"
git push origin v0.1.0-beta.23
```

The tag launches both complete build graphs and publishes only after all jobs
pass. If a release already exists for the tag, a manual rerun replaces only the
six generated assets. Do not move or recreate a published tag to hide a failure;
fix master and use the next version. Complete the independent public download
audit before calling the release verified.

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
