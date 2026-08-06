r"""su_break.py - break every check, and show which one catches it.

A check with no demonstrated falsifier is a claim, not a check.  This file
takes su_spec.py / su_fp.py, applies ONE localised textual edit, imports the
result as a fresh module in a private directory, and re-runs the ten captures.
The driver, the corpus and the reference artefacts never change.

Each row reports which check fired and on how many of the ten captures.  A
sabotage that NOTHING catches is printed as such and is evidence about the
check set, not a pass - see SRANDONCE, which exists precisely to measure the
void that U3 refuses to claim.
"""

import importlib
import os
import shutil
import struct
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import numpy as np

import su_corpus
import su_ledger

RECON = su_corpus.RECON
REC_SZ = 64800 + 32400 + 768 + 24
CBIN = open(os.path.join(HERE, "su_ref.bin"), "rb").read()

# name -> (file, old, new, what it models)
MUTS = [
 ("TYPE3ASSIGN", "su_spec.py",
  "                nv = (pb[di] + bl) & 0xFF",
  "                nv = bl",
  "niv-lr ASSIGNS the land noise where vanilla ADDs it (:4915)"),
 ("TYPE3BYTE", "su_spec.py",
  "                    pb[(di + 1) & M16] = 0x00   # the word store's high byte",
  "                    pass",
  "byte store instead of vanilla's `mov WORD ptr es:[di],3Eh` (:4919)"),
 ("NOISESKIP", "su_spec.py",
  """            if cur < gl:
                pb[di] = 16""",
  """            if cur < gl:
                ax = (ax + cx) & M16
                sv = ax - 0x10000 if ax & 0x8000 else ax
                p = (sv * sv) & 0xFFFFFFFF
                dx = (p >> 16) & M16
                ax = ((p & M16) + dx) & M16
                pb[di] = 16""",
  "advance the noise register on the sea branch too"),
 ("WAVEPLUS4", "su_spec.py",
  "            ax = (ax + 4) & M16",
  "            ax = (ax + 0) & M16",
  "treat wave()'s `add ax,4` as something other than offset(p_background)"),
 ("LSSM1", "su_spec.py",
  "        n = ((self.QUADWORDS - 80) << 2) & M16",
  "        n = (((self.QUADWORDS - 80) << 2) & M16) - 1",
  "niv-lr's lssmooth smooths one pixel fewer"),
 ("T9NOCLEAR", "su_spec.py",
  "            self.pclear(0x1F)",
  "            pass",
  "type 9 not filling the surface buffer - niv-lr paints the offscreen page"),
 ("PSGLANE", "su_spec.py",
  """            al = al + ((e >> np.uint32(16)) & np.uint32(0xFF))
            al = al + ((e >> np.uint32(24)) & np.uint32(0xFF))
            al &= np.uint32(0xFF)
            al >>= np.uint32(2)
            v[p:p + L] = al.astype(np.uint8)
            off += L

    def pclear""",
  """            al &= np.uint32(0xFF)
            al >>= np.uint32(2)
            v[p:p + L] = al.astype(np.uint8)
            off += L

    def pclear""",
  "psmooth_grays summing two lanes instead of four (niv-lr's uint8_t)"),
 ("STORMTRUNC", "su_spec.py",
  """    def storm(self):
        self.g = 1
        while self.g < self.cr:
            for a in ASEQ4:
                self.a = a
                self.px = d2u16(self.cx + self.g * math.cos(a))
                self.py = d2u16(self.cy + self.g * math.sin(a))""",
  """    def storm(self):
        self.g = 1
        while self.g < self.cr:
            for a in ASEQ4:
                self.a = a
                self.px = d2u16(self.cx + int(self.g * math.cos(a)))
                self.py = d2u16(self.cy + int(self.g * math.sin(a)))""",
  "niv-lr's inner cast in storm(): trunc the product before adding the "
  "centre, which differs from trunc-the-sum for every negative product"),
 ("ARGORDER", "su_spec.py",
  """            thr = i16(25 + F.rfr(3, 4963))
            kq = f32(ext(ext(_Fr(F.rfr(350, 4963)) / 100) + _Fr(4.0)))
            kt = f32(ext(ext(_Fr(F.rfr(200, 4962)) / 900) + _Fr(0.6)))""",
  """            kt = f32(ext(ext(_Fr(F.rfr(200, 4962)) / 900) + _Fr(0.6)))
            kq = f32(ext(ext(_Fr(F.rfr(350, 4963)) / 100) + _Fr(4.0)))
            thr = i16(25 + F.rfr(3, 4963))""",
  "contrast()'s arguments evaluated left to right instead of right to left"),
 ("SUBORDER", "su_spec.py",
  "        r1 = float(r + B.random(c, 5166) - B.random(c, 5166))",
  "        _s = B.random(c, 5166); r1 = float(r + B.random(c, 5166) - _s)",
  "`x + random(c) - random(c)` evaluated right to left"),
 ("SEEDTRUNC", "su_spec.py",
  "        F.srand(ftol32(_Fr(seedval) + 4112))",
  "        F.srand(ftol32(_Fr(ftol32(_Fr(seedval))) + 4112))",
  "truncate seedval BEFORE adding 4112 (niv-lr's order)"),
 ("FTOLSAT", "su_fp.py",
  """    lo = ftol64(v) & 0xFFFFFFFF
    return lo - 0x100000000 if lo & 0x80000000 else lo""",
  """    t = ftol64(v)
    if t > 2147483647:
        return 2147483647
    if t < -2147483648:
        return -2147483648
    return t""",
  "a saturating __ftol instead of one that keeps the low 32 bits"),
 ("LOOP91", "su_spec.py",
  "ASEQ4 = _accum(0.0, _STEP4, stop=TWO_PI)",
  "ASEQ4 = _accum(0.0, _STEP4, count=90)",
  "keeping `a` in a double, so the angle loop runs 91 times not 90"),
 # CRATERWRAP is deliberately NOT in this list, and the reason is the point:
 # `(px + ((360*py) & M16)) & M16` and `(px + 360*py) & M16` are EQUAL for
 # every input, so that edit is provably a no-op and the "check" it exercised
 # could never fail.  A vptr genuinely wider than 16 bits cannot be expressed
 # in this model at all, because Wave 5's buffer model makes p_background a
 # 65,536-byte SEGMENT and every index goes through `& M16` by construction.
 # C7 - bytes 64,800..65,551 zero after every capture - is the check that
 # would catch it in a model where it could occur, and C7 grades 10/10.
 ("RNDPATUNSIGNED", "su_spec.py",
  """            sv = ax - 0x10000 if ax & 0x8000 else ax
            p = (sv * sv) & 0xFFFFFFFF
            dx = (p >> 16) & M16
            ax = ((p & M16) + dx) & M16
            pb[di] = ax & 0x3E""",
  """            sv = ax
            p = (sv * sv) & 0xFFFFFFFF
            dx = (p >> 16) & M16
            ax = ((p & M16) + dx) & M16
            pb[di] = ax & 0x3E""",
  "MUL instead of IMUL in the base-noise hash"),
 ("SSMOOTHCHUNK", "su_spec.py",
  "        step = 320",
  "        step = 360",
  "ssmooth vectorised in chunks of 360, so the last three iterations of every "
  "chunk read stale bytes.  This one is not hypothetical - it is the bug this "
  "reference actually had, and it cost 196/614/3724 pixels on types 7/4/0."),
 ("SRANDONCE", "su_spec.py",
  "        B.srand(seed)                           # :4844  UNGRADED (§2 U3):",
  "        pass  #                                 # :4844  UNGRADED (§2 U3):",
  "delete the second srand(seed).  EXPECTED TO BE CAUGHT BY NOTHING - it is "
  "run to measure the void, not to pass."),
]


def build(mutname, fname, old, new, tmp):
    for f in ("su_fp.py", "su_spec.py", "brtl_oracle.py"):
        shutil.copy(os.path.join(HERE, f), os.path.join(tmp, f))
    p = os.path.join(tmp, fname)
    s = open(p, encoding="utf-8").read()
    if old not in s:
        return False
    s = s.replace(old, new, 1)
    open(p, "w", encoding="utf-8").write(s)
    return True


def run_all(mod, rows, kind="capture"):
    out = []
    for r in rows:
        if r["kind"] != kind:
            continue
        S = mod.Surface(ledger=False)
        if r["use_scaled"]:
            S._secs_scaled = r["secs_scaled"]
        o = S.run(r["id"], r["type"], r["seedval"], r["colorbase"], secs=0.0,
                  plwp=r["plwp"], owner=r["owner"], nearstar_rgb=r["rgb"])
        out.append((r, S, o))
    return out


def verdict(res, rows):
    """which checks fire, and on how many captures"""
    hit = dict(C1=0, C2=0, C3=0, C7=0, D2=0, E1e=0)
    for r, S, o in res:
        ref = open(os.path.join(RECON, r["tag"] + ".p_background"), "rb").read()
        rov = open(os.path.join(RECON, r["tag"] + ".objectschart"), "rb").read()
        want = b"".join(bytes(t) for t in r["manifest"]["palette_192_255"])
        cb = r["colorbase"]
        if S.map_bytes() != ref[:64800]:
            hit["C1"] += 1
        if S.ovl_bytes() != rov[:32400]:
            hit["C2"] += 1
        if bytes(S.tmppal)[3 * cb:3 * cb + 192] != want:
            hit["C3"] += 1
        if sum(S.pseg[4 + 64800:4 + 65552]):
            hit["C7"] += 1
        try:
            if su_ledger.predict(r["type"], cb, S.gates) != \
               (o.get("fast_n"), o.get("brtl_n")):
                hit["D2"] += 1
        except Exception:
            hit["D2"] += 1
        # E1e on captures: rtperiod/rotation vs the cref trailer.  This is the
        # check the dead `E1e=0` key above was pretending to be.  It fires for
        # any mutation that moves the +4112 bridge's two outputs on a capture.
        ci = rows.index(r)
        cnt = struct.unpack_from("<6i", CBIN, ci * REC_SZ + 97968)
        if o.get("rtperiod", 0) != cnt[2] or o.get("rotation", 0) != cnt[3]:
            hit["E1e"] += 1
    return hit


def main():
    rows = su_corpus.all_cases()
    n_cap = sum(1 for r in rows if r["kind"] == "capture")
    print("%-15s %-38s %s" % ("sabotage", "caught by", "modelled defect"))
    print("-" * 110)
    uncaught = []
    for name, fname, old, new, why in MUTS:
        tmp = tempfile.mkdtemp(prefix="subrk_")
        try:
            if not build(name, fname, old, new, tmp):
                print("%-15s %-38s %s" % (name, "EDIT DID NOT APPLY", why))
                continue
            sys.path.insert(0, tmp)
            for m in ("su_spec", "su_fp", "brtl_oracle"):
                sys.modules.pop(m, None)
            mod = importlib.import_module("su_spec")
            try:
                res = run_all(mod, rows)
                hit = verdict(res, rows)
            except Exception as exc:
                hit = None
                err = "%s: %s" % (type(exc).__name__, exc)
            sys.path.remove(tmp)
            for m in ("su_spec", "su_fp", "brtl_oracle"):
                sys.modules.pop(m, None)
            # E1 on the SYNTHETIC cases: su_ref.exe is not mutated, so a
            # defect that no capture can reach may still show up here.  This
            # is BOUNDED evidence (two readings of one text), never EXACT.
            try:
                syn = run_all(mod, rows, kind="synthetic")
                e1 = 0
                for k, (rr, SS, oo) in enumerate(syn):
                    idx = [x for x in rows if x["kind"] == "synthetic"].index(rr)
                    off = (len(rows) - len(syn) + idx) * REC_SZ
                    cnt = struct.unpack_from("<6i", CBIN, off + 97968)
                    # The +4112 bridge feeds only rtperiod/rotation and is
                    # RESEEDED before the map, so map_bytes alone cannot see a
                    # defect there.  Check the two outputs it actually moves -
                    # this is SEEDTRUNC's blind spot.  (Three separate tests,
                    # not one OR: w5audit's sampler never draws the all-equal
                    # case, so a single OR of three != reads as always-true.)
                    if SS.map_bytes() != CBIN[off:off + 64800]:
                        e1 += 1
                    elif oo.get("rtperiod", 0) != cnt[2]:
                        e1 += 1
                    elif oo.get("rotation", 0) != cnt[3]:
                        e1 += 1
                if e1:
                    fired_syn = "E1(synthetic) %d/%d" % (e1, len(syn))
                else:
                    fired_syn = ""
            except Exception:
                fired_syn = ""
            if hit is None:
                print("%-15s %-38s %s" % (name, "CRASH " + err[:30], why))
                continue
            fired = ["%s %d/%d" % (k, v, n_cap) for k, v in
                     sorted(hit.items()) if v]
            if fired_syn:
                fired.append(fired_syn)
            if not fired:
                uncaught.append(name)
                print("%-15s %-38s %s" % (name, "*** NOTHING ***", why))
            else:
                print("%-15s %-38s %s" % (name, ", ".join(fired), why))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    import su_spec  # restore the real one for anything downstream
    print("\nuncaught:", uncaught or "none")


if __name__ == "__main__":
    main()
