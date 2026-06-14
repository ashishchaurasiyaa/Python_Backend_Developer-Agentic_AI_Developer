# L06 — Day 1: Building Your First Agentic AI Workflow with OpenAI API (Step-by-Step)

> **Week 1 — Foundations** · ⏱️ ~18 min · 🎥 Lecture 6 of 131
> **Instructor:** Ed Donner · **Lecture ID:** 49770893

---

## 🎯 Ek Line Mein (TL;DR)

Pehla **actual coding lab** — Jupyter notebook mein OpenAI client setup karke ek call `2+2` poochte hain, fir **do LLM calls chain karte hain** (call-1 ek hard IQ question banata hai → call-2 use solve karta hai). Yahi **agentic workflow** ki simplest form hai: multiple LLM calls ko orchestrate karna.

---

## 📝 Hinglish Explanation (Detailed + Code)

### 0. Lab setup (notebooks)
- Cursor mein `1_foundations` folder → **`1_lab1.ipynb`** kholo.
- Ye ek **Jupyter notebook** hai (code "cells" mein bata hota hai). Engineers ko pehle ajeeb lagta hai (wo plain `.py` pasand karte hain), par notebooks **R&D + learning** ke liye perfect — step-by-step run, experiment, print statements. Course mein **dono** (notebooks + normal `.py` modules) use honge.
- **`guides` folder:** beginner + intermediate Python (async, generators, debugging, name errors) + **troubleshooting guide**. Zaroor dekho.
- **Kernel select karo:** top-right "Select Kernel" → Python Environments → **`.venv` (recommended, Python 3.12)**. Har naye lab mein ye karna padta hai.
- Ed ka tarika: pehle **video dekho** (Ed explain kare), fir aap **khud lab dobara karo** step-by-step (print statements daal ke).

### 1. Environment variables load karo
```python
from dotenv import load_dotenv
load_dotenv(override=True)
```
- `load_dotenv()` project root mein **`.env`** file dhoondta hai, parse karke environment variables set kar deta hai.
- **`override=True` (important trick):** by default agar koi env var pehle se globally set hai (profile mein), wo priority leta hai aur `.env` use nahi hoti → "OpenAI mera key kyun reject kar raha?" wala nasty gotcha. `override=True` ensure karta hai **`.env` wali value jeete**.

### 2. Key check karo
```python
import os
api_key = os.getenv("OPENAI_API_KEY")
if api_key:
    print(f"Key exists and begins {api_key[:8]}")
else:
    print("Key not set - troubleshooting guide dekho")
```
- `sk-proj...` se shuru hona chahiye. ✅

### 3. OpenAI client banao
```python
from openai import OpenAI
openai = OpenAI()
```
- ⚠️ **Galatfehmi clear karo:** ye **locally GPT model nahi** banata! `OpenAI` ek **lightweight client library** hai — bas cloud ke HTTP endpoints ko call karne wala simple wrapper. (Lowercase `openai` variable = instance; uppercase `OpenAI` = class.)

### 4. Messages format (industry standard)
```python
messages = [{"role": "user", "content": "What is 2+2?"}]
```
- LLM conversations is format mein represent hote hain: **list of dicts**, har dict mein `role` + `content`. OpenAI ne invent kiya, ab har jagah ubiquitous.

### 5. Pehla call
```python
response = openai.chat.completions.create(model="gpt-4o-mini", messages=messages)
print(response.choices[0].message.content)   # -> "2 + 2 = 4"
```
- `chat.completions.create` = OpenAI ko call karne ka **standard tarika**. Cursor auto-complete kar deta hai. Connected! ✅

### 6. 🚀 First Agentic Pattern (do calls chain karo)
**Call 1 — ek hard question generate karwao:**
```python
messages = [{"role": "user", "content": "Please propose a hard, challenging question to assess someone's IQ. Respond only with the question."}]
response = openai.chat.completions.create(model="gpt-4o-mini", messages=messages)
question = response.choices[0].message.content
print(question)   # e.g. ek train brainteaser
```
**Call 2 — ab us question ka answer nikalwao:**
```python
messages = [{"role": "user", "content": question}]   # call-1 ka output -> call-2 ka input
response = openai.chat.completions.create(model="gpt-4o-mini", messages=messages)
answer = response.choices[0].message.content
print(answer)
```
- **Yahi "agentic" hai:** humne **ek LLM ka output dusre LLM ke input** mein feed kiya — multiple calls ko orchestrate karke ek bada problem solve kiya. (Ed: technically abhi ye "workflow" zyada hai, pure "agent" kam — par direction sahi hai.)
- Output markdown mein aata hai → nicely display:
```python
from IPython.display import Markdown, display
display(Markdown(answer))
```

### 7. 🎯 Exercise (zaroor karo — commercial angle)
Ek **3-call workflow** banao:
1. LLM se **ek business sector** chunwao jisme AI opportunity ho.
2. Us sector ka ek **pain point** identify karwao (explicitly explain).
3. Us problem ka **AI/agentic solution** propose karwao.
- Teeno calls chain karke print karo (markdown mein). Ye agentic workflow practice + real business idea dono deta hai. Cursor/ChatGPT se help le sakte ho.

---

## 🔑 Key Concepts / Important Terms

| Term | Simple Hinglish Meaning |
|------|--------------------------|
| **Notebook (.ipynb)** | Cells mein code — R&D/learning ke liye. Select kernel = `.venv`. |
| **`load_dotenv(override=True)`** | `.env` se keys load; `override=True` global var gotcha se bachata hai. |
| **`OpenAI()` client** | Cloud endpoints ka lightweight wrapper (local model NAHI). |
| **messages** | `[{"role","content"}]` — LLM conversation ka standard format. |
| **`chat.completions.create`** | OpenAI ko call karne ka standard API. |
| **Agentic workflow** | Ek call ka output → agle call ka input. Multiple LLM calls orchestrate karna. |

---

## 💡 Backend Dev Ke Liye Note (aapke liye)

- **Aapke liye ye easy hai:** aap already `load_dotenv()` (`main.py` mein) aur LLM clients use kar rahe ho. Bas Ed `openai` SDK directly use kar raha hai (aap LangChain `ChatGroq` use kar rahe the) — dono ka core same: messages bhejo, `choices[0].message.content` lo.
- **Notebook vs `.py`:** as a backend dev aapko `.py` zyada natural lagega, par **notebooks ko prototyping tool** ki tarah apनाओ — AI engineering mein experiment/iterate karne ka best way.
- **"Agentic = orchestration" mindset:** ek backend dev ke liye ye basically **chained API calls + data passing** hai. Magic kam, engineering zyada. Difference: har "API" ek reasoning LLM hai.

---

## 🧠 Takeaway (yaad rakho)

1. `load_dotenv(override=True)` → `OpenAI()` → `messages` → `chat.completions.create`.
2. **`OpenAI()` = cloud wrapper**, local model nahi.
3. **Agentic workflow ki seed:** call-1 ka output → call-2 ka input.
4. Exercise (business sector → pain point → AI solution) **zaroor** karo.

---

<details>
<summary>📜 Full English Transcript (original, click to expand)</summary>

Welcome back everybody. The Mac, PC, Linux people reunite for our video where we now start to work with our project. Your environment is set up. You should be looking at Cursor looking nice and clean like this — X out of any windows that are open, have it look a bit like me. And then on the left here you've got the directories. The first one up here, 1_foundations, represents the directory for week one where we are right now. We open that up and I'd like you to click on lab one that comes up right here at the top. Here is a little section that tells you about the setup folder, which has all of the setup guide that by this point you should have already covered. And then the guides folder has a bunch of useful guides. It has some stuff to take you through intermediate level Python, and it also has beginner Python. If you're new to Python coding, then it will take you through some self-study guides there. If you're willing to do that, it will need some time investment but will be well worth it. And then for intermediate level Python there's important stuff there too. One of the things that comes up a lot in agents is working with async code — there's async stuff in there. There's also going to be things about generators, which are very important, and a lot of good intermediate level Python material. If you're also not as experienced with coding, there's going to be stuff about debugging, how to go about debugging. If you get something called a name error, there's a way to work out a name error. So there's good details on that too. So please do look at the guides — I've put tons of stuff in there. There's also a troubleshooting guide if things go wrong. Troubleshooting takes you through every step, including some great diagnostics at the end.

And then this next little comment here is saying that these labs — think of it a bit like an e-book. It's got content and information as well as things to try. And what you'll find is that what you'll see as we go through this may be different. What you have may look different to what I go through right now. And you may say, well, that's annoying, I wish it was all the same. But here's the thing — the reason is because I like to keep adding more stuff, make it current. I try and make it very clear when it's something new that I've added. I bring in extra information to keep it up to date, and when people struggle and they hit problems or they need something explained better, I can put that in there. And that means that everyone benefits from where some people have struggled or I haven't explained something well. So for me it's super important to do that. And the reason I don't come back and record all the videos as I do it — well, first of all, that would take a lot of time and I'd rather spend time getting this up to date. But also because that would erase some of the progress that people have made with videos they've watched, and it can be quite jarring if you're in the middle of a series and then the videos are changing under you. So it's really worked out better for me to keep these labs up to date as much as I can. So treat the labs like a resource. And the way that I suggest you work with me is: watch the video of me going through a lab — I'll go through it, I'll explain it, I'll execute things. I wouldn't necessarily suggest that you do it at the same time as me, because that's not really the point. The point is, as soon as I've done a lab, you come back and you go through it step by step yourself, and you use that as a way to build the learning, add in print statements and so on.

Okay, a couple more things. I'm using here things called notebooks, which are a particular type of Python code that's organized into cells. And there's a guide on how to use notebooks like this if you're not familiar with them. And I know that a lot of people from an engineering background initially get a bit frustrated like this because they'd rather work with just Python code. We will work with Python code as well — we're going to use both — but this kind of notebook has its place. It's very useful for research and development, which is an important part of being an AI engineer. And it's also great for learning because you can run things step by step, experiment, tweak, put in print statements, and learn. So even if you're not used to these kinds of notebooks, I promise you there's good stuff here too. And we will also do some Python coding using normal modules.

All right. Let's get to running this first lab. Okay. The first step is to go to the top right just here where you see select kernel. You click there and you have to choose your Python environment. And the way you do that is you type Python environments right here. And this first one up here with the star that says venv — it says recommended, and it's right in this directory. That is the one you want to pick. And hopefully that's going to come up really clear for you as Python 3.12 at the top. And once you've done that, it will be set up. And you'll always, when you come to a new lab, you'll need to do that, so do bear that in mind for it to work. And then as a final little thing here, it's got one more link to my LinkedIn in case you haven't succumbed by this point.

All right. So now what we do is we come here to the first of the cells. Each of these things are called cells, these code cells. And we're going to do an import. And what import are we going to do? Well, we're going to do this import here: from dotenv import load_dotenv. And cursor is already suggesting what we could do. I hope you're familiar with what it means to import a function from a module, but if not, please do check out the guides for a refresher. But I'm now going to run this code cell by simply pressing shift followed by return or enter. And that executes the cell, and it's done.

So the next thing we're going to do is use that function. And this is how we do it. We say load_dotenv, and I'm getting prompted already — there it is, override equals true. So what does this do? load_dotenv is just a utility function which does something very specific. It looks for a file with a very particular name in your project root directory, and that file name happens to be, as you probably guessed, the name .env. And it's assuming that that is where you're setting some of the environment variables that you want to use for this project. And it's just a utility that looks at that file, interprets it, and sets environment variables as a result. That's all it does. And override equals true is just a nice little trick to know about. By default, load_dotenv — if you've already got an environment variable set, perhaps with your profile — then that takes priority and it won't overwrite it. And that can be a nasty little gotcha, because if in the past you've set up an OpenAI API key and you've stored it somewhere global on your computer, that would take priority and you wouldn't be able to figure out why on earth OpenAI is rejecting your key. So it turns out that this was a common problem in the past, and I have learned to tell people to always put override equals true, which means that what's in the env file takes priority. And we run this by pressing shift enter. And now our environment variables will be set.

So let's check that. This next cell does an import os, and then we look for an environment variable that's called OPENAI_API_KEY, which is exactly what we named it in the env file. And if it exists, we're going to print it exists and give the first few letters. Otherwise it's going to say it's not set, please go to the troubleshooting guide. I press shift and enter to run this. And there we go — the OpenAI key exists. It begins sk-proj. All is good, and I hope all is good for you too. If not, go to the troubleshooting guide.

Okay. And now we have a super important import statement. And it looks like this: from openai import OpenAI. So if that seems weird to you, why is one in lowercase and one not — again, go to the guides, I'll explain the difference between classes and modules. But we are now going to execute this, and if this gives you any problems at all, then that might suggest a problem with your UV environment — troubleshooting guide. And always contact me if you get stuck. I'm here to unstick you.

All right. So what we're now going to do is create an instance of this class. Now I tend to always do it this way: openai equals OpenAI. And that can be a bit confusing to people because again, when we're using the same word OpenAI, the proper way to call this would be something like the OpenAI Python client, because what we're doing is creating an instance of the Python client library. But I just call that openai because it's simpler and shorter. We're creating an instance of that class, and let's run that right now. And it's worth bearing in mind that some people think that when you do this, you're creating something to do with the actual GPT large language model locally, but you're not. OpenAI is a lightweight library for connecting to OpenAI's endpoints on the cloud. So this is just what people sometimes call a client library. It's just a simple wrapper library around endpoints that calls HTTP endpoints to call the API that's running in the cloud. And that's all it is.

So with that, let's keep going. What we're now going to do is create a list called messages. And this is a format that I hope most of you are very familiar with. On my LLM engineering course, we do this one to death. Conversations with large language models are often represented in this format that OpenAI invented and has become ubiquitous everywhere: lists of dictionaries where each dictionary has a role and a content. And in this case we say the role is user, the content is this simple question: what is two plus two? So we run that, and now we're going to actually make a call to OpenAI and check everything is working okay.

And so now we're going to come here and type the code to call OpenAI. And cursor is going to make this very easy for us. We're just going to type response equals openai dot — and it's chat dot completions dot create. And you can see that cursor is already filling that in for us. I can just press Tab and it's going to complete that right away. And it's going to say the model is GPT-4o-mini, and the messages are messages. That's perfect. And it's also going to take the response, take the first choice dot message content, and print it. And that's exactly what we want to do. This structure of OpenAI is something that is so common these days. If you're new to it, then take a look. But people who are familiar with this will see this as a very simple way to call OpenAI. And if we run this, we get the response to the question what is two plus two? We get two plus two equals four. So we know we are connected to OpenAI, and so far so good.

So hopefully you're now comfortable that we can both call OpenAI, we can get responses, we can use the very standard chat completions API structure, and cursor will fill it in for us if we ever forget what it is. But now let's ask a harder question. It's time for us to be a little bit agentic. We're going to put one foot in the agent camp. It's more a workflow than an agentic AI, but still, it's getting there. We're going to ask a question: Please propose a hard, challenging question to assess someone's IQ. Respond only with the question. So that's going to be our question. And we're going to put that into the standard messages structure. And now we're going to ask it. So again we say response, and it's already filling it in for us. We press tab to complete that. But we're just going to change this slightly. We're going to make this question equals — so we're going to take what comes back and we're going to make it question. And then we'll just print the question. Cursor fills that in. Let's run that. And here we go, here we have a question from OpenAI: If a train leaves the station traveling at 60 miles an hour, another train at a different station 120 miles away at the same time traveling 90 — how far from the first station will the two trains meet? A nice brainteaser right there.

So what we're going to do now is we're going to take this question, and we're going to make a second call to an LLM to answer the question. And that's why I describe this as an agentic pattern, because it is making multiple calls. We are orchestrating multiple calls to LLMs to solve a bigger problem. And so it's going to be relatively easy. We're simply going to continue this by again making another messages — look at how cursor fills it in for us — messages with role as a user, and the content is that question. Great. Let's run that. And now we're going to ask OpenAI again. So we're going to say response is openai create. And again, cursor fills it all in, and it fills in the answer. And it's even clever enough to recommend that we call it answer instead of question. Honestly it's incredible. So this is exactly what we want to do. We're making the same kind of call to OpenAI's chat completions API, the simplest way to call OpenAI in the cloud. And we are now getting back the answer to the question, and we will print that answer. And I believe the answer we're looking for is 48, I think. Let's see. So we'll get that to print. And here we go, a bunch of information right here written with 48 at the end there. And you may recognize that this has come back in a form of markdown. It's got some markdown stuff in it, which LLMs love to talk in markdown. We can just add in a little code in here. from IPython.display import Markdown and display. And then the next line that cursor is telling us to write — I don't really have a job here, do I? display Markdown — but the only thing it's got wrong (thank goodness it got something wrong) is that what we actually want to display is the answer, not the question. So if we do that and we run this, then we see the answer formatted nicely. I'll let you read through its work, and it comes up with the conclusion of 48 miles.

So there we go. That is our first semi-agentic pattern, built just in a few minutes. If any of that was unfamiliar to you, check out the guides, play with it, look at it. And as I say, congratulations on getting here. But at the end of this lab there is an exercise. And I do encourage you to do the exercises. This is where you really get to show that you've done this. You may be thinking, okay, there wasn't much commercial about this project, and I do like to try and weave commercial angles in wherever I can to make this applicable to business. And so I've got an exercise for you to now make this applicable slightly to business. So we are going to try and ask an LLM, first of all, to pick a business area that might be worth exploring for an AI opportunity. Secondly, to identify a pain point in that business sector that it's decided on — one that it needs to explicitly explain, what is that challenge that might be ripe for an agentic solution. And then the third step will be to actually propose an AI solution to that problem. So I would like you, in this empty cell here, probably assisted by cursor, to go through and make this happen with three calls to LLMs. First of all, you put something in this message to explain that you want it to pick a business sector. Then you get back the response; based on that response, you read in the business idea, and then you will repeat these three steps in order to get the pain point, and then to get the AI solution, and print them all out. Print them in markdown if you wish, nicely formatted, and use that as a way both to experiment with some agentic workflows and also actually to get some commercial benefit — to get perhaps an interesting idea about a way that you can apply AI to a real business pain point. All right. I hope you enjoy that challenge. If you have any problems with it, then you can either get help from ChatGPT or cursor, or just drop me a note. And I will see you for the final lecture for this first day.

</details>

---
*Source: Official Udemy lecture transcript (auto-captions, lightly cleaned). Notes in Hinglish for self-study.*
