import json
import os
import statistics as stats
import glob
import math
import sys
from util import tex_def

TOTAL = "Total"

def fmt(x):
    if x > 10:
        return str(int(x))
    else:
        return "{:.1f}".format(x)

def tex_fmt(x):
    return f"\\num{{{fmt(x)}}}"

def tex_fmt_bold(x):
    return f"\\textbf{{{fmt(x)}}}"

def tex_def_table(row_num, col_name, definitions):
    return f"\def\{col_name}{row_num}{{{definitions}\\xspace}}\n"

def combine(membalancer_data, baseline_data, time_mb, time_baseline):
    tex_data = {TOTAL:
                {"l": 0,
                 "g": 0,
                 "s": 0,
                 "membalancer_exta_mem": 0,
                 "total_gc_time_mb": 0,
                 "total_run_time_mb": 0,
                 "current_v8_extra_mem": 0,
                 "total_gc_time_baseline": 0,
                 "total_run_time_baseline": 0}}

    for data in membalancer_data.values():
        name = data["name"]
        tex_data[name] = {}
        tex_data[name]["l"] = data["after_memory"] / 1e6
        tex_data[TOTAL]["l"] += tex_data[name]["l"]
        tex_data[name]["g"] = data["allocation_bytes"] / data["allocation_duration"] * 1e3
        tex_data[TOTAL]["g"] += tex_data[name]["g"]
        tex_data[name]["s"] = data["gc_bytes"] / data["gc_duration"] * 1e3
        tex_data[TOTAL]["s"] += tex_data[name]["s"]

        print(data)
        assert data["Limit"] > data["after_memory"]
        tex_data[name]["membalancer_exta_mem"] = (data["Limit"] - data["after_memory"]) / 1e6
        tex_data[TOTAL]["membalancer_exta_mem"] += tex_data[name]["membalancer_exta_mem"]

    for name in time_mb.keys():
        tex_data[name]["total_gc_time_mb"] = time_mb[name]["total_gc_time"]
        tex_data[TOTAL]["total_gc_time_mb"] += tex_data[name]["total_gc_time_mb"]
        tex_data[name]["total_run_time_mb"] = time_mb[name]["total_run_time"]
        tex_data[TOTAL]["total_run_time_mb"] += tex_data[name]["total_run_time_mb"]

    for data in baseline_data.values():
        name = data["name"]
        tex_data[name]["current_v8_extra_mem"] = (data["Limit"] - data["after_memory"]) / 1e6
        tex_data[TOTAL]["current_v8_extra_mem"] += tex_data[name]["current_v8_extra_mem"]

    for name in time_baseline.keys():
        tex_data[name]["total_gc_time_baseline"] = time_baseline[name]["total_gc_time"]
        tex_data[TOTAL]["total_gc_time_baseline"] += tex_data[name]["total_gc_time_baseline"]
        tex_data[name]["total_run_time_baseline"] = time_baseline[name]["total_run_time"]
        tex_data[TOTAL]["total_run_time_baseline"] += tex_data[name]["total_run_time_baseline"]

    return tex_data

def convert_to_tex(data, membalancer_dir, baseline_dir):
    all_keys = list(data.keys())
    all_keys.remove(TOTAL)
    all_keys.append(TOTAL)
    print(all_keys)
    one_key = all_keys[0]
    tex_str = ""
    tex_str += f"% membalancer_dir: {membalancer_dir}\n"
    tex_str += f"% baseline_dir: {baseline_dir}\n"
    row = 'A'
    for (idx, key) in enumerate(all_keys):
        l = data[key]["l"]
        g = data[key]["g"]
        s = data[key]["s"]
        total_run_time_mb = data[key]["total_run_time_mb"]
        total_gc_time_mb = data[key]["total_gc_time_mb"]
        total_run_time_baseline = data[key]["total_run_time_baseline"]
        total_gc_time_baseline = data[key]["total_gc_time_baseline"]
        tex_str += tex_def_table(row, "name", key)
        tex_str += tex_def_table(row, "l", f"{tex_fmt(l)}")
        tex_str += tex_def_table(row, "g", f"{tex_fmt(g)}")
        tex_str += tex_def_table(row, "s", f"{tex_fmt(s)}")
        mb_extra = data[key]["membalancer_exta_mem"]
        curr_extra = data[key]["current_v8_extra_mem"]
        if mb_extra < curr_extra:
            tex_str += tex_def_table(row, "mbextra", f"{tex_fmt_bold(mb_extra)}")
            tex_str += tex_def_table(row, "baseextra", f"{tex_fmt(curr_extra)}")
        elif mb_extra > curr_extra:
            tex_str += tex_def_table(row, "mbextra", f"{tex_fmt(mb_extra)}")
            tex_str += tex_def_table(row, "baseextra", f"{tex_fmt_bold(curr_extra)}")
        else:
            tex_str += tex_def_table(row, "mbextra", f"{tex_fmt(mb_extra)}")
            tex_str += tex_def_table(row, "baseextra", f"{tex_fmt(curr_extra)}")
        if total_run_time_mb < total_run_time_baseline:
            tex_str += tex_def_table(row, "mbruntime", f"{tex_fmt_bold(total_run_time_mb)}")
            tex_str += tex_def_table(row, "baseruntime", f"{tex_fmt(total_run_time_baseline)}")
        elif total_run_time_mb > total_run_time_baseline:
            tex_str += tex_def_table(row, "mbruntime", f"{tex_fmt(total_run_time_mb)}")
            tex_str += tex_def_table(row, "baseruntime", f"{tex_fmt_bold(total_run_time_baseline)}")
        else:
            tex_str += tex_def_table(row, "mbruntime", f"{tex_fmt(total_run_time_mb)}")
            tex_str += tex_def_table(row, "baseruntime", f"{tex_fmt(total_run_time_baseline)}")
        if total_gc_time_mb < total_gc_time_baseline:
            tex_str += tex_def_table(row, "mbgctime", f"{tex_fmt_bold(total_gc_time_mb)}")
            tex_str += tex_def_table(row, "basegctime", f"{tex_fmt(total_gc_time_baseline)}")
        elif total_gc_time_mb > total_gc_time_baseline:
            tex_str += tex_def_table(row, "mbgctime", f"{tex_fmt(total_gc_time_mb)}")
            tex_str += tex_def_table(row, "basegctime", f"{tex_fmt_bold(total_gc_time_baseline)}")
        else:
            tex_str += tex_def_table(row, "mbgctime", f"{tex_fmt(total_gc_time_mb)}")
            tex_str += tex_def_table(row, "basegctime", f"{tex_fmt(total_gc_time_baseline)}")
        row = ord(row)
        row += 1
        row = chr(row)
    return tex_str

def write_tex(tex_str, path):
    with open(path, "w") as tex_file:
        tex_file.write(tex_str)

def tex_compare_splay_pdfjs(data):
    splay_pdfjs_l = data["splay.js"]["l"]/data["pdfjs.js"]["l"]
    splay_pdfjs_g = data["splay.js"]["g"]/data["pdfjs.js"]["g"]
    splay_pdfjs_s = data["splay.js"]["s"]/data["pdfjs.js"]["s"]
    splay_pdfjs_extra_mem = math.sqrt(splay_pdfjs_l*splay_pdfjs_g/splay_pdfjs_s)
    tex_str = ""
    tex_str += tex_def("JSSplayPDFJSl", f"{tex_fmt(splay_pdfjs_l)}")
    tex_str += tex_def("JSSplayPDFJSg", f"{tex_fmt(splay_pdfjs_g)}")
    tex_str += tex_def("JSSplayPDFJSs", f"{tex_fmt(splay_pdfjs_s)}")
    tex_str += tex_def("JSSplayPDFJSgDivs", f"{tex_fmt(splay_pdfjs_g / splay_pdfjs_s)}")
    tex_str += tex_def("JSSplayPDFJSExtraMemSquared", f"{tex_fmt(splay_pdfjs_extra_mem ** 2)}")
    tex_str += tex_def("JSSplayPDFJSExtraMem", f"{tex_fmt(splay_pdfjs_extra_mem)}")
    return tex_str

def get_data_from_gc_log(gc_log):
    with open(gc_log) as f:
        for line in f.read().splitlines():
            data = json.loads(line)
            if data["before_time"] >= 15e9:
                return data

def get_table_data(data_dir):
    data = {}
    for name in glob.glob(data_dir + "/*.gc.log", recursive=True):
        tmp = get_data_from_gc_log(name)
        data[tmp["name"]] = tmp
    return data

def get_last_row(filepath):
    with open(filepath) as f:
        data = {}
        for line in f.read().splitlines():
            data = json.loads(line)
        return data
    return {}

def get_total_time(dir):
    # {"name": {"total_run_time":, "total_gc_time"}}
    data = {}
    path = dir+"/*.gc.log"
    print("path for total time: "+path)
    for name in glob.glob(path, recursive=True):
        last_row = get_last_row(name)
        name = last_row["name"]
        total_gc_time = last_row["total_major_gc_time"]/1e9
        total_run_time = last_row["after_time"]/1e9
        data[name] = {"total_gc_time": total_gc_time, "total_run_time": total_run_time}
    return data

def main(membalancer_log_dir, baseline_log_dir):
    data_mb = get_table_data(membalancer_log_dir)
    data_baseline = get_table_data(baseline_log_dir)
    time_mb = get_total_time(membalancer_log_dir)
    time_baseline = get_total_time(baseline_log_dir)
    combined_data = combine(data_mb, data_baseline, time_mb, time_baseline)
    converted_tex = convert_to_tex(combined_data, membalancer_log_dir, baseline_log_dir)
    converted_tex += tex_compare_splay_pdfjs(combined_data)
    write_tex(converted_tex, "../membalancer-paper/data/js_table.tex")

if __name__ == "__main__":
    assert(len(sys.argv) == 3)
    membalancer_log_dir = sys.argv[1]
    baseline_log_dir = sys.argv[2]
    main(membalancer_log_dir, baseline_log_dir)
    print("done creating tex file for table!")
