# L87 — Day 5: Graph Builders & Node Communication

> **Week 4 — LangGraph** · ⏱️ ~9m · 🎥 Lecture 87 of 131
> **Instructor:** Ed Donner · **Lecture ID:** 49821429

---

## 🎯 Ek Line Mein (TL;DR)

Sidekick app ke **worker** aur **evaluator** nodes ka prompt-engineering walkthrough — phir **graph builder** se 3 nodes + edges wire karke compile, aur **run_superstep** function jo graph ko `ainvoke` karta hai. Lesson: agentic systems mein **prompt tweaking experimental kaam hai**, aur graph building ab "easy part" lagti hai.

---

## 📝 Hinglish Explanation (Detailed)

- **Worker node ka system message (meaty prompt):**
  - Worker node ka **system message kaafi lamba** hai — Ed ne apne experiments ke basis pe isse build kiya hai, aur bola ki tum bhi aise hi iterate karte rahoge.
  - **Current date/time directly prompt mein inject** kiya. Pehle Ed ne iske liye ek **tool** banaya tha, par phir realize hua: tool banao, phir prompt mein bolo "ye tool zaroor use karna" — **double kaam, silly idea**. Jo info *hamesha* chahiye, usse tool mat banao, **prompt mein shove kar do**.
  - Ye cheez aage **MCP** mein "**resource**" kehlayegi — static info jo model ko har baar deni hoti hai (vs. tool = action jo model decide karke call karta hai).

- **Python tool ka GPT-4o mini bug (real debugging story):**
  - GPT-4o mini ne **Python REPL tool ko galat samjha** — usse laga ki code ka *evaluated value* automatically return hoga. Actually tool se output paane ke liye **code mein `print()` statement chahiye**.
  - Result: model **baar-baar code re-run karta raha**, kuch output nahi mila, confused loop mein phans gaya.
  - **Fix = ek prompt line:** *"You have a tool to run Python code, but note that you need to include a print statement if you want to receive output."* — aur turant kaam karne laga.
  - Lesson: shayad bada GPT-4 ye khud figure kar leta, ya tool description improve ho sakti thi (ya wrapper tool banate) — par **prompt mein ek hint daalna sabse fast fix tha**. Ye **experimental nature** of agentic engineering ka perfect example hai.

- **Worker router + format function:**
  - **worker_router** = conditional edge ka decision function — worker ke baad **tools jaayein ya evaluator**? (Tool call hai to ToolNode, warna evaluator.)
  - Ek **utility method** hai jo messages list ko clean **"User: ... / Assistant: ..."** formatted conversation mein convert karta hai (evaluator ke prompt ke liye).

- **Evaluator node ("the big guy"):**
  - Evaluator ka bhi **substantive prompt** hai jo time ke saath tweak hua: tum evaluator ho, ye tumhara role hai + **formatted conversation + success criteria + last response** + feedback dena.
  - Problem: evaluator **zyada harsh** tha — worker bole "file likh di" to evaluator trust hi nahi karta tha ("pata nahi sach mein hua ya nahi").
  - Fix: prompt mein add kiya — *"Assistant ke paas file write karne ka tool hai; agar wo bole file likhi hai to assume karo likhi hai. Overall benefit of the doubt do, par agar lage aur kaam chahiye to reject karo."*
  - Ed manta hai shayad ab **too lenient** ho gaya — ye **constant tweaking & refinement** ka game hai.
  - **Concrete examples** prompt mein dena helpful hai, par **trade-off**: jitna zyada info prompt mein, model ke liye **coherent rehna utna hard** (zyada context absorb karna padta hai).

- **Evaluator ka structured output + state update:**
  - End mein **`llm_with_output` invoke** hota hai — ye **structured outputs** wala LLM hai (Pydantic `EvaluatorOutput` schema bound), to wo ek **populated EvalResult object** return karta hai.
  - Us object ke **fields pluck karke new state populate** karte hain aur **new state return** karte hain — kyunki **har node old state leta hai, new state return karta hai** (LangGraph ka core contract).
  - **route_based_on_evaluation** = doosra conditional branch: agar **success criteria met** YA **user input needed** → **END**; warna **wapas worker** ko bounce — ek aur shot do.

- **build_graph — ab ye "easy part" hai:**
  - Week ke pehle dino mein jis graph building ka itna "song and dance" tha, ab wo **sabse aasaan hissa** lagta hai (kyunki saari complexity nodes/prompts mein hai).
  - Steps: **StateGraph builder** banao apni **State class** ke liye → **3 nodes add** karo (**worker, tools, evaluator**) → **edges add** karo:
    - **worker → conditional edge** (tools ya evaluator ya...) — worker_router se,
    - **tools → worker** (ye **normal edge** hai, conditional nahi — tool run hua to hamesha worker pe wapas),
    - **evaluator → conditional edge** (worker pe wapas ya END),
    - **START → worker**.
  - Phir **`graph.compile()`** — done.

- **run_superstep — graph invoke karne wala function:**
  - **`sidekick_id`** = ek **random UUID** instance variable → isse **config** banta hai (`thread_id` ke liye, checkpointing/memory ka key).
  - **Initial state** banta hai: user ka **message**, **success_criteria** (agar user ne pass nahi kiya / null / empty string → default: *"The answer should be clear and accurate"*), **feedback_on_work = None**, aur dono boolean flags (**success_criteria_met, user_input_needed**) **False**.
  - Phir **`graph.ainvoke()`** (async invoke) se kick-off → result se **user message, reply, feedback** pluck karke **history construct** karte hain — wahi UI ko reply hota hai.

- **cleanup function (resource hygiene):**
  - End mein ek **cleanup function** hai jo resources release hone pe call hota hai — Ed sure nahi hai ki ye **100% reliably sab clean** karta hai, time ke saath refine karega.
  - Main concern: **headless browser** (Playwright) jo spawn hota hai — naya Sidekick process start karo to **naya browser spawn** hota hai; purana browser close/quit hua ya nahi, ye track karna zaroori hai (warna **orphan browser processes** leak hoti hain).
  - Agla step: **user interface (the app)** — Gradio UI agle lecture mein.

---

## 🔑 Key Concepts / Important Terms

| Term | Simple Hinglish Meaning |
|------|--------------------------|
| **Worker node** | Main assistant node — lamba system message, tools use karke kaam karta hai |
| **Evaluator node** | Doosra LLM node jo worker ke output ko success criteria ke against judge karta hai |
| **Resource (MCP term)** | Static info (jaise current date/time) jo har baar prompt mein inject hoti hai — tool banane ki zaroorat nahi |
| **Tool vs Prompt injection** | Agar info *hamesha* chahiye → prompt mein daalo; agar model ko *decide* karke fetch karna hai → tool banao |
| **Print-statement hint** | Python REPL tool output ke liye `print()` chahiye — model confuse ho to prompt mein hint daal do |
| **worker_router** | Conditional edge function: worker ke baad tools jaana hai ya evaluator |
| **route_based_on_evaluation** | Conditional edge: success met / user input needed → END, warna worker pe retry |
| **Structured outputs (`with_structured_output`)** | LLM ko Pydantic schema bind karna — wo populated object return karta hai, free text nahi |
| **Node contract** | Har node: old state in → new state out (return new state) |
| **build_graph** | StateGraph builder + add_node ×3 + edges (normal + conditional) + `compile()` |
| **tools → worker edge** | Normal (unconditional) edge — tool run hone ke baad hamesha worker pe wapas |
| **run_superstep** | Graph ko `ainvoke` karne wala method — initial state + config (UUID/thread) banakar |
| **sidekick_id (UUID)** | Random UUID jo config/thread identity ke liye instance variable hai |
| **Default success criteria** | User na de to: "The answer should be clear and accurate" |
| **cleanup function** | Resources (especially headless browser) release karne ka function — warna orphan processes leak |

---

## 💡 Backend Dev Ke Liye Note (aapke liye)

- **Tool vs resource = API call vs request middleware.** Current date/time ko tool banana waise hi hai jaise har request pe client se bolo "ab timestamp endpoint call karo" — jabki middleware/context injection se wo automatically har request mein aa sakta hai. Jo data deterministic aur hamesha needed hai, usse **context mein inject karo, RPC mat banao**. MCP mein yahi `tools` vs `resources` ka split hai.
- **Evaluator ka leniency tuning = retry policy + circuit breaker calibration.** Too strict evaluator → infinite retry loops (wasted tokens = wasted compute); too lenient → bad output ship. Ye exactly waise hi hai jaise health-check thresholds tune karna — false positives vs false negatives ka trade-off, aur production feedback se hi sahi balance milta hai.
- **Cleanup function ka concern classic resource-leak problem hai** — jaise DB connections ya subprocess handles ka lifecycle: `finally`/context-manager guarantee ke bina headless browsers orphan ho jaate hain. Agentic apps mein bhi `async with` / explicit teardown discipline wahi hai jo tum connection pools ke saath karte ho.
- **Hands-on lab:** is lecture ka code khud chalane ke liye `Practical/lab4_sidekick.py` run karo (is repo me, `uv run` se chalta hai, Groq pe free via langchain-groq `ChatGroq`). Note: hamare lab course se thoda alag hai — **Playwright browser-driving SKIP** kiya hai (heavy dep; uski jagah safe sandbox file/python tools hain), LangSmith tracing bhi skip (key nahi), aur SerperDev ki jagah free Wikipedia search — to lecture wala "headless browser cleanup" issue hamare lab mein nahi aayega.

---

## 🧠 Takeaway (yaad rakho)

1. **Hamesha-needed info prompt mein inject karo, tool mat banao** — date/time jaisi cheez "resource" hai, action nahi.
2. **Ek prompt line se tool-confusion fix ho sakta hai** — GPT-4o mini ko `print()` hint dene se Python tool loop turant theek hua; agentic engineering = experiment + tweak.
3. **Evaluator prompts ko calibrate karna padta hai** — too harsh = retry loops, too lenient = bad accepts; concrete examples help karte hain par context overload ka trade-off hai.
4. **Graph building ab easy part hai:** builder + 3 nodes (worker/tools/evaluator) + edges (tools→worker normal, baaki conditional) + compile. Complexity nodes ke andar hai, wiring mein nahi.
5. **run_superstep = UUID config + initial state + `ainvoke`**, aur **cleanup zaroori hai** warna har run pe spawned headless browser leak hota hai.

---

<details>
<summary>📜 Full English Transcript (original, click to expand)</summary>

Okay. And so what we have now is the worker node that is defined right here. And it's quite long. Um, and uh, it doesn't even fit on one screen. I think I expanded the font size a bit so that, uh, but that does have that drawback. Maybe I will make it a little bit smaller for a second, and we'll make it bigger again in a minute. Uh, go down a little bit so you can at least see it all in one screen. Uh, so this here is the is the, uh, is worker. So it's got a pretty meaty system message, which I have built up based on my experiments. And you will need to keep doing so too.

I added in here the current date and time. I actually, for a bit made another tool to to come up with the current date and time, but I realized that then I had to come in here and prompt it to be sure to use that tool. And then I thought to myself, okay, this is silly. I always want it to know the current date and time. I put that in as a tool, and then I'm telling it in the prompt to be sure to use that tool. And that's just such a waste. This is an example of something that doesn't need to be a tool. It needs to be inserted in the prompt every time. It is what we'll call a resource when we when we get to MCP time. But it's like it's like a piece of information that we want to add in there. So I just shove in the current date and time in the prompt.

I also, I had an interesting thing happen when I was using the Python tool that I saw that for some reason, GPT-4o mini misunderstood how the tool worked and thought that the code it would put in there, whatever that evaluates to, would be what it would receive in the response from the tool, where in fact, you had to put in a print statement in that code if you want to actually get back some text. And it didn't do that. Uh, and so as a result, it was going backwards and forwards, trying to rerun again and again and not getting any results and seeming confused. Uh, and uh, so I added in this line, you have a tool to run Python code, but note that you need to include a print statement if you want to receive output. And then it started to work immediately. So maybe that's just a GPT-4o mini anomaly. Maybe if I use the big GPT-4, it would be fine. It would have figured it out or it would just know. But or maybe the way that the tool, the description in the tool isn't clear enough. And I could always wrap it in a, in a, in another tool that would make that clearer. Um, but uh, but regardless, this, this fixed it. And this is such a good example of the experimental nature of this kind of work that you need to be able to come in and just shove something like that in the prompt. Maybe this won't be needed for what you do, but it was needed for me. Um, and there was another example of, of where I came across something similar. Um, and, uh, yeah, you'll probably find it yourself if you if you look through this, you'll see other times when I had to tweak things, uh, to, to handle some cases.

Um, so anyway, other than that, this is all identical to what we have in Jupyter in the, uh, notebook. Let me expand here. Um, okay. And now this is the router, the worker router, the decision, the condition on whether or not the worker should go to tools or to evaluator. This is the utility method that converts our messages into a nice user assistant. User assistant.

And finally not not not finally. But the big the big guy is the other node the evaluator. And this has again, a lot of pretty substantive prompting that I have tweaked over time. That describes you're an evaluator, what you're there to do. Uh, it's got the formatted conversation, the success criteria, the last response. And then, uh, responding with your feedback. Uh, and, um, I remember now, I added in this, I noticed that the evaluator was quite harsh and never seemed to sort of trust that what the, um, assistant said it had done, what the worker said it did. The evaluator always said, you know, I don't know if this actually happened. So I put I put in here the assistant has access to a tool to write files. If the assistant says they've written a file, then you can assume that they've done so. Overall, you should give the assistant the benefit of the doubt if they say they've done something, but you should reject if you feel that more work is needed. So you know, again. And maybe this time I've gone too far and I'm going to make it accept too many times. It's something that requires constant tweaking and refinement as you find cases that are that are that work or don't work. And of course, it's always good to add an example to give real concrete examples. And there's some trade off, because the more information you put in here, uh, the, the harder it is for the model to be coherent because it's just got a lot more information to absorb. Uh, but, um, yeah, it's definitely it's definitely something that I found that giving these kinds of hints and examples has helped me get better outcomes. And you will need to experiment.

Okay. So that is the evaluator. We've then got at the end of it, I'll just mention again, remember at the end of the evaluator, we, we we invoke the LLM with output. And because it's, it's one that has a structured outputs which is what that with output means, uh, it returns back an object, an eval result object populated, and then we pluck out the fields of that object, and we populate them in our new state, and we return the new state as all nodes take an old state, return a new state. And then this route based on evaluation, this is again another of these condition branches. We take, uh, we see whether either the success criteria is met or user input is needed. In either of those situations we need to end, but otherwise we're going to bounce back to the worker to give it another shot.

Okay. And then here is the build graph. And this after I made such a song and dance about this in the first couple of, of uh, of days of this week. Now this is like the easy part of the whole thing. We create our graph builder for, for the state of the class that we have created. And then we add our worker, we add our tools, we add our evaluator, the three nodes. We add our our edges. Uh, um, conditional edge. This is not a conditional. This is the if a tool is run, it needs to come back to the worker. A conditional edge to choose between the worker and ending and the start going into the worker. And then we compile our graph.

Okay. And then I've got this run super step function which is the one that actually invokes the graph. So run super step then is pretty straightforward. Uh, I've got uh, the uh, the random UUID I've set as, as an instance variable sidekick ID. So I set up the config this way. And then the state the initial state that we will use to invoke our graph. It is the message from the user for the success criteria. It's either the success criteria that's passed in or if that's if that's not set, if it's null or an empty string, then I use this default. The answer should be clear and accurate. Um, feedback on work is set to none. And these two are both false initially. And then we call our graph ainvoke to kick it off. And then we pluck back the user's thing, the user's message, the reply, and the feedback from it. And we construct our history and that is what we reply.

And then I've also got this at the end like a clean up function. And as I say, it's kind of as you'll see this gets called when resources get cleaned up. And I'm not 100% sure if this is always cleaning everything up. And so over time I will I will try and keep an eye on this. And I may refine this as as we go, as I get, get to see whether this is properly cleaning things up. So if it looks a bit different when you're looking at this code, then I might have found a better way to do this that's more reliably cleaning resources. Um, after after they've been used. And I'm talking particularly about, of course, about the browser that we spawn this headless browser. And the thing to be aware of is, okay, once we've done that, if we then kick off a new sidekick process, it spawns another browser. What have we done to that first browser? Have we closed it? Have we quit the browser that's running behind the scenes? Uh, or running in front of the scenes as it would happen? Uh, so, um, yeah, I've, uh, put this in to do that. Okay. And now on to the user interface, the app.

</details>

---
*Source: Official Udemy lecture transcript (auto-captions, lightly cleaned). Notes in Hinglish for self-study.*
