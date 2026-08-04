"""GUARDS: the operand table that all three 64-bit-multiply backends are graded
against - that it FITS the buffer the lino program allocates for it, that it can
tell MUL from IMUL at all, and that the copy on disk is the copy the generator
would produce.

No lino program is built here; this is pure arithmetic and text, and it runs in
well under a second. It guards three ways the multiply evidence could quietly
stop meaning anything:

  1. THE TABLE OUTGROWING THE BUFFER. work/sitecount_mul64.txt allocates
     `inbuf = MAXPAIRS multiplied 2` and `outbuf = MAXPAIRS multiplied 4`, but
     it loops on the count it reads out of the FILE, not on MAXPAIRS. Raising
     NRANDOM in sitecount_vectors.py past that bound does not fail the build,
     does not fail the run and does not fail sitecount_cmp.py's length check -
     it just starts returning (0,0,0,0) at pair 4096 while the program exits
     normally. Verified: NRANDOM 4000 -> 4200 corrupts the last 162 pairs in
     silence. Today the headroom is 38 pairs.
  2. A TABLE THAT CANNOT SEE SIGNEDNESS. Only pairs where exactly one operand
     has bit 31 set make the signed and unsigned high halves differ. Without
     those, a backend that calls MUL where the game calls IMUL passes
     everything - and sky/isthere are IMUL while fast_random is MUL, so that is
     the single most consequential mistake available here. sitecount_vectors.py
     has a sign_sensitive() for exactly this and sitecount_cmp.py never calls it.
  3. A STALE TABLE ON DISK. The lino program reads work/sitecount-vec.bin;
     sitecount_cmp.py grades against vectors() computed in memory and never
     rewrites the file. If the two ever drift, the backends are graded on
     answers to a different question and every one of them "fails".

Also cross-checked: the exact answers in expected() against the two's-complement
identity mul64limb.txt is built on -

    signed_hi = unsigned_hi - (x<0 ? y : 0) - (y<0 ? x : 0)   mod 2^32

which is an independent route to the same numbers, and the identity the pure
L.in.oleum backend would be wrong without.

NEGATIVE CONTROLS: each guard is re-run against a deliberately broken input and
must reject it - an oversized table, a table whose operands all have bit 31
clear, and the sign identity with one correction term dropped. A check that
cannot fail is not a check.

HOW IT FAILS: an oversized table names the count and the bound; a stale file
prints both sizes and the first differing pair.

RUN: python tests/test_sitevectors.py
"""

import os
import re
import struct
import sys

import linoharness as L

sys.path.insert(0, L.HARNESS)
import sitecount_vectors as V


M32 = 0xFFFFFFFF

MUL64_SRC = os.path.join(L.WORK, "sitecount_mul64.txt")
RND_SRC = os.path.join(L.WORK, "sitecount_rnd.txt")
VEC_BIN = os.path.join(L.WORK, "sitecount-vec.bin")


def lino_constant(path, name):
    """Read `NAME = 1234;` out of a lino source's "constants" period."""
    with open(path, encoding="latin-1") as fh:
        m = re.search(r"^\s*%s\s*=\s*(\d+)\s*;" % re.escape(name),
                      fh.read(), re.M)
    return int(m.group(1)) if m else None


def lino_workspace(path, name):
    """Read `name = EXPR;` out of a lino source's "workspace" period."""
    with open(path, encoding="latin-1") as fh:
        body = fh.read().split('"workspace"', 1)[-1].split('"programme"', 1)[0]
    m = re.search(r"^\s*%s\s*=\s*(.+?)\s*;" % re.escape(name), body, re.M)
    return m.group(1) if m else None


def s32(v):
    v &= M32
    return v - 0x100000000 if v & 0x80000000 else v


def sign_corrected(pairs, drop_second_term=False):
    """(lo, hi) of the SIGNED product, reached from the unsigned one by the
    identity mul64limb.txt implements rather than by multiplying signed."""
    out = []
    for x, y in pairs:
        pu = (x & M32) * (y & M32)
        hi = pu >> 32
        if x & 0x80000000:
            hi -= y
        if (y & 0x80000000) and not drop_second_term:
            hi -= x
        out.append((pu & M32, hi & M32))
    return out


def table_fits(pairs, maxpairs):
    return len(pairs) <= maxpairs


def main():
    c = L.Check("test_sitevectors - the table the three backends are graded on")

    pairs = V.vectors()
    exp = V.expected(pairs)

    # ------------------------------------------------ 1. it fits the buffer
    maxpairs = lino_constant(MUL64_SRC, "MAXPAIRS")
    if not c.ok(maxpairs is not None, "MAXPAIRS read out of sitecount_mul64.txt"):
        return c.done()
    c.eq(lino_workspace(MUL64_SRC, "inbuf"), "MAXPAIRS multiplied 2",
         "inbuf is sized off MAXPAIRS - two units per pair")
    c.eq(lino_workspace(MUL64_SRC, "outbuf"), "MAXPAIRS multiplied 4",
         "outbuf is sized off MAXPAIRS - four units per pair")
    c.ok(table_fits(pairs, maxpairs),
         "the table fits the workspace the program allocates for it",
         "%d pairs, MAXPAIRS = %d, headroom %d"
         % (len(pairs), maxpairs, maxpairs - len(pairs)))
    c.note("beyond MAXPAIRS the program neither fails nor warns: it writes "
           "(0,0,0,0) and exits 0, and the length check still passes")
    c.ok(not table_fits(pairs + [(1, 1)] * (maxpairs - len(pairs) + 1), maxpairs),
         "NC1 one pair too many is rejected by the same predicate",
         "a table of %d would overrun" % (maxpairs + 1))

    # the rnd program's loop bound and its buffer must agree the same way
    ndraws = lino_constant(RND_SRC, "NDRAWS")
    c.eq(lino_workspace(RND_SRC, "draws"), "NDRAWS multiplied 2",
         "sitecount_rnd's buffer is sized off its own loop bound (NDRAWS = %s)"
         % ndraws)

    # -------------------------------------- 2. it can tell MUL from IMUL
    ss = V.sign_sensitive(pairs)
    c.ok(ss >= len(pairs) // 4,
         "the table can detect a MUL/IMUL swap on a large fraction of pairs",
         "%d of %d pairs have signed hi != unsigned hi" % (ss, len(pairs)))
    blind = [(x & 0x7FFFFFFF, y & 0x7FFFFFFF) for x, y in pairs]
    c.eq(V.sign_sensitive(blind), 0,
         "NC2 ...and a table with bit 31 clear everywhere scores 0, so that "
         "check is not passing by construction")

    for p in V.ADVERSARIAL:
        if p not in pairs:
            c.ok(False, "adversarial pair %r is in the table" % (p,))
            break
    else:
        c.ok(True, "all %d adversarial pairs are in the table"
             % len(V.ADVERSARIAL))
    corners = [(x, y) for x in V.CORNERS for y in V.CORNERS]
    c.ok(all(p in pairs for p in corners),
         "all %d corner combinations are in the table" % len(corners))

    # ------------------------- 3. the exact answers, by a second route
    want = [(e[2], e[3]) for e in exp]      # (lo_signed, hi_signed)
    got = sign_corrected(pairs)
    bad = [i for i in range(len(pairs)) if got[i] != want[i]]
    c.ok(not bad, "the signed answers agree with the two's-complement identity "
                  "mul64limb.txt is built on, over all %d pairs" % len(pairs),
         "" if not bad else "%d differ, first at pair %d: %r" %
         (len(bad), bad[0], (pairs[bad[0]], got[bad[0]], want[bad[0]])))
    broken = sign_corrected(pairs, drop_second_term=True)
    nbad = sum(1 for i in range(len(pairs)) if broken[i] != want[i])
    c.ok(nbad > len(pairs) // 4,
         "NC3 dropping one correction term from that identity breaks it, so "
         "the agreement above is not an identity of the checker with itself",
         "%d of %d pairs would differ" % (nbad, len(pairs)))

    # the unsigned half must differ from the signed half often enough that a
    # program returning the same thing for both entry points cannot pass
    same = sum(1 for e in exp if (e[0], e[1]) == (e[2], e[3]))
    c.ok(len(pairs) - same >= len(pairs) // 4,
         "one routine used for both signednesses would fail on most pairs",
         "%d of %d pairs have different signed and unsigned products"
         % (len(pairs) - same, len(pairs)))

    # -------------------------------- 4. the copy on disk is the live one
    if c.ok(os.path.exists(VEC_BIN),
            "work/sitecount-vec.bin exists (regenerate: python "
            "noctis-harness/sitecount_vectors.py)"):
        blob = open(VEC_BIN, "rb").read()
        fresh = struct.pack("<I", len(pairs))
        for x, y in pairs:
            fresh += struct.pack("<II", x, y)
        c.eq(len(blob), 4 + 8 * len(pairs),
             "its length is one count unit plus two units per pair")
        n = struct.unpack_from("<I", blob)[0] if len(blob) >= 4 else -1
        c.eq(n, len(pairs), "the count in its header is the table's length")
        c.ok(blob == fresh,
             "the file on disk is byte-identical to what the generator "
             "produces now - nothing is grading the backends on stale operands",
             "" if blob == fresh else "%d bytes on disk, %d fresh"
             % (len(blob), len(fresh)))

    return c.done()


if __name__ == "__main__":
    sys.exit(main())
