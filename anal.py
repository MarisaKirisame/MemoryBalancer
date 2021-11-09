import os
import sys
from pathlib import Path
import json
import numpy as np
import collections

class FrozenDict(collections.Mapping):
    """Don't forget the docstrings!!"""
    def __repr__(self):
        return repr(self._d)

    def __init__(self, *args, **kwargs):
        self._d = dict(*args, **kwargs)
        self._hash = None

    def __iter__(self):
        return iter(self._d)

    def __len__(self):
        return len(self._d)

    def __getitem__(self, key):
        return self._d[key]

    def __hash__(self):
        # It would have been simpler and maybe more obvious to 
        # use hash(tuple(sorted(self._d.iteritems()))) from this discussion
        # so far, but this solution is O(n). I don't know what kind of 
        # n we are going to run into, but sometimes it's hard to resist the 
        # urge to optimize when it will gain improved algorithmic performance.
        if self._hash is None:
            hash_ = 0
            for pair in self.items():
                hash_ ^= hash(pair)
            self._hash = hash_
        return self._hash

def deep_freeze(d):
    if isinstance(d, dict):
        return FrozenDict([(k, deep_freeze(v)) for k, v in d.items()])
    else:
        return d

vals = []
for filename in os.listdir("log"):
    log_path = os.path.join("log", filename, "log")
    if os.path.exists(log_path):
        with open(log_path) as f:
            j = json.load(f)
            vals.append(deep_freeze(j))
    else:
        print(f"Warning: {log_path} does not exists")

def report(x):
    print(f"mean: {np.mean(x)} std: {np.std(x)}")

bucket = {}
for x in vals:
    m = x["CFG"]["MEMORY_LIMIT"]
    if m not in bucket:
        bucket[m] = dict()
    cfg = x["CFG"]
    if cfg not in bucket[m]:
        bucket[m][cfg] = []
    bucket[m][cfg].append(x)

ms = list(bucket.keys())
ms.sort(reverse=True)

for m in ms:
    for cfg, vals in bucket[m].items():
        ok_vals = [x for x in vals if x["OK"]]
        assert(len(vals) > 0)
        print(f"With CFG {cfg}:")
        print(f"OOM rate: {1 - len(ok_vals) / len(vals)} size:{len(vals)}")
        if len(ok_vals) > 0:
            report([x["MAJOR_GC"] for x in ok_vals])
