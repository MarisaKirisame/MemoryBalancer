import os
import sys
from pathlib import Path
import json
import matplotlib.pyplot as plt

assert(len(sys.argv) == 2)
directory = sys.argv[1]

logs = []
with open(directory + "v8_log") as f:
    for line in f.readlines():
        j = json.loads(line)
        if j["type"] == "heap-stat":
            logs.append(j["data"])
with open(directory + "cfg") as f:
    title = f.read()
with open(directory + "score") as f:
    j = json.load(f)
    if j["OK"] == False:
        title = f"OOM: {title}"

assert all(logs[i]["time"] <= logs[i+1]["time"] for i in range(len(logs)-1))

# alas, can not write in functional style even though it is cleaner, due to python efficiency concern.
def stack(l, r):
    len_l = len(l)
    len_r = len(r)
    old_ly = 0
    old_ry = 0
    ret = []
    while True:
        if len_l == 0:
            return ret + [(x, y + old_ly) for x, y in r]
        elif len_r == 0:
            return ret + [(x, y + old_ry) for x, y in l]
        else:
            assert len_l > 0 and len_r > 0
            (lx, ly) = l[0]
            (rx, ry) = r[0]
            if lx < rx:
                l = l[1:]
                len_l -= 1
                old_ly = ly
                ret.append((lx, old_ly + old_ry))
            else:
                r = r[1:]
                len_r -= 1
                old_ry = ry
                ret.append((rx, old_ly + old_ry))

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
        self.l = []
    def point(self, time, memory):
        self.l.append((time, memory))
    def draw(self, baseline):
        l = stack(baseline, self.l)
        plt.plot([x for x, y in l], [y for x, y in l], label=self.name)
    def stack(self, baseline):
        return stack(baseline, self.l)

instance_map = {}
instance_list = []

for l in logs:
    name = l["name"]
    time = l["time"]
    memory = l["max-memory"]
    if name not in instance_map:
        x = Process(name)
        instance_map[name] = x
        instance_list.append(x)
    instance_map[name].point(time, memory)

draw_stacks(instance_list)

plt.legend()
plt.title(title)
plt.show()
