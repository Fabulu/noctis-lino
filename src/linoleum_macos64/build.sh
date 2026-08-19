#!/bin/bash
set -e
cd "$(dirname "$0")"
CC=${CC:-clang}
ARCH=x86_64
HEADLESS=${HEADLESS:-0}
DEPLOYMENT_TARGET=${MACOSX_DEPLOYMENT_TARGET:-10.15}
CFLAGS="-arch $ARCH -mmacosx-version-min=$DEPLOYMENT_TARGET -O2 -W -Wall -D_GNU_SOURCE"
LDFLAGS="-mmacosx-version-min=$DEPLOYMENT_TARGET -Wl,-pagezero_size,0x4000000 -Wl,-no_adhoc_codesign"

case "$HEADLESS" in
	0)
		display_source=lino_cocoa.m
		display_object=lino_cocoa.o
		display_ldflags="-framework Cocoa -framework AudioToolbox"
		;;
	1)
		display_source=lino_noX11.c
		display_object=lino_noX11.o
		display_ldflags=
		CFLAGS="$CFLAGS -DLINO_HEADLESS"
		;;
	*)
		echo "HEADLESS must be 0 or 1" >&2
		exit 2
		;;
esac

rm -f *.o rtm01.bin

for f in rtm.c lino_file.c lino_globalK.c lino_socket.c lino_sound.c \
	lino_keyboard.c; do
	echo "compiling $f"
	$CC $CFLAGS -c -o ${f%.c}.o $f
done
echo "compiling $display_source"
$CC $CFLAGS -c -o "$display_object" "$display_source"
echo "assembling isokernel.s"
$CC $CFLAGS -c -o isokernel.o isokernel.s

echo "linking"
$CC $CFLAGS $LDFLAGS -o rtm01.bin \
	rtm.o lino_file.o lino_globalK.o lino_socket.o lino_sound.o \
	lino_keyboard.o "$display_object" isokernel.o \
	$display_ldflags

echo "done"
file rtm01.bin
ls -la rtm01.bin
