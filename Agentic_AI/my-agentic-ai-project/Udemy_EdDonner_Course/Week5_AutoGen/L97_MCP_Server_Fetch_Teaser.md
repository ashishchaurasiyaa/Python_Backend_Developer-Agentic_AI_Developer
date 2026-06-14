# L97 — Day 2: Headless Web Scraping — MCP Server Fetch

> **Week 5 — AutoGen** · ⏱️ ~8m · 🎥 Lecture 97 of 131
> **Instructor:** Ed Donner · **Lecture ID:** 49821613

---

## 🎯 Ek Line Mein (TL;DR)

Ed ek **MCP (Model Context Protocol) teaser** dikhate hain — **mcp-server-fetch** naam ka open-source MCP tool locally chala kar, AutoGen ke **`mcp_server_tools` wrapper** se uske tools nikaal kar ek **AssistantAgent** ko de diye, aur agent ne **headless browser** se edwarddonner.com scrape karke markdown summary bana di — full MCP deep-dive Week 6 me aayega.

---

## 📝 Hinglish Explanation (Detailed)

- **Pichle lecture ka correction/tip:** Ed pehle clarify karte hain ki agents ke "off track" jaane wali problem ko **smarter termination conditions** se control kar sakte ho. Sirf ek **hardcoded text** (jaise "APPROVE") agent response me dhoondhna risky hai — agar agent wo word casually bol de to team galat time pe ruk jayegi. **Exercise:** better termination conditions try karo (e.g., combine karna, max messages, structured signal).
- **Big drum roll — MCP teaser:** **MCP** asli topic **next week (Week 6)** ka hai, lekin kyunki ye "all the rage" hai, Ed ek chhota sa preview de rahe hain — bina detail me gaye, taaki next week ka show spoil na ho.
- **MCP kya hai (intuition level):** MCP koi **abstraction layer ya code library nahi** hai — ye bas ek **agreement / spec / protocol** hai: agar tum apna tool ek particular tarike se likhte ho, to **koi bhi LLM/model us tool ko discover aur call kar sakta hai**.
- **LangChain analogy:** LangChain ne apna ecosystem banaya — agar tum apni cheez ko **LangChain tool** me wrap kar do, to koi bhi LangChain/LangGraph user use kar sakta hai. **Anthropic** ne MCP ke saath kaha: glue code ki zaroorat hi nahi — bas function ek **spec** ke according likho, aur wo tool **kisi bhi model, kisi bhi ecosystem** ke liye available ho jata hai. Matlab MCP = LangChain-tools wala idea, but **zyada open** — kisi ek framework ka membership nahi chahiye.
- **"USB-C connector for AI":** Anthropic MCP ko aise describe karta hai — ek **agreed protocol** jisse models ko **tools** me plug kar sakte ho, aur **resources** me bhi (resources = RAG jaise use-cases ke liye context).
- **AutoGen ki khoobi:** Jaise AutoGen ke paas **LangChain tools ka wrapper** hai (pichle lecture me dekha), waise hi **MCP tools ka wrapper** bhi hai (`autogen_ext.tools.mcp`). Koi bhi MCP tool bahar available hai → AutoGen me directly use kar lo.
- **Code (poora extent bas itna hai):**
  - **AssistantAgent** + **OpenAIChatCompletionClient** (same as pehle).
  - `autogen_ext.tools` se MCP wala class import — Ed bolte hain **MCP ke saath kaam karne ke 2 tarike** hain (stdio vs SSE/HTTP transport), detail next week.
  - Tool: **mcp-server-fetch** — ek **open-source MCP server** jo tum download karke **locally apne computer pe** chala sakte ho. Ye headless mode me browser chala kar web pages **fetch** karta hai (Ed ke according Playwright-style headless browsing — Week 4 ke **Sidekick** jaisa hi kaam, bas **bina visible browser window ke**, "quietly behind the scenes").
  - Server se tools nikaal kar `fetcher` variable me daala → `tools=fetcher` AssistantAgent ko pass kar diya. **Bas, itna hi simple.**
- **Demo:** Agent ko task — "review the website edwarddonner.com, summarize what you learn, reply in markdown" (website koi bhi rakh sakte ho). Result: sahi summary ("technology enthusiast focused on coding and experimenting with LLMs"), **markdown me**, actual **LinkedIn link** ke saath.
- **Kyun cool hai:** Kisi aur ka likha tool (headless Playwright fetch) sirf isliye drop-in use ho gaya kyunki wo **MCP standard** follow karta hai. Aur MCP itna open hai ki **poori public community ka tools ecosystem** mil jata hai — websites/directories hain jahan se hazaaro MCP tools utha sakte ho — "LangChain ecosystem access, only a whole lot more."
- **Day 2 wrap-up recap:** multimodal ✅, structured outputs (`output_content_type`) ✅, LangChain tools ✅, **RoundRobinGroupChat teams** (briefly) ✅, aur MCP tools ka special-guest teaser ✅. Ye **AgentChat layer** ki last deep foray thi — **next time: Autogen Core**, underlying infrastructure layer.

---

## 🔑 Key Concepts / Important Terms

| Term | Simple Hinglish Meaning |
|------|--------------------------|
| **MCP (Model Context Protocol)** | Anthropic ka open standard/spec — tool ek particular tarike se likho to koi bhi LLM use discover & call kar sakta hai; koi framework lock-in nahi |
| **"USB-C connector for AI"** | MCP ki famous analogy — ek universal plug jisse models tools aur resources se connect hote hain |
| **MCP resources** | Tools ke alawa MCP ka doosra concept — context/data provide karna (RAG-type use cases) |
| **mcp-server-fetch** | Open-source MCP server jo locally chalta hai aur headless browsing se web pages fetch karta hai |
| **Headless browser** | Browser bina visible window ke background me chalna — Sidekick (Week 4) wala kaam, par "quietly behind the scenes" |
| **`mcp_server_tools` (autogen_ext.tools.mcp)** | AutoGen ka wrapper jo kisi bhi MCP server ke tools ko AutoGen tools me convert kar deta hai (`fetcher` list → `tools=fetcher`) |
| **2 ways of working with MCP** | MCP transports — stdio (local process) vs SSE/HTTP (remote) — detail Week 6 me |
| **Smart termination conditions** | Hardcoded text match pe rukne ke bajaye robust conditions use karo, warna agents galat time pe stop/never-stop ho sakte hain |
| **LangChain tools vs MCP tools** | Dono "tool packaging" ideas — LangChain ecosystem-specific, MCP open-to-everyone |
| **Autogen Core** | Agla topic — AgentChat ke neeche wali infrastructure layer (RoutedAgent, runtimes, messaging) |

---

## 💡 Backend Dev Ke Liye Note (aapke liye)

- **MCP = tools ka OpenAPI/Swagger moment:** Jaise REST APIs ke liye OpenAPI spec ne "describe once, any client can discover & call" enable kiya, waise hi MCP tools ke liye karta hai — schema-based **discovery + invocation contract**, glue code ke bina. LangChain tools = ek vendor SDK; MCP = vendor-neutral wire protocol.
- **mcp-server-fetch locally chalana = sidecar process pattern:** Tumhara agent ek **subprocess (stdio transport)** spawn karta hai aur usse structured messages exchange karta hai — bilkul jaise ek sidecar container ya local gRPC service. Isi liye "2 ways of working with MCP" hain: stdio (local child process) vs SSE/HTTP (remote service) — same dichotomy jo unix pipes vs network RPC me hoti hai.
- **Termination warning ko production lens se dekho:** hardcoded-string termination = magic string sentinel in a message queue — fragile. Structured output ya typed signal pe terminate karna = proper poison-pill/ack pattern.
- **Hands-on lab:** is lecture ka code khud chalane ke liye `Practical/lab2_primary_evaluator.py` run karo (is repo me, `uv run` se chalta hai, Groq pe free via `OpenAIChatCompletionClient` + `base_url` + `ModelInfo`). Difference: hamare lab me **MCP-fetch ki jagah simple httpx fetch tool** hai (real MCP Week 6 me aayega), aur AutoGen **0.7.5** hai (course 0.5.1, same API family).

---

## 🧠 Takeaway (yaad rakho)

1. **MCP koi library nahi, ek open spec hai** — tool ko spec ke mutabik likho, koi bhi LLM/framework use kar sakta hai ("USB-C for AI").
2. **AutoGen me MCP tools drop-in hain** — `autogen_ext.tools.mcp` wrapper se MCP server ke tools nikalo aur seedha `tools=` me AssistantAgent ko de do.
3. **mcp-server-fetch** locally chal kar headless web scraping deta hai — Sidekick jaisa kaam, bina browser window ke.
4. **Hardcoded text termination se bacho** — smarter/structured termination conditions use karo warna agent teams derail ho jati hain.
5. Day 2 (AgentChat) khatam — **next: Autogen Core**, the underlying infrastructure layer; full MCP deep-dive Week 6 me.

---

<details>
<summary>📜 Full English Transcript (original, click to expand)</summary>

And of course, I should have been clear on what I just said as I was, uh, waffling away about the problem with the agents going going, uh, off track — that you can use more intelligent termination conditions to make sure that this doesn't go awry and that you keep your agent interactions on rails. Don't just look for a hard coded piece of text in an agent response if you don't want to get yourself in trouble, right. Uh, there's an exercise for you. Okay.

But now, in the meantime, big drum roll — MCP is a topic for next week. But it is, of course, all the rage. And so I thought I'd give you a teaser, a little a little tiny sense of what it's like to work with MCP without going into any detail, because I don't want to spoil the show for next time, but let's just do a quick, quick bit of looking at MCP within Autogen.

Okay, so what is MCP? Well, again, I don't want to spoil it for next time, but but MCP amongst other things is just a nice, simple, elegant way that that we can package up tools so that different models can use those tools. It's like a — it's it's not an abstraction layer. It's not particularly code. It's just an agreement for a way. If you write tools in this way, then models — LLMs — can discover them and call them in many ways. If you think of it like with something like LangChain, there is an ecosystem and LangChain built some code and they built some wrappers — that's LangChain tools — and they say, if you can wrap your stuff in a LangChain tool, then anyone else writing LangChain or LangGraph will be able to use the tools that have been packaged this way.

And what Anthropic have done with MCP is they've said, well, actually, let's just go simpler than that. We don't necessarily need to have this glue code. We can just say, look, anyone, if you write a function a particular way, that's good enough — that as long as it conforms to a particular kind of spec, then that that can be a tool that we can make available to any model we want. So it's very similar to the LangChain idea. It's just more open. And rather than saying you need to be part of the LangChain LangGraph ecosystem, it's just saying, look, anyone can be part of the MCP ecosystem, anyone can use this. And Anthropic describes MCP as being like the USB-C connector for AI, for LLMs. It's just an agreed protocol, an agreed way that we can plug models into tools and also into into what they call resources, which is stuff like context for RAG. Um, so if this was just to give you some intuition for it — I didn't mean to explain it, because we will explain it next time, next week.

But, uh, one of the things that's great about Autogen is that not only do they give you a nice little, little wrapper so that you can use any LangChain tool, but they also give you a nice little wrapper so you can use any MCP tool. So if there's an MCP tool out there you can just use it in Autogen really, really easily, and that is what we're going to do right now.

And so let me take you through this. This is the whole extent of the code. Uh, we are using the assistant agent. We're using the OpenAI chat completion client. And from autogen tools, we're bringing in this class here. There are two different types of ways of working with MCP. And this is one of them. Uh, and we will talk about those next week, of course. And in particular, uh, we are going to be using a tool called MCP fetch. And what this, this — this is going to be running locally on our computers. So we're going to kick off this tool to run locally on our computers. And because it's been written a certain way, that tool is just a tool we can use from Autogen. So the key to MCP is that different people can write tools and as long as they write them a certain way, you can just use them out of the box. It's a bit like saying people could, like, write a LangChain tool and you can just use it out of the box. But MCP is just more open, available to any ecosystem, not just the LangChain ecosystem.

So mcp server fetch is an example of a tool that is open source and available, and that you can just download and run it yourself. And that is what this thing here does. It runs it locally, and it is a tool which actually runs the Playwright browser in a headless mode and allows it to go and fetch web pages. So it's doing something a bit similar to what we worked on with Sidekick last week, but it's just doing it not not in a way that brings up the browser, but just does it quietly behind the scenes — headless, as they call it. And it will run that and then it will, it will, uh, get those tools and it will put those tools into this thing called fetcher. And we can just provide fetcher in as our tools. That's — it's just as simple as that.

And so, uh, yeah, basically what we're doing here is that we're using a public online tool available that runs Playwright browser locally and uses that to scrape the web. And we're making that tool available to our assistant. And what we're going to ask our assistant to do is review the website edwarddonner.com — but you can change that to any website that you want — and summarize what you learn and reply in markdown. So without further ado, let's kick this off. And again, the takeaway for you is just to show — and there we go. There I am. Look at that. A technology enthusiast with a focus on coding and experimenting with LLMs. Sounds about right. Uh uh. And oh look, it's got a link. I wonder if that's an actual link to my LinkedIn profile. It almost certainly is. Uh, these these, uh, things are amazing at — it's replied in markdown, and I'm sure it's got the right, the right links.

Uh, so, um, the, the — this is cool. And the reason it's cool is that we've just used a tool that someone else has written for, for running Playwright in a headless way. And we have just incorporated that tool because that tool uses this, this open standard, this standard called MCP. We're able to just drop that tool in and use it from within Autogen. So just like we could use a LangChain tool from within Autogen, we can use an MCP tool — anyone that's written a tool that conforms to the MCP standard. And the cool thing about MCP is that it's such an open standard that anyone can write tools, and there are websites where you can get access to lots and lots of these tools. So it's like saying, we've got access to the LangChain ecosystem, only it's a whole lot more. It's this massive open source, public community ecosystem of tools. Anyone that writes tools that conforms to the MCP standard, you can then access just like this, and you can do it from within Autogen in this way and immediately have access to any of them.

So it's only meant to be a teaser. I wanted to show you how you can use MCP tools. Don't worry if you don't really understand. Just get an idea and we'll we'll go through MCP, and then you can come back once you fully understand it and use lots and lots of MCP tools right here from Autogen.

And so there we have it. We went multimodal. We looked at structured outputs. We used tools from LangChain. We saw briefly teams — the round robin teams. And you can experiment with more should you wish. And then we introduced a special guest in the form of MCP tools — your teaser, your preview that we will come back to shortly. And that wraps up day two of Autogen. And it is the, the — probably the — our last deeper foray into Autogen agent chat. Next time we switch to Autogen core, the underlying infrastructure part. I'll see you then.

</details>

---
*Source: Official Udemy lecture transcript (auto-captions, lightly cleaned). Notes in Hinglish for self-study.*
