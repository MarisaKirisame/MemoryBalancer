import json
import matplotlib.pyplot as plt
import numpy as np
import sys

path = sys.argv[1]
class ListAdder:
    def __init__(self):
        self.data = None
    def add(self, data):
        if not self.data:
            self.data = [data[i] for i in range(len(data))]
        else:
            self.data = listadd(self.data, data)

def listadd(l, r):
    assert len(l) == len(r)
    return [l[i] + r[i] for i in range(len(l))]

def draw_simulated_single_point(data):
    def get_endtime(d):
        return d['start'] + len(d['stats'])
    endtime = max([get_endtime(d) for d in data])
    def get_property(name):
        ret = []
        for d in data:
            x = d['start'] * [0] + [s[name] for s in d['stats']]
            x = x + (endtime + 1 - len(x)) * [0]
            ret.append(x)
        return ret
    max_memory = get_property("max_memory")
    current_memory = get_property("current_memory")
    bottom = ListAdder()
    for d in max_memory:
        plt.bar(np.arange(len(d)), d, width=1.0, bottom=bottom.data)
        bottom.add(d)
    bottom = ListAdder()
    for i in range(len(current_memory)):
        d = current_memory[i]
        bottom.add([0 for _ in range(len(d))])
        plt.plot(listadd(bottom.data, d), color="black")
        bottom.add(max_memory[i])
    plt.savefig("plot.png")

def draw_simulated_pareto_curve(data):
    bc_time = []
    bc_memory = []
    fc_time = []
    fc_memory = []
    def process(point, used_memory, time, memory):
        if (point["tag"] == "Some"):
            v = point["value"]
            time.append(v["ticks_in_gc"])
            memory.append(used_memory)
    for point in data["points"]:
        process(point["balance_controller"], point["memory"], bc_time, bc_memory)
        process(point["fcfs_controller"], point["memory"], fc_time, fc_memory)
    plt.plot(bc_memory, bc_time)
    plt.plot(fc_memory, fc_time)
    plt.savefig("plot.png")

with open(path) as f:
    data = json.load(f)
    if data["type"] == "simulated experiment(pareto curve)":
        draw_simulated_pareto_curve(data["data"])
    else:
        raise
