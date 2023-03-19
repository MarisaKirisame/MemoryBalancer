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

def plot(m, benches, name, *, show_baseline=True, normalize_baseline=True, reciprocal_regression=True, legend=True, invert_graph=False):
    plt.title(hack(name))
    # todo: fix for other path
    rel = "relative to current v8"
    if invert_graph:
        plt.xlabel(f'Speedup {rel}')
        plt.ylabel(f'Memory Saving {rel}')
    else:
        plt.xlabel(f'Average heap usage ({rel if normalize_baseline else "MB"})')
        plt.ylabel(f'Garbage collection time ({rel if normalize_baseline else "s"})')
    if normalize_baseline:
        plt.axhline(y=1, color='k', lw=1, linestyle='-')
        plt.axvline(x=1, color='k', lw=1, linestyle='-')
    ret = {}

    points = []
    transformed_points = []
    xmins = []
    xmaxs = []
    ymins = []
    ymaxs = []
    for bench in benches:
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
        x_yg = []
        y_yg = []
        baseline_x = []
        baseline_y = []
        for balancer_cfg in m[bench]:
            if show_baseline or balancer_cfg != BASELINE:
                for exp in m[bench][balancer_cfg]:
                    memory = exp.average_benchmark_memory()
                    memory /= 1e6
                    time = exp.total_major_gc_time()
                    time /= 1e9
                    if normalize_baseline:
                        memory /= baseline_memory
                        time /= baseline_time
                    if balancer_cfg != BASELINE:
                        if balancer_cfg["BALANCE_STRATEGY"] == "YG_BALANCER":
                            x_yg.append(memory)
                            y_yg.append(time)
                        elif balancer_cfg["BALANCE_STRATEGY"] == "classic":
                            x.append(memory)
                            y.append(time)
                    else:
                        baseline_x.append(memory)
                        baseline_y.append(time)
                    points.append(Point(memory, time, balancer_cfg, exp, balancer_cfg == BASELINE))
                    transformed_points.append(Point(1 / memory, 1 / time, balancer_cfg, exp, balancer_cfg == BASELINE))
        if invert_graph:
            plt.scatter([1/x_ for x_ in x], [1/y_ for y_ in y], label=bench, linewidth=0.1, s=20)
            plt.scatter([1/x_ for x_ in x_yg], [1/y_ for y_ in y_yg], label=bench, color="red", linewidth=0.1, s=20)
            if len(baseline_x) != 0:
                plt.scatter([1/x_ for x_ in baseline_x], [1/y_ for y_ in baseline_y], label=bench, linewidth=0.1, color="black", s=35)
        else:
            plt.scatter(x, y, label=bench, linewidth=0.1, s=20)
            plt.scatter(x_yg, y_yg, label=bench, linewidth=0.1, s=20, color="red")
            if len(baseline_x) != 0:
                plt.scatter(baseline_x, baseline_y, label=bench, linewidth=0.1, color="black", s=35)
        xmins.append(min(*x, *baseline_x))
        xmaxs.append(max(*x, *baseline_x))
        ymins.append(min(*y, *baseline_y))
        ymaxs.append(max(*y, *baseline_y))
    ret["points"] = points
    ret["transformed_points"] = transformed_points
    x = list([p.memory for p in transformed_points if not p.is_baseline])
    y = list([p.time for p in transformed_points if not p.is_baseline])
    if len(x) > 0:
        coef = np.polyfit(x, y, 1)
        poly1d_fn = np.poly1d(coef)
        sd = sum((poly1d_fn(x) - y) ** 2) ** 0.5 / (len(y) - 1) ** 0.5
        se = sd / len(y) ** 0.5
        ret["coef"] = coef
        ret["sd"] = sd
        ret["se"] = se
        if reciprocal_regression:
            ci_x = np.linspace(min(transformed_points, key=lambda p: p.memory).memory,
                               max(transformed_points, key=lambda p: p.memory).memory,
                               100)
            ci_y = poly1d_fn(ci_x)
            if invert_graph:
                plt.plot(ci_x, ci_y, color='b')
                plt.fill_between(ci_x, (poly1d_fn(ci_x) - 2*se), (poly1d_fn(ci_x) + 2*se), color='b', alpha=.1)
            else:
                plt.plot(1 / ci_x, 1 / np.maximum(ci_y, 0), color='b')
                plt.fill_between(1 / ci_x, (1 / np.maximum((poly1d_fn(ci_x) - 2*se), 0)), (1 / np.maximum((poly1d_fn(ci_x) + 2*se), 0)), color='b', alpha=.1)
    if legend:
        plt.legend(bbox_to_anchor=(1.04, 0.5), loc="center left")
    if len(xmins) != 0:
        xmin = min(xmins)
        xmax = max(xmaxs)
        ymin = min(ymins)
        ymax = max(ymaxs)
        xmargin = (xmax - xmin) * 0.05
        ymargin = (ymax - ymin) * 0.05
        if not invert_graph:
            plt.xlim([xmin - xmargin, xmax + xmargin])
            plt.ylim([ymin - ymargin, ymax + ymargin])
    return ret

if __name__ == "__main__":
    m = anal_log("log/")
    plot(m, m.keys())
    plt.show()
