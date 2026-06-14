# L62 — Day 4: Crew AI for Coding Tasks

> **Week 3 — CrewAI** · ⏱️ ~8m · 🎥 Lecture 62 of 131
> **Instructor:** Ed Donner · **Lecture ID:** 49821201

---

## 🎯 Ek Line Mein (TL;DR)

Is lecture me hum ek **coder agent** banate hain jo Python code **likh bhi sakta hai aur run bhi** — aur CrewAI me ye "advanced" feature sirf do flags se on ho jaata hai: **`allow_code_execution=True`** + **`code_execution_mode="safe"`** (safe mode = code **Docker container** ke andar sandboxed chalta hai).

---

## 📝 Hinglish Explanation (Detailed)

- **Aaj ka goal**: Ek agent banana jo sirf code *generate* nahi karta, balki us code ko **execute** bhi karta hai — problem do, wo code likhega, chalayega, output dekhega, aur results interpret karke aage action lega.
- **Docker sandbox kyun?** Agent ka generated code aapke machine pe directly chalana risky hai. Isliye CrewAI use ek **Docker container** me run karta hai — ek **sandboxed, ring-fenced environment** jisme code aapke computer ko damage nahi kar sakta. Docker zaroori nahi hai, but strongly recommended.
- **Sounds hard, but it's not**: Ed kehte hain ye "next level" task lagta hai, but CrewAI me bas itna karna hai:
  - Agent pe **`allow_code_execution=True`** set karo → agent code execute kar sakta hai.
  - **`code_execution_mode="safe"`** set karo → agar Docker installed hai to code Docker container me chalega (direct host pe nahi). Ed ko itna disbelief tha ki unhone Docker band karke verify kiya ki ye sach me container use kar raha hai!
  - Yahi jagah hai jahan **frameworks like CrewAI shine** karte hain — itna complex kaam itna simple bana dete hain.
- **"Coder agent" terminology**: Jab log "coder agent" bolte hain, to matlab sirf "code deliver karne wala agent" nahi hota. Asli matlab: agent jo **Python generate kare AUR run kare** as a *means to an end* — yaani code-writing ek bade problem ko solve karne ka step hai, end goal nahi. (Confusingly, hamara is week ka project literally code likhne wala hi hai — but run karne ki ability hi cool part hai.)
- **Project setup (familiar drill)**: Cursor me crew folder kholo, terminal me **`crewai create crew coder`** — scaffolding ban jaati hai. Provider me **OpenAI + GPT-4o-mini** choose karo, key ki zaroorat nahi (already env me hai).
- **`agents.yaml` config — single agent is baar**:
  - **role**: "You are a Python developer" — Python code likhta hai assignment achieve karne ke liye. `{assignment}` as **input placeholder** jo `run` method se inject hota hai.
  - **goal**: First **plan** how the code will work → then **write** the code → then **run it and check the output**. (Plan → Write → Run → Verify loop.)
  - **backstory**: "A seasoned Python developer with a knack for writing clean, efficient code."
  - **llm**: GPT-4o-mini — Cursor ke suggestion pe `provider/model_name` format use kiya (e.g. `openai/gpt-4o-mini`), jo cleaner lagta hai.
- **`tasks.yaml` — single task**:
  - Task: "Write Python code to achieve this assignment."
  - **expected_output**: Ek **text file jisme code BHI ho aur code ka output BHI** — `code_and_output.txt` as `output_file`.
  - Dono kyun? Kyunki Ed point prove karna chahte hain ki agent ne sach me code likha, run kiya, output mila — sirf final answer pe trust nahi karna, **double-check** kar sakein ki wo sahi kar raha hai.
- **`crew.py` module**: Default templating delete karo, config relationships rakho. Ed ne comment me **Docker Desktop install link** bhi daala — Mac/Windows/Linux pe one-click install. Engineering background walo ke liye Docker familiar hoga; nahi to install karke chhod do, bas installed hona chahiye.
- **Coder agent definition (`@agent` decorator ke saath)**:
  - `config=self.agents_config['coder']` (YAML se), `verbose=True` as usual.
  - **`allow_code_execution=True`** — bas, ab code execute kar sakta hai.
  - **`code_execution_mode="safe"`** — Docker container me run hoga, host platform pe nahi.
  - **`max_execution_time=30`** — 30 seconds ki limit, simple task hai. Runaway code se bachne ke liye good practice.
  - **`max_retry_limit=5`** — agar code fail ho to agent 5 baar tak retry kar sakta hai (likho → run karo → error dekho → fix karo loop).
- **Task definition (`@task` decorator)**: Coding task banaya; `expected_output` code me dobara dene ki zaroorat nahi kyunki YAML task me already defined hai. Iske baad bas `@crew` function method banana baaki hai (next lecture me continue).

---

## 🔑 Key Concepts / Important Terms

| Term | Simple Hinglish Meaning |
|------|--------------------------|
| **Coder agent** | Agent jo Python code likhta hai AUR run karta hai — code-execution as a step towards bada problem solve karna, not just code delivery |
| **`allow_code_execution=True`** | Agent parameter jo code execute karne ki power on karta hai — bas yahi ek flag |
| **`code_execution_mode="safe"`** | "Safe" mode = generated code **Docker container** me chalta hai, aapke host machine pe nahi |
| **Docker container / sandbox** | Ring-fenced, isolated environment — code yahan chal sakta hai but aapke computer ko damage nahi kar sakta |
| **`max_execution_time`** | Code run ki time limit (yahan 30s) — infinite loop / runaway code se protection |
| **`max_retry_limit`** | Agent kitni baar fail hone pe retry kar sakta hai (yahan 5) — self-healing write→run→fix loop |
| **`{assignment}` input** | YAML me placeholder jo `crew().kickoff(inputs=...)` / run method se inject hota hai |
| **`output_file`** | Task output file (`code_and_output.txt`) — code + uska execution output dono, taaki verify kar sakein |
| **Plan → Write → Run → Check** | Agent goal me explicitly likha workflow — pehle plan, phir code, phir execute, phir output verify |

---

## 💡 Backend Dev Ke Liye Note (aapke liye)

- **Docker sandboxing aap pehle se jaante ho** — ye wahi pattern hai jo CI runners (GitHub Actions containers) ya serverless sandboxes use karte hain: untrusted code ko ephemeral, ring-fenced container me chalao. Difference bas itna ki yahan "untrusted code" LLM-generated hai. Production me `code_execution_mode="safe"` ko non-negotiable maano — unsafe mode = `eval()` on steroids on your host.
- **`max_execution_time` + `max_retry_limit`** ko aap request timeout + retry policy (jaise `tenacity` ya HTTP client retries) ki tarah socho — but yahan retry loop *self-healing* hai: agent error output padh ke code fix karke dobara try karta hai. Ye exponential-backoff-with-blind-retry se smarter hai.
- **YAML me `expected_output` ek hi jagah rakho** — Ed ne code-side `expected_output` hata diya kyunki YAML me already tha. Same DRY principle jo aap config management me follow karte ho: single source of truth, warna do definitions drift karengi.
- **Hands-on lab**: is lecture ka code khud chalane ke liye `Practical/lab4_engineering_team.py` run karo (is repo me, `uv run` se chalta hai, Groq pe free via LiteLLM). Note: hamare labs course se thoda alag hain — self-contained code-style hai (YAML scaffolding nahi), aur **Docker code-execution ki jagah hum generated code ko khud compile + unittest karte hain** (lecture ka `allow_code_execution` + Docker wala part lab me simulate hota hai, sandbox nahi chahiye).

---

## 🧠 Takeaway (yaad rakho)

1. **Coder agent = code likho + chalao + output verify karo** — execution ek means to an end hai, sirf code generation nahi.
2. CrewAI me code execution on karna = **`allow_code_execution=True`**; bas ek flag, koi complex setup nahi.
3. **`code_execution_mode="safe"`** = Docker container me sandboxed run — Docker Desktop installed hona chahiye, host machine safe rehti hai.
4. **`max_execution_time=30`** aur **`max_retry_limit=5`** lagao — runaway code rokta hai aur agent ko fail hone pe self-fix retry loop deta hai.
5. Output me **code + execution output dono** mangwao (`output_file`) taaki aap double-check kar sako ki agent ne sach me sahi kaam kiya.

---

<details>
<summary>📜 Full English Transcript (original, click to expand)</summary>

And now for something completely different. We are going to work on making an agent that knows how to code, how to write Python code, how to write software, and a little bit more than that, it's not only going to know how to write software, but how to run it as well. So this is challenging and complex, but it's possible to have an agent in Crew, in the CrewAI environment, which has this ability. Not only is it able to take a problem that you set it, it can write code to solve that problem. It can then execute that code in a Docker container. It doesn't need to, but it's good to have it run it in a Docker container, which means that it is a sort of sandboxed, ring-fenced environment that doesn't have access to do damage to your computer because it's in this protected world, and then it can run the code, it can execute it in that container and look at the results and interpret those results to take on some more action.

So as I say this, this is a really advanced task. This is something that's taking us to the next level, and it's going to be hard and complex. Except it's not going to be hard or complex. You probably saw that coming, but it is going to be as simple as when we create an agent, we're going to say allow code execution equals true. And that's going to be it. And then it's going to be able to execute code. And if you say code execution mode equals safe, then if you have Docker installed on your system, and I will show you how to install Docker if you don't, it will run it in a Docker container. And it seems almost so good. It's uh, it's crazy. I had to like close down Docker to make sure that it failed when it was closed, because I almost couldn't believe it was happening. It's that simple. And this is where frameworks like CrewAI really stand out because they make things like this so very easy to do.

It's worth mentioning that this kind of system is sometimes called a coder agent. There's various other names for it, you hear. And it's worth knowing that when people talk about coder agents, they're not just talking about agents that can deliver code. Agents that are able to generate Python, but also this ability to generate Python and then run that Python as steps towards solving a greater problem, so that this is more a means to an end than just saying it is something which writes code. Now, confusingly, our project for this week, we are going to build something that writes code. But the fact that it can run it too is kind of cool. So that is the introduction. And with that, let's go and actually build something like this. Let's build something that can write code and can run it. Let's do that. See you in a sec.

Okay. Welcome back to Cursor. Welcome back to the crew folder. And I'm going to open up a new terminal and go into that third folder. And you know how to create a crew project so well now that you have it committed to memory. But you know that it's crewai create crew, and then the name of the project, which we will call coder, and it's going to build the directories, it's going to do the scaffolding. All we have to say is that we want OpenAI and we want GPT-4o-mini, and we don't need a key. And kabam, we have all of the folder structure. Great.

Okay. So as always, the first thing we do is we go into the config and we start by defining our agents. So what agents are we going to have? We're only going to have one this time. It's going to be a very simple agent. Let me just remove this so we can see what we're doing. Let's delete the scaffolding and put in our coder agent. So we're going to say you are a Python developer. That's the role. You write Python code to achieve this assignment. And then we pass in the assignment — that is the input that will be set in the run method. First you plan how the code will work. Then you write the code, then you run it and check the output. Backstory: a seasoned Python developer with a knack for writing clean, efficient code. And we can use GPT-4o-mini. Yes, you can do it either way, but we'll do what Cursor suggests. Change it to have the provider and the name of the model, which looks a bit better. Okay, so there we go. That's pretty simple. That was our single agent.

And we're going to have one single task. Let's put it in here. It is: write Python code to achieve this assignment. A text file that includes the code. So the output we want from it is a text file that includes the code and the output of the code. We want it to put both in the output. So I've called it code and output text as the output. So that is what we want it to do. So because I really want to make the point that it's going to write code, run it, get the output, and it's going to think all of this through and then respond with all of that. We don't just want it to give us the output, because we want to double check what it's doing is right.

Okay, now we know we have to go to the crew module. Let's do that next. Okay. Here we are in the crew module that I've just gone through and deleted the templating stuff that's in there by default. And so we're just leaving our config relationships here. And I'm just going to put a little comment here. So this is a link to how you can install Docker if you don't already have it installed. And this is just literally the Docker Desktop web page for you. And as it does claim, it is a one-click install for Mac or Windows or Linux. And it should be as simple as that. Many of you, I suspect, from an engineering background, already know and love Docker. If you don't, then welcome to it. This should be as simple as installing it, and then it's installed and you can then leave it be, but you will need to have it installed for this to work properly in a Docker setting.

Okay. So now we are going to create our agent. We start with an agent decorator to make sure it goes in the right place. And we are going to create a coder. I'm going to return an agent. This is the usual fare. So what is our agent going to do? Well, the config is going to be the config that we set in the YAML file. But then we'll have verbose being true as usual. Now what else do we want? We now want this super complex, super hard step of making sure that this agent has the power to execute code, which is as simple as allow code execution equals true. There it is. Now it can execute code. There's this step of saying code execution mode is safe, and now that ensures that it runs it within a Docker container so that it's not just running the code on your platform. Now we can say max execution time. This is a good one to have in there. And we're going to say 30 seconds. This is going to be a simple task. And max retry limit. Let's give it five retries. It can have up to five times of trying this. And that is our coder agent.

So now we have a task. And the task is going to be a coding task. And I rather suspect that we can just use what Cursor does, but we can take out expected output because we already defined the expected output in the task itself. So it's not needed again. All right. So there we go. We have our agent and our task defined. Now we just have to do the crew function method just below.

</details>

---
*Source: Official Udemy lecture transcript (auto-captions, lightly cleaned). Notes in Hinglish for self-study.*
