# L19 — Day 4: Using Gemini to Evaluate GPT-4 Responses

> **Week 1 — Foundations** · ⏱️ ~13m · 🎥 Lecture 19 of 131
> **Instructor:** Ed Donner · **Lecture ID:** 49771203

---

## 🎯 Ek Line Mein (TL;DR)

Is lecture mein hum **Evaluator-Optimizer pattern** ko bina kisi agentic framework ke implement karte hain — **GPT-4o-mini** answer deta hai, **Gemini** (via **structured outputs** + ek **Pydantic model**) us answer ko judge karta hai, aur agar answer reject ho jaye toh ek **rerun function** feedback ke saath GPT ko dobara try karwata hai.

---

## 📝 Hinglish Explanation (Detailed)

- **Aaj ka goal — Multi-LLM pipeline, framework-less:**
  - Ek LLM (GPT-4o-mini) answer dega, **doosra LLM (Gemini)** us answer ko **evaluate** karega.
  - Agar evaluation **fail** hui, toh hum GPT-4o-mini ko **dobara call** karenge (rerun) feedback ke saath.
  - Yeh poora workflow **bina kisi agentic framework ke** banega — sirf direct LLM calls se. Ed kehte hain ki yeh practice aapko in systems ke **internals** sikhati hai, aur yeh surprisingly simple hai.

- **Step 1 — Pydantic model for the evaluation:**
  - Ek class banayi `Evaluation` jo **`BaseModel` ko subclass** karti hai.
  - Do fields: **`is_acceptable: bool`** (answer theek hai ya nahi) aur **`feedback: str`** (kyun/kya improve karna hai).
  - **Pydantic** isliye use ho raha hai kyunki yeh ek clean mechanism deta hai **schema specify karne ka via classes** — yahi schema baad mein LLM ko diya jayega.
  - Side note: **Cursor** ne field names khud autocomplete kar diye — Ed mazak karte hain ki yeh "cheating" hai (shayad pehle ka deleted code ya neeche ke usage se infer kiya), mind-reading nahi.

- **Step 2 — Evaluator ka system prompt:**
  - Yeh exactly wahi **Agentic design pattern** hai — **Evaluator-Optimizer**.
  - System prompt: *"You are an evaluator that decides whether a response to a question is acceptable."*
  - Evaluator ko bataya jata hai ki agent ko **professional aur engaging** hone ka instruction diya gaya tha, aur agent ke paas jo **context** (LinkedIn/summary) tha — **wahi same context evaluator ko bhi diya jata hai**, taaki woh fairly judge kar sake.

- **Step 3 — Evaluator ka user prompt (function):**
  - `evaluator_user_prompt(reply, message, history)` — teen cheezein leta hai:
    - **`reply`** — jo answer evaluate karna hai
    - **`message`** — user ka original question
    - **`history`** — uske pehle ki conversation
  - Format: "Here's the conversation, here's the latest message from the user, here's the response from the agent. Please evaluate."
  - Ed ka advice: agar clear nahi hai toh **print statements daal ke khud try karo** — "it does exactly what it says on the tin."

- **Step 4 — `evaluate()` function with Structured Outputs (Gemini):**
  - Evaluation ke liye **Gemini 2.0 Flash** use ho raha hai — but yeh optional hai; aap normal OpenAI, **Ollama** (local), ya koi bhi model use kar sakte ho.
  - Key technique: **Structured Outputs** — ek tarika jisse aap LLM ko **force** kar sakte ho ki woh ek specific object/schema ke format mein respond kare.
  - API call normal chat completions jaisi hi hai, bas ek difference:
    - `gemini.beta.chat.completions.parse(...)` type call — model + messages ke saath aap **`response_format`** mein apna **Pydantic class (`Evaluation`)** pass karte ho.
  - **Behind the scenes reality:** LLM actually mein **JSON** return karta hai — client library us JSON ko parse karke aapke Pydantic object mein **populate** kar deti hai. Yeh ek aur "**conjuring trick**" hai (jaise tools the) — lagta hai code/object aa raha hai, but it's just JSON + parsing.
  - Function return karta hai ek populated **`Evaluation` instance** — `is_acceptable` + `feedback`.

- **Step 5 — Test run:**
  - Question: *"Do you hold a patent?"* → GPT-4o-mini ne sahi answer diya (Ed ke paas sach mein patent hai).
  - Phir `evaluate(reply, message, history)` call kiya → Gemini ne return kiya: `is_acceptable=True`, feedback: *"The response is acceptable — directly answers the question, provides context, invites further discussion."*
  - Moral: **simple LLM calls se hi yeh design patterns build ho jate hain** — koi heavy framework zaroori nahi.

- **Step 6 — `rerun()` function (the red feedback arrow):**
  - Agar Gemini bole "not acceptable", toh `rerun()` chalega:
    - Naya system prompt banta hai: *"The previous answer was rejected"* + **attempted answer** + **rejection ka reason** (Gemini ka feedback).
    - Phir GPT-4o-mini ko dobara call karke naya answer liya jata hai.
  - Yeh design diagram ka **bottom red feedback arrow** hai — evaluator se generator tak feedback loop.

- **Step 7 — Full workflow chat function:**
  - Naya beefier `chat()` clearly do sections mein hai:
    1. Pehle jaisa — **GPT-4o-mini ko call** karke reply lo.
    2. **`evaluate()` call** (Gemini, structured outputs) → agar `is_acceptable` toh reply return; **nahi toh `rerun()`**.
  - Test: "What is your current job?" → pass. "Do you have a patent?" → pass. Workflow kaam kar raha hai, console mein evaluation logs print ho rahe hain.

- **Step 8 — Sneaky Pig Latin sabotage (failure ko force karna):**
  - Chat function mein `system = system_prompt` wali line ka raaz khulta hai — yeh isliye thi taaki conditionally prompt modify kar sakein.
  - Hack: **agar message mein word "patent" hai**, toh system prompt mein add kar do: *"respond only and entirely in Pig Latin."*
  - **Pig Latin** = words ke chunks flip karke extra vowel sounds daalna — almost impossible to understand (Ed aur unki sister isse parents ko pagal karte the 😄).
  - **Gradio** UI launch kiya:
    - "What is your current role?" → normal answer, evaluation **passed**.
    - "Do you hold a patent?" → answer **Pig Latin mein aaya** → Gemini ne **reject** kiya: *"The agent is answering in Pig Latin, which is not professional."* → **rerun trigger hua** → final response normal English mein. 🎉
  - Silly example, but point proven: **evaluator galat output catch karta hai aur self-correction hoti hai.**

- **Closing thoughts:**
  - **Homework/insight:** Structured outputs aur **tools** ke beech ki **analogy** spot karo — dono closely related hain (dono mein LLM ko JSON schema diya jata hai aur woh structured JSON return karta hai).
  - Yeh technique **commercially bahut applicable** hai — Ed ne khud multiple business projects mein **LLM response validation** ke liye yahi use kiya hai.
  - Kal ke lab mein is project ko **finish + deploy** karenge (apne LinkedIn profile ke liye), us se pehle ek quick recap.

---

## 🔑 Key Concepts / Important Terms

| Term | Simple Hinglish Meaning |
|------|--------------------------|
| **Evaluator-Optimizer pattern** | Ek LLM generate kare, doosra LLM judge kare; fail hone par feedback ke saath retry — Anthropic ke 5 workflow patterns mein se ek |
| **Pydantic `BaseModel`** | Class-based schema definition — yahan `Evaluation(is_acceptable: bool, feedback: str)` |
| **Structured Outputs** | LLM ko force karna ki woh ek specific schema ke format mein respond kare; `.parse()` call mein `response_format` ke through Pydantic class pass hoti hai |
| **JSON behind the scenes** | LLM object nahi, JSON bhejta hai — client library use parse karke Pydantic object populate karti hai (ek aur "conjuring trick") |
| **`evaluate()`** | Reply + original message + history leke Gemini se populated `Evaluation` object return karne wala function |
| **`rerun()`** | Rejection par naya system prompt (rejected answer + reason) banakar GPT-4o-mini ko dobara call karna — diagram ka red feedback arrow |
| **Multi-LLM pipeline** | Alag-alag providers (GPT-4o-mini generator, Gemini 2.0 Flash evaluator) ek workflow mein — vendor lock-in nahi |
| **Pig Latin test** | Jaan-bujhkar broken output force karke evaluator ka rejection + retry path test karna |
| **Framework-less** | Koi agentic framework nahi — sirf vanilla Python + direct LLM API calls se poora workflow |

---

## 💡 Backend Dev Ke Liye Note (aapke liye)

- **Structured outputs = response_model pattern of FastAPI, ulta direction mein.** FastAPI mein aap Pydantic se *apna* response validate karte ho; yahan aap LLM ko schema dekar *uska* output validate/parse karwate ho. `.parse()` call internally JSON Schema bhejti hai aur JSON response ko `Evaluation` mein deserialize karti hai — bilkul `Model.model_validate_json()` jaisa.
- **Yeh basically ek retry-with-feedback middleware hai.** Socho jaise API gateway pe response validation: response → validator → fail hone par enriched request (original + failure reason) ke saath ek retry. Difference sirf yeh ki validator deterministic code nahi, ek aur LLM hai — isliye "LLM-as-judge" bhi kehte hain.
- **Cross-provider evaluation ek smart architecture choice hai** — generator aur evaluator alag models hone se correlated failures/biases kam hote hain. Jaise prod mein independent health-checker service deploy karna, app ke self-reporting pe bharosa karne ke bajaye.
- **Homework hint (tools vs structured outputs):** dono mein aap LLM ko JSON Schema dete ho aur woh schema-conformant JSON return karta hai. Tools = "yeh JSON banao taaki main function call karun"; structured outputs = "yeh JSON banao taaki main object banaun." Same mechanism, alag intent — yeh samajhna agentic frameworks ke internals decode karne ki key hai.

---

## 🧠 Takeaway (yaad rakho)

1. **Evaluator-Optimizer workflow plain Python + LLM calls se ban jata hai** — generator (GPT-4o-mini) → evaluator (Gemini) → fail par rerun with feedback. Koi framework nahi chahiye.
2. **Structured outputs** = Pydantic class ko `response_format` mein pass karo, LLM JSON return karega, library object populate karegi — guaranteed parseable output.
3. **Rerun ka secret sauce feedback hai** — sirf retry nahi, balki "yeh answer reject hua, yeh reason tha" system prompt mein dalke retry, tabhi second attempt better hota hai.
4. **Failure path ko deliberately test karo** (Pig Latin trick) — evaluator tabhi valuable hai jab woh actually reject karke loop trigger kare.
5. **Structured outputs aur tools sage-bhai hain** — dono LLM se schema-conformant JSON nikalwane ke conjuring tricks hain. Yeh technique production/business projects mein LLM response validation ke liye directly use hoti hai.

---

<details>
<summary>📜 Full English Transcript (original, click to expand)</summary>

Okay, hold on to your hat. It's about to get real. We're going to do a whole lot. So what we're about to do, we are going to be able to ask another LLM to evaluate the answer that comes back from this LLM, from GPT-4o-mini. If the answer fails the evaluation, we're going to be able to rerun and make a second call to GPT-4o-mini. And we're going to put all of this together in one workflow. And we're going to do that without an agentic framework. We're doing it the framework-less way, just by directly calling LLMs. Okay. Let's see if we can make this work now. It's a great practice because this is going to really teach you the internals of how these things work. And it's super simple. It sort of works exactly as you might expect.

So the first thing we're going to do is create something called a Pydantic model. And this might be something that you know well, if you're an engineer, but you might not. Pydantic is something which is a framework for specifying a schema using classes. You use a class to describe a particular structure, data structure of information. And the way it works is that there's a class called BaseModel that you need to subclass from. So we make a new class called Evaluation, and it's going to be a subclass of BaseModel, and Cursor builds it all in for me — takes away all the fun. We do indeed want this to have two fields: one field called is_acceptable, is a bool, a true or false, and another called feedback, which is string. Now you might wonder how on earth, how is it possible that Cursor knew the exact names of the fields that I wanted to use? And I suspect it's because I did have that code in there before I deleted it, because I have, of course, run this in advance. Or it may be because it sees that later on in this code I use it, and so it's filling it in. So it's cheating in some way. It can't read my mind. But it has done very well. So anyways, we have a class called Evaluation. It has these two fields. And we're using Pydantic because it gives us this mechanism for specifying a class structure like this.

Okay, so we're now going to set up a system prompt for our evaluator. So we're now following that design pattern, the agentic design pattern where we have an evaluator-optimizer. So the evaluator system prompt: you are an evaluator that decides whether a response to a question is acceptable. You're provided with a conversation and you have to decide whether the latest response is acceptable. So I say the agent has been instructed to be professional, engaging. The agent has been provided with context. And then we give the evaluator the same context and we tell it to evaluate. So let's run that. So that this is just a variable called system prompt.

I've now got a function called user prompt. It's going to take a reply to be evaluated, a message — the original message that the reply was replying to — and history before it. And it says: here's the conversation, here's the latest message from the user, and here's the response from the agent. Please evaluate. Hopefully that makes complete sense. You should try it out if you're not sure. Put in some print statements. Try it out. This does exactly what it says on the tin.

Okay, we're going to use Gemini to be doing our evaluation. And you don't need to use Gemini. You can just simply replace this with the normal OpenAI or with Ollama if you want to run locally, or anything of your choice. But I'm choosing Gemini here. And now I have this function evaluate. So evaluate will take a reply from the LLM, the original message it was replying to, and the history. And it will return one of these objects, one of these beasts, these things right here that we've just defined. And how's it going to do that? It uses a technique called structured outputs, which is a way that you can require an LLM to respond in a form of an object like this. It's just JSON behind the scenes, of course. So the way that you do that, the way that this looks, it's very similar to the normal chat completions API, but there is a difference. So we start by building the messages as always — a system message and a user prompt. And then we say gemini-dot-dot-dot — that's the way that you call an API to use structured outputs. We pass in the model — we're going to use Gemini 2.0 Flash — the messages, and you also specify the object that you want to be populated. You're giving it a schema, a Pydantic object. And you're saying I want you to respond with this object. Now of course, it's not actually responding with an object. It's going to respond with JSON. And the client library is going to take that JSON and use it to populate the object. So it gives you the impression that you're getting code back from the LLM. But that's another of these conjuring tricks. All right. And we're going to return the response message — that is going to be an instance of Evaluation populated with the response from the LLM. I know I've gone through a lot. If you're not following, just come back. Go through this step by step. Try it for yourself. Okay. So let's run that.

All right. So now we're actually going to give this a try. So we're going to ask the original LLM, GPT-4o. We're going to ask the question: do you hold a patent? We're going to ask it that question, and we're going to call GPT-4o-mini as before and return the reply. And let's see what it says. Here's the reply: Yes, I hold a patent for blah blah blah blah blah — which is true, I do hold that patent with several others. And what we're now going to do is we're going to call the evaluate function. We're going to call the evaluate function with that reply, tell it the question — do you hold a patent — and pass in the history. So this is now going to call Gemini. It's going to ask it to build an evaluator object to represent whether or not this is a good answer. And we'll run that. We get back an Evaluation object. So it works: is_acceptable is true. The feedback is: the response is acceptable, it directly answers the question, provides context and invites further discussion. So a clear, quick evaluation from Gemini. And hopefully you see how just simply calling LLMs is an easy way to build these kinds of design patterns.

All right. So number one, we built a function that calls GPT-4o-mini to answer questions. Number two, we built an evaluator function that calls Gemini to check the answer that came before in number one and respond with an evaluator object populated. And that appears to be working. So the final piece of the puzzle is to write a function rerun, that if Gemini comes back and says no, that's not acceptable, rerun has to be able to go and do that, do a rerun. So we build a new system prompt that says the previous answer was rejected, and we give the attempted answer and the reason for the rejection. And then we build the history as before, and we get back an answer and we try it again. So this is simply calling GPT-4o-mini and providing the results of Gemini's evaluation if it fails validation. And this, if you remember that design diagram, it's like the bottom arrow, the red feedback arrow in that diagram — making sure that we can rerun the original question.

All right. And with all of that together, we now have a slightly longer chat function. This is the full workflow now coded, written as just vanilla code calling LLMs. And you can see that it's very clearly in two sections. First of all, this is the same as the previous chat function — we simply call an LLM. We call GPT-4o-mini with our question. Then we call evaluate — extra line there — then we call evaluate to evaluate it. And you know that this is going to call Gemini with structured outputs. And then we look at this evaluation: is it acceptable? If so, all is good. If it's not acceptable, we rerun, and we call the rerun method that we just wrote there — function, okay. So that is our new beefier chat. So let's give this a whirl. Let's give it a try. Okay, I'm going to say: what is your current job? It's thinking about that. And there's the response. And down here you can see I have it printing that the evaluation happened and Gemini was satisfied. Do you have a patent? And that was the reply. And Gemini was satisfied with that reply. So, so far, so good. This seems to be working.

Now we'll try shaking things up. Okay. Now just to be sneaky, we're going to come back to this chat function here. And you see up here I have this slightly dodgy looking system equals system prompt. You might have wondered what that was about. Well, it's so that I could put in something here. So let's say if the word patent is in the message — so if the message has the word patent in it, it's something to do with the patent — then (Cursor is going a bit all over the place here) then system equals system prompt plus... So we're going to tell it in that case that it needs — let's make this really strongly worded — everything in your reply needs to be in Pig Latin. In it is... that you respond only and entirely in Pig Latin. Hang on. I can't see what's going on here. Let's do this. Perfect. Our system equals system prompt. Exactly. So basically, if any question comes in with the word patent in it, then we are going to add on an instruction that everything in the reply needs to be in Pig Latin. You may wonder what Pig Latin is. Pig Latin is what you call it when you mess around words — you flip the order of the chunks of the words and insert extra vowel sounds in it, and it makes it almost impossible to understand. My sister and I used to be really great at speaking quickly in Pig Latin to each other, and it used to drive my parents crazy. So, anyway, it would probably drive a future employer crazy too. And so hopefully our evaluator will reject a response that's in Pig Latin.

So that is our new chat function. And with that, let's start a Gradio user interface. And let's say: what is your current role? And get back an answer that will hopefully be a very decent answer. There we go. Passed an evaluation? I should hope so. Do you hold a patent? And we're asking if it holds a patent. We'll see what happens. This response is not acceptable. The agent is answering in Pig Latin, which is not professional. It failed evaluation. It retried. And the final response that we got is no longer in Pig Latin. So it's a silly example, but I did want to show you that we can force it to do this. And I wanted to show you our workflow at work.

I know that a lot happened. If you've already experienced structured outputs and you know about them, then this hopefully all made complete sense. And I'd like you to use this as an opportunity to see the analogy between using structured outputs with using tools — they are actually closely related to each other. See if you can spot that and understand that. If you're new to structured outputs and I went through a lot here, then I urge you to come back, step through this, put in print statements, understand what's going on, and see how we were just able to build a workflow which was very much an evaluator-optimizer workflow. And we were able to use structured outputs as a way of communicating with the evaluator. And this is a kind of technique that you can absolutely use in any business project as a way of validating the response from the LLM. And indeed, I've used it myself in multiple business projects using this kind of technique, so very much applicable commercially. And obviously this whole project is applicable commercially because you can use it for your own LinkedIn profile. And coming up in tomorrow's lab, we're actually going to do just that. We're going to sort of finish the job off and have it so you will be able to deploy it. Before that, let's just go and do a quick recap.

</details>

---
*Source: Official Udemy lecture transcript (auto-captions, lightly cleaned). Notes in Hinglish for self-study.*
