# L23 — Day 5: Building AI Assistants — Implementing Tools for Handling Unknown Questions

> **Week 1 — Foundations** · ⏱️ ~3m · 🎥 Lecture 23 of 131
> **Instructor:** Ed Donner · **Lecture ID:** 49771329

---

## 🎯 Ek Line Mein (TL;DR)

Career agent ke **system prompt** mein ab tools ke liye explicit instructions add hoti hain — "unknown question aaye toh **record_unknown_question tool** use karo, user engage ho toh **email ki taraf steer** karo" — aur Ed ek important reality check deta hai: tool calling koi magic autonomy nahi, sirf **statistical next-token prediction** hai jisko hum prompt se **bias** karte hain.

---

## 📝 Hinglish Explanation (Detailed)

- **Moment of truth — setup wapas assemble hota hai:**
  - Pehle ki tarah **LinkedIn profile** read karte hain (PDF se text) — Ed bolta hai hopefully ye *aapka* profile hai, uska nahi.
  - Phir **summary text** load hota hai, aur `name` variable mein **apna naam** daalna hai.
  - In sab se LLM ke liye **system prompt** aur **user prompt** ready ho jate hain — system prompt wahi purana hai: "tum is person ki tarah act kar rahe ho, unki website pe unke **career** ke baare mein questions answer kar rahe ho", etc.

- **System prompt mein naya twist — tool-use instructions:**
  - End mein 2 nayi lines: **"agar kisi question ka answer nahi pata, toh apna tool use karke us question ko record karo"** (yaani `record_unknown_question`).
  - Aur: **"agar user discussion mein engage ho raha hai, toh use email ke through get-in-touch karne ki taraf steer karo, aur tool se record karo"** (yaani `record_user_details`).

- **"In theory ye needed nahi hai" — par repetition kaam karti hai:**
  - Technically, tool ka **JSON schema/description** (jo humne pichhle lab mein likha) already model ko batata hai ki tool kya hai aur kab use karna hai.
  - Lekin Ed ka prompting principle: **repetition never hurts** — cheezein **kai baar explain karo**, isse probability badhti hai ki model aapke hisaab se behave karega.
  - Core idea: aap model ko **bias** kar rahe ho ki woh aapke **objective ke consistent tokens** output kare. Ye baat hamesha dimaag mein rakhni chahiye.

- **Important sidebar — tool calling ki asli reality (demystification):**
  - Hum casually bolte hain "model ne tool **call** kiya", jaise model ke paas **true autonomy** ho. Par actually aisa kuch nahi hai.
  - Ek **LLM** bas ek sequence of tokens ke baad **most likely next tokens** generate karta hai — basically glorified **predictive text**.
  - Agar humne prompt mein **tools ka description** + "kab use karna hai" wali directions insert ki hain, toh **most likely next tokens** wahi honge jo us information ke consistent hain — bas yahi tool calling hai.
  - Ed admit karta hai ki ye **mind-bending** hai — itna unlikely lagta hai ki sirf next-token prediction se tool calling jaisi powerful cheezein ho sakti hain — par **yahi ho raha hai**: statistical most-likely tokens.
  - Ed ke paas is topic pe (next-token prediction kaise ye sab achieve karta hai) kuch **YouTube videos** bhi hain agar deep dive karna ho.

- **Aage kya:** ab sab kuch ready hai — **chat function** banega jahan ye sab action mein aayega. Woh **next video** mein cover hoga.

---

## 🔑 Key Concepts / Important Terms

| Term | Simple Hinglish Meaning |
|------|--------------------------|
| **System Prompt (tool instructions ke saath)** | Persona + context ke saath explicit directions: "unknown question → record karo, engaged user → email ki taraf le jao" |
| **record_unknown_question tool** | Jab LLM ko answer nahi pata, woh ye tool call karke question log/record karwata hai (silent failure ki jagah visibility) |
| **Repetition in Prompting** | Same instruction tool JSON + system prompt dono mein dena — redundancy se model ke sahi behave karne ki probability badhti hai |
| **Biasing the Model** | Prompt mein info daal kar model ke "most likely next tokens" ko apne objective ki taraf shift karna |
| **Next-Token Prediction** | LLM ki asli mechanics — input sequence ke baad statistically most likely text generate karna; tool calling bhi isi se hota hai |
| **No True Autonomy** | "Model tool call karta hai" sirf bolne ka tareeka hai — actually model bas tool-call jaisa dikhne wala JSON token-by-token predict karta hai |

---

## 💡 Backend Dev Ke Liye Note (aapke liye)

- **Tool calling = structured output + dispatch table, no magic:** model kabhi aapka function execute nahi karta — woh bas ek JSON (`{"name": "record_unknown_question", "arguments": {...}}`) *predict* karta hai, aur **aapka code** use parse karke dispatch karta hai. Ye samajh lena debugging ke liye game-changer hai: agar tool call nahi ho raha, toh problem prompt/schema mein hai (model ko enough bias nahi mila), runtime mein nahi.
- **Redundant instructions ≈ defense in depth:** tool JSON description + system prompt repetition waise hi hai jaise aap DB constraint + application-level validation dono rakhte ho. LLMs probabilistic hain, deterministic nahi — isliye redundancy yahan code smell nahi, **best practice** hai.
- **`record_unknown_question` ek observability pattern hai:** production API mein jaise aap unhandled cases ko Sentry/structured logs mein bhejte ho, waise hi ye tool LLM ke "I don't know" moments ko capture karta hai — taaki aap baad mein resources/prompt improve kar sako. Silent hallucination se kahin better.
- **Hands-on:** is lecture ka code khud chalane ke liye ye lab run karo — `Practical/lab4_career_agent.py` (uv run se chalega, Groq-free).

---

## 🧠 Takeaway (yaad rakho)

1. System prompt mein **explicit tool instructions** add karo ("unknown → record karo, engaged → email steer karo") — bhale hi tool JSON mein already likha ho.
2. **Repetition works:** prompting mein same baat multiple jagah repeat karna model ke correct behaviour ki probability badhata hai.
3. Tool calling mein **koi autonomy nahi hai** — LLM sirf most likely next tokens predict karta hai; prompt mein tool info dene se woh tokens tool-call ke consistent ho jate hain.
4. Prompting ka mental model: aap model ko apne **objective ki taraf bias** kar rahe ho, command nahi de rahe.
5. Ye demystified samajh (next-token prediction → tool calls) hamesha yaad rakho — agentic systems design aur debug karne mein kaam aayegi.

---

<details>
<summary>📜 Full English Transcript (original, click to expand)</summary>

All right. Now it's the moment of truth. We now read the LinkedIn profile in as before, and hopefully this is your LinkedIn profile, not mine. And then we bring in the summary text. You should change this name to be your name. We run that and we now have our system prompt and user prompt for the LLM. And the system prompt is going to be the same as last time: you're acting as me or you, you're answering questions on their website, particularly related to their career, etc., etc. But there's a twist at the end here. It says if you don't know the answer to any question, use your tool to record the question you couldn't answer. And if the user is engaging in discussion, try to steer them towards getting in touch via email. Record it using your tool.

Now, in theory, this isn't needed because the JSON that we've written to describe the tool already gives this kind of context and describes the tool and when it should be used. But it never hurts to be repetitive in prompting, as I'm sure you know — repetition always works well. Explain things several times over, because you will increase the probability that your model performs the way you want it to. You're biasing the model to be outputting tokens consistent with your objective, and it is important to always keep that in the back of your mind.

We often like to talk about, you know, the model calls this tool, and we make it sound like it almost has something that has true autonomy. But all that's actually going on here — and always remind yourself of this from time to time — an LLM is just something that's generating the most likely next tokens to follow a sequence of tokens. It's got an input and it's generating like predictive text. What is the most likely text to follow this? And if we've inserted into this prompt stuff about different tools that it could call and stuff that directs it to use them, then that just means that the most likely next tokens will be consistent with that information that we passed in. And that's all that's going on. It's about statistical most likely tokens.

And that really — I mean, it hurts my mind to try and think that one through, because it seems so unlikely that predicting next tokens could be so powerful as to do things like calling tools. But that really is what's happening here. All right, that was a sidebar, but it's an important sidebar. You should always try and keep that in mind. And I have a bunch of YouTube videos about that stuff, if you want to learn more about how next token prediction is able to achieve these things.

Okay, so with all of this we get to our chat function again. And this is where it really comes down to action. And we'll cover it in the next video.

</details>

---
*Source: Official Udemy lecture transcript (auto-captions, lightly cleaned). Notes in Hinglish for self-study.*
