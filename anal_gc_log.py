import os
import sys
from pathlib import Path
import json
import matplotlib.pyplot as plt

assert(len(sys.argv) == 2)
directory = sys.argv[1]

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
#with open(directory + "score") as f:
#    j = json.load(f)
#    if j["OK"] == False:
#        title = f"OOM: {title}"

print(f"{len(logs)} point in total")
assert all(logs[i]["time"] <= logs[i+1]["time"] for i in range(len(logs)-1))

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
    old_rx = 0
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
                old_lx = lx
                old_ly = ly
                ret.append((lx, old_ly + interpol((old_rx, old_ry), (rx, ry), lx)))
            else:
                r = r[1:]
                len_r -= 1
                old_rx = rx
                old_ry = ry
                ret.append((rx, interpol((old_lx, old_ly), (lx, ly), rx) + old_ry))

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
    def point(self, time, working_memory, memory):
        self.memory.append((time, memory))
        self.working_memory.append((time, working_memory))
    def draw(self, baseline):
        memory = stack(baseline, self.memory)
        p = plt.plot([x for x, y in memory], [y for x, y in memory], label=self.name)
        working_memory = stack(baseline, self.working_memory)
        plt.fill_between([x for x, y in working_memory], [y for x, y in working_memory],  [y for x, y in stack(baseline, [(x, 0) for x, y in self.memory])], color=p[0].get_color())
        plt.plot([x for x, y in working_memory], [y for x, y in working_memory], color=p[0].get_color())
    def stack(self, baseline):
        return stack(baseline, self.memory)

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
    instance_map[name].point(time, working_memory, memory)
#for l in memory_msg_logs:
#    name = l["name"]
#    time = l["time"]
#    working_memory = l["working-memory"]
#    memory = l["max-memory"]
#    if name not in instance_map:
#        x = Process(name)
#        instance_map[name] = x
#        instance_list.append(x)
#    instance_map[name].point(time, working_memory, memory)
#draw_stacks([instance_list[3], instance_list[5]])
draw_stacks(instance_list)

plt.legend()
plt.title(title)
plt.show()
