# L94 — Setting Up Production Database Architecture for AI Agent Systems

> **Week 4 · Day 1** · ⏱️ ~6 min

---

## 🎯 TL;DR

Alex ka **data model** samjho: `users → accounts → positions → instruments` (+ `jobs` = agentic runs), Clerk user ID se multi-tenant isolation. Phir **`uv run reset_db --with-test-data`** se DB reset + migrate + seed + ek test user (3 accounts, 5 positions) populate karo. Day 1 done — kal 5 Lambda agents banenge. **Reminder: har baar infra rebuild karne par secrets `.env` mein wapas copy karne padenge.**

---

## 🗣️ Hinglish Explanation

### Data model samjho (entity diagram)

Test data run karne se pehle Ed data model dikhata hai. Yeh ek **SaaS system** hai — har user apna **separate portfolio** dekhega, sab completely isolated.

#### Tables aur unke relationships

```
            ┌──────────┐
            │  users   │  (clerk_user_id se keyed)
            └────┬─────┘
                 │ 1-to-many
            ┌────▼─────┐         ┌──────────┐
            │ accounts │         │  jobs    │  (agentic runs/tasks)
            └────┬─────┘         └──────────┘
                 │ 1-to-many       ▲ (user ke many jobs)
            ┌────▼──────┐
            │ positions │  (holding: e.g. "10 IBM")
            └────┬──────┘
                 │ many-to-1
            ┌────▼────────┐
            │ instruments │  (symbol, name, current_price)
            └─────────────┘
```

| Table | Matlab |
|---|---|
| **users** | SaaS users — har ek **`clerk_user_id`** se keyed, taaki user sirf apna data dekhe (multi-tenant isolation) |
| **accounts** | Ek user ke multiple accounts — brokerage, retirement, savings |
| **positions** | Ek holding — jaise "main 10 IBM stock rakhta hoon" (quantity = 10). Account ke andar |
| **instruments** | Stock/ETF entity — **symbol, name, current_price**. IBM/Google/Amazon stock = ek-ek instrument |
| **jobs** | "runs/tasks" — job openings nahi! Jab agentic process kick off hota hai, ek naya jobs entry banta hai. User ke many jobs ho sakte |

#### Relationships ka logic

- Ek **user** ke **many accounts** (brokerage + retirement + savings)
- Har **account** ke **many positions** (holdings)
- Har **position** ek **instrument** ko refer karti hai
- Ek hi **instrument** (jaise Amazon stock — one instrument, one price) ko **many alag log alag accounts** mein hold kar sakte hain

#### Finance simplification

Finance log bolenge ki **`current_price`** ko instruments table par rakhna "lame" hai — sahi tareeka ek **time-series of prices** hota. Ed ne pehle time-series socha tha par realize kiya ki bahut finance detail mein bog down ho jaayenge. Toh simplification: **har instrument ka ek current_price**. (Finance log isse time-series mein extend kar sakte hain — fantastic update. Par yeh production deploy ke liye theek hai.)

### Test data populate karo

```bash
cd backend
cd database
uv run reset_db --with-test-data
```

Yeh kya karta hai:
1. **Database reset** (agar already reset nahi tha)
2. **Migrations chalata hai** (schema)
3. **Seed data load** karta hai (22 instruments)
4. **Test user create**: `user_001` ke saath:
   - **3 accounts**
   - **5 positions** ek **401(k) account** mein (positions = kuch shares in an instrument)

Tum entity diagram se relate kar sakte ho — user, 3 accounts, aur positions (shares in instruments).

### Verify

```bash
uv run test_data_api
```

Ab output:
- **Database size = 8 MB** (pehle 7 MB tha — thoda bada)
- **5 tables found** jo humne setup kiye
- Sab kuch working

Toh ab tum ek **populated Aurora database** ke owner ho — test user + accounts + positions + instruments ke saath.

### Cost reminder + CRITICAL re-deploy note

- **Schema zaroor padho** — point building karna nahi hai, par code dekho, satisfy karo ki samajh aa gaya
- **Billing & cost management** check karo (always)
- Day end / break ho toh **`terraform destroy`** karo
- Wapas kaam karte time **`terraform apply`** se rebuild karo

⚠️ **CRITICAL**: jab bhi infra **rebuild** karoge, woh **secrets (cluster + secret ARN) wapas `.env` mein copy karne padenge** — har baar! (Aurora destroy/recreate par ARNs/secret badal jaate hain.)

### Day 1 wrap-up

*"A gentle start to this big week."* Aaj cover hua:
- Multi-agent architecture + single agent loop (L89)
- Database architectures in AWS (L91)
- Aurora database build (L92-94)

**Kal (Day 2) huge hai** — 5 agents build + deploy honge (Lambda functions), ton of infrastructure. Ed bolta hai **"get a lot of sleep tonight."** Yeh course ka **80% point** hai — home stretch, 2 din deploying baaki.

---

## 📋 Key Concepts

| Concept | Matlab |
|---|---|
| **users table** | Clerk user ID se keyed; multi-tenant isolation (sirf apna data dikhe) |
| **accounts** | Ek user ke multiple accounts (brokerage/retirement/savings) |
| **positions** | Holding — quantity of an instrument in an account |
| **instruments** | Stock/ETF — symbol, name, current_price (one price per instrument) |
| **jobs** | Agentic runs/tasks (job openings nahi); user ke many jobs |
| **current_price simplification** | Time-series ki jagah single price per instrument (deliberate) |
| **reset_db --with-test-data** | DB reset + migrate + seed + test user (3 accounts, 5 positions) |
| **401(k)** | US retirement account type — test positions yahaan hain |
| **terraform destroy/apply** | Cost control — break par destroy, wapas par apply |
| **Re-copy secrets** | Har rebuild par cluster+secret ARN `.env` mein wapas daalna |

---

## 💼 Backend Dev Ke Liye Note

Yeh ek textbook **normalized relational schema** hai jo har backend dev pehchaan lega — `users (1) → accounts (N) → positions (N) → instruments (1)` foreign-key chain, plus `instruments` ek **shared lookup/master table** (many positions point to one instrument, denormalization avoid). **`clerk_user_id` per row** = **row-level multi-tenancy** — har query ko user ID se scope karna padega, warna data leak (cross-tenant access) ho jaata hai; yeh production SaaS ka #1 security concern hai. Ed ka Clerk (auth provider) ID ko tenant key banana clean hai — auth aur data ownership ek hi identifier se tie hote hain.

**`jobs` table = async task tracking** — agentic run ka lifecycle (status, timestamps) DB mein persist hota hai, jaise tum Celery task state ya ek `runs` table maintain karte ho long-running background work ke liye. Yeh SQS pattern (L90) ke saath fit hota hai: API job create karke jobs row insert karta hai → SQS message → planner consume karke job update karta hai → front end polls jobs table for status. **`current_price` simplification** ek pragmatic engineering call hai — Ed scope creep avoid kar raha hai (time-series prices = alag table + ingestion pipeline + point-in-time query complexity); MVP ke liye denormalized current value theek, baad mein extract. Aur **destroy par secret ARN badalna** ek real gotcha hai: ephemeral infra ke saath secret references stable nahi rehte, isliye production mein log Secrets Manager ko **persistent** rakhte hain (DB cluster se alag lifecycle) taaki har rebuild par re-wire na karna pade.

---

## ✅ Takeaway

- **Data model**: `users → accounts → positions → instruments` (FK chain) + `jobs` (agentic runs); `clerk_user_id` se multi-tenant isolation
- `instruments` shared lookup table; **`current_price`** deliberate simplification (time-series ki jagah)
- **`uv run reset_db --with-test-data`** → DB reset + migrate + seed + test user (3 accounts, 5 positions in 401k)
- Verify: `uv run test_data_api` → 8 MB, 5 tables found
- **Cost control**: break par `terraform destroy`, wapas par `apply` — **par har rebuild par secrets `.env` mein wapas copy karo**
- Day 1 done (80% course point); **kal 5 Lambda agents** — sleep well!

---

<details>
<summary>📜 Full Transcript (English)</summary>

So the next thing we're going to do is run a script which populates our database with test data that we can use. But first, let me just show you what our model, what our data model actually looks like. There's a diagram here that describes our data model just so you understand what we're building. So at the top we have a users table. This is a SaaS system. Different users will be able to log in and see their own separate portfolios as they interact with the with the financial planner. And they should all be completely separate. And they're going to be keyed off a clerk user ID, which is how we're going to make sure that that only a user sees their data. Then a user has multiple accounts. Because a user like yourself, you might have a brokerage account, a retirement account, a savings account. So you can have multiple accounts and each account has multiple positions. A position is like a holding. Like I own ten IBM stock. That would be a position. The the value would be that would be the quantity would be ten. And the instrument, the IBM stock would be another entity in our database, an instrument which has a symbol, a name, and a current price. Now finance people along amongst you will say that it's. It is a bit lame to put current price on an instrument table like this. You should really have a time series of prices. And the first time I was going to build this, I was going to have a time series of prices. But I realized that we would get bogged down in lots of finance detail. So for finance people, if you want to take this a step further and really have a time series of current prices of prices, that would be a fantastic update to make. But for us, we're just going to have every instrument having a current price. A simplification that we will live with. It's still going to allow us to deploy everything nicely to production. So again a user has a user ID that has a number of accounts, each user number of accounts, and each account has a number of positions. And each position is in instruments. And of course you'd have like one instrument referring to IBM stock or Google stock or Amazon stock. And lots of different people could have different accounts, could hold positions in that same instrument, one instrument, one price representing Amazon stock. So that is how it holds together. And the only thing I didn't mention was jobs over on the right. And this is not referring to like, job openings, like a job you take. This is jobs as in runs, as in when we kick off our agentic process to manage things, it's going to create a new entry in this jobs table. So this is this is like tasks. That's how to think of this this this jobs table. And each user can have many of these jobs running. So that's the database schema that we're going to be building. And we've now got a test script to run that will populate that for one test account. So here we go I'm going back into back end and into database. And then I'm going to do UV run reset underscore db dash dash with test dash data. And off it goes. And this is now resetting the database if it wasn't already reset. Running the migrations loading in the seed data. And it's done it, it created a test user uh, user 001 with three accounts and five positions in a 401 account. And if you look back here, you'll see the user, the three accounts being created and the positions which are a certain number of shares in an instrument. So you can relate that back to the entity diagram, the schema that we just looked at a moment ago. And so now we are not only the proud owners of an Aurora database, but it's also a populated aurora database with a test user, some accounts and some positions and some instruments. And indeed, if I run the UV run test data API again, we'll see if it gives us more information. Now let's make that a bit bigger for us and we'll see. The database size is now eight megabytes slightly bigger. And it found the five tables that we we set up. And everything seems to be working well. So that is successfully populated database. Do look through the schema. As I say, the point is not necessarily to be doing the building, but by all means take a look through the code. Satisfy yourself that it's doing what I said and that you understand it so that it's clear how we are. We are going to now be taking this to continue our production build out, uh, and do do come through and look at your cost, your billing and cost management, as always in AWS. If this is going to be a break for you for, for for the end of this day. Then at the end of it, be sure to do a terraform destroy. And then when you're back to working again, do a terraform apply to build it again. All you have to do is please, please remember any time for this one. Anytime you build that infrastructure again, you're going to have to copy those secrets back into your env file. So you'll need to do that each time with with with this piece it's important to remember that, uh, but otherwise uh, that concludes the building of our database. I will see you back for the slides. Well, I'd say today was a gentle start to this big week. Uh, we covered multi-agent architecture, the agent loop, the single agent loop, the database architectures in AWS. And then we built our Aurora database. Tomorrow is a big day. Tomorrow is all about building and deploying agents. That will be Lambda functions. There'll be five of them. We're going to build a ton of infrastructure, so be sure to get a lot of sleep tonight because tomorrow is going to be huge. And it's worth mentioning that this is the 80% point on this course. You're coming into the home stretch. Two days of deploying ahead of us. I can't wait for it. I'll see you then.

</details>
