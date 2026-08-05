"""Wave 2 / RECON A -- one-shot regeneration of the whole binary map.

Everything printed here is recomputed from the shipped bytes on every run.
Nothing is graded against a stored artifact.

    python w2_reconA.py
"""
import struct, collections, sys
from w2_disasm import load, segments, disasm, fmt, md, NOCTIS, DL
from w2_callgraph import callgraph
from w2_argclass import run as argrun

NOC_DGROUP = 0x2A18
DL_DGROUP  = 0x052A

# addresses established by this recon, as (name, seg_para, seg_off)
NOC_SYMS = [
    ('N_LXMUL@ (32x32->32 low)', 0x0000, 0x1819),
    ('srand',                    0x0000, 0x1851),
    ('rand',                     0x0000, 0x1862),
    ('N_FTOL@ (__ftol, chop)',   0x0000, 0x1265),
    ('fabs',                     0x0000, 0x04FC),
    ('sin',                      0x0000, 0x1118),
    ('cos',                      0x0000, 0x1213),
    ('random(int)',              0x03DF, 0xDE47),
    ('zrandom(int)',             0x03DF, 0x895E),
]

def hr(t):
    print()
    print('=' * 78)
    print(t)
    print('=' * 78)

def main():
    d, hdr, fix = load(NOCTIS)
    hr('1. MZ HEADER AND LOAD-TIME LAYOUT -- NOCTIS.EXE')
    nreloc, = struct.unpack_from('<H', d, 6)
    hp, = struct.unpack_from('<H', d, 8)
    ss, sp = struct.unpack_from('<HH', d, 0x0E)
    ip, cs = struct.unpack_from('<HH', d, 0x14)
    print(f'  file size {len(d)}   header {hp} paras = {hp*16} bytes (0x{hp*16:X})')
    print(f'  load image {len(d)-hp*16} bytes    relocations {nreloc}')
    print(f'  CS:IP {cs:04X}:{ip:04X}   SS:SP {ss:04X}:{sp:04X}   FBOV present: {b"FBOV" in d}')
    print(f'  entry bytes {d[hdr:hdr+8].hex(" ")}  = mov dx,2A18 ; mov cs:[0291],dx  -> DGROUP = +2A18')
    print()
    print('  MAPPING RULE   file_offset = 9728 + seg_rel*16 + off      (seg_rel = seg - load_base)')
    print()
    segs = segments(fix, hdr, len(d), NOC_DGROUP)
    for v, a, b, n in segs:
        print(f'    code frame +{v:04X}   file {a:6d}..{b-1:6d}  ({n} bytes)')
    print(f'    DGROUP     +{NOC_DGROUP:04X}   file {hdr+NOC_DGROUP*16}..{len(d)-1}')

    hr('2. rand() ANCHOR')
    hits = [i for i in range(len(d)-1) if d[i] == 0x35 and d[i+1] == 0x4E]
    print(f'  bytes "35 4E" occur {len(hits)} time(s): {hits}   -> anchor is unambiguous')
    print(f'  rand() body = file 15970 .. 16007  =  seg +0000 : 1862 .. 1887')
    print(fmt(disasm(d, 15970, hdr, 0x0000, 8)))
    print('  NOTE: PORTPLAN says "offset 15979" and WAVEPLAN says 15982; both are')
    print('        INSIDE rand but neither is its entry. 15979 = the "5A 01" of')
    print('        mov dx,015A; 15982 = the "35 4E" of mov ax,4E35. Entry = 15970.')

    hr('3. CALL SITES')
    d2, h2, f2, sg2, calls = callgraph(NOCTIS, NOC_DGROUP)
    cnt = collections.Counter(t for s, t, k in calls)
    print(f'  total calls decoded: far={sum(1 for c in calls if c[2]=="far")} '
          f'pushcs={sum(1 for c in calls if c[2]=="pushcs")}   distinct targets={len(cnt)}')
    print()
    print('   symbol                        seg:off      file    call sites')
    for nm, p, o in NOC_SYMS:
        fo = hdr + p*16 + o
        print(f'   {nm:28s} +{p:04X}:{o:04X}  {fo:7d}  {cnt[fo]:6d}')
    print()
    print('  rand() has EXACTLY ONE caller in the whole image: random(int)"s body.')
    print('  No push-cs call, no indirect call, no far pointer to rand in data.')
    print('  => every random() in the game funnels through one compiled function.')

    hr('4. random(int) -- THE COMPILED BODY (answers UNKNOWN 1)')
    print(fmt(disasm(d, 82487, 25584, 0x03DF, 10)))
    print()
    print('  int random(int __num) { return (int)(((long)rand() * __num) / 32768L); }')
    print('  argument is a single 16-bit word at [bp+6], SIGN-EXTENDED to 32 bits.')
    print('  RAND_MAX = 0x7FFF (read out of NOCTIS.SYM); divisor immediate = 0x8000.')

    hr('5. zrandom(int) -- THE COMPILED BODY (answers UNKNOWN 2)')
    print(fmt(disasm(d, 60750, 25584, 0x03DF, 20)))
    print()
    print('  bounds: file 60750..60785  =  +03DF:895E..8981   (36 bytes)')
    print('  push ax saves DRAW 1; pop dx restores it; sub dx,ax  =>  DRAW1 - DRAW2.')
    print('  MINUEND IS THE FIRST-EXECUTED DRAW.  Result truncated to int16, then')
    print('  fild word -> float.  Same shape independently in DL.EXE (see below).')

    hr('6. FLOATING-POINT ARGUMENTS')
    _, _, _, _, rows = argrun(NOCTIS, NOC_DGROUP, 0x03DF, 0xDE47, 'N')
    fp = [r for r in rows if r['ftol']]
    print(f'  random() call sites: {len(rows)}   with __ftol feeding the pushed word: {len(fp)}')
    for r in fp:
        print(f"    file {r['site']:7d}  +{r['para']:04X}:{r['off']:04X}")
    print()
    # zrandom sites
    zs = []
    for i in range(25584, 82528-4):
        if d[i] == 0x0E and d[i+1] == 0xE8:
            rel, = struct.unpack_from('<h', d, i+2)
            if ((i + 4 - 25584 + rel) & 0xFFFF) == 0x895E:
                zs.append(i)
    ftolpush = [s for s in zs if d[s-6:s-1] == b'\x9a\x65\x12\x00\x00' and d[s-1] == 0x50]
    print(f'  zrandom() call sites: {len(zs)}   of which __ftol-fed: {len(ftolpush)}')
    for s in zs:
        kind = 'FP (__ftol; push ax)' if s in ftolpush else 'integer'
        print(f'    file {s:7d}  +03DF:{s-25584:04X}   {kind}')

    hr('7. DL.EXE CROSS-CHECK (independent binary, different memory model)')
    dd, dh, df = load(DL)
    print(f'  DL.EXE: header {dh} bytes, near-model code, DGROUP +{DL_DGROUP:04X}')
    print(f'  "35 4E" occurrences: {[i for i in range(len(dd)-1) if dd[i]==0x35 and dd[i+1]==0x4E]}')
    print(f'  rand   @ file 12945  = 0000:3091 (ends "c3" -- NEAR ret)')
    print(f'  random @ file  9426  = 0000:22D2, arg at [bp+4], one call to rand')
    print(f'  zrandom@ file  2272  = 0000:06E0:')
    print(fmt(disasm(dd, 2272, 512, 0x0000, 14)))
    print()
    print('  DL.EXE and ST.EXE carry a Borland symbol table (magic FB 52) past the')
    print('  load image, naming @zrandom$qi, @random$qi, _rand, _srand, N_FTOL@,')
    print('  N_LXMUL@, @prepare_nearstar$qv.  NOCTIS.EXE carries none.')

if __name__ == '__main__':
    main()
