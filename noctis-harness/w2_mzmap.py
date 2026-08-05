"""Wave 2 / Recon A -- MZ header parse + load-image map for NOCTIS.EXE and DL.EXE.

Read-only. Prints the header fields, the relocation table summary, the
file-offset <-> segment:offset mapping rule, and verifies the rand() anchor.
"""
import struct, sys, collections

def parse_mz(path):
    d = open(path, 'rb').read()
    (sig, lastpage, pages, nreloc, hdrparas, minalloc, maxalloc,
     ss, sp, csum, ip, cs, lfarlc, ovno) = struct.unpack_from('<2sHHHHHHHHHHHHH', d, 0)
    hdr_bytes = hdrparas * 16
    if lastpage:
        image_bytes = (pages - 1) * 512 + lastpage
    else:
        image_bytes = pages * 512
    load_bytes = image_bytes - hdr_bytes
    relocs = []
    for i in range(nreloc):
        off, seg = struct.unpack_from('<HH', d, lfarlc + 4*i)
        relocs.append((seg, off))
    return dict(data=d, sig=sig, lastpage=lastpage, pages=pages, nreloc=nreloc,
                hdrparas=hdrparas, hdr_bytes=hdr_bytes, minalloc=minalloc,
                maxalloc=maxalloc, ss=ss, sp=sp, csum=csum, ip=ip, cs=cs,
                lfarlc=lfarlc, ovno=ovno, image_bytes=image_bytes,
                load_bytes=load_bytes, filesize=len(d), relocs=relocs)

def report(path):
    m = parse_mz(path)
    d = m['data']
    print('=' * 78)
    print('FILE', path)
    print('=' * 78)
    print(f"  signature            {m['sig']!r}")
    print(f"  file size            {m['filesize']} (0x{m['filesize']:X})")
    print(f"  pages / lastpage     {m['pages']} / {m['lastpage']}")
    print(f"  image bytes (hdr+ld) {m['image_bytes']} (0x{m['image_bytes']:X})")
    print(f"  overlay/extra bytes  {m['filesize'] - m['image_bytes']}")
    print(f"  header paragraphs    {m['hdrparas']}  -> header bytes {m['hdr_bytes']} (0x{m['hdr_bytes']:X})")
    print(f"  load image bytes     {m['load_bytes']} (0x{m['load_bytes']:X})")
    print(f"  min/max alloc paras  {m['minalloc']} / {m['maxalloc']}")
    print(f"  initial SS:SP        {m['ss']:04X}:{m['sp']:04X}")
    print(f"  initial CS:IP        {m['cs']:04X}:{m['ip']:04X}")
    print(f"  reloc count / table  {m['nreloc']} @ 0x{m['lfarlc']:X}")
    print(f"  overlay number       {m['ovno']}")
    # FBOV check
    print(f"  FBOV signature       {'PRESENT' if b'FBOV' in d else 'ABSENT (not overlaid)'}")
    ep_off = m['hdr_bytes'] + m['cs'] * 16 + m['ip']
    print(f"  entry point file off {ep_off} (0x{ep_off:X})")
    print(f"  entry bytes          {d[ep_off:ep_off+16].hex(' ')}")
    print()
    print("  MAPPING RULE (load base = paragraph LB at runtime):")
    print(f"    file_offset = {m['hdr_bytes']} + (seg_rel * 16) + off      where seg_rel = seg - LB")
    print(f"    seg_rel:off  such that seg_rel*16+off = file_offset - {m['hdr_bytes']}")
    print()
    # relocation histogram by target segment
    segs = collections.Counter(s for s, o in m['relocs'])
    print(f"  distinct reloc segments: {len(segs)}; top 12 by count:")
    for s, c in segs.most_common(12):
        print(f"    seg {s:04X}  {c} fixups")
    print()
    # The set of segment values that appear in the reloc *values* (i.e. the
    # segments actually referenced) tells us the segment layout.
    vals = collections.Counter()
    for s, o in m['relocs']:
        fo = m['hdr_bytes'] + s * 16 + o
        if fo + 2 <= m['filesize']:
            v, = struct.unpack_from('<H', d, fo)
            vals[v] += 1
    print(f"  distinct relocated segment VALUES (relative): {len(vals)}")
    for v, c in sorted(vals.items()):
        print(f"    +{v:04X}  x{c}   (file region {m['hdr_bytes']+v*16}..)")
    print()
    return m

def find_anchor(m, path):
    d = m['data']
    print('-' * 78)
    print('rand() ANCHOR SEARCH in', path)
    hits = [i for i in range(len(d) - 1) if d[i] == 0x35 and d[i+1] == 0x4E]
    print(f"  occurrences of bytes 35 4E : {len(hits)} -> {[hex(h) for h in hits]} = {hits}")
    for h in hits:
        start = h - 8
        print(f"  context around {h} (0x{h:X}):")
        print(f"    {d[start:h+24].hex(' ')}")
    # also the full 32-bit constant 0x015A4E35 as an immediate pair
    print(f"  occurrences of '5A 01' : {[i for i in range(len(d)-1) if d[i]==0x5A and d[i+1]==0x01][:20]}")
    return hits

if __name__ == '__main__':
    for p in [r'C:\programmieren\noctis\niv-plus\modules\NOCTIS.EXE',
              r'C:\programmieren\noctis\niv-plus\modules\DL.EXE']:
        m = report(p)
        find_anchor(m, p)
        print()
