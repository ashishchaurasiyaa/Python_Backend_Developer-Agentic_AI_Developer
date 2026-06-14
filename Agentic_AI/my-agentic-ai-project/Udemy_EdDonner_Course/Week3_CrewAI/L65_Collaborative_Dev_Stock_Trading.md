# L65 — Day 5: Collaborative AI Agent Development — Stock Trading

> **Week 3 — CrewAI** · ⏱️ ~8m · 🎥 Lecture 65 of 131
> **Instructor:** Ed Donner · **Lecture ID:** 49821237

---

## 🎯 Ek Line Mein (TL;DR)

Is lecture me Ed **engineering team crew** ka **crew module** (`crew.py`) complete karta hai — 4 agents (**engineering lead, backend engineer, frontend engineer, test engineer**), jisme backend aur test engineers ko **Docker-sandboxed code execution** milta hai — aur assignment deta hai ek **stock trading account management system** banana, jo Week 6 ke trader-agents project me reuse hoga.

---

## 📝 Hinglish Explanation (Detailed)

- **Crew module setup:** Ed `crew.py` (crew module) me jaata hai aur scaffolding ka saara extra "gunk" delete kar deta hai — sirf **YAML files se hook-up** wala part rakhta hai. Phir `@agent` decorators ke saath agents define karna shuru karta hai.
- **Agent 1 — Engineering Lead:** Cursor (AI editor) auto-suggestions deta hai, lekin perfect nahi — engineering lead ko **code execution ki zaroorat NAHI** hai, kyunki uska kaam sirf **design** karna hai, code run karna nahi. Isliye Ed `allow_code_execution` hata deta hai.
- **Agent 2 — Backend Engineer:** Yahan ulta — Cursor ne miss kiya ki is agent ko **code execution chahiye**. Ed enable karta hai:
  - `allow_code_execution=True`
  - `code_execution_mode="safe"` → code **Docker container** me chalega (safety ke liye)
  - `max_execution_time` → kuch **minutes** diye (kaam karne ka time)
  - `max_retries=5` → 5 baar try karega fail hone par
- **Agent 3 — Frontend Engineer:** Ye agent **frontend (Gradio UI) code likhega, lekin execute NAHI karega** — kyunki Docker container ke andar Gradio UI launch karna "a whole different ball game" hota (UI container me khulta, dikhta nahi). So sirf creation, no execution.
- **Agent 4 — Test Engineer:** Isko **unit tests likhne AUR run karne** dono chahiye — so code execution enabled, couple of minutes execution time, aur **5 retries**.
- **Tasks define karna:** `@task` decorators ke saath — design task, code task, frontend task, test task. Cursor pattern samajh ke baaki tasks auto-suggest kar deta hai (kyunki YAML me already defined hain).
- **Crew definition — vibe coding warning:** Jab Cursor ko crew banane diya, usne "disaster" generate kiya — **LLMs ka common problem: too much code generate karna**. Ed kehta hai log usse problems bhejte hain jo clearly LLM-generated bloated code hota hai — LLMs "err on the side of more". Correct version simple hai:
  - `agents=self.agents` (decorators ki wajah se auto-collected — saare agents list out karne ki zaroorat nahi)
  - `tasks=self.tasks` (same auto-collection)
  - `process=Process.sequential`
  - `verbose=True`
  - Method ka naam conventionally `def crew()` hota hai (`@crew` decorator ke saath).
- **`main.py` / run function:** Usual boilerplate delete karke simple run function — 3 input variables: **`requirements`** (assignment text), **`module_name`**, **`class_name`**. Phir `EngineeringTeam().crew().kickoff(inputs=...)` — decorated `crew` method ko call karke kickoff.
- **The Assignment — Trading Simulation Account Management System:** Requirements:
  - Account **create** karna, funds **deposit/withdraw** karna
  - Shares **buy/sell record** karna (quantity ke saath)
  - **Portfolio ki total value** aur initial deposit se **profit/loss (P&L)** calculate karna
  - Kisi bhi time par user ki **holdings** aur **P&L report** karna
  - User ke saare **transactions list** karna
  - **Validations:** negative balance withdrawal block, afford na kar sakne wale shares buy block, jo shares hai hi nahi unka sell block
  - System ko ek function **`get_share_price`** milta hai jo current price return karta hai — test ke liye 3 shares ki **fixed price** wali implementation included.
- **Why THIS challenge? Two-for-one:** Week 6 (last week) me hum **agent traders** banayenge — **OpenAI Agents SDK + MCP** use karke — jo live financial markets monitor karke trading decisions lenge. Uske liye ek **lightweight account/portfolio management framework** chahiye. Off-the-shelf frameworks **heavyweight backtesting frameworks** hain — koi simple lightweight option nahi mila. So idea: **AI se hi build karwa lo!** Hamari apni engineering crew ye framework banayegi — is week ka project bhi complete, aur Week 6 ke liye head start bhi. Time bhi bachega.

---

## 🔑 Key Concepts / Important Terms

| Term | Simple Hinglish Meaning |
|------|--------------------------|
| `allow_code_execution=True` | Agent generated code ko actually **run** kar sakta hai (sirf likhna nahi) |
| `code_execution_mode="safe"` | Code **Docker container** me sandboxed chalta hai — host machine safe |
| `max_execution_time` | Code execution ke liye time limit (seconds) — Ed ne few minutes diye |
| `max_retries` | Execution fail hone par kitni baar retry — yahan 5 |
| `self.agents` / `self.tasks` | `@agent`/`@task` decorators se **auto-collected lists** — manually list karne ki zaroorat nahi |
| `Process.sequential` | Tasks ek ke baad ek chalenge: design → code → frontend → test |
| `kickoff(inputs={...})` | Crew run karna; inputs (`requirements`, `module_name`, `class_name`) YAML placeholders me interpolate hote hain |
| Vibe coding pitfall | LLMs (Cursor) **zaroorat se zyada code** generate karte hain — "err on the side of more" |
| `get_share_price` | Assignment me diya gaya function — fixed test prices return karta hai (real market data nahi) |
| Two-for-one project | Ye crew jo framework banayegi, wahi Week 6 ke trader agents (OpenAI Agents SDK + MCP) me reuse hoga |

---

## 💡 Backend Dev Ke Liye Note (aapke liye)

- **Decorator auto-collection = registry pattern:** `@agent`/`@task` decorators class me methods ko ek internal registry me collect karte hain, isliye `agents=self.agents` kaafi hai — bilkul jaise Flask ke `@app.route` ya pytest ke fixture collection me hota hai. Cursor ka generated "list everything manually" code isi registry ko bypass karke DRY tod raha tha.
- **Per-agent capability flags = principle of least privilege:** Sirf backend aur test engineers ko code execution mila, lead ko nahi (design only), frontend ko nahi (Gradio UI container me nahi khul sakta). Ye waise hi hai jaise aap microservices me har service ko sirf zaroori IAM permissions dete ho. Docker sandbox + `max_execution_time` + `max_retries` = timeout aur retry policy with isolation — production job-runner jaisa.
- **Vibe coding warning seriously lo:** LLM-generated code review karte waqt "kya ye framework already ye provide karta hai?" poochna — Cursor ne crew me redundant boilerplate bhar diya tha. Framework conventions (`self.agents`, `def crew()`) jaano, warna AI bloat ship karoge.
- **Hands-on lab:** is lecture ka code khud chalane ke liye `Practical/lab4_engineering_team.py` run karo (is repo me, `uv run` se chalta hai, Groq pe free via LiteLLM). Hamare labs course se thoda alag hain: self-contained code-style (YAML scaffolding nahi), aur **Docker code-execution ki jagah hum generated code ko khud compile + unittest karte hain** — to lecture ke `allow_code_execution`/Docker wale parts lab me is tarah replace hue hain.

---

## 🧠 Takeaway (yaad rakho)

1. **Code execution selectively do:** backend + test engineers ko `allow_code_execution=True` + `code_execution_mode="safe"` (Docker); lead (design-only) aur frontend (UI container me nahi chalega) ko nahi.
2. **`max_execution_time` aur `max_retries=5`** set karo jab agent code run karega — execution flaky ho sakta hai.
3. **Decorators ka faayda:** `agents=self.agents`, `tasks=self.tasks` — manual listing mat karo; LLM-generated bloat (vibe coding) se bacho.
4. **Assignment = trading account management system:** deposit/withdraw, buy/sell, portfolio value, P&L, holdings, transactions, validations + `get_share_price` test function.
5. **Two-for-one:** ye project Week 6 ke agent traders (OpenAI Agents SDK + MCP) ke liye lightweight trading framework ready kar dega — heavyweight backtesting frameworks ki zaroorat nahi.

---

<details>
<summary>📜 Full English Transcript (original, click to expand)</summary>

Okay. Okay. It's time for us to go to the crew module as well, you know? You know that that's the next step. And of course, you also know that I like to get rid of all of the gunk. No more gunk for us, but we'll keep in, of course, the hooking up to the YAML files. Let's get rid of everything else from here, and we will do our work to define the agents.

So agents, the first agent is called the engineering lead. And good old Cursor is giving us some good suggestions here, but not perfect because we don't need the engineering lead to be able to execute code. That's not its idea, it's just meant to be designing stuff. All right. But now the backend engineer. So thank you Cursor for that. But you have missed this time what we really need here. So we do indeed want it to be able to have code execution. We want the code execution to be safe in a Docker container. Absolutely. The, uh, max execution time. We probably want to give it a bit more. Let's give it a few minutes to work on this. Why not? And then max retries. We'll give it five times before we are upset. That seems pretty good.

Okay. The front end engineer. Need to remember my decorator. The the front end engineer. Let's have a look. So actually we're going to have it write front end. But we're not going to have it try and execute because that would bring up a Gradio UI in the Docker container. That'd be a whole different, different ball game. So we're not going to do that. But we are going to have it do its creation. And now we just have the test engineer. So thank you Cursor. And that seems like a good enough start. But the test engineer we absolutely want the test engineer to not only write the unit tests but then to run the unit tests. But it probably doesn't need. Well we'll give it we'll give it a couple of minutes to do that, and we'll give it five retries as well. That seems fine. Okay, those are our agents.

Next, it's time for us to define our tasks. And this is going to start to get very complicated. The design task is just going to look like that. And I bet Cursor is going to know everything else. That's all we want for the code task now. And, uh, let's see if it can help us more. That's probably great for the front end task. And, uh, the test task. Is it going to help us with that? Yes it is. And I think that's it for our tasks. I don't think there's anything missing here. Perfect. All right. Thank you. Cursor. Those are indeed our tasks.

It's time though. It's time for our crew. Let's see if, uh, Cursor can do this. Oh, no no, no, that's all. All a disaster. This is, uh, a moment to, uh, definitely mention that you do have to be mindful of this. The whole vibe coding thing. As I said before, it is common for LLMs to generate too much code and to to just put stuff in there. And often people send me problems they've got and I can see that they've used an LLM to generate lots of code, because it will tend to err on the side of more. Of course, in this situation, we don't need to list out all of the agents like this. We can just say the agents are self dot agents. That's the why we decorated them. And we can say that the tasks is self dot tasks. And we also need to mention that the process is process sequential and verbose is true. And that really is it. But we would normally call this def crew like that. And I think we've got it.

Okay well you know what's left. We have to do our run function and we will come to that right now. Okay. This is the usual main full of stuff. Gonna delete all of that. Going to delete all of this stuff here and leave us with something very simple. So let's have a think about this, this run. So, so first of all, we know that the what we've got here is we've got requirements are going to be let's let's just give ourselves a variable that we'll have we'll have a variable requirements okay. Module name was one of them. And we'll have that be a variable module name. And class name is going to be a variable class name. Isn't it great the way again Cursor just guesses since we had that before that. That's going to be our thing. And now engineering team. That's because that the the function, the method that we decorated with, with the crew is indeed called crew kickoff with our inputs.

Okay. So all that remains now is for us to actually come up with the assignment. And I have produced an assignment which I wish to show you now and which I think you may find rather interesting. So here is the coding challenge that we have for our team of agents. Let me tell you about this challenge. And then I'm going to tell you why. This is an interesting challenge. So the requirements we would like a simple account management system for a trading simulation platform. The system should allow users to create an account, deposit funds and withdraw funds. The system should allow users to record that they've bought or sold shares and providing a quantity. It should be able to calculate the total value of the user's portfolio and the profit or loss from the initial deposit. The system should be able to report the holdings of a user at any time, and the PNL at any time. And it should be able to list the transactions that the user has made. And it should prevent the user from withdrawing funds that would leave them with a negative balance, or buying shares that they can't afford, or selling shares that they don't possess. And I'm telling it, the system has access to a function get share price, which returns the current price of a share, and includes an implementation that returns a fixed price for three shares there. So that should be built into this code. So that's the challenge. It's like to build a kind of framework for simulating trading activity, which you know that's a fair bit of work to do that properly. That's that's not going to be easy.

And you may wonder why why this particular challenge? Well, here's the thing. In the last week of our course, we are going to try to build agent traders. We're going to be using back to OpenAI Agents SDK. And we're going to be using MCP. It's going to be really cool. And the idea is going to be, can we build like a set of traders of agents that are able to monitor financial markets, look at actual live real time prices and make trading decisions? But for this to work, we're going to want to have a kind of framework that they can make trades in and that a framework that will keep track of portfolios and so on. And there are some frameworks that you can get off the shelf, but they're very heavyweight because they're sort of big financial markets, backtesting frameworks. There isn't something that I could find easily that's just a lightweight account management stock portfolio management framework. And so I thought, why don't we get AI to build it for us? And what could be better than having our own crew, our own engineering team, take on this challenge and try and build out this, this whole framework for us. So that's why this is a two for one. Not only are we doing this week's project, putting together a crew of software engineers and a test engineer and so on, but also this is going to hopefully provide us with a framework that will then be able to reuse, give us a head start in week six, so we don't have to build our own and do a whole ton of coding. So it's actually going to save us some time as well to boot. Well, with that introduction, I think it's time to try and run this thing.

</details>

---
*Source: Official Udemy lecture transcript (auto-captions, lightly cleaned). Notes in Hinglish for self-study.*
