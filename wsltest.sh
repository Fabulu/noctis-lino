#!/bin/sh
B=/mnt/c/programmieren/linoleum/main/linux_compiler.bin
echo "DISPLAY=[$DISPLAY]"
echo
echo "=== A: no args, DISPLAY set (does it survive display init?) ==="
DISPLAY=:0 timeout 25 "$B"; echo "exit=$?"
echo
echo "=== B: with args, run from inside the source dir ==="
cd /mnt/c/programmieren/linoleum/work
DISPLAY=:0 timeout 40 "$B" "--sys:win32--cpu:i386--ext:.exe--env:/mnt/c/programmieren/linoleum/main--src:/mnt/c/programmieren/linoleum/work/hello.txt"
echo "exit=$?"
echo
echo "=== C: native linux target instead of win32 ==="
DISPLAY=:0 timeout 40 "$B" "--sys:linux--cpu:i386--ext:.bin--env:/mnt/c/programmieren/linoleum/main--src:/mnt/c/programmieren/linoleum/work/hello.txt"
echo "exit=$?"
echo
ls -l /mnt/c/programmieren/linoleum/work/
