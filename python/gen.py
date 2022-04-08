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
from scipy import stats
import math
import subprocess
import sys
import anal_work

class Counter:
    def __init__(self):
        self.count = 0

    def __call__(self):
        ret = self.count
        self.count += 1
        return ret

if len(sys.argv) > 1:
    eval_name = sys.argv[1]
else:
    eval_name = ""

assert eval_name in [
    "", # do not generate+upload tex or plot for the paper
    "WEBI", # 1 website run
    "WEBIIBL", # 2 website run, baseline
    "WEBIIAB", # 2 website run, ablation study (turned off memory reducer and memory notification for baseline),
    "WEBIII", # 3 website run
    "JS", # JetStream, embedded v8
]

tex = ""

path = Path("out/" + time.strftime("%Y-%m-%d-%H-%M-%S"))
path.mkdir(parents=True, exist_ok=True)

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
        plt.savefig(str(path.joinpath(png_path)), bbox_inches='tight')
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
        mp = megaplot.plot(m, [bench], summarize_baseline=False)
        points = mp["points"]
        png_path = f"{png_counter()}.png"
        plt.savefig(str(path.joinpath(png_path)), bbox_inches='tight')
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

def fmt(x):
    return "{0:.3g}".format(x)

# as dominate do not support recursive call of document(), we have to do some weird plumbing and generate the inner doc before the outer doc.
with dominate.document(title='Plot') as doc:
    mp = megaplot.plot(m, m.keys())
    points = mp["points"]
    if "coef" in mp:
        coef = mp["coef"]
        slope, bias = coef
        sd = mp["sd"]
    plt.savefig(str(path.joinpath("plot.png")), bbox_inches='tight')
    plt.clf()
    img(src="plot.png")
    def get_deviate_in_sd(x, y):
        return (y - (x * slope + bias)) / sd
    if "coef" in mp:
        y_projection = slope+bias
        tex += f"\def\{eval_name}Speedup{{{fmt((y_projection-1)*100)}\%}}\n"
        x_projection = (1-bias)/slope
        tex += f"\def\{eval_name}MemorySaving{{{fmt((1-x_projection)*100)}\%}}\n"
        p(f"{(1.0, fmt(y_projection))}")
        p(f"{(fmt(x_projection), 1.0)}")
        baseline_deviate = get_deviate_in_sd(1, 1)
        p(f"improvement = {fmt(-baseline_deviate)} sigma")
        tex += f"\def\{eval_name}Improvement{{{fmt(-baseline_deviate)} \sigma}}\n"
        improvement_over_baseline = []
        for point in points:
            assert not point.is_baseline
            improvement_over_baseline.append(get_deviate_in_sd(point.memory, point.time) - baseline_deviate)
        if len(improvement_over_baseline) > 1:
            pvalue = stats.ttest_1samp(improvement_over_baseline, 0.0, alternative="greater").pvalue
            tex += f"\def\{eval_name}PValue{{{fmt(pvalue)}}}\n"
            p(f"""pvalue={fmt(pvalue)}""")
            bin_width = 0.5
            min_improvement = min(*improvement_over_baseline)
            tex += f"\def\{eval_name}MaxRegress{{{fmt(-min_improvement)} \sigma}}\n"
            bin_start = math.floor(min_improvement / bin_width)
            max_improvement = max(*improvement_over_baseline)
            tex += f"\def\{eval_name}MaxImprovement{{{fmt(max_improvement)} \sigma}}\n"
            bin_stop = math.ceil(max(*improvement_over_baseline) / bin_width)
            plt.hist(improvement_over_baseline, [x * bin_width for x in range(bin_start, bin_stop)], ec='black')
            plt.savefig(str(path.joinpath("sd.png")), bbox_inches='tight')
            plt.clf()
            img(src="sd.png")
    for name, filepath in subpages:
    	li(a(name, href=filepath))

if eval_name == "WEBIIBL":
    working_frac = anal_work.main()
    tex += f"\def\{eval_name}WorkingFrac{{{fmt(working_frac * 100)}\%}}\n"
    tex += f"\def\{eval_name}ExtraMemorySaving{{{fmt((1-x_projection)/(1-working_frac) * 100)}\%}}\n"
with open(str(path.joinpath("index.html")), "w") as f:
    f.write(str(doc))

if eval_name != "":
    subprocess.call("git pull", shell=True, cwd="../membalancer-paper")
    with open(f"../membalancer-paper/{eval_name}.tex", "w") as tex_file:
        tex_file.write(tex)

    dir = sorted(os.listdir("out"))[-1]
    shutil.copy(f"out/{dir}/plot.png", f"../membalancer-paper/{eval_name}_pareto.png")
    shutil.copy(f"out/{dir}/sd.png", f"../membalancer-paper/{eval_name}_sd.png")

    subprocess.call("git add -A", shell=True, cwd="../membalancer-paper")
    subprocess.call("git commit -am 'sync file generated from eval'", shell=True, cwd="../membalancer-paper")
    subprocess.call("git push", shell=True, cwd="../membalancer-paper")
os.system(f"xdg-open {path.joinpath('index.html')}")
