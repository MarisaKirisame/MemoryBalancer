import pyppeteer
import asyncio
import sys
import subprocess
import os

USE_MEMBALANCER_CHROME = True

USE_MEMBALANCER = True

DEBUG = True

def check_config():
    if USE_MEMBALANCER:
        assert(USE_MEMBALANCER_CHROME)

def hang():
    while True:
        pass

async def get_browser():
    browseroptions = {"headless":False,
                      "args":["--no-sandbox"]}

    if USE_MEMBALANCER_CHROME:
        browseroptions["executablePath"] = "/home/marisa/Work/chromium/src/out/Default/chrome"

    # we need the environment variable for headless:False, because it include stuff such for graphics such as DISPLAY.
    # todo: isolate them instead of passing the whole env var?
    env = os.environ.copy()
    if USE_MEMBALANCER:
        env["USE_MEMBALANCER"] = "1"

    browseroptions["env"] = env

    if DEBUG:
        browseroptions["dumpio"] = True
    return await pyppeteer.launch(browseroptions)

async def run_jetstream(page):
    await page.goto("https://browserbench.org/JetStream/")
    await page.waitForSelector("div#status a.button", timeout=0)
    await page.click("div#status a.button")

    await page.waitForSelector("div.score", timeout=0)
    scoreElement = await page.querySelector("div.score")
    score = await page.evaluate('(element) => element.innerText', scoreElement)
    return float(score)

async def worker():
    browser = await get_browser()
    pages = await browser.pages()
    assert(len(pages) == 1)
    score = await run_jetstream(pages[0])
    return score

NUM_JETSTREAM = 3
async def main(filename):
    f = open(filename, "w")

    tasks = []
    for _ in range(NUM_JETSTREAM):
        tasks.append(asyncio.create_task(worker()))
        await asyncio.sleep(60)

    score = 0
    for t in tasks:
        score += await t

    print("async done, score: " + str(score / NUM_JETSTREAM))
    f.write(str(score / NUM_JETSTREAM))
    f.close()

check_config()

balancer = subprocess.Popen("/home/marisa/Work/MemoryBalancer/build/MemoryBalancer")

assert(len(sys.argv) == 2)
asyncio.get_event_loop().run_until_complete(main(sys.argv[1]))

print("kill balancer")
balancer.terminate()
