#!/usr/bin/env python3
"""fpdiff.py - compare fpout.bin (L.in.oleum) against fprefout.bin (C/x87).

    python fpdiff.py [lino.bin] [ref.bin] [label]

Every sentinel and every header field is checked before a single value is
compared, because each of them is a way for the comparison to be vacuous:
a short read silently corrects [Block Size] in L.in.oleum, so a truncated
file looks like a complete one unless the per-case sentinel is inspected.
"""
import struct
import sys

MAGIC_OUT = 0x46504F54
OUTU = 8
FIELDS = ['f64 result', 'int chop', 'int near', 'int16 chop', 'compare',
          'flags']


def load(path):
    d = open(path, 'rb').read()
    u = struct.unpack('<%dI' % (len(d) // 4), d)
    if u[0] != MAGIC_OUT:
        raise SystemExit('%s: magic is %08X, not FPOT' % (path, u[0]))
    if u[1] != 1:
        raise SystemExit('%s: version %d' % (path, u[1]))
    ncase, caseu = u[2], u[3]
    if caseu != OUTU:
        raise SystemExit('%s: caseu %d' % (path, caseu))
    if u[7] != 0x0DEFACED:
        raise SystemExit('%s: tail sentinel %08X' % (path, u[7]))
    if len(u) != 8 + ncase * OUTU:
        raise SystemExit('%s: %d units, header says %d'
                         % (path, len(u), 8 + ncase * OUTU))
    for i in range(ncase):
        if u[8 + i * OUTU + 7] != 0x5A5A5A5A:
            raise SystemExit('%s: case %d sentinel %08X - the file is short '
                             'or misaligned' % (path, i, u[8 + i * OUTU + 7]))
    return u, ncase


def main():
    lp = sys.argv[1] if len(sys.argv) > 1 else 'fpout.bin'
    rp = sys.argv[2] if len(sys.argv) > 2 else 'fprefout.bin'
    label = sys.argv[3] if len(sys.argv) > 3 else ''

    a, na = load(lp)
    b, nb = load(rp)
    if na != nb:
        raise SystemExit('case counts differ: %d vs %d' % (na, nb))

    bad_header = []
    if a[5] != b[5]:
        bad_header.append('control word lino %04X ref %04X' % (a[5], b[5]))
    atop, btop = (a[6] >> 11) & 7, (b[6] >> 11) & 7
    if atop != btop:
        bad_header.append('x87 TOP lino %d ref %d' % (atop, btop))

    bad = [0] * 6
    first = [None] * 6
    for i in range(na):
        oa = 8 + i * OUTU
        ob = 8 + i * OUTU
        va = (a[oa + 1] << 32) | a[oa]
        vb = (b[ob + 1] << 32) | b[ob]
        if va != vb:
            bad[0] += 1
            if first[0] is None:
                first[0] = (i, '%016X' % va, '%016X' % vb)
        for k in range(1, 6):
            if a[oa + 1 + k] != b[ob + 1 + k]:
                bad[k] += 1
                if first[k] is None:
                    first[k] = (i, a[oa + 1 + k], b[ob + 1 + k])

    tot = sum(bad) + len(bad_header)
    tag = ('%-14s ' % label) if label else ''
    print('%scases %d  lino cw %04X TOP %d | ref cw %04X TOP %d'
          % (tag, na, a[5], atop, b[5], btop))
    for error in bad_header:
        print('  DIFF %-12s %s' % ('header', error))
    for k in range(6):
        mark = 'OK  ' if bad[k] == 0 else 'DIFF'
        line = '  %s %-12s %5d/%d' % (mark, FIELDS[k], na - bad[k], na)
        if first[k] is not None:
            line += '   first case %d: lino %s ref %s' % first[k]
        print(line)
    return 1 if tot else 0


if __name__ == '__main__':
    sys.exit(main())
