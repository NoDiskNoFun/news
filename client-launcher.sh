#!/bin/bash

set -e

BIN="/usr/share/bredos-news/client.bin"
SRC="/usr/share/bredos-news/client.py"

# Override with environment
if [[ "$BREDOS_NEWS_INTERPRETED" == "1" ]]; then
    echo "Forcibly running interpreted version."
    exec python3 "$SRC" "$@"
fi

ARCH=$(uname -m)
if [[ "$ARCH" != "aarch64" ]]; then
    exec python3 "$SRC" "$@"
fi

# Try binary, fallback if it fails
"$BIN" "$@" || {
    echo "Native binary failed, running interpreted."
    exec python3 "$SRC" "$@"
}
