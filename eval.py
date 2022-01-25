import subprocess

# list monad
class NONDET:
    def __init__(self, *args):
        self.l = args

    def bind(self, f):
        ret = []
        for x in self.l:
            res = f(x)
            if not isinstance(res, NONDET):
                print(type(res))
                assert(isinstance(res, NONDET))
            ret += res.l
        return NONDET(*ret)

    def join(self):
        return self.bind(lambda x: x)

    def map(self, f):
        return self.bind(lambda x: NONDET(f(x)))

    def __repr__(self):
        return f"NONDET{repr(self.l)}"

def flatten_nondet(x):
    if isinstance(x, (bool, int, str, float)):
        return NONDET(x)
    elif isinstance(x, dict):
        return flatten_nondet([i for i in x.items()]).map(lambda x: dict(x))
    elif isinstance(x, list):
        if len(x) == 0:
            return NONDET([])
        else:
            head = flatten_nondet(x[0])
            tail = flatten_nondet(x[1:])
            return head.bind(lambda y: tail.bind(lambda z: NONDET([y] + z)))
    elif isinstance(x, NONDET):
        return NONDET(*[flatten_nondet(y) for y in x.l]).join()
    elif isinstance(x, tuple):
        return NONDET(*[tuple(y) for y in flatten_nondet(list(x)).l])
    else:
        print(type(x))
        print(x)
        raise

cfgs = flatten_nondet({
    "LIMIT_MEMORY": True,
    "DEBUG": False,
    "NAME": "jetstream",
    "MEMORY_LIMIT": NONDET(*[600 + 30 * i for i in range(10)]),
    "BALANCER_CFG": NONDET({
        "BALANCE_STRATEGY": NONDET("classic", "extra-memory", "ignore"),
        "RESIZE_CFG": {"RESIZE_STRATEGY": "ignore"},
        "SMOOTHING": {"TYPE": "no-smoothing"},
        "BALANCE_FREQUENCY": 0
    })
}).l

cfgs = flatten_nondet(NONDET({
    "LIMIT_MEMORY": True,
    "DEBUG": False,
    "NAME": "jetstream",
    "MEMORY_LIMIT": NONDET(10000),
    "BALANCER_CFG": {
        "BALANCE_STRATEGY": "classic",
        "RESIZE_CFG": {"RESIZE_STRATEGY": "after-balance", "GC_RATE":NONDET(0.01, 0.015, 0.02, 0.03, 0.04, 0.06, 0.08, 0.10, 0.15, 0.2)},
        "SMOOTHING": {"TYPE": "no-smoothing"},
        "BALANCE_FREQUENCY": 0
    }}, {
        "LIMIT_MEMORY": True,
        "DEBUG": False,
        "NAME": "jetstream",
        "MEMORY_LIMIT": NONDET(*[500 + 30 * i for i in range(16)], 10000),
        "BALANCER_CFG": {
            "BALANCE_STRATEGY": NONDET("ignore"),
            "RESIZE_CFG": {"RESIZE_STRATEGY": "ignore"},
            "SMOOTHING": {"TYPE": "no-smoothing"},
            "BALANCE_FREQUENCY": 0
        }})).l

cfgs = [{
    "LIMIT_MEMORY": True,
    "DEBUG": False,
    "NAME": "browser",
    "MEMORY_LIMIT": 10000,
    "BALANCER_CFG": {
        "BALANCE_STRATEGY": "ignore",
        "RESIZE_CFG": {"RESIZE_STRATEGY": "ignore"},
        "SMOOTHING": {"TYPE": "no-smoothing"},
        "BALANCE_FREQUENCY": 0
    }}]

cfgs = flatten_nondet({
    "LIMIT_MEMORY": True,
    "DEBUG": False,
    "NAME": "browser",
    "MEMORY_LIMIT": NONDET(10000),
    "BALANCER_CFG": NONDET({
        "BALANCE_STRATEGY": "classic",
        "RESIZE_CFG": {"RESIZE_STRATEGY": "after-balance", "GC_RATE":NONDET(0.001, 0.002, 0.003)},
        "SMOOTHING": {"TYPE": "no-smoothing"},
        "BALANCE_FREQUENCY": 0
    }, {
        "BALANCE_STRATEGY": NONDET("ignore"),
        "RESIZE_CFG": {"RESIZE_STRATEGY": "ignore"},
        "SMOOTHING": {"TYPE": "no-smoothing"},
        "BALANCE_FREQUENCY": 0
    })}).l

cfgs = flatten_nondet({
    "LIMIT_MEMORY": True,
    "DEBUG": False,
    "NAME": "browser",
    "MEMORY_LIMIT": NONDET(10000),
    "BALANCER_CFG": NONDET({
        "BALANCE_STRATEGY": NONDET("ignore"),
        "RESIZE_CFG": {"RESIZE_STRATEGY": "ignore"},
        "SMOOTHING": {"TYPE": "no-smoothing"},
        "BALANCE_FREQUENCY": 0
    })}).l

for _ in range(20):
    for cfg in cfgs:
        subprocess.run(f"python3 single_eval.py \"{cfg}\"", shell=True, check=True)
