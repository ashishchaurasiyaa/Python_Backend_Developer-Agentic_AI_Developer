# L33 — Day 2: Build AI Sales Agents with SendGrid — Tools & Cold Email Workflows

> **Week 2 — OpenAI Agents SDK** · ⏱️ ~7m · 🎥 Lecture 33 of 131
> **Instructor:** Ed Donner · **Lecture ID:** 49820431

---

## 🎯 Ek Line Mein (TL;DR)

Aaj hum apna pehla **OpenAI Agents SDK project** banate hain — ek **Sales Development Rep (SDR)** — jo **3 layers of agentic architecture** dikhata hai: simple **agent workflow**, phir **tools** (SendGrid se email bhejna), aur phir **agent collaboration** (agents-as-tools vs **handoffs**).

---

## 📝 Hinglish Explanation (Detailed)

- **Aaj ka project — AI Sales Agents (SDR)**:
  - Week 2 ka pehla **hands-on project**: ek **Sales Development Representative** banana jo **cold sales emails** likhe aur bheje.
  - Ed isko **3 layers of agentic architecture** mein build karta hai — step by step complexity badhti hai:
    1. **Simple agent workflow** — agents ko Python code mein **manually orchestrate** karna (sirf sequential calls).
    2. **Agent + Tool** — ek agent jo **tool use** kar sake (yaad karo Week 1 mein humne ye **manually JSON boilerplate** likh ke kiya tha — ab SDK ye sab handle karega).
    3. **Agents calling agents** — collaboration ke **2 alag tarike**: **agents as tools** ya **handoffs** (jo pehle mention hua tha).
  - Ye construct dimaag mein rakho — workflow → tools → collaboration — yahi progression follow hogi.

- **Setup — Lab 2 (Week 2, Day 2)**:
  - Cursor mein **OpenAI folder → Lab 2** kholte hain. Plan: agent workflow → tools to call functions → collaboration via tools & handoffs.

- **SendGrid setup (transactional email service)**:
  - **SendGrid** ek service hai jo unke servers se **transactional emails** bhejne deti hai. **Free tier** hai, setup easy hai.
  - Ye **Twilio** ki company hai — well known. **Sparkpost** jaisa hi hai; agar tum Sparkpost prefer karo to wo bhi chalega.
  - Setup steps:
    1. SendGrid pe jao, **"Start for free"** button se account banao.
    2. **Settings → API Keys** section mein jaa ke ek **API key** create karo aur clipboard pe copy karo.
    3. **Sender Authentication** tab → **"Verify a Single Sender"** button — apna khud ka **email address verify** karo (verification email aayega). Iske baad tum us address se emails bhej paoge.
  - **Important**: hum duniya ko actual cold emails NAHI bhej rahe — emails **sirf wapas tumhare hi address pe** jayengi. Ye purely experimental hai (future mein aur uses ke liye kaam aa sakta hai).
  - Phir `.env` file mein ek line add karo: `SENDGRID_API_KEY=` aur copied key paste karo.

- **Imports**:
  - Usual cheezein + `agents` package se kuch naya: **`function_tool`** (Python function ko tool banane ke liye), streaming text helper, aur **SendGrid** ke imports. `.env` se environment variables load hote hain.

- **Layer 1 — Simple agent workflow (manual orchestration)**:
  - Bina kisi fancy cheez ke — agents ko hum **khud Python code mein orchestrate** karte hain (manual sequential calls).
  - **3 instructions** (yaad rakho — instructions = **system prompts**, yahi har agent ka framing/persona set karti hain):
    - Company ka naam: **ComplAI** — ek **SaaS tool** jo companies ko **SOC 2 compliance** / SOC 2 audits ke liye prepare karne mein help karta hai.
    - **Agent 1**: professional, serious sales agent — formal cold emails likhta hai.
    - **Agent 2**: humorous, engaging sales agent — witty emails jo response milne ke chances badhayein.
    - **Agent 3**: busy sales agent — concise, to-the-point emails.
  - Good prompting principle: **system prompt/instructions se context, tone, mood, character set karo** — succinct, instructive background do.
  - Phir **3 agents** create hote hain (`sales_agent1/2/3`) — har ek ko alag **name** + alag **instructions** milti hain, sab **GPT-4o-mini** use karte hain (**keep it cheap**).

- **Streaming — `Runner.run_streamed()`**:
  - Pehle humne `Runner.run()` dekha tha; ab **`Runner.run_streamed()`** — results ko **stream back** karne ka tarika (jaise simple OpenAI examples mein streaming hoti hai, par SDK style).
  - **Note**: yahan **`await` nahi** hai — alarm bells! Iska matlab return value response nahi, ek **coroutine** hai.
  - Phir **`async for`** construct se hum stream ke events iterate karte hain — thoda **boilerplate** check karta hai ki jo aaya wo **text delta** hai ya nahi, aur agar hai to print kar deta hai (same line pe, naye line pe nahi).
  - Run karne par output **bit-by-bit stream** hota hai — streaming API ka nice use, taaki tumhare paas ek working example ho.

- **Result**:
  - Professional agent ne ek **slick, professional cold email** likha ("simplify your SOC 2 compliance efforts" type). Koi surprise nahi — **LLMs is kaam mein bahut acche hain**: realistic, reasonable sales outreach emails likhna inka strong suit hai. So far, so good.

---

## 🔑 Key Concepts / Important Terms

| Term | Simple Hinglish Meaning |
|------|--------------------------|
| **SDR (Sales Development Rep)** | Cold emails likh ke leads generate karne wala sales role — yahi hamara AI project hai |
| **3 Layers of Agentic Architecture** | (1) Workflow of agent calls → (2) Agent + Tools → (3) Agents calling agents |
| **SendGrid** | Twilio ki transactional email service — free tier se programmatically emails bhejo |
| **Sender Authentication / Single Sender Verify** | SendGrid mein apna email address verify karna taaki us address se emails bhej sako |
| **`SENDGRID_API_KEY`** | `.env` file mein rakha jaane wala SendGrid ka API key |
| **`function_tool`** | Agents SDK ka import — Python function ko agent ke liye tool bana deta hai |
| **Instructions = System Prompt** | Agent ka persona/tone/context set karne wala text — ComplAI ke 3 alag personas |
| **ComplAI** | Fictional SaaS company — SOC 2 compliance audits ke liye AI tool |
| **`Runner.run_streamed()`** | SDK se streaming response lene ka tarika — `await` nahi, coroutine/stream milta hai |
| **`async for`** | Stream ke events ko iterate karne ka async construct |
| **Agents as Tools vs Handoffs** | Agents collaboration ke 2 tarike — agla concept jo is lab mein aayega |

---

## 💡 Backend Dev Ke Liye Note (aapke liye)

- **`run_streamed()` ka pattern** waise hi hai jaise FastAPI mein `StreamingResponse` + async generator: function turant ek stream object return karta hai (no `await`), aur tum `async for` se **SSE-style deltas** consume karte ho. Wahi event-loop mental model — bas yahan events agent-run ke hain (text deltas, tool calls etc.).
- **Instructions-per-agent** ko aise socho jaise ek hi service class ke 3 instances alag-alag **config/strategy injection** ke saath — same model (GPT-4o-mini), alag system prompt = alag behavior. Cheap A/B testing of personas.
- **SendGrid = paid/external setup wali cheez** (free tier hai par account + API key + sender verification chahiye). Hamare labs **OpenAI ki jagah FREE Groq** use karte hain (`OpenAIChatCompletionsModel` + `base_url` trick), is liye OpenAI tracing dashboard bhi apply nahi hota — SendGrid optional rakho ya email-send function ko console-print stub se replace karke bhi seekh sakte ho.
- **Hands-on lab**: is lecture ka code khud chalane ke liye `Practical/lab2_sales_agents_handoffs.py` run karo (is repo me, `uv run` se chalta hai, Groq pe free).

---

## 🧠 Takeaway (yaad rakho)

1. Agentic projects ko **3 layers** mein socho: pehle plain **workflow** (manual Python orchestration), phir **tools**, phir **agent collaboration** (agents-as-tools ya handoffs).
2. **Instructions hi system prompt hai** — ek hi model se 3 alag personas (professional / witty / concise) sirf instructions badal ke milte hain.
3. **`Runner.run_streamed()` + `async for`** = SDK ka streaming pattern; `await` missing hona bug nahi, design hai — coroutine/stream milta hai.
4. **SendGrid** free transactional email service hai (Twilio ki) — API key `.env` mein, sender email verify karna zaroori; emails sirf khud ko bhejte hain, real cold outreach nahi.
5. LLMs **cold sales emails likhne mein naturally strong** hain — isi liye SDR ek perfect starter agent project hai.

---

<details>
<summary>📜 Full English Transcript (original, click to expand)</summary>

So look, you're here because you like getting hands on and building stuff. And that's why I'm here, too. And I got good news for both of us. That's what we're doing right now. Today we're going to be building our first OpenAI Agents SDK project, building a sales development rep. And we're going to be building really three different pieces. We're going to be building three different layers of agentic architecture. The way we do this, we're going to be starting with something quite simple, a workflow of agent calls. We're then going to spice it up by adding an agent that can use a tool. Remembering back to when we did this, the sort of manual way with the the JSON with the boilerplate in week one. And then we're going to have agents that can call on other agents, and you're going to discover there are two different ways of doing this. You can treat agents as tools, or you can use the thing called handoffs that I mentioned before. So keep this in mind. Keep this construct in mind. This is how we'll be approaching it. There's a lot of coding to do. Let's get started.

And so here we are back in Cursor ready for the day to begin, we open the OpenAI folder. We go to lab two. Here we are at the start of week two. Lab two, day two. We're going to do an agent workflow. We're going to use tools to call functions. And then we're going to collaborate with tools and handoffs.

So before we start we're going to be making use of a tool. It's called SendGrid. And it will allow you to send transactional emails from their servers. It is free. So it's going to be very easy to set up. It's actually owned by Twilio. So it's a very well known company. It's similar to something like Sparkpost if you've used that before. And of course you can use Sparkpost instead if you'd prefer. So there's a link here. If you visit SendGrid right there up, it will come and you can start for free by pressing this button right here. And once you do that and you've set up an account, I will switch to another window. Here we go. This is what I get once I've signed in. You can see that I've sent 1 or 2 emails, and there's just a few things for you to do. Once you've done this, you go to the settings menu down here and to the API keys section. That is where you will set up an API key and copy it to your clipboard. You can guess where that's going to go in just a second. The other thing to do is to go to this tab here Sender Authentication. And you're going to click this verify a single sender button. And what that's going to do is it's going to allow you to set up your your own email address. This is my email address right here. And do like a verify email to confirm that you do own that email. And once you've done that, you'll be able to send emails from that email address. So that's a nice thing to do, just so that you'll be able to send emails via SendGrid from that email address. But don't worry, we're not actually going to be sending any cold emails out to the world. It will only be emails going back to you again, this would just be experimental, but you can always use it for more purposes in the future. So that is SendGrid. Please go ahead and get that set up.

And shockingly, I'm sure you expected this. Once you've done that, you'll then edit your env file over there and you will add in a single row SendGrid API key equals. And of course you will paste in there the thing that you've copied from the API keys section. You created a key there in SendGrid itself. All right. So go ahead and do that and then we will proceed.

Okay. And so now we have some imports. We're going to be doing some usual stuff. We've got a few more from agents. We're also importing this thing called function tool. We're importing something to help us stream back text. And we're importing some SendGrid stuff. We're going to load our environment variables as usual.

And now let's do a simple workflow between agents without anything fancy. Here we're just going to have some agents calling other agents, and we're going to orchestrate it manually ourselves in Python code. And it's going to be super simple. So first of all three instructions. And these instructions again think of it in the back of your mind. These are basically system prompts. But they are the way that we are framing different agents. All three are about being sales agents working for a company that I'm calling ComplAI. The wonderful naming. This is a SOC 2 compliance company that is looking at helping companies prepare for SOC 2 audits. So something to do with compliance if you're not familiar with this stuff. But, uh, yeah, it's a SaaS tool that will ensure SOC 2 compliance. So it's saying you're a sales agent working for this company. You write professional, serious cold emails. It's like a cold sales email or email to to get people interested. The second one is a humorous, engaging sales agent. You write witty, engaging, cold emails that are likely to get a response. And the third one is you're a busy sales agent and you write concise to the point cold emails. So, as you know from good prompting, you use a system prompt instructions to set the context, to give the tone to sort of set. Set the mood and the character and give as much background information as you can in a succinct, instructive way.

Okay, so now we create three agents sales agent one, two and three. And this should be very simple. It should make complete sense to you. Each agent gets given a different name. They have the three instructions the three system prompts. And we're going to be using GPT-4o mini throughout. Keep it cheap. We've just created those three agents all right.

And now we're just going to start with the first one. And I just wanted to show you a different way. You remember we had runner run before. Well now I'm calling runner run streamed which is a way that you can do it. That will allow us to stream back results. You may be familiar with streaming from from simpler OpenAI examples, but this is how you can do it with the agents SDK. So you may spot that there's no await word there which which may set off alarm bells, because that means that what we're getting here is not a response. We're getting a coroutine and you can see what happens next. We use a special construct async for a special way of of then calling this, calling this in a way that will return a coroutine, and we will then iterate through those answers. And this is just a little bit of boilerplate code to make sure that what's coming back is some text that we can print. And if we get that, then we print it. And this just stops it printing on a separate line every time. So if I run this, it's just very similar to what we did last time. But you'll see that what comes back streams back bit by bit. And it's a very nice use of the streaming APIs and I show it to you. So you have an example of how to how to do this. And of course, just as you would expect, we see a great behavior from our agent. This is the professional one, I think, and we can see that it's come back with something nice and professional, nice and slick. To simplify your SOC 2 compliance efforts. And it's no surprise to to everyone that's worked with LLMs for a bit that they are really good at this kind of thing. They can write great professional, realistic, reasonable sales outreach emails. So far, so good.

</details>

---
*Source: Official Udemy lecture transcript (auto-captions, lightly cleaned). Notes in Hinglish for self-study.*
