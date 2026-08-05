"""ns_corpus.py -- build the graded corpus, and prove it did not select itself.

The corpus is a set of star coordinate triples paired with the STARMAP.BIN
records that belong to them.  It is built from the galaxy hash and the 1996
catalogue and from NOTHING ELSE.  In particular no candidate is ever chosen,
ranked, broken or dropped using anything prepare_nearstar computes -- if it
were, the grader would be measuring the chooser.  Wave 3's QA pass found
exactly that had happened to fpstarin.bin, so the rules below are the ones
FLOATPOLICY.md section 2 imposed afterwards, applied again here:

  * SINGLE CANDIDATE.  A catalogue record matched by more than one sector,
    or a sector matching more than one record, is DISCARDED UNEXAMINED.
    Both counts are reported, so a reviewer can see how much was thrown
    away and satisfy themselves it was not thrown away selectively.
  * EXACT ARITHMETIC.  Matching is done on integers.  P = x*y*z is exact,
    N = trunc(stored_double * 1e15) is exact, and search_id_code's
    +/- 1e-5 window becomes |P - N| < 1e10.  starmapspec.py is the referee
    for that and test_starwindow.py pins it; this file reuses it rather
    than re-deriving it.
  * THE (long) SHORTCUT IS CHECKED, NOT ASSUMED.  NOCTIS-0.CPP:4080 chops
    three doubles to long before taking remainders.  The port carries the
    coordinates as int32 instead, which is only legitimate if every
    coordinate is an exact integer inside int32.  assert_exact_integers()
    checks that for every star in the corpus and reports the count.  If one
    star ever fails, the shortcut is void and the seed has to go through
    __ftol -- and we find out at corpus-build time, not at grading time.

Boxes:

  dl      the cube DL.EXE's isthere() scans with no Current.BIN, i.e. the
          set of stars the dynamic oracle can reach at all:
          origin trunc((dzat - 100*50000)/1e5)*1e5, 100 sectors per axis.
  cK      the centred (2K+1)^3 cube, matching tests/test_starcatalogue.py.

Usage:
    python ns_corpus.py [--box dl|cK] [--out FILE.nsin] [--manifest FILE.tsv]
                        [--flags N] [--limit N]
"""

import os
import struct
import sys
from bisect import bisect_left

HERE = os.path.dirname(os.path.abspath(__file__))
TESTS = os.path.join(os.path.dirname(HERE), "tests")
for p in (HERE, TESTS):
    if p not in sys.path:
        sys.path.insert(0, p)

import galaxyspec as G                                          # noqa: E402
import starmapspec as S                                         # noqa: E402

WINDOW = S.WINDOW                 # 10**10, i.e. idscale 1e-5 scaled by 1e15
SCALE = S.SCALE                   # 10**15
SECTOR = G.SECTORSIZE             # 100000

# DL.EXE / ST.EXE defaults, NOCTIS-D.H + DL.CPP.  See tests/gen/recon_c.
DZAT = (3797120.0, -4352112.0, -925018.0)
DL_RANGE = 100


def dl_box():
    origin = []
    for d in DZAT:
        q = (d - DL_RANGE * 50000) / 100000.0
        origin.append(int(q) * 100000)          # C long conversion: toward 0
    return [(o, DL_RANGE) for o in origin]


def centred_box(k):
    return [(-k * SECTOR, 2 * k + 1)] * 3


def parse_box(spec):
    if spec == "dl":
        return dl_box()
    if spec.startswith("c"):
        return centred_box(int(spec[1:]))
    raise ValueError("unknown box %r" % spec)


# --------------------------------------------------------------- the sweep

def sweep(box):
    """Every live sector of the box, as (x, y, z, P) with P = x*y*z exact.

    A sector whose cutoff flags are non-zero has no star in it and is not
    emitted -- that is the galaxy's own rule, not a filter of ours.
    """
    (x0, nx), (y0, ny), (z0, nz) = box
    out = []
    hs = G.hash_sector
    s32 = G.s32
    for i in range(nx):
        sx = x0 + i * SECTOR
        for j in range(ny):
            sy = y0 + j * SECTOR
            for k in range(nz):
                tx, ty, tz, _net, flags = hs(sx, sy, z0 + k * SECTOR)
                if flags:
                    continue
                x, y, z = s32(tx), s32(ty), s32(tz)
                out.append((x, y, z, x * y * z))
    return out


# ----------------------------------------------------------- the catalogue

def catalogue_records(path=S.CATALOGUE):
    """Decoded STARMAP.BIN: stars and planets separately.

    stars   [(ordinal, N, name, class_tag)]
    planets [(ordinal, N, name, index)]
    N is trunc(stored * 1e15), exact.  Tombstones ("Removed:") and records
    whose exponent the port's decoder rejects are dropped and counted.
    """
    recs = S.load_catalogue(path)
    stars, planets = [], []
    counts = {"nrec": len(recs), "tomb": 0, "rej": 0, "big": 0,
              "badtail": 0, "otherstype": 0}
    for (i, raw, _tail, typ, name) in recs:
        if raw == S.TOMB:
            counts["tomb"] += 1
            continue
        n, rej = S.decode_exact(raw)
        if rej:
            counts["rej"] += 1
            continue
        if abs(n) >= S.BIGKEY:
            counts["big"] += 1
            continue
        tailbytes = _tail_bytes(path, i)
        if typ == S.STAR:
            if not tailbytes.isdigit():
                counts["badtail"] += 1
                stars.append((i, n, name, -1))
            else:
                stars.append((i, n, name, int(tailbytes)))
        elif typ == ord("P"):
            if not tailbytes.isdigit():
                counts["badtail"] += 1
                continue
            planets.append((i, n, name, int(tailbytes)))
        else:
            counts["otherstype"] += 1
    return stars, planets, counts


_TAILCACHE = {}


def _tail_bytes(path, ordinal):
    blob = _TAILCACHE.get(path)
    if blob is None:
        blob = _TAILCACHE[path] = open(path, "rb").read()
    return blob[4 + 32 * ordinal + 30:4 + 32 * ordinal + 32].decode("latin-1")


# ------------------------------------------------------------- the pairing

class Corpus(object):
    def __init__(self):
        self.rows = []          # (ordinal, x, y, z, name, cls_tag, [indices])
        self.stats = {}


def build(box="dl", path=S.CATALOGUE, verbose=False):
    """Pair catalogue 'S' records with sectors, 1-to-1, and attach the
    charted body indices from the 'P' records underneath each."""
    stars, planets, counts = catalogue_records(path)
    sectors = sweep(parse_box(box))

    keys = sorted((n, i, name, cls) for (i, n, name, cls) in stars)
    kn = [k[0] for k in keys]

    # every (record, sector) pair inside the window -- ALL of them, not the
    # nearest, because the identity is symmetric in x/y/z and near-equal
    # catalogue ids sit inside one another's windows
    byrec, bysec = {}, {}
    for (x, y, z, P) in sectors:
        j = bisect_left(kn, P - WINDOW + 1)
        while j < len(kn) and kn[j] - P < WINDOW:
            byrec.setdefault(keys[j][1], []).append((x, y, z, P))
            bysec.setdefault((x, y, z), []).append(keys[j][1])
            j += 1

    multi_rec = sum(1 for v in byrec.values() if len(v) > 1)
    multi_sec = sum(1 for v in bysec.values() if len(v) > 1)

    recinfo = {i: (n, name, cls) for (i, n, name, cls) in stars}
    accepted = {}
    for rec, cands in byrec.items():
        if len(cands) != 1:
            continue
        x, y, z, P = cands[0]
        if len(bysec[(x, y, z)]) != 1:
            continue
        accepted[rec] = (x, y, z, P)

    # attach the charted bodies.  A 'P' record's id was written as
    # nearstar_identity + index (NOCTIS.CPP:1263 / :1808), so subtracting
    # index * 1e15 from its exact key lands it on its parent's P.
    pkeys = sorted((P, rec) for rec, (x, y, z, P) in accepted.items())
    pn = [k[0] for k in pkeys]
    bodies = {}
    orphan = 0
    ambig_planet = 0
    for (_i, n, _name, idx) in planets:
        want = n - idx * SCALE
        j = bisect_left(pn, want - WINDOW + 1)
        hits = []
        while j < len(pn) and pn[j] - want < WINDOW:
            hits.append(pkeys[j][1])
            j += 1
        if not hits:
            orphan += 1
            continue
        if len(hits) > 1:
            ambig_planet += 1
            continue
        bodies.setdefault(hits[0], set()).add(idx)

    c = Corpus()
    for rec in sorted(accepted):
        x, y, z, _P = accepted[rec]
        _n, name, cls = recinfo[rec]
        c.rows.append((rec, x, y, z, name, cls, sorted(bodies.get(rec, ()))))
    c.stats = dict(counts)
    c.stats.update(
        sectors=len(sectors), scatalogue=len(stars), pcatalogue=len(planets),
        matched_records=len(byrec), matched_sectors=len(bysec),
        multi_candidate_records=multi_rec, multi_record_sectors=multi_sec,
        accepted=len(accepted), planets_orphan=orphan,
        planets_ambiguous=ambig_planet,
        stars_with_bodies=sum(1 for r in c.rows if r[6]),
    )
    if verbose:
        for k in sorted(c.stats):
            print("  %-26s %d" % (k, c.stats[k]))
    return c


# ------------------------------------------------------------- the assertion

def assert_exact_integers(corpus):
    """NOCTIS-0.CPP:4080's three (long) chops are the identity function only
    if every coordinate is an exact integer inside int32.  Checked, counted,
    and fatal if it ever fails."""
    bad = []
    for (rec, x, y, z, _nm, _cl, _b) in corpus.rows:
        for v in (x, y, z):
            if int(v) != v or not (-2147483648 <= v <= 2147483647):
                bad.append((rec, x, y, z))
                break
    return len(corpus.rows) * 3, bad


# ------------------------------------------------------------------- NSIN

def to_nsin_rows(corpus, flags=0, limit=None):
    rows = []
    for (_rec, x, y, z, _nm, _cl, _b) in corpus.rows[:limit]:
        rows.append((x, y, z, -1, -1, -1, flags, 0))
    return rows


def write_manifest(path, corpus, limit=None):
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("#ordinal\tx\ty\tz\tname\tclasstag\tbodies\n")
        for (rec, x, y, z, nm, cl, b) in corpus.rows[:limit]:
            fh.write("%d\t%d\t%d\t%d\t%s\t%d\t%s\n"
                     % (rec, x, y, z, nm, cl, ",".join(str(i) for i in b)))


def synthetic_rows(nseed, flags=0):
    """The stress corpus: every class against a stride of seeds.

    The NSIN class/seed overrides exist for exactly this.  Real coordinates
    only reach the (class, seed) pairs the galaxy happens to produce, and the
    branchy paths -- class 8's type-10 moons, class 9's 109-iteration phase C,
    the 80-body clamp -- are rare there.  Sweeping the overrides reaches all
    of them, and it costs nothing because no coordinate has to exist.
    """
    step = max(1, 65536 // nseed)
    rows = []
    for cls in range(12):
        for s in range(0, 65536, step):
            rows.append((0, 0, 0, cls, s, -1, flags, 0))
    return rows


def main(argv):
    box = "dl"
    out = os.path.join(HERE, "ns_corpus.nsin")
    manifest = os.path.join(HERE, "ns_corpus.tsv")
    flags = 0
    limit = None
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--box":
            box = argv[i + 1]; i += 1
        elif a == "--out":
            out = argv[i + 1]; i += 1
        elif a == "--manifest":
            manifest = argv[i + 1]; i += 1
        elif a == "--flags":
            flags = int(argv[i + 1]); i += 1
        elif a == "--limit":
            limit = int(argv[i + 1]); i += 1
        elif a == "--synthetic":
            import ns_spec
            n = int(argv[i + 1]); i += 1
            rows = synthetic_rows(n, flags)
            ns_spec.write_nsin(out, rows)
            print("written: %s   (%d synthetic systems, 12 classes x %d seeds)"
                  % (out, len(rows), len(rows) // 12))
            return 0
        i += 1

    print("box: %s" % box)
    c = build(box, verbose=True)
    ncoord, bad = assert_exact_integers(c)
    print("\n(long) shortcut: %d coordinates checked, %d not exact int32"
          % (ncoord, len(bad)))
    if bad:
        for r in bad[:10]:
            print("  NOT AN EXACT INTEGER: %r" % (r,))
        print("FATAL: NOCTIS-0.CPP:4080's (long) chop is not the identity "
              "here; the seed must go through __ftol.")
        return 1

    rows = to_nsin_rows(c, flags=flags, limit=limit)
    import ns_spec
    ns_spec.write_nsin(out, rows)
    write_manifest(manifest, c, limit=limit)
    print("\nwritten: %s   (%d systems)" % (out, len(rows)))
    print("written: %s" % manifest)
    nb = sum(1 for r in c.rows[:limit] if r[6])
    print("systems carrying at least one charted body: %d" % nb)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
