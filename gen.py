import dominate
from dominate.tags import *
import megaplot
import matplotlib.pyplot as plt
import os
from pathlib import Path, PurePath
import time

path = Path("out/" + time.strftime("%Y-%m-%d-%H-%M-%S"))
path.mkdir()

doc = dominate.document(title='Plot')

m = megaplot.anal_log()
megaplot.plot(m, m.keys())
plt.savefig(str(path.joinpath("plot.png")))
plt.clf()

subpages = []
i = 0
for bench in m.keys():
    with dominate.document(title=str(bench)) as inner_doc:
        coords = megaplot.plot(m, [bench])
        plt.savefig(str(path.joinpath(f"{i}.png")))
        plt.clf()
        img(src=f"{i}.png")
        for ((x, y), name) in coords:
            li(f"{(round(x,2), round(y, 2))} -> {name}")
    with open(str(path.joinpath(f"{i}.html")), "w") as f:
        f.write(str(inner_doc))
    subpages.append((str(bench), f"{i}.html"))
    i += 1

# as dominate do not support recursive call of document(), we have to do some weird plumbing and generate the inner doc before the outer doc.
with doc:
    img(src="plot.png")
    for name, filepath in subpages:
        li(a(name, href=filepath))

with open(str(path.joinpath("index.html")), "w") as f:
    f.write(str(doc))

os.system(f"xdg-open {path.joinpath('index.html')}")
