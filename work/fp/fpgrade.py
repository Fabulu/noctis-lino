#!/usr/bin/env python3
"""fpgrade.py - grade fpstarout.bin against STARMAP.BIN.

Deliberately NOT graded against any table this project produced.  The
expected bit patterns in fpstarexp.txt are checked, every run, to occur
verbatim as stored star ids inside the shipped STARMAP.BIN; if any of them
does not, the grader refuses to report a score at all.  That turns
"grading against a stored artifact", which the house standard forbids, into
"grading against the 1996 binary", which is the whole point of the oracle.

Structural checks run BEFORE any score is printed, because each of them is
a way for every score below to be meaningless for a reason that has nothing
to do with floating point.
"""
import struct
import sys
import os

HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.dirname(HERE)

BATT = [
    ('NsIdentity          CW 133F', 4194),
    ('NsIdentity          CW 123F', 2315),
    ('NsIdentity          CW 103F', 66),
    ('NsIdentityPermuted  CW 133F', 4194),
    ('spill after op 1', None),
    ('spill after op 2', None),
    ('spill after op 3', None),
    ('spill after op 4', None),
    ('store after every op', None),
    ('IsThereIdentity (lookup formula)', 0),
    ('SCALAR route, fpx87+fpconv', None),
]


def main(outpath):
    exp = [int(l.strip(), 16) for l in open(os.path.join(HERE, 'fpstarexp.txt'))]

    # --- the expected values must be real STARMAP.BIN contents ---
    sm = open(os.path.join(WORK, 'STARMAP.BIN'), 'rb').read()
    nrec = (len(sm) - 4) // 32
    ids = set(struct.unpack('<Q', sm[4 + 32 * r: 12 + 32 * r])[0]
              for r in range(nrec))
    missing = [e for e in exp if e not in ids]
    print('STARMAP.BIN: %d bytes, %d records, %d distinct ids'
          % (len(sm), nrec, len(ids)))
    if missing:
        raise SystemExit('REFUSING TO GRADE: %d of %d expected values are not '
                         'in STARMAP.BIN' % (len(missing), len(exp)))
    print('provenance  : all %d expected values occur verbatim in STARMAP.BIN'
          % len(exp))

    d = open(outpath, 'rb').read()
    u = struct.unpack('<%dI' % (len(d) // 4), d)
    qlo, qhi, cw, sw, flg, nbat, nstar, sent = u[:8]

    print('')
    print('header      : qword layout %08X %08X | cw %04X | TOP %d | flags %d'
          % (qlo, qhi, cw, sw, flg))
    print('              nbat %d nstar %d sentinel %07X' % (nbat, nstar, sent))

    bad = []
    if (qlo, qhi) != (0x00000000, 0x3FF00000):
        bad.append('qword layout is NOT low-then-high (fld1 gave %08X %08X)'
                   % (qlo, qhi))
    if sw != 0:
        bad.append('x87 stack TOP is %d, not 0 - a fragment leaks a register' % sw)
    if flg != 0:
        bad.append('FFLG is %d - an unordered compare or a stack fault' % flg)
    if sent != 0x0DEFACED:
        bad.append('tail sentinel is %08X, not 0DEFACED' % sent)
    if nstar != len(exp):
        bad.append('nstar %d != %d expected values' % (nstar, len(exp)))
    if len(u) != 8 + nbat * nstar * 2:
        bad.append('file is %d units, expected %d'
                   % (len(u), 8 + nbat * nstar * 2))
    if bad:
        for b in bad:
            print('STRUCTURAL FAILURE: ' + b)
        raise SystemExit('REFUSING TO GRADE')
    print('structure   : OK')

    print('')
    print('  # battery                            score    required  verdict')
    print('  - --------------------------------- -------- --------- -------')
    vals = []
    fails = 0
    for b in range(nbat):
        base = 8 + b * nstar * 2
        v = [(u[base + 2 * i + 1] << 32) | u[base + 2 * i] for i in range(nstar)]
        vals.append(v)
        ok = sum(1 for i in range(nstar) if v[i] == exp[i])
        name, want = BATT[b] if b < len(BATT) else ('?', None)
        if want is None:
            verdict = '(measured)'
            if ok >= nstar:
                verdict = 'FAIL-not-a-break'
                fails += 1
        elif ok == want:
            verdict = 'MATCH'
        else:
            verdict = 'FAIL'
            fails += 1
        print('  %d %-33s %4d/%d %9s  %s'
              % (b, name, ok, nstar, '-' if want is None else want, verdict))

    print('')
    # the cross-check that means something: two independent implementations
    same = sum(1 for i in range(nstar) if vals[8][i] == vals[10][i])
    print('cross-check : generated chain NsIdentitySpillAll vs hand-written')
    print('              SCALAR route agree on %d/%d values' % (same, nstar))
    if same != nstar:
        print('              FAIL - one of the two has a bug')
        fails += 1
    else:
        print('              MATCH - a generated path and a hand-written path')
        print('              performing the same five stores agree bit for bit')

    print('')
    print('FAILURES: %d' % fails)
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1
                  else os.path.join(HERE, 'fpstarout.bin')))
