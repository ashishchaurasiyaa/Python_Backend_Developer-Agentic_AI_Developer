# L43 — Day 4: Building a Planner Agent — Using Structured Outputs with Pydantic

> **Week 2 — OpenAI Agents SDK** · ⏱️ ~8m · 🎥 Lecture 43 of 131
> **Instructor:** Ed Donner · **Lecture ID:** 49820797

---

## 🎯 Ek Line Mein (TL;DR)

Is lecture me hum deep-research system ka **Planner Agent** banate hain — ek aisa agent jo user ki query lekar **3 web searches plan** karta hai, aur apna output free text me nahi balki **pydantic BaseModel** (`WebSearchPlan` → list of `WebSearchItem`) ke roop me deta hai via **structured outputs** (`output_type`).

---

## 📝 Hinglish Explanation (Detailed)

- **Planner Agent ka role:** Deep research pipeline me ye pehla agent hai — iska kaam hai ek **query** lena aur decide karna ki us query ka best answer dene ke liye **kaun-kaun se web searches** run karne chahiye. Ye khud search nahi karta, sirf **plan** banata hai.

- **Searches ki count = 3 (cost control):**
  - Har OpenAI hosted **WebSearchTool** call ka cost **~2.5 cents** hai, isliye Ed ne search count **3** rakhi hai.
  - Pehle Ed ne 10 rakha tha — zyada searches = **better results**, but bill bhi badhta hai. Personal preference hai: 3 se start karo ($0.10–$0.20 ka kharcha), maza aaye to half a dollar tak "splash out" karke ek comprehensive result lo.

- **System prompt (instructions) bilkul simple:** *"You are a helpful research assistant. Given a query, come up with a set of web searches to perform to best answer that query. Output 3 terms to query for."* — bas itna hi. Agent ka naam **planner** isi kaam se aata hai.

- **Structured outputs with pydantic — main concept:**
  - Ek class banao jo **`BaseModel`** (pydantic) ki subclass ho — ye ek **schema** ki tarah kaam karti hai jisme hum model se bolte hain ki "isi structure me jawab do".
  - **`WebSearchItem`**: do fields — `reason: str` aur `query: str`.

- **Field ke neeche docstring/comment = model ko instructions (naya trick!):**
  - Har field ke **just neeche jo description/doc-comment** likhte ho, wo structured outputs ke through **model tak actually pahunchta hai**.
  - Matlab model ko pata hota hai ki **kyun** wo field populate kar raha hai. Kal (Day 3) ye trick use nahi kiya tha — ab ye bhi toolkit me hai.

- **`reason` field pehle kyun? — Chain of Thought effect:**
  - `query` ke saath `reason` maangne ki ek badi wajah: ye **reasoning-style behaviour** trigger karta hai — effectively **chain-of-thought prompting** hi hai.
  - **Reason ko query se PEHLE** maangne se model "sochta hua" dikhta hai, aur side effect ke roop me **better queries** milti hain.
  - **Underlying reality:** models me koi "humanity" nahi — ye sirf **next token prediction** hai. Agar model pehle *reason* ke tokens predict karta hai, to baad me *query* ke tokens us reason ke **consistent** hone ki likelihood badh jaati hai → zyada **coherent output** jo aapke kaam ka hota hai.

- **`WebSearchPlan` — nested structure:**
  - Dusra pydantic model: ek hi field `searches`, jo **`list[WebSearchItem]`** hai.
  - Field annotation kehti hai: *"A list of web searches to perform to best answer the query."* — ye bhi model ko jaata hai.

- **Planner agent banana:**
  - `Agent(name="planner_agent", instructions=..., model="gpt-4o-mini", output_type=WebSearchPlan)`
  - **`output_type`** hi wo jagah hai jahan hum structured outputs specify karte hain — agent ko bolte hain: free-form **natural language text** generate mat karo, balki **`WebSearchPlan` type ka object** banao.

- **"Magic" demystified — behind the scenes sirf JSON hai:**
  - "LLM Python object kaise generate karta hai?" — jab bhi aisa magical lage, samajh lo **JSON** chal raha hai backstage.
  - Pydantic class **JSON schema** me convert hoti hai, model ko prompt me bola jaata hai "tumhara response is JSON ke conform kare", model JSON generate karta hai, aur SDK us JSON ko **pydantic object me populate** kar deta hai. Bas — kuch magical nahi.

- **Run karke dekha:**
  - Query: *"latest AI agent frameworks in 2025"* — koi searching nahi hui, sirf planner ne **`WebSearchPlan` object** return kiya jisme `searches` list me 3 `WebSearchItem` the.
  - Examples: (1) reason: recent developments/releases find karna → query: "latest AI agent frameworks 2025", (2) reason: industry-specific/academic research explore karna → query: "emerging AI agent frameworks", (3) reason: conferences/publications/announcements pe updated rehna → query: "AI frameworks conferences announcements 2025".
  - Profound nahi, but **perfectly plausible** plan — aur structured outputs ka ek solid real use-case.

---

## 🔑 Key Concepts / Important Terms

| Term | Simple Hinglish Meaning |
|------|--------------------------|
| **Planner Agent** | Deep-research ka pehla agent — query lekar 3 web searches **plan** karta hai (khud search nahi karta) |
| **Structured Outputs** | Model ko free text ki jagah ek **fixed schema (pydantic object)** me respond karwana |
| **`output_type`** | `Agent(...)` ka param jahan pydantic class dete ho — SDK model ko us schema me force karta hai |
| **`BaseModel` (pydantic)** | Schema define karne ka base class — fields + types + descriptions |
| **`WebSearchItem`** | `reason: str` + `query: str` — ek planned search ka unit |
| **`WebSearchPlan`** | `searches: list[WebSearchItem]` — poora search plan, nested structure |
| **Field docstring/description** | Field ke neeche likha comment **model ko bheja jaata hai** — model samajhta hai field kyun bharna hai |
| **Chain-of-Thought (CoT) via `reason`** | `reason` ko `query` se pehle maangne se model "soch ke" better queries deta hai |
| **Next token prediction** | Models ka asli mechanism — reason ke tokens pehle aane se query ke tokens consistent ban jaate hain |
| **JSON behind the scenes** | "Model object banata hai" = model schema-conforming **JSON** generate karta hai, SDK object me parse karta hai |

---

## 💡 Backend Dev Ke Liye Note (aapke liye)

- **Pydantic aap roz use karte ho** — FastAPI me request/response models exactly yahi hain. `output_type=WebSearchPlan` ko aise socho jaise FastAPI ka `response_model=` — fark itna hai ki yahan **LLM** ko schema bheja jaata hai (JSON schema ke roop me, OpenAI ke constrained decoding / json_schema response format ke through) aur SDK validate + parse karke typed object deta hai. Field descriptions = OpenAPI docs jo **machine (LLM) padhti hai**, sirf humans nahi.
- **Field ordering matters — ye API design se alag hai:** REST response me field order irrelevant hota hai, but LLM output me `reason` ko `query` se **pehle** rakhna output quality badalta hai (autoregressive generation = pehle wale tokens baad walon ko condition karte hain). Schema design yahan **prompt engineering** ka hissa hai.
- **Typed contracts between agents:** Planner ka `WebSearchPlan` output agle agent (search agent) ka typed input banega — ye microservices ke beech shared DTO/protobuf contract jaisa hai. Free text parse karne ki jagah structured handoff = reliable multi-agent pipeline.
- **🧪 Hands-on lab:** is lecture ka code khud chalane ke liye ye lab run karo — `Practical/lab4_deep_research.py` (is repo me, `uv run` se chalta hai, **Groq pe free**). Note: hamare labs OpenAI ki jagah **FREE Groq** use karte hain (`OpenAIChatCompletionsModel` + `base_url` trick), aur lecture me jo **paid WebSearchTool (~2.5 cents/search)** hai uski jagah lab4 **free Wikipedia search tool** use karta hai — to Ed wali cost-tension ($0.10 vs $0.50) hamare setup me hai hi nahi, searches free hain.

---

## 🧠 Takeaway (yaad rakho)

1. **Planner Agent** = query → 3 planned web searches; `output_type=WebSearchPlan` se output ek **typed pydantic object** hota hai, free text nahi.
2. Pydantic field ke neeche likhi **description model tak pahunchti hai** — ye documentation nahi, **prompt ka hissa** hai.
3. **`reason` ko `query` se pehle** maangna = built-in chain-of-thought → better, more coherent queries (next-token-prediction ka side effect).
4. Structured outputs me **koi magic nahi** — schema → JSON schema → model JSON generate karta hai → SDK pydantic object me parse karta hai.
5. Search count chhota rakho (3) cost control ke liye — hosted WebSearchTool **~2.5 cents/search** charge karta hai (hamari labs me free Wikipedia tool hai, ye tension nahi).

---

<details>
<summary>📜 Full English Transcript (original, click to expand)</summary>

Okay. So now we're going to work on another agent. And we're going to make heavier use of structured outputs than we did last time. So the agent in particular that we're going to work on, we're going to call the planner agent. This is the one that's going to be responsible for taking a query and coming up with a handful of searches that it should run based on that query in order to do some deep research. Now, I'm going to keep the number of searches small to three searches because as I say, it's two and a half cents for each search. And I don't want to add up to some big old bill. When I first did this, I had that at ten. So you certainly can have it at bigger numbers. You obviously get better results if you do that, and it's very much a personal preference thing. Run it with three to start with. See you know your cost $0.10, $0.20. And if you're enjoying yourself then you know splash out, spend half a dollar and get one really good comprehensive result. Okay. So we're going to keep it on three.

So the instructions — what is the system prompt we're going to use here? You are a helpful research assistant. Given a query, come up with a set of web searches to perform to best answer that query output. And then the number three terms to query for. So that hopefully is super simple. We're just building an agent that is going to, given some sort of query, come up with a bunch of things you would search the internet for in order to research that query, and we're calling that the planner. So keep that in mind because then everything is going to click into place.

So now we use structured outputs. Remember this. This is where you have a class that is a subclass of this thing called base model from pydantic. And that means that we're going to use it as like a schema. We're going to use it to describe a structure, which we will later ask a model to return information in. And we in the case of a web search item, we're going to have a reason and a query. And the reason is a string, and the query is a string, and the doc string that we have right here underneath this is this is super important. And by by adding this documentation, by annotating these fields with this comment right underneath them, we ensure that that that information is actually provided. That's as part of structured outputs. That is part of the information that's provided to the model. So it knows why it's populating these fields. So this is another good trick. We didn't do that yesterday. So so now you've you've got this in your toolkit as well.

Now one other small point. There's various reasons why you might ask for a reason as well as just the query. But one of them is that this does actually result in sort of reasoning style behavior. This is very similar to to what people call chain of thought prompting. I guess it is chain of thought prompting, but by asking the model to output its rationale for why that search is important, and actually by asking for that first before the query itself, you encourage the model to be sort of apparently thinking through, and as a result, you tend to get better outputs. You get better queries, just as a side effect of asking for a rationale first. And I've said it before, but you always have to come back to remembering that while we try and treat models like they're like there's a bit of humanity to them, this is just a strange side effect of great next token prediction, because it's predicting the most likely next tokens. That's all these models are doing. If you ask it to start predicting tokens reflecting a reason, then when it starts to predict tokens reflecting the query, it is more likely to be consistent with that reason, and it ends up with this very coherent output that just makes more sense. That has a higher likelihood of being what you're after. So another those little sidebars, and I do have a bunch of YouTube videos that clarify that more, but it's so important to keep that in your mind because it really helps figure out what works well with these kinds of prompts.

All right. So this is a pydantic object with a reason and a query. And now we've got another one called Web Search plan. So this was web search item — a web search plan is a list of web search items in a field searches. So this is an object which has one field searches. And that is a list of these guys. And you can see it says they're a list of web searches to perform to best answer the query, a list of web searches to perform to best answer the query. And that is what goes there. And this annotation is associated with this field searches. Okay, hopefully you are with me.

So then we now create our planner agent. It is an agent that's named planner agent. Its instructions are these ones right here. The model is GPT-4o mini and the output type — remember this is where we specify structured outputs. We tell the planner agent that it shouldn't output in text like these things normally do. It shouldn't just create generate natural language in the form of text, but rather it should build an object of type web search plan, which means it's an object with one field searches, which has a list of items that looks like this.

And remember, as another sidebar, keep in the back of your mind when I say that we're going to tell the model to create an object. Maybe that all sounds a bit magical. Like how does a model, how does a large language model, a transformer architecture, know to generate objects? Python objects. Remember, any time you hear magical stuff like that, it usually means we're talking about JSON behind the scenes. And that's exactly what this is. What happens is that this is turned into a bunch of JSON, and the model is prompted and it says your response should conform to this JSON. Here is how it needs to look. And as a result, the model generates that JSON and it gets populated into an object of this type. That's that's the end of it. There's nothing magical about it.

All right. We should now run this and see it working. Here we go. Let's do it. We run this, and now we're going to say the same. The same thing that before we just did an internet search on latest AI frameworks in 2025, what we're now going to do is carry out. We're not going to do any searching at all. We're just going to use this planner agent to come up with three web searches that would be relevant, and we would want it to respond with an object of type web search plan. So let's see what we get if we run it and print the result. So what we get back is an object which has a field searches like that. And that field is a list. Good. And it's a list of things called web search items. Great. And a web search item should have a reason and a query — reason: to find the most recent developments and releases in AI agent frameworks for 2025. And the query is just latest AI agent frameworks 2025. Okay, fine. That doesn't seem particularly profound, but it seems perfectly reasonable. The next one to explore industry specific or academic research. And the query is emerging AI agent frameworks. And the next one is to be updated with major conferences, publications or announcements. AI frameworks. Conferences. Announcements 2025. Fair enough. Seems like a perfectly plausible, reasonable way of doing it. I'm not sure I would have done that last one, but. But who's to say whether I would have done it better or GPT-4o mini is going to do it better. But that is the planner at work and you're seeing structured outputs used very well there.

</details>

---
*Source: Official Udemy lecture transcript (auto-captions, lightly cleaned). Notes in Hinglish for self-study.*
