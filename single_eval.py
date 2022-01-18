import asyncio
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from pyppeteer import launch

assert(len(sys.argv) == 2)
cfg = eval(sys.argv[1])

LIMIT_MEMORY = cfg["LIMIT_MEMORY"]
DEBUG = cfg["DEBUG"]
if LIMIT_MEMORY:
    MEMORY_LIMIT = cfg["MEMORY_LIMIT"]
BALANCER_CFG = cfg["BALANCER_CFG"]
BALANCE_STRATEGY = BALANCER_CFG["BALANCE_STRATEGY"]
RESIZE_CFG = BALANCER_CFG["RESIZE_CFG"]
RESIZE_STRATEGY = RESIZE_CFG["RESIZE_STRATEGY"]
if RESIZE_STRATEGY == "constant":
    RESIZE_AMOUNT = RESIZE_CFG["RESIZE_AMOUNT"]
if RESIZE_STRATEGY == "after-balance":
    GC_RATE = RESIZE_CFG["GC_RATE"]
SMOOTH_TYPE = BALANCER_CFG["SMOOTHING"]["TYPE"]
if not SMOOTH_TYPE == "no-smoothing":
    SMOOTH_COUNT = BALANCER_CFG["SMOOTHING"]["COUNT"]
BALANCE_FREQUENCY = BALANCER_CFG["BALANCE_FREQUENCY"]

NAME = cfg["NAME"]

def report_jetstream_score():
    with open(filename) as f:
        print(f.read())

def calculate_peak_heap_memory(directory):
    total_heap_memory = []
    with open(os.path.join(directory, "balancer_log")) as f:
        for line in f.read().splitlines():
            tmp = json.loads(line)
            if tmp["type"] == "total-memory":
                total_heap_memory.append(tmp["data"])
    return max(total_heap_memory)

result_directory = "log/" + time.strftime("%Y-%m-%d-%H-%M-%S") + "/"
Path(result_directory).mkdir()
with open(os.path.join(result_directory, "cfg"), "w") as f:
    json.dump(cfg, f)

# weird error: terminate does not work when exception is raised. fix this.
class ProcessScope:
    def __init__(self, p):
        self.p = p
    def __enter__(self):
        return self.p
    def __exit__(self, *args):
        self.p.terminate()

MB_IN_BYTES = 1024 * 1024

balancer_cmds = ["/home/marisa/Work/MemoryBalancer/build/MemoryBalancer", "daemon"]
balancer_cmds.append(f"--balance-strategy={BALANCE_STRATEGY}")
balancer_cmds.append(f"--resize-strategy={RESIZE_STRATEGY}")
if RESIZE_STRATEGY == "constant":
    balancer_cmds.append(f"--resize-amount={RESIZE_AMOUNT * MB_IN_BYTES}")
if RESIZE_STRATEGY == "after-balance":
    balancer_cmds.append(f"--gc-rate={GC_RATE}")
balancer_cmds.append(f"--smooth-type={SMOOTH_TYPE}")
if not SMOOTH_TYPE == "no-smoothing":
    balancer_cmds.append(f"--smooth-count={SMOOTH_COUNT}")
balancer_cmds.append(f"--balance-frequency={BALANCE_FREQUENCY}")
balancer_cmds.append(f"""--log-path={result_directory+"balancer_log"}""")

def tee_log(cmd, log_path):
    return f"{cmd} 2>&1 | tee {log_path}"


def env_vars_str(env_vars):
    ret = ""
    for k, v in env_vars.items():
        ret = f"{k}={v} {ret}"
    return ret

def run_jetstream(v8_env_vars):
    command = f"""build/MemoryBalancer v8_experiment --heap-size={int(10 * 1000 * 1e6)} --log-path={result_directory+"v8_log"}""" # a very big heap size to essentially have no limit
    main_process_result = subprocess.run(f"{env_vars_str(v8_env_vars)} {command}", shell=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    with open(os.path.join(result_directory, "v8_out"), "w") as f:
        f.write(main_process_result.stdout)
    if main_process_result.returncode != 0:
        if "Fatal javascript OOM" in main_process_result.stdout:
            j = {}
            j["OK"] = False
            j["CFG"] = cfg
            with open(os.path.join(result_directory, "score"), "w") as f:
                json.dump(j, f)
        else:
            print(main_process_result.stdout)
            print("UNKNOWN ERROR!")
    else:
        j = {}
        j["OK"] = True
        j["PEAK_HEAP_MEMORY"] = calculate_peak_heap_memory(result_directory)
        v8_log_path = os.path.join(result_directory, "v8_log")
        total_time = None
        total_major_gc_time = None
        peak_memory = None
        with open(v8_log_path) as f:
            for line in f.read().splitlines():
                tmp = json.loads(line)
                if tmp["type"] == "total_time":
                    assert(total_time == None)
                    total_time = tmp["data"]
                elif tmp["type"] == "total_major_gc_time":
                    assert(total_major_gc_time == None)
                    total_major_gc_time = tmp["data"]
                elif tmp["type"] == "peak_memory":
                    assert(peak_memory == None)
                    peak_memory = tmp["data"]
        assert(peak_memory != None)
        j["PEAK_MEMORY"] = peak_memory
        assert(total_time != None)
        j["TOTAL_TIME"] = total_time
        assert(total_major_gc_time != None)
        j["TOTAL_MAJOR_GC_TIME"] = total_major_gc_time
    with open(os.path.join(result_directory, "score"), "w") as f:
        json.dump(j, f)


def run_browser(v8_env_vars):
    async def new_browser():
        browseroptions = {"headless":False,
                          "args":["--no-sandbox", "--disable-notifications", "--start-maximized"]}

        browseroptions["executablePath"] = "/home/marisa/Work/chromium/src/out/Release/chrome"

        # we need the environment variable for headless:False, because it include stuff such for graphics such as DISPLAY.
        # todo: isolate them instead of passing the whole env var?
        env = os.environ.copy()
        browseroptions["env"] = {**os.environ.copy(), **v8_env_vars}

        if DEBUG:
            browseroptions["dumpio"] = True
        return await launch(browseroptions)

    async def new_page(browser):
        page = await browser.newPage()
        await page.setViewport({"width": 1280, "height": 1080})
        return page

    async def reddit(browser):
        page = await new_page(browser)
        await page.goto("https://reddit.com", timeout=120*1000)
        await page.waitForSelector("i.icon-comment")
        for i in range(1):
            l = await page.querySelectorAll("i.icon-comment")
            assert i < len(l)
            await page.evaluate("(element) => element.scrollIntoView()", l[i])
            await asyncio.sleep(5)
            link = await page.evaluate("(element) => element.parentElement.href", l[i])
            sub_page = await new_page(browser)
            await sub_page.goto(link, {"waitUntil" : "domcontentloaded"})
            await asyncio.sleep(5)
            await sub_page.close()
            await asyncio.sleep(5)

    # problem - twitter is being blocked when it detect we are bot
    async def twitter(browser):
        page = await new_page(browser)
        await stealth(page)
        await page.setUserAgent('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/73.0.3683.75 Safari/537.36');
        await page.goto("https://twitter.com")
        for i in range(20):
            await page.evaluate("{window.scrollBy(0, 10);}")
            await asyncio.sleep(5)

    # problem - cannot watch twitch video
    async def twitch(browser):
        page = await new_page(browser)
        await page.goto("https://www.twitch.com/")
        await asyncio.sleep(100)

    async def cookie_clicker(browser):
        page = await new_page(browser)
        await page.goto("https://orteil.dashnet.org/cookieclicker/", timeout=120*1000)
        for i in range(150):
            bigCookie = await page.querySelector("#bigCookie")
            items = await page.querySelectorAll(".product.unlocked.enabled")
            upgrades = await page.querySelectorAll(".crate.upgrade")
            notifications = await page.querySelectorAll(".note .close")
            for clickable in [bigCookie] + items + upgrades + notifications:
                await page.evaluate("(c) => c.click()", clickable)
                await asyncio.sleep(1)

    async def youtube(browser):
        page = await new_page(browser)
        await page.goto("https://www.youtube.com/watch?v=dQw4w9WgXcQ", {'waitUntil' : 'domcontentloaded'})
        await asyncio.sleep(100)

    async def gmap(browser):
        page = await new_page(browser)
        await page.goto("https://www.google.com/maps", {'waitUntil' : 'domcontentloaded'})
        await page.evaluate("""document.querySelector("#searchboxinput").value='subway'""")
        await asyncio.sleep(2)
        await page.evaluate("""document.querySelector("[aria-label=Directions]").click()""")
        await asyncio.sleep(2)
        await page.evaluate("""document.querySelector("#directions-searchbox-0 input").value='University of Utah'""")
        await asyncio.sleep(2)
        await page.evaluate("""document.querySelector("#directions-searchbox-0 input").click()""")
        await asyncio.sleep(2)
        await page.keyboard.press('Enter');
        await asyncio.sleep(100)

    def hang():
        while True:
            pass

    async def run_browser_main():
        await asyncio.gather(reddit(await new_browser()))

    start = time.time()
    asyncio.get_event_loop().run_until_complete(run_browser_main())
    end = time.time()
    j = {}
    j["OK"] = True
    j["PEAK_HEAP_MEMORY"] = calculate_peak_heap_memory(result_directory)
    j["TOTAL_TIME"] = end - start
    with open(os.path.join(result_directory, "score"), "w") as f:
        json.dump(j, f)

with ProcessScope(subprocess.Popen(balancer_cmds, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)) as p:
    subprocess.Popen(["tee", result_directory+"balancer_out"], stdin=p.stdout)
    time.sleep(1) # make sure the balancer is running
    memory_limit = f"{MEMORY_LIMIT * MB_IN_BYTES}"

    v8_env_vars = {"USE_MEMBALANCER": "1", "LOG_GC": "1"}

    if not RESIZE_STRATEGY == "ignore":
        v8_env_vars["SKIP_RECOMPUTE_LIMIT"] = "1"

    if LIMIT_MEMORY:
        v8_env_vars["MEMORY_LIMITER_TYPE"] = "ProcessWide"
        v8_env_vars["MEMORY_LIMITER_VALUE"] = str(memory_limit)

    if NAME == "jetstream":
        run_jetstream(v8_env_vars)
    elif NAME == "browser":
        run_browser(v8_env_vars)
    else:
        raise Exception(f"unknown benchmark name: {NAME}")

    for filename in os.listdir(os.getcwd()):
        if (filename.endswith(".log")):
            Path(filename).rename(result_directory + filename)
