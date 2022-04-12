#!/bin/sh
set -o errexit -o xtrace

python3 python/gen.py
last=`ls "out" | sort -r | head -1`
result_dir="out/$last"
echo "** uploading files to membalancer.uwplse.org/$last **"
scp -r $result_dir "uwplse.org:/var/www/membalancer"
echo "** uploaded files **"
if command -v nightly-results &>/dev/null; then
    nightly-results url "http://membalancer.uwplse.org/$last"
    nightly-results img "http://membalancer.uwplse.org/$last/plot.png"
fi
