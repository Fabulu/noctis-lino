#!/bin/sh
# Cross-compile the production game for macOS x86_64 with a supplied Cocoa RTM.
# The historical compiler remains resident after writing, so run it under Xvfb
# and accept only a settled, structurally valid Mach-O output.
set -eu

repo=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
rtm=${1:-"$repo/build/macos-cocoa-rtm01.bin"}
output=${2:-"$repo/build/Noctis-IV.game"}
runtime_provenance=${3:-"$(dirname "$rtm")/cocoa-runtime.provenance.txt"}
source="$repo/work/vhgame.txt"
compiled="$repo/work/vhgame.exe"
log="$repo/work/errorlog.txt"
compiler_log="$repo/build/noctis-macos-compiler.log"
compiler_group_file="$repo/build/noctis-macos-compiler.pgid"
compiler="$repo/build/linux-compiler114m.bin"

if [ ! -f "$rtm" ] || [ ! -f "$runtime_provenance" ]; then
    echo "a Cocoa RTM and its macOS-host provenance are required" >&2
    exit 2
fi
runtime_commit=${GITHUB_SHA:-$(git -C "$repo" rev-parse HEAD)}
python3 "$repo/tools/macos_runtime_provenance.py" verify \
    --runtime "$rtm" --provenance "$runtime_provenance" \
    --mode cocoa --commit "$runtime_commit"

python3 "$repo/tools/fix_x64_pack_flags.py" "$repo/main/cpu/x64.bin"
python3 "$repo/tools/pack_lino_sys.py" "$rtm" "$repo/main/sys/macos.bin"
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
    echo "macOS compiler process group did not start" >&2
    exit 1
fi
read -r compiler_group <"$compiler_group_file"
case $compiler_group in
    ''|*[!0-9]*)
        /bin/kill -TERM "$compiler_supervisor" 2>/dev/null || true
        wait "$compiler_supervisor" 2>/dev/null || true
        echo "macOS compiler reported an invalid process group" >&2
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
    echo "macOS game cross-compile did not settle" >&2
    exit 1
fi

cleanup
trap - EXIT INT TERM
if [ "$(sha256sum "$compiled" | cut -d ' ' -f 1)" != "$previous" ]; then
    echo "macOS game changed while the compiler process group stopped" >&2
    exit 1
fi
mkdir -p "$(dirname "$output")"
cp "$compiled" "$output"
chmod +x "$output"
rm -f "$compiled"

provenance="$repo/build/macos-build.provenance.txt"
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
if len(data) < 1024 or data[:4] != b"\xcf\xfa\xed\xfe":
    raise SystemExit(f"{path} is not a thin little-endian 64-bit Mach-O")
cpu_type = struct.unpack_from("<I", data, 4)[0]
if cpu_type != 0x01000007:
    raise SystemExit(f"expected x86_64 Mach-O, got CPU type {cpu_type:#x}")
if len(data) <= runtime.stat().st_size:
    raise SystemExit("compiled game does not contain an appended Lino application")

marker = b"LNLMInit"
runtime_data = runtime.read_bytes()
marker_offset = runtime_data.find(marker)
if marker_offset < 0 or runtime_data.find(marker, marker_offset + 1) >= 0:
    raise SystemExit("supplied RTM lacks one unambiguous Lino initialization paragraph")
if data[marker_offset : marker_offset + len(marker)] != marker:
    raise SystemExit("compiled game does not preserve the RTM initialization paragraph")
paragraph = marker_offset + len(marker)
paragraph_end = paragraph + 40 + 14 * 4
if paragraph_end > len(runtime_data) or paragraph_end > len(data):
    raise SystemExit("compiled game's Lino initialization paragraph is truncated")
if (
    data[:paragraph] != runtime_data[:paragraph]
    or data[paragraph_end : len(runtime_data)] != runtime_data[paragraph_end:]
):
    raise SystemExit("compiled game runtime prefix differs outside the initialization fields")
appname = data[paragraph : paragraph + 40]
fields = struct.unpack_from("<14i", data, paragraph + 40)
(
    app_ws_size,
    app_code_size,
    app_code_entry,
    physwsentry,
    physappsize,
    default_ramtop,
    app_code_pri,
    lfb_x,
    lfb_y,
    lfb_w,
    lfb_h,
    pointermode,
    testflags,
    displaymode,
) = fields
if b"\0" not in appname:
    raise SystemExit("compiled game has no terminated application name")
if app_ws_size < 0 or app_code_size <= 0 or not 0 <= app_code_entry < app_code_size:
    raise SystemExit("compiled game has invalid Lino workspace/code bounds")
if default_ramtop < app_ws_size or physwsentry != runtime.stat().st_size:
    raise SystemExit("compiled game does not identify the supplied RTM and workspace")
expected_size = physwsentry + (app_ws_size + app_code_size) * 4
if physappsize != len(data) or expected_size != len(data):
    raise SystemExit(
        f"compiled Lino image is incomplete: header={physappsize}, "
        f"sections={expected_size}, file={len(data)}"
    )


def sha256(file: Path) -> str:
    return hashlib.sha256(file.read_bytes()).hexdigest()


def tracked_tree_sha256(directory: Path) -> str:
    prefix = directory.relative_to(repo).as_posix()
    listed = subprocess.check_output(
        ["git", "-C", str(repo), "ls-files", "-z", "--", prefix]
    )
    relatives = sorted(
        item.decode("utf-8") for item in listed.split(b"\0") if item
    )
    if not relatives:
        raise SystemExit(f"no tracked files found under {prefix}")
    digest = hashlib.sha256()
    for relative_text in relatives:
        file = repo / relative_text
        if not file.is_file():
            raise SystemExit(f"tracked runtime input is not a file: {relative_text}")
        relative = relative_text.encode("utf-8")
        payload = file.read_bytes()
        digest.update(len(relative).to_bytes(4, "little"))
        digest.update(relative)
        digest.update(len(payload).to_bytes(8, "little"))
        digest.update(payload)
    return digest.hexdigest()


commit = os.environ.get("GITHUB_SHA")
if not commit:
    commit = subprocess.check_output(
        ["git", "-C", str(repo), "rev-parse", "HEAD"], text=True
    ).strip()

runtime_values = {}
for line in runtime_provenance.read_text(encoding="ascii").splitlines():
    if not line or "=" not in line:
        raise SystemExit(f"invalid runtime provenance line: {line!r}")
    key, value = line.split("=", 1)
    if not key or key in runtime_values:
        raise SystemExit(f"invalid or duplicate runtime provenance key: {key!r}")
    runtime_values[key] = value
required_runtime_keys = {
    "runtime_provenance_format",
    "commit",
    "runtime_sha256",
    "runtime_mode",
    "runtime_build_script_sha256",
    "runtime_source_tree_sha256",
    "runtime_architecture",
    "runtime_deployment_target",
    "runtime_host_arch",
    "runtime_macos_version",
    "runtime_xcode_version",
    "runtime_sdk_version",
    "runtime_clang_version",
    "runtime_signing",
    "runtime_provenance",
}
if set(runtime_values) != required_runtime_keys:
    raise SystemExit("Cocoa runtime provenance schema differs")
runtime_expected = {
    "runtime_provenance_format": "1",
    "commit": commit,
    "runtime_sha256": sha256(runtime),
    "runtime_mode": "cocoa",
    "runtime_build_script_sha256": sha256(repo / "src/linoleum_macos64/build.sh"),
    "runtime_source_tree_sha256": tracked_tree_sha256(
        repo / "src/linoleum_macos64"
    ),
    "runtime_architecture": "x86_64",
    "runtime_deployment_target": "10.15",
    "runtime_host_arch": "arm64",
    "runtime_signing": "unsigned before the Lino image is appended",
}
if any(runtime_values.get(key) != value for key, value in runtime_expected.items()):
    raise SystemExit("Cocoa RTM does not match its macOS-host provenance")
records = [
    ("commit", commit),
    ("source_sha256", sha256(repo / "work/vhgame.txt")),
    ("executable_sha256", sha256(path)),
    ("compile_script_sha256", sha256(repo / "build/compile_noctis_macos_linux.sh")),
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
    ("cpu_pack_sha256", sha256(repo / "main/cpu/x64.bin")),
    ("cpu_pack_auditor_sha256", sha256(repo / "tools/fix_x64_pack_flags.py")),
    (
        "runtime_provenance_tool_sha256",
        sha256(repo / "tools/macos_runtime_provenance.py"),
    ),
    ("runtime_provenance_sha256", sha256(runtime_provenance)),
    ("runtime_provenance_format", runtime_values["runtime_provenance_format"]),
    ("runtime_sha256", runtime_values["runtime_sha256"]),
    ("runtime_mode", runtime_values["runtime_mode"]),
    ("runtime_build_script_sha256", runtime_values["runtime_build_script_sha256"]),
    ("runtime_source_tree_sha256", runtime_values["runtime_source_tree_sha256"]),
    ("runtime_architecture", runtime_values["runtime_architecture"]),
    ("runtime_deployment_target", runtime_values["runtime_deployment_target"]),
    ("runtime_host_arch", runtime_values["runtime_host_arch"]),
    ("runtime_macos_version", runtime_values["runtime_macos_version"]),
    ("runtime_xcode_version", runtime_values["runtime_xcode_version"]),
    ("runtime_sdk_version", runtime_values["runtime_sdk_version"]),
    ("runtime_clang_version", runtime_values["runtime_clang_version"]),
    ("runtime_signing", runtime_values["runtime_signing"]),
    ("runtime_provenance", runtime_values["runtime_provenance"]),
    ("system_pack_sha256", sha256(repo / "main/sys/macos.bin")),
    ("target", "macos/x64"),
    (
        "build_provenance",
        "all hashes were recorded from exact bytes on the macOS RTM and Linux compiler hosts; the extended compiler was bootstrapped and fixpoint-verified before compiling the game",
    ),
]
provenance.write_text(
    "".join(f"{key}={value}\n" for key, value in records), encoding="ascii"
)
print(f"compiled {path} ({len(data)} bytes, x86_64 Mach-O with appended Lino image)")
print(f"wrote {provenance}")
PY
