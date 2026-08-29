from pathlib import Path
import hashlib

ROOT = Path("C:/programmieren/linoleum")
EVIDENCE = ROOT / "build/deferred-orbital-terminal-replay-20260829"
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
            b"\tVHGlocalveccacheepoch = 0; VHGlocalveccachevalid = 0; VHGlocalveccachefill = 0;",
            b"\tVHGlocalveccachepending = 0FFFFFFFFh;",
        ),
    )
    replace_once(
        b"\tVHGwideoutput = 183200;",
        lines(
            b"\tVHGwideoutput = 183200;",
            b"\t( 80 exact absolute body vectors and terminal down-y pairs. )",
            b"\tVHGlocalvectorcache = 640;",
        ),
    )
    replace_once(
        b"\t[VHGlocalactive] = 0; [VHGlocaltarget] = 0FFFFFFFFh; [VHGlandpending] = 0;",
        lines(
            b"\t[VHGlocalactive] = 0; [VHGlocaltarget] = 0FFFFFFFFh; [VHGlandpending] = 0;",
            b"\t[VHGlocalveccachevalid] = 0; [VHGlocalveccachefill] = 0; [VHGlocalveccachepending] = 0FFFFFFFFh;",
        ),
    )
    replace_once(
        b"\t[VHGlocalactive] = 1; [VHGlocaltarget] = [VHGplanet]; [VHGlocalacc] = 0;",
        lines(
            b"\t[VHGlocalactive] = 1; [VHGlocaltarget] = [VHGplanet]; [VHGlocalacc] = 0;",
            b"\t[VHGlocalveccachevalid] = 0; [VHGlocalveccachefill] = 0; [VHGlocalveccachepending] = 0FFFFFFFFh;",
        ),
    )
    replace_once(
        b'"VHG restore local checkpoint"',
        lines(
            b'"VHG restore local checkpoint"',
            b"\t[VHGlocalveccachevalid] = 0; [VHGlocalveccachefill] = 0; [VHGlocalveccachepending] = 0FFFFFFFFh;",
        ),
    )
    replace_once(
        lines(
            b'"VHG local render"',
            b"\tA = [VHGlocalactive]; ? A = 0 -> VHG local render done;",
            b"\t( planet_xyz(selected) places the approached world in the generated",
        ),
        lines(
            b'"VHG local render"',
            b"\t[VHGlocalveccachepending] = 0FFFFFFFFh;",
            b"\tA = [VHGlocalactive]; ? A = 0 -> VHG local render done;",
            b"\t[VHGlocalveccachefill] = 0; A = [VHGlocalveccachevalid];",
            b"\t? A = 0 -> VHG local vector cache fill; A = [VHGNDsecs];",
            b"\t? A = [VHGlocalveccacheepoch] -> VHG local vector cache ready;",
            b"\t[VHGlocalveccachevalid] = 0;",
            b'    "VHG local vector cache fill"',
            b"\t[VHGlocalveccachefill] = 1;",
            b'    "VHG local vector cache ready"',
            b"\t( planet_xyz(selected) places the approached world in the generated",
        ),
    )
    replace_once(
        b"\t[VHGNDvecindex] = [VHGlocalbody]; => VHGND absolute body vector;",
        b"\t[VHGlocalveccachepending] = 0FFFFFFFFh; [VHGNDvecindex] = [VHGlocalbody]; => VHGND absolute body vector;",
    )
    replace_once(
        lines(
            b'"VHG local render done"',
            b"\tend;",
        ),
        lines(
            b'"VHG local render done"',
            b"\tA = [VHGlocalveccachepending]; ? A = 0FFFFFFFFh -> VHG local terminal down y ready;",
            b"\tA < 3; E = VHGlocalvectorcache; E + A;",
            b"\t[VHGNDowny0] = [E plus 6]; [VHGNDowny1] = [E plus 7];",
            b'    "VHG local terminal down y ready"',
            b"\tend;",
        ),
    )
    replace_once(
        b"\t[VHGNDvecindex] = A; => VHGND absolute body vector;\n\t=> VHG local body relative;".replace(b"\n", nl),
        b"\t[VHGNDvecindex] = A; => VHG local absolute body vector;\n\t=> VHG local body relative;".replace(b"\n", nl),
    )
    replace_once(
        lines(
            b"\t[VHGNDvecindex] = A; => VHGND absolute body vector; => VHG local body relative;",
            b"\t=> VHG local body distance;",
            b"\tA = [VHGlocalresident1]; ? A != 0FFFFFFFFh -> VHG local resident compare first;",
        ),
        lines(
            b"\t[VHGNDvecindex] = A; => VHG local absolute body vector; => VHG local body relative;",
            b"\t=> VHG local body distance;",
            b"\tA = [VHGlocalveccachefill]; ? A = 0 -> VHG local resident vector ready;",
            b"\tA = [VHGlocalbody]; ? A < 80 -> VHG local resident vector store;",
            b"\t[VHGlocalveccachefill] = 0; [VHGlocalveccachevalid] = 0;",
            b"\t-> VHG local resident vector ready;",
            b'    "VHG local resident vector store"',
            b"\tA = [VHGlocalbody]; A < 3; E = VHGlocalvectorcache; E + A;",
            b"\t[E plus 0] = [VHGNDvecx0]; [E plus 1] = [VHGNDvecx1];",
            b"\t[E plus 2] = [VHGNDvecy0]; [E plus 3] = [VHGNDvecy1];",
            b"\t[E plus 4] = [VHGNDvecz0]; [E plus 5] = [VHGNDvecz1];",
            b"\t[E plus 6] = [VHGNDowny0]; [E plus 7] = [VHGNDowny1];",
            b'    "VHG local resident vector ready"',
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
            b"\tA = [VHGlocalveccachefill]; ? A = 0 -> VHG local vector cache published;",
            b"\t[VHGlocalveccacheepoch] = [VHGNDsecs]; [VHGlocalveccachevalid] = 1;",
            b"\t[VHGlocalveccachefill] = 0;",
            b'    "VHG local vector cache published"',
            b"\tA = [VHGlocalresident1]; ? A = 0FFFFFFFFh -> VHG local resident scan done;",
        ),
    )
    replace_once(
        b"\t[VHGNDvecindex] = A; => VHGND absolute body vector; => VHG local body relative;\n\t=> VHG local body distance;".replace(b"\n", nl),
        b"\t[VHGNDvecindex] = A; => VHG local absolute body vector; => VHG local body relative;\n\t=> VHG local body distance;".replace(b"\n", nl),
    )
    replace_once(
        lines(
            b'"VHG local body relative"',
            b"\t( Current VHGND vector is body-from-star.  Convert it into",
        ),
        lines(
            b'"VHG local absolute body vector"',
            b"\tA = [VHGlocalveccachevalid]; ? A = 0 -> VHG local absolute body vector live;",
            b"\tA = [VHGNDsecs]; ? A != [VHGlocalveccacheepoch] -> VHG local absolute body vector stale;",
            b"\tA = [VHGNDvecindex]; ? A >= 80 -> VHG local absolute body vector live;",
            b"\t[VHGlocalveccachepending] = A; A < 3; E = VHGlocalvectorcache; E + A;",
            b"\t[VHGNDvecx0] = [E plus 0]; [VHGNDvecx1] = [E plus 1];",
            b"\t[VHGNDvecy0] = [E plus 2]; [VHGNDvecy1] = [E plus 3];",
            b"\t[VHGNDvecz0] = [E plus 4]; [VHGNDvecz1] = [E plus 5]; end;",
            b'    "VHG local absolute body vector stale"',
            b"\t[VHGlocalveccachevalid] = 0;",
            b'    "VHG local absolute body vector live"',
            b"\t[VHGlocalveccachepending] = 0FFFFFFFFh; => VHGND absolute body vector; end;",
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
