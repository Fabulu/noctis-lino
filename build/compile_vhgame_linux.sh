#!/bin/sh
# Compile the production Windows game from source with the repository's Linux
# compiler. The historical compiler owns an X11 window and remains resident
# after writing, so run it under Xvfb and accept only a settled non-empty PE.
set -eu

repo=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
output=${1:-"$repo/build/vhgame.exe"}
stage=$(mktemp -d "/tmp/linoleum-windows-i386-source.XXXXXX")
source="$stage/work/vhgame.txt"
compiled="$stage/work/vhgame.lxe"
log="$stage/work/errorlog.txt"
compiler_log="$repo/build/vhgame-compiler.log"
compiler="$repo/build/linux-compiler114m.bin"
compiler_pid=
stop_compiler() {
    if [ -n "$compiler_pid" ]; then
        kill "$compiler_pid" 2>/dev/null || true
        wait "$compiler_pid" 2>/dev/null || true
        compiler_pid=
    fi
}
cleanup() {
    stop_compiler
    rm -rf "$stage"
}
trap cleanup EXIT INT TERM

python3 "$repo/tools/stage_windows_i386_source.py" --output "$stage" >/dev/null
# Keep CPU/system packs on the build host's native filesystem too. Historical
# Linux compiler file I/O is not reliable through WSL's mounted Windows drive.
mkdir -p "$stage/main"
cp -R "$repo/main/." "$stage/main"
"$repo/build/build_compiler114m_linux.sh" "$compiler"
rm -f "$compiled" "$log" "$compiler_log"

xvfb-run -a setarch "$(uname -m)" -X "$compiler" \
    "--sys:win32--cpu:i386m--ext:.lxe--env:$stage/main--src:$source" \
    >"$compiler_log" 2>&1 &
compiler_pid=$!

stable=0
previous=-1
attempt=0
while [ "$attempt" -lt 600 ]; do
    attempt=$((attempt + 1))
    if [ -f "$log" ] && grep -Eqi 'error:|internal problem:' "$log"; then
        cat "$log" >&2
        exit 1
    fi
    if [ -s "$compiled" ]; then
        current=$(wc -c <"$compiled")
        if [ "$current" = "$previous" ]; then
            stable=$((stable + 1))
        else
            stable=1
            previous=$current
        fi
        if [ "$stable" -ge 5 ]; then
            break
        fi
    else
        stable=0
        previous=-1
    fi
    if ! kill -0 "$compiler_pid" 2>/dev/null && [ ! -s "$compiled" ]; then
        cat "$compiler_log" >&2 || true
        [ ! -f "$log" ] || cat "$log" >&2
        exit 1
    fi
    sleep 0.25
done

if [ "$stable" -lt 5 ] || [ ! -s "$compiled" ]; then
    cat "$compiler_log" >&2 || true
    [ ! -f "$log" ] || cat "$log" >&2
    echo "Windows game compile did not settle" >&2
    exit 1
fi

stop_compiler
python3 "$repo/tools/patch_runtime_fcw.py" "$compiled" >/dev/null
mkdir -p "$(dirname "$output")"
cp "$compiled" "$output"

provenance="$repo/build/windows-build.provenance.txt"
python3 - "$output" "$repo" "$compiler" "$provenance" "$stage" <<'PY'
from pathlib import Path
import hashlib
import os
import struct
import subprocess
import sys

path = Path(sys.argv[1])
repo = Path(sys.argv[2])
compiler = Path(sys.argv[3])
provenance = Path(sys.argv[4])
stage = Path(sys.argv[5])
data = path.read_bytes()
if len(data) < 1024 or data[:2] != b"MZ":
    raise SystemExit(f"{path} is not a plausible Windows PE")
pe = struct.unpack_from("<I", data, 0x3C)[0]
if pe < 0 or pe + 24 > len(data) or data[pe:pe + 4] != b"PE\0\0":
    raise SystemExit(f"{path} has no valid PE signature")
machine, sections = struct.unpack_from("<HH", data, pe + 4)
if machine != 0x014C or sections == 0:
    raise SystemExit(
        f"expected sectioned i386 PE, got machine {machine:#06x} with {sections} sections"
    )


def sha256(file: Path) -> str:
    return hashlib.sha256(file.read_bytes()).hexdigest()


commit = os.environ.get("GITHUB_SHA")
if not commit:
    commit = subprocess.check_output(
        ["git", "-C", str(repo), "rev-parse", "HEAD"], text=True
    ).strip()
source_records = []
source_keys = set()
source_manifest = stage / "windows-i386-source.provenance.txt"
for line in source_manifest.read_text(encoding="ascii").splitlines():
    key, value = line.split("=", 1)
    if not key or key in source_keys or not value:
        raise SystemExit(f"invalid staged-source provenance key: {key!r}")
    source_keys.add(key)
    source_records.append((key, value))
records = [
    ("commit", commit),
    ("source_manifest_sha256", sha256(source_manifest)),
    *source_records,
    ("runtime_patcher_sha256", sha256(repo / "tools/patch_runtime_fcw.py")),
    ("executable_sha256", sha256(path)),
    ("compile_script_sha256", sha256(repo / "build/compile_vhgame_linux.sh")),
    (
        "compiler_runtime_installer_sha256",
        sha256(repo / "build/install_linux_compiler_runtime.sh"),
    ),
    ("bootstrap_compiler_sha256", sha256(repo / "main/linux_compiler.bin")),
    ("compiler_source_sha256", sha256(repo / "main/lib/gen/compiler114m.txt")),
    ("compiler_bits_library_sha256", sha256(repo / "main/lib/gen/bits.txt")),
    ("compiler_bytes_library_sha256", sha256(repo / "main/lib/gen/bytes.txt")),
    ("compiler_build_script_sha256", sha256(repo / "build/build_compiler114m_linux.sh")),
    ("bootstrap_cpu_pack_sha256", sha256(repo / "main/cpu/i386.bin")),
    ("bootstrap_system_pack_sha256", sha256(repo / "main/sys/linux.bin")),
    ("compiler_sha256", sha256(compiler)),
    ("cpu_pack_sha256", sha256(stage / "main/cpu/i386m.bin")),
    ("system_pack_sha256", sha256(stage / "main/sys/win32.bin")),
    ("target", "win32/i386m"),
    (
        "build_provenance",
        "all hashes were recorded from bytes on the Linux build host; the extended compiler was bootstrapped and fixpoint-verified before compiling the game",
    ),
]
provenance.write_text(
    "".join(f"{key}={value}\n" for key, value in records), encoding="ascii"
)
print(f"compiled {path} ({len(data)} bytes, {sections} PE sections)")
print(f"wrote {provenance}")
PY
cleanup
trap - EXIT INT TERM
