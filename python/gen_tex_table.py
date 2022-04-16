import json
import os
import statistics as stats
import glob
import sys
from  util import tex_fmt, fmt, tex_fmt_bold
TOTAL = "Total"
def tex_def_table(row_num, col_name, definitions):
    return f"\def\{col_name}{row_num}{{{definitions}\\xspace}}\n"
	
def combine(membalancer_data, baseline_data, time_mb, time_baseline, membalancer_dir, baseline_dir):
	tex_data = {TOTAL: {"w": 0, "g": 0, "s": 0, "membalancer_exta_mem": 0, "total_gc_time_mb": 0, "total_run_time_mb": 0, "total_gc_time_mb": 0, "total_run_time_mb": 0, "current_v8_extra_mem": 0, "total_gc_time_baseline": 0, "total_run_time_baseline": 0, "membalancer_dir": "", "baseline_dir": ""}}
	
	for data in membalancer_data:
		name = data["name"]
		tex_data[name] = {}
		tex_data[name]["w"] = data["mem_diff"]
		tex_data[TOTAL]["w"] += tex_data[name]["w"]
		
		tex_data[name]["g"] = data["gc_rate"]
		tex_data[TOTAL]["g"] += tex_data[name]["g"]
		
		tex_data[name]["s"] = data["gc_speed"]
		tex_data[TOTAL]["s"] += tex_data[name]["s"]
		
		tex_data[name]["membalancer_exta_mem"] = data["extra_mem"]
		tex_data[TOTAL]["membalancer_exta_mem"] += tex_data[name]["membalancer_exta_mem"]
		
		tex_data[name]["membalancer_dir"] = membalancer_dir
	
	for name in time_mb.keys():
		tex_data[name]["total_gc_time_mb"] = time_mb[name]["total_gc_time"]
		tex_data[TOTAL]["total_gc_time_mb"] += tex_data[name]["total_gc_time_mb"]
		
		tex_data[name]["total_run_time_mb"] = time_mb[name]["total_run_time"]
		tex_data[TOTAL]["total_run_time_mb"] += tex_data[name]["total_run_time_mb"]
	
	for data in baseline_data:
		name = data["name"]
		tex_data[name]["current_v8_extra_mem"] = data["extra_mem"]
		tex_data[TOTAL]["current_v8_extra_mem"] += tex_data[name]["current_v8_extra_mem"]
		
		tex_data[name]["baseline_dir"] = baseline_dir
		
	for name in time_baseline.keys():
		tex_data[name]["total_gc_time_baseline"] = time_baseline[name]["total_gc_time"]
		tex_data[TOTAL]["total_gc_time_baseline"] += tex_data[name]["total_gc_time_baseline"]
		
		tex_data[name]["total_run_time_baseline"] = time_baseline[name]["total_run_time"]
		tex_data[TOTAL]["total_run_time_baseline"] += tex_data[name]["total_run_time_baseline"]
	return tex_data
	
def convert_to_tex(data):
	all_keys = list(data.keys())
	all_keys.remove(TOTAL)
	all_keys.append(TOTAL)
	print(all_keys)
	one_key = all_keys[0]
	tex_str = "% membalancer_dir: "+ data[one_key]["membalancer_dir"]+ "\n % baseline_dir: "+data[one_key]["baseline_dir"]+" \n"
	row = 'A'
	for (idx, key) in enumerate(all_keys):
		w = data[key]["w"]
		g = data[key]["g"]
		s = data[key]["s"]
		mb_extra = data[key]["membalancer_exta_mem"]
		curr_extra = data[key]["current_v8_extra_mem"]
		total_run_time_mb = data[key]["total_run_time_mb"]
		total_gc_time_mb = data[key]["total_gc_time_mb"]
		total_run_time_baseline = data[key]["total_run_time_baseline"]
		total_gc_time_baseline = data[key]["total_gc_time_baseline"]
		
		
		tex_str += tex_def_table(row, "name", key)
		tex_str += tex_def_table(row, "w", f"{tex_fmt(w)}")
		tex_str += tex_def_table(row, "g", f"{tex_fmt(g)}")
		tex_str += tex_def_table(row, "s", f"{tex_fmt(s)}")
		tex_str += tex_def_table(row, "mbextra", f"{tex_fmt(mb_extra)}")
		tex_str += tex_def_table(row, "baseextra", f"{tex_fmt(curr_extra)}")
		
		if total_run_time_mb < total_run_time_baseline:
			tex_str += tex_def_table(row, "mbruntime", f"{tex_fmt_bold(total_run_time_mb)}")
			tex_str += tex_def_table(row, "baseruntime", f"{tex_fmt(total_run_time_baseline)}")
		elif total_run_time_mb > total_run_time_baseline:
			tex_str += tex_def_table(row, "mbruntime", f"{tex_fmt(total_run_time_mb)}")
			tex_str += tex_def_table(row, "baseruntime", f"{tex_fmt_bold(total_run_time_baseline)}")
			
		if total_gc_time_mb < total_gc_time_baseline:
			tex_str += tex_def_table(row, "mbgctime", f"{tex_fmt_bold(total_gc_time_mb)}")
			tex_str += tex_def_table(row, "basegctime", f"{tex_fmt(total_gc_time_baseline)}")
		elif total_gc_time_mb > total_gc_time_baseline:
			tex_str += tex_def_table(row, "mbgctime", f"{tex_fmt(total_gc_time_mb)}")
			tex_str += tex_def_table(row, "basegctime", f"{tex_fmt_bold(total_gc_time_baseline)}")
		
		row = ord(row)
		row += 1
		row = chr(row)
	return tex_str

def write_tex(tex_str, path):
	with open(path, "w") as tex_file:
		tex_file.write(tex_str)
	
def get_optimal_table(data):
	
	min_w = 100000
	result = data[0]
	for each_row in data:
		for each_pgm in each_row:
			if each_pgm["name"] == "pdfjs.js":
				diff_w = abs(each_pgm["mem_diff"] - 50)
				if diff_w < min_w:
					result = each_row
					min_w = diff_w
	print("optimal table_data: "+ str(result))
	return result

def get_tex_data(dirname, filename):
	with open(dirname+"/"+filename) as f:
		data = []
		for line in f.read().splitlines():
			data = json.loads(line)
		return data
	return []

def get_last_row(filepath):
	with open(filepath) as f:
		data = {}
		for line in f.read().splitlines():
			data = json.loads(line)
		return data
	return {}

def get_table_data(mb_dir, baseline_dir):
	
	mb_raw_data = get_tex_data(mb_dir, "tex_data")
	sz = int(len(mb_raw_data)/3)
	mb_data =  get_optimal_table(mb_raw_data[sz:])
	
	baseline_raw_data = get_tex_data(baseline_dir, "tex_data")
	sz = int(len(baseline_raw_data)/3)
	baseline_data = get_optimal_table(baseline_raw_data[sz:])
	return (mb_data, baseline_data)

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
	(data_mb, data_baseline) = get_table_data(membalancer_log_dir, baseline_log_dir)
	time_mb = get_total_time(membalancer_log_dir)
	time_baseline = get_total_time(baseline_log_dir)
	
	combined_data = combine(data_mb, data_baseline, time_mb, time_baseline, membalancer_log_dir, baseline_log_dir)
	converted_tex = convert_to_tex(combined_data)
	write_tex(converted_tex, "../membalancer-paper/js_table.tex")
	
if __name__ == "__main__":
	assert(len(sys.argv) == 3)
	membalancer_log_dir = sys.argv[1]
	baseline_log_dir = sys.argv[2]
	main(membalancer_log_dir, baseline_log_dir)
	print("done creating tex file for table!")

		
		
	
