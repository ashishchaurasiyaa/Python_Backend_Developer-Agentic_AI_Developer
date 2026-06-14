# L96 — Setting Up AWS Bedrock Models and Enterprise APIs for AI Agents

> **Week 4 · Day 2** · ⏱️ ~7 min

---

## 🎯 TL;DR

Agents ko chalane ke liye do prerequisites: (1) AWS Bedrock par **Amazon Nova** models ka access request karo (cheap + reliable, US West 2 region), aur (2) ek enterprise API — **Polygon.io** — ka free API key lo for real market data. Phir sab credentials `.env` file mein daalo.

---

## 🗣️ Hinglish Explanation

### Step 0: Bedrock model access request karo

Guide ke "6_agents" section mein pehla step hai Bedrock model access maangna. Ed ki model journey:

- Pehle wo **GPT-OSS 120B** (OpenAI ka naya open-source model Bedrock par) use kar raha tha — pehle chala, fir band ho gaya. Toh usne course se hata diya.
- Ab wo **Amazon Nova** range use karta hai — **bahut fast access milta hai aur extremely sasta hai**. Recommendation: Nova se shuru karo.
- Caveat: retirement/financial advice Nova se "so-so" milta hai. Zyada powerful answers chahiye toh paid better models try karo (optional).

> **Bedrock recap**: AWS Bedrock ek fully-managed service hai jahan se tum multiple foundation models (Amazon Nova, Anthropic Claude, Meta Llama, etc.) ek hi unified API se access karte ho — apna server nahi chalana padta, AWS infra par inference hota hai, IAM se access control hota hai. Har model ke liye pehle **"model access"** explicitly request karna padta hai.

### Model access UI se kaise milta hai

1. AWS Console mein **root user** (Ed bolta hai "as editor" = uska user) se login.
2. Search box mein **bedrock** → Bedrock console.
3. Yeh **model catalog** dikhata hai (UI tease karta hai "OSS available" 😏).
4. Bottom-left → **Configure** → **Model Access**.
5. **Manage / Modify model access** → jo models chahiye unko **check** karo → **Save**.

> ⚠️ **UI badal raha hai**: Ed warning deta hai ki yeh model-access page **October 8 ko ja raha hai** — purana UX "really flaky aur hard to figure out" tha. Tum (future viewer) ko probably better UI dikhega. So exact clicks match na karein toh ghabrao mat — screen-cues padho.

Ed ke paas already access hai: **Nova Pro** (jo use karenge), cheaper Nova variants, aur fancy **Nova Premier** (use nahi karega par experiment kar sakte ho). **Claude Sonnet 4** ka bhi access hai — bahut achha model — par naye account par rate limiting kam hoti hai, toh course ke liye Nova use kar rahe hain. Nova access usually refresh karte hi mil jaata hai (theory mein 1-2 min lag sakte hain).

### Region ka pecha: US West 2

Bahut important detail:

- Models **US West 2** region mein request karo — yahan models ka widest range milta hai.
- Yeh region tumhare **baaki infrastructure (Lambda etc.) ke region se match karne ki zaroorat NAHI** — Bedrock alag region par ho sakta hai.
- Safety move: Ed ne **US East 1 mein bhi** same models ka access request kiya — taaki agar koi environment variable muddle ho jaaye toh dono regions mein access ho. Tum bhi aisa kar sakte ho.

### Step 1: Enterprise API — Polygon.io

Production systems mein enterprise APIs ka heavy use hota hai. Alex ek API use karega latest financial/market data ke liye — Ed ka favorite **Polygon.io** (financial services ke liye market data provider, reliable + robust).

- **Free plan** kaafi hai is course ke liye. Live (intraday) market data chahiye toh **paid plan** lo (Ed paid use karta hai).
- Steps: polygon.com → **Create account** → free account setup → **API key** collect karo.

### Polygon kyun, yfinance kyun nahi?

Bahut achha production lesson:

- **yfinance** ek free Python library hai jo Yahoo Finance ki **unofficial API** use karti hai — koi API key nahi chahiye.
- Par yeh official nahi hai: koi **SLA nahi, supported nahi, guaranteed nahi**. Kabhi bhi break ho sakti hai.
- Demo ke liye theek, **production ke liye nahi**. "Every API should matter to you." Polygon jaisa industry-standard, robust, scalable API choose karna production sense banata hai. True SaaS ke liye paid plan (decent rate limiting) chahiye.

### Step 2: `.env` file setup

Saare secrets/config ek `.env` file mein daalo (Ed ne already kar liya, tumhe karna hai):

```bash
# Bedrock model — EXACTLY jo access mila hai wahi ID
BEDROCK_MODEL_ID=us.amazon.nova-pro-v1:0

# Jis region mein model ka access hai
BEDROCK_REGION=us-west-2

# Default AWS region — Lambda + baaki sab ke liye (Bedrock se ALAG ho sakta hai)
AWS_REGION=us-east-1

# Polygon
POLYGON_API_KEY=your_free_api_key_here
POLYGON_PLAN=free        # ya 'paid' agar paid plan hai
```

Critical notes Ed ke:

- **`BEDROCK_MODEL_ID`** bilkul exact hona chahiye jo access mila — Ed ke paas Nova Pro v1 hai. Galat ID = hard-to-track-down errors. Double-triple check karo.
- **`BEDROCK_REGION`** (US West 2) aur **`AWS_REGION`** (US East 1, ya tumhare paas jo closest ho) **alag** hain — Bedrock models ko Lambda ke same region se serve karne ki zaroorat nahi.
- **`POLYGON_PLAN`** = `free` ya `paid` — yeh code ko switch karata hai: `free` par end-of-day cached prices, `paid` par intraday equity ticker prices.

---

## 📋 Key Concepts

| Concept | Matlab |
|---|---|
| **AWS Bedrock** | Managed multi-model LLM service — Nova/Claude/Llama ek API se |
| **Model Access** | Bedrock par har model ka access explicitly request karna padta hai |
| **Amazon Nova Pro** | Sasta, fast, reliable model — Alex ka default LLM |
| **US West 2** | Bedrock model region — baaki infra se match karna zaroori nahi |
| **Polygon.io** | Enterprise market-data API (free + paid plan) — production-grade |
| **yfinance** | Free unofficial Yahoo API — demo theek, production NAHI (no SLA) |
| **`.env` file** | BEDROCK_MODEL_ID, BEDROCK_REGION, AWS_REGION, POLYGON_API_KEY/PLAN |
| **POLYGON_PLAN** | `free` = end-of-day prices; `paid` = intraday prices (code switch) |

---

## 💼 Backend Dev Ke Liye Note

Yeh lecture pure config-and-secrets hygiene hai jo har backend dev jaanta hai. `.env` + 12-factor app config — environment-specific values code se bahar. Polygon-vs-yfinance debate exactly wahi "vendor SLA matters" discussion hai jo tum payment gateway ya email provider choose karte time karte ho: ek unofficial/scraped endpoint production dependency nahi ban sakta kyunki uske uptime/breaking-changes par tumhara koi contract nahi. Do alag regions ke env vars (`BEDROCK_REGION` vs `AWS_REGION`) yeh yaad dilate hain ki cloud services ki locality independent ho sakti hai — apne app server ki region aur apni LLM/DB ki region ko alag se reason karo. Aur "exact model ID, warna silent hard-to-debug failure" — wahi classic lesson hai ki misconfigured env var production mein sabse painful bug hota hai.

---

## ✅ Takeaway

- Bedrock console → Configure → **Model Access** → Nova models check → Save (UI Oct 8 ke baad change ho sakta hai)
- **Amazon Nova Pro** use karo — sasta, fast, reliable; **US West 2** region (baaki infra se match nahi karna)
- Real market data ke liye **Polygon.io** free API key lo — yfinance nahi, kyunki production-grade SLA chahiye
- `.env` mein daalo: exact `BEDROCK_MODEL_ID`, `BEDROCK_REGION`, alag `AWS_REGION`, `POLYGON_API_KEY`, `POLYGON_PLAN`
- Model ID **bilkul exact** likhna — chhoti galti = bahut hard-to-find error

---

<details>
<summary>📜 Full Transcript (English)</summary>

I'm back in six underscore agents and previewing this guide. And the first step is to request bedrock model access. Now look for this section for the agents I wanted to use OS 120, the new open source model for OpenAI. And I did to start with. And it worked okay. And then it stopped working and I've had to redo it without OS 120. And so I will be using Amazon's Nova model range, which are very quick to request access for an extremely cheap. So I suggest you start with that. Two but the the retirement and the financial advice that we get from it is kind of, uh, so, so should you wish, should you be willing to spend a little bit more? Then I would encourage you to investigate, experiment with different models to get even more powerful answers from it. But for now, we will stick with the very cheap and very reliable and solid Amazon Nova models. So first of all, we go in to the AWS console in as our root user. Here I am as editor and I'm going to go to bedrock in the search box that you know well by now. Here we go. This is bedrock. This is the model catalog. Look, it even teases me by telling me that OSS is available. Well. Thank you. Well, we go down here to configure on the bottom left and we click Model Access. Now I noticed that you get this, this yellow sign here that says that this model access page is going away on October the 8th. And the chances are you're watching this after October the 8th, which is good because this is really lame. It's horrible. Uh, this is a really flaky UX that's hard to figure out. So hopefully you see something better. And I don't know what you see, but but I imagine it's easier to navigate. And it's an exercise for you to figure out how to request access to the models that you need, although you probably already did that last week. Uh, so anyways, what we've got here, if we have a look, is I have already requested access and got access to Anova Pro, which is the one we'll use also to the even cheaper ones and also to the fancier Nova Premier. Uh, but I won't actually use that. But but by all means, you can experiment if you wish. I also have access to Claude Sonnet four, which is a very good model indeed, but it doesn't have such good, uh, rate limiting. The rate limiting for a new account is relatively low, so it didn't work for me. I would have to have requested more, and I didn't want you to have to do that. So I won't be using Claude sonnet four. But if you do have the ability to use it, then it might well be worth an experiment. And I think that's it. So. So those are the models you will have to come in to these press model, modify model access and then check the ones you want and then press save. And then with the Nova models. Uh, honestly I got I got access as soon as I refreshed the page. But I think in theory it might take a minute or two. Um, now, just just to be safe, we're going to be using it in US West two, the region you pick up here, uh, US West two does not need to match the region of the US, uh, of the rest of your infrastructure. So you should select US West two to do this if you want to see the greatest range of models. Um, but I also I went back to US East one, and I also requested access to the same models in US East one as well, because sometimes it's a bit it's a bit hard to figure out like which region it's selecting. And I thought to keep it simple, I would just make sure I have access in both in case some of my environment variables gets gets muddled up at any point. So you might want to do the same if you want to avoid any potential region issues if the model you pick is in both regions, but otherwise I'd suggest use us West two for your models and request access. Get access to them. Wait a couple of minutes and then I will see you back in the lab. Okay, moving on to step one. So one of the things that production systems often have is, is a use significant use of enterprise APIs. And we will use an API ourselves. Right now we'll use an API to give us latest financial data. And students from my agent course will recognize this one. Well, we will use my one of my favorites polygon IO, which is a provider of market data to financial services. And it's it's great Reliable, robust API and you can do it for free. It has a free plan and a paid plan, and all you need for this course is a free plan, unless you want to be able to have live market data, in which case, by all means get the paid plan I do because I'm into that stuff. So you go to Polygon.com and this will come up this way. Modernizing Wall Street, you press create account and then you use that to set up a free account and collect your API key. Uh, and then then you come back, uh, here again and it's time for us to set up our environment, uh, file with these, these, these parameters. Now, someone might say, someone asked me, why do we use polygon? Why not use something like Yfinance, which is a free API that doesn't even need an API key? So, so Yfinance is an alternative. And if you use it yourself, you can by all means use it. But it is. It's like a it's not an official API. It takes advantage of Yahoo's unofficial API for serving ticker symbols, which isn't doesn't necessarily have an SLA, isn't supported and isn't guaranteed. So it's a great example of it's fine for a demo project, but when it comes to building production systems, every API should matter to you. And so picking something like polygon as a sort of industry standard, robust scalable API makes a lot of sense. And of course, if you were building this to be true SaaS product, you would want to have the paid plan which has decent rate limiting and so on. So with that in mind, it's time to take these and add them to your EMV file. The bedrock model ID needs to be exactly the model ID that you have access to. And here's here's the one that I've got access to us. Pro v1. It's got to be exactly that. The region where I have access to this model, the bedrock region is US West two. And so that's what I've got in here. And that is different to my default AWS region that I'm going to be using for Lambda and everything else, which is US East one for me, but it should be whatever is closest to you. So these two can be different. You don't need to have your your bedrock models served from the same region as your lambda. So you should you should pick whichever ones make most sense to you. Um, or wherever you've requested the approval for the model. Um, so be sure to get this right. Mistakes here will be hard to track down. So? So double triple check. And then for polygon you should have your free API key and put it there. And then I've got this variable polygon plan which is just the word free. If it's a free plan or change that to the word paid if it's a paid plan. And that will mean the code will switch between just cashing and doing end of day market prices and doing. If you're paying for it, it will get you intraday prices of equity tickets. So that is the setup I need you now. I've already done this but so I don't need to do it. But you need to do it. You need to go into your EMV file and put in these secrets. I will let you do that right now.

</details>
