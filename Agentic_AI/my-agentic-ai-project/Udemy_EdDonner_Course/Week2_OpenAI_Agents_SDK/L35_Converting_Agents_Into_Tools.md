# L35 — Day 2: Converting Agents into Tools — Building Hierarchies

> **Week 2 — OpenAI Agents SDK** · ⏱️ ~6m · 🎥 Lecture 35 of 131
> **Instructor:** Ed Donner · **Lecture ID:** 49820447

---

## 🎯 Ek Line Mein (TL;DR)

Sirf functions hi nahi, **poore agents ko bhi tool bana sakte ho** — bas `agent.as_tool()` call karo — aur phir ek **sales manager (planning agent)** ko ye agent-tools + real tools deke usse khud decide karne do ki kya, kab chalana hai. Yahi se **agent hierarchies** banti hain.

---

## 📝 Hinglish Explanation (Detailed)

- **Core idea (thoda confusing, lekin powerful):** Pichle lecture me humne function ko tool banaya (`@function_tool`). Ab Ed bata rahe hain ki **ek poora agent bhi tool ban sakta hai**.
  - Sales agent = ek LLM call with a prompt jo cold sales email likhta hai. Ye **poora process khud ek tool** consider ho sakta hai — "sales agent tool".
- **Kaise? Sirf `as_tool()`:** Lagta hai ki agent ko tool me package karna bahut kaam hoga, lekin nahi — bas agent pe **`.as_tool(tool_name=..., tool_description=...)`** call karo, done.
  - Iska matlab kya hai? SDK ek **naya tool create** karta hai with all the **JSON gunk** (schema/description) jo describe karta hai ki tool kya kar sakta hai.
  - Jab wo tool **invoke** hota hai, to wo internally **agent ko call karta hai**, aur agent LLM call karta hai.
  - In short: **`as_tool()` ek wrapper hai** — agent ke around ek wrapper jo agent ko tool bana deta hai. Bas itna hi.
- **Inspect karke dekho:** `sales_agent1.as_tool(...)` ka result ek **`FunctionTool`** hi hai — bilkul `send_email` jaisa:
  - Different **name** (e.g., `sales_agent1`), apni **description** ("write a cold sales email"), wahi expected **parameters JSON blob**, aur ek special **function** jo batata hai ki call hone par kya karna hai — yani actually agent ko run karna.
- **Teen agents → teen tools:** Ed ne deliberately loop nahi likha, repetition ke saath spell out kiya taaki crystal clear ho:
  - `tool1`, `tool2`, `tool3` = `sales_agent1/2/3` pe `as_tool()` call, har ek ko same tool description di.
  - (Exercise: ise ek **clean loop** me rewrite karo, repetition hatao.)
- **Final tools list = mixed bag:** `tools = [tool1, tool2, tool3, send_email]`
  - Pehle teen = **agents wrapped as tools** (call karne par agent chalega).
  - `send_email` = **real plain tool** — ek function jo **SendGrid** se actual email bhejta hai.
  - Print karke dekho: list me **4 function tools** dikhte hain — sales agent one, two, three aur send email. Bahar se sab same dikhte hain!
- **Sales Manager — the planning agent:** Ab in sab tools ko ek **sales manager agent** me daalte hain. Key difference from before:
  - Pehle hum **Python code se sequence control** kar rahe the (do this, this, this, then send email).
  - Ab hum **agent ko decide karne de rahe hain** ki kya kab run karna hai — yahi "agentic" hai.
- **Instructions (system prompt) — very precise:** "You are a sales manager working for ComplAI. You use the tools given to you to generate cold sales emails. **You never generate sales emails yourself, you always use the tools.** You try **all three tools once** before choosing the best. You pick the **single best email** and use the **send_email tool** to send the best email — and only the best email."
  - Ed maanta hai ki ye thoda over-spell-out hai; hamesha itna pedantic hona zaroori nahi, **but precise & instructive prompts kabhi bura idea nahi** hote.
- **Run karo:** Sales manager agent banao — instructions (system prompt), saare **4 tools**, ek model — aur message do: "Send a cold sales email addressed to 'Dear CEO'".
  - Expected ~30s, actually **18 seconds** me complete ho gaya.
  - Email actually inbox me aaya, **verified sender** se, aur kaafi accha tha. (Ek glitch: "Dear [CEO's Name]" jaisa template placeholder aa gaya — prompting improve karke fix kar sakte ho; end me **mail merge** wali exercise hai jo real names daalegi.)
- **Trace dekho (important!):** OpenAI traces me jaake flow inspect karo:
  - Sales manager ne **Sales Agent 1 → Sales Agent 2 → Sales Agent 3 → Send Email** call kiya.
  - Har sales-agent tool ke **neeche ek agent dikhta hai** — proof ki tool ke andar wrapped agent run hua.
  - `send_email` ke neeche kuch nahi — wo **simply ek function** tha jo body ke saath call hua.
  - Ed ka strong advice: **trace zaroor padho** — tools aur agents ke beech interactions samjho, dekho ki sales manager ne khud kaise decide kiya kya, kis order me karna hai.

---

## 🔑 Key Concepts / Important Terms

| Term | Simple Hinglish Meaning |
|------|--------------------------|
| **`agent.as_tool()`** | Ek poore agent ko tool me convert karne ka one-liner — naam + description do, ban gaya tool |
| **Agent-as-tool (wrapper)** | Tool ke andar agent wrapped hota hai; tool call hone par agent apna LLM call karta hai |
| **`FunctionTool`** | SDK ka tool object — name, description, params JSON schema, aur on-invoke function; agent-tool aur plain function-tool dono yahi type hain |
| **JSON gunk / schema** | Tool ki auto-generated JSON description (params, types) jo LLM ko batati hai tool kaise use karna hai |
| **Planning agent (Sales Manager)** | Upar ka agent jo tools (including agent-tools) me se khud choose karta hai kya, kab chalana hai |
| **Agent hierarchy** | Manager agent → worker agents (as tools) → real tools — layered structure |
| **`send_email` (real tool)** | Plain function tool jo SendGrid se actual email bhejta hai — andar koi agent nahi |
| **Trace** | OpenAI platform pe execution ka visual log — dikhata hai kaun sa tool/agent kab chala |
| **Precise prompting** | Instructions me explicitly rules likhna ("never write yourself, always use tools, try all three") — pedantic but reliable |

---

## 💡 Backend Dev Ke Liye Note (aapke liye)

- **`as_tool()` = Adapter pattern:** Jaise aap ek service class ko ek common interface ke peeche wrap karte ho, waise hi agent ko `FunctionTool` interface me adapt kiya jata hai. Caller (sales manager LLM) ko farq hi nahi pata ki tool ke andar plain function hai ya poora LLM-backed agent — **uniform interface, polymorphic behavior**.
- **Orchestration shift samjho:** Pehle wala approach = aapka Python code as orchestrator (jaise ek controller jo services ko fixed order me call karta hai). Ab = **LLM as orchestrator** — control flow runtime pe model decide karta hai. Ye microservices me hard-coded workflow vs. dynamic saga/coordinator jaisa shift hai; trade-off bhi wahi: flexibility ↑, determinism ↓ — isliye prompt me strict rules likhne padte hain.
- **Hands-on lab:** Is lecture ka code khud chalane ke liye ye lab run karo — `Practical/lab2_sales_agents_handoffs.py` (is repo me, `uv run` se chalta hai, **Groq pe free**). Note: hamare labs OpenAI ki jagah **free Groq** use karte hain (`OpenAIChatCompletionsModel` + `base_url` trick), aur lecture wala **SendGrid** real email bhejta hai (paid/signup) — lab me email sending mock/print ho sakti hai; **OpenAI traces** bhi Groq route pe nahi dikhenge, to flow samajhne ke liye console output padho.
- **Debugging tip:** Trace = aapka distributed tracing (Jaeger/Zipkin) equivalent. Nested spans dekhke hi pata chalta hai ki agent-tool ke andar actual agent run hua — production agentic systems me ye observability **must-have** hai, optional nahi.

---

## 🧠 Takeaway (yaad rakho)

1. **`agent.as_tool(tool_name, tool_description)`** se koi bhi agent ek tool ban jata hai — ye bas ek wrapper hai jo call hone par agent ko run karta hai.
2. Agent-tools aur plain function-tools dono **same `FunctionTool` type** hote hain — manager LLM ke liye sab ek jaise tools hain.
3. **Sales manager = planning agent:** Python code nahi, **LLM khud decide** karta hai kaun sa tool kab call karna hai — yahi true agentic behavior hai.
4. Prompts me **precise, explicit rules** likho ("never generate yourself, try all three, send only the best") — over-spelling se reliability badhti hai.
5. **Trace hamesha inspect karo** — wahi proof hai ki tool ke andar agent chala, aur wahi se aap agent hierarchies ko samajhte/debug karte ho.

---

<details>
<summary>📜 Full English Transcript (original, click to expand)</summary>

Okay, now there's something a bit confusing now, which I'll have to get your head around, which is that you can, as we've just done, turn a function into a tool. There's something else you can turn into a tool as well. You can turn a whole agent into a tool. You can say, we've got this sales agent, something that can write a sales email. Well, that whole thing, that whole process of calling that LLM with that prompt, that can just be considered itself to be a tool. We can think of it as a sales agent tool. And doing that might sound like there's a fair amount of work to be done to package an LLM call into a tool. But no, all you have to do is call as_tool on the agent, and you will convert the agent into a tool.

What does it mean to convert an agent into a tool? All it means is it's going to create a new tool. It's going to have all of the JSON gunk that describes what that tool can do. And if that tool is called, it's going to actually call the agent and make the agent make the call to the LLM. So it's a wrapper. A wrapper around the agent that turns the agent into a tool. That's all it is.

So let's look at this sales agent one as_tool. We're going to give it a tool name, sales agent one still, and "write a cold sales email" is our description of what that tool can do. And now if we look at tool one, you can see it's a function tool just like this one. Just like send email. It's got a different name. Its description is this description here. Now it's got the same parameters, the JSON blob that we would expect. And it's got a special function to tell it what to do when the tool is actually called. And that of course is actually going to call our agent. So hopefully that makes sense. We're now going to package our agents into tools and use them.

All right, here we go. So this — I could have done this with a fancy loop, but I thought, you know what? I'll just spell it out so that you're crystal clear on what's happening here. We're going to have three tools. Tool one, tool two, and tool three. And it is just taking the three agents — sales agent one, two and three — and calling as_tool on each of them. And for each one we just give it a tool name and a tool description, which is the same tool description. That is it. Now if you feel up to it, just rewrite that as a nice little loop so that we don't have a silliness with repetition like this. But I wanted to spell it out.

And now I'm giving myself a list called tools, and tools has tool one, tool two, tool three. And these are like the agents wrapped as tools. They're tools that would simply call the agents. And then send email is the real tool that is just a function — send email that calls SendGrid, the email program. And let's have a look at what we get if we run this. So now this is our list of tools. And it is indeed four function tools: sales agent one, sales agent two, salesperson three, and send email, all in a list of tools.

Okay, now it's time to put all of that into a sales manager. Our planning agent. So now it's a bit like we did before, except we're giving an agent the ability to choose what to run when. It's not like we're just writing Python code to say, do this, this, this, and then send email. But rather, we're letting the agent decide. You are a sales manager working for ComplAI. You use the tools given to you to generate cold sales emails. You never generate sales emails yourself. You always use the tools. You try all three tools once before choosing the best. You pick the single best email and use the Send Email tool to send the best email, and only the best email, to the user. Now, I'm probably over spelling it out here. You can experiment. It's not always required to be so pedantic, but I'm also doing it to show you what's going on. And it's never a bad thing to be very precise and instructive with your prompts.

Okay, so with that, we want to create a new sales manager agent. There it is. We want to give it these instructions — its system prompt. We want to pass in all four tools, all these tools right here. And we give it a model. And then we say: send a cold sales email addressed to "Dear CEO". And we start this going and off it runs. And this will take about 30 seconds. So I will see you in a sec. Well actually, it didn't take 30 seconds. It took 18 seconds. So it's quite quick, and it finished.

And we can — first, let's look in my email. I did in fact just receive an email, and here it is. And very good. It does indeed do things quite nicely. You'll see it's put like a template "CEO's name", not "Dear CEO" — you can improve the prompting to stop it doing that if you wish, but there's an exercise at the end to incorporate mail merge, so it actually would put in real people's names here. But very nice. We got the email, it came through to me, and it came from the verified email sender as expected.

The other thing to do, of course, is to go and have a look at the trace. Let's go and do that now. So here it is. Sales manager is what we called it. Four tools were used. It took 18 seconds. Let's go in and have a look. So it called Sales Agent one. It called Sales Agent two. Sales Agent three. And then it called Send Email. That's the tool that is just a tool. If you look at each of these sales agents tools, represented by this sort of green thing, you'll see that underneath that was an agent. So this hopefully makes it crystal clear for you that we had an agent, the professional sales agent, that was wrapped in the tool, sales agent one. And you can see that again for this one and for this one. But in the case of send email, it was simply a function that was called with a body. But you can look through the trace — and you should look through the trace — and understand the interactions between tools and agents to allow the sales manager to carry out its full activity, allowing itself to make its decisions about what it does, in what order.

</details>

---
*Source: Official Udemy lecture transcript (auto-captions, lightly cleaned). Notes in Hinglish for self-study.*
