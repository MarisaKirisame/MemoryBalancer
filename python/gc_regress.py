import glob
import json
import numpy as np
xs = []
ys = []
for name in glob.glob('log/**/*.gc.log', recursive=True):
    with open(name, "r") as f:
        log = [json.loads(l) for l in f.readlines()]
        if len(log) >= 2:
            x = [l["before_memory"] for l in log if l["major"]]
            y = [l["gc_duration"] for l in log if l["major"]]
            model = np.polyfit(x, y, 1)
            print(((x, y), model))
            xs += x
            ys +=y
model = np.polyfit(xs, ys, 1)
print(model)

