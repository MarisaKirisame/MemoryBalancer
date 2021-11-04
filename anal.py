import os
import sys
from pathlib import Path
import json
import numpy as np

vals = []
for filename in os.listdir("log"):
    with open(os.path.join("log", filename, "log")) as f:
        j = json.load(f)
        vals.append(j)

def report(x):
    print(f"mean: {np.mean(x)} std: {np.std(x)}")

bucket = {}

for x in vals:
    m = x["CFG"]["MEMORY_LIMIT"]
    if m not in bucket:
        bucket[m] = []
    bucket[m].append(x)

ms = list(bucket.keys())
ms.sort(reverse=True)

for m in ms:
    print(f"When memory limit is {m}:")
    for SEND_MSG in [True, False]:
        print(f"When SEND_MSG is {SEND_MSG}")
        data = [x for x in bucket[m] if x["CFG"]["SEND_MSG"] == SEND_MSG]
        ok_data = [x for x in data if x["OK"]]
        print(f"OOM rate: {1 - len(ok_data) / len(data)}")
        report([x["MAJOR_GC"] for x in ok_data])
