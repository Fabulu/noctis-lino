"""Decode probe_w5b_disp output: per-frame HPT counts -> milliseconds.

Reports median / p10 / p90 / max per battery per round, so warm-up and tail
behaviour are visible instead of being averaged away.
"""
import struct, sys, statistics, os

path = sys.argv[1] if len(sys.argv) > 1 else r"C:\programmieren\linoleum\work\probew5bdisp.bin"
d = open(path, "rb").read()
u = struct.unpack("<" + "I" * (len(d) // 4), d)

HDR = 32
h = u[:HDR]
cpm = h[0]
FRAMES, ROUNDS, NB, NB2 = h[1], h[2], h[3], h[4]
print(f"file            {os.path.basename(path)}  {len(d)} bytes")
print(f"counts/ms       {cpm}")
print(f"frames/battery  {FRAMES}   rounds {ROUNDS}   batteries {NB} + {NB2}")
print(f"final display   {h[5]}x{h[6]}  status {h[7]} (bit0=EXCLUSIVE bit1=ACTIVE)")
print(f"physical screen {h[8]}x{h[9]}")
print(f"resize cost     {h[10]} counts = {h[10]/cpm:.3f} ms")
print(f"wall 320 phase  {h[11]} ms      wall 640 phase {h[12]} ms")
print(f"priority        {h[14]}")
print()

NAMES = [
    "0 null (2 READ COUNTS isocalls)",
    "1 clear 64000 index units",
    "2 palette expand 64000 px",
    "3 RETRACE whole 320x200",
    "4 expand + RETRACE 320x200",
    "5 clear + expand + RETRACE",
    "6 RETRACE, VOID REGION",
    "7 RETRACE, 16x16 live region",
]
NAMES2 = [
    "8 RETRACE whole 640x400",
    "9 expand2x + RETRACE 640x400",
]

def stats(vals):
    v = sorted(vals)
    n = len(v)
    return dict(
        med=v[n // 2] / cpm,
        p10=v[n // 10] / cpm,
        p90=v[(9 * n) // 10] / cpm,
        mn=v[0] / cpm,
        mx=v[-1] / cpm,
        mean=sum(v) / n / cpm,
    )

def dump(base, names, nb):
    per = {}
    print(f"{'battery':34s} {'median':>8s} {'mean':>8s} {'p10':>8s} {'p90':>8s} {'min':>8s} {'max':>8s}")
    for b in range(nb):
        allv = []
        rows = []
        for r in range(ROUNDS):
            off = base + ((r * nb + b) * FRAMES)
            v = list(u[off:off + FRAMES])
            rows.append(v)
            allv += v
        s = stats(allv)
        per[b] = s
        print(f"{names[b]:34s} {s['med']:8.4f} {s['mean']:8.4f} {s['p10']:8.4f} "
              f"{s['p90']:8.4f} {s['mn']:8.4f} {s['mx']:8.4f}")
        rm = "  per-round median: " + "  ".join(f"{stats(x)['med']:.4f}" for x in rows)
        print(rm)
    return per

print("=== 320x200, cooperative ===")
p = dump(HDR, NAMES, NB)
print()
print("=== 640x400 ===")
q = dump(HDR + NB * ROUNDS * FRAMES, NAMES2, NB2)
print()

null = p[0]["med"]
print("--- net of the null battery (median - median(null)) ---")
for b in range(1, NB):
    print(f"{NAMES[b]:34s} {p[b]['med']-null:8.4f} ms")
for b in range(NB2):
    print(f"{NAMES2[b]:34s} {q[b]['med']-null:8.4f} ms")
print()
tick = 65536 / 1193182 * 1000
print(f"DOS tick period = {tick:.4f} ms")
print(f"battery 5 (Noctis-shaped frame) = {(p[5]['med']-null)/tick*100:.2f}% of a tick")
print(f"battery 9 (2x upscale frame)    = {(q[1]['med']-null)/tick*100:.2f}% of a tick")
