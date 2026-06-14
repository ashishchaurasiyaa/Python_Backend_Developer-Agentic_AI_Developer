# L24 — Setting Up AWS Cost Monitoring for Production AI Deployments

> **Week 1 · Day 5** · ⏱️ ~8 min

---

## 🎯 TL;DR

AWS par **koi spend cap nahi hota** — sirf alerts. Isliye root user se **Billing & Cost Management** mein jaake do budgets banao: ek **zero-spend budget** ($0.01 par alert) aur ek **monthly cost budget** (e.g. $5, jo 85%/100%/forecast par email bhejta hai). Week 1 project ~$1–$5/month hai; cost monitoring ek production skill hai.

---

## 🗣️ Hinglish Explanation

### Pehle: API/AWS costs ka refresher

Ed dobara yaad dilata hai (kyunki yeh **serious** hai) — AWS costs **tumhari responsibility** hai, har step par aware aur monitoring zaroori. AWS naye users ko offers deta hai (region-dependent, studying status, etc.) — jo mile le lo. Common ek hai **first 3 months free credits.**

Lekin kuch activities ki **hamesha cost** hoti hai:
- Apna **domain name** register karna (registrar ke through) — domain ke hisaab se cost
- Aur generally AWS "industrial strength" hai — **costs aati hain**

Week 1 project ka estimate: **agar poora month chalta rahe toh $1–$5**. Agar tum sirf 2-din chala ke band kar do (tear down), toh cost **de minimis** (lagbhag zero) honi chahiye. Par check karna tumhari zimmedari hai.

### Vercel vs AWS — pricing mindset

```
Vercel  = hobbyist-friendly, ek idea upload karne wale ke liye
AWS     = serious business, major corporations use karte hain
        → pricing tiers + scaling built-in
        → cost samajhna ek PRODUCTION SKILL hai (employers expect karte hain)
```

### ⚠️ Critical: AWS par koi spend CAP nahi hai

Yeh sabse important point hai:

> AWS (aur baaki cloud platforms) ke paas **bahut achhi granular alerting** hai — par **koi hard cap nahi.** Tum AWS ko nahi bol sakte "is amount se zyada mat spend karna, sab band kar do."

AWS ka stated reason: woh enterprises (Netflix jaisi companies) serve karte hain — agar billing glitch ya card fail ki wajah se "lights off" ho jaayen toh Netflix down ho jaayega, jo acceptable nahi. Ed ka personal take: usse ajeeb lagta hai (opt-in cap toh ho sakta tha), shayad technically complex hai — par jo bhi reason ho, **yeh option available nahi hai.**

Comparison:
- **OpenAI** — $5 upfront draw-down model. Log complain karte hain, par Ed ko **pasand** hai: worst-case liability sirf $5.
- **AWS** — theory mein **liability unlimited** hai. Agar galti se massive infrastructure create ho gaya, toh badi cost. Isiliye:
  1. Har point par samjho kya ho raha hai
  2. Alerts set karo (aur **test karo ki kaam kar rahe hain**)
  3. Spend regularly check karte raho

### LAB: Billing & Cost Management kholo

1. Root user se login confirm karo (top-right par "ed, root user" type indicator dikhega)
2. Top-left **search box** par jao — yeh AWS console ka go-to place hai (100 baar use hoga); har service yahin se milti hai
3. Type karo `billing` → results mein **"Billing and Cost Management"** select karo

Yahan **Billing & Cost Management home** dikhta hai — abhi tak ka spend, up-to-the-minute. (Ed ne khud August mein ~$100 spend kiya — par woh course banane mein, mostly ek mehenga service "Amazon OpenSearch" jise usne sasta wala replace kar diya. Tumhara number kuch bhi aisa nahi hoga.) Yeh page roz dekhna — at-a-glance spend.

### LAB: Budget 1 — Zero-Spend Budget

Left sidebar → **Budgets and Planning** → **Budgets**. Pehli baar kuch nahi hoga. Top-right **"Create budget"** (yellow button):

1. **Use a template** select karo
2. Template: **Zero spend budget** → tumhe alert milega jaise hi spend **$0.01** se upar jaaye
3. Naam: `zero spend`
4. **Email recipients** daalo — ⚠️ **sahi se** daalo, yeh tumhara safety net hai
5. **Create budget**

```
Budget #1 — "zero spend"
Type:    Zero spend (template)
Trigger: spend > $0.01
Email:   tumhara-email@example.com
Purpose: confirm karta hai ki alerts kaam kar rahe hain
```

### LAB: Budget 2 — Monthly Cost Budget

Phir se **Create budget** → **Use a template** → **Monthly cost budget**:

1. Naam: `monthly check`
2. **Amount** — woh number jitna tum is month AWS production par comfortable spend kar sakte ho. Ed example $5 deta hai; $1 bhi chalega — jo tum comfortable ho
3. **Email** daalo
4. **Create budget**

Monthly cost budget par **3 alerts** trigger hote hain:

```
Budget #2 — "monthly check" (e.g. $5)
  → 85% actual spend par   → email
  → 100% actual spend par  → email
  → 100% FORECAST par      → email (AWS predict karta hai agar aise hi chalta raha)
```

(Forecast = AWS ka prediction ki current rate par month-end tak kitna spend hoga.)

### Habit banao

Ed ka final advice:
- **Zyada budgets** add kar sakte ho zaroorat ho toh
- Zero-spend check rakho taaki **confirm** ho jaaye ki email aata hai
- Jab tak **emails actually aate na dikhein** (test karo), tab tak **Billing & Cost Management** page **frequently** dekhte raho — apne numbers samjho, comfortable raho

> Yeh tumhari responsibility hai, aur yeh serious business hai.

---

## 📋 Key Concepts

| Concept | Matlab |
|---|---|
| **No spend cap** | AWS spending ko hard-stop nahi kar sakta; sirf alert deta hai (unlike OpenAI ka $5 draw-down) |
| **Unlimited liability** | Theory mein AWS bill ki koi upper limit nahi — isliye monitoring critical |
| **Billing & Cost Management** | AWS console section jahan spend dikhta hai aur budgets banta hai (root user only) |
| **Zero-spend budget** | Template budget — $0.01 spend par hi alert; safety net + alert-test |
| **Monthly cost budget** | Template budget — set amount par 85%/100%/forecast email triggers |
| **Forecast alert** | AWS ka prediction-based alert — current rate se month-end spend project karke warn |
| **Free credits** | AWS new-user offers (region/student dependent), e.g. first 3 months free |
| **Search box** | Top-left console search — har service yahin se accessible, go-to navigation |

---

## 💼 Backend Dev Ke Liye Note

Backend dev ke liye yeh **FinOps / observability** ka foundation hai. Tum logs/metrics/alerts (Prometheus, CloudWatch, PagerDuty) ke saath system health monitor karte ho — yahan wahi discipline **cost** par apply ho rahi hai. AWS ka "no hard cap" model bilkul aisa hai jaise ek **un-rate-limited API** — agar runaway loop ya misconfigured autoscaling hua, bill unbounded ho sakta hai. Zero-spend + monthly budgets ko **canary alerts** samjho. Production mein iske aage AWS Cost Anomaly Detection, tagging-based cost allocation, aur Service Control Policies (org-level) aate hain, par concept wahi hai: **fail-loud early.** OpenAI ke prepaid-credit model vs AWS ke postpaid-unlimited model ka contrast yaad rakho — agentic apps mein LLM token spend + infra spend dono blow up kar sakte hain, isliye dono par alert lagao. Habit: deploy ke baad resources **tear down** karo (de minimis cost), aur alert emails ko ek baar deliberately trigger karke test karo.

---

## ✅ Takeaway

- AWS par **spend cap nahi hota** — liability theoretically unlimited; monitoring tumhari zimmedari
- **OpenAI** ($5 draw-down, bounded loss) vs **AWS** (postpaid, unbounded) ka mindset contrast samjho
- Root user → **Billing & Cost Management** → 2 budgets banao: **zero-spend** ($0.01) + **monthly cost** ($5)
- Monthly budget par **3 alerts** aate hain: 85%, 100% actual, aur 100% forecast
- Week 1 project ~$1–$5/month; **roz spend page check karo** aur alerts ko **test** karo

---

<details>
<summary>📜 Full Transcript (English)</summary>

I want to say a few words about API costs in AWS before we go and set up some some alerts. And I'm conscious that I have already talked about this before. So it's just a just a refresher one more time. API costs are something which is your responsibility that you need to be aware of and monitoring and understanding at every step on our journey together. AWS has a number of offers that they make to people that sign up for the first time, and those offers depend on your region and various things like whether you're studying and and other offers you may or may not be eligible for, but you should try and sign up for whatever you can. And I think one of the very common ones is your first three months of free credits. Um, but some AWS activities still have costs. For example, if you want to register your own domain name, then that has a cost. But of course you have to register it with a domain registrar. There's there's that cost that depends on what domain you're getting. So things like that that will have a cost. This first weeks project is estimated to cost between $1 and $5. If you were to leave it running for the entire month, if you just leave it running for a couple of days and bring it down, the costs should be de minimis. It should be nothing, but it's incumbent on you to keep an eye on it to check that that is the case. API costs should always be your choice throughout this course. Now, there's no doubt that when you're using an industrial strength platform like AWS, the costs they have cost. It's not like Vercel, which is like a more. It can be used by a hobbyist and by someone that's just wanting to get an idea up there. AWS is serious business and it's used by major corporations. And so the different pricing tiers and the ability to scale is built into it. And understanding how to manage and monitor costs is part of the production skill set that would be expected by many employers. So this is important learning as well. We're now going to go and set up some alerts, which is the way that we can monitor. And it's one of the ways that that we can check what's going on. We'll set up alerts. And I'm also going to encourage you to go back often to look at the total spend. So you keep a careful eye on this. Here's the thing AWS and the other platforms have alerting functionality. Very good granular alerting functionality. But there is no cap. There is no way to say, okay, AWS, I don't want to spend more than this amount. If I do shut everything off, they don't do that. Now, their stated reason for this is that they are used by by major companies, by enterprises. And it's it's not okay to imagine that AWS could ever turn the lights off in a normal situation just because a billing has gone wrong or a credit card didn't go through. Suddenly Netflix is down. That's that's not going to happen and that's AWS reason for it. Um, I do I feel like it seems strange to me because because why couldn't there still be an opt in thing where you could say, I want to be shut down if I go above this amount? They don't offer that. I suspect it's technically more complex than they than they want to admit. Uh, but nonetheless, whatever the real reason is, it's not something you can do. People complain a lot about open AI with the the need for $5 up front that you draw down against. But I have to be honest, I kind of personally prefer that for my projects, because I have a sense that if something were to go really wrong, my my, my greatest, uh, liability would be that $5 up front. I would I would spend it and that would be done. Uh, with AWS, that is not the case. In theory, your liability is unlimited. If somehow you were to write something that created massive, great infrastructure. Uh, and so that's certainly something to be cognizant of. And that's why I do want to impress on you how important it is to understand what's happening at every point, to set up the alerts that we're going to go and do right now, and to try them out and make sure they work, and to keep an eye on your costs, on your spend regularly. Uh, the remember again one more time that that this is your responsibility and it's serious business. Okay. So we're now back in the AWS console. This is what you get when you go to AWS, Amazon.com. Let me just prove that AWS, Amazon.com, and I'm logged in as my root user. And I press that button and here I am. And if you come up here to the account ID, you can see that we are logged in and logged in as ed, the root user for this account. So keep an eye on that. Um, and uh, I'm now going to go to this search box on the top left. Now Amazon, the AWS console website has many different sections for different services offered by AWS. There are so many of them, and the way that you can get to any of them is through this search box. This is your go to place. You will go to this 100 times. And right now I'm going to click here and type the word billing. And when I do that, up come the services that match this. And the one we're looking for is billing and cost management. So that's what I select. And I'm now at the billing and cost management home. This in a nutshell tells me that my costs that I've incurred with AWS up to date up to the minute. And you can see that I've actually spent quite a lot myself, $100 so far in August. And uh, the reason is that it's all on this, this course. But but not the not what you will need to spend. I spent a lot on this thing called Amazon OpenSearch service. That turned out to be much more expensive than I was expecting, and I've replaced it with something that is significantly cheaper. That means that it won't appear, or there won't be any measurable cost for that at all. So don't worry about how much I've spent. Your number shouldn't be anything like that. And anyway, you will be actively watching it to make sure. But this page is where you can see your spend at a glance, and you should be coming back here every day to double check. But what we're going to do is we're going to look in the left bar here, and we're going to scroll down to budgets under the title Budgets and Planning and Budgets. And we get here to the budgets section of the billing and cost management. So you can see the breadcrumbs up here. We're in billing and cost management under budgets. Looking at the overview right here and now. You won't have anything here because you haven't set up any budgets yet. And let's fix that right away. Press this yellow create Budget button on the top right and come in here. So first of all select this user template box. And then here we're going to start by creating something called a zero spend budget. Which means that you'll get notified as soon as your spending exceeds $0.01. So in we come. Uh, we need to give it a name, so we'll call it zero zero spend. We have to put in the email recipients and make sure that you get this right, because this is your safety net. So it needs to be right. There is my email address. Double check it. And, uh, it tells me I'll be notified by email when any spend above a cent is incurred. And I press the create budget button. And it's been created right here. Go back and create budget again. Use a template monthly cost budget. And now we'll come up with a number. We'll call it monthly check. Monthly check. Come up with a number which is the amount that you are comfortable spending this month on deploying to AWS production. Let's say it's $5. Put in the email address here, and your number is whatever number you're comfortable with. And it can be $1 if that's all you want to spend, uh, you will be notified when your actual spend reaches 85% of this number, when your actual spend reaches 100% of this number. And if the forecast if Amazon's prediction, if you continue going the way you are, uh, reaches 100%. So you should get three possible emails associated with this report with this this alert. And now we press Create Budget and that has been created as well. And now you can add more if you want to check for more things. And it's worth having like that zero spend check just to make sure you definitely get that email. And regardless, until you're getting these emails and you see that it's working, you should be coming back to the billing and cost management part and looking at your numbers frequently to make sure you're comfortable that you understand your spend and you know what's going on.

</details>
