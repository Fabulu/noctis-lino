import json, os, struct
HERE = os.path.dirname(os.path.abspath(__file__))
M32 = 0xFFFFFFFF
labels = json.load(open(os.path.join(HERE, "probe_w1_arith_labels.json")))
blob = open(r"C:\programmieren\linoleum\work\probew1arith.bin", "rb").read()
vals = struct.unpack("<%dI" % (len(blob) // 4), blob)
assert len(vals) == len(labels), (len(vals), len(labels))

def s32(u):
    u &= M32
    return u - 0x100000000 if u & 0x80000000 else u

def sdiv(a, b):           # C truncation toward zero
    q = abs(a) // abs(b)
    return -q if (a < 0) != (b < 0) else q

def predict(name, x, y):
    if name == "M.signed":   return (s32(x) * s32(y)) & M32
    if name == "M.unsigned": return (x * y) & M32
    if name == "S.shr16":    return (x >> 16) & M32
    if name == "S.sar16":    return (s32(x) >> 16) & M32
    if name == "S.shr16mask":return ((x >> 16) & 0x7FFF)
    if name == "S.sar16mask":return ((s32(x) >> 16) & 0x7FFF)
    if name == "S.low16":    return x & 0xFFFF
    if name == "S.sx16":     return (((x & 0xFFFF) ^ 0x8000) - 0x8000) & M32
    if name == "D.sdiv":     return sdiv(s32(x), 32768) & M32
    if name == "D.udiv":     return (x // 32768) & M32
    if name == "D.sar15":    return (s32(x) >> 15) & M32
    if name == "D.shr15":    return (x >> 15) & M32
    raise KeyError(name)

bad = 0
groups = {}
for (lab, got) in zip(labels, vals):
    name, x, y = lab
    want = predict(name, x, y)
    ok = (got == want)
    if not ok: bad += 1
    groups.setdefault(name, []).append((x, y, got, want, ok))

print("slots:", len(vals), " mismatches vs model:", bad)
print()
for name in ["M.signed", "M.unsigned"]:
    pass
print("== M: 32x32 -> low 32 ==")
for i in range(0, len(groups["M.signed"])):
    xs, ys, gs, ws, oks = groups["M.signed"][i]
    xu, yu, gu, wu, oku = groups["M.unsigned"][i]
    print("  %08X * %08X   signed=%08X %s   unsigned=%08X %s   agree=%s"
          % (xs, ys, gs, "ok" if oks else "MODEL=%08X" % ws,
             gu, "ok" if oku else "MODEL=%08X" % wu, gs == gu))
print()
print("== S: shift right 16 and mask ==")
n = len(groups["S.shr16"])
for i in range(n):
    s = groups["S.shr16"][i][0]
    shr  = groups["S.shr16"][i][2]
    sar  = groups["S.sar16"][i][2]
    shrm = groups["S.shr16mask"][i][2]
    sarm = groups["S.sar16mask"][i][2]
    low  = groups["S.low16"][i][2]
    sx   = groups["S.sx16"][i][2]
    print("  s=%08X  >16=%08X  >>16=%08X  (>16)&7FFF=%04X  (>>16)&7FFF=%04X  masked-agree=%s  s&FFFF=%04X  sx16=%d"
          % (s, shr, sar, shrm, sarm, shrm == sarm, low, s32(sx)))
print()
print("== D: divide by 32768 ==")
for i in range(len(groups["D.sdiv"])):
    v = groups["D.sdiv"][i][0]
    sd = groups["D.sdiv"][i][2]; sdok = groups["D.sdiv"][i][4]
    ud = groups["D.udiv"][i][2]; udok = groups["D.udiv"][i][4]
    sa = groups["D.sar15"][i][2]
    sh = groups["D.shr15"][i][2]
    print("  v=%08X (%12d)  /32768=%12d %s  '/32768=%10u %s  >>15=%12d  >15=%10u   sdiv==sar15:%s"
          % (v, s32(v), s32(sd), "ok" if sdok else "MODEL %d" % s32(groups['D.sdiv'][i][3]),
             ud, "ok" if udok else "MODEL %u" % groups['D.udiv'][i][3],
             s32(sa), sh, s32(sd) == s32(sa)))
