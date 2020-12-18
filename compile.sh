#!/bin/sh
cd ../
set -e

cd v8
ninja -C out.gn/x64.release.sample v8_monolith
cd ../

cd MemoryBalancer
mkdir -p build
cd build
cmake ../
cmake --build .
#systemd-run --scope -p MemoryLimit=300M ./hello_world

