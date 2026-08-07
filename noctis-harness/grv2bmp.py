"""grv2bmp.py -- render fragpage's grv-page.bin (raw 64000 int32 adapted page) as a BMP."""
import struct, sys, os
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
src = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "work", "grv-page.bin")
out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(ROOT, "work", "ground-view.bmp")
raw = open(src, "rb").read()
n = len(raw) // 4
vals = struct.unpack("<%dI" % n, raw)
indices = bytes(v & 255 for v in vals[:64000])
w, h = 320, 200
# grayscale palette: index i -> gray (i, i, i)
pal = bytearray()
for i in range(256):
    pal += bytes((i, i, i, 0))  # BGR + reserved (BMP palette is BGR)
rowsize = (w + 3) & ~3
pix = bytearray()
for y in range(h - 1, -1, -1):
    pix += indices[y * w:(y + 1) * w] + bytes(rowsize - w)
filesize = 54 + 1024 + len(pix)
bmp = b"BM" + struct.pack("<IHHI", filesize, 0, 0, 54 + 1024)
bmp += struct.pack("<IiiHHIIiiII", 40, w, h, 1, 8, 0, len(pix), 0, 0, 256, 0)
bmp += pal + pix
open(out, "wb").write(bmp)
distinct = len(set(indices))
nz = sum(1 for v in indices if v)
print("wrote %s (%dx%d, %d distinct indices, %d/%d nonzero)" % (out, w, h, distinct, nz, len(indices)))
