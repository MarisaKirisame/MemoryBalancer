import subprocess
import time

memory_limit = "2G"
result_directory = time.strftime("%Y-%m-%d-%H-%M-%S") + "/"

subprocess.run(f"echo {memory_limit} > /sys/fs/cgroup/memory/MemBalancer/memory.limit_in_bytes", shell=True, check=True)
subprocess.run(f"cgexec -g memory:MemBalancer python3 benchmark.py {result_directory}", shell=True, check=True)
f = open(result_directory + "log")
print(f.read())
f.close()
