#!/bin/sh
# 1) Switch off the slow global round-robin mirror.
# 2) Enable i386 and install the one 32-bit library linux_compiler.bin needs.
# Run with:  wsl -e sudo sh /mnt/c/programmieren/linoleum/install_x11.sh
set -e

if [ ! -f /etc/apt/sources.list.bak-lino ]; then
    cp /etc/apt/sources.list /etc/apt/sources.list.bak-lino
    echo "Backed up sources.list -> /etc/apt/sources.list.bak-lino"
fi

sed -i 's|http://archive.ubuntu.com/ubuntu/|http://de.archive.ubuntu.com/ubuntu/|g' /etc/apt/sources.list
echo "Mirror now:"
grep -m1 'de.archive' /etc/apt/sources.list || echo "  (no change made)"
echo

dpkg --add-architecture i386
apt-get update
apt-get install -y libx11-6:i386

echo
echo "=== verifying ==="
ls -l /usr/lib/i386-linux-gnu/libX11.so.6
