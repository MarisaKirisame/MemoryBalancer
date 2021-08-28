import subprocess

memory_limit = "2G"
log_filename = "eval.log"

subprocess.run(f"echo {memory_limit} > /sys/fs/cgroup/memory/MemBalancer/memory.limit_in_bytes", shell=True, check=True)
subprocess.run(f"cgexec -g memory:MemBalancer python3 jetstream.py {log_filename}", shell=True, check=True)
f = open(log_filename)
print(f.read())
f.close()
