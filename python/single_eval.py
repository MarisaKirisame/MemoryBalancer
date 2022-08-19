import asyncio
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from collections import defaultdict
from util import tex_def, tex_fmt, new_browser
import paper
import pyppeteer

SCROLL_PIX = 50
SCROLL_SLEEP = 1
EVAL_SLEEP = 5
GMAIL_WAIT_TIME = 5
GMAIL_INBOX_TIME = 10
GMAIL_EMAIL_TIME = 5

if len(sys.argv) == 1:
    print("generating tex file...")
    tex = ""
    for name in ["SCROLL_PIX", "SCROLL_SLEEP", "EVAL_SLEEP", "GMAIL_WAIT_TIME", "GMAIL_INBOX_TIME", "GMAIL_EMAIL_TIME"]:
        tex += tex_def("SingleEval" + name.replace('_', ''), f"{tex_fmt(eval(name))}")
    paper.pull()
    with open(f"../membalancer-paper/single_eval.tex", "w") as tex_file:
        tex_file.write(tex)
    paper.push()
    sys.exit(0)

assert(len(sys.argv) == 3)
cfg = eval(sys.argv[1])["CFG"]
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
if RESIZE_STRATEGY == "gradient":
    GC_RATE_D = RESIZE_CFG["GC_RATE_D"]
BALANCE_FREQUENCY = BALANCER_CFG["BALANCE_FREQUENCY"]

TYPE = cfg["TYPE"]

wait_until = "networkidle2"
wait_until = "domcontentloaded"

def report_jetstream_score():
    with open(filename) as f:
        print(f.read())

def hang():
    while True:
        pass

# weird error: terminate does not work when exception is raised. fix this.
class ProcessScope:
    def __init__(self, p):
        self.p = p
    def __enter__(self):
        return self.p
    def __exit__(self, *args):
        self.p.terminate()

MB_IN_BYTES = 1024 * 1024

balancer_cmds = ["./build/MemoryBalancer", "daemon"]
balancer_cmds.append(f"--resize-strategy={RESIZE_STRATEGY}")
if RESIZE_STRATEGY == "gradient":
    balancer_cmds.append(f"--gc-rate-d={GC_RATE_D}")
balancer_cmds.append(f"--balance-frequency={BALANCE_FREQUENCY}")

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
        j = {}
        j["OK"] = False
        j["ERROR"] = main_process_result.stdout
        with open(os.path.join(result_directory, "score"), "w") as f:
            json.dump(j, f)
    else:
        j = {}
        j["OK"] = True
        with open(os.path.join(result_directory, "score"), "w") as f:
            json.dump(j, f)

def run_acdc(v8_env_vars):
    command = f"""build/MemoryBalancer acdc""" # a very big heap size to essentially have no limit
    main_process_result = subprocess.run(f"{env_vars_str(v8_env_vars)} {command}", shell=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    with open(os.path.join(result_directory, "v8_out"), "w") as f:
        f.write(main_process_result.stdout)
        j = {}
    if main_process_result.returncode == 0:
        j["OK"] = True
    else:
        j["OK"] = False
        j["ERROR"] = main_process_result.stdout
    with open(os.path.join(result_directory, "score"), "w") as f:
        json.dump(j, f)

def run_browser(v8_env_vars):
    async def new_page(browser):
            page = await browser.newPage()
            await page.setViewport({"width": 1280, "height": 1080})
            await (await browser.pages())[0].bringToFront()
            return page
    bench = {}

    async def reddit(browser, duration):
        start = time.time()
        page = await new_page(browser)
        await page.goto("https://reddit.com", timeout=duration*1000, waitUntil=wait_until)
        await page.waitForSelector("i.icon-comment")
        i = 0
        while time.time() - start < duration:
            l = await page.querySelectorAll("i.icon-comment")
            assert i < len(l)
            await page.evaluate("(element) => element.scrollIntoView()", l[i])
            await asyncio.sleep(5)
            link = await page.evaluate("(element) => element.parentElement.href", l[i])
            sub_page = await new_page(browser)
            await sub_page.goto(link, timeout=15*1000, waitUntil=wait_until)
            await asyncio.sleep(10)
            await sub_page.close()
            await asyncio.sleep(5)
            i += 1
    bench["reddit"] = reddit

    async def scroll_website(browser, duration, website):
        start = time.time()
        page = await new_page(browser)
        await page.goto(website, timeout=duration*1000, waitUntil=wait_until)
        while time.time() - start < duration:
            await page.evaluate(f"{{window.scrollBy(0, {SCROLL_PIX});}}")
            await asyncio.sleep(SCROLL_SLEEP)

    async def twitter(browser, duration):
        await scroll_website(browser, duration, "https://www.twitter.com")
    bench["twitter"] = twitter

    async def cnn(browser, duration):
        await scroll_website(browser, duration, "https://www.cnn.com/")
    bench["cnn"] = cnn

    async def gmail(browser, duration):
        start = time.time()
        page = await new_page(browser)
        # cannot use domcontentloaded as that is too quick
        await page.goto("https://www.gmail.com", timeout=duration*1000)
        await asyncio.sleep(GMAIL_WAIT_TIME)
        i = 0
        while time.time() - start < duration:
            await page.evaluate(f'document.querySelectorAll(".zA")[{i}].click()')
            await asyncio.sleep(GMAIL_EMAIL_TIME)
            await page.evaluate('document.querySelector(".TN.bzz.aHS-bnt").click()')
            await asyncio.sleep(GMAIL_INBOX_TIME)
            i += 1
    bench["gmail"] = gmail

    async def espn(browser, duration):
        await scroll_website(browser, duration, "https://www.espn.com/")
    bench["espn"] = espn

    async def facebook(browser, duration):
        start = time.time()
        page = await new_page(browser)
        await page.goto("https://www.facebook.com/", timeout=duration*1000, waitUntil=wait_until)
        await asyncio.sleep(EVAL_SLEEP)
        groups = (await page.xpath("//*[text() = 'Groups']"))[0]
        await page.evaluate("(g) => g.click()", groups)
        await asyncio.sleep(EVAL_SLEEP)
        while time.time() - start < duration:
            await page.evaluate(f"{{window.scrollBy(0, {SCROLL_PIX});}}")
            await asyncio.sleep(SCROLL_SLEEP)
    bench["facebook"] = facebook

    # problem - doesnt seems to load as it scroll continuously
    async def foxnews(browser, duration):
        await scroll_website(browser, duration, "https://www.foxnews.com/")
    bench["foxnews"] = foxnews

    async def yahoo(browser, duration):
        start = time.time()
        page = await new_page(browser)
        await page.goto("https://www.news.yahoo.com/", timeout=duration*1000, waitUntil=wait_until)
        await asyncio.sleep(1)
        while time.time() - start < duration:
            await page.evaluate("{window.scrollBy(0, 50);}")
            await asyncio.sleep(1)
    bench["yahoo"] = yahoo

    async def medium(browser, duration):
        start = time.time()
        page = await new_page(browser)
        await page.goto("https://www.medium.com/", timeout=duration*1000, waitUntil=wait_until)
        await asyncio.sleep(1)
        while time.time() - start < duration:
            await page.evaluate("{window.scrollBy(0, 50);}")
            await asyncio.sleep(1)
    bench["medium"] = medium

    # problem - cannot watch twitch video
    async def twitch(browser):
        page = await new_page(browser)
        await page.goto("https://www.twitch.com/")
        await asyncio.sleep(100)

    # problem - use too little memory
    async def cookie_clicker(browser, duration):
        start = time.time()
        page = await new_page(browser)
        await page.goto("https://orteil.dashnet.org/cookieclicker/", timeout=duration*1000)
        while time.time() - start < duration:
            bigCookie = await page.querySelector("#bigCookie")
            items = await page.querySelectorAll(".product.unlocked.enabled")
            upgrades = await page.querySelectorAll(".crate.upgrade")
            notifications = await page.querySelectorAll(".note .close")
            for clickable in [bigCookie] + items + upgrades + notifications:
                await page.evaluate("(c) => c.click()", clickable)
                await asyncio.sleep(1)

    # problem - use too little memory
    async def youtube(browser, duration):
        page = await new_page(browser)
        await page.goto("https://www.youtube.com/watch?v=dQw4w9WgXcQ", {'waitUntil' : wait_until})
        await asyncio.sleep(100)

    async def gmap(browser):
        page = await new_page(browser)
        await page.goto("https://www.google.com/maps", {'waitUntil' : wait_until})
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

    def get_bench(bench_name):
        return bench[bench_name]

    async def run_browser_main():
        b = await new_browser(env_vars=v8_env_vars, headless=True, debug=False)
        d = 180
        try:
            await asyncio.wait_for(asyncio.gather(*[get_bench(bench)(b, d) for bench in BENCH]), timeout=d*2)
        finally:
            await b.close()

    start = time.time()
    asyncio.get_event_loop().run_until_complete(run_browser_main())
    end = time.time()

    j = {}
    j["OK"] = True
    j["TOTAL_TIME"] = end - start
    with open(os.path.join(result_directory, "score"), "w") as f:
        json.dump(j, f)

with open(result_directory+"balancer_out", "w") as balancer_out:
    with ProcessScope(subprocess.Popen(balancer_cmds, stdout=balancer_out, stderr=subprocess.STDOUT)) as p:
        time.sleep(1) # make sure the balancer is running
        memory_limit = f"{MEMORY_LIMIT * MB_IN_BYTES}"

        v8_env_vars = {"LOG_GC": "1", "LOG_DIRECTORY": result_directory}

        if not RESIZE_STRATEGY == "ignore":
            v8_env_vars["USE_MEMBALANCER"] = "1"
            v8_env_vars["SKIP_RECOMPUTE_LIMIT"] = "1"
            v8_env_vars["SKIP_MEMORY_REDUCER"] = "1"
            v8_env_vars["C_VALUE"] = str(GC_RATE_D)
        if TYPE == "jetstream":
            run_jetstream(v8_env_vars)
        elif TYPE == "browser":
            run_browser(v8_env_vars)
        elif TYPE == "acdc":
            run_acdc(v8_env_vars)
        else:
            p.kill()
            raise Exception(f"unknown benchmark type: {TYPE}")
        time.sleep(10) # make sure the balancer is running
        p.kill()
