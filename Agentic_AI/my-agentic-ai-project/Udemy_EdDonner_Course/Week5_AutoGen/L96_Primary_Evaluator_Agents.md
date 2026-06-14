# L96 — Day 2: Primary and Evaluator Agents

> **Week 5 — AutoGen** · ⏱️ ~14m · 🎥 Lecture 96 of 131
> **Instructor:** Ed Donner · **Lecture ID:** 49821605

---

## 🎯 Ek Line Mein (TL;DR)

**LangChainToolAdapter** se LangChain ke saare tools AutoGen me directly use kar sakte ho, aur phir do **AssistantAgents** (primary + evaluator) ko **RoundRobinGroupChat** team me daal kar **TextMentionTermination("approve")** se ek self-correcting evaluator loop banta hai — but warning: AutoGen me LangGraph jaisa recursion limit nahi hai, to teams **infinite thrash** kar sakti hain.

---

## 📝 Hinglish Explanation (Detailed)

- **Part 1 — LangChain tools ko AutoGen me wrap karna:**
  - Pichle week (LangGraph) me hum **LangChain tools** use kar rahe the. AutoGen ka **`LangChainToolAdapter`** kisi bhi LangChain tool ko wrap karke usse **AutoGen tool** bana deta hai — bas ek wrapper hai.
  - Ye bada deal hai kyunki LangChain ka **huge tools community** hai — Serper search, file tools, Python REPL, push notifications — sab kuch ab AutoGen ecosystem ke andar available ho gaya.
  - Lecture me 3 cheezein import hoti hain: **`GoogleSerperAPIWrapper`** (Google search via Serper API), **`FileManagementToolkit`** (ek directory se files read/write karne ka toolkit), aur generic **`Tool`** class of LangChain.
  - **Task prompt:** "JFK (New York) se London Heathrow ki one-way nonstop flights June me dhundo, online search karo, details file me likho, aur best option select karo."
  - Code flow: pehle bilkul last week wala code — Serper wrapper banao, usse LangChain `Tool` banao (description ke saath). Phir `LangChainToolAdapter(langchain_tool)` call karke usse AutoGen tool bana do, aur ek `autogen_tools` list me daal do.
  - **FileManagementToolkit** ko ek empty **`sandbox`** directory di jaati hai, `get_tools()` se file tools milte hain (read, write, move, etc.), aur har ek ko bhi `LangChainToolAdapter` me wrap karke list me append karte hain.
  - Phir ek **AssistantAgent** ko ye `tools=autogen_tools` pass karke prompt diya, **inner messages** print kiye taaki tool-calls dikhein.
  - Run karne pe: agent ne internet query ki (function call), results mile, bola "main details file me likhunga". Interesting baat — AutoGen agents is mode me typically **ek turn ke baad ruk jaate hain**, to Ed ne dusra message bheja: **"okay, proceed"** — tab usne `flights.md` file likhi aur best flight select ki.
  - Result: **Virgin Atlantic** select hui — jo sabse **mehengi** option thi! Kyun? Kyunki prompt me "cheapest" nahi bola tha, sirf "best" bola tha. Classic prompt-precision lesson. Sandbox me `flights.md` nicely formatted options ke saath ban gayi.
  - **Mini side mission:** aur LangChain tools le aao — Python tool se pi × 3 multiply karwao, etc.

- **Part 2 — Team interactions: Primary + Evaluator pattern:**
  - Do **AssistantAgents** banate hain: **primary** aur **evaluator**. Pattern guess kar lo — ye **evaluator-optimizer / reflection pattern** hai (Week 1 ke design patterns yaad karo).
  - **Primary agent:** sirf **Serper search tool** rakhta hai (ab files nahi likh rahe). System message: "You are a helpful AI research assistant who looks for promising deals. Respond with one option, different from others."
  - **Evaluator agent:** check karta hai ki recommendation promising lagti hai ya nahi. System message: "Respond **approve** when satisfied. Agar sirf ek hi reply dekha hai to approve mat karo" — thoda **artificially** forced taaki interaction dikhe (real use-case me pehla answer bhi theek ho sakta hai).
  - **Team banana:** **`RoundRobinGroupChat`** — agents **ek ke baad ek** baari-baari bolte hain. Ye CrewAI ke "crew" jaisa hai but kaafi **simpler**. Pass karte ho: agents ki list `[primary, evaluator]` + ek **termination condition**.
  - **`TextMentionTermination("approve")`** — jab kisi message me "approve" word aaye, team ruk jaati hai. Ed khud bolta hai ye **brittle/hacky** hai — production me **structured outputs** use karke programmatically check karna better hai. Yahan bas flavor ke liye simple rakha.
  - Run karna: **`await team.run(task=...)`**. Side note — agents ke liye bhi `on_messages()` ke alawa **`agent.run(task=...)`** available hai jo final messages return karta hai.
  - **⚠️ Real-world warning (sabse important hissa):** Ed ka pehla run **1 minute+ thrash** karta raha — agents backwards-forwards baat karte rahe. Usne kernel **interrupt/restart** kiya, prompts tighten kiye, dusra run **10 seconds** me ho gaya.
  - **LangGraph vs AutoGen safety:** LangGraph me **recursion limit = 25** hai (25 se zyada agent-conversations pe exception throw hota hai jab tak explicitly badhao nahi). **AutoGen me ye protection NAHI hai** — wo bas chalta hi rehta hai. To token bill bachane ke liye kernel interrupt karne ke liye ready raho.
  - Ye **instability** in agent frameworks ka eye-opening example hai: jab agents ko **autonomy** hai ki kab tak chalte rahein, to behavior unpredictable ho sakta hai.
  - Successful run ka flow: user task → primary ne Serper se search kiya → $402 flight ka response → evaluator ne **stern feedback** diya ("lacks a specific answer, clarify dates, organize information, remove redundancy" — "little does it know it's talking to itself!") → primary ne "thank you for the feedback" bol ke **revised response** diya → evaluator ne **"approve"** bola → termination condition met → done. Self-correction in action!

---

## 🔑 Key Concepts / Important Terms

| Term | Simple Hinglish Meaning |
|------|--------------------------|
| **LangChainToolAdapter** | AutoGen ka wrapper jo kisi bhi LangChain tool ko AutoGen tool bana deta hai — `LangChainToolAdapter(lc_tool)` |
| **GoogleSerperAPIWrapper** | LangChain ka class jo Serper API se Google search karwata hai (last week wala hi) |
| **FileManagementToolkit** | LangChain toolkit — ek diye gaye directory (sandbox) me files read/write/move karne ke tools ka bundle |
| **RoundRobinGroupChat** | Simplest AutoGen team — agents fixed order me ek ke baad ek bolte hain |
| **TextMentionTermination** | Termination condition: jab message me specific text (yahan "approve") dikhe, team stop |
| **Primary / Evaluator pattern** | Ek agent kaam karta hai, dusra critique karta hai jab tak satisfied na ho — reflection / evaluator-optimizer pattern |
| **`team.run(task=...)` / `agent.run(task=...)`** | `on_messages()` ka shortcut — task pass karo, final messages wapas milte hain |
| **Recursion limit** | LangGraph me 25-step safety cap hai; **AutoGen me nahi** — infinite agent loops possible, khud intercept karo |
| **Sandbox directory** | Empty folder jisme file tools ko restrict kiya — agent sirf wahin likh sakta hai |

---

## 💡 Backend Dev Ke Liye Note (aapke liye)

- **LangChainToolAdapter = classic Adapter pattern** (GoF). Jaise aap kisi third-party SDK ke client ko apne internal interface me wrap karte ho — signature/schema translate hota hai, logic same rehta hai. Isi wajah se ek framework ka tool ecosystem dusre me reuse ho jaata hai — vendor lock-in kam.
- **TextMentionTermination("approve") brittle hai** — ye string-matching pe sentinel value check karna hai, jaise HTTP response body me `"SUCCESS"` grep karna instead of status code dekhna. Production me structured output (Pydantic model with `approved: bool`) use karo — wahi cheez jo aap API contracts me karte ho.
- **No recursion limit = unbounded retry loop without circuit breaker.** Aap kabhi Kafka consumer ya Celery task me max-retries ke bina infinite requeue nahi karte — yahan bhi `MaxMessageTermination` jaisa guard lagao, warna token bill = AWS bill surprise.
- **Hands-on lab:** is lecture ka code khud chalane ke liye `Practical/lab2_primary_evaluator.py` run karo (is repo me, `uv run` se chalta hai, Groq pe free via `OpenAIChatCompletionClient` + `base_url` + `ModelInfo`). Difference: lecture me Serper + LangChain tool adapters hain, hamare lab me Serper ki jagah **free Wikipedia/httpx tools** plain functions ke roop me hain (AutoGen 0.7.5 vs course ka 0.5.1, same API family) — primary+evaluator team aur termination logic bilkul same hai.

---

## 🧠 Takeaway (yaad rakho)

1. **`LangChainToolAdapter`** se LangChain ka pura tools ecosystem (Serper, FileManagementToolkit, Python REPL...) AutoGen me one-line wrap ho jaata hai.
2. **Team = agents list + termination condition.** Simplest team **`RoundRobinGroupChat`** hai — agents baari-baari bolte hain, `await team.run(task=...)` se chalao.
3. **Primary + Evaluator** = reflection pattern: evaluator feedback deta hai, primary revise karta hai, "approve" pe **`TextMentionTermination`** trigger ho kar loop band hota hai.
4. Text-mention termination **hacky** hai — real systems me structured outputs se approval check karo.
5. **AutoGen me LangGraph jaisa recursion limit (25) nahi hai** — teams indefinitely thrash kar sakti hain; kernel interrupt karne / prompts tighten karne ke liye ready raho.

---

<details>
<summary>📜 Full English Transcript (original, click to expand)</summary>

What we're going to do now is pretty cool. We're going to use the tools that we worked with last week in LangChain. Autogen has a really easy way to wrap LangChain tools so that you can call them directly from within Autogen. So when we were working with LangGraph last week, we were using LangChain's tools, and now in Autogen, we're also going to be able to use LangChain's tools. And that's great because LangChain has a huge tools community and lots to choose from, and that's great. And we've already used many of them, so we can just suddenly have access to all of them from within the Autogen ecosystem. So within Autogen, there is this LangChainToolAdapter, and you can use that to wrap any LangChain tool and it becomes an Autogen tool.

So for example, uh, this, this uh, this is importing some of LangChain's classes. We've already used these before. The GoogleSerperAPIWrapper is a way to call the Google Serper API that we've we've used that. We've got access to the FileManagementToolkit. Was that great set of tools for reading and writing files with from a particular directory. And then this is just the generic LangChain Tool class.

So just before we do that, let me tell you the prompt that we're going to have for an LLM. Your task is to find one way nonstop flights from New York's John F Kennedy to London's Heathrow Airport in June. Search online, write the details to a file and select the best one.

So then this code. These two lines here are taken identically from what we did last week. This is creating a Google search API wrapper. And this is the LangChain code to create a LangChain tool for searching the internet with a description based on this function. And we could also do the same thing for things like sending a push notification, and for running Python code and everything else that we did last time. And so we end up with, with, with this LangChain tool. And now I can call LangChainToolAdapter. Create a new instance of that passing in the LangChain tool. And by passing that in this adapter adapts that LangChain tool to become an Autogen tool. It's just sort of a wrapper around it. And so I put that in a little list called autogen tools.

And then I've also collected some LangChain file tools by getting the FileManagementToolkit giving it a directory sandbox. I've created an empty directory sandbox on the left. And we call get tools. And we get a bunch of tools. And for each of those, I'm going to add them to my autogen tools by appending a LangChainToolAdapter, an Autogen piece of Autogen code that adapts LangChain's tool to be an Autogen tool. That's what this does right here. And then I'm going to print each one out. So we get to see what is this set of tools that we've got.

And then. Then I'm simply going to call an Autogen agent with this prompt. Find me a flight, use your tools and I'm going to give it. Of course. Tools. Here they are. I pass in the autogen tools so that that is what it can use. And then I will print out the inner messages. So we see it doing its thing and then get it to display the outcome.

All right let's run this. Let's see what it actually does. So what you'll see is that it uh it's printed out the different tools it has access to. It has access to do an internet search to file move things around. So what's it actually done? So it's done a function call to to do a query, an internet query for finding the non-stop flights. Uh, it then, uh, got the results and it sound. It's replied with, I have found several promising deals. I will now write the details to a to a file called.

Now, one of the interesting things about Autogen is the way that it handles the interactions that agents typically, uh, will then stop. Um, particularly in this kind of mode of working with them. And so what we now do is that I'm just going to send the next message of, okay, proceed, send a second message to this agent in the same way. And we'll see what it comes back with. So it's thinking about that which which probably means it's streaming back something big. And here we go. The details of the flights have been saved to flights. Now I will select the best flight. The selected flight is all of this. This flight offers a good balance of price and service, making it a great option for travel. Sounds good. It's with Virgin Atlantic, a great airline. And there's details. And this of course, has actually been, uh, grabbed from the true internet search. And it is like a useful piece of information.

And of course, I know you're wondering, did it write a file? Let's go and have a look. We open up sandbox and there's a file flights MD. Let's let's open a preview of that file. And here we go. Here are a bunch of different options nicely formatted with a bunch of different, uh, things. Uh, does seem interestingly as if there was a cheaper option, but it has selected, uh, Virgin, which is one of my favorite airlines, but is the most expensive of the options. But I guess we didn't necessarily say the cheapest, uh, did we? I'll go back and check out the the prompt, um, the best flight. So, uh, um, a good choice of food and drinks and on board. Let's see, uh, promising deals. Yes. So we don't necessarily say that it needs to be the cheapest. So it chose, for whatever reason, to recommend the Virgin flight out of those flights. And that is what it did. But by all means you can rerun it asking for the cheapest and hopefully GPT-4o mini can handle that task.

Okay, so we've shown how you can wrap LangChain tools and access them from Autogen. And a little mini side mission for you right now is to go and find some more tools. Bring in the Python one, and have it be able to multiply pi by three and try some other tools. There are so many tools in the LangChain ecosystem that now you can be unleashed to make Autogen do all sorts of cool things for you.

Uh, and, um, okay, next up we have, uh, team interactions. So check this out. I'm going to take you through this pretty quickly because it's fairly self-explanatory. Uh, so you can create multiple assistants. So in this case, we're going to have, um, an assistant agent, uh, called primary and one called evaluator. Any guesses what pattern I might be about to work with here? So the prompt is your task is to find a one way non-stop flight from JFK to London Heathrow uh, first. Search online for promising deals, then reply with the best option you found. Each time you're called, you should reply with a different option.

So then we. Create a primary agent, which is the, uh. It's only going to have access to the. Serper to search. We're no longer writing files at this point. Uh, so it's the one that's going to be doing internet searches and its system message is. You're a helpful AI research assistant who looks for promising deals. Respond only with one option. And, uh, make sure it's different from others. And then we have an evaluator check whether it looks like the assistant has given a very promising recommendation. Respond. Approve when you're satisfied. If you've only seen one reply, then don't approve. You need to see more. You can tell slightly artificially making this so that we get some sort of interactions between them. If this were a real, uh, proper challenge you were trying to set, you might be perfectly happy with the first option if the evaluator agent is satisfied with it.

Um, okay. So this this is the, uh, the way it works. Um, and then we create a team, and there's various ways to create teams. This is a bit like a crew in crew, but it's, uh, it's really, uh, somewhat simpler. Really. This is a RoundRobinGroupChat, which means, like, one after the other, obviously. Um, and, uh, that is the simplest way that you could have some kind of relationship between them. And we pass in a list of agents to talk to each other, primary agent, and then an evaluation agent and a termination condition that tells it. When do you know that enough is enough? And this is, uh, you can see here how it's defined. TextMentionTermination. The word approve. So this is a little bit brittle. I'm relying on the fact that the assistant, the evaluator agent, will reply the word approve. Normally you would want something a little bit more profound than that. You would probably want to reply, have structured outputs here and use that to test. But this is perfectly good. For now. I just want to get you a feel for this. I don't necessarily want to give you a full bells and whistles solution.

And then this. This is how it comes together. You call team run and you await team run. And it might be worth me mentioning. Actually I've been focusing a lot on the on messages. The on_messages, uh, thing that you call agents here. You can also call agent run as well. An agent can be called with run. And then you just pass in this exactly the same thing. You pass in the task, um, task equals and a prompt. And what comes back is just going to be the final messages. So that is another way of doing it as well. Um, but this is what we will do now.

Okay. I've actually just gone and tightened these prompts a bit and made them just shorter and simpler because it. It was going. It was thrashing around a bit. The prompt is just find a one way non-stop flight. The system message says you are a helpful AI research assistant who looks for promising deals on flights. Incorporate any feedback, the evaluator says. Provide constructive feedback. Respond with approve. And so with that, I'm now kicking off our message here. And it does take it's quite chatty I discovered and it goes backwards and forwards. And I'm sure there's ways you can tighten up these prompts to make the conversation be a little bit crisper. But I will let this thing run and let it go for a little bit. And when we are back in a sec, we'll see the response from the agents.

Well, I'm going to be honest with you, this is my second shot at it that I'm showing you here. I kicked this off even with these shorter prompts, and it was running for more than a minute, like going backwards and forwards. And GPT-4o mini is quick, so. So I imagine it was in quite a conversation there. Uh, and so I interrupted it. I restarted my my lab and then I ran it a second time and it took 10s. And it's done. So you may want to be if you if you run it like this, then then obviously interrupt the, the, uh, the notebook by pressing the, the, uh, the button here when it's running to stop it or restart, restart the kernel. Um, if it's thrashing because you don't want to spend all of your, your, your tokens on this on this message.

But I mean, I think this is a very eye opening sign of what can be troubling with these sorts of agent platforms that they can be quite hard to get them to perform the way you want. Um, you may have discovered when you're working with LangGraph that there is a maximum, a recursion limit, as they call it, of 25, meaning that if you have more than 25 conversations between agents, then it will throw an exception unless you explicitly say you want more than that. And it appears that that there isn't the same kind of protection in Autogen. So it just kept and kept and kept on going. Uh, so, uh, be sure to to restart the kernel if that happens to you, or try and tighten up this prompt so that it doesn't happen. And observe that this is the kind of instability that is problematic, uh, with these kinds of agent frameworks, when there is autonomy to decide to keep going if they wish.

But anyway, this time it took 10s. It was quick. And let's see what actually happened. The user said find a non-stop flight or a one way flight. A non-stop uh. The primary agent used the tools to do a query, and then it said it gave a response. Uh, with, with the the $402 flight there. And the evaluator responded, your response contains a lot of good information, but it lacks a specific answer to the question. And then it gives it's quite authoritative. Little does it know it's talking to itself, but it's quite, quite, quite stern. Focus on the user's request. Clarify dates, organize information, remove redundant. So it's really great to see the evaluator doing what it's told to do and evaluating. And then the primary says, thank you for the feedback. Here's a revised response. And it does indeed give a revised response with all that detail. And the evaluator sends approve which is the text that it has to respond. This is a little bit hacky, but it responds to the word approve because reply approve and your feedback is addressed and because it says approve, that means that the termination condition is met. And this completes. And that is how we arrive at our decent answer here.

And this is an example of a team at work. And there's a lot more that you can do with teams, but I feel like it's pretty consistent with stuff we've done before. So this gives you enough of a flavor for it. Now, should you wish to build out your teams, you can look at some of the docs and build out something a bit more extensive than this. And. But just be aware. Be be aware of the fact that they can just just keep going. And you need to be you need to be ready to intercept if necessary.

</details>

---
*Source: Official Udemy lecture transcript (auto-captions, lightly cleaned). Notes in Hinglish for self-study.*
