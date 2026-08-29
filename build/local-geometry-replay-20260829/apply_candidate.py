from pathlib import Path
import hashlib

ROOT = Path("C:/programmieren/linoleum")
EVIDENCE = ROOT / "build/local-geometry-replay-20260829"
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
        b"\tVHGlocalbatch = 0; VHGlocalacc = 0; VHGlocalphasetick = 0;",
        lines(
            b"\tVHGlocalbatch = 0; VHGlocalacc = 0; VHGlocalphasetick = 0;",
            b"\tVHGlocalcacheepoch = 0;",
        ),
    )
    replace_once(
        b"\tVHGwideoutput = 183200;",
        lines(
            b"\tVHGwideoutput = 183200;",
            b"\t( 80 exact body records: relative x/y/z and rooted distance, two units each. )",
            b"\tVHGlocalbodycache = 640;",
        ),
    )
    replace_once(
        lines(
            b"\t[VHGlocaltz0] = [VHGNDvecz0]; [VHGlocaltz1] = [VHGNDvecz1];",
            b"\t=> VHG local resident scan;",
            b"\t( The primary star is -planet_xyz-ship. )",
        ),
        lines(
            b"\t[VHGlocaltz0] = [VHGNDvecz0]; [VHGlocaltz1] = [VHGNDvecz1];",
            b"\t=> VHG local resident scan; [VHGlocalcacheepoch] = [VHGNDsecs];",
            b"\t( The primary star is -planet_xyz-ship. )",
        ),
    )
    replace_once(
        lines(
            b"\t[VHGNDvecindex] = A; => VHGND absolute body vector;",
            b"\t=> VHG local body relative;",
            b"\tA = [VHGlocalbody]; A < 1; E = nspray; E + A;",
        ),
        lines(
            b"\tA = [VHGNDsecs]; ? A != [VHGlocalcacheepoch] -> VHG local body live geometry;",
            b"\tA = [VHGlocalbody]; A < 3; E = VHGlocalbodycache; E + A;",
            b"\t[VHGlocalringcx0] = [E plus 0]; [VHGlocalringcx1] = [E plus 1];",
            b"\t[VHGlocalringcy0] = [E plus 2]; [VHGlocalringcy1] = [E plus 3];",
            b"\t[VHGlocalringcz0] = [E plus 4]; [VHGlocalringcz1] = [E plus 5];",
            b"\t[FA0] = [VHGlocalringcx0]; [FA1] = [VHGlocalringcx1]; [PGFi] = SFXX; => PGF sa;",
            b"\t[FA0] = [VHGlocalringcy0]; [FA1] = [VHGlocalringcy1]; [PGFi] = SFYY; => PGF sa;",
            b"\t[FA0] = [VHGlocalringcz0]; [FA1] = [VHGlocalringcz1];",
            b"\t[FB0] = [VHGlocalz0]; [FB1] = [VHGlocalz1]; [PGFi] = SFZZ; => PGF sa;",
            b"\t-> VHG local body geometry ready;",
            b'    "VHG local body live geometry"',
            b"\t[VHGNDvecindex] = [VHGlocalbody]; => VHGND absolute body vector;",
            b"\t=> VHG local body relative;",
            b'    "VHG local body geometry ready"',
            b"\tA = [VHGlocalbody]; A < 1; E = nspray; E + A;",
        ),
    )
    replace_once(
        b"\t[VHGlocalringbody] = [VHGlocalbody]; => VHG local body distance;",
        lines(
            b"\t[VHGlocalringbody] = [VHGlocalbody];",
            b"\tA = [VHGNDsecs]; ? A != [VHGlocalcacheepoch] -> VHG local body live distance;",
            b"\tA = [VHGlocalbody]; A < 3; E = VHGlocalbodycache; E + A;",
            b"\t[VHGlocaldist0] = [E plus 6]; [VHGlocaldist1] = [E plus 7];",
            b"\t-> VHG local body distance ready;",
            b'    "VHG local body live distance"',
            b"\t=> VHG local body distance;",
            b'    "VHG local body distance ready"',
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
            b"\tA = [VHGlocalbody]; A < 3; E = VHGlocalbodycache; E + A;",
            b"\t[E plus 0] = [VHGlocalringcx0]; [E plus 1] = [VHGlocalringcx1];",
            b"\t[E plus 2] = [VHGlocalringcy0]; [E plus 3] = [VHGlocalringcy1];",
            b"\t[E plus 4] = [VHGlocalringcz0]; [E plus 5] = [VHGlocalringcz1];",
            b"\t[E plus 6] = [VHGlocaldist0]; [E plus 7] = [VHGlocaldist1];",
            b"\tA = [VHGlocalresident1]; ? A != 0FFFFFFFFh -> VHG local resident compare first;",
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
