import struct, sys, statistics as st

p = r"C:\programmieren\linoleum\work\probew5arch.bin"
u = list(struct.unpack("<464I", open(p, "rb").read()))
h, s = u[:64], u[64:464]

cpms = h[0]
def ms(c): return c / cpms

print("cpms reported            ", cpms)
print()
print("K1  workspace top unit   ", h[1], "units =", h[1]*4, "bytes")
print("    nw[0]                 0x%08X  (want 0x12345678)" % h[2])
print("    nw[top-1]             0x%08X  (want 0x9ABCDEF0)" % h[3])
print()
print("K2  OR of", h[5], "units sampled at stride 997 across the whole workspace:", h[4])
print("    -> workspace is", "ZERO at launch" if h[4] == 0 else "NOT zero -- guards need explicit init")
print()
print("K3  txtr 64 KiB windows, farmalloc-order layout, NO per-buffer padding")
names = ["p_background", "s_background", "n_globes_map", "p_surfacemap", "p_surfacemap+2064"]
for i, n in enumerate(names):
    print("      %-18s base %7d   headroom above window top %+8d" % (n, h[20+2*i], h[21+2*i]))
print("    txchk (0 = every window fits and its top unit is live):", h[10])
print()
print("K6  byte semantics bchk =", h[6], " quadrant qchk =", h[7], " (0 = all pass)")
print()
print("K7  texel sweep over 5 bases x 65536 (U,V) pairs")
print("      min offset reached", h[8], "  max", h[9])
print("      highest workspace unit touched:", h[9], "of", h[1])
print()
print("K5  canary, pads poisoned")
print("      clean check   : fired =", h[30], " units differing =", h[31], "(want 0, 0)")
print("      after a ONE-UNIT overrun of n_globes_map:")
print("      fired = %d (region id+1; n_globes_map is 2)  units differing = %d  at nw offset %d"
      % (h[32], h[33], h[34]))
print()
print("K4  frame cost with the whole 1.87 MB working set resident")
print("    display status", h[14], " physical", h[15], "x", h[16])
nb, ne, npc = h[11], h[12], h[13]
segs = [("back-to-back full frame", s[0:nb]),
        ("palette expand alone   ", s[nb:nb+ne]),
        ("paced full frame       ", s[nb+ne:nb+ne+npc])]
print("    %-24s %8s %8s %8s %8s %8s" % ("battery", "min", "p50", "p90", "max", "mean"))
for n, v in segs:
    v = [ms(x) for x in v]
    vs = sorted(v)
    print("    %-24s %8.4f %8.4f %8.4f %8.4f %8.4f"
          % (n, vs[0], vs[len(vs)//2], vs[int(len(vs)*.9)], vs[-1], st.mean(vs)))
tick = 65536/1193182*1000
p50 = sorted(ms(x) for x in s[0:nb])[nb//2]
e50 = sorted(ms(x) for x in s[nb:nb+ne])[ne//2]
print()
print("    tick = %.4f ms;  full frame p50 = %.4f ms = %.2f%% of a tick" % (tick, p50, 100*p50/tick))
print("    palette expand p50 = %.4f ms = %.3f%% of a tick" % (e50, 100*e50/tick))
