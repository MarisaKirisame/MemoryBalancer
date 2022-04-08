import glob
import os

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

def main():
    avg_of_div = baseline_average(lambda x: calculate_total(x, "working-memory")) / baseline_average(lambda x: calculate_total(x, "current-memory"))
    div_of_avg = baseline_average(lambda x: calculate_total(x, "working-memory") / calculate_total(x, "current-memory"))
    # no idea which one i should use... but the result is pretty similar so i guess it is not an issue
    return avg_of_div

if __name__ == "__main__":
    print(main())
