#!/bin/bash
# Build the noctis-lino headless sector CLI (nivsector) for macOS x86_64.
#
# Runs inside the workspace container (see build/build_nivlin.sh for the
# environment variables used to override the container/runtime and paths):
#   NOLINO_RUNTIME  container runtime executable (default: finch)
#   NOLINO_CTR      container name (default: lino-workspace)
#   NOLINO_WS       working dir inside the container (default: /workspace)
#   NOLINO_ENV      linoenv dir inside the container (default: /workspace/linoenv)
set -euo pipefail
cd "$(dirname "$0")/.."

: "${NOLINO_RUNTIME:=finch}"
: "${NOLINO_CTR:=lino-workspace}"
: "${NOLINO_WS:=/workspace}"
: "${NOLINO_ENV:=$NOLINO_WS/linoenv}"

"$NOLINO_RUNTIME" exec -i "$NOLINO_CTR" sh -c "cat > $NOLINO_WS/t1/nivlinvh.txt" < work/nivlinvh.txt
"$NOLINO_RUNTIME" exec "$NOLINO_CTR" sh -c "cd $NOLINO_WS && ./lino-compiler --sys:macos--cpu:x64--ext:.exe--env:$NOLINO_ENV--src:$NOLINO_WS/t1/nivlinvh.txt" 2>/dev/null
"$NOLINO_RUNTIME" exec "$NOLINO_CTR" sh -c "cat $NOLINO_WS/t1/nivlinvh.exe" > build/nivsector
chmod +x build/nivsector
echo "built build/nivsector"
