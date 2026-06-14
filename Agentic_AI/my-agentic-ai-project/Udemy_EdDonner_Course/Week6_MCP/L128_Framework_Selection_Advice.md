# L128 — Day 5: Advice for Selecting Agentic Frameworks

> **Week 6 — MCP** · ⏱️ ~8m · 🎥 Lecture 128 of 131
> **Instructor:** Ed Donner · **Lecture ID:** 50769781

---

## 🎯 Ek Line Mein (TL;DR)

Ed ka seedha jawab — **"kaunsa framework choose karu?" galat sawaal hai**: framework selection **matter nahi karta** (sab me agent solution ban sakta hai, jo tumhe aur tumhari team ko suit kare wahi pick karo); asli important cheez hai Ed ke **10 pieces of practitioner advice**, jisme se pehle do yahan aate hain — **problem se start karo, solution se nahi**, aur **success metric (+ data) identify karo**.

---

## 📝 Hinglish Explanation (Detailed)

- **Trading floor project pe garv + sabse common sawaal:**
  - Ed **chuffed** (khush) hain ki capstone project itna achha bana — aur ye ek **commercial use of agents** ki taraf nod hai.
  - Course ke is point pe log thoda **frazzled** feel karte hain — itne saare projects aur frameworks dekhne ke baad sawaal aata hai: *"ab apna project shuru kar raha hoon, kaunsa framework select karu?"*

- **Ed ka jawab — framework selection doesn't matter:**
  - **Jo framework select karo wo actually matter nahi karta** — ye sabse important question hi nahi hai.
  - Har framework ke **pros and cons** hain; wo pick karo jo **tumhe jibe kare** — tumhari strengths, jahan tumhe help chahiye, aur **tumhari team ki skills/capabilities** ke hisaab se.
  - **Tum kisi bhi framework me agent solution build kar sakte ho** — jo enjoy karo, jiske saath best experience ho, wahi use karo.

- **Ed ki personal preference + covered frameworks ka quick compare:**
  - **OpenAI Agents SDK** — Ed ka go-to: **lightweight**, **stays out of the way**, coding me **flexibility aur control** deta hai. Ed ne isse **live projects** banaye hain, aur **MCP ke saath** other tooling bring-in karte hain.
  - **CrewAI** — **batteries included**: box me bahut kuch milta hai, tum bas **YAMLs** likho aur focus karo, saath me **low-code visualization tools** bhi — super convenient aur attractive for many.
  - **LangGraph** — famous for being **repeatable, reproducible**, aur **LangChain ecosystem** ke saath tightly integrated, including **LangSmith** for monitoring.

- **"DJ playing favorite tracks" — jo frameworks cover nahi hue:**
  - Ed ko log message karte hain *"X kyun nahi cover kiya?"* — DJ ki tarah har kisi ka favorite track nahi baja sakte; selection karni padi.
  - **Google ADK (Agent Development Kit):**
    - Increasingly popular; kuch hafte pehle tak infancy me tha, par ab **version 1 — production-ready** release ho gaya hai, kaafi companies involved hain.
    - Saath me Google ka announced protocol — **A2A (Agent-to-Agent)** — jo **MCP ka companion protocol** hai:
      - **MCP** tumhe **tools** se connect karta hai; **A2A** alag-alag **agents ko ek doosre ko discover** karne deta hai, capabilities exchange karne deta hai, aur agents ek doosre ko **call** kar sakte hain — chahe wo **different hardware, completely different setting** me run ho rahe hon.
      - Ye connectivity wala part **AutoGen Core** jaisa hai (heterogeneous agents interact karna — yaad hai?).
      - **Discoverability** idea: agents ek doosre se pooch sakte hain *"tum kya kar sakte ho?"* via **agent card** — jo **model card** jaisa hai, par agents ke liye.
    - Par A2A abhi **infancy** me hai — **community traction nahi** mila ab tak, to early to call ki ye MCP jitna popular hoga ya nahi (MCP ka role zyada immediate/obvious hai).
    - Positioning: ADK **OpenAI Agents SDK aur CrewAI ke beech** me hai — thode batteries included + kuch UI stuff bhi.
  - **Hugging Face smolagents** — very popular (kuch time pehle aur bhi zyada tha), **super simplistic** — OpenAI Agents SDK ke shades: simple raho, raaste se hat jao.
  - **Pydantic AI** — bada following, **fun to work with**, OpenAI Agents SDK se bahut similar — actually **OpenAI Agents SDK ne announcement me Pydantic AI ko shout-out** diya tha ki unse inspire hue; isme **LangGraph ke elements** bhi hain.

- **Ed ne ye frameworks kyun chune:**
  - Taaki tumhe agentic frameworks ki **techniques ka poora gamut** ka flavor mile — ab tum **koi bhi naya framework easily adopt** kar sakte ho.
  - Google ADK ka tutorial kholo to **familiar concepts** hi milenge — **tools, structured outputs** waghaira.
  - Proof: ek student ne **community contributions** me ek week ka **Google ADK solution** contribute bhi kiya hai — same techniques.
  - **Overall message: framework selection me bogged down mat ho** — jo land kare use pick karo; ye important stuff nahi hai.

- **Ab important stuff — 10 pieces of advice (personal, practitioner experience; disagree karne ki choot hai):**
  - **Advice #1 — Problem se start karo, solution se nahi:**
    - Bahut log (especially **agentic hype** ki wajah se) space me **solution-in-mind** ke saath aate hain: *"I want to use agents for X"*.
    - Ye **red flag** hai — pehle focus karo **problem** pe: X kya hai, kya wrong hai. Agar realize ho ki agent solution sach me right way hai, **tab** agents use karo. **Problem → solution**, ulta nahi.
  - **Advice #2 — Success metric identify karo:**
    - Problem mil jaye to wo **metric** identify karo jisse measure karoge ki problem **successfully solve** hui ya nahi — ye tumhara **North Star** hai (closer ja rahe ho ya further).
    - Metric dhundhna **difficult** ho sakta hai — ye task ka important part hai, isi se start karo.
    - **Associated (10 me se nahi, par zaroori): data curation** — samjho kaunsa data hai, kaunsa chahiye, aur use curate karo taaki **metric measure** ho sake. Standard data science stuff — par agentic solutions me log often bypass kar dete hain kyunki wo *"agents should do blah"* pe focused hote hain.
  - (Baaki advice agle lectures me continue hoti hai.)

---

## 🔑 Key Concepts / Important Terms

| Term | Simple Hinglish Meaning |
|------|--------------------------|
| **Framework selection** | Ed ka verdict: matter nahi karta — sab frameworks me agent solution ban sakta hai; jo tumhe/team ko suit kare wo lo |
| **OpenAI Agents SDK** | Ed ka go-to — lightweight, out of the way, full flexibility/control; MCP ke saath pair karte hain |
| **CrewAI** | Batteries-included framework — YAML configs likho, bahut kuch box me milta hai + low-code visualization |
| **LangGraph** | Repeatable/reproducible graphs, LangChain ecosystem + LangSmith monitoring ke saath tight integration |
| **Google ADK** | Agent Development Kit — naya, ab v1 production-ready; OpenAI SDK aur CrewAI ke beech ki positioning |
| **A2A (Agent-to-Agent)** | Google ka MCP-companion protocol — agents ek doosre ko discover/call karein across hardware; abhi infancy me, traction pending |
| **Agent card** | Model card jaisa, par agent ke liye — agent apni capabilities advertise karta hai (A2A discoverability) |
| **smolagents** | Hugging Face ka super-simplistic framework — OpenAI Agents SDK jaisi "keep it simple" philosophy |
| **Pydantic AI** | Popular, fun framework — OpenAI Agents SDK ka inspiration source (official shout-out), LangGraph ke bhi elements |
| **Advice #1: Problem-first** | "I want agents for X" = red flag; pehle problem samjho, phir decide karo ki agents right solution hain ya nahi |
| **Advice #2: Metric (North Star)** | Success measure karne wala metric pehle define karo + uske liye data curate karo |

---

## 💡 Backend Dev Ke Liye Note (aapke liye)

- **Ye course ki sabse valuable career-advice lectures me se ek hai** — framework war me time waste karna waise hi hai jaise Flask vs FastAPI vs Django pe mahino debate karna: concepts (tools, structured outputs, handoffs, guardrails) transferable hain, syntax nahi. Hiring interviews me bhi "problem-first" framing hi senior signal hai.
- **A2A vs MCP** ko aise socho: **MCP = OpenAPI/Swagger for tools** (ek service apne endpoints describe karti hai), **A2A = service discovery/registry (Consul/Eureka) for agents** — agent card ek service manifest hai. Aur jaise har naya RPC protocol adoption ki ladai ladta hai (gRPC vs Thrift vs Avro), A2A bhi abhi traction ka wait kar raha hai.
- **Advice #1-2 = classic engineering discipline:** "I want agents for X" wahi anti-pattern hai jo "let's use Kafka/microservices for everything" tha. Aur metric-first approach = pehle SLOs/observability dashboards define karna, phir feature shipping — agentic systems me eval metric ke bina tum blind deploy kar rahe ho.
- **L129 ke 10 lessons sirf theory nahi** — wo hamare poore repo ke labs me practically dikhte hain (Week 1 ke evaluator-optimizer se lekar Week 6 ke trading floor tak), to unhe padhte waqt apne likhe labs se map karna.

---

## 🧠 Takeaway (yaad rakho)

1. **Framework selection is NOT the important question** — sab me build ho sakta hai; jo tumhe aur team ko suit kare wo pick karo.
2. **Ed ka go-to: OpenAI Agents SDK + MCP** (lightweight, control); CrewAI = batteries included + YAML; LangGraph = reproducible + LangSmith.
3. **Google ADK ab production-ready (v1)** hai aur **A2A protocol** laya hai — MCP tools connect karta hai, A2A agents ko aapas me discover/call karne dega (abhi infancy me).
4. **Advice #1: Problem-first** — "I want agents for X" bolna red flag hai; problem se solution tak jao, ulta nahi.
5. **Advice #2: Metric + data** — success ka North Star metric define karo aur use measure karne ka data curate karo, tabhi aage badho.

---

<details>
<summary>📜 Full English Transcript (original, click to expand)</summary>

Well, as you can probably tell, I'm quite chuffed about that project. I think it came together so nicely, and I really do hope that there's a lot to learn from it and seeing it together like that. And I love the fact that it is actually a nod to a commercial use of agents. So a question that I get quite often at this point that people that have got to this point in the course, is that people feel a bit frazzled by everything that we've covered, like thinking back to the different variety of projects and frameworks and left with the question, okay, so now that I'm embarking on my own project, which of these frameworks do I select? What do I choose? And I'm here to give you that answer. I want to tell you exactly which framework you should select. And the answer is the framework that you should select doesn't actually matter. It's not the most important question. And in a minute I'm going to take you through what I think does matter and the sorts of things you should be thinking about when you embark on your project.

Look, the different frameworks have different pros and cons, and you should pick the one that just suits you. The one that you jibe with the most, that suits your kinds of strengths and the places where you need help and also the skills and capabilities of your team as well. I find that, as you probably know, I like OpenAI Agents SDK because it's lightweight, it stays out of the way, and it gives you a level of flexibility and control that I like to be able to code with. But I fully recognize that there are other frameworks like CrewAI, that are much more batteries included, where you get a lot in the box, you get, you know, you just write your YAMLs and you can focus on your YAMLs and a lot comes along for the ride, and that can be super convenient and really attractive. And they even come with some of the low code tools that let you visualize this too. So there are lots of benefits to using the other frameworks too, but you can build an agent solution in any of them. So really you just pick the one that works for you the best, that you enjoy using and that you have the best experience with. Sure, my go-to is to use OpenAI Agents SDK. I've used it a lot. I've used it to build projects which are live. And of course I use MCP as well to bring in other tooling. Um, but I totally get that the batteries included ones work better for others and that there are pros and cons. LangGraph of course, famous for the way that it's so very repeatable, reproducible, and so tightly integrated with the LangChain ecosystem and with things like LangSmith for monitoring. So plenty of pros and cons.

And there are also other frameworks too. Now I feel a bit like a DJ that is up there trying to play the favorite tracks that everyone's going to like, and I always miss one that someone's favorite. And I've had some people message me and say, why didn't you cover whatever? And they're hurt by this and I'm sorry, I had to pick a selection. Some of the other, the sort of the ones that almost made it: Google Agent Development Kit, ADK, that's becoming increasingly popular. It's very new and it was still in its infancy even a few weeks ago. But they've just released what they're calling the version one that's ready for production for the first time and it's starting to get more traction. They've got a lot of companies involved. ADK also comes with a protocol that Google has announced, called A2A, Agent to Agent, which is meant to be a sort of companion protocol to MCP. But while MCP lets you connect to other tools, A2A would allow different agents to discover each other, to be able to exchange information about what they can do, and agents to be able to call each other, even if they're running on different hardware in a completely different setting. Now, that second part of it, this connectivity piece, that's a bit similar to AutoGen Core, if you remember, that same kind of idea. So it's got that AutoGen Core angle to it, allow different heterogeneous agents to interact. And it's also got this discoverability idea that agents will be able to ask each other, okay, what are you capable of doing, through a sort of agent card, which is a bit like a model card, but for agents. But this is also still in its infancy. It hasn't yet got community traction, so it's a bit too early to call whether this is going to be as popular as something like MCP that has a more immediate, more obvious role to play. So that's Google Agent Development Kit, which is somewhere in between OpenAI Agents and also it's got some shades of CrewAI because it has a little bit more of batteries and it's got some user interface stuff as well.

Hugging Face smolagents, very popular. Uh, it was more popular a while ago and it's super simplistic. It's very much again, shades of OpenAI Agents SDK — keep it simple and keep out of your way, which is great. Pydantic AI has a big following. It's really fun to work with. It's also very similar to OpenAI Agents SDK. In fact, OpenAI Agents SDK said that they were inspired by some of the Pydantic AI work, and they gave a shout out to Pydantic AI in their announcements. And, uh, Pydantic AI also has some elements of LangGraph in there too.

But here's the thing. I chose the frameworks that I chose because I felt that it gives you a great flavor of the gamut of different kinds of techniques that are used in agentic frameworks. And I feel like it prepares you really well to adopt any of these. If you just bring up Google ADK and go through their tutorial and how-to, you'll see so many familiar concepts that will be like, okay, sure. And in fact, you'll see that already a student has contributed in the community contributions a Google SDK solution for one of the weeks, which is so cool. And so you can see that it's just very, very similar, the same kind of techniques. And so I do encourage you, if one of these is one that you really want to explore as well, then go and take a look at it. But I think you'll find it's super easy to pick up — same kinds of concepts as we've used: tools, structured outputs and so on. But the overall message is don't get bogged down in framework selection. They all have their pros and cons. You can focus on the one that lands well for you. It's not the most important stuff.

Let's talk about the important stuff. So I'm going to give you ten pieces of advice, ten things that I think matter. And this is personal advice, so you can feel free to disagree with me. Reject this. This is not necessarily the, you know, the gospel. This is simply my experiences, my advice as a practitioner in the field. First things first, and this is general advice. In a lot of cases I do find, and perhaps particularly in agentic AI, that a lot of people come into this space with the solution in mind. They come in and say, I want to use agents for X, and it's super important to say that that is a bad way of thinking about it. You should always catch yourself with a little red flag if you're coming into building something and the starting point is "I want agents to do X". First of all, focus on the problem you're solving and what is X, what is wrong, and go with an agent solution if you realize that that is in fact the right way to solve that problem. Start with the problem. Go to the solution, not the other way around. I know it's the kind of thing that everyone says. You probably heard that a million times, but particularly with agents, there's so many people, because of the agentic hype, that are just jumping on — I need an agent for this, I need an agent for that. Start with the problem.

Second piece of advice is that once you've got a problem, identify the metric that you will use to measure whether you have successfully solved that problem. This is like a standard piece of data science advice, but this can be your North Star as you're working, to see whether you're getting closer or further from solving the problem. And finding that metric can be really difficult. And that's something which is an important part of the task, which you have to start with. And associated with that — it's not one of the ten, but along with the metric — you have to be able to curate the data that will allow you to measure that metric. So understanding the data that you've got, the data that you need, and making sure that you curate that data in order to measure that metric. This is all pretty standard data science stuff. But often again, I think particularly with agentic solutions, people sometimes bypass this because they're so focused on "I want my agents to do blah".

</details>

---
*Source: Official Udemy lecture transcript (auto-captions, lightly cleaned). Notes in Hinglish for self-study.*
