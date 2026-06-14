# L56 — Day 2: Multi-Agent Financial Research Systems

> **Week 3 — CrewAI** · ⏱️ ~11m · 🎥 Lecture 56 of 131
> **Instructor:** Ed Donner · **Lecture ID:** 49821169

---

## 🎯 Ek Line Mein (TL;DR)

Is lecture me Ed ek **financial researcher crew** banate hain — ek **researcher agent** (DeepSeek pe) + ek **analyst agent** (Groq pe Llama 3.3 70B), jisme **`context`** ke through research task ka output analysis task me feed hota hai, aur final me Tesla ka polished **report.md** generate hota hai.

---

## 📝 Hinglish Explanation (Detailed)

- **Project setup:** `financial_researcher` project ke andar **source folder → config** se shuru karte hain — pehle **agents.yaml**, fir **tasks.yaml**, fir `crew.py`, fir `main.py`. Wahi standard CrewAI scaffolding flow.

- **Do agents define kiye:**
  - **Researcher agent** — role: *senior financial researcher* for a company (company **inputs** se template hoke aati hai, `{company}` curly braces wala pattern). Goal: us company ki **news aur potential** research karna. Backstory: "seasoned financial researcher with a talent for finding the most relevant information... present it in a clear and concise manner." Yahin pe **LLM specify** hota hai — chahein to mix-and-match kar sakte hain.
  - **Analyst agent** — role: *market analyst and report writer*. Company ko analyze karke ek **comprehensive, well-structured report** banata hai jo insights ko clear aur engaging way me present kare. Backstory me "meticulous, skilled analyst with a background in financial analysis" jaise words.

- **Backstory ka asli faayda:** Ed ka observation — agar wo seedha system prompt likhte (jaise Week 2 me OpenAI Agents SDK me), to shayad "meticulous" ya "meaningful insights" jaise words use hi na karte. **Backstory likhne ki discipline** hume better prompting ki taraf push karti hai — zyada context, better outputs.

- **Do tasks define kiye (tasks.yaml):**
  - **Research task** — description me detail se bataya: company ki **current status & health, historical performance, challenges & opportunities, recent news, future outlook, potential developments** research karo; findings ko **structured format with clear sections** me organize karo. Expected output thoda repetitive hai (wahi sections fir se mention) — Ed kehte hain *"there's never a harm in being repetitive"*. Agent: **researcher**.
  - **Analysis task** — research findings analyze karke **comprehensive report** banao jisme **executive summary, information, insights, market outlook** sections hon, professional style me formatted. Agent: **analyst**.

- **`context` — task chaining ka magic:** Research task ka output analysis task me include karne ke liye CrewAI ek super easy tareeka deta hai — analysis task me bas **`context:`** field add karo jo ek **list** leta hai, aur usme `research_task` daal do. Bas — **continuity ensure**, researcher ka output automatically analyst ke prompt me chala jaata hai.

- **`output_file`:** Research task me output file nahi hai, sirf **analysis task** me `output_file: output/report.md` set kiya — final report disk pe save hoti hai.

- **crew.py — bold rewrite:** Ed boilerplate ka saara "gunk" delete karke pura file fresh likhte hain (config paths rakh ke):
  - **`@agent`** decorator wale do methods — `researcher` aur `analyst`, dono me `verbose=True`.
  - **`@task`** decorator wale do methods — `research_task` aur `analysis_task`.
  - **`@crew`** decorator wala method — `Crew(agents=self.agents, tasks=self.tasks, process=Process.sequential, verbose=True)`.
  - Yaad rakho: **`self.agents` aur `self.tasks` automatically populate** hote hain kyunki decorators un methods ko register kar dete hain — manually list banane ki zaroorat nahi.
  - Cursor (AI IDE) zyada tar code autocomplete kar deta hai — "Cursor is faster than me."

- **main.py — simplify:** Saara gunk delete, sirf **`run()`** function bacha. `inputs = {"company": "Tesla"}` — Cursor ne khud detect kiya ki YAML me `{company}` template variable hai. Fir `result = FinancialResearcher().crew().kickoff(inputs=inputs)` aur result print.

- **Serper ka teaser:** "Didn't we set up Serper?" — haan, use karenge, **but all in good time** (agle lecture me web search tool aayega). Abhi bina Google lookup ke run karke dekhte hain.

- **Model mixing — LiteLLM ki power:**
  - Researcher → **DeepSeek** (`deepseek-chat`) — 671B parameter model, DeepSeek ke servers pe.
  - Analyst → **Groq** pe **Llama 3.3 70B Versatile** — Meta ka powerful open-source model, high-performance inference.
  - Options: OpenAI pe stick karo, ya **Ollama** se locally Llama 3.2 (1B/3B) chalao — har agent alag provider pe ho sakta hai.

- **Run:** Terminal me project folder me jaake **`crewai run`**. Output me dikhta hai agent ko task assign hua — "senior financial researcher **for Tesla**" — yaani inputs automatically agent ke role me interpolate ho gaye. **DeepSeek slow hai (~30s)** kyunki comprehensive research produce kar raha hai; **Groq itna fast tha ki dikha hi nahi**. End me Tesla ka financial report ready. *"Wasn't that easy?"*

---

## 🔑 Key Concepts / Important Terms

| Term | Simple Hinglish Meaning |
|------|--------------------------|
| **Researcher agent** | Senior financial researcher role — company ki news, health, outlook research karta hai |
| **Analyst agent** | Market analyst + report writer — research ko polished professional report me badalta hai |
| **Backstory** | Agent ki personality/expertise wala YAML field — better prompting ki discipline force karta hai |
| **`context` (Task field)** | Tasks ki list — un tasks ka output is task ke prompt me include hota hai (task chaining) |
| **`output_file`** | Task ka final output disk pe save karne ka path (yahan `output/report.md`) |
| **`{company}` input templating** | YAML me curly-brace variable jo `kickoff(inputs={...})` se runtime pe fill hota hai |
| **`@agent` / `@task` / `@crew` decorators** | Methods ko register karte hain — `self.agents` / `self.tasks` auto-populate |
| **Process.sequential** | Tasks defined order me ek ke baad ek chalti hain |
| **DeepSeek (`deepseek-chat`)** | 671B param model — comprehensive but slow (~30s per task) |
| **Groq + Llama 3.3 70B Versatile** | Meta ka open-source model, Groq ke ultra-fast inference pe — blink me done |
| **LiteLLM model mixing** | Har agent ko alag provider/model (DeepSeek, Groq, OpenAI, Ollama) assign kar sakte ho |
| **`crewai run`** | Project chalane ki CLI command |

---

## 💡 Backend Dev Ke Liye Note (aapke liye)

- **`context: [research_task]`** essentially ek **DAG dependency declaration** hai — jaise Airflow me `task_a >> task_b` ya Celery chains, jahan upstream ka result downstream ke input me inject hota hai. Difference: yahan "result passing" ka matlab hai pura output text agle agent ke prompt me concatenate ho jaana.
- **Per-agent model assignment** LiteLLM ki wajah se trivially easy hai — sochiye microservices me har service apna DB choose karti hai; yahan har agent apna LLM. Pattern: **expensive/deep model research ke liye, fast/cheap model formatting ke liye** — cost-latency optimization bilkul waise hi jaise aap read-heavy path pe cache aur write path pe strong consistency choose karte ho.
- **Decorator-based auto-registration** (`self.agents`, `self.tasks`) wahi pattern hai jo pytest fixtures ya Flask route registries use karte hain — method pe decorator lagao, framework collect kar leta hai. Manual wiring zero.
- **Hands-on lab:** is lecture ka code khud chalane ke liye ye lab run karo — `Practical/lab2_financial_researcher.py` (is repo me, `uv run` se chalta hai, Groq pe free via LiteLLM). Note: hamare labs course se thoda alag hain — self-contained code-style (YAML scaffolding nahi), aur DeepSeek/Serper ki jagah sab kuch free Groq + Wikipedia-style tools pe; concepts (do agents, `context` chaining, `output_file`) wahi hain.

---

## 🧠 Takeaway (yaad rakho)

1. **`context` field** se task chaining hoti hai — analysis task me `context: [research_task]` likho, researcher ka output automatically analyst ko mil jaata hai.
2. **Sirf last task pe `output_file`** rakho jab final deliverable ek report ho — intermediate task ka output `context` se flow hota hai, file ki zaroorat nahi.
3. **Backstory likhna prompting discipline hai** — "meticulous", "seasoned" jaise descriptive words better outputs dilate hain jo plain system prompt me aap shayad na likhte.
4. **Har agent alag LLM le sakta hai** — DeepSeek (deep, slow) researcher ke liye, Groq Llama 3.3 70B (fast) analyst ke liye — LiteLLM string change ki baat hai.
5. **Inputs (`{company}`) YAML me template hote hain** aur `kickoff(inputs=...)` se role/goal/task descriptions sab me interpolate ho jaate hain.

---

<details>
<summary>📜 Full English Transcript (original, click to expand)</summary>

Okay, so let's close the terminal. Come into financial researcher. You know the deal. Now there is a source folder. It has a config. And that is where we want to begin. We want to begin by looking at our agents. So this is the agents. And we are in fact also we're going to have a researcher agent. And we're going to make this a bit shorter and just have an analyst agent, a researcher agent and an analyst agent. So what are they going to do? So this time I'm going to to simply copy and paste a whole new section here and talk it through with you. So the role is going to be a senior financial researcher for a company that we will specify in the inputs like before, it's going to research that company news and potential for that company. The backstory. You're a seasoned financial researcher with a talent for finding the most relevant information about a company known for your ability to find the most relevant information, present it in a clear and concise manner. And that's where we specify the LLM, which we can we can mix this up if we wish. And we now choose to have our second second agent, the analyst. Let me put in what I've got here. Market analyst and report writer focused on a company. You analyze the company and you create a comprehensive, well structured report that represents insights in a clear and engaging way. Meticulous, skilled analyst with a background in financial analysis and company research, a talent, etc., etc.

It's interesting that this construct of having us tell the back story, it really does encourage better prompting. If I were just writing a system prompt instructions as we did last week, I probably wouldn't think through expressing myself this way in terms of using a word like meticulous and meaningful insights and so on. So it is helpful. Putting us through the discipline of having to give a backstory, helps give more context, and helps make sure that we're going to get the best outputs, the best outcomes from running the LLM.

All right. So with this, let's now talk about our tasks. Okay. So we're moving over to tasks. And we are going to have a research task and an analysis task. So it's not too different to the the boilerplate one. But we are going to do a little bit more work here. So for the research task going to really spell out what it is that we want this task to involve. Conduct thorough research on this company. Focus on the current status and health, the historical performance challenges and opportunities, recent news, future outlook, potential development. Make sure to organize your findings in a structured format with clear sections, and then the expected output is a bit repetitive, but it says what we want the well-defined sections and we again mention the input the company. And that is going to be assigned to the researcher. Okay. And the analysis task. Now you'll notice there's no output file there. So you might be thinking what what's going on here. Well let's see. Now let's give this a description that is going to be quite detailed. Again analyze the research findings and create a comprehensive report. The report should. And then we have the different sections in the report. Executive summary information insights market outlook and be formatted in a professional style. And for the expected output will again be a bit repetitive here. There's never a harm in being repetitive. Polished professional report on the company representing the research findings and the agent that we want to mention here. Of course should be the analyst. That's the agent that we that we made for the analysis task. Of course.

Okay. So there's a few more things that we want to add here. We want to make sure that the output from the research task is included as part of the analysis task. And Crew gives us a super easy way to do that. You just type context. And yes, of course Cursor tells us what to do by saying that context. Context can take a list like this. And we are giving the research task as part of the context that's needed for the analysis task. And just with that simple step, we ensure continuity and we ensure that the output is included in the research task. And then finally we are going to have an output file for this. And we're going to let's let's call that report.md in the output directory. That seems fine.

Okay. And now to the all important crew.py. And here we have as usual, some gunk. We have the financial researcher. I am. I'm going to be bold here. I'm going to leave in the config file that we want. And I am just going to delete everything else. And then we're just going to rewrite it. We're going to rewrite this entire file right now okay. So what do we want here. We want an agent. So we put in the decorator for agent. And uh let's see. Well let's just press tab and see what we get. We want an agent that is the researcher. That's correct. We probably want to say verbose is true. There we go. And then we also want an agent that's called the analyst. And that is going to be an agent. And now we're getting help from Cursor. That all looks great. Okay, so now we want to have a couple of tasks. So we want to have a task that is called the research task. That sounds right. It's going to be a task that is going to the research task. That's perfect. And the analysis task that looks good to me as well. So all is well. And now we want the crew and yes thank you. Very nice Cursor. It's filling it all in for us. We want the process to be the process sequential and verbose to be true. Cursor is faster than me. I'm playing catch up here but that is perfect. So remember self.agents is populated because we have agent decorators around our agent functions methods and then tasks is also decorated here. So everything looks great to me.

Okay, now we go to main, and I think, again, we're going to want to, uh, delete all of this and start again. And I will type it for you manually. Okay. Here we go. So we're going to delete the gunk. We are going to delete everything but just only leave in run. That's going to be it. Okay. So run the researcher crew. Isn't it amazing that Cursor realized knows that our input is a company that that inputs. We did indeed just have company as the templated curly braces thing. Just in case you don't know what I mean. I mean, we have this right here. Company is the one input that needs to go in to our YAML. And if we go back to main, then automatically Cursor realized that we needed to set company and populated it there. All right. Then we're going to say yeah result is the financial researcher crew kickoff. And that all looks great to me. And then we're going to print the results. Thank you, Cursor. And that's really it. I think that's all we need.

Now you might be thinking hey, didn't we set up Serper? Are we not going to use that for something? We are going to use it for something. But all in good time. Let's first just try running this without making any any proper Google lookup and see what happens. Okay, well, just before we run it, let's let's change the models. Let's give ourselves some more interesting models to experiment with for our researcher. Let's go with DeepSeek. Now of course you could do whatever models you would like here. This should be deepseek-chat. That'll be the right one for us to use. And you could stick with OpenAI. Or you could use a different model, or use Ollama and run it locally if you wish. I will try a Groq model for this one. Let's use this this here llama 3.3 70 billion versatile. That's one of the most powerful open source models from from Meta. And we'll use that via Groq the high performance inference. You can also run something locally like use Ollama to to run llama 3.2 1 billion or 3 billion version of it. So that's just a mix up the models to try something a bit different.

And now let's go and open up a new one of these guys a new terminal. Let's make it nice and big. And we will go into project or folder number three for Crew. We will go into our financial researcher. And you remember we type crewai run to kick this off and we'll see what happens. It's thinking now I will tell you that uh, you'll see, by the way, that the agent has been assigned the task financial researcher for Tesla. That shows how that those inputs, those parameters automatically got set as the, the, uh, the agents, uh, role. Now, I'll tell you that the DeepSeek takes takes its time over this. It takes a good 30s, I guess, because it's producing quite comprehensive research as part of this. So we will allow it to do its thing. Maybe next time we should have them both be Groq so that it's nice and fast. But it's going through. It's, uh, we've gone off to DeepSeek's servers where it is. The 671 billion parameter model is busy at work, and once it's finished, we're then going to flip across to our other agent, and our other agent will use Groq running in the cloud a 70 billion Meta model. And then we should get our financial report on Tesla at the end of it. Here it is. Groq was so quick we didn't even see it. There's uh the Groq taking the task and completing it. Here is the result. Our financial report on Tesla. It all looks great. Wasn't that easy?

</details>

---
*Source: Official Udemy lecture transcript (auto-captions, lightly cleaned). Notes in Hinglish for self-study.*
