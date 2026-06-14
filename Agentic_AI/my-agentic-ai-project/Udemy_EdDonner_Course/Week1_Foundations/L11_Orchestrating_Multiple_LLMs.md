# L11 — Day 3: Orchestrating Multiple LLMs — GPT-4o, Claude, Gemini & DeepSeek

> **Week 1 — Foundations** · ⏱️ ~10m · 🎥 Lecture 11 of 131
> **Instructor:** Ed Donner · **Lecture ID:** 49771139

---

## 🎯 Ek Line Mein (TL;DR)

Day 3 ka focus hai **multiple LLMs ko orchestrate** karna — **GPT-4o mini**, **Claude 3.7 Sonnet**, **Gemini 2.0 Flash**, **DeepSeek**, **Groq** aur **Ollama** — yaani ek hi workflow mein paid cloud APIs aur free local open-source models, dono ko call karna seekhna.

---

## 📝 Hinglish Explanation (Detailed)

- **Day 3 ka agenda:** Ab tak humne pehla agentic workflow banaya aur design patterns dekhe. Aaj practical day hai — hum **bahut saare LLMs ko call** karenge aur unke beech **orchestration** karenge.

- **Flexibility upfront:** Ed dono tarah ke models use karega:
  - **Paid APIs** (cloud mein) aur **open-source models** (cloud + locally).
  - Aap **completely free** mein bhi course kar sakte ho — sab kuch **local models** se possible hai, bas performance vary karegi. Ed ke paid-model results dekh ke compare kar sakte ho ki free open-source models se kya achieve hota hai.
  - Model selection/deployment ki deep theory is course mein cover nahi hogi (uske liye Ed ka **LLM Engineering course** hai) — yahan assume kiya gaya hai ki aapko closed vs open source ka basic sense hai.

- **Cast of characters — jo models hum use karenge:**
  - **GPT-4o mini** (OpenAI) — sabse zyada use hoga, already 2 calls mein use kar chuke hain. **GPT-4o** iska bada cousin hai.
  - **Reasoning models (o1, o3-mini)** — ye models trained hote hain **steps think through** karne ke liye, ek **agentic-like internal workflow** mein. Key insight: LLM ko apne steps sochne ko bolo toh **much better outcomes** milte hain. Course mein kabhi-kabhi dekhenge, par mostly GPT-4o mini hi rahega.
  - **Claude 3.7 Sonnet** (Anthropic — OpenAI ke ex-logo ne start ki thi company) — Ed ka main Claude model. Cheaper option chahiye toh **Claude 3 Haiku**, though Sonnet bhi fairly cheap hai.
  - **Gemini 2.0 Flash** (Google) — Pro version bhi hai, par Flash use karenge. **Abhi Flash certain usage limits ke andar FREE hai** — agar bina paise diye frontier model chahiye toh Gemini best path hai.
  - **DeepSeek** — Chinese startup jisne **V3 aur R1** se sabko shock kiya. Important nuance:
    - Sensation isliye nahi tha ki model **strongest** tha (wo OpenAI ke latest se thoda peeche tha)...
    - ...balki isliye ki unhone **training techniques** itni powerful banayi ki **~30x kam spend** mein OpenAI-comparable performance mil gayi. **Wahi asli innovation thi.** Plus model **open-sourced** hai.
    - Main model **671 billion parameters** ka hai — kisi ke laptop pe nahi chalega. Par **distilled versions** available hain — ye actually **Llama aur Qwen** ke smaller models hain jo bade DeepSeek ke generated data pe **fine-tuned** kiye gaye hain. Ye free mein use ho sakte hain.
  - **Grok vs Groq — confusion alert:**
    - **Grok (with K)** = X (formerly Twitter) ka model. Aaj ke lab mein nahi, par baad mein shayad use ho.
    - **Groq (with Q)** = ek company jo **super-fast, super-cheap inference** provide karti hai open-source models ke liye — jaise **Llama 3.3 70B** aur **DeepSeek variants**. Hum Groq use karenge.
  - **Ollama** — ek **local platform** jo aapke computer pe **OpenAI-jaise consistent endpoints** expose karta hai. Andar se ye open-source models ko **llama.cpp** (high-performance optimized C++ library) se locally run karta hai. Yaani local API call → local model inference.

- **Leaderboards — Ed ka favorite topic:** (Jon Krohn ne podcast pe Ed ko mazak mein "leaderboard" hi bula diya tha 😄)
  - **Vellum leaderboard** strongly recommended — closed + open source models **side by side compare** karta hai:
    - **Costs** (input/output tokens ke hisaab se calculate kar sakte ho)
    - **Context window size**
    - **Key benchmark results** multiple dimensions pe
  - Isse **bookmark** karo aur har naye API ke saath cost/capability gauge karne ke liye use karo.

- **Resources + thick skin reminder (first lecture ka double-down):**
  - Course resource page (videos + links), **GitHub repo** (guides + troubleshooting) available hai.
  - Ed **labs continuously update** karta rahega — naye models aate hi labs refresh honge, toh video ek story hai, labs latest story.
  - **Roadblocks aayenge — guaranteed.** Par **real learning debugging mein hoti hai** — diagnose karo, figure out karo, fix hone pe super satisfying lagega.
  - Stuck ho toh Ed ko **LinkedIn/email** pe contact karo — wo responsive hai.

- **Pro tip — manual agentic workflow for debugging:**
  - Difficult question ho toh **ChatGPT aur Claude dono** se poochho.
  - Phir ek model ka answer doosre ko de ke bolo: *"Do you agree? Is this accurate?"* — yaani doosra model **evaluator** ban gaya.
  - Ye literally **Evaluator-Optimizer pattern** hai (jo pichhle lecture mein dekha tha) — bas **manually** kiya hua. Stuck hone pe great technique.

- **Closing:** Preamble done — ab next lab ka time hai.

---

## 🔑 Key Concepts / Important Terms

| Term | Simple Hinglish Meaning |
|------|--------------------------|
| **Orchestrating LLMs** | Ek workflow mein multiple models ko call karna aur unke outputs ko coordinate karna |
| **GPT-4o mini / GPT-4o** | OpenAI ke models — mini course ka default workhorse, 4o bada cousin |
| **Reasoning models (o1, o3-mini)** | Models jo answer dene se pehle steps think-through karte hain — better outcomes |
| **Claude 3.7 Sonnet / 3 Haiku** | Anthropic ke models — Sonnet main, Haiku cheaper option |
| **Gemini 2.0 Flash** | Google ka model — usage limits ke andar abhi free |
| **DeepSeek V3 / R1** | Chinese open-source models — ~30x kam training cost mein OpenAI-comparable performance |
| **Distilled models** | Bade DeepSeek ke data pe fine-tuned chhote Llama/Qwen models — free, locally runnable |
| **Grok (K) vs Groq (Q)** | Grok = X/Twitter ka model; Groq = fast/cheap inference platform for open-source models |
| **Ollama** | Local platform jo OpenAI-style endpoints deta hai, andar llama.cpp se models chalata hai |
| **Inference** | Trained model se runtime pe predictions/outputs lena (training nahi) |
| **Vellum leaderboard** | Website jo models ke costs, context windows aur benchmarks side-by-side compare karti hai |
| **Evaluator-Optimizer (manual)** | Ek model ka answer doosre model se verify karwana — pattern ko manually apply karna |

---

## 💡 Backend Dev Ke Liye Note (aapke liye)

- **Ollama = local mock server with production contract:** Jaise aap WireMock/localstack se AWS APIs locally simulate karte ho, Ollama OpenAI-compatible REST endpoints `localhost` pe expose karta hai. `base_url` swap karo aur same `openai` SDK client local model pe chal jaata hai — **adapter pattern** at the HTTP layer, zero code change.
- **Groq vs self-hosting trade-off** wahi hai jo managed RDS vs self-managed Postgres ka hai: open-source model (Llama 3.3 70B) ka weight free hai, par inference infra (GPU, batching, latency) Groq jaise provider ko outsource karna often cheaper + faster hota hai than DIY.
- **Vellum leaderboard ko capacity-planning sheet ki tarah treat karo** — model choice = instance-type choice. Input/output token pricing × expected traffic = monthly bill estimate, bilkul jaise aap EC2 sizing karte ho. Context window = max request payload size.
- **Multi-model evaluator trick = code review by a different team:** ek LLM ka output doosre vendor ke LLM se validate karwana correlated-failure risk kam karta hai — same reasoning jaise aap multi-AZ/multi-vendor redundancy design karte ho.
- 🧪 **Hands-on lab:** is lecture ka code khud chalane ke liye ye lab run karo — `Practical/lab2_multi_model_judge.py` (`uv run` se chalega, Groq-free).

---

## 🧠 Takeaway (yaad rakho)

1. Day 3 = practical orchestration — **multiple LLMs** (paid + free, cloud + local) ko ek saath use karna; aap **100% free** path bhi choose kar sakte ho.
2. Cast: **GPT-4o mini** (default), **Claude 3.7 Sonnet**, **Gemini 2.0 Flash** (abhi free), **DeepSeek** (open-source, 30x cheaper training), **Groq** (fast inference), **Ollama** (local).
3. **Grok (K)** = X ka model; **Groq (Q)** = inference platform — confuse mat karna.
4. **Vellum leaderboard** bookmark karo — costs, context windows, benchmarks ek jagah.
5. Stuck ho toh **2 models se cross-check** karo (manual Evaluator-Optimizer) — aur yaad rakho, **real learning debugging mein hai**.

---

<details>
<summary>📜 Full English Transcript (original, click to expand)</summary>

Well, hello. I'm back. And you're back too, which is a great thing. It means it's time for us to start day three of our journey together. And day three, we've already done building an agentic workflow for the first time. And we've talked about patterns. And now we're going to talk about orchestrating between LLMs and many of them. So this is going to be a practical day. You'll be pleased to hear. It's about time we got some more coding. And we're going to be calling a lot of LLMs.

And I just want to of course, say a few things up front. We're going to be calling both paid APIs and also open source models, and we're going to be calling them both in the cloud and also open source models locally and doing it throughout this course. And I want to be clear that you have complete flexibility to decide which models you pick, at which point I'm going to have coded it one way, but a great exercise is to take what I've done and apply it to other models. And if you don't want to spend a dime, you don't need to. You can do this all using local models. Although performance might vary, you can see the results I get from the models I use, and try and see what you can achieve with free open source models as well. And if you want more information on what it's like to select models, whether they're open or closed source, apply them and deploy them, then you should take a look at my other course. We're not going to be covering that in detail here, because otherwise I feel like it's going to be too much of a of a rabbit hole and we'll get distracted. So I'm assuming you're coming into this knowing about the different kinds of models and having a sense of what makes sense for closed source, open source, and so on. If you don't have that, you can either just go along with it, just just sort of pick it up as we go. Or of course, you could always turn to look at my other course, or I'll try and put some more background information in the guides as well, because that won't be required. You can just just go, go with the flow in terms of how we pick models.

So let's talk about the cast of characters, the different models that we're going to be experiencing now. So the first model needs no introduction really. It is of course, the model GPT-4o mini from OpenAI. We've already used it in a couple of calls. It's for sure the most well known of the models out there. And of course, there's also GPT-4o, the bigger cousin of GPT-4o mini. And then there are the reasoning models, which are models that have been trained to think through their steps in an agentic like way, in like a workflow of thinking through the different steps before they arrive at their conclusion. Because it turns out that when you ask an LLM to think through its steps, you get much better outcomes. So we may take a look at some point at o1 and o3-mini, but it's less essential for this course. Most of the time we're going to be sticking with GPT-4o mini.

Now, OpenAI's great rival, of course, their competitor is Anthropic. That was actually started by a couple of people from OpenAI originally, and we'll be looking at some of their models. But Claude 3.7 Sonnet is the model that I will spend most time on. And if you want to have a cheaper version, you can go with the Claude 3 Haiku, which is significantly lower cost. But Sonnet is also fairly cheap.

For Google, we're going to be using Gemini 2.0 Flash. There is also the Pro version of that too, but I think we'll stick with Flash. And as of right now, Flash is actually free, at least as long as you use it within certain usage limits. I don't know how long that will be the case for, but by all means, if you want to use an open frontier model without paying for it, then Gemini might be your path. Do look into that.

DeepSeek. DeepSeek, of course, is the Chinese upstart startup that shocked us all by coming up with such a powerful model in the form of DeepSeek V3 and R1. And it's important to understand that what made DeepSeek so sensational was not necessarily that their model was the strongest in the world, because it wasn't. It was slightly behind the latest from OpenAI, but that they developed such powerful techniques to train DeepSeek to be that good, that it cost them a fraction of the spend that OpenAI had spent to train GPT-4o and train o1. DeepSeek was able to achieve very similar performance, pretty much comparable at a fraction. I think it's like 30 times less spend. That was the true innovation. That's the remarkable thing about DeepSeek. And also that they open sourced the model so that you can use it. But the major model has 671 billion parameters, which means it's far too big for anyone to run that on their computers. But there are versions of it, small versions of it called the distilled versions, which are in fact themselves just smaller models. They're versions of Llama and Qwen, two different models that have been fine tuned on data generated by the big DeepSeek, and those smaller distilled versions of DeepSeek are for sure available free of charge.

Grok. We will also be using Grok, and there are two Groks. Confusingly, if you don't know this, Grok spelt with a K at the end is the name of the model that comes from the company formerly known as Twitter. Now X. X's is Grok, and we might use Grok with a K at some point as well. Not in today's lab, but Groq with a Q is something different. Groq with a Q is a company that has come up with a really cheap, fast way to run inference on models like Llama 3.3, which is the massive version of Llama with 70 billion parameters. So you can run Llama 3.3 really fast, really low cost on Groq's infrastructure, and along with many other open source models including DeepSeek variants. So Groq is great to use for that.

And then Ollama. So Ollama is itself more of a platform. It's something that you can use to run something locally that provides endpoints locally that are consistent, very similar to the endpoints that OpenAI and other models here have, so that you can make local calls to an API, which is in fact going to just run an open source model locally on your computer in high performance optimized C++ using a library called llama.cpp. And so Ollama is something that we will use as well.

Now, if some of these terms are unfamiliar to you, terms like inference — if you're not sure about that, if you don't fully understand the difference between running something over Ollama or Groq, then I can suggest background materials. Look in the guides, and also consider whether you'd like to look at my LLM engineering course, which does cover all of this.

And the final point that I will make is that you may know that I'm something of a fanatic on leaderboards, on places you can go to read about metrics and performance of different models. So much so that I was called a "leaderboard" humorously by my great friend Jon Krohn on his Super Data Science podcast. But there is a website called the Vellum leaderboard, which I've given the web address right there. And that is a great resource because it compares a number of the leading closed source and open source models together side by side. And it has things like the costs, and it has the context window size, if you're familiar with that, and it has the cost you can calculate based on the number of input and output tokens. And it's also got the performance, the results of key benchmarks across a number of dimensions. So I strongly encourage people to go and check out the Vellum leaderboard. And there'll be a link in the resources. And it's great to have that bookmarked. And as you go through different APIs, use that to gauge the costs and capabilities associated with them.

And now I'm going to put up one more time something that I said to you in the first lecture. But just to really double down on this, I want to remind you that there are great resources all over the place for this course. There's a resource for the whole course with videos and links. There's GitHub, the repo that has guides. It has the troubleshooting. And I'm always updating the labs to keep them up to date. I might add on new models. The models that we just went through a moment ago, those are the models that right now are the latest and greatest. But as new versions come out, I will update the labs. So you've got the latest in there. And so, you know, what you've heard is one story, but you'll get an even better story when you go through the labs yourselves.

And I will also urge you to keep a thick skin. You will hit roadblocks. There will be problems. That's one thing I can say for sure, but see them as — this is where real learning happens. It's in debugging. It's in diagnosing and figuring things out, even if it's painful to start with. It's super satisfying when you fix it and get it on track, and that is the way to do it. And if all else fails, or as I say, if not all else fails, you just want to, then reach out and contact me. Of course, one more time, I've got my LinkedIn right there, but also you can email me. I've got my details all over the place and I like hearing from people. I'm responsive. But most importantly, I don't want you to be suffering in pain with problems. I want to be fixing them. So keep this in mind.

And also, I mean, ask ChatGPT — you do tend to get great, great answers. Honestly, it's amazing. And I tend to, when I have a really difficult question, I will often ask ChatGPT and Claude both, because sometimes you get answers that are too long winded or take you in too many different directions, and so asking a couple of different models can help. And you can also basically have like an agent workflow that you do manually. You can ask a question to ChatGPT and then to Claude, you can say, I've got this response to my question. Do you agree? Is this accurate? You can have it be the evaluator, like the evaluator-optimizer pattern that we looked at a moment ago. So that's really cool that you can do it manually. And it's a great technique to get good answers from LLMs when you're stuck yourself.

Okay. With that preamble, it's time for our next lab. Let's get to it.

</details>

---
*Source: Official Udemy lecture transcript (auto-captions, lightly cleaned). Notes in Hinglish for self-study.*
