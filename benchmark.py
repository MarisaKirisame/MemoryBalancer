import pyppeteer
import asyncio
import sys
import subprocess
import os
import json
from pathlib import Path

USE_MEMBALANCER_CHROME = True

USE_MEMBALANCER = True

LOG_GC = True

BENCHMARK_NAME = "JETSTREAM"

DEBUG = True

def check_config():
    if USE_MEMBALANCER:
        assert(USE_MEMBALANCER_CHROME)
    if LOG_GC:
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
    if LOG_GC:
        env["LOG_GC"] = "1"

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

async def run_speedometer(page):
    await page.goto("https://browserbench.org/Speedometer2.0/")
    await page.waitForSelector(".selected .buttons", timeout=0)
    await page.click(".selected .buttons")
    await page.waitForSelector("#result-number", timeout=0)
    scoreElement = await page.querySelector("#result-number")
    await page.waitForFunction(""" document.querySelector("#result-number").textContent != "" """, timeout=0);
    score = await page.evaluate('(element) => element.textContent', scoreElement)
    return float(score)

BENCHMARK = {"JETSTREAM":run_jetstream, "SPEEDOMETER":run_speedometer}
async def worker():
    browser = await get_browser()
    pages = await browser.pages()
    assert(len(pages) == 1)
    score = await BENCHMARK[BENCHMARK_NAME](pages[0])
    return score

NUM_WORKER = 3
async def async_main(result_directory):
    f = open(result_directory + "log", "w")

    tasks = []
    for _ in range(NUM_WORKER):
        tasks.append(asyncio.create_task(worker()))
        await asyncio.sleep(60)

    score = 0
    for t in tasks:
        score += await t

    print("async done, score: " + str(score / NUM_WORKER))
    f.write(str(score / NUM_WORKER))
    f.close()

def main():
    assert(len(sys.argv) == 2)
    result_directory = sys.argv[1]
    check_config()
    asyncio.get_event_loop().run_until_complete(async_main(sys.argv[1]))

main()
