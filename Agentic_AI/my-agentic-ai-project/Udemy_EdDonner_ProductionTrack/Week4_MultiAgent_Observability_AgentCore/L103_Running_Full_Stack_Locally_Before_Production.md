# L103 — Running Full-Stack AI Apps Locally Before Production Deployment

> **Week 4 · Day 3** · ⏱️ ~7 min

---

## 🎯 TL;DR

Deploy se pehle Alex ka front end (Next.js **pages router**, TypeScript + Tailwind, mostly AI-generated) aur API layer (ek aur boilerplate Lambda jo Aurora query karta hai) ka code dekhte hain — phir `npm install` + `scripts/run_local.py` se backend (port 8000) aur front end (port 3000) **dono locally** ek saath chala dete hain.

---

## 🗣️ Hinglish Explanation

### "Not so fast" — launch se pehle code dekho

Ed bolta hai: launch karne se pehle kam-se-kam code dekh lo — kya launch karne ja rahe ho.

### Front end ki structure

`front end` folder kholo. Pehli cheez jo dikhti hai — **`pages`** folder. Yeh clue hai ki **pages router** use ho raha hai, **app router** nahi (Next.js ke do routing systems).

**Pages router kyun, app router kyun nahi?** (Week 1 se yaad) — **Clerk**, jab **static website** ke saath use hota hai, toh use **pages router** chahiye. Clerk static export + app router ke liye abhi ready nahi.

> **Background — Next.js routing:**
> - **Pages router** (purana, `pages/` directory): har file ek route, file-based routing, mature aur stable. `_app.tsx` global wrapper hai.
> - **App router** (naya, `app/` directory): React Server Components, layouts, streaming — par static-export + kuch auth integrations ke saath edge cases hain.
> - **Static export** matlab build par pure static files banti hain (S3/CDN ke liye) — isiliye pages router safe choice yahan.

`pages` mein **`_app.tsx`** dikhta hai (familiar from Week 1) — yeh app ka global entry/wrapper hai (providers, global styles yahan wrap hote hain). App **Tailwind** + **TypeScript** par hai (Week 1 jaisa).

> **Tailwind CSS** = utility-first CSS framework (classes jaise `flex`, `p-4`, `text-lg`). **TypeScript** = typed JavaScript (compile-time safety).

### AI ne front end banaya — backend vs front end experience

Ed ek honest reflection deta hai (yeh lecture ka emotional core hai):
- **Server-side / agentic code** banate waqt Claude Code (ya Cursor agent) **frustrating** tha, "hit and miss" — Ed apna aapa kho baitha (joke: jab AI overlords aayenge toh in baaton ke liye bail karwana padega 😅)
- **Front end experience bilkul ulta** tha — code quality **excellent**, "spot on". Bas thoda fine-tuning chahiye tha (kuch janky aspects), AI ne turant pick kar liya
- **Lesson**: agar tum front-end dev nahi ho toh koi baat nahi — **Claude Code / Cursor agent front end mein fantastic kaam** karta hai. Tumhe direction aur explanation deni padti hai, par usne pages-router code khud likh diya

Front-end code Ed ne khud nahi likha — usne **brand colors** diye, **style describe** kiya, "we need pages router Next.js app" bola, baaki AI ne kiya. Recommend karta hai ki tum **structure/organization dekho** (clean, Tailwind classes, color scheme).

### Front end ki navigation aur pages

- **`pages/index.tsx`** — home screen
- Main nav ke **4 sections**: **Dashboard → Accounts → Advisor Team → Analysis**
- Ek **alag directory** ek specific account lookup ke liye — **account details page** (`document` → `accounts` ke andar)
- High-level page wahi cloud provider use karta hai (Week 1 se familiar)

Ed yeh front-end code line-by-line nahi padhayega (course UI banane ke baare mein nahi hai, aur usne khud nahi likha), par structure dekhne ko strongly recommend karta hai.

### npm install

Ab chalane ka time:

```bash
cd front end
npm install
```

Yeh saare **node modules** install karta hai — **React, Next.js, Tailwind**, aur baaki. (Ed ke liye fast, tumhare liye thoda lamba — first time download.)

> **Background — `npm install`:** `package.json` mein listed dependencies ko `node_modules/` mein download karta hai. React/Next.js JS ecosystem ke equivalents hain Python ke `pip install -r requirements.txt` ke.

### Ek aur ingredient — API layer (backend/api)

Locally chalane se pehle ek aur folder jo Ed ne ab tak mention nahi kiya: **`backend/api`**.

- Yeh ek **UV project** hai aur **ek aur Lambda** hai
- Ek chhota **Lambda handler** hai jo `main` ko run karta hai
- `main` mein **boilerplate code** hai jo alag **API routes** lookup karta hai — jaise **user details**, **accounts**
- Har route basically ek **database call** karta hai us **shared database package** ke through jo do din pehle (Day 1) dekha tha
- E.g. individual account retrieve karne ke liye route

> **Background — API handler / routes:** yeh wahi backend API Lambda hai jo pichle lecture ke diagram mein tha. Browser → API Gateway → yeh Lambda → Aurora (shared DB package). Routes REST-style endpoints hain jo UI ke liye data serve karte hain.

**AI generation experience (again)**: yeh API boilerplate banana **"fire and forget"** tha — Ed ne LM agent ko bataya kya chahiye, usne sab generate kiya, **first time hi kaam kiya**, check tak nahi karna pada. Front end + boilerplate API ke liye AI **fast aur reliable** tha; agentic/server-side logic ke liye hit-and-miss. (Yeh ek genuine engineering insight hai: **AI well-patterned boilerplate par excel karta hai, novel/complex logic par struggle**.)

### scripts/run_local.py — sab kuch locally chalao

Ab ek **root-level `scripts`** folder (pehle nahi dikhaya), jisme kuch scripts hain — ek hai **`run_local.py`**:

```bash
cd scripts        # yeh bhi ek UV project hai
uv run run_local.py
```

Yeh script:
- **backend code** start karta hai → **port 8000** par
- **front end code** start karta hai → **port 3000** par
- Configure hai taaki front end (3000) backend (8000) ko serve/call kare

> **Background — local dev setup:** dono services local machine par chal rahi hain, **Lambda ya AWS ko call kiye bina**. Front end port 3000 par, API port 8000 par; front end apni requests local API par bhejta hai. Yeh fast iteration ke liye standard local-dev pattern hai — cloud par deploy karne se pehle sab kuch local box par verify.

Sab locally running — ab hum dekh sakte hain kya ho raha hai. "Let's go and do that now."

---

## 📋 Key Concepts

| Concept | Matlab |
|---|---|
| **Pages router (Next.js)** | File-based routing (`pages/`); Clerk + static site ke liye zaroori (app router nahi) |
| **App router** | Naya Next.js routing (`app/`); static export + Clerk ke saath ready nahi |
| **`_app.tsx`** | Global app wrapper/entry (providers, global styles) |
| **Tailwind + TypeScript** | Utility-CSS + typed JS — Week 1 jaisa stack |
| **AI: front end vs backend** | AI front end/boilerplate par excellent; agentic/server logic par hit-and-miss |
| **4-section nav** | Dashboard / Accounts / Advisor Team / Analysis |
| **`npm install`** | node_modules (React, Next.js, Tailwind) install karta hai |
| **`backend/api`** | Ek aur boilerplate Lambda — API routes (user, accounts) jo Aurora query karte hain |
| **Shared database package** | Day 1 ka reusable DB-access code, API routes isse call karte hain |
| **`scripts/run_local.py`** | Backend (8000) + front end (3000) ek saath locally start karta hai |
| **Local-first dev** | Cloud/Lambda call kiye bina pura stack local par verify karna |

---

## 💼 Backend Dev Ke Liye Note

Backend dev ke liye yahan teen takeaways hain. **(1) Local-first development**: deploy se pehle pura stack local par chalao — Ed ka `run_local.py` ek **dev orchestrator** hai (jaise `docker-compose up` ya `foreman/honcho` Procfile), jo multiple services (API + UI) ek command se boot karta hai. Yeh feedback loop fast rakhta hai aur AWS bill bachata hai. **(2) Shared DB package pattern**: API routes ek **shared database package** ke through Aurora hit karte hain — yeh DRY data-access layer (repository pattern) hai, jise agents aur API dono reuse karte hain; tum bhi DB logic ko ek package mein consolidate karo, har service mein duplicate na karo. **(3) AI code-gen ki taakat aur seema**: Ed ka observation engineering-grade insight hai — **LLMs well-trodden boilerplate (CRUD API routes, standard React/Tailwind UI) par reliably first-try kaam karte hain, par novel/stateful/concurrent logic (agent orchestration) par careful review chahiye**. Code generate karwate waqt is line ko dhyan mein rakho: boilerplate fire-and-forget, complex logic verify-everything.

---

## ✅ Takeaway

- Front end **pages router** use karta hai (app router nahi) — kyunki **Clerk + static export** ko pages router chahiye
- Stack: Next.js + TypeScript + Tailwind, **mostly AI-generated** (Ed ne brand colors + style diye, baaki AI ne); 4-nav: Dashboard / Accounts / Advisor Team / Analysis
- **`backend/api`** = ek aur boilerplate Lambda jo API routes (user, accounts) ko shared DB package ke through Aurora se serve karta hai — AI ne ise **first-try** bana diya
- AI insight: **boilerplate par fast+reliable, agentic/server logic par hit-and-miss** — review accordingly
- Locally chalao: `cd front end && npm install`, phir `scripts/run_local.py` → backend **:8000** + front end **:3000** ek saath (no AWS call)

---

<details>
<summary>📜 Full Transcript (English)</summary>

Okay. Not so fast. I hear what you're saying. Before we launch it, we should at least look at the code for a second. We should at least see what is it that we're going to be launching. So let's just take a quick look in front end. So you'll notice right away the word pages there, which is your clue that we are using the pages router, not the app router. You remember those two different ones. And the reason we're using pages is because, again, I don't know if you remember from week one that I discovered that Clark, when you're using it with a static website, needs to use the pages router. It's not ready for the router. So we look in pages. You may remember the familiar underscore app TSX. Uh, and we've got a bunch of things going on here. And you can take a look through this code. Again. It's going to be a tailwind app. It's again TypeScript version just like we had in week one. And whilst this isn't a course about building user interfaces, you can look through some of this. But this is what I will tell you. You remember I said that I had the experience with Claude code in yesterday building the agents, which was pretty frustrating and I lost my temper a little bit. Sorry. You got to worry. When. When, uh, when the overlords take over? Uh, when when when when Claude rules the roost. Uh, I hope it's not able to look back and see some of the things I said to it, because I'm going to be in big trouble. You guys are gonna have to bail me out. You tell tell tell her that it's not what I'm normally like. Anyway, uh, the Claude code experience with the server side code was, was was, uh, hit and miss, and I got very frustrated. The front end experience was extremely different. And maybe it's because I'm a terrible front end developer, but. But I don't think so. Uh, generally speaking, the code quality was excellent, and it was just it was just spot on with the back end. It would make mistake after mistake with the front end. It built really quickly and I only need to give it some fine tuning around, changes I wanted to make or some some aspects of the page that seemed a bit janky. Uh, and it picked it up really quickly. So one thing I will say to you, if you're not a front end developer, then it's not a problem because cloud code can do a really fantastic job. Or the cursor agent. Anytime I say cloud code, the cursor agent can can can achieve the same thing. So you still have to give it direction. You still have to explain. But I didn't have to describe how to do the pages like the the code that you'll see in here from, from obviously this is the, the high level one which uses the same cloud provider you remember from before. Um, and but if we go into, uh, document and then into, say accounts, you'll see all of this here. It's very nicely done. It's, it's, uh, extremely clean. It's using all of the tailwind classes. It's using a color scheme that I laid out. I gave it the brand colors to use. I described the style, um, and it's built each of these different sections. And as I say, I'm not I'm not planning to go through this front end code with you, especially as I didn't write it. Uh, but I do recommend you at least look at how it's structured and organized to give you these these cues. And bear in mind that I'm a horrible front end developer. I didn't write any of this. I finessed it from, uh, in a very small way. This was largely Lem generated, and it just shows you what you're able to achieve. So this is all in pages, and there's also a separate directory for looking up a particular account. This is the account details page. Um, and you'll also see you'll see the different the main nav which is going to be dashboard and then accounts and then advisor team and then analysis. Those are going to be the four main navigations that you will see. Uh, and uh, like in the index page is the, the uh, the home screen. Uh, so as I say, all created by doing, uh, some interactions with AI agents to generate this, but but I gave it a color scheme. I said, we need the pages, router, Next.js app. Uh, it did the rest. Okay. that's enough. Intro. It's time now for us to run the good old, uh, npm install and get this running. Okay, so here we go. I'm bringing up a new screen here. I'm going to CD into front end. Front end I'm excited. Jittery. All right. So now we're going to type npm install which for me will be very quick. But for you will take longer. This is when it installs all the node modules associated with this project which is going to include react, Next.js, tailwind and others. So that might take a minute or two. Now we're about to kick everything off and to look at it locally. There's one more ingredient. There's one more thing I haven't talked about yet. You know what that is? It's the API. It's one more folder in back end that I haven't even mentioned. If you look in back end, you'll see there is another folder called API. And if you open that up you'll see this is a UV project and it is just another lambda. It's got a lambda handler which is rather small that involves running main Maine and Maine. If you look through this, you'll see that this is some pretty boilerplate code that looks up different API routes for things like the user details and, uh, accounts. And in each of them, it's basically making a database call through that shared through the database package that we looked at two days ago. Um, and this is to retrieve an individual account. So it's a series of API routes to get to each of these. And I'll say that my experience with this was quite similar to the front end generating this kind of boilerplate code to match our database model. This was a fire. And forget I said to the LM agent what I wanted. It generated all this and it just worked. First time I knew exactly what I wanted, I didn't have to check this at all. It worked. So it's another example. When it came to building the Agentic code yesterday, uh, the Claude was was was not so good. It was hit and miss. But for this stuff, for more boilerplate code, it was super impressive, fast and reliable. And it worked first time. Okay, so with this in mind, you've now seen the API layer. What we're now going to do is, uh, go to a new folder that I haven't shown you before, a new root level folder called scripts. And inside this folder are a few scripts. And one of them is called run py. And we're going to go and run that right now. So I'm going to go into scripts which is a UV project. So we can just do a UV run. And I'm going to do UV run run run local py. And what that's going to do is it's going to start the backend code, and it's also going to start the front end code as well. And this is all now running. We've got a backend running on port 8000 and we've got a front end running on port 3000. And it's configured so that that will, will will serve the 8000. So it's all running locally on my box. And this is how without calling out to Lambda or anything like that we can see some of what's going on. So let's go and do that now.

</details>
