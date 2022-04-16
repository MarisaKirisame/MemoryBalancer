import subprocess
from pathlib import Path, PurePath
import time
import random
import sys
import json
import shutil
import os
from git_check import get_commit

# list monad
class NONDET:
    def __init__(self, *args):
        self.l = args

    def bind(self, f):
        ret = []
        for x in self.l:
            res = f(x)
            if not isinstance(res, NONDET):
                print(type(res))
                assert(isinstance(res, NONDET))
            ret += res.l
        return NONDET(*ret)

    def join(self):
        return self.bind(lambda x: x)

    def map(self, f):
        return self.bind(lambda x: NONDET(f(x)))

    def __repr__(self):
        return f"NONDET{repr(self.l)}"

class QUOTE:
    def __init__(self, x):
        self.x = x
    def __repr__(self):
        return f"QUOTE({self.x})"

def flatten_nondet(x):
    if isinstance(x, (bool, int, str, float)):
        return NONDET(x)
    elif isinstance(x, dict):
        return flatten_nondet([i for i in x.items()]).map(lambda x: dict(x))
    elif isinstance(x, list):
        if len(x) == 0:
            return NONDET([])
        else:
            head = flatten_nondet(x[0])
            tail = flatten_nondet(x[1:])
            return head.bind(lambda y: tail.bind(lambda z: NONDET([y] + z)))
    elif isinstance(x, NONDET):
        return NONDET(*[flatten_nondet(y) for y in x.l]).join()
    elif isinstance(x, tuple):
        return NONDET(*[tuple(y) for y in flatten_nondet(list(x)).l])
    elif isinstance(x, QUOTE):
        return NONDET(x)
    else:
        print(type(x))
        print(x)
        raise

def has_meta(x):
    if isinstance(x, (str, bool, int, float)):
        return False
    elif isinstance(x, (QUOTE, NONDET)):
        return True
    elif isinstance(x, dict):
        return has_meta(tuple(its for its in x.items()))
    elif isinstance(x, tuple):
        return any([has_meta(y) for y in x])
    elif isinstance(x, list):
        return has_meta(tuple(x))
    else:
        print(type(x))
        print(x)
        raise

def strip_quote(x):
    if isinstance(x, (str, bool, int, float)):
        return x
    elif isinstance(x, QUOTE):
        return x.x
    elif isinstance(x, dict):
        return {strip_quote(k): strip_quote(v) for k, v in x.items()}
    elif isinstance(x, list):
        return list([strip_quote(y) for y in x])
    elif isinstance(x, tuple):
        return tuple([strip_quote(y) for y in x])
    elif isinstance(x, NONDET):
        return NONDET(*strip_quote(x.l))
    else:
        print(type(x))
        print(x)
        raise

cfgs = flatten_nondet({
    "LIMIT_MEMORY": True,
    "DEBUG": False,
    "NAME": "jetstream",
    "MEMORY_LIMIT": NONDET(*[600 + 30 * i for i in range(10)]),
    "BALANCER_CFG": NONDET({
        "BALANCE_STRATEGY": NONDET("classic", "extra-memory", "ignore"),
        "RESIZE_CFG": {"RESIZE_STRATEGY": "ignore"},
        "SMOOTHING": {"TYPE": "no-smoothing"},
        "BALANCE_FREQUENCY": 0
    })
}).l

cfgs = flatten_nondet(NONDET({
    "LIMIT_MEMORY": True,
    "DEBUG": False,
    "NAME": "jetstream",
    "MEMORY_LIMIT": NONDET(10000),
    "BALANCER_CFG": {
        "BALANCE_STRATEGY": "classic",
        "RESIZE_CFG": {"RESIZE_STRATEGY": "after-balance", "GC_RATE":NONDET(0.01, 0.015, 0.02, 0.03, 0.04, 0.06, 0.08, 0.10, 0.15, 0.2)},
        "SMOOTHING": {"TYPE": "no-smoothing"},
        "BALANCE_FREQUENCY": 0
    }}, {
        "LIMIT_MEMORY": True,
        "DEBUG": False,
        "NAME": "jetstream",
        "MEMORY_LIMIT": NONDET(*[500 + 30 * i for i in range(16)], 10000),
        "BALANCER_CFG": {
            "BALANCE_STRATEGY": NONDET("ignore"),
            "RESIZE_CFG": {"RESIZE_STRATEGY": "ignore"},
            "SMOOTHING": {"TYPE": "no-smoothing"},
            "BALANCE_FREQUENCY": 0
        }})).l

cfgs = [{
    "LIMIT_MEMORY": True,
    "DEBUG": True,
    "NAME": "browser",
    "MEMORY_LIMIT": 10000,
    "BALANCER_CFG": {
        "BALANCE_STRATEGY": "ignore",
        "RESIZE_CFG": {"RESIZE_STRATEGY": "ignore"},
        "SMOOTHING": {"TYPE": "no-smoothing"},
        "BALANCE_FREQUENCY": 0
    }}]


cfgs = flatten_nondet({
    "LIMIT_MEMORY": True,
    "DEBUG": True,
    "NAME": "browser",
    "MEMORY_LIMIT": NONDET(10000),
    "BENCH": NONDET(["twitter"], ["twitter", "cnn"], ["twitter", "cnn", "espn"]),
    "BALANCER_CFG": NONDET({
        "BALANCE_STRATEGY": NONDET("ignore"),
        "RESIZE_CFG": {"RESIZE_STRATEGY": "ignore"},
        "SMOOTHING": {"TYPE": "no-smoothing"},
        "BALANCE_FREQUENCY": 0
    })}).l

BALANCER_CFG = QUOTE(NONDET({
    "BALANCE_STRATEGY": "classic",
    "RESIZE_CFG": {"RESIZE_STRATEGY": "after-balance", "GC_RATE":NONDET(0.001, 0.002, 0.005, 0.01, 0.02, 0.04, 0.06)},
    "BALANCE_FREQUENCY": 0
}, {
    "BALANCE_STRATEGY": "ignore",
    "RESIZE_CFG": {"RESIZE_STRATEGY": "ignore"},
    "BALANCE_FREQUENCY": 0
}))

BASELINE = {
    "BALANCE_STRATEGY": "ignore",
    "RESIZE_CFG": {"RESIZE_STRATEGY": "ignore"},
    "BALANCE_FREQUENCY": 0
}

js_c_range = [0.01, 0.02, 0.03, 0.04, 0.05, 0.1, 0.2, 0.3, 0.5, 0.7, 0.9, 2, 3, 4]
browser_c_range = [0.05, 0.1, 0.2, 0.3, 0.5, 0.7, 0.9]
js_c_range = [3]
BALANCER_CFG = QUOTE(NONDET({
                                "BALANCE_STRATEGY": "classic",
                                "RESIZE_CFG": {"RESIZE_STRATEGY": "gradient", "GC_RATE_D":NONDET(*[x / -1e9 for x in js_c_range])},
                                "BALANCE_FREQUENCY": 0
                            }, BASELINE, BASELINE, BASELINE))

if 1 < len(sys.argv):
    mode = sys.argv[1]
else:
    mode = "browser"

# yahoo is removed as it is too flaky, and has too much variance
# reddit is removed because the ip got banned
# medium is removed because it allocate little memory in rare fashion
bench = ["twitter", "cnn", "espn", "facebook", "gmail", "foxnews"]
choose_one = [(x,) for x in bench]
choose_two = [(x, y) for x in bench for y in bench if x != y]
choose_three = [random.sample(bench, 3) for _ in range(30)]
cfg_browser = {
    "LIMIT_MEMORY": True,
    "DEBUG": True,
    "NAME": "browser",
    "MEMORY_LIMIT": 10000,
    "BENCH": NONDET(*choose_three),
    "BALANCER_CFG": BALANCER_CFG
}

cfg_jetstream = {
    "LIMIT_MEMORY": True,
    "DEBUG": True,
    "NAME": "jetstream",
    "MEMORY_LIMIT": 10000,
    "BENCH": ["pdfjs", "splay", "typescript"],
    "BALANCER_CFG": BALANCER_CFG
}

if mode == "jetstream":
	cfg = cfg_jetstream
elif mode == "browser":
	cfg = cfg_browser
else:
	print(mode)
	assert False

subprocess.run("make", shell=True)
subprocess.run("autoninja -C out/Release/ chrome", shell=True, cwd="../chromium/src")

def run(config, in_path):
    def make_path():
        path = in_path.joinpath(time.strftime("%Y-%m-%d-%H-%M-%S"))
        path.mkdir()
        with open(path.joinpath("cfg"), "w") as f:
            f.write(str(config))
        commit = {}
        commit["v8"] = get_commit("../chromium/src/v8")
        commit["membalancer"] = get_commit("./")
        with open(path.joinpath("commit"), "w") as f:
            f.write(str(commit))
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

run(cfg, Path("log"))
