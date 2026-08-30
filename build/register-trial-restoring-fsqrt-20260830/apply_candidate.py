from pathlib import Path
import hashlib

ROOT = Path("C:/programmieren/linoleum")
EVIDENCE = ROOT / "build/register-trial-restoring-fsqrt-20260830"
ACCEPTED = EVIDENCE / "accepted/fpsoft.txt"
SOURCE = ROOT / "work/fp/fpsoft.txt"
EXPECTED_ACCEPTED_SHA256 = (
    "063ecf40b0faab3b2779d8ff159b8fa815eec7b397de0d47e68223841e2a59cc")

OLD_INIT = b'''    "XRoot radicand ready"
\t[sqrh] = 0; [sqrl] = 0;
\t( E holds each incoming pair; srm3 is assigned from E at the
'''
NEW_INIT = b'''    "XRoot radicand ready"
\t( Keep the odd trial carrier T = 2*q+1 live in C:D. )
\tC = 0; D = 1;
\t( E holds each incoming pair; srm3 is assigned from E at the
'''

OLD_TRIAL = b'''\t( Shift the partial root and form its 65-bit trial 2*q+1. )
\tA = [sqrl]; A > 31; E = A;
\tA = [sqrh]; A < 1; B = E; A | B; [sqrh] = A;
\tA = [sqrl]; A < 1; [sqrl] = A;
\tA = [sqrh]; A > 31; [sqcarry] = A;
\tA = [sqrh]; A < 1; B = [sqrl]; B > 31; A | B; C = A;
\tA = [sqrl]; A < 1; A | 1; D = A;
'''
NEW_TRIAL = b'''\t( Form trial = 2*T-1 = 4*q+1.  Since T is odd, the low
\t  subtraction cannot borrow. )
\tA = C; A > 31; [sqcarry] = A;
\tA = D; A > 31; E = A;
\tA = C; A < 1; B = E; A | B; C = A;
\tA = D; A < 1; A - 1; D = A;
'''

OLD_ACCEPT = b'''\t( Set the admitted low root bit. )
\t[sqrl]+;
\t? [sqrl] != 0 -> XRoot restoring next;
\t[sqrh]+;
    "XRoot restoring next"
'''
NEW_ACCEPT = b'''\t( The admitted bit makes T = trial+2.  The odd-carrier
\t  invariant proves the low word cannot wrap. )
\tD + 2;
    "XRoot restoring next"
'''

OLD_COMPLETE = b'''    "XRoot restoring complete"

\t( Reproduce the accepted residual subtraction's low-limb equality
'''
NEW_COMPLETE = b'''    "XRoot restoring complete"
\t( Recover q = T>>1 before private residual compatibility. )
\tA = C; A < 31; B = D; B > 1; A | B; [sqrl] = A;
\tA = [sqcarry]; A < 31; B = C; B > 1; A | B; [sqrh] = A;

\t( Reproduce the accepted residual subtraction's low-limb equality
'''

OLD_PAD = b'''\t( The buffered handoff consumes the accepted calibration footprint. )
'''
NEW_PAD = b'''\t( Unreachable footprint calibration follows the register recurrence. )
\tA = 0; A = 0; A = 0; A = 0; A = 0;
\tA = 0; A = 0; A = 0; A = 0;
\tA+; A+; A+; A+;
'''


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def transform(data):
    assert sha256(data) == EXPECTED_ACCEPTED_SHA256
    for old in (OLD_INIT, OLD_TRIAL, OLD_ACCEPT, OLD_COMPLETE, OLD_PAD):
        assert data.count(old) == 1
    data = data.replace(OLD_INIT, NEW_INIT, 1)
    data = data.replace(OLD_TRIAL, NEW_TRIAL, 1)
    data = data.replace(OLD_ACCEPT, NEW_ACCEPT, 1)
    data = data.replace(OLD_COMPLETE, NEW_COMPLETE, 1)
    data = data.replace(OLD_PAD, NEW_PAD, 1)
    return data


if __name__ == "__main__":
    accepted = ACCEPTED.read_bytes()
    candidate = transform(accepted)
    (EVIDENCE / "candidate").mkdir(exist_ok=True)
    SOURCE.write_bytes(candidate)
    (EVIDENCE / "candidate/fpsoft.txt").write_bytes(candidate)
    print("accepted", sha256(accepted), len(accepted))
    print("candidate", sha256(candidate), len(candidate))
