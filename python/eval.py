import subprocess
from pathlib import Path, PurePath
import time
import random
import sys
import json
import shutil
import os
from git_check import get_commit
from util import tex_def, tex_fmt
import paper
from EVAL import *

assert len(sys.argv) == 4
mode = sys.argv[1]
assert mode in ["jetstream", "browseri", "browserii", "browseriii", "acdc", "all", "macro"]
benchmark = sys.argv[2]
yg_semispace_size = sys.argv[3]

BASELINE = {
    "BALANCE_STRATEGY": "ignore",
    "RESIZE_CFG": {"RESIZE_STRATEGY": "ignore"},
    "BALANCE_FREQUENCY": 0
}

js_c_range = [3, 5, 10, 20, 30] * 2
yg_semispace_sizes = [ 1, 2, 3, 4, 5, 6, 7, 8, 9, 10 ]

#for testing
js_c_range = [3, 5, 10, 20, 30]
# yg_semispace_sizes = [ 5 ]

browser_c_range = [0.05, 0.1, 0.2, 0.3, 0.5, 0.7, 0.9]
acdc_c_range = [0.1 * i for i in range(1, 11)] + [1 * i for i in range(1, 11)]

acdc_c_range = [0.1 * i for i in range(1, 3)] + [1 * i for i in range(1, 3)]
if mode == "macro":
    exit()

# yahoo is removed as it is too flaky, and has too much variance
# reddit is removed because the ip got banned
# medium is removed because it allocate little memory in rare fashion
bench = ["twitter", "cnn", "espn", "facebook", "gmail", "foxnews"]

def get_cfg(balance_strategy, c_range):
    cfg = {
        "BALANCE_STRATEGY": balance_strategy,
        "RESIZE_CFG": {"RESIZE_STRATEGY": "gradient", "GC_RATE_D":NONDET(*[x / -1e9 for x in c_range])},
        "BALANCE_FREQUENCY": 0
    }
    return cfg

def BALANCER_CFG(c_range, baseline_time=2):
    
    yg_balancer_cfg = get_cfg("YG_BALANCER", c_range)
    # yg_balancer_cfg["YG_SEMISPACE_SIZE"] = NONDET(*[x for x in yg_semispace_sizes])
    yg_balancer_cfg["YG_SEMISPACE_SIZE"] = yg_semispace_size

    # return QUOTE(NONDET(*[yg_balancer_cfg]))
    return QUOTE(NONDET(*[get_cfg("classic", c_range)] + baseline_time * [BASELINE] + [yg_balancer_cfg]))

cfg_browseri = {
    "LIMIT_MEMORY": True,
    "DEBUG": True,
    "TYPE": "browser",
    "MEMORY_LIMIT": 10000,
    "BENCH": NONDET(*[(x,) for x in bench]),
    "BALANCER_CFG": BALANCER_CFG(browser_c_range)
}

cfg_browserii = {
    "LIMIT_MEMORY": True,
    "DEBUG": True,
    "TYPE": "browser",
    "MEMORY_LIMIT": 10000,
    "BENCH": NONDET(*[(x, y) for x in bench for y in bench if x != y]),
    "BALANCER_CFG": BALANCER_CFG(browser_c_range)
}

cfg_browseriii = {
    "LIMIT_MEMORY": True,
    "DEBUG": True,
    "TYPE": "browser",
    "MEMORY_LIMIT": 10000,
    "BENCH": NONDET(*[random.sample(bench, 3) for _ in range(30)]),
    "BALANCER_CFG": BALANCER_CFG(browser_c_range)
}

eval_browseri = {
    "Description": "Browser one-tab experiment",
    "NAME": "browseri",
    "CFG": cfg_browseri
}

eval_browserii = {
    "Description": "Browser two-tab experiment",
    "NAME": "browserii",
    "CFG": cfg_browserii
}

eval_browseriii = {
    "Description": "Browser three-tab experiment",
    "NAME": "browseriii",
    "CFG": cfg_browseriii
}

# cfg_jetstream = {
#     "LIMIT_MEMORY": True,
#     "DEBUG": True,
#     "TYPE": "jetstream",
#     "MEMORY_LIMIT": 10000,
#     "BENCH": ["pdfjs", "splay", "typescript"],
#     "BALANCER_CFG": BALANCER_CFG(js_c_range)
# }

# benchmarks = ["all", "pdfjs.js", "splay.js", "typescript.js", "box2d.js", "earley-boyer.js"]
cfg_jetstream = {
    "LIMIT_MEMORY": True,
    "DEBUG": True,
    "TYPE": "jetstream",
    "MEMORY_LIMIT": 10000,
    "BENCH": benchmark,
    "BALANCER_CFG": BALANCER_CFG(js_c_range)
}

eval_jetstream = {
    "Description": "Jetstream2 experiment",
    "NAME": "jetstream",
    "CFG": cfg_jetstream
}

cfg_acdc = {
    "LIMIT_MEMORY": True,
    "DEBUG": True,
    "TYPE": "acdc",
    "MEMORY_LIMIT": 10000,
    "BENCH": ["acdc"],
    "BALANCER_CFG": BALANCER_CFG(acdc_c_range)
}

eval_acdc = {
    "Description": "ACDC-JS experiment",
    "NAME": "acdc",
    "CFG": cfg_acdc,
}

evaluation = []
if mode in ["jetstream", "all"]:
    evaluation.append(QUOTE(eval_jetstream))
if mode in ["browseri", "all"]:
    evaluation.append(QUOTE(eval_browseri))
if mode in ["browserii", "all"]:
    evaluation.append(QUOTE(eval_browserii))
if mode in ["browseriii", "all"]:
    evaluation.append(QUOTE(eval_browseriii))
if mode in ["acdc", "all"]:
    evaluation.append(QUOTE(eval_acdc))

subprocess.run("make", shell=True)
# subprocess.run("autoninja -C out/Release/ chrome", shell=True, cwd="../chromium/src")

def run(config, in_path):
    def make_path():
        path = in_path.joinpath(time.strftime("%Y-%m-%d-%H-%M-%S"))
        path.mkdir()
        with open(path.joinpath("cfg"), "w") as f:
            f.write(str(config))
        commit = {}
        # commit["chrome_v8"] = get_commit("../chromium/src/v8")
        # commit["v8"] = get_commit("../v8/src")
        # with open("v8_commit") as f:
        #     lines = f.readlines()
        #     assert len(lines) == 1
        #     assert lines[0] == str(get_commit("../v8/src"))
        # commit["membalancer"] = get_commit("./")
        # with open(path.joinpath("commit"), "w") as f:
        #     f.write(str(commit))
        return path
    if has_meta(config):
        path = make_path()
        for x in strip_quote(flatten_nondet(config)).l:
            run(x, path)
    else:
        for i in range(5):
            try:
                path = make_path()
                cmd = f'python3 python/single_eval.py "{config}" {path}'
                subprocess.run(cmd, shell=True, check=True)
                break
            except subprocess.CalledProcessError as e:
                print(e.output)
                subprocess.run("pkill -f chrome", shell=True)
                if os.path.exists(path):
                    shutil.rmtree(path)

run(NONDET(*evaluation), Path("log"))
