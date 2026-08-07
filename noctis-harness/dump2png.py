#!/usr/bin/env python3
"""dump2png.py -- the dump-to-image converter for the Noctis port.

The three Wave 5/6b/7a dump formats (SUDUMP, SPDUMP, FBDUMP v2) all carry a
320x200 or 360x180 INDEX page and a palette, but none of them IS an image.
This reads any of them and writes a viewable PNG/BMP.  It is the missing piece
that fb_bmp.py (which only READS bmps) is the inverse of.

DUMP FORMATS
------------
All three are a stream of fixed 16-unit (64-byte) records, header + payload,
serialised as little-endian 32-bit units.  They differ in magic, header layout
and -- crucially -- in how a payload unit maps to data bytes:

  SUDUMP (su-out.bin, sumain)   magic 826622293 ('SUD1')
     header: u0 magic u1 ver u2 kind u3 w u4 h u5 count u6 case u7 tag u8.. zero
     payload: lino-packed -- 4 data bytes per unit, little-endian.  Because the
              unit is then written LE to disk, the on-disk bytes ARE the data
              bytes in order.  Kinds: 1 KMAP (360x180 albedo, 16200u/64800B),
              3 KPAL (64 colours x 3 = 192B at tmppal[3*colorbase]), 2 KOVL etc.
              The surface byte v indexes the 64-colour gradient at KPAL[v].

  SPDUMP (sp-out.bin, spmain)   magic 826622291 ('SPD1')
     header: u0 magic u1 ver u2 kind u3 w u4 h u5 count u6 case u7 0 u8 tag ...
     payload: lino-packed (same as SUDUMP).  Kind 48 SPPAGE = a packed 320x200
              index page; NO palette is carried, so one must be supplied
              (--pal) for the globe page (use the FBDUMP/surface palette).

  FBDUMP v2 (fb-out.bin, fbmain)  magic 0x46424431 ('FBD1')
     header: u0 magic u1 ver(=2) u2 kind u3 w u4 h u5 count u6 cpms u7 ticks
             u8 tag u9.. zero
     payload: one value per unit (fb_layout.fbdump_write packs each as <I), so
              data byte k lives at file offset payload_start + 4k (low byte).
              Kinds: 1 INDEXPAGE (320x200 indices), 2 PALETTE6 (768 6-bit RGB).

PALETTE EXPANSION
-----------------
The DAC components are 6-bit (0..63).  Two historic expansions exist and
fb_bmp.py:226 documents both:
  x4              snapshot() BMP writer:  v * 4          (63 -> 252)
  (v<<2)|(v>>4)   DOSBox-X screenshot:                    (63 -> 255)
The port's own fbpal LUT uses v*4; DOSBox uses the shift-or.  The shift-or is
the visually smoother one and is the default here; --scale x4 selects the
port-LUT-faithful one.

USAGE
-----
  python dump2png.py <dump.bin> [--out OUT.png] [--case N] [--kind K] \
      [--scale shift-or|x4] [--pal FBDUMP_or_rawpal.bin] [--format png|bmp] \
      [--list]
  python dump2png.py su-out.bin --case 3 --out felisian.png
  python dump2png.py fb-out.bin --out frame.png
  python dump2png.py sp-out.bin --pal su-out.bin --out globe.png   (needs pal)

No PIL hard-dependency: PNG is written via zlib if PIL is absent, and BMP is a
raw 8-bit writer.  PIL is used for PNG when available.
"""

import argparse
import os
import struct
import sys
import zlib

SU_MAGIC = 826622293      # 'SUD1' LE
SP_MAGIC = 826622291      # 'SPD1' LE
FB_MAGIC = 0x46424431     # 'FBD1' LE
HDR_U = 16                 # header is always 16 units
HDR_B = HDR_U * 4          # 64 bytes

SU_NAME = {1: "KMAP", 2: "KOVL", 3: "KPAL", 4: "KSCAL", 5: "KLED",
           6: "KTAIL", 7: "KTRL"}
SP_NAME = {48: "SPPAGE", 49: "SPCEN", 50: "SPMAP", 57: "SPSCALE", 59: "SPTRL"}
FB_NAME = {1: "INDEXPAGE", 2: "PALETTE6", 3: "LUT", 4: "TICKLOG", 5: "LAYOUT",
           6: "CANARY", 7: "KSELF"}


def detect(path):
    with open(path, "rb") as fh:
        raw = fh.read(HDR_B)
    if len(raw) < 8:
        raise ValueError("%s: too short" % path)
    m = struct.unpack("<I", raw[:4])[0]
    if m == SU_MAGIC:
        return "SUDUMP"
    if m == SP_MAGIC:
        return "SPDUMP"
    if m == FB_MAGIC:
        return "FBDUMP"
    raise ValueError("%s: unknown magic %08X (not a SUDUMP/SPDUMP/FBDUMP)"
                     % (path, m))


def parse_records(path):
    """Yield dicts: kind,w,h,count,case,tag, payload (bytes), offset, raw_type."""
    with open(path, "rb") as fh:
        data = fh.read()
    rtype = None
    off = 0
    while off + HDR_B <= len(data):
        hdr = struct.unpack("<16I", data[off:off + HDR_B])
        magic = hdr[0]
        if rtype is None:
            if magic == SU_MAGIC:
                rtype = "SUDUMP"
            elif magic == SP_MAGIC:
                rtype = "SPDUMP"
            elif magic == FB_MAGIC:
                rtype = "FBDUMP"
            else:
                break
        elif magic != {"SUDUMP": SU_MAGIC, "SPDUMP": SP_MAGIC,
                       "FBDUMP": FB_MAGIC}[rtype]:
            break   # ran off the end into garbage
        kind = hdr[2]
        count = hdr[5]
        if rtype == "SUDUMP":
            case, tag = hdr[6], hdr[7]
        elif rtype == "SPDUMP":
            case, tag = hdr[6], hdr[8]
        else:   # FBDUMP v2
            case, tag = 0, hdr[8]
        w, h = hdr[3], hdr[4]
        payload = data[off + HDR_B: off + HDR_B + count * 4]
        yield {"type": rtype, "kind": kind, "w": w, "h": h, "count": count,
               "case": case, "tag": tag, "payload": payload,
               "offset": off, "ver": hdr[1]}
        off += HDR_B + count * 4


# ------------------------------------------------------------- payload decoding


def payload_bytes_lino(rec):
    """SUDUMP/SPDUMP payload: lino-packed, 4 data bytes per LE unit.  On disk
    these ARE the data bytes in order, so the payload bytes map 1:1."""
    return rec["payload"]


def payload_values_per_unit(rec):
    """FBDUMP payload: one value per 32-bit unit.  Yield the low byte of each."""
    n = rec["count"]
    return list(struct.unpack("<%dI" % n, rec["payload"][:n * 4]))


# ------------------------------------------------------------------- palettes


def expand6(v, scale):
    if scale == "x4":
        return (v & 63) * 4
    return ((v & 63) << 2) | ((v & 63) >> 4)


def palette_rgb(pal6_bytes, scale):
    """768 6-bit RGB components (R,G,B order) -> list of (r,g,b) 0..255."""
    out = []
    for i in range(256):
        if 3 * i + 2 < len(pal6_bytes):
            r = expand6(pal6_bytes[3 * i + 0], scale)
            g = expand6(pal6_bytes[3 * i + 1], scale)
            b = expand6(pal6_bytes[3 * i + 2], scale)
        else:
            r = g = b = 0
        out.append((r, g, b))
    return out


def palette_from_kpal(kpal_bytes, colorbase, scale):
    """SUDUMP KPAL: 64 colours at tmppal[3*colorbase], i.e. absolute indices
    colorbase..colorbase+63.  Surface byte v (0..62) maps to colour
    colorbase+v, i.e. KPAL row v."""
    pal = [(0, 0, 0)] * 256
    for i in range(min(64, len(kpal_bytes) // 3)):
        r = expand6(kpal_bytes[3 * i + 0], scale)
        g = expand6(kpal_bytes[3 * i + 1], scale)
        b = expand6(kpal_bytes[3 * i + 2], scale)
        pal[colorbase + i] = (r, g, b)
    return pal


# --------------------------------------------------------------- image writers


def write_bmp8(path, indices, w, h, pal256):
    """8-bit bottom-up BMP, 320/360-wide.  indices row-major top-down."""
    stride = ((w + 3) // 4) * 4     # BMP rows are DWORD-padded
    pix = bytearray(stride * h)
    for y in range(h):
        row = indices[y * w:(y + 1) * w]
        base = (h - 1 - y) * stride        # bottom-up
        for x in range(w):
            pix[base + x] = indices[y * w + x] & 0xFF
    pal_bytes = bytearray()
    for (r, g, b) in pal256:
        pal_bytes += bytes((b, g, r, 0))
    pixoff = 14 + 40 + 1024
    out = b"BM" + struct.pack("<IHHIiiHHIIiiII",
        pixoff + len(pix), 0, 0, pixoff,
        w, h, 1, 8, 0, stride * h, 0, 0, 256, 0) + bytes(pal_bytes) + bytes(pix)
    with open(path, "wb") as fh:
        fh.write(out)


def _png_image_bytes(indices, w, h, pal256):
    """Build a colour-type-3 (indexed) PNG image IDAT, one byte per pixel,
    filtered with filter type 0 per scanline."""
    raw = bytearray()
    for y in range(h):
        raw.append(0)   # filter: none
        raw += bytes(i & 0xFF for i in indices[y * w:(y + 1) * w])
    return zlib.compress(bytes(raw), 9)


def _png_chunk(typ, data):
    return (struct.pack(">I", len(data)) + typ + data +
            struct.pack(">I", zlib.crc32(typ + data) & 0xFFFFFFFF))


def write_png8(path, indices, w, h, pal256):
    """8-bit indexed PNG via zlib only (no PIL)."""
    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 3, 0, 0, 0)
    plte = b"".join(bytes((r & 0xFF, g & 0xFF, b & 0xFF)) for (r, g, b) in pal256)
    idat = _png_image_bytes(indices, w, h, pal256)
    with open(path, "wb") as fh:
        fh.write(sig)
        fh.write(_png_chunk(b"IHDR", ihdr))
        fh.write(_png_chunk(b"PLTE", plte))
        fh.write(_png_chunk(b"IDAT", idat))
        fh.write(_png_chunk(b"IEND", b""))


def write_image(path, indices, w, h, pal256, rgb=False):
    """Write an image.  If rgb=True, indices are taken to be direct RGB triples
    (3 bytes per pixel) and pal256 is ignored; the output is a 24-bit image via
    PIL or a 24-bit PNG via zlib."""
    ext = os.path.splitext(path)[1].lower()
    if rgb:
        write_image_rgb(path, indices, w, h)
        return
    if ext == ".bmp":
        write_bmp8(path, indices, w, h, pal256)
    else:
        try:
            from PIL import Image   # type: ignore
            img = Image.new("P", (w, h))
            flat = bytes(i & 0xFF for i in indices)
            img.frombytes(flat)
            img.putpalette([c for rgb in pal256 for c in rgb][:768])
            img.save(path)
        except ImportError:
            write_png8(path, indices, w, h, pal256)


def write_image_rgb(path, rgb_bytes, w, h):
    """24-bit RGB image (for the sphere projection, which produces true RGB
    because the sphere's background is not a palette index)."""
    try:
        from PIL import Image   # type: ignore
        img = Image.frombytes("RGB", (w, h), bytes(rgb_bytes))
        img.save(path)
        return
    except ImportError:
        pass
    # raw 24-bit BMP fallback (bottom-up, no palette)
    stride = ((w * 3 + 3) // 4) * 4
    pix = bytearray(stride * h)
    for y in range(h):
        base = (h - 1 - y) * stride
        pix[base:base + w * 3] = rgb_bytes[y * w * 3:(y + 1) * w * 3]
    pixoff = 14 + 40
    out = b"BM" + struct.pack("<IHHIiiHHIIiiII",
        pixoff + len(pix), 0, 0, pixoff, w, h, 1, 24, 0,
        stride * h, 0, 0, 0, 0) + bytes(pix)
    with open(path, "wb") as fh:
        fh.write(out)


# ---------------------------------------------------- sphere projection (viewer)


def project_sphere(indices, w, h, pal256, outw, outh, lon0=0.0, lat0=0.0,
                   radius=None, bg=(0, 0, 0)):
    """Orthographic projection of an equirectangular texture onto a disc.

    This is a VIEWER, not the port's globe() rasterizer: it samples the
    generated p_background through a straightforward camera projection so the
    texture reads as a planet.  globe()'s integer-pinned sphere mapping is its
    own (Wave 6b) proof; this only visualises the generation pipeline's output.

    indices: row-major equirectangular byte values (0..255), w x h.
    pal256:  256-entry (r,g,b) LUT the indices address.
    lon0/lat0: the longitude/latitude at the disc centre, in turns.
    bg: RGB for pixels outside the disc.
    """
    import math
    if radius is None:
        radius = min(outw, outh) / 2.0 - 1.0
    cx = outw / 2.0
    cy = outh / 2.0
    # precompute the palette as a flat bytearray for speed
    lut = bytearray(768)
    for i, (r, g, b) in enumerate(pal256):
        lut[3 * i] = r
        lut[3 * i + 1] = g
        lut[3 * i + 2] = b
    out = bytearray(outw * outh * 3)
    r2 = radius * radius
    cos_lat0 = math.cos(lat0 * 2 * math.pi)
    sin_lat0 = math.sin(lat0 * 2 * math.pi)
    for py in range(outh):
        dy = py - cy
        for px in range(outw):
            dx = px - cx
            d2 = dx * dx + dy * dy
            base = (py * outw + px) * 3
            if d2 > r2:
                out[base] = bg[0]
                out[base + 1] = bg[1]
                out[base + 2] = bg[2]
                continue
            # orthographic: the sphere's surface point at screen (dx,dy)
            dz = math.sqrt(r2 - d2) / radius       # forward component
            sx = dx / radius
            sy = dy / radius
            # rotate by lat0 around the X axis, then lon0 around Y
            y1 = cos_lat0 * sy - sin_lat0 * dz
            z1 = sin_lat0 * sy + cos_lat0 * dz
            x1 = sx
            lon = math.atan2(x1, z1) / (2 * math.pi) + lon0
            lat = math.asin(max(-1.0, min(1.0, y1)))
            # sample equirectangular
            tx = int((lon % 1.0) * w) % w
            ty = int((lat + 0.5) * h)
            if ty < 0:
                ty = 0
            elif ty >= h:
                ty = h - 1
            v = indices[ty * w + tx] & 0xFF
            o = 3 * v
            out[base] = lut[o]
            out[base + 1] = lut[o + 1]
            out[base + 2] = lut[o + 2]
    return out, outw, outh


# --------------------------------------------------------------- the rendering


def render_su(recs, case, scale, fmt, outbase, project="flat", sw=320, sh=200):
    """Render SUDUMP cases.  Each case has a KMAP (360x180) and a KPAL
    (64 colours at colorbase).  Renders every case with emit, or --case N.

    project='flat'  : the equirectangular map, w x h (Path B default).
    project='sphere': an orthographic disc of the SAME texture, so the surface
                      reads as a planet.  This is a python VIEWER of the
                      generated p_background -- NOT the port's globe() -- meant
                      only to make the generation pipeline's output legible as
                      'a planet'.  globe()'s integer-pinned mapping is Wave 6b."""
    by_case = {}
    for r in recs:
        by_case.setdefault(r["case"], []).append(r)
    targets = [c for c in sorted(by_case) if c >= 0]
    if case is not None:
        targets = [c for c in targets if c == case]
    rendered = []
    for c in targets:
        recs_c = {r["kind"]: r for r in by_case[c]}
        if 1 not in recs_c:       # no KMAP
            continue
        mapb = payload_bytes_lino(recs_c[1])
        w, h = recs_c[1]["w"], recs_c[1]["h"]
        cb = 192
        pal = [(0, 0, 0)] * 256
        if 3 in recs_c:
            cb = recs_c[3]["tag"] // 3 if recs_c[3]["tag"] else 192
            pal = palette_from_kpal(payload_bytes_lino(recs_c[3]), cb, scale)
        # surface byte v -> absolute index colorbase+v
        indices = [(cb + (b & 0x3F)) & 0xFF for b in mapb[:w * h]]
        tag_case = "c%d" % c
        if project == "sphere":
            rgb, ow, oh = project_sphere(indices, w, h, pal, sw, sh,
                                         lon0=0.0, lat0=-0.08)
            out = "%s-%s-globe.%s" % (outbase, tag_case, fmt)
            write_image(out, rgb, ow, oh, None, rgb=True)
            rendered.append((out, ow, oh, indices, cb))
        else:
            out = "%s-%s.%s" % (outbase, tag_case, fmt)
            write_image(out, indices, w, h, pal)
            rendered.append((out, w, h, indices, cb))
    return rendered


def render_fb(recs, scale, fmt, outbase):
    """FBDUMP: INDEXPAGE (320x200) + PALETTE6 (768 components)."""
    page = pal = None
    for r in recs:
        if r["kind"] == 1:
            page = r
        elif r["kind"] == 2:
            pal = r
    if page is None:
        return []
    idx = payload_values_per_unit(page)
    w, h = page["w"], page["h"]
    if w == 0 or h == 0:
        w, h = 320, 200
    pal6 = payload_values_per_unit(pal) if pal else [0] * 768
    pal256 = palette_rgb(pal6, scale)
    out = "%s.%s" % (outbase, fmt)
    write_image(out, idx[:w * h], w, h, pal256)
    return [(out, w, h, idx[:w * h], None)]


def render_sp(recs, scale, fmt, outbase, pal_path):
    """SPDUMP: SPPAGE kind 48 (320x200 lino-packed).  No palette in the dump;
    one must be supplied (an FBDUMP or a SUDUMP for the palette, or raw 768)."""
    pages = [r for r in recs if r["kind"] == 48]
    if not pages:
        return []
    pal256 = [(0, 0, 0)] * 256
    if pal_path:
        pal256 = load_palette(pal_path, scale)
    page = pages[-1]
    idx = list(payload_bytes_lino(page))[:320 * 200]
    out = "%s.%s" % (outbase, fmt)
    write_image(out, idx, 320, 200, pal256)
    return [(out, 320, 200, idx, None)]


def load_palette(path, scale):
    """Load a palette from an FBDUMP PALETTE6 record, a SUDUMP KPAL, or a raw
    768-byte file.  Returns a 256-entry (r,g,b) list."""
    with open(path, "rb") as fh:
        raw = fh.read()
    if len(raw) >= 8:
        m = struct.unpack("<I", raw[:4])[0]
        if m == FB_MAGIC:
            for r in parse_records(path):
                if r["kind"] == 2:
                    return palette_rgb(payload_values_per_unit(r), scale)
        if m == SU_MAGIC:
            # use the LAST KPAL; caller picks colorbase by case elsewhere
            for r in parse_records(path):
                if r["kind"] == 3:
                    cb = r["tag"] // 3 if r["tag"] else 192
                    return palette_from_kpal(payload_bytes_lino(r), cb, scale)
    if len(raw) >= 768:
        return palette_rgb(list(raw[:768]), scale)
    raise ValueError("%s: not an FBDUMP/SUDUMP and shorter than 768 bytes"
                     % path)


# ---------------------------------------------------------------- verification


def describe(out, w, h, indices, cb):
    used = {}
    for v in indices:
        used[v] = used.get(v, 0) + 1
    nu = len(used)
    if not indices:
        return "BLANK (no pixels)"
    imin = min(indices)
    imax = max(indices)
    nz = sum(1 for v in indices if v != 0)
    # crude 2D structure check: how many distinct values appear in the top vs
    # bottom half, and the variance of per-row distinct counts
    half = h // 2
    top = set(indices[:w * half])
    bot = set(indices[w * half:])
    per_row = [len(set(indices[r * w:(r + 1) * w])) for r in range(h)]
    rows_var = (max(per_row) - min(per_row)) if per_row else 0
    return ("w=%d h=%d px=%d distinct=%d idx[%d..%d] nonzero=%d (%.1f%%) "
            "top/bottom distinct=%d/%d row-distinct span=%d..%d colorbase=%s"
            % (w, h, len(indices), nu, imin, imax, nz,
               100.0 * nz / max(1, len(indices)),
               len(top), len(bot), min(per_row), max(per_row), cb))


# ----------------------------------------------------------------------- main


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dump")
    ap.add_argument("--out", help="output base (extension sets format)")
    ap.add_argument("--case", type=int, help="SUDUMP case index to render")
    ap.add_argument("--kind", type=int, help="render only this record kind")
    ap.add_argument("--scale", choices=("shift-or", "x4"), default="shift-or",
                    help="6->8 bit palette expansion (default shift-or)")
    ap.add_argument("--pal", help="palette source for SPDUMP, or override")
    ap.add_argument("--format", choices=("png", "bmp"), default="png")
    ap.add_argument("--list", action="store_true",
                    help="list records and exit")
    ap.add_argument("--outdir", default=".",
                    help="output directory (default cwd)")
    ap.add_argument("--project", choices=("flat", "sphere"), default="flat",
                    help="SUDUMP: flat equirectangular map (Path B, default) "
                         "or an orthographic globe disc (python VIEWER of the "
                         "generated texture, NOT the port's globe())")
    ap.add_argument("--sw", type=int, default=320, help="sphere output width")
    ap.add_argument("--sh", type=int, default=200, help="sphere output height")
    a = ap.parse_args(argv)

    rtype = detect(a.dump)
    recs = list(parse_records(a.dump))

    if a.list:
        name = {"SUDUMP": SU_NAME, "SPDUMP": SP_NAME, "FBDUMP": FB_NAME}[rtype]
        print("%s: %d records, type %s" % (a.dump, len(recs), rtype))
        for r in recs:
            kn = name.get(r["kind"], "?")
            extra = ""
            if rtype == "SUDUMP":
                extra = "case=%d tag=%d" % (r["case"], r["tag"])
            elif rtype == "SPDUMP":
                extra = "case=%d tag=%d" % (r["case"], r["tag"])
            elif rtype == "FBDUMP":
                extra = "tag=%d" % r["tag"]
            print("  off=%8d kind=%2d %-10s w=%-4d h=%-4d count=%-7d %s"
                  % (r["offset"], r["kind"], kn, r["w"], r["h"], r["count"],
                     extra))
        return 0

    outbase = os.path.join(a.outdir, a.out or "render")
    rendered = []
    if rtype == "SUDUMP":
        rendered = render_su(recs, a.case, a.scale, a.format, outbase,
                             a.project, a.sw, a.sh)
    elif rtype == "FBDUMP":
        rendered = render_fb(recs, a.scale, a.format, outbase)
    elif rtype == "SPDUMP":
        rendered = render_sp(recs, a.scale, a.format, outbase, a.pal)

    if not rendered:
        print("nothing rendered (no matching records)", file=sys.stderr)
        return 1

    for (out, w, h, indices, cb) in rendered:
        print("wrote %s -- %s" % (out, describe(out, w, h, indices, cb)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
