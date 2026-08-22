#!/bin/sh
# Append compiler-owned AArch64 Lino code to an unsigned macOS arm64 RTM.
set -eu

repo=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
compiler=${1:-"$repo/build/linux-compiler114m.bin"}
runtime=${2:-"$repo/build/rtm-macos-aarch64"}
source_input=${3:-"$repo/tests/fixtures/macos_aarch64_runtime.txt"}
output=${4:-"$repo/build/macos-aarch64-fixture.unsigned"}
source_mode=${5:-single}
stage=$(mktemp -d "${TMPDIR:-/tmp}/macos-aarch64-lino.XXXXXX")
compiler_group=
compiler_supervisor=
cleanup() {
    if [ -n "$compiler_group" ]; then
        /bin/kill -TERM -- "-$compiler_group" 2>/dev/null || true
        /bin/kill -KILL -- "-$compiler_group" 2>/dev/null || true
    fi
    if [ -n "$compiler_supervisor" ]; then
        wait "$compiler_supervisor" 2>/dev/null || true
    fi
    rm -rf "$stage"
}
trap cleanup EXIT INT TERM

if [ ! -x "$compiler" ] || [ ! -f "$runtime" ] || [ ! -f "$source_input" ]; then
    echo "compiler, unsigned runtime, and fixture source are required" >&2
    exit 2
fi
source_input=$(CDPATH= cd -- "$(dirname -- "$source_input")" && pwd)/$(basename -- "$source_input")
case $source_mode in
    single)
        required_commands="python3 xvfb-run setsid setarch"
        ;;
    tracked-work)
        if [ "$source_input" != "$repo/work/vhgame.txt" ]; then
            echo "tracked-work mode accepts only work/vhgame.txt" >&2
            exit 2
        fi
        required_commands="python3 xvfb-run setsid setarch git tar"
        ;;
    *)
        echo "source mode must be single or tracked-work" >&2
        exit 2
        ;;
esac
for command in $required_commands; do
    if ! command -v "$command" >/dev/null 2>&1; then
        echo "required command not found: $command" >&2
        exit 2
    fi
done

mkdir -p "$stage/env/sys" "$stage/source" "$(dirname "$output")"
ln -s "$repo/main/lib" "$stage/env/lib"
ln -s "$repo/main/cpu" "$stage/env/cpu"
python3 "$repo/tools/pack_lino_sys.py" \
    "$runtime" "$stage/env/sys/macarm64.bin"
case $source_mode in
    single)
        cp "$source_input" "$stage/source/fixture.txt"
        source="$stage/source/fixture.txt"
        ;;
    tracked-work)
        git -C "$repo" archive --format=tar HEAD -- \
            'work/*.txt' 'work/**/*.txt' 'work/*.tga' \
            | tar -xf - -C "$stage/source"
        source="$stage/source/work/vhgame.txt"
        if [ ! -f "$source" ] || \
            [ "$(sha256sum "$source_input" | cut -d ' ' -f 1)" != \
              "$(sha256sum "$source" | cut -d ' ' -f 1)" ]; then
            echo "tracked work/vhgame.txt differs from the requested source" >&2
            exit 2
        fi
        ;;
esac
compiled="${source%.*}.bin"
error_log="$(dirname "$source")/errorlog.txt"
compiler_log="$stage/compiler.log"
group_file="$stage/compiler.pgid"
arch=$(uname -m)

compiled_complete() {
    python3 - "$compiled" "$runtime" <<'PY' >/dev/null 2>&1
from pathlib import Path
import struct
import sys

image = Path(sys.argv[1]).read_bytes()
runtime = Path(sys.argv[2]).read_bytes()
marker = b"LNLMInit"
end_marker = b"LNLMIend"
offset = image.find(marker)
end_offset = runtime.find(end_marker)
if offset < 0 or image.find(marker, offset + 1) >= 0:
    raise SystemExit(1)
if offset != runtime.find(marker) or end_offset < 0:
    raise SystemExit(1)
if image.find(end_marker) != end_offset:
    raise SystemExit(1)
init_start = offset + len(marker)
if image[:init_start] != runtime[:init_start]:
    raise SystemExit(1)
if image[end_offset:len(runtime)] != runtime[end_offset:]:
    raise SystemExit(1)
try:
    fields = struct.unpack_from("<14i", image, offset + len(marker) + 40)
except struct.error:
    raise SystemExit(1)
app_ws_size, app_code_size, app_code_entry = fields[:3]
physwsentry, physappsize = fields[3:5]
if app_ws_size <= 0 or app_code_size <= 0:
    raise SystemExit(1)
if not 0 <= app_code_entry < app_code_size:
    raise SystemExit(1)
if physwsentry < len(runtime) or physappsize != len(image):
    raise SystemExit(1)
if physwsentry + (app_ws_size + app_code_size) * 4 != physappsize:
    raise SystemExit(1)
PY
}

setsid sh -c '
    group_file=$1
    shift
    printf "%s\n" "$$" > "$group_file"
    exec "$@"
' sh "$group_file" xvfb-run -a setarch "$arch" -X "$compiler" \
    "--sys:macarm64--cpu:aarch64--ext:.bin--env:$stage/env--src:$source" \
    >"$compiler_log" 2>&1 &
compiler_supervisor=$!

attempt=0
while [ ! -s "$group_file" ] && [ "$attempt" -lt 100 ]; do
    attempt=$((attempt + 1))
    sleep 0.025
done
if [ ! -s "$group_file" ]; then
    echo "AArch64 fixture compiler process group did not start" >&2
    exit 1
fi
read -r compiler_group < "$group_file"
case $compiler_group in
    ''|*[!0-9]*)
        echo "AArch64 fixture compiler reported an invalid process group" >&2
        exit 1
        ;;
esac

stable=0
previous=
attempt=0
while [ "$attempt" -lt 600 ]; do
    attempt=$((attempt + 1))
    if [ -f "$error_log" ] && grep -Eqi 'error:|internal problem:' "$error_log"; then
        cat "$error_log" >&2
        exit 1
    fi
    if [ -s "$compiled" ] && compiled_complete; then
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
    if ! /bin/kill -0 -- "-$compiler_group" 2>/dev/null; then
        if [ -s "$compiled" ]; then
            previous=$(sha256sum "$compiled" | cut -d ' ' -f 1)
            stable=8
            break
        fi
        cat "$compiler_log" >&2 || true
        [ ! -f "$error_log" ] || cat "$error_log" >&2
        exit 1
    fi
    sleep 0.25
done
if [ "$stable" -lt 8 ] || [ ! -s "$compiled" ]; then
    cat "$compiler_log" >&2 || true
    [ ! -f "$error_log" ] || cat "$error_log" >&2
    echo "AArch64 fixture compile did not settle" >&2
    exit 1
fi

/bin/kill -TERM -- "-$compiler_group" 2>/dev/null || true
attempt=0
while /bin/kill -0 -- "-$compiler_group" 2>/dev/null && \
    [ "$attempt" -lt 20 ]; do
    attempt=$((attempt + 1))
    sleep 0.05
done
/bin/kill -KILL -- "-$compiler_group" 2>/dev/null || true
wait "$compiler_supervisor" 2>/dev/null || true
compiler_group=
compiler_supervisor=

if [ "$(sha256sum "$compiled" | cut -d ' ' -f 1)" != "$previous" ]; then
    echo "AArch64 fixture changed while its compiler stopped" >&2
    exit 1
fi
cp "$compiled" "$output"
chmod +x "$output"
python3 - "$output" "$runtime" <<'PY'
from pathlib import Path
import struct
import sys

image = Path(sys.argv[1]).read_bytes()
runtime = Path(sys.argv[2]).read_bytes()
if len(image) < len(runtime) or image[:4] != b"\xcf\xfa\xed\xfe":
    raise SystemExit("compiled fixture is not a thin 64-bit Mach-O")
if struct.unpack_from("<i", image, 4)[0] != 0x0100000C:
    raise SystemExit("compiled fixture is not arm64")
marker = b"LNLMInit"
end_marker = b"LNLMIend"
offset = image.find(marker)
end_offset = runtime.find(end_marker)
if offset < 0 or image.find(marker, offset + 1) >= 0:
    raise SystemExit("compiled fixture has an invalid initialization paragraph")
if runtime.find(marker) != offset or end_offset < 0:
    raise SystemExit("compiler moved the runtime initialization paragraph")
if image.find(end_marker) != end_offset:
    raise SystemExit("compiler moved the runtime end marker")
init_start = offset + len(marker)
if image[:init_start] != runtime[:init_start]:
    raise SystemExit("compiler changed the runtime before initialization fields")
if image[end_offset:len(runtime)] != runtime[end_offset:]:
    raise SystemExit("compiler changed immutable runtime bytes")
fields = struct.unpack_from("<14i", image, offset + len(marker) + 40)
app_ws_size, app_code_size, app_code_entry = fields[:3]
physwsentry, physappsize, default_ramtop = fields[3:6]
if app_ws_size <= 0 or app_code_size <= 0 or not 0 <= app_code_entry < app_code_size:
    raise SystemExit("compiled fixture has invalid Lino payload bounds")
if physwsentry < len(runtime) or physappsize != len(image):
    raise SystemExit(
        "compiled fixture does not identify the supplied runtime: "
        f"physwsentry={physwsentry}, runtime={len(runtime)}, "
        f"physappsize={physappsize}, image={len(image)}"
    )
if default_ramtop < app_ws_size + 12:
    raise SystemExit("compiled fixture leaves no arm64 communication slots")
if physwsentry + (app_ws_size + app_code_size) * 4 != physappsize:
    raise SystemExit("compiled fixture has inconsistent section extents")
print(f"compiled native macOS AArch64 fixture ({len(image)} bytes)")
PY
printf 'wrote %s\n' "$output"
