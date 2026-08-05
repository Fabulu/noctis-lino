import struct, sys

path = sys.argv[1] if len(sys.argv) > 1 else r"C:\programmieren\linoleum\work\probew5bpal.bin"
d = open(path, "rb").read()
u = struct.unpack("<" + "I" * (len(d) // 4), d)
HDR = 32
cpm, FRAMES, ROUNDS, NBAT, NPIX = u[0], u[1], u[2], u[3], u[4]
chk = u[5:9]
print(f"counts/ms {cpm}  frames {FRAMES}  rounds {ROUNDS}  batteries {NBAT}  pixels {NPIX}")
print(f"checksums  V0={chk[0]:08X}  V1={chk[1]:08X}  V2={chk[2]:08X}  V5={chk[3]:08X}"
      f"   {'ALL EQUAL' if len(set(chk)) == 1 else '*** MISMATCH ***'}")
print(f"display status {u[9]}  priority {u[10]}")
print()

N = [
    "0  null",
    "1  LUT rebuild, 256 colours",
    "2  tavola_colori filter, 64 col",
    "3  tavola_colori filter, 256 col",
    "4  sky band: 3x shade + LUT 64",
    "5  expand V0 baseline",
    "6  expand V1 unrolled x4",
    "7  expand V2 pre-biased index",
    "8  expand V3 straight copy (floor)",
    "9  expand V4 cycle fused in",
    "10 colour cycle alone",
    "11 expand V5 biased + unrolled",
    "12 page copy 64000",
]

def st(v):
    v = sorted(v)
    return v[len(v) // 2] / cpm, sum(v) / len(v) / cpm, v[0] / cpm, v[-1] / cpm

print(f"{'battery':36s} {'median':>9s} {'mean':>9s} {'min':>9s} {'max':>9s}  {'ns/px':>7s}")
med = {}
for b in range(NBAT):
    allv = []
    for r in range(ROUNDS):
        off = HDR + (r * NBAT + b) * FRAMES
        allv += list(u[off:off + FRAMES])
    m, mn, lo, hi = st(allv)
    med[b] = m
    npx = f"{m*1e6/NPIX:7.2f}" if b >= 5 else "       "
    print(f"{N[b]:36s} {m:9.4f} {mn:9.4f} {lo:9.4f} {hi:9.4f}  {npx}")

print()
null = med[0]
tick = 65536 / 1193182 * 1000
print("net of null, and as a fraction of the 54.9254 ms DOS tick:")
for b in range(1, NBAT):
    v = med[b] - null
    print(f"{N[b]:36s} {v:9.4f} ms   {v/tick*100:6.3f}%")
