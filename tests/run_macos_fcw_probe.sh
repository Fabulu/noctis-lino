#!/bin/bash
set -eu

root=$(cd "$(dirname "$0")/.." && pwd)
out=${1:-"$root/build/macos-fcw-probe"}
mkdir -p "$(dirname "$out")"

xcrun --sdk macosx clang \
  -arch x86_64 -mmacosx-version-min=10.15 -std=c11 \
  -O2 -Wall -Wextra -Werror \
  "$root/tests/macos_fcw_probe.c" -o "$out"
file "$out" | grep -q 'x86_64'
xcrun vtool -show-build "$out" | grep -Eq 'minos[[:space:]]+10\.15'
arch -x86_64 "$out" | grep -q '^FCW_HOST_PROBE_OK '
