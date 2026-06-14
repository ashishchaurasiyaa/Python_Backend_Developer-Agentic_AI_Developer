# L40 — Day 3: Implementing Guardrails & Structured Outputs

> **Week 2 — OpenAI Agents SDK** · ⏱️ ~10m · 🎥 Lecture 40 of 131
> **Instructor:** Ed Donner · **Lecture ID:** 49820721

---

## 🎯 Ek Line Mein (TL;DR)

Autonomous agents kabhi-kabhi **loop me phas jaate hain** (instability!), isliye Ed do safety concepts sikhate hain — **structured outputs** (pydantic schema se agent ka output type fix karna) aur **guardrails** (`@input_guardrail` / `@output_guardrail` decorated coroutines jo khud ek **agent** ho sakte hain, aur problem dikhne par **tripwire** trigger karte hain).

---

## 📝 Hinglish Explanation (Detailed)

- **Pichle run ki cautionary tale** — Ed ne jo multi-model sales agent flow kick off kiya tha, wo **expected se zyada time** le gaya aur "lose its way" ho gaya — baar-baar wapas jaake aur emails generate karta raha. Ed ne cancel karke dobara run kiya, tab theek chala.
  - Reason: instructions me likha tha *"you can use the tools multiple times if you're not satisfied with the results"* — yehi line agent ko **autonomy + potential infinite loop** de deti hai.
  - Trace me dikha: **14 tool calls, 300+ seconds**, sales agents 1→2→3 phir wapas 1→2→3... loop chalta raha.
- **Parallel async execution** — trace me ye bhi dikha ki teeno sales agents (**Agent 1 = DeepSeek, Agent 2 = Gemini, Agent 3 = Llama 3.3**) **parallel me run** ho rahe the.
  - Kyunki LLM calls **I/O bound** hain — API response ka wait hota hai — isliye **asyncio** multiple agents ko ek saath chala sakta hai.
  - Teeno run hone ke baad **sales manager** unke results review karta hai aur decide karta hai ki dobara run karna hai ya nahi (jo us bigde run me usne "lots of times" kiya).
  - **Key lesson**: autonomous agent frameworks me **inherent instability** hoti hai — iske liye **explicitly code** karna padta hai (guardrails yahi solve karte hain!).
- **Successful run** — dusri baar har agent sirf **ek baar** chala (DeepSeek, Gemini, Llama 3.3), response **handoff** ke through **email manager** ke paas gaya, jisne subject + email likha aur email inbox me aa gayi. Sab kaam kar gaya.
- **Anthropic Claude kyun missing hai?** — baaki sab models **OpenAI-compatible endpoints** dete hain, isliye unko use karna easy tha. Lekin **Anthropic OpenAI-compatible endpoint offer nahi karta**, isliye Claude ko directly is setup me use nahi kar sakte. Workarounds:
  - **OpenRouter** — third-party provider jo Claude (aur baaki models) ke liye OpenAI-compatible endpoint deta hai; apni keys set karke Claude use kar sakte ho.
  - **MCP protocol** — Anthropic ka "incredible" protocol, course ke **last week** me cover hoga; ye Anthropic use karne ka dusra route hai.
  - Filhaal easiest: **Anthropic ke alawa models** use karo.
- **Guardrails kya hain** — agent platform ke around ek **constraint/test**.
  - Aap soch sakte ho: "simple Python check likh do, property check karo, exception throw karo" — ho sakta hai. Lekin **special baat**: guardrails **khud agents ho sakte hain** — matlab ek **LLM se check karwa sakte ho** ki sab theek lag raha hai.
  - **Important limitation**: guardrails sirf **do jagah** lag sakte hain — **first agent ka input** ya **last agent ka output**. Beech me kahin nahi!
  - Purpose: model ko **inappropriate/unintended input** se bachana, aur user ko **galat output** dikhne se rokna. Sirf ye do extremes.
  - Is lecture me **input guardrail** implement hota hai; **output guardrail** challenge ke liye chhoda gaya (dono basically same hote hain).
- **Structured outputs — `NameCheckOutput`** — use case: emails me **personal names nahi chahiye**, to check karna hai ki user ke message me kisi ka naam to nahi.
  - Ek **pydantic class** define karo jo data ka **schema** reflect kare, do fields ke saath:
    - `is_name_in_message: bool` — true matlab message me naam hai
    - `name: str` — agar naam hai to wo naam
- **Guardrail agent banana** — ye abhi bas ek **normal agent** hai:
  - name: `"Name check"`, instructions: *"check if the user is including someone's personal name in what they want you to do"*
  - **`output_type=NameCheckOutput`** — yehi **structured outputs** ka piece hai! By default sab agents **plain string** output karte hain; `output_type` set karne se agent ko bolte ho ki **is schema ke conform karta object** return karo.
  - Ed ka hint: ye **kisi bhi agent** pe use kar sakte ho — e.g. emails ko strings ki jagah `subject`, `recipient`, `body` wale structured objects banana "much nicer" hoga (end ke challenges me hai).
  - Model: **GPT-4o-mini**.
- **Guardrail function likhna** — ye ek **coroutine** (async function) hai jise **`@input_guardrail`** decorator se decorate karte ho (bilkul tool decorate karne jaisa). Output ke liye analogous **`@output_guardrail`** hai.
  - Signature me milta hai: **context** (agents ke beech pass hone wala data — yahan use nahi kiya), **agent** khud, aur **message** (incoming input).
  - Andar: **guardrail agent ko run karo** us message pe — wo `NameCheckOutput` return karega.
  - **Return rule**: hamesha **`GuardrailFunctionOutput`** return karna hota hai, jisme do cheezein:
    - **`output_info`** — dictionary of useful stuff (tracing ke liye)
    - **`tripwire_triggered`** — boolean; **`True` = problem hai**, guardrail fail, "tripwire trip" ho gaya
  - Logic: agar guardrail agent ke output me `is_name_in_message == True` (LLM ko message me personal name mila), to **tripwire trigger** karo → guardrail fail → flow ruk jaata hai.
  - **Output guardrail** bilkul same hota hai — bas `message` ki jagah `output` check karte ho.

---

## 🔑 Key Concepts / Important Terms

| Term | Simple Hinglish Meaning |
|------|--------------------------|
| **Guardrail** | Agent platform ke around constraint/test — input ya output check karke problem hone par flow rok deta hai |
| **Input Guardrail** | First agent ke **input** pe lagne wala check — inappropriate input se model ko bachata hai |
| **Output Guardrail** | Last agent ke **output** pe lagne wala check — galat output user tak jaane se rokta hai |
| **`@input_guardrail` / `@output_guardrail`** | Decorators jo ek coroutine ko guardrail bana dete hain (tool decorator jaisa) |
| **Tripwire (`tripwire_triggered`)** | Boolean flag — `True` matlab guardrail fail hua, problem hai, flow halt |
| **`GuardrailFunctionOutput`** | Guardrail function ka mandatory return type — `output_info` (dict, tracing ke liye) + `tripwire_triggered` (bool) |
| **Structured Outputs** | Agent ko plain string ki jagah **pydantic schema** ke conform karta object return karwana |
| **`output_type`** | Agent constructor ka param jisme pydantic class dete ho — yehi structured output enable karta hai |
| **Guardrail-as-Agent** | Guardrail khud ek LLM agent ho sakta hai — simple Python check se zyada smart validation |
| **Agent instability / loops** | "Use tools multiple times" jaisi instructions agent ko loop me daal sakti hain — explicitly handle karna padta hai |
| **OpenRouter** | Third-party provider jo Claude jaise models ke liye OpenAI-compatible endpoint deta hai |
| **MCP** | Anthropic ka protocol (last week me cover hoga) — Claude use karne ka alternate route |

---

## 💡 Backend Dev Ke Liye Note (aapke liye)

- **Guardrail = middleware/validator, lekin LLM-powered**: FastAPI me jaise pydantic request validation + middleware hota hai, waise hi yahan — farak ye ki validator khud ek LLM agent hai jo *semantic* checks kar sakta hai ("kya isme personal name hai?") jo regex se impossible hain. Aur `GuardrailFunctionOutput` ka `tripwire_triggered=True` basically `raise HTTPException(422)` ka agentic equivalent hai.
- **`output_type` = response_model**: FastAPI ke `response_model=` jaisa hi mental model — SDK under the hood LLM ko JSON-schema-constrained output pe force karta hai aur pydantic se parse karke typed object deta hai. String parsing ki jagah `result.final_output.is_name_in_message` — type-safe access.
- **Infinite loop wali cautionary tale serious lo**: "retry if unsatisfied" instruction = unbounded retry loop without backoff/max-attempts. Production me jaise aap circuit breakers aur max-retry limits lagate ho, waise hi agent instructions me explicit bounds do ("at most 2 retries") — warna 14 tool calls, 300+ seconds, aur token bill.
- **Hands-on lab**: is lecture ka code khud chalane ke liye `Practical/lab3_multimodel_guardrails.py` run karo (is repo me, `uv run` se chalta hai, **Groq pe free**). Note: hamare labs OpenAI ki jagah FREE Groq use karte hain (`OpenAIChatCompletionsModel` + `base_url` trick) — lecture me jo GPT-4o-mini, SendGrid email aur OpenAI tracing dikhte hain, lab me wo free alternatives se replace hain, concepts bilkul same.

---

## 🧠 Takeaway (yaad rakho)

1. **Autonomous agents inherently unstable hain** — "use tools multiple times" jaisi instructions loop bana sakti hain; ek run fail, dusra fine. Explicitly code karo is instability ke liye.
2. **Guardrails sirf do jagah lagte hain** — first agent ka **input** ya last agent ka **output**; beech ke steps me nahi.
3. **Guardrail khud ek agent ho sakta hai** — LLM se semantic validation, plain Python checks se kahin powerful.
4. **Structured outputs = `output_type` me pydantic class** — agent string ki jagah schema-conforming object return karta hai; kisi bhi agent pe use karo.
5. **Guardrail function ka contract fix hai** — `@input_guardrail` decorated coroutine jo `GuardrailFunctionOutput(output_info=..., tripwire_triggered=...)` return kare; tripwire `True` = flow halt.

---

<details>
<summary>📜 Full English Transcript (original, click to expand)</summary>

Well, I'm back, although it took slightly longer than I expected, so the run that I had just kicked off actually ended up taking several minutes, and it appeared to lose its way. Going back again and again to get more and more emails generated. So I actually cancelled it and ran it a second time and it ran fine. But it is interesting. It's a cautionary tale to reflect on the fact that by their very nature, these autonomous agents are made. This statement here, and this was the answer to the challenge from last time that I say you can use the tools multiple times if you're not satisfied with the results. And that's really giving this kind of autonomy and potentially an infinite loop to the agent. And sure enough, I don't know if it was infinite, but we certainly had some kind of a loop going on. But I ran it a second time and it was fine.

If I bring up the trace, here come the traces. This is the one that was going wrong. You can see it had run 14 tools and it was taking more than 300 seconds. If I bring it up, you'll see that it was going through sales agents one, two and three and then back to one, two and three again. And I can load more and on. So it kept going. Now you'll see, of course, that agent one is DeepSeek. Agent two is Gemini. Agent three is Llama 3.3.

One other thing that I didn't point out last time that I would like to mention is that you can see that these are running in parallel. They are running, of course asynchronously because again, because they're very I/O bound, they are waiting for information to come back from the API call that allows asyncio to be running multiple in parallel. But of course the three run and then it needs to sort of wait for. Then the sales manager will review those three runs and decide whether it wants to run them again, which apparently it did lots of times. And Llama 3.3 for some reason took a really long time on one of them. So you can see there is inherent instability with these autonomous agent frameworks. And that's something that you need to code explicitly for.

Okay, but now let's just go back and look at the trace that did better. So this is the trace that just ran. And it took a rather more pleasing amount of time. And you can see that this time it only ran each agent once. DeepSeek, Gemini and Llama 3.3. Each one ran. Each one came back with a response. That response of course went to our handoff, went to the email manager that wrote the subject, wrote the email, and then an email arrived right here in my inbox. So all has worked well in the end.

So I went through that code very fast because it's something that we saw before yesterday, so hopefully it was somewhat familiar. The new angle was that we were calling multiple models, and it was very easy because they are all models which have OpenAI compatible endpoints. Now, you may have noticed that there is one model that was missing there in the form of Anthropic's Claude, and Anthropic does not offer an OpenAI compatible endpoint. And so I understand that there isn't, as of today, an easy way to use Anthropic's Claude in lieu of those other models that have an OpenAI compatible endpoint. But there are plenty of workarounds. So there is, for example, a third party provider called OpenRouter that probably a lot of people use, and it allows you to set up your keys for other models, including Anthropic's Claude. And it has an OpenAI compatible endpoint. So you can go through OpenRouter to use Claude. Also, Anthropic has the incredible MCP protocol, which we'll be talking about in the last week. And that gives us another route to be using Anthropic through MCP. So more will come on that later. In the meantime, the easiest way to do this is to use models other than Anthropic for this purpose. And perhaps quite soon Anthropic's Claude will be available through the OpenAI SDK direct.

Anyway, the next thing we're going to do is talk about both structured outputs and guardrails. We're going to do them together, and guardrails are ways that you can put a constraint around your agent platform. It's a test that you will do. And the cool thing about guardrails — I mean, you might think if guardrails were simply like a check of, like, checking that something has given the right kind of results, you could just write that in Python code. You can just obviously test whether the results have a certain property in them or not, and throw an exception if they don't. The special thing about guardrails here is that guardrails can themselves be agents, which means that you can use an LLM to be checking that things look good at any point in your flow.

Well, actually, that's not quite true. When I say at any point, guardrails actually can only be applied either to the input at the very beginning, the input of the first agent, or the output of the last agent. You can't insert guardrails all over the place. You just have them at the very beginning or the very end. And they're designed to protect your model against getting an input which is inappropriate or not what it's intended for. And also to protect it against producing an output which should not be shown to the user. So it's those two extremes. That's where you can implement guardrails. And we're going to implement an input guardrail right now. But as you'll see, it's basically exactly the same thing either way. And I'll leave a challenge for you to add an output one afterwards.

So the first thing I do, because we're going to be working with structured outputs, is I define a class called NameCheckOutput. We're going to be checking for names, for people's names, because we don't want people's names in our emails, we decided. So we're going to have a NameCheckOutput. And this is one of these pydantic objects. If you remember, this is where you have classes which are designed to reflect a particular schema of data. So what we want is that we want the NameCheckOutput to be something which has two fields: is_name_in_message, which is a boolean where true should mean that there is a name in this message, and name, a string, would be the name if there is a name in the message. Okay, so all we're doing here is we're defining a schema. We're saying this is a particular structure of class that we want to think of.

And now we're going to define an agent. And I'm naming it guardrail agent. You can name it whatever you want. We are going to use this in a guardrail. But this is, as of now, just another agent we're creating. Its name is going to be name check. The instructions are: check if the user is including someone's personal name in what they want you to do. The output type — this is the structured outputs piece. We are telling this agent we don't want you to output text, which is what you normally do by default. All of these are outputting just strings of data, but rather we want you to output a NameCheckOutput. We want you to output an object that conforms to this schema. And you can use this for any of your agents. So we could go back and use this as a way to structure our emails better. So we could use this so that rather than emails being just strings, they could actually already have a subject, a recipient, a body. We could do it that way from the get go. And that would be much nicer. And that is in the challenges at the end. But for here we specify the output type is NameCheckOutput. And as before we specify a model, GPT-4o-mini.

And that brings us simply to the guardrail. So a guardrail is — it's like an asynchronous, it's a coroutine. It's going to say a function, but it is of course strictly speaking a coroutine. And you simply decorate it with input_guardrail to say, I'm going to be using this as an input guardrail. It's a bit like decorating something to be a tool. And there's a completely analogous one called output_guardrail, which is what you would use if it was to be used as a guardrail for the output. You can call it whatever you want, and it takes the context — is a bunch of data that you can pass between agents that we haven't made use of — the agent itself, and this is the input, the input that's coming in. I've called it message.

And so what we can do right here is, as part of implementing this guardrail, we can actually kick off this guardrail agent. We can run this guardrail agent. And it will be giving it these instructions. It will be passing in the message, and it will be expecting a NameCheckOutput to come out of that. So this is basically going to do just what it says on the tin. It's going to check if someone's personal name is being included in the message.

And then you have to return — the rule about writing these guardrails is you have to return something called a GuardrailFunctionOutput. That's always a thing you return, which is informing the system whether or not there is a problem. And it has two things. Output info is just a dictionary of stuff that might be useful for tracing, and tripwire_triggered is a boolean. It's true if there's a problem. You pass in true here if something has happened which should trip the tripwire and alert that the guardrail has not been met and there is a problem.

So what we're doing here is we're saying if this agent that we just ran produced an object of type NameCheckOutput, if that has is_name_in_message set to true, which means that this agent reckons that there's someone's personal name in the instructions, then that should trigger the tripwire. That should cause this guardrail to fail. And there should be a problem. That's the key. That's how it works. I hope that makes sense. And you could use exactly this structure. And then of course, for output guardrails, it's pretty much the same thing. But instead of message you would put the output there. Otherwise exactly the same. All right, let's give this a try.

</details>

---
*Source: Official Udemy lecture transcript (auto-captions, lightly cleaned). Notes in Hinglish for self-study.*
