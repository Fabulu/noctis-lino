#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
shared_dir="$script_dir/../linoleum_macos64"
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

base_flags=(
    -arch arm64 -mmacosx-version-min="$deployment_target"
    -O2 -g -fno-strict-aliasing
)
checked_flags=(
    -std=c11 "${base_flags[@]}"
    -Wall -Wextra -Werror -Wconversion -Wshadow
)
legacy_flags=(
    -std=c11 "${base_flags[@]}"
    -Wall -Wextra -Wno-deprecated-declarations
)
link_flags=(
    -arch arm64 -mmacosx-version-min="$deployment_target"
    -Wl,-no_adhoc_codesign
)

printf 'compiling checked ARM64 loader\n'
"$compiler" "${checked_flags[@]}" -c "$script_dir/rtm.c" \
    -o "$build_dir/rtm.o"
for source in lino_file.c lino_globalK.c lino_keyboard.c lino_sound.c; do
    printf 'compiling shared %s\n' "$source"
    "$compiler" "${legacy_flags[@]}" -c "$shared_dir/$source" \
        -o "$build_dir/${source%.c}.o"
done
printf 'compiling shared lino_cocoa.m\n'
"$compiler" "${legacy_flags[@]}" -c "$shared_dir/lino_cocoa.m" \
    -o "$build_dir/lino_cocoa.o"
printf 'assembling isokernel.s\n'
"$compiler" -arch arm64 -g -c "$script_dir/isokernel.s" \
    -o "$build_dir/isokernel.o"
printf 'linking %s\n' "$output"
"$compiler" "${link_flags[@]}" \
    "$build_dir/rtm.o" "$build_dir/lino_file.o" \
    "$build_dir/lino_globalK.o" "$build_dir/lino_keyboard.o" \
    "$build_dir/lino_sound.o" "$build_dir/lino_cocoa.o" \
    "$build_dir/isokernel.o" \
    -framework Cocoa -framework AudioToolbox -o "$output"
printf 'built unsigned thin-arm64 Cocoa/audio RTM %s\n' "$output"
