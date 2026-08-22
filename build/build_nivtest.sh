#!/bin/sh
# Build the production NIVGEN harness for the macOS x86_64 SheetBot worker.
#
# The compiler/runtime container is the same one used by the contributor's
# macOS port. Override its location with NOLINO_RUNTIME, NOLINO_CTR,
# NOLINO_WS, and NOLINO_ENV when the worker uses different names.
set -eu

repo=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$repo"

: "${NOLINO_RUNTIME:=finch}"
: "${NOLINO_CTR:=lino-workspace}"
: "${NOLINO_WS:=/workspace}"
: "${NOLINO_ENV:=$NOLINO_WS/linoenv}"

output="$repo/build/nivtest"
candidate="$output.candidate"
provenance="$repo/build/nivtest-build.provenance.txt"
provenance_candidate="$provenance.candidate"
smoke="$repo/build/nivtest-smoke.json"
smoke_candidate="$smoke.candidate"
remote_root="$NOLINO_WS/nivtest-src"
remote_env="$remote_root/linoenv"
remote_source="$remote_root/work/nivtestmain.txt"
remote_output="$remote_root/work/nivtestmain.exe"

mkdir -p "$repo/build"
rm -f "$candidate" "$provenance_candidate" "$smoke_candidate"
cleanup() {
    rm -f "$candidate" "$provenance_candidate" "$smoke_candidate"
}
trap cleanup EXIT INT TERM

# Never let the worker silently reuse the historical x64 pack whose ADD cleanup
# destroyed x87 comparison flags and visibly skipped cirrus/palette branches.
python3 "$repo/tools/fix_x64_pack_flags.py" "$repo/main/cpu/x64.bin"
expected_cpu_hash=$(python3 - "$repo/main/cpu/x64.bin" <<'PY'
from pathlib import Path
import hashlib
import sys
print(hashlib.sha256(Path(sys.argv[1]).read_bytes()).hexdigest())
PY
)
python3 -c 'from tools.nivtest import derive_main; derive_main()'

# Keep the externally supplied libraries and macOS SYS read-only, but isolate the
# target CPU pack so this build always receives the audited bytes from this tree.
"$NOLINO_RUNTIME" exec "$NOLINO_CTR" sh -c '
    set -eu
    root=$1
    source_env=$2
    staged_env=$3
    if [ "$source_env" = "$staged_env" ]; then
        echo "NOLINO_ENV must not equal the isolated worker environment" >&2
        exit 2
    fi
    if [ ! -d "$source_env/lib" ] || [ ! -f "$source_env/sys/macos.bin" ]; then
        echo "NOLINO_ENV lacks lib/ or sys/macos.bin" >&2
        exit 2
    fi
    rm -rf "$root/work" "$staged_env"
    mkdir -p "$root/work/fp" "$staged_env/cpu"
    ln -s "$source_env/lib" "$staged_env/lib"
    ln -s "$source_env/sys" "$staged_env/sys"
' sh "$remote_root" "$NOLINO_ENV" "$remote_env"
"$NOLINO_RUNTIME" exec -i "$NOLINO_CTR" sh -c '
    set -eu
    cat > "$1/cpu/x64.bin"
' sh "$remote_env" < "$repo/main/cpu/x64.bin"

remote_cpu_hash=$("$NOLINO_RUNTIME" exec "$NOLINO_CTR" sh -c '
    sha256sum "$1/cpu/x64.bin" | cut -d " " -f 1
' sh "$remote_env")
if [ "$remote_cpu_hash" != "$expected_cpu_hash" ]; then
    echo "container x64 pack differs after transfer" >&2
    exit 1
fi

# Send only committed Lino source libraries, then overlay the generated main.
# This avoids copying local saves, captures, executables, and debug artifacts.
git ls-files -z -- ':(glob)work/*.txt' ':(glob)work/fp/*.txt' | \
    tar --null -T - -cf - | \
    "$NOLINO_RUNTIME" exec -i "$NOLINO_CTR" \
        sh -c 'tar -xf - -C "$1"' sh "$remote_root"
"$NOLINO_RUNTIME" exec -i "$NOLINO_CTR" \
    sh -c 'cat > "$1"' sh "$remote_source" \
    < "$repo/work/nivtestmain.txt"

remote_compiler_hash=$("$NOLINO_RUNTIME" exec "$NOLINO_CTR" sh -c '
    sha256sum "$1/lino-compiler" | cut -d " " -f 1
' sh "$NOLINO_WS")
remote_system_hash=$("$NOLINO_RUNTIME" exec "$NOLINO_CTR" sh -c '
    sha256sum "$1/sys/macos.bin" | cut -d " " -f 1
' sh "$remote_env")

"$NOLINO_RUNTIME" exec "$NOLINO_CTR" sh -c '
    set -eu
    cd "$1"
    exec ./lino-compiler "--sys:macos--cpu:x64--ext:.exe--env:$2--src:$3"
' sh "$NOLINO_WS" "$remote_env" "$remote_source"

"$NOLINO_RUNTIME" exec "$NOLINO_CTR" \
    sh -c 'cat "$1"' sh "$remote_output" > "$candidate"
chmod +x "$candidate"

python3 - "$candidate" "$repo" "$remote_compiler_hash" \
    "$remote_cpu_hash" "$remote_system_hash" "$provenance_candidate" <<'PY'
from pathlib import Path
import hashlib
import struct
import subprocess
import sys

path = Path(sys.argv[1])
repo = Path(sys.argv[2])
compiler_hash = sys.argv[3]
cpu_hash = sys.argv[4]
system_hash = sys.argv[5]
provenance = Path(sys.argv[6])
data = path.read_bytes()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(value: Path) -> str:
    return sha256_bytes(value.read_bytes())


if len(data) < 1024 or data[:4] != b"\xcf\xfa\xed\xfe":
    raise SystemExit("worker NIVTEST is not a thin little-endian 64-bit Mach-O")
if struct.unpack_from("<I", data, 4)[0] != 0x01000007:
    raise SystemExit("worker NIVTEST is not an x86_64 Mach-O")
marker = b"LNLMInit"
marker_offset = data.find(marker)
if marker_offset < 0 or data.find(marker, marker_offset + 1) >= 0:
    raise SystemExit("worker NIVTEST has an invalid initialization paragraph")
paragraph = marker_offset + len(marker) + 40
fields = struct.unpack_from("<14i", data, paragraph)
app_ws_size, app_code_size, app_code_entry = fields[:3]
physwsentry, physappsize, default_ramtop = fields[3:6]
if app_ws_size < 0 or app_code_size <= 0 or not 0 <= app_code_entry < app_code_size:
    raise SystemExit("worker NIVTEST has invalid workspace/code bounds")
if default_ramtop < app_ws_size:
    raise SystemExit("worker NIVTEST has an undersized default RAMtop")
expected_size = physwsentry + (app_ws_size + app_code_size) * 4
if physappsize != expected_size or len(data) < expected_size:
    raise SystemExit(
        f"worker NIVTEST is incomplete: header={physappsize}, "
        f"sections={expected_size}, file={len(data)}"
    )
commit = subprocess.check_output(
    ["git", "-C", str(repo), "rev-parse", "HEAD"], text=True
).strip()
records = [
    ("nivtest_worker_provenance_format", "1"),
    ("commit", commit),
    ("nivtest_source_sha256", sha256_file(repo / "work/nivtestmain.txt")),
    ("nivtest_executable_sha256", sha256_file(path)),
    ("runtime_prefix_sha256", sha256_bytes(data[:physwsentry])),
    ("compiler_sha256", compiler_hash),
    ("cpu_pack_sha256", cpu_hash),
    ("system_pack_sha256", system_hash),
    ("build_script_sha256", sha256_file(repo / "build/build_nivtest.sh")),
    ("cpu_pack_auditor_sha256", sha256_file(repo / "tools/fix_x64_pack_flags.py")),
    ("nivtest_tool_sha256", sha256_file(repo / "tools/nivtest.py")),
    ("target", "macos/x64"),
    (
        "nivtest_worker_provenance",
        "the x64 pack is copied from and audited against this checkout; the externally supplied compiler, macOS SYS, resulting runtime prefix, source, and executable are hash recorded",
    ),
]
provenance.write_text(
    "".join(f"{key}={value}\n" for key, value in records), encoding="ascii"
)
PY

# Refuse to publish a worker executable until the exact tagged Rosetta fixture
# proves all seven buffers and reaches the formerly skipped cirrus write.
python3 "$repo/tools/nivtest.py" json \
    -x -1996209872 -y 55508 -z 816148 -p 2 -lon 0 -lat 60 \
    --diagnostic --exe "$candidate" > "$smoke_candidate"
python3 - "$smoke_candidate" <<'PY'
from pathlib import Path
import json
import sys

result = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
expected = {
    "surf": "390A2CCB",
    "atmo": "114562E8",
    "pal": "26961E4A",
    "hm": "97022FD7",
    "oc": "22913F4E",
    "stex": "0D52F001",
    "sky": "1E308D29",
}
got = {name: result["hashes"][name]["fnv"] for name in expected}
if got != expected:
    raise SystemExit(f"worker NIVTEST tagged fixture mismatch: {got!r}")
first_cirrus = result.get("diagnostic", {}).get("first_cirrus", {})
if not first_cirrus.get("reached"):
    raise SystemExit("worker NIVTEST did not reach the first cirrus write")
print("worker NIVTEST tagged Rosetta fixture passed all seven hashes")
PY

mv "$candidate" "$output"
mv "$provenance_candidate" "$provenance"
mv "$smoke_candidate" "$smoke"
trap - EXIT INT TERM
printf '%s\n' "built $output with audited x64 pack $expected_cpu_hash"
printf '%s\n' "wrote $provenance and $smoke"
