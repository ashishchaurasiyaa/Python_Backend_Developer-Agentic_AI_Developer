"""
Modern Topics — Doc 6: Playwright (PRACTICAL — Hands On)
=========================================================
Real browser ko Python se chalao. Har section run karke dekho.

Topics:
  1. Hello browser (launch → goto → screenshot)
  2. Locators + actions (fill a form, click)  [public demo site]
  3. Auto-waiting vs time.sleep (the killer feature)
  4. Web-first assertions (expect, auto-retry)
  5. Scraping a JS list (real data nikalna)
  6. Network interception (images block / API mock)
  7. Save & reuse login (storage_state)
  8. Async API (FastAPI/asyncio style)

Install (ek baar):
    pip install playwright
    playwright install chromium

Run:
    python 06_playwright_browser_automation_practical.py
    # ya ek section: python 06_playwright_browser_automation_practical.py 5

Note: ye public demo sites use karta hai. Internet chahiye.
      HEADLESS=False kar do agar browser dikhana ho.
"""

import sys
import time

HEADLESS = True   # False kar do to browser khulta dikhe ga

try:
    from playwright.sync_api import sync_playwright, expect
except ImportError:
    print("Playwright not installed. Run:")
    print("    pip install playwright && playwright install chromium")
    sys.exit(1)


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1: Hello browser — launch, navigate, screenshot
# ─────────────────────────────────────────────────────────────────────────────

def section_1_hello():
    print("\n[1] Hello browser")
    with sync_playwright() as p:
        # Browser → Context → Page  (yaad rakho: 3-layer model)
        browser = p.chromium.launch(headless=HEADLESS)
        context = browser.new_context()        # fresh cookies/storage
        page = context.new_page()              # ek tab

        page.goto("https://example.com")
        print("   title:", page.title())
        print("   h1   :", page.get_by_role("heading").inner_text())

        page.screenshot(path="example_shot.png")
        print("   saved -> example_shot.png")

        browser.close()


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2: Locators + actions — login form bharna (demo site)
# ─────────────────────────────────────────────────────────────────────────────

def section_2_form():
    print("\n[2] Locators + form fill (the-internet.herokuapp.com)")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=HEADLESS)
        page = browser.new_page()
        page.goto("https://the-internet.herokuapp.com/login")

        # get_by_label / get_by_role — user-facing locators (refactor-proof)
        page.get_by_label("Username").fill("tomsmith")
        page.get_by_label("Password").fill("SuperSecretPassword!")
        page.get_by_role("button", name="Login").click()

        # success message padho
        msg = page.locator("#flash").inner_text()
        print("   server says:", msg.split("\n")[0].strip())

        browser.close()


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3: Auto-waiting vs time.sleep — THE killer feature
# ─────────────────────────────────────────────────────────────────────────────

def section_3_autowait():
    print("\n[3] Auto-waiting (no sleep needed)")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=HEADLESS)
        page = browser.new_page()
        # Is page pe button click karne ke baad content 'dynamically' (delay se) aata hai
        page.goto("https://the-internet.herokuapp.com/dynamic_loading/2")

        t0 = time.time()
        page.get_by_role("button", name="Start").click()
        # ❌ NO time.sleep(5). Playwright khud wait karega jab tak text visible na ho:
        page.wait_for_selector("#finish")
        print("   loaded text:", page.locator("#finish").inner_text())
        print(f"   waited ~{time.time()-t0:.1f}s automatically (no manual sleep)")

        browser.close()


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4: Web-first assertions — expect() auto-retries
# ─────────────────────────────────────────────────────────────────────────────

def section_4_expect():
    print("\n[4] expect() assertions (auto-retry)")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=HEADLESS)
        page = browser.new_page()
        page.goto("https://the-internet.herokuapp.com/login")

        # plain assert ke bajaye expect — ye timeout tak retry karta hai
        expect(page).to_have_title("The Internet")
        expect(page.get_by_role("button", name="Login")).to_be_enabled()
        print("   ✓ title correct, ✓ login button enabled")

        browser.close()


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5: Scraping — JS list se structured data nikalna
# ─────────────────────────────────────────────────────────────────────────────

def section_5_scrape():
    print("\n[5] Scrape quotes (quotes.toscrape.com)")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=HEADLESS)
        page = browser.new_page()
        page.goto("https://quotes.toscrape.com/")

        quotes = page.locator(".quote")
        count = quotes.count()
        print(f"   found {count} quotes on page 1:")
        for i in range(min(count, 3)):       # pehle 3 dikhao
            q = quotes.nth(i)
            text = q.locator(".text").inner_text()
            author = q.locator(".author").inner_text()
            print(f"     - {author}: {text[:50]}...")

        browser.close()


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 6: Network interception — images block + API mock
# ─────────────────────────────────────────────────────────────────────────────

def section_6_network():
    print("\n[6] Network interception")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=HEADLESS)
        page = browser.new_page()

        # Saari images abort kar do (page fast load + bandwidth bachao)
        blocked = {"n": 0}

        def block_images(route):
            blocked["n"] += 1
            route.abort()

        page.route("**/*.{png,jpg,jpeg,gif,svg}", block_images)
        page.goto("https://quotes.toscrape.com/")
        print(f"   blocked {blocked['n']} image request(s) — page still loaded")

        browser.close()


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 7: Save & reuse login — storage_state (har test me login mat karo)
# ─────────────────────────────────────────────────────────────────────────────

def section_7_storage():
    print("\n[7] Save login state -> reuse in new context")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=HEADLESS)

        # --- Pehli baar: login karo aur state save karo ---
        ctx1 = browser.new_context()
        page1 = ctx1.new_page()
        page1.goto("https://the-internet.herokuapp.com/login")
        page1.get_by_label("Username").fill("tomsmith")
        page1.get_by_label("Password").fill("SuperSecretPassword!")
        page1.get_by_role("button", name="Login").click()
        page1.wait_for_url("**/secure")
        ctx1.storage_state(path="auth.json")        # cookies/localStorage save
        print("   saved cookies -> auth.json")

        # --- Doosri baar: naya context with saved state = already logged in ---
        ctx2 = browser.new_context(storage_state="auth.json")
        page2 = ctx2.new_page()
        page2.goto("https://the-internet.herokuapp.com/secure")
        logged_in = page2.get_by_text("Welcome to the Secure Area").is_visible()
        print("   reused session, logged in:", logged_in)

        browser.close()


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 8: Async API — FastAPI / asyncio ke saath aise use karo
# ─────────────────────────────────────────────────────────────────────────────

def section_8_async():
    print("\n[8] Async API (asyncio)")
    import asyncio
    from playwright.async_api import async_playwright

    async def run():
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=HEADLESS)
            page = await browser.new_page()
            await page.goto("https://example.com")
            title = await page.title()
            print("   async title:", title)
            await browser.close()

    asyncio.run(run())


# ─────────────────────────────────────────────────────────────────────────────
# Runner
# ─────────────────────────────────────────────────────────────────────────────

SECTIONS = {
    1: section_1_hello,
    2: section_2_form,
    3: section_3_autowait,
    4: section_4_expect,
    5: section_5_scrape,
    6: section_6_network,
    7: section_7_storage,
    8: section_8_async,
}

if __name__ == "__main__":
    if len(sys.argv) > 1:
        SECTIONS[int(sys.argv[1])]()
    else:
        for n, fn in SECTIONS.items():
            try:
                fn()
            except Exception as e:
                print(f"   [section {n} skipped: {e}]")
    print("\nDone. (HEADLESS=False kar do browser dekhne ke liye)")
