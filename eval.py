import subprocess
import time
from pathlib import Path
import os
import json

def report_jetstream_score():
    with open(filename) as f:
        print(f.read())

def report_major_gc_time(directory):
    major_gc_total = 0
    minor_gc_total = 0
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

result_directory = time.strftime("%Y-%m-%d-%H-%M-%S") + "/"
Path(result_directory).mkdir()

class ProcessScope:
    def __init__(self, p):
        self.p = p
    def __enter__(self):
        return self.p
    def __exit__(self, *args):
        self.p.terminate()

with ProcessScope(subprocess.Popen(["/home/marisa/Work/MemoryBalancer/build/MemoryBalancer", "daemon", "--send-msg=true"])):
    time.sleep(1) # make sure the balancer is running

    memory_limit = f"{700 * 1e6}"

    env_vars = "USE_MEMBALANCER=1 LOG_GC=1"

    #subprocess.run(f"echo {memory_limit} > /sys/fs/cgroup/memory/MemBalancer/memory.limit_in_bytes", shell=True, check=True)
    #subprocess.run(f"echo {memory_limit} > /sys/fs/cgroup/memory/MemBalancer/memory.memsw.limit_in_bytes", shell=True, check=True)

    command = f"python3 benchmark.py {result_directory}"
    command = f"../chromium/src/out/Default/chrome --no-sandbox"
    command = f"build/MemoryBalancer v8_experiment --heap-size={int(10 * 1000 * 1e6)}"

    LIMIT_MEMORY = True

    if LIMIT_MEMORY:
        env_vars = f"MEMORY_LIMITER_TYPE=ProcessWide MEMORY_LIMITER_VALUE={memory_limit} {env_vars}"

    DEBUG = False
    if DEBUG:
        command = f"gdb -ex=r --args {command}"

    subprocess.run(f"{env_vars} {command}", shell=True, check=True)

    for filename in os.listdir(os.getcwd()):
        if (filename.endswith(".gc.log")):
            Path(filename).rename(result_directory + filename)

    report_major_gc_time(result_directory)
