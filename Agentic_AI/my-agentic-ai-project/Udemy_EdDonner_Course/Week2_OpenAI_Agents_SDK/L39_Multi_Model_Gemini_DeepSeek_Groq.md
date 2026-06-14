# L39 — Day 3: Multi-Model Integration — Using Gemini, DeepSeek & Groq

> **Week 2 — OpenAI Agents SDK** · ⏱️ ~8m · 🎥 Lecture 39 of 131
> **Instructor:** Ed Donner · **Lecture ID:** 49820713

---

## 🎯 Ek Line Mein (TL;DR)

OpenAI Agents SDK sirf OpenAI ke liye nahi hai — **OpenAI-compatible endpoints** + **AsyncOpenAI client** + **OpenAIChatCompletionsModel** ka combo use karke aap **Gemini, DeepSeek, aur Groq (Llama 3.3)** jaise kisi bhi model ko same SDK se chala sakte ho; aaj ke din ka agenda hai **multi-model + structured outputs + guardrails**.

---

## 📝 Hinglish Explanation (Detailed)

- **Pichle lecture ka recap (Day 2):**
  - **`@function_tool` decorator** — ek simple decorator se koi bhi Python function tool ban jaata hai, week 1 wala boilerplate JSON likhne ki zaroorat nahi.
  - **`agent.as_tool()`** — ek agent ko doosre agent ka **tool** banana bhi utna hi easy hai.
  - **Handoffs vs Tools** — confusion clear karte hain:
    - **Tool** = doosre agent ko **call** karna; woh kaam karke **return back** karta hai (control wapas aata hai).
    - **Handoff** = **transfer of control**; workflow ka next step receiving agent ke haath me chala jaata hai, wapas nahi aata.
- **Aaj ke 3 extensions (Day 3 agenda):**
  1. **Non-OpenAI models** — SDK se Gemini, DeepSeek waghaira chalana (jo promise kiya tha).
  2. **Structured outputs** — agent sirf free text nahi, balki ek **object** populate kare jisme fields hum specify karein.
  3. **Guardrails** — agent setup me jo information **aati** hai aur jo **bahar jaati** hai, uspe controls lagana.
- **Multi-model setup ka recipe (lab 3, week 2 day 3):**
  - `.env` se usual se zyada keys load karte hain — **Google, DeepSeek, Groq**. Ye optional hai: agar ye keys nahi hain to sirf OpenAI se kaam chala sakte ho. **OpenRouter** use karte ho to wahi bhi laga sakte ho.
  - **3 sales agent instructions** wapas aate hain — ek **professional**, ek **witty/engaging**, ek **concise** (SDR project continue ho raha hai).
  - **Step 1 — Base URLs:** Gemini, DeepSeek aur Groq ke **OpenAI-compatible endpoints** ke base URLs set karo. Gemini aur Groq ke URL me literally "openai" likha hota hai; DeepSeek ka endpoint already by-default OpenAI-compatible hai.
  - **Step 2 — Client:** har provider ke liye ek **`AsyncOpenAI`** client instance banao, jisme `base_url` aur us provider ki API `key` pass hoti hai.
  - **Step 3 — Model object:** **`OpenAIChatCompletionsModel(model=<naam>, openai_client=<client>)`** — model ka naam + upar wala client pass karo.
- **Sabse important rule — `model` param ka behaviour:**
  - Agar `Agent(..., model="gpt-4o-mini")` me **string** pass karo → SDK assume karta hai ki tum **directly OpenAI** se baat kar rahe ho (default case, koi extra boilerplate nahi).
  - Agar **`OpenAIChatCompletionsModel` ka instance** pass karo → SDK us custom endpoint/client ke through us model se connect karega.
- **Teen agents, teen alag models:**
  - **Sales Agent 1 → DeepSeek**
  - **Sales Agent 2 → Gemini**
  - **Sales Agent 3 → Llama 3.3 via Groq** (massive Llama model, Groq = fast inference platform)
- **Baaki pipeline same as Day 2 (quick revision):**
  - Teeno sales agents ko **`as_tool()`** se `tool1`, `tool2`, `tool3` banaya, common description ke saath ("write a cold sales email").
  - **`@function_tool`** se normal function tool (send email) wrap kiya — decorator hi boilerplate JSON generate karta hai.
  - **Subject writer agent** (email ka subject likhta hai) aur **HTML converter agent** (text email → HTML) banaye — dono plain string `"gpt-4o-mini"` model ke saath — aur dono ko bhi tools me convert kiya.
  - **Emailer agent** = instructions + email tools + **handoff description** (taaki manager use handoff target ke roop me samjhe).
  - **Sales Manager agent** = instructions + 3 sales tools + handoffs me emailer agent → run karo, cold sales email likhi jaati hai. ~1 minute lagta hai complete hone me.
- **Net learning:** ek hi workflow me **3 alag LLM providers** seamlessly mix ho gaye — SDK ko fark nahi padta model kahan host hai, bas endpoint OpenAI-compatible hona chahiye.

---

## 🔑 Key Concepts / Important Terms

| Term | Simple Hinglish Meaning |
|------|--------------------------|
| **OpenAI-compatible endpoint** | Doosre providers (Gemini, Groq, DeepSeek) ka URL jo OpenAI ke API format me hi requests accept karta hai — isi wajah se same SDK chal jaata hai |
| **`AsyncOpenAI`** | OpenAI ka async client class; `base_url` + `api_key` change karke kisi bhi compatible provider se connect ho jaata hai |
| **`OpenAIChatCompletionsModel`** | SDK ka model wrapper — model name + custom client leta hai; isko `Agent(model=...)` me pass karo to non-OpenAI model use hota hai |
| **model as string vs object** | String (`"gpt-4o-mini"`) = direct OpenAI assume hota hai; object = custom endpoint use hota hai |
| **Tool (agent as tool)** | Doosre agent ko call karna, jawab wapas milta hai — control caller ke paas hi rehta hai |
| **Handoff** | Control ka transfer — receiving agent workflow ka agla step apne haath me le leta hai |
| **Structured outputs** | Agent free text ki jagah ek defined-fields wala object populate kare (aaj ke din ka 2nd topic) |
| **Guardrails** | Input/output pe controls — kya andar aa sakta hai, kya bahar ja sakta hai (aaj ka 3rd topic) |
| **Groq** | Fast-inference platform jo open models (jaise Llama 3.3) ko bahut tezi se serve karta hai (xAI ke "Grok" model se alag cheez) |
| **OpenRouter** | Ek aggregator service — ek hi key/endpoint se kai models access karne ka alternative tareeka |

---

## 💡 Backend Dev Ke Liye Note (aapke liye)

- **Ye pattern ekdum `boto3`/DB-driver jaisa adapter pattern hai:** interface (OpenAI chat completions API) standard ho gaya hai, implementation (Gemini/DeepSeek/Groq) pluggable. Jaise tum Postgres-wire-compatible databases me sirf connection string badalte ho, yahan sirf `base_url` + key badalti hai — application code untouched.
- **`AsyncOpenAI` ka matlab hai sab kuch asyncio event loop pe chal raha hai** — teen alag providers ko parallel `asyncio.gather` style fan-out karna free me milta hai. Ye wahi non-blocking I/O hai jo tum FastAPI me external API calls ke liye karte ho.
- **String vs object polymorphism in `model` param** — ye classic "convenience overload" API design hai (jaise requests me `auth=("user","pass")` vs `auth=CustomAuth()`). Production code me explicit `OpenAIChatCompletionsModel` use karna better hai, taaki provider switch config-driven ho.
- **Hands-on lab:** is lecture ka code khud chalane ke liye **`Practical/lab3_multimodel_guardrails.py`** run karo (is repo me, `uv run` se chalta hai, **Groq pe free**). Note: hamare labs OpenAI ki jagah FREE Groq use karte hain (wahi `OpenAIChatCompletionsModel` + `base_url` trick jo is lecture me sikhaya gaya — yani lab khud is technique ka live proof hai), is liye OpenAI ka paid key bilkul zaroori nahi.

---

## 🧠 Takeaway (yaad rakho)

1. **3-step recipe for any model:** base URL (OpenAI-compatible) → `AsyncOpenAI(base_url, api_key)` → `OpenAIChatCompletionsModel(model_name, client)` → `Agent(model=<object>)`.
2. **String = OpenAI direct, object = custom provider** — `model` param ka ye dual behaviour yaad rakho.
3. **Tools return back, handoffs transfer control** — ye distinction har multi-agent design decision ka core hai.
4. Ek hi workflow me **multiple providers mix** karna trivial hai — sales agent 1 = DeepSeek, 2 = Gemini, 3 = Llama 3.3 @ Groq, manager = GPT-4o-mini.
5. Aaj ke aage ke topics: **structured outputs** (object-shaped responses) aur **guardrails** (input/output controls) — ye agle lectures me deep dive honge.

---

<details>
<summary>📜 Full English Transcript (original, click to expand)</summary>

And welcome to week two, day three. We have lots to cover today. Continuing our exploration of OpenAI Agents SDK and with our SDR project. So I want to quickly take a moment to recap what we did last time. We looked at tools by just using that simple decorator as a way to allow us to wrap a function into a tool and to be able to call that tool so easily without the boilerplate JSON that we'd needed to use in week one. We then looked at the way that agents can also be turned into tools. By using the as tool function, we can simply change an agent into being a tool. And that turned out to be very easy indeed. And then slightly confusingly, we saw that there is another way that agents can collaborate with each other, which is using handoffs. When you're creating a new agent, you can give it any number of tools and you can give it handoffs. And I explained that the key difference between them is that when you're using tools, you can think of that as a call to the other agent, which will then return back. But when you're doing handoffs, you can really think of that as a transfer of control. The next step on the workflow is giving over control to that agent that is on the receiving end of the handoff.

We're now going to go and extend what we did last time in three different ways. Three things that will allow us just to learn a bit more about the framework. First of all, we're going to do what I promised we'd do and look at models other than OpenAI. So using OpenAI Agents SDK to drive things like Gemini and DeepSeek. We're also going to look at structured outputs. The way that we can require an agent not to respond just with text, but to populate some kind of an object where we can specify the fields that are going to get populated. And then we're going to look importantly at guardrails, which are an approach to making sure that we have some controls over the information that comes in to our agent setup and what comes out.

All right. With that intro, let's go back to Cursor, back to the lab. And here we are back in Cursor. And we are looking at the second week. And we're looking at day three. Here we are lab three week two day three. And we're going to start by doing a sort of quick recap of what we did last time. We're going to do some imports. We're going to load the env. We're actually going to bring in a bunch more environment variables than usual. I'm looking at a bunch of different keys here. Google, DeepSeek, Groq. Now you don't have to do this. You can just stick with OpenAI if you don't have these other keys. But if you'd like to experiment with others, then this is the way to do it. And of course, if you have other things, perhaps you use OpenRouter as your way to connect to different models. You can be using any of these here.

All right. Now we have the three instructions for our three different sales agents. You'll remember one is more professional, one is more witty and engaging, and one is more concise. So in come our three instructions. We're now going to remember that we can use OpenAI's endpoints. We can use that compatible OpenAI endpoints to talk to other models like Gemini, DeepSeek and Groq. And any time that we have this approach, we will be able to easily use the OpenAI Agents SDK. So here we're setting the base URL for Gemini endpoint, the base URL for the DeepSeek endpoint, and for the Groq. These are the OpenAI compatible endpoints. So for Gemini you can see it's got OpenAI in there. And the same for Groq. For DeepSeek it is the only one. It's already OpenAI compatible. Then we create a new instance of the client by instantiating an AsyncOpenAI object. As you can see here, passing in the base URL and passing in the key. And finally we create three model objects. These are called OpenAIChatCompletionsModel, passing in the name of the model and the client that we just defined in the group above. So this is a little bit boilerplate. And if you're using GPT-4o-mini, if you're using any of OpenAI's models, you don't need to do any of this because it assumes by default that this is the case.

So what I mean is that when we actually create our agents, we're going to give them a name, instructions, and we're going to pass in one of these models. Now if for this model you pass in a string — you just pass in text, which is what we did before, we just passed in GPT-4o-mini right there — if it's text, then it assumes that you're talking directly to OpenAI. But if, by contrast, you pass in a model object, an instance of OpenAIChatCompletionsModel, then it will connect to this model using this endpoint. And so as you can see we have three agents: sales agents one, two and three. The first one is connecting to DeepSeek. The second one is connecting to Gemini. And the third one is connecting to Llama 3.3, the massive Llama model, through Groq, the fast inference platform. So there they are. This is how it all connects together. And we'll run that. And we now have these three agents connecting to these three different models.

We will now do exactly what we did before — our description, write a cold sales email. And we're now going to repackage each of those three sales agents into tools called tool one, tool two, tool three, and passing in this description as the description of the tool. And that is done. And we will now have a normal function tool. We use this decorator to reconstitute — wrap this function in the boilerplate JSON that describes this tool. And it's almost a wrap. We're zooming through everything we did last time. We've now got some instructions: you can write a subject for a cold email. We've got some HTML instructions: you can convert a text email to HTML. We then make a subject writer an agent, which is going to do this. And as I say, I'm just passing in the string GPT-4o-mini. So this is an agent that can write the subject of an email. This is turning that into a tool, a tool that can write the subject of an email. This is an agent that can convert an email to HTML format. And here it is as a tool, a tool that could convert a text email body to HTML email. I know I'm going through this very fast, but we just did it yesterday, so hopefully this is just immediate revision.

So we run that and we collect together those three tools. This is our emailer agent — the agent which is able to take some instructions, the email tools. And it has a handoff description, if you remember that. And now we're almost done. We now put these three sales tools into one group of tools. The handoff is now this one handoff agent, this emailer agent. We run that. And finally here we are, the same arrival as before: the sales manager's instructions. We pass in the instructions, we pass in the tools, we pass in the handoffs. And we then write the cold sales email. And with that I kick this off. It takes about a minute and I will see you in a second when it completes.

</details>

---
*Source: Official Udemy lecture transcript (auto-captions, lightly cleaned). Notes in Hinglish for self-study.*
