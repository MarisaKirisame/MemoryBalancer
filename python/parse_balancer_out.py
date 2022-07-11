import sys

def get_index(col_name):
	if col_name == "gc_rate_d":
		return

def chunking(filtered_logs):
	chunks = []
	tmp = []
	for log in filtered_logs:
		if log.startswith("|name"):
			if len(tmp) > 0:
				chunks.append(tmp)
			tmp = []
		else:
			tmp.append(log)
	if len(tmp) > 0:
		chunks.append(tmp)
	return chunks

def convert_each_chunk(chunk):
	for pgm_line in chunk:
		split_lines = pgm_line.split('|')
		print(split_lines)

# [{"ts": {"name": <name>,"gc_rate_d": <rate>, "": }, "pdfjs": {"name": <name>,"gc_rate_d": <rate>, }}]
def convert_to_dict(chunks):
	data = []
	for chunk in chunks:
		convert_each_chunk(chunk)

def filter_log(filepath):
	filtered_log = []
	with open(filepath) as f:
		for (index, line) in enumerate(f.read().splitlines()):
			if len(line) > 0 and line.startswith("|"):
				filtered_log.append(line)
	return filtered_log

def display(chunks):
	for chunk in chunks:
		print(chunk)

def main(filepath):
	filtered_logs = filter_log(filepath)
	chunks = chunking(filtered_logs)
	convert_to_dict(chunks)
#	display(chunks)

if __name__ == "__main__":
    assert(len(sys.argv) == 2)
    main(sys.argv[1])
