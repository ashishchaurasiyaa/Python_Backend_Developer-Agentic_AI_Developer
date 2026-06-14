# L24 — Day 5: Creating & Deploying an AI Agent — From Chat Loop to HuggingFace Spaces

> **Week 1 — Foundations** · ⏱️ ~11m · 🎥 Lecture 24 of 131
> **Instructor:** Ed Donner · **Lecture ID:** 49771331

---

## 🎯 Ek Line Mein (TL;DR)

Ye lecture pure lab ka **sabse important moment** hai — **agentic chat loop** jo `while not done` mein LLM ko **tools** ke saath call karta hai, `finish_reason == "tool_calls"` aane par tools execute karke results wapas messages mein daalta hai, aur loop repeat karta hai; phir is poore agent ko **app.py** module mein pack karke **Gradio + HuggingFace Spaces** pe **production deploy** kiya jata hai — aapka **virtual resume / avatar** live website pe.

---

## 📝 Hinglish Explanation (Detailed)

- **"The single most important moment of the entire lab"** — naya, powerful **chat function** jo tool calling include karta hai. Ed ne isse intentionally space out kiya hai taaki har step clear ho.

- **Chat function ka structure (start same as before):**
  - `messages` list banao: `{"role": "system", "content": system_prompt}` → phir **history** (prior conversation) → phir `{"role": "user", "content": message}`.
  - Ab **standard trick**: ek variable `done = False`, aur **loop chalta rahega jab tak `done` True na ho jaye** (`while not done`).

- **Loop ke andar kya hota hai:**
  - **`openai.chat.completions.create()`** call — familiar cheez: `model` pass karo, `messages` pass karo, **lekin ab `tools` bhi pass karo**.
  - **`tools` = wahi JSON blob** (tool descriptions ka structure) jo LLM ko batata hai — "ye sab cheezein tum kar sakte ho, ye unka description hai."
  - Response wapas aata hai — ye **do cheezon mein se ek** ho sakta hai:
    1. User ke liye **final output** (normal text reply), ya
    2. Ek response jo indicate karta hai ki **tools call karne hain**.

- **Decision point — `finish_reason`:**
  - `response.choices[0]` dekho — **`finish_reason`** batata hai LLM **done** hai ya **tool call** chahta hai.
  - Agar **`finish_reason == "tool_calls"`** → message se **`tool_calls`** pluck karo, aur **`handle_tool_calls()`** call karo — wahi **"clever/sneaky" function** jo pichhle lecture mein likha tha:
    - **Fancy version** = "glorified if statement" (`globals()` se dynamic dispatch), aur
    - **Silly version** = literal `if/elif` statement — dono kaam karte hain.
  - Tools execute karne ke baad, **messages list mein do cheezein append karo**: (1) LLM **kya karna chahta tha** (assistant ka tool-call message), aur (2) **karne ka result** (tool results). Phir **loop back** — LLM ko dobara call karo.
  - Ye tab tak repeat hota hai jab tak `finish_reason` **tool_calls nahi** hai — matlab LLM ne bas reply kar diya — tab **`content` return** karo, wahi user ka actual response hai.
  - Ed: "**This is pivotal. This is how the whole thing hangs together.**" Samajh na aaye toh slowly, carefully tab tak repeat karo jab tak aa jaye.

- **Live demo — code actually chalta hai:**
  - "Hi there" → normal reply. "What's your job?" → "**Co-founder and CTO of Nebula**." "Do you have a patent?" → Yes.
  - "**Who is your favorite musician?**" → LLM ke paas answer nahi tha (LinkedIn/summary mein nahi hai) → **tool call hua** (`record_unknown_question`) → **Pushover** se Ed ke **phone pe push notification** aayi (recording mein phone ka sound sunai diya!). Bot ne gracefully reply kiya: "I'm not sure about my favorite musician..."
  - **Pura chain kaam kiya:** LLM ne JSON tools dekha → `finish_reason = "tool_calls"` diya → humne `handle_tool_calls` chalaya → function ne Pushover call kiya → phone pe notification. Sab kuch hang together.
  - "I'd like to get in touch" → bot ne email maanga → email diya → **dusra tool** (`record_user_details`) fire hua → phir notification. Ab tak magic ki aadat ho gayi!

- **Vision — "the future of resumes":**
  - Ab goal: ye app **production mein live deploy** karna, taaki aapke **personal website pe aapka avatar** serve ho.
  - Ed ka pitch: aage chal ke static **CV/resume/profile** ki jagah log ek **chatbot** se interact karenge jo aapke career ke baare mein baat karega — aur **Agentic AI skills** dikhane ka isse behtar tareeka kya hoga ki khud ek **agentic solution** aapki website pe ho.
  - Stuck ho toh Ed se email/LinkedIn pe contact karo — wo help karega.

- **Step 1 — Code ko Python module mein daalo (`app.py`):**
  - Notebook ka sab kuch **`app.py`** mein organize kiya gaya hai:
    - Top pe **tool functions** (Pushover wale) — nice little functions.
    - Ek **class `Me`** (as in "me" — aap) jisme:
      - **`handle_tool_call`** (wahi familiar function),
      - **system prompt**,
      - aur wahi **chat loop** — `while not done`, `openai.chat.completions.create()` with `tools` JSON, `choices[0].finish_reason` check, tools run karo, loop, final response return.
  - Ed deliberately ek baar **phir se repeat** karta hai — ye chat-with-loop itna critical hai ki do baar explain karna banta hai.
  - Bottom mein **Gradio code**: agar file directly run ho (`if __name__ == "__main__"` pattern) toh **`gr.ChatInterface(me.chat, ...)`** create hoke launch ho jata hai.

- **Locally run karna:**
  - Cursor mein terminal kholo (**Ctrl + backtick** `` ` ``), week 1 folder mein jao.
  - **`python` mat type karo — `uv run` type karo**: `uv run app.py`.
  - Link aata hai → **Ctrl+click** → browser mein app — local box pe chal raha hai. "Hi there", "Do you have a patent?" — sab kaam karta hai.

- **Step 2 — Deployment with HuggingFace Spaces:**
  - Deploy karne ke kai tareeke hain, lekin ek **particularly simple & elegant** option: **HuggingFace** — wahi AI company jo **Gradio ko own** karti hai.
  - **HuggingFace Spaces** = cheezein **really simply deploy** karne ka platform; chaaho toh apne **homepage mein embed** bhi kar sakte ho.
  - **Steps:**
    1. **HuggingFace account** banao (agar nahi hai).
    2. Terminal mein **foundations folder** ke andar jao, run karo: **`gradio deploy`**.
    3. Ye **kuch simple questions** poochega — answers Ed ne guide mein de rakhe hain.
    4. **Secrets** ka question aayega — "yes" bolo aur apni **OpenAI API key** do (deployment use karega), saath mein **Pushover tokens** bhi.
    5. Done — app ek **HuggingFace Space** mein deploy ho jayega.
  - **Public vs Private:** Space ko **private** rakh sakte ho agar nahi chahte ki dusre log aapki key use karein.
  - **Cost safety:** waise toh super cheap hai — app ko **viral** hona padega tab jaake significant spend hoga. Phir bhi:
    - OpenAI account pe **auto-refill kabhi on mat rakho** — viral case mein protection.
    - OpenAI ke apne **rate limits** bhi hain.
  - Next: Ed khud **`gradio deploy`** run karke ye process live karke dikhayega.

---

## 🔑 Key Concepts / Important Terms

| Term | Simple Hinglish Meaning |
|------|--------------------------|
| **Agentic chat loop** | `while not done` loop — LLM call karo with tools, agar tool_calls maange toh execute karo, results append karo, dobara call karo; final text aane par return |
| **`tools` parameter** | `chat.completions.create()` mein pass hone wala JSON blob — LLM ko available tools ka description deta hai |
| **`finish_reason`** | `response.choices[0]` mein flag — `"tool_calls"` matlab LLM tool chalwana chahta hai; kuch aur matlab final answer ready |
| **`handle_tool_calls`** | Wo function jo LLM ke tool-call requests ko actual Python function calls mein translate karta hai ("glorified if statement" — `globals()` dispatch ya plain if/elif) |
| **Tool results → messages** | Tool ka request + result dono messages list mein append karke LLM ko wapas bhejna — yahi loop ko close karta hai |
| **`app.py` module** | Notebook code ko production-ready Python module mein organize karna — tool functions + class `Me` + Gradio launch |
| **Class `Me`** | Aapke avatar ka encapsulation — system prompt, `handle_tool_call`, aur chat loop ek class mein |
| **`uv run app.py`** | uv environment ke saath app chalane ka command — `python app.py` ki jagah |
| **HuggingFace Spaces** | HuggingFace ka simple app-hosting platform (Gradio bhi HF ka hi hai) — `gradio deploy` se one-command deployment |
| **`gradio deploy`** | CLI command jo questions poochh ke app ko HF Space pe deploy kar deta hai (secrets: OpenAI key + Pushover tokens) |
| **Secrets** | Deployment ke waqt diye gaye API keys/tokens jo Space environment mein securely store hote hain |
| **Public vs Private Space** | Private = sirf aap; Public = sab use kar sakte hain (aapki key se) — auto-refill off rakho as safety |
| **Virtual resume** | Static CV ki jagah ek live agentic chatbot jo aapke career pe baat kare — Ed ka "future of resumes" |

---

## 💡 Backend Dev Ke Liye Note (aapke liye)

- **Chat loop = retry/polling loop with side effects.** `while not done: response = llm(); if finish_reason == "tool_calls": execute + append; else: return` — ye structurally bilkul ek **message-broker consumer loop** ya **saga orchestrator** jaisa hai: LLM ek "command" emit karta hai, aap execute karke "event" (result) wapas log mein append karte ho, aur state machine aage badhti hai. `messages` list yahan aapka **append-only event log** hai — LLM API stateless hai, pura context har call pe jata hai.
- **`finish_reason` = HTTP status code analogy.** Jaise aap `response.status_code` pe branch karte ho (200 vs 3xx redirect), waise hi yahan `finish_reason` pe branch hota hai — `"tool_calls"` ek "redirect" hai jo bolta hai "pehle ye kaam karo, phir wapas aao"; normal stop = "200, body ready".
- **`gradio deploy` = Heroku-style PaaS push.** HuggingFace Spaces essentially ek managed container hosting hai — `gradio deploy` aapke liye repo create karta hai, requirements detect karta hai, secrets ko env vars ki tarah inject karta hai (12-factor app config pattern). Production hygiene wahi hai jo aap jaante ho: **secrets kabhi code mein nahi**, billing pe **hard caps/no auto-refill**, aur private deployment by default.
- **Hands-on lab:** is lecture ka code khud chalane ke liye ye lab run karo — `Practical/lab4_career_agent.py` (runnable with `uv run`, Groq-free).

---

## 🧠 Takeaway (yaad rakho)

1. **Agentic loop ka core:** `while not done` → LLM call with `tools` → `finish_reason == "tool_calls"` toh tools execute karo, request+results messages mein append karo, loop → warna `content` return. **Yahi pura agent hang together hota hai.**
2. Tool results LLM ko **wapas bhejne** padte hain — sirf tool chalana kaafi nahi; LLM ko result dikhao taaki wo final user-facing answer bana sake.
3. Notebook → **`app.py` module** (tool functions + class `Me` + Gradio launch) — production ka pehla step code organization hai; `uv run app.py` se locally test karo.
4. **`gradio deploy`** ek command mein app ko **HuggingFace Spaces** pe live kar deta hai — secrets (OpenAI key, Pushover tokens) deployment ke waqt do, Space ko private rakh sakte ho.
5. Cost safety: OpenAI **auto-refill off** rakho — viral hone par bhi protected raho; ye **virtual resume** aapke Agentic AI skills ka best live showcase hai.

---

<details>
<summary>📜 Full English Transcript (original, click to expand)</summary>

Okay. This is the single most important moment of the entire lab. So it's the chat function, and I've spaced it out a bit to really explain what's going on. It's a more powerful chat function that includes the calling of a tool. It starts exactly the same way as it did before. We create some messages. Role of system. The content is the system prompt. We add in the history from before. Role of user. The content is the user's message. And now do a pretty standard trick of looping again and again and again until a variable called done gets set to true. So it's going to keep going until done is true. What is it going to keep doing? It's going to call OpenAI. And this is the usual thing — OpenAI .create, we're familiar with that. We pass in the model. We pass in the messages, this set of messages. But look, we also pass in tools. Tools is that JSON blob, that structure of JSON, which is going to be sent to the LLM saying, these are all the things you can do. This is the description of everything you can do. All right. And back it comes into response. And what comes in response might just be the output to go to the user, or it might be a response that indicates that tools need to be called. So that is what we do next. We look at response choices. And this tells us whether the LLM is finished and it's done, or whether it wants to call a tool. So if the finish reason is tool calls, it wants to call a tool. Then we look at the message itself, we pluck out the tool calls from it. And this is where we call that function that we just wrote, that clever function, that sneaky function. Right here it is. Remember it — handle tool calls. This is the one that is the glorified if statement, the one that has the fancy if statement. But there's also this more silly version here that just has an actual if statement. But it's going to call this. So back we go. So again, if it wants to call tools then we do that. We handle the tool calls. We call the tools. And then into the set of messages, we put what it wanted to do and the results of doing it. And then we will loop back and call a second time. And we will keep doing this until the finish reason is not tool calls — it does not want to call tools with whatever, it's just responded — in which case we return the content, because that is going to be the actual response to the user. I hope that made sense. If not, go through it slowly, carefully until it does. This is pivotal. This is how the whole thing hangs together.

Now, I know what you're thinking. You're thinking it's all very well showing us all this code. But does it actually work? Well, let's find out. Let's run the code. Here we have it. Let's say hi there. Hello. How can I assist you today? What's your job? I'm currently the co-founder and CTO of Nebula. Very nice. Uh, do you have a patent? Yes I do. Very nice. Uh, who is your favorite musician? That's what I want to know. I hope you, uh, heard that — success. So it says: I'm not sure about my favorite musician. I appreciate a variety. If you have a favorite, I'd love to hear about it. It called the tool. You heard my phone go. We have success. The agent was able to take that JSON. It knew that this was a tool that it could call. It was able to respond with the finish reason as tool calls. And that caused us to interpret that, to make the call to our function handle tool calls, which had our fancy code that ended up calling this function, that ended up calling Pushover, that then sent the push notification to my phone — and it all hung together. All right, let's keep going. I'd like to get in touch. That's great to hear. Please share your email address. I'm ed at edwarddonner.com. I know you're expecting it now. The, uh, the magic's worn off. You're not impressed anymore? Well, I think that's really cool. So it has indeed, of course, notified me about my own email address, which is great. And so it shows you that it does hold together. Uh, and you are indeed able to have these interactions and get it to text you. Okay. That's great. I hope you enjoyed it.

But next it's all about doing this for you and actually deploying this live to production, so that you can serve your own avatar on your personal website. So if you've followed everything so far, then many congratulations. If you haven't, then also congratulations, because it gives you this great opportunity to go through, work through this until you do. And if I can help — email me or contact me anytime. LinkedIn with me. Message me so that I can help you out. So what I want to do now is show you how you can deploy this application in production for yourself, so that you can have this as your virtual resume. Surely this is the future of resumes. No longer will we have profiles or CVs, resumes where you list out your skills and experience, but rather you'll have a chat bot that people can interact with to learn about your career. And what better way to highlight your AI abilities and your abilities to work with Agentic AI than to have an agentic solution up on your website that will allow you to interact with people and talk about your career.

So let me show you some steps to deploying this. So the first thing to do is to put the code into a Python module. And I have done that right here for you in app.py. And you'll see that this has all of the stuff you would expect. It's got the same information in here, but organized into nice little functions at the top — the functions that cover the tools that we call. And then there is a class Me, as in me or you. And that's something which has the handle tool call that we know so well — that's right here. And it has the system prompt and this loop that we just went through, this chat loop that has the while not done — it calls OpenAI create, it passes in the tools. I don't think I mentioned this actually, so I'm pleased I pause for a minute here, because I do want to show this one more time. We call chat completions create. We select the model, we pass in the messages, and we pass in the tools JSON — the description of the tools that it can call. And with what comes back, we take choices zero. And we look at the finish reason back in the response. And we see whether or not that is tool calls. And if so, then we loop through to make sure that we run all of the tools before calling it again to get the final response. So this is so critical, this chat with its loop, that I do encourage you to take a look at it.

And now at the bottom here we have the Gradio code. We've got it set up here so that if this is just run as it is, then it will create a Gradio chat interface, with showing me chat and with the messages, and it will launch it. So what I can do now, in fact, is I can bring up a terminal — which you may remember, you press control and the backwards tick mark. I can go into the week one folder. Here we are. And I can now type — remember you don't type python, you type uv run to run something. In this way: uv run app.py. And if I run that, then it should come up. So this link — now on this link I can press control and click it to bring it up. Up it comes. Let me make that a bit bigger for you. This is now an app running on my box, and I can say hi there. Hello. How can I assist you. And, and uh, do you have a patent, and so on. And there we go. Okay. So that works.

Going back here, what we now want to do is look at actually deploying this. So there are various ways you can deploy an application like this, but one of them that's particularly simple and elegant is brought to you by the lovely AI company HuggingFace, which also happens to be the company that owns Gradio, that beautiful framework. HuggingFace has something called HuggingFace Spaces, and HuggingFace Spaces is a way that you can deploy things really simply. And then if you wish, you can also embed them in your own home page. So it gives you a really nice, simple way to do it. So this is how you do it. You first have to go to HuggingFace's website and set up your own account if you don't already have one. So you may already have a HuggingFace account, but if not, you need to set one up. Once you've done with that, you go into the foundations folder in a terminal and you run this command: gradio deploy. It's then going to ask you a series of questions, a bunch of simple questions, to which I've got the answers you have to give right here. And I'll go through and do it right now. But I'm not going to do it properly, because one of the questions it's going to ask you about some secrets — that you'll say yes, and you're going to provide your OpenAI API key so that it can use that in the deployment. And you can also give your Pushover tokens as well. And then I have got the rest of the instructions right there for you. And once that's done, it will be deployed into a HuggingFace Space. And you can choose whether that is public or private. You can have it be private if you don't want other people using your key. Although as I say, it's super cheap, but people would have to — it would have to go viral for you to have any kind of significant spend. And of course, make sure that your OpenAI account — you never want to have that auto-refilling, so that if that ever were to happen, if your app did go viral, then you would be protected. And anyway, OpenAI has limits, as you probably know. So, uh, let's go and actually do this. Let's run gradio deploy. So I'm going to bring up the terminal now, and then we will go and do this ourselves together.

</details>

---
*Source: Official Udemy lecture transcript (auto-captions, lightly cleaned). Notes in Hinglish for self-study.*
