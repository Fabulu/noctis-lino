"""Mechanism for test_nearstar.py: sandbox, corpus, build, run, mutate.

Three rules of this suite are baked in here and must not be worked around:

  * TESTS NEVER TOUCH work/. Every run copies the eight L.in.oleum sources
    the Wave 4 driver needs - nsrun.txt and its libraries brtl, nsrng,
    nsseed, nstopo, geoconv, nsident, nslabel, plus work/fp's five engine
    files - into a sandbox under tests/gen and builds THERE. The code under
    test is still the code in work/: a regression there fails this test. But
    work/nstopo.bin and work/nsdiag.bin keep whatever the pipeline left in
    them, and the deliberate sabotages below are applied to the copy only.
  * NOTHING IS EVER WAITED ON. nsrun.exe is a GUI-subsystem binary;
    linoharness drives it through lino_build.ps1 / linorun.ps1, which poll
    for the artifact and kill the process.
  * NOTHING IS GRADED AGAINST A STORED EXPECTATION. The corpus is re-swept
    from the galaxy hash and re-paired against STARMAP.BIN every run; the C
    reference is rebuilt by gcc every run; the Python reference is re-run
    every run; the L.in.oleum programme is recompiled every run. No .nstopo
    checked in anywhere is ever opened.

    The one thing read off disk rather than recomputed is the set of DL.EXE
    captures under tests/gen/recon_c, and they are the same KIND of thing as
    STARMAP.BIN: stdout of the 1996 executable, not output of ours. They are
    opened read-only. Re-capturing them needs a DOSBox-X window, which a
    routine suite run must not open; test_nearstar says so in its header
    rather than letting the distinction go unstated.

WHY THE SANDBOX NEEDS NO SOURCE EDITS. nsrun.txt names its files with plain
literals - { nsin.bin }, { nstopo.bin }, { nsdiag.bin } - and nslabel.txt
names { STARMAP.BIN }. linorun.ps1 starts the programme with its own
directory as the working directory, so a sandbox that carries its own copies
of those four files is completely isolated without a single literal being
rewritten. That matters: it means the source this test compiles is
byte-identical to work/, except where a mutation deliberately says otherwise,
and install() asserts exactly that.

THE MUTATIONS. Each is one surgical edit to the sandbox's nstopo.txt that a
careful porter could plausibly have made, and each changes WHERE or HOW MANY
draws the RNG stream takes. They are the reason this file exists: a test that
only ever runs the correct programme measures nothing.
"""

import hashlib
import os
import shutil
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
HARNESS = os.path.join(REPO, "noctis-harness")
for p in (HERE, HARNESS):
    if p not in sys.path:
        sys.path.insert(0, p)

import linoharness as L                                          # noqa: E402
import starmapspec as S                                          # noqa: E402
import ns_spec as N                                              # noqa: E402

# nsrun.txt's own library list, in its dependency order. Copied flat; the
# fp/ ones keep their subdirectory because that is how nsrun.txt spells them.
LIBS = ("brtl.txt", "nsrng.txt", "nsseed.txt", "nstopo.txt",
        "geoconv.txt", "nsident.txt", "nslabel.txt")
FPLIBS = ("fpabi.txt", "fpctl.txt", "fpx87.txt", "fpconv.txt", "fpchains.txt")
PROG = "nsrun.txt"

# The programme's own file-name literals. Named here so the test can say what
# it is isolating rather than relying on a coincidence of layout.
IO_FILES = ("nsin.bin", "nstopo.bin", "nsdiag.bin", "STARMAP.BIN")

DIAG_MAGIC = 0x0DEFACED


# ------------------------------------------------------------ the mutations

class Mutation(object):
    """One deliberate sabotage of the draw sequence.

    kind, describing the EDIT and not its consequences:
      'add'    a draw is inserted at the site
      'drop'   a draw is deleted at the site
      'order'  a draw's stream position moves, with nothing added or removed
               AT THE SITE. Downstream counts may still move anyway, because
               later draws are conditional on the value that now lands there
               - measured, and reported by test_nearstar rather than assumed
               either way.

    must: the graders that MUST catch it, each one argued from the invariant
      table in nsspec.AUDIT or from what the 1996 artifacts can see. It is a
      floor, not a prediction: test_nearstar prints the full matrix of what
      actually caught what, and asserts aggregate power separately. Claiming
      more here than can be argued would turn a measurement into a wish.
    """

    def __init__(self, name, phase, kind, blurb, edits, must):
        self.name = name
        self.phase = phase
        self.kind = kind
        self.blurb = blurb
        self.edits = edits
        self.must = set(must)

    def apply(self, text):
        n = 0
        for old, new in self.edits:
            c = text.count(old)
            if c != 1:
                raise ValueError("mutation %r: anchor occurs %d times, want 1:"
                                 " %r" % (self.name, c, old[:60]))
            text = text.replace(old, new)
            n += 1
        return text, n


# The anchors are exact text from work/nstopo.txt, tabs included. apply()
# refuses to proceed if one of them stops matching exactly once, so a rewrite
# of the subject turns into a loud failure instead of a silent no-op break.
#
# The `must` sets below are floors with a reason attached:
#   'audit' appears only where nsspec.AUDIT carries an EXACT invariant for
#     that phase - A is 12 (13) per planet, B is 3 or 0, G is 2 per planet.
#     Phases C, D and E have range invariants only, because the source has
#     unbounded while-loops and short-circuits there, so the audit cannot
#     see a sabotage in them and this table does not pretend it can.
#   'refs' is the comparison against the reference NSTOPO recomputed this
#     run, and every sabotage must fail it - a stream that has slipped by
#     one cannot agree with a correct one anywhere downstream.
#   'catalogue' and 'dl' appear where a desynchronised stream reaches the
#     types, owners and moon ids the 1996 artifacts recorded. They are
#     absent for phase G, which is the last drawing phase.
MUTATIONS = [
    Mutation(
        "adrop", "A", "drop",
        "phase A: the random(1000) at :4094 removed - one draw per planet",
        [("\tA = 1000; => NsRandom;\t\t( :4094 random(1000), int arg   )\n",
          "\t( BREAK adrop: the :4094 random(1000) draw removed )\n")],
        ("refs", "audit", "catalogue", "dl")),
    Mutation(
        "bclip", "B", "drop",
        "phase B: skipped when nop <= 4 - the 'do not draw for planets that "
        "do not exist' repair the source header warns about",
        [("      ? [nsclass] != 0 -> nsbdone;\n",
          "      ? [nsclass] != 0 -> nsbdone;\n"
          "      ? [nsnop] <= 4 -> nsbdone;\t( BREAK bclip )\n")],
        ("refs", "audit")),
    Mutation(
        "cadd", "C", "add",
        "phase C: one spurious draw per class-9 re-roll",
        [("\tA = 10; => NsRandom;\t\t( :4134 )\n",
          "\tA = 2; => NsRandom;\t\t( BREAK cadd: a spurious draw )\n"
          "\tA = 10; => NsRandom;\t\t( :4134 )\n")],
        ("refs", "catalogue", "dl")),
    Mutation(
        "d4152", "D", "drop",
        "phase D: the short-circuited random(4) at :4152 removed",
        [("\tA = 4; => NsRandom;\t\t( :4152 )\n",
          "\tA = 3;\t\t\t\t( BREAK d4152: draw removed )\n")],
        ("refs", "catalogue", "dl")),
    Mutation(
        "e4213", "E", "drop",
        "phase E: the random(c) at :4213 skipped when c == 0 - the tidy-port "
        "repair the source header names as trap 1",
        [("      ? [nsn] <= 7 -> nsecool2;\n\tA = [nsc]; => NsRandom;\n",
          "      ? [nsn] <= 7 -> nsecool2;\n"
          "      ? [nsc] = 0 -> nsecool2;\t( BREAK e4213 )\n"
          "\tA = [nsc]; => NsRandom;\n")],
        ("refs", "catalogue", "dl")),
    Mutation(
        "eorder", "E", "order",
        "phase E: the :4201 type draw moved from stream position 7 to 2 - "
        "the same draws at the site, a different one landing on p_type",
        [("\tA = 360; => NsRandom;\t\t( :4194 orb_orient, int arg )\n",
          "\tA = 360; => NsRandom;\t\t( :4194 orb_orient, int arg )\n"
          "\tA = NSPLTYPES; => NsRandom; [nsr] = A;\t( BREAK eorder )\n"),
         ("\tA = NSPLTYPES; => NsRandom;\t\t\t( :4201 )\n",
          "\tA = [nsr];\t\t\t\t\t( BREAK eorder )\n")],
        ("refs", "catalogue", "dl")),
    Mutation(
        "gadd", "G", "add",
        "phase G: one extra draw per planet - the last drawing phase, whose "
        "values reach nothing but p_ring",
        [("\tA = 3; => NsRandom;\t\t( :4348 ring radius, int arg )\n",
          "\tA = 3; => NsRandom;\t\t( :4348 ring radius, int arg )\n"
          "\tA = 3; => NsRandom;\t\t( BREAK gadd )\n")],
        ("refs", "audit")),                    # see test_nearstar section 9
]

MUT_BY_NAME = {m.name: m for m in MUTATIONS}


# ---------------------------------------------------------------- the driver

class Driver(object):
    """One sandbox: the delivered sources, optionally mutated, built and run."""

    def __init__(self, sbox, mutation=None):
        self.mut = mutation
        self.dir = os.path.join(L.gen_dir(), sbox)
        os.makedirs(os.path.join(self.dir, "fp"), exist_ok=True)
        self.src = os.path.join(self.dir, PROG)
        self.exe = os.path.join(self.dir, "nsrun.exe")
        self.nsin = os.path.join(self.dir, "nsin.bin")
        self.out = os.path.join(self.dir, "nstopo.bin")
        self.diag = os.path.join(self.dir, "nsdiag.bin")

    # -- sources ------------------------------------------------------------

    def install(self):
        """Copy work/'s sources in and apply the mutation.

        Returns (nedits, identical_names) where identical_names is the list of
        sandbox files that are byte-for-byte the work/ file they came from.
        Everything except a mutated nstopo.txt must be in that list.
        """
        same = []
        for lib in (PROG,) + LIBS:
            src = os.path.join(L.WORK, lib)
            dst = os.path.join(self.dir, lib)
            shutil.copyfile(src, dst)
            same.append(lib)
        for lib in FPLIBS:
            shutil.copyfile(os.path.join(L.WORK, "fp", lib),
                            os.path.join(self.dir, "fp", lib))
            same.append("fp/" + lib)
        # The catalogue the programme reads is the reference clone's, not
        # work/'s copy, so both sides of every phase-H comparison are the
        # same 1996 bytes.
        shutil.copyfile(S.CATALOGUE, os.path.join(self.dir, "STARMAP.BIN"))

        # The mutation is text-level, and the anchors are spelled with "\n",
        # so the read below uses universal newlines: a CRLF work/nstopo.txt
        # would still match and would simply be rewritten LF in the sandbox.
        # The unmutated copies above are byte copies, which is what the
        # "identical to work/" check compares.
        nedits = 0
        if self.mut is not None:
            path = os.path.join(self.dir, "nstopo.txt")
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                text = fh.read()
            text, nedits = self.mut.apply(text)
            with open(path, "w", encoding="utf-8", newline="") as fh:
                fh.write(text)
            same.remove("nstopo.txt")
        return nedits, same

    def unmodified(self, names):
        """Which of `names` are byte-identical to their work/ original."""
        out = []
        for n in names:
            a = os.path.join(L.WORK, n.replace("/", os.sep))
            b = os.path.join(self.dir, n.replace("/", os.sep))
            if _sha(a) == _sha(b):
                out.append(n)
        return out

    # -- build and run ------------------------------------------------------

    def build(self):
        for stale in (self.exe, self.out, self.diag):
            if os.path.exists(stale):
                os.remove(stale)
        rc, msg = L.build(self.src)
        return rc == 0, msg.strip()

    def run(self, rows, timeout=300):
        """Write an NSIN, run, return (records, diag, note).

        records is None if no fresh nstopo.bin appeared - which is what the
        programme's own failure path produces, and must never be read as an
        empty result.
        """
        N.write_nsin(self.nsin, rows)
        for stale in (self.out, self.diag):
            if os.path.exists(stale):
                os.remove(stale)
        rc, msg, blob = L.run(self.exe, self.out, timeout_sec=timeout)
        if blob is None:
            return None, self.read_diag(), msg
        _hdr, recs = N.read_nstopo(self.out)
        return recs, self.read_diag(), msg

    def read_diag(self):
        if not os.path.exists(self.diag):
            return None
        with open(self.diag, "rb") as fh:
            b = fh.read()
        if len(b) < 32:
            return None
        return list(struct.unpack_from("<8I", b, 0))


def _sha(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


# ------------------------------------------------------------- the corpora

def combined_rows(corpus, nsweep):
    """The NSIN this test grades, in two blocks.

    block 1  every accepted star of the DL box, phase H ON. These are the
             rows the 1996 catalogue can speak about, so every external leg
             is scored on them.
    block 2  the first `nsweep` of the same coordinates repeated once per
             star class, with the CLASS OVERRIDE set. Real stars only reach
             the (class, seed) pairs the galaxy happens to produce, and the
             branchy paths - class 8's type-10 else branch, class 9's long
             phase C, the 80-body clamp - are thin there.

             The SEED override is deliberately not used, and that is not a
             stylistic choice: the lino side applies an NSIN seed override to
             starnop() and the two references do not, so a seed-override row
             disagrees on field r7 by convention rather than by arithmetic.
             The spec does not settle it. test_nearstar pins the divergence
             to that one field instead of hiding it, and this corpus stays
             clear of it so every other comparison means what it says.
    """
    rows = [(x, y, z, -1, -1, -1, 1, 0)
            for (_r, x, y, z, _n, _c, _b) in corpus.rows]
    for cls in range(N.STAR_CLASSES):
        for (_r, x, y, z, _n, _c, _b) in corpus.rows[:nsweep]:
            rows.append((x, y, z, cls, -1, -1, 0, 0))
    return rows
