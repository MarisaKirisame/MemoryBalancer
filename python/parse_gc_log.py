import json
import os
import glob
import sys
import matplotlib.pyplot as plt

def get_data(filepath):
	data = []
	with open(filepath) as f:
		for line in f.read().splitlines():
			data.append(json.loads(line))
	return data

def evaluate_c(file_data):
	c_vals = [] #(time, c)
	prev_w = 0
	for each_entry in file_data:
		g = each_entry["allocation_bytes"]/each_entry["allocation_duration"]
		s = each_entry["gc_bytes"]/each_entry["gc_duration"]
		m = each_entry["before_memory"]
		t = each_entry["after_time"]
		c = (g*prev_w)/(s* (m-prev_w)**2)
		prev_w = each_entry["after_memory"]
		c_vals.append((t, c))
	return c_vals
	
def plot_c(all_c_vals, title):
	
	for name in all_c_vals.keys():
		plt.plot([p[0] for p in all_c_vals[name]], [p[1] for p in all_c_vals[name]], label=name)
	plt.title(title)
	plt.legend()
	plt.show()
	
#	plt.legend()
#	plt.show()
	
def parse_gc_logs(dir):
	
	data = {}
	path = dir+"/*.gc.log"
	for name in glob.glob(path, recursive=True):
		file_data = get_data(name)
		name = file_data[0]["name"]
		all_c = evaluate_c(file_data)
		data[name] = all_c
	return data
#		print(all_c)
#		plot_c(all_c, name)
		
def main(mb_dir, base_dir):
	mb_data = parse_gc_logs(mb_dir)
	plot_c(mb_data, "Membalancer")
	base_data = parse_gc_logs(base_dir)
	plot_c(base_data, "Baseline")
	
	
if __name__ == "__main__":
    assert(len(sys.argv) == 3)
    main(sys.argv[1], sys.argv[2])
		
		
	

