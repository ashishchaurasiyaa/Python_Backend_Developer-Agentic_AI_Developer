# L57 — Day 2: Web Search — Knowledge Cutoff Problem

> **Week 3 — CrewAI** · ⏱️ ~6m · 🎥 Lecture 57 of 131
> **Instructor:** Ed Donner · **Lecture ID:** 49821175

---

## 🎯 Ek Line Mein (TL;DR)

Financial researcher crew ka report **2023 ka stale data** de raha tha kyunki LLM ki **knowledge cutoff** wahi tak thi — fix sirf 2 lines ka: **`SerperDevTool`** import karo aur researcher agent ki **`tools=[...]`** list me pass kar do, ab crew **live Google search** karke 2025 ka fresh report banata hai.

---

## 📝 Hinglish Explanation (Detailed)

- **Pichle run ka recap:** Second agent (report writer) ne Tesla pe summary likhi thi **first agent (researcher) ke output ko apne context me leke** — yahi sequential process ka core idea hai: ek task ka output agle task ke context me inject hota hai.
- **Problem spot hui:** Report me likha tha *"as of October 2023"* aur *"key financial metrics Q3 2023"* — yaani data **purana** tha. Reason: research **DeepSeek** model ne ki thi, aur DeepSeek ki **last training 2023** me hui thi. LLM apni **knowledge cutoff** ke baad ki duniya nahi jaanta — ye har pure-LLM pipeline ki fundamental limitation hai.
- **Fix ka plan = Tool dena.** Is week ka bada theme yahi hai — agents ko **tools** dena. Aur CrewAI me ye surprisingly easy hai.
- **Step 1 — Import:** `crew.py` (jahan crew define hota hai) me ek naya import:
  ```python
  from crewai_tools import SerperDevTool
  ```
  **`SerperDevTool`** CrewAI ka built-in tool hai jo **Serper.dev** account use karke **Google lookups** karta hai. (Cursor ne autocomplete se khud hi suggest kar diya — "clever old Cursor".)
- **Step 2 — API key:** Apni **`SERPER_API_KEY`** ko **`.env` file** me daalna zaroori hai (Serper free credits deta hai sign-up pe).
- **Step 3 — Sirf researcher ko tool do:** Ed ka point — tool **selectively** assign hota hai. Sirf **researcher agent** ko search chahiye, writer ko nahi. To bas researcher ke `Agent(...)` me:
  ```python
  tools=[SerperDevTool()]
  ```
  Instance banao, `tools` list me pass karo — **bas itna hi**. "It is really rather easy."
- **Model swap:** Speed ke liye researcher ka model **DeepSeek se OpenAI `gpt-4o-mini`** pe switch kiya (`agents.yaml` me sirf model string badli — YAML config ka fayda, code untouched).
- **Run:** Terminal me project directory (`financial_researcher`) me jaakar **`crewai run`**. Logs me dikhta hai: *"Search the internet with Serper"* — multiple searches fire ho rahi hain ("Tesla latest news today"), aur results me **2025** dates aane lagti hain. Promising!
- **Result:** Report writer (jo **Groq** pe chal raha hai) ne **early-2025 ka fresh report** generate kiya — Tesla ki recent news ke saath, clear aur accurate. Knowledge cutoff problem **solved**.
- **Do takeaways jo Ed highlight karta hai:**
  1. **Output genuinely useful hai** — agar tum khud 10–15 min internet search karke info synthesize karte, to lagbhag aisa hi report banta. Ye "proper work" hai.
  2. **Banane me kitna aasaan tha** — couple of CLI commands, **YAML files me plain English** me agents/tasks ke objectives, aur ek tool pass karna. Bas.
- **Cost angle:** OpenAI ke hosted web-search ka **2.5 cents per lookup** vs Serper ke **free credits** — ye pura run **zero cost** me hua.
- **Homework:** Khud try karo, alag models experiment karo (Ollama users free open-source models try karein), backstories/instructions me changes karke dekho kya farak padta hai, aur search-based quick agent projects banao. Next lecture me CrewAI ke **advanced features** aayenge.

---

## 🔑 Key Concepts / Important Terms

| Term | Simple Hinglish Meaning |
|------|--------------------------|
| **Knowledge Cutoff** | Wo date jahan tak LLM ki training data jaati hai — uske baad ki duniya model ko pata nahi (DeepSeek ke liye 2023) |
| **SerperDevTool** | `crewai_tools` ka ready-made tool jo Serper.dev API se Google search karta hai |
| **Serper.dev** | Google Search ka cheap/free API wrapper — `SERPER_API_KEY` `.env` me daalo |
| **`tools=[...]`** | Agent constructor ka param — jis agent ko ye list doge, sirf wahi tool use kar payega |
| **Selective tool assignment** | Har agent ko har tool mat do — researcher ko search, writer ko kuch nahi |
| **Context passing** | Sequential process me Task 1 ka output Task 2 ke LLM context me automatically jaata hai |
| **`crewai run`** | Project root se crew execute karne ki CLI command |
| **Free credits vs paid lookup** | Serper free credits vs OpenAI ~2.5¢/search — hobby projects ke liye Serper jeet gaya |

---

## 💡 Backend Dev Ke Liye Note (aapke liye)

- **Tool dena = dependency injection jaisa hai:** `Agent(tools=[SerperDevTool()])` bilkul waise hi hai jaise aap kisi service class me ek client inject karte ho. Framework tool ka **schema LLM ko expose** karta hai aur function-calling loop khud handle karta hai — aapko sirf instance pass karna hai.
- **Knowledge cutoff ko RAG vs Tool lens se dekho:** stale-data problem ke 2 classic fixes hain — (a) **RAG** (apna data vector DB me) ya (b) **live tool call** (search API). Ye lecture option (b) hai — jab data "internet pe fresh" ho to search tool > RAG.
- **Least-privilege principle yahan bhi:** sirf researcher ko search tool milta hai, writer ko nahi — waise hi jaise aap DB write-access sirf usi microservice ko dete ho jise chahiye. Kam tools = kam confusion = LLM ke better tool-choices.
- 🧪 **Hands-on lab:** is lecture ka code khud chalane ke liye `Practical/lab2_financial_researcher.py` run karo (is repo me, `uv run` se chalta hai, **Groq pe free via LiteLLM**). Note: hamare labs course se thoda alag hain — self-contained code-style (YAML scaffolding nahi), aur **SerperDev ki jagah free Wikipedia search tool** use kiya hai (API key ki zaroorat nahi) — concept wahi hai: agent ko `tools=[...]` me search tool do, knowledge cutoff bypass.

---

## 🧠 Takeaway (yaad rakho)

1. LLM ki **knowledge cutoff** ke baad ka data chahiye? Use **tool** do — model badalne se problem solve nahi hoti.
2. CrewAI me web search = **2 lines**: `from crewai_tools import SerperDevTool` + agent me `tools=[SerperDevTool()]`.
3. **`SERPER_API_KEY`** `.env` me hona chahiye — Serper free credits deta hai, OpenAI ka hosted search ~2.5¢/lookup hai.
4. Tools **selectively** assign karo — sirf us agent ko jo actually use karega (researcher haan, writer nahi).
5. Sequential crew me **Task 1 ka output Task 2 ke context me** jaata hai — isliye fresh research milte hi report bhi fresh ho gayi.

---

<details>
<summary>📜 Full English Transcript (original, click to expand)</summary>

And of course, the key point for us to have focused on here is that this second agent that did the summary of the research report on Tesla was taking advantage of the output from the first agent, because that was included in its context. And that's how it was able to give what it gave. And you'll note, if we look into this, that it's as of October 2023. And that's a bit disappointing because that's clearly not right now — a key financial metrics Q3 2023. And yeah, we're not super happy about that. And that is, of course, because we're relying on the context, on the knowledge cutoff from DeepSeek that did our research, and DeepSeek didn't have more, was last trained back in 2023 and doesn't have more recent information, which is unfortunate, but something that we can now fix.

So the way we're going to fix it is by adding in a tool, which is the big plan for this week. And it's going to be quite easy. So we do that by going back. Let's close this and go back to the other crew module which is where we define our crew. And we are going to add another import here. We're going to import from crewai_tools. And yeah, there's not going to be much of a job for us in the not too distant future. So yes indeed, clever old Cursor knows that we want the SerperDevTool here, which is indeed what we want, which is a tool from CrewAI that's able to do Google lookups using our Serper.dev account. And so you need to put your SERPER API key into the ENV file.

But now is the challenging, the difficult task of giving the researcher the ability to use that tool. That's what we want to do. And the way we're going to do that is we're going to say that we only want our researcher tool to have it. So it's not difficult at all. It is really rather easy. We simply create an instance of the SerperDevTool, and we pass that in in this tools list right here. That's all it will take. I save that and we should be good to go. Maybe we'll go back to models, though, and pick a different model. Let me see. We're going to go back to agents. And why don't we just use OpenAI GPT-4o mini so that we have a faster time of it?

Okay, let's give this a shot. Let's bring up our terminal. Let's exit that one actually. Let's just start again. I could have typed clear. We go into the third directory into crew. We go into our financial researcher directory and now we type crewai run. And we're hoping now that it's going to go and look up using that tool. It's going to look up Google about Tesla. And we're going to get some information. Financial researcher in progress. There's something happening here. There's lots happening. Search the internet with Serper. You can see it's doing its stuff. Plenty of searches happening. Tesla latest news today. I see 2025 appearing in the search results. This is promising. This is good news, but we'll soon see.

So the researcher is still working. It's now on the report writer. We're now talking to Groq. And here is the summary. Here is the report. And it's great to see we do indeed have a report as of early 2025. And we've got the most recent news from Tesla — hasn't done as brilliantly as usual in the last month or so, in the last few weeks, including. It's definitely got relevant recent information in this report. And it is, of course, a clear and accurate report. And, you know, it's fantastic to see this stuff.

And I guess the usual things for you to appreciate. One is that this is actually a high quality output. This is something that would genuinely, legitimately be useful. If you spent about ten minutes, 15 minutes yourself searching the internet, doing some searches, gathering some information, synthesizing it into an email like this, you probably would come up with something quite similar. It's proper work that's been done with a good output. And the other part of this is how easy it was to build this whole infrastructure. Thanks to Crew, thanks to just a couple of commands, building this and then writing in plain English in these YAML files our objectives for our couple of agents and tasks, and then just giving it the tool, it was able to handle all of this. And unlike OpenAI's costs of 2.5 cents per lookup, these costs have been coming out of our free credits. And so this has cost us nothing.

Okay. Well, I hope you enjoyed that and I hope you've done it yourself and had a similar outcome. And I will now see you for the wrap up. Well, I hope you enjoyed that. And you've tried it yourself and experimented with some different models. If you're using Ollama, experiment with some different free open source models, try messing around with the instructions and the backstories and see what it takes, what sorts of differences you can make, and try other kinds of quick agent projects that involve using searches. And you're getting more and more familiar with Crew. And I imagine, like me, that you quite enjoy using CrewAI as well. It has a lot to love. All right, next time we're going to take this project a step further, and we're going to experiment with some of the more advanced features of Crew. See you then.

</details>

---
*Source: Official Udemy lecture transcript (auto-captions, lightly cleaned). Notes in Hinglish for self-study.*
