# L12 — Building Your First FastAPI Backend for Production LLM Deployment

> **Week 1 · Day 2** · ⏱️ ~9 min

---

## 🎯 TL;DR

`sass` project ko Cursor mein kholkar Next.js ki built-in `pages/api/` (JS backend) hatate hain, phir top-level **`api/` folder** + **`requirements.txt`** (fastapi, uvicorn, openai) banate hain. Andar **`api/index.py`** likhte hain — ek FastAPI `/api` route jo OpenAI (GPT-5 nano) se ek business idea generate karke return karta hai. Aaj ka **only AI code** yahi hai.

---

## 🗣️ Hinglish Explanation

### Step: `sass` project ko kholna

1. Cursor → **File → New Window** → **Open Project** → `projects/sass` → **Open**
2. Naya `sass` project khulta hai. Structure:
   - **`pages/`** directory — kyunki hum Pages Router use kar rahe hain
   - **`public/`** — static assets (images etc.)
   - **`styles/`** — CSS files
   - Bunch of **config files** (`package.json`, `tsconfig.json`, `tailwind.config`, etc.)
3. Terminal kholo (`Ctrl + ` `). AI chat band kar do (chaaho toh rakho).

Yeh `sass` project poore week ka **naya ghar** hoga.

### Convenience: instructions copy karna (optional)

`production` project ek dusre window mein hai (recipe wahan hai). Do windows ke bich flip karna awkward ho sakta hai, toh Ed `production/week1/` ki saari markdown files ko `sass` ke andar ek naye **`week1`** folder mein copy kar leta hai. Yeh **zaroori nahi** — tum dusre window se refer kar sakte ho, ya File Explorer/Finder se folder copy kar sakte ho. Ed terminal se Mac command chalata hai (ek directory upar → `production/week1` → saari files copy → local `week1`). Sirf convenience ke liye, taaki windows switch na karne pade.

Phir `day2` ka **Open Preview** wapas kholta hai. Hum abhi bhi **Step 1** (Next.js project create) mein hain, jo ho chuka — `pages/` subdirectory dikh rahi hai jaise instructions kehti hain.

### `pages/` ke andar kya hai

`pages/` directory mein:

- **`_app.tsx`** — app-level wrapper (TSX = TypeScript + HTML hybrid)
- **`_document.tsx`** — overall page document structure
- **`index.tsx`** — home page (root par serve hota hai)
- Aur ek **`api/`** folder jisme **`hello.ts`** hai

> **`pages/api/` kya hai (background):** Next.js ka apna built-in feature — agar tum chaho ki **Next.js khud tumhara backend** ho (JavaScript API routes), toh code yahan jaata hai. `hello.ts` ek sample endpoint hai.

#### `pages/api/hello.ts` ko delete karna

Hum **JavaScript backend nahi** chahte — hamara backend **Python FastAPI** hoga. Toh yeh `pages/api/` folder hamare liye "waste of space" hai. Ise delete karo:

- `pages/api` par **right-click → Delete** → confirm **Yes**

### Tailwind ka thoda aur intro

**Tailwind** ek **CSS framework** hai. Purane din mein bahut saari styling khud likhni padti thi — tum achhe ho jaate ho par styling "a strange dark art" hai (frontend log jaante hain). Tailwind ek **canned set of styles** deta hai jinke naam easy-to-understand descriptions hote hain (jaise `text-2xl`, `bg-blue-500`, `p-4`). Tum bas mimic/copy-paste karte ho jo styles pasand hain — styling ekdum easy ho jaati hai.

### Step 2: Backend structure banana

Ed warning deta hai: baaki Week 1 aur Week 2 mostly aisa hi rahega — instructions follow karna, cheezein set up karna, code paste karna. "The whole thing is environment set up because that's what production deployment is all about." Is mode ki aadat ho jaayegi.

#### 1. Top-level `api/` folder

`pages/api` (jo abhi delete kiya) ke **andar** wala folder tha. Ab hum **project root** (`sass/`) mein ek **naya top-level `api/` folder** banayenge:

- Project root area mein khaali jagah par **right-click → New Folder** → naam **`api`**

Yeh root-level folder hai — Vercel iss convention ko pehchaanta hai (aage clear hoga).

#### 2. Top-level `requirements.txt`

Project root mein ek **file** (folder nahi) banao — exactly **`requirements.txt`**:

```
fastapi
uvicorn
openai
```

> **requirements.txt kya hai (background):** Yeh Python package dependencies list karta hai; deploy/install time par inhe automatically `pip install` kiya jaata hai.

Teen packages:
- **fastapi** — backend framework
- **uvicorn** — ASGI web server jo FastAPI app ko serve karta hai
- **openai** — OpenAI Python client library (LLM call karne ke liye)

> ⚠️ Ed bar-bar bolta hai: **kai cheezein exactly waise hi honi chahiye jaise woh kehta hai**, warna "something is going to go bump." Folder naam `api`, file naam exactly `index.py` — yeh Vercel ke auto-detection ke liye critical hain.

### Step 3: `api/index.py` — pehla FastAPI backend

`api/` folder ke andar ek **naya file** banao — **exactly `index.py`** (yeh naam exact hona zaroori hai). Andar yeh code paste karo:

```python
from fastapi import FastAPI
from openai import OpenAI

app = FastAPI()


@app.get("/api", response_class=PlainTextResponse)
def generate_idea():
    openai = OpenAI()
    prompt = "Come up with a new business idea for AI Agents"
    messages = [{"role": "user", "content": prompt}]
    response = openai.chat.completions.create(
        model="gpt-5-nano",
        messages=messages,
    )
    return response.choices[0].message.content
```

> Note: `PlainTextResponse` ke liye import bhi chahiye — `from fastapi.responses import PlainTextResponse`. (Transcript mein Ed paste karta hai; exact instructions repo ki day2 file mein hain.)

#### Line-by-line breakdown

1. **`app = FastAPI()`** — naya FastAPI application object instantiate karte hain (saari routes hold karta hai).
2. **`@app.get("/api", response_class=PlainTextResponse)`** — yeh decorator FastAPI ko batata hai: jab koi **GET request** is app ke `/api` path par aaye, toh neeche wala Python function call karo. `response_class=PlainTextResponse` matlab response **plain text** type ka hoga (JSON nahi). Yahi FastAPI mein backend routes describe karne ka tareeka hai — request aati hai, woh path match hota hai, function chalta hai, jo return hota hai woh response ban jaata hai.
3. **AI code (aaj ka only AI code — "milk this, enjoy"):**
   - **`OpenAI()`** — OpenAI Python client ka naya instance. Yeh ek simple wrapper hai jo backend par actual web call (HTTPS request to OpenAI API) karta hai.
   - **`prompt`** — ek user message: *"Come up with a new business idea for AI Agents."* (Ise change kar sakte ho — be creative.)
   - **`chat.completions.create(...)`** — familiar OpenAI API call:
     - **`model="gpt-5-nano"`** — GPT-5 ka **nano** (ultra-cheap) variant. Har call extremely cheap padti hai.
     - **`messages`** — prompt pass karte hain
   - **`return response.choices[0].message.content`** — OpenAI se response nikaalne ka standard way (`choices[0]` → pehla completion → `.message.content` → actual text).

#### OpenAI nahi use karna chahte?

OpenAI ka **$5 upfront** payment har koi nahi karna chahta (per-call cost minimal hai, par initial $5 hai). Alternatives `guides/` mein hain:
- **Gemini** — abhi free plan hai (future mein change ho sakta hai)
- **OpenRouter** — bahut saare free models
- Aur bhi local/different options

> **Recap:** Hamara backend route `/api` par hai, `api/index.py` mein described, ek LLM ko call karta hai aur result (with the prompt) return karta hai. Yahi backend hai jise agle lecture mein frontend (`index.tsx`) `fetch` karega.

---

## 📋 Key Concepts

| Concept | Matlab |
|---|---|
| **`pages/`** | Pages Router ka core folder (`_app.tsx`, `_document.tsx`, `index.tsx`) |
| **`pages/api/` (delete)** | Next.js ka built-in JS backend — hum Python use kar rahe, isliye hata do |
| **Top-level `api/` folder** | Project root mein naya folder for Python backend (Vercel convention) |
| **`requirements.txt`** | Python deps — `fastapi`, `uvicorn`, `openai`; `pip install` isse hota hai |
| **`api/index.py`** | FastAPI backend file — naam **exactly** `index.py` (Vercel detect karta hai) |
| **`@app.get("/api")`** | Decorator — GET request `/api` par yeh function chalega |
| **`PlainTextResponse`** | Response plain text type ka (JSON nahi) |
| **`OpenAI()` client** | OpenAI Python wrapper — backend se LLM API call |
| **`gpt-5-nano`** | GPT-5 ka ultra-cheap variant; per-call cost minimal |
| **`response.choices[0].message.content`** | OpenAI se text response nikaalne ka standard tareeka |
| **Tailwind** | Canned CSS utility classes — easy descriptive styling |
| **LLM alternatives** | Gemini (free plan), OpenRouter (free models) — guides mein |

---

## 💼 Backend Dev Ke Liye Note

Yeh tumhare comfort zone ka core hai — ek FastAPI route, ek external API client, ek response. Production lens se do cheezein note karo. **Pehla: naming-as-contract.** `api/index.py` aur top-level `api/` folder koi random choice nahi — yeh **Vercel ka filesystem convention** hai (jaise AWS Lambda handler `lambda_function.lambda_handler` expect karta hai). Production platforms structure se behavior infer karte hain, isliye exact naming critical hai. **Doosra: provider abstraction.** Ed ne OpenAI client hardcode kiya hai, par alternatives (Gemini/OpenRouter) ka mention production thinking hai — real systems mein tum LLM client ko ek **interface/adapter** ke peeche rakhoge taaki provider swap ek config change ho (yeh exactly Week 2 Day 3 mein OpenAI→Bedrock migration ka theme hai). Abhi `OpenAI()` env var `OPENAI_API_KEY` se key uthata hai — **secrets code mein hardcode mat karna** (agle lecture mein `vercel env add` se inject hoga). Aur `requirements.txt` mein pinning nahi hai (no `==versions`) — prototype ke liye theek, par production mein **version-pin** karo reproducible builds ke liye. `response_class=PlainTextResponse` ek choti par real production detail hai: tum response content-type ko explicitly control kar rahe ho, default JSON wrapping skip karke — frontend ka `fetch` raw text expect karta hai.

---

## ✅ Takeaway

- `sass` project mein **`pages/api/hello.ts` delete** karo (no JS backend), phir **top-level `api/` folder** + **`requirements.txt`** (fastapi, uvicorn, openai) banao
- Backend file **exactly `api/index.py`** — naam exact hona Vercel auto-detection ke liye **critical**
- Route: `@app.get("/api")` → OpenAI `gpt-5-nano` ko prompt bhejta hai → `response.choices[0].message.content` return karta hai (plain text)
- Yeh **aaj ka only AI code** hai — baaki sab deployment/setup hai
- OpenAI ka $5 upfront na chahiye toh **Gemini/OpenRouter** alternatives `guides/` mein

---

<details>
<summary>📜 Full Transcript (English)</summary>

And so now I'm going to go in cursor to file and new window. And up it comes. And I go to open project I go into my projects directory. There is sass, I press open and here is our new Sass project. Let me make this bigger for you. Let's look at our pride and joy. Um, so we've got a directory called pages because we're using the pages router got a directory called Public Style and then a bunch of different, uh, configuration files. So these this is going to be our new home for the rest of this week. I'm going to start by bringing up a terminal like that with control and backtick. If you remember that I also closed down like an AI thing that was here. You can keep it and ask it questions as you wish. Now before we go on. So so we've got this other project, uh, called production, which I have running in another window, and that's got our recipe for what we're going to do today. And you can click between the two. But that might be a bit awkward. So I'm actually going to copy across all of the the files for the markdown files for the instructions for what we're going to do this week. You don't need to do this. You can just refer back to the other window. You can also just bring up a File Explorer, just a Windows Explorer or Mac Finder, and just copy in the folder as you wish. This is only for convenience, but I'm going to create a new folder. I'm going to call it week one. And here I'm going to do this. This is now like a mac command. And as I say you can just do this through the user interface. You don't need to do it through a command up a directory. Go to production and go to week one and take all those files and copy them into the week one folder that I've got right here. And that's happened. And now when I go here, you'll see that we've got all of these files. And I just do this for convenience so we don't have to flip between the two different windows. You can do this as you wish, but I'm now going to open the preview of day two. I'll close this screen here for now. And we are back here. We're still in step one, creating your Next.js project. Uh, but. And we've now just opened the project, and you can now see a little description of what we've got here. We have indeed got the, uh, the, the pages subdirectory, just as it's described here. And within this we have an underscore app dot TSX. Remember I said that the TSX these are the special files which kind of combine TypeScript and HTML into one type of file. And we've got a document TSX, uh, an index TSX. And then we've uh, we've got various other things. Okay. Uh, and there's also this API folder here with hello TS as well. But we are going to be removing this just as it tells you. All right. So as it says we're going to be using a Python backend. We're not going to be using next for our backend. Not going to be using a JavaScript backend. So this API folder, which is designed if you wanted next to be your backend, this is this is a waste of space. We want to get rid of this. So right click here and delete. And it's going to say are you sure you want to. And I say yes and off it goes. We've got rid of that file. Great. Then just just a bit of a more introduction on tailwind. Just because I didn't talk about it earlier. It is a CSS framework. In the old days we used to have to write lots of this styling. You get very good at writing styling, but it's a strange dark art getting styling right as your front end people know only too well. Um, but tailwind gives you this sort of canned set of styles that you can use with all sorts of of very easy to understand descriptions of what each one means. Here's some examples. You're going to get used to this. It's something to just just mimic, copy and paste the styles that you like. You're going to see how easy this makes styling. All right, onwards. Let's get to step two. So I should say the rest of this is going to be similar for all of weeks one and two. We're going to basically be following instructions and setting things up and pasting in code, which is a slightly weird. It's like the whole thing is environment set up because that's what production deployment is all about. It's basically set up. So you're going to get kind of used to this mode of working. Uh, but but you'll see what I mean. Now the first thing we want to do is we want to create a new folder called API. And you might say we just deleted a folder called API. We deleted a folder called API that was inside pages. Instead we're going to make a folder by right click in this area here and go new folder. It's going to be called API here. It's created at the top here. And it is a top level folder. It's a it's in the project root directory in sass called API. And within that uh sorry not not yet within that we're going to put things in there in a minute. First another top level file. And this one is going to be a file, not a folder. And it's called requirements dot txt which I need to spell properly. Requirements dot txt and you will know this well as being the file which lists Python packages that need to get pip installed automatically. Uh, and in fact you probably saw we've got three packages to take. We've got fast API, Uvicorn and open AI. There they are. We're installing the them um, and looking forward to using fast API. Okay. So within this API folder that I told you, I promised you we were going to populate it. We are now we're going to make a new file called index dot. And it needs to be called exactly index dot pi. There's many things in this set of instructions that need to be exactly as I say them. Or something is going to go bump, uh, and this is really one of them. So I'm going to take this copy it and I'm going to make a new file new file index dot pi. And just you see the way this file is in the API directory. If I click that swizzle there you'll see how it comes and goes. And I click here and I paste in this text. All right. So what is this doing. Okay. So this is fast API code. Uh and you start by by creating an app called uh instantiating a new object fast API. And this is the way in fast API you describe the different backend routes. When when something comes to you, uh, comes to to the web address that this app is running. If it goes to slash API, then this Python function is going to get called. And whatever this comes up with is going to be returned in the response. And we're describing it here. We're telling it it's going to be a plain text type of response okay. And so what is this function actually going to do. Well here comes some AI code. And side note this is going to be the only AI code we're going to do today. So so so milk this, enjoy some AI code. Everything else is about deployment. Uh, so we're going to this is going to be very familiar to everyone who's used OpenAI's API. We're going to create a new instance of the OpenAI Python client library again. So this is something which is a simple wrapper around making a web call itself. On the back end. We're going to have a prompt. It's going to be a user message. The content will be come up with a new business idea for AI agents. And this is going to be what our app is going to do to start with until they fall. And feel free to change this. As you wish. Uh, be creative. Come up with a more interesting thing than this if you wish, or come back and do it later. Remember this point. And then this is the only two familiar OpenAI API responses client completions dot create. We pass in the name of the model, we'll use the nano, the ultra cheap variant of GPT five. We pass in our prompt and we return response dot choices zero. Let me actually type this out. So I'm doing some work with response dot choices, zero dot message content, which is the way that we get back the response from OpenAI. Now if you're using if you don't want to use OpenAI, you don't perhaps like that $5 upfront payment. This will only this will cost such a tiny amount each call. But there is that $5 upfront. You can of course use any of the alternatives that are in the guides. Gemini at the moment has a free plan. I don't know if it still still will do when you when you hear this, but obviously Open Router has lots of free models and you can run, uh, things, uh, lots of different options in the guides. Uh, so this then is our back end route at slash API described in index dot pi. It makes a call to an LLM and it returns the results and the prompt it sends the LLM.

</details>
