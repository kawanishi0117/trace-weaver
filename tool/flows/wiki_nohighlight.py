import re
from playwright.sync_api import Playwright, sync_playwright, expect


def run(playwright: Playwright) -> None:
    browser = playwright.chromium.launch(channel="chrome", headless=False)
    context = browser.new_context(viewport={"width":1280,"height":720})
    page = context.new_page()
    page.goto("https://ja.wikipedia.org")
    page.get_by_role("link", name="Wikipedia:今日の一枚", exact=True).click()
    page.get_by_role("link", name="Wikipedia:秀逸な画像", exact=True).click()
    page.close()

    # ---------------------
    context.close()
    browser.close()


with sync_playwright() as playwright:
    run(playwright)
