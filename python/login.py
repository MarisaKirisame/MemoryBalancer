import asyncio
from util import new_browser
async def login_main():
    await new_browser(headless=False)
    while True:
        pass
asyncio.get_event_loop().run_until_complete(login_main())
