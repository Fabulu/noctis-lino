"""Wave 2 / Recon A -- COMPLETE call-site scanner.

Borland large model emits three call forms for a FAR function:
  (1) 9A off16 seg16          -- true far call, seg16 carries a reloc fixup
  (2) 0E E8 rel16             -- push cs ; call near   (same-segment far callee)
  (3) FF 1E / FF 5E ...       -- indirect far call through a pointer
This scans for all three.
"""
import struct, collections, bisect
from w2_disasm import load, segments, disasm, fmt, NOCTIS, DL

def build(path, dgroup):
    d, hdr, fix = load(path)
    segs = segments(fix, hdr, len(d), dgroup)
    return d, hdr, fix, segs

def seg_at(segs, fo):
    for v, a, b, n in segs:
        if a <= fo < b:
            return v, a, b
    return None, None, None

def all_calls(d, hdr, fix, segs, dgroup):
    """Return list of (site_file_off, target_file_off, kind)."""
    code_end = hdr + dgroup * 16
    out = []
    for v, a, b, n in segs:
        i = a
        while i < b - 4:
            if d[i] == 0x9A:
                off, seg = struct.unpack_from('<HH', d, i + 1)
                if i + 3 in fix:
                    out.append((i, hdr + fix[i+3]*16 + off, 'far'))
                i += 5
                continue
            if d[i] == 0x0E and d[i+1] == 0xE8:
                rel, = struct.unpack_from('<h', d, i + 2)
                tgt = (i + 4 - a + rel) & 0xFFFF
                out.append((i, a + tgt, 'pushcs'))
                i += 4
                continue
            if d[i] == 0xE8:
                rel, = struct.unpack_from('<h', d, i + 1)
                tgt = (i + 3 - a + rel) & 0xFFFF
                out.append((i, a + tgt, 'near'))
                i += 3
                continue
            i += 1
    return out

def scan(path, dgroup, label):
    d, hdr, fix, segs = build(path, dgroup)
    calls = all_calls(d, hdr, fix, segs, dgroup)
    return d, hdr, fix, segs, calls
