import glob
import json
import os
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

def plot(m, benches, summarize_baseline=True):
    p = "Average(PhysicalMemory)"
    p = "Average(BalancerMemory)"
    p = "Average(SizeOfObjects)"

    coords = []

    for bench in benches:
        if BASELINE not in m[bench]:
            print("WARNING: BASELINE NOT FOUND")
            continue
        baseline_memorys = []
        baseline_times = []
        for score, name in m[bench][BASELINE]:
            if p not in score:
                print(score)
            memory = score[p]
            time = score["MAJOR_GC_TIME"]
            baseline_memorys.append(memory)
            baseline_times.append(time)
            if not summarize_baseline:
                coords.append(((memory, time), name))
        baseline_memory = sum(baseline_memorys) / len(baseline_memorys)
        baseline_time = sum(baseline_times) / len(baseline_times)
        if not summarize_baseline:
            plt.scatter(baseline_memorys, baseline_times, label="baseline")
        x = []
        y = []
        for balancer_cfg in m[bench]:
            if balancer_cfg != BASELINE:
                for score, name in m[bench][balancer_cfg]:
                    memory = score[p]
                    time = score["MAJOR_GC_TIME"]
                    if summarize_baseline:
                        memory /= baseline_memory
                        time /= baseline_time
                    x.append(memory)
                    y.append(time)
                    coords.append(((memory, time), name))
        plt.scatter(x, y, label=bench, linewidth=0.1)
    plt.xlabel(p)
    plt.ylabel("Time")
    if summarize_baseline:
        plt.scatter([1], [1], label="baseline", color="black")
    plt.legend()
    return coords

if __name__ == "__main__":
    m = anal_log()
    plot(m, m.keys())
    plt.show()
