# L37 — Day 2: From Function Calls to Agent Autonomy — Sales Automation

> **Week 2 — OpenAI Agents SDK** · ⏱️ ~7m · 🎥 Lecture 37 of 131
> **Instructor:** Ed Donner · **Lecture ID:** 49820479

---

## 🎯 Ek Line Mein (TL;DR)

Sales manager agent ko **tools** (request-response) aur **handoffs** (delegation) dono ke saath run karke pura **automated SDR pipeline** dekha — manager ne 3 sales email tools ko 2-2 baar try kiya, best email choose ki, fir **email manager ko handoff** kiya jo subject + HTML + send kara ke control kabhi wapas nahi lautata. Yahi chhota sa change hai jo "agent workflow" ko sach mein **agentic autonomy** banata hai.

---

## 📝 Hinglish Explanation (Detailed)

- **Setup — Sales Manager agent:** Ed ek naya **sales manager** agent banata hai jiski instructions bahut explicit hain:
  - "Tum **ComplAI** ke sales manager ho, **tools** use karke cold sales emails generate karo — **kabhi khud email mat likho**, hamesha tools use karo."
  - **Teeno sales email tools at least ek baar try karo** before choosing; chaho to multiple baar bhi use kar sakte ho agar first try se satisfied nahi ho.
  - Apne **judgment** se single best email pick karo, aur pick karne ke baad **email manager agent ko handoff** karo jo format + send karega.
- **Prescriptive instructions kyun?** Technically itna spell out karna zaroori nahi tha kyunki **handoff description** already di gayi thi — par Ed ka point: jaise-jaise system **complex** hota hai, **precise instructions** dena reliability ke liye **best practice** hai. Agent ko on-track rakhna hai to ambiguity mat chhodo.
- **Crux of the lecture — tools vs handoffs ek hi agent mein:**
  - Agent constructor mein **dono pass kiye**: `tools=` (teen sales agents as tools) aur `handoffs=` (email manager).
  - **Tools = request-response** — manager tool ko call karta hai, result wapas aata hai, control manager ke paas hi rehta hai.
  - **Handoff = delegation** — control **transfer** ho jaata hai, doosra agent baaki ka kaam khatam karta hai, control **wapas nahi aata**.
- **Run + Trace:** Pura run ek **trace** mein wrap kiya (`"Automated SDR"` naam se) aur run kiya — ~1 minute laga.
  - Result: ek **short, crisp email** chuni gayi (concise email writer wali) — "Dear CEO" se start, "Alice" se sign-off, sharp AI-driven solutions pitch.
- **Trace analysis (OpenAI traces UI):** Ye is lecture ka sabse satisfying part hai:
  - Manager ne **sales agent 1, 2, 3** ko call kiya... fir **dobara 1, 2, 3** ko call kiya (total **9 tool calls**) — yaani usne first results se satisfied na hokar **apne aap retry kiya**. Ye uski autonomy hai, code mein loop nahi likha.
  - Fir trace mein **handoff** clearly dikhta hai → **email manager** → **subject writer** tool → **HTML converter** tool → **send_email** function.
  - **Control kabhi sales manager ke paas wapas nahi aaya** — handoff ke baad blue timeline pura email manager ka hai. Tools (agents-as-tools + plain functions dono) aur handoff, sab ek trace mein visible.
- **Big takeaway — simplicity:** Itna complex multi-agent system (5 agents, 4+ tools, handoff, tracing) sirf **kuch minutes** mein ban gaya — **OpenAI Agents SDK lightweight hai**, yahi iski sabse badi strength hai.
- **Exercises (homework):**
  1. **Identify the agentic design patterns** jo yahan use hue (agents-as-tools, evaluator/judgement, handoff/delegation...).
  2. **Spot the moment:** Anthropic ki definition ke hisaab se kis chhote change pe hum "**agent workflows**" se "**truly agentic**" territory mein gaye? (Hint: jab LLM khud decide karne laga ki kaunsa tool kitni baar call karna hai aur kab handoff karna hai — control flow code se nikal ke model ke paas chala gaya.)
  3. **Extend karo:** Aur tools, aur agents add karo — ye system extend karna bahut easy hai.
  4. **Hard challenge (engineering-heavy):** Isko **long-living agent** banao jo email **replies** handle kare — SendGrid se incoming replies ke liye **webhooks** research karne padenge, processing trigger karna hoga, aur track karna hoga ki email kisko bheji thi. Ed kehta hai ye mostly engineering hai, agentic kam — skip karna allowed hai.
- **Commercial applications:** Ye literally ek **sales automation / cold email campaign tool** ban sakta hai; reply-handling ke saath full conversation engine. Aur generally — **koi bhi at-scale business process** (recruitment jaise Ed ki company Nebula mein, outreach, etc.) ko "agents collaborating with autonomy + tools + handoffs" pattern se end-to-end automate kiya ja sakta hai.

---

## 🔑 Key Concepts / Important Terms

| Term | Simple Hinglish Meaning |
|------|--------------------------|
| **Tools vs Handoffs** | Tools = request-response (control wapas aata hai); Handoff = delegation (control transfer, wapas nahi aata) |
| **Sales Manager agent** | Orchestrator agent jise tools (3 email writers) aur handoff (email manager) dono diye gaye |
| **Agents as tools** | `agent.as_tool()` se ek agent doosre agent ka callable tool ban jaata hai |
| **Handoff description** | Handoff ke saath attached description jo LLM ko batati hai kab delegate karna hai |
| **Trace ("Automated SDR")** | OpenAI platform pe pura execution timeline — har tool call, handoff, agent visible |
| **Agent autonomy** | LLM khud decide karta hai kaunsa tool, kitni baar, kab handoff — control flow code mein hardcoded nahi |
| **Agentic workflow vs Agentic agents** | Anthropic ki definition: fixed orchestration = workflow; LLM-driven dynamic control = truly agentic |
| **SDR (Sales Development Rep)** | Cold outreach karne wala sales role — yahan AI agents se automate kiya |
| **Webhooks (SendGrid replies)** | Incoming email reply pe SendGrid tumhare endpoint ko HTTP call kare — long-living agent ka trigger |

---

## 💡 Backend Dev Ke Liye Note (aapke liye)

- **Tools vs Handoffs = sync RPC vs fire-and-forget queue handoff.** Tool call bilkul synchronous HTTP call jaisa hai (request → response → caller continues), jabki handoff waisa hai jaise aap message queue pe task daal ke ownership transfer kar dete ho — downstream consumer hi response ka maalik hai, caller picture se out. Architecture decide karte waqt yahi question pucho: "kya mujhe result wapas chahiye, ya kaam ka ownership dena hai?"
- **Autonomy ka matlab: control flow code se prompt mein shift.** Trace mein manager ne teeno tools 2 baar call kiye — ye retry loop kisi `for` loop mein nahi likha tha, LLM ne instructions ("not satisfied to dobara try karo") padh ke khud decide kiya. Ye waise hi hai jaise imperative orchestration (Airflow DAG) se declarative goal-based system pe move karna — aap *kya* chahiye batate ho, *kaise* model decide karta hai. Reliability ke liye isi liye instructions ko precise rakhna padta hai — prompt ab aapka control flow spec hai.
- **Hard challenge (email replies) pure backend engineering hai** — SendGrid Inbound Parse webhook → aapka FastAPI endpoint → conversation state lookup (kisko bheja tha, thread ID) → agent run trigger. Aap ye 4+ saal ke webhook/async experience se aaram se design kar sakte ho; agentic part sirf itna hai ki handler ke andar `Runner.run()` call hoga with conversation history.
- **Hands-on lab:** is lecture ka code khud chalane ke liye `Practical/lab2_sales_agents_handoffs.py` run karo (is repo me, `uv run` se chalta hai, **Groq pe free**). Note: hamare labs OpenAI ki jagah FREE Groq use karte hain (`OpenAIChatCompletionsModel` + `base_url` trick), is wajah se lecture wali **OpenAI tracing UI** hamare runs me nahi dikhegi (traces OpenAI platform ka paid/account feature hai) — aur **SendGrid** ki jagah lab email ko console pe print karta hai, koi real email nahi jaati.

---

## 🧠 Takeaway (yaad rakho)

1. **Tools = request-response, Handoffs = delegation** — ek hi agent ko dono de sakte ho; yahi is example ka crux hai. Handoff ke baad control wapas nahi aata.
2. **Trace ne autonomy prove ki:** manager ne 9 tool calls kiye, teeno writers ko do baar try kiya — ye decision LLM ka tha, code ka nahi. Yahi "workflow → truly agentic" wala moment hai.
3. **Precise instructions = reliability.** Handoff description hone ke bawajood explicit instructions likhna best practice hai, especially jab system complex ho.
4. **SDK lightweight hai** — 5 agents, tools, handoff, tracing... sab kuch minutes mein. Complexity SDK mein nahi, design patterns mein hai.
5. **Pattern generalizes:** sales outreach sirf example hai — recruitment, support, koi bhi at-scale business process is "autonomous agents + tools + handoffs" pattern se automate ho sakta hai.

---

<details>
<summary>📜 Full English Transcript (original, click to expand)</summary>

Okay. Moment of truth. I'm going to run it. And while it's running, I will talk through what it's doing. Hang on. Off it goes. So we have a new sales manager. We say you are the sales manager working for ComplAI. You use the tools given to you to generate cold sales emails. Never generate one yourself. Always use the tools. You try all three sales email tools at least once before choosing the best one. You can use all the tools multiple times. If you're not satisfied with the results from the first try, you select the single best email using your own judgment of which email will be most effective, and then after picking it, you hand off to the email manager agent to format and send the email.

Now again, I'm really spelling it out here, and you shouldn't need to be that prescriptive because the handoff description was there. But it helps to be precise. And particularly as these things get more complex, if you want it to stay on track and to be reliable, then this is a good practice to do.

So then we create the agent. It's a sales manager. We give it these instructions. We pass in both the tools and the handoffs. This is the crux of this. This is how we separate out the tools, which is where it's like a request response, from the handoffs, which is a delegation — control is passed across to take care of the rest of the work. And that is our message. And we put a trace around it, automated SDR, and we give it a run. And it took about a minute and let's see what came back.

This is the result and it's picked a very short one in the end. You remember one of them is a very concise email writer. It does indeed begin, dear CEO. And it ends, Alice, as we asked for. And it's given a nice, short, sharp, AI driven solutions that can optimize your business processes. And so it's nice and crisp. There we go.

And importantly, we now have to go and look at the trace. So the trace here it is, automated SDR. You can see how long it took. It used nine tools. Let's go and have a look. So it came in and it used sales agent one and two and three. And then look at what happened. It went back and used sales one, two and three a second time. Load more. And then this was the handoff you can see here shown. Then it goes to the email manager. And then that goes to the subject writer followed by the converter followed by the send email. And you'll see the control does not then come back. So you're seeing everything in action here. The sales manager that's able to handle things. And it hands off here. And the email manager takes the rest of control for the rest of this blue timeline that you see highlighted in here. You can see the multiple calls to different agents and the handoff and the use of tools, both wrapping agents and just directly calling functions. And that is a satisfying conclusion to quite an interesting example of agentic workflows and design patterns.

Okay. Well, we covered a few of the constructs and concepts with OpenAI Agents SDK, including tools and handoffs. And the most important thing that I want you to take on board is that it was simple. It's relatively lightweight. We achieved something quite complex, quite advanced, and we did it all in a matter of a few minutes.

Now, some exercises for you, as of course it's very important that you now come back and spend some time on this yourself. That is the best way to learn. So first of all, go through and identify the agentic design patterns that we used here. Now, there was a moment in this when we moved from doing what Anthropic would just describe as agent workflows to something that was really like agentic agents under their definition, although I think it's a little bit hand-wavy. But still, there was a clear moment. Can you identify it? Can you spot what was the change? The small change that made that difference?

And then try adding in more tools and more agents. This is a great way. This is so easy to extend. Obviously, calling this an SDR was maybe a bit of a stretch because it's really just a cold email writer, but it would be very easy to see how you could build this into something that's much more interactive.

And then a hard challenge for you, particularly if you've got some engineering experience. Figure out if you could turn this into something which is more of a longer living agent workflow, in that someone could reply to that email, and the agent would then be able to pick up and continue the conversation. Have an email based conversation about the company. Now the hard part about that is handling replies back from SendGrid. That will need a little bit of research and understanding about things like webhooks and how that will work, and how you'd use that to trigger this processing, and how would you identify who you sent it to. So there's a fair amount of stuff in there, but it's engineering stuff rather than much agentic stuff. So you could be forgiven for skipping it if it doesn't appeal to you. But if it does, then that's a very interesting framework to put in place.

And in terms of commercial applications, because you remember, I do always like to try and bring this back to how can you apply this to business. And hopefully — I mean, obviously there's the fact that it could be literally a sales automation tool that could just be working to generate a bunch of different cold sales emails or email campaigns. And if you were to do this extra hard project, it could in fact be something that engages and continues the conversation. And generally, the point here is that you can really apply this to any end to end automation of these kinds of business processes. You can think of how you can apply this in this context of sales, but you can think of applying it to so many contexts. Imagine my day job at Nebula that involves recruitment. Imagine how applicable something like this is to that space as well, and many others. Think of a business area. Think of the kinds of activities that are done at scale with things like cold sales outreach, and picture how this kind of approach — agents collaborating with a level of autonomy and with use of tools and handoffs — can automate a complex business process.

</details>

---
*Source: Official Udemy lecture transcript (auto-captions, lightly cleaned). Notes in Hinglish for self-study.*
