# L83 — Day 4: Worker-Evaluator Implementation

> **Week 4 — LangGraph** · ⏱️ ~10m · 🎥 Lecture 83 of 131
> **Instructor:** Ed Donner · **Lecture ID:** 49821391

---

## 🎯 Ek Line Mein (TL;DR)

Is lecture me hum **worker-evaluator pattern** ka poora implementation complete karte hain — **worker router** (tool call hai to `tools`, warna `evaluator`), **evaluator node** jo **structured outputs (Pydantic)** se feedback + decision deta hai, **route_based_on_evaluation** router, aur finally poora **graph** assemble karke ek **true agentic workflow** banate hain jisme loop hai aur LLM ke paas autonomy hai.

---

## 📝 Hinglish Explanation (Detailed)

- **Worker router (conditional edge function):** Ye ek simple Python function hai jo **conditional edge** me use hota hai control route karne ke liye. Logic seedha hai — state ka **most recent message** uthao, check karo ki usme **tool call** hai ya nahi. Tool call hai to `"tools"` return karo, nahi hai to `"evaluator"`. Matlab: jab worker (assistant) ne final answer de diya hai (koi tool call nahi), tab us answer ko **evaluate** karna zaroori hai.

- **`format_conversation` utility:** Ed ne ek chhota helper function likha jo message objects ki list ko ek simple text summary me convert karta hai — `User: ... Assistant: ... User: ... Assistant: ...` format me. Ye evaluator ke prompt me poori conversation cleanly dikhane ke kaam aata hai.

- **Evaluator node — structure:** Evaluator bhi ek **node** hai — **state leta hai, state return karta hai**. Ye us LLM ko represent karta hai jo worker/assistant ke answer ko assess karega aur decide karega: answer user ko return karne layak hai, ya worker ko wapas bhejna hai aur kaam karne ke liye.

- **Structured outputs use ho rahe hain:** Evaluator LLM ko `with_structured_output` ke through bola gaya hai ki wo ek particular type ka object (Pydantic class `EvaluatorOutput`) return kare. Pehle state ke `messages` collection se **last response** (assistant ka attempt) nikalte hain.

- **Evaluator ka system prompt:** "You are an evaluator that determines if a task has been completed successfully by an assistant. Assess the last response based on the criteria. Respond with your feedback and a decision on whether the success criteria is met, and whether more input is needed from the user."

- **Evaluator ka user prompt (detailed):**
  - Poori conversation (`format_conversation` se formatted) include hoti hai.
  - **Success criteria** state se pluck karke prompt me insert hota hai — ye wahi criteria hai jo **user ne graph invoke karte waqt set kiya tha** aur poore graph me state me maintained rehta hai.
  - Last response explicitly alag se dobara diya jata hai — taaki evaluator **crystal clear** rahe ki use poori conversation nahi, sirf **ye final response** assess karna hai (jo user ko jaane wala hai).
  - "Respond with feedback, decide if success criteria is met, also if **more user input is required** — kyunki assistant ko question hai, clarification chahiye, ya wo stuck hai."

- **Prompting me repetition theek hai:** `user_input_needed` ka description already **EvaluatorOutput** Pydantic class me likha tha — to prompt me repeat kyun? Ed ka rule: **prompting me repetition se kabhi nuksaan nahi**. *Be clear, be instructive, repeat yourself* — thode different words me dohraana model ko desired behavior ki taraf **bias** karta hai.

- **Prior feedback ka handling (loop-breaking trick):** Agar state me already `feedback` pada hai, matlab evaluator **isi loop me pehle bhi call ho chuka hai**. To prompt me add hota hai: "In a prior attempt you provided this feedback. Agar assistant **same mistakes repeat** kar raha hai, to consider responding that **user input is required**." Ye line genius lagti hai, but Ed honestly bolte hain — **koi magic nahi hai**. Testing ke time evaluator baar-baar same problem wapas bhej raha tha (infinite loop type situation), to **trial and error** se ye prompt fix nikla. Different model ya different task pe ye tweak karna pad sakta hai. **AI engineering = research & development** — experiment karo, prompt change karo, phir try karo.

- **SystemMessage + HumanMessage:** System prompt aur user prompt ko **LangChain ke message constructs** (`SystemMessage`, `HumanMessage`) me wrap karke ek list `evaluator_messages` banate hain. Thoda confusing hai — ye "human message" actually koi human nahi likh raha, hum khud manufacture kar rahe hain — but LangChain me system/user prompts banane ka yahi standard tareeka hai (LangGraph internally LangChain constructs use karta hai).

- **Evaluator invoke + naya state:** `evaluator_llm_with_output.invoke(evaluator_messages)` call karte hain. Wapas **EvaluatorOutput Pydantic object** aata hai — behind the scenes LLM ne **JSON** return kiya, wo JSON parse hoke Pydantic object ban gaya. Phir **naya state** banate hain:
  - `messages` me evaluator ka feedback add karte hain — yaad rahe `messages` pe **reducer** laga hai, to ye **concatenate/accumulate** hota hai, overwrite nahi.
  - Pydantic object se `feedback` → state, `success_criteria_met` → state, `user_input_needed` → state. New state return.

- **`route_based_on_evaluation` router:** Doosra router function — agar **success criteria met** hai **YA** **user input needed** hai, to **END** (super-step khatam, control user ko wapas). Dono extremes me — "humne bahut achha kiya" ya "hum bilkul stuck hain" — user involve hona chahiye. But agar criteria meet nahi hua **aur** user ki help bhi nahi chahiye, to **worker ko wapas** — cycle back, worker feedback ke saath dobara try kare aur improve kare. Yahi pura workflow ka idea hai.

- **Graph assembly:** Ab graph banate hain — simple hai:
  - **Nodes:** `worker`, `tools` (ToolNode), `evaluator`.
  - **Conditional edge:** `worker` se, `worker_router` use karke — `"tools"` return hua to tools node, `"evaluator"` return hua to evaluator node.
  - **Normal edge:** `tools` → `worker` (tool run hone ke baad **wapas worker** pe aana hi hai). Ed bolte hain ye thoda "hokey" hai — lagta hai automatic hona chahiye, but LangGraph me **explicitly** likhna padta hai.
  - **Conditional edge:** `evaluator` se — `route_based_on_evaluation` ke hisaab se ya `worker` pe wapas, ya `END`.
  - **Start edge:** `START` → `worker`.

- **Graph ka diagram:** Run karke picture dekho — START → worker; worker se **dotted line (conditional edge)** tools tak, tools se **solid line (definite edge)** wapas worker; worker se conditional edge evaluator tak (sirf tab jab tool call nahi); evaluator se conditional — END (success criteria met ya user input needed) ya wapas worker.

- **True agentic workflow:** Ye Anthropic ke **agentic patterns** me se ek hai (evaluator-optimizer), but ek workflow se zyada — kyunki isme **infinite loop** possible hai, ye **keep running** kar sakta hai, aur iske paas apne actions pe **agency/autonomy** hai. Isliye ye sirf workflow nahi, **true agent pattern** hai. Next step: ise actually chala ke dekhna.

---

## 🔑 Key Concepts / Important Terms

| Term | Simple Hinglish Meaning |
|------|--------------------------|
| **Worker router** | Conditional edge wala function — last message me tool call hai to `"tools"`, warna `"evaluator"` return karta hai |
| **`format_conversation`** | Utility jo message objects ki list ko "User: ... Assistant: ..." text summary me convert karti hai (evaluator prompt ke liye) |
| **Evaluator node** | Node (state in → state out) jisme LLM worker ka last answer assess karke decide karta hai: done, retry, ya user input chahiye |
| **Structured outputs** | LLM ko force karna ki wo specific Pydantic class ke shape ka JSON return kare — parse hoke typed object milta hai |
| **Success criteria** | User dwara graph invoke karte waqt set kiya gaya goal — state me maintain hota hai, evaluator prompt me inject hota hai |
| **`user_input_needed`** | Evaluator ka flag — assistant ko clarification chahiye ya wo stuck hai, to user ko wapas control do |
| **Repetition in prompting** | Same instruction ko prompt me alag words me dohraana — model ko desired behavior ki taraf bias karta hai, koi harm nahi |
| **Prior feedback trick** | State me purana feedback hai to prompt me daalo: "same mistakes repeat ho rahi hain to user input maang lo" — infinite loop se bachne ka trial-and-error fix |
| **SystemMessage / HumanMessage** | LangChain ke message constructs — system aur user prompts ko programmatically banane ka standard tareeka |
| **Reducer (on messages)** | `messages` field ka `add_messages` reducer — naya message return karo to wo existing list me append/accumulate hota hai, overwrite nahi |
| **`route_based_on_evaluation`** | Evaluator ke baad ka router — criteria met YA user input needed to END, warna wapas worker |
| **Super-step** | Graph execution ka ek round — END pe super-step khatam, control user ko wapas |
| **Conditional vs normal edge** | Diagram me dotted line = conditional (router decide karta hai), solid line = definite edge (hamesha follow hota hai, jaise tools → worker) |
| **True agent pattern** | Anthropic ke evaluator-optimizer workflow se aage — loop + optionality + autonomy, theoretically infinitely chal sakta hai |

---

## 💡 Backend Dev Ke Liye Note (aapke liye)

- **Worker-evaluator loop = retry-with-feedback pattern:** Ye bilkul waisa hai jaise aap message queue me failed job ko **error context ke saath** requeue karte ho — naive retry nahi, har retry me feedback state me accumulate hota hai. Aur "same mistake repeat ho rahi hai to user input maango" wala trick = **circuit breaker**: bounded retries, phir human escalation. Production LLM loops me ye bina kisi guard ke infinite token-burn ban jaate hain.
- **State return = event append, not mutate:** Evaluator naya state *return* karta hai aur `messages` ka reducer use append/merge karta hai — ye **event sourcing** jaisa hai (append-only log + fold function), in-place `UPDATE` jaisa nahi. `feedback`/`success_criteria_met` jaise plain fields default reducer se overwrite hote hain, `messages` reducer se accumulate — same state object me dono semantics coexist karte hain.
- **Structured outputs = response schema validation at the boundary:** `with_structured_output(EvaluatorOutput)` waise hi hai jaise aap FastAPI me `response_model` lagate ho — LLM ka raw JSON Pydantic se parse/validate hota hai, aur aapka routing code typed fields (`output.success_criteria_met`) pe branch karta hai, string-parsing pe nahi. Control-flow decisions ko hamesha structured output pe base karo.
- **Hands-on lab:** Is lecture ka code khud chalane ke liye ye lab run karo — `Practical/lab3_worker_evaluator.py` (is repo me, `uv run` se chalta hai, Groq pe free via langchain-groq `ChatGroq`). Hamare labs course se thode alag hain: **LangSmith tracing skip** (key nahi) aur **SerperDev ki jagah free Wikipedia search** — lecture wala worker-evaluator loop, router functions aur graph wiring same hai.

---

## 🧠 Takeaway (yaad rakho)

1. **Do router, ek loop:** `worker_router` (tool call → tools, warna → evaluator) aur `route_based_on_evaluation` (criteria met ya user input needed → END, warna → worker) — bas in dono se poora agentic loop ban jata hai.
2. **Evaluator = node + structured output:** State leta hai, LLM ko Pydantic schema (`EvaluatorOutput`) ke saath invoke karta hai, aur feedback/decision naye state me daal ke return karta hai — `messages` reducer se accumulate hota hai.
3. **Prompting me repeat karna feature hai, bug nahi** — Pydantic field description me likha hai to bhi prompt me dobara likho; clarity + repetition model ko bias karti hai.
4. **Infinite loop ka ilaaj prompt me hai:** prior feedback state me ho aur assistant same galti repeat kare, to evaluator ko bolo user input maang le — ye trial-and-error se nikla fix hai; **AI engineering = R&D**, no magic rules.
5. **`tools` → `worker` edge explicitly likhna padta hai** — LangGraph automatically wapas route nahi karta; aur final graph ek **true agent pattern** hai (loop + autonomy), sirf fixed workflow nahi.

---

<details>
<summary>📜 Full English Transcript (original, click to expand)</summary>

So the worker router then is a Python function that we will use in our edge, in our conditional edge to decide which way to route control. And it's very simple. It's going to take the most recent message. It's going to see if it's a tool call. If so it returns tools, if not evaluator. And that is to say that when our worker, our assistant has come up with an answer, if it's not involving a tool call, then it needs to be evaluated. And that's what we get to right now.

So for the evaluation, we have first of all, this little utility function format conversation that's just used to take in. I just wrote that to transform a list of these message objects into something which says like user assistant, user assistant in just a nice little text summary. And you'll see why right now, as we come on to look at the evaluator code, we run these two cells and we will talk about the evaluator.

So this is the evaluator. This function right here. It is a node. It takes a state and it returns a state. And it's meant to represent the LLM, which is going to be assessing our our assistant, our worker, and deciding if it's ready to return to the user or it needs to go back for more. And so it all comes down to some prompting and let me take it through you, through it. Remember that we're using structured outputs that will require that the model returns a particular type of object. So first we take the most recent response which is of course the assistant's attempt. We take that out of the state object the messages collection.

So then we come up with this system prompt. You are an evaluator that determines if a task has been completed successfully by an assistant. Assess the last response based on the criteria. Respond with your feedback and a decision on whether the success criteria is met and whether more input is needed from the user. And then the user message. This is going to be a bit more detailed. You're evaluating a conversation between the user and the assistant. You decide what action to take based on the last response from the assistant. The entire conversation with the assistant, along with the user's original request and all replies, is here. And this is going to use this little utility thing, which is just going to say like user assistant, user assistant with the whole conversation so far. So it's going to look very simple in language.

The success criteria for this assignment is, and then I'm plucking out of the state this success criteria. And as I hope you've guessed, this is something that's going to be set right at the very beginning when we invoke the graph. So that's going to be passed in by the user. And it'll be maintained throughout our graph. So we can pluck it out and just insert it in the user prompt for this evaluator right here. And then I say the final response from the assistant that you were evaluating is this last response. And of course that will already be included in here. But I just want to be crystal clear so that the evaluator understands that it's not assessing the whole conversation, it's just assessing this response right here, which is what's going back to the user.

Respond with your feedback and decide if the success criteria is met. Also if more user input is required, either because the assistant has a question, needs clarification, or seems to be stuck and unable to answer without help. So you may remember that we already put some of this in the definition of the structured outputs of the response, right up at the top. Let me show you that right here in the evaluator output. We already gave a little description of user input needed right here. And so you may wonder why I'm repeating myself here. And the answer is because there's never a harm in being repetitious with prompting. Be clear. Be instructive. Repeat yourself. These are good things to do in slightly different ways, because it biases the model to doing what we want it to do. Okay.

And then finally in here I put, if we've already got some feedback in the state object, that means that the evaluator was already called in this very loop and has already provided feedback in the past. And so I add in: also note that in a prior attempt from the assistant, you provided this feedback. If you're seeing the assistant repeating the same mistakes, then consider responding that user input is required. Now you might think this is very clever. How did you come up with that and why? Why that? And when do I use this kind of thing? And look, the answer is there's no magic here. That is there because I was testing this and it kept messing up by the evaluator sending back the same problem again and again. And so this is the kind of thing that is trial and error. You experiment, you try. When something goes wrong, you change the prompt and you try some more. There's no magic and no clever rules to this. This won't always apply, but it applies here. And if you use a different model or slightly different tasks, you may find that you need to tweak this or use something different. And that is what AI engineering is all about. And that is what prompting is about. And so yeah, the answer is it's research and development. Okay. We'll finish this off in just a second.

So we then put the system message and the user message, which is called a human message object, together into one list called evaluator messages. And it's confusing because we're using this concept of system message and user message in order to talk to an evaluator. And this isn't actually a human message, it's actually something where it's a user prompt, but it's a message that we have manufactured. But that's just really how you go about building system and user prompts using LangChain's constructs. This is a LangChain construct within LangGraph. And so, you know, this is still achieving the same thing.

All right. Now we then take our LLM, which is the evaluator LLM with structured outputs, we call invoke with these messages. And what comes back will be an instance of that class evaluator output. It is that Pydantic object filled up. And behind the scenes what's going on is that it's been asked to provide JSON and that JSON has come back and that JSON has been parsed into this object. That's how it did it. And so we're then going to create a new state because we're meant to return a new state, and in that state we're going to respond. We're going to add to the messages, because remember, messages has the reducer. So whatever we reply here gets concatenated, accumulated with the existing messages. We're going to shove in there that the assistant is replying evaluator feedback on this answer and something in there. Then we're going to give some feedback. And so what we're doing here is we're taking the feedback from the Pydantic object, and we're putting that in the state. We're taking the success criteria from the Pydantic object, putting it in the state, taking user input needed, taking it from the Pydantic, the structured outputs that came back, put it in the state and return the new state. Hopefully you followed all that. If not, you will when it comes together.

And then we've got another of these router functions, route based on evaluation. If the success criteria is met or if user input is needed, then end the super step. The super step is done. It's got to pass back to the user. In either of these two extremes, either we've done great or we've done horribly. Either of those extremes, we need the user to get involved again. But if we didn't meet the success criteria and we don't need help from the user, then it needs to be passed back to the worker. We need to cycle back. The worker has got to try again and improve on this, given this feedback. That is the whole idea. That is the workflow.

And now we come to our graph. It's very simple and all of this is pretty simple. I've been making a bit of a meal out of it, explaining this step by step and talking about prompting, but it's not that hard. If you go through it yourself, you'll see what I mean. So this is our graph. We're going to add our worker node. We're going to add our tools node and our evaluator node that we just built. Now some edges. We're going to have a conditional edge for the worker. We're going to use the router that we wrote, the worker router. If it returns tools, we're going to go with the node tools. If it returns evaluator, we'll pick the node evaluator. We're going to add another edge that goes from tools back to worker. Again, remember this one. When the tools finishes, it's got to route back to the worker. That's kind of hokey that you have to do that. You think it would sort of be done automatically for you. But you have to be clear. And then another conditional edge from the evaluator based on its evaluation. If it wants to go to the worker, we put it back to the worker. If we're done, we're done. And then we also add a start edge to bring us, first of all, to the worker.

Let's run that and look at a picture of this. There it is. There it is. We have ourselves a true agentic workflow. There's the start, goes to a worker that optionally can run tools, which has to come back. There's a thick line, optionally a dotted line, an optional edge — a conditional edge is the word, sorry. It will run a tool and then it will definitely come back, an edge. And then when it's done, this is shown as a conditional because it's only if it hasn't decided to run a tool, then it will come this way. And the evaluator chooses either to end in two situations — either success criteria is met or user feedback is required — and if not, it comes back to the worker.

So this diagram hopefully has everything coming together for you. And now scroll back up in the lab and just take a look through those nodes again. And at this point it should be like, oh, got it, got it, got it, got it. And hopefully you'll see that although I made a bit of a meal out of it, it is actually quite quick to build something like this. And you see one of Anthropic's agentic patterns loud and clear here, although it's a little bit more than one of their workflows, because this has like an infinite loop in it, it can keep going. And there's a lot of optionality here. So this is a true agent pattern, because in theory this could just keep running and running. And it has some sort of agency, autonomy over what it does. And surely you're now thinking, well, I want to see this thing, and that is what we will do next.

</details>

---
*Source: Official Udemy lecture transcript (auto-captions, lightly cleaned). Notes in Hinglish for self-study.*
