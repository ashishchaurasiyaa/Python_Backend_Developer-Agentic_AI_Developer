# L89 — Day 5: Inside AI Feedback Loops

> **Week 4 — LangGraph** · ⏱️ ~12m · 🎥 Lecture 89 of 131
> **Instructor:** Ed Donner · **Lecture ID:** 49821439

---

## 🎯 Ek Line Mein (TL;DR)

Sidekick ko live chala ke Ed dikhate hain ki **worker-evaluator feedback loop** parde ke peeche kaise kaam karta hai — **evaluator** ne worker ka imprecise answer **reject** kiya, worker ne **Python REPL tool** dobara chala ke khud ko correct kiya, aur **LangGraph checkpointing** ki wajah se agent ne pehle likhi file ka naam bina bataye yaad rakha.

---

## 📝 Hinglish Explanation (Detailed)

- **Pehle ek chhota debugging lesson:** Ed ne tools list change karte waqt **brackets miss** kar diye the, jisse app crash ho gaya. Lesson: jab kuch achanak kaam karna band kar de, to **pehla suspect hamesha tumhara last change** hona chahiye. Classic debugging rule.
- **App run karna:** terminal kholo (Ctrl + backtick), 4th week directory me jao, aur plain `python` nahi — **`uv run app.py`** se application start karo. Gradio UI me **Sidekick personal co-worker** aa jata hai.
- Ed bolte hain ki ye project **continuously evolve** ho raha hai — tumhara version video se alag (better!) dikh sakta hai, aur contributions (naye tools, features) welcome hain.
- **Test 1 — "What is pi times 3?":** simple sa question, lekin response me ek ajeeb line aayi — *"addressing the previous mistakes about rounding"*. Matlab? **Worker (assistant) aur evaluator ke beech ek poori conversation hui jo user ko dikhi hi nahi.**
- Trace kholne par pata chala ki agent ne pi × 3 ke liye kaafi **rigmarole** kiya — pehle online search kiya, phir **Python REPL tool** use kiya. Ed ke pichle lecture wale fix (`print(result)` instruction) ki wajah se REPL se **empty string nahi**, balki actual output **9.4477...** mila.
- **Evaluator ne pehla answer REJECT kiya:** worker ne ~9.425 / 9.45 jaisa **too-early rounded** answer diya tha. Evaluator bola — *"the answer provided by the assistant is incorrect... precision was lacking"*. Yahi worker-evaluator pattern ka magic hai: **success criteria meet nahi hua to feedback ke saath wapas worker ke paas**.
- **Worker ka retry:** feedback milne par worker ne tool dobara chalaya — pehli baar **syntax error** (code curly brace `}` se end hua, closed bracket ki jagah), phir teesri attempt me sahi code, accurate output, aur tab evaluator ne **accept** kiya.
- **Key insight:** evaluator ko poori **message history** dikhti hai (Ed ka utility function jo user/assistant turns format karta hai), isliye uska final feedback "previous mistakes about rounding" mention karta hai. Ye saara **multi-turn self-correction loop** sirf 2-3 seconds me hua aur user ko sirf final correct answer dikha. Cost: ~0.1 cent (one-thousandth of a dollar).
- **Reset button:** naya Sidekick **instance** banata hai aur **graph rebuild** karta hai — completely fresh state (naya thread/checkpoint).
- **Test 2 — Real-world task:** "NYC me French restaurant dhundo, markdown report likho (name, address, menu, reviews), aur push notification bhejo restaurant name + phone ke saath."
  - Agent ke paas **do raaste** the: **Serper API** se search ya **Playwright browser** kholke khud drive karna. Browser window pop hua, lekin agent ne use mostly skip karke search se kaam nikal liya.
  - Result: **Le Bernardin, Balthazar, Daniel** (genuinely top-tier French restaurants — 2-3 Michelin stars) ki report bani, **push notification** phone pe aaya Le Bernardin ke naam aur phone number ke saath.
  - **Verification:** Ed ne push notification wala number (212) 554-1515 Google kiya — sach me Le Bernardin ka number nikla. **Sandbox** me `dinner` naam ki markdown file bhi mili, nicely formatted.
- **Test 3 — Memory test (sabse important):** "Please update **the file** to only contain Le Bernardin info with more details." Note karo — **file ka naam nahi bataya**. Agent ne phir bhi sahi file (`dinner`) update ki, kyunki **LangGraph checkpointing** se poori conversation history persist thi. Ye proof hai ki memory genuinely kaam kar rahi hai — file update + push notification dono hue.
- **Practical tips from Ed:**
  - Sidekick **real work** kar sakta hai — Ed ne khud ek work task me multiple sites browse karwa ke compiled report banwayi.
  - **PDF reports chahiye?** LLM se directly PDF mat banwao — **LLMs markdown me brilliant hain**. Ek simple tool banao jo Python library se **markdown → PDF convert** kare. Ye trick generally useful hai: LLM ko uske comfort zone (text/markdown) me output dene do, conversion deterministic code se karo.

---

## 🔑 Key Concepts / Important Terms

| Term | Simple Hinglish Meaning |
|------|--------------------------|
| **Feedback Loop (Worker-Evaluator)** | Worker answer deta hai, evaluator check karta hai; fail hone par feedback ke saath worker dobara try karta hai — sab user ko dikhe bina |
| **Evaluator Rejection** | Evaluator ka kisi answer ko criteria (yahan: precision) pe fail karna aur reasoned feedback dena |
| **Self-Correction** | Worker ka feedback/error (syntax error, rounding) dekh ke apne aap retry karke sahi answer tak pahunchna |
| **Python REPL Tool** | LangChain ka tool jo LLM-generated Python code execute karta hai; `print()` zaroori hai output capture ke liye |
| **Checkpointing (LangGraph)** | Har super-step ke baad state save hoti hai; isi se agent ne bina naam bataye "the file" = `dinner` yaad rakha |
| **Reset / Graph Rebuild** | Naya Sidekick instance + fresh graph = clean slate, purani memory gone |
| **Serper API vs Playwright** | Do search options — API-based Google search vs actual browser ko drive karna; agent khud choose karta hai |
| **Sandbox** | Restricted folder jahan agent files likh/update kar sakta hai (jaise `dinner` report) |
| **Markdown → PDF trick** | LLM se markdown banwao, PDF conversion deterministic Python tool se karo |
| **uv run** | `uv run app.py` — uv environment ke saath app launch karne ka tarika |

---

## 💡 Backend Dev Ke Liye Note (aapke liye)

- **Evaluator rejection + retry = retry-with-context, not blind retry.** Tumhare backend retries (tenacity, Celery `retry()`) same input dobara bhejte hain; yahan worker ko **structured failure feedback** milta hai (jaise code review comments) aur wo *different* attempt karta hai. Ye exponential backoff se fundamentally zyada powerful pattern hai — failure reason loop ka input ban jata hai.
- **"The file" wala moment event sourcing jaisa hai:** LangGraph checkpointer har super-step pe state snapshot karta hai (per `thread_id`), to follow-up request me poora context replay ho jata hai — bilkul jaise event-sourced aggregate apni history se current state rebuild karta hai. Session-based web app me ye tumhe Redis session + audit log dono ek saath milne jaisa hai.
- **Markdown → PDF tip ek general architecture principle hai:** LLM ko probabilistic part (content) do, deterministic part (format conversion) code ko do. Ye wahi separation hai jo tum business logic vs serialization layer me karte ho — LLM ko serializer mat banao.
- **Hands-on lab:** is lecture ka worker-evaluator code khud chalane ke liye `Practical/lab3_worker_evaluator.py` run karo (is repo me, `uv run` se chalta hai, Groq pe free via langchain-groq ChatGroq). Note: hamare labs course se thode alag hain — lecture me jo **Serper** search aur **Playwright** browser-driving dikhti hai, uski jagah humne free **Wikipedia search** aur safe sandbox file/python tools rakhe hain, aur **LangSmith tracing** skip ki hai (key nahi chahiye).

---

## 🧠 Takeaway (yaad rakho)

1. **Worker-evaluator loop invisible self-correction deta hai** — user ko sirf final correct answer dikhta hai; rejection, syntax error, retry sab parde ke peeche seconds me ho jata hai.
2. **Evaluator ko poori message history do** — tabhi wo "previous mistakes" jaisa contextual feedback de sakta hai; isolated single-answer grading kamzor hai.
3. **Checkpointing = real memory:** agent ne "the file" se `dinner` file pehchani bina naam bataye — yahi LangGraph persistence ka practical payoff hai.
4. **Jab kuch crash ho, pehla suspect tumhara last change hai** — Ed ke missing brackets wala timeless debugging lesson.
5. **LLM se markdown banwao, PDF deterministic tool se** — probabilistic generation aur deterministic conversion ko alag rakho.

---

<details>
<summary>📜 Full English Transcript (original, click to expand)</summary>

And just before we take this thing for a drive, let me just mention that I made a little mistake here when I was changing the tools — I left off those brackets. Uh, and that caused it to crash. So you may have spotted that, in which case you should have shouted, uh. I, uh, have now fixed that after a few minutes of messing around and, uh, remember, when things stop working, the first thing you should be suspicious of is what did you change? Uh, so now let's run this. So we run it by bringing up our terminal — control and the backtick — and then we move into the fourth directory, and then we don't do Python. Uh, we do uv run and then app dot py to bring up our application. And here it is. Here is the sidekick personal co-worker at your disposal.

And I'm rather hoping that what you see is a bit different to this, because I'm loving this project and I'm fully planning to keep working on it, uh, and to keep improving it in time. And so don't worry if what you see doesn't match this video, because you should revel in the fact that it'll have more functionality, more ability, and and if it doesn't, then please help. Come and help me contribute. Make some tools, make some features and push them so this can look better and better.

Uh, anyways, now let's set some challenges. Okay, let's start with what is pi times three? Let's let it have a think of that. And the funny thing is that, uh. Well there we go. Uh, this is, um. Well, that's interesting response. Addressing the previous mistakes about rounding. So, uh, what we're seeing there, I haven't seen this before, and this is something that we'll have to, uh, have to, uh, look into, but the. So we're seeing a value of pi, um, which is great. And I like the way it's put pi with the Greek symbol and of pi times three. And we're seeing in the feedback, the final response accurately states that it's that this is correct and precise, addressing the previous mistakes around rounding. So I wonder what that even means. It sounds like, unbeknownst to us, the agent and the evaluator had a conversation about this. Let's go and take a look.

Wowser there's a lot of information here. It had it. It really went to town on calculating pi times three. Uh, and, uh, see that, uh, it's still we still ended up spending, uh, about 0.1 of a cent, so a thousandth of a dollar. It didn't cost us very much. But, uh, it's interesting that it had it went, went on quite, quite a rigmarole here. So let's see what happens. Uh, so this is, uh, so first of all, it went to, um, wow. It did some looking on online first of all. And then I think and then it gets to, uh, using, uh, the Python, the Python REPL and it gets that. So it, um, it uses, it uses print results. So it does follow my instructions because previously it would have got just an empty string there. So it gets something back there. 9.4477. Is that what what we see when we, uh, look in the. Yes it is. Okay. Okay. So it did it did faithfully get there in the end.

Uh, so now we keep going down. Let's see what happens when the evaluator evaluated this. So, um, based on this, it says the answer provided by the assistant is incorrect. The result of this should be approximately that, not 9.425. Let's see. So. Oh yes, it replied approximately 9.45. The assistant rounded the answer too early or incorrectly. Therefore, while the intention was to provide an approximate value, the precision was lacking. And so that's great. That's this is amazing. So, uh, were the, um, the the assistant gave an answer that was too imprecise. It wasn't to enough decimal places, which annoyed the evaluator that rejected it. And so then, uh, for some reason, the the assistant decides it's going to go back and run the tool a second time. It gets a syntax error. Let's see that syntax error. Look at that. It ends with a curly instead of a closed bracket. So it makes a mistake. It uses it again. This time it gets it right and it gets a good output. And that is then what it what it sends back. And now we see the evaluator, uh, and uh, the response is what we already saw in the screen. Uh, that and that now explains exactly why. Because the evaluator, of course, sees the whole history of this backwards and forwards, which we don't see.

Um, and, uh, so, um, yeah. And if you look at what the evaluator got to evaluate, this is the result of that function. I wrote that utility function with the user assistant, user assistant. And you can see that it says user. What is pi times three? Assistant uses the tools and then gets that approximate thing. And the evaluator feedback says that's no good. The assistant uses the tools and gets a syntax error. Uses the tools again and gets the accurate number and then gets the value right there. So this is really fascinating. What what a journey to see this happen. It all happened in a couple of seconds. So we weren't aware that this uh this syntax error this this feedback was happening and we got to the right answer. So, uh, that's that's a very, very cool to see.

Okay, I press the reset button, which creates a new instance of sidekick and it rebuilds the graph. So we've got a completely fresh one here. And I'm going to paste in a question I'd like to go to dinner tomorrow in a French restaurant in New York. Please find a great French restaurant and write a report in markdown to dinner, including the name, address, menu and reviews. Send me a push notification with the restaurant name and phone. All right, let's, uh, let's give this a try. Now, there is a risk here. We will see what happens. The the risk is that. And what's cool that it's just popped up a browser window. It could have used the Serper API to be searching that way. Or it could bring up a browser and drive it this way. So I'm not sure what it's going to do. And it might bring up the browser, but decide not to use it as it appears to be doing now.

So it's got. Oh, and it's finished. It's finished. Uh, I've uh uh, hang on and see if I've got that pushed. I have my phone on silent so we won't have heard it. And I have indeed got a push and it's pushed notified me about Le Bernardin. So. Uh oh, it's chosen some snazzy French restaurants. I'll have, you know. Um, so, um, let me see. It's compiled a report. It's named it. The report includes detailed information about Le Bernardin, Balthazar and Daniel, such as their addresses, menus and reviews. And those, by the way, are phenomenal French restaurants. But, uh, Le Bernardin is like a three Michelin star or two. Daniel is two, I think. And, uh, Balthazar is obviously super famous and popular and celebrity haunt. So these are all like, uh, top French restaurants for sure. Uh, it probably found like some website with, with top French restaurants. Um, it did indeed send me the push notification with the name and the phone number, but we will need to verify that the phone number is accurate, which we will do right now. Um, and, uh, we will also go and, uh, uh, check the file. Let's do that right away.

Okay. Well, let's start with the phone number. So I've got the my push notification in front of me. The phone number for Le Bernardin. According to this push notification is (212) 554-1515. Let's see what comes up. If we Google that, we get Le Bernardin. Fantastic. So well done our sidekick. And now we need to see whether or not we've got a file. So if we go back to Cursor and look at the file in the sandbox, there is indeed a file called dinner. Let's bring that up in a preview mode and let's get rid of the terminal. Here it is. Dinner report French restaurants in New York City. Le Bernardin highlights and Daniel and a summary. There we go. So that does seem to be a successful report, nicely formatted, nicely written to my file system. And I know from from trying with this that I can then go back. I can then ask it to flesh out one.

Well let's do let's do a little bit more. Let's go one step further and then I'll leave with you to experiment with yourself. Okay. So I'm going to add in here. Please update the file to only contain information about Le Bernardin and include as much information as possible. Um. And include um, more details including, um, some extracts of reviews, a summary of reviews, and some menu items. Okay, let's give this a shot. Go. Let's give it a few seconds. Okay. It says that it's been doing that. It also says it's sent me a push notification. See if that's true. Yes. It has. Uh, okay. Let's go and have a look in here, and we'll just re load this open preview. Hang on. Maybe I need to, um, close the screen and open it up again. Try this one more time. Hold on. It is indeed now just on Le Bernardin. It has. So it updated a file on the on the drive in its sandbox, which is pretty cool. It updated it with more details. The cuisine menu highlights ambience and summary of reviews. Impeccable service. It is three Michelin stars. So is, uh, right. Good. Uh. And uh, yeah, it's got some menu highlights too. So it has improved the report. But the thing that I really want to show you is that it knew how to update a file that it had written before, and I also it shows that it understood the memory because I just said the file, I didn't name it. And of course it remembered that it had been called dinner, which it was getting from LangGraph's checkpointing.

So there you have it. There is our sidekick in action, uh, doing plenty of things. And, uh, and of course, it can do a lot more. You can keep experimenting. It can do a lot more just with the tools it's already got. It can build files, it can write reports. The specific thing I did for a work thing is I had it go and search and browse a number of different sites, compile them and produce a report. And it did all of that. Uh, and it was really impressive. If you want it to make PDF reports, you can add a tool that just converts markdown to PDF. That's the trick. Uh, because the these, um, these, uh, LLMs are great at generating markdown and they would have a harder time building a PDF, although they could do it, but it would be harder. But make markdown and you can write a tool that just uses a Python library to convert markdown to PDF. And so then you can build those kinds of reports as well. And it can do real work. It really can. And you should put it to the test.

</details>

---
*Source: Official Udemy lecture transcript (auto-captions, lightly cleaned). Notes in Hinglish for self-study.*
