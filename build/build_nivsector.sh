#!/bin/bash
# Build the noctis-lino headless sector CLI (nivsector) for macOS x86_64
# via the finch lino-workspace container, then copy the Mach-O to build/nivsector.
set -euo pipefail
cd "$(dirname "$0")/.."
finch exec -i lino-workspace sh -c 'cat > /workspace/t1/nivlinvh.txt' < work/nivlinvh.txt
finch exec lino-workspace sh -c 'cd /workspace && ./lino-compiler --sys:macos--cpu:x64--ext:.exe--env:/workspace/linoenv--src:/workspace/t1/nivlinvh.txt' 2>/dev/null
finch exec lino-workspace sh -c 'cat /workspace/t1/nivlinvh.exe' > build/nivsector
chmod +x build/nivsector
echo "built build/nivsector"
