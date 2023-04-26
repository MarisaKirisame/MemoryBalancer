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
from util import tex_fmt, fmt, tex_def
import util
import parse_gc_log
from EVAL import *
from anal_common import Run, Experiment
import single_run_analysis as sra

from matplotlib.ticker import FormatStrFormatter
from git_check import get_commit
import argparse
import analysis_charts

# paper.pull()

parser = argparse.ArgumentParser()
# parser.add_argument("--action", default="", help="what to do to the generated html")
parser.add_argument("--dir", default="", help="what to do to the generated html")
args = parser.parse_args()
# action = args.action


all_stats = []
benchmark = ""
input_dir = args.dir

# assert action in ["check", "open", "upload", "paper"]

class page(dominate.document):
    def __init__(self, path, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.path = path

    def _add_to_ctx(self):
        pass # don't add to contexts

    def __exit__(self, *args):
        super().__exit__(*args)
        with open(str(self.path), "w") as f:
            f.write(str(self))

class Counter:
    def __init__(self):
        self.count = 0

    def __call__(self):
        ret = self.count
        self.count += 1
        return ret

pre_path = time.strftime("%Y-%m-%d-%H-%M-%S")
path = Path("out/" + pre_path)
path.mkdir(parents=True, exist_ok=True)

tex = ""
tex += f"% path: membalancer.uwplse.org/{pre_path}\n"

commit = None
for name in glob.glob('log/**/commit', recursive=True):
    with open(name) as f:
        if commit == None:
            commit = eval(f.read())
        else:
            pass
            #assert commit == eval(f.read())
# tex += tex_def("MBHash", commit["membalancer"])
# tex += tex_def("VEightHash", commit["v8"])

png_counter = Counter()
html_counter = Counter()
txt_counter = Counter()

def gen_anal_gc_log(cfg, exp):
    html_path = f"{html_counter()}.html"
    with page(path=path.joinpath(html_path), title=str(cfg)) as doc:
        anal_gc_log.main(cfg, exp)
        png_path = f"{png_counter()}.png"
        plt.savefig(str(path.joinpath(png_path)), bbox_inches='tight')
        plt.clf()
        img(src=png_path)
        p(f"cfg = {cfg}")
        p(f"total_memory = {exp.average_benchmark_memory()/1e6}")
        p(f"old_gen_mem = {exp.avg_old_gen_memory()/1e6}")
        p(f"yg_memory_periodic = {exp.get_yg_avg_memory_periodic()/1e6}")
        p(f"yg_memory = {exp.avg_yg_memory()/1e6}")
        
        p(f"total_time = {exp.total_major_gc_time()/1e9}")
        p(f"old_gen_gc_time = {exp.old_gen_total_time()/1e9}")
        p(f"yg_gen_gc_time = {exp.yg_gc_total_time()/1e9}")
        p(f"total_promoted_bytes = {exp.total_promoted_bytes()/1e6}")
        p(f"total_allocated_bytes = {exp.total_allocated_bytes()/1e6}")
        p(f"total_copied_bytes = {exp.total_copied_bytes()/1e6}")
        p(f"yg_total_before_memory = {exp.yg_total_before_memory()/1e6}")
        p(f"yg_total_after_memory = {exp.yg_total_after_memory()/1e6}")
        p(f"total Old gen bytes = {exp.get_total_old_gc_bytes()/1e6}")
        p(f"avg Old gen bytes = {exp.get_avg_old_gc_bytes()/1e6}")
        p(f"total og allocated bytes = {exp.og_allocated_bytes()/1e6}")
        p(f"p/g = {exp.total_promoted_bytes()/exp.total_allocated_bytes()}")
        tmp_dict = {}
        # tmp_dict['bench'] = cfg['BENCH']
        tmp_dict["benchmark"] = benchmark
        if 'GC_RATE_D' in cfg['RESIZE_CFG']:
            tmp_dict['c_value'] = cfg['RESIZE_CFG']['GC_RATE_D']
        tmp_dict['strategy'] = cfg['BALANCE_STRATEGY']
        tmp_dict['total_memory'] = exp.average_benchmark_memory()/1e6
        tmp_dict['old_gen_mem'] = exp.avg_old_gen_memory()/1e6
        tmp_dict['yg_memory'] = exp.avg_yg_memory()/1e6
        tmp_dict['total_time'] = exp.total_major_gc_time()/1e9
        tmp_dict['old_gen_total_time'] = exp.old_gen_total_time()/1e9
        tmp_dict['yg_gc_total_time'] = exp.yg_gc_total_time()/1e9
        tmp_dict['total_promoted_bytes'] = exp.total_promoted_bytes()/1e6
        tmp_dict['total_allocated_bytes'] = exp.total_allocated_bytes()/1e6
        tmp_dict['total_copied_bytes'] = exp.total_copied_bytes()/1e6
        tmp_dict['yg_total_before_memory'] = exp.yg_total_before_memory()/1e6
        tmp_dict['yg_total_after_memory'] = exp.yg_total_after_memory()/1e6
        tmp_dict['p_g'] = exp.total_promoted_bytes()/exp.total_allocated_bytes()
        all_stats.append(tmp_dict)



        bd = exp.perf_breakdown()
        for name in sorted(list(bd.keys())):
            (memory, time) = bd[name]
            p(f"{name}_memory = {memory}")
            p(f"{name}_time = {time}")

        for dirname in exp.all_dirname():
            for filename in os.listdir(dirname):
                if filename not in ["cfg", "score"]:
                    txt_path = f"{txt_counter()}.txt"
                    shutil.copy(dirname + "/" + filename, path.joinpath(txt_path))
                    li(a(filename, href=txt_path))
    return html_path

def gen_megaplot_bench(m, bench):
    html_path = f"{html_counter()}.html"
    with page(path=path.joinpath(html_path), title=str(bench)) as doc:
        mp = megaplot.plot(m, [bench], str(bench), normalize_baseline=False)
        points = mp["points"]
        def sorted_by(p):
            resize_cfg = p.cfg["RESIZE_CFG"]
            return 0 if resize_cfg["RESIZE_STRATEGY"] == "ignore" else 1/-resize_cfg["GC_RATE_D"]
        points.sort(key=sorted_by)
        png_path = f"{png_counter()}.png"
        plt.savefig(str(path.joinpath(png_path)), bbox_inches='tight')
        plt.clf()
        img(src=png_path)
        with table():
            with tr():
                th("memory")
                th("time")
                th("GC_RATE_D")
                th("link")
            for point in points:
                with tr():
                    td(round(point.memory,2))
                    td(round(point.time, 2))
                    resize_cfg = point.cfg["RESIZE_CFG"]
                    td("ignore" if resize_cfg["RESIZE_STRATEGY"] == "ignore" else resize_cfg["GC_RATE_D"])
                    td(a(str(point.cfg), href=gen_anal_gc_log(point.cfg, point.exp)))
    return html_path

def g_fmt(x):
	return "{0:.2g}".format(float(x))

def tex_g_fmt(x):
    return f"\\num{{{g_fmt(x)}}}"

def format_sigma(x, pos):
    if x == 0:
        return "baseline"
    else:
        sigma = '\u03C3'
        return ("+" if x > 0 else "") + str(x) + sigma

def gen_eval(tex_name, m, *, anal_frac=None, show_baseline=True, reciprocal_regression=True, normalize_baseline=True):
    html_path = f"{html_counter()}.html"
    with page(path=path.joinpath(html_path), title='Plot') as doc:
        megaplot.plot(m, m.keys(), tex_name, legend=False, show_baseline=show_baseline, reciprocal_regression=True, normalize_baseline=normalize_baseline, invert_graph=False)
        png_path = f"{tex_name}plot.png"
        plt.savefig(str(path.joinpath(png_path)), bbox_inches='tight')
        # plt.savefig(f"../membalancer-paper/img/{png_path}", bbox_inches='tight')
        plt.clf()
        img(src=png_path)
        mp = megaplot.plot(m, m.keys(), tex_name, legend=False)
        plt.clf()
        points = mp["points"]
        transformed_points = mp["transformed_points"]

        if "coef" in mp:
            coef = mp["coef"]
            slope, bias = coef
            sd = mp["sd"]
            def get_deviate_in_sd(x, y):
                return (y - (x * slope + bias)) / sd
            y_projection = slope+bias
            speedup = (1-1/y_projection)
            global tex
            tex += tex_def(tex_name + "Speedup", f"{tex_fmt(speedup*100)}\%")
            x_projection = (1-bias)/slope
            memory_saving = (1-1/x_projection)
            tex += tex_def(tex_name + "MemorySaving", f"{tex_fmt(memory_saving*100)}\%")
            p(f"speedup = {fmt(speedup*100)}%")
            p(f"memory_saving = {fmt(memory_saving*100)}%")
            baseline_deviate = get_deviate_in_sd(1, 1)
            p(f"improvement = {fmt(-baseline_deviate)} sigma")
            tex += tex_def(tex_name + "Improvement", f"{tex_fmt(-baseline_deviate)}\,\sigma")
            if anal_frac is not None:
                tex += tex_def("WorkingFrac", f"{tex_fmt(anal_frac * 100)}\%")
                tex += tex_def("ExtraMemorySaving", f"{tex_fmt((1-1/x_projection)/(1-anal_frac) * 100)}\%")
            improvement_over_baseline = []
            for point in transformed_points:
                if not point.is_baseline:
                    improvement_over_baseline.append(get_deviate_in_sd(point.memory, point.time) - baseline_deviate)
            if len(improvement_over_baseline) > 1:
                pvalue = stats.ttest_1samp(improvement_over_baseline, 0.0, alternative="greater").pvalue
                tex += tex_def(tex_name + "PValue", f"{tex_g_fmt(pvalue)}")
                p(f"""pvalue={g_fmt(pvalue)}""")
                bin_width = 0.5
                min_improvement = min(*improvement_over_baseline)
                tex += tex_def(tex_name + "MaxRegress", f"{tex_fmt(-min_improvement)}\,\sigma")
                max_improvement = max(*improvement_over_baseline)
                tex += tex_def(tex_name + "MaxImprovement", f"{tex_fmt(max_improvement)}\,\sigma")
                distance_from_zero = max(abs(min_improvement), abs(max_improvement))
                bin_start = math.floor(-distance_from_zero / bin_width)
                bin_stop = math.ceil(distance_from_zero / bin_width)
                plt.hist(improvement_over_baseline, [x * bin_width for x in range(bin_start, bin_stop + 1)], ec='black')
                plt.axvline(x=0, color="black")
                plt.gca().xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(format_sigma))
                png_path = f"{tex_name}sd.png"
                plt.savefig(str(path.joinpath(png_path)), bbox_inches='tight')
                # plt.savefig(f"../membalancer-paper/img/{png_path}", bbox_inches='tight')
                plt.clf()
                img(src=png_path)
                p_g_plots = glob.glob(str(path)+"/promotion_rate*")
                for each_plot in p_g_plots:
                    li(a(str(each_plot), href=Path(each_plot).name))
                    img(src=each_plot)
                
        for bench in m.keys():
            li(a(str(bench), href=gen_megaplot_bench(m, bench)))
    return html_path

def calculate_extreme_improvement(directory, m):
    mp = megaplot.plot(m, m.keys(), "extreme") # todo - no plot only anal
    plt.clf()
    bl_time = mp["baseline_time"] * 1e9
    bl_memory = mp["baseline_memory"] * 1e6
    max_speedup = 0
    max_saving = 0
    for name in glob.glob(f'{directory}/**/score', recursive=True):
        dirname = os.path.dirname(name)
        e = Experiment([Run(dirname)])
        max_speedup = max(max_speedup, (bl_time / e.total_major_gc_time()) - 1)
        max_saving = max(max_saving, 1 - (e.average_benchmark_memory() / bl_memory))
    global tex
    tex += tex_def("JSMaxSpeedup", f"{tex_fmt(max_speedup * 100)}\%")
    tex += tex_def("JSMaxSaving", f"{tex_fmt(max_saving * 100)}\%")

def gen_jetstream(directory):
    print("Started gen_jetstream")
    m = megaplot.anal_log(directory)
    m_exp = {benches: {cfg: [Experiment([x]) for x in aggregated_runs] for cfg, aggregated_runs in per_benches_m.items()} for benches, per_benches_m in m.items()}
    # calculate_extreme_improvement(directory, m_exp)
    found_baseline = False
    found_compare = False
    tex_table_baseline_dir = None
    tex_table_membalancer_dir = None
    JSCompareAt = -2e-8
    for name in glob.glob(f'{directory}/**/score', recursive=True):
        dirname = os.path.dirname(name)
        with open(dirname + "/cfg") as f:
            cfg = eval(f.read())
        # sra.process_dir(dirname, cfg, path)
        if cfg["CFG"]["BALANCER_CFG"]["BALANCE_STRATEGY"] == "ignore":
            if not found_baseline:
            	found_baseline = True
            	tex_table_baseline_dir = dirname
            	anal_gc_log.main(cfg, Experiment([Run(dirname + "/")]), legend=False)
            	plt.xlim([0, 40])
            	plt.ylim([0, 450])
            	# plt.savefig(f"../membalancer-paper/img/js_baseline_anal.png", bbox_inches='tight')
            	plt.clf()
        elif cfg["CFG"]["BALANCER_CFG"]["RESIZE_CFG"]["GC_RATE_D"] == JSCompareAt:
            if not found_compare:
                found_compare = True
                global tex
                tex += tex_def("CompareAt", tex_fmt(JSCompareAt*-1e9))
                tex_table_membalancer_dir = dirname
                anal_gc_log.main(cfg, Experiment([Run(dirname + "/")]), legend=False)
                plt.xlim([0, 40])
                plt.ylim([0, 450])
                # plt.savefig(f"../membalancer-paper/img/js_membalancer_anal.png", bbox_inches='tight')
                plt.clf()
    # gen_tex_table.main(tex_table_membalancer_dir, tex_table_baseline_dir)
    # parse_gc_log.main([tex_table_membalancer_dir], [tex_table_baseline_dir], "JS")
    return gen_eval("JETSTREAM", m_exp)

def gen_acdc(directory):
    m = megaplot.anal_log(directory)
    m_exp = {benches: {cfg: [Experiment([x]) for x in aggregated_runs] for cfg, aggregated_runs in per_benches_m.items()} for benches, per_benches_m in m.items()}
    return gen_eval("ACDC", m_exp, normalize_baseline=False, reciprocal_regression=False)

def gen_browser(directory, i):
    m = megaplot.anal_log(dd)
    def n_choose_k(n, k):
        if k == 0:
            return ((),)
        elif len(n) == 0:
            return ()
        else:
            return n_choose_k(n[1:], k) + tuple(x + (n[0],) for x in n_choose_k(n[1:], k-1))
    def un_1_tuple(x):
        assert len(x) == 1
        return x[0]
    all_bench = list([un_1_tuple(x) for x in m.keys()])
    real_m = {}
    for benches in n_choose_k(all_bench, i):
        per_benches_m = {}
        for bench in benches:
            m_bench = m[(bench,)]
            for cfg, runs in m_bench.items():
                if cfg not in per_benches_m:
                    per_benches_m[cfg] = [[x] for x in runs]
                else:
                    pbmcfg = per_benches_m[cfg]
                    for j in range(min(len(pbmcfg), len(runs))):
                        pbmcfg[j].append(runs[j])
        real_m[benches] = {cfg: [Experiment(x) for x in aggregated_runs if len(x) == i] for cfg, aggregated_runs in per_benches_m.items()}
    return gen_eval(f"WEB{i * 'I'}", real_m, anal_frac=(anal_work.main(directory) if i == 1 else None))

def print_stats(output_dir):
    path = output_dir.joinpath("stats.html")
    print("writing stats")
    with page(path=path, title=str("Stats")) as doc:
        with table(border=1, style="table-layout: fixed;"):
            with tr():
                th('benchmark')
                th('strategy')
                # th('semispace_size')
                th('c_value')
                th('total_memory')
                th('old_gen_mem')
                th('yg_memory')
                th('total_time')
                th('old_gen_total_time')
                th('yg_gc_total_time')
                th('total_promoted_bytes')
                th('total_allocated_bytes')
                th('total_copied_bytes')
                th('yg_total_before_memory')
                th('yg_total_after_memory')
                th('p_g')
            for each_stat in all_stats:
                with tr():
                    th(each_stat['benchmark'])
                    th(each_stat['strategy'])
                    # th(each_stat['semispace_size'])
                    if 'c_value' in each_stat:
                        c = each_stat['c_value']
                    else:
                        c = 0
                    th(c)
                    th(each_stat['total_memory'])
                    th(each_stat['old_gen_mem'])
                    th(each_stat['yg_memory'])
                    th(each_stat['total_time'])
                    th(each_stat['old_gen_total_time'])
                    th(each_stat['yg_gc_total_time'])
                    th(each_stat['total_promoted_bytes'])
                    th(each_stat['total_allocated_bytes'])
                    th(each_stat['total_copied_bytes'])
                    th(each_stat['yg_total_before_memory'])
                    th(each_stat['yg_total_after_memory'])
                    th(each_stat['p_g'])


with page(path=path.joinpath("index.html"), title='Main') as doc:
    d = list(Path(input_dir).iterdir()) 
    for d_elem in d:
        if not d_elem.is_dir():
            continue;
        for dd in d_elem.iterdir():
            if dd.is_dir():
                analysis_charts.plot_promotion_rate(str(dd), str(path))
                with open(f"{dd}/cfg", "r") as f:
                    cfg = eval(f.read())
                    name = cfg["NAME"]
                    benchmark = cfg['CFG']['BENCH']
                if name == "jetstream":
                    li(a("jetstream", href=gen_jetstream(dd)))
                elif name == "acdc":
                    li(a("acdc", href=gen_acdc(dd)))
                elif name in ["browseri", "browserii", "browseriii"]:
                    m = megaplot.anal_log(dd)
                    m_exp = {benches: {cfg: [Experiment([x]) for x in aggregated_runs] for cfg, aggregated_runs in per_benches_m.items()} for benches, per_benches_m in m.items()}
                    li(a(name, href=gen_eval(name.upper(), m_exp)))
                    #for i in [1, 2, 3]:
                    #    li(a(f"browser_{i}", href=gen_browser(dd, i)))
                else:
                    raise
    print_stats(path)
    tex_file_name = "EVAL.tex.txt"
    with open(path.joinpath(tex_file_name), "w") as tex_file:
        tex_file.write(tex)
    li(a("tex", href=tex_file_name))

# if action == "open":
os.system(f"xdg-open {path.joinpath('index.html')}")

