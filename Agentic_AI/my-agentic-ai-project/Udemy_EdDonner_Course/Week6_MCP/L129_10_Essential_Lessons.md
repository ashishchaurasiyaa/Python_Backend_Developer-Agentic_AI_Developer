# L129 — Day 5: 10 Essential Lessons for Building Agent Solutions

> **Week 6 — MCP** · ⏱️ ~8m · 🎥 Lecture 129 of 131
> **Instructor:** Ed Donner · **Lecture ID:** 50769785

---

## 🎯 Ek Line Mein (TL;DR)

Ed ke **10 essential lessons** ka second half (lesson 3–10) — **workflows over autonomy**, **bottoms-up building**, **start simple**, **pehle expensive models** se prove karo, **memory = bas prompt me context**, zyada tar problems **better prompting** se fix hoti hain, **traces hamesha check karo**, aur sabse important — project start pe **software engineer hat utaar ke scientist hat pehno** aur experiment karo.

---

## 📝 Hinglish Explanation (Detailed)

- Ye **advice/wrap-up lecture** hai — koi code ya lab nahi. Ed apne saalon ke experience se **10 lessons** de raha hai (lesson 1–2 pichhle lecture me the); yahan **lesson 3 se 10** cover hote hain.

### Lesson 3 — Favor Workflows Over Autonomy (Start Me)
- Naya agent solution banate waqt **fully autonomous system me rush mat karo** — pehle **simple workflows** banao jo step-by-step kaam karein.
- OpenAI Agents SDK me agent-to-agent ke do known tareeke hain: **tools** (ek agent doosre ko tool ki tarah call kare) aur **handoffs** (control pass karna). Par Ed ek **teesra approach** suggest karta hai jo humne **deep research agent** me use kiya tha:
  - **Plain Python code** se har agent call **isolation me** karo — `runner.run()` call karo, output lo, phir agla `runner.run()` karo. Organized, step-by-step, Python-coded workflow.
- Baad me jab ye chal jaaye, tab isko **handoffs/tools me convert** karo aur **autonomy add** karo — ek agent ko zyada responsibility do. Par **shuruaat hard-coded/Python-coded workflows se**.

### Lesson 4 — Bottoms Up, Not Top Down
- Software engineering background walon (Ed jaise) ki common galti: blank sheet pe **bada agent architecture diagram** bana dena. Ed ke hisaab se ye best approach **nahi** hai.
- Better: **bottoms up** — problem ka ek **chhota hissa lo, ek simple agent (ek LLM call)** se usko **achhe se solve karo**, phir agla agent add karo. Platform **discover karte karte** banao — kya kaam karta hai, kya nahi.
- Kabhi-kabhi dono angles (thoda top-down + thoda bottoms-up) sahi hote hain, par agentic workflows me Ed **bottoms-up favor** karta hai — kyunki pehle **discover** karna padta hai ki tumhare LLMs ke saath kya perform karega.

### Lesson 5 — Start Simple, Phir Complicate Karo
- Pehle **simple solution working** karao, tabhi platform complicated banao.
- Ed ko log **hundreds of lines ke massive solutions** bhejte hain — "broken hai, fix kar do". Answer: **aise kaam nahi karta** — itne bade tangle me dekhna impossible hai ki problem kahan hai.
- Sahi approach: **chhota simple problem solve karo, really well**, phir **gradually expand** — har building block solve karke jodte jao, tab bada agent workflow sahi se chalega. Agar sab kuch ek saath complex bana diya aur answer galat aaya, to **dhoondhna namumkin** ki kahan dekhna hai.

### Lesson 6 — Start With The Highest-End Models (Opposite Point!)
- Interesting ulta point: shuru me **sabse powerful models** use karo, **small datasets** ke saath — jaise **GPT-4.1** ya **Claude 4 Sonnet** (Opus shayad zyada expensive ho jaaye).
- Logic: pehle **prove karo ki jo tum karna chahte ho wo theoretically possible hai**. Expensive model se kaam ho gaya = idea valid.
- Phir **cheaper models** pe move karo — **GPT-4.1 mini/nano** — aur jaise-jaise prompts ko **more instructive aur precise** banaoge, lighter models se bhi **similar performance** mil sakti hai.

### Lesson 7 — Memory = Bas Relevant Context In The Prompt
- Subtle lesson: log **memory types** me uljhe rehte hain — Ed ke hisaab se ye construct **"overworked"** hai.
  - **Short-term memory** = usually bas **conversation so far**.
  - **Long-term memory** = usually **RAG retrieval** database se, ya **knowledge graph** (jaisa trading project me use kiya).
- Asli baat: **saari memory techniques bas "relevant context dhoondh ke prompt me daalne" ke alag-alag tareeke hain**. End me sab kuch **prompt me kya jaa raha hai** pe depend karta hai.
- Isliye: **prompts dekho** — kya include ho raha hai; tools dekho — kya information retrieve ho rahi hai; aur ensure karo ki LLM ko **question answer karne ke liye sahi context** mil raha hai. Memory ke "kinds" me bogged down mat ho — focus karo: **LLM ko kya information chahiye, aur kya wo prompt me hai?**

### Lesson 8 — Zyada Tar Problems Better Prompting Se Fix Hoti Hain
- Agent systems aur LLMs ki **most difficulties prompting improve karke** solve hoti hain.
- Log poochte hain: "**Fine-tuning** use karoon? RAG ke liye **different encoder LLM**?" — sophisticated cheezein. Often sahi answer: **bas prompts pe kaam karo** — simpler, **more directive, more instructive** banao; agar galat output de raha hai to **explicitly mana karo** aur **good output ke examples** do.
- **Prompts pe kaam karke hi bahut door tak ja sakte ho.**

### Lesson 9 — Traces Hamesha Dekho
- **Great discipline**: agents sahi answers de rahe hon **tab bhi traces check karo** — kahin **extra tool call** ya koi "weird stuff" to nahi ho raha.
- Ed khud confess karta hai ki wo aksar traces check karna skip kar deta hai jab sab "working" lagta hai — aur jab check karta hai to **aksar koi gotcha milta hai** jo fix ho sakta hai.
- Rule: agent system banate waqt **always traces me verify karo** ki sab waisa hi behave kar raha hai jaisa expect kiya.

### Lesson 10 — Be A Scientist (Sabse Important!)
- **AI/LLM engineer = do hats**: ek **software engineering hat**, ek **data scientist hat**.
- Naye project ke **starting point pe software engineering hat firmly utaaro** aur **scientist hat pehno** — **experimentation aur R&D** ke saath comfortable raho.
- Log poochte hain: "Model A, B ya C? Ye technique ya wo? Kaunsa tool?" — Answer: **try them ALL**. Experiment karo, apna **overall business metric** dekho jo success gauge karta hai, aur usse judge karo kaunsi technique better hai.
- Ed ne is topic pe ek **poora guide** likha hai (course guides me, last ones me se ek — "how to build your own projects").
- **R&D ka koi shortcut nahi.** Ed ke khud ke instincts bhi **aksar galat** nikalte hain — isliye instinct pe trust mat karo (Ed ke bhi nahi!), **experiment karke khud discover karo**.

---

## 🔑 Key Concepts / Important Terms

| Term | Simple Hinglish Meaning |
|------|--------------------------|
| Workflows over autonomy | Start me fully autonomous nahi — step-by-step Python-coded workflow banao |
| "Third approach" | Tools/handoffs ke alawa: plain Python se har `runner.run()` call isolation me (deep research jaisa) |
| Bottoms-up building | Ek simple agent se shuru karo, discover karte karte platform banao — big architecture diagram pehle nahi |
| Start simple | Chhota problem really well solve karo, phir gradually expand — warna debug impossible |
| High-end models first | GPT-4.1 / Claude 4 Sonnet se prove karo ki idea possible hai, phir mini/nano pe optimize karo |
| Memory (short-term) | Usually bas conversation so far |
| Memory (long-term) | RAG retrieval / knowledge graph — fancy naam, kaam ek hi |
| Context engineering | Saari memory = relevant material dhoondh ke prompt me daalna — "it's all about the prompt" |
| Better prompting | Most fixes: directive/instructive prompts + good output examples (fine-tuning se pehle) |
| Traces discipline | Working system me bhi traces check karo — extra tool calls / gotchas milte hain |
| Scientist hat | Project start pe experimentation/R&D mode — sab options try karo, business metric se judge karo |
| Business metric | Success ka overall measure jo batata hai kaunsi technique/model better perform kar raha hai |

---

## 💡 Backend Dev Ke Liye Note (aapke liye)

- **Ye course ki sabse valuable career-advice lectures me se hai** — code zero hai, par ye 10 lessons aapke **poore repo ke labs me practically dikhte hain**: deep research lab me Python-coded sequential `runner.run()` workflow (Lesson 3), har week ka lab1→lab4 progression bottoms-up/simple-first hai (Lessons 4–5), trading-floor lab ka custom trace pipeline Lesson 9 ka embodiment hai, aur memory servers Lesson 7 ("sab context hi hai") ko prove karte hain.
- **Lesson 3 = orchestration vs choreography debate** jo aap microservices me jaante ho: pehle ek plain **service-layer pipeline** (explicit Python orchestrator) likho, Temporal/event-driven choreography baad me. Handoffs = choreography (control distribute), Python workflow = orchestration (control centralized) — debugging me orchestration hamesha aasaan.
- **Lesson 6 "make it work, then make it cheap" = premature optimization rule LLM-flavor me.** Bilkul jaise aap pehle Postgres pe naive query likh ke correctness prove karte ho, phir index/cache lagate ho — pehle Claude 4 Sonnet se correctness, phir nano/mini + tighter prompts se cost optimization. Model downgrade ek **perf-tuning pass** hai, architecture decision nahi.
- **Lesson 9 traces = OpenTelemetry discipline.** "Sab green hai to bhi spans dekho" wahi habit hai jo aap APM dashboards (Grafana/Datadog) ke saath rakhte ho — silent extra tool call agentic world ka N+1 query problem hai. Aur **Lesson 10** = backend dev ke liye mindset shift: deterministic systems me design upfront hota hai, LLM systems me **A/B-test-style experimentation** hi design process hai.

---

## 🧠 Takeaway (yaad rakho)

1. **Autonomy baad me, workflow pehle** — plain Python se step-by-step `runner.run()` calls; tools/handoffs upgrade hain, starting point nahi.
2. **Bottoms-up + start simple** — ek simple agent ko really well chalao, phir expand; bada complex system pehle banaya to debug impossible.
3. **Expensive model se prove karo, cheap model se ship karo** — GPT-4.1/Claude 4 Sonnet → mini/nano, prompts ko precise banate hue.
4. **Memory ka mystique chhodo** — short-term ho ya knowledge graph, sab "relevant context prompt me daalna" hai; aur most fixes better prompting se aate hain, fine-tuning se nahi.
5. **Traces hamesha check karo, aur scientist bano** — instinct (Ed ka bhi!) aksar galat hota hai; sab options try karo aur business metric se judge karo. R&D ka koi shortcut nahi.

---

<details>
<summary>📜 Full English Transcript (original, click to expand)</summary>

And moving on to the third piece of sage advice from me. It is to favor workflows over autonomy to start with. So when you're embarking on a new agent solution, it's tempting to rush into a fully autonomous solution. It's better to start by building something which is using simple workflows to take things step by step. Now, when you're working with OpenAI Agents SDK, there are a number of different ways to do this. You remember, you can use tools as a way to have one agent call out to another, and you can also use handoffs as a way that an agent can pass control to a different one. But actually I would suggest starting using a third approach. You might wonder what's the third approach? I don't remember that. Well, this is actually what we did with our deep research agent. The third approach is simply to use Python code to make each agent call in isolation. Call runner run, make a call to an agent, get an output, and then call runner run again and do things step by step in this organized way with Python code. Later, you can turn this into handoffs or tools, and you can add autonomy and give more activities to one agent, more responsibility. But start simple with hard coded or Python coded workflows.

So my fourth piece of advice is super important, particularly for people from a software engineering background such as myself. It's common to come into building agent solutions with a blank sheet of paper and draw some big agent architecture diagram. And in my view, that's not the best approach. It's better to work on these things bottoms up. Start with a simple agent. Take a small part of your problem and solve it well with one simple agent, one LLM call, and work on that until you've got that working well, and then add another agent and work bottoms up, building your platform as you discover what works well and what doesn't. Now, sometimes it's good to actually approach it from both angles. Do a bit of top down and a bit of bottoms up, but out of the two I would favor bottoms up in the case of agentic workflows, because you need to first discover what's going to perform well with your LLMs.

And the next one is very similar, which is to say, it's best to always start simple and then make your platform more complicated when the simple solution is working. I can't tell you how many people have sent me these massive, great solutions, hundreds of lines of code, and it's not giving them the outcome that they want. And they're saying, I don't know, it's broken. Why? Help improve this, fix it. And the answer is it doesn't work that way. You can't do that. It's too hard. You have to start small and simple, solve a simple problem and do it really well, and then gradually expand and with each of the building blocks, as you solve each problem, you put them together and you see the bigger agent workflow working well. But that's the right approach, because if you build everything and get complex and the answer doesn't match what you're looking for, it's impossible to know where to look. And so the simple key: start simple.

And a sort of opposite point to that, interestingly, is I recommend, when starting out, begin by using the highest end models to start with, with small data sets, such as using the GPT 4.1 or using Claude 4 right now, Claude 4 Sonnet — maybe not Claude 4 Opus, that might be a little bit too expensive — but start with the expensive ones so that you can make sure that in theory, what you're trying to accomplish will work. And then once you've got that working, you can then look to move to cheaper models like GPT 4.1 mini, or maybe GPT 4.1 nano. And as you make your prompts more and more instructive and precise, you may be able to achieve similar performance with lighter models. But as you start with your simple solutions, start with the high powered models so you can prove out what works and what doesn't.

And then the next piece of advice for you. This is a subtle one. So I see a lot of people getting caught up in trying to figure out different types of memory, which is a construct that I feel is like overworked. There's like short term memory, some people call it, which is usually just looking at the conversation so far. And then there's longer term memory, which is usually other words for looking up like a RAG retrieval in a database or using the kind of knowledge graph that we used in the trading project. The thing to keep in mind is that all of these different memory techniques are, in fact, just different ways of finding relevant context and shoving it in the prompt. It's all about what goes in the prompt at the end of the day. And so keep a clear mind about that and make sure that whilst you might use various tools and techniques for memory, at the end of the day, all you're doing is trying to find the right relevant material for the prompts. So look at the prompts, see what's being included there, look at the tools you're using and see what information is being retrieved. And make sure that you're giving the LLM the right context to be able to answer its question. And so rather than getting too bogged down in what kinds of memory you're using, focus on what kind of information does the LLM need to answer the question? And are you providing that information in the prompts?

Okay. And I'm almost done with this preachy advice for you. Let's go to number eight. It's very similar point again, which is that look, most of the difficulties that you come up against working with agent systems and with LLMs generally are fixed by better prompting and by experimenting with your prompts. People often message me and say, can I use fine tuning for this? Can I use a different encoder LLM for my RAG? All sorts of sophisticated stuff, when often the right answer is to just focus on the prompts. Make something a bit simpler, a bit more directive, a bit more instructive. If it's outputting one thing, then try and tell it not to. Give it some examples of what a good output looks like. You can get so far just by working on your prompts.

And a similar point again is also: look at the traces. Of course, this is a great discipline to get into, even if your agents seem to be working well and they're giving the answers that you expect. You should still be disciplined to go and check that everything is just as you want in the traces, just in case there's extra tool call happening, there's some weird stuff happening. Now, I'm often guilty of not going back and looking at the traces, particularly if things seem to be working, and then often when I do, I then discover that there is something in there, there is a gotcha that I can fix. And so it is so important, even if I don't take my own advice on this always — you should go in and check the traces. Always. As you're building your agent system, make sure things are behaving the way that you expect.

And I've left the most important piece of advice to the very end. And here it is. Look, being an AI engineer, being an LLM engineer involves wearing two hats: a software engineering hat, and a data scientist's hat. And when you're beginning your project, when you're at the starting point of building a new system, you need to be taking firmly off the software engineering hat and putting on that scientist hat and be a scientist. That means be comfortable with experimentation and R&D. People often come to me and say, which model should I pick, A, B, or C? Which technique should I use? This, this or this? Which tool should I use? And the answer is you should try them all. Try them. Experiment. Look at your overall business metric that you're using to gauge success, and use that to judge which of the different techniques is working better for you, and embrace the experimentation. It's absolutely key. I've put a whole guide about this. If you look in the guides, you'll see one — I think it's one of the last ones — is about how to build your own projects. And I talk a lot about this. There's no shortcut to R&D. Embrace being a scientist and researching and exploring and understanding what works well. I often have an instinct about the right way to go and build something, but it turns out my instinct is often wrong. So don't trust my instinct, but instead experiment and discover for yourself.

</details>

---
*Source: Official Udemy lecture transcript (auto-captions, lightly cleaned). Notes in Hinglish for self-study.*
