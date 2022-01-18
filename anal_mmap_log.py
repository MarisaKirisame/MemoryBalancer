import os
import sys
import json

logs = []
for filename in os.listdir(sys.argv[1]):
    if filename.endswith(".allocator.log"):
        with open(os.path.join(sys.argv[1], filename)) as f:
            for line in f.read().splitlines():
                logs.append(json.loads(line))

logs.sort(key=lambda x: x["time"])
logs = list(filter(lambda x: x["value"] != 134217728, logs))

allocation_count = 0
max_memory = 0
memory = 0

for i in range(len(logs)):
    l = logs[i]
    if l["type"] == "allocate":
        memory += l["value"]
        allocation_count += l["value"]
    elif l["type"] == "free":
        memory -= l["value"]
    else:
        raise Exception(l["type"])
    max_memory = max(max_memory, memory)
    if i % 20 == 0:
        print(allocation_count)
        print(memory)
        print(max_memory)

print(allocation_count)
print(memory)
print(max_memory)
