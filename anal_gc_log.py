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

class Stacked:
    pass

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

instance_map = {}
instance_list = []
xs = []
ragged_ys = []

class Instance:
    def __init__(self, name):
        self.name = name
        self.memory = 0
    def point(self, time, memory):
        self.memory = memory
        xs.append(time)
        y = []
        memory = 0
        for i in instance_list:
            memory += i.memory
            y.append(memory)
        ragged_ys.append(y)

new_map = {}
new_list = []

for l in logs:
    name = l["name"]
    time = l["time"]
    memory = l["max-memory"]
    if name not in instance_map:
        i = Instance(name)
        instance_map[name] = i
        instance_list.append(i)
    instance_map[name].point(time, memory)
    if name not in new_map:
        x = []
        new_map[name] = x
        new_list.append(x)
    new_map[name].append((time, memory))

l = 0
for ragged_y in ragged_ys:
    l = max(l, len(ragged_y))

ys = []

for ragged_y in ragged_ys:
    ys.append(ragged_y + (l - len(ragged_y)) * [ragged_y[-1]])

old = []

ps = []
for l in new_list:
    p = stack(old, l)
    ps.append(p)
    old = p

i = 0
ps.reverse()
for p in ps:
    plt.plot([x for x, y in p], [y for x, y in p], label=i)
    i += 1

plt.legend()
plt.title(title)
plt.show()
