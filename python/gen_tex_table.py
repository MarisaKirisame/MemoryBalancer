import json
import os
import statistics as stats
import glob

path1 = "/Users/u1365432/Documents/Research/Pavel/code/MemoryBalancer/log/2022-04-11-17-58-21/2022-04-11-17-58-21/2022-04-11-17-58-21/tex_data"
path2 = "/Users/u1365432/Documents/Research/Pavel/code/MemoryBalancer/log/2022-04-11-17-58-21/2022-04-11-17-58-21/2022-04-11-18-00-12/tex_data"

def parseJSON(path):

	with open(path) as f:
		data = []
		for line in f.read().splitlines():
			data = json.loads(line)
		w = []
		for each_entry in data:
			for each_pgm in each_entry:
				if each_pgm["name"] == "pdfjs.js":				
					w.append(each_pgm["mem_diff"])
			# print(each_entry)
	# 		print("**")
	# 		w.append(each_entry["mem_diff"])
		w.sort()
		print(w)
		print("mean "+ str(stats.mean(w)))
		print("median "+ str(stats.median(w)))
		print("mode "+ str(stats.mode(w)))
		print("**")
		
	
	
for name in glob.glob('log/**/tex_data', recursive=True):
	parseJSON(name)
		

		
		
	