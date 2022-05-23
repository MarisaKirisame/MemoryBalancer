#!/bin/sh
set -o errexit -o xtrace

python3 python/gen.py --eval_name=JS --action=upload
last=`ls "out" | sort -r | head -1`
result_dir="out/$last"
if command -v nightly-results &>/dev/null; then
    nightly-results url "http://membalancer.uwplse.org/$last"
    nightly-results img "http://membalancer.uwplse.org/$last/plot.png"
fi
