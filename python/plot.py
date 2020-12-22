import json
import matplotlib.pyplot as plt

path = "2020-12-22-13-11-27"
with open("logs/" + path) as f:
    data = json.load(f)
    plt.hist([1,2,3,4,5])
    plt.savefig("plot.png")
    print(data)
