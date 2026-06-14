# L03 — Day 1: Agent Engineering Setup (Cursor IDE, UV & API Options)

> **Week 1 — Foundations** · ⏱️ ~12 min · 🎥 Lecture 3 of 131
> **Instructor:** Ed Donner · **Lecture ID:** 49770323

---

## 🎯 Ek Line Mein (TL;DR)

Coding shuru karne se pehle ka **setup + expectations** lecture: ye course har level ke liye hai (non-coder se agent engineer tak), tools honge **Cursor IDE + UV**, aur API costs ka honest breakdown (Ed ne **poore course mein <$5** kharch kiye — ya Ollama/Gemini se bilkul free bhi kar sakte ho).

---

## 📝 Hinglish Explanation (Detailed)

### 1. Ye course kiske liye hai? (poora spectrum)
Ed kehte hain course **har level** ke liye design kiya hai:
- **Bilkul naye (non-coders):** challenging hoga, patience chahiye — par **guides folder** (repo install karne pe milega) se foundational skills build karke aage badh sakte ho.
- **Python coders / AI engineers (beech wale — yellow boxes):** aapke liye **best fit**. Sabse zyada maza aayega. *(👈 aap yahan ho)*
- **Experienced agent engineers:** kuch basic parts speed-up kar sakte ho, par **advanced material aur projects** pe focus karo — wahi asli action hai.
- Ed ka pichhla **"LLM Engineering"** course complementary hai (prerequisite nahi). Liya hai toh bonus, nahi liya toh bhi chalega.

### 2. Tools: Cursor + UV
- **Cursor (IDE):** AI-powered IDE, **VSCode pe built**, LLMs se powered. Bahut productive. Ye course ka main editor.
- **UV (package/environment manager):** Anaconda ka replacement (jo pichhle course mein tha). Virtual environments pe built, **bahut fast, simple, "just works"**.
  - Rust mein likha hua hai 🦀 (isliye fast).
  - Itna popular ho gaya ki **zyaadatar agent frameworks (jaise CrewAI) UV ko core mein use karte hain**.
  - Anaconda jaisa heavy nahi — basically `venv` jaisa hi, par better.

> 💡 Aap already UV use kar rahe ho (`my-agentic-ai-project` mein `uv.lock` + `.python-version` hai), toh ye step aapke liye familiar hai. ✅

### 3. API Costs — honest baat
Course frontier models (OpenAI, DeepSeek) ko call karta hai — **paisa lagta hai**, par **aapki marzi**:
- **Paid (cheap):** Ed ne **poore course mein < $5** kharch kiye. OpenAI pehli baar **$5 minimum upfront** maangta hai (pay-as-you-go). DeepSeek itna sasta ki kharch karna mushkil.
- **Free options:** **Gemini** (abhi free tier hai), ya **Ollama** se **open-source models bilkul locally free**.
- **Trade-off:** free/local models slow ya kam coherent (jaise llama 3.2) — Ed jaise frontier results nahi milenge. Aap free mein chala ke dekho + Ed ko frontier pe dekho.
- Week 6 mein ek **real-time market data provider ($20)** optional hai — free alternatives bhi hain.
- **Mindset:** API charges "nickel-and-diming" lagte hain, par yaad rakho inference mein **trillions of floating-point calculations** chalte hain — heavy compute, margins patle. Ek gamer box jo bade models chalaye = hazaaron dollar. Toh ye pricing context mein samajhdari hai. **Aur agar nahi kharchna, toh kuch bhi spend kiye bina course poora kar sakte ho.**

### 4. Teen cheezein yaad rakho
1. **Resources:** course ki website (links + YouTube extras), **GitHub guides** (skill-specific + troubleshooting), aur **labs** (har `git pull` pe fresh content — living resource).
2. **Patient raho:** roadblock aaye toh wo **best learning opportunity** hai. "Kyun nahi chal raha" figure-out karna hi asli seekh hai.
3. **Contact karo:** email ya LinkedIn — Ed super-responsive hain. LinkedIn pe apne projects post karke unko tag karo → wo amplify karenge → future employers/clients tak pahunchega.

### 5. Aage kya
Ab environment setup hoga: **agle video PC (Windows) ke liye**, uske baad **Mac + Linux** ke liye. (Linux waale Mac waala video dekhein.) Fir sab fully-built environment ke saath wapas milenge.

---

## 🔑 Key Concepts / Important Terms

| Term | Simple Hinglish Meaning |
|------|--------------------------|
| **Cursor** | AI-powered IDE (VSCode pe based) — is course ka editor. |
| **UV** | Fast Rust-based Python package + venv manager. Anaconda ka modern replacement. |
| **Frontier models** | Sabse capable LLMs (OpenAI GPT, etc.) — best results, thoda paisa. |
| **DeepSeek** | Bahut sasta frontier-ish model — cost bachane ke liye. |
| **Ollama** | Open-source models **locally + free** chalane ka tool. |
| **guides / labs folder** | Repo ke andar learning guides + troubleshooting + updatable lab notebooks. |

---

## 💡 Backend Dev Ke Liye Note (aapke liye)

- **UV aapke liye naya nahi** — project mein already use ho raha hai. Bas confirm karlo: `uv sync` / `uv run` flow. Anaconda bhulne ki zaroorat nahi padegi.
- **Cost-wise:** aap Groq/Gemini free tiers se kaafi kuch kar sakte ho (aapke `main.py` mein already `ChatGroq` use ho raha hai). OpenAI ka $5 sirf tab jab specifically OpenAI features chahiye.
- **Pro tip:** as a working dev, "guides folder" skip karke seedha projects pe jaa sakte ho — par Ed ke **troubleshooting guides** bookmark kar lena, environment issues ke time bachayenge.

---

## 🧠 Takeaway (yaad rakho)

1. Course **har level** ke liye — aap (Python dev) ke liye sweet spot.
2. Tools: **Cursor (IDE) + UV (env manager)**.
3. APIs optional kharcha — **< $5 total**, ya **Ollama/Gemini se free**.
4. **Patience + community (LinkedIn)** = course ka hidden value.

---

<details>
<summary>📜 Full English Transcript (original, click to expand)</summary>

So please humor me. I've got a couple more admin things before we get into action. So I wanted to talk about how I've positioned this course and whether it's right for you. You may be new to coding — someone that's never written a line of code before. You might be someone that already considers yourself an agent engineer. Those are the two extremes. Or you might be in the middle — you're already a Python coder or you are an AI engineer. Maybe you're even someone that's taken my LLM engineering course, in which case, thank you and welcome. But I'm here to tell you that this course is designed to appeal to everyone across that entire continuum. There is something here for everyone. The people in the yellow boxes in the middle — you're going to have the best time with this. It's most well positioned for you, that is for sure.

For the people that are new to coding, it's going to be challenging. There's no doubt you're going to have to have a lot of patience, but this course is okay — you'll be able to get there and build amazing things. For someone who's already an agent engineer that's built some agent platforms before, you may want to speed through some of this, but I've made sure that there's advanced material covered too. We're going to be doing some really interesting things at every point and building some great projects too.

So I'm here to say: if you're new to coding, take some time with the guides that I've written. You'll find them in the guides folder when we install the repo. I've used that as a way to build up your basic, your foundational expertise so that you can hit the ground running. For Python coders and particularly for AI engineers — if you've taken the LLM engineering course, it's perfect, then you're going to have a great time. And for agent engineers, focus on the projects. That's when we really put things into action. I'm really proud of the projects we've built.

And for anyone that hasn't taken the LLM engineering course, I'll be sure to put links to it in the course resources. And it's something that I really do see as complementary, and it's not necessarily a prerequisite to this course. You can come into this course without having taken it for sure, but if you have taken it, you will be really well equipped for this course because it builds up a lot of depth of expertise in terms of what it means to choose and apply LLMs to solve problems.

So in just a moment, we're going to be starting to code. I know you're antsy. I know you're waiting for this. "Can't he stop talking and get to it?" We will be. But I do want to tell you that the first thing we're going to have to do is set up your environment. And setting up an environment — a big data science environment at the frontier of what's possible — it can be a bit of a painful process. I'm here to help. I'm here to make it go smoothly. But please do have something of a thick skin for knowing that you may hit some challenges. We'll figure them out. We'll get them fixed. We'll get you up and running.

This time, though, we're going to be helped out by a couple of really great friends in the form of the platform Cursor, which we'll be using as our IDE. And I just love Cursor. Cursor, of course, is the AI platform that's powered by LLMs that allows us to be so productive, and it's built on VSCode, and it's just great. So it's going to be a lot of fun working with that. But perhaps more specifically for building the environment, we're going to be using this product called UV, which you can think of as something which is replacing Anaconda that I used in the LLM engineering course. And it's built on top of using virtual environments. It's really fast and it's really simple and it just works. I am such a fan of UV. It's actually a student on the LLM engineering course that first drew my attention to it and said, this is what we should be using. And it was too late for LLM engineering, but it's not too late for this course. And it turns out that UV has become so popular that most of the agent frameworks that we'll be looking at already have UV at their core. Crew is, in a way, kind of like built with UV, as you'll see. So UV is really easy to use. It is nothing like Anaconda for people that have done this before. And it's basically very, very similar to using virtual envs, and you are going to love it. So I know it's always annoying to have to bring in something new to the mix, but it will be worth it. You're going to thank me for this. You're going to love UV. And it's written in Rust, and everyone loves things that are written in Rust. So there you go.

There's actually one more difficult conversation that we have to have, and it's about APIs. So look, this course does involve making calls to frontier models like OpenAI and DeepSeek. And they come at a price. There is a price point there. And I want to make the point that it is completely up to you. You can choose. I use both OpenAI and DeepSeek, but you can choose to only use DeepSeek throughout for a much lower cost. And Gemini you can also use, and right now Gemini has a free tier. I don't know how long that will last, but you can use Gemini for free for most of the course. You can also use Ollama completely free, just running open source models locally on your computer, no cost at all. But there are some trade-offs here. If you want to use any kind of good model, it will take a very long time. If you use the quick models like llama 3.2, then it might have troubles being coherent, and you certainly won't get to see the kinds of results that I'll be getting when I'm using the frontier models. But that allows you to have a sort of balance. You can run things locally for free and see one set of results, and you can watch me do it with the frontier models if you don't want to spend the API charges yourself.

So what are these API charges? Well, different countries might have different pricing. What I can tell you is that for me, running this entire course, I spent well under $5 on any of the LLM model costs. It's very cheap. OpenAI — the first time you use it, you need to put down at least $5 upfront, and you kind of pay as you go that you spend against. So that's annoying. So you might have to do that if you haven't done it before. But other than that, the actual amount that we'll spend will be relatively small, a matter of a few dollars. And it's very hard to spend very much on DeepSeek because it's so cheap. Now, I will say that in the last week I have an option to use a proper real-time market data provider that I use, and that cost me $20. But that's not necessary. There are free options as well, but if you get into it like I do, then you might do that.

And I just want to make the point at the end — people do get frustrated about API costs. There's something about them that are a bit galling, because it feels like everyone is sort of nickel-and-diming you. You're getting charged a little bit here, a little bit there, another API cost. And I understand that even though I say these things are very cheap, a few dollars, it adds up. And that's not always cheap. And particularly with exchange rates and different economies, that might be quite a burden. But I do want to make the point that you have to keep in mind what's going on. When we run inference on these large LLMs, there are trillions of floating point calculations going on. This is heavy machinery. And so it's not like these companies are just making extra cash off you. I'm sure they are quite profitable, but most of it — the margins are relatively slim because there's a lot of compute costs associated with running these massive models. And if you think of the price of buying a new laptop, or even a big gamer box that could actually run larger models itself, you'd be talking about thousands of dollars. So this kind of API pricing, while it can feel a little bit galling sometimes having to pay each of these different APIs, it is worth keeping in mind the context of what's going on behind the scenes. These companies need to pay their electricity bills. There's a lot of compute, and we're getting real value from what we use. So I don't know if that helps or not, but it gives you some context. Please do keep in mind you don't need to spend anything on APIs if you don't want to.

So there are three things for you to remember. The first of them is that there are resources that accompany this course, and they're really great. There's a website where I've put links, and I've got extra content in the form of YouTube videos that should be helpful. In GitHub, there's a whole section with different guides to teach different kinds of skills that you might need. And there's some troubleshooting guides in there too that will fix problems for you, and the labs. So the labs — I'm updating them all the time. You can think of them as an ongoing, fluid resource. Every time you do a git pull to get the latest, you'll get refreshed with new content. Maybe not every time, but most times, I'm trying to keep them to be a living, breathing resource for you.

Then remember to stay patient. Remember that if you hit problems, if you hit roadblocks, that's actually a great learning opportunity. Because figuring out what's going on, figuring out how to solve this, is one of the best ways to learn. Try and go with it. Try and enjoy it as much as you can. There's some juicy projects, and figuring out why they don't work first time — that's part of the fun.

And then the third point is that if all else fails, or even if nothing else fails, then contact me. I'm here. I love this stuff. I'm actually super responsive. If you email me or if you LinkedIn with me, then I'll respond very quickly. Unless I'm in a meeting or I'm traveling or something, or I'm asleep — for people in different time zones — I do tend to reply really quickly. People are always surprised. In fact, a lot of people think that I'm an AI agent when I reply. They're like, "do you have an agent of yourself?" But no, it's the real me. I will reply. I love getting questions. I love answering. So do feel free to reach out. Be in touch. I welcome ideas and thoughts and questions and whatever you got.

And by all means, if you're up for it, then LinkedIn with me. Some people don't feel comfortable doing that for some reason, but I'm very open to it. I love building a community of people in data science that can support each other — that can, if people are looking to hire someone or if they're looking for jobs, I can help connect people. So it's a really great way for me to build and contribute to the community. And this is really important. One of the things that people did from my last course is they would post projects that they've done and tag me on them, or things that they've done from the course, and I can then amplify it, because I can then jump in with some comments and make some observations or say how great it is they've done something, and that will then be available to all the other students from the course. You can weigh in as well. And this has really happened, and it allows you to share things and amplify them. And LinkedIn is a great place to do that. And it will be something that will be seen, perhaps by future clients of yours or perhaps by future employers of yours as well. So it's a really good thing to do. So I strongly encourage it — LinkedIn with me and share on LinkedIn. It's a great resource and I can't wait to see what you're doing.

So at this point, you've put up with half an hour of me yammering away. Finally, it's time for action. We're going to the lab. We're going to set up your environment. The next video is for PC people — we're going to have a video for PC setup, and then the video after that is for Mac people and Linux. You should probably join in with the Mac people; it'll be similar enough for you. And then we will reconvene on the video after that. So it's going to be PC, followed by Mac, followed by us all back together again with fully built environments. Let's do it.

</details>

---
*Source: Official Udemy lecture transcript (auto-captions, lightly cleaned). Notes in Hinglish for self-study.*
