import json
import os
import statistics as stats
import glob

# path1 = "/Users/u1365432/Documents/Research/Pavel/code/MemoryBalancer/log/2022-04-11-17-58-21/2022-04-11-17-58-21/2022-04-11-17-58-21/tex_data"
# path2 = "/Users/u1365432/Documents/Research/Pavel/code/MemoryBalancer/log/2022-04-11-17-58-21/2022-04-11-17-58-21/2022-04-11-18-00-12/tex_data"
# 
# def parseJSON(path):
# 
# 	with open(path) as f:
# 		data = []
# 		for line in f.read().splitlines():
# 			data = json.loads(line)
# 		w = []
# 		for each_entry in data:
# 			for each_pgm in each_entry:
# 				if each_pgm["name"] == "pdfjs.js":				
# 					w.append(each_pgm["mem_diff"])
# 			# print(each_entry)
# 	# 		print("**")
# 	# 		w.append(each_entry["mem_diff"])
# 		w.sort()
# 		print(w)
# 		print("mean "+ str(stats.mean(w)))
# 		print("median "+ str(stats.median(w)))
# 		print("mode "+ str(stats.mode(w)))
# 		print("**")
# for name in glob.glob('log/**/tex_data', recursive=True):
# 	parseJSON(name)
	
	
def fmt(x):
    return "{0:.3g}".format(x)
    
def tex_fmt(x):
    return f"\\num{{{fmt(x)}}}"

def tex_def(row_num, col_name, definitions):
    return f"\def\{col_name}{row_num}{{{definitions}\\xspace}}\n"
	
def combine(membalancer_data, baseline_data, membalancer_dir, baseline_dir):
	tex_data = {}
	
	for data in membalancer_data:
		name = data["name"]
		tex_data[name] = {}
		tex_data[name]["w"] = data["mem_diff"]
		tex_data[name]["g"] = data["gc_rate"]
		tex_data[name]["s"] = data["gc_speed"]
		tex_data[name]["membalancer_exta_mem"] = data["extra_mem"]
		tex_data[name]["membalancer_dir"] = membalancer_dir
		
	for data in baseline_data:
		name = data["name"]
		tex_data[name]["current_v8_extra_mem"] = data["extra_mem"]
	return tex_data
	
def convert_to_tex(data):
	tex_str = ""
	row = 'A'
	for (idx, key) in enumerate(data.keys()):
		w = data[key]["w"]
		g = data[key]["g"]
		s = data[key]["s"]
		mb_extra = data[key]["membalancer_exta_mem"]
		curr_extra = data[key]['current_v8_extra_mem']
		tex_str += tex_def(row, "name", key)
		tex_str += tex_def(row, "w", f"{tex_fmt(w)}")
		tex_str += tex_def(row, "g", f"{tex_fmt(g)}")
		tex_str += tex_def(row, "s", f"{tex_fmt(s)}")
		tex_str += tex_def(row, "mbextra", f"{tex_fmt(mb_extra)}")
		tex_str += tex_def(row, "currextra", f"{tex_fmt(curr_extra)}")
		row = ord(row)
		row += 1
		row = chr(row)
	return tex_str

def write_tex(tex_str, path):
	with open(path, "w") as tex_file:
		tex_file.write(tex_str)
	

data1 = [{"extra_mem":137.822194,"gc_rate":0.0001,"gc_speed":0.0002,"max_mem":142.94269,"mem_diff":5.120496,"name":"typescript.js"},{"extra_mem":88.882765,"gc_rate":0.0007290227590384409,"gc_speed":0.012857043118567554,"max_mem":121.647277,"mem_diff":32.764512,"name":"splay.js"},{"extra_mem":126.479322,"gc_rate":0.0001,"gc_speed":0.0002,"max_mem":129.964186,"mem_diff":3.484864,"name":"pdfjs.js"}]
data2 = [{"extra_mem":463.415321,"gc_rate":0.0001,"gc_speed":0.0002,"max_mem":468.535817,"mem_diff":5.120496,"name":"typescript.js"},{"extra_mem":30.571057,"gc_rate":0.0005745020259359467,"gc_speed":0.007347164016431199,"max_mem":61.797877,"mem_diff":31.22682,"name":"splay.js"},{"extra_mem":16.50624,"gc_rate":3.514286827199678e-05,"gc_speed":0.0007114535396069207,"max_mem":26.271176,"mem_diff":9.764936,"name":"pdfjs.js"}]
combined_data = combine(data1, data2, ".", ".")
converted_tex = convert_to_tex(combined_data)
write_tex(converted_tex, "../membalancer-paper/js_table.tex")
print("done creating tex file for table!")

		
		
	