#!/bin/bash

set -e

BIN="/usr/share/bredos-news/server.bin"
SRC="/usr/share/bredos-news/server.py"

# Override with environment
if [[ "$BREDOS_NEWS_INTERPRETED" == "1" ]]; then
    echo "Forcibly running interpreted version."
    exec python3 "$SRC" "$@"
fi

ARCH=$(uname -m)
if [[ "$ARCH" != "aarch64" ]]; then
    echo "Non-aarch64 architecture: $ARCH, running interpreted."
    exec python3 "$SRC" "$@"
fi

# Try binary, fallback if it fails
"$BIN" "$@" || {
    echo "Native binary failed, running interpreted."
    exec python3 "$SRC" "$@"
}
