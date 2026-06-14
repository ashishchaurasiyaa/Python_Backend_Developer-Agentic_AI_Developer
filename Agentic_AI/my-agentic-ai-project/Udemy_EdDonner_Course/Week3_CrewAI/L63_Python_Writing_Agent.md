# L63 — Day 4: Python-Writing AI Agent

> **Week 3 — CrewAI** · ⏱️ ~6m · 🎥 Lecture 63 of 131
> **Instructor:** Ed Donner · **Lecture ID:** 49821207

---

## 🎯 Ek Line Mein (TL;DR)

**Coder agent** ko run karte hain — `main.py` me **kickoff** likha, ek tricky **pi-series assignment** diya (taki LLM "pretend" na kar sake), aur agent ne **Docker code interpreter** me khud Python code likh kar, run karke, **pi ka approximation (3.1414...)** nikal diya.

---

## 📝 Hinglish Explanation (Detailed)

- **Crew function ki zaroorat nahi padi:** Ed bolte hain ki ye thoda anti-climax hai — `crew()` function me **default setup hi kaafi hai**. Scaffold me jo `@crew` decorator wala default crew bana hua hai, wahi humara kaam karta hai. Kuch extra likhna nahi padta.
- **`main.py` rewrite karna hai:** Scaffold ke `main.py` me jo boilerplate (usual stuff) hai, wo sab **delete** karo aur apna simple **`run()` function** likho:
  - `inputs = {"assignment": ...}` — assignment variable set karo
  - `result = Coder().crew().kickoff(inputs=inputs)` — crew ko **kickoff** karo inputs ke saath
  - `print(result.raw)` — result **`.raw`** attribute me wapas aata hai, usse print karo
- **Assignment design — LLM ko "pretend" karne se rokna:** Agar assignment simple ho jaise *"Python script that prints Hello World"*, to **LLM bina code run kiye bhi output guess kar sakta hai** — code generate karke "ran it" ka pretend kar sakta hai. Isliye Ed ne **deliberately tricky assignment** chuna jo fake nahi kiya ja sakta.
- **The assignment — Leibniz series for pi:** *"Write a Python program to calculate the first 10,000 terms of this series, multiplying the total by 4: 1 − 1/3 + 1/5 − 1/7 + ..."*
  - Ye **deliberately complicated tarike se phrase** kiya gaya hai — LLM ko ek intelligent human ki tarah figure out karna padega ki loop chahiye, 10,000 terms tak chalana hai, phir total × 4 karna hai.
  - Math-savvy log pehchaan lenge: ye **pi calculate karne ka classic (slow & boring) tarika** hai.
  - **Clever trap:** LLM formula pehchaan kar bol sakta hai "answer pi hai" — lekin **10,000 terms ke baad sirf approximate pi** aata hai jo kuch decimal places ke baad **wrong** hota hai. Agar output exact pi (3.14159...) ki jagah **approximation** aaya, to pakka pata chalega ki code **sach me run hua hai**, pretend nahi.
- **Run karna:** Terminal kholo → third week ki directory → `coder` project folder → **`crewai run`** type karo. Crew start hota hai aur agent assignment pe sochna shuru karta hai.
- **First try fail, retry pass:** Pehli baar **code interpreter me kuch run hua aur fail** ho gaya — agent ne **retry** kiya. Ed point karte hain: ye hamesha first attempt me kaam nahi karta, lekin failure se ye bhi confirm hota hai ki **kuch genuinely interpreter me run ho raha hai**.
- **Generated code ki quality:** Agent ne smart code likha:
  - Loop me number of terms ke through jaata hai (terms variable neeche define kiya)
  - **`(-1) ** index`** trick use kiya — alternate +1/−1 sign ke liye (clever technique!)
  - Us se divide kiya, aur end me **result × 4** kiya — bilkul sahi
- **Output verify hua:** Answer aaya **3.14149** (not 3.14159) — yani **pi ka bad approximation**, exactly jaisa expect tha. Iska matlab code **genuinely Docker me run hua**, LLM ne pretend nahi kiya. ✅
- **Output file bhi bani:** Task ke `output_file` config ke hisaab se ek file create hui jisme **code + uske neeche output** dono hain.
- **Ed ka takeaway:** Itna sab machinery — **Docker container start karna, code likhna, run karna, vaguely-phrased problem ko samajhna** — sab itni aasani se ho gaya. Bas ek `allow_code_execution=True` flag se agent ko **coding skills mil gayi**.
- **Next up:** Ab ek coder hai, to natural extension — **poori engineering team** banayenge. "Crew" ka asli matlab yahi hai — ek **engineering crew** jo problems ko front-to-back solve kare.

---

## 🔑 Key Concepts / Important Terms

| Term | Simple Hinglish Meaning |
|------|--------------------------|
| **`kickoff(inputs=...)`** | Crew ko run karne ka method — inputs dict pass karte ho jo YAML me `{placeholders}` fill karta hai |
| **`result.raw`** | Kickoff ke result object ka attribute jisme final raw text output hota hai |
| **`run()` in main.py** | Scaffold ka entry point — `crewai run` command isi ko call karti hai |
| **`crewai run`** | CLI command jo project folder se crew execute karti hai |
| **Code Interpreter** | Docker container jisme agent apna generated Python code safely run karta hai |
| **Leibniz series (pi)** | 1 − 1/3 + 1/5 − 1/7 + ... × 4 ≈ pi — slow convergence wala classic formula |
| **"Pretend" problem** | LLM bina code run kiye output guess kar sakta hai — isliye approximation-based test design karo jo guess na ho sake |
| **`(-1) ** index` trick** | Alternating sign (+/−) generate karne ka clever coding pattern jo agent ne khud use kiya |
| **`output_file`** | Task config — agent ka final answer (code + output) file me save hota hai |
| **Retry on failure** | First code run fail hua to agent ne khud retry kiya — agentic self-correction |

---

## 💡 Backend Dev Ke Liye Note (aapke liye)

- **LLM output verification ka smart pattern:** Ye lecture ka asli gem testing philosophy hai — LLM se aisa output maango jo **wo memorize/guess nahi kar sakta** (10,000-term approximation ≠ exact pi). Backend testing me ye waisa hi hai jaise mocked response vs real integration test ka difference — agar exact pi aata to "mock" tha, approximation aaya to "real execution" hua. LLM-based systems ke evals design karte waqt ye trick yaad rakho.
- **`kickoff()` + `result.raw`** ko ek job-runner API ki tarah socho — `celery_task.delay(**inputs).get().result` jaisa: inputs dict jao, blocking run ho, structured result object wapas aaye. Ed agle lectures me `result.pydantic` bhi dikhayenge (typed response schema, FastAPI `response_model` jaisa).
- **Docker-based code execution = sandboxed CI runner:** Agent ka generated code untrusted code hai — usse host pe `exec()` karna suicide hai. CrewAI isko Docker container me chala kar wahi karta hai jo aap CI me untrusted PR builds ke liye karte ho. Failure + retry loop bhi CI retry policy jaisa hai.
- **🧪 Hands-on lab:** Is lecture ka code khud chalane ke liye ye lab run karo — `Practical/lab4_engineering_team.py` (is repo me, `uv run` se chalta hai, Groq pe free via LiteLLM). Hamare labs course se thoda alag hain: self-contained code-style (YAML scaffolding nahi), aur **Docker code-execution ki jagah hum generated code ko khud compile + unittest karte hain** — kyunki Docker `allow_code_execution` ke liye paid setup/local Docker chahiye, lab me verification deterministic rakha hai.

---

## 🧠 Takeaway (yaad rakho)

1. **Default `@crew` setup kaafi hai** — coder project me crew function me kuch custom nahi likhna pada; sirf `main.py` me `run()` + `kickoff(inputs)` + `print(result.raw)`.
2. **LLM ko verify karne ke liye un-guessable output maango** — pi-series ka 10,000-term approximation (3.1414...) prove karta hai ki code sach me run hua, LLM ne pretend nahi kiya.
3. **First failure normal hai** — code interpreter me first try fail hua, agent ne khud retry karke sahi answer nikala (agentic self-correction).
4. **`allow_code_execution=True` + Docker = coding skills unlocked** — agent code likhta hai, sandboxed container me run karta hai, output validate karta hai.
5. **Next step: engineering crew** — single coder se aage, ek poori multi-agent engineering team jo problems front-to-back solve karegi.

---

<details>
<summary>📜 Full English Transcript (original, click to expand)</summary>

Well, this might be a bit of an anti-climax. I'm just saying we have to write our crew function. We don't have to write our crew function because the default thing there is all that we need. We don't need to do anything else. We've already got something which can do exactly what we want.

What we do need to do still is come into main and rewrite this. And of course it's got all of the usual stuff. We don't need any of the stuff that's there. We'll just delete everything and come back here and write our own run function. Def run. This is the thing that's going to run the crew. And so we are going to say inputs equals assignment. There we go, colon. Let's just give that a variable assignment for now. And then we're going to say result equals coder dot crew dot kickoff, passing in those inputs. And then we want to print result raw is how the result will come back. Okay.

And so what's left to do, of course, is to set the actual assignment. So let's come up with assignment. And we're going to do something challenging here, because I want to check — if I said something like the default that Cursor has got for us there, right, a Python script that prints Hello World, then we might not know for sure that it's actually running it, because LLMs are perfectly capable of knowing what a script like that would yield, would result in. So it could generate the Python code and then pretend it ran it. So we want something that it can't do any pretending for.

And so I have one thing to show you, although knowing LLMs, it probably could pretend this as well, but I certainly think this is a harder one. So I wanted to write a Python program to calculate the first 10,000 terms of this series, multiplying the total by four. So I put it in quite a complicated way. And here's the series: one minus a third plus a fifth, minus a seventh plus dot dot dot. And so I'm just kind of — it's a classic case of just sort of asking the LLM to figure it out like a reasonable, intelligent human would. And who would have thought a few years ago that you could write software that would be able to take something like this with all of the nuance, all of the implications, and figure out that it needs to write code to put this into a loop, to keep it going for 10,000 terms, and then to take the total and multiply it by four.

And the mathmos around will probably have already spotted this as being a very slow and very, uh, boring way to calculate pi. So if it does this right, and if it calculates the first 10,000 terms and multiplies by four, then it will be an approximation — a bad approximation — of pi. And now the LLMs are perfectly capable of recognizing this formula and knowing that the answer should be pi. But what's much harder is for them to realize that 10,000 terms would be approximately pi, and be wrong after a few decimal places. And so that's how we can tell that it's really doing its thing. So I hope that all makes sense.

It's time for us to actually run this. All right, everyone, this is exciting. The drum roll. We're going to try and have our coder do its thing. So let's bring up a terminal. Let's go into the third directory. Let's go into coder and let's type crewai run to kick this off. And remember the challenge is now being set to our agent. You can see it started. There's the command and it's now going to be thinking about it.

And something just ran and failed in the code interpreter. So it's — that one means it's its first try and it's trying again. So it's not like it always works. At least it shows us that something is trying to run in an interpreter. Okay. It's done some code. It's got an answer. It just all happened really fast.

So, um, this is the code that it's got, that it's written, and this is the output. It's used an interesting technique, I can see. It's obviously, uh, it's going through the number of terms as it should do. It's a number of terms it sets down below. That's nicely done. And then it's using this idea of take minus one to the power of the index, which is either going to be minus one or plus one. It's a clever trick. And dividing by that, which looks right to me. And then where do we see it multiplying the result by four? There, right there. I was going to say that would be suspicious. It does indeed multiply the result by four. And that's why we get 3.14149, not 3.14159, because it is just an approximation of pi. And it seems to have worked.

And indeed, if also we see that it's created an output file. Yes it has. And here in the output file we will find the same output, which has got the code, the output below it. And I gotta tell you, I'm blown away by how easy it is to do this. And all of the machinery that's happening behind the scenes to be able to start a Docker container, come up with the code, run the code, come up with the answer to the way that I expressed it in quite a simplistic way. It just figured the whole thing out. And I think that's really cool.

And there you have it. We just gave coding skills to an agent. We have our coder agent and it was so simple. And I hope you enjoyed it as much as I did. All right. Well, it ain't over yet. We've got more to go because the natural extension, now that we've got a coder, we can build an entire engineering team. It's really the — goes to the meaning of crew. We're going to build a crew, an engineering crew, to be able to solve problems front to back. And it's going to be so great. I'll see you then.

</details>

---
*Source: Official Udemy lecture transcript (auto-captions, lightly cleaned). Notes in Hinglish for self-study.*
