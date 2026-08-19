#!/bin/sh
# Compile the production Windows game from source with the repository's Linux
# compiler. The historical compiler owns an X11 window and remains resident
# after writing, so run it under Xvfb and accept only a settled non-empty PE.
set -eu

repo=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
output=${1:-"$repo/build/vhgame.exe"}
source="$repo/work/vhgame.txt"
compiled="$repo/work/vhgame.lxe"
log="$repo/work/errorlog.txt"
compiler_log="$repo/build/vhgame-compiler.log"

rm -f "$compiled" "$log" "$compiler_log"

xvfb-run -a "$repo/main/linux_compiler.bin" \
    "--sys:win32--cpu:i386m--ext:.lxe--env:$repo/main--src:$source" \
    >"$compiler_log" 2>&1 &
compiler_pid=$!
cleanup() {
    kill "$compiler_pid" 2>/dev/null || true
    wait "$compiler_pid" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

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

cleanup
trap - EXIT INT TERM
mkdir -p "$(dirname "$output")"
cp "$compiled" "$output"
rm -f "$compiled"

python3 - "$output" <<'PY'
from pathlib import Path
import struct
import sys

path = Path(sys.argv[1])
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
print(f"compiled {path} ({len(data)} bytes, {sections} PE sections)")
PY
