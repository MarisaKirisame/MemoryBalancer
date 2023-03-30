import json
import os

class Line:
    def __init__(self, plot_std, name=None):
        self.plot_std = plot_std
        self.name = name
        self.xs = []
        self.ys = []
        if self.plot_std:
            self.errs = []

    def point(self, x, y, err=None):
        self.xs.append(x)
        self.ys.append(y)
        if self.plot_std:
            assert err is not None
            self.errs.append(err)

    def plot(self):
        if self.plot_std:
            return plt.errorbar(self.xs, self.ys, self.errs, label=self.name)
        else:
            return plt.plot(self.xs, self.ys, label=self.name)

class Data:
    def __init__(self, name):
        self.name = name
        self.xs = []
        self.ys = []
        self.y_errs = []
        self.y_es = []
        self.oom_rates = []
    def point(self, x, y, y_err, y_e, oom_rate):
        self.xs.append(x)
        self.ys.append(y)
        self.y_errs.append(y_err)
        self.y_es.append(y_e)
        self.oom_rates.append(oom_rate)
    def plot(self):
        #descending
        split_i = 0
        for i in range(len(self.xs)):
            if self.oom_rates[i] < 0.5:
                split_i = i + 1
        x = plt.errorbar(self.xs[:split_i], self.ys[:split_i], self.y_errs[:split_i], label=self.name)
        if split_i > 0:
            plt.errorbar(self.xs[split_i-1:], self.ys[split_i-1:], self.y_errs[split_i-1:], ls="--", color=x[0].get_color())
        #plt.plot(self.xs, self.y_es, label=f"{self.name} / E")

def parse_log():
    ret = []
    for filename in os.listdir("log"):
        score_path = os.path.join("log", filename, "score")
        cfg_path = os.path.join("log", filename, "cfg")
        if os.path.exists(score_path):
            with open(score_path) as f:
                score = json.load(f)
            with open(cfg_path) as f:
                cfg = json.load(f)
            ret.append((deep_freeze(score), deep_freeze(cfg)))
        else:
            print(f"Warning: {score_path} does not exists")
    return ret

def report(name, x):
    print(f"{name} mean: {np.mean(x)} std: {np.std(x)}")


class Run:
    def __init__(self, dirname):
        self.dirname = dirname
        with open(dirname + "/score") as f:
            self.score = json.load(f)
        with open(dirname + "/cfg") as f:
            self.cfg = eval(f.read())

    def ok(self):
        return self.score["OK"]

class Experiment:
    def __init__(self, runs):
        for run in runs:
            assert(isinstance(run, Run))
        self.runs = runs

    def all_dirname(self):
        return [x.dirname for x in self.runs]

    def avg_old_gen_memory(self):
        return calculate_average(self.all_dirname(), "BenchmarkMemory")

    def avg_yg_memory(self):
        #for 2 semispace
        return 2 * calculate_average_yg(self.all_dirname(), "before_yg_memory")
    
    def average_benchmark_memory(self):
        return self.avg_old_gen_memory() + self.avg_yg_memory()

    def yg_gc_total_time(self):
        return calculate_yg_gc_time(self.all_dirname())
    
    def yg_total_before_memory(self):
        return self.get_total("before_yg_memory", True)
    
    def yg_total_after_memory(self):
        return self.get_total("after_yg_memory", True)
    
    def get_total(self, property_name, shouldAdd):
        all_log_yg = read_yg_log_separate(self.all_dirname())
        ret = 0
        for key, logs in all_log_yg.items():
            acc = 0
            for log in logs:
                if shouldAdd:
                    acc += log[property_name]
                else:
                    acc = log[property_name]
            ret += acc
        return ret

    def total_copied_bytes(self):
        return self.get_total("total_copied_bytes", False)

    def total_allocated_bytes(self):
        return self.get_total("allocated_bytes", True)
    
    def total_promoted_bytes(self):
        return self.get_total("total_promoted_bytes", False)
        
    def old_gen_total_time(self):
        return calculate_total_major_gc_time(self.all_dirname())
    
    def total_major_gc_time(self):
        return self.old_gen_total_time() + self.yg_gc_total_time()

    def perf_breakdown(self):
        ret = {}
        for d in self.all_dirname():
            for gc_log in os.listdir(d):
                if gc_log.endswith(".gc.log"):
                    name = None
                    major_gc_time = 0
                    average_benchmark_memory = 0
                    with open(os.path.join(d, gc_log)) as f:
                        for line in f.readlines():
                            j = json.loads(line)
                            major_gc_time = j["total_major_gc_time"]
                            name = j["name"]
                            #if name == "":
                            #    name = j["guid"]
                    with open(os.path.join(d, gc_log.rstrip(".gc.log") + ".memory.log")) as f:
                        memorys = []
                        for line in f.readlines():
                            j = json.loads(line)
                            memorys.append(j["BenchmarkMemory"])
                            name = j["name"]
                            if name == "":
                                name = j["guid"]
                        if len(memorys) != 0:
                            average_benchmark_memory = sum(memorys) / len(memorys)
                        else:
                            average_benchmark_memory = 0
                    if name == None:
                        name = gc_log
                    ret[name] = (average_benchmark_memory, major_gc_time)
        return ret


def calculate_yg_gc_time(directory_list):
    total_major_gc_time = 0
    for directory in directory_list:
        for filename in os.listdir(directory):
            if filename.endswith(".yg.log"):
                with open(os.path.join(directory, filename)) as f:
                    major_gc_time = 0
                    for line in f.read().splitlines():
                        j = json.loads(line)
                        major_gc_time += j["yg_gc_time"]  #adding each line
                    total_major_gc_time += major_gc_time
    return total_major_gc_time

def calculate_total_major_gc_time(directory_list):
    total_major_gc_time = 0
    for directory in directory_list:
        for filename in os.listdir(directory):
            if filename.endswith(".gc.log"):
                with open(os.path.join(directory, filename)) as f:
                    major_gc_time = 0
                    for line in f.read().splitlines():
                        j = json.loads(line)
                        major_gc_time = j["total_major_gc_time"]
                    total_major_gc_time += major_gc_time
    return total_major_gc_time 

def read_yg_log_separate(directory_list):
    logs = {}
    for directory in directory_list:
        for filename in os.listdir(directory):
            if filename.endswith(".yg.log"):
                with open(os.path.join(directory, filename)) as f:
                    for line in f.read().splitlines():
                        j = json.loads(line)
                        if filename not in logs:
                            logs[filename] = []
                        logs[filename].append(j)
    return logs


def read_memory_log_separate(directory_list):
    logs = {}
    for directory in directory_list:
        for filename in os.listdir(directory):
            if filename.endswith(".memory.log"):
                with open(os.path.join(directory, filename)) as f:
                    for line in f.read().splitlines():
                        j = json.loads(line)
                        if filename not in logs:
                            logs[filename] = []
                        logs[filename].append(j)
                    if filename in logs:
                        time = j["time"] + 1
                        j = {"source": filename, "time": time}
                        for p in ["Limit", "PhysicalMemory", "SizeOfObjects", "BenchmarkMemory"]:
                            j[p] = 0
                        logs[filename].append(j)
    return logs

def read_memory_log(directory):
    ret = []
    for filename, logs in read_memory_log_separate(directory).items():
        for log in logs:
            log["source"] = filename
            ret.append(log)
    ret.sort(key=lambda x: x["time"])
    return ret

def calculate_peak(directory, property_name):
    logs = read_memory_log(directory)

    max_memory = 0
    memory = 0
    memory_breakdown = defaultdict(int)

    for i in range(len(logs)):
        l = logs[i]
        memory -= memory_breakdown[l["source"]]
        memory += l[property_name]
        memory_breakdown[l["source"]] = l[property_name]
        max_memory = max(max_memory, memory)

    return max_memory


def calculate_average_yg(directory, property_name):
    all_log_yg = read_yg_log_separate(directory)
    ret = 0
    for key, logs in all_log_yg.items():
        acc = 0
        for log in logs:
            acc += log[property_name]
        tmp = acc / len(logs)
        ret += tmp
    return ret

def calculate_average(directory, property_name):
    all_log_memory = read_memory_log_separate(directory)
    ret = 0
    for key, logs in all_log_memory.items():
        acc = 0
        for log in logs:
            acc += log[property_name]
        tmp = acc / len(logs)
        ret += tmp
    return ret

# positive variation
def calculate_pv(directory, property_name):
    ret = 0
    for logs in read_memory_log_separate(directory).values():
        last = 0
        for log in logs:
            ret += max(0, log[property_name] - last)
            last = log[property_name]
    return ret

def calculate_peak_balancer_memory(directory):
    total_heap_memory = []
    with open(os.path.join(directory, "balancer_log")) as f:
        for line in f.read().splitlines():
            tmp = json.loads(line)
            if tmp["type"] == "total-memory":
                total_heap_memory.append(tmp["data"])
    if len(total_heap_memory) == 0:
        return 0
    else:
        return max(total_heap_memory)

def calculate_average_balancer_memory(directory):
    total_heap_memory = []
    with open(os.path.join(directory, "balancer_log")) as f:
        for line in f.read().splitlines():
            tmp = json.loads(line)
            if tmp["type"] == "total-memory":
                total_heap_memory.append(tmp["data"])
    if len(total_heap_memory) == 0:
        return 0
    else:
        return sum(total_heap_memory) / len(total_heap_memory)
