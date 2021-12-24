import subprocess
import time
from pathlib import Path
import os
import json
import sys

assert(len(sys.argv) == 2)
cfg = eval(sys.argv[1])

LIMIT_MEMORY = cfg["LIMIT_MEMORY"]
DEBUG = cfg["DEBUG"]
if LIMIT_MEMORY:
    MEMORY_LIMIT = cfg["MEMORY_LIMIT"]
BALANCER_CFG = cfg["BALANCER_CFG"]
BALANCE_STRATEGY = BALANCER_CFG["BALANCE_STRATEGY"]
RESIZE_CFG = BALANCER_CFG["RESIZE_CFG"]
RESIZE_STRATEGY = RESIZE_CFG["RESIZE_STRATEGY"]
if RESIZE_STRATEGY == "constant":
    RESIZE_AMOUNT = RESIZE_CFG["RESIZE_AMOUNT"]
if RESIZE_STRATEGY == "after-balance":
    GC_RATE = RESIZE_CFG["GC_RATE"]
SMOOTH_TYPE = BALANCER_CFG["SMOOTHING"]["TYPE"]
if not SMOOTH_TYPE == "no-smoothing":
    SMOOTH_COUNT = BALANCER_CFG["SMOOTHING"]["COUNT"]
BALANCE_FREQUENCY = BALANCER_CFG["BALANCE_FREQUENCY"]

def report_jetstream_score():
    with open(filename) as f:
        print(f.read())

def report_major_gc_time(directory):
    major_gc_total = 0
    minor_gc_total = 0
    balancer_efficiency = []
    for filename in os.listdir(directory):
        if filename.endswith(".gc.log"):
            with open(os.path.join(directory, filename)) as f:
                for line in f.read().splitlines():
                    j = json.loads(line)
                    if j["is_major_gc"]:
                        major_gc_total += j["after_time"] - j["before_time"]
                    else:
                        minor_gc_total += j["after_time"] - j["before_time"]
    print(f"major gc took: {major_gc_total}")
    print(f"minor gc took: {minor_gc_total}")
    total_memory = []
    with open(os.path.join(directory, "balancer_log")) as f:
        for line in f.read().splitlines():
            j = json.loads(line)
            if j["type"] == "efficiency":
                balancer_efficiency.append(j["data"])
            elif j["type"] == "total-memory":
                total_memory.append(j["data"])
    total_time = None
    total_major_gc_time = None
    with open(os.path.join(directory, "v8_log")) as f:
        for line in f.read().splitlines():
            j = json.loads(line)
            if j["type"] == "total_time":
                assert(total_time == None)
                total_time = j["data"]
            elif j["type"] == "total_major_gc_time":
                assert(total_major_gc_time == None)
                total_major_gc_time = j["data"]
    # filter out the nans
    balancer_efficiency = list([x for x in balancer_efficiency if x])
    j = {}
    j["OK"] = True
    j["MAJOR_GC_OLD"] = major_gc_total
    j["MINOR_GC_OLD"] = minor_gc_total
    j["PEAK_MEMORY"] = max(total_memory)
    assert(total_time != None)
    j["TOTAL_TIME"] = total_time
    assert(total_major_gc_time != None)
    j["TOTAL_MAJOR_GC_TIME"] = total_major_gc_time
    with open(os.path.join(directory, "score"), "w") as f:
        json.dump(j, f)

result_directory = "log/" + time.strftime("%Y-%m-%d-%H-%M-%S") + "/"
Path(result_directory).mkdir()
with open(os.path.join(result_directory, "cfg"), "w") as f:
    json.dump(cfg, f)

# weird error: terminate does not work when exception is raised. fix this.
class ProcessScope:
    def __init__(self, p):
        self.p = p
    def __enter__(self):
        return self.p
    def __exit__(self, *args):
        self.p.terminate()

MB_IN_BYTES = 1024 * 1024

balancer_cmds = ["/home/marisa/Work/MemoryBalancer/build/MemoryBalancer", "daemon"]
balancer_cmds.append(f"--balance-strategy={BALANCE_STRATEGY}")
balancer_cmds.append(f"--resize-strategy={RESIZE_STRATEGY}")
if RESIZE_STRATEGY == "constant":
    balancer_cmds.append(f"--resize-amount={RESIZE_AMOUNT * MB_IN_BYTES}")
if RESIZE_STRATEGY == "after-balance":
    balancer_cmds.append(f"--gc-rate={GC_RATE}")
balancer_cmds.append(f"--smooth-type={SMOOTH_TYPE}")
if not SMOOTH_TYPE == "no-smoothing":
    balancer_cmds.append(f"--smooth-count={SMOOTH_COUNT}")
balancer_cmds.append(f"--balance-frequency={BALANCE_FREQUENCY}")
balancer_cmds.append(f"""--log-path={result_directory+"balancer_log"}""")

def tee_log(cmd, log_path):
    return f"{cmd} 2>&1 | tee {log_path}"

with ProcessScope(subprocess.Popen(balancer_cmds, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)) as p:
    subprocess.Popen(["tee", result_directory+"balancer_out"], stdin=p.stdout)
    time.sleep(1) # make sure the balancer is running
    memory_limit = f"{MEMORY_LIMIT * MB_IN_BYTES}"

    env_vars = "USE_MEMBALANCER=1 LOG_GC=1"

    if not RESIZE_STRATEGY == "ignore":
        env_vars = f"{env_vars} SKIP_RECOMPUTE_LIMIT=1"

    command = f"python3 -u benchmark.py {result_directory}"
    command = f"../chromium/src/out/Default/chrome --no-sandbox"
    command = f"""build/MemoryBalancer v8_experiment --heap-size={int(10 * 1000 * 1e6)} --log-path={result_directory+"v8_log"}""" # a very big heap size to essentially have no limit

    if LIMIT_MEMORY:
        env_vars = f"MEMORY_LIMITER_TYPE=ProcessWide MEMORY_LIMITER_VALUE={memory_limit} {env_vars}"

    if DEBUG:
        command = f"gdb -ex=r --args {command}"

    main_process_result = subprocess.run(f"{env_vars} {command}", shell=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

    for filename in os.listdir(os.getcwd()):
        if (filename.endswith(".gc.log")):
            Path(filename).rename(result_directory + filename)

    if main_process_result.returncode != 0:
        if "Fatal javascript OOM" in main_process_result.stdout:
            j = {}
            j["OK"] = False
            j["CFG"] = cfg
            with open(os.path.join(result_directory, "score"), "w") as f:
                json.dump(j, f)
        else:
            print(main_process_result.stdout)
            print("UNKNOWN ERROR!")
    else:
        report_major_gc_time(result_directory)
    with open(os.path.join(result_directory, "v8_out"), "w") as f:
        f.write(main_process_result.stdout)
