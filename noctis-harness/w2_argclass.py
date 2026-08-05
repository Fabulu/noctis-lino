"""Wave 2 / Recon A -- exact classification of the argument produced at every
random() call site, by decoding the instruction that pushes it.

Borland cdecl, 16-bit: the argument word is pushed immediately before the call
(the `90` in the `90 0E E8` push-cs thunk is padding that belongs to the call).
"""
import struct, collections
from w2_disasm import load, segments, md, NOCTIS, DL

FTOL = (0x0000, 0x1265)          # __ftol / FTOL@ in NOCTIS.EXE

def find_sites(d, hdr, fix, segs, tgt_para, tgt_off):
    out = []
    for v, a, b, n in segs:
        for i in range(a, b - 4):
            if d[i] == 0x9A:
                off, _ = struct.unpack_from('<HH', d, i+1)
                if off == tgt_off and fix.get(i+3) == tgt_para:
                    out.append((i, v, a, 'far', 5))
            elif d[i] == 0x0E and d[i+1] == 0xE8 and v == tgt_para:
                rel, = struct.unpack_from('<h', d, i+2)
                if ((i + 4 - a + rel) & 0xFFFF) == tgt_off:
                    out.append((i, v, a, 'pushcs', 4))
    out.sort()
    return out

def push_before(d, site, form):
    """Return (start_off, bytes, mnemonic) of the push feeding the call."""
    end = site - 1 if (form == 'pushcs' and d[site-1] == 0x90) else site
    # strip Borland's post-x87-store sync idiom (NOP;FWAIT) and stray FWAITs
    while d[end-1] in (0x90, 0x9B):
        end -= 1
    # try instruction lengths 1..5 ending exactly at `end`
    for ln in (1, 2, 3, 4, 5, 6):
        s = end - ln
        ins = list(md.disasm(d[s:end], 0))
        if len(ins) == 1 and ins[0].size == ln and ins[0].mnemonic.startswith('push'):
            return s, d[s:end], f'{ins[0].mnemonic} {ins[0].op_str}'
    return None, d[end-6:end], '??'

def preceded_by_ftol(d, fix, pstart):
    """Is the pushed AX the direct result of a __ftol call?"""
    if pstart is None:
        return False
    # far form: 9A 65 12 <seg>
    if pstart >= 5 and d[pstart-5] == 0x9A:
        off, _ = struct.unpack_from('<HH', d, pstart-4)
        if off == FTOL[1] and fix.get(pstart-2) == FTOL[0]:
            return True
    # push-cs form of the __ftol call (only reachable from segment +0000)
    if pstart >= 5 and d[pstart-5] == 0x90 and d[pstart-4] == 0x0E and d[pstart-3] == 0xE8:
        return 'maybe-pushcs-ftol'
    return False

def run(path, dgroup, tgt_para, tgt_off, label):
    d, hdr, fix = load(path)
    segs = segments(fix, hdr, len(d), dgroup)
    sites = find_sites(d, hdr, fix, segs, tgt_para, tgt_off)
    rows = []
    for site, para, base, form, sz in sites:
        ps, pb, pm = push_before(d, site, form)
        ftol = preceded_by_ftol(d, fix, ps)
        rows.append(dict(site=site, para=para, off=site-base, form=form,
                         push=pm, pushbytes=pb.hex(' '), ftol=ftol))
    return d, hdr, fix, segs, rows

if __name__ == '__main__':
    d, hdr, fix, segs, rows = run(NOCTIS, 0x2A18, 0x03DF, 0xDE47, 'NOCTIS')
    print(f'random() call sites in NOCTIS.EXE: {len(rows)}')
    kinds = collections.Counter()
    for r in rows:
        p = r['push']
        if p.startswith('push') and p.split()[-1].startswith('0x') and 'ptr' not in p:
            kinds['immediate constant'] += 1
        elif r['ftol']:
            kinds['push ax <- __ftol (FLOATING POINT ARGUMENT)'] += 1
        elif p == '??':
            kinds['UNDECODED'] += 1
        else:
            kinds['register / memory word'] += 1
    for k, v in kinds.most_common():
        print(f'   {k:48s} {v}')
    print()
    print('--- FLOATING-POINT ARGUMENT SITES (__ftol immediately feeding random) ---')
    for r in rows:
        if r['ftol']:
            print(f"  file {r['site']:7d}  +{r['para']:04X}:{r['off']:04X}  {r['form']:7s}  "
                  f"{r['pushbytes']}  {r['push']}")
    print()
    print('--- UNDECODED ---')
    for r in rows:
        if r['push'] == '??':
            print(f"  file {r['site']:7d}  +{r['para']:04X}:{r['off']:04X}  {r['form']:7s}  {r['pushbytes']}")
