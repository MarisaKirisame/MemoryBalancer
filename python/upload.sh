#!/bin/sh
set -o errexit -o xtrace

DIR=$1
TIME=$(date +%s)

last=`ls "$1" | sort -r | head -1`
./clean_log
python3 python/gen.py --no-open
scp plot.png "uwplse.org:/var/www/membalancer/$TIME.png"

if command -v nightly-results &>/dev/null; then
    nightly-results img https://membalancer.uwplse.org/$TIME.png
fi
