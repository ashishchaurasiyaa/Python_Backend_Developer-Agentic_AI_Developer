# L67 — Day 5: From Single Modules to Complete Systems

> **Week 3 — CrewAI** · ⏱️ ~9m · 🎥 Lecture 67 of 131
> **Instructor:** Ed Donner · **Lecture ID:** 49821253

---

## 🎯 Ek Line Mein (TL;DR)

Week 3 ka closing lecture — engineering team project se aage badhke **challenge project** milta hai: **structured outputs (output_pydantic)** + **runtime task creation via task callbacks** use karke ek aisa crew banao jo single module nahi, balki **poora multi-module system** dynamically build kare.

---

## 📝 Hinglish Explanation (Detailed)

- Ed engineering team project ke results se **genuinely blown away** hai — 4 agents ke crew ne ek poora product banaya: backend module, frontend UI, aur test module — aur UI **pehli baar me hi run** ho gaya, front end + back end sab kuch hold karke kaam kar raha tha.
- Ed ne apna generated example **`example_output_new`** folder me daala hai, saath me kuch aur examples bhi hain. Lekin asli baat — **khud try karo**, alag-alag **models ke saath experiment** karo. Learning building se hi hoti hai.
- **Easy extension — "your team is hiring":**
  - Abhi jo **test engineer** tha wo sirf test cases *likhta* tha — ek real test engineer add karo jo **test plan banaye aur execute** kare.
  - Ek **business analyst** add karo jo requirements ko flesh out kare.
  - Aur richer **user interface** banao. Sky's the limit — abhi sirf 4 log the team me, aur aap surface hi scratch kar rahe ho.
- **Hard challenge — week ka real challenge:**
  - Problem: abhi tak crew sirf **ek hi Python module** (backend) banata tha — design pehle se fixed tha, sab kuch "on rails" tha.
  - Better: team **poora system piece by piece** banaye — alag classes, alag modules, alag agents — aur phir sab assemble ho.
  - Iske liye workflow ko **dynamic** banana padega kyunki pehle se pata nahi hota ki engineering lead kitne modules design karega.
- **Solution ke 2 building blocks:**
  1. **Structured outputs** — engineering lead se clear output lo ki **kaun kya banayega** (modules ki list). Ye **`output_pydantic`** (ya **`output_json`**) se hota hai.
  2. **Dynamic task creation via callback** — CrewAI me aap **runtime pe Task object create** kar sakte ho. **Task pe `callback=` field** hota hai (note: callback **task level** pe hota hai, **agent level pe nahi** — Ed ne khud correct kiya); callback function me ek task complete hone par **naya task create** karwa sakte ho. Isse "ek cheez complete hone par doosri trigger ho" wala dynamic system banta hai — har module ke liye engineer ko **dynamic number of times** call karo.
- **CrewAI Task docs walkthrough** — Ed docs ke Tasks page pe interesting cheezein dikhata hai:
  - Tasks **YAML config** se bhi ban sakte hain (jo hum jaante hain) ya **pure code** me bhi — description + expected_output directly pass karke.
  - **Task guardrails** — OpenAI Agents SDK ke guardrails jaisa concept: outputs ko **validate aur transform** karo before next task. Farak ye hai ki OpenAI SDK me guardrail sirf first input / last output pe lagta tha, CrewAI me **kisi bhi task** pe laga sakte ho. Error handling bhi documented hai.
  - **Structured outputs** — `output_pydantic` ya `output_json`.
  - **Tools with tasks** — task pe tools attach karna (jaise **SerperDev** tool jo humne use kiya).
  - **Context / referring to other tasks** — output automatically next task ko milta hai, lekin **`context`** explicitly define bhi kar sakte ho (humne kiya tha).
  - **Async execution** — is week async use nahi hua, but Ed promise karta hai ye **wapas aayega** aage ke weeks me.
- **Apply to your day job:** Ed koi fixed system nahi deta — apne profession ka system socho (website, e-commerce platform, medical records organizer...) aur crew se banwao.
- **Share progress on LinkedIn** — Ed ko tag karo, visibility milegi, aur ye projects expertise **build + demonstrate** karte hain.
- **Week 3 wrap-up:** Stock picker interesting tha (investment ke liye use mat karna!), engineering team **mind-blowing** tha. Ed ko CrewAI bahut pasand hai (though **OpenAI Agents SDK** uska favourite hai). Ab **Week 4 = LangGraph** — ek heavier-weight framework.

---

## 🔑 Key Concepts / Important Terms

| Term | Simple Hinglish Meaning |
|------|--------------------------|
| **Task callback** | Task create karte time `callback=function` do — task complete hone par wo function call hota hai; wahan se **naya Task runtime pe create** kar sakte ho |
| **Dynamic task creation** | Tasks ki sankhya code likhte waqt fixed nahi — engineering lead ke design ke hisaab se runtime pe tasks bante hain |
| **Structured outputs (`output_pydantic` / `output_json`)** | Task ka output ek **pydantic model / JSON schema** me force karna — taaki "kaun sa module kaun banayega" machine-readable ho |
| **Task guardrails** | Output ko **validate/transform** karne wala check before next task — CrewAI me **kisi bhi task** pe laga sakte ho (OpenAI SDK ki tarah sirf edges pe nahi) |
| **Context (task referencing)** | Ek task ka output by default next ko jaata hai, lekin `context=[...]` se explicitly specify kar sakte ho kaun se tasks ka output chahiye |
| **YAML vs code Tasks** | Task YAML config se ya directly code me (description, expected_output pass karke) — dono valid |
| **Async execution** | Crew tasks asynchronously bhi chal sakte hain — is week use nahi hua, docs me hai |
| **`example_output_new`** | Ed ka folder jisme uske generated engineering-team outputs rakhe hain reference ke liye |

---

## 💡 Backend Dev Ke Liye Note (aapke liye)

- **Task callback = post-commit hook / Celery chord:** ek task finish hone par callback fire hota hai jo naye tasks enqueue karta hai — bilkul Celery me `chain`/`chord` ya DB trigger jaisa pattern. Fixed DAG se **dynamic DAG** banane ka CrewAI tareeka yahi hai.
- **Structured outputs as API contract:** engineering lead ka output ek **pydantic schema** (e.g. `class ModulePlan(BaseModel): modules: list[ModuleSpec]`) banao — phir us list pe loop karke per-module Task spawn karo. Ye waise hi hai jaise aap microservice boundaries pe OpenAPI/pydantic contracts enforce karte ho — LLM ke free-text pe kabhi parse-by-regex mat karo.
- **Guardrails = middleware/validators:** CrewAI task guardrails ko FastAPI dependency/response-validator ki tarah socho — har hop pe output validate + transform, fail hone par retry/error path. OpenAI SDK se zyada flexible kyunki kisi bhi task pe lagta hai.
- **Hands-on lab:** `Practical/lab4_engineering_team.py` (is repo me, `uv run` se chalta hai, Groq pe free via LiteLLM) — **is lecture ka code khud chalane ke liye ye lab run karo**. Note: hamare labs course se thoda alag hain — self-contained code-style (YAML scaffolding nahi), SerperDev ki jagah free Wikipedia search tool, aur Docker code-execution ki jagah generated code ko **khud compile + unittest** karte hain; memory feature skip hai (OpenAI embeddings chahiye).

---

## 🧠 Takeaway (yaad rakho)

1. **Challenge of the week:** single fixed module → **multi-module system** — structured outputs + dynamic task creation se.
2. **Callback task level pe hota hai** (`callback=` in Task), agent level pe nahi — wahan se runtime pe naye tasks banao.
3. **`output_pydantic`/`output_json`** se engineering lead ka plan structured banao, phir modules ki list pe loop karke engineers ko dynamic number of times call karo.
4. **Task guardrails** CrewAI me kisi bhi task pe lag sakte hain — validate/transform before next task (OpenAI SDK se zyada flexible).
5. Week 3 khatam — **CrewAI done**; Ed ka ranking: OpenAI Agents SDK > CrewAI, lekin dono pasand. Next: **Week 4 = LangGraph** (heavier-weight framework).

---

<details>
<summary>📜 Full English Transcript (original, click to expand)</summary>

So I am genuinely blown away by how well that did. And and you know, again, how easy it was for us to get to that point of having these different, this crew of different agents building that product and the fact that that user interface just worked right away, like it just came up and it ran and, and it looked so great and that the functionality behind it there was like a front end and back end and it all held together and did its thing. So I hope that you're going through the same as what I'm going through, somewhat some disbelief and I hope you're seeing similar results. I've put that particular example in something called example output new. And there's also you'll see a couple of other examples in there. If you you want to try out the ones that I generated. But you should try it yourself. Play with different models and experiment. And that's not all you should experiment with.

Now this this week has some important projects for you. This this is where you really learn. You learn by building stuff yourself, by coming in. Take an example like this and just build it step by step. Take it a piece at a time. Gradually add to it. So the first way you can add to it, the easy way you can add to it is to have your team grow. Your team is hiring. Add in some more. The role that I call test engineer wasn't really a test engineer because this was some something that wrote test cases, but you could actually have a test engineer that's responsible for going through maybe writing a test plan and then executing the test plan. You could add a business analyst that fleshes out the requirements. You could you could have some more detail. You could have an even richer user interface. Honestly, the sky's the limit with this. We're just scratching the surface. We only had four people in this team, and and you can just keep on and on going and try different models and see where it takes you.

But that's the relatively easy change there is then a harder change for you, which is the real challenge of the week. And here it is. So the thing is that this was all very well, but ultimately it only produced one Python module for the back end code. And then of course front end module to go with it and a test module to go with that. But it was all still very much on rails in that there was just the one, the one module that was already fixed at the beginning. Now, it would be a lot better if your team could build a whole system piece by piece, working on the different classes to build the different modules and then assembling them together. But therein lies a problem, because you would need to have a workflow that's a little bit more interactive in that potentially you'd need to have different classes being created by different agents.

Now there's a few ways to do this. One way is, of course, you'll want to use structured outputs as a way to get more clarity from the engineering lead about who's doing what. Use structured outputs as a way to construct the different modules that need to be written. But ultimately, you're probably going to want to call an engineer a certain dynamic number of times. That will depend on how many modules the engineering lead wants to create. So it's not like you're fixed when you write the code that you know exactly how many tasks will be run now. CrewAI allows you to do that and it makes it quite easy for you. You can create a task object at runtime while it's actually running. You can have a task object, and one of the the fields you can have is have a callback. And actually the callbacks with the agent and the callback can make it create another task. So you can use this approach to build a more dynamic system where the results of completing one thing causes another thing to happen. And so you can assign tasks for each of the modules that need to be built.

And that is the challenge for you. Add structured outputs and then add the dynamic creation of tasks so that an entire set of modules can be created, and you can build a whole system and then apply that. And I don't necessarily have a system to be built. You should apply that yourself to your day job. Think of a system that you would like, whether it's building a website, whether it's building an e-commerce platform, whether it's building something to organize medical records, whatever line of business, whatever profession you work in, think about the challenge that you could set your crew and have it be something which which is dynamic and which could involve building an entire system with several modules. And once you've done that, of course, or while you're doing it, you must share your progress. This will be hugely something that that will generate excitement on LinkedIn. So post updates there. Tag me so that I can weigh in and get it more visibility. These are projects that really count, and it really helps you to build and solidify your expertise and demonstrate it to others.

Actually, to correct myself there, I was right the first time. If you want to to work with callbacks, then the way you do it is at the task level, not the agent level. And I'm looking right now in the CrewAI docs. At docs. Or just just click on tasks right there. And it's worth looking through this because there's lots of lots of interesting information here that you might want to try out. So the callback you can specify when you create a task, the in the code you would say callback equals. And then the name of a function that should be called back. And that is where you could potentially create a new task.

So it talks generally about the fact that you can create tasks from from YAML as we know well. Or you can also do it just by having the full code version of it too. As you can imagine, you can just pass in the description the expected output instead of specifying the YAML config. Then there's a lot of interesting stuff here that's worth taking a quick peek at. There's stuff we know about, but then there's also task guardrails, an analogous concept to what we looked at with OpenAI Agents SDK. Using guardrails a way to validate and transform outputs before they're passed to the next task. It looks like it doesn't have the same constraint that OpenAI has that it needs to be input of the very first one, or output of the very last one. You can implement this at any task, it appears. And then there's stuff about how to handle errors with with those guardrails and then structured outputs. We know about that. That is of course using the output pydantic or output JSON is another way of doing it.

And now integrating tools with tasks is of course something that we know about. And creating a task with tools is is listed out here, which is. Yes, sorry, that is what we're used to. Again, that is using a tool like the Serper dev tool that we already used, actually, right in there referring to other tasks. The output is automatically related to the next one, but you can define the context that should be used. And and we we did that. There's some stuff on asynchronous execution. You know I remember I said last time I think that we would be using async every single week, and we haven't actually used async this week. We're going to it's going to make a comeback, don't worry. But if you miss it then you can read up around asynchronous execution of your crew tasks here. This then is the callback mechanism. This is where you can implement a callback function. So if you had referred to it like so, then your function will get called subsequently when the task completes. And then there's a more interesting stuff here. And uh, more now on the, uh, the guardrails as well. And there we go. So I, I do encourage you to take a read through this, read a bit more about things like guardrails, which are interesting, and also about using callbacks. And some of this may be helpful when you look to build this more advanced flow. When completing one task can trigger setting dynamically, creating multiple other tasks.

And very sadly, that brings our crew week to an end. It's the end of week three, the end of crew week. We've done some great things, so we built some fun projects. The stock picker was was really interesting. You haven't used that for investment decisions, I hope. And the engineering team was just mind blowing. Wow. Um, so I really hope you enjoyed it. I hope you have the same feeling as me about crew. I really love crew. I prefer OpenAI Agents SDK, but but I love crew too, and I'm excited to now move to a heavier weight framework in the form of LangGraph for week four. It's going to be great and I will see you then.

</details>

---
*Source: Official Udemy lecture transcript (auto-captions, lightly cleaned). Notes in Hinglish for self-study.*
