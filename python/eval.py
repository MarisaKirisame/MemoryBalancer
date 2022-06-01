import subprocess
from pathlib import Path, PurePath
import time
import random
import sys
import json
import shutil
import os
from git_check import get_commit
from util import tex_def_generic, tex_fmt
import paper

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

assert len(sys.argv) == 2
mode = sys.argv[1]
assert mode in ["jetstream", "browser", "all", "macro"]

BASELINE = {
    "BALANCE_STRATEGY": "ignore",
    "RESIZE_CFG": {"RESIZE_STRATEGY": "ignore"},
    "BALANCE_FREQUENCY": 0
}

js_c_range = [0.5, 0.7, 0.9, 2, 3] * 2
js_c_range.reverse()
browser_c_range = [0.05, 0.1, 0.2, 0.3, 0.5, 0.7, 0.9]

def tex_def(name, definition):
    return tex_def_generic("", name, definition)

tex = ""
tex += tex_def("JSMinC", f"{tex_fmt(min(js_c_range))}\%/MB")
tex += tex_def("JSMaxC", f"{tex_fmt(max(js_c_range))}\%/MB")
tex += tex_def("WEBMinC", f"{tex_fmt(min(browser_c_range))}\%/MB")
tex += tex_def("WEBMaxC", f"{tex_fmt(max(browser_c_range))}\%/MB")

paper.pull()
with open(f"../membalancer-paper/eval_param.tex", "w") as tex_file:
    tex_file.write(tex)
paper.push()

if mode == "macro":
    exit()

# yahoo is removed as it is too flaky, and has too much variance
# reddit is removed because the ip got banned
# medium is removed because it allocate little memory in rare fashion
bench = ["twitter", "cnn", "espn", "facebook", "gmail", "foxnews"]

def BALANCER_CFG(c_range):
    return QUOTE(NONDET({
        "BALANCE_STRATEGY": "classic",
        "RESIZE_CFG": {"RESIZE_STRATEGY": "gradient", "GC_RATE_D":NONDET(*[x / -1e9 for x in c_range])},
        "BALANCE_FREQUENCY": 0
    }, BASELINE, BASELINE, BASELINE))

choose_one = [(x,) for x in bench]
choose_two = [(x, y) for x in bench for y in bench if x != y]
choose_three = [random.sample(bench, 3) for _ in range(30)]
cfg_browser = {
    "LIMIT_MEMORY": True,
    "DEBUG": True,
    "TYPE": "browser",
    "MEMORY_LIMIT": 10000,
    "BENCH": NONDET(*choose_two),
    "BALANCER_CFG": BALANCER_CFG(browser_c_range)
}

eval_browser = {
    "NAME": "browser",
    "CFG": cfg_browser
}

cfg_jetstream = {
    "LIMIT_MEMORY": True,
    "DEBUG": True,
    "TYPE": "jetstream",
    "MEMORY_LIMIT": 10000,
    "BENCH": ["pdfjs", "splay", "typescript"],
    "BALANCER_CFG": BALANCER_CFG(js_c_range)
}

eval_jetstream = {
    "NAME": "jetstream",
    "CFG": cfg_jetstream
}

evaluation = []
if mode in ["jetstream", "all"]:
    evaluation.append(QUOTE(eval_jetstream))
if mode in ["browser", "all"]:
    evaluation.append(QUOTE(eval_browser))

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

run(NONDET(*evaluation), Path("log"))
