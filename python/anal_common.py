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
