# L44 — Day 4: Building an End-to-End Research Pipeline

> **Week 2 — OpenAI Agents SDK** · ⏱️ ~10m · 🎥 Lecture 44 of 131
> **Instructor:** Ed Donner · **Lecture ID:** 49820803

---

## 🎯 Ek Line Mein (TL;DR)

Is lecture mein Ed saare building blocks — **planner agent**, **search agent**, **writer agent (structured outputs)**, **email agent (function tool)** — ko **5 plain async functions** mein wrap karke ek complete **end-to-end deep research pipeline** chalata hai: query → search plan → parallel searches (**asyncio.gather**) → markdown report → HTML email.

---

## 📝 Hinglish Explanation (Detailed)

- **Send email tool (recap)** — wahi purana `send_email` function jo pehle use kiya tha:
  - **`@function_tool` decorator** lagao → SDK behind the scenes saara **JSON schema** generate kar deta hai (function ka naam, description, params).
  - Tool **SendGrid** se email bhejta hai — `subject` + `body` (HTML content) leta hai.
  - Ed reminder deta hai: apna **verified email** daalo, aur usko AI-generated research emails mat bhejo 😄.
  - Tool object print karke dikhata hai → ye ab ek **FunctionTool** hai with description etc. Agar samajh na aaye to **decorators** revise karo.

- **Email agent** — ab familiar pattern:
  - Instructions: *"You can send a nicely formatted HTML email based on a detailed report... use your tool to send ONE email... convert it into clean, well-presented HTML with a subject line."*
  - **Important shift:** Ed ab cheezein manually break nahi kar raha — agent ko **full discretion** de raha hai: subject line khud banao, email khud rewrite karo, HTML khud format karo. Ye **autonomy** wala mindset hai.
  - Model: **GPT-4o mini**, ek hi tool: `send_email`.

- **Writer agent (the researcher)** — yahan se "real meat" shuru:
  - Instructions: *"You are a senior researcher tasked with writing a cohesive report for a query"* — original query + research assistant ke initial findings milenge, pehle **outline** banao (structure & flow), phir **report generate** karo.
  - Output expectations: **markdown**, lengthy — **5 to 10 pages**, at least **1000 words**.
  - **Structured outputs** again: ek **`ReportData` pydantic model** (subclass of `BaseModel`) with 3 fields:
    - `short_summary` — 2-3 sentence summary
    - `markdown_report` — full final report
    - `follow_up_questions` — aage research karne layak suggested topics
  - Agent banate waqt **`output_type=ReportData`** — yahi specify karta hai ki structured output chahiye.

- **The 5 glue functions** — pipeline ka asli orchestration, sab **short, simple async functions**:
  1. **`plan_searches(query)`** — `Runner.run(planner_agent, query)` call karta hai → planner wapas deta hai **`WebSearchPlan`** (list of **`WebSearchItem`s**, har item mein query + reason). Kitne searches plan hue, wo print karta hai.
  2. **`perform_searches(search_plan)`** — yahan **asyncio shine** karta hai:
     - Har search item ke liye `search(item)` call karo → ye ek **coroutine** deta hai
     - Usko **`asyncio.create_task()`** se task banao
     - Phir **`asyncio.gather(*tasks)`** ko `await` karo → saare searches **parallel** mein chalte hain, results ek list mein aate hain.
  3. **`search(item)`** — search agent ko input dete waqt sirf query nahi, **reason bhi** pass karte hain. Yaad hai planner se reason kyun manga tha? Ek wajah ye bhi — search agent ko **context** milta hai ki ye search kyun ho rahi hai. Final output (summary) return hota hai.
  4. **`write_report(query, search_results)`** — writer agent run karo → `ReportData` milta hai.
  5. **`send_email(report)`** — email agent run karo → wo markdown report ko HTML email mein convert karke SendGrid tool se bhej deta hai.

- **Showtime — the final flow** (Ed is baar live type karta hai, Cursor ke autocomplete se ladte hue 😅 — "we're not just ruled by the machines"):
  ```python
  with trace("Research trace"):
      print("Starting research...")
      search_plan = await plan_searches(query)
      search_results = await perform_searches(search_plan)
      report = await write_report(query, search_results)
      await send_email(report)
  ```
  - **4 sequential awaits** — bas itna hi hai pura deep research orchestration!

- **Run hone par kya hua:**
  - Planner agent ne figure out kiya ki **3 searches** karni hain
  - Har search ke liye OpenAI ka **hosted WebSearchTool** (remote tool) use hua — searches parallel mein, seconds mein finish
  - Writer agent ne results synthesize karke **markdown report** banayi (`ReportData` format)
  - Email agent ne **subject line** khud socha, report ko **HTML email** mein convert kiya, aur bhej diya — Ed ko inbox mein email mil gaya. **End-to-end agentic pipeline complete!**

---

## 🔑 Key Concepts / Important Terms

| Term | Simple Hinglish Meaning |
|------|--------------------------|
| **End-to-end pipeline** | Query se lekar final HTML email tak — saare agents ek flow mein chained |
| **`@function_tool`** | Decorator jo Python function ko tool bana deta hai (JSON schema auto-generate) |
| **Email agent** | GPT-4o mini agent with full discretion — subject, HTML formatting, sab khud decide karta hai |
| **Writer agent** | "Senior researcher" — outline banao, phir 1000+ words ki markdown report likho |
| **`ReportData`** | Pydantic model: `short_summary` + `markdown_report` + `follow_up_questions` |
| **`output_type`** | Agent param jo structured output (pydantic schema) enforce karta hai |
| **`plan_searches`** | Planner agent run karke `WebSearchPlan` (searches ki list) laata hai |
| **`perform_searches`** | Saare searches ko `asyncio.gather` se **parallel** mein run karta hai |
| **Coroutine → Task** | `search(item)` coroutine deta hai, `asyncio.create_task` se concurrent task banta hai |
| **Reason field ka use** | Planner ka reason search agent ko context dene ke kaam aata hai |
| **Hosted WebSearchTool** | OpenAI ka remote/hosted search tool — agent ke through actual web search karta hai (paid) |
| **`trace()`** | Context manager — pura multi-step flow OpenAI traces dashboard pe ek trace mein dikhta hai |

---

## 💡 Backend Dev Ke Liye Note (aapke liye)

- **Ye pattern bilkul ek async service orchestrator jaisa hai** — jaise aap ek API handler mein `await db_fetch()` → `await asyncio.gather(*external_calls)` → `await render()` → `await notify()` karte ho. Yahan har step ek LLM agent hai, lekin orchestration logic **plain Python async/await** hai — koi magic framework DSL nahi. Fan-out/fan-in (`gather`) wahi hai jo aap parallel HTTP calls ke liye karte ho.
- **`output_type=ReportData` = response_model in FastAPI** — jaise FastAPI pydantic se response validate karta hai, waise hi SDK LLM output ko schema mein force karta hai. Downstream functions ko **typed object** milta hai, fragile string parsing nahi — agent chaining isi se reliable banti hai.
- **Hands-on lab:** is lecture ka code khud chalane ke liye **`Practical/lab4_deep_research.py`** run karo (is repo mein, `uv run` se chalta hai, **Groq pe FREE**). Note: hamare labs OpenAI ki jagah free **Groq** use karte hain (`OpenAIChatCompletionsModel` + `base_url` trick), aur lecture ke **paid cheezon** ke substitutes hain — OpenAI ke paid **WebSearchTool** ki jagah lab mein free **Wikipedia search tool** hai, **SendGrid** email optional/skip hai, aur OpenAI **tracing** dashboard Groq ke saath kaam nahi karega. Pipeline ka structure (plan → parallel search → write → deliver) bilkul same hai.
- **Decorator-as-schema-generator** appreciate karo: `@function_tool` runtime pe function signature + docstring inspect karke tool JSON banata hai — same idea jaise `@app.route` ya `@click.command` introspection se metadata nikaalte hain.

---

## 🧠 Takeaway (yaad rakho)

1. Complex agentic workflow = **agents (building blocks) + plain async functions (glue)** — orchestration ke liye sirf 4 sequential `await` calls kaafi the.
2. **`asyncio.gather`** se saare planned searches parallel mein — agentic pipelines mein latency ka sabse bada win yahi hai.
3. **Structured outputs (`output_type` + pydantic)** har step ke beech ka contract hai — planner → searcher → writer → emailer, sab typed data pass karte hain.
4. Agents ko **discretion do** (subject line, formatting, rewriting) — micromanage karne ki jagah instructions mein intent batao.
5. Planner ke **reason field** ka double use: LLM better planning karta hai + search agent ko context milta hai.

---

<details>
<summary>📜 Full English Transcript (original, click to expand)</summary>

Okay, next one is a boring one because you know it. Well, I've brought in the same send email tool that we used before. So this is — we're using the decorator, the function tool. If you remember, you use that decorator if you want to convert a function into something that can be a tool. And it will generate all of that JSON for you behind the scenes. So this is send email: a subject and a body, and it sends out an email with the given subject in the body. We're going to use SendGrid as before. Hopefully you still have your account handy and you have it in your env file. Remember to change this email. Let me change this to your verified email. And yes, and please do also change this one. Again, don't send me lots of emails with AI generated content, but by all means send me emails with your questions. Of course I always welcome them, but I don't welcome AI generated deep research things as much. Uh, so then uh, content would be, uh, the HTML version, and then we send the email exactly as before. That is our tool.

You don't need to see this, but I'm going to show it to you anyway. You remember that if I just print this — what's it doing here? If I just print this out, we should see that we get a function tool with a description and so on. And if you're not sure why this has happened, then do look up decorators. Make sure you understand how decorators work and how they're able to convert a function like this.

Okay, with that in mind, this is an email agent. This is all old hat to you. Now we've done this several times. The instructions are: you're able to send a nicely formatted HTML email based on a detailed report. You'll be provided with a detailed report, you should use your tool to send one email providing the report. Convert it into a clean, well presented HTML with a subject line. So you can see I'm no longer trying to break things out. I'm giving this agent full discretion to come up with a subject line, to rewrite the email, to do the whole lot, using GPT-4o mini, and we're providing it with the one tool to actually send the email. So that is our email agent. And that is something which is old news to you.

Okay. We're about to get real. And so I will, uh, take a pause for a second and then we will get into the real meat of the project.

Okay. So we have another agent — again that's going to use structured outputs. So this is the researcher. So: you are a senior researcher tasked with writing a cohesive report for a query. You'll be provided with the original query and some initial research done by a research assistant. You come up with an outline for the report that describes the structure and flow of the report, and then generate the report and return that as your final output. It should be in markdown, it should be lengthy, detailed — 5 to 10 pages of content, of at least a thousand words. Okay, so that has framed the situation.

Now we're going to use structured outputs. Again we're going to have a ReportData pydantic object, a subclass of BaseModel. It has a short summary, which we begin with — a short 2 to 3 sentence summary — the full markdown final report, and then some follow up suggestions: suggested topics to research further. And so this is an agent. It will take these instructions. It will use GPT-4o mini. The output type — this is where you specify that we're using structured outputs — the output type is the ReportData. And there we have our report writer. And this is our writer agent. And this is the final building block before we get to the actual flow through this project.

Okay. So it's crunch time. We have five functions for me to show you. But they're relatively simple. They're pretty straightforward. So here they are. I'm going to show you three and then two. The first three are the ones that are going to execute a search using the two agents that we defined before: the planner agent and the search agent. And these functions, you can see they're very short. They're very simple. Let me tell you what they each do.

Plan searches: this very simply calls Runner.run for our planner agent, passing in the query. And we make a query and that gets passed into the planner agent. Remember, the planner agent is the one that will then come back with a number of searches. So we'll then count how many searches there are and print that. And we will return that final output, which is in the form of that search list. That's what formatted it. Again, it is this thing here, the web search plan, a list of web search items. All right. Back we go.

Okay. So then the next function is perform searches. This is when we're actually going to do the searches. For each of these — now do you remember I showed you that asyncio a while ago? That was the great way that you can run things in parallel. Perfect time for it right now. So we're going to create a bunch of asyncio tasks to search for each item — for item in the results of these searches. This is the pydantic object — the searches field gives you the list of the search items. And for each item we're going to call search — the next function we'll talk about — we're going to call search. This gives you a coroutine, so we can turn that into a task. And then we can use this gather approach that I told you about — asyncio gather. If you then await that, it will run all of these tasks in parallel and the results will go into results. And then we will print finished. So hopefully I didn't lose you there. Basically all I'm saying is: we take the results from the planner and we just search for all of these things in parallel using the search agent.

And this is how we actually use the search agent. We give it an input. And what we're actually doing is we don't just tell it the query, we also tell it the reason that we're searching for that. Remember I said there's more than one reason why we asked for a reason — it's also so we can give some context here. And then we run the search agent and then we return the final output of the search. Okay. Hopefully you followed these three. If not, come back and look at these — they're such short functions that it should make sense.

And then finally, some housekeeping: two functions. One of them to write the report, one of them to send the email. Writing the report will use the writer agent — it will run that agent. The email agent is going to reconstitute the output in HTML. And then finally we will write an email using the email agent. And that will then complete the process. So I should run these to define these five functions. And now we should be ready for showtime.

All right. And if you're one of the people that doesn't like the way that I just execute code and talk to it — it's sort of lazy — then you're going to be happy. This time I will type the code so that we get to do this part together. So it is a moment of truth. We're going to say: with trace — research trace. Cursor is already filling it in. No, no luck for me. Well, I'm going to ignore what Cursor is saying here. I'm not looking at that. So we're going to print a message like "starting research". Sometimes Cursor is too good. All right, let's get rid of Cursor. No cheating. I'm not looking at Cursor saying search. What if I type something different? Uh, confuse Cursor. All right. Now search — that doesn't work. It still figures it out. All right. But there we go. It knows.

So the first thing we're going to do is have a variable called search plan, which is going to await planning the searches. So if you come up here, there is planning the searches. So that's the first step. We do that. All right. The next step is the search results — we're going to perform the searches. So we come up here, we perform the searches, passing in the search plan. That's the next step of this, which we also await. The next thing we need to do is actually run the report. So we await writing the report, passing in the query and the search results. And Cursor knows — as do you — you're already saying what we need to do next is send the email. And that really is it. And then I can print — all right, we will do something different to what Cursor suggests, to show that we have some autonomy here. We're not just ruled by the machines.

Okay, there we go. Let's kick this off. Let's have this running. So it's starting the research. It's planning the searches. It will perform the searches. And it's already finished. So it used an agent to figure out what three searches to do. And then for each of those, it used a remote, hosted tool from OpenAI to actually carry out that search. It got back all of the results. We're now using an agent to synthesize the results and turn it into a report. It's going to generate a report in markdown, and then it's going to turn that into an HTML email. So, um, we will let it do its thing. Let's just come back up. The final report is in this format, which has markdown as one of the parts of it. And that's the part — we're now doing the writing email. And it's in writing the email that it will both come up with a subject line, and it will also write it as an HTML email. And in a second, hopefully I will receive that email.

</details>

---
*Source: Official Udemy lecture transcript (auto-captions, lightly cleaned). Notes in Hinglish for self-study.*
