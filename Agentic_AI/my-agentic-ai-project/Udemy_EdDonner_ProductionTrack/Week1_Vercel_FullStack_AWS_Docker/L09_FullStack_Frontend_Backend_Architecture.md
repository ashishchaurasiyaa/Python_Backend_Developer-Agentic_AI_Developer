# L09 — Building Full-Stack AI Apps: Frontend-Backend Architecture for LLMs

> **Week 1 · Day 2** · ⏱️ ~8 min

---

## 🎯 TL;DR

Day 2 ka conceptual foundation: **frontend vs backend** kya hain, woh aapas mein API calls (JSON ya full-page) se kaise baat karte hain, Gradio kahan fit hota hai, aur frontend tech ka **3-tier evolution** — vanilla HTML/CSS/JS+jQuery → JavaScript frameworks (React/Vue/Angular/Svelte, SPA, JS vs TypeScript) → application frameworks (**Next.js**, jo hum use karenge).

---

## 🗣️ Hinglish Explanation

Day 1 ek "marathon" tha — agar tum abhi tak ho, toh Day 2 mein swagat. Aaj **frontend + backend** ko jodkar ek **full-stack application** banane ki theory hai. Ed honestly bolta hai: hum frontend ki *surface bhi scratch nahi* karenge — bas itna ki **intuition** ban jaaye. Agar code samajh na aaye toh **LLM se explain karwao** (woh frontend code generate aur explain dono mein amazing hain).

### Frontend vs Backend — definitions

**Frontend** = woh code jo **user ke browser mein chalta hai**. Teen cheezon ka combination:

- **HTML** → page ki **structure** (kya content hai, kahan hai)
- **CSS** → page ka **appearance** (stylesheets — color, layout, fonts)
- **JavaScript** → page ki **interactivity** (button click par kya ho, animations, dynamic behavior)

**Backend** = **server par chalne wali business logic**. Isme aata hai:

- **Database access** (data padhna/likhna)
- **LLMs ko call karna**
- Doosre **APIs** call karna
- **Secrets store** karna (API keys, jo browser mein kabhi nahi honi chahiye)

### Frontend-Backend kaise baat karte hain (2 patterns)

Typical web app mein frontend aur backend hote hain, aur do tareekon se communicate karte hain:

**Pattern 1 — API call returning JSON (most common):**

1. Frontend ek specific **URL** hit karta hai — isse **web endpoint** kehte hain.
2. Us URL par backend code chalta hai.
3. Backend kuch content generate karta hai aur frontend ko **JSON object** ke roop mein wapas bhejta hai.
4. Frontend us JSON ko collect karke **UI mein changes** karta hai (DOM update).

```
Browser (frontend)  ──GET /api/message──▶  Server (backend)
                    ◀──{ "reply": "..." }──   (JSON response)
   │
   └─▶ JS reads JSON → updates the page
```

**Pattern 2 — backend serves a full web page:**

1. Frontend ek URL call karta hai (e.g. home page).
2. Server **poora HTML page** (frontend code) generate karke browser ko bhej deta hai.

> Hum is course ki labs mein **dono patterns** use karenge.

> **Background — yeh do patterns kya hain.** Pattern 1 = **client-side rendering / SPA + API**: browser pehle se loaded hai, sirf data (JSON) fetch karta hai. Pattern 2 = **server-side rendering (SSR)**: server har request par taiyaar HTML bhejta hai. Next.js (jo hum use karenge) dono kar sakta hai — yahi uski khaasiyat hai.

### Gradio kahan fit hota hai?

Agar tumne Ed ke doosre courses kiye hain toh **Gradio** se familiar hoge — Python se quick, achchi-dikhne wali UIs banane ka tool. Toh Gradio frontend hai ya backend?

**Jawab:** Gradio ek **backend framework** hai — par confusingly, woh **frontend code generate bhi kar deta hai** (behind the scenes). Tum Python mein UI *describe* karte ho, aur Gradio serving ke waqt frontend khud bana deta hai. Isiliye Gradio "frontend + backend in one" lagta hai — backend code hi frontend produce karta hai.

> **Is course mein Gradio nahi use karenge** — kyunki yahan hum *"for reals"* kaam kar rahe hain: real, separate **frontends aur backends** banayenge (production-style).

### Frontend tech ki 3-tier evolution

Ed frontend technologies ka historical progression batata hai — teen tiers:

#### Tier 1 — Vanilla HTML/CSS/JS (+ jQuery)

Shuruaat mein sab **vanilla HTML pages** likhte the:

- Basic **HTML** se page describe karo
- Apni **CSS** likho styling ke liye
- **JavaScript** se interactivity — aksar **jQuery** jaisi lightweight library use hoti thi (raw JS ko simplify karne ke liye)

Is level par tum kaafi **DOM** ke saath khelte ho.

> **DOM = Document Object Model.** Yeh browser mein render ho rahe web page ka ek **in-memory tree model** hai. JavaScript se tum DOM mein navigate karke ek button dhoondh sakte ho, uska color badal sakte ho, etc. DOM = "page abhi screen par kaisa dikhta hai" ka programmatic representation.

*(Aaj bhi kuch log vanilla likhte hain — isme ek satisfying simplicity hai.)*

#### Tier 2 — JavaScript frontend frameworks

Phir aaye **JS frameworks** — ek **abstraction layer** taaki sophisticated pages **tezi se aur reusable** tareeke se banein. Inka "zoo" hai:

- **React** (by far most popular) — *"I'm sure you've heard of"*
- **Vue**, **Angular**, **Svelte**, aur bahut saare

Ye sab **reusable components** se UIs banane ke baare mein hain — components ko plug-and-play karke complex UIs jaldi bante hain.

**SPA = Single Page Application:** React jaise frameworks mein aksar tum ek SPA banate ho. Matlab — bhale user ko lage woh "alag-alag pages" par click kar raha hai, asal mein **poora app ek hi baar load hota hai** (jab pehla URL hit hota hai). Uske baad clicking par browser sirf **server ko API calls** karta hai; effectively wahi same web page chalti rehti hai, bas alag-alag dikhti hai. Yahi "SPA" ka matlab hai.

**JS vs TypeScript flavors:** React (aur baaki) do flavors mein aate hain:

- **JavaScript** variant (original)
- **TypeScript** variant (modern) — TypeScript JavaScript ki **strongly-typed sister language** hai.

> **Background — TypeScript kya hai.** TypeScript = JavaScript + **static types**. Compile-time par type errors pakadta hai (jaise Python type hints + mypy, par enforced). Bade frontend codebases mein bugs kam karne ke liye standard ban gaya hai. *(Confusion ho toh ChatGPT se poocho — Ed bolta hai woh "brilliantly" explain karega.)*

#### Tier 3 — Application frameworks (Next.js) — jo hum use karenge

Aakhri (sabse modern) tier: **application frameworks** jaise **Next.js**.

**Kyun zaroorat padi?** React **super flexible par bare-bones** hai. Woh khud bahut kuch nahi deta — jaise:

- Form **validation** ka code
- **Routing** (app ke alag sections ke beech navigation)
- **Data fetching**

React ka assumption hai ki tum khud apne frameworks chun-chun ke jodoge. Yeh flexibility achchi hai, par isse **bahut saare options** ban jaate hain — log React apps **alag-alag tareekon** se banate hain.

**Next.js** = React ke **upar bana ek higher-level framework** jo bahut saare useful frameworks ko **bundle** kar deta hai, taaki tumhe har baar alag decisions na lene padein. Bas Next use karo aur chal pado. Ismein built-in:

- **Routing**
- **Data fetching**
- **Server-side rendering (SSR)** — *"we'll talk more about later"*
- Aur bahut saare tools

Yeh **bahut quick to get started** hai. Yahi **Next.js** hai — aur isi ke saath modern frontend development ka **3-tier narrative** (vanilla → JS frameworks → app frameworks) complete hota hai.

---

## 📋 Key Concepts

| Concept | Matlab |
|---|---|
| **Frontend** | Browser mein chalne wala code: HTML (structure) + CSS (appearance) + JS (interactivity) |
| **Backend** | Server-side business logic: DB, LLM calls, other APIs, secrets |
| **Web endpoint** | Woh URL jise frontend hit karta hai backend code chalane ke liye |
| **JSON response pattern** | Backend JSON return karta hai → frontend UI update karta hai (SPA-style) |
| **Full-page pattern** | Backend poora HTML page generate karke bhejta hai (SSR-style) |
| **Gradio** | Backend framework jo frontend bhi generate karta hai — is course mein nahi use hoga |
| **DOM** | Document Object Model — browser ke rendered page ka in-memory tree, JS isse manipulate karta hai |
| **jQuery** | Lightweight JS library jo raw JavaScript ko simplify karti hai (Tier 1) |
| **React / Vue / Angular / Svelte** | JS frontend frameworks — reusable components (Tier 2); React most popular |
| **SPA** | Single Page Application — poora app ek baar load, phir API calls; ek hi page redraw hoti hai |
| **TypeScript** | JavaScript ka strongly-typed variant (compile-time type checking) |
| **Next.js** | React ke upar application framework — routing + data fetching + SSR bundled (Tier 3); hum yahi use karenge |
| **SSR** | Server-side rendering — server taiyaar HTML bhejta hai |

---

## 💼 Backend Dev Ke Liye Note

Python backend dev ke liye yeh lecture frontend ki *mental map* deta hai — tum FastAPI se backend banana jaante ho, ab samjho ki frontend ek **alag deployable** hai jo tumhare endpoints se JSON khaata hai. "Endpoint returns JSON" wala pattern bilkul wahi hai jo tum FastAPI mein `@app.get("/api/...")` se banate ho — frontend bas uska consumer hai. Architecture decision jo aage matter karega: **JSON API (CSR/SPA) vs server-rendered (SSR)** — yeh CORS, auth (cookies vs tokens), caching, aur SEO ko affect karta hai. Next.js yahan interesting isliye hai ki uske paas **apne server-side routes** (API routes / server components) hote hain, toh question banta hai: kaunsa logic Next ke backend mein jaaye aur kaunsa tumhare FastAPI/Lambda backend mein? Is course ka stack (Next.js frontend + FastAPI/Lambda backend) ek classic **decoupled full-stack** architecture hai — frontend ko CDN/Vercel par, backend ko Lambda/App Runner par alag deploy/scale karna. Gradio wala point bhi note karo: Gradio prototyping ke liye great hai par production frontend control nahi deta — isliye Ed isse drop kar raha hai.

---

## ✅ Takeaway

- **Frontend** = browser code (HTML + CSS + JS); **Backend** = server logic (DB, LLM calls, APIs, secrets)
- Frontend↔backend do tarah se baat karte hain: **JSON API call** (SPA-style) aur **full HTML page serve** (SSR-style) — dono labs mein aayenge
- **Gradio** = backend framework jo frontend bhi banata hai; *is course mein nahi* (hum real separate frontend/backend banayenge)
- Frontend evolution 3 tiers: **vanilla HTML/CSS/JS+jQuery (DOM)** → **JS frameworks (React/Vue/Angular/Svelte, SPA, JS vs TypeScript)** → **app frameworks (Next.js)**
- **Next.js** = React ke upar, routing + data fetching + SSR bundled — quick start, aur yahi hum use karenge

---

<details>
<summary>📜 Full Transcript (English)</summary>

Well, if you're still here, that means you haven't been completely put off by day one, which was quite a marathon day. And you're here back for day two of Genii and Agentic AI in production. So what do I have in store for you today? We're going to be talking about the front end and the back end, putting them together to make a full stack application. And I gotta tell you, we are hardly going to scrape the surface of what it takes to write a front end. I imagine some of you are actually front end engineers on this course, looking to get more well rounded. And for you, the next few slides are going to be kind of easy for some of you. You might be completely new to front end engineering. I'm just going to cover the basics to give you a framework, to give you the intuition for what it is that goes on when you build the front end side of a web application. I'm going to ask you to review the code to look at what I'm doing, get an LLM to explain it if you don't understand it. They're also amazing at generating front end code. Use this to give you the foundation of what's going on. When you build a front end and a back end to work together. And just to start with some definitions. So obviously when we say front end, we're referring to the code that runs in the user's browser, a combination of HTML for the structure of the page, CSS, the stylesheets for the appearance of the page, and then JavaScript which is used, for example, for what happens when a button is clicked, or for making animations move. It's the interactivity of the page, and then the back end is the business logic running on the server. It includes database access, calling LMS, potentially calling other APIs, storing your secrets and the like. And so your typical web application, of course has a front end and a back end. The front end makes API calls to the back end by hitting a particular URL, which we call a web endpoint, hits that URL that calls the backend code. The backend generates some content, and it returns it to the front end, typically in the form of a JSON object, and the front end collects that JSON object and uses that to make some changes to the UI. There is another way. The back end is sometimes called, which is that it can be called to to create an entire web page, to serve up a whole web page to the front end. So the front end might call my home page. And when when that that URL is called, the server generates the entire home page front end code and passes that back to the browser. So that's a second way that servers back end code is used. And we'll be doing both of them in our labs. And now you may be wondering how does Gradio fit into this? If you've taken my other courses, you'll know that I'm a huge fan of Gradio. I use it a lot to build quick UIs that look great, uh, in my opinion. And you might be wondering, okay, so so where does the front end back end of gradio? Well, here's the answer. So Gradio is a back end framework, but confusingly, Gradio is able to generate front end code, and that's kind of kept kept behind the scenes for us. We write, we describe a UI with Python, and Gradio generates the front end for us when it's serving up that user interface. So that's why when you're using Gradio, it's a kind of front end, back end in one, because the back end code is able to generate the front end code. We won't be using Gradio in this course because we're doing stuff for reals. We're going to be building real front ends and back ends. So I just want to talk about the progression of different technologies that have happened over time. When it comes when it comes to front end code, the front end landscape, it started off some time ago that we would all be writing vanilla HTML web pages, and still some people do. There's something very satisfying about doing this, but this is where you just have basic HTML code to describe a web page. You write your own CSS to do the styling, and you have JavaScript. And typically people use lightweight, low level frameworks, libraries like like jQuery. That just simplifies some of the stuff that you have to write with JavaScript. And a lot of what you're doing when you write JavaScript at this level is playing around with something called the Dom stands for Document Object Model, and this is the kind of JavaScript model that represents the web page that's being rendered in the browser, so that you can do things like navigate around in the code to find a button, and then do something like change its color or with JavaScript code so that that model of what the web page looks like in the browser's screen is known as the Dom. And next came the JavaScript front end frameworks, an abstraction layer to make it quicker and more reusable to build sophisticated web pages. And there's a zoo of these frameworks. The most popular by far is react that I'm sure you've heard of. There's also Vue and Angular and Svelte. And there's a bunch of others, and they're all about building UIs from reusable components that you can kind of plug and play together so that you can construct quite sophisticated UIs quite quickly. And most of the time when you're working with a framework like react, you're building what's known as a single page application spa. And that's referring to the fact that typically, even though as a user, it feels like you're clicking around lots of different web pages, the whole of that react application, as it's called, all of the the content, the front end code behind it is loaded up once when you first hit the first URL, and then from that point onwards, when you're clicking around the application, you're typically making a series of API calls to the server, but it's all running effectively the same web page, even though it appears to redraw itself in different ways and it feels like you're navigating around, it's all just the same client code that's running there. The react application. And so that's that's what Spa means. And you do hear that a lot. Now react and the others come in two flavors. There's a JavaScript flavor a JavaScript variant which which it began with. And then there's a more modern TypeScript variant which is react using the language TypeScript, the sister language to JavaScript, which is a strongly typed version of JavaScript. And if you're not sure what that means, then then ask ChatGPT. It will explain it brilliantly. All right. And the final step in this progression is to explain the application frameworks which which came next and which are the the most recent part of this story. And they are things like Next.js, which is what we will be using. Uh, and this is really because when you're using something like react, react is super flexible and it's quite bare bones. It doesn't come with a lot of the stuff, like the code to to handle validations of forms on a web page, and the code to do things like routing between different sections of your app. And the assumption is if you're using react, that you pick and choose which framework you want to add together. And that's that's really that's great. It means you can have a lot of flexibility in what kind of app you want to build, but it also means there's a lot of different options. And people have built react apps in lots of different ways. And next is an example of a higher level framework built on top of react that bundles together a bunch of useful frameworks so that you don't need to make lots of different decisions. You can just use next and go. So it has routing and data fetching. It also has this this idea called server side rendering that we'll talk more about later. Uh, and and others. It comes with a bunch of tools built into it. Uh, and it's very quick to get started. So that is Next.js. And that completes the narrative of the kind of three tiers of technology that have formed modern front end development.

</details>
