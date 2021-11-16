import os
import sys
from pathlib import Path
import json
import numpy as np
import collections
import matplotlib.pyplot as plt

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

class Line:
    def __init__(self, plot_std, name=None):
        self.plot_std = plot_std
        self.name = name
        self.xs = []
        self.ys = []
        if self.plot_std:
            self.errs = []

    def point(self, x, y, err=None):
        self.xs.append(x)
        self.ys.append(y)
        if self.plot_std:
            assert err is not None
            self.errs.append(err)

    def plot(self):
        if self.plot_std:
            return plt.errorbar(self.xs, self.ys, self.errs, label=self.name)
        else:
            return plt.plot(self.xs, self.ys, label=self.name)

vals = []
for filename in os.listdir("log"):
    log_path = os.path.join("log", filename, "score")
    if os.path.exists(log_path):
        with open(log_path) as f:
            j = json.load(f)
            balancer_cfg = j["CFG"]["BALANCER_CFG"]
            if (not balancer_cfg["SEND_MSG"]) or balancer_cfg["BALANCE_FREQUENCY"] < 200:
                vals.append(deep_freeze(j))
    else:
        print(f"Warning: {log_path} does not exists")

def report(name, x):
    print(f"{name} mean: {np.mean(x)} std: {np.std(x)}")

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

lines = {}

PLOT_STD = True

for m in ms:
    for cfg, vals in bucket[m].items():
        ok_vals = [x for x in vals if x["OK"]]
        assert(len(vals) > 0)
        print(f"With CFG {cfg}:")
        print(f"OOM rate: {1 - len(ok_vals) / len(vals)} size:{len(vals)}")
        if len(ok_vals) > 0:
            major_gc = list([x["MAJOR_GC"] for x in ok_vals])
            balancer_efficiency = list([x["BALANCER_EFFICIENCY"] for x in ok_vals])
            report("major gc time", major_gc)
            report("balancer efficiency", balancer_efficiency)
            balancer_cfg = cfg["BALANCER_CFG"]
            if balancer_cfg not in lines:
                lines[balancer_cfg] = (Line(PLOT_STD, balancer_cfg), Line(False, f"{balancer_cfg} / E"))
            lines[balancer_cfg][0].point(m, np.mean(major_gc), np.std(major_gc))
            lines[balancer_cfg][1].point(m, np.mean([x["MAJOR_GC"] / x["BALANCER_EFFICIENCY"] for x in ok_vals]))

for l in lines.values():
    l[0].plot()
    l[1].plot()
plt.legend()
plt.show()
