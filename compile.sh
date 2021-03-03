#!/bin/sh
set -e
cd ../

cd v8/src
ninja -C out.gn/x64.release.sample v8_monolith
cd ../../

cd MemoryBalancer
mkdir -p build
cd build
cmake ../
cmake --build .
#systemd-run --scope -p MemoryLimit=300M ./hello_world

