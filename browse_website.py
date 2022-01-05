import asyncio
from pyppeteer import launch
from pyppeteer_stealth import stealth

async def reddit(browser):
    page = await browser.newPage()
    await page.goto("https://reddit.com")
    await page.waitForSelector("i.icon-comment")
    for i in range(10):
        l = await page.querySelectorAll("i.icon-comment")
        assert i < len(l)
        link = await page.evaluate("(element) => element.parentElement.href", l[i])
        sub_page = await browser.newPage()
        await sub_page.goto(link, {"waitUntil" : "domcontentloaded"})
        await asyncio.sleep(5)
        await sub_page.close()
    await asyncio.sleep(100)

# problem - twitter is being blocked when it detect we are bot
async def twitter(browser):
    page = await browser.newPage()
    await stealth(page)
    await page.setUserAgent('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/73.0.3683.75 Safari/537.36');
    await page.goto("https://twitter.com")
    for i in range(20):
        await page.evaluate("{window.scrollBy(0, 10);}")
        await asyncio.sleep(5)

async def twitch(browser):
    page = await browser.newPage()
    await page.goto("https://www.twitch.com/")
    await asyncio.sleep(100)
    return

async def cookie_clicker(browser):
    page = await browser.newPage()
    await page.setViewport({"width": 1280, "height": 1080})
    await page.goto("https://orteil.dashnet.org/cookieclicker/")
    while True:
        bigCookie = await page.querySelector("#bigCookie")
        items = await page.querySelectorAll(".product.unlocked.enabled")
        upgrades = await page.querySelectorAll(".crate.upgrade")
        notifications = await page.querySelectorAll(".note .close")
        for clickable in [bigCookie] + items + upgrades + notifications:
            await page.evaluate("(c) => c.click()", clickable)
        await asyncio.sleep(0.1)
    return

async def youtube(browser):
    page = await browser.newPage()
    await page.setViewport({"width": 1280, "height": 1080})
    await page.goto("https://www.youtube.com/watch?v=dQw4w9WgXcQ", {'waitUntil' : 'domcontentloaded'})
    await asyncio.sleep(100)

async def gmap(browser):
    page = await browser.newPage()
    await page.setViewport({"width": 1280, "height": 1080})
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

async def main():
    browser = await launch(headless=False, args=["--disable-notifications", "--start-maximized"])
    await gmap(browser)
asyncio.get_event_loop().run_until_complete(main())
