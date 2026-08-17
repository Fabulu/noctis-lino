#!/bin/bash
# Build the noctis-lino headless CLI (nivlin) for macOS x86_64.
#
# The L.in.oleum compiler is a subsystem-2 (GUI) binary that only produces
# output via the host environment, so the build runs inside the workspace
# container.  Override the container/runtime and paths via environment
# variables if your setup differs from the defaults below:
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

"$NOLINO_RUNTIME" exec -i "$NOLINO_CTR" sh -c "cat > $NOLINO_WS/t1/nivlin.txt" < work/nivlin.txt
"$NOLINO_RUNTIME" exec "$NOLINO_CTR" sh -c "cd $NOLINO_WS && ./lino-compiler --sys:macos--cpu:x64--ext:.exe--env:$NOLINO_ENV--src:$NOLINO_WS/t1/nivlin.txt" 2>/dev/null
"$NOLINO_RUNTIME" exec "$NOLINO_CTR" sh -c "cat $NOLINO_WS/t1/nivlin.exe" > build/nivlin
chmod +x build/nivlin
echo "built build/nivlin"
