#!/bin/bash

set -e
set -x

#cleanup
mkdir -p log

rm -f /tmp/membalancer_socket

#sync with the main branch (for custom branches)
git pull --rebase origin main

mem_balancer_dir=$PWD
cd $mem_balancer_dir

export PATH="$PWD/../depot_tools:$PATH"
./clean_log
./clean_out
echo "** Pulling latest changes in MemoryBalancer and v8 **"
git submodule init
git submodule update
git submodule sync
echo "** pulling changes in MemoryBalancer"

echo "** pulling changes in v8 **"
cd ../v8/src
git stash
git checkout 2020-12-24
git pull origin
gclient sync -f --no-history

echo "** pulling changes in chrome **"
cd $mem_balancer_dir
cd "../chromium/src"
git checkout master
git pull
gclient sync -f --no-history
cd "v8"
git pull
cd "../"
echo "** building chrome **"
autoninja -C out/Release chrome

echo "** cloning membalancer-paper **"
cd $mem_balancer_dir
cd "../"
[ ! -d "membalancer-paper" ] && git clone git@github.com:cputah/membalancer-paper.git

cd $mem_balancer_dir
echo "** building v8 **"
make clean
make v8
echo "** building memorybalancer **"
make

pip3 install pyppeteer
pip3 install dominate

echo "** running eval **"
python3 python/eval.py "all"
python3 python/gen.py --action=upload
echo "** uploading results **"
last=`ls "out" | sort -r | head -1`
result_dir="out/$last"
if command -v nightly-results &>/dev/null; then
    nightly-results url "http://membalancer.uwplse.org/$result_dir"
fi
