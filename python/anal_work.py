import glob
import os
import json

def read_gc_log(dirname):
    for name in glob.glob(dirname + "/*.gc.log"):
        max_before_memory = None
        corresponding_after_memory = None
        with open(name) as f:
            for l in f.read().splitlines():
                j = json.loads(l)
                before_memory = j["before_memory"]
                after_memory = j["after_memory"]
                if (max_before_memory == None) or (before_memory > max_before_memory):
                    max_before_memory = before_memory
                    corresponding_after_memory = after_memory
        return (max_before_memory, corresponding_after_memory)

def calculate_total(dirname, property_name):
    with open(dirname + "/balancer_log") as f:
        m = {}
        ret = 0
        for l in f.readlines():
            j = eval(l)
            if j["type"] == "heap-stat":
                j = j["data"]
                m[j["name"]] = j[property_name]
                for v in m.values():
                    ret += v
        return ret

def baseline_average(func):
    val = []
    for name in glob.glob('log/**/score', recursive=True):
        dirname = os.path.dirname(name)
        with open(dirname + "/cfg") as f:
            cfg = eval(f.read())
        if cfg["BALANCER_CFG"]["BALANCE_STRATEGY"] == "ignore":
            val.append(func(dirname))
    return sum(val) / len(val)

def old_calculation():
    avg_of_div = baseline_average(lambda x: calculate_total(x, "working-memory")) / baseline_average(lambda x: calculate_total(x, "current-memory"))
    div_of_avg = baseline_average(lambda x: calculate_total(x, "working-memory") / calculate_total(x, "current-memory"))
    # no idea which one i should use... but the result is pretty similar so i guess it is not an issue
    return div_of_avg
    
def new_calculation():
    before_memory_sum = 0
    after_memory_sum = 0
    for name in glob.glob('log/**/score', recursive=True):
        dirname = os.path.dirname(name)
        with open(dirname + "/cfg") as f:
            cfg = eval(f.read())
        if cfg["BALANCER_CFG"]["BALANCE_STRATEGY"] == "ignore":
            (before_memory, after_memory) = read_gc_log(dirname)
            if before_memory != None:
                before_memory_sum += before_memory
                after_memory_sum += after_memory
    return after_memory_sum / before_memory_sum
    
def main():
    return old_calculation()

if __name__ == "__main__":
    print(main())
