# L46 — Day 5: Building a Modular AI Research System with Gradio UI

> **Week 2 — OpenAI Agents SDK** · ⏱️ ~12m · 🎥 Lecture 46 of 131
> **Instructor:** Ed Donner · **Lecture ID:** 49820807

---

## 🎯 Ek Line Mein (TL;DR)

Pichle lecture ka **deep research agent** (jo notebook me tha) ab proper **Python modules** me refactor hota hai — har agent apni alag file me, ek **ResearchManager** class sab orchestrate karti hai, aur upar ek **Gradio UI** (`gr.Blocks`) jisme **generator + yield** trick se live streaming status updates browser me dikhte hain.

---

## 📝 Hinglish Explanation (Detailed)

- **Aaj ka plan (Week 2 ka last day):** Ed bolte hain good news + bad news — good news ye ki aaj ka kaam quick, easy aur satisfying hai; bad news ye ki end me ek **really hard challenge** milega (big and juicy). Aaj hum notebook wale deep research agent ko **proper Python modules** me convert karenge, with a **Gradio UI**.

- **Ed ka workflow philosophy (phir se sales pitch):** Pehle **notebook me experiment** karo — prompts refine karo, agent architecture try karo — phir jab design settle ho jaye to use **modules me productionize** karo. Notebook → modules ka transition surprisingly natural hai.

- **Folder structure:** Cursor me `openai` folder ke andar ek **`deep_research`** subfolder hai. Isme:
  - Har agent ke liye ek **module with a single agent class** (4 agent modules)
  - Ek **`research_manager`** jo sab kuch package karta hai
  - **`deep_research`** — Gradio UI wali entry-point file

- **Agent 1 — Planner Agent:** Bilkul wahi jo notebook me tha:
  - `HOW_MANY_SEARCHES` — Ed ne 20 set kiya tha demo ke liye, lekin **check-in se pehle wapas 3** karenge taaki koi accidentally **badi bill** na bana le
  - Same instructions + same **pydantic models**: `WebSearchItem` aur `WebSearchPlan` (jisme `searches` field = list of items)
  - Planner agent in instructions ko use karta hai aur `output_type=WebSearchPlan` return karta hai

- **Agent 2 — Search Agent (ek chhota fix):**
  - Instructions: "you're a research assistant" + wahi **summarization format jo OpenAI ke docs se liya tha** (concise, 2-3 paragraphs, <300 words)
  - **Important change live in lecture:** `WebSearchTool` me **`search_context_size="low"`** parameter add kiya — ye notebook lab me top pe tha lekin module me miss ho gaya tha. Ye cost ko **nice and cheap** rakhta hai taaki koi unexpected paisa na ude

- **Agent 3 — Writer Agent:**
  - Modules ka fayda — code **crisp aur simple** dikhta hai, ek nazar me samajh aata hai
  - Pydantic model **`ReportData`**: `short_summary`, `markdown_report`, `follow_up_questions`
  - Writer agent saari searches ki info lekar usse ek **ReportData object** (full report) banata hai

- **Agent 4 — Email Agent:**
  - Wahi **SendGrid** wala `send_email` function tool — HTML body ke saath email bhejta hai
  - **Warning:** `from_email` ko apna **verified sender** banao aur `to_email` me apna address daalo, Ed ka nahi — warna Ed spam se overload ho jayenge 😄
  - Tool function me **docstring/comment** rakhna good practice hai — "send an email with the given subject and HTML body" — kyunki yahi LLM ko tool ka purpose batata hai

- **ResearchManager class — orchestration with a twist:**
  - Single entry point: **`async def run(...)`** — technically ek **coroutine** ("if you want to be pedantic")
  - **Trace ID trick:** manually trace ID generate karte hain taaki exact **OpenAI Traces URL print** kar saken ("is run ka trace yahan dekho")
  - **Sabse bada twist — `yield`:** `run` ab ek **async generator** hai. Har step pe status text **print bhi karta hai aur `yield` bhi** ("Planning searches...", "Searches complete...", etc.), aur end me **full markdown report yield** karta hai
  - Baaki 5 functions wahi hain jo notebook me the: `plan_searches`, `perform_searches`, `search`, `write_report`, `send_email` — bas thode **beefed up**: zyada **type hints** (proper checked-in code ke liye), **exception handling**, aur searches ke dauran **incremental status updates** ka support
  - Ye hi pattern hai notebook → production: **same functionality, tidied up code**

- **`deep_research.py` — Gradio UI (the magic):**
  - **Gradio** = data scientists ke liye UI banane ka package, **zero front-end knowledge** chahiye
  - Ab tak hum `gr.ChatInterface` (super canned, ready-made) use karte the; **custom UI** ke liye **`with gr.Blocks() as ui:`** pattern use hota hai, end me `ui.launch()`
  - **Theme** pass kar sakte ho (yahan sky blue chosen)
  - UI fields top-to-bottom declare karo:
    - `gr.Markdown` — "Deep Research" heading
    - `gr.Textbox` — "What topic would you like to research?" → variable `query_textbox`
    - `gr.Button("Run", variant="primary")` — blue primary button
    - `gr.Markdown(label="Report")` — output report area
  - **Event registration (callback wiring):**
    - `run_button.click(fn=run, inputs=query_textbox, outputs=report)` — button click pe `run` callback call hoga; textbox ka content input, callback ka output report markdown me jayega
    - `query_textbox.submit(...)` — same wiring, lekin **Enter key** dabane pe
  - `ui.launch(inbrowser=True)` — **front-end code generate** karta hai jo browser me chalta hai; button press hone par Python callback wapas call hota hai. `inbrowser=True` = browser window turant khul jaye

- **Final piece — streaming callback as generator:**
  - Normally Gradio callback bas ek **result return** karta hai (jaise pehle ka `chat` function)
  - Lekin callback ko **generator** bhi bana sakte ho — `yield` karte raho, aur **Gradio incrementally UI update** karega
  - Isi liye `ResearchManager.run` me itne saare yields the — user ko **interim status updates live** dikhte hain, long wait ke baad achanak output nahi aata
  - UI ka `run` callback bas `ResearchManager().run(query)` ko **async-iterate karke chunks yield** karta hai

---

## 🔑 Key Concepts / Important Terms

| Term | Simple Hinglish Meaning |
|------|--------------------------|
| **Notebook → Modules** | Experiment notebook me karo, fir settle hone par proper Python modules me refactor karo — Ed ka standard workflow |
| **gr.Blocks** | Gradio ka custom-UI builder — `with gr.Blocks() as ui:` ke andar widgets declare karo, fir `ui.launch()` |
| **Event registration** | `button.click(fn, inputs, outputs)` / `textbox.submit(...)` — UI widget ko Python callback se wire karna |
| **Generator callback** | Gradio callback jo `yield` karta hai — Gradio har yield pe UI **incrementally update** karta hai (streaming status) |
| **Async generator / coroutine** | `async def run()` jo `yield` bhi kare — status updates + final report stream karne ka mechanism |
| **search_context_size="low"** | `WebSearchTool` ka cost-control parameter — search saste me chalti hai |
| **Trace ID** | Manually generate kiya gaya ID jisse exact OpenAI Traces URL print kar sakte ho debugging ke liye |
| **ReportData** | Writer agent ka pydantic output: `short_summary`, `markdown_report`, `follow_up_questions` |
| **ResearchManager** | Orchestrator class — plan → search → write → email, sab ek `run()` coroutine me |
| **inbrowser=True** | `ui.launch()` ka flag — launch hote hi browser window khol deta hai |

---

## 💡 Backend Dev Ke Liye Note (aapke liye)

- **Gradio ka `button.click(fn, inputs, outputs)` = declarative event binding**, bilkul jaise frontend frameworks me event handlers wire karte hain — lekin yahan callback **server-side Python** hai. Socho isse ek auto-generated REST endpoint + websocket ki tarah: browser button click → Python function call → result wapas DOM me. FastAPI route likhne ki zaroorat hi nahi.
- **Generator-as-callback pattern** wahi hai jo aap **FastAPI `StreamingResponse` / SSE (Server-Sent Events)** me karte ho — chunked response, client incrementally render karta hai. Gradio ye plumbing free me de deta hai: bas `yield` karo, websocket/streaming sab handle ho jata hai.
- **Notebook → modules refactor** ko aap apne migration playbook se relate karo: prototype script → typed, exception-handled, single-responsibility modules. Notice karo ki har agent **apni file me ek self-contained unit** hai (instructions + pydantic schema + agent object) — testable aur reusable, jaise aap services ko alag modules me rakhte ho.
- **Hands-on lab:** is lecture ka code khud chalane ke liye `Practical/lab4_deep_research.py` run karo (is repo me, `uv run` se chalta hai, **Groq pe free**). Note: hamare labs OpenAI ki jagah **FREE Groq** use karte hain (`OpenAIChatCompletionsModel` + `base_url` trick), aur lab4 me OpenAI ke **paid `WebSearchTool`** ki jagah **free Wikipedia search tool** hai — to lecture wala `search_context_size="low"` cost-fix aur SendGrid email + OpenAI tracing parts hamare lab me apply nahi hote (email console-print hota hai), functionality same flow follow karti hai.

---

## 🧠 Takeaway (yaad rakho)

1. **Workflow:** notebook me experiment → proper modules me productionize (type hints, exception handling, ek class per file) — Ed ka recommended pattern.
2. **Architecture:** 4 agent modules (Planner, Search, Writer, Email) + 1 **ResearchManager** orchestrator + 1 Gradio entry-point — clean separation of concerns.
3. **Custom Gradio UI = `gr.Blocks`** — widgets declare karo, `button.click()`/`textbox.submit()` se callbacks wire karo, `ui.launch(inbrowser=True)` se chalao.
4. **Streaming UX ka secret = generator callbacks:** callback me `yield` karo to Gradio interim results live dikhata hai — long-running agent pipelines ke liye must-have.
5. **Cost discipline:** `search_context_size="low"` aur search count kam (3) rakhna — warna `WebSearchTool` ki bill badh sakti hai (~2.5 cents/search).

---

<details>
<summary>📜 Full English Transcript (original, click to expand)</summary>

So I have good news and bad news for you. The good news is that today, the last day of week two, it's going to be quick and easy and satisfying. So there's going to be fun stuff right away. The bad news is there's going to be a really hard challenge at the end of it. It's going to be hard, but really big and juicy and good. So I do hope that you will take on the challenge that's coming up. But first, let's just talk about what we're going to do today. We're going to take our deep research. The agent that we built last time in a notebook. And we're going to turn it into proper Python code in modules. Yes, with a user interface featuring Gradio. Let's go and do that right now.

And so here we are in Cursor and we're going into the OpenAI folder. But now we're going into another folder into the deep research folder that is beneath it. And you will see that there are some Python modules you'll be happy to see. Because I know you like Python modules, and I'm going to just talk you through them, and I hope going to be pleasantly surprised how easy it is, and also how natural it is to move from a notebook world into proper modules. And again, one more sales pitch. It's where I like to work experimentally, first in a notebook and then turn it into modules. As you've built out your prompts, as you've experimented and refined your agent architecture. So what we've got in here are some agent classes, some agent modules with a single agent class, and then a manager that packages it all together. And then finally, deep research is the user interface, which is a very simple user interface.

So let's start with the classes that represent the agents. And it's going to be really simple. We will start with the planner agent, which is exactly where we started when we were in the notebook the planner agent. We've got this. How many searches? I've got it set to 20 now, but I'll turn it back to three before I check this in so that no one racks up a big bill. If you use it, and you'll recognize the same old instructions and the same pydantic objects for a web search item and a web search plan, which is the list of web search items in the single field searches. And here is our planner agent that takes our instructions and it uses the web search plan. There we go.

Okay, next up, the search agent and I need to make one little change to this guy. So this is the search agent. The instructions you'll see here your research assistant. And it's got got this this format. You'll remember that we stole that format from OpenAI's documentation. A very nice set of instructions right there. I don't know if you spot the little change I have to make, but the tools in here, I need to add in that parameter to make it nice and cheap. So let's go and do that together. If we go to this lab, if we look at what that parameter was, that parameter was actually near the top. I think we did at the very beginning. There we go. It is that the search context size is low. Let's go and put that in there right now so that no one spends unexpected amounts there. We have it done. Okay, so that is the search agent class in the search agent module.

And now we've got a couple more, two more agents to talk about the writer agent again. And you know, the benefit of having these in Python modules, it looks very crisp and simple. You can see exactly what's going on. We've got our instructions. We've got the pydantic report data that has a short summary, a markdown report and follow up questions. And then our writer agent, which is the agent that will take all of the information from all of the searches and turn it into a report data object.

And the final agent, if you remember, is of course, the email agent. Here it is. This is stuff that you will recognize. This is just the same thing that is going to send the email. You must remember, please to change this to be your verified sender here, and then put some other email here. Put your recipient here, not me. I think I might change this before I check it in because otherwise someone's going to forget. Well, many people will forget and I'll be overloaded with spam email. All right, so this is the tool. And actually it's good to have a comment in here because that will send an email with the given subject in HTML body. Very nice. Okay. So that is our email agent and that is all four of our agents.

What's coming next is research manager. Okay. So research manager is a class. And this contains those short functions that we had last time with a little bit of a twist spiced it up. So first of all there is a single method here run or it's a coroutine. If you want to be pedantic with me, this coroutine run an async def run. And this is just the same as the as the code that I had before. We've got a little trick here to, to generate a trace ID so that we can, we can print where to go to look at the precise trace that we're looking at here. Now you may wonder why we've got all of this yielding going on. We, uh, we're treating this as a generator that is going to yield various bits of text along the way. So that is going to become clear in a bit, but just take a look at what's going on here. I print some updates and I also yield those updates. And I end by yielding the full markdown report. Now hopefully you've done your intermediate. Either you already know all about generators or if you don't, then you've taken a look at the guide that explains generators so that there's no surprise.

Okay. And then I've just got each of these functions plan searches, perform searches, search and write, report and send email. These are the five functions that are exactly the same as the five functions we talked through before, except a little bit beefed up. They've got more type hints put in, as one should do for proper checked in Python modules. And there's a bit more exception handling. And this is a little bit fancier to handle the being able to print a status update while it's going through the different searches, but otherwise it is much the same. So it's just a bit tidied up, which is the kind of practice you should do when you move from the notebook environment, when you're being more experimental into something that's more well baked code, but it's the same functionality.

And that finally brings us to Deep Research. Here we are. This is our Gradio app. This is where the magic happens. So Gradio which we import here. This is the the the package which you may know I love, which lets data scientists build great UIs without needing to know anything about front end. And I'm going to give you just some, some insights into how this works without I'm not giving you a full Gradio lesson here. And Gradio has great docs. It's really easy to read up about it and build build your own. But just very briefly, this this code here is where the user interface is defined. And we're used to using things like chat interface which is the super canned simple one where you just you can create an interface out of nothing. If you want to actually build your own user interface from scratch, then you have to use a slightly more detailed version when you do with gr.Blocks as and then something like UI, and then you put your your code in there and then you say UI dot launch at the end and that that's the way to do it, that that will then build your user interface.

So that is exactly what we've got here. We say with gr blocks. And then you can pass in a theme if you want to have a different theme to the to the standard theme, and you can find the different colors that you can have in here. And then you simply put down the fields that you want. So we're going to start with a heading GR markdown gives us a heading and we want to have the word deep research as a big heading. Then we want a text box that says what topic would you like to research. And we're associating that text box with a field called query. So this this is a is a field. It might be a bit query clearer if we call this query text box. Let's say that query text box. And then here the next field we're going to put on a user interface is called run button. It's a button. It says run on it and it's a primary button. So it'll be nice and blue because blue is the sky, blue is the color we've chosen. And then the next one is going to be report, which is going to be our actual report text. It's a markdown and its label is report. Okay I'm going to change this here to query text box.

So what we can now do is register an event. We want to register an event with the run button. We're going to say if the run button is clicked and we register that event by calling a function, click on run button and we just have to tell Gradio we want you to call us back. If that run button is clicked, then call this callback. And that callback is going to be something called run. And spoiler alert, run is right up here. So if if run button is clicked then call that callback. Run. The inputs that you should use should be the contents of the query text box. So the inputs to this callback should be whatever's in the text box when they press the run button, when they click the run button, and the outputs. Whatever comes out of this callback should go into, I want you to hook that up Gradio hook it up into this report markdown. And then for the this, this next one is really the same thing. It's, it's saying that if they're in the query text box and they hit the enter key to submit, then again call the run. The input should be the contents of the query text box, and the output should be the report.

So this is a way that you can hook up Gradio so that the widgets that you've constructed here get associated with inputs and outputs of a callback function that's getting called. And this this method here is going to generate front end code that's going to run in a browser. And when they press that button it's actually going to call back this Python code in our class populating it with the right the right fields. So it doesn't matter if you didn't follow all of that, or you don't get or even care how Gradio hooks things up together, just have some general intuition for it and know that UI launch is the thing that is then going to generate the front end code based on that, and figure out how to make sure that our callback gets called in browser equals true means that it's going to bring up a browser window right away. You don't need to have that if you don't wish.

So the only remaining thing for me to mention is what then is this? What is going on with the with the run up here? So this is the callback that gets called, and you can see that as part of this I am calling the research manager dot run, and that is the the long function that we looked at a moment ago that had lots of yields in there. And that brings me to the final part of the puzzle, which is normally in Gradio. With these callbacks, you just return a result, the chat function that we've worked on in the past, that's an example of a callback. Chat just returns the result, but you can also, instead of doing that, have your callback functions be generators that Gradio needs to needs to iterate over and they will yield back results. And if you do that, then Gradio will show that incrementally in the user interface, so that you don't have to sit there and wait for a long time and suddenly see an output. You can see interim results as well. And that is why we had a bunch of yields, and that is why we have them here in our callback. I hope that makes some sense, but it certainly will do when we actually see it. If it works, let's find out.

</details>

---
*Source: Official Udemy lecture transcript (auto-captions, lightly cleaned). Notes in Hinglish for self-study.*
