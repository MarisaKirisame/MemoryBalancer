import os
import sys
from pathlib import Path
import json

assert(len(sys.argv) == 2)
directory = sys.argv[1]

MAJOR_GC_TIME = 0
TOTAL_GC_TIME = 0
for filename in os.listdir(directory):
    if (filename.endswith(".gc.log")):
        with open(directory + filename) as f:
            for l in f.readlines():
                data = json.loads(l)
                time = data["after_time"] - data["before_time"]
                TOTAL_GC_TIME += time
                if data["is_major_gc"]:
                    MAJOR_GC_TIME += time
print(MAJOR_GC_TIME, TOTAL_GC_TIME)
