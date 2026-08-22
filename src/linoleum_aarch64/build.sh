#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
build_dir=${BUILD_DIR:-"$script_dir/build"}
compiler=${CC:-aarch64-linux-gnu-gcc}
output=${OUTPUT:-"$build_dir/rtm-aarch64"}

if ! command -v "$compiler" >/dev/null 2>&1; then
    printf 'AArch64 compiler not found: %s\n' "$compiler" >&2
    exit 2
fi

mkdir -p -- "$build_dir" "$(dirname -- "$output")"

common_flags=(
    -O2 -g -Wall -Wextra -Werror -Wconversion -Wshadow
    -fno-pie -fno-strict-aliasing
)
c_flags=(-std=c11 "${common_flags[@]}")
link_flags=(
    -static -no-pie -Wl,-z,noexecstack -Wl,--build-id=none
)

printf 'compiling rtm.c\n'
"$compiler" "${c_flags[@]}" -c "$script_dir/rtm.c" -o "$build_dir/rtm.o"
printf 'assembling isokernel.s\n'
"$compiler" -g -fno-pie -c "$script_dir/isokernel.s" -o "$build_dir/isokernel.o"
printf 'linking %s\n' "$output"
"$compiler" "${common_flags[@]}" "${link_flags[@]}" \
    "$build_dir/rtm.o" "$build_dir/isokernel.o" -lm -o "$output"
printf 'built %s\n' "$output"
