from pathlib import Path
import hashlib

ROOT = Path("C:/programmieren/linoleum")
EVIDENCE = ROOT / "build/live-space-render-attribution-20260829"
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
        b"\tVHGprofpart = 0; VHGprofspace = 0; VHGprofcupola = 0; VHGprofhull = 0; VHGprofdetail = 0;",
        lines(
            b"\tVHGprofpart = 0; VHGprofspace = 0; VHGprofcupola = 0; VHGprofhull = 0; VHGprofdetail = 0;",
            b"\tVHGprofauxstart = 0; VHGprofaux0 = 0; VHGprofaux1 = 0; VHGprofaux2 = 0;",
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
            b"\tA = [VHGlocalactive]; ? A = 0 -> VHG local render inactive;",
            b"\t( Attribution phase 0: selected origin, resident scan, stars, coronas, and mask. )",
            b"\t[Timer Command] = READ COUNTS; isocall; [VHGprofauxstart] = [Counts];",
            b"\t=> VHG fpu clean;",
            b"\t( planet_xyz(selected) places the approached world in the generated",
        ),
    )
    replace_once(
        lines(
            b'    "VHG local planet render"',
            b"\t( planets() traverses every generated body.  The selected body retains",
        ),
        lines(
            b'    "VHG local planet render"',
            b"\t[Timer Command] = READ COUNTS; isocall; A = [Counts]; A - [VHGprofauxstart];",
            b"\tA + [VHGprofaux0]; [VHGprofaux0] = A; [VHGprofauxstart] = [Counts];",
            b"\t=> VHG fpu clean;",
            b"\t( Attribution phase 1: every non-selected generated body. )",
            b"\t( planets() traverses every generated body.  The selected body retains",
        ),
    )
    replace_once(
        lines(
            b'    "VHG local selected render"',
            b"\t=> VHG local center coords;",
        ),
        lines(
            b'    "VHG local selected render"',
            b"\t[Timer Command] = READ COUNTS; isocall; A = [Counts]; A - [VHGprofauxstart];",
            b"\tA + [VHGprofaux1]; [VHGprofaux1] = A; [VHGprofauxstart] = [Counts];",
            b"\t=> VHG fpu clean;",
            b"\t( Attribution phase 2: the selected body and its rings or surface. )",
            b"\t=> VHG local center coords;",
        ),
    )
    replace_once(
        lines(
            b"\t=> VHG local center coords; => VHG local far pixel;",
            b'"VHG local render done"',
            b"\tend;",
        ),
        lines(
            b"\t=> VHG local center coords; => VHG local far pixel;",
            b'"VHG local render done"',
            b"\t[Timer Command] = READ COUNTS; isocall; A = [Counts]; A - [VHGprofauxstart];",
            b"\tA + [VHGprofaux2]; [VHGprofaux2] = A;",
            b"\t=> VHG fpu clean;",
            b'"VHG local render inactive"',
            b"\tend;",
        ),
    )
    replace_once(
        lines(
            b'    "VHG close star rendered"',
            b"\t=> VHG local render;",
            b"\tA = [VHGdosim]; ? A = 0 -> VHG star palette frame done; => VHG star palette update;",
        ),
        lines(
            b'    "VHG close star rendered"',
            b"\t( Attribution-only counter: isolate the exact local-system renderer. )",
            b"\t[Timer Command] = READ COUNTS; isocall; [VHGprofpart] = [Counts];",
            b"\t=> VHG fpu clean;",
            b"\t=> VHG local render;",
            b"\t[Timer Command] = READ COUNTS; isocall; A = [Counts]; A - [VHGprofpart];",
            b"\tA + [VHGprofspace]; [VHGprofspace] = A;",
            b"\t=> VHG fpu clean;",
            b"\tA = [VHGdosim]; ? A = 0 -> VHG star palette frame done; => VHG star palette update;",
        ),
    )
    replace_once(
        lines(
            b"\t=> VHG rescue render;",
            b"\t[Timer Command] = READ COUNTS; isocall; A = [Counts]; A - [VHGprofpart];",
            b"\tA + [VHGprofspace]; [VHGprofspace] = A;",
            b"\t[Timer Command] = READ COUNTS; isocall; [VHGprofpart] = [Counts];",
        ),
        lines(
            b"\t=> VHG rescue render;",
            b"\t( VHGprofspace already contains only local render; begin the cupola counter here. )",
            b"\t[Timer Command] = READ COUNTS; isocall; [VHGprofpart] = [Counts];",
        ),
    )
    replace_once(
        b"\t[VHGprofcupola] = 0; [VHGprofhull] = 0; [VHGprofdetail] = 0;",
        lines(
            b"\t[VHGprofcupola] = 0; [VHGprofhull] = 0; [VHGprofdetail] = 0;",
            b"\t[VHGprofauxstart] = 0; [VHGprofaux0] = 0; [VHGprofaux1] = 0; [VHGprofaux2] = 0;",
        ),
    )
    replace_once(
        lines(
            b"\t[vhgprofile plus 9] = [VHGprofspace]; [vhgprofile plus 10] = [VHGprofcupola];",
            b"\t[vhgprofile plus 11] = [VHGprofhull]; [vhgprofile plus 12] = [VHGprofdetail];",
        ),
        lines(
            b"\t( Attribution profile: space=local total, cupola=star/setup, hull=other bodies, detail=selected body. )",
            b"\t[vhgprofile plus 9] = [VHGprofspace]; [vhgprofile plus 10] = [VHGprofaux0];",
            b"\t[vhgprofile plus 11] = [VHGprofaux1]; [vhgprofile plus 12] = [VHGprofaux2];",
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
    print(f"subphase_instrumented_source_sha256={digest(SOURCE)}")
