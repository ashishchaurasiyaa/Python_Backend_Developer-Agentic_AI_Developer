# L84 — Day 4: Building an AI Sidekick

> **Week 4 — LangGraph** · ⏱️ ~9m · 🎥 Lecture 84 of 131
> **Instructor:** Ed Donner · **Lecture ID:** 49821409

---

## 🎯 Ek Line Mein (TL;DR)

**Sidekick** ka final demo — **Gradio UI** se ek **worker–evaluator graph** ko `ainvoke` karte hain (har session ka apna **thread_id**), worker **Playwright tools** se browser drive karke USD→GBP rate nikaalta hai, aur **LangSmith trace** me poora flow (worker → tools → evaluator → routing) dikhta hai.

---

## 📝 Hinglish Explanation (Detailed)

- **Gradio callback se super-step kick-off**: UI me button press hote hi ek **callback** chalta hai jo graph ka ek **super-step** start karta hai. Yani UI event → graph invocation, simple wiring.

- **Random thread_id per session**: Ed ek "cheeky" trick use karte hain — har baar interface load hone par ek **random bada unique number** generate hota hai as **thread_id**. Kyun?
  - Taaki har Gradio session ka apna **separate thread** ho — pichli conversation se continue na ho (warna cheezein "hectic" ho jaati).
  - Bonus: **multiple users** ek saath interface use kar sakte hain, sabki **alag-alag conversations** — kyunki checkpointer thread_id ke hisaab se state alag rakhta hai. Sidekick sirf single-user tool nahi raha.

- **`process_message` — async coroutine**: Ye main handler hai. Steps:
  1. **Config banao** thread_id se (`{"configurable": {"thread_id": ...}}` pattern).
  2. **Initial state set karo**:
     - `messages` ← user ka message,
     - `success_criteria` ← user ne UI me jo success definition di,
     - `feedback_on_work` ← evaluator ke liye (evaluator hi ise set karega),
     - `success_criteria_met` = **False** (start me),
     - `user_input_needed` = **False** (start me).
  3. **`graph.ainvoke(state, config)`** call karo aur result ka `await` karo.

- **State poore graph se travel karti hai**: Yahi state worker, tools, evaluator — sab nodes se hokar guzarti hai. Evaluator hi `success_criteria_met` flip kar sakta hai.

- **Gradio UI ke liye result packaging**: ainvoke ke result se:
  - User ka message package hota hai,
  - **Second-last message** = assistant ka reply,
  - **Last message** = **evaluator ka evaluation** — dono UI me dikhte hain (evaluation dikhana optional hai, hata bhi sakte ho).

- **Ek honest confession**: yahan **Gradio ki history** aur **LangGraph ki memory wali history** dono mix ho rahi hain. Zyada elegant hota agar state se **full history unpack** karte, par wo messy ho jaata — so "keep it simple", ye fine hai.

- **`reset` callback**: ek chhota callback jo bas interface reset kar deta hai.

- **Live demo — exchange rate**: Question: *"What is the current USD/GBP exchange rate?"*, Success criteria: *"An accurate answer"*. Go dabate hi:
  - **Browser window khud khul gaya** (Playwright tools worker ko diye gaye hain),
  - Worker ne amount "1" daala, rate dhoondha — pehle galti se **EUR default** tha (quirky!), par scroll karke usne **USD→GBP = 0.77463** sahi nikaal liya.
  - Assistant ka answer wahi number — **browser drive karke real info** laaya.

- **Evaluator ka stern feedback**: Evaluator (doosra agent) ne kaha — answer approximate hai, assistant ko note karna chahiye tha ki rate change ho sakta hai. Phir bhi usne **control user ko return** karna choose kiya. Yani evaluator strict bhi hai aur routing decision bhi leta hai.

- **LangSmith trace — andar kya hua**: Poora run **19,000 tokens, ~0.2 cent** (fifth of a cent!) me hua. Trace me dikhta hai:
  - **Worker** ne tools call kiye: `navigate_browser`, `extract_text`, `get_elements` — yahi se wo browser navigate kar raha tha,
  - Worker ↔ tools ka loop kai baar chala,
  - End me **evaluator** call hua — exactly jaisa design tha.

- **Evaluator ko bheja gaya exact message** (LangSmith me ChatOpenAI tak drill-down karke):
  - **System**: "You're an evaluator, determine if task completed successfully, assess assistant's last response based on criteria…"
  - **Human**: poori conversation (wo **utility function** jo `User:/Assistant:` format me history banata hai, **tool calls ko "Tools use" likh ke** clear karta hai), plus success criteria (seedha Gradio UI se), plus final response.
  - Reply: **JSON** jo **structured outputs schema** se conform karta hai — isi liye LangChain use parse karke Pydantic object populate kar paata hai, aur graph ko wahi return milta hai. Phir **route based on evaluation** END tak le jaata hai.

- **Prompt iteration ka sach**: Ed ke early prompts itne ache nahi the — kabhi-kabhi worker–evaluator ke beech **25 messages** ka ping-pong hota tha hard tasks pe. **Prompts improve karna** is loop ko tighten karne ka main lever hai.

- **Big picture — "humne apna Operator bana liya"**: Playwright dekar ye agent **OpenAI ke Operator** jaisa, ya **Manus**-type agent jaisa feel hota hai — aur banana itna easy tha. Bigger tasks try karo: websites summarize karwana, navigate karwana, etc.

- **Wrap-up**: Aaj bahut kuch cover hua — graph visual, worker–evaluator back-and-forth, Playwright operation. Ed ab khud ko **LangGraph advocate / true believer** kehte hain. Kal isi ko ek **packaged project** banayenge with more features.

---

## 🔑 Key Concepts / Important Terms

| Term | Simple Hinglish Meaning |
|------|--------------------------|
| **Gradio callback** | UI button press par chalne wala function jo graph ka super-step kick off karta hai |
| **Random thread_id** | Har session ke liye unique bada number — alag conversation, alag checkpoint history; multi-user support free me |
| **`ainvoke(state, config)`** | Graph ko async run karna — initial state + thread config pass karke result await karna |
| **Initial state** | `messages`, `success_criteria`, `feedback_on_work`, `success_criteria_met=False`, `user_input_needed=False` |
| **success_criteria** | User-defined "kya hua to task successful" — evaluator isi ke against judge karta hai |
| **Evaluator feedback** | Doosre agent ka structured JSON verdict — feedback + met/not-met + user input needed flags |
| **Structured outputs schema** | Pydantic schema jisse evaluator ka JSON guaranteed parse hota hai aur object populate hota hai |
| **Playwright tools** | `navigate_browser`, `extract_text`, `get_elements` — worker inse real browser drive karta hai |
| **LangSmith trace** | Run ka full X-ray: kaunsa node chala, kaunse tools, exact prompts, tokens (19k = ~0.2¢) |
| **Route based on evaluation** | Conditional edge — evaluator ke verdict par worker pe wapas ya END pe |
| **Operator-like agent** | Browser chalane wala autonomous agent — OpenAI Operator / Manus jaisa, par khud ka bana hua |

---

## 💡 Backend Dev Ke Liye Note (aapke liye)

- **Random thread_id = session isolation, bilkul HTTP session cookie jaisa.** Checkpointer ek multi-tenant store hai jo thread_id se partition hota hai — same pattern jaise aap Redis me `session:{uuid}` keys rakhte ho. Naya UUID = fresh conversation; purana UUID reuse = resume. Multi-user concurrency free me mil gayi, koi locking code nahi.
- **Gradio history vs LangGraph memory — dual source of truth ka classic smell.** Ed khud maante hain ki elegant approach hoti checkpointed state ko single source of truth maan ke UI history usse derive karna (jaise DB se view render karna), na ki do parallel histories chalana. Production me aap yahi karoge: state se unpack.
- **Evaluator ko bheja message ek serialized event log hai** — utility function tool-calls ko "Tools use" likh ke flatten karta hai, jaise aap audit log me structured events ko human-readable banate ho. Aur structured-output JSON contract ka matlab: evaluator ka response parse hone ki **schema-level guarantee** hai, regex/string parsing nahi.
- **Hands-on lab**: is lecture ka code khud chalane ke liye `Practical/lab4_sidekick.py` run karo (is repo me, `uv run` se chalta hai, Groq pe free via `langchain-groq` `ChatGroq`). Hamare labs course se thode alag: **LangSmith tracing skip** (key nahi — to trace inspection wala part console logs se samjho), **Playwright browser-driving SKIP** (heavy dep — sidekick lab me uski jagah safe sandbox file/python tools hain), aur SerperDev ki jagah free Wikipedia search.
- **25-message ping-pong warning = retry storm.** Worker–evaluator loop bina max-iteration guard ke ek unbounded retry loop hai — production me aap jaise circuit breaker / max-retries lagate ho, waise hi yahan recursion limit ya iteration cap zaroori hai. Prompt quality hi loop ko converge karaati hai.

---

## 🧠 Takeaway (yaad rakho)

1. **Har Gradio session ko random thread_id do** — checkpointer per-thread state rakhta hai, isse session isolation + multi-user support dono mil jaate hain.
2. **`graph.ainvoke(initial_state, config)`** hi UI aur graph ke beech ka bridge hai — initial state me flags `False` se start karo, evaluator unhe set karega.
3. **Evaluator structured outputs (JSON schema) se respond karta hai** — isi liye LangChain reliably parse karke routing decision le paata hai.
4. **LangSmith trace padhna seekho** — worker → tools (navigate/extract/get_elements) → evaluator → route, sab dikhta hai, cost bhi (19k tokens ≈ 0.2¢).
5. **Playwright + worker-evaluator = apna khud ka Operator-style agent** — aur iska sabse bada improvement lever hai **better prompts** (warna 25-message ping-pong).

---

<details>
<summary>📜 Full English Transcript (original, click to expand)</summary>

Okay, so first of all, we have a callback, a gradio callback that gradio will call into when we press a button, which will kick off a super step. So I've got this little thing here, which is a sort of cheeky thing that that comes up with a thread ID, a random big unique number to make sure that each time that we bring up the interface, it's not going to continue the conversation from last time or things can get quite hectic. So this this means that every gradio session is going to have a separate thread. This also means that we could actually run this and have multiple different people that come on and use the interface and each have different conversations, which is really cool. So it's not just going to be for us this this sidekick.

All right. So then the process message, uh, async, this coroutine, as I should call it, this, this function. Uh, so first of all, it creates a config based on the thread, uh, code that we're going to give it. Then it sets the initial state. So first of all the initial state. It's going to take the user's message, the message that comes in that's going to be the initial the initial message. It's going to take the success criteria as the, uh, the success criteria from, um, the the user that the user is going to tell us what what they see as being needed for success. And this state will go through all of the graph and it will be used by the evaluator, the feedback on work. Uh, this is what the evaluator can set. Success criteria met. This is false. To start with user input needed. This is false to start with.

And then here it is. Here we do it. We take a graph we call ainvoke. We pass in the state the initial state we pass in our config. And we wait for that to come back with what comes back. We then need to build the stuff that's going to appear in the Gradio user interface. We package up the user's message. We package up the the the last two things that will have come back. The second last one will be the assistant's reply, and the very last one is going to actually be the evaluator's evaluation. And we'll show them both coming so that they both appear in the UI, because it'll be nice to see the evaluation as well. But you could remove this if you don't want to see the evaluation in the UI. And then we package that together in the history with with all of this. And that's what we reply.

There is a little bit of a confusion here if you're following all this, that we're sort of combining gradio's history with the history that's being stored in LangGraph's memory, it would probably be be elegant, more more elegant here to actually unpack the full history from from the state. But that would start to get sort of messy. So I thought, keep it simple. It this this is fine. Um, and then I've also got a little callback called reset that just resets the interface.

So we'll just run this that ran quickly. Check. I ran the other cells I did. And now we're going to launch our user interface. This is going to be a UI for our sidekick. Let's see what it looks like. Here we go. The sidekick. Personal coworker. It's got a nice, uh, nice shade of green I got for this UI. And, uh, we can ask a question and we can put the success criteria. So we will ask our sidekick the question. Uh, what is the current USD, GBP exchange rate? And the success criteria is going to be an accurate answer. Simple as that. Let's see how it does.

Here we go. Press the go button. Up comes a browser window. It's put in one as the amount. So it's driving this browser. It's looked for the, uh, for the dollar pound exchange rate. It appears to be on dollar euro. That's not a good sign. See what's happening back here? It's still processing. I wonder if it's going to work this out. Well, it seemed to do okay, but I don't see on the screen how it did that. Maybe that's down here. Or did it make a mistake? Let's see. Aha. No, it got it right. I see it scrolled down it for some reason it was defaulted to Euro, but it got the US dollar to GBP at 0.77463. And if we come back here let's see what it said. It did say 0.77463. So it did. It drove the user interface. It was a bit quirky there that it didn't pick the right currency, but it found the information. Uh, so the answer was the current USD to GBP exchange rate is approximately that number.

The evaluator feedback from our other agent, the assistant, provided approximate exchange rate. However, the assistant should ideally note that it may change, so it gives some some stern feedback there, but it still chose to return control to you. Uh, so it's unclear. It thinks if it met our needs completely. Nonetheless, we saw it working. Uh, but now we need to see in LangSmith whether the right messages were exchanged.

Well, here we are in LangSmith looking at what just happened. It's worth noting that it it cost us 19,000 tokens or 0.2 of a cent, a 2/10, a fifth of a cent. So if we look here, we'll see that a lot went on. Actually look at all of this stuff. So the worker uh, called a navigate browser tool, it called extract text. It called get elements. Uh, so I guess yeah, this is, this is how it was doing its navigations and running. Uh, and then you can see down here that the this is where the these are all worker tasks. Worker tools. Worker. And then this is the evaluator getting called at the end, just as we would hope.

And we can actually go all the way into chat OpenAI to see what message was sent to the evaluator. So here we go. So this is the results of that function that I belabored a bit earlier. System you're an evaluator determines if a task has been completed successfully assess the assistant's last response based on the given criteria. Respond with your feedback, blah blah blah. Human you're evaluated. Conversation between user and assistant. You decide what action to take and then look at this. This is this is that that utility function that says user assistant, assistant assistant. And you can see that I made it. Just print tools use like this so that it's clear to the evaluator what's going on. The success criteria for the assignment is an accurate answer. So that's straight from the Gradio UI. And the final response that you're evaluating is that that is the same of course as this. And then this is the respond with your feedback blah blah blah blah blah.

And we can see that what it responded with was JSON. Uh, of course. And it's JSON that conforms to the structured outputs schema that we provided. And that's why, uh, LangChain is able to read that in and populate that object. And that's what our graph then gets returned to it. and that is how the whole thing fits together. And there's the route based on evaluation taking us to the end. So it's kind of cool to see it here in LangSmith and see the trace through the agent flow.

And I can tell you obviously I've done some experiments with this with some of my prompts. Didn't didn't work so great early on. And there was times when there was like 25 different messages between the agent and the evaluator, particularly on some harder tasks. So it was quite interesting to see it bounce around and and a lot of fun. And obviously improving the prompts is one way to get there, but overall I see this as a really exciting project. You can really feel the beginnings of something very substantive here, and when you run this, you can experiment with giving it bigger tasks, asking it to summarize the various websites, to navigate around and to summarize back something to you. And there's lots that you can do here, which is terrific fun. And so that's going to put put this on pause for now, because when we come back tomorrow, we're going to try and make this into like a packaged project with a few more features.

But let's go now to the wrap up. So I realized it was a long day today. We got through a lot, and I hope that you did have that same journey as me as seeing the visual there of that, uh, LangGraph graph and seeing the ability to build an evaluator and an agent that's able to talk like that and to go backwards and forwards, being able to give it playwright and be able to operate playwright like that. It's like we've built our own operator, the, the, uh, the agent from OpenAI, or that we built like a kind of agent. And it's been so easy to do it. And it's so cool to see the graph like this, to be able to interact with it in LangSmith. So as I say, I'm becoming I'm becoming a true believer. Uh, I'm becoming, uh, LangGraph advocate. It's exciting to see it come together. And tomorrow we'll try and take it one more step forwards. See you then.

</details>

---
*Source: Official Udemy lecture transcript (auto-captions, lightly cleaned). Notes in Hinglish for self-study.*
