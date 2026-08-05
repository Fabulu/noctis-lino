"""Wave 2 / Recon A -- whole-image call graph.

Borland reserves a 5-byte slot for every far call and fills it either with
    9A off16 seg16          (inter-segment, seg16 relocated)
or  90 0E E8 rel16          (NOP; PUSH CS; CALL near  -- same-segment callee)
Both forms are scanned; the NOP makes the push-cs form self-identifying.
"""
import struct, collections
from w2_disasm import load, segments, disasm, fmt, NOCTIS, DL

X87 = set(range(0xD8, 0xE0))

def callgraph(path, dgroup):
    d, hdr, fix = load(path)
    segs = segments(fix, hdr, len(d), dgroup)
    calls = []
    for v, a, b, n in segs:
        i = a
        while i < b - 5:
            if d[i] == 0x9A and (i+3) in fix:
                off, _ = struct.unpack_from('<HH', d, i+1)
                calls.append((i, hdr + fix[i+3]*16 + off, 'far'))
                i += 5
                continue
            # NOP padding before PUSH CS is optional -- Borland omits it when the
            # preceding instruction already leaves the slot 5 bytes wide.
            if d[i] == 0x0E and d[i+1] == 0xE8:
                rel, = struct.unpack_from('<h', d, i+2)
                calls.append((i, a + ((i + 4 - a + rel) & 0xFFFF), 'pushcs'))
                i += 4
                continue
            i += 1
    return d, hdr, fix, segs, calls

def fp_helpers(d, hdr, segs, calls, limit=40):
    cnt = collections.Counter(t for s, t, k in calls)
    rows = []
    for tgt, c in cnt.items():
        body = d[tgt:tgt+limit]
        # x87 opcode preceded by FWAIT is Borland's signature for real FP code
        isfp = any(body[k] == 0x9B and body[k+1] in X87 for k in range(len(body)-1))
        rows.append((tgt, c, isfp))
    return sorted(rows, key=lambda r: -r[1])

if __name__ == '__main__':
    for path, dg, label in ((NOCTIS, 0x2A18, 'NOCTIS.EXE'), (DL, 0x04CD, 'DL.EXE')):
        d, hdr, fix, segs, calls = callgraph(path, dg)
        print('=' * 78)
        print(label, ' segments:')
        for v, a, b, n in segs:
            print(f'    +{v:04X}  file {a}..{b-1}  ({n} bytes)')
        print(f'  far calls={sum(1 for c in calls if c[2]=="far")}  '
              f'pushcs calls={sum(1 for c in calls if c[2]=="pushcs")}  '
              f'distinct targets={len(set(t for s,t,k in calls))}')
        print()
        print('  targets whose body starts with FWAIT+x87 (floating-point helpers):')
        for tgt, c, isfp in fp_helpers(d, hdr, segs, calls):
            if isfp:
                for v, a, b, n in segs:
                    if a <= tgt < b:
                        print(f'    +{v:04X}:{tgt-a:04X}  file {tgt:7d}   {c:4d} calls')
        print()
