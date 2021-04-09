import json
import matplotlib.pyplot as plt
import numpy as np
from optparse import OptionParser

parser = OptionParser()
parser.add_option("-l", "--log", dest="log",
                  help="filename of log", metavar="FILE")
(options, args) = parser.parse_args()
path = options.log
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

with open(path) as f:
    data = json.load(f)
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
