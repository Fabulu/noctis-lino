from pathlib import Path
import hashlib

ROOT = Path("C:/programmieren/linoleum")
EVIDENCE = ROOT / "build/gray-split-mul128-20260830"
ACCEPTED = EVIDENCE / "accepted/fpsoft.txt"
CANDIDATE = EVIDENCE / "candidate/fpsoft.txt"
EXPECTED_ACCEPTED_SHA256 = (
    "063ecf40b0faab3b2779d8ff159b8fa815eec7b397de0d47e68223841e2a59cc")

LABEL_OLD = b"""\tA = [xub]; A > 16; A & XM16;\t\t[xuh1] = A;
\tA = [xul0]; A '* [xul1];\t\t[xup0] = A;
"""
LABEL_NEW = b"""\tA = [xub]; A > 16; A & XM16;\t\t[xuh1] = A;
    "XMul32u split"
\tA = [xul0]; A '* [xul1];\t\t[xup0] = A;
"""

SCHEDULE_OLD = b"""\t[xua] = [XML]; [xub] = [YML]; => XMul32u;
\t[xa0] = [xulo]; [xa1] = [xuhi];
\t[xua] = [XML]; [xub] = [YMH]; => XMul32u;
\t[xb0] = [xulo]; [xb1] = [xuhi];
\t[xua] = [XMH]; [xub] = [YML]; => XMul32u;
\t[xc0] = [xulo]; [xc1] = [xuhi];
\t[xua] = [XMH]; [xub] = [YMH]; => XMul32u;
\t[xd0] = [xulo]; [xd1] = [xuhi];

"""
SCHEDULE_NEW = b"""\t( Split each source word once.  xa..xd hold halves until their
\t  canonical partial product replaces them. )
\tA = [XML]; A & XM16;\t\t[xa0] = A;
\tA = [XML]; A > 16; A & XM16;\t[xa1] = A;
\tA = [YMH]; A & XM16;\t\t[xb0] = A;
\tA = [YMH]; A > 16; A & XM16;\t[xb1] = A;
\tA = [YML]; A & XM16;\t\t[xc0] = A;
\tA = [YML]; A > 16; A & XM16;\t[xc1] = A;
\tA = [XMH]; A & XM16;\t\t[xd0] = A;
\tA = [XMH]; A > 16; A & XM16;\t[xd1] = A;

\t( Gray order b, a, c, d changes one staged operand at a time.
\t  Keep d last to retain the accepted terminal helper scratch. )
\t[xul0] = [xa0]; [xuh0] = [xa1];
\t[xul1] = [xb0]; [xuh1] = [xb1]; => XMul32u split;
\t[xua] = [xulo]; [xub] = [xuhi];

\t[xul1] = [xc0]; [xuh1] = [xc1]; => XMul32u split;
\t[xa0] = [xulo]; [xa1] = [xuhi];

\t[xul0] = [xd0]; [xuh0] = [xd1]; => XMul32u split;
\t[xc0] = [xulo]; [xc1] = [xuhi];

\t[xul1] = [xb0]; [xuh1] = [xb1]; => XMul32u split;
\t[xd0] = [xulo]; [xd1] = [xuhi];

\t( Restore canonical b before replacing its temporary product image. )
\t[xb0] = [xua]; [xb1] = [xub];
\t[xua] = [XMH]; [xub] = [YMH];

"""


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def transform(source):
    assert sha256(source) == EXPECTED_ACCEPTED_SHA256
    assert source.count(LABEL_OLD) == 1
    assert source.count(SCHEDULE_OLD) == 1
    candidate = source.replace(LABEL_OLD, LABEL_NEW, 1)
    candidate = candidate.replace(SCHEDULE_OLD, SCHEDULE_NEW, 1)
    assert candidate != source
    assert candidate.count(b'"XMul32u split"') == 1
    assert candidate.count(b"=> XMul32u split;") == 4
    return candidate


if __name__ == "__main__":
    accepted = ACCEPTED.read_bytes()
    candidate = transform(accepted)
    CANDIDATE.write_bytes(candidate)
    print(sha256(candidate))
