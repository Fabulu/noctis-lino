#!/bin/bash
set -e
cd "$(dirname "$0")"
CC=clang
ARCH=x86_64
CFLAGS="-arch $ARCH -O2 -W -Wall -D_GNU_SOURCE"
LDFLAGS="-Wl,-pagezero_size,0x4000000"

rm -f *.o rtm01.bin

for f in rtm.c lino_file.c lino_globalK.c lino_socket.c lino_sound.c \
	lino_keyboard.c; do
	echo "compiling $f"
	$CC $CFLAGS -c -o ${f%.c}.o $f
done
echo "compiling lino_cocoa.m"
$CC $CFLAGS -c -o lino_cocoa.o lino_cocoa.m
echo "assembling isokernel.s"
$CC -arch $ARCH -c -o isokernel.o isokernel.s

echo "linking"
$CC -arch $ARCH $LDFLAGS -o rtm01.bin \
	rtm.o lino_file.o lino_globalK.o lino_socket.o lino_sound.o \
	lino_keyboard.o lino_cocoa.o isokernel.o \
	-framework Cocoa

echo "done"
file rtm01.bin
ls -la rtm01.bin
