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

# alas, can not write in functional style even though it is cleaner, due to python efficiency concern.
def stack(l, r):
    len_l = len(l)
    len_r = len(r)
    old_lx = 0
    old_ly = 0
    old_lz = 0
    old_rx = 0
    old_ry = 0
    old_rz = 0
    ret = []
    while True:
        if len_l == 0:
            return ret + [(x, y + old_ly, z) for x, y, z in r]
        elif len_r == 0:
            return ret + [(x, y + old_ry, z) for x, y, z in l]
        else:
            assert len_l > 0 and len_r > 0
            (lx, ly, lz) = l[0]
            (rx, ry, rz) = r[0]
            if lx < rx:
                l = l[1:]
                len_l -= 1
                old_lx = lx
                old_ly = ly
                old_lz = lz
                ret.append((lx, old_ly + interpol((old_rx, old_ry), (rx, ry), lx), lz))
            else:
                r = r[1:]
                len_r -= 1
                old_rx = rx
                old_ry = ry
                old_rz = rz
                ret.append((rx, interpol((old_lx, old_ly), (lx, ly), rx) + old_ry, rz))

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

    def point(self, time, working_memory, memory, gc_trigger):
        self.memory.append((time, memory, gc_trigger))
        self.working_memory.append((time, working_memory, gc_trigger))

    def draw(self, baseline):
        memory = stack(baseline, self.memory)
        p = plt.plot([x for x, y, z in memory], [y for x, y, z in memory], label=self.name)
        working_memory = stack(baseline, self.working_memory)
        plt.fill_between([x for x, y, z in working_memory], [y for x, y, z in working_memory],  [y for x, y, z in stack(baseline, [(x, 0, z) for x, y, z in self.memory])], color=p[0].get_color())
        plt.plot([x for x, y, z in working_memory], [y for x, y, z in working_memory], color=p[0].get_color())

        for (index, obj) in enumerate(memory):
            (time, mem, is_trigger) = obj
            (work_t, work_mem, is_trigger) = working_memory[index]
            if is_trigger:
                plt.vlines(time, ymin=work_mem, ymax=mem, color='black', linestyle= '--')

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

    print(len(logs))

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
        gc_trigger = False
        if l["msg-type"] == "major_gc":
            gc_trigger = True
        instance_map[name].point(time, working_memory, memory, gc_trigger)

    draw_stacks(instance_list)
    plt.legend()
    plt.title(title)

if __name__ == "__main__":
    assert(len(sys.argv) == 2)
    main(sys.argv[1])
    plt.show()
