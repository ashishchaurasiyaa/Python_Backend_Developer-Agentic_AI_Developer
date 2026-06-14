# L80 — Day 4: Playwright Integration — Web-Browsing AI Agents

> **Week 4 — LangGraph** · ⏱️ ~9m · 🎥 Lecture 80 of 131
> **Instructor:** Ed Donner · **Lecture ID:** 49821363

---

## 🎯 Ek Line Mein (TL;DR)

Ed ka **change of heart** — woh ab **LangGraph** ke serious fan ban rahe hain, aur Day 4 pe naya project **Sidekick** shuru hota hai: **async LangGraph** + **Playwright browser automation toolkit** se ek aisa agent banana jo khud **web browser drive** kar sake (navigate, click, text extract).

---

## 📝 Hinglish Explanation (Detailed)

- **Ed ka confession:** Week ki shuruaat mein unka favourite **OpenAI Agents SDK** tha, second favourite **CrewAI**, aur LangGraph se thode skeptical the (kyunki "you sign up for a lot"). Lekin ab woh **convert ho rahe hain** — LangGraph mein bahut maza aa raha hai, aur aaj ka demo dekh ke shayad aap bhi convince ho jaoge.

- **Aaj ka plan (Week 4, Day 4) — naya project: Sidekick.** Teen cheezein:
  1. Ek **naya powerful tool** unveil karna (spoiler: Playwright browser tools),
  2. **Structured outputs** use karna (har framework mein recurring theme raha hai),
  3. LangGraph mein ek proper **multi-agent workflow** banana — OpenAI Agents SDK ke **handoff** ya CrewAI ke **crew** ka equivalent.

- **Quick recap (pichle lecture ka diagram):**
  - **Super-step** = graph ka ek complete invocation — ek user input aaya, woh poore graph (agents + tools) se flow hua.
  - **State** graph ke through manage hota hai; state object **immutable** hai, aur **reducers** call hote hain taaki state properly maintain/merge ho.
  - **Super-steps ke beech** state maintain karne ka tareeka = **checkpointing** — itna powerful hai ki aap **clock rewind** karke state ko kisi bhi prior point pe wapas le ja sakte ho (**time travel**).

- **Lab 3 (Week 4):** imports + hamesha wala `load_dotenv(override=True)` — ab tak ye second nature ho gaya hai.

- **Async LangGraph (naya concept):** Sync mode jaisa hi hai, bas async variants use karo:
  - Tool run karna: `tool.run(...)` ki jagah → `await tool.arun(...)` (same inputs).
  - Graph invoke karna: `graph.invoke(state)` ki jagah → `await graph.ainvoke(state)`.
  - Bas itna hi difference — baaki sab same.

- **State definition:** Phir se **TypedDict** use ho raha hai (Pydantic objects jaisa lagta hai). Ek hi field — `messages`:
  - Type hai `Annotated` list, jisme LangGraph ko bataya jaata hai ki **`add_messages`** (ek **canned/built-in function** jo import karte ho) ko **reducer** banao.
  - Ye reducer har node return pe messages ko **append/add** karta rehta hai (overwrite nahi).
  - Is state se `StateGraph` builder start hota hai.

- **Push notification tool (repeat from last time):** `push` function define karo, phir use ek `tool_push` Tool mein **wrap/package** karo jo describe karta hai ki ye kya karta hai. Done.

- **Ab magic — Playwright kya hai?**
  - **Browser automation** software — **Selenium ka next-generation** mana jaata hai. (Ed ne Selenium bahut use kiya hai.)
  - **Microsoft** ka banaya hua, originally **testing** ke liye, lekin log **web scraping** ke liye bhi khoob use karte hain.
  - Kyun? Kyunki plain HTTP request se sirf **server content** milta hai — Playwright/Selenium page ko **real browser mein render** karta hai, **JavaScript run** karta hai, **page paint** karta hai, aur tab content nikaalta hai.
  - **Headless mode** = browser window dikhti hi nahi, behind-the-scenes chalti hai. **Headful** = window dikhti hai aur aap interact kar sakte ho.
  - Install: `playwright install` (Windows/macOS), Linux pe thoda lamba command.

- **nest_asyncio sidebar (sirf notebook ke liye):**
  - **asyncio** ek **event loop** chalata hai jo awaited cheezein run karta rehta hai; IO pe hold hua to doosri awaited cheez run karta hai.
  - Problem: asyncio **sirf ek event loop** support karta hai — running event loop ke andar doosra event loop nahi chala sakte.
  - Jupyter notebook **khud ek event loop** mein chal raha hai, aur humein Playwright ko **async** drive karna hai → "event loop within an event loop" chahiye.
  - Solution: **`nest_asyncio`** package — asyncio ko **patch** kar deta hai taaki nested loops allowed ho jayein.
  - Note: jab baad mein ye code **plain Python file** mein move karenge, tab `nest_asyncio` ki zaroorat **nahi** padegi.

- **LangChain community ka Playwright toolkit (the magic):**
  - LangGraph/LangChain ke saath **out of the box** bahut saare ready-made tools aate hain (mostly **community package** mein).
  - Playwright ke liye **2 sets of tools** hain — ek simplistic/higher-level, aur ye wala: **Playwright Browser Toolkit** — **lower-level, granular** tools ka set.
  - Code: pehle ek **asynchronous Playwright browser** create karo, phir us browser se **toolkit** build karo → `tools` variable mein saare tools mil gaye.
  - **Milne wale tools:** element pe **click** karna, kisi web page pe **navigate** karna, **back button** (previous page), page se **text extract** karna, **hyperlinks extract** karna, **elements get** karna, aur **current web page** dekhna.
  - **Recap:** Playwright browser window launch karta hai; LangChain ka toolkit us browser se interact karne ke tools deta hai (open, navigate, read text/elements) — aur **yehi tools hum apne agent ko arm karenge** taaki woh khud browser chala sake.

---

## 🔑 Key Concepts / Important Terms

| Term | Simple Hinglish Meaning |
|------|--------------------------|
| **Sidekick** | Week 4 ka naya flagship project — ek personal co-worker agent jo browser + tools use karta hai |
| **Super-step** | Graph ka ek complete invocation — ek user input ka poore graph se flow ho jaana |
| **Reducer** | Function jo batata hai ki node ke return pe state field kaise merge ho (e.g. append vs overwrite) |
| **Checkpointing** | Super-steps ke beech state save karna — time travel/rewind possible |
| **Async LangGraph** | `await tool.arun(...)` aur `await graph.ainvoke(state)` — sync API ke async twins |
| **`add_messages`** | LangGraph ka canned reducer jo messages list mein naye messages add karta rehta hai |
| **`Annotated`** | Type hint jisme type ke saath metadata (yahan reducer) attach hota hai |
| **Playwright** | Microsoft ka browser automation framework — Selenium ka next-gen; testing + scraping |
| **Headless / Headful** | Browser bina window ke chale (headless) ya visible window ke saath (headful) |
| **JS rendering** | Plain request = sirf server HTML; browser render = JavaScript run karke actual painted page ka content |
| **`nest_asyncio`** | Package jo asyncio ko patch karta hai taaki event loop ke andar event loop chal sake (notebook ke liye) |
| **Playwright Browser Toolkit** | LangChain community ka lower-level toolkit — click, navigate, back, extract text/links, get elements wale tools |

---

## 💡 Backend Dev Ke Liye Note (aapke liye)

- **Selenium → Playwright** wahi jump hai jo `requests` → `httpx` ka tha: same job, modern async-first API, auto-waiting, Microsoft-backed. Agar aapne Selenium se E2E tests ya scraping ki hai, to yahan naya sirf itna hai ki browser ka "driver" ab ek **LLM agent** hai, aap nahi — toolkit ke granular tools (click/navigate/extract) agent ke liye **function-calling surface** ban jaate hain.
- **`nest_asyncio` wala issue aapne shayad jhela hoga:** running loop ke andar `asyncio.run()` call karo to `RuntimeError: This event loop is already running` — Jupyter/IPython ka classic problem (FastAPI/uvicorn ke andar bhi yahi pattern). `nest_asyncio.patch()` ek monkey-patch hai, production code mein avoid karo — isliye Ed bhi bolte hain ki plain `.py` file mein iski zaroorat nahi.
- **`Annotated[list, add_messages]`** ko Redux reducer ya event-sourcing **append-only log** ki tarah socho: state immutable hai, nodes "deltas" return karte hain, reducer decide karta hai merge strategy — yahi cheez parallel nodes pe write-conflict (last-writer-wins bug) se bachaati hai.
- **Hands-on lab:** `Practical/lab4_sidekick.py` (is repo me, `uv run` se chalta hai, Groq pe free via `langchain-groq` `ChatGroq`) — is lecture ka code khud chalane ke liye ye lab run karo. Note: lecture mein **Playwright browser-driving** hai, lekin hamare lab mein woh **SKIP** hai (heavy dep) — uski jagah sidekick lab mein safe sandbox file/python tools hain; LangSmith tracing bhi skip (key nahi).

---

## 🧠 Takeaway (yaad rakho)

1. **Sidekick project shuru** — LangGraph mein proper multi-agent workflow + structured outputs + ek powerful naya tool (Playwright).
2. **Async LangGraph trivially easy hai:** `tool.arun(...)` aur `graph.ainvoke(state)` — baaki sab sync jaisa.
3. **State = TypedDict + `Annotated[list, add_messages]`** — reducer messages ko append karta hai, overwrite nahi.
4. **Playwright** = next-gen Selenium (Microsoft): real browser render karta hai, JS chalata hai — isliye scraping/agent browsing ke liye plain requests se kahin better; headless ya headful dono mode.
5. **LangChain community ka Playwright Browser Toolkit** ready-made granular tools deta hai (click, navigate, back, extract text/links, get elements) — inhi se agent ko "arm" karke web-browsing agent banta hai; notebook mein async ke liye `nest_asyncio` patch chahiye.

---

<details>
<summary>📜 Full English Transcript (original, click to expand)</summary>

So, look, I don't know if you're anything like me, but I'm having something of a change of heart. So I started this week quite clearly with OpenAI agents SDK as my favorite, and obviously with crew as my second favorite, and being a little bit skeptical of LangGraph because you sign up for a lot. But I'm coming around. I'm having a really great time. And what I've got to show you today, I feel like you're going to be there, right there with me. I'm actually becoming a serious fan of LangGraph. Uh, and there's some really cool stuff, so see what you think. Uh, I'm, uh, I'm suddenly feeling treacherous against OpenAI agents SDK. Uh, so, uh, welcome. Welcome to week four, day four, introducing a new project sidekick, and I can't wait to tell you about it.

So what are we going to do today? How are we going to go deeper? You know, we always go a bit deeper with each of these. So first of all I'm going to introduce I'm going to unveil a new tool which is going to be incredibly powerful and which is going to allow us to do very different things. We're going to talk about structured outputs, something that we've I mean, it's been a recurring theme. We've done that in each of these. We'll use it here too. And we're also going to build a proper multi-agent workflow in LangGraph so that you see it really coming together, the equivalent of the handoff in OpenAI agents SDK, or having a crew of agents. We will be doing that.

And as a reminder, on the diagram I did last time, that brings it all together. Remember the terminology? A super step is a complete invocation of the graph, and each super step represents like one user input coming in and then flowing it through your graph of agents and tools. And then those blue diagrams are representing the graph that gets executed. The state is managed through that graph, and reducers are called to make sure that the state object, which is an immutable object, is maintained and managed through that. But between the super steps, you use checkpointing as your way of maintaining state. And checkpointing is very powerful, and it lets you do things like rewind the clock and put your state back to any prior point. So with that quick recap, let's go to the lab.

All right. So we get started in week four and we're going to go to lab number three. Week four. Day four. Lab three. Uh, it's, as I say, the start of an awesome project. I am super happy with this. I hope you will be too. We do some imports. Takes a while. There's a lot of stuff to go. And then we've got this empty cell here. Why have we got empty cell? Because of course we have to do load dot env override is true. This is second nature to you at this point. Okay.

So I also I'm going to introduce this time asynchronous LangGraph using LangGraph in async mode, uh, which I promised was going to happen this week. And it's very similar to using LangGraph in sync mode. Uh, when we used to call tools to run a tool, you can now call await tool dot arun to run the tool asynchronously, but passing in the same inputs. Otherwise it's just the same. And to invoke the graph, if we would have said graph invoke state before, we can now say await graph ainvoke state. So that is just simply a way to run a graph in asynchronous mode. And that is what we're going to be doing.

Uh, for the state, I'm going to again be using a typed dict. So that means that it looks very much like when we use pydantic objects, you just have one field I'm going to have called messages. It is annotated. The type is a list. And this is telling LangGraph we want it to use add messages, which is a canned function that you can import. We want that to be the reducer, which is going to keep on adding messages whenever we return that as our state from a node. And we will start a graph builder with that state. Okay. So far so good.

Okay. Next up we are going to create a tool that we did last time. So we can do it nice and quickly. Here it is the push notification tool. We define our function push. And then we wrap it package it in a tool called tool push which describes what it is it calls the function. And that is all we need to do okay.

Now now it gets exciting. Playwright. Do you know what playwright is? Playwright is one of these browser automation bits of software. It's considered the sort of the new the next generation of selenium, which many, many people have used. I've used selenium an awful lot. Playwright is by Microsoft and it's a, it's a it's a very nice framework for running a browser. And it's traditionally originally used for testing. So it's used for test purposes. And a lot of people also use it for web scraping, because if you just try and request a web page, you just get back like the server content, if you use something like Selenium or Playwright, you can actually render it in a browser, run the JavaScript, paint the page, and then use that to actually get the content. So playwright is a is a powerful tool for running a browser window, and it can do so what they call headless, which means you don't even see the browser windows, just like running behind the scenes or not headless headful in which case you see the browser screen yourself and you can interact with it. So that is playwright. You may already know it. A lot of people use playwright. This is how you install it. You type playwright install to do it on on Windows and Mac OS or on Linux it's this longer command and it will then be installed. And if you have problems with that, then let me know. But hopefully not.

Okay, one other thing to mention. One other little detail here. And this is just for running it in a notebook. Um, one of the problems, one of the challenges with async IO is that Asyncio runs an event loop. Um, and when you when it runs an event loop, it runs this thing that's just constantly making sure that it's running anything that's being awaited. And then when it's holding on IO, it runs something else that's being awaited. Uh, and one of the problems is that that async IO only supports one event loop. And if there's an event loop running, you can't within that event loop, run another event loop. And we're running an event loop as part of running, uh, this notebook right now. And so that can cause problems when you try and kick off async processes within async processes. Uh, and so there is this package called nest asyncio that's quite popular, which you can just simply use this and then it like patches asyncio so that you can have an event loop within an event loop. And as you will soon understand from me prattling away, we're going to want that because we're going to want to run playwright asynchronously, because we're going to build an agent that can drive playwright. And so we're going to need that concept of an event loop within an event loop. But when we later put this into Python code, we actually won't need this anymore. But we'll need it for now. All right. That's a long sidebar. That's over.

But now comes the magic. So one of the incredible things about LangGraph and LangChain, I'm becoming a convert of both, is that they come with so many great tools out of the box. Many of them are in the community package. There's actually a couple of different ways that you can run a playwright. There's two sets of tools. One of them is a more simplistic one that's just a bit higher level. This one that I've got here, uh, the Playwright Browser Toolkit. This is a lower level set of tools which provides a bunch of different tools. Let's just We're gonna create this. So this is this is, um, creating an asynchronous playwright browser, and then it's building a toolkit from that browser. And now we've, we've got the tools into a variable tools. So I'm just going to print these. And here are all of the tools that we get in this package. We get something that lets you uh, click on an element in a web page, navigate the browser to a particular web page, go to the previous web page like press the back button, extract text from a web page, extract hyperlinks, get elements, and then the current web page. Uh, so it gives you quite granular control over what's going on in this playwright browser. So again, to recap, playwright allows you to launch a browser window. And then this LangGraph or LangChain set of tools gives us a series of tools that will allow us to interact with that browser open windows, navigate, read the text, read the elements, do that kind of thing. That's pretty cool. And that is something we're going to be able to arm our agent to be able to use.

</details>

---
*Source: Official Udemy lecture transcript (auto-captions, lightly cleaned). Notes in Hinglish for self-study.*
