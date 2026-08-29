from pathlib import Path
import hashlib

ROOT = Path("C:/programmieren/linoleum")
EVIDENCE = ROOT / "build/two-level-orbital-replay-20260830"
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
            b"\tVHGlocalbasisepoch = 0; VHGlocalbasisvalid = 0; VHGlocalbasisfill = 0;",
            b"\tVHGlocalframeepoch = 0; VHGlocalframevalid = 0; VHGlocalterminalvalid = 0;",
        ),
    )
    replace_once(
        b"\tVHGwideoutput = 183200;",
        lines(
            b"\tVHGwideoutput = 183200;",
            b"\t( 80 exact selected-relative basis, absolute scratch, frame geometry, and distance records. )",
            b"\tVHGlocalbodycache = 5120;",
        ),
    )
    replace_once(
        b"\t[VHGlocalactive] = 0; [VHGlocaltarget] = 0FFFFFFFFh; [VHGlandpending] = 0;",
        lines(
            b"\t[VHGlocalactive] = 0; [VHGlocaltarget] = 0FFFFFFFFh; [VHGlandpending] = 0;",
            b"\t[VHGlocalbasisvalid] = 0; [VHGlocalbasisfill] = 0;",
            b"\t[VHGlocalframevalid] = 0; [VHGlocalterminalvalid] = 0;",
        ),
    )
    replace_once(
        b"\t[VHGlocalactive] = 1; [VHGlocaltarget] = [VHGplanet]; [VHGlocalacc] = 0;",
        lines(
            b"\t[VHGlocalactive] = 1; [VHGlocaltarget] = [VHGplanet]; [VHGlocalacc] = 0;",
            b"\t[VHGlocalbasisvalid] = 0; [VHGlocalbasisfill] = 0;",
            b"\t[VHGlocalframevalid] = 0; [VHGlocalterminalvalid] = 0;",
        ),
    )
    replace_once(
        b'"VHG restore local checkpoint"',
        lines(
            b'"VHG restore local checkpoint"',
            b"\t[VHGlocalbasisvalid] = 0; [VHGlocalbasisfill] = 0;",
            b"\t[VHGlocalframevalid] = 0; [VHGlocalterminalvalid] = 0;",
        ),
    )
    replace_once(
        lines(
            b'"VHG local render"',
            b"\tA = [VHGlocalactive]; ? A = 0 -> VHG local render done;",
        ),
        lines(
            b'"VHG local render"',
            b"\t[VHGlocalbasisfill] = 0; [VHGlocalframevalid] = 0; [VHGlocalterminalvalid] = 0;",
            b"\tA = [VHGlocalactive]; ? A = 0 -> VHG local render done;",
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
            b"\t[VHGlocalframeepoch] = [VHGNDsecs]; [VHGlocalframevalid] = 1;",
            b"\tA = [nsnob]; ? A <= 0 -> VHG local cache disabled; ? A > 80 -> VHG local cache disabled;",
            b"\tA = [VHGlocalbasisvalid]; ? A = 0 -> VHG local fill basis;",
            b"\tA = [VHGlocalframeepoch]; ? A = [VHGlocalbasisepoch] -> VHG local cache ready;",
            b"\t[VHGlocalbasisvalid] = 0;",
            b'    "VHG local fill basis"',
            b"\t[VHGlocalbasisfill] = 1; -> VHG local cache ready;",
            b'    "VHG local cache disabled"',
            b"\t[VHGlocalbasisvalid] = 0; [VHGlocalbasisfill] = 0; [VHGlocalframevalid] = 0;",
            b'    "VHG local cache ready"',
            b"\tA = [VHGlocalbasisvalid]; [VHGlocalterminalvalid] = A;",
            b"\t=> VHG local resident scan;",
            b"\t( The primary star is -planet_xyz-ship. )",
        ),
    )
    replace_once(
        b"\t[VHGNDvecindex] = [VHGlocalbody]; => VHGND absolute body vector;",
        b"\t[VHGlocalterminalvalid] = 0; [VHGNDvecindex] = [VHGlocalbody]; => VHGND absolute body vector;",
    )
    replace_once(
        lines(
            b"\t[VHGlocalbody] = 0;",
            b'    "VHG local body loop"',
        ),
        lines(
            b"\tA = [nsnob]; ? A <= 1 -> VHG local body terminal ready;",
            b"\tA = [VHGlocalframevalid]; [VHGlocalterminalvalid] = A;",
            b'    "VHG local body terminal ready"',
            b"\t[VHGlocalbody] = 0;",
            b'    "VHG local body loop"',
        ),
    )
    replace_once(
        lines(
            b"\t[VHGNDvecindex] = A; => VHGND absolute body vector;",
            b"\t=> VHG local body relative;",
            b"\tA = [VHGlocalbody]; A < 1; E = nspray; E + A;",
        ),
        lines(
            b"\t=> VHG local frame body geometry;",
            b"\tA = [VHGlocalbody]; A < 1; E = nspray; E + A;",
        ),
    )
    replace_once(
        b"\t[VHGlocalringbody] = [VHGlocalbody]; => VHG local body distance;",
        b"\t[VHGlocalringbody] = [VHGlocalbody]; => VHG local frame body distance;",
    )
    replace_once(
        lines(
            b'"VHG local render done"',
            b"\tend;",
        ),
        lines(
            b'"VHG local render done"',
            b"\tA = [VHGlocalterminalvalid]; ? A = 0 -> VHG local terminal down y ready;",
            b"\tA = [nsnob]; ? A <= 0 -> VHG local terminal down y ready;",
            b"\t? A = 1 -> VHG local terminal only body; A - 1; C = [VHGplanet];",
            b"\t? A != C -> VHG local terminal body ready; A - 1; -> VHG local terminal body ready;",
            b'    "VHG local terminal only body"',
            b"\tA = 0;",
            b'    "VHG local terminal body ready"',
            b"\tA < 6; E = VHGlocalbodycache; E + A;",
            b"\t[VHGNDowny0] = [E plus 8]; [VHGNDowny1] = [E plus 9];",
            b'    "VHG local terminal down y ready"',
            b"\tend;",
        ),
    )
    replace_once(
        lines(
            b"\t[VHGNDvecindex] = A; => VHGND absolute body vector; => VHG local body relative;",
            b"\t=> VHG local body distance;",
            b"\tA = [VHGlocalresident1]; ? A != 0FFFFFFFFh -> VHG local resident compare first;",
        ),
        lines(
            b"\t=> VHG local resident body geometry;",
            b"\tA = [VHGlocalresident1]; ? A != 0FFFFFFFFh -> VHG local resident compare first;",
        ),
    )
    replace_once(
        lines(
            b'    "VHG local resident pair ready"',
            b"\tA = [VHGlocalresident1]; ? A = 0FFFFFFFFh -> VHG local resident scan done;",
        ),
        lines(
            b'    "VHG local resident pair ready"',
            b"\tA = [VHGlocalframevalid]; ? A = 0 -> VHG local frame published;",
            b"\tA = [VHGNDsecs]; ? A = [VHGlocalframeepoch] -> VHG local frame epoch ready;",
            b"\t[VHGlocalbasisvalid] = 0; [VHGlocalbasisfill] = 0; [VHGlocalframevalid] = 0;",
            b"\t[VHGlocalterminalvalid] = 0; -> VHG local frame published;",
            b'    "VHG local frame epoch ready"',
            b"\tA = [VHGlocalbasisfill]; ? A = 0 -> VHG local frame published;",
            b"\t[VHGlocalbasisepoch] = [VHGlocalframeepoch]; [VHGlocalbasisvalid] = 1;",
            b"\t[VHGlocalbasisfill] = 0;",
            b'    "VHG local frame published"',
            b"\tA = [VHGlocalresident1]; ? A = 0FFFFFFFFh -> VHG local resident scan done;",
        ),
    )
    replace_once(
        lines(
            b"\t[VHGNDvecindex] = A; => VHGND absolute body vector; => VHG local body relative;",
            b"\t=> VHG local body distance;",
            b"\tA = [VHGlocalresident2]; ? A != 0FFFFFFFFh -> VHG local resident primary compare;",
        ),
        lines(
            b"\t=> VHG local primary body distance;",
            b"\tA = [VHGlocalresident2]; ? A != 0FFFFFFFFh -> VHG local resident primary compare;",
        ),
    )
    replace_once(
        lines(
            b'"VHG local body relative"',
            b"\t( Current VHGND vector is body-from-star.  Convert it into",
        ),
        lines(
            b'"VHG local resident body geometry"',
            b"\tA = [VHGlocalframevalid]; ? A = 0 -> VHG local resident live geometry;",
            b"\tA = [VHGNDsecs]; ? A != [VHGlocalframeepoch] -> VHG local resident cache stale;",
            b"\tA = [VHGlocalbasisfill]; ? A != 0 -> VHG local resident fill geometry;",
            b"\tA = [VHGlocalbody]; A < 6; E = VHGlocalbodycache; E + A;",
            b"\t[VHGNDvecx0] = [E plus 0]; [VHGNDvecx1] = [E plus 1];",
            b"\t[VHGNDvecy0] = [E plus 2]; [VHGNDvecy1] = [E plus 3];",
            b"\t[VHGNDvecz0] = [E plus 4]; [VHGNDvecz1] = [E plus 5];",
            b"\t=> VHG local cached basis relative; => VHG local body distance;",
            b"\t-> VHG local resident cache frame;",
            b'    "VHG local resident fill geometry"',
            b"\t[VHGNDvecindex] = [VHGlocalbody]; => VHGND absolute body vector;",
            b"\tA = [VHGlocalbody]; A < 6; E = VHGlocalbodycache; E + A;",
            b"\t[E plus 6] = [VHGNDvecx0]; [E plus 7] = [VHGNDvecx1];",
            b"\t[E plus 8] = [VHGNDvecy0]; [E plus 9] = [VHGNDvecy1];",
            b"\t[E plus 10] = [VHGNDvecz0]; [E plus 11] = [VHGNDvecz1];",
            b"\t[E plus 20] = [VHGNDvecindex]; [E plus 21] = [VHGNDvecowner];",
            b"\t[E plus 22] = [VHGNDmass0]; [E plus 23] = [VHGNDmass1];",
            b"\t[E plus 24] = [VHGNDorbit0]; [E plus 25] = [VHGNDorbit1];",
            b"\t[E plus 26] = [VHGNDangle0]; [E plus 27] = [VHGNDangle1];",
            b"\t[E plus 28] = [VHGNDsin0]; [E plus 29] = [VHGNDsin1];",
            b"\t[E plus 30] = [VHGNDcos0]; [E plus 31] = [VHGNDcos1];",
            b"\t[E plus 32] = [VHGNDct0]; [E plus 33] = [VHGNDct1];",
            b"\t[E plus 34] = [VHGNDxx0]; [E plus 35] = [VHGNDxx1];",
            b"\t[E plus 36] = [VHGNDzz0]; [E plus 37] = [VHGNDzz1];",
            b"\t[E plus 38] = [VHGNDso0]; [E plus 39] = [VHGNDso1];",
            b"\t[E plus 40] = [VHGNDco0]; [E plus 41] = [VHGNDco1];",
            b"\t=> VHG local selected basis relative;",
            b"\t[E plus 0] = [VHGNDvecx0]; [E plus 1] = [VHGNDvecx1];",
            b"\t[E plus 2] = [VHGNDvecy0]; [E plus 3] = [VHGNDvecy1];",
            b"\t[E plus 4] = [VHGNDvecz0]; [E plus 5] = [VHGNDvecz1];",
            b"\t-> VHG local resident distance;",
            b'    "VHG local resident cache stale"',
            b"\t[VHGlocalbasisvalid] = 0; [VHGlocalbasisfill] = 0; [VHGlocalframevalid] = 0;",
            b"\t[VHGlocalterminalvalid] = 0;",
            b'    "VHG local resident live geometry"',
            b"\t[VHGNDvecindex] = [VHGlocalbody]; => VHGND absolute body vector;",
            b"\t=> VHG local body relative;",
            b'    "VHG local resident distance"',
            b"\t=> VHG local body distance;",
            b"\tA = [VHGlocalframevalid]; ? A = 0 -> VHG local resident geometry done;",
            b'    "VHG local resident cache frame"',
            b"\tA = [VHGlocalbody]; A < 6; E = VHGlocalbodycache; E + A;",
            b"\t[E plus 12] = [VHGlocalringcx0]; [E plus 13] = [VHGlocalringcx1];",
            b"\t[E plus 14] = [VHGlocalringcy0]; [E plus 15] = [VHGlocalringcy1];",
            b"\t[E plus 16] = [VHGlocalringcz0]; [E plus 17] = [VHGlocalringcz1];",
            b"\t[E plus 18] = [VHGlocaldist0]; [E plus 19] = [VHGlocaldist1];",
            b"\t=> VHG local replay absolute scratch;",
            b'    "VHG local resident geometry done"',
            b"\tend;",
            b"",
            b'"VHG local primary body distance"',
            b"\tA = [VHGlocalframevalid]; ? A = 0 -> VHG local primary live geometry;",
            b"\tA = [VHGNDsecs]; ? A != [VHGlocalframeepoch] -> VHG local primary cache stale;",
            b"\tA = [VHGlocalbody]; A < 6; E = VHGlocalbodycache; E + A;",
            b"\t=> VHG local replay frame geometry; => VHG local replay body distance; end;",
            b'    "VHG local primary cache stale"',
            b"\t[VHGlocalbasisvalid] = 0; [VHGlocalbasisfill] = 0; [VHGlocalframevalid] = 0;",
            b"\t[VHGlocalterminalvalid] = 0;",
            b'    "VHG local primary live geometry"',
            b"\t[VHGlocalterminalvalid] = 0; [VHGNDvecindex] = [VHGlocalbody];",
            b"\t=> VHGND absolute body vector; => VHG local body relative; => VHG local body distance; end;",
            b"",
            b'"VHG local frame body geometry"',
            b"\tA = [VHGlocalframevalid]; ? A = 0 -> VHG local frame body live geometry;",
            b"\tA = [VHGNDsecs]; ? A != [VHGlocalframeepoch] -> VHG local frame body cache stale;",
            b"\tA = [VHGlocalbody]; A < 6; E = VHGlocalbodycache; E + A;",
            b"\t=> VHG local replay frame geometry; end;",
            b'    "VHG local frame body cache stale"',
            b"\t[VHGlocalbasisvalid] = 0; [VHGlocalbasisfill] = 0; [VHGlocalframevalid] = 0;",
            b"\t[VHGlocalterminalvalid] = 0;",
            b'    "VHG local frame body live geometry"',
            b"\t[VHGlocalterminalvalid] = 0; [VHGNDvecindex] = [VHGlocalbody];",
            b"\t=> VHGND absolute body vector; => VHG local body relative; end;",
            b"",
            b'"VHG local frame body distance"',
            b"\tA = [VHGlocalframevalid]; ? A = 0 -> VHG local frame body live distance;",
            b"\tA = [VHGNDsecs]; ? A != [VHGlocalframeepoch] -> VHG local frame distance stale;",
            b"\tA = [VHGlocalbody]; A < 6; E = VHGlocalbodycache; E + A;",
            b"\t=> VHG local replay body distance; end;",
            b'    "VHG local frame distance stale"',
            b"\t[VHGlocalbasisvalid] = 0; [VHGlocalbasisfill] = 0; [VHGlocalframevalid] = 0;",
            b"\t-> VHG local frame body live distance;",
            b'    "VHG local frame body live distance"',
            b"\t=> VHG local body distance; end;",
            b"",
            b'"VHG local replay frame geometry"',
            b"\t[VHGlocalringcx0] = [E plus 12]; [VHGlocalringcx1] = [E plus 13];",
            b"\t[VHGlocalringcy0] = [E plus 14]; [VHGlocalringcy1] = [E plus 15];",
            b"\t[VHGlocalringcz0] = [E plus 16]; [VHGlocalringcz1] = [E plus 17];",
            b"\t=> VHG local replay absolute scratch;",
            b"\t[FA0] = [VHGlocalringcx0]; [FA1] = [VHGlocalringcx1]; [PGFi] = SFXX; => PGF sa;",
            b"\t[FA0] = [VHGlocalringcy0]; [FA1] = [VHGlocalringcy1]; [PGFi] = SFYY; => PGF sa;",
            b"\t[FA0] = [VHGlocalringcz0]; [FA1] = [VHGlocalringcz1];",
            b"\t[FB0] = [VHGlocalz0]; [FB1] = [VHGlocalz1]; [PGFi] = SFZZ; => PGF sa; end;",
            b"",
            b'"VHG local replay body distance"',
            b"\t[PGFi] = SFXX; => PGF a; [PGFi] = SFXX; => PGF mul; [PGFi] = FSW0; => PGF sa;",
            b"\t[VHGlocaldist0] = [E plus 18]; [VHGlocaldist1] = [E plus 19];",
            b"\t[FA0] = [VHGlocaldist0]; [FA1] = [VHGlocaldist1];",
            b"\t[FB0] = [VHGlocalz0]; [FB1] = [VHGlocalz1]; end;",
            b"",
            b'"VHG local replay absolute scratch"',
            b"\t[VHGNDvecx0] = [E plus 6]; [VHGNDvecx1] = [E plus 7];",
            b"\t[VHGNDownx0] = [E plus 6]; [VHGNDownx1] = [E plus 7];",
            b"\t[VHGNDvecy0] = [E plus 8]; [VHGNDvecy1] = [E plus 9];",
            b"\t[VHGNDowny0] = [E plus 8]; [VHGNDowny1] = [E plus 9];",
            b"\t[VHGNDvecz0] = [E plus 10]; [VHGNDvecz1] = [E plus 11];",
            b"\t[VHGNDownz0] = [E plus 10]; [VHGNDownz1] = [E plus 11];",
            b"\t[VHGNDvecindex] = [E plus 20]; [VHGNDvecowner] = [E plus 21];",
            b"\t[VHGNDmass0] = [E plus 22]; [VHGNDmass1] = [E plus 23];",
            b"\t[VHGNDorbit0] = [E plus 24]; [VHGNDorbit1] = [E plus 25];",
            b"\t[VHGNDangle0] = [E plus 26]; [VHGNDangle1] = [E plus 27];",
            b"\t[VHGNDsin0] = [E plus 28]; [VHGNDsin1] = [E plus 29];",
            b"\t[VHGNDcos0] = [E plus 30]; [VHGNDcos1] = [E plus 31];",
            b"\t[VHGNDct0] = [E plus 32]; [VHGNDct1] = [E plus 33];",
            b"\t[VHGNDxx0] = [E plus 34]; [VHGNDxx1] = [E plus 35];",
            b"\t[VHGNDzz0] = [E plus 36]; [VHGNDzz1] = [E plus 37];",
            b"\t[VHGNDso0] = [E plus 38]; [VHGNDso1] = [E plus 39];",
            b"\t[VHGNDco0] = [E plus 40]; [VHGNDco1] = [E plus 41];",
            b"\tA = [VHGNDvecowner]; ? A >= 0 -> VHG local absolute scratch ready;",
            b"\t[FS0] = [nsstarray];",
            b'    "VHG local absolute scratch ready"',
            b"\tend;",
            b"",
            b'"VHG local selected basis relative"',
            b"\t[FA0] = [VHGNDvecx0]; [FA1] = [VHGNDvecx1];",
            b"\t[FB0] = [VHGlocaltx0]; [FB1] = [VHGlocaltx1]; => FSub;",
            b"\t[VHGNDvecx0] = [FA0]; [VHGNDvecx1] = [FA1];",
            b"\t[FB0] = [VHGlocalx0]; [FB1] = [VHGlocalx1]; => FSub;",
            b"\t[VHGlocalringcx0] = [FA0]; [VHGlocalringcx1] = [FA1]; [PGFi] = SFXX; => PGF sa;",
            b"\t[FA0] = [VHGNDvecy0]; [FA1] = [VHGNDvecy1];",
            b"\t[FB0] = [VHGlocalty0]; [FB1] = [VHGlocalty1]; => FSub;",
            b"\t[VHGNDvecy0] = [FA0]; [VHGNDvecy1] = [FA1];",
            b"\t[FB0] = [VHGlocaly0]; [FB1] = [VHGlocaly1]; => FSub;",
            b"\t[VHGlocalringcy0] = [FA0]; [VHGlocalringcy1] = [FA1]; [PGFi] = SFYY; => PGF sa;",
            b"\t[FA0] = [VHGNDvecz0]; [FA1] = [VHGNDvecz1];",
            b"\t[FB0] = [VHGlocaltz0]; [FB1] = [VHGlocaltz1]; => FSub;",
            b"\t[VHGNDvecz0] = [FA0]; [VHGNDvecz1] = [FA1];",
            b"\t[FB0] = [VHGlocalz0]; [FB1] = [VHGlocalz1]; => FSub;",
            b"\t[VHGlocalringcz0] = [FA0]; [VHGlocalringcz1] = [FA1]; [PGFi] = SFZZ; => PGF sa; end;",
            b"",
            b'"VHG local cached basis relative"',
            b"\t[FA0] = [VHGNDvecx0]; [FA1] = [VHGNDvecx1];",
            b"\t[FB0] = [VHGlocalx0]; [FB1] = [VHGlocalx1]; => FSub;",
            b"\t[VHGlocalringcx0] = [FA0]; [VHGlocalringcx1] = [FA1]; [PGFi] = SFXX; => PGF sa;",
            b"\t[FA0] = [VHGNDvecy0]; [FA1] = [VHGNDvecy1];",
            b"\t[FB0] = [VHGlocaly0]; [FB1] = [VHGlocaly1]; => FSub;",
            b"\t[VHGlocalringcy0] = [FA0]; [VHGlocalringcy1] = [FA1]; [PGFi] = SFYY; => PGF sa;",
            b"\t[FA0] = [VHGNDvecz0]; [FA1] = [VHGNDvecz1];",
            b"\t[FB0] = [VHGlocalz0]; [FB1] = [VHGlocalz1]; => FSub;",
            b"\t[VHGlocalringcz0] = [FA0]; [VHGlocalringcz1] = [FA1]; [PGFi] = SFZZ; => PGF sa; end;",
            b"",
            b'"VHG local body relative"',
            b"\t( Current VHGND vector is body-from-star.  Convert it into",
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
