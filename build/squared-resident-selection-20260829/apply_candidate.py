from pathlib import Path
import hashlib

ROOT = Path("C:/programmieren/linoleum")
EVIDENCE = ROOT / "build/squared-resident-selection-20260829"
SOURCE = ROOT / "work/vhgame.txt"
ACCEPTED = EVIDENCE / "accepted/vhgame.txt"


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
            b"\tVHGlocalsqnear10 = 0; VHGlocalsqnear11 = 0; VHGlocalsqnear20 = 0; VHGlocalsqnear21 = 0;",
            b"\tVHGlocalsqcand0 = 0; VHGlocalsqcand1 = 0;",
        ),
    )
    replace_once(
        lines(
            b'"VHG local resident scan"',
            b"\t( NOCTIS-0.CPP:5290-5317.  Find the two nearest bodies without changing",
            b"\t  their generated order.  When the nearest is a moon, the second resident",
            b"\t  is the nearest primary, preserving one useful body for each physical map. )",
            b"\t[VHGlocalresident1] = 0FFFFFFFFh; [VHGlocalresident2] = 0FFFFFFFFh;",
            b"\t[VHGlocalbody] = 0;",
            b'    "VHG local resident scan body"',
            b"\tA = [VHGlocalbody]; ? A '>= [nsnob] -> VHG local resident pair ready;",
            b"\t[VHGNDvecindex] = A; => VHGND absolute body vector; => VHG local body relative;",
            b"\t=> VHG local body distance;",
            b"\tA = [VHGlocalresident1]; ? A != 0FFFFFFFFh -> VHG local resident compare first;",
            b"\t[VHGlocalresident1] = [VHGlocalbody];",
            b"\t[VHGlocalnear10] = [VHGlocaldist0]; [VHGlocalnear11] = [VHGlocaldist1];",
            b"\t-> VHG local resident scan next;",
            b'    "VHG local resident compare first"',
            b"\t[FA0] = [VHGlocaldist0]; [FA1] = [VHGlocaldist1];",
            b"\t[FB0] = [VHGlocalnear10]; [FB1] = [VHGlocalnear11]; => FCmp;",
            b"\tA = [FI]; ? A >= 0 -> VHG local resident compare second;",
            b"\t[VHGlocalresident2] = [VHGlocalresident1];",
            b"\t[VHGlocalnear20] = [VHGlocalnear10]; [VHGlocalnear21] = [VHGlocalnear11];",
            b"\t[VHGlocalresident1] = [VHGlocalbody];",
            b"\t[VHGlocalnear10] = [VHGlocaldist0]; [VHGlocalnear11] = [VHGlocaldist1];",
            b"\t-> VHG local resident scan next;",
            b'    "VHG local resident compare second"',
            b"\tA = [VHGlocalresident2]; ? A != 0FFFFFFFFh -> VHG local resident compare second distance;",
            b"\t[VHGlocalresident2] = [VHGlocalbody];",
            b"\t[VHGlocalnear20] = [VHGlocaldist0]; [VHGlocalnear21] = [VHGlocaldist1];",
            b"\t-> VHG local resident scan next;",
            b'    "VHG local resident compare second distance"',
            b"\t[FA0] = [VHGlocaldist0]; [FA1] = [VHGlocaldist1];",
            b"\t[FB0] = [VHGlocalnear20]; [FB1] = [VHGlocalnear21]; => FCmp;",
            b"\tA = [FI]; ? A >= 0 -> VHG local resident scan next;",
            b"\t[VHGlocalresident2] = [VHGlocalbody];",
            b"\t[VHGlocalnear20] = [VHGlocaldist0]; [VHGlocalnear21] = [VHGlocaldist1];",
            b'    "VHG local resident scan next"',
            b"\t[VHGlocalbody]+; -> VHG local resident scan body;",
        ),
        lines(
            b'"VHG local resident scan"',
            b"\t( NOCTIS-0.CPP:5290-5317.  Find the two nearest bodies without changing",
            b"\t  their generated order.  Finite squared distances reject bodies which",
            b"\t  cannot enter the rooted top two; rooted comparisons retain exact ties,",
            b"\t  special-value handling, the final public distance, and generated order. )",
            b"\t[VHGlocalresident1] = 0FFFFFFFFh; [VHGlocalresident2] = 0FFFFFFFFh;",
            b"\t[VHGlocalbody] = 0;",
            b'    "VHG local resident scan body"',
            b"\tA = [VHGlocalbody]; ? A '>= [nsnob] -> VHG local resident pair ready;",
            b"\t[VHGNDvecindex] = A; => VHGND absolute body vector; => VHG local body relative;",
            b"\t=> VHG local body distance squared;",
            b"\t[VHGlocalsqcand0] = [FA0]; [VHGlocalsqcand1] = [FA1];",
            b"\tA = [VHGlocalresident1]; ? A != 0FFFFFFFFh -> VHG local resident compare first square;",
            b"\t[VHGlocalsqnear10] = [VHGlocalsqcand0]; [VHGlocalsqnear11] = [VHGlocalsqcand1];",
            b"\t=> VHG local body distance root; [VHGlocalresident1] = [VHGlocalbody];",
            b"\t[VHGlocalnear10] = [VHGlocaldist0]; [VHGlocalnear11] = [VHGlocaldist1];",
            b"\t-> VHG local resident scan next;",
            b'    "VHG local resident compare first square"',
            b"\t( Portable FSqrt deliberately maps special binary64 input to zero. )",
            b"\tA = [VHGlocalsqcand1]; A > 20; A & 7FFh; ? A = 7FFh -> VHG local resident compare first root;",
            b"\tA = [VHGlocalbody]; A + 1; ? A = [nsnob] -> VHG local resident compare first root;",
            b"\t[FA0] = [VHGlocalsqcand0]; [FA1] = [VHGlocalsqcand1];",
            b"\t[FB0] = [VHGlocalsqnear10]; [FB1] = [VHGlocalsqnear11]; => FCmp;",
            b"\tA = [FI]; ? A >= 0 -> VHG local resident compare second square;",
            b'    "VHG local resident compare first root"',
            b"\t[FA0] = [VHGlocalsqcand0]; [FA1] = [VHGlocalsqcand1]; => VHG local body distance root;",
            b"\t[FB0] = [VHGlocalnear10]; [FB1] = [VHGlocalnear11]; => FCmp;",
            b"\tA = [FI]; ? A >= 0 -> VHG local resident compare second rooted;",
            b"\t[VHGlocalresident2] = [VHGlocalresident1];",
            b"\t[VHGlocalnear20] = [VHGlocalnear10]; [VHGlocalnear21] = [VHGlocalnear11];",
            b"\t[VHGlocalsqnear20] = [VHGlocalsqnear10]; [VHGlocalsqnear21] = [VHGlocalsqnear11];",
            b"\t[VHGlocalresident1] = [VHGlocalbody];",
            b"\t[VHGlocalnear10] = [VHGlocaldist0]; [VHGlocalnear11] = [VHGlocaldist1];",
            b"\t[VHGlocalsqnear10] = [VHGlocalsqcand0]; [VHGlocalsqnear11] = [VHGlocalsqcand1];",
            b"\t-> VHG local resident scan next;",
            b'    "VHG local resident compare second square"',
            b"\tA = [VHGlocalresident2]; ? A = 0FFFFFFFFh -> VHG local resident root second;",
            b"\t[FA0] = [VHGlocalsqcand0]; [FA1] = [VHGlocalsqcand1];",
            b"\t[FB0] = [VHGlocalsqnear20]; [FB1] = [VHGlocalsqnear21]; => FCmp;",
            b"\tA = [FI]; ? A >= 0 -> VHG local resident scan next;",
            b'    "VHG local resident root second"',
            b"\t[FA0] = [VHGlocalsqcand0]; [FA1] = [VHGlocalsqcand1]; => VHG local body distance root;",
            b'    "VHG local resident compare second rooted"',
            b"\tA = [VHGlocalresident2]; ? A != 0FFFFFFFFh -> VHG local resident compare second distance;",
            b"\t[VHGlocalresident2] = [VHGlocalbody];",
            b"\t[VHGlocalnear20] = [VHGlocaldist0]; [VHGlocalnear21] = [VHGlocaldist1];",
            b"\t[VHGlocalsqnear20] = [VHGlocalsqcand0]; [VHGlocalsqnear21] = [VHGlocalsqcand1];",
            b"\t-> VHG local resident scan next;",
            b'    "VHG local resident compare second distance"',
            b"\t[FA0] = [VHGlocaldist0]; [FA1] = [VHGlocaldist1];",
            b"\t[FB0] = [VHGlocalnear20]; [FB1] = [VHGlocalnear21]; => FCmp;",
            b"\tA = [FI]; ? A >= 0 -> VHG local resident scan next;",
            b"\t[VHGlocalresident2] = [VHGlocalbody];",
            b"\t[VHGlocalnear20] = [VHGlocaldist0]; [VHGlocalnear21] = [VHGlocaldist1];",
            b"\t[VHGlocalsqnear20] = [VHGlocalsqcand0]; [VHGlocalsqnear21] = [VHGlocalsqcand1];",
            b'    "VHG local resident scan next"',
            b"\t[VHGlocalbody]+; -> VHG local resident scan body;",
        ),
    )
    replace_once(
        lines(
            b'"VHG local body distance"',
            b"\t[PGFi] = SFXX; => PGF a; [PGFi] = SFXX; => PGF mul; [PGFi] = FSW0; => PGF sa;",
            b"\t[PGFi] = SFYY; => PGF a; [PGFi] = SFYY; => PGF mul; [PGFi] = FSW0; => PGF add;",
            b"\t[PGFi] = SFZZ; => PGF a; [PGFi] = SFZZ; => PGF mul; [PGFi] = FSW0; => PGF add;",
            b"\t=> FSqrt; [VHGlocaldist0] = [FA0]; [VHGlocaldist1] = [FA1];",
            b"\tend;",
        ),
        lines(
            b'"VHG local body distance squared"',
            b"\t[PGFi] = SFXX; => PGF a; [PGFi] = SFXX; => PGF mul; [PGFi] = FSW0; => PGF sa;",
            b"\t[PGFi] = SFYY; => PGF a; [PGFi] = SFYY; => PGF mul; [PGFi] = FSW0; => PGF add;",
            b"\t[PGFi] = SFZZ; => PGF a; [PGFi] = SFZZ; => PGF mul; [PGFi] = FSW0; => PGF add;",
            b"\tend;",
            b"",
            b'"VHG local body distance root"',
            b"\t=> FSqrt; [VHGlocaldist0] = [FA0]; [VHGlocaldist1] = [FA1];",
            b"\tend;",
            b"",
            b'"VHG local body distance"',
            b"\t=> VHG local body distance squared; => VHG local body distance root;",
            b"\tend;",
        ),
    )
    return data


if __name__ == "__main__":
    accepted = ACCEPTED.read_bytes()
    assert digest(SOURCE) == digest(ACCEPTED)
    candidate = transform(accepted)
    assert candidate != accepted
    SOURCE.write_bytes(candidate)
    print(f"accepted_source_sha256={digest(ACCEPTED)}")
    print(f"candidate_source_sha256={digest(SOURCE)}")
