# L82 — Day 4: LLM Evaluator Agents — Feedback Loops

> **Week 4 — LangGraph** · ⏱️ ~9m · 🎥 Lecture 82 of 131
> **Instructor:** Ed Donner · **Lecture ID:** 49821381

---

## 🎯 Ek Line Mein (TL;DR)

Aaj **worker-evaluator pattern** shuru hota hai — ek **worker LLM** (assistant) kaam karta hai aur ek alag **evaluator LLM** (`with_structured_output` + Pydantic schema se) decide karta hai ki answer **success criteria** meet karta hai ya **feedback** ke saath wapas worker ke paas jaye — yahi **feedback loop** kal ke Sidekick project ki foundation hai.

---

## 📝 Hinglish Explanation (Detailed)

- **Context — do labs ek din me**: Week 4, Day 4, lab 4 (Cursor me). Ye kal ke **big project "Sidekick"** ki tayari hai. Aaj ke do naye topics: **structured outputs** aur ek **multi-agent flow** (worker + evaluator).
- **Structured outputs — step 1: schema define karo**:
  - Pehla step hamesha wahi — ek **Pydantic class** jo describe kare ki LLM se **kaisa result wapas aana chahiye**. Yahan wo class hai **`EvaluatorOutput`**.
  - Evaluator actually **JSON** return karega, aur wo JSON is schema pe **conform** karega. Teen fields:
    - **`feedback`** — assistant ke response par feedback (string).
    - **`success_criteria_met`** — success criteria meet hua ya nahi (bool).
    - **`user_input_needed`** — `True` agar user se aur input/clarification chahiye, **ya assistant stuck hai**.
- **Evaluator ka role kya hai**:
  - Ek aisa LLM jo decide karta hai ki **worker (assistant) ka answer achha hai ya nahi** — kya ise **user ko forward** karna theek hai, ya **wapas assistant ke paas** bhejna chahiye more work ke liye.
  - **Do situations me flow user ke paas lautta hai**: (1) success criteria met — kaam ho gaya, ya (2) worker **stuck** hai / clarification chahiye — tab bhi user ke paas wapas jana chahiye.
- **State — pehli baar "meaty" state**:
  - Reminder: state **koi bhi Python object** ho sakta hai — Pydantic object bhi — lekin aksar **`TypedDict`** use karte hain, aur yahan wahi hai.
  - Ab tak state me sirf `messages` hota tha; ab **real information** bhi hai jo evaluator se worker tak pass hogi:
    - **`messages`** — user-assistant discussion (as usual).
    - **`success_criteria`** — **upfront set** hota hai: "successful hone ka matlab kya hai" ye define karta hai.
    - **`feedback_on_work`** — evaluator ka feedback worker ke kaam par. **`Optional`** hai — matlab `None` ho sakta hai ya string (nullable field ka type-hint pattern).
    - **`success_criteria_met`** — bool; `True` matlab successful outcome, worker ke paas wapas jane ki zaroorat nahi.
    - **`user_input_needed`** — bool; `True` matlab user se aur info chahiye.
  - Lesson: **state poori tarah aapke logic ke hisaab se design hota hai** — wo cheez hai jo graph me move karti hai, aur **har node ko state milta hai + naya state return karne ka mauka**.
- **Reducer semantics — accumulate vs overwrite (important!)**:
  - Sirf **ek reducer** specify hua hai: **`add_messages`** on `messages` — koi node messages return kare to wo **purani list me concatenate/accumulate** honge.
  - Baaki sab fields (jaise `user_input_needed`) par **koi reducer nahi** — node ne return kiya to wo value **old state ko overwrite** kar deti hai, aur **downstream nodes ko nayi value milti hai**.
- **Playwright tools setup**: same code as before — **async browser** + **Playwright Browser Toolkit**. (Hamare labs me ye skip hai — niche dekho.)
- **Do LLMs initialize hote hain — yahi multi-agent ka core**:
  - **Worker LLM** — assistant ka role; **GPT-4o-mini**, jo **`bind_tools`** se tools ke saath bound hai (tools ka JSON automatically handle).
  - **Evaluator LLM** — bilkul **alag LLM**; is baar `bind_tools` nahi balki **`with_structured_output(EvaluatorOutput)`** — response guaranteed schema-conform hoga.
- **Structured output sab models support nahi karte — fallback**:
  - Agar model structured output support nahi karta, to **old-fashioned way**: prompt me bolo "JSON me respond karo", **schema list karo**, **couple of examples do** (bias karne ke liye), aur phir **response ka JSON khud parse karo**.
  - Ed ka point: **behind the scenes structured outputs yahi karta hai** — bas framework abstract kar deta hai. Congratulations — LangGraph ke saath structured outputs itna hi simple hai.
- **Worker node (`def worker`) — lamba sirf prompting ki wajah se**:
  - Normal node hi hai: **state leta hai, state return karta hai** — `messages` return karta hai jo reducer ki wajah se accumulate hote hain.
  - **System message** ka gist: "You're a helpful assistant that can use tools. **Task par kaam karte raho** jab tak ya to user ke liye question/clarification ho, ya **success criteria met** ho" — aur success criteria **state se aata hai**.
  - Reply rules: **ya clearly-stated question, ya final answer** — aur agar finish ho gaya to **sirf answer do, question mat poochho**. Kyun? Kyunki models ko "Can I help you with anything else?" type endings ki aadat hai, jo **evaluator ko confuse** kar sakti hai (use lagega help chahiye).
  - Ed ka meta-point: **prompting = experimentation/R&D** — koi hard and fast rule nahi; usne ye prompt ghanton craft kiya hai, aur different models/assignments ke liye **tweak** karna padega.
- **Feedback loop ka prompt-side**:
  - Agar state me **`feedback_on_work`** bhara hai → matlab evaluation ho chuki hai aur **fail** hui — kaam wapas aaya hai.
  - Tab system message me add hota hai: *"Previously you thought you completed the assignment, but your reply was **rejected** because the success criteria was not met. Here is the **feedback**... please **continue the assignment** ensuring you meet the success criteria."* — pura loop prompt me spelled out.
- **Thoda "hokey" code — system message handling**:
  - Code check karta hai ki messages me **already koi system message hai ya nahi** — hai to **replace** karta hai naye se, nahi hai to **front me insert** karta hai.
  - Careful rehna padta hai kyunki **LangGraph shayad pehle se system message bana chuka ho** — different models ke saath **testing** worth it hai.
- **End of node**: `worker_llm_with_tools.invoke(messages)` → response milta hai → wahi return. Aur phir teaser: ab aata hai kuch interesting — **worker router** (agla part).

---

## 🔑 Key Concepts / Important Terms

| Term | Simple Hinglish Meaning |
|------|--------------------------|
| **Worker (assistant)** | Wo LLM jo actual kaam karta hai — tools ke saath bound, task complete karne ki koshish |
| **Evaluator** | Doosra LLM jo worker ke answer ko judge karta hai — user ko bhejna ok hai ya wapas worker ko |
| **`EvaluatorOutput`** | Pydantic schema jo evaluator ke JSON response ka shape fix karta hai (feedback, success_criteria_met, user_input_needed) |
| **`with_structured_output()`** | `bind_tools` ka structured-output bhai — LLM ko Pydantic object do, response schema-conform JSON me aayega |
| **Structured output fallback** | Model support na kare to: prompt me JSON schema + examples do, response khud parse karo — behind the scenes yahi hota hai |
| **Meaty state** | `messages` ke alawa real business fields — success_criteria, feedback_on_work, success_criteria_met, user_input_needed |
| **`success_criteria`** | Upfront defined — "is task me success ka matlab kya hai"; worker ke prompt me jata hai |
| **`Optional[str]`** | Field jo `None` ya string ho sakta hai — nullable type hint (feedback_on_work aisa hai) |
| **Accumulate vs overwrite** | Sirf `messages` pe `add_messages` reducer = append; baaki fields node return kare to **overwrite** ho jate hain |
| **Feedback loop** | Evaluator reject kare → feedback state me → worker ke system prompt me "rejected because..." add hota hai → worker dobara try karta hai |
| **Worker router** | Agla piece (next lecture) — worker ke baad flow kahan jaye, ye decide karne wala routing |
| **Sidekick** | Kal ka Week 4 ka big project — ye lab uski direct tayari hai |

---

## 💡 Backend Dev Ke Liye Note (aapke liye)

- **Worker-evaluator = maker-checker / PR review loop**: worker ka output ek PR hai, evaluator reviewer — approve (criteria met) ya "changes requested" with comments (`feedback_on_work`), aur worker rebased retry karta hai. Fintech wale **maker-checker** pattern jaisa hi hai — ek hi actor ko self-approve mat karne do; alag LLM se judge karwao.
- **Reducer vs overwrite = event log vs last-write-wins register**: `messages` append-only event log hai (`add_messages` reducer — event sourcing style), jabki `success_criteria_met` jaise scalars **LWW** hain — jo node last me return kare wahi value downstream dikhti hai. Yahi mental model rakho ki state me kya accumulate hota hai aur kya replace.
- **`with_structured_output` = `instructor`/`response_model` pattern**: ORM jaise SQL chhupata hai, waise hi ye "respond in JSON + parse + validate" boilerplate chhupata hai. Ed ka fallback (schema in prompt + manual parse) wahi hai jo aap kisi flaky third-party API ke liye Marshmallow/Pydantic validation layer me karte ho — abstraction toote to ye manual path yaad rakho.
- **Hands-on lab**: is lecture ka code khud chalane ke liye **`Practical/lab3_worker_evaluator.py`** run karo (is repo me, `uv run` se chalta hai, **Groq pe free** via `langchain-groq` `ChatGroq`). Ek difference: lecture me **Playwright browser tools** hain jo hum SKIP karte hain (heavy dep) — sidekick lab me uski jagah **safe sandbox file/python tools** hain; worker-evaluator concepts bilkul same.

---

## 🧠 Takeaway (yaad rakho)

1. **Structured outputs LangGraph me = `with_structured_output(PydanticClass)`** — jaise tools ke liye `bind_tools`, waise output shape ke liye ye; model support na kare to prompt-me-schema + manual JSON parse wala fallback.
2. **Evaluator ek alag LLM hai** jo worker ke answer ko 3 dimensions pe judge karta hai: feedback, criteria met?, user input needed?
3. **State aapke logic ka design hai** — `messages` ke saath success_criteria, feedback, flags sab daal sakte ho; sirf `messages` accumulate hota hai (reducer), baaki **overwrite**.
4. **Feedback loop prompt ke through close hota hai** — rejected work ka feedback worker ke system message me inject hota hai ("rejected because... continue ensuring criteria met").
5. Prompt me explicit raho ("question hai to clearly bolo, done ho to sirf answer do") — warna polite filler ("anything else?") **evaluator ko confuse** karta hai. Prompting = R&D, tweak karte raho.

---

<details>
<summary>📜 Full English Transcript (original, click to expand)</summary>

And so here we are back in Cursor to go to lab four. Because this is a day when we do two labs in one day. Week four, day four preparing for tomorrow's big project, which is called the Sidekick. And it's time to introduce structured outputs and a multi-agent flow. So we've got a bunch of imports and we are going to set our dot env as usual.

And now we're going to be using structured outputs. And you'll remember the first step with structured outputs is to define the schema. What are we using to describe the results that must come back from an LLM. And in particular, the thing that we're going to be working on is an evaluator, something which is going to decide whether or not an answer from an LLM is good. And so our evaluator is going to respond using this object an EvaluatorOutput. Or really it's going to respond with JSON. And the JSON is going to have to conform to this. So we just describe what this means. There's going to be a field feedback which is going to be feedback on the assistant's response. Success criteria is whether the success criteria has been met and user input needed. True. If more input is needed from the user or clarifications, or if the assistant is stuck. So this is going to allow we're going to have an evaluator that's going to evaluate the results of our worker, the assistant, to use their terminology. And it's going to decide whether it's okay to forward that back to the user, or whether it needs to go back to the assistant for more work. And one situation is if the success criteria are met and it's done its job. But another situation is if the worker seems to be stuck or needs clarifications, in which case it should return. So there we go.

Um, okay. And now to manage state. You remember with state it can really be any Python object. It can be a Pydantic object. But we often use typed dicts. And that's what we're doing here. And now for the first time, we have some real meaty information to store in the state. We've always had messages before, but now we have a real state and we've got a bunch of things. We do still have messages, which is representing the discussion between the user and the assistant, but we've got other stuff which is going to represent the information being passed from the the evaluator. Back to the thing. I'm going to call the worker, the assistant. Um, and so we're going to have some more stuff. We're going to have success criteria, which is going to be set up front to define what does it mean to be successful, feedback on the work that's going to come from the the worker. And by the way, you use optional like this. If this can be null, it can be none or it can be a string. Success criteria met is a bool is true or false and is going to be true if the if there has been a successful outcome that the criteria met and the the, it doesn't need to go back to the worker for more. And user input needed is if we need to go back to the user to get some more information. So that is our state. So it's a much meatier state. And this shows you that you can have whatever you want in the state. The state is really up to you and the flow of your logic. And that state is like something that has moved through the graph and everyone gets their opportunity. Every node gets the state and gets its opportunity to to return a new state. That is some change to that state.

And we're only specifying one reducer add messages, which means that if one of these nodes returns with some messages, they will get accumulated. They will get concatenated with the existing messages. But if one of these nodes returns user input needed, that will overwrite whatever was in the old state. So when you return the new state, if you change one of these values here, that becomes the new setting for anything that is downstream of you in the graph.

Okay. So next up we set up our Playwright tools. This is the same code as before using the async browser, the Playwright browser and the Playwright Browser toolkit. So we just run that. That's pretty simple.

And now we're going to have two LLMs that we're going to initialize. One of them is called the worker LLM. It plays the role of the assistant. It's going to be GPT-4o-mini. And it's going to be bound to those tools so that it will automatically have the JSON gumpf in it. And then separately we're going to have an evaluator LLM. This is a separate LLM. And it is we're setting it up. Whereas before we said bind tools. And now we say with structured output and pass in the Pydantic object. And that means that the response will conform to this output. Now not all models are set up to support structured output. So you may find that some models can't do it if you're if you're going to be playing around with different models. If that is the case, of course, the alternative to this is to do it the old fashioned way, which means instead of using structured outputs like this and passing a pydantic object, you ask the model in the prompt to respond in JSON. You give it the schema. You give, you list out what kind of JSON it should respond in. You maybe give a couple of examples to make sure that it's really biased to do well, and then you have to parse that JSON in the response. And that's all that is happening behind the scenes when we do structured outputs like this. So that means you congratulations. You now learn how to do structured outputs with LangGraph. It's that simple.

Okay. So this is a bit of a long looking uh, function. This node, the def worker which is representing our worker node, our assistant. But it's only long because we've got a lot of prompting in here. So it's a node. And so as usual it takes a state and it's going to return a state. And you can see it's returning something with messages. And we know that messages accumulates because we have the reducer. So that is going to add on more messages. Okay. So we've got like a long system message. Let me talk you through it. We say look you're a helpful assistant that can use tools to complete tasks. You keep working on a task until either you have a question or clarification for the user, or the success criteria has been met. And this is the success criteria, and we take it from the state. It's something that should be held in the state. You should reply either with a question for the user about the assignment or with your final response. If you have a question for the user, you need to reply by clearly stating your question. An example might be this. It's not super necessary for me to have done that, but I wanted to make it really clear that it will say when it has a question and sort of force, force the point. If you finished reply with the final answer and don't ask a question, simply reply with the answer. And I say that because these models love to reply with things like can I help you with anything else? And that then might confuse our evaluator that's looking to see if it needs help. So I want it to be super clear on this front. Okay. And of course all these things are subject for experimentation. There's no hard and fast rules. It's not like that is a as a rule that you have to put this in the prompt. I hope you know this by now. This is this is really the the the part of AI engineering that is about experimentation, R&D. You can imagine I've been crafting this prompt for the last couple of hours. So it's something that obviously you hone in on something that works well. And you may find that particularly with different models or if you have different assignments, it's something that you have to tweak to get the kind of performance you want anyways.

Uh, if, if we've got in our state something in this, in this field feedback on work, then that means that an evaluation has happened and it's not gone well. There's been feedback and it's come back for more. So then we add to the system message. Previously you thought you completed the assignment, but your reply was rejected because the success criteria was not met. Here is the feedback on why this was rejected. And then we give the feedback. And then with this feedback please continue the assignment ensuring you meet the success criteria. Uh so there it is spelled out in detail.

Um, okay. And then I've got here some, some slightly hokey code that that looks to see whether there's already a system message inside there. And if there already is, then it just replaces whatever system message is there with this system message. If it doesn't find a system message, then, uh, it, uh, it creates a new one and puts it at the front. So this is, this is just to make sure that we handle those various scenarios. Now, this is a little bit hokey because, uh, LangGraph will have already perhaps have built a system message. So, so we have to be a bit careful about this, and it might be worth doing some testing to make sure that it works for different models.

Okay. So at the end of all that we then call worker LLM with tools and we invoke the messages. We get back a response and that is what we then return. So there we have it. Uh, okay. Now we now have something pretty interesting called the worker router.

</details>

---
*Source: Official Udemy lecture transcript (auto-captions, lightly cleaned). Notes in Hinglish for self-study.*
