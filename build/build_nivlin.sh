#!/bin/bash
# Build the noctis-lino headless CLI (nivlin) for macOS x86_64 via the
# finch lino-workspace container, then copy the Mach-O to build/nivlin.
set -euo pipefail
cd "$(dirname "$0")/.."
finch exec -i lino-workspace sh -c 'cat > /workspace/t1/nivlin.txt' < work/nivlin.txt
finch exec lino-workspace sh -c 'cd /workspace && ./lino-compiler --sys:macos--cpu:x64--ext:.exe--env:/workspace/linoenv--src:/workspace/t1/nivlin.txt' 2>/dev/null
finch exec lino-workspace sh -c 'cat /workspace/t1/nivlin.exe' > build/nivlin
chmod +x build/nivlin
echo "built build/nivlin"
