# CI and tagged releases

## Current release boundary

Beta 21 is the first release whose Windows executable is compiled from the
tagged Lino source on a GitHub-hosted runner. CI does not package a committed
`work/vhgame.exe` and does not depend on a self-hosted desktop to produce the
release artifact.

The protected historical Linux compiler is still the trust anchor. On current
Linux, that compiler loads its Lino application into heap memory and jumps to
it; normal NX policy rejects the jump. The build invokes the unchanged binary
through `setarch -X`, which restores the executable-heap process personality
expected by the historical runtime. It then:

1. compiles `main/lib/gen/compiler114m.txt` with the protected compiler and the
   protected `i386` CPU pack;
2. uses the generated compiler with `i386m` to rebuild itself;
3. requires the two generated compiler images to be byte-identical;
4. uses that fixpoint compiler to compile `work/vhgame.txt` for
   `win32/i386m`; and
5. validates a nonempty, sectioned i386 PE before upload.

The compatibility boundary and 32-bit glibc/X11 dependencies belong to the
compiler host only. They do not alter the protected compiler, the Lino source,
or the released Windows executable.

## Workflow roles

- `.github/workflows/windows-release.yml` runs on pull requests and master
  pushes. A Windows job runs the focused gameplay regression, an Ubuntu job
  builds the extended compiler and production PE from source, and a fresh
  Windows job verifies and packages the transferred PE. The result is the
  `Noctis-IV-windows-x86-snapshot` Actions artifact.
- `.github/workflows/tagged-release.yml` repeats that source build for every
  pushed `v*` tag. It publishes the exact tested ZIP, ZIP checksum, and build
  provenance as a GitHub prerelease. Publication cannot run if regression,
  compilation, provenance verification, or packaging fails.
- `.github/workflows/source-release.yml` remains an optional independent build
  through the historical Win32 compiler on an interactive `lino-gui` runner.
  It is useful as a second compiler-host comparison, but is no longer required
  for hosted release production and is not the release provenance authority.
- `.github/workflows/macos-runtime.yml` builds both Cocoa and headless x86_64
  runtimes on Intel macOS.
- `.github/workflows/macos-rosetta-nivgen.yml` builds the x86_64 runtime on Apple
  Silicon, cross-compiles the production NIVGEN executable on Ubuntu, executes
  it through Rosetta 2, and checks all seven output families against the
  authoritative Windows hashes. A runnable process is not enough: any numerical
  mismatch keeps this workflow red and blocks a macOS release claim.

Linux dependency installation is shared by the source-build workflows. Mirror
requests and package-manager locks have finite timeouts and retries, and compile
jobs have a 30-minute outer bound instead of occupying a runner indefinitely.

## Provenance and package integrity

`build/compile_vhgame_linux.sh` writes
`build/windows-build.provenance.txt` in the Ubuntu compile job. Hashing occurs on
the host that consumed the bytes, so a later Windows checkout cannot substitute
CRLF-converted hashes for the actual Linux inputs. The record includes:

- commit and target;
- root game source and top-level compile script;
- Linux dependency installer;
- protected bootstrap compiler;
- extended compiler source, `bits` and `bytes` libraries, and bootstrap script;
- bootstrap `i386`/Linux and target `i386m`/Win32 packs;
- generated fixpoint compiler; and
- final PE.

The package job requires every field, verifies the downloaded compiler and PE
against the Linux record, and copies the record unchanged. The ZIP contains a
`MANIFEST.sha256` covering every payload file, while the adjacent
`Noctis-IV-windows-x86.zip.sha256` covers the archive itself. GitHub also records
an Actions/release-asset digest.

A release is not considered verified merely because its workflow is green.
After publication, download the public assets into an empty directory, verify
the ZIP checksum, reject duplicate or escaping archive paths, verify every
manifest entry, compare the packaged PE with the provenance hash, and inspect
the PE machine and section table. This independent download check is part of the
release procedure.

## Creating a prerelease

First require green master regression and source-package jobs, review the
release notes, and use the next annotated beta tag:

```sh
git tag -a v0.1.0-beta.21 -m "Noctis IV Lino beta 21"
git push origin v0.1.0-beta.21
```

The tag launches compilation, packaging, and publication. If any prerequisite
fails, no GitHub release is created. If a release already exists for the tag, a
manual rerun replaces only the three generated assets. Do not move or recreate a
published tag to hide a failure; fix master and use the next version.

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
