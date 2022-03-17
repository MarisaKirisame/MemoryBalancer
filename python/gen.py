import dominate
from dominate.tags import *
import megaplot
import anal_gc_log
import matplotlib.pyplot as plt
import os
from pathlib import Path, PurePath
import time
import glob
import json
import shutil

class Counter:
    def __init__(self):
        self.count = 0

    def __call__(self):
        ret = self.count
        self.count += 1
        return ret

path = Path("out/" + time.strftime("%Y-%m-%d-%H-%M-%S"))
path.mkdir()

png_counter = Counter()
html_counter = Counter()
txt_counter = Counter()

gc_log_plot = {}
for name in glob.glob('log/**/score', recursive=True):
    dirname = os.path.dirname(name)
    with open(dirname + "/cfg") as f:
        cfg = eval(f.read())
    with open(dirname + "/score") as f:
        score = json.load(f)
    with dominate.document(title=dirname) as doc:
        print(dirname)
        anal_gc_log.main(dirname + "/")
        png_path = f"{png_counter()}.png"
        plt.savefig(str(path.joinpath(png_path)))
        plt.clf()
        img(src=png_path)
        p(f"cfg = {cfg}")
        p(f"score = {score}")
        for filename in os.listdir(dirname):
            if filename not in ["cfg", "score"]:
                txt_path = f"{txt_counter()}.txt"
                shutil.copy(dirname + "/" + filename, path.joinpath(txt_path))
                li(a(filename, href=txt_path))
    html_path = f"{html_counter()}.html"
    with open(str(path.joinpath(html_path)), "w") as f:
        f.write(str(doc))
    bench = tuple(cfg["BENCH"])
    if bench not in gc_log_plot:
        gc_log_plot[bench] = {}
    gc_log_plot[bench][dirname] = html_path

m = megaplot.anal_log()

subpages = []
for bench in m.keys():
    with dominate.document(title=str(bench)) as doc:
        points = megaplot.plot(m, [bench], summarize_baseline=False)
        png_path = f"{png_counter()}.png"
        plt.savefig(str(path.joinpath(png_path)))
        plt.clf()
        img(src=png_path)
        for point in points:
            dirname = os.path.dirname(point.name)
            with open(dirname + "/cfg") as f:
                cfg = eval(f.read())
            li(f"{(round(point.memory,2), round(point.time, 2))} {cfg['BALANCER_CFG']['RESIZE_CFG']} -> ", a(dirname, href=gc_log_plot[bench][dirname]))
    html_path = f"{html_counter()}.html"
    with open(str(path.joinpath(html_path)), "w") as f:
        f.write(str(doc))
    subpages.append((str(bench), html_path))

# as dominate do not support recursive call of document(), we have to do some weird plumbing and generate the inner doc before the outer doc.
with dominate.document(title='Plot') as doc:
    megaplot.plot(m, m.keys())
    plt.savefig(str(path.joinpath("plot.png")))
    plt.clf()
    img(src="plot.png")
    for name, filepath in subpages:
        li(a(name, href=filepath))

with open(str(path.joinpath("index.html")), "w") as f:
    f.write(str(doc))

os.system(f"xdg-open {path.joinpath('index.html')}")
