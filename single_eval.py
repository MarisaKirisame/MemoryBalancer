import asyncio
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from pyppeteer import launch
from collections import defaultdict

assert(len(sys.argv) == 3)
cfg = eval(sys.argv[1])
result_directory = sys.argv[2] + "/"

print(f"running: {cfg}")
LIMIT_MEMORY = cfg["LIMIT_MEMORY"]
DEBUG = cfg["DEBUG"]
if LIMIT_MEMORY:
    MEMORY_LIMIT = cfg["MEMORY_LIMIT"]
BENCH = cfg["BENCH"]
BALANCER_CFG = cfg["BALANCER_CFG"]
BALANCE_STRATEGY = BALANCER_CFG["BALANCE_STRATEGY"]
RESIZE_CFG = BALANCER_CFG["RESIZE_CFG"]
RESIZE_STRATEGY = RESIZE_CFG["RESIZE_STRATEGY"]
if RESIZE_STRATEGY == "constant":
    RESIZE_AMOUNT = RESIZE_CFG["RESIZE_AMOUNT"]
if RESIZE_STRATEGY == "after-balance":
    GC_RATE = RESIZE_CFG["GC_RATE"]
BALANCE_FREQUENCY = BALANCER_CFG["BALANCE_FREQUENCY"]

NAME = cfg["NAME"]

def report_jetstream_score():
    with open(filename) as f:
        print(f.read())

def calculate_total_major_gc_time(directory):
    total_major_gc_time = 0
    for filename in os.listdir(directory):
        if filename.endswith(".gc.log"):
            with open(os.path.join(directory, filename)) as f:
                major_gc_time = 0
                for line in f.read().splitlines():
                    j = json.loads(line)
                    major_gc_time = j["total_major_gc_time"]
                total_major_gc_time += major_gc_time
    return total_major_gc_time

def read_memory_log(directory):
    logs = []
    for filename in os.listdir(directory):
        if filename.endswith(".memory.log"):
            with open(os.path.join(directory, filename)) as f:
                writeOnce = False
                for line in f.read().splitlines():
                    j = json.loads(line)
                    j["source"] = filename
                    logs.append(j)
                    writeOnce = True
                if writeOnce:
                    time = j["time"] + 1
                    j = {"source": filename, "time": time}
                    for p in ["Limit", "PhysicalMemory", "SizeOfObjects"]:
                        j[p] = 0
                    logs.append(j)
    logs.sort(key=lambda x: x["time"])
    return logs

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

def calculate_average(directory, property_name):
    logs = read_memory_log(directory)

    memory_sum = 0
    memory = 0
    memory_breakdown = defaultdict(int)

    for i in range(len(logs)):
        l = logs[i]
        memory -= memory_breakdown[l["source"]]
        memory += l[property_name]
        memory_breakdown[l["source"]] = l[property_name]
        memory_sum += memory

    return memory_sum / len(logs)

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
        j["MAJOR_GC_TIME"] = calculate_total_major_gc_time(result_directory)
        j["AVERAGE_HEAP_MEMORY"] = calculate_average_heap_memory(result_directory)
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
                          "args":["--no-sandbox", "--disable-notifications", "--start-maximized", "--user-data-dir=/home/marisa/membalancer_profile"]}

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
    bench = {}

    async def reddit(browser, duration):
        page = await new_page(browser)
        await page.goto("https://reddit.com", timeout=duration*1000, waitUntil='domcontentloaded')
        await page.waitForSelector("i.icon-comment")
        i = 0
        while time.time() - start < duration:
            l = await page.querySelectorAll("i.icon-comment")
            assert i < len(l)
            await page.evaluate("(element) => element.scrollIntoView()", l[i])
            await asyncio.sleep(5)
            link = await page.evaluate("(element) => element.parentElement.href", l[i])
            sub_page = await new_page(browser)
            await sub_page.goto(link, {"waitUntil" : "domcontentloaded"}, timeout=duration*1000, waitUntil='domcontentloaded')
            await asyncio.sleep(10)
            await sub_page.close()
            await asyncio.sleep(5)
            i += 1
    bench["reddit"] = reddit

    async def twitter(browser, duration):
        start = time.time()
        page = await new_page(browser)
        await page.goto("https://www.twitter.com", timeout=duration*1000, waitUntil='domcontentloaded')
        await asyncio.sleep(1)
        while time.time() - start < duration:
            await page.evaluate("{window.scrollBy(0, 50);}")
            await asyncio.sleep(1)
    bench["twitter"] = twitter

    async def cnn(browser, duration):
        start = time.time()
        page = await new_page(browser)
        await page.goto("https://www.cnn.com/", timeout=duration*1000, waitUntil='domcontentloaded')
        await asyncio.sleep(1)
        while time.time() - start < duration:
            await page.evaluate("{window.scrollBy(0, 50);}")
            await asyncio.sleep(1)
    bench["cnn"] = cnn

    async def gmail(browser):
        page = await new_page(browser)
        await page.goto("https://www.gmail.com")
        await asyncio.sleep(5)
        for i in range(5):
            await page.evaluate(f'document.querySelectorAll(".zA")[{i}].click()')
            await asyncio.sleep(10)
            await page.evaluate('document.querySelector(".TN.bzz.aHS-bnt").click()')
            await asyncio.sleep(5)

    async def espn(browser, duration):
        start = time.time()
        page = await new_page(browser)
        await page.goto("https://www.espn.com/", timeout=duration*1000, waitUntil='domcontentloaded')
        await asyncio.sleep(1)
        while time.time() - start < duration:
            await page.evaluate("{window.scrollBy(0, 50);}")
            await asyncio.sleep(1)
    bench["espn"] = espn

    # problem - cannot watch twitch video
    async def twitch(browser):
        page = await new_page(browser)
        await page.goto("https://www.twitch.com/")
        await asyncio.sleep(100)

    async def cookie_clicker(browser, duration):
        start = time.time()
        page = await new_page(browser)
        await page.goto("https://orteil.dashnet.org/cookieclicker/", timeout=duration*1000)
        while time.time() - start > duration:
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

    # bug
    async def two_browser_bug():
        l = await new_browser()
        r = await new_browser()

    def get_bench(bench_name):
        return bench[bench_name]

    async def run_browser_main():
        b = await new_browser()
        d = 180
        await asyncio.gather(*[get_bench(bench)(b, d) for bench in BENCH])
        await b.close()

    #for sign in and other configuration purpose
    #async def run_browser_main():
    #    b = await new_browser()
    #    hang()

    start = time.time()
    asyncio.get_event_loop().run_until_complete(run_browser_main())
    end = time.time()

    j = {}
    j["OK"] = True
    j["MAJOR_GC_TIME"] = calculate_total_major_gc_time(result_directory)
    for p in ["PhysicalMemory", "SizeOfObjects", "Limit"]:
        j[f"Peak_{p}"] = calculate_peak(result_directory, p)
        j[f"Average_{p}"] = calculate_average(result_directory, p)
    j["Peak_BalancerMemory"] = calculate_peak_balancer_memory(result_directory)
    j["Average_BalancerMemory"] = calculate_peak_balancer_memory(result_directory)
    j["TOTAL_TIME"] = end - start
    with open(os.path.join(result_directory, "score"), "w") as f:
        json.dump(j, f)

with ProcessScope(subprocess.Popen(balancer_cmds, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)) as p:
    subprocess.Popen(["tee", result_directory+"balancer_out"], stdin=p.stdout)
    time.sleep(1) # make sure the balancer is running
    memory_limit = f"{MEMORY_LIMIT * MB_IN_BYTES}"

    v8_env_vars = {"USE_MEMBALANCER": "1", "LOG_GC": "1", "LOG_DIRECTORY": result_directory}

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
