import subprocess
import time

class ProcessScope:
    def __init__(self, p):
        self.p = p
    def __enter__(self):
        return self.p
    def __exit__(self, *args):
        self.p.terminate()

with ProcessScope(subprocess.Popen(["/home/marisa/Work/MemoryBalancer/build/MemoryBalancer", "daemon"])):
    time.sleep(1)

    memory_limit = "1G"
    result_directory = time.strftime("%Y-%m-%d-%H-%M-%S") + "/"
    env_vars = "USE_MEMBALANCER=1"

    subprocess.run(f"echo {memory_limit} > /sys/fs/cgroup/memory/MemBalancer/memory.limit_in_bytes", shell=True, check=True)

    command = f"build/MemoryBalancer v8_experiment"
    command = f"python3 benchmark.py {result_directory}"
    command = f"../chromium/src/out/Default/chrome --no-sandbox"

    LIMIT_MEMORY = True

    if LIMIT_MEMORY:
        subprocess.run(f"{env_vars} cgexec -g memory:MemBalancer {command}", shell=True, check=True)
    else:
        subprocess.run(f"{env_vars} {command}", shell=True, check=True)

    f = open(result_directory + "log")
    print(f.read())
    f.close()
