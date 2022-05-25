import os
import sys
from pathlib import Path
import json
import numpy as np
import collections
import matplotlib.pyplot as plt
from util import FrozenDict, deep_freeze
from anal_common import parse_log

def plot():
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
            #x = list([x["PEAK_MEMORY"] for x in ok_vals])
            x = list([x["PEAK_HEAP_MEMORY"] for x in ok_vals])
            #x = list([x["AVERAGE_HEAP_MEMORY"] for x in ok_vals])
            #y = list([x["TOTAL_TIME"] for x in ok_vals])
            y = list([x["MAJOR_GC_TIME"] for x in ok_vals])
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
