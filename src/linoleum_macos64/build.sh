#!/bin/bash
set -e
cd "$(dirname "$0")"
CC=clang
ARCH=x86_64
X11=/opt/X11
DEBUG="${DEBUG:-0}"
if [ "$DEBUG" = "1" ]; then
	CFLAGS="-arch $ARCH -O2 -W -Wall -D_GNU_SOURCE -DDEBUG"
else
	CFLAGS="-arch $ARCH -O2 -W -Wall -D_GNU_SOURCE"
fi
CFLAGS="$CFLAGS -I$X11/include"
LDFLAGS="-Wl,-pagezero_size,0x4000000 -L$X11/lib -lX11"

rm -f *.o rtm01.bin

for f in rtm.c lino_file.c lino_globalK.c lino_socket.c lino_sound.c \
	lino_keyboard.c lino_xdisplay.c lino_xevent.c lino_mouse.c \
	lino_xclip.c; do
	echo "compiling $f"
	$CC $CFLAGS -c -o ${f%.c}.o $f
done
echo "assembling isokernel.s"
$CC -arch $ARCH -c -o isokernel.o isokernel.s

echo "linking"
$CC -arch $ARCH $LDFLAGS -o rtm01.bin \
	rtm.o lino_file.o lino_globalK.o lino_socket.o lino_sound.o \
	lino_keyboard.o lino_xdisplay.o lino_xevent.o lino_mouse.o \
	lino_xclip.o isokernel.o

echo "done"
file rtm01.bin
ls -la rtm01.bin
