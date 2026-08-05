"""Wave 2 / Recon A -- capstone 16-bit decoder + rand() call-site scanner.

Segment layout is derived from the relocation table's *stored values* (the
paragraph numbers Borland's linker wrote into far pointers), cross-checked
against the C0 startup's `mov dx,DGROUP`.
"""
import struct, sys, collections
from capstone import *

NOCTIS = r'C:\programmieren\noctis\niv-plus\modules\NOCTIS.EXE'
DL     = r'C:\programmieren\noctis\niv-plus\modules\DL.EXE'

def load(path):
    d = open(path, 'rb').read()
    hdrparas, = struct.unpack_from('<H', d, 8)
    nreloc,   = struct.unpack_from('<H', d, 6)
    lfarlc,   = struct.unpack_from('<H', d, 0x18)
    hdr = hdrparas * 16
    # MZ reloc entry is (offset, segment) in that order
    relocs = [struct.unpack_from('<HH', d, lfarlc + 4*i) for i in range(nreloc)]
    # file offset of each fixup word
    fixups = {}
    for o, s in relocs:
        fo = hdr + s*16 + o
        v, = struct.unpack_from('<H', d, fo)
        fixups[fo] = v
    return d, hdr, fixups

def segments(fixups, hdr, filesize, dgroup):
    vals = sorted(set(fixups.values()))
    code = [v for v in vals if v < dgroup]
    segs = []
    for i, v in enumerate(code):
        end = code[i+1] if i+1 < len(code) else dgroup
        segs.append((v, hdr + v*16, hdr + end*16, (end-v)*16))
    return segs

md = Cs(CS_ARCH_X86, CS_MODE_16)
md.detail = True

def disasm(d, file_off, seg_base_file, seg_para, count=40, stop=None):
    """Disassemble from file_off; addresses reported as segment-relative."""
    addr = file_off - seg_base_file
    out = []
    for ins in md.disasm(d[file_off:file_off+count*8], addr):
        out.append((seg_base_file + ins.address, seg_para, ins))
        if len(out) >= count:
            break
        if stop and stop(ins):
            break
    return out

def fmt(rows, note=None):
    lines = []
    for fo, sp, ins in rows:
        lines.append('  %-7d %04X:%04X  %-24s %s %s'
                     % (fo, sp, ins.address, ins.bytes.hex(' '), ins.mnemonic,
                        ins.op_str))
    return '\n'.join(lines)
