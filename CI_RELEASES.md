# CI and tagged releases

The repository has three deliberately separate GitHub Actions paths.

- `.github/workflows/windows-release.yml` runs regression checks and packages
  the committed executable on GitHub-hosted Windows runners. It runs for pull
  requests and master pushes, but it never claims to compile L.in.oleum source
  and it cannot publish a release.
- `.github/workflows/tagged-release.yml` runs for every pushed `v*` tag. It
  validates the exact revision on hosted Windows, packages the versioned i386
  executable, records hashes and provenance, and publishes a GitHub prerelease.
- `.github/workflows/source-release.yml` is manually dispatched. It deletes
  stale game artifacts, compiles the checked-out `work/vhgame.txt` on an
  interactive Windows runner, verifies the fresh i386 PE, and uploads a
  source-build artifact with source, compiler, executable, and commit hashes.

The split exists because `compiler114m.exe` accepts unattended build arguments
but its historical Win32 host runtime still initializes a graphical display and
remains resident after emitting the artifact. `lino_build.ps1` already supplies
the arguments, detects a settled artifact and error log, and terminates that
process. The missing CI requirement is a real logged-in Windows desktop, not UI
click automation. Hosted GitHub runners can test and package the committed
product, but they cannot honestly claim to compile it from L.in.oleum source.

The tagged release workflow is therefore automated and usable now. Its
provenance record says that the executable was compiled locally before the tag,
then tested and packaged on GitHub-hosted Windows. The manual interactive build
is the stricter clean-source provenance path when a dedicated runner is online.

## One-time runner setup

Use a dedicated Windows 10 or 11 VM or spare machine with no personal files,
SSH keys, cloud credentials, or access to unrelated internal services.

1. In the GitHub repository, open Settings, Actions, Runners, then choose New
   self-hosted runner and Windows x64.
2. Install the current runner under `C:\actions-runner`. The Node 24 actions in
   these workflows require runner version 2.327.1 or newer.
3. Run GitHub's displayed `config.cmd` command and add the custom label
   `lino-gui`. Do not install the runner as a Windows service.
4. Log into the dedicated account and launch `C:\actions-runner\run.cmd`
   directly. The source workflow rejects Session 0 so a service configuration
   fails visibly instead of hanging the compiler.
5. If automatic startup is wanted, use the account's Startup folder or a Task
   Scheduler logon trigger with "Run only when user is logged on". Disable sleep
   and hibernation. Keep the desktop session unlocked through a VM console.

GitHub warns that public-repository pull requests can persistently compromise a
self-hosted runner. This project therefore never routes pull requests to the
runner. The compile job has only `contents: read`, checkout does not persist its
token, and the runner uploads an Actions artifact only. A separate ephemeral
GitHub-hosted job receives `contents: write` and publishes tagged releases.

Official references:

- [Adding a self-hosted runner](https://docs.github.com/en/actions/how-tos/manage-runners/self-hosted-runners/add-runners)
- [Secure use of self-hosted runners](https://docs.github.com/en/actions/reference/security/secure-use)

## Creating a build or release

For an unpublished source-build artifact, start the VM, confirm that `run.cmd`
reports it is listening, then manually run the `Interactive source build`
workflow. The compile job produces:

- `Noctis-IV-windows-x86.zip`
- `Noctis-IV-windows-x86.zip.sha256`
- `Noctis-IV-windows-x86.source.txt`

For a GitHub prerelease, first build and commit the current executable locally,
make sure master CI is green, then push an annotated version tag:

```powershell
git tag -a v0.1.0 -m "Noctis IV L.in.oleum port v0.1.0"
git push origin v0.1.0
```

The tag launches hosted validation, packaging, and publication. If validation
or packaging fails, no release is created. If the tag already has a release,
rerunning the workflow replaces its three generated assets. The release remains
a prerelease while the game is under active parity development.

As of 2026-08-11 no self-hosted runner is registered for this repository. This
only blocks the optional clean-source rebuild artifact. It does not block
tests, tagged package builds, or GitHub prerelease publication.
