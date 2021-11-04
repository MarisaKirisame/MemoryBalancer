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

cfg_nondet = {
    "LIMIT_MEMORY": True,
    "DEBUG": False,
    "SEND_MSG": NONDET(True, False),
    "MEMORY_LIMIT": NONDET(600, 650, 700, 750, 800),
}

def flatten_nondet_aux(x):
    assert isinstance(x, list)
    if len(x) == 0:
        return NONDET([])
    else:
        def process_rest(tail):
            head = x[0]
            head_key = head[0]
            head_value = head[1]
            return (head_value if isinstance(head_value, NONDET) else NONDET(head_value)).map(lambda hv: [(head_key, hv)] + tail)
        return flatten_nondet_aux(x[1:]).bind(process_rest)

def flatten_nondet(x):
    return flatten_nondet_aux(x).map(lambda x: dict(x))

cfgs = flatten_nondet(list(cfg_nondet.items()))
for _ in range(10):
    for cfg in cfgs.l:
        subprocess.run(f"python3 single_eval.py \"{cfg}\"", shell=True, check=True)
