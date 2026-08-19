#!/bin/sh
# Cross-compile the production NIVGEN harness with the repository's Linux
# compiler and a supplied macOS x86_64 RTM. The compiler owns an X11 window and
# remains resident after writing, so CI runs it under Xvfb and accepts only a
# settled non-empty output.
set -eu

repo=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
rtm=${1:-"$repo/build/macos-rtm01.bin"}
output=${2:-"$repo/build/nivtest"}
source="$repo/work/nivtestmain.txt"
compiled="$repo/work/nivtestmain.exe"
log="$repo/work/errorlog.txt"
compiler="$repo/build/linux-compiler114m.bin"

python3 "$repo/tools/pack_lino_sys.py" "$rtm" "$repo/main/sys/macos.bin"
python3 -c 'from tools.nivtest import derive_main; derive_main()'
"$repo/build/build_compiler114m_linux.sh" "$compiler"
rm -f "$compiled" "$log"

xvfb-run -a setarch "$(uname -m)" -X "$compiler" \
    "--sys:macos--cpu:x64--ext:.exe--env:$repo/main--src:$source" \
    >"$repo/build/nivtest-compiler.log" 2>&1 &
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
        cat "$repo/build/nivtest-compiler.log" >&2 || true
        [ ! -f "$log" ] || cat "$log" >&2
        exit 1
    fi
    sleep 0.25
done

if [ "$stable" -lt 5 ] || [ ! -s "$compiled" ]; then
    cat "$repo/build/nivtest-compiler.log" >&2 || true
    [ ! -f "$log" ] || cat "$log" >&2
    echo "macOS NIVGEN cross-compile did not settle" >&2
    exit 1
fi

cleanup
trap - EXIT INT TERM
mkdir -p "$(dirname "$output")"
cp "$compiled" "$output"
chmod +x "$output"
file "$output"
