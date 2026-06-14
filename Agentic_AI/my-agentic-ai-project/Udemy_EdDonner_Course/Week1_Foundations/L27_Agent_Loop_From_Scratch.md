# L27 — Day 5 [Extra]: Building Your First Agent Loop with OpenAI Tools from Scratch

> **Week 1 — Foundations** · ⏱️ ~13m · 🎥 Lecture 27 of 131
> **Instructor:** Ed Donner · **Lecture ID:** 54173707

---

## 🎯 Ek Line Mein (TL;DR)

Ed (4 mahine baad wapas aakar) batate hain ki 2026 ki sabse popular definition of **agentic AI** hai — **"an LLM that runs tools in a loop to achieve a goal"** — aur fir ek simple **to-do list tool** + **while loop** se, sirf raw OpenAI library use karke, ek **agent loop from first principles** live build karke dikhate hain.

---

## 📝 Hinglish Explanation (Detailed)

- **Context — ye ek "extra" lecture hai:** Ed ye video original recording ke ~4 mahine baad record karke course mein insert kar rahe hain, kyunki field mein **agents ki definition evolve** ho chuki hai aur wo latest update dena chahte hain — plus ek demo jo concept ko "real" feel karaye.

- **Agents ki definition ka evolution (timeline yaad rakho):**
  - **Early days:** Sam Altman / OpenAI agents ko describe karte the — *"AI systems that can do work for you independently"* (GPT Operator → ab GPT Agent paradigm).
  - **Early 2025:** **Anthropic ke seminal post** aur **Hugging Face** se consensus aaya — agentic AI = *"AI systems where an **LLM controls the workflow**"*. Ye 2025 ki standard definition rahi.
  - **2026 (current):** Nayi solidifying definition — **"an LLM equipped with tools, that runs those tools in a loop to achieve a goal."** Short form: **LLM + tools + loop + goal.**
  - Ed recommend karte hain tech writer **Simon Willison** ka blog — wo ye point bahut clearly banate hain ("you know it when you see it").

- **Illusion vs Reality — AI engineer ki mindset:**
  - **Feel:** Aapne software likha, LLM ko call kiya, aur wo "off in its loop" chala gaya — tools chala raha hai, kaam kar raha hai, aur end mein answer wapas aata hai. Lagta hai koi autonomous entity kaam kar rahi hai.
  - **Reality:** Aapka software **repeatedly LLM ko call** kar raha hai. Jab **finish/stopping reason = tool calls** hota hai, aap tool execute karte ho, result wapas dete ho, aur fir se LLM call karte ho. LLM bas **likely tokens generate** karta hai — aap un tokens ko interpret karke tool calls banate ho. **"Something busy working out there" ek illusion hai** jo loop create karta hai.

- **Demo setup (Cursor, week1 ka extra notebook — "The Unreasonable Effectiveness of the Agent Loop"):**
  - Imports: `dotenv` (ab tak pro ho chuke ho), **Rich Console** — terminal pe **colored/formatted output** ke liye. Ek chhota `show()` utility jo `console.print` try karta hai, exception aaye to plain `print` fallback.
  - Usual `OpenAI()` client.

- **Vanilla Python to-do system (zero AI yahan):**
  - Do lists: **`todos`** (strings — kaam) aur **`completed`** (True/False flags).
  - **`get_todo_report()`** — current to-do list ko formatted print karta hai.
  - **`create_todos(descriptions)`** — list of strings leke todos mein add karta hai, sab `False` (not completed) mark karke report print karta hai.
  - **`mark_completed(index, notes)`** — given index ka item complete mark karta hai (completion notes ke saath); report mein completed items pe **strikethrough** dikhta hai.
  - Demo: "buy groceries, finish extra lab, eat banana" create kiye → fir item 1 ko "bought" se complete kiya → strikethrough ke saath print hua. **Pure vanilla Python — bas do functions se to-do list manage.**

- **In functions ko tools banana — "janky JSON":**
  - `create_todos` aur `mark_completed` dono ke liye wahi **JSON schema** likhna (function ka naam, description, required fields) — **exactly jaise career conversation lab mein kiya tha**.
  - Dono ko ek **`tools` list** mein daal do. Done.

- **`handle_tool_calls()` — copy-paste reuse:**
  - Ye function **literally career conversation wala hi hai** (Ed ne copy-paste kiya, ek unneeded cheez hataai). Tool calls pe iterate karta hai aur **`globals()` trick** se string name → actual function dispatch karta hai (short, sharp, pythonic).

- **THE LOOP — star of the show (`loop()` function):**
  - **`while not done:`** — bas ek simple while loop.
  - Andar: `openai.chat.completions.create(...)` call — Ed **GPT 5.2** use karte hain (koi bhi model chalega, behavior alag ho sakta hai), `messages` + `tools` pass karte hain.
  - **`reasoning_effort = none`** — latest reasoning models ke liye, taaki model extra "thinking tokens" generate na kare aur loop **fast** chale.
  - **`finish_reason` check:** agar `"tool_calls"` hai → tool execute karo, output messages mein record karo, loop continue. Agar tool call **nahi** chahiye → `done = True`, loop khatam, result `show()` se print.
  - Bas. **"Calling tools in a loop until it's done."**

- **Run — train problem:**
  - **System message:** "You have a problem to solve. Use your to-do tools to plan out the steps, then carry out each step in turn... provide your solution in rich console markup, do not ask the user questions."
  - **User message:** classic puzzle — *"Train leaves Boston at 2pm @ 60mph, another leaves New York at 3pm @ 80mph towards Boston — when do they meet?"*
  - `todos`/`completed` empty karke `loop(messages)` call kiya — aur **magic**: model ne khud 4 to-dos banaye (interpret the problem, set up variables, estimate missing quantity, compute), ek-ek karke complete mark kiye (strikethroughs live print hote gaye), aur **final answer** de diya. **Ed ne kuch touch nahi kiya.**

- **"This is Claude Code" moment:**
  - Ye behavior **Claude Code jaisa hi dikhta hai** — kyunki Ed ne **to-do list ka idea Claude Code se hi liya** (cribbed).
  - **Asli news:** ye banana **insanely easy** tha. First principles se — ek LLM jo tokens generate karta hai + while loop + 2 tools = "something busy working, planning, tracking, crossing things off" ka impression.

- **Kyun powerful hai ye technique:**
  - Sirf LLM se direct answer tokens genenerate karwana **utna accha perform nahi karta** jitna agentic technique — loop model ko problem ko **slow, step-by-step reason** karne pe majboor karta hai.
  - Aur agar tools **actually kuch karte hain** (file create karna, code run karna, calculate karna) — to results aur bhi better hote jaate hain.

- **Exercise (Ed ka challenge):**
  - Ed generally rote-typing ke fan nahi hain (IDEs + LLMs autocomplete kar dete hain; **samajhna > memorize karna**) — **lekin ye exception hai.**
  - Har kisi ko **ek baar apna agent loop from scratch** likhna chahiye — fresh Python notebook, sirf OpenAI library. Boilerplate (jaise `handle_tool_calls`) copy-paste karna theek hai, lekin **to-dos + loop khud likho**, run karke "come to life" hote dekho.
  - Fir alag interesting problems do, **extra tools add karo**, aur experiment karo. Very rewarding + very instructive.

---

## 🔑 Key Concepts / Important Terms

| Term | Simple Hinglish Meaning |
|------|--------------------------|
| **Agentic AI (2026 definition)** | "An LLM that runs tools in a loop to achieve a goal" — LLM + tools + loop + goal |
| **2025 definition** | Anthropic/Hugging Face wali — "LLM controls the workflow" (iska evolved version hai 2026 wali) |
| **Agent Loop** | `while not done:` → LLM call → agar tool_calls hai to tool chalao, result wapas do → repeat jab tak model done na bole |
| **`finish_reason`** | LLM response ka field jo batata hai ki model ne kyun rukna chaha — `"tool_calls"` matlab tool chalana hai |
| **The Illusion** | Lagta hai autonomous agent kaam kar raha hai; reality — aapka code repeatedly token-generator (LLM) ko call kar raha hai |
| **To-do Tools** | `create_todos` + `mark_completed` — 2 vanilla Python functions jo agent ko planning/tracking ability dete hain |
| **`reasoning_effort=none`** | Reasoning models ko bolna ki extra thinking tokens mat banao — loop fast rahe |
| **Rich Console** | Python library — terminal pe colored/formatted output (strikethrough waghaira) |
| **Simon Willison** | Tech writer jiska blog "LLM + tools in a loop" definition clearly explain karta hai — Ed ka recommendation |
| **Claude Code connection** | Claude Code bhi yahi pattern hai — to-do list idea Ed ne wahin se liya |

---

## 💡 Backend Dev Ke Liye Note (aapke liye)

- **Agent loop = event loop / worker poll loop pattern.** Jaise Celery worker queue se task uthata hai, process karta hai, result push karta hai, fir next task — yahan "queue" LLM ka response hai aur "task" tool call. `finish_reason` aapka loop-exit condition hai, bilkul `while msg := queue.get()` pattern. Koi framework magic nahi — ek while loop + dispatch table.
- **State machine lens:** har iteration mein system 2 states mein se ek mein hai — `AWAITING_TOOL_EXECUTION` ya `DONE`. `messages` list hi aapka **append-only event log** hai (event sourcing jaisa) — LLM stateless hai, poora context har call pe wapas jaata hai. Isliye long loops = token cost linearly badhta hai — production mein context-trimming sochna padta hai.
- **To-do tools asal mein "scratchpad via side effects" hain** — model ko external mutable state (2 lists) de di, jisse wo apna plan persist aur track kar sakta hai. Ye wahi reason hai ki Redis/DB-backed state agents ke liye natural extension hai — lists ko Postgres table se replace karo aur aapke paas durable agent hai.
- **Hands-on:** is lecture ka code khud chalane ke liye ye lab run karo — `Practical/lab5_agent_loop_from_scratch.py` (uv run se chalega, Groq-free).

---

## 🧠 Takeaway (yaad rakho)

1. **2026 definition ratta maar lo:** Agent = **LLM + tools + loop + goal** — "an LLM that runs tools in a loop to achieve a goal."
2. **Illusion vs reality:** autonomous "agent" jaisa feel hota hai, lekin actually aapka code **LLM ko repeatedly call** kar raha hai aur `finish_reason == "tool_calls"` pe tools dispatch kar raha hai.
3. **Poora agent = ~4 cheezein:** 2 vanilla Python functions (to-dos), unka JSON schema, `handle_tool_calls()` (copy-paste), aur ek `while not done:` loop. Bas.
4. **Agentic loop better results deta hai** — direct token generation se zyada, kyunki model step-by-step plan banakar reason karta hai; real tools (files, code, calc) add karo to aur improve hota hai.
5. **Ed ka exercise skip mat karo:** ek baar apna agent loop **from scratch** likho — Claude Code jaise tools ke andar exactly yahi chal raha hai, aur ye samajh permanent ho jaayegi.

---

<details>
<summary>📜 Full English Transcript (original, click to expand)</summary>

Well, fancy seeing you again. I realize for you, this is just like the very next video along from videos you're already watching. But for me, this is me coming back like four months later to give you a latest update from the front lines, to show you something super interesting that fits perfectly at this point in the course. So I'm slipping this extra in to show you something really cool.

During week one, I explained that there's no standard definition of the word agents, and it can really mean whatever you want it to mean. But there are some hallmarks of common agent solutions. But I will say that over the course of the last few months, there has become a kind of evolving and somewhat solidifying definition of agents that people are using more and more in the field. And so I did want to get that across. And then I wanted to show you something to make it feel real.

In the early days of agents, Sam Altman and OpenAI would sometimes describe them as AI systems that can do work for you independently — thinking a bit about the GPT Operator, now called the GPT Agent, kind of paradigm. And then in early 2025, there became this consensus that came from Anthropic's seminal post and from Hugging Face, that the right way to define agentic AI was AI systems where an LLM controls the workflow. And that's been the sort of solidifying definition for most of 2025. But now there's a new evolving definition that has really taken hold in 2026. And that's what I want to explain. As of 2026, the most common definition of agentic AI is: it's where you have an LLM that's equipped with tools, and it runs those tools in a loop to achieve a goal. An LLM that runs tools in a loop to achieve a goal. And it's one of these things that you know it when you see it. And I highly recommend the tech writer Simon Willison, who has a terrific blog, and this is one of the points that he makes very clearly there.

And when you're running such an agent system in a loop, this is what it feels like. You write some software, it calls the LLM, and then the LLM is off in its loop — calling, running, calling tools, calling tools until it's done, and back comes the answer. It's always important, as an AI engineer, to keep in the back of your mind that even though it feels this way — this is the experience that you have as it's off doing its thing — what's actually happening is, of course, this: what's actually happening is that you've written some software that is repeatedly calling an LLM, and when their stopping reason is tool calls, you're calling the tool, you're calling the LLM again. The LLM is just something that generates likely tokens, and you are interpreting those tokens and using them to make tool calls, and giving this kind of illusion that there is something out there that has the ability to be using these tools and keeping on going until it's satisfied that it's done the job.

And so with that, let's see it in action. Let's go to Cursor and build ourselves an LLM with tools in a loop to achieve a goal. Okay, here I am in Cursor. I'm going into week one foundations. I'm going to the new "five extra" — an extra addition to week one: "The unreasonable effectiveness of the agent loop" — a little recap on what an agent is, and making it real. I'm going to start with some imports, and I'm loading env — and I trust at this point you are pros with env, I don't need to talk about that. I'm also importing this thing called Rich Console, which is just a nice little library that lets you print to a terminal output and still have some colors in an easy way, because that's going to look nice. All right. And in fact, so the way you do that is you call something called console.print. And just so that I can handle if that ever throws an exception or anything, I've just made this little utility, show, which tries to do a console.print; otherwise it just prints — just a little simple way to show anything. Okay. And then the usual OpenAI's OpenAI that you know well.

And now let me tell you about to-dos. This is super simple. I've got two lists. One is called todos and one is called completed todos. We'll just have a list of strings of things I need to do, and completed will be trues and falses, if it's been done. And I've got a little function here, get to-do report, and it just prints out what's in that todos list. So if I run that, it prints nothing. Okay, nothing clever so far. Bear with me — this is going to deliver. Here is a function, create todos. It takes a set of descriptions, a list of strings, and it adds them to the todos. And it puts false in the completed so that they're all not completed. And then it gets the report, okay. And then another little function — the last of these — called mark completed, which takes an index and some notes on how it's being completed. And it just prints out what's happened.

So let's see this in action. Again, we will empty todos and completed, and we will create some to-dos: buy groceries, finish extra lab, eat banana. I run that and look — it prints out this nice little to-do list in formatted text. To-do one is to buy groceries, to-do two is finish the extra lab, and shockingly, three is to eat the banana. Okay. And now I am going to try marking complete the first item there, with the comment of "bought". Let's see what happens if I do that. Well bam, it prints out — and you can see I've been a bit fancy with my formatting — it puts a strikethrough on the "buy groceries", but the other two items are still there. It works great. Nothing about AI here. This is just like vanilla Python, just doing something to manage a to-do list with two functions. That's all we've done. But we're going to give that as tools to an agent and put it in a loop.

Well, you know the scoop — we have to come up with janky JSON. Here is JSON for create todos. It simply describes that function: add to-dos from a list of descriptions. It describes the kind of data it needs. It's the JSON that's the same as we used before. And this is the mark completed JSON. Feel free to take a look at it, but it says: mark completed to-do at the position and return the full list. That's the description of each of the different fields it needs to provide. Done. And now we put that into one list of tools, exactly as we did for the career conversation. That's it.

Now, time for running the tools in a loop. Okay — handle tool calls. This function is exactly the same as the function from the career conversation. And the reason I know it's exactly the same is I copied and pasted it in here. I think I might have taken out one thing that wasn't needed. And we probably don't need this print statement here — that's not going to — we don't need that. We can keep this as short and sharp as we can: handle tool calls. That just iterates through, and you can see here it calls that globals trick that makes this a nice, short and sharp, pythonic function.

And look at this function here. This is a function whose name is "loop". So we probably better look at it. I am saying while not done — while you're not finished — it's a while loop, just like the other while loop. It then calls OpenAI create. I'm using what is for me right now the latest model, GPT 5.2. You can pick whatever model you want — might have different behavior, but as you wish. It's going to pass in the messages. I'm going to take the tools that we've just created up here. And I'm saying reasoning effort is none — for these latest reasoning models, we want it to be nice and quick for this to work well, so I don't want it to be going off and thinking and making extra tokens to describe a process. And then this is something that you're familiar with: we do finish reason — is the response's reason — and if it wants to call a tool, then we go ahead and call the tool and record the output. If it's decided it does not want to call a tool, then we say the loop is done — because it's in a loop calling tools until it's done — and then we will print the results using that show thing that I wrote before, that just shows it in a formatted way or just prints it normally. That is a loop. It's a very simple loop, a simple while loop.

Let's try it. Let me give you a system message: you have a problem to solve. Use your to-do tools to plan out the steps and then carrying out each step in turn, blah blah blah blah blah blah. Provide your solution in rich console markup. Do not ask the user questions, blah blah blah. Then the user message: a train leaves Boston at 2 p.m. traveling 60 miles an hour. Another train leaves New York at 3 p.m., traveling 80 miles an hour towards Boston. When do they meet? That is what we're putting in messages — the system message and the user message in the usual list of dicts. I've done that. And now — and now I'm emptying out my todos and completed, and I'm just gonna call this loop with those messages. That's all I'm doing. I'm just calling this loop with this set of messages right here, and it's equipped with those very simple to-do tools.

Let's see what happens. Here we go. Off it goes. Oh, what's that? It's printed out a few things it wants to do: interpret the problem, set up variables, estimate any missing quantity, compute. Oh, look at that — it's just doing things and I'm not touching it. It's doing things. It's crossing them off the list. Things are printing out. It's done all four to-dos and bam! There's the answer. That is an LLM in a loop with tools to achieve a goal.

Now, of course, this isn't big news for you, because you've seen things like Claude Code do this. And in fact, Claude Code, if you've seen it, looks very like this — it has to-dos, because I sort of cribbed the idea of having a to-do list from Claude Code. The thing that might be news to you — the thing that you should recognize — is how insanely easy it was to build this, how basic it was. We just built this from first principles. We just have an LLM that generates tokens, and we turned it into this thing that gives us the impression that there's something out there that's busy working and thinking and planning and tracking and crossing things off the list. But in fact, it is simply calling an LLM repeatedly in a while loop and giving it tools and letting it use the tools to make progress. And so that hopefully really solidifies it — really makes it real for you, makes it concrete — that you see that it's very easy to build an agent loop from first principles.

And the other point to make, of course, is that it turns out that using these kinds of techniques results in better outcomes. It's kind of obvious in some ways, but it still needs to be thought about a bit: just simply getting an LLM to generate tokens as the answer doesn't perform as well as using these sorts of agentic techniques that cause it to take longer to work through and reason its way through a difficult problem. And that's why it's so powerful. But also, of course, if using these tools is actually doing something — like creating a file or running something or calculating something — you can add those sorts of tools in here and see it get better and better at what it's doing.

Okay. But with that, that's a wrap on this great simple example. And there is, of course, an exercise for you. And here's the exercise. You know, I'm not a fan of typing things in from scratch, from nothing, or trying to memorize things, because it's just not the way that it works anymore. IDEs and LLMs can help autocomplete code so fast, it's more important to understand what's happening than to be able to memorize and type things out by rote. But here's an exception, perhaps. I do think that it's incredibly beneficial for everybody to have had one crack at writing a simple agent loop from first principles, just using the OpenAI library and basically doing what I just did there. It's both very, very rewarding and satisfying, but it's also very instructive to see that coming together and really understand the nuts and bolts. So I challenge you now to start a new, fresh Python notebook, go through it, and try and create your own agent loop from scratch. And of course, refer back to this one from time to time. I mean, I copied and pasted some of this, like the handle tool calls — I couldn't be bothered to write that again, and nor should you. But there are parts of it, like just the todos and the completed — it's so interesting and fun to build that from scratch and then run it and see it come to life. And then think of some interesting different problems that you can give your LLM to see it reason its way through, and maybe add in some extra tools while you're doing it, and have fun with it. And I hope you found this both interesting and revealing, and hopefully also very satisfying.

</details>

---
*Source: Official Udemy lecture transcript (auto-captions, lightly cleaned). Notes in Hinglish for self-study.*
