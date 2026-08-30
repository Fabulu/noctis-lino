from pathlib import Path
import hashlib

ROOT = Path("C:/programmieren/linoleum")
EVIDENCE = ROOT / "build/restoring-fsqrt-20260830"
SOURCE = ROOT / "work/fp/fpsoft.txt"
ACCEPTED = EVIDENCE / "accepted/fpsoft.txt"
CANDIDATE = EVIDENCE / "candidate/fpsoft.txt"
EXPECTED_ACCEPTED_SHA256 = (
    "5031845ed5dbc0e7913eca691259873d45f0bfc67f1969a14dbd3c3ae172527a")

OLD_VARIABLES = """\
\t( square-root state: fixed 128-bit radicand, root and descending
\t  candidate mask.  Candidate squares use Mul128, so every decision
\t  remains exact in ordinary 32-bit integer instructions. )
\tsrd0 = 0; srd1 = 0; srd2 = 0; srd3 = 0;
\tsqrh = 0; sqrl = 0; sqmh = 0; sqml = 0;
\tsqcarry = 0; sqstep = 0;
\tsrm0 = 0; srm1 = 0; srm2 = 0; srm3 = 0;
"""

NEW_VARIABLES = """\
\t( square-root state: fixed 128-bit radicand, 64-bit root, 96-bit
\t  restoring remainder, 65-bit trial divisor, and bounded scratch. )
\tsrd0 = 0; srd1 = 0; srd2 = 0; srd3 = 0;
\tsqrh = 0; sqrl = 0; sqmh = 0; sqml = 0;
\tsqcarry = 0; sqstep = 0;
\tsrm0 = 0; srm1 = 0; srm2 = 0; srm3 = 0;
"""

NEW_ROOT = """\
      ( XRootCore - exact restoring sqrt(X) at 64 significand bits.
\t  The normalized 64-bit mantissa forms the same fixed 128-bit
\t  radicand as before.  Each of 64 iterations consumes its next two
\t  high bits, shifts the partial root, and subtracts 2*q+1 exactly
\t  when the 96-bit remainder admits the next root bit.  The final
\t  integer remainder drives the same p64 nearest rounding. )

"XRootCore"
\tA = [XE]; A - XBIAS; [xtmp] = A;
\tA = [xtmp]; A & 1;
\t? A = 0 -> XRoot even;
\t[srd0] = 0; [srd1] = 0;
\tA = [XML]; [srd2] = A;
\tA = [XMH]; [srd3] = A;
\tA = [xtmp]; A - 1; [xtmp] = A;
\t-> XRoot radicand ready;
    "XRoot even"
\t[srd0] = 0;
\tA = [XML]; A < 31; [srd1] = A;
\tA = [XML]; A > 1; [srd2] = A;
\tA = [XMH]; A < 31; B = [srd2]; A | B; [srd2] = A;
\tA = [XMH]; A > 1; [srd3] = A;
    "XRoot radicand ready"
\t[sqrh] = 0; [sqrl] = 0;
\t( E holds each incoming pair; srm3 is assigned from E at the
\t  compatibility boundary before its first read. )
\t[srm0] = 0; [srm1] = 0; [srm2] = 0;
\t[sqstep] = 0;
    "XRoot restoring loop"
\t( Consume the radicand's high pair and shift it left by two. )
\tA = [srd3]; A > 30; E = A;
\tA = [srd3]; A < 2; B = [srd2]; B > 30; A | B; [srd3] = A;
\tA = [srd2]; A < 2; B = [srd1]; B > 30; A | B; [srd2] = A;
\tA = [srd1]; A < 2; B = [srd0]; B > 30; A | B; [srd1] = A;
\tA = [srd0]; A < 2; [srd0] = A;

\t( remainder = remainder*4 + pair )
\tA = [srm2]; A < 2; B = [srm1]; B > 30; A | B; [srm2] = A;
\tA = [srm1]; A < 2; B = [srm0]; B > 30; A | B; [srm1] = A;
\tA = [srm0]; A < 2; B = E; A | B; [srm0] = A;

\t( Shift the partial root and form its 65-bit trial 2*q+1. )
\tA = [sqrl]; A > 31; E = A;
\tA = [sqrh]; A < 1; B = E; A | B; [sqrh] = A;
\tA = [sqrl]; A < 1; [sqrl] = A;
\tA = [sqrh]; A > 31; [sqcarry] = A;
\tA = [sqrh]; A < 1; B = [sqrl]; B > 31; A | B; C = A;
\tA = [sqrl]; A < 1; A | 1; D = A;

\t( Accept the next root bit iff remainder >= trial. )
\tA = [srm2]; B = [sqcarry];
\t? A '> B -> XRoot restoring accept;
\t? A '< B -> XRoot restoring next;
\tA = [srm1]; B = C;
\t? A '> B -> XRoot restoring accept;
\t? A '< B -> XRoot restoring next;
\tA = [srm0]; B = D;
\t? A '< B -> XRoot restoring next;
    "XRoot restoring accept"
\t( Subtract the trial with exact unsigned borrows. )
\tA = [srm0]; B = D;
\t? A '< B -> XRoot restoring low borrow;
\tE = 0; -> XRoot restoring low subtract;
    "XRoot restoring low borrow"
\tE = 1;
    "XRoot restoring low subtract"
\tA = [srm0]; A - D; [srm0] = A;
\tA = [srm1]; B = C;
\t? A '> B -> XRoot restoring middle no borrow;
\t? A '< B -> XRoot restoring middle borrow;
\t? E = 0 -> XRoot restoring middle no borrow;
    "XRoot restoring middle borrow"
\tA = [srm1]; A - C; A - E; [srm1] = A;
\tE = 1; -> XRoot restoring high subtract;
    "XRoot restoring middle no borrow"
\tA = [srm1]; A - C; A - E; [srm1] = A;
\tE = 0;
    "XRoot restoring high subtract"
\tA = [srm2]; A - [sqcarry]; A - E; [srm2] = A;

\t( Set the admitted low root bit. )
\t[sqrl]+;
\t? [sqrl] != 0 -> XRoot restoring next;
\t[sqrh]+;
    "XRoot restoring next"
\t[sqstep]+;
\t? [sqstep] < 64 -> XRoot restoring loop;

\t( Reproduce the accepted residual subtraction's low-limb equality
\t  borrow.  Since the fixed radicand's low word is zero, this case
\t  occurs exactly when q's low 16 bits are zero.  Subtracting one
\t  from residual word one, with propagation, forms the accepted
\t  private residual before its p64 rounding decision. )
\tE = 0;
\tA = [sqrl]; A & XM16;
\t? A != 0 -> XRoot residual compatible;
\t[srm1]-;
\t? [srm1] != 0FFFFFFFFh -> XRoot residual compatible;
\t[srm2]-;
\t? [srm2] != 0FFFFFFFFh -> XRoot residual compatible;
\tE = 0FFFFFFFFh;
    "XRoot residual compatible"
\tA = E; [srm3] = A;

\t( Round up iff the accepted residual is greater than q. )
\t? E != 0 -> XRoot increment;
\t? [srm2] != 0 -> XRoot increment;
\tA = [srm1]; B = [sqrh];
\t? A '> B -> XRoot increment;
\t? A '< B -> XRoot done;
\tA = [srm0]; B = [sqrl];
\t? A '> B -> XRoot increment;
\t-> XRoot done;
    "XRoot increment"
\t[sqrl]+;
\t? [sqrl] != 0 -> XRoot done;
\t[sqrh]+;
\t? [sqrh] != 0 -> XRoot overflow;
\t-> XRoot done;
    "XRoot overflow"
\t[XMH] = 80000000h; [XML] = 0; [xtmp]+;
\t-> XRoot finish;
    "XRoot done"
\tA = [sqrh]; [XMH] = A;
\tA = [sqrl]; [XML] = A;
    "XRoot finish"
\tA = [xtmp]; A / 2; A + XBIAS; [XE] = A;
\t[XS] = 0;
\tend;
\t( Unreachable footprint calibration: preserve downstream addresses. )
\tA = 0; A = 0; A = 0; A = 0;
"""


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def transform(original):
    newline = "\r\n" if b"\r\n" in original else "\n"
    text = original.decode("utf-8").replace("\r\n", "\n")
    assert text.count(OLD_VARIABLES) == 1
    text = text.replace(OLD_VARIABLES, NEW_VARIABLES)
    start = text.index("      ( XRootCore - exact integer bit-search")
    end = text.index("      ( XChop32 - truncate", start)
    old_root = text[start:end]
    assert old_root.count("=> Mul128;") == 2
    assert '"XRoot bit loop"' in old_root
    assert old_root.count("[sqstep]+;") == 1
    text = text[:start] + NEW_ROOT + "\n" + text[end:]
    candidate = text.replace("\n", newline).encode("utf-8")
    assert candidate != original
    return candidate


if __name__ == "__main__":
    accepted = ACCEPTED.read_bytes()
    assert digest(ACCEPTED) == EXPECTED_ACCEPTED_SHA256
    assert SOURCE.read_bytes() == accepted
    candidate = transform(accepted)
    CANDIDATE.write_bytes(candidate)
    SOURCE.write_bytes(candidate)
    print(f"accepted_source_sha256={digest(ACCEPTED)}")
    print(f"candidate_source_sha256={digest(CANDIDATE)}")
