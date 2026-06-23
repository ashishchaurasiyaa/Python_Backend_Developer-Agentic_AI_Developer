# Modern Topics — Doc 6: Playwright (Browser Automation) ⭐

> **Goal:** Playwright = code se browser ko control karna (click, type, scrape, test). Ye **agentic AI ka "hands" hai web ke liye** — aur backend devs ke liye E2E testing ka modern standard. Selenium ka successor.

---

## 1. Playwright kya hai?

**Playwright** = Microsoft ka open-source library jo **real browser** (Chromium, Firefox, WebKit) ko code se drive karta hai.

Tum likhte ho:
```
"is page pe jao → login button click karo → email bharo → submit karo → result padho"
```
Aur Playwright ek **real Chrome** kholkar wahi steps perform karta hai — bilkul ek insaan ki tarah.

Do bade use-cases:
1. **E2E Testing** — pura user flow automate karke test karna (login, checkout, etc.)
2. **Automation / Scraping** — JS-heavy pages se data nikalna, forms bharna, repetitive web kaam.
3. **Agentic AI** — LLM agent ko "web browse karne wale haath" dena (Playwright MCP). → Section 12.

---

## 2. Selenium se behtar kyun? (Interview gold 🎯)

| Feature | Selenium | **Playwright** |
|---|---|---|
| Auto-waiting | ❌ manual `sleep`/waits | ✅ built-in, har action se pehle |
| Speed | Slow | Fast (CDP protocol) |
| Browsers | Driver dauwnload jhanjhat | ✅ ek command me sab |
| Async support | Limited | ✅ native async + sync dono |
| Network intercept | Mushkil | ✅ first-class |
| Auto-wait flaky tests | Bahut | Kam (biggest win) |
| Codegen (record) | Plugin chahiye | ✅ built-in `playwright codegen` |

**One-line answer:** "Playwright auto-waits for elements, so tests become **far less flaky** than Selenium — that's the killer feature."

---

## 3. Install & Setup (Python)

```bash
pip install playwright
playwright install            # browsers download (chromium, firefox, webkit)
# ya sirf ek:
playwright install chromium
```

Testing ke liye pytest plugin:
```bash
pip install pytest-playwright
```

---

## 4. Core Mental Model — 3 layers 🧠

Playwright ki har cheez in 3 cheezon ke around ghoomti hai:

```
Browser   →  pura browser process (Chromium)
  └─ Context →  ek "incognito session" (apne cookies, storage)  ← isolation yahin hota hai
       └─ Page →  ek tab / web page                              ← yahan tum kaam karte ho
```

- **Browser**: heavy, ek hi launch karo.
- **Context**: sasta. Har test ke liye naya context = clean state, no leaks. (Selenium me ye pain tha.)
- **Page**: actual tab jahan navigate/click/type hota hai.

```python
browser = p.chromium.launch()
context = browser.new_context()   # fresh cookies/storage
page = context.new_page()         # ek tab
page.goto("https://example.com")
```

---

## 5. Sync vs Async API

Playwright dono deta hai. **Seekhne ke liye sync simpler hai**, production async me scale karta hai.

```python
# SYNC (simple, padhna aasan)
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    page = p.chromium.launch().new_page()
    page.goto("https://example.com")

# ASYNC (FastAPI/asyncio ke saath, concurrent pages)
from playwright.async_api import async_playwright
async with async_playwright() as p:
    browser = await p.chromium.launch()
    page = await browser.new_page()
    await page.goto("https://example.com")
```

> Backend dev tip: agar tum FastAPI me browser automation chahte ho → **async API** use karo, warna event loop block hoga.

---

## 6. Locators — element dhoondhne ka modern tareeka ⭐

Purana tareeka (CSS/XPath) brittle hota hai. Playwright **user-facing locators** push karta hai — jaise ek insaan element dhoondhta hai:

```python
page.get_by_role("button", name="Sign in")   # ✅ BEST — accessibility role
page.get_by_text("Welcome back")
page.get_by_label("Email")                     # form fields ke liye
page.get_by_placeholder("Enter your email")
page.get_by_test_id("submit-btn")              # data-testid attribute
page.locator("css=.btn-primary")               # fallback: CSS
page.locator("xpath=//button")                 # fallback: XPath
```

**Rule of thumb (interview):** prefer `get_by_role` → `get_by_label` → `get_by_test_id` → CSS → XPath (last resort). Role/label locators **refactor ke baad bhi tootte nahi**.

Locator **lazy** hota hai — banane pe DOM query nahi hoti, sirf action ke time hoti hai. Isliye locator ko variable me reuse kar sakte ho.

---

## 7. Actions

```python
page.goto("https://site.com")
page.get_by_role("button", name="Login").click()
page.get_by_label("Email").fill("a@b.com")     # fill = clear + type (fast)
page.get_by_label("Password").type("secret")   # type = key-by-key (slow, events fire)
page.get_by_role("checkbox").check()
page.get_by_role("combobox").select_option("IN")
page.get_by_role("button", name="Submit").click()

# Navigation / waiting
page.wait_for_url("**/dashboard")
text = page.get_by_role("heading").inner_text()
```

---

## 8. Auto-waiting — THE killer feature ⭐⭐

Selenium me `time.sleep(2)` likhna padta tha → flaky. Playwright **har action se pehle automatically wait** karta hai jab tak element:
- DOM me attached ho
- visible ho
- stable ho (animate ho raha to ruk jao)
- enabled ho (disabled button click nahi karega)
- events receive kar sake

```python
# Ye line internally wait karti hai jab tak button clickable na ho:
page.get_by_role("button", name="Save").click()
# ❌ NO time.sleep needed
```

Default timeout 30s. Explicit waits jab chahiye:
```python
page.wait_for_selector(".results")
page.wait_for_load_state("networkidle")
expect(page.get_by_text("Success")).to_be_visible(timeout=5000)
```

**Interview line:** "Playwright's auto-waiting eliminates `sleep()`-based flakiness — it waits on the element's *actionability*, not a fixed time."

---

## 9. Assertions (`expect`)

Web-first assertions bhi **auto-retry** karte hain jab tak condition true na ho ya timeout:

```python
from playwright.sync_api import expect

expect(page.get_by_role("heading")).to_have_text("Dashboard")
expect(page.get_by_test_id("cart-count")).to_have_text("3")
expect(page.get_by_role("button", name="Pay")).to_be_enabled()
expect(page).to_have_url("**/checkout")
expect(page).to_have_title("My App")
```

`assert page.inner_text(...) == "x"` se behtar — kyunki `expect` retry karta hai (race conditions handle).

---

## 10. Practical superpowers

```python
# Screenshot / PDF
page.screenshot(path="shot.png", full_page=True)
page.pdf(path="page.pdf")            # sirf chromium headless

# Network interception (ads/images block, mock API)
page.route("**/*.png", lambda route: route.abort())
page.route("**/api/user", lambda route: route.fulfill(json={"name": "Test"}))

# Login state save karke reuse (har test me login na karna pade)
context.storage_state(path="auth.json")
context = browser.new_context(storage_state="auth.json")

# JS evaluate (page ke andar code chalao)
title = page.evaluate("() => document.title")

# Multiple tabs / popups
with page.expect_popup() as popup_info:
    page.get_by_text("Open in new tab").click()
popup = popup_info.value
```

---

## 11. Testing workflow (pytest-playwright)

```python
# test_login.py
def test_login(page):              # 'page' fixture auto-inject
    page.goto("https://app.com/login")
    page.get_by_label("Email").fill("a@b.com")
    page.get_by_label("Password").fill("pass")
    page.get_by_role("button", name="Sign in").click()
    expect(page.get_by_role("heading")).to_have_text("Welcome")
```

```bash
pytest                       # headless (CI default)
pytest --headed              # browser dikhega
pytest --browser firefox
pytest --tracing on          # trace.zip → debug ke liye

# RECORD MODE — sabse useful seekhne ke liye:
playwright codegen https://example.com
# Tum click karo, ye apne aap Python code likh deta hai 🤯
```

**Debugging:** `PWDEBUG=1 pytest` → Playwright Inspector kholta hai (step-by-step). `playwright show-trace trace.zip` → time-travel debugging with screenshots.

---

## 12. Playwright + Agentic AI 🤖 (ye tumhare course se connect hota hai)

Yahan ye topic Modern Topics me hai. Compare with `02_computer_use.md`:

| | **Computer Use** (Claude/GPT vision) | **Playwright** |
|---|---|---|
| Kaise dekhta hai | Screenshot → pixels samajhta hai | DOM (HTML structure) padhta hai |
| Action | "click at x=340,y=210" | "click button named Login" |
| Reliability | Vision galti kar sakta hai | Deterministic, exact |
| Speed | Slow (screenshot loop) | Fast |
| Best for | Koi bhi desktop app | Sirf web, par bahut reliable |

**Playwright MCP** = ek MCP server jo LLM agent ko Playwright tools deta hai (`navigate`, `click`, `type`, `snapshot`). Agent **accessibility tree** (text form me page) dekhta hai aur structured actions leta hai — pixels guess karne se zyada reliable.

```
LLM Agent → "Login karo" 
   → Playwright MCP tool: get_by_role("button", name="Login").click()
   → page ka accessibility snapshot wapas → agent agla step decide karta hai
```

Ye **ReAct loop** (Level 6) ka web-flavour hai: Thought → Action (browser tool) → Observation (page snapshot) → repeat. Tool-use (Level 4) + browser = web-browsing agent.

> Is session me tumhare paas **Claude-in-Chrome** aur **Claude Preview** MCP hain (Playwright jaisa kaam), par alag "Playwright" skill installed nahi hai.

---

## 13. Common pitfalls ⚠️

- `playwright install` bhoolना → "Executable doesn't exist" error. Pehle browsers download karo.
- Sync API ko `asyncio` ke andar mat chalao → crash. FastAPI me **async API** use karo.
- `time.sleep()` ki aadat chhodo → auto-waiting + `expect` use karo.
- Har test me `browser.close()` / context close karo, warna memory leak.
- CSS/XPath selectors par over-depend mat karo → `get_by_role`/`get_by_label` zyada robust.

---

## 14. Interview Q&A 🎯

**Q: Playwright vs Selenium?**
A: Playwright auto-waits on element actionability (kills flakiness), faster (CDP), built-in browser install, native async, network interception, codegen — Selenium me ye sab extra effort.

**Q: Browser vs Context vs Page?**
A: Browser = process (ek launch). Context = isolated session (apne cookies/storage, har test ke liye naya = clean state). Page = ek tab jahan actions hote hain.

**Q: Auto-waiting kya hai?**
A: Action se pehle Playwright wait karta hai jab tak element attached + visible + stable + enabled na ho. Isliye `sleep()` nahi chahiye.

**Q: Locators best practice?**
A: `get_by_role` > `get_by_label` > `get_by_test_id` > CSS > XPath. User-facing locators refactor-proof hote hain.

**Q: Tests ko fast/reliable kaise banao?**
A: `storage_state` se login reuse, parallel workers, contexts for isolation, web-first `expect` (auto-retry), network mock for flaky APIs.

---

## TL;DR

- Playwright = code se **real browser** chalao (test / scrape / automate).
- **Auto-waiting** = no `sleep`, kam flaky → Selenium ka biggest upgrade.
- **Locators**: `get_by_role`/`get_by_label` prefer karo.
- **Browser → Context → Page** mental model.
- Agentic AI me = web-browsing agent ke "haath" (Playwright MCP, accessibility-tree based, computer-use se zyada reliable for web).

➡️ Hands-on: `06_playwright_browser_automation_practical.py`
