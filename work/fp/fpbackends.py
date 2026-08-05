#!/usr/bin/env python3
"""fpbackends.py - cross-grade the three backends against each other.

X87 vs SOFT is the one that carries weight: the two consume the SAME
schedule and produce the same bits by completely different means, one on
Intel's FPU and one in integer code that never touches it.  That is
circular with respect to the schedule and not circular with respect to the
arithmetic, and the distinction matters enough to print it.

NATIVE vs the PC=24 x87 battery is a different kind of claim: it tests
whether "L.in.oleum is 24 bits per operation" is literally true, by running
L.in.oleum's own instructions against an x87 forced to the same precision.
"""
import struct
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def load(name, nbat):
    d = open(os.path.join(HERE, name), 'rb').read()
    u = struct.unpack('<%dI' % (len(d) // 4), d)
    n = u[6]
    if u[7] != 0x0DEFACED:
        raise SystemExit('%s: tail sentinel %08X' % (name, u[7]))
    bats = []
    for k in range(nbat):
        base = 8 + k * n * 2
        bats.append([(u[base + 2 * i + 1] << 32) | u[base + 2 * i]
                     for i in range(n)])
    return u[:8], bats, n


exp = [int(l.strip(), 16) for l in open(os.path.join(HERE, 'fpstarexp.txt'))]
hx, x87, N = load('fpstarout.bin', 11)
hn, nat, _ = load('fpstarnatout.bin', 3)
hs, sft, _ = load('fpstarsoftout.bin', 2)


def score(v):
    return sum(1 for i in range(N) if v[i] == exp[i])


def same(a, b):
    return sum(1 for i in range(N) if a[i] == b[i])


fails = 0
print('scores against STARMAP.BIN, %d stars' % N)
print('  X87    NsIdentity   CW 133F   %4d/%d' % (score(x87[0]), N))
print('  SOFT   NsIdentity   CW 133F   %4d/%d' % (score(sft[0]), N))
print('  SOFT   NsIdentity   CW 103F   %4d/%d' % (score(sft[1]), N))
print('  NATIVE NsIdentity   CW 103F   %4d/%d' % (score(nat[0]), N))
print('  NATIVE NsIdentity   CW 1C3F   %4d/%d   (RC=chop, the shipped word)'
      % (score(nat[1]), N))
print('  NATIVE NsIdentity   CW 133F   %4d/%d' % (score(nat[2]), N))
print('')

checks = [
    ('X87 == SOFT, both at CW 133F', same(x87[0], sft[0]), N,
     'different machinery, same schedule, same bits'),
    ('SOFT PC=64 == SOFT PC=24', same(sft[0], sft[1]), N,
     'the precision control cannot reach code that never touches the FPU'),
    ('NATIVE RC=nearest == X87 PC=24', same(nat[0], x87[2]), N,
     'L.in.oleum is 24 bits per operation, measured against an x87 held there'),
    ('NATIVE PC=24 == NATIVE PC=64', same(nat[0], nat[2]), N,
     'raising the precision control does NOTHING for native instructions'),
]
for label, got, want, why in checks:
    ok = got == want
    if not ok:
        fails += 1
    print('  %-34s %4d/%d  %s' % (label, got, want, 'MATCH' if ok else 'FAIL'))
    print('      %s' % why)

print('')
print('required scores:')
for label, got, want in [('X87 CW 133F', score(x87[0]), N),
                         ('SOFT CW 133F', score(sft[0]), N),
                         ('SOFT CW 103F', score(sft[1]), N)]:
    ok = got == want
    if not ok:
        fails += 1
    print('  %-16s %4d/%d  %s' % (label, got, want, 'MATCH' if ok else 'FAIL'))

print('')
print('FAILURES: %d' % fails)
sys.exit(1 if fails else 0)
