#!/usr/bin/bash

./clean.sh
CARCH="aarch64" makepkg -s
CARCH="x86_64"  makepkg -s
CARCH="riscv64" makepkg -s
