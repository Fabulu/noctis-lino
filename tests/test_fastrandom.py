"""GUARDS: fast_random - the OTHER genuine 32x32 -> 64 site in Noctis IV, and
the only unsigned one - is bit-exact under all three multiply backends.

The galaxy hash gets the attention and has three tests of its own. fast_random
has more of the game hanging off it: it seeds every planet surface, every star
name and every terrain feature through roughly 168 call sites, so a wrong
sequence is not a wrong number, it is a different universe that still looks
entirely plausible.

Two details of NOCTIS-0.CPP:1086-1101 carry the whole thing, and both are
pinned here:

  * `db 0x66; mul dx` is MUL, not IMUL. sky and isthere are the other way
    round. This is the reason Mul64u and Mul64s are separate entry points
    instead of one routine with a sign flag - and the negative control below
    builds a backend that gets it wrong, to show the harness would notice.
  * `add al, dl` is an EIGHT-BIT add whose carry is discarded, so only bits
    32..39 of the 64-bit product are ever consumed. Widening it to 32 bits
    produces a different and equally plausible sequence.

WHAT IS COMPARED. work/sitecount_rnd.txt is built unchanged three times, once
against each backend (`{ F7 E3 }`, pure-L.in.oleum limbs, and the `*%'`
extension), and all three are graded against an oracle written in this file
directly from the DOS assembly - not imported from noctis-harness, so a mistake
in that transcription cannot be laundered into agreement here. That oracle is
in turn pinned three ways: against the published golden vector for seed 12345,
against noctis-harness/sitecount_rndoracle.py, and against its C oracle when
gcc is available (a third author's reading, lifted from noctis-iv-lr).

Nothing in work/ is written to. The sources are copied into tests/gen and the
backend is selected by which file is copied to tests/gen/mul64be.txt, so this
test cannot disturb work/mul64be.txt or any shipped output while it runs.

NEGATIVE CONTROLS:
  1. a fourth backend, identical to mul64frag but with Mul64u encoding
     `imul ebx` instead of `mul ebx`, is built and run. It must DIVERGE - and
     it diverges at draw 3 and stays wrong for 4093 of 4096 draws, which is
     what "silent" means here: the program runs, exits and writes a full-length
     file of confident nonsense.
  2. folding with a 32-bit add instead of `add al, dl` diverges at draw 1.
  3. using only the low 32 bits of the product - i.e. not needing a 64-bit
     multiply at all - diverges at draw 1. This is the claim that justifies
     the whole track.

HOW IT FAILS: a backend that breaks prints its first differing draw with the
seed state, so it is immediately visible whether the value or the seed went
wrong first.

RUN: python tests/test_fastrandom.py   (gcc optional, for the third oracle)
"""

import os
import shutil
import struct
import sys

import linoharness as L

sys.path.insert(0, L.HARNESS)
import sitecount_rndoracle as O


NIV_PLUS = r"C:\programmieren\noctis\niv-plus\source"

RND_SRC = os.path.join(L.WORK, "sitecount_rnd.txt")
DRAWS, SEED, MASK = 4096, 12345, 0xFFFF

# noctis-harness/sitecount_rndoracle.py prints this for seed 12345.
GOLDEN16 = [11673, 46877, 35395, 41614, 6091, 22323, 36880, 43493,
            25490, 22381, 34338, 38609, 34996, 29267, 25289, 63327]

# The instruction sequence the oracle below was transcribed from. If the
# reference clone ever changes these lines, the oracle is stale and every
# agreement it certifies is worthless - so they are pinned as text.
DOS_ASM = [
    "db 0x66; mov ax, word ptr flat_rnd_seed",
    "db 0x66; mov dx, word ptr flat_rnd_seed",
    "db 0x66; mul dx",
    "add al, dl",
    "db 0x66; add word ptr flat_rnd_seed, ax",
    "db 0x66; and ax, word ptr mask",
]

BACKENDS = [
    ("frag", "mul64frag.txt", L.STOCK_COMPILER, L.STOCK_CPU),
    ("limb", "mul64limb.txt", L.STOCK_COMPILER, L.STOCK_CPU),
    ("star", "mul64star.txt", L.EXT_COMPILER, L.EXT_CPU),
]

M32 = 0xFFFFFFFF


def oracle(n=DRAWS, seed=SEED, mask=MASK, fold="al", signed=False):
    """fast_random, straight off the assembly, in exact Python integers.

    fold="al"   add al, dl        the original: 8 bits, carry discarded
    fold="eax"  add eax, edx      the plausible mistake
    fold="none" low half only     no 64-bit product at all
    """
    s = (seed | 3) & M32                      # fast_srand: or word ptr seed, 3
    out = []
    for _ in range(n):
        if signed:
            a = s - 0x100000000 if s & 0x80000000 else s
            product = (a * a) & 0xFFFFFFFFFFFFFFFF
        else:
            product = (s * s) & 0xFFFFFFFFFFFFFFFF
        eax, edx = product & M32, (product >> 32) & M32
        if fold == "al":
            eax = (eax & 0xFFFFFF00) | (((eax & 0xFF) + (edx & 0xFF)) & 0xFF)
        elif fold == "eax":
            eax = (eax + edx) & M32
        s = (s + eax) & M32                   # 32-bit: the 0x66 prefix is there
        out.append((eax & mask, s))
    return out


def rows_of(blob):
    vals = struct.unpack("<%dI" % (len(blob) // 4), blob)
    return [(vals[i * 2], vals[i * 2 + 1]) for i in range(len(vals) // 2)]


def agree(check, got, want, label):
    """Compare two draw sequences without printing 4096 tuples on success."""
    i = first_diff(got, want)
    return check.ok(i is None, label,
                    "%d draws" % len(want) if i is None else
                    "differ at draw %d: %r vs %r" % (i, got[i], want[i]))


def first_diff(a, b):
    for i in range(min(len(a), len(b))):
        if a[i] != b[i]:
            return i
    return None if len(a) == len(b) else min(len(a), len(b))


def build_with(backend_file, compiler, cpu, gen, prog="sitcntrnd"):
    """Build the SHIPPED sitecount_rnd.txt against one backend, in tests/gen."""
    shutil.copyfile(backend_file, os.path.join(gen, "mul64be.txt"))
    src = os.path.join(gen, prog + ".txt")
    shutil.copyfile(RND_SRC, src)
    blob, exe, note = L.build_and_run(src, os.path.join(gen, "sitecount-rnd.bin"),
                                      compiler, cpu)
    return blob, note


def main():
    c = L.Check("test_fastrandom - the unsigned 64-bit site, under all three backends")
    gen = L.gen_dir()

    # ------------------------------------------- the oracle is not stale
    if os.path.isdir(NIV_PLUS):
        with open(os.path.join(NIV_PLUS, "NOCTIS-0.CPP"), encoding="latin-1") as fh:
            text = fh.read()
        missing = [s for s in DOS_ASM if s not in text]
        c.ok(not missing,
             "every instruction the oracle was transcribed from is still in "
             "NOCTIS-0.CPP", repr(missing))
    else:
        c.note("niv-plus not present - the transcription cannot be re-checked")

    ref = oracle()
    c.ok([v for v, _ in ref[:16]] == GOLDEN16,
         "the oracle reproduces the published golden vector for seed 12345",
         " ".join(str(v) for v, _ in ref[:8]) + " ...")
    agree(c, ref, O.py_draws(DRAWS, SEED, MASK),
          "...and agrees with noctis-harness's independent Python oracle")
    try:
        agree(c, ref, O.c_draws(DRAWS, SEED, MASK),
              "...and with the C oracle lifted from noctis-iv-lr (a third "
              "author's reading of the same assembly)")
    except SystemExit as exc:
        c.note("C oracle unavailable (%s) - two oracles instead of three"
               % str(exc).split("\n")[0])

    # -------------------------------- 2. the arithmetic really needs 64 bits
    wide = oracle(fold="eax")
    c.ok(first_diff(wide, ref) is not None and first_diff(wide, ref) <= 2,
         "NC2 folding with a 32-bit add instead of `add al, dl` diverges "
         "immediately", "first difference at draw %s" % first_diff(wide, ref))
    low = oracle(fold="none")
    c.ok(first_diff(low, ref) is not None and first_diff(low, ref) <= 2,
         "NC3 using only the low 32 bits of the product diverges immediately "
         "- this site genuinely needs the high half",
         "first difference at draw %s" % first_diff(low, ref))

    # ------------------------------------------- 3. the three backends
    results = {}
    for name, fname, compiler, cpu in BACKENDS:
        blob, note = build_with(os.path.join(L.WORK, fname), compiler, cpu, gen)
        if not c.ok(blob is not None,
                    "sitecount_rnd builds and runs on the %s backend" % name, note):
            continue
        rows = rows_of(blob)
        results[name] = rows
        if not c.eq(len(rows), DRAWS, "  %s produced %d draws" % (name, DRAWS)):
            continue
        i = first_diff(rows, ref)
        c.ok(i is None,
             "  %s is bit-exact with the oracle over all %d draws" % (name, DRAWS),
             "" if i is None else "first difference at draw %d: got %r want %r"
             % (i, rows[i], ref[i]))

    if len(results) == len(BACKENDS):
        L.compare_records(c, results, "backends")

    # ------------------------------------ 4. the MUL/IMUL negative control
    with open(os.path.join(L.WORK, "mul64frag.txt"), encoding="latin-1") as fh:
        frag = fh.read()
    assert frag.count("F7 E3") == 1 and frag.count("F7 EB") == 1
    signed_frag = os.path.join(gen, "mul64bad.txt")
    with open(signed_frag, "w", encoding="utf-8") as fh:
        # Mul64u encoded as imul: the mistake a single shared routine would make
        fh.write(frag.replace("F7 E3", "F7 EB"))
    blob, note = build_with(signed_frag, L.STOCK_COMPILER, L.STOCK_CPU, gen,
                            prog="sitcntbad")
    if c.ok(blob is not None,
            "NC1 a backend whose Mul64u is IMUL builds and runs - nothing "
            "complains", note):
        bad = rows_of(blob)
        i = first_diff(bad, ref)
        c.ok(i is not None,
             "NC1 ...and it produces a DIFFERENT sequence, so this test can "
             "tell MUL from IMUL",
             "diverges at draw %s, %d of %d draws wrong"
             % (i, sum(1 for k in range(min(len(bad), len(ref)))
                       if bad[k] != ref[k]), DRAWS))
        c.eq(len(bad), DRAWS,
             "NC1 ...while still writing a full-length file and exiting "
             "normally, which is exactly why it needs a test")
        agree(c, bad, oracle(signed=True),
              "NC1 ...and the wrong sequence is precisely the signed one, so "
              "the failure is understood rather than merely observed")

    # do not leave a wrong backend lying next to the right ones
    for stale in (os.path.join(gen, "mul64be.txt"), signed_frag):
        if os.path.exists(stale):
            os.remove(stale)

    return c.done()


if __name__ == "__main__":
    sys.exit(main())
