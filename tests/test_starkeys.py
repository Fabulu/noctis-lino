"""GUARDS: work/starmap_read.txt decodes the real catalogue exactly, and
work/starmap_find.txt's key table refuses everything it is supposed to refuse.

The whole Tier 2 comparison is done in integers: a catalogue double d becomes
the exact integer N = trunc(d * 1e15) and is compared against P = x*y*z with no
floating point anywhere. If that decode is wrong the hit rate is meaningless,
so all 37,578 records - the real ones, not a sample - are decoded on both sides
and required to agree on the 96-bit N, the rejection code and the record tail.
The Python side reads the bytes itself and uses Fractions.

The guards on the key table matter for the same reason. Each is driven with a
crafted STARMAP.BIN of the correct length rather than argued about:

  * exponent 0 REJECTS instead of decoding to zero. Two records land there
    (WESTOS is -0.0, MDIR 17 is a NaN written byte-reversed) and a key of
    N = 0 would claim every generated star with |P| < 1e10 - the largest false
    positive available in this design.
  * |N| >= 2^94 rejects, so that P - N cannot overflow the 96-bit difference.
  * more than MAXKEY usable keys is a clean io failure, not a silent overrun.

KNOWN LATENT GAP, pinned rather than fixed: a double small enough that
1075 - exponent >= 104 takes Decode's early exit and comes back N = 0 with
rejection code 0, i.e. as a usable key at the origin of identity space. No
record in the real catalogue is anywhere near that - the largest 1075-e among
usable star records is checked here and is 65 - so the defect is unreachable.
The test asserts BOTH: that the port really does behave that way on a crafted
key, and that the real catalogue stays far from the trip point. If a future
catalogue crosses it this fails and says why.

NEGATIVE CONTROL: a copy of starmap_read with 1075 changed to 1074 in Decode -
a one-token error that halves every key - must disagree with the referee on
essentially every record. Without it, "the two agree" would also be the verdict
of a comparison that was not looking.

RUN: python tests/test_starkeys.py     (~30s)
"""

import os
import struct
import sys

import linoharness as L
import starmapdrive as D
import starmapspec as S


def with_ids(blob, raws, retype=None):
    """The real catalogue with record j's double replaced by raws[j]."""
    buf = bytearray(blob)
    for j, raw in enumerate(raws):
        off = 4 + 32 * j
        buf[off:off + 8] = raw
        if retype:
            buf[off + 29] = ord(retype)
    return bytes(buf)


def main():
    c = L.Check("test_starkeys - the catalogue decoder and the key-table guards")
    if not c.ok(os.path.exists(S.CATALOGUE),
                "the real STARMAP.BIN is where the reference clone puts it",
                S.CATALOGUE):
        return c.done()

    with open(S.CATALOGUE, "rb") as fh:
        real = fh.read()
    recs = S.load_catalogue()
    c.eq(len(recs), 37578, "the real catalogue is 37,578 records")

    # ------------------------------------------------- 1. decode them all
    r = D.Read(stem="tsread", sbox_name="tsread")
    c.eq(r.nsubs, r.want_subs, "sandbox copy rewrote every file-name literal")
    ok, msg = r.build()
    if not c.ok(ok, "starmap_read.txt builds on the extended toolchain", msg):
        return c.done()
    r.catalogue(real)
    hdr, got, failed, msg = r.run(timeout=180)
    if not c.ok(got is not None and not failed, "starmap_read runs", msg):
        return c.done()

    nstar = sum(1 for x in recs if x[3] == S.STAR)
    nbad28 = sum(1 for x in recs if (x[2] & 0xFF) != 0x20)
    ntomb = sum(1 for x in recs if x[1] == S.TOMB)
    c.eq(hdr, (len(recs), nstar, nbad28, ntomb),
         "header: records, 'S' records, byte-28 anomalies, tombstones")

    badT = badR = badN = 0
    first = []
    for (i, raw, tail, _typ, name) in recs:
        gtail, grej, g0, g1, g2 = got[i]
        n, rej = S.decode_exact(raw)
        want = S.limbs96(n) if rej == 0 else (0, 0, 0)
        if gtail != tail:
            badT += 1
        if grej != rej:
            badR += 1
            if len(first) < 5:
                first.append("[%d] %s rej %d want %d" % (i, name, grej, rej))
        elif (g0, g1, g2) != want:
            badN += 1
            if len(first) < 5:
                first.append("[%d] %s N %r want %r" % (i, name, (g0, g1, g2), want))
    c.eq(badT, 0, "record tail field agrees on all %d records" % len(recs))
    c.eq(badR, 0, "rejection code agrees on all %d records" % len(recs))
    c.eq(badN, 0, "the 96-bit N agrees on all %d records" % len(recs))
    for line in first:
        c.note(line)

    rej = [(i, name, S.decode_exact(raw)[1]) for (i, raw, _t, typ, name) in recs
           if typ == S.STAR and S.decode_exact(raw)[1]]
    c.eq(sorted((name, code) for _i, name, code in rej),
         [("MDIR 17", 1), ("WESTOS", 1)],
         "exactly two star records are unusable, and they are the known two: "
         "WESTOS is -0.0, MDIR 17 is a NaN written byte-reversed, which reads "
         "back as a denormal - both exponent 0, both rejection code 1")

    # ------------------------------------------------- 2. the latent N=0 path
    ks = [1075 - ((struct.unpack("<Q", raw)[0] >> 52) & 0x7FF)
          for (_i, raw, _t, typ, _n) in recs
          if typ == S.STAR and S.decode_exact(raw)[1] == 0]
    c.ok(max(ks) < 104,
         "no real key comes within reach of Decode's N=0 early exit "
         "(trip point 1075-e >= 104)", "largest 1075-e is %d" % max(ks))
    usable = [S.decode_exact(raw)[0] for (_i, raw, _t, typ, _n) in recs
              if typ == S.STAR and S.decode_exact(raw)[1] == 0]
    c.eq(sum(1 for n in usable if n == 0), 0,
         "and no usable key decodes to N = 0, whose window would claim "
         "every star with |P| < 1e10")

    # The same crafted run exercises the two rejection codes the real
    # catalogue never reaches, so all four Decode outcomes are covered.
    tiny = struct.pack("<d", 2.0 ** -110)          # e = 965, so 1075-e = 110
    nan = struct.pack("<Q", 0x7FF8000000000000)    # a NaN the right way round
    huge = struct.pack("<d", 1e300)                # e >= EMAX
    r.catalogue(with_ids(real, [tiny, nan, huge]))
    _hdr2, got2, failed, msg = r.run(timeout=180)
    if c.ok(got2 is not None and not failed, "crafted rejection probes run", msg):
        c.eq(got2[0][1:], (0, 0, 0, 0),
             "sub-threshold key comes back N = 0 with rejection code 0 - the "
             "latent gap, pinned so a change in behaviour is visible")
        c.eq(S.decode_exact(tiny), (0, 0),
             "the referee agrees that its exact value truncates to 0")
        c.eq((got2[1][1], got2[2][1]), (2, 3),
             "NaN rejects with code 2 and an over-large exponent with code 3 - "
             "branches the real catalogue never reaches")

    # ------------------------------------------------- 3. negative control
    m = D.Read(stem="tsreadm", sbox_name="tsreadm")
    text = open(m.src, "r", encoding="utf-8").read()
    mutated = text.replace("A = 1075; A - [de];", "A = 1074; A - [de];")
    c.ok(mutated != text, "negative control: Decode's exponent bias off by one")
    open(m.src, "w", encoding="utf-8").write(mutated)
    ok, msg = m.build()
    if c.ok(ok, "the mutant builds", msg):
        m.catalogue(real)
        _h, mgot, failed, msg = m.run(timeout=180)
        if c.ok(mgot is not None and not failed, "the mutant runs", msg):
            differ = sum(1 for i in range(len(recs)) if mgot[i] != got[i])
            c.ok(differ > len(recs) // 2,
                 "the mutant disagrees with the referee on most records - the "
                 "comparison is actually looking at N",
                 "%d of %d records differ" % (differ, len(recs)))

    # ------------------------------------------------- 4. the key-table guards
    f = D.Find(stem="tskey", sbox_name="tskey")
    ok, msg = f.build()
    if not c.ok(ok, "starmap_find builds", msg):
        return c.done()

    nstar_recs = [x for x in recs if x[3] == S.STAR]
    cases = [
        ("all ids +0.0", struct.pack("<d", 0.0), "nrejkey"),
        ("all ids 3e13 (N = 3e28, over the 2^94 ceiling)",
         struct.pack("<d", 3e13), "nbigkey"),
    ]
    for label, raw, field in cases:
        f.catalogue(with_ids(real, [raw] * len(recs)))
        h, _hits, failed, msg = f.run(0, 0, timeout=180)
        if not c.ok(h is not None and not failed, "%s runs" % label, msg):
            continue
        c.eq(h[field], len(nstar_recs), "%s: all %d star records land in %s"
             % (label, len(nstar_recs), field))
        c.eq(h["nkeys"], 0, "...and none of them becomes a key")
        c.eq(h["nhits"], 0, "...so nothing can match")

    # more usable keys than the table holds: a clean failure, not an overrun
    good = S.double_for_N(10 ** 12)
    f.catalogue(with_ids(real, [good] * (len(recs)), retype="S"))
    h, _hits, failed, msg = f.run(0, 0, timeout=180)
    c.ok(h is None,
         "a catalogue with %d usable keys (MAXKEY is 8000) fails cleanly"
         % len(recs), "err file written: %s" % failed)

    # The size check refuses a catalogue of the wrong length outright - and a
    # refused run must not be graded by the artifact of the run before it.
    # That is not hypothetical: the delivered pipeline reads its output file
    # without noticing the .err the run just wrote. starmapdrive removes the
    # .err first and linorun.ps1 requires an artifact NEWER than the launch,
    # so both signals are checked here.
    stale = os.path.getmtime(f.out) if os.path.exists(f.out) else None
    c.ok(stale is not None, "a previous run's output is sitting in the sandbox")
    f.catalogue(real[:-32])
    h, _hits, failed, msg = f.run(0, 0, timeout=180)
    c.ok(h is None, "a catalogue 32 bytes short is refused", "err: %s" % failed)
    c.ok(failed, "...the programme wrote its .err file")
    c.ok("no fresh" in msg,
         "...and the stale artifact was not mistaken for this run's result", msg)

    f.catalogue(real)
    h, _hits, failed, msg = f.run(0, 0, timeout=180)
    c.ok(h is not None and not failed,
         "the real catalogue is accepted again afterwards - the refusals above "
         "were about the data, not a wedged sandbox", msg)

    return c.done()


if __name__ == "__main__":
    sys.exit(main())
