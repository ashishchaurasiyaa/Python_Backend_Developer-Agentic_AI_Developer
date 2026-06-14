# L12 — Day 3: Multi-LLM API Integration — Comparing OpenAI, Anthropic & Other Models

> **Week 1 — Foundations** · ⏱️ ~10m · 🎥 Lecture 12 of 131
> **Instructor:** Ed Donner · **Lecture ID:** 49771145

---

## 🎯 Ek Line Mein (TL;DR)

Lab 2 shuru — ek hi **OpenAI-style messages format** se **multiple LLM providers** (OpenAI, Anthropic, Gemini, DeepSeek, Groq) ko call karna seekhte hain, aur ek **multi-model orchestration pattern** banate hain jisme ek model question generate karta hai aur baaki models **competitors** ban ke usse answer karte hain.

---

## 📝 Hinglish Explanation (Detailed)

- **Lab 2 setup (Week 1, Day 3):** Cursor mein foundations folder ke andar **lab 2 notebook** kholte hain. Is lab ka goal — **bahut saare models ke saath kaam karna**.

- **Ed ka teaching style (controversial but practical):**
  - Ed live typing nahi karta kyunki usse **momentum slow** hota hai — wo cells ko **explain → run → inspect → print** karta hai.
  - Tumhara kaam: video dekho, phir **khud notebook run karo**, **print statements add karo**, cheezein **change/experiment** karo. Experimentation hi asli learning hai.

- **Community Contributions + career tip:**
  - Exercises complete karne ke baad apne changes **`community_contributions`** folder mein save karke **PR (pull request)** raise karo — dusre students ko benefit milta hai. Ed ke previous course mein **hundreds of PRs** aaye the.
  - **Apna GitHub repo** banao, projects showcase karo, **LinkedIn post** karo aur Ed ko **tag** karo — wo comment karke tumhara post **amplify** karega. Ye future **clients/employers** ka attention attract kar sakta hai.

- **Environment setup:**
  - Sabse pehle **imports run karo** (Shift+Enter) — warna **NameError** milega.
  - **`load_dotenv(override=True)`** — `.env` se environment variables load hote hain; `override=True` isliye taaki **existing/stale env vars priority na le lein**.
  - Ed ne **5 API keys** set ki hain (sab optional): **OpenAI**, **Anthropic**, **Google Gemini**, **DeepSeek**, **Groq**.
  - **Pricing notes:**
    - **Groq** — koi upfront minimum nahi, **pay-as-you-go**, bahut **cheap** — try karne ke liye best.
    - **DeepSeek** — **$2 upfront**, jo drawdown hota hai (Ed $2 bhi spend nahi kar paya).
    - **Gemini** — certain tiers tak **free**.
    - **OpenAI & Anthropic** — dono mein ~**$5 upfront** (US), though OpenAI ka koi naya deal chal raha tha.
  - Key-check cell run karo — keys ke **prefixes** verify hote hain. Agar koi key set nahi hai to "not set" aayega — **koi problem nahi**, bas us model ko call mat karna.

- **Is lab ke 2 objectives:**
  1. **Different LLM APIs** aur unke **messaging styles** ka feel lena (aage ke weeks mein bahut saare LLMs se baat karni hai).
  2. **Models ke beech orchestration** karna — pichle lecture wale **design patterns** ko practically dekhna.

- **Step 1 — Question generation (LLM se hi sawal banwana):**
  - Ek **request** banate hain: *"Please come up with a challenging, nuanced question that I can ask a number of LLMs to evaluate their intelligence. Please answer only with the question, no explanation."*
  - Isse standard **OpenAI message format** mein daalte hain: **list of dicts** — `[{"role": "user", "content": request}]`.
  - **System message kahan hai?** — System message **optional** hai. Agar default behaviour ("you are a helpful assistant" type) hi chahiye to bina system message ke bhi perfectly kaam karta hai.
  - `OpenAI()` client banao → **`chat.completions.create()`** call karo with **`gpt-4o-mini`** (cheap model) → response se **`choices[0].message.content`** nikalo → variable **`question`** mein store karo.
  - Result: GPT-4o-mini ne khud ek tough question banaya — *"AI in predictive policing ke ethical implications — bias, accountability, societal impact"* — kaafi nuanced sawal!

- **Step 2 — Competition setup (orchestration begins):**
  - Do empty lists banate hain: **`competitors`** (model names) aur **`answers`** (har model ka jawab).
  - Naya `messages` banate hain — wahi list-of-dicts format, content = **GPT-4o-mini ka generate kiya hua question**.
  - Pehla competitor: **GPT-4o-mini khud** — apne hi sawal ka jawab dega!
  - Pattern: `model_name` set karo → `create()` call → answer extract → **`display(Markdown(answer))`** se pretty render (models **markdown mein respond** karna pasand karte hain) → model name `competitors` mein append, answer `answers` mein append.
  - GPT-4o-mini ne **robust, well-structured markdown answer** diya — categories, sections, conclusion ke saath.

- **API memorize mat karo, instinct banao:** Cursor autocomplete se API fill ho jayega, lekin **chat completions API ka shape** (client → create → model + messages → choices[0].message.content) tumhe **intuitively** aana chahiye.

- **Next:** Ab dusre providers (Anthropic etc.) ke APIs pe move karenge — wahi question, alag-alag models.

---

## 🔑 Key Concepts / Important Terms

| Term | Simple Hinglish Meaning |
|------|--------------------------|
| **Multi-LLM Integration** | Ek hi code pattern se alag-alag providers (OpenAI, Anthropic, Gemini, DeepSeek, Groq) ke models ko call karna |
| **Chat Completions API** | OpenAI ka standard API — `client.chat.completions.create(model=..., messages=...)` → `choices[0].message.content` |
| **Messages format** | List of dicts — `[{"role": "user", "content": "..."}]` — har LLM call ka standard input shape |
| **System message (optional)** | Model ko persona/instructions dene wala message — default "helpful assistant" behaviour ke liye zaroori nahi |
| **`load_dotenv(override=True)`** | `.env` file se API keys load karna; `override=True` se stale env vars override ho jaate hain |
| **Orchestration** | Ek LLM ka output dusre LLMs ka input banana — yahan: ek model question banata hai, baaki answer karte hain |
| **Competitors / Answers lists** | Multi-model comparison ke liye accumulator lists — model names aur unke answers track karne ke liye |
| **Groq** | Fast inference provider — no upfront minimum, pay-as-you-go, sasta — beginners ke liye ideal |
| **Community Contributions + PR** | Apne experiments course repo mein PR karke share karna — portfolio + visibility |
| **`display(Markdown(...))`** | Jupyter mein LLM ke markdown response ko render karke dikhana (raw print se better) |

---

## 💡 Backend Dev Ke Liye Note (aapke liye)

- **OpenAI messages format = de-facto wire protocol.** Jaise REST/JSON har language ka lingua franca ban gaya, waise hi `[{"role": ..., "content": ...}]` LLM world ka standard hai — DeepSeek, Groq, Gemini sab **OpenAI-compatible endpoints** dete hain, matlab sirf `base_url` aur `api_key` swap karke same client reuse hota hai (classic **adapter pattern**, but provider ne hi adapter de diya).
- **Orchestration pattern = pipeline/fan-out jo tum queues ke saath karte ho.** Ek model ka output (`question`) dusre calls ka input banta hai — bilkul jaise ek service ka response downstream services ko fan-out karna. `competitors`/`answers` lists yahan ka poor-man's result aggregator hain.
- **`load_dotenv(override=True)` ka backend analogue:** config precedence bugs — shell mein purani `OPENAI_API_KEY` export padi ho to bina override ke wahi pick hogi. Wahi 12-factor config hygiene yahan bhi apply hoti hai.
- **Hands-on lab:** is lecture ka code khud chalane ke liye ye lab run karo — `Practical/lab2_multi_model_judge.py` (`uv run` se chalega, **Groq-free** setup).

---

## 🧠 Takeaway (yaad rakho)

1. **Ek hi messages format** (`role`/`content` dicts) se lagbhag saare LLM providers se baat hoti hai — ye shape muscle memory bana lo.
2. **System message optional hai** — default assistant behaviour ke liye sirf user message kaafi hai.
3. **Sab API keys set karna zaroori nahi** — Groq sasta/no-minimum hai, Gemini free tier hai; jo key nahi hai us model ko skip karo.
4. **Orchestration ka core idea:** ek LLM ka output dusre LLM ka input — yahi agentic workflows ki foundation hai.
5. **Experiment karo aur PR bhejo** — watch → run → modify → community contribution; ye learning bhi hai aur portfolio bhi.

---

<details>
<summary>📜 Full English Transcript (original, click to expand)</summary>

So here we are, back in Cursor. A great place to be. So on the left is our directory structure. I open up the foundations folder and I'm going to go to lab two which is what we're doing right now. Welcome to the second lab week one. Day three. We're going to work with a lot of models. Now let me start with just some quick points. First of all, I want to mention that the way that I like to do this, the way that that I collaborate with you may be different to some other courses that you've taken. And it's something that is a bit controversial. Some people like it, some people don't like it, and I hope that you'll get used to it. Typically, I don't like to just sit here typing code because I feel like that slows down the momentum. Rather, I look at cells, I explain what they do, I run them, I inspect them, I print them, and that's what I recommend you do as well. Watch while I go through this and explain it, and then come back afterwards and run it yourself. And then add in print statements. Change things. Experiment. It's all about experimentation and that's what you should be doing. So for people that would prefer it if I, if I sat here typing, I'm sorry, I will try and do it from time to time. I'm going to do it right here. I will do it occasionally, but most of the time I'm going to explain what I'm doing and I hope you'll get used to that. And you'll see that there are pros and cons of everything, but that's the way I like to do it.

Now, one thing I will really, really encourage you is written here that that once you've gone through this and made some changes, done the exercises, perhaps it would be fabulous if you were willing to save your changes in the folder called Community Contributions and raise a PR or a pull request for me to merge that into the repo so that other students get to benefit from this as well. To my great joy for my other course, there have been hundreds of PRs. There are tons of examples from people like you taking the course and submitting what they do with all sorts of fun and interesting examples, and it's been a real joy to see. And it's also been valuable for other students to experiment with, with people's contributions. So it's a fabulous thing to do. I really encourage it. In addition to that, something which is a good career thing to try is it's good if you have your own GitHub repo, and as you work on different projects, put some of your own stuff there as well. Showcase the work that you're doing. And if you put a post on LinkedIn to talk about some of the projects that you've worked on or some of the things you've done or what you've learned from it, and you tag me on it so that I get a notification in LinkedIn. Then when I see that, I'll come in and I'll weigh in and I'll make sure that I post something there as well. And that amplifies what you're doing. It means that it goes out to all the other people I'm connected with on this course, and people can then weigh in with their thoughts too. And it helps to draw attention to this, the skills you're acquiring, your expertise and your examples. And that's the kind of thing that that might attract the attention, perhaps, of a future client of yours, someone that might contact you for some business and potentially even a future employer as well. So it's a great thing to do. I strongly encourage it, and I'll be here to amplify the work that you do.

Okay, let's get on with it. So it begins, of course, with some imports and I press Shift+Enter to run these imports. Be sure to run the imports or you will get name errors. Okay. So always remember to do this as the comment what is that. Well it is of course doing a load to bring in the environment variables. And you remember that I like to have override is true to avoid any existing environment variables taking priority. So that has happened. So now that that's run, what we should find is that we've got a bunch of environment variables. Now I've been I've been quite greedy and I've set up a bunch of different APIs. And I don't expect you to do the same, but should you wish to, here are all of the APIs that you could set up. And I have done so and I have enjoyed it. OpenAI, Anthropic, Google's Gemini, DeepSeek, and Groq. It's worth mentioning Groq as when I did it at least doesn't have like an upfront a minimum. You only pay for what you use and it's really cheap, so this is a good one to try. DeepSeek has a $2 upfront. At least it did for me. And then you draw down against that $2 and I haven't been able to spend $2. Gemini is free for within certain tiering. And Anthropic and OpenAI both require an upfront, which I believe is $5 in the US for both. Although OpenAI appears to have a new deal right now, which I don't know how long that will last for, but you could always go and check it out. So this code here will load in the environment variables and just check that these keys look right if you're using them. And when I run this it gets this print here. And you can see that I've got keys that look like they should look or with the right kinds of prefixes. And if you run this cell and you haven't set up some of these keys, you'll get you'll get some sort of not set. But don't worry about that. Just don't don't call that particular model okay.

And now to get started, we're going to make a bunch of different calls to LLMs. And there's two objectives for this. One of them is just to show you the different kinds of APIs, the different style of messaging that we have with with different LLMs. So you get a sense of it, because we'll be talking to lots of LLMs over the next few weeks, and the other is to do some orchestration between models. A few of the design patterns that we talked about last time to see how that works out. So the first thing we're going to do here is we have a question. We're going to have a request. Please come up with a challenging, nuanced question that I can ask a number of LLMs to evaluate their intelligence. Please answer only with the question. No explanation. So that's going in a variable called request and into a variable called messages. We're going to have this standard OpenAI construct role is user. The content is going to be this request that we have right here. So in fact what I'm going to do is I'm going to add another code cell here. Let's run this. And I'm just going to print messages. Just so you see this, just in case it's not completely clear to you. It's a list of dictionaries role user content. And there's the content. Now, people who've been on my prior course or generally know about these things might be wondering why there isn't a system message. Well, we often do do talk about the need for a system message and a user message, but system messages are optional. You don't need one, particularly if it is a kind of standard. You are a helpful assistant then. Then you don't need to say it. It will work perfectly well without it, as you will see.

Let's give it a try. We're going to to use the same API structure that we did last time that hopefully most of you are pretty familiar with, and that Cursor will just fill in for you if you start typing this. Anyway, we create a new instance of the OpenAI Python client library and we call OpenAI create. We pass in the model, we're going to use the cheap GPT-4o mini. We pass in this list of dicts, and we get back and we ask for the choices zero message content, and we'll print it, and we're putting it in a variable called question. Let's see what we get. So how would you analyze the ethical implications of using AI in predictive policing? Wow. Considering factors such as bias, accountability and societal impact that is a good question. Goodness. Wow. Okay, that's a hard question for sure. This is going to be an interesting challenge. We will see what happens next okay.

So what I'm going to do next is I'm going to first set up an empty list called competitors list that we will be filling up with different names of competitors. And I'm then going to have another list which I'm going to call answers. And that's going to be where we will fill up different answers from different LLMs answering this question. And then we will put together the, the messages that we're going to to, to say to them. And I love the way Cursor does this, but this is exactly what we want. We want a list of dicts role is user. The content will be this question, the exact question that GPT-4o mini just asked us. Okay, we're now going to go through and I need to remember to run that cell. We'll run that cell and we will go through and ask some models. And why not start with the same model that came up with the question? We will start by asking GPT-4o mini its own question. So this is what we do. We're going to have a variable model name which we will put GPT-4o mini in. And then we will say response is OpenAI create that standard API. We pass in the model name. We pass in the messages that we've got right here. And then we take back the answer choices zero message content. We will print that answer. Let's do better than than print it. Let's use markdown instead. So we'll say display markdown answer so that we get to see it in a nice format. Because, you know, these models love to respond in markdown. And then we will add GPT-4o mini to our competitors. And we will add that answer to our list of answers. Sound good? Let's give this a try. So it's running while it's running. Take a look. And and whilst you should never need to memorize these APIs because it will always fill it in for you, it's good to have an instinct for what this API looks like. The chat completions API.

All right, so here came the response. It was of course in beautiful markdown. And you can see it's a I am not going to read it through now. Live with you. But it looks like it's a pretty robust answer that has good categories and a bunch of different sections and a conclusion. The ethical implications are complex and multifaceted. Okay. Fair enough. That's good. That's GPT-4o mini. We will now move on to another API.

</details>

---
*Source: Official Udemy lecture transcript (auto-captions, lightly cleaned). Notes in Hinglish for self-study.*
