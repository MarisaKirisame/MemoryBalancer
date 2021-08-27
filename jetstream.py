import pyppeteer
import asyncio
import time

USE_MEMBALANCER_CHROME = True

DEBUG = False

def hang():
    while True:
        pass


async def main():
    browseroptions = {"headless":False,
                      "args":["--no-sandbox"]}
    if USE_MEMBALANCER_CHROME:
        browseroptions["executablePath"] = "/home/marisa/Work/chromium/src/out/Default/chrome"
    else:
        browseroptions["executablePath"] = "chromium"
    if DEBUG:
        browseroptions["dumpio"] = True
    browser = await pyppeteer.launch(browseroptions)
    page = await browser.newPage()
    await page.goto("https://browserbench.org/JetStream/")
    await page.waitForSelector("div#status a.button", timeout=0)
    await page.click("div#status a.button")

    await page.waitForSelector("div.score", timeout=0)
    scoreElement = await page.querySelector("div.score")
    score = await page.evaluate('(element) => element.innerText', scoreElement)
    print(score)
    await page.screenshot({'path': 'example.png'})
    await browser.close()

asyncio.get_event_loop().run_until_complete(main())
