# L106 — Testing Your Multi-Agent Financial AI System Live in Production

> **Week 4 · Day 3** · ⏱️ ~9 min

---

## 🎯 TL;DR

Alex ab **CloudFront par live** hai — Ed real production app par "Start new analysis" dabata hai aur **5 agents** (SQS → planner Lambda → reporter/charter/retirement-planner/researcher) milkar real Polygon data se portfolio analysis + charts generate karte hain. Capstone **90% complete**; baaki 10% = observability (kal).

---

## 🗣️ Hinglish Explanation

### Pehle: Live deployment kholo

Pichle lecture mein Terraform apply complete hua. CloudFront distribution ka URL "open" karte hi — **bam, app internet par live** hai. Yeh ab local nahi, **CloudFront par real production** hai, jise duniya mein koi bhi access kar sakta hai.

Same landing page, **Sign In with Google** → authorize → **signed in**, avatar upar dikh raha hai. Ed local server **band** kar chuka hai — ab sab kuch **deployed Lambda API** + **API Gateway** ke through chal raha hai.

### Accounts setup (production)

- Accounts tab par nice **loading pulse** (skeleton state).
- **Reset all** → phir **populate test data** → fresh test portfolio.
- **Brokerage account** edit → **JP Morgan (JPM)** ki position add, quantity 10 → "add position" → ho gaya.
- Abhi in positions ki **koi price nahi** — system ko price nahi pata (analysis run hone se pehle).

### Advisor team tab — "Start new analysis" 🚀

Yeh naya hissa hai. **Start new analysis** button dabate hi ek **animated line** screen par aati hai (kuch ho raha hai indicate karti hai). Behind the scenes pura **multi-agent orchestration** chalta hai:

```
"Start new analysis" dabaya
        │
        ▼
  SQS queue par ek message daala gaya
        │
        ▼
  Planner Lambda (spun up) ne message pick kiya
        │  → Bedrock call kiya (Nova Pro model)
        │  → 3 tools se equip hua, decide kiya tools use karna hai
        ▼
  3 doosre Lambda services parallel mein chale:
   ├─ Reporter (Nova)            → financial planning report likha
   ├─ Chart specialist (Nova)    → charts ke liye JSON describe kiya
   └─ Retirement planner          → portfolio dekhke long-term implications predict ki
  (+ Researcher agent ne pehle research data daala tha jo report mein use hua)
```

> **Background — yeh architecture kya hai**:
> - **SQS (Simple Queue Service)** = managed message queue; frontend ek job message daalta hai, decouple ho jaata hai (frontend ko wait nahi karna padta, agents async chalte hain).
> - **Planner Lambda** = orchestrator agent; SQS message trigger par spin up hota hai (serverless, idle par cost nahi).
> - **Bedrock + Nova Pro** = AWS managed LLM service; **Amazon Nova Pro** model use ho raha hai reasoning/tool-calling ke liye.
> - **Tools** = planner ko diye gaye functions (yahan baaki 3 agents ko invoke karne ke liye) — LLM khud decide karta hai kab call karna hai (agentic behaviour).
> - Yeh **multi-agent on separate Lambdas** pattern hai — har specialist apna independent endpoint, planner unhe coordinate karta hai.

Run **complete** hote hi results screen turn ho jaata hai.

### Results — kya generate hua

1. **Portfolio analysis report** (Reporter se) — yahi main report researcher ke research ko bhi include karta hai.
2. **Retirement projections** (Retirement planner se) — test portfolio chhota hai, toh report "insufficient to meet target" bolti hai (target bahut zyada tha vs invested) — Ed bolta hai bilkul sahi "cross" hai.
3. **Charts** (Chart specialist se) — agent ne **khud decide kiya kaunse charts dikhane hain**:
   - Top 5 holdings
   - Account distribution
   - Tax efficiency
   - Asset class distribution (Equity sabse zyada, + commodities, cash, fixed income)
   - Global distribution
   - Sector distribution

Ye saare charts **JSON mein describe** kiye gaye charter agent dwara, aur **frontend ne wahi JSON render** kar diya. (Yeh ek clean separation hai — LLM data/spec deta hai, UI render karta hai.)

### Polygon prices ab populate ho gaye

Accounts par wapas jaake brokerage account edit karo — pehle "N/A" wali prices ab **real share prices** dikha rahi hain, including JP Morgan jo Ed ne add kiya tha. Yeh sab **Polygon API** se aaya (tagger agent + Polygon ne instruments tag karke real prices fetch ki). Ab portfolio ki **real total value** as-of-now dikh rahi hai.

> **Background — tagger + Polygon**: jab analysis chala, ek "tagger" step ne portfolio positions ko market instruments se match kiya aur Polygon API se real-time prices laaye, jo DB mein persist ho gaye — isliye agle screen par real values dikhte hain.

### Reflection — sab kuch production mein chal raha tha

Ed satisfied hai — **multiple AWS services collaborate** kar rahe the, **many LLM calls** mile, sab production out-there. Par ek **gap** rehta hai: usse "behind the scenes kya ho raha tha" ka feel nahi mila. Animation cool thi, results great the, par **visibility kam** thi — 5 agents communicate kar rahe the, planner AWS ke across calls kar raha tha, multiple LLM calls ho rahe the, par hum dekh nahi paaye.

**Yahi production AI ka critical missing piece hai: monitoring + observability.** Yeh gap kal (Day 4) address hoga.

### Bonus — production-ize karna trivial hai

Ed reminder deta hai:
- **Week 2** se: custom **domain name** de sakte ho (proper deploy).
- **Week 1** se: **subscription plans** add karke "agent run" feature sirf paying subscribers ke liye lock kar sakte ho.
- Yeh dono **trivial changes** hain — Alex ko real commercial paid SaaS bana sakte ho.

### Milestone 🎉

Ed bolta hai apne aap ko **seriously congratulate** karo — do bade capstone-building days paar ho gaye, aur ab hum **90% mark** par hain. Sirf **10% baaki** (observability/enterprise-grade).

---

## 📋 Key Concepts

| Concept | Matlab |
|---|---|
| **CloudFront live** | App ab internet par real production mein (local nahi), deployed Lambda + API Gateway |
| **SQS** | Message queue — frontend job daalta hai, agents async pick karte hain (decoupling) |
| **Planner Lambda** | Orchestrator agent — SQS trigger par spin up, Bedrock+Nova Pro, 3 tools |
| **Nova Pro / Nova** | Amazon ke Bedrock LLM models — planner/reporter/charter use karte hain |
| **5 agents** | Planner + Reporter + Chart specialist + Retirement planner + Researcher |
| **Tools (agentic)** | Planner ko diye functions; LLM khud decide karta hai kab invoke karna |
| **Charts as JSON** | Charter agent JSON spec deta hai, frontend render karta hai (clean separation) |
| **Tagger + Polygon** | Positions ko instruments se match karke real prices fetch + persist |
| **Observability gap** | Sab chala par "behind the scenes" visibility nahi — kal ka topic |
| **90% milestone** | Capstone build done; baaki 10% = enterprise-grade observability |

---

## 💼 Backend Dev Ke Liye Note

Yeh lecture ek backend dev ko **event-driven, decoupled multi-agent architecture** ka live proof dikhata hai. Pattern classic hai: synchronous HTTP request (frontend → API Gateway → Lambda) **fire-and-queue** ho jaata hai — API SQS par ek job message daalti hai aur turant return karti hai (long-running agent work ke liye HTTP timeout avoid). SQS message **planner Lambda** ko trigger karta hai, jo specialist Lambdas ko **fan-out** karta hai (parallel workers). Yeh exactly woh background-job pattern hai jo tum Celery/RQ + Redis se karte the, par **fully serverless** (SQS = broker, Lambda = workers, idle par zero cost). Do design points note karo: (1) **agent output as structured JSON** (charts) — UI dumb rehta hai, sirf render karta hai; LLM ko presentation se decouple rakha. (2) **side-effect persistence** — tagger ne prices DB mein likhe, toh next read par derived data ready hai (write-on-process, read-from-cache). Ek hi cheez missing: **observability** — jo asli production-readiness ka marker hai (next lecture).

---

## ✅ Takeaway

- Alex ab **CloudFront par live production** mein — local server band, sab kuch deployed Lambda API + API Gateway se.
- **"Start new analysis"** → SQS message → planner Lambda (Bedrock/Nova Pro + 3 tools) → 3 specialist Lambdas (reporter, charter, retirement planner) + researcher fan-out.
- Results: portfolio report + retirement projections ("insufficient to meet target") + **6 charts** jo charter agent ne **JSON mein describe** kiye, frontend ne render kiye.
- **Polygon + tagger** ne real share prices (incl. JPM) populate kiye — portfolio ki real total value dikhti hai.
- **90% milestone** — capstone build complete; **gap = observability** (next: Day 4). Domain + subscription gating trivial add-ons.

---

<details>
<summary>📜 Full Transcript (English)</summary>

So here we are. Here we're looking at the, uh, the results of our deployment. And the question is, is this just going to work? First time we just did a Terraform apply. So I am going to this is where it's saying that that it is deployed CloudFront distribution. And I am going to launch this right now I'm going to say open. And here bam this is running on the internet. Everybody on the internet on CloudFront. This is our financial advisor. This is the landing page. And this is the same as before of course. So first of all there's the sign in button. Let's give it a try. Sign in with Google. And I'm authorizing my Google account. Continue. And here we are. We're signed in and it's got my my avatar at the top there. It knows who I am. And we'll now go to dashboard. And this is of course running. This is, you know, for real running out there. This is now no longer I've I've closed my local server. This is all running using the deployed Lambda API and going through API gateway, of course. So it's, uh, let's let's go to our accounts. You can see it's got a nice loading pulse there. Here we go. Uh, and I'm going to just show you I'm going to reset all my accounts like this, and then I'm going to populate my test data. So we create test data from scratch. Here it is. And, uh, yeah. Let's come on into the brokerage account. Let's edit that brokerage account. Lovely. And let's add a position. I'm going to add a position in my, uh, uh, older friend, uh, JP Morgan. And we will give that a quantity of ten. Add the position. There it is. It's ten. And none of these have a price yet. It doesn't know the price of these, uh, positions. Uh, okay. So now let's go to the next tab along which says advisor team. And this this is the new one. And what we're going to want to do now is press this Start new analysis button. Let's see what happens. Uh, when we do that. Okay. Here we go. I pressed the button and you'll see right away that something happens that this this line comes across. It's showing something going on. What happened? It put a message on the queue on SQS. That message was picked up by financial planner, by by our planner Lambda service that that spun up, that then called to bedrock that used Nova Pro and armed it with three tools, equipped it with tools that it could use. It decided to use those tools. And so as a result, uh, all three of the other Lambda services were called and started working. That includes reporter, which is the Lambda service that again uses Nova to write reports on our, uh, on, on our retirement, uh, on our on our financial planning. The chart specialist, which is the Lambda service that uses Nova to come up with some JSON that could describe different charts, that it can come up with any charts that it thinks would be good to visualize about my investments, and then retirement planner, which looks at my portfolio and predicts longer term implications, things that we could move back to, to, to, to come to. And it just completed and it turns immediately to the results. And here we are seeing the results of the run. And so you get a portfolio analysis report. This is the report from the reporter. This is the retirement projections. Uh and it has this this test portfolio isn't a very impressive portfolio. So it's very concerned about it insufficient to meet target. So which which makes sense I think uh, the target was uh, yeah. Much more than, than we currently have invested. So it's quite right to be quite cross about that. Uh, so these two reports were indeed produced by Nova, and they look great. Uh, and presumably the the main report. This one here also involved looking into some of its research that our researcher agent has been busy putting in there. And then last but not least, let's look at charts. We turn over here. And these charts were they were they were invented. They were created by the charter agent. It decided how to to what? I wanted to show us the top five holdings. There they are. The account distribution, the tax efficiency, how the asset classes are distributed. Equity is most of it, uh, and commodities and some cash and some fixed income and how it's distributed globally and then how it's distributed by sectors. All of these charts were described in JSON by charter. And then the front end just displayed them as they are. Uh, and it's all come up looking great. And, uh, yeah. So this this is the results of the analysis. If we go back to accounts, one of the things that we'll notice is that, uh, the, the because the tagger was at play, uh, and because also we were using the polygon API. You'll see now that whilst before it was saying Na for some of the prices, if we go into our brokerage account now and edit this, you'll see that we do now have prices for these different instruments, including JP Morgan, the one that I added in that has a share price as well. This has all come from polygon. And so we have real share prices associated with our account and real values of our portfolio. And that's been used to give us the total value of this test portfolio as of right now. And so that that really is a wrap to this demo of this product. And I hope you're you're blown away as I am about how comprehensively how well this fits together. But of course, the thing to bear in mind is that this has all been running in production out there. This has been multiple AWS services collaborating whilst working on this, with many calls to LMS that have come together to make this possible and to give us the kinds of results that we have. So look, I'm not gonna lie, I found this very satisfying indeed. And I hope that you did, too. But there is still one hole for me. There is one thing that perhaps doesn't feel as satisfying as it could do, and that is a sense that I didn't really get a feel for what was going on behind the scenes when we were running this. I mean, it looked really cool, like this animation when the different agents flashed up, looked great, and it was fun. And it was, of course, great to see the analysis that we can now do every time just by pressing this view button and come in and look at it again. So it's fantastic to see it all here presented. And I know that behind the scenes our five agents were communicating. The planet agent was making calls that were going out across AWS and that were making multiple calls to LMS. But I feel like we don't have much visibility into that. And obviously a massive part of delivering AI to production is having great monitoring and great observability. And that's why that is perhaps still the gap in what we've built so far. And that's a gap that we will be addressing tomorrow. And I hope you have a big old smile on your face, because today was fun and look great. And it's so cool to have this, this production app on on CloudFront. And of course as well, if you want to take it one step further, you remember from week two how we actually can give that a domain name and deploy it properly. And you also remember from week one how we can add subscription plans so that this functionality may be kicking off. The agent run is only available to subscribers, so it would be very easy to actually roll this out to a proper domain and have it be something which people have to pay to have access to. These would all be trivial changes to make to to actually have a real commercial production application at your fingertips, and you should certainly look into that. But before you do so can I please, please ask that you take a serious moment to congratulate yourself in a big way? We've got so much done. We've got past those two big days of building our capstone project, and it has brought us to a 90%, the 90% mark. We've got 10% left to go.

</details>
