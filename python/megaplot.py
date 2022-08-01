import glob
import json
import os
import collections
import matplotlib.pyplot as plt
import numpy as np
from scipy import stats
from util import FrozenDict, deep_freeze
from anal_common import *

BASELINE = deep_freeze({'BALANCE_STRATEGY': 'ignore', 'RESIZE_CFG': {'RESIZE_STRATEGY': 'ignore'}, 'BALANCE_FREQUENCY': 0})

def anal_log(path):
    data = []

    for name in glob.glob(f'{path}/**/score', recursive=True):
        dirname = os.path.dirname(name)
        r = Run(dirname)
        if r.ok():
            data.append(r)

    m = {}

    for r in data:
        k = deep_freeze(r.cfg["CFG"]["BENCH"])
        if k not in m:
            m[k] = {}
        k_k = deep_freeze(r.cfg["CFG"]["BALANCER_CFG"])
        if k_k not in m[k]:
            m[k][k_k] = []
        m[k][k_k].append(r)

    return m

class Point:
    # todo: remove is_baseline. the info is in cfg.
    def __init__(self, memory, time, cfg, exp, is_baseline):
        self.memory = memory
        self.time = time
        self.cfg = cfg
        self.exp = exp
        self.is_baseline = is_baseline
    def __repr__(self):
        return f"Point{repr((self.memory, self.time, self.exp, self.is_baseline))}"

def hack(name):
    table = {"browseri": "Browser one-tab experiment",
            "browserii": "Browser two-tab experiment",
            "browseriii": "Browser three-tab experiment",
            "jetstream": "Jetstream2 experiment",
            "acdc": "ACDC-JS experiment"}
    nl = name.lower()
    if nl in table:
        return table[nl]
    else:
        return name

def plot(m, benches, name, *, summarize_baseline=True, reciprocal_regression=True, legend=True):
    plt.title(hack(name))
    # todo: fix for other path
    plt.xlabel('Memory consumption (relative to current v8)')
    plt.ylabel('Time taken (relative to current v8)' if reciprocal_regression else 'Speedup (relative to current v8)')
    if summarize_baseline:
        plt.axhline(y=1, color='k', lw=1, linestyle='-')
        plt.axvline(x=1, color='k', lw=1, linestyle='-')
    ret = {}

    points = []
    transformed_points = []

    for bench in benches:
        if summarize_baseline:
            if BASELINE not in m[bench]:
                print("WARNING: BASELINE NOT FOUND")
                continue
            baseline_memorys = []
            baseline_times = []
            for exp in m[bench][BASELINE]:
                memory = exp.average_benchmark_memory()
                memory /= 1e6
                time = exp.total_major_gc_time()
                time /= 1e9
                baseline_memorys.append(memory)
                baseline_times.append(time)
            baseline_memory = sum(baseline_memorys) / len(baseline_memorys)
            baseline_time = sum(baseline_times) / len(baseline_times)
            ret["baseline_memory"] = baseline_memory
            ret["baseline_time"] = baseline_time
        x = []
        y = []
        baseline_x = []
        baseline_y = []
        for balancer_cfg in m[bench]:
            if not summarize_baseline or balancer_cfg != BASELINE:
                for exp in m[bench][balancer_cfg]:
                    memory = exp.average_benchmark_memory()
                    memory /= 1e6
                    time = exp.total_major_gc_time()
                    time /= 1e9
                    if summarize_baseline:
                        memory /= baseline_memory
                        time /= baseline_time
                    if balancer_cfg != BASELINE:
                        x.append(memory)
                        y.append(time)
                    else:
                        baseline_x.append(memory)
                        baseline_y.append(time)
                    points.append(Point(memory, time, balancer_cfg, exp, balancer_cfg == BASELINE))
                    transformed_points.append(Point(1 / memory, 1 / time, balancer_cfg, exp, balancer_cfg == BASELINE))
        plt.scatter(x, y, label=bench, linewidth=0.1, s=20)
        xmin = min(*x)
        xmax = max(*x)
        ymin = min(*y)
        ymax = max(*y)
        if len(baseline_x) != 0:
            plt.scatter(baseline_x, baseline_y, label=bench, linewidth=0.1, color="orange", s=35)
            xmin = min(xmin, min(*baseline_x))
            xmax = max(xmax, max(*baseline_x))
            ymin = min(ymin, min(*baseline_y))
            ymax = max(ymax, max(*baseline_y))
        xmargin = (xmax - xmin) * 0.05
        ymargin = (ymax - ymin) * 0.05
        plt.xlim([xmin - xmargin, xmax + xmargin])
        plt.ylim([ymin - ymargin, ymax + ymargin])
    ret["points"] = points
    ret["transformed_points"] = transformed_points
    if legend:
        plt.xlabel("AverageBenchmarkMemory")
        plt.ylabel("Time")
    if reciprocal_regression and len(points) > 0:
        x = []
        y = []
        # include baseline
        memory = []
        time = []
        for p in transformed_points:
            if not p.is_baseline:
                x.append(p.memory)
                y.append(p.time)
            memory.append(p.memory)
            time.append(p.time)
        if len(x) > 0:
            min_memory = min(*memory) if len(memory) > 1 else memory[0]
            max_memory = max(*memory) if len(memory) > 1 else memory[0]
            coef = np.polyfit(x, y, 1)
            poly1d_fn = np.poly1d(coef)
            sd = sum((poly1d_fn(x) - y) ** 2) ** 0.5 / (len(y) - 1) ** 0.5
            se = sd / len(y) ** 0.5
            ret["coef"] = coef
            ret["sd"] = sd
            ret["se"] = se
            ci_x = np.linspace(min_memory, max_memory, 100)
            ci_y = 1 / poly1d_fn(ci_x)
            plt.plot(1 / ci_x, ci_y, color='b')
            for ci_xx in ci_x:
                assert poly1d_fn(ci_xx) > 2*se
            plt.fill_between(1 / ci_x, (1 / (poly1d_fn(ci_x) - 2*se)), (1 / (poly1d_fn(ci_x) + 2*se)), color='b', alpha=.1)
    if legend:
        plt.legend(bbox_to_anchor=(1.04, 0.5), loc="center left")
    return ret

if __name__ == "__main__":
    m = anal_log("log/")
    plot(m, m.keys())
    plt.show()
