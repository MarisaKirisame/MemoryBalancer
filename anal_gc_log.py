import os
import sys
from pathlib import Path
import json
import matplotlib.pyplot as plt

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
                ret_l.append((lx, old_ly + interpol((old_rx, old_ry), (rx, ry), lx)))
            else:
                r = r[1:]
                len_r -= 1
                old_rx = rx
                old_ry = ry
                ret_r.append((rx, old_ry + interpol((old_lx, old_ly), (lx, ly), rx)))

def merge(l, r):
    if len(l) == 0:
        return r
    elif len(r) == 0:
        return l
    else:
        lx, ly = l[0]
        rx, ry = r[0]
        if lx < rx:
            return [(lx, ly)] + merge(l[1:], r)
        else:
            return [(rx, ry)] + merge(l, r[1:])

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
        self.memory = []
        self.working_memory = []
        self.gc_line_low = []
        self.gc_line_high = []

    def point(self, time, working_memory, memory, gc_trigger):
        self.memory.append((time, memory))
        self.working_memory.append((time, working_memory))
        if gc_trigger:
            self.gc_line_low.append((time, 0))
            self.gc_line_high.append((time, memory))

    def draw(self, baseline):
        memory = stack(baseline, self.memory)
        p = plt.plot([x for x, y in memory], [y for x, y in memory], label=self.name)
        working_memory = stack(baseline, self.working_memory)
        plt.fill_between([x for x, y in working_memory], [y for x, y in working_memory],  [y for x, y in stack(baseline, [(x, 0) for x, y in self.memory])], color=p[0].get_color())
        plt.plot([x for x, y in working_memory], [y for x, y in working_memory], color=p[0].get_color())
        gc_line_low = stack_unmerged(baseline, self.gc_line_low)[1]
        gc_line_high = stack_unmerged(baseline, self.gc_line_high)[1]
        assert len(gc_line_low) == len(gc_line_high)
        for (x_low, y_low), (x_high, y_high) in zip(gc_line_low, gc_line_high):
            assert x_low == x_high
            plt.vlines(x_low, ymin=y_low, ymax=y_high, color="black", linestyle="--")

    def stack(self, baseline):
        return stack(baseline, self.memory)

def main(directory):
    memory_msg_logs = []

    logs = []
    with open(directory + "balancer_log") as f:
        for line in f.readlines():
            j = json.loads(line)
            if j["type"] == "memory-msg":
                memory_msg_logs.append(j["data"])
            if j["type"] == "heap-stat":
                logs.append(j["data"])
                if j["data"]["msg-type"] == "close":
                    memory_msg_logs.append(j["data"])

    with open(directory + "cfg") as f:
        title = eval(f.read())["BALANCER_CFG"]

    print(f"{len(logs)} point in total")
    assert all(logs[i]["time"] <= logs[i+1]["time"] for i in range(len(logs)-1))

    instance_map = {}
    instance_list = []

    for l in logs:
        name = l["name"]
        time = l["time"]
        working_memory = l["working-memory"]
        memory = l["max-memory"]
        if name not in instance_map:
            x = Process(name)
            instance_map[name] = x
            instance_list.append(x)
        gc_trigger = l["msg-type"] == "major_gc"
        instance_map[name].point(time, working_memory, memory, gc_trigger)

    draw_stacks(instance_list)
    plt.legend()
    plt.title(title)

if __name__ == "__main__":
    assert(len(sys.argv) == 2)
    main(sys.argv[1])
    plt.show()
