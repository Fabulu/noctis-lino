#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
build_dir=${BUILD_DIR:-"$script_dir/build"}
compiler=${CC:-clang}
output=${OUTPUT:-"$build_dir/rtm-macos-aarch64"}
deployment_target=${MACOSX_DEPLOYMENT_TARGET:-11.0}

if [[ $(uname -s) != Darwin ]]; then
    printf 'native macOS AArch64 runtime builds require Darwin\n' >&2
    exit 2
fi
if ! command -v "$compiler" >/dev/null 2>&1; then
    printf 'compiler not found: %s\n' "$compiler" >&2
    exit 2
fi

mkdir -p -- "$build_dir" "$(dirname -- "$output")"

common_flags=(
    -arch arm64 -mmacosx-version-min="$deployment_target"
    -O2 -g -Wall -Wextra -Werror -Wconversion -Wshadow
    -fno-strict-aliasing
)
c_flags=(-std=c11 "${common_flags[@]}")
link_flags=(
    -arch arm64 -mmacosx-version-min="$deployment_target"
    -Wl,-no_adhoc_codesign
)

printf 'compiling rtm.c\n'
"$compiler" "${c_flags[@]}" -c "$script_dir/rtm.c" -o "$build_dir/rtm.o"
printf 'assembling isokernel.s\n'
"$compiler" -arch arm64 -g -c "$script_dir/isokernel.s" \
    -o "$build_dir/isokernel.o"
printf 'linking %s\n' "$output"
"$compiler" "${common_flags[@]}" "${link_flags[@]}" \
    "$build_dir/rtm.o" "$build_dir/isokernel.o" -o "$output"
printf 'built unsigned thin-arm64 RTM %s\n' "$output"
