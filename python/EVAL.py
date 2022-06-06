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

class QUOTE:
    def __init__(self, x):
        self.x = x
    def __repr__(self):
        return f"QUOTE({self.x})"

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
    elif isinstance(x, QUOTE):
        return NONDET(x)
    else:
        print(type(x))
        print(x)
        raise

def has_meta(x):
    if isinstance(x, (str, bool, int, float)):
        return False
    elif isinstance(x, (QUOTE, NONDET)):
        return True
    elif isinstance(x, dict):
        return has_meta(tuple(its for its in x.items()))
    elif isinstance(x, tuple):
        return any([has_meta(y) for y in x])
    elif isinstance(x, list):
        return has_meta(tuple(x))
    else:
        print(type(x))
        print(x)
        raise

def strip_quote(x):
    if isinstance(x, (str, bool, int, float)):
        return x
    elif isinstance(x, QUOTE):
        return x.x
    elif isinstance(x, dict):
        return {strip_quote(k): strip_quote(v) for k, v in x.items()}
    elif isinstance(x, list):
        return list([strip_quote(y) for y in x])
    elif isinstance(x, tuple):
        return tuple([strip_quote(y) for y in x])
    elif isinstance(x, NONDET):
        return NONDET(*strip_quote(x.l))
    else:
        print(type(x))
        print(x)
        raise
