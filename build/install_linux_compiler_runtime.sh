#!/bin/sh
# Install the 32-bit runtime required by the protected Linux compiler without
# allowing a transient package mirror or package-manager lock to hang CI.
set -eu

sudo dpkg --add-architecture i386

apt_retry() {
    attempt=1
    while [ "$attempt" -le 3 ]; do
        if sudo env \
            DEBIAN_FRONTEND=noninteractive \
            DEBIAN_PRIORITY=critical \
            NEEDRESTART_MODE=a \
            APT_LISTCHANGES_FRONTEND=none \
            apt-get \
                -o Acquire::Retries=3 \
                -o Acquire::http::Timeout=30 \
                -o Acquire::https::Timeout=30 \
                -o DPkg::Lock::Timeout=60 \
                "$@"; then
            return 0
        fi
        if [ "$attempt" -lt 3 ]; then
            sleep $((attempt * 10))
        fi
        attempt=$((attempt + 1))
    done
    return 1
}

apt_retry update
apt_retry install -y --no-install-recommends \
    libc6:i386 libx11-6:i386 libxau6:i386 libxcb1:i386 libxdmcp6:i386 \
    util-linux xvfb xauth
