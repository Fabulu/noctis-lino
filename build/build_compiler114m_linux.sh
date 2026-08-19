#!/bin/sh
# Bootstrap the extended L.in.oleum compiler with the protected stock compiler.
# The historical ELF executes its loaded Lino image from the heap, so modern
# Linux must supply the legacy READ_IMPLIES_EXEC personality through setarch.
set -eu

repo=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
output=${1:-"$repo/build/linux-compiler114m.bin"}
arch=$(uname -m)
stage=$(mktemp -d "${TMPDIR:-/tmp}/linoleum-compiler114m.XXXXXX")
compiler_pid=
cleanup() {
    if [ -n "$compiler_pid" ]; then
        kill "$compiler_pid" 2>/dev/null || true
        wait "$compiler_pid" 2>/dev/null || true
    fi
    rm -rf "$stage"
}
trap cleanup EXIT INT TERM

mkdir -p "$stage/main"
cp -R "$repo/main/." "$stage/main"
source="$stage/main/lib/gen/compiler114m.txt"
generated="$stage/main/lib/gen/compiler114m.bin"
log="$stage/main/lib/gen/errorlog.txt"

compile_compiler() {
    compiler=$1
    cpu=$2
    compiler_log=$3

    rm -f "$generated" "$log" "$compiler_log"
    xvfb-run -a setarch "$arch" -X "$compiler" \
        "--sys:linux--cpu:$cpu--ext:.bin--env:$stage/main--src:$source" \
        >"$compiler_log" 2>&1 &
    compiler_pid=$!

    stable=0
    previous=-1
    attempt=0
    while [ "$attempt" -lt 600 ]; do
        attempt=$((attempt + 1))
        if [ -f "$log" ] && grep -Eqi 'error:|internal problem:' "$log"; then
            cat "$log" >&2
            return 1
        fi
        if [ -s "$generated" ]; then
            current=$(wc -c <"$generated")
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
        if ! kill -0 "$compiler_pid" 2>/dev/null && [ ! -s "$generated" ]; then
            cat "$compiler_log" >&2 || true
            [ ! -f "$log" ] || cat "$log" >&2
            return 1
        fi
        sleep 0.25
    done

    kill "$compiler_pid" 2>/dev/null || true
    wait "$compiler_pid" 2>/dev/null || true
    compiler_pid=
    if [ "$stable" -lt 5 ] || [ ! -s "$generated" ]; then
        cat "$compiler_log" >&2 || true
        [ ! -f "$log" ] || cat "$log" >&2
        echo "Linux compiler bootstrap did not settle" >&2
        return 1
    fi
}

compile_compiler "$stage/main/linux_compiler.bin" i386 "$stage/bootstrap.log"
cp "$generated" "$stage/compiler114m-first.bin"
chmod +x "$stage/compiler114m-first.bin"

compile_compiler "$stage/compiler114m-first.bin" i386m "$stage/fixpoint.log"
if ! cmp -s "$stage/compiler114m-first.bin" "$generated"; then
    echo "patched Linux compiler failed its self-hosting fixpoint" >&2
    exit 1
fi

mkdir -p "$(dirname "$output")"
cp "$generated" "$output"
chmod +x "$output"

python3 - "$output" <<'PY'
from pathlib import Path
import struct
import sys

path = Path(sys.argv[1])
data = path.read_bytes()
if len(data) < 52 or data[:7] != b"\x7fELF\x01\x01\x01":
    raise SystemExit(f"{path} is not a 32-bit little-endian ELF")
if struct.unpack_from("<H", data, 18)[0] != 3:
    raise SystemExit(f"{path} is not an i386 ELF")
print(f"bootstrapped {path} ({len(data)} bytes; fixpoint identical)")
PY
