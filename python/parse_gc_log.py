import json
import os
import glob
import sys
import matplotlib.pyplot as plt
import paper

def get_data(filepath):
	data = []
	with open(filepath) as f:
		for line in f.read().splitlines():
			data.append(json.loads(line))
	return data

def evaluate_c(file_data):
    c_vals = [] #(time, c)
    prev_w = None
    prev_s = None
    for each_entry in file_data:
        if prev_w == None:
            prev_w = each_entry["after_memory"]
            prev_s = each_entry["gc_bytes"]/each_entry["gc_duration"]
        else:
            g = each_entry["allocation_bytes"]/each_entry["allocation_duration"]
            s = (prev_s + each_entry["gc_bytes"]/each_entry["gc_duration"]) / 2
            m = each_entry["before_memory"]
            t = each_entry["after_time"]
            c = (g*prev_w)/(s* (m-prev_w)**2)
            prev_w = each_entry["after_memory"]
            prev_s = each_entry["gc_bytes"]/each_entry["gc_duration"]
            c_vals.append((t, c))
    return c_vals

def plot_c(all_c_vals, title):
    for val in all_c_vals:
        for name in val.keys():
            for v in val[name]:
                plt.plot([p[0] for p in v], [p[1] for p in v], label=name)
    plt.title(title)
    if eval_name == "JS":
        plt.legend()
    filepath = "../membalancer-paper/c_plot_{}.png".format(title)
    plt.savefig(filepath, bbox_inches='tight')
    plt.clf()

def parse_gc_logs(dir):
    data = {}
    path = dir+"/*.gc.log"
    for name in glob.glob(path, recursive=True):
        file_data = get_data(name)
        if len(file_data) > 0:
            name = file_data[0]["name"]
            all_c = evaluate_c(file_data)
            if name not in data:
                data[name] = []
            data[name].append(all_c)
    return data

def main(mb_dir, base_dir, header):
    assert isinstance(mb_dir, list)
    assert isinstance(base_dir, list)
    paper.pull()
    mb_data = [parse_gc_logs(d) for d in mb_dir]
    plot_c(mb_data, header + "Membalancer")
    base_data = [parse_gc_logs(d) for d in base_dir]
    plot_c(base_data, header + "Baseline")
    paper.push()

if __name__ == "__main__":
    eval_name = sys.argv[1]
    baseline_dir = {}
    membalancer_dir = {}
    for name in glob.glob('log/**/score', recursive=True):
        dirname = os.path.dirname(name)
        with open(dirname + "/cfg") as f:
            cfg = eval(f.read())
        bench = tuple(cfg["BENCH"])
        if cfg["BALANCER_CFG"]["BALANCE_STRATEGY"] == "ignore":
            if bench not in baseline_dir:
                baseline_dir[bench] = dirname
        elif cfg["BALANCER_CFG"]["RESIZE_CFG"]["GC_RATE_D"] == -5e-10:
            membalancer_dir[bench] = dirname
    main(list(membalancer_dir.values()), list(baseline_dir.values()), eval_name)
