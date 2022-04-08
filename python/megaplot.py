import glob
import json
import os
import collections
import matplotlib.pyplot as plt
import numpy as np
from scipy import stats

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
    elif isinstance(d, list):
        return tuple(d)
    else:
        return d

def filter_warn(x):
    score, cfg, name = x
    if score["MAJOR_GC_TIME"] == 0:
        print("WARNING: MAJOR_GC_TIME == 0 FOUND, FILTERING")
        return False
    else:
        return True

BASELINE = deep_freeze({'BALANCE_STRATEGY': 'ignore', 'RESIZE_CFG': {'RESIZE_STRATEGY': 'ignore'}, 'BALANCE_FREQUENCY': 0})

def anal_log():
    data = []

    for name in glob.glob('log/**/score', recursive=True):
        dirname = os.path.dirname(name)
        with open(dirname + "/score") as f:
            score = json.load(f)
        with open(dirname + "/cfg") as f:
            cfg = eval(f.read())
        data.append((score, cfg, name))

    data = [x for x in data if   filter_warn(x)]

    m = {}

    for d in data:
        k = deep_freeze(d[1]["BENCH"])
        if k not in m:
            m[k] = {}
        k_k = deep_freeze(d[1]["BALANCER_CFG"])
        if k_k not in m[k]:
            m[k][k_k] = []
        m[k][k_k].append((d[0], d[2]))

    return m

class Point:
    def __init__(self, memory, time, name, is_baseline):
        self.memory = memory
        self.time = time
        self.name = name
        self.is_baseline = is_baseline
    def __repr__(self):
        return f"Point{repr((self.memory, self.time, self.name, self.is_baseline))}"

def plot(m, benches, *, summarize_baseline=True, reciprocal_regression=True):
    
    if summarize_baseline:
        plt.axhline(y=1, color='k', lw=1, linestyle='-')
        plt.axvline(x=1, color='k', lw=1, linestyle='-')
    

    ret = {}
    p = "Average(PhysicalMemory)"
    p = "Average(BalancerMemory)"
    p = "Average(SizeOfObjects)"
    p = "Average(BenchmarkMemory)"

    points = []

    for bench in benches:
        if summarize_baseline:
            if BASELINE not in m[bench]:
                print("WARNING: BASELINE NOT FOUND")
                continue
            baseline_memorys = []
            baseline_times = []
            for score, name in m[bench][BASELINE]:
                if p not in score:
                    print(score)
                memory = score[p]
                memory /= 1e6
                time = score["MAJOR_GC_TIME"]
                time /= 1e9
                baseline_memorys.append(memory)
                baseline_times.append(time)
                baseline_memory = sum(baseline_memorys) / len(baseline_memorys)
                baseline_time = sum(baseline_times) / len(baseline_times)
        x = []
        y = []
        baseline_x = []
        baseline_y = []
        for balancer_cfg in m[bench]:
            if not summarize_baseline or balancer_cfg != BASELINE:
                for score, name in m[bench][balancer_cfg]:
                    if p not in score:
                        print(score)
                    memory = score[p]
                    memory /= 1e6
                    time = score["MAJOR_GC_TIME"]
                    time /= 1e9
                    if summarize_baseline:
                        memory /= baseline_memory
                        time /= baseline_time
                    if reciprocal_regression:
                        time = 1 / time
                    if balancer_cfg != BASELINE:
                        x.append(memory)
                        y.append(time)
                    else:
                        baseline_x.append(memory)
                        baseline_y.append(time)
                    points.append(Point(memory, time, name, balancer_cfg == BASELINE))
        plt.scatter(x, y, label=bench, linewidth=0.1, s=20)
        if len(baseline_x) != 0:
            plt.scatter(baseline_x, baseline_y, label=bench, linewidth=0.1, color="orange", s=35)
    ret["points"] = points
    plt.xlabel(p)
    if reciprocal_regression:
        plt.ylabel("Inversed time")
    else:
        plt.ylabel("Time")
    if reciprocal_regression and len(points) > 0:
        x = []
        y = []
        # include baseline
        memory = []
        time = []
        for p in points:
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
            ci_x = [min_memory, max_memory]
            ci_y = poly1d_fn([min_memory, max_memory])
            plt.plot(ci_x, ci_y, "k", color='b')
            plt.fill_between(ci_x, (ci_y-2*se), (ci_y+2*se), color='b', alpha=.1)
    plt.legend(bbox_to_anchor=(1.04, 0.5), loc="center left")
    return ret

if __name__ == "__main__":
    m = anal_log()
    plot(m, m.keys())
    plt.show()
