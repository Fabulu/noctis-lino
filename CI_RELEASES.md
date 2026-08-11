# CI and source-built releases

The repository has two deliberately separate GitHub Actions paths.

- `.github/workflows/windows-release.yml` runs regression checks and packages
  the committed executable on GitHub-hosted Windows runners. It runs for pull
  requests and master pushes, but it never claims to compile L.in.oleum source
  and it cannot publish a release.
- `.github/workflows/source-release.yml` first validates the exact revision on
  hosted Windows, then deletes every stale game artifact, compiles the
  checked-out `work/vhgame.txt`, verifies the
  resulting i386 PE, packages it, and records source, compiler, executable, and
  commit hashes. It runs only for `v*` tags or an authorized manual dispatch.

The split exists because `compiler114m.exe` accepts unattended build arguments
but its historical Win32 host runtime still initializes a graphical display and
remains resident after emitting the artifact. `lino_build.ps1` already supplies
the arguments, detects a settled artifact and error log, and terminates that
process. The missing CI requirement is a real logged-in Windows desktop, not UI
click automation.

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
reports it is listening, then manually run the `Source build and release`
workflow. The compile job produces:

- `Noctis-IV-windows-x86.zip`
- `Noctis-IV-windows-x86.zip.sha256`
- `Noctis-IV-windows-x86.source.txt`

For a GitHub prerelease, push a version tag while that runner is online:

```powershell
git tag -a v0.1.0 -m "Noctis IV L.in.oleum port v0.1.0"
git push origin v0.1.0
```

The self-hosted job compiles and uploads the exact tagged revision. Only after
that succeeds does the hosted publish job create or update the GitHub release.
If the runner is offline, the compile job waits without publishing anything.

As of 2026-08-11 no self-hosted runner is registered for this repository. The
workflow and security boundary are ready, but the first real source-built
Actions artifact requires completing the one-time runner registration above.
