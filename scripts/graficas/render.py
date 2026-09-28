import glob, asyncio
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(device_scale_factor=2, viewport={"width":1600,"height":1100})
        for h in sorted(glob.glob("*.html")):
            import os
            await pg.goto("file://" + os.path.abspath(h)); await pg.wait_for_timeout(300)
            await (await pg.query_selector("#c")).screenshot(path=h.replace(".html",".png"))
        await b.close()
asyncio.run(main())
