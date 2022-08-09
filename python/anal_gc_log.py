import os
import sys
from pathlib import Path
import json
import matplotlib.pyplot as plt
from anal_common import *
import glob

def interpol(pl, pr, x):
    plx, ply = pl
    prx, pry = pr
    pr_percent = (x - plx) / (prx - plx)
    return (1 - pr_percent) * ply + pr_percent * pry

def stack_unmerged(l, r):
    len_l = len(l)
    len_r = len(r)
    old_lx = 0
    old_ly = 0
    old_lz = 0
    old_rx = 0
    old_ry = 0
    old_rz = 0
    ret_l = []
    ret_r = []
    while True:
        if len_l == 0:
            return (ret_l, ret_r + [(x, y + old_ly) for x, y in r])
        elif len_r == 0:
            return (ret_l + [(x, y + old_ry) for x, y in l], ret_r)
        else:
            assert len_l > 0 and len_r > 0
            (lx, ly) = l[0]
            (rx, ry) = r[0]
            if lx < rx:
                l = l[1:]
                len_l -= 1
                old_lx = lx
                old_ly = ly
                if len(ret_r) == 0:
                    ret_l.append((lx, ly))
                else:
                    ret_l.append((lx, ly + interpol((old_rx, old_ry), (rx, ry), lx)))
            else:
                r = r[1:]
                len_r -= 1
                old_rx = rx
                old_ry = ry
                if len(ret_l) == 0:
                    ret_r.append((rx, ry))
                else:
                    ret_r.append((rx, ry + interpol((old_lx, old_ly), (lx, ly), rx)))

def merge(l, r):
    ret = []
    x = 0
    y = 0
    while True:
        if len(l) == x:
            return ret + r[y:]
        elif len(r) == y:
            return ret + l[x:]
        else:
            lx, ly = l[x]
            rx, ry = r[y]
            if lx < rx:
                x += 1
                ret.append((lx, ly))
            else:
                y += 1
                ret.append((rx, ry))

# alas, can not write in functional style even though it is cleaner, due to python efficiency concern.
def stack(l, r):
    return merge(*stack_unmerged(l, r))

class Stackable:
    def draw(self, baseline):
        raise NotImplementedError()

    # return a new baseline
    def stack(self, baseline):
        raise NotImplementedError()

def draw_stacks(stacks):
    def go(stacks, len_stacks, baseline):
        if len_stacks != 0:
            go(stacks[1:], len_stacks - 1, stacks[0].stack(baseline))
            stacks[0].draw(baseline)
    go(stacks, len(stacks), ())

class Process(Stackable):
    def __init__(self, name):
        self.name = name
        self.working_memory = []
        self.current_memory = []
        self.max_memory = []
        self.gc_line_low = []
        self.gc_line_high = []

    def point(self, time, working_memory, current_memory, max_memory, gc_trigger):
        self.working_memory.append((time, working_memory))
        self.current_memory.append((time, current_memory))
        self.max_memory.append((time, max_memory))
        if gc_trigger:
            self.gc_line_low.append((time, 0))
            self.gc_line_high.append((time, max_memory))

    def draw(self, baseline):
        max_memory = stack(baseline, self.max_memory)
        p = plt.plot([x for x, y in max_memory], [y for x, y in max_memory], label=self.name)
        current_memory = stack(baseline, self.current_memory)
        plt.fill_between([x for x, y in current_memory], [y for x, y in current_memory],  [y for x, y in stack(baseline, [(x, 0) for x, y in self.max_memory])], color=p[0].get_color(), alpha=0.5)
        working_memory = stack(baseline, self.working_memory)
        plt.fill_between([x for x, y in working_memory], [y for x, y in working_memory],  [y for x, y in stack(baseline, [(x, 0) for x, y in self.max_memory])], color=p[0].get_color())
        plt.plot([x for x, y in working_memory], [y for x, y in working_memory], color=p[0].get_color())
        gc_line_low = stack_unmerged(baseline, self.gc_line_low)[1]
        gc_line_high = stack_unmerged(baseline, self.gc_line_high)[1]
        assert len(gc_line_low) == len(gc_line_high)
        for (x_low, y_low), (x_high, y_high) in zip(gc_line_low, gc_line_high):
            assert x_low == x_high
            plt.vlines(x_low, ymin=y_low, ymax=y_high, color="black", zorder=100, linewidth=0.5)

    def stack(self, baseline):
        return stack(baseline, self.max_memory)

def remove_suffix(input_string, suffix):
    if suffix and input_string.endswith(suffix):
        return input_string[:-len(suffix)]
    return input_string

def main(cfg, exp, legend=True):
    instance_list = []

    title = str(cfg)
    for directory in exp.all_dirname():
        for gc_log_str in glob.glob(f'{directory}/*.gc.log'):
            memory_log_str = f"""{remove_suffix(gc_log_str, ".gc.log")}.memory.log"""
            jsons = []
            name = ""
            with open(gc_log_str) as f:
                for line in f.readlines():
                    j = json.loads(line)
                    j["type"] = "gc"
                    j["time"] = j["before_time"]
                    name = j["name"]
                    jsons.append(j)
            with open(memory_log_str) as f:
                for line in f.readlines():
                    j = json.loads(line)
                    j["type"] = "memory"
                    jsons.append(j)
            jsons.sort(key=lambda x:x["time"])
            x = Process(name)
            instance_list.append(x)
            working_memory = 0
            for j in jsons:
                if j["type"] == "gc" and not j["major"]:
                    pass
                elif j["type"] == "memory":
                    current_memory = j["AllocatedExternalMemorySinceMarkCompact"] + j["SizeOfObjects"]
                    max_memory = j["Limit"]
                    x.point(j["time"] / 1e9, working_memory / 1e6, current_memory / 1e6, max_memory / 1e6, False)
                else:
                    working_memory = j["after_memory"]
                    current_memory = working_memory
                    max_memory = j["Limit"]
                    x.point(j["time"] / 1e9, working_memory / 1e6, current_memory / 1e6, max_memory / 1e6, True)
            x.point((j["time"] + 1) / 1e9, 0, 0, 0, False)
    instance_list.sort(key=lambda x: x.name)
    draw_stacks(instance_list)
    if legend:
        plt.legend(bbox_to_anchor=(1.04, 0.5), loc="center left")
    plt.ylim([0, (exp.average_benchmark_memory() * 2.5)/1e6])

if __name__ == "__main__":
    assert(len(sys.argv) == 2)
    main(sys.argv[1])
    plt.show()
