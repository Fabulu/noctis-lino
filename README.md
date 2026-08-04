# Noctis IV in L.in.oleum

An attempt to port [Noctis IV](https://en.wikipedia.org/wiki/Noctis_(video_game))
to **L.in.oleum**, the cross-platform assembly language its own author wrote.

Alessandro Ghignola wrote both. He built L.in.oleum specifically to write
Noctis V in it, then abandoned both projects. This repository is an attempt to
finish what the language was made for.

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
python tests\run_all.py           # everything, about 80 seconds
python tests\run_all.py galaxy    # just the tests matching "galaxy"
```

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

Upstream content is under the WTOF Public License — see `wpl.htm`. Redistribution
is permitted; selling for profit and modification are not.
`src/linoleum_linux32/` is GPLv2 (Peterpaul Klein Haneveld).

Files added by this project are our own work. Noctis IV itself is
Copyright © 1996–2002 Alessandro Ghignola, also under WPL, and distributing
modified versions requires his authorisation.
