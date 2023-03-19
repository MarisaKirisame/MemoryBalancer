import subprocess
from pathlib import Path, PurePath
import time
import random
import sys
import json
import shutil
import os
import matplotlib.pyplot as plt
from git_check import get_commit
from util import tex_def, tex_fmt
import paper
from EVAL import *
import glob
import copy
import numpy as np
import statistics
import collections

assert len(sys.argv) > 1
mode = sys.argv[1]
assert mode in ["all", "run", "global_plots", "single_plots", "anal_gc_plots"]

def make_path(in_path):
    path = in_path.joinpath(time.strftime("%Y-%m-%d-%H-%M-%S"))
    path.mkdir()
    return path

if mode == "run":
    root_dir = make_path(Path("log"))
else:
    assert len(sys.argv) > 2
    root_dir = sys.argv[2]
    
benchmarks = ["all", "pdfjs.js", "splay.js", "typescript.js", "box2d.js", "earley-boyer.js"]


# js_c_range = [3, 5]
# js_c_range = [3, 5, 10, 20, 30]
js_c_range = [3, 4, 5, 7, 10, 13, 15, 17, 20, 30] 
acdc_c_range = [0.1 * i for i in range(1, 11)] + [1 * i for i in range(1, 11)]



BASELINE = {
    "BALANCE_STRATEGY": "ignore",
    "RESIZE_CFG": {"RESIZE_STRATEGY": "ignore"},
    "BALANCE_FREQUENCY": 0
}

def get_cfg(balance_strategy, c_range):
    cfg = {
        "BALANCE_STRATEGY": balance_strategy,
        "RESIZE_CFG": {"RESIZE_STRATEGY": "gradient", "GC_RATE_D":NONDET(*[x / -1e9 for x in c_range])},
        "BALANCE_FREQUENCY": 0
    }
    return cfg

def BALANCER_CFG(c_range, baseline_time=5):
    # return QUOTE(NONDET(*[get_cfg("YG_BALANCER", c_range)]))
    # return QUOTE(NONDET(*[get_cfg("classic", c_range)] + baseline_time * [BASELINE] + [get_cfg("YG_BALANCER", c_range)]))
    return QUOTE(NONDET(*[get_cfg("classic", c_range)] + baseline_time * [BASELINE])) #PRANAV: for running the old way

cfg_jetstream = {
    "LIMIT_MEMORY": True,
    "DEBUG": True,
    "TYPE": "jetstream",
    "MEMORY_LIMIT": 10000,
    "BALANCER_CFG": BALANCER_CFG(js_c_range, baseline_time=5)
}

eval_jetstream = {
    "Description": "Jetstream2 experiment",
    "NAME": "jetstream",
    "CFG": cfg_jetstream
}



flattened_cfgs = []
def flatten_config(cfg):
    if has_meta(cfg):
        for x in strip_quote(flatten_nondet(cfg)).l:
            flatten_config(x)
    else:
        flattened_cfgs.append(cfg)
flatten_config(eval_jetstream)


def add_more_benchmarks_to(config, benchmark):
    all_cfgs = []
    for bm in benchmark:
        for cfg in flattened_cfgs:
            new_cfg = copy.deepcopy(cfg)
            new_cfg["CFG"]["BENCH"] = bm
            all_cfgs.append(new_cfg)
    return all_cfgs


def run(cfgs, root_dir):
    # with open(root_dir.joinpath("cfg"), "w") as f:
    #     f.write(str(cfgs))
    for (idx, cfg) in enumerate(cfgs):
        exp_path = root_dir.joinpath(str(idx)+cfg["CFG"]["BALANCER_CFG"]["BALANCE_STRATEGY"])
        exp_path.mkdir()
        with open(exp_path.joinpath("cfg"), "w") as f:
                f.write(str(cfg))
        cmd = f'python3 python/single_eval.py "{cfg}" {exp_path}'
        subprocess.run(cmd, shell=True, check=True)
        # print(str(idx) + " " + str(cfg))

def get_dirs(path):
    # print(path)
    dirs = glob.glob(str(path)+'/*/')
    return dirs


def get_values_from(filename, key):
        res = []
        if os.stat(filename).st_size == 0:
            return [0]
        with open(filename) as f:
            for line in f.readlines():
                j = json.loads(line)
                
                # major_gc_time = j["total_major_gc_time"]
                res.append(j[key])
        print(len(res))
        return res
    
def read_cfg(dir):
    cfg = {}

    line = ""
    path = os.path.join(dir, "cfg")
    with open(path) as f:
        for l in f.readlines():
            line +=  l
    line = line.replace("'", '"')
    line = line.replace("True", "true")
    line = line.replace("False", "false")
    cfg = json.loads(line)
    # print(cfg)
    return cfg

def merge_log_files(dir, pattern, output_file):
    files = glob.glob(dir+pattern)
    data = ""
    for file in files:
        with open(file) as f:
            data += f.read()
    complete_path = dir+output_file
    with open(complete_path, "w") as f:
        f.write(data)
    print(complete_path)
    return complete_path
        

# res = {yg:{x: [val], y: [val]}, classic:{x: [val], y: [val]}, ignore:{x: [val], y: [val]}]}
def eval_jetstream(benchmark, root_dir, plt_config):
    dirs = get_dirs(root_dir)
    result = {}
    for dir in dirs:
        cfg =  read_cfg(dir)
        if cfg['CFG']['BENCH'] != benchmark:
            continue
        balance_type = cfg['CFG']['BALANCER_CFG']['BALANCE_STRATEGY']
        gc_file = merge_log_files(dir, '/*.gc.log', "/tmp_gc_file")
        mem_file = merge_log_files(dir, '/*.memory.log', "/tmp_mem_file")
        x = plt_config.items[0].operation(gc_file, mem_file)
        y = plt_config.items[1].operation(gc_file, mem_file)
        print(balance_type + " "+ benchmark + " " + str(x) + " - "+str(y) + " dir: "+ dir)
        if balance_type not in result.keys():
            result[balance_type] = {}
            result[balance_type]["x"] = []
            result[balance_type]["y"] = []
        result[balance_type]["x"].append(x)
        result[balance_type]["y"].append(y)

    return result

def plot(values, root_dir, benchmark, plt_config):
    colors = {"YG_BALANCER":"orange", "ignore": "black", "classic":"blue"}
    plt.figure()
    plt.xlabel(plt_config.x_axis)
    plt.ylabel(plt_config.y_axis)
    for (idx, key) in enumerate(values.keys()):
        plt.scatter(values[key]["x"], values[key]["y"], label=key, linewidth=0.1, s=20, color=colors[key])
    path = os.path.join(root_dir, benchmark+plt_config.filename)
    plt.legend(bbox_to_anchor=(1.04, 0.5), loc="center left")
    plt.savefig(path, bbox_inches='tight')
    plt.close()
        
class ParamWrapper:
    key = ""
    legend = ""
    operation = None
    def __init__(self, key, legend, operation):
        self.key = key
        self.legend = legend
        self.operation = operation        

class PlotWrapper:
    filename = ""
    x_axis = ""
    y_axis = ""
    items = []
    def __init__(self, filename, x_axis, y_axis, items):
        self.filename = filename
        self.y_axis = y_axis
        self.x_axis = x_axis
        self.items = items

def eval_single_run(config):

    colors = ["blue", "red", "black"]
    def plot(dir, config):
        cfg =  read_cfg(dir)
        balance_type = cfg['CFG']['BALANCER_CFG']['BALANCE_STRATEGY']
        gc_file = glob.glob(dir+'/*.gc.log')[0]
        mem_file = glob.glob(dir+'/*.memory.log')[0]
        plt.figure()
        plt.title = balance_type
        plt.xlabel(config.x_axis)
        plt.ylabel(config.y_axis)
        for idx, item in enumerate(config.items):
            y = item.operation(gc_file, mem_file)
            x = np.arange(0, len(y), 1)
            # y = y[:1000]
            # x = x[:1000]
            plt.plot(x, y, color=colors[idx], label=item.legend, linewidth=0.75)
            # plt.scatter(x, y, label=item.legend, linewidth=0.0001, color=colors[idx])
        path = os.path.join(dir +config.filename)
        plt.legend(bbox_to_anchor=(1.04, 0.5), loc="center left")
        plt.savefig(path, bbox_inches='tight')
        plt.close()

    dirs = get_dirs(root_dir)
    result = {}
    for dir in dirs:
        plot(dir, config)



def eval_and_plot(plt_config, benchmark):
    for bm in benchmark:
        result = eval_jetstream(bm, root_dir, plt_config)
        plot(result, root_dir, bm, plt_config)

def old_gen_size_of_obj(gc_file):
    total = get_values_from(gc_file, "size_of_objects")
    yg = get_values_from(gc_file, "yg_size_of_object")
    res = []
    for idx, cur_total in enumerate(total):
        res.append(cur_total - yg[idx])
    return res

def run_anal_gc():
    dirs = get_dirs(root_dir)
    for dir in dirs:
        cmd = f'python3 python/anal_gc_log.py  {dir}'
        subprocess.run(cmd, shell=True, check=True)

yg_semispace_limit = ParamWrapper("yg_semispace_limit", "young gen", lambda gc_file: get_values_from(gc_file, "yg_semispace_limit"))
# og_heap_limit = ParamWrapper("og_heap_limit", "old gen", lambda gc_file: get_values_from(gc_file, "og_heap_limit"))
# yg_size_of_object = ParamWrapper("yg_size_of_object", "young gen", lambda gc_file: get_values_from(gc_file, "yg_size_of_object"))
# og_size_of_object = ParamWrapper("og_size_of_object", "old gen", lambda gc_file: get_values_from(gc_file, "og_size_of_object"))
# yg_gc_time = ParamWrapper("yg_gc_time", "young gen", lambda gc_file: get_values_from(gc_file, "yg_gc_time"))
# og_gc_time = ParamWrapper("og_gc_time", "old gen", lambda gc_file: get_values_from(gc_file, "total_major_gc_time"))
# yg_allocated_bytes_since_last_gc = ParamWrapper("yg_allocated_bytes_since_last_gc", "young gen", lambda gc_file: get_values_from(gc_file, "yg_allocated_bytes_since_last_gc"))
# yg_allocation_time = ParamWrapper("yg_allocation_time", "young gen", lambda gc_file: get_values_from(gc_file, "yg_allocation_time"))


#single config plots

# limit_plot = PlotWrapper("limit_plot.png", "Progress", "Heap Limit (B)", [yg_semispace_limit, og_heap_limit])
yg_limit_plot = PlotWrapper("yg_limit_plot.png", "Progress", "Heap Limit (B)", [ yg_semispace_limit])
# og_limit_plot = PlotWrapper("og_limit_plot.png", "Progress", "Heap Limit (B)", [ og_heap_limit])
# yg_size_of_obj_plot = PlotWrapper("yg_size_of_obj_plot.png", "Progress", "Size of objects (B)", [yg_size_of_object])
# og_size_of_obj_plot = PlotWrapper("og_size_of_obj_plot.png", "Progress", "Size of objects (B)", [og_size_of_object])
# yg_gc_time_plot = PlotWrapper("yg_gc_time_plot.png", "Progress", "time (ns)", [yg_gc_time])
# og_gc_time_plot = PlotWrapper("og_gc_time_plot.png", "Progress", "time (ns)", [og_gc_time])


# #global yg_only
# total_yg_size_of_object = ParamWrapper("yg_size_of_object", "young gen", lambda gc_file: statistics.mean(get_values_from(gc_file, "yg_size_of_object")))
# total_yg_gc_time = ParamWrapper("yg_gc_time", "young gen", lambda gc_file: sum(get_values_from(gc_file, "yg_gc_time")))
# total_yg_gc_time_vs_yg_soo = PlotWrapper("-yg_only.png", "Size of Obj (bytes)", "time (ns)", [total_yg_size_of_object, total_yg_gc_time])

#global og_only
total_og_size_of_object = ParamWrapper("BenchmarkMemory", "", lambda gc_file, memory_file: statistics.mean(get_values_from(memory_file, "BenchmarkMemory"))/1e6)
total_og_gc_time = ParamWrapper("total_major_gc_time", "", lambda gc_file, memory_file: get_values_from(gc_file, "total_major_gc_time")[-1]/1e9)
total_og_gc_time_vs_og_soo = PlotWrapper("-og_only.png", "Size of Obj (MB)", "time (s)", [total_og_size_of_object, total_og_gc_time])

#global total
# total_size_of_object = ParamWrapper("size_of_objects", "", lambda gc_file, memory_file: statistics.mean(get_values_from(gc_file, "size_of_objects")))
# total_gc_time = ParamWrapper("total_gc_time", "", lambda gc_file, memory_file: sum(get_values_from(memory_file, "total_gc_time")))
# total_gc_time_vs_soo = PlotWrapper("-total.png", "Size of Obj (bytes)", "time (ns)", [total_size_of_object, total_gc_time])


local_benchmark_copy = benchmarks[1:2]
if mode == "run" or mode == "all":
    cfgs = add_more_benchmarks_to(eval_jetstream, local_benchmark_copy)
    run(cfgs, root_dir)

if mode == "global_plots" or mode == "all":
    print("Global Plots")
    # global_plots = [total_yg_gc_time_vs_yg_soo, total_og_gc_time_vs_og_soo, total_gc_time_vs_soo]
    global_plots = [total_og_gc_time_vs_og_soo]
    for p in global_plots:
        eval_and_plot(p, local_benchmark_copy)

if mode == "single_plots" or mode == "all":
    # all_single_plots = [yg_limit_plot, og_limit_plot, yg_size_of_obj_plot, og_size_of_obj_plot, yg_gc_time_plot, og_gc_time_plot]
    all_single_plots = [yg_limit_plot]
    for p in all_single_plots:
        eval_single_run(p)

if mode == "anal_gc_plots" or mode == "all":
    run_anal_gc()