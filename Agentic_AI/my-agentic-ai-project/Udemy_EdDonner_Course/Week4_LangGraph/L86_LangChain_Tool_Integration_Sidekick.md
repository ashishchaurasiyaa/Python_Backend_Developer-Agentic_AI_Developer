# L86 — Day 5: LangChain Tool Integration — AI Sidekick from Scratch

> **Week 4 — LangGraph** · ⏱️ ~10m · 🎥 Lecture 86 of 131
> **Instructor:** Ed Donner · **Lecture ID:** 49821423

---

## 🎯 Ek Line Mein (TL;DR)

Sidekick project ka **tools module** banaya — **Serper search, Playwright browser tools, Pushover push, File Management toolkit, Wikipedia, Python REPL** — sab LangChain ecosystem se plug-in kiye; phir notebook wala code ek proper **`Sidekick` class** (Python module) me productionize kiya jisme **State (Annotated reducer)**, **structured-output Evaluator schema**, async `setup()` coroutine aur `build_graph()` hai.

---

## 📝 Hinglish Explanation (Detailed)

- **Tools module ka structure**: Ye module bas saare tools load karta hai jo ab tak use kiye hain. Start hota hai **`load_dotenv()`** se (API keys chahiye), phir **Pushover** ke liye kuch constants, aur **Google Serper API wrapper** create hota hai web search ke liye.
- **Playwright tools (browser driving)**: Pichle notebook se same code — **async** code se Playwright instance start karte hain, **Chromium** launch karte hain, **toolkit** lete hain aur toolkit se tools return karte hain. Saath me **browser aur playwright object bhi return** karte hain kyunki end me unko **clean up** karna padta hai (resources release).
  - Ed honestly bolte hain: pakka nahi ke cleanup hamesha sahi se hota hai — kabhi-kabhi **Chromium browser expected se zyada der tak hang around** karta hai. Browser windows ka "leak" ho sakta hai, monitor karna padega.
- **Push notification function**: Wahi familiar simple function — `requests` se **Pushover URL** pe push notification bhejta hai. Homegrown tool.
- **`get_file_tools()` — File Management Toolkit (NEW)**: Ye **`langchain_community`** se aata hai. Ed ka point: **LangChain ecosystem itna popular hai** ke tons of ready-made tools available hain jo LangChain ke **tools format** me conform karte hain — ek tarah ka **"mini MCP"** sirf LangChain walon ke liye. (Week 6 me **MCP** aayega jo isko universal bana deta hai.)
  - File toolkit LLM ko ek directory me files ke saath kaam karne deta hai — Ed ne **`sandbox`** root directory set ki hai, aur toolkit LLM ko **us root directory ke andar hi force** karta hai. Safe.
- **Tools ki final collection** (jo sidekick ko milegi):
  - **Push tool** — push notification function ke around manually `Tool` define kiya.
  - **File tools** — File Management toolkit se.
  - **Serper search tool** — search wrapper ke around manually bana tool.
  - **Wikipedia tool** — **`WikipediaAPIWrapper`** banaya (iske liye `wikipedia` Python package install karna pada). Ye Wikipedia ke **free public API** se pages fetch karta hai — LLM ko general knowledge expertise milti hai.
  - **Python REPL tool** — LLM ko **Python code run karne ki power** milti hai, jaise command line pe `python` type karke code run karo aur answer milta hai.
- **⚠️ Python REPL — NOT sandboxed**: Crew wale week me Python code **Docker container** ke andar chalta tha (insulated). Ye wala **bilkul insulated nahi hai** — LLM directly aapke computer pe code chala sakta hai. Ed ki warning: agar comfortable nahi ho to **is tool ko tools list se remove kar do**. Ed khud GPT-4o mini use kar rahe hain aur monitor karte hain, to comfortable hain — "as long as you're careful, it should be fine. You have been warned."
  - Same option Playwright tools ke liye bhi — pasand nahi to wahan se empty return kara do.
- **Extensibility — `other_tools` list**: Is list me jo bhi tool daaloge, sidekick **automatically use karega**. LangChain ke `community`, `utilities`, `experimental`, `tools` folders me ya documentation me dekho — **bahut saare tools** hain (Google Calendar tool tak, jo scheduling kar sake). Project ki beauty yahi hai: **LLM/agent ko capabilities dete jao, bas list me add karte jao**.
- **`Sidekick` module — notebook se production**: Lab wala same code ab ek Python module me. Ed ka **notebook pitch**: engineering background wale bolenge "ye TDD nahi hai, ye software likhne ka tarika nahi" — lekin AI engineering kaam **experimental by nature** hai: prompts craft karna, ideas try karna, trial-and-error. Isliye workflow: **notebook me prototype/iterate/perfect karo → phir Python module me productionize karo**.
- **State definition**: Wahi **TypedDict** state — **`messages`** field jo **`Annotated`** hai ek list ke saath jo **reducer** use karti hai (append, overwrite nahi). Plus: **`success_criteria`**, **`feedback`**, **`success_criteria_met`**, **`user_input_needed`** — ye sab evaluator ke assessment se aate hain.
- **Evaluator schema (structured outputs)**: LLM se jo output chahiye uska **schema**: `feedback`, success criteria met hua ya nahi, aur user input chahiye ya nahi. Schema ke **field descriptions LLM ko diye jaate hain** taaki wo structured output sahi populate kare.
- **`Sidekick` class + async init pattern**: Class kaafi badi hai (Ed maante hain refactoring warrant karti hai). Ek **fussy async issue**: `__init__` ko async nahi bana sakte, lekin graph setup async hai — to ek **alag `setup()` coroutine** banaya. Pattern: **pehle instantiate karo, phir `await setup()` call karo**.
- **`setup()` me kya hota hai**:
  1. `playwright_tools()` coroutine call → `tools`, `browser`, `playwright` populate.
  2. Other module ke baaki tools `tools` me add.
  3. **Worker LLM** create (GPT-4o mini, switch kar sakte ho) → **`bind_tools(tools)`** → instance variable me store.
  4. **Evaluator LLM** create → instance variable me store.
  5. **`build_graph()`** call — wahi classic **5 steps** jo graph run karne aur **super-steps** execute karne se pehle hone chahiye.

---

## 🔑 Key Concepts / Important Terms

| Term | Simple Hinglish Meaning |
|------|--------------------------|
| **Tools module** | Ek alag Python module jo saare tools (search, browser, files, push, Wikipedia, REPL) load karke ek list me return karta hai |
| **Google Serper wrapper** | LangChain ka wrapper jo Serper API se Google search karwata hai |
| **Playwright toolkit** | LangChain community toolkit jo async Playwright + Chromium se browser-driving tools deta hai; browser/playwright objects cleanup ke liye return hote hain |
| **File Management Toolkit** | `langchain_community` ka ready-made toolkit — LLM ko ek **sandbox root directory** ke andar file read/write tools deta hai |
| **Wikipedia tool** | `WikipediaAPIWrapper` (free public API) se LLM ko Wikipedia pages fetch karne ka tool |
| **Python REPL tool** | LLM ko directly Python code run karne ki power — **NOT sandboxed** (CrewAI ke Docker wale se alag), caution ke saath use karo |
| **"Mini MCP"** | Ed ki analogy: LangChain ka common tools format ecosystem ke andar wahi kaam karta hai jo MCP universally karta hai — koi bhi conforming tool plug-in ho jata hai |
| **Notebook → Module workflow** | AI engineering experimental hai: notebook me prototype/iterate karo, fir productionize karke Python module banao |
| **State (TypedDict + Annotated reducer)** | `messages` pe reducer (append), plus `success_criteria`, `feedback`, `success_criteria_met`, `user_input_needed` fields |
| **Structured outputs schema** | Evaluator LLM ke output ka Pydantic-style schema; field descriptions LLM ko guide karti hain |
| **Async `setup()` coroutine** | `__init__` sync rakhna padta hai, isliye async initialization (playwright, graph build) alag coroutine me — instantiate first, then `await setup()` |
| **Worker / Evaluator LLMs** | Worker = GPT-4o mini + `bind_tools`; Evaluator = structured output wala doosra LLM instance |
| **5 steps + super-steps** | Graph banane ke classic 5 steps (`build_graph`) jo run/super-step execution se pehle complete hone chahiye |

---

## 💡 Backend Dev Ke Liye Note (aapke liye)

- **Async `__init__` problem aapne dekha hoga**: Python me constructor coroutine nahi ho sakta — isliye `Sidekick()` + `await sidekick.setup()` ka two-phase init. Ye wahi pattern hai jo aap `aiohttp.ClientSession` ya async DB pools ke saath use karte ho (ya classmethod factory `async def create()`). Playwright/browser objects ko return karke baad me close karna = context-manager discipline jo yahan manually karna pada.
- **Python REPL tool = unsandboxed `eval()` as a service**: Backend me aap kabhi user input ko `exec()` nahi karte — yahan LLM ka generated code directly host pe chalta hai. CrewAI ne Docker isolation diya tha; LangChain ka REPL nahi deta. Production me iske liye gVisor/Firecracker/containers sochna padega. File toolkit ka `sandbox` root = chroot-jail jaisi soch.
- **LangChain tools format as "mini MCP"**: Ye bilkul ek interface contract hai — jaise aapke services ek common API spec (OpenAPI) follow karte hain to koi bhi client plug ho jata hai. `other_tools` list me append karte jao = dependency injection of capabilities, zero orchestration code change.
- **🧪 Hands-on lab**: `Practical/lab4_sidekick.py` (is repo me, `uv run` se chalta hai, Groq pe free via `langchain-groq` ChatGroq) — **is lecture ka code khud chalane ke liye ye lab run karo**. Hamare labs course se thode alag: LangSmith tracing skip (key nahi), SerperDev ki jagah **free Wikipedia search**, aur **Playwright browser-driving SKIP** (heavy dep — sidekick lab me uski jagah safe sandbox file/python tools hain). Lecture me Serper + Playwright dono hain, to bas yaad rakho: lab me search Wikipedia se hota hai aur browser tools ki jagah sandboxed file/python tools hain — concepts (tool list assembly, bind_tools, async setup) same hain.

---

## 🧠 Takeaway (yaad rakho)

1. **Tools module** = saare tools ek jagah assemble: Serper search, Playwright browser, Pushover push, File Management (sandbox), Wikipedia, Python REPL — aur `other_tools` list me kuch bhi add karo, sidekick automatically use karega.
2. **Python REPL tool unsandboxed hai** — LLM aapke machine pe code chala sakta hai; uncomfortable ho to list se hata do ("You have been warned").
3. **LangChain ecosystem = "mini MCP"** — common tools format ki wajah se community ke tons of ready-made tools plug-in ho jaate hain (Week 6 me real MCP aayega).
4. **Notebook me prototype, module me productionize** — AI engineering trial-and-error hai, TDD-first nahi; perfect hone ke baad code class me move karo.
5. **`Sidekick` class pattern**: sync `__init__` + async `setup()` coroutine → playwright tools load → worker LLM (`bind_tools`) + evaluator LLM → `build_graph()` (5 steps) → tab super-steps run hote hain. State me `messages` (Annotated reducer) + success_criteria/feedback/user_input_needed fields.

---

<details>
<summary>📜 Full English Transcript (original, click to expand)</summary>

Okay, so I am going to start by taking us over to the tools which we're in right here. So the way that the tools module works is it's just a module that's going to load in all of the tools that we've worked with in the past. Um, it starts with a loading in the dot env. Um, because we'll need the API keys, we set up a few constants for Pushover. We create the Google Serper API wrapper so that we can use that API. Um, and then we have uh, the Playwright tools. This is the tools for navigating for driving the browser, taking exactly from the notebook that we were looking at before. Uh, we, we use the async code to start the Playwright instance, and we launch Playwright's Chromium, and then we get the toolkit, and then we return the tools from the toolkit. We also return this browser and the playwright object itself. And we do that because we need to clean them up at the end of it when it's finished with resources. And this is something that I'm not sure I. It remains to be seen whether this is properly cleaning up resources. I'm checking to see if it does. Sometimes I see that the Playwright the Chromium browser, hangs around for longer than I was expecting, but I think it does. It does close it down properly. Uh, but uh, yeah, we'll see if it if it ever causes like a leak of browser windows being, being left open.

All right. And then this you should recognize because this is the push notification that we've used many times. Uh, it's just a simple function that sends a push notification using requests using the Pushover URL. And then there's also one here that's new. This is get file tools. And this is using the file management toolkit which is from right here from LangChain Community. And this is an example again of one of the things that is so amazing about the LangChain ecosystem. It's so popular. So many people have used it that there are tons and tons of tools that you can tap into. Now in the in week six, we're going to get very excited about MCP, which of course has taken the world by storm. And MCP is so amazing because it's sort of unleashed the ability to connect together with different tools all over the place. But already people who are part of the LangChain ecosystem have had the advantage of a lot of of tools that can form to LangChain's tools format, which in itself is like a sort of a mini MCP, but but just for people in in LangChain and so we can take advantage of this now we'll have more in week six, but for now we have access to all of the ones that come in the LangChain Toolkit, which includes this file management, one which will give tools for our LLM to be able to to mess around in a directory that I'm setting sandbox. And it will be it will be forced to stay in that root directory. So that's good.

And then so so I'm going to put together these different tools into this, this um, uh, this this collection of tools here. So we're going to take a push tool. We're going to define a tool around that, that push notification. So this is like a homegrown tool to do that. Um, there's file tools that we've just talked about. There's uh a tool to run the Serper search. So this is again us manually creating a tool around the search. There's something called the Wikipedia tool. Uh, so we create a Wikipedia API wrapper. Uh, we create that. And that needed me to install a Wikipedia Python package in our environment, which I did. And then this tool is able to call and collect Wikipedia pages using Wikipedia's API, which is freely available to everybody. And so that gives our LLM expertise about stuff through Wikipedia. And then I also create here a Python tool. Maybe it'd be nicer just to show that separately. Python REPL. So this means this is slightly nicer. This means that we are giving our, our, uh, LLM the ability to run Python code, much as if you just typed Python at the command line in one of these kinds of interfaces where it can put in some code and get back the answer. So we're giving it that power. And this this is something which isn't sandboxed. So it's unlike when we did this with Crew when we ran Python code within a Docker container. So it was somewhat insulated from the world. This is not insulated. And so this should be used with caution. And if you're not comfortable with it then you should comment this out. Uh, and so just just by or just remove it from here, I mean remove it from these tools. If you're not happy with your LLM being able to run Python code on your computer. Uh, and, uh, but but for me, I'm, I'm especially as I'm using GPT-4o mini, I'm quite comfortable that it's going to be sensible. And besides, I'll monitor it and be be be careful with it. So as long as you're careful, as long as you show caution, it should be completely fine. Um, but do be aware of what we're doing there. And if you're not comfortable, if you have any doubts at all, then remove that tool from the list. You have been warned. And you can also, of course, just, uh, remove the the the, um, Playwright tools. If you don't like it, just have it return something empty there instead. Uh, instead of returning those, uh, those tools.

Okay, so that is our set of tools, all the tools that we want to arm our coworker, uh, sidekick with. And you can just add more tools to this other tools list. Anything you put in there will just automatically get used by our sidekick. You can just keep putting more and more and more things in there, and you can Google or ask ChatGPT about some of the tools that are in the LangChain tools and the community folders like community utilities and experimental tools and tools. You can look at these or you can just look at them on LangChain's documentation. There's a lot to choose from and you can just put them all in here. You can have a tool that can look at your Google Calendar and attach to to Google, so that it could schedule things for you. You can have all sorts of tools. There's so many. And that's the beauty of this project that you can just keep giving more and more capabilities to your LLM, that to your agent. That's the idea.

All right. Next up we're going to go to the big class which is sidekick. So now I've gone to the sidekick module. Here it is. So the good news is this should all be familiar to you, because it's just the same code we had in the lab just moved into a Python module, which shows how, again, if I can do another of these, like a pitch for, for using, uh, these notebooks, you can iterate on something in a notebook, you can prototype, iterate, perfect your prompts, and then move to a module and people from an engineering background will say, well, that's not the way that we write software. We have things like TDD. We have we have a very different kind of process. The thing about this kind of work is that it is much more experimental by nature. The mindset of an AI engineer is more about crafting prompts, trying different ideas, seeing how they work. And so because by its very nature, it is a bit more trial and error. And and it means that it lends itself very well to a notebook interface initially until you've got things better down, and then you move to sort of productionizing something in Python code like this.

So anyways, this is the the module we define the state, the typed dict that is our state. It has the messages field which is the annotated field that that is a list that will use this reducer. And messages we have success criteria, feedback success criteria met and user input needed. These these are the things that we get back from our assessment and talking about our assessment. Our evaluation here is the structured outputs schema. The the schema for the output that we get from our LLM. And we want feedback whether or not the success criteria is met and whether or not user input is needed. That's what we want back. And these descriptions are what will be provided to the LLM so that it populates the structured output. Well okay.

And now we have a class called Sidekick. And it's a it's quite a quite a big one. And maybe this could be could could warrant some refactoring. But it's basically everything we had in the notebook. Um, there's one fussy thing about working with async code, which is that the init method, when we create this, we don't want that to be to be async. Um, but we need to be able to do some initialization that will be async, like setting up our graph. And so we have to have like a separate async, uh I can say async method, but a coroutine uh, that, that is going to be handling that part of it. And we're going to need to make sure when we when we initialize a sidekick that we can first instantiate it and then call this setup asynchronously. Um, so first the first thing I do in this setup is I call that playwright tools function coroutine that we saw in the other, um, in the, in the sidekick tools. And then I populate my tools, my browser and playwright, and then I add into tools the other tools that we also put together in the other module. Okay. And then I create my worker LLM, which is in this case GPT-4o mini. But feel free to switch it up and bind it to tools and store that as an instance variable. And then an evaluator LLM and I also store that as an instance variable. And then I call build graph. That's going to be the the the big part of that's what we've always said is the five steps that need to happen before you can actually run your graph and do your super steps.

</details>

---
*Source: Official Udemy lecture transcript (auto-captions, lightly cleaned). Notes in Hinglish for self-study.*
