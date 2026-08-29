from pathlib import Path
import hashlib

ROOT = Path("C:/programmieren/linoleum")
EVIDENCE = ROOT / "build/folded-resident-primary-scan-20260830"
SOURCE = ROOT / "work/vhgame.txt"
ACCEPTED = EVIDENCE / "accepted/vhgame.txt"
CANDIDATE = EVIDENCE / "candidate/vhgame.txt"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def transform(original):
    data = original
    nl = b"\r\n" if b"\r\n" in data else b"\n"

    def lines(*items):
        return nl.join(items)

    def replace_once(old, new):
        nonlocal data
        assert data.count(old) == 1, old
        data = data.replace(old, new, 1)

    replace_once(
        b"\tVHGlocalnear10 = 0; VHGlocalnear11 = 0; VHGlocalnear20 = 0; VHGlocalnear21 = 0;",
        lines(
            b"\tVHGlocalnear10 = 0; VHGlocalnear11 = 0; VHGlocalnear20 = 0; VHGlocalnear21 = 0;",
            b"\tVHGlocalprimarybest = 0FFFFFFFFh; VHGlocalprimarylast = 0FFFFFFFFh;",
            b"\tVHGlocalprimaryprior = 0FFFFFFFFh;",
            b"\tVHGlocalprimarybest0 = 0; VHGlocalprimarybest1 = 0;",
            b"\tVHGlocalprimaryprior0 = 0; VHGlocalprimaryprior1 = 0;",
        ),
    )
    replace_once(
        lines(
            b"\t[VHGlocalresident1] = 0FFFFFFFFh; [VHGlocalresident2] = 0FFFFFFFFh;",
            b"\t[VHGlocalbody] = 0;",
            b'    "VHG local resident scan body"',
        ),
        lines(
            b"\t[VHGlocalresident1] = 0FFFFFFFFh; [VHGlocalresident2] = 0FFFFFFFFh;",
            b"\t[VHGlocalprimarybest] = 0FFFFFFFFh; [VHGlocalprimarylast] = 0FFFFFFFFh;",
            b"\t[VHGlocalprimaryprior] = 0FFFFFFFFh; [VHGlocalbody] = 0;",
            b'    "VHG local resident scan body"',
        ),
    )
    replace_once(
        lines(
            b"\t[VHGNDvecindex] = A; => VHGND absolute body vector; => VHG local body relative;",
            b"\t=> VHG local body distance;",
            b"\tA = [VHGlocalresident1]; ? A != 0FFFFFFFFh -> VHG local resident compare first;",
        ),
        lines(
            b"\t[VHGNDvecindex] = A; => VHGND absolute body vector; => VHG local body relative;",
            b"\t=> VHG local body distance;",
            b"\t( Fold nearest-primary selection into this mandatory all-body pass.  The",
            b"\t  unchanged generic comparison below restores its exact terminal FP state. )",
            b"\tE = nspowner; E + [VHGlocalbody]; A = [E];",
            b"\t? A >= 0 -> VHG local primary track ready;",
            b"\t[VHGlocalprimarylast] = [VHGlocalbody];",
            b"\t[VHGlocalprimaryprior] = [VHGlocalprimarybest];",
            b"\tA = [VHGlocalprimarybest]; ? A = 0FFFFFFFFh -> VHG local primary track first;",
            b"\t[VHGlocalprimaryprior0] = [VHGlocalprimarybest0];",
            b"\t[VHGlocalprimaryprior1] = [VHGlocalprimarybest1];",
            b"\t[FA0] = [VHGlocaldist0]; [FA1] = [VHGlocaldist1];",
            b"\t[FB0] = [VHGlocalprimarybest0]; [FB1] = [VHGlocalprimarybest1]; => FCmp;",
            b"\tA = [FI]; ? A >= 0 -> VHG local primary track ready;",
            b"\t[VHGlocalprimarybest] = [VHGlocalbody];",
            b"\t[VHGlocalprimarybest0] = [VHGlocaldist0];",
            b"\t[VHGlocalprimarybest1] = [VHGlocaldist1];",
            b"\t-> VHG local primary track ready;",
            b'    "VHG local primary track first"',
            b"\t[VHGlocalprimarybest] = [VHGlocalbody];",
            b"\t[VHGlocalprimarybest0] = [VHGlocaldist0];",
            b"\t[VHGlocalprimarybest1] = [VHGlocaldist1];",
            b'    "VHG local primary track ready"',
            b"\tA = [VHGlocalresident1]; ? A != 0FFFFFFFFh -> VHG local resident compare first;",
        ),
    )
    replace_once(
        lines(
            b"\tA = [VHGlocalresident1]; ? A = 0FFFFFFFFh -> VHG local resident scan done;",
            b"\tE = nspowner; E + A; A = [E]; ? A < 0 -> VHG local resident scan done;",
            b"\t( Closest is a moon: replace the generic runner-up with the nearest primary. )",
            b"\t[VHGlocalresident2] = 0FFFFFFFFh; [VHGlocalbody] = 0;",
            b'    "VHG local resident primary body"',
        ),
        lines(
            b"\tA = [VHGlocalresident1]; ? A = 0FFFFFFFFh -> VHG local resident scan done;",
            b"\tE = nspowner; E + A; A = [E]; ? A < 0 -> VHG local resident scan done;",
            b"\t( Closest is a moon.  Re-enter the original primary scan at its final",
            b"\t  primary with the exact preceding nearest state, then retain its trailing",
            b"\t  owner checks.  Malformed systems without a primary use the full scan. )",
            b"\t[VHGlocalresident2] = 0FFFFFFFFh; A = [VHGlocalprimarylast];",
            b"\t? A = 0FFFFFFFFh -> VHG local resident primary full scan;",
            b"\t[VHGlocalbody] = A; [VHGlocalresident2] = [VHGlocalprimaryprior];",
            b"\tA = [VHGlocalprimaryprior]; ? A = 0FFFFFFFFh -> VHG local resident primary body;",
            b"\t[VHGlocalnear20] = [VHGlocalprimaryprior0];",
            b"\t[VHGlocalnear21] = [VHGlocalprimaryprior1];",
            b"\t-> VHG local resident primary body;",
            b'    "VHG local resident primary full scan"',
            b"\t[VHGlocalbody] = 0;",
            b'    "VHG local resident primary body"',
        ),
    )
    return data


if __name__ == "__main__":
    accepted = ACCEPTED.read_bytes()
    assert digest(SOURCE) == digest(ACCEPTED)
    candidate = transform(accepted)
    assert candidate != accepted
    CANDIDATE.parent.mkdir(parents=True, exist_ok=True)
    CANDIDATE.write_bytes(candidate)
    SOURCE.write_bytes(candidate)
    print(f"accepted_source_sha256={digest(ACCEPTED)}")
    print(f"candidate_source_sha256={digest(CANDIDATE)}")
