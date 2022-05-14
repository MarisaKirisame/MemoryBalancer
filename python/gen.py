import dominate
from dominate.tags import *
import megaplot
import anal_gc_log
import matplotlib
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
import gen_tex_table
import paper
from util import tex_fmt, fmt, tex_def_generic
import util
import parse_gc_log

from matplotlib.ticker import FormatStrFormatter
from git_check import get_commit
import argparse

parser = argparse.ArgumentParser()
parser.add_argument("--eval_name", default="", help="name of the evaluation")
parser.add_argument("--action", default="", help="what to do to the generated html")
args = parser.parse_args()
eval_name = args.eval_name
action = args.action

assert eval_name in [
    "", # do not generate+upload tex or plot for the paper
    "WEBI", # 1 website run
    "WEBII", # 2 website run
    "WEBIII", # 3 website run
    "JS", # JetStream, embedded v8
]

assert action in ["", "open", "upload"]

class Counter:
    def __init__(self):
        self.count = 0

    def __call__(self):
        ret = self.count
        self.count += 1
        return ret

def tex_def(name, definition):
    return tex_def_generic(eval_name, name, definition)

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

def g_fmt(x):
	return "{0:.2g}".format(float(x))

def tex_g_fmt(x):
    return f"\\num{{{g_fmt(x)}}}"

# as dominate do not support recursive call of document(), we have to do some weird plumbing and generate the inner doc before the outer doc.
with dominate.document(title='Plot') as doc:
    mp = megaplot.plot(m, m.keys())
    points = mp["points"]
    transformed_points = mp["transformed_points"]
    if "coef" in mp:
        coef = mp["coef"]
        slope, bias = coef
        sd = mp["sd"]
    png_path = f"{png_counter()}.png"
    plt.savefig(str(path.joinpath(png_path)), bbox_inches='tight')
    plt.clf()
    img(src=png_path)
    megaplot.plot(m, m.keys(), legend=False)
    plt.savefig(str(path.joinpath("plot.png")), bbox_inches='tight')
    plt.clf()
    def get_deviate_in_sd(x, y):
        return (y - (x * slope + bias)) / sd
    if "coef" in mp:
        y_projection = slope+bias
        tex += tex_def("Speedup", f"{tex_fmt((1-1/y_projection)*100)}\%")
        x_projection = (1-bias)/slope
        tex += tex_def("MemorySaving", f"{tex_fmt((1-1/x_projection)*100)}\%")
        p(f"{(1.0, fmt(y_projection))}")
        p(f"{(fmt(x_projection), 1.0)}")
        baseline_deviate = get_deviate_in_sd(1, 1)
        p(f"improvement = {fmt(-baseline_deviate)} sigma")
        tex += tex_def("Improvement", f"{tex_fmt(-baseline_deviate)}\sigma")
        improvement_over_baseline = []
        for point in transformed_points:
            assert not point.is_baseline
            improvement_over_baseline.append(get_deviate_in_sd(point.memory, point.time) - baseline_deviate)
        if len(improvement_over_baseline) > 1:
            pvalue = stats.ttest_1samp(improvement_over_baseline, 0.0, alternative="greater").pvalue
            tex += tex_def("PValue", f"{tex_g_fmt(pvalue)}")
            p(f"""pvalue={g_fmt(pvalue)}""")
            bin_width = 0.5
            min_improvement = min(*improvement_over_baseline)
            tex += tex_def("MaxRegress", f"{tex_fmt(-min_improvement)}\sigma")
            max_improvement = max(*improvement_over_baseline)
            tex += tex_def("MaxImprovement", f"{tex_fmt(max_improvement)}\sigma")
            distance_from_zero = max(abs(min_improvement), abs(max_improvement))
            #bin_start = math.floor(min_improvement / bin_width)
            bin_start = math.floor(-distance_from_zero / bin_width)
            #bin_stop = math.ceil(max_improvement / bin_width)
            bin_stop = math.ceil(distance_from_zero / bin_width)
            print((bin_start, bin_stop))
            plt.hist(improvement_over_baseline, [x * bin_width for x in range(bin_start, bin_stop + 1)], ec='black')
            plt.axvline(x=0, color="black")
            def format_sigma(x, pos):
                if x == 0:
                    return "baseline"
                else:
                    sigma = '\u03C3'
                    return ("+" if x > 0 else "") + str(x) + sigma
            plt.gca().xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(format_sigma))
            plt.savefig(str(path.joinpath("sd.png")), bbox_inches='tight')
            plt.clf()
            img(src="sd.png")
    for name, filepath in subpages:
    	li(a(name, href=filepath))

with open(str(path.joinpath("index.html")), "w") as f:
    f.write(str(doc))

if eval_name == "WEBII":
    working_frac = anal_work.main()
    tex += tex_def("WorkingFrac", f"{tex_fmt(working_frac * 100)}\%")
    tex += tex_def("ExtraMemorySaving", f"{tex_fmt((1-1/x_projection)/(1-working_frac) * 100)}\%")

def calculate_extreme_improvement():
    mp = megaplot.plot(m, m.keys()) # todo - no plot only anal
    plt.clf()
    bl_time = mp["baseline_time"] * 1e9
    bl_memory = mp["baseline_memory"] * 1e6
    max_speedup = 0
    max_saving = 0
    for name in glob.glob('log/**/score', recursive=True):
        with open(name) as f:
            score = json.load(f)
            max_speedup = max(max_speedup, (bl_time / score["MAJOR_GC_TIME"]) - 1)
            max_saving = max(max_saving, 1 - (score["Average(BenchmarkMemory)"] / bl_memory))
    global tex
    tex += tex_def("MaxSpeedup", f"{tex_fmt(max_speedup * 100)}\%")
    tex += tex_def("MaxSaving", f"{tex_fmt(max_saving * 100)}\%")

if eval_name == "JS":
    calculate_extreme_improvement()
    found_baseline = False
    tex_table_baseline_dir = None
    tex_table_membalancer_dir = None
    for name in glob.glob('log/**/score', recursive=True):
        dirname = os.path.dirname(name)
        with open(dirname + "/cfg") as f:
            cfg = eval(f.read())
        if cfg["BALANCER_CFG"]["BALANCE_STRATEGY"] == "ignore":
            if not found_baseline:
            	tex_table_baseline_dir = dirname
            	found_baseline = True
            	anal_gc_log.main(dirname + "/", legend=False)
            	plt.xlim([0, 50])
            	plt.ylim([0, 400])
            	plt.savefig(f"../membalancer-paper/js_baseline_anal.png", bbox_inches='tight')
            	plt.clf()
        elif cfg["BALANCER_CFG"]["RESIZE_CFG"]["GC_RATE_D"] == -5e-10:
            tex_table_membalancer_dir = dirname
            anal_gc_log.main(dirname + "/", legend=False)
            plt.xlim([0, 50])
            plt.ylim([0, 400])
            plt.savefig(f"../membalancer-paper/js_membalancer_anal.png", bbox_inches='tight')
            plt.clf()
    gen_tex_table.main(tex_table_membalancer_dir, tex_table_baseline_dir)
    parse_gc_log.main([tex_table_membalancer_dir], [tex_table_baseline_dir], "JS")

if eval_name != "":
    tex += tex_def("GraphHash", get_commit("./"))

for name in glob.glob('log/**/commit', recursive=True):
    commit = None
    with open(name) as f:
        if commit == None:
            commit = eval(f.read())
        else:
            assert commit == eval(f.read())
tex += tex_def("MBHash", commit["membalancer"])
tex += tex_def("VEightHash", commit["v8"])

dir = str(path)

if eval_name != "":
    paper.pull()
    with open(f"../membalancer-paper/{eval_name}.tex", "w") as tex_file:
        tex_file.write(tex)
    shutil.copy(f"{dir}/plot.png", f"../membalancer-paper/{eval_name}_pareto.png")
    shutil.copy(f"{dir}/sd.png", f"../membalancer-paper/{eval_name}_sd.png")
    paper.push()

if action == "open":
    os.system(f"xdg-open {path.joinpath('index.html')}")
elif action == "upload":
    server_name = "uwplse.org:/var/www/membalancer"
    os.system(f"scp -r {dir} {server_name}")
