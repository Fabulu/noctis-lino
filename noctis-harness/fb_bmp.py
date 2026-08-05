#!/usr/bin/env python3
"""fb_bmp.py -- Wave 5, implementer 2.

Puts the two 1996-artifact capture routes on a common footing:

  route 1  the game's own snapshot(), NOCTIS-0.CPP:6292, key 'b'.
           An 8bpp bottom-up BMP.  Palette entries are written
               b = tmppal[c+2]*4  (blue), then green, then red, then 0
           so the DAC is recovered EXACTLY by  //4  -- no rounding.
           Pixels are `adapted` copied out row by row from ptr=63680
           downwards, i.e. the hidden page, bottom row first.

  route 2  DOSBox-X's raw screenshot.  A palette-indexed PNG that is exactly
           2x2 pixel-and-line doubled from the 320x200 mode-13h plane, so
           //2 on both axes recovers the index plane.  DOSBox writes the DAC
           as (v<<2)|(v>>4), so >>2 recovers the 6-bit value.

Both return (indices, pal6): a 320*200 list of 0..255 and a 768-entry list of
0..63 in R,G,B order -- the same shape as an FBDUMP kind 1 and kind 2 payload.

No third-party imaging library: PNG is decoded here with zlib only, so the
decode is auditable and cannot silently resample.

  python fb_bmp.py <file.bmp|file.png> [...]        # report
  python fb_bmp.py --scale-audit <file.bmp>         # decide x4 vs (v<<2)|(v>>4)
"""

import argparse
import os
import struct
import sys
import zlib

W, H = 320, 200


# --------------------------------------------------------------------- BMP


def read_bmp8(path):
    """Read the 8bpp BMP that snapshot() writes.  Returns (indices, pal6, info)."""
    with open(path, "rb") as fh:
        raw = fh.read()
    if raw[:2] != b"BM":
        raise ValueError("%s: not a BMP" % path)
    (_size, _r1, _r2, pixoff) = struct.unpack("<IHHI", raw[2:14])
    hdrsize = struct.unpack("<I", raw[14:18])[0]
    if hdrsize < 40:
        raise ValueError("%s: BITMAPCOREHEADER not supported" % path)
    width, height, planes, bpp = struct.unpack("<iiHH", raw[18:30])
    compression = struct.unpack("<I", raw[30:34])[0]
    if bpp != 8 or planes != 1:
        raise ValueError("%s: want 8bpp/1 plane, got %d bpp / %d planes" % (path, bpp, planes))
    if compression != 0:
        raise ValueError("%s: compressed BMP not supported" % path)

    # palette: BGR0 quads, immediately after the info header
    ptab = 14 + hdrsize
    quads = (pixoff - ptab) // 4
    ncol = min(256, quads)
    pal8 = [0] * 768                      # as stored, 0..255
    for i in range(ncol):
        b, g, r, _a = raw[ptab + 4 * i: ptab + 4 * i + 4]
        pal8[3 * i + 0] = r
        pal8[3 * i + 1] = g
        pal8[3 * i + 2] = b

    bottom_up = height > 0
    ah = abs(height)
    stride = ((width * 8 + 31) // 32) * 4
    rows = []
    for y in range(ah):
        off = pixoff + y * stride
        rows.append(list(raw[off: off + width]))
    if bottom_up:
        rows.reverse()

    idx = [v for row in rows for v in row]
    info = {
        "path": path, "width": width, "height": ah, "bottom_up": bottom_up,
        "bpp": bpp, "palette_entries": ncol, "route": "snapshot-bmp",
    }
    return idx, pal8, info


def bmp_pal6(pal8):
    """snapshot() stored tmppal*4.  Exact inverse is //4."""
    return [v // 4 for v in pal8]


# --------------------------------------------------------------------- PNG


def png_chunks(raw):
    if raw[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("not a PNG")
    p = 8
    while p + 8 <= len(raw):
        ln = struct.unpack(">I", raw[p:p + 4])[0]
        typ = raw[p + 4:p + 8]
        data = raw[p + 8:p + 8 + ln]
        yield typ, data
        p += 12 + ln


def _unfilter(data, width, height, bypp, stride):
    out = bytearray()
    prev = bytearray(stride)
    p = 0
    for _y in range(height):
        ft = data[p]
        p += 1
        line = bytearray(data[p:p + stride])
        p += stride
        if ft == 0:
            pass
        elif ft == 1:
            for i in range(bypp, stride):
                line[i] = (line[i] + line[i - bypp]) & 255
        elif ft == 2:
            for i in range(stride):
                line[i] = (line[i] + prev[i]) & 255
        elif ft == 3:
            for i in range(stride):
                a = line[i - bypp] if i >= bypp else 0
                line[i] = (line[i] + ((a + prev[i]) >> 1)) & 255
        elif ft == 4:
            for i in range(stride):
                a = line[i - bypp] if i >= bypp else 0
                b = prev[i]
                c = prev[i - bypp] if i >= bypp else 0
                pa, pb, pc = abs(b - c), abs(a - c), abs(a + b - 2 * c)
                pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                line[i] = (line[i] + pr) & 255
        else:
            raise ValueError("bad PNG filter type %d" % ft)
        out += line
        prev = line
    return out


def read_png(path):
    """Decode a PNG with zlib only.  Handles colour type 3 (palette, the raw
    DOSBox capture) and colour type 2 (truecolor, the scaled one)."""
    with open(path, "rb") as fh:
        raw = fh.read()
    ihdr = None
    plte = None
    idat = b""
    for typ, data in png_chunks(raw):
        if typ == b"IHDR":
            ihdr = struct.unpack(">IIBBBBB", data)
        elif typ == b"PLTE":
            plte = data
        elif typ == b"IDAT":
            idat += data
    if ihdr is None:
        raise ValueError("%s: no IHDR" % path)
    width, height, depth, ctype, comp, filt, interlace = ihdr
    if depth != 8 or comp != 0 or filt != 0 or interlace != 0:
        raise ValueError("%s: only 8-bit non-interlaced supported (got d=%d i=%d)" % (path, depth, interlace))
    bypp = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[ctype]
    stride = width * bypp
    data = _unfilter(zlib.decompress(idat), width, height, bypp, stride)
    return width, height, ctype, plte, data


def read_dosbox_raw(path):
    """DOSBox-X raw screenshot -> (indices 320*200, pal6 768, info).

    Verifies the 2x2 doubling rather than assuming it: every 2x2 block must be
    uniform, or the capture is not a raw mode-13h dump and must not be used as
    an oracle.
    """
    width, height, ctype, plte, data = read_png(path)
    if ctype != 3:
        raise ValueError("%s: colour type %d, not a palette-indexed raw capture" % (path, ctype))
    if plte is None:
        raise ValueError("%s: palette-indexed PNG with no PLTE" % path)
    sx, sy = width // W, height // H
    if sx * W != width or sy * H != height:
        raise ValueError("%s: %dx%d is not an integer multiple of 320x200" % (path, width, height))

    nonuniform = 0
    for y in range(H):
        base = y * sy * width
        for x in range(W):
            v = data[base + x * sx]
            for dy in range(sy):
                row = base + dy * width
                for dx in range(sx):
                    if data[row + x * sx + dx] != v:
                        nonuniform += 1
    idx = [data[(y * sy) * width + x * sx] for y in range(H) for x in range(W)]

    pal8 = list(plte) + [0] * (768 - len(plte))
    info = {
        "path": path, "width": width, "height": height, "scale": (sx, sy),
        "nonuniform_subpixels": nonuniform, "palette_entries": len(plte) // 3,
        "route": "dosbox-raw-png",
    }
    return idx, pal8[:768], info


def png_pal6(pal8):
    """DOSBox expands the 6-bit DAC as (v<<2)|(v>>4).  >>2 recovers v."""
    return [v >> 2 for v in pal8]


def load_any(path):
    """Dispatch on content, return (indices, pal6, info)."""
    with open(path, "rb") as fh:
        sig = fh.read(8)
    if sig[:2] == b"BM":
        idx, pal8, info = read_bmp8(path)
        return idx, bmp_pal6(pal8), pal8, info
    if sig == b"\x89PNG\r\n\x1a\n":
        idx, pal8, info = read_dosbox_raw(path)
        return idx, png_pal6(pal8), pal8, info
    raise ValueError("%s: unrecognised capture format" % path)


# ------------------------------------------------------------- scale audit


def scale_audit(pal8):
    """Decide, from the stored 8-bit palette alone, which 6->8 expansion the
    writer used.

    x4              : every byte is a multiple of 4, and <= 252.
    (v<<2)|(v>>4)   : bytes 0..3 mod 4 appear; byte 255 is reachable.
    Reporting both counts makes the claim falsifiable either way.
    """
    mod = [0, 0, 0, 0]
    for v in pal8:
        mod[v & 3] += 1
    x4_consistent = (mod[1] == mod[2] == mod[3] == 0) and max(pal8) <= 252
    # a value produced by (v<<2)|(v>>4) always satisfies  v>>2 == (v-(v>>6))>>2
    dosbox_consistent = all((((v >> 2) << 2) | ((v >> 2) >> 4)) == v for v in pal8)
    return {
        "mod4_histogram": mod,
        "max": max(pal8),
        "consistent_with_x4": x4_consistent,
        "consistent_with_shift_or": dosbox_consistent,
        "distinct": x4_consistent != dosbox_consistent,
    }


# -------------------------------------------------------------------- main


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--scale-audit", action="store_true")
    ap.add_argument("--emit-pal6", metavar="PATH", help="write the pal6 of the FIRST file as FBDUMP kind 2")
    ap.add_argument("--emit-index", metavar="PATH", help="write the index plane of the FIRST file as FBDUMP kind 1")
    args = ap.parse_args(argv)

    first = None
    for path in args.files:
        try:
            idx, pal6, pal8, info = load_any(path)
        except Exception as exc:
            print("%-46s ERROR %s" % (os.path.basename(path), exc))
            continue
        if first is None:
            first = (idx, pal6)
        used = sorted(set(idx))
        print("%s" % path)
        for k in sorted(info):
            print("    %-22s %s" % (k, info[k]))
        print("    %-22s %d px, %d distinct indices, min %d max %d"
              % ("indices", len(idx), len(used), min(idx), max(idx)))
        print("    %-22s nonzero entries %d, max6 %d"
              % ("pal6", sum(1 for v in pal6 if v), max(pal6)))
        if args.scale_audit:
            a = scale_audit(pal8)
            for k in ("mod4_histogram", "max", "consistent_with_x4", "consistent_with_shift_or", "distinct"):
                print("    scale.%-16s %s" % (k, a[k]))
        print()

    if first and (args.emit_pal6 or args.emit_index):
        from fb_layout import fbdump_write, KIND_PALETTE6, KIND_INDEXPAGE
        if args.emit_pal6:
            fbdump_write(args.emit_pal6, KIND_PALETTE6, first[1])
            print("wrote %s" % args.emit_pal6)
        if args.emit_index:
            fbdump_write(args.emit_index, KIND_INDEXPAGE, first[0], width=W, height=H)
            print("wrote %s" % args.emit_index)
    return 0


if __name__ == "__main__":
    sys.exit(main())
