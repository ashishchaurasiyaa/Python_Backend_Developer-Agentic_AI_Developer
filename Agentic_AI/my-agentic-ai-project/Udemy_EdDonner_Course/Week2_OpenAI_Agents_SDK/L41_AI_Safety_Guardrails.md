# L41 — Day 3: AI Safety in Practice — Implementing Guardrails

> **Week 2 — OpenAI Agents SDK** · ⏱️ ~5m · 🎥 Lecture 41 of 131
> **Instructor:** Ed Donner · **Lecture ID:** 49820725

---

## 🎯 Ek Line Mein (TL;DR)

Is lecture me hum **input guardrail** ko live action me dekhte hain — ek **"careful sales manager"** agent jo PII (kisi ka **naam**) detect hote hi **tripwire exception** throw karke pura agent run rok deta hai, aur clean input pe normally chalta hai.

---

## 📝 Hinglish Explanation (Detailed)

- **Careful Sales Manager banana** — bilkul pehle wala hi sales manager agent: same **name**, same **instructions**, same **tools**, same **handoffs**, same **model**. Sirf ek difference:
  - `input_guardrails=[guardrail_against_name]` — ek **input guardrail** pass kiya gaya hai.
  - Ed mention karta hai ki **output guardrails** bhi hote hain jo **final output** pe apply hote hain (input pe nahi).
- **Test 1 — Tripwire trigger karna (intentionally)**:
  - Message bheja: *"Send a cold sales email addressed to 'Dear CEO' from Alice"* — yaani input me deliberately kisi ka **naam (Alice)** daala.
  - Expectation: guardrail naam detect karega aur **tripwire** trigger hoga.
- **"Iska point kya hai?" — Ed ka important justification**:
  - Notebook me message **hard-coded** hai, to lag sakta hai ki "main to khud dekh sakta hoon ki naam hai, guardrail ki kya zaroorat?"
  - Real point: production me ye ek **product** hoga jaha input **users (sales team)** type karenge — hard-coded nahi hoga.
  - Guardrail ensure karta hai ki koi user galti se **CEO ka actual naam** ya doosra **PII** (jaise **phone numbers**) cold sales emails me na daal de.
  - Yaani protection **kisi bhi incoming input prompt** pe apply hota hai jo aapke agentic framework me aata hai — yahi guardrail ka asli purpose hai.
- **Run karne pe — Exception!**:
  - Run karte hi **exception** aata hai. Lagta hai code me bug hai, par nahi — **guardrail trigger hone pe SDK exception hi throw karta hai**: `InputGuardrailTripwireTriggered` type ka behaviour — output me dikhta hai *"Guardrail InputGuardrail triggered tripwire"*.
  - Ed kehta hai: *"something went right because something went wrong"* — exception aana hi success hai yaha.
- **Trace me inspect karna**:
  - Trace me **"Protected SDR"** run kholte hain → andar **guardrail_against_name** → **name check** agent dikhta hai.
  - Guardrail ka **structured output** dikhta hai: `is_name_in_message: true`, `name: "Alice"` — isliye process exception ke saath stop hua.
- **Test 2 — Tripwire trigger NA hona (clean input)**:
  - Same careful sales manager, par ab message: *"Send out a cold sales email addressed to 'Dear CEO' from the Head of Business Development"* — **Alice ka koi mention nahi**.
  - Ab koi angry guardrail nahi — run **successfully complete** hota hai aur ek decent email aata hai jo **"Head of Business Development"** se signed-off hai.
  - Funny observation: email me **"copyright 2023"** likha aaya — ye **knowledge cutoff** ka side-effect hai. Ed suggest karta hai ki chaaho to iske liye bhi ek aur guardrail/tripwire add kar sakte ho!
- **Exercises (lecture ke end me)**:
  - **Different models try karo** — course me **Gemini**, **DeepSeek**, aur **Llama 3.3 via Groq** try kiye gaye; aur bhi models experiment karo.
  - **More guardrails add karo** — additional input guardrails aur **output guardrails** dono.
  - **Structured outputs expand karo** — abhi emails plain text me generate hote hain; inhe bhi ek **pydantic object/schema** me populate karo — ye zyada **robust/bulletproof** approach hai.
  - SDR ko polish karo, chaaho to ek **user interface** bhi laga do — ek genuine business development tool ban sakta hai.
- **Wrap-up**: Ye session khatam — tools, agents, guardrails, structured outputs cover ho gaye. Next: **Deep Research** project (Week 2 ka agla bada project).

---

## 🔑 Key Concepts / Important Terms

| Term | Simple Hinglish Meaning |
|------|--------------------------|
| **Input Guardrail** | Agent ke **input** pe lagne wala safety check — `input_guardrails=[...]` param se agent pe attach hota hai |
| **Output Guardrail** | Final **output** pe lagne wala check — response user tak jaane se pehle validate karta hai |
| **Tripwire** | Guardrail ka "alarm" — condition match hote hi trigger hota hai aur run **exception** ke saath ruk jaata hai |
| **InputGuardrailTripwireTriggered** | Wo exception jo SDK throw karta hai jab input guardrail trip hota hai — bug nahi, intended behaviour |
| **PII (Personally Identifiable Information)** | Personal data jaise naam, phone number — jo cold emails me leak nahi hona chahiye |
| **Guardrail-as-Agent** | Guardrail khud ek chota agent hai (name-check agent) jo **structured output** (`is_name_in_message`, `name`) return karta hai |
| **Knowledge Cutoff** | Model ki training-data ki last date — isi wajah se email me stale "copyright 2023" aa gaya |
| **Structured Outputs** | Pydantic schema se typed output lena — plain text se zyada robust/bulletproof |

---

## 💡 Backend Dev Ke Liye Note (aapke liye)

- **Guardrail = middleware/validation layer**: Jaise FastAPI me request body pe **pydantic validation** fail hone par `422` aata hai aur handler kabhi execute nahi hota — waise hi input guardrail trip hone par expensive agent pipeline (tools, handoffs, LLM calls) **kabhi run hi nahi hoti**. Fail-fast at the boundary.
- **Exception-as-control-flow**: Tripwire trigger hona exception throw karta hai — production me ise `try/except InputGuardrailTripwireTriggered` me wrap karke user ko clean error message dena hoga (jaise aap custom exception handlers register karte ho). Exception ko bug mat samjho, ye **designed control flow** hai.
- **Defense-in-depth mindset**: Hard-coded notebook input pe guardrail "pointless" lagta hai, par ye wahi logic hai jisse aap user-facing API pe **input sanitization** kabhi skip nahi karte — "trust no input" rule LLM products pe bhi apply hota hai, balki zyada, kyunki prompt injection bhi ek attack vector hai.
- **Hands-on lab**: Is lecture ka code khud chalane ke liye ye lab run karo — `Practical/lab3_multimodel_guardrails.py` (is repo me, `uv run` se chalta hai, **Groq pe free**). Note: hamare labs OpenAI ki jagah **FREE Groq** use karte hain (`OpenAIChatCompletionsModel` + `base_url` trick), to lecture me jo OpenAI **tracing UI** dikh raha hai (Protected SDR trace kholna) wo hamare free setup me available nahi hoga — guardrail ka structured output console pe print karke inspect karo.

---

## 🧠 Takeaway (yaad rakho)

1. **Guardrail attach karna trivial hai** — agent definition me bas `input_guardrails=[...]` add karo; baaki sab (name, instructions, tools, handoffs, model) same rehta hai.
2. **Tripwire trigger = exception** — guardrail trip hone par SDK exception throw karke pura run rok deta hai; "something went right because something went wrong."
3. **Guardrails production ke liye hain** — notebook me input hard-coded hai, par real product me users input type karenge; PII (naam, phone) ko emails me jaane se rokna hi point hai.
4. **Guardrail khud ek agent hai** with structured output — trace me dekh sakte ho: `is_name_in_message: true, name: "Alice"`.
5. **Aage badhao**: aur models (Gemini/DeepSeek/Groq-Llama), aur guardrails (input + output), aur structured outputs (email bhi pydantic schema me) — phir UI lagao to ready business tool.

---

<details>
<summary>📜 Full English Transcript (original, click to expand)</summary>

Okay. The moment of truth. It's time to actually run a careful sales manager, a new sales manager. And this is an agent. It's named the same as before. Sales manager. The instructions. Same as before. Sales manager's instructions. Same tools and same handoffs as before. And the same model. The difference is right here. The difference is that we are passing in an input guardrail. Input guardrails is guardrail against name. And of course you can also have output guardrails that will affect the final output. And what we're doing is we're going to make this message send a cold sales email address to dear CEO from Alice and then kick this off. And no surprise, what we're doing here is we're passing in someone's name. And so we are expecting that the trip wire is going to get triggered, because our guardrail is going to notice that there's someone's name in here.

Now, you might be forgiven for thinking, okay, well, what exactly is the point in this? I can see with my own eyes that we're passing in someone's name here, and you could just call an LLM at this point or something, you know? What are you doing exactly? The point is that, look, we've hard coded here the message that we're sending in to generate these sales emails. But the idea is that you'll be building this into a product. You'd have a product which would have a prompt, and your users, this kind of input wouldn't just be hard coded in a, in a notebook. It would be typed in by your users, your sales team, a prompt to kick off their sales automation. And so the purpose of this kind of tripwire is to make sure that no one types in your CEO's actual name, or perhaps there'll be other PII personal identifiable information like phone numbers, that you'd want to make sure did not get put in your cold sales emails. That's the intention here. So whilst this is a little bit artificial that we've got it right here, the point is that this protection would apply to any input prompts that are coming in to your agentic framework. That's the purpose of the guardrail.

So with that explained we will now kick this off. We're going to run the careful sales manager and off it goes. And bam there's been an exception, you might think bug in my code, but no. The exception is what happens when a guardrail is triggered. And what you'll see here is guardrail input. Guardrail triggered tripwire. So something went wrong. And to look in more detail on what went wrong I mean, something went right because something went wrong. We go in here, we open up the protected SDR and we should see guardrail against name, name check. And we should see that this guardrail got triggered. The output is name and message is true. Name is Alice. So indeed the guardrail here was triggered and that's why the process was stopped with an exception. So that is successful triggering of a tripwire and hopefully makes some sense.

And of course, to make sure you're convinced this is working, I need to show you an example with tripwire not being triggered. So we can just call exactly the same careful sales manager, but this time the message is going to be send out a cold sales email address to the CEO from the Head of Business development. No more mention of Alice. And if I kick this off? Off it goes. It's running. You can see right away that there isn't an angry guardrail that's being trip wired. And so that is running successfully. And in fact, I just kicked this off a moment ago as well. And so I already have my prior email. And here it is. It did indeed come back with a perfectly decent email, and you'll be pleased to see that it's signed off. The head of Business Development. I'm interested to see it also has a copyright 2023, which is a slight sign of the results of knowledge cut offs there. You could always try and add that as a tripwire, as a guardrail if you wished.

So that is showing you guardrails working and now some exercises for you to take this to the next level. Try some different models. We've tried Gemini and DeepSeek and Grok llama 3.3 through Groq. This has just finished successfully, and you can try more of those two and see the different, different kinds of models that you can use there. The variety add some more input guardrails and output guardrails. And then finally we had our first exploration of structured outputs there with the agents SDK. Try adding some more. When we generate emails we could actually be populating one of these pydantic objects a schema instead of just returning text of the email. So try adding that too that is obviously a more robust, more bulletproof way of doing it. And then experiment with this and get to a point when you're happy with your SDR. You could also put a user interface around it if you wanted. And that is an interesting business development tool.

All right. That concludes our session on tools agents, guardrails structured outputs and the like. Next time we're moving on to our next big project, which I'm so excited about building our own deep research. See you next time.

</details>

---
*Source: Official Udemy lecture transcript (auto-captions, lightly cleaned). Notes in Hinglish for self-study.*
