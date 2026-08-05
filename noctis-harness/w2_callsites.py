"""Wave 2 / Recon A -- find every call site that resolves to rand().

Large-model Borland: all functions are FAR, so call sites are 9A off16 seg16
with a relocation fixup on the seg16 word. Near (E8) calls are also scanned in
case any intra-segment call slipped through, and the load image is scanned for
far *pointers* to rand (indirect-call material).
"""
import struct, collections, sys
from w2_disasm import load, segments, disasm, fmt, md, NOCTIS, DL

def seg_of(segs, fo):
    for v, a, b, n in segs:
        if a <= fo < b:
            return v, a
    return None, None

def scan(path, dgroup, rand_off, rand_seg=0x0000, label='NOCTIS'):
    d, hdr, fix = load(path)
    segs = segments(fix, hdr, len(d), dgroup)
    code_end = hdr + dgroup*16
    far = []
    for i in range(hdr, code_end - 5):
        if d[i] != 0x9A:
            continue
        off, seg = struct.unpack_from('<HH', d, i+1)
        if off != rand_off:
            continue
        segfo = i + 3
        if segfo not in fix:
            continue            # not a relocated far call -> not a real target
        if fix[segfo] != rand_seg:
            continue
        far.append(i)
    near = []
    for v, a, b, n in segs:
        if v != rand_seg:
            continue
        for i in range(a, b - 2):
            if d[i] != 0xE8:
                continue
            rel, = struct.unpack_from('<h', d, i+1)
            tgt = (i + 3 - a + rel) & 0xFFFF
            if tgt == rand_off:
                near.append(i)
    # far pointers to rand sitting in data (indirect call material)
    ptrs = []
    for fo, val in fix.items():
        if val != rand_seg:
            continue
        o, = struct.unpack_from('<H', d, fo-2) if fo >= 2 else (None,)
        if o == rand_off:
            ptrs.append(fo-2)
    return d, hdr, fix, segs, far, near, ptrs

def report(path, dgroup, rand_off, label):
    d, hdr, fix, segs, far, near, ptrs = scan(path, dgroup, rand_off, 0x0000, label)
    print('=' * 78)
    print(f'{label}: call sites resolving to rand() at seg+0000:{rand_off:04X} '
          f'(file {hdr + rand_off})')
    print('=' * 78)
    print(f'  FAR calls  (9A {rand_off & 0xFF:02X} {rand_off >> 8:02X} + reloc seg=+0000): {len(far)}')
    print(f'  NEAR calls (E8 within seg +0000)                       : {len(near)}')
    print(f'  far POINTERS to rand in relocated data                 : {len(ptrs)}')
    print()
    bysem = collections.Counter()
    rows = []
    for i in far:
        v, a = seg_of(segs, i)
        bysem[v] += 1
        rows.append((i, v, i - a))
    for i in near:
        v, a = seg_of(segs, i)
        bysem[('near', v)] += 1
        rows.append((i, v, i - a))
    rows.sort()
    print('  per code segment:', dict(bysem))
    print()
    print('   #   file_off   seg:off        bytes')
    for n, (fo, v, off) in enumerate(rows):
        print(f'  {n:3d}  {fo:8d}   +{v:04X}:{off:04X}   {d[fo:fo+5].hex(" ")}')
    return d, hdr, fix, segs, rows

if __name__ == '__main__':
    report(NOCTIS, 0x2A18, 0x1862, 'NOCTIS.EXE')
