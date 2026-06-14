# L42 — Day 4: Building Deep Research Agents — Implementing OpenAI's Web Search Tool

> **Week 2 — OpenAI Agents SDK** · ⏱️ ~9m · 🎥 Lecture 42 of 131
> **Instructor:** Ed Donner · **Lecture ID:** 49820791

---

## 🎯 Ek Line Mein (TL;DR)

Week 2 ka pehla bada project — **Deep Research agent** — shuru hota hai, aur iska pehla building block hai OpenAI ka **hosted `WebSearchTool`**: ek tool jo aapke machine pe nahi, **OpenAI ke servers pe remotely** chalta hai, aur jisko `tool_choice="required"` se **mandatory** banaya jata hai taaki search agent har baar search zaroor kare.

---

## 📝 Hinglish Explanation (Detailed)

- **Project context — Deep Research:**
  - Ye Agentic AI ka ek **classic use case** hai — ek agent jo internet pe jaake search kare, links explore kare, aur diye gaye topic pe research kare.
  - Frontier Labs (jaise OpenAI) khud ye feature offer karte hain — ChatGPT me **"Deep Research" button** dabao to wahi cheez chalti hai: ek model **agentic workflow mode** me run hota hai.
  - Hum wahi cheez khud build karenge — apna **deep research agent**, jo kisi bhi business area pe customize ho sakta hai ya personal **sidekick** ki tarah use ho sakta hai.
  - Is project me 3 cheezein combine hongi jo pehle seekh chuke hain: **tools**, **structured outputs**, aur naya concept — **hosted tools**.

- **Notebook vs proper Python modules:**
  - Aaj phir **notebook** (Cursor ke andar) me kaam hoga — experimenting/explaining ke liye best.
  - Kal (Day 5) yahi project **proper Python modules** me convert hoga — to "real code" chahne walon ke liye intezaar bas ek din ka hai.

- **Hosted Tools — sabse bada naya concept:**
  - **Hosted tool** = tool jo **OpenAI khud apne servers pe run karta hai** — aapka code sirf tool ko attach karta hai, execution remote hota hai.
  - Abhi (recording ke time) OpenAI sirf **3 hosted tools** deta hai:
    1. **`WebSearchTool`** — OpenAI aapke behalf pe web search chalata hai (aaj yahi use hoga).
    2. **`FileSearchTool`** — OpenAI ke paas uploaded **vector stores** pe search (RAG-style).
    3. **`ComputerTool`** — screenshots lena, computer pe click karna etc.
  - Course me baad me hum apna **khud ka computer tool** banayenge — hosted nahi, **apne machine pe** chalega.

- **⚠️ Cost warning — WebSearchTool sasta nahi hai:**
  - Cheapest config (**GPT-4o-mini + low search context**) pe bhi **~2.5 cents per call**.
  - Deep research me typically **~10 searches** hoti hain → **~$0.25 per run**, aur experiments repeat karte karte **$2–3** tak pahunch sakta hai (Ed ne pehli baar itna hi spend kiya).
  - Suggestions: **costs monitor karo**, chaaho to searches **skip** karo, ya settings **lowest** pe rakho (sirf few cents). Future weeks me iska **bahut sasta alternative** aayega.
  - Pricing **region ke hisaab se alag** ho sakti hai aur OpenAI badalta rehta hai — official pricing link check karte raho.

- **Search Agent banana:**
  - **Instructions (system prompt):** *"You're a research assistant. Given a search term, you search the web for that term. Produce a concise summary (2–3 paragraphs), capture the main points, write succinctly — no need for good grammar because it will be consumed by someone else synthesizing a report."*
  - Ye prompt **OpenAI ke official documentation se verbatim** liya gaya hai — yaani model banane walon ka khud ka likha hua, isliye "good authority" pe well-written maan sakte hain.
  - Interesting design point: output **insaan ke liye nahi**, balki **doosre agent ke liye** hai (jo report synthesize karega) — isliye grammar perfect hone ki zaroorat nahi, sirf information density chahiye.
  - Agent setup:
    - `Agent(name="Search agent", instructions=..., tools=[WebSearchTool(search_context_size="low")], model="gpt-4o-mini", model_settings=ModelSettings(tool_choice="required"))`
  - **`search_context_size`** parameter: `low` / `medium` / `high` — price isi se decide hoti hai. `low` cheapest, `medium` (default) thoda zyada, `high` kaafi zyada.
  - **Model choice** bhi cost pe asar dalta hai: GPT-4o-mini bahut sasta, full GPT-4o kaafi mehenga.

- **`tool_choice="required"` — mandatory tool call:**
  - `ModelSettings(tool_choice="required")` pass karne se agent ko tool **chalana hi padega** — uske paas discretion nahi hai.
  - Yahan ye perfect fit hai kyunki search agent essentially **tool call ka wrapper** hai — bina search kiye "research assistant" ka koi matlab nahi.
  - Ye snippet "side me note karke rakho" wali cheez hai — kaafi useful pattern.

- **First run — results aur unki accuracy:**
  - Query: *"Latest AI agent frameworks in 2025"* — result **nice markdown** me aaya.
  - Results me aaye: LangChain, LangGraph, CrewAI, Semantic Kernel, AutoGen... lekin **OpenAI Gym** bhi (jo ki RL framework hai, agent framework nahi 😄), aur **Rasa**, **JADE** jaise purane frameworks bhi.
  - Funny observation: model ko **khud apne OpenAI Agents SDK ke baare me pata nahi** — knowledge cutoff/search quality ka classic example.
  - Ed ka verdict: **mixed accuracy** — LangChain/Semantic Kernel ko "agent framework" kehna debatable hai, lekin LangGraph, CrewAI, AutoGen bilkul sahi (in teeno pe course me ek-ek week milega).

- **Trace check (OpenAI platform):**
  - Notebook me diye link se **OpenAI trace UI** kholo → "Search agent" trace dikhega.
  - Trace me dikhta hai: agent call hua, **web search tool** use hua, **total tokens**, system prompt, user prompt, aur final output — sab kuch transparently logged.

---

## 🔑 Key Concepts / Important Terms

| Term | Simple Hinglish Meaning |
|------|--------------------------|
| **Deep Research** | Classic agentic use case — agent internet pe search karke topic research karta hai aur report banata hai (ChatGPT ke Deep Research button jaisa) |
| **Hosted Tools** | Tools jo OpenAI **apne servers pe remotely** run karta hai — aapke code me sirf attach hote hain, execute wahan hote hain |
| **`WebSearchTool`** | OpenAI ka hosted tool jo aapke behalf pe live web search karta hai (~2.5¢/call cheapest config pe) |
| **`FileSearchTool`** | Hosted tool — OpenAI pe uploaded vector stores pe search (RAG-type) |
| **`ComputerTool`** | Hosted tool — screenshots + computer pe clicking (course me baad me iska local version banega) |
| **`search_context_size`** | `low`/`medium`/`high` — search me kitna context fetch hoga, directly price control karta hai |
| **`ModelSettings(tool_choice="required")`** | Agent ko tool call **mandatory** banata hai — LLM ke paas skip karne ka discretion nahi rehta |
| **Search Agent** | Deep research ka pehla agent — search term leta hai, web search karke 2–3 paragraph ka concise summary deta hai (doosre agent ke consumption ke liye) |
| **Trace** | OpenAI platform pe har run ka log — kaunsa agent, kaunsa tool, kitne tokens, kya input/output |

---

## 💡 Backend Dev Ke Liye Note (aapke liye)

- **Hosted tool vs function tool** ka farak waise hi hai jaise **managed service vs self-hosted service**: `@function_tool` wala code aapke process me chalta hai (jaise aapka own microservice), lekin `WebSearchTool` ek **managed API** hai — aap sirf capability declare karte ho, execution + infra OpenAI ka. Trade-off bhi same: convenience vs **per-call billing** aur vendor lock-in.
- **`tool_choice="required"`** ko aise socho jaise API me ek **mandatory middleware** — request handler tak pahunchne se pehle auth check skip nahi ho sakta. Yahan LLM ki "creativity" pe rok lagti hai ki wo bina search kiye apni training memory se jawab gher de — **determinism inject karne ka pattern** hai ye.
- **Cost engineering = capacity planning:** 2.5¢/call × 10 searches/run × N runs — ye exactly waise hi sochna hai jaise aap DB read units ya egress costs estimate karte ho. `search_context_size` ek **cost knob** hai, rate-limit/quota ki tarah monitor karo.
- 🧪 **Hands-on lab:** is lecture ka code khud chalane ke liye `Practical/lab4_deep_research.py` run karo (is repo me, `uv run` se chalta hai, **Groq pe free**). Note: hamare labs OpenAI ki jagah **FREE Groq** use karte hain (`OpenAIChatCompletionsModel` + `base_url` trick), aur lecture ke **paid `WebSearchTool` (2.5¢/call)** ki jagah lab4 me **free Wikipedia search tool** hai — to deep research ka pura flow ₹0 me practice ho jata hai. OpenAI traces bhi Groq setup me nahi dikhenge, wo OpenAI-key-only feature hai.

---

## 🧠 Takeaway (yaad rakho)

1. **Hosted tools = OpenAI ke servers pe chalne wale tools** — abhi sirf 3 hain: `WebSearchTool`, `FileSearchTool`, `ComputerTool`.
2. **`WebSearchTool` paid hai** (~2.5¢/call cheapest config pe) — deep research ke ~10 searches per run ke saath cost quickly badh sakti hai, isliye `search_context_size="low"` + GPT-4o-mini use karo aur monitor karo.
3. **`ModelSettings(tool_choice="required")`** se agent ko tool call **force** kar sakte ho — jab agent essentially tool ka wrapper ho to ye must hai.
4. **Agent-to-agent output design:** search agent ka summary insaan ke liye nahi, **synthesizer agent** ke liye hai — isliye prompt me "no need for good grammar" likha hai. Multi-agent pipelines me consumer ke hisaab se output design karo.
5. Web search ke results **mixed accuracy** ke ho sakte hain (model ko khud apna SDK nahi pata tha!) — search ≠ guaranteed truth, verification layer ki zaroorat samjho.

---

<details>
<summary>📜 Full English Transcript (original, click to expand)</summary>

Well, I'm extremely excited about today. This is of course, day four of week two, and we're getting on to our first large, juicy project in the form of deep research. This is one of the classic use cases of Agentic AI, the case where you have an agent that is able to go off, search the internet and do some research, look at different links and try and research a topic that you give it. And we know this so well because many of the Frontier Labs offer this agent via their online chat tools. And for example, on OpenAI, you can go to GPT and you can press the deep research button. And that runs a model in deep research mode, which is basically running an agentic workflow. So we are going to do that. We are going to give our agents the ability to do deep research, and we're going to use a few things that we've already learned about. We're going to use tools. Of course we're going to use structured outputs again. We encountered it briefly last time, a little bit more this time. And we're going to use something called hosted tools for the first time, using tools that are running remotely. All right, let's get straight to it.

Okay. So here we are in Cursor. We're going to open up the directory for week two. And we're now going to lab four, deep research. And we are going to start again in a notebook like this, in one of the notebooks running within Cursor. And I know that a lot of you would prefer to be working with real Python modules. And fear not. We will get to that tomorrow. We will do this in Python code and proper modules. The lab, this kind of format, these notebooks, they're so good for talking through things, for experimenting. And it gives you the power to be changing things, playing around while we go through this. So I think it's good just for today.

So this is of course an enormous classic agentic use case. And what's great about it is it applies so broadly. You can apply this to any business area. You can build a deep research agent that's focused on your business area, or you can use this as something which is like a sidekick for yourself. We're going to build a different kind of sidekick later in this course. But this is one kind already, and it should be useful for you immediately. So I think it's terrific that we're doing this, and I hope you're as excited as me to be building your own deep research agent, something which the Frontier Labs have done themselves.

Okay, so let's get started. Enough of my prattling away. We do some imports. We do one of these usual load dot envs. All right. And now it's time for me to talk about the big change this week, which is that we are going to use some things called hosted tools, which means that they are tools that OpenAI is going to run for us. There only are three of them that OpenAI provides, at least as of now, and we're going to use one of them. The three are the web search tool, the file search tool, and the computer tool. The web search tool lets us do what we're going to do today, which is ask OpenAI to run a search on our behalf. The file search tool is how we can run searches across the vector stores that you can upload and have remotely with OpenAI, and the computer tool allows things like taking screenshots and clicking around a computer. Now we're not going to be using either of those two. We're going to be doing the web search tool. But fear not, later in the course we will have basically our own computer tool, but we won't be running it as hosted. We'll be running it on our own computers, as you will see. In case that sounds intriguing, but for now we're going to be using the web search tool.

And I want to make an important point, which is that OpenAI's web search tool is not that cheap for some reason, which seems not entirely clear to me. It actually costs 2.5 cents right now for me to run this, even at the low end of the cheapest model at the lowest end — 2.5 cents per call, which may not sound like it's a huge amount. But typically if we're running a deep research, we might be doing like ten different searches. And that means it's $0.25 a pop, which means that you can quite quickly add up to 2 to 3 dollars, which is what I spent the first time I did this. I think the way I have it set up now would be more like $1. Still, that's maybe not to be sniffed at. So I would suggest monitor this and you can decide to skip doing the searches, or I'll show you where you can turn it all the way down so that you're only spending a few cents. And then later in future weeks, we're going to be doing this a bit differently. And we'll have other ways to do this which will cost a fraction of this. So fear not. But for now, it's nice for us to use OpenAI's. And OpenAI's is actually really good. So maybe it's worth a 2.5 cents. I don't know. The costs themselves are on this link here. So it's always worth double checking because it might be different for your region, or OpenAI might change the pricing all the time. So go there and you can look. We are going to be using GPT-4o-mini, low search. Okay. With that, let's get started with our first search.

Okay. It's now time for us to create our first agent for this product. And the first agent is called the search agent. So here are the instructions, the system prompt for this agent: You're a research assistant. Given a search term, you search the web for that term. You produce a concise summary, 2 to 3 paragraphs, capture the main points, write succinctly, and no need to have good grammar because it will be consumed by someone else synthesizing a report. It's a very clearly written set of instructions right here, and I would love to take credit for it. But I must confess that I just took this verbatim from OpenAI's documentation for how to do web searches with their tool, so we can probably take it on good authority that this is a well written prompt, since it's written by the people that built the model.

So, um, we're going to use this prompt. We're going to create a search agent. It is an agent named search agent. This is the instructions. And we're going to give it one tool. And that tool is called a web search tool. And this is one of OpenAI's three hosted tools. So we're providing that as our tool. There is an optional parameter. You can specify the search context size, which can be low, medium or high, where that reflects the price that you'll pay. Low is of course the cheapest, and then medium is the default — is only a little bit more, but high I think is quite a lot more. You can also pick the model. It's a lot cheaper to pick GPT-4o-mini. GPT-4o is a lot more. And um, finally there's this here. This is a nice little snippet of code to keep in mind. This is how you say that this agent is required to run the tool. It is mandatory. It doesn't have discretion over this. So this is the way you do it. You pass in this model settings with tool choice is required. And that's a nice handy thing to have to one side. And of course in this case we want to do that. We want to — it's basically this agent is wrapping this tool call. And so when we're picking GPT-4o-mini and we're picking low, this is when, as of now, this costs two and a half cents every time we run this agent.

So let's run this agent. Let's ask for the latest AI agent frameworks in 2025. We will run that search and we will display the results and see what happens. It's running. And there we go. There are the results. It's come in nice markdown. Let's see — it says LangChain, LangGraph, CrewAI, Semantic Kernel, AutoGen, OpenAI Gym. That's uh, not exactly — I guess that's a reinforcement learning framework. It doesn't know about itself. It doesn't know about OpenAI Agents SDK. Amusingly, uh, Rasa is an older framework, and JADE for Java people, and, uh, yeah. So, uh, an interesting set of results, I'd say mixed accuracy, because I would argue that LangChain and Semantic Kernel aren't really agent frameworks, but certainly LangGraph, CrewAI, and AutoGen are very much there, and ones that we will be spending a week on each.

All right. But this is a perfectly pleasant search result, and it is the beginning of our deep research agent. And it's always worth taking a quick look at the trace in OpenAI. So click on this little useful link here. And up it comes. And here it is. The search agent is our current trace. If I open it up we'll see, sure enough, that the search agent was called. And it tells us over here the tool it used was web search. And we get a bit of information about the total number of tokens that it did. That's the instructions, the system prompt. That was the user prompt. And this comes back as the output. Just as we would expect, the trace has worked nicely. Now we can get on with the show.

</details>

---
*Source: Official Udemy lecture transcript (auto-captions, lightly cleaned). Notes in Hinglish for self-study.*
