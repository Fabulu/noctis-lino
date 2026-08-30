from pathlib import Path
import argparse
import hashlib

ROOT = Path("C:/programmieren/linoleum")
EVIDENCE = ROOT / "build/native-fquo-lowering-20260830"
FILES = {
    "fpsoft.txt": ROOT / "work/fp/fpsoft.txt",
    "vhgame.exe": ROOT / "work/vhgame.exe",
    "compiler114m.txt": ROOT / "main/lib/gen/compiler114m.txt",
    "compiler114m.exe": ROOT / "main/lib/gen/compiler114m.exe",
}
EXPECTED = {
    "accepted": {
        "fpsoft.txt": "95417cf412787e6f33c773f4f7eb4d5d685f44fceff6b6e21649024b4d8d62dc",
        "vhgame.exe": "70c7fc0a3f97270768eb86ea3ad30d18ffb2811fe07f821aff8ade7d2f2063d4",
        "compiler114m.txt": "c3a185ed4539eff86ea639943e3ea103b9b3065a895ae97bd93de9ff7efb93a0",
        "compiler114m.exe": "facfb8b9373c548c569771978606fcd5d5273760ec7b1e2f0b4ee6bcc30d2e78",
    },
    "candidate": {
        "fpsoft.txt": "6681e59e64835fc25ec87ec18387e4c448208cef7fd03040768ebb5c613c7c37",
        "vhgame.exe": "fcb0b008c7d05e383a7759ec6978c7189aae669811c9b4348a511e31c93c5340",
        "compiler114m.txt": "1d424fd70b0aeccf689acbc527419c566895c3e591eb3646b1db6e438f15d4c2",
        "compiler114m.exe": "07621242048e1e49ee01db07f614a6cd0f37a87aef3235139ed17f5b8e666e27",
    },
}


def digest(data):
    return hashlib.sha256(data).hexdigest()


parser = argparse.ArgumentParser()
parser.add_argument("selection", choices=("accepted", "candidate"))
args = parser.parse_args()

current = {name: path.read_bytes() for name, path in FILES.items()}
for name, data in current.items():
    assert digest(data) in {
        EXPECTED["accepted"][name], EXPECTED["candidate"][name]
    }, (name, digest(data))

target = {}
for name in FILES:
    source = EVIDENCE / args.selection / name
    data = source.read_bytes()
    assert digest(data) == EXPECTED[args.selection][name], name
    target[name] = data

try:
    for name, path in FILES.items():
        path.write_bytes(target[name])
    for name, path in FILES.items():
        assert digest(path.read_bytes()) == EXPECTED[args.selection][name], name
except BaseException:
    for name, path in FILES.items():
        path.write_bytes(current[name])
    raise

print(args.selection)
for name, value in EXPECTED[args.selection].items():
    print(name, value)
