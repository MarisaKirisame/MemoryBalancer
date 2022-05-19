import os
from pyppeteer import launch

def fmt(x):
	return "{0:.2f}".format(float(x))

def fmt_int(x):
	return "{}".format(int(x))

def tex_fmt(x):
    return f"\\num{{{fmt(x)}}}"
    
def tex_fmt_int(x):
	return f"\\num{{{fmt_int(x)}}}"

def tex_fmt_bold(x):
    return f"\\textbf{{{fmt(x)}}}"

def tex_def_generic(eval_name, name, definition):
    return f"\def\{eval_name}{name}{{{definition}\\xspace}}\n"

async def new_browser(*, env_vars={}, headless=True, debug=True):
    args = ["--no-sandbox", "--disable-notifications", "--start-maximized", "--user-data-dir=./membalancer_profile"]
    args.append("--noincremental-marking")
    args.append("--no-memory-reducer")
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
