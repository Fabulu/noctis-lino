#!/bin/sh
# Cross-compile the production NIVGEN harness with the repository's Linux
# compiler and a supplied macOS x86_64 RTM. The compiler owns an X11 window and
# remains resident after writing, so CI runs it under Xvfb and accepts only a
# settled non-empty output.
set -eu

repo=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
rtm=${1:-"$repo/build/macos-rtm01.bin"}
output=${2:-"$repo/build/nivtest"}
runtime_provenance=${3:-"$(dirname "$rtm")/headless-runtime.provenance.txt"}
provenance=${4:-"$repo/build/nivtest-build.provenance.txt"}
source="$repo/work/nivtestmain.txt"
compiled="$repo/work/nivtestmain.exe"
log="$repo/work/errorlog.txt"
compiler="$repo/build/linux-compiler114m.bin"
compiler_log="$repo/build/nivtest-compiler.log"
compiler_group_file="$repo/build/nivtest-compiler.pgid"

if [ ! -f "$rtm" ] || [ ! -f "$runtime_provenance" ]; then
    echo "a headless RTM and its macOS-host provenance are required" >&2
    exit 2
fi
runtime_commit=${GITHUB_SHA:-$(git -C "$repo" rev-parse HEAD)}
python3 "$repo/tools/macos_runtime_provenance.py" verify \
    --runtime "$rtm" --provenance "$runtime_provenance" \
    --mode headless --commit "$runtime_commit"

python3 "$repo/tools/fix_x64_pack_flags.py" "$repo/main/cpu/x64.bin"
python3 "$repo/tools/pack_lino_sys.py" "$rtm" "$repo/main/sys/macos.bin"
python3 -c 'from tools.nivtest import derive_main; derive_main()'
"$repo/build/build_compiler114m_linux.sh" "$compiler"
rm -f "$compiled" "$log" "$compiler_log" "$compiler_group_file"

setsid sh -c '
    group_file=$1
    shift
    printf "%s\n" "$$" >"$group_file"
    exec "$@"
' sh "$compiler_group_file" xvfb-run -a setarch "$(uname -m)" -X "$compiler" \
    "--sys:macos--cpu:x64--ext:.exe--env:$repo/main--src:$source" \
    >"$compiler_log" 2>&1 &
compiler_supervisor=$!
count=0
while [ ! -s "$compiler_group_file" ] && [ "$count" -lt 100 ]; do
    count=$((count + 1))
    sleep 0.025
done
if [ ! -s "$compiler_group_file" ]; then
    /bin/kill -TERM "$compiler_supervisor" 2>/dev/null || true
    wait "$compiler_supervisor" 2>/dev/null || true
    cat "$compiler_log" >&2 || true
    echo "NIVTEST compiler process group did not start" >&2
    exit 1
fi
read -r compiler_group <"$compiler_group_file"
case $compiler_group in
    ''|*[!0-9]*)
        /bin/kill -TERM "$compiler_supervisor" 2>/dev/null || true
        wait "$compiler_supervisor" 2>/dev/null || true
        echo "NIVTEST compiler reported an invalid process group" >&2
        exit 1
        ;;
esac
cleanup() {
    /bin/kill -TERM -- "-$compiler_group" 2>/dev/null || true
    count=0
    while /bin/kill -0 -- "-$compiler_group" 2>/dev/null && \
        [ "$count" -lt 20 ]; do
        count=$((count + 1))
        sleep 0.05
    done
    /bin/kill -KILL -- "-$compiler_group" 2>/dev/null || true
    wait "$compiler_supervisor" 2>/dev/null || true
    rm -f "$compiler_group_file"
}
trap cleanup EXIT
trap 'cleanup; exit 130' INT
trap 'cleanup; exit 143' TERM

stable=0
previous=
attempt=0
while [ "$attempt" -lt 600 ]; do
    attempt=$((attempt + 1))
    if [ -f "$log" ] && grep -Eqi 'error:|internal problem:' "$log"; then
        cat "$log" >&2
        exit 1
    fi
    if [ -s "$compiled" ]; then
        current=$(sha256sum "$compiled" | cut -d ' ' -f 1)
        if [ "$current" = "$previous" ]; then
            stable=$((stable + 1))
        else
            stable=1
            previous=$current
        fi
        if [ "$stable" -ge 8 ]; then
            break
        fi
    else
        stable=0
        previous=
    fi
    if ! /bin/kill -0 -- "-$compiler_group" 2>/dev/null && \
        [ ! -s "$compiled" ]; then
        cat "$compiler_log" >&2 || true
        [ ! -f "$log" ] || cat "$log" >&2
        exit 1
    fi
    sleep 0.25
done

if [ "$stable" -lt 8 ] || [ ! -s "$compiled" ]; then
    cat "$compiler_log" >&2 || true
    [ ! -f "$log" ] || cat "$log" >&2
    echo "macOS NIVGEN cross-compile did not settle" >&2
    exit 1
fi

cleanup
trap - EXIT INT TERM
if [ "$(sha256sum "$compiled" | cut -d ' ' -f 1)" != "$previous" ]; then
    echo "macOS NIVGEN changed while the compiler process group stopped" >&2
    exit 1
fi
mkdir -p "$(dirname "$output")"
cp "$compiled" "$output"
chmod +x "$output"
python3 - "$output" "$repo" "$compiler" "$rtm" "$runtime_provenance" \
    "$provenance" <<'PY'
from pathlib import Path
import hashlib
import os
import struct
import subprocess
import sys

path = Path(sys.argv[1])
repo = Path(sys.argv[2])
compiler = Path(sys.argv[3])
runtime = Path(sys.argv[4])
runtime_provenance = Path(sys.argv[5])
provenance = Path(sys.argv[6])
data = path.read_bytes()


def sha256(file: Path) -> str:
    return hashlib.sha256(file.read_bytes()).hexdigest()


if len(data) < 1024 or data[:4] != b"\xcf\xfa\xed\xfe":
    raise SystemExit(f"{path} is not a thin little-endian 64-bit Mach-O")
if struct.unpack_from("<I", data, 4)[0] != 0x01000007:
    raise SystemExit(f"{path} is not an x86_64 Mach-O")
runtime_data = runtime.read_bytes()
marker = b"LNLMInit"
marker_offset = runtime_data.find(marker)
if marker_offset < 0 or runtime_data.find(marker, marker_offset + 1) >= 0:
    raise SystemExit("supplied headless RTM has an invalid initialization paragraph")
if data[marker_offset : marker_offset + len(marker)] != marker:
    raise SystemExit("compiled NIVTEST does not preserve the RTM paragraph")
paragraph = marker_offset + len(marker)
paragraph_end = paragraph + 40 + 14 * 4
if paragraph_end > len(runtime_data) or paragraph_end > len(data):
    raise SystemExit("compiled NIVTEST initialization paragraph is truncated")
if (
    data[:paragraph] != runtime_data[:paragraph]
    or data[paragraph_end : len(runtime_data)] != runtime_data[paragraph_end:]
):
    raise SystemExit("compiled NIVTEST runtime prefix differs outside the initialization fields")
appname = data[paragraph : paragraph + 40]
fields = struct.unpack_from("<14i", data, paragraph + 40)
app_ws_size, app_code_size, app_code_entry = fields[:3]
physwsentry, physappsize, default_ramtop = fields[3:6]
if b"\0" not in appname:
    raise SystemExit("compiled NIVTEST has no terminated application name")
if app_ws_size < 0 or app_code_size <= 0 or not 0 <= app_code_entry < app_code_size:
    raise SystemExit("compiled NIVTEST has invalid workspace/code bounds")
if default_ramtop < app_ws_size or physwsentry != runtime.stat().st_size:
    raise SystemExit("compiled NIVTEST does not identify the supplied headless RTM")
expected_size = physwsentry + (app_ws_size + app_code_size) * 4
if physappsize != expected_size or len(data) < expected_size:
    raise SystemExit(
        f"compiled NIVTEST is incomplete: header={physappsize}, "
        f"sections={expected_size}, file={len(data)}"
    )

runtime_lines = runtime_provenance.read_text(encoding="ascii").splitlines()
runtime_values = {}
for line in runtime_lines:
    if not line or "=" not in line:
        raise SystemExit(f"invalid runtime provenance line: {line!r}")
    key, value = line.split("=", 1)
    if not key or key in runtime_values:
        raise SystemExit(f"invalid or duplicate runtime provenance key: {key!r}")
    runtime_values[key] = value
commit = os.environ.get("GITHUB_SHA")
if not commit:
    commit = subprocess.check_output(
        ["git", "-C", str(repo), "rev-parse", "HEAD"], text=True
    ).strip()
expected_runtime = {
    "runtime_provenance_format": "1",
    "commit": commit,
    "runtime_sha256": sha256(runtime),
    "runtime_mode": "headless",
    "runtime_build_script_sha256": sha256(repo / "src/linoleum_macos64/build.sh"),
    "runtime_architecture": "x86_64",
    "runtime_deployment_target": "10.15",
    "runtime_host_arch": "arm64",
    "runtime_signing": "unsigned before the Lino image is appended",
}
if any(runtime_values.get(key) != value for key, value in expected_runtime.items()):
    raise SystemExit("headless RTM does not match its macOS-host provenance")
records = [
    ("nivtest_provenance_format", "1"),
    ("commit", commit),
    ("nivtest_source_sha256", sha256(repo / "work/nivtestmain.txt")),
    ("nivtest_executable_sha256", sha256(path)),
    ("nivtest_compile_script_sha256", sha256(repo / "build/compile_nivtest_linux.sh")),
    ("nivtest_tool_sha256", sha256(repo / "tools/nivtest.py")),
    ("compiler_sha256", sha256(compiler)),
    ("cpu_pack_sha256", sha256(repo / "main/cpu/x64.bin")),
    ("cpu_pack_auditor_sha256", sha256(repo / "tools/fix_x64_pack_flags.py")),
    (
        "runtime_provenance_tool_sha256",
        sha256(repo / "tools/macos_runtime_provenance.py"),
    ),
    ("runtime_provenance_sha256", sha256(runtime_provenance)),
]
records.extend(
    (key, value) for key, value in runtime_values.items() if key != "commit"
)
records.extend(
    [
        ("system_pack_sha256", sha256(repo / "main/sys/macos.bin")),
        ("target", "macos/x64"),
        (
            "nivtest_build_provenance",
            "the exact headless RTM, compiler, generated source, CPU/SYS packs, and test executable are hash-bound across the macOS and Linux build hosts",
        ),
    ]
)
provenance.write_text(
    "".join(f"{key}={value}\n" for key, value in records), encoding="ascii"
)
print(f"compiled {path} ({len(data)} bytes, complete x86_64 Lino image)")
print(f"wrote {provenance}")
PY
file "$output"
