#!/bin/bash
set -e
CC=aarch64-linux-gnu-gcc
CFLAGS="-O2 -W -Wall -D_GNU_SOURCE -DDEBUG"
rm -f *.o rtm01_arm.bin
for f in rtm.c lino_file.c lino_globalK.c lino_socket.c lino_sound.c lino_keyboard.c lino_noX11.c; do
  echo "compiling $f"
  $CC $CFLAGS -c -o ${f%.c}.o $f
done
aarch64-linux-gnu-as -o isokernel.o isokernel.s
echo "linking"
$CC -static -o rtm01_arm.bin rtm.o lino_file.o lino_globalK.o lino_socket.o lino_sound.o lino_keyboard.o lino_noX11.o isokernel.o
echo done
file rtm01_arm.bin
