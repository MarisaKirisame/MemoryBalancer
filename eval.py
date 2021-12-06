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

    def map(self, f):
        return self.bind(lambda x: NONDET(f(x)))

    def __repr__(self):
        return f"NONDET{repr(self.l)}"

def flatten_nondet(x):
    assert isinstance(x, list)
    if len(x) == 0:
        return NONDET([])
    else:
        def process_rest(tail):
            head = x[0]
            head_key = head[0]
            head_value = head[1]
            return (head_value if isinstance(head_value, NONDET) else NONDET(head_value)).map(lambda hv: [(head_key, hv)] + tail)
        return flatten_nondet(x[1:]).bind(process_rest)

def flatten_nondet_dict(x):
    return flatten_nondet(list(x.items())).map(lambda x: dict(x))

def recursive_flatten_nondet_dict(x):
    def recurse(x):
        if isinstance(x, (bool, int, str)):
            return x
        elif isinstance(x, dict):
            return recursive_flatten_nondet_dict(x)
        elif isinstance(x, NONDET):
            return NONDET(*[recurse(y) for y in x.l])
        else:
            print(type(x))
            raise
    return flatten_nondet_dict({k:recurse(v) for k, v in x.items()})

# test out relationship btwn resize-amount
cfgs = recursive_flatten_nondet_dict({
    "LIMIT_MEMORY": True,
    "DEBUG": False,
    "MEMORY_LIMIT": 1000,
    "BALANCER_CFG": {
        "BALANCE_STRATEGY": "extra-memory",
        "RESIZE_CFG": {
            "RESIZE_STRATEGY": "constant",
            "RESIZE_AMOUNT": NONDET(100, 150, 200, 250),
        },
        "SMOOTHING": {"TYPE": "no-smoothing"},
        "BALANCE_FREQUENCY": 0
    }
}).l

cfgs = flatten_nondet_dict({
    "LIMIT_MEMORY": True,
    "DEBUG": False,
    "MEMORY_LIMIT": NONDET(*[600 + 30 * i for i in range(10)]),
    "BALANCER_CFG": flatten_nondet_dict({
        "BALANCE_STRATEGY": NONDET( "ignore", "extra-memory", "classic"),
        "RESIZE_CFG": {"RESIZE_STRATEGY": "ignore"},
        "SMOOTHING": {"TYPE": "no-smoothing"},
        "BALANCE_FREQUENCY": 0
    })
}).l

for _ in range(20):
    for cfg in cfgs:
        subprocess.run(f"python3 single_eval.py \"{cfg}\"", shell=True, check=True)
