#!/bin/sh
pwd
cd ../../v8/src
ninja -C out.gn/x64.release.sample v8_monolith
