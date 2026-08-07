"""flat2png.py -- render 7a's generated surface texture (p_background) from
work/su-out.bin as a viewable BMP. The "vertical slice" screenshot, fast path.

Usage: python flat2png.py [su-out.bin] [out.bmp] [case_index]
"""
import struct
import sys
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
KMAP, KOVL, KPAL = 1, 2, 3


def read_records(path):
    raw = open(path, "rb").read()
    u = struct.unpack("<%dI" % (len(raw) // 4), raw)
    magic = u[0]  # auto-detect (7a and 7b dumpers use slightly different magics)
    recs, i = [], 0
    while i < len(u):
        if u[i] != magic:
            raise SystemExit("bad magic at unit %d (expected %d, got %d)" % (i, magic, u[i]))
        hdr = u[i:i + 16]
        bc = hdr[5]
        recs.append(dict(kind=hdr[2], case=hdr[6], body=u[i + 16:i + 16 + bc]))
        i += 16 + bc
    return recs


def unpack_bytes(units, n):
    out = bytearray()
    for v in units:
        out += bytes((v & 255, (v >> 8) & 255, (v >> 16) & 255, (v >> 24) & 255))
    return bytes(out[:n])


def write_bmp8(path, w, h, indices, pal_band, band_base):
    """Write an 8-bit BMP. pal_band covers palette indices [band_base, band_base+n).
    6-bit components expanded to 8-bit via v<<2 | v>>4."""
    ncol = len(pal_band) // 3
    palentries = bytearray()
    for i in range(256):
        if band_base <= i < band_base + ncol:
            j = i - band_base
            r = (pal_band[j * 3] << 2) | (pal_band[j * 3] >> 4)
            g = (pal_band[j * 3 + 1] << 2) | (pal_band[j * 3 + 1] >> 4)
            b = (pal_band[j * 3 + 2] << 2) | (pal_band[j * 3 + 2] >> 4)
        else:
            r = g = b = 0
        palentries += bytes((b, g, r, 0))
    rowsize = (w + 3) & ~3
    pad = rowsize - w
    pix = bytearray()
    for y in range(h - 1, -1, -1):
        pix += indices[y * w:(y + 1) * w] + bytes(pad)
    filesize = 54 + 1024 + len(pix)
    bmp = bytearray()
    bmp += b"BM" + struct.pack("<IHHI", filesize, 0, 0, 54 + 1024)
    bmp += struct.pack("<IiiHHIIiiII", 40, w, h, 1, 8, 0, len(pix), 0, 0, 256, 0)
    bmp += palentries + pix
    open(path, "wb").write(bmp)


def main():
    su = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "work", "su-out.bin")
    out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(ROOT, "work", "surface-shot.bmp")
    ci = int(sys.argv[3]) if len(sys.argv) > 3 else 0
    recs = read_records(su)
    maps = [r for r in recs if r["kind"] == KMAP]
    pals = [r for r in recs if r["kind"] == KPAL]
    if not maps:
        raise SystemExit("no KMAP in %s" % su)
    if ci >= len(maps):
        ci = 0
    mapbytes = unpack_bytes(maps[ci]["body"], 64800)
    # The palette band: 7a dumps the surface palette (64 triples = 192 bytes for
    # planet band 192..255; or 768 if full). Detect by size.
    pal_raw = unpack_bytes(pals[ci]["body"], 4096) if (pals and len(pals) > ci) else b""
    if len(pal_raw) >= 768:
        band, base = pal_raw[:768], 0
    elif len(pal_raw) >= 192:
        band, base = pal_raw[:192], 0  # surface albedo 0..62 -> first 64 palette triples
    else:
        band, base = pal_raw, 0
    idx_min, idx_max = min(mapbytes), max(mapbytes)
    distinct = len(set(mapbytes))
    print("case %d: KMAP %d bytes, KPAL %d bytes (using %d as band base %d)"
          % (maps[ci]["case"], len(mapbytes), len(pal_raw), len(band), base))
    print("  indices: min=%d max=%d distinct=%d/256" % (idx_min, idx_max, distinct))
    write_bmp8(out, 360, 180, mapbytes, band, base)
    print("wrote", out)


if __name__ == "__main__":
    main()
