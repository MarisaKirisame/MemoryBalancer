import os
from pyppeteer import launch
import collections

def fmt(x):
	return "{0:%s}".format(float("{0:.2g}".format(float(x))))

def fmt_int(x):
	return "{}".format(int(x))

def tex_fmt(x):
    return f"\\num{{{fmt(x)}}}"

def tex_fmt_int(x):
	return f"\\num{{{fmt_int(x)}}}"

def tex_fmt_bold(x):
    return f"\\textbf{{{fmt(x)}}}"

def tex_def(name, definition):
    return f"\def\{name}{{{definition}\\xspace}}\n"

async def new_browser(*, env_vars={}, headless=True, debug=True):
    args = ["--no-sandbox", "--disable-notifications", "--user-data-dir=./membalancer_profile", "--disable-popup-blocking"]
    browseroptions = {"headless":headless, "args":args}
    browseroptions["executablePath"] = "../chromium/src/out/Release/chrome"

    # we need the environment variable for headless:False, because it include stuff such for graphics such as DISPLAY.
    # todo: isolate them instead of passing the whole env var?
    env = os.environ.copy()
    browseroptions["env"] = {**os.environ.copy(), **env_vars}

    if debug:
        browseroptions["dumpio"] = True
    b = await launch(browseroptions)
    assert(len(await b.pages()) == 1)
    return b

class FrozenDict(collections.Mapping):
    """Don't forget the docstrings!!"""
    def __repr__(self):
        return repr(self._d)

    def __init__(self, *args, **kwargs):
        self._d = dict(*args, **kwargs)
        self._hash = None

    def __iter__(self):
        return iter(self._d)

    def __len__(self):
        return len(self._d)

    def __getitem__(self, key):
        return self._d[key]

    def __hash__(self):
        # It would have been simpler and maybe more obvious to
        # use hash(tuple(sorted(self._d.iteritems()))) from this discussion
        # so far, but this solution is O(n). I don't know what kind of
        # n we are going to run into, but sometimes it's hard to resist the
        # urge to optimize when it will gain improved algorithmic performance.
        if self._hash is None:
            hash_ = 0
            for pair in self.items():
                hash_ ^= hash(pair)
            self._hash = hash_
        return self._hash

def deep_freeze(d):
    if isinstance(d, dict):
        return FrozenDict([(k, deep_freeze(v)) for k, v in d.items()])
    elif isinstance(d, list):
        return tuple(d)
    else:
        return d
