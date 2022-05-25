import os
import sys
from pathlib import Path
import json
import numpy as np
import matplotlib.pyplot as plt
import random
from util import FrozenDict, deep_freeze
from anal_common import parse_log

def plot():
    bucket = {}
    for x, cfg in parse_log():
        balancer_cfg = cfg["BALANCER_CFG"]
        if balancer_cfg not in bucket:
            bucket[balancer_cfg] = []
        bucket[balancer_cfg].append(x)

    seen_cfg = list(bucket.keys())
    def sort_f(cfg):
        if cfg["BALANCE_STRATEGY"] == "ignore":
            return -1
        return cfg["RESIZE_CFG"]["GC_RATE"]
    seen_cfg.sort(key = sort_f)
    cfg_ordering = {}
    for cfg in seen_cfg:
        cfg_ordering[cfg] = len(cfg_ordering)
    def cfg_to_x(cfg):
        return cfg_ordering[cfg] + random.uniform(0, 1)

    for cfg, vals in bucket.items():
        assert(len(vals) > 0)
        ok_vals = [x for x in vals if x["OK"]]
        if len(ok_vals) > 0:
            x = list([cfg_to_x(cfg) for x in ok_vals])
            #y = list([x["TOTAL_TIME"] for x in ok_vals])
            #y = list([x["PEAK_HEAP_MEMORY"] for x in ok_vals])
            y = list([x["AVERAGE_HEAP_MEMORY"] for x in ok_vals])
            #y = list([x["MAJOR_GC_TIME"] for x in ok_vals])
            #y = list([x["TOTAL_TIME"] * 1000 - x["MAJOR_GC_TIME"] for x in ok_vals])
            if cfg["BALANCE_STRATEGY"] == "ignore":
                plt.scatter(x, y, label=cfg, color="black")
            elif cfg["BALANCE_STRATEGY"] == "extra-memory":
                plt.scatter(x, y, label=cfg, color="pink")
            else:
                plt.scatter(x, y, label=cfg)
    plt.legend()
    plt.show()

plot()
