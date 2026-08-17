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

python3 -c 'from tools.nivtest import derive_main; derive_main()'

remote_root="$NOLINO_WS/nivtest-src"
"$NOLINO_RUNTIME" exec "$NOLINO_CTR" sh -c \
    "mkdir -p '$remote_root/work/fp'"

# Send only committed Lino source libraries, then overlay the generated main.
# This avoids copying local saves, captures, executables, and debug artifacts.
git ls-files -z -- ':(glob)work/*.txt' ':(glob)work/fp/*.txt' | \
    tar --null -T - -cf - | \
    "$NOLINO_RUNTIME" exec -i "$NOLINO_CTR" \
        sh -c "tar -xf - -C '$remote_root'"
"$NOLINO_RUNTIME" exec -i "$NOLINO_CTR" \
    sh -c "cat > '$remote_root/work/nivtestmain.txt'" \
    < work/nivtestmain.txt

"$NOLINO_RUNTIME" exec "$NOLINO_CTR" sh -c \
    "cd '$NOLINO_WS' && ./lino-compiler --sys:macos--cpu:x64--ext:.exe--env:'$NOLINO_ENV'--src:'$remote_root/work/nivtestmain.txt'"

mkdir -p build
"$NOLINO_RUNTIME" exec "$NOLINO_CTR" \
    sh -c "cat '$remote_root/work/nivtestmain.exe'" > build/nivtest
chmod +x build/nivtest
echo "built build/nivtest"
