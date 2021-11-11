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
    def __init__(self, name=None):
        self.name = name
        self.xs = []
        self.ys = []

    def point(self, x, y):
        self.xs.append(x)
        self.ys.append(y)

    def plot(self, color=None):
        return plt.plot(self.xs, self.ys, label=self.name, color=color)

class EvalLine:
    def __init__(self, name, plot_std):
        self.plot_std = plot_std
        if not self.plot_std:
            self.line = Line(name)
        else:
            self.low_line = Line(name)
            self.high_line = Line()

    def point(self, x, y):
        if not self.plot_std:
            self.line.point(x, np.mean(y))
        else:
            m = np.mean(y)
            s = np.std(y)
            self.low_line.point(x, m - s)
            self.high_line.point(x, m + s)

    def plot(self):
        if not self.plot_std:
            return self.line.plot()
        else:
            ll = self.low_line.plot()[0]
            rr = self.high_line.plot(ll.get_color())[0]
            return (ll, rr)

vals = []
for filename in os.listdir("log"):
    log_path = os.path.join("log", filename, "score")
    if os.path.exists(log_path):
        with open(log_path) as f:
            j = json.load(f)
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
            major_gc = [x["MAJOR_GC"] for x in ok_vals]
            report("major gc time", major_gc)
            report("balancer efficiency", [x["BALANCER_EFFICIENCY"] for x in ok_vals])
            balancer_cfg = cfg["BALANCER_CFG"]
            if balancer_cfg not in lines:
                lines[balancer_cfg] = EvalLine(balancer_cfg, PLOT_STD)
            lines[balancer_cfg].point(m, major_gc)

for l in lines.values():
    l.plot()
plt.legend()
plt.show()
