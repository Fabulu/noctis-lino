"""Wave 2 / Recon A -- classify every random() call site by how its argument
was produced: x87 (floating-point expression) vs pure integer.
"""
import struct, collections, sys
from w2_disasm import load, segments, disasm, fmt, md, NOCTIS, DL

X87 = set(range(0xD8, 0xE0))

def sites_of(d, hdr, fix, segs, tgt_para, tgt_off):
    far, pcs = [], []
    for v, a, b, n in segs:
        for i in range(a, b - 4):
            if d[i] == 0x9A:
                off, seg = struct.unpack_from('<HH', d, i+1)
                if off == tgt_off and fix.get(i+3) == tgt_para:
                    far.append(i)
            elif d[i] == 0x0E and d[i+1] == 0xE8 and v == tgt_para:
                rel, = struct.unpack_from('<h', d, i+2)
                if ((i + 4 - a + rel) & 0xFFFF) == tgt_off:
                    pcs.append(i)
    return sorted(far + pcs), set(far), set(pcs)

def decode_window(d, start, end, seg_base):
    """Linear-sweep a window; return list of insns. Sweep is anchored by trying
    every start offset and keeping the decoding that consumes the window with
    no invalid instruction and lands exactly on `end`."""
    best = None
    for s in range(start, end):
        rows, ok, addr = [], True, s
        for ins in md.disasm(d[s:end], s - seg_base):
            rows.append(ins)
            addr = s + (ins.address - (s - seg_base)) + ins.size
        if rows and addr == end:
            best = rows
            break
    return best or []

def classify(path, dgroup, tgt_para, tgt_off, label, window=40):
    d, hdr, fix = load(path)
    segs = segments(fix, hdr, len(d), dgroup)
    sites, far, pcs = sites_of(d, hdr, fix, segs, tgt_para, tgt_off)
    ftol_para, ftol_off = 0x0000, 0x1265
    res = []
    for s in sites:
        for v, a, b, n in segs:
            if a <= s < b:
                base, para = a, v
                break
        win = d[max(base, s-window):s]
        has_x87 = any(bb in X87 for bb in win)
        # __ftol call inside window?
        ftol = False
        for k in range(len(win)-4):
            if win[k] == 0x9A:
                o, sg = struct.unpack_from('<HH', win, k+1)
                fo = max(base, s-window) + k
                if o == ftol_off and fix.get(fo+3) == ftol_para:
                    ftol = True
            if win[k] == 0x0E and win[k+1] == 0xE8 and para == ftol_para:
                rel, = struct.unpack_from('<h', win, k+2)
                fo = max(base, s-window) + k
                if ((fo + 4 - base + rel) & 0xFFFF) == ftol_off:
                    ftol = True
        res.append((s, para, s-base, 'far' if s in far else 'pushcs',
                    has_x87, ftol, win.hex(' ')))
    return d, hdr, fix, segs, res

if __name__ == '__main__':
    d, hdr, fix, segs, res = classify(NOCTIS, 0x2A18, 0x03DF, 0xDE47, 'NOCTIS')
    n_x87 = sum(1 for r in res if r[4])
    n_ftol = sum(1 for r in res if r[5])
    print(f'random() call sites: {len(res)}')
    print(f'  with x87 opcode (D8-DF) in preceding 40 bytes : {n_x87}')
    print(f'  with a __ftol call in preceding 40 bytes       : {n_ftol}')
    print()
    print('SITES WITH FLOATING-POINT ARGUMENT CONSTRUCTION:')
    print(' file_off   seg:off     form    x87 ftol   preceding 40 bytes')
    for s, para, off, form, x, f, w in res:
        if x or f:
            print(f' {s:8d}  +{para:04X}:{off:04X} {form:7s} {int(x)}   {int(f)}    {w}')
