import asyncio
from pyppeteer import launch
from pyppeteer_stealth import stealth
import os
import time
import subprocess
from pathlib import Path

# weird error: terminate does not work when exception is raised. fix this.
class ProcessScope:
    def __init__(self, p):
        self.p = p
    def __enter__(self):
        return self.p
    def __exit__(self, *args):
        self.p.terminate()

async def new_page(browser):
    page = await browser.newPage()
    await page.setViewport({"width": 1280, "height": 1080})
    return page

async def reddit(browser):
    page = await new_page(browser)
    await page.goto("https://reddit.com", timeout=120*1000)
    await page.waitForSelector("i.icon-comment")
    for i in range(10):
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

# problem - does not work with membalancer
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

USE_MEMBALANCER_CHROME = True
LOG_GC = True
USE_MEMBALANCER = True
DEBUG = False
async def new_browser():
    browseroptions = {"headless":False,
                      "args":["--no-sandbox", "--disable-notifications", "--start-maximized"]}

    if USE_MEMBALANCER_CHROME:
        browseroptions["executablePath"] = "/home/marisa/Work/chromium/src/out/Release/chrome"

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
    return await launch(browseroptions)

def hang():
    while True:
        pass

result_directory = "log/" + time.strftime("%Y-%m-%d-%H-%M-%S") + "/"
Path(result_directory).mkdir()
balancer_cmds = ["/home/marisa/Work/MemoryBalancer/build/MemoryBalancer", "daemon"]
balancer_cmds.append(f"--balance-strategy=ignore")
balancer_cmds.append(f"--resize-strategy=ignore")
balancer_cmds.append(f"--smooth-type=no-smoothing")
balancer_cmds.append(f"--balance-frequency=0")
balancer_cmds.append(f"""--log-path={result_directory+"balancer_log"}""")
async def main():
    with ProcessScope(subprocess.Popen(balancer_cmds, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)) as p:
        subprocess.Popen(["tee", result_directory+"balancer_out"], stdin=p.stdout)
        time.sleep(1) # make sure the balancer is running
        await new_browser()
        hang()
        #await asyncio.gather(reddit(await new_browser()))

asyncio.get_event_loop().run_until_complete(main())
