#!/bin/sh
cd ../
set -e

cd v8
ninja -C out.gn/x64.release.sample v8_monolith
cd ../

cd MemoryBalancer
g++ -std=c++17 -I. -I../v8/include -Ithird_party/json/include hello-world.cc -o hello_world -lv8_monolith -L../v8/out.gn/x64.release.sample/obj/ -pthread  -DV8_COMPRESS_POINTERS
#systemd-run --scope -p MemoryLimit=300M ./hello_world

