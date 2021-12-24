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

class Data:
    def __init__(self, name):
        self.name = name
        self.xs = []
        self.ys = []
        self.y_errs = []
        self.y_es = []
        self.oom_rates = []
    def point(self, x, y, y_err, y_e, oom_rate):
        self.xs.append(x)
        self.ys.append(y)
        self.y_errs.append(y_err)
        self.y_es.append(y_e)
        self.oom_rates.append(oom_rate)
    def plot(self):
        #descending
        split_i = 0
        for i in range(len(self.xs)):
            if self.oom_rates[i] < 0.5:
                split_i = i + 1
        x = plt.errorbar(self.xs[:split_i], self.ys[:split_i], self.y_errs[:split_i], label=self.name)
        if split_i > 0:
            plt.errorbar(self.xs[split_i-1:], self.ys[split_i-1:], self.y_errs[split_i-1:], ls="--", color=x[0].get_color())
        #plt.plot(self.xs, self.y_es, label=f"{self.name} / E")

def parse_log():
    ret = []
    for filename in os.listdir("log"):
        score_path = os.path.join("log", filename, "score")
        cfg_path = os.path.join("log", filename, "cfg")
        if os.path.exists(score_path):
            with open(score_path) as f:
                score = json.load(f)
            with open(cfg_path) as f:
                cfg = json.load(f)
            ret.append((deep_freeze(score), deep_freeze(cfg)))
        else:
            print(f"Warning: {score_path} does not exists")
    return ret

def report(name, x):
    print(f"{name} mean: {np.mean(x)} std: {np.std(x)}")

def old_plot():
    bucket = {}
    for x, cfg in parse_log():
        if cfg["BALANCER_CFG"]["RESIZE_CFG"]["RESIZE_STRATEGY"] != "ignore":
            pass
        m = cfg["MEMORY_LIMIT"]
        if m not in bucket:
            bucket[m] = dict()
        if cfg not in bucket[m]:
            bucket[m][cfg] = []
        bucket[m][cfg].append(x)

    ms = list(bucket.keys())
    ms.sort(reverse=True)

    data = {}

    PLOT_STD = True

    for m in ms:
        for cfg, vals in bucket[m].items():
            assert(len(vals) > 0)
            ok_vals = [x for x in vals if x["OK"]]
            print(f"With CFG {cfg}:")
            oom_rate = 1 - len(ok_vals) / len(vals)
            print(f"OOM rate: {oom_rate} size:{len(vals)}")
            if len(ok_vals) > 0:
                #major_gc = list([x["MAJOR_GC"] for x in ok_vals])
                #major_gc = list([x["EXTRA_TIME"] for x in ok_vals])
                major_gc = list([x["TOTAL_TIME"] for x in ok_vals])
                balancer_efficiency = list([x["BALANCER_EFFICIENCY"] for x in ok_vals])
                report("major gc time", major_gc)
                report("balancer efficiency", balancer_efficiency)
                balancer_cfg = cfg["BALANCER_CFG"]
                if balancer_cfg not in data:
                    data[balancer_cfg] = Data(balancer_cfg)
                data[balancer_cfg].point(m, np.mean(major_gc), np.std(major_gc), np.mean([x["TOTAL_TIME"] / x["BALANCER_EFFICIENCY"] for x in ok_vals]), oom_rate)
    for d in data.values():
        d.plot()
    plt.legend()
    plt.show()

def new_plot():
    bucket = {}
    for x, cfg in parse_log():
        balancer_cfg = cfg["BALANCER_CFG"]
        if balancer_cfg not in bucket:
            bucket[balancer_cfg] = []
        bucket[balancer_cfg].append(x)

    for cfg, vals in bucket.items():
        assert(len(vals) > 0)
        ok_vals = [x for x in vals if x["OK"]]
        if len(ok_vals) > 0:
            x = list([x["PEAK_MEMORY"] for x in ok_vals])
            y = list([x["TOTAL_TIME"] for x in ok_vals])
            #y = list([x["TOTAL_MAJOR_GC_TIME"] for x in ok_vals])
            #y = list([x["TOTAL_TIME"] - x["TOTAL_MAJOR_GC_TIME"] for x in ok_vals])
            plt.scatter(x, y, label=cfg)
    plt.legend()
    plt.show()

new_plot()
