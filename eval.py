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

cfgs = flatten_nondet_dict({
    "LIMIT_MEMORY": True,
    "DEBUG": False,
    "MEMORY_LIMIT": NONDET(600, 650, 700, 750, 800),
    "BALANCER_CFG":NONDET(
        {"SEND_MSG":False, "SMOOTHING":{"TYPE":"no-smoothing"}},
        *flatten_nondet_dict({"SEND_MSG":True,
                              "SMOOTHING": NONDET({"TYPE":"no-smoothing"}, *flatten_nondet_dict({
                                "TYPE": NONDET("smooth-approximate", "smooth-exact"),
                                "COUNT": NONDET(2, 3)
                              }).l)}).l)
})

cfgs = flatten_nondet_dict({
    "LIMIT_MEMORY": True,
    "DEBUG": False,
    "MEMORY_LIMIT": NONDET(600, 650, 700, 750, 800),
    "BALANCER_CFG": {
        "SEND_MSG":True,
        "SMOOTHING": {
            "TYPE": "smooth-approximate",
            "COUNT": 1
        }}
})

for _ in range(10):
    for cfg in cfgs.l:
        subprocess.run(f"python3 single_eval.py \"{cfg}\"", shell=True, check=True)
