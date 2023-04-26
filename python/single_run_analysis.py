

import glob
import json
import matplotlib.pyplot as plt
# import numpy as np



def get_property_val(filepath, property_val):
    values = []
    with open(filepath) as f:
        for line in f.read().splitlines():
            j = json.loads(line)
            values.append(j[property_val])
    return values

def get_gi(filepath):
    values = []
    with open(filepath) as f:
        for line in f.read().splitlines():
            j = json.loads(line)
            gi_bytes = j["gi_bytes"]
            gi_time = j["gi_time"]
            if(gi_time != 0):
                values.append(gi_bytes/gi_time)
    return values

def get_si(filepath):
    values = []
    with open(filepath) as f:
        prev = 0
        for line in f.read().splitlines():
            j = json.loads(line)
            si_bytes = j["si_bytes"]
            si_time = j["si_time"]
            if(si_time != 0):
                values.append(si_bytes/si_time)
                prev = si_bytes/si_time
            else:
                values.append(prev)
    return values


def scatter_plot(cfg, kv, output_dir, o_filename):
    color = ["red", "blue", "black", "orange", "yellow", "brown"]
    plt.figure()
    # plt.xlabel("YG semispace size")
    # plt.ylabel("Promotion rate")
    plt.title("gi and si"+ str(cfg))
    for idx, key in enumerate(kv.keys()):
        x = list(range(1, len(kv[key])))
        plt.scatter(x, kv[key], label=key, color=color[idx])
    plt.legend(bbox_to_anchor=(.75, 1.05), loc="center left")
    plt.savefig(output_dir+"/"+o_filename)    
    plt.close()  

def process_dir(dir, cfg, output_dir):
    yg_gc_file = glob.glob(dir+"/*.yg.log")[0]
    values = {}
    values["gi"] = get_gi(yg_gc_file)
    values["si"] = get_si(yg_gc_file)
    scatter_plot(cfg, values, output_dir, "g_and_s_rates")





