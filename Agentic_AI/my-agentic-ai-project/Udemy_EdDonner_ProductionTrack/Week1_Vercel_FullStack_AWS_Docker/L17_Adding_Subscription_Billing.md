# L17 — Adding Subscription Billing to Your Production AI SaaS Application

> **Week 1 · Day 3** · ⏱️ ~7 min

---

## 🎯 TL;DR

Auth wala app production par deploy karte hain (pehle Vercel ki deployment protection band karke, taaki sirf Clerk protect kare), live secured app test karte hain. Phir Day 3 part 2 shuru — **Clerk Billing** se subscription plans (free + premium) set up karte hain, Clerk ke built-in payment gateway (ya optionally Stripe) se, taaki idea generator ek **paid feature** ban jaaye.

---

## 🗣️ Hinglish Explanation

### Step 1: Vercel deployment protection band karo

Production par bhejne se pehle ek important cleanup. Vercel → **SaaS production project** → **Settings** → **Deployment Protection**.

Problem: ab humare paas **do layers** of protection ho sakti hain — Vercel ka apna auth (Day 1 wala wrapper) **aur** Clerk. Hum chahte hain ki sirf **Clerk** protect kare. Toh:

1. Settings → Deployment Protection.
2. **Vercel Authentication band (turn off)** kar do.
3. Save.

Ab SaaS app **internet par expose** hai — lekin **Clerk** use protect kar raha hai. Yeh sahi setup hai: app public hai, par andar ka generator sirf logged-in users ke liye.

> Concept: Vercel Deployment Protection ek platform-level gate hai (Vercel team ke alawa koi nahi dekh sakta). Clerk app-level auth hai (koi bhi sign up kar sakta hai, phir features unlock hote hain). Production app ke liye tumhe app-level auth chahiye, platform gate nahi — isliye Vercel wala off.

### Step 2: Production par deploy

```bash
vercel --prod
```

(Ed ne yeh kuch second pehle hi chala diya tha.) Chaaho toh pehle `vercel .` se preview par deploy karke test kar sakte ho, phir production. Deploy hone ke baad URL kholo:

- "Generate your new business idea" dikhta hai.
- **Sign in** karo (Ed apne existing account se aata hai) → "Continue" → **logged in on the internet**, Vercel app par.
- **"Generate business idea"** dabao → ab yeh **protected back-end route** ko call karta hai jise humne secure kiya hai. Route ko pata hai ki user logged in hai.
- Ek **handshake trace** print hota hai (front end ↔ back end ke beech JWT verification).
- Results **nicely streaming** aate hain, properly formatted.

**Yeh ek fully front-end + back-end secured app hai, production mein deployed.** Refresh karke dobara generate kar sakte ho. Simple app hai abhi, par foundation solid hai.

Iske saath **part 1 (security architecture) khatam** — ab **part 2: subscriptions**.

### Day 3 Part 2: Subscription billing intro

Cursor mein `week1` folder → **day three part 2** ki MD preview kholo. Aaj 2-parter hai. Goal: SaaS app ko **subscription management** ke saath transform karna — idea generator ab **paid subscription** maangega. Iska point: **tum apna khud ka business idea leke rapidly online deploy kar sakte ho, jiske liye log subscribe karke pay karein.**

**Yeh bhi Clerk se hi hoga.** Clerk sirf user management + social login nahi deta — uske paas ek **billing platform** bhi hai. Aur khaas baat: yeh **Stripe se hooked up** ho sakta hai. Agar tumhare paas Stripe account hai ya Stripe se payments collect karna chahte ho, toh Clerk ke through use kar sakte ho — fabulous.

> **Stripe** kya hai? Industry-standard payment processing platform — credit card payments, subscriptions, invoicing handle karta hai. Clerk Billing ya toh apna built-in gateway use karta hai, ya tumhare Stripe account se connect ho jaata hai.

### Step 3: Clerk Billing enable karo

Clerk dashboard par jaao:
1. Overview screen dikhega SaaS app ka — ab **"Congratulations, your application has users"** message bhi (kyunki tumne khud sign in kiya). Apne sign-ups bhi dikhenge (Ed ke paas 2 Gmail accounts).
2. **Configure** → left mein scroll down → **Billing settings** aur **Subscription plans**.
3. Billing **Settings** mein jaao → first time ho toh ek **"Get started" / "Set up"** button hoga → dabao.
4. Do options dikhte hain:
   - **Clerk payment gateway** — out-of-the-box, very simple. **Hum yahi use karenge.**
   - **Stripe connect** — more sophisticated; agar Stripe se payments collect karte ho. (Yeh ek **exercise** hai agar tum sach mein monetize karna chahte ho.)

Yeh billing ko enable karta hai.

### Step 4: Subscription plans banao

**Configure → Subscription plans** mein jaao. Yahan plans set hote hain. Ed ke paas already **free plan** + **premium subscription plan** hai. Tum **"Create plan"** button dabaoge:

- **Name** do: e.g. "Premium Subscription"
- **Key** do: yeh `subscription-plan` jaisa kuch hona chahiye — par **hyphen allowed nahi**, **underscore use karo**. Ed ka key: **`premium_subscription`** (usne pehle hyphen try kiya, fail hua, phir underscore).
- **Description** do.
- **Monthly base fee** — yeh sirf **test payments** ke liye hai, **actual money nahi lagega**. Ed ne **$100/month** rakha.
- Optionally **Annual discount** on karo — agar koi pura saal commit kare aur upfront pay kare, toh discounted monthly price. Ed ne **$90/month** (annual) rakha.
- **Publicly available: ON** — taaki log access kar sakein.

Ed ka exact setup (match karne ke liye):

| Field | Value |
|---|---|
| Plan name | Premium Subscription |
| Plan key | `premium_subscription` (underscore, NOT hyphen) |
| Monthly fee | $100/month |
| Annual discount | $90/month (committed annually) |
| Publicly available | On |

### Step 5: Features (optional power-up)

Plan ke andar **Features** configure kar sakte ho — alag-alag features jinhe user subscribe karta hai. Phir yaad karo pichle lecture mein back-end route mein wo **`creds`** the (decoded JWT) — un creds se figure out kar sakte ho user kis plan/features par hai, aur uske hisaab se kuch functionality do, kuch na do. Yeh **authorization by subscription tier** ka pattern hai — ek **exercise** as you wish.

```python
# Back end mein subscription-gated feature ka idea (creds se):
@app.get("/api/generate")
def generate(creds = Depends(clerk_auth)):
    plan = creds.decoded.get("pla")  # ya features claim
    if plan != "premium_subscription":
        raise HTTPException(status_code=402, detail="Subscription required")
    # ... premium feature ...
```

### Step 6: Plan ID note kar lo

Plan banane ke baad **plan ID note karo** — aage chahiye hoga. Instructions mein bhi exact steps hain (yahan tak ki `premium_subscription` likha hai). Ed ek break leta hai taaki tum apna plan set up kar sako.

---

## 📋 Key Concepts

| Concept | Matlab |
|---|---|
| **Deployment Protection (Vercel)** | Platform-level gate; subscription wale app ke liye OFF karo taaki Clerk hi protect kare |
| **Clerk + Vercel auth dono** | Double protection avoid karo — sirf Clerk rakho (app-level), Vercel gate hatao |
| **Handshake trace** | Front end ↔ back end JWT verification, request par dikhta hai |
| **Clerk Billing** | Clerk ka built-in subscription/billing platform |
| **Clerk payment gateway** | Out-of-the-box simple payment option (yahan test payments) |
| **Stripe** | Industry payment processor; Clerk se optionally connect hota hai |
| **Subscription plan** | Free/Premium tiers — name, key, monthly fee, annual discount |
| **Plan key** | Identifier (e.g. `premium_subscription`) — underscore, NOT hyphen |
| **Features** | Plan ke andar fine-grained capabilities; back end creds se gate kar sakte ho |
| **Authorization by tier** | User ke plan ke hisaab se functionality allow/deny — decoded JWT se |

---

## 💼 Backend Dev Ke Liye Note

Yeh lecture **authentication se authorization** ki taraf step hai — backend dev ke liye yeh distinction critical hai. Day 3 part 1 mein humne "kaun ho" (auth) solve kiya; ab "kya kar sakte ho" (authz) — subscription tier ke basis par. Pattern: JWT claims (Clerk plan/feature claims inject karta hai token mein) ko back-end route mein decode karke entitlement check karo, fail par `402 Payment Required` / `403 Forbidden` raise karo. Yeh **feature flagging / entitlement check** ka standard server-side gate hai — kabhi client par trust mat karo, hamesha back end par enforce karo (client UI hide kar sakta hai, par security back end par hoti hai). Billing flow stateless rehta hai kyunki entitlement JWT mein carry hota hai (Clerk webhook par subscription change hone par token refresh hota hai). Architecture lesson bhi hai: **layered protection avoid karna** — Vercel deployment gate + Clerk dono on rakhne se confusion; ek clear auth boundary rakho (yahan Clerk). Stripe integration production billing ka real-world standard hai — idempotency keys, webhooks (subscription created/cancelled/payment failed), aur reconciliation jaise concerns aate hain jab tum isse aage le jaate ho.

---

## ✅ Takeaway

- Production par bhejne se pehle **Vercel Deployment Protection OFF** karo — sirf **Clerk** ko protect karne do (double-auth avoid)
- `vercel --prod` se deploy; live app par sign-in → generate → **protected route + JWT handshake** kaam karta hai, streaming output aata hai
- Part 2 = **subscriptions via Clerk Billing** — idea generator ko paid feature banao; **Clerk payment gateway** (simple) ya **Stripe** (advanced) choose kar sakte ho
- Subscription plan banao: **key underscore se** (`premium_subscription`, hyphen nahi), monthly fee ($100), optional annual discount ($90), publicly available ON — **test payments only, real paisa nahi**
- **Features + decoded `creds`** se back end mein **authorization by subscription tier** implement kar sakte ho — auth (kaun) vs authz (kya allowed) ka clean separation

---

<details>
<summary>📜 Full Transcript (English)</summary>

Okay, so just before we deploy to production, I've gone back into Vercel. I'm going into the SaaS production project, and you see, it gives you a little preview of our production deployment right here. And I just wanted to show you I want to go to settings over here. And I want to go to Deployment Protection. We're in Vercel. So so we want to use Clark's protection. We don't want vassal to also add in its protection. So I go into deployment protection and I turn off vassal authentication and save. So we're no longer using that. Our SaaS app is exposed to the internet, but Clark will be protecting us. Okay. And with that we go here and we run vassal dash, dash, prod, which I already did a few seconds ago. So that ran and it deployed it to production. You could also do, uh, vassal Dot to deploy it first to the preview environment before you deploy it to production. But with that in mind, we can now launch it and see what it looks like. So we will open that. Here it comes. generate your new business idea. We'll sign in. We'll come in as, uh, me with because I've already set up an account. Here I am in, I come, uh, say continue. I am now logged in. This is logged in on the internet, logged in to my vassal app. Uh, I can now say generate business idea. It's now calling my back end the route that we've protected so that it knows that I'm logged in. And that handshake, we saw that trace being printed there. Uh, before we know that it does this handshaking between the front end and the back end, and here comes the results. Uh, it's printing it nicely. We're seeing streaming coming back. Uh, and, uh, we've got our results. This is a front end and back end secured app running, deployed in production. Um, and we can run it again to get another one. Uh, just you could simply refresh the page. At the moment, it's a very simple app, I admit. But nonetheless, I imagine the users will come flooding in when you release your business idea generator and get these different ideas. Okay, so with that, that wraps up the first part. If we go back to our instructions, uh, this is now, uh, finished up the first part with our security architecture, and we will now be moving to the second part, where we're going to allow people to be able to subscribe to this app. Okay. So in cursor, I'm opening up the week one folder, and I'm now going to day three part two to open the preview. It's a two parter today. Uh, now we're going to transform our SaaS application with subscription management will require a paid subscription to access the idea generator. This will allow you to take your own business idea and rapidly deploy it online for people to subscribe to your product. So the way we're going to do it is still through Clark. Clark not only offers this user management feature with social login, but also a billing platform as well, and brilliantly, it's hooked up. If you wish to stripe so that if you have a stripe account or you want to use stripe to collect payments, then you can use that via Clark, which is fabulous. So we're going to go back to the Clark dashboard. First of all, where we're going to go to configure and go to subscription plans. Uh, and if it's the first time, as it says, we'll have to press get started. So let's go and do that now. Okay. So the first step to enabling Clark billing is we go back to the Clark dashboard. Here we have it. You'll see your overview screen for the SaaS app. And you will also now have the message congratulations. Your application has users because you will have signed in yourself. And you'll see your own sign up where I see my two Gmail accounts here and go to configure. And on the left here, scroll down and you'll see there's like a billing settings and subscription plans. And when you go to settings I've already set mine up. So you'll. You should have a button that's like, uh, set up or create or something like that. I think it says in the instructions, but it will say. And you press that, uh, and in you come, there are these two different options. There's the one that comes out of the box with clerk called the clerk payment gateway, which is very simple, and we'll be using it. Um, and there's also, uh, more sophisticated is to connect it to stripe. If you use stripe to collect payments. And this would be an exercise for you should you wish to do so, should you actually have an idea that you do want to monetize right now on the internet? But that is all where you set it up. Um, so this is this is enabling it to start with, uh, and then you go to subscription plans here, and this is where you set up your plans, and you can see that, that I've got a free plan and a premium subscription plan. And you will be able to press the create plan button. You give your plan a name and a key, which should be something like a subscription hyphen plan. Uh, and uh oh, it can't have a hyphen in it. So, uh, like that, uh, give it a name, a description, a monthly base fee. And we're going to be using this only for test payments, and no actual money will take place. So you can you can do whatever you wish for our testing purposes. Uh, and uh, I think I put in 100 a month. And then if you wish, you can turn on the annual discount, which is saying if someone wants to, to pay for an entire year and commit for the year and pay upfront for the year, then this would be, um, the, the discounted monthly price that would apply for, uh, the year and, uh, leave publicly available on so that people get access to it. And that is all you need to do. Let me just go back to look at the one that I set up, so that you can make sure that yours matches mine. Exactly. Um, so, uh, um, hang on. Sorry. So, um, we're we're in configure and subscription plans. There we go. I lost it for one second in premium subscription, so I call mine The Key. I gave it was premium underscore subscription. I was doing a hyphen. It takes underscores. Called it premium subscription. I have it being $100 a month and a $90 a month is the discount if people choose to commit annually. So that's what you could put in if you want to match what I've got. Exactly. And I've got that turned on. Um, and features, you may imagine this, this is where you can configure different features that the user subscribes to. And then you can imagine that in our back end route where we've got those, those creds, we could use that to figure out which features the user has access to. If that's how you take this a step further, uh, and that can be an exercise for you should you wish. Okay. And once you've done that, come back here. And this has the instructions for doing it. Look, it even says premium underscore subscription. So, uh, follow all of this and keep a note of what plan ID that you used. Um, and, uh, I'll break for a second for you to do that and see you in a minute.

</details>
