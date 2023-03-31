import numpy as np
import matplotlib.pyplot as plt
from statistics import mean
import statistics
import glob
import json
import sys
import random
import os
import math
from tabulate import tabulate
from scipy.stats import linregress
import pathlib
from enum import Enum
import matplotlib.colors as pltc


# arg_dir = sys.argv[1]+"/"


def read_json(file):
    j = []
    with open(file) as f:
        for line in f.readlines():
            # tmp = json.loads(line)
            tmp = eval(line)
            j.append(tmp)
    return j


def get_dirs(input_dir):
    dirs = glob.glob(str(input_dir)+"/*/")
    return dirs


def get_all_value_for_key(file, key):
    all_entries = read_json(file)
    res = []
    for entry in all_entries:
        res.append(entry[key])
    return res


def plot_promotion_rate_for(input_dir, strategy):
    all_dirs = get_dirs(input_dir)
    x_yg_promotion_rate = []
    y_yg_semispace_size = []
    benchmark = ""
    for dir in all_dirs:
        cfg = read_json(dir+"/cfg")[0]
        tmp_strategy = cfg["CFG"]["BALANCER_CFG"]["BALANCE_STRATEGY"]
        if strategy != tmp_strategy:
            continue
        files = glob.glob(dir+"*.yg.log")
        total_promoted_byte = 0
        total_allocated_bytes = 1
        yg_semispace_size = 0
        for file in files:
            total_promoted_byte += get_all_value_for_key(file, "total_promoted_bytes")[-1]
            total_allocated_bytes += sum(get_all_value_for_key(file, "allocated_bytes"))
            yg_semispace_size = statistics.mean(get_all_value_for_key(file, "yg_semispace_limit"))
        promotion_rate = total_promoted_byte/total_allocated_bytes
        x_yg_promotion_rate.append(yg_semispace_size)
        y_yg_semispace_size.append(promotion_rate)
        benchmark = cfg["CFG"]["BENCH"]
    return (x_yg_promotion_rate, y_yg_semispace_size, benchmark)

def plot_promotion_rate(input_dir, output_dir):
    
    strategy = ["YG_BALANCER", "classic", "ignore"]
    color = ["red", "blue", "black"]
    plt.figure()
    plt.xlabel("YG size")
    plt.ylabel("Promotion rate")
    
    for idx, tmp in enumerate(strategy):
        x, y, bm = plot_promotion_rate_for(input_dir, tmp)
        plt.title(bm)
        plt.scatter(x, y, label=strategy[idx], color=color[idx])
    plt.legend(bbox_to_anchor=(.75, 1.05), loc="center left")
    plt.savefig(output_dir+"/promotion_rate")    
    plt.close()  
# plot_promotion_rate(arg_dir)






