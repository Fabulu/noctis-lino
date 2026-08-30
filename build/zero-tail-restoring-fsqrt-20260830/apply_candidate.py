from pathlib import Path
import hashlib

ROOT = Path("C:/programmieren/linoleum")
EVIDENCE = ROOT / "build/zero-tail-restoring-fsqrt-20260830"
ACCEPTED = EVIDENCE / "accepted/fpsoft.txt"
SOURCE = ROOT / "work/fp/fpsoft.txt"
EXPECTED_ACCEPTED_SHA256 = (
    "063ecf40b0faab3b2779d8ff159b8fa815eec7b397de0d47e68223841e2a59cc")

OLD_ODD = b'''\t[srd0] = 0; [srd1] = 0;
\tA = [XML]; [srd2] = A;
'''
NEW_ODD = b'''\tA = [XML]; [srd2] = A;
'''

OLD_EVEN = b'''    "XRoot even"
\t[srd0] = 0;
\tA = [XML]; A < 31; [srd1] = A;
\tA = [XML]; A > 1; [srd2] = A;
'''
NEW_EVEN = b'''    "XRoot even"
\t( XFromF64 leaves at least eleven low XML bits clear, so XML<<31
\t  is exactly zero for every scalar binary64 input. )
\tA = [XML]; A > 1; [srd2] = A;
'''

OLD_READY = b'''    "XRoot radicand ready"
\t[sqrh] = 0; [sqrl] = 0;
'''
NEW_READY = b'''    "XRoot radicand ready"
\t( Both binary64-derived lower radicand limbs are exactly zero. )
\t[srd0] = 0; [srd1] = 0;
\t[sqrh] = 0; [sqrl] = 0;
'''

OLD_INPUT = b'''    "XRoot restoring loop"
\t( Consume and shift the directly addressed active-limb buffer. )
\tA = [sqmh]; E = A;
\tA < 2; [sqmh] = A;
\tA = E; A > 30; E = A;

\t( remainder = remainder*4 + pair )
'''
NEW_INPUT = b'''    "XRoot restoring loop"
\t( Consume and shift the directly addressed active-limb buffer.  Once
\t  it is zero, all remaining pairs in that limb are zero. )
\tA = [sqmh]; E = A;
\t? A = 0 -> XRoot restoring pair ready;
\tA < 2; [sqmh] = A;
\tA = E; A > 30; E = A;
    "XRoot restoring pair ready"

\t( remainder = remainder*4 + pair )
'''

OLD_ACCEPT_BIT = b'''\t( Set the admitted low root bit. )
\t[sqrl]+;
\t? [sqrl] != 0 -> XRoot restoring next;
\t[sqrh]+;
    "XRoot restoring next"
'''
NEW_ACCEPT_BIT = b'''\t( The shifted low root word is even, so admitting its low bit
\t  cannot wrap or carry into the high word. )
\t[sqrl]+;
    "XRoot restoring next"
'''

OLD_HANDOFF = b'''\t[sqml]-;
\t? [sqml] != 0 -> XRoot restoring loop;
\t[sqstep]-;
\t? [sqstep] < srd0 -> XRoot restoring complete;
\tB = [sqstep]; A = [B]; [sqmh] = A;
\tA = 0; [B] = A; [sqml] = 16;
\t-> XRoot restoring loop;
    "XRoot restoring complete"
'''
NEW_HANDOFF = b'''\t[sqml]-;
\t? [sqml] != 0 -> XRoot restoring loop;
\t[sqstep]-;
\t? [sqstep] < srd2 -> XRoot restoring lower;
\t( The only live handoff is the second high radicand limb. )
\tA = [srd2]; [sqmh] = A; [srd2] = 0; [sqml] = 16;
\t-> XRoot restoring loop;
    "XRoot restoring lower"
\t? [sqstep] < srd0 -> XRoot restoring complete;
\t( The binary64-derived lower limbs are already zero.  Account for their
\t  two pointer steps once and consume their 32 zero pairs in one phase. )
\t[sqstep]-; [sqml] = 32;
\t-> XRoot restoring loop;
    "XRoot restoring complete"
'''

OLD_PAD = b'''\t( The buffered handoff consumes the accepted calibration footprint. )
'''
NEW_PAD = b'''\t( Eight unreachable increments retain the accepted helper endpoint. )
\tA+; A+; A+; A+; A+; A+; A+; A+;
'''


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def transform(data):
    assert sha256(data) == EXPECTED_ACCEPTED_SHA256
    for old in (OLD_ODD, OLD_EVEN, OLD_READY, OLD_INPUT, OLD_ACCEPT_BIT,
                OLD_HANDOFF, OLD_PAD):
        assert data.count(old) == 1
    data = data.replace(OLD_ODD, NEW_ODD, 1)
    data = data.replace(OLD_EVEN, NEW_EVEN, 1)
    data = data.replace(OLD_READY, NEW_READY, 1)
    data = data.replace(OLD_INPUT, NEW_INPUT, 1)
    data = data.replace(OLD_ACCEPT_BIT, NEW_ACCEPT_BIT, 1)
    data = data.replace(OLD_HANDOFF, NEW_HANDOFF, 1)
    data = data.replace(OLD_PAD, NEW_PAD, 1)
    return data


if __name__ == "__main__":
    accepted = ACCEPTED.read_bytes()
    candidate = transform(accepted)
    SOURCE.write_bytes(candidate)
    (EVIDENCE / "candidate/fpsoft.txt").write_bytes(candidate)
    print("accepted", sha256(accepted), len(accepted))
    print("candidate", sha256(candidate), len(candidate))
