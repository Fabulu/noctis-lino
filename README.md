# Noctis IV in L.in.oleum

[![Windows build and release](https://github.com/Fabulu/noctis-lino/actions/workflows/windows-release.yml/badge.svg)](https://github.com/Fabulu/noctis-lino/actions/workflows/windows-release.yml)

An attempt to port [Noctis IV](https://en.wikipedia.org/wiki/Noctis_(video_game))
to **L.in.oleum**, the cross-platform assembly language its own author wrote.

Alessandro Ghignola wrote both. He built L.in.oleum specifically to write
Noctis V in it, then abandoned both projects. This repository is an attempt to
finish what the language was made for.

## Play the game

The current Windows build is a playable first-person port: walk through the
Stardrifter, use its GOES console, fly to generated star systems, approach and
land on planets, explore their surfaces, return in the capsule, and save your
journey. It opens in a practical 2x window while retaining Noctis's authentic
320x200 software framebuffer; iGUI's size and full-view controls can resize it
without changing simulation or rendering coordinates. From PowerShell in the
repository root, run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\play_noctis.ps1
```

Landing coordinates use the generated globe's local albedo, atmosphere,
weather, and scenario data, so different sites on the same world are visibly
distinct.

The launcher keeps the working directory fixed so the GUI assets, soundtrack,
starmap, and `work\CURRENT.LIN` checkpoint are found consistently. It builds
the game automatically when the executable is absent; pass `-Build` to force a
fresh production build. Clean saves also retain the current validated window
dimensions, so a resized game reopens at the same size.

Essential controls: F10 opens the native GAME menu, W/A/S/D move, Ctrl + W/A/S/D stalks surface birds, right mouse drag or arrow keys look, G or Enter opens GOES,
`NEXT` selects and flies toward a nearby generated star, L approaches and opens
the landing-site selector at standby, arrows choose coordinates, L/Enter descends,
R returns from the capsule, F5 opts into 60 FPS presentation (the original
18.2 FPS mode is the default), F6/F7 save and load, F8 toggles music, `?` or F9 displays
the complete in-game control card, and Esc saves and quits. A valid checkpoint
resumes automatically; verified saves maintain `CURRENT.BAK`, and a damaged
primary recovers visibly from that last-known-good copy. Enter `NEW` in GOES
to start over.

To build a clean, self-contained redistributable play folder with every runtime
asset and a SHA-256 manifest:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\package_noctis.ps1
```

The default output is `dist\Noctis-IV`; the command refuses to merge
with an existing directory so stale files cannot masquerade as bundle content.
Inside the bundle, double-click `Play Noctis IV.cmd`. The relocatable launcher
anchors all relative asset, checkpoint, catalogue, and diagnostic paths to the
bundle even when it is started from an unrelated working directory.

Version tags matching `v*` assemble the checked production payload and runtime
assets in GitHub Actions, then publish the ZIP plus its SHA-256 checksum as a
prerelease. Ordinary pushes and pull requests run the protected-source check,
integrated-game regression, and package assembly without creating a release.
The historical GUI-subsystem compiler cannot run in GitHub's noninteractive
Windows service session, so production source builds remain a local release
step; the exact resulting `work\vhgame.exe` is versioned for reproducible CI/CD.

## Project documentation

- [`HISTORY.md`](HISTORY.md) is the chronological development and release story,
  including the recent Stardrifter, lift, frame-rate, and checkpoint fixes.
- [`PLAYTEST.md`](PLAYTEST.md) is the detailed capability and verification log.
- [`PORTPLAN.md`](PORTPLAN.md) is the technical source of truth and remaining-work
  ledger.
- [`RELEASE_NOTES.md`](RELEASE_NOTES.md) describes the current public beta and
  its known limitations.

## Provenance

The base of this repository is an unmodified clone of
[8l/linoleum](https://github.com/8l/linoleum) — commits `eb25dcb` and `9559333`.

**No upstream file has been modified.** Every commit after `9559333` only *adds*
files. This is deliberate: `main/lib/gen/compiler.txt` is licensed under the WTOF
Public License, which permits consulting, keeping and freely redistributing the
source but forbids changing it — for personal use as well as redistribution —
without the author's authorisation. To see exactly what is ours:

```
git diff 9559333..HEAD --stat
```

## What has been established

L.in.oleum can reproduce Noctis IV's galaxy, bit for bit.

The Feltyrion galaxy has no star table. Every one of its ~78 billion stars is a
pure hash of its sector's integer coordinates — the universe *is* that function.
`work/galaxy.txt` ports it, and its output is byte-identical to both a C
reference extracted from `noctis-iv-lr` and an independent arbitrary-precision
Python implementation, across 343 sectors spanning the galactic origin.

Two details turned out to be load-bearing:

- **The multiply must be signed.** Sector coordinates go negative either side of
  the centre; an unsigned product yields a different high word and therefore a
  different galaxy — one that generates perfectly happily and matches nothing.
  The fragment is `IMUL` (`F7 EB`), not `MUL` (`F7 E3`).
- **L.in.oleum has no 64-bit multiply.** The original folds `edx:eax` back
  together (`edx += eax`) after an `imul`, and the language exposes only the low
  32 bits. Both routes are implemented and verified against each other:
  `work/mulcheck.txt` (portable, four 16×16 partial products) and
  `work/mulcheck2.txt` (a two-byte inline machine-language fragment). They
  produce byte-identical output.

## Layout

| Path | What |
|---|---|
| `docs/`, `main/`, `examples/`, `src/` | upstream, untouched |
| `lino_build.ps1` | drives the compiler non-interactively |
| `work/*.txt` | our L.in.oleum programs |
| `verify_mul.py` | checks the 64-bit multiply against exact arithmetic |
| `noctis-harness/` | C and Python reference implementations + three-way diff |
| `tests/` | regression suite for the galaxy hash and the `*%` instruction |

## Building and testing

The compiler is a GUI-subsystem binary: it never writes to stdout and it lingers
on screen until dismissed. `lino_build.ps1` works around this by detecting the
artifacts it leaves behind and killing it as soon as they appear.

```powershell
powershell -File lino_build.ps1 -Src work\galaxy.txt
```

Success prints `OK <path> <bytes> <seconds>`; warnings are listed but do not
fail the build; `error:` in `errorlog.txt` does.

To reproduce the galaxy-hash result you also need the reference implementations:

```powershell
git clone https://github.com/dgcole/noctis-iv-lr        # de-assembled C++ reference
git clone https://github.com/jorisvddonk/Noctis-IV-Plus # the maintained DOS original

cd noctis-harness
gcc -O2 -o oracle.exe oracle.c && ./oracle.exe   # C ground truth
python oracle.py                                 # independent Python, cross-checks C
# run work/galaxy.exe, copy galaxy.bin here as lino.bin
python compare3.py
```

Those two repositories are deliberately **not** vendored here — they are separate
upstream projects with their own licensing.

### Regression suite

```powershell
python tests\run_all.py           # optional --deep historical/release audit
python tests\run_all.py galaxy    # just the tests matching "galaxy"
```

Routine work uses the smallest relevant regression or smoke check (normally within 10% of
the change's implementation effort). Run the full roster explicitly for a release or deep
audit; the historical timing above is not a standing delivery promise.

Four tests, each also runnable on its own and each carrying a header that says
what it guards and how it would fail:

| Test | Guards |
|---|---|
| `test_toolchain.py` | the extended toolchain is installed, the two copies of `i386m.bin` agree, `main/` is pristine, and every wrong compiler/pack pairing refuses to build |
| `test_galaxy.py` | `work/galaxy2.txt` (the `*%` rewrite) is bit-exact with the `{ F7 EB }` version, a freshly compiled C oracle, and two bignum Python references — plus signedness at the opcode level |
| `test_galaxy_stress.py` | the same arithmetic on coordinates the 343-sector sweep cannot reach, including the ones that make all three cutoff branches fire |
| `test_mulsplit.py` | the `*%` contract `galaxy2.txt` cannot self-test: which half lands in which operand, signed vs unsigned, and which registers survive |

Nothing is graded against a stored `.bin` — every side is rebuilt and re-run on
each invocation, because a stored `.bin` is exactly what goes stale unnoticed.
Each test also builds a deliberately wrong version of its subject and requires
it to *fail*, so a check that has quietly stopped discriminating shows up as a
failure rather than a green tick. Needs `gcc` on `PATH` for the C references.

## Toolchain gotchas

Hard-won; all of these cost real debugging time.

- **`"variables"` vs `"workspace"` is not a style choice.** In `variables`,
  `name = N;` declares a variable initialised to N. In `workspace`,
  `name = N;` allocates an *uninitialised vector of N units* and the name is its
  **address**. So `foo = 0;` in `workspace` allocates nothing, top-of-workspace
  never advances, and every symbol silently collapses onto the same cell. No
  error, no warning — just uniformly wrong values.
- **Do not launch the compiler with PowerShell's `Start-Process`.** It appends a
  trailing space to the argument string, which the compiler folds into the output
  filename, giving `prog.txt .exe`. Use `ProcessStartInfo.Arguments`, which is
  passed verbatim.
- **No path may contain `--`.** See below.

## Bugs found in L.in.oleum

1. **Command-line parser truncates on `--` anywhere.** `copy option` ends a
   value at any two consecutive hyphens, including inside a filesystem path,
   with no check that an option name follows. A path containing `--` silently
   truncates and the build dies reporting `error reading cpu pack` — pointing at
   a component that is perfectly fine. `lino_build.ps1` refuses such paths rather
   than let you chase the phantom.
2. **`main/linux_compiler.bin` is dead on modern systems.** Segfaults at startup,
   before parsing arguments, in every configuration — including with no arguments
   at all.
3. **The relative-address modifier is documented backwards.** For `<+N label>` in
   machine-language fragments the manual gives `label - pc + N`; the compiler
   computes `label - pc - N`, and `+` and `-` behave identically (both subtract).
   The manual's own worked example proves the manual wrong.
4. **The application-name field is not cleared before writing.** The compiler
   writes `strlen+1` bytes over the 40-byte field in the runtime template, so a
   program named `mul64` ships with `mul64\0leum runtime` embedded — a shard of
   the template string `L.in.oleum runtime`.

Documentation drift worth knowing: `readme.htm` says the CPU pack holds 6616
instruction patterns; it holds **6241** (`48 × 6241 + 8` = the exact file size of
`main/cpu/i386.bin`, and the compiler enforces that equality). The manual also
calls the program counter `bcodesize`; it is `bpos`.

## Licence

Noctis IV and the Noctis-derived parts of this port are distributed under the
original WTOF Public License (WPL); the verbatim Noctis licence and credits are
in [`LICENSE.htm`](LICENSE.htm). The WPL permits free redistribution,
forbids charging for the covered work, and does not generally permit modified
versions without the copyright holder's express authorisation. Alessandro
Ghignola authorised this port to proceed on the condition that the original
gameplay is preserved; this repository is published on that basis.

The upstream L.in.oleum compiler has its own WPL notice in [`wpl.htm`](wpl.htm).
`src/linoleum_linux32/` is separately GPLv2 (Peterpaul Klein Haneveld). Those
notices remain scoped to their respective material; no single licence is
claimed for unrelated third-party components.

Noctis IV is Copyright © 1996–2002 Alessandro Ghignola. Portions of the manual
and soundtrack are Copyright © 2001–2002 Ryan J. Bury. See the licence files
before copying or redistributing the project or a packaged build.
