from pathlib import Path
import hashlib

ROOT = Path("C:/programmieren/linoleum")
EVIDENCE = ROOT / "build/live-space-render-attribution-20260829"
SOURCE = ROOT / "work/vhgame.txt"
ACCEPTED = EVIDENCE / "accepted/vhgame.txt"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


data = SOURCE.read_bytes()
assert digest(SOURCE) == digest(ACCEPTED)
nl = b"\r\n" if b"\r\n" in data else b"\n"
old_call = nl.join((
    b'    "VHG close star rendered"',
    b"\t=> VHG local render;",
    b"\tA = [VHGdosim]; ? A = 0 -> VHG star palette frame done; => VHG star palette update;",
))
new_call = nl.join((
    b'    "VHG close star rendered"',
    b"\t( Attribution-only counter: isolate the exact local-system renderer. )",
    b"\t[Timer Command] = READ COUNTS; isocall; [VHGprofpart] = [Counts];",
    b"\t=> VHG fpu clean;",
    b"\t=> VHG local render;",
    b"\t[Timer Command] = READ COUNTS; isocall; A = [Counts]; A - [VHGprofpart];",
    b"\tA + [VHGprofspace]; [VHGprofspace] = A;",
    b"\t=> VHG fpu clean;",
    b"\tA = [VHGdosim]; ? A = 0 -> VHG star palette frame done; => VHG star palette update;",
))
old_total = nl.join((
    b"\t=> VHG rescue render;",
    b"\t[Timer Command] = READ COUNTS; isocall; A = [Counts]; A - [VHGprofpart];",
    b"\tA + [VHGprofspace]; [VHGprofspace] = A;",
    b"\t[Timer Command] = READ COUNTS; isocall; [VHGprofpart] = [Counts];",
))
new_total = nl.join((
    b"\t=> VHG rescue render;",
    b"\t( VHGprofspace already contains only local render; begin the cupola counter here. )",
    b"\t[Timer Command] = READ COUNTS; isocall; [VHGprofpart] = [Counts];",
))
assert data.count(old_call) == 1
assert data.count(old_total) == 1
candidate = data.replace(old_call, new_call, 1).replace(old_total, new_total, 1)
assert candidate != data
SOURCE.write_bytes(candidate)
print(f"accepted_source_sha256={digest(ACCEPTED)}")
print(f"local_instrumented_source_sha256={digest(SOURCE)}")
