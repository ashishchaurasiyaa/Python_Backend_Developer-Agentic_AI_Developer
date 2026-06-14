# L102 — Building the Frontend for Your Production AI Agent System

> **Week 4 · Day 3** · ⏱️ ~8 min

---

## 🎯 TL;DR

Day 3: Alex capstone ka **front end + API layer** add karte hain — Next.js app (static export) → S3 → CloudFront CDN, plus ek backend API Lambda jo Aurora se data laata hai, sab API Gateway ke peeche, Clerk auth ke saath (Week 1 wala SaaS setup reuse karke). Yeh lecture architecture samjhati hai aur Clerk env config karti hai.

---

## 🗣️ Hinglish Explanation

### Aaj ka mission

Week 4, Day 3. Aaj **capstone ka build-out complete** karte hain front end add karke. (Enterprise-grade banana abhi baaki hai — wo Day 4.) Recap of Alex:
- **Alex** = SaaS commercial financial planner app, **subscription-based** users ke liye
- **Week 3**: research agent banaya
- **Day 1 (this week)**: database — **Aurora Serverless v2**
- **Day 2** (big day): **5 agents on Lambda** orchestrating financial planning
- **Aaj (Day 3)**: front end — par "front end" se matlab hai **front end + API layer** jise wo call karega

### Agent diagram (one more time)

Ed diagram dohrata hai (chahta hai ab "click" ho jaaye):
- **5 blue boxes** (middle): agent deployment — **planner** jo orchestrate karta hai **tagger** ko (workflow-style, plain Python loop se tagger ko bar-bar call), aur tools ke through **reporter, charter, retirement** ko call karta hai
- **Yellow queue (SQS)**: planner ispe sunta hai — Day 2 mein test kiya
- Sab agents **Bedrock frontier model** (Nova; tum OSS 120B try kar sakte ho) use karte hain
- Sab **Aurora Serverless v2** database use karte hain
- Diagram mein **NOT shown**: Week 3 ka pura **SageMaker + Bedrock** wala side (research/embeddings) — wo bhi mix mein hai, mentally rakho

### Production-grade kyun? (Ed ka core point, "100 times" hammered)

Yeh isliye production-grade hai kyunki humne **ek hi runner mein OpenAI Agents SDK code** (`await Runner.run(...)`) jaisa kuch nahi banaya jisme tools doosre agents ko in-process call karein. Balki — **har tool call ek alag Lambda serverless function ko call karta hai**. Toh har blue box ek **totally separate deployed API/service** hai jo serverless chal rahi hai. Planner ke tool calls alag Lambda functions ko hit karte hain — aur wo Lambda **agent hone ki zaroorat nahi**: wo plain Python ho sakta hai ya kuch bilkul alag. Planner ko pata hi nahi, wo bas "tool use" kar raha hai. **Har agent = separate Lambda** approach **scalable** aur **production agentic systems ke liye bahut common** hai.

> **Background — yeh kyun matters:** Monolithic agent (sab kuch ek process) vs distributed agents (har ek apni service). Distributed mein har agent **independently scale**, deploy, version, aur monitor ho sakta hai; ek crash poore system ko nahi giraata; aur tool-call boundary ek clean API contract ban jaati hai. Yeh microservices philosophy ka agentic version hai.

### Aaj kya add ho raha hai (top-left of diagram)

Do cheezein add hongi:
1. **Front end** — ek **Next.js app** jo **static website** banega, **S3** par deploy hoga, phir **CloudFront distribution** ke through internet par push hoga
2. **Backend API** — ek aur **Lambda function** jise front end call karega khud ko populate karne ke liye; yeh API Lambda **Aurora Serverless DB query** karke UI ke liye data laata hai

> **Background services:**
> - **Next.js** — React-based framework. **Static export** mode mein wo pre-rendered HTML/CSS/JS files banata hai (no Node server needed) — perfect S3 + CDN hosting ke liye.
> - **S3** — *Simple Storage Service*, object storage; static website files (HTML/JS/CSS) host kar sakta hai.
> - **CloudFront** — AWS ka **CDN (Content Delivery Network)** — files ko duniya bhar ke edge locations par cache/serve karta hai, fast + global. S3 ka origin banta hai.

### Do technicalities (Week 1 se yaad)

1. **CORS (Cross-Origin Resource Sharing)** — browser (front end) ko **authority** chahiye backend ko call karne ki, kyunki origins alag hote hain. Sahi CORS setup zaroori hai warna browser request block kar dega.
2. **API Gateway** — front end **directly Lambda call nahi karega**; wo **API Gateway** call karega. Yeh enterprise-robust tareeka hai kyunki API Gateway ko **rate limiting + throttling** se configure kar sakte ho taaki API abuse na ho. Best practice.

> **Background — API Gateway:** AWS managed service jo HTTP endpoints expose karke unhe backend (Lambda, etc.) se connect karta hai. Yeh authentication, throttling, rate-limiting, request validation, CORS, aur logging ek hi jagah handle karta hai — ek **front door** for your APIs.

### Detailed diagram (Guide 7 front-end)

Cursor mein Alex project → **guides → guide 7 front end** → preview ("building Alex's front end"). Yeh detailed diagram dikhata hai:
- **Clerk** (auth) wapas aa gaya — Week 1 se familiar
- Web pages **CloudFront distribution (CDN)** ke through deploy
- Data ke liye **static files** ek **S3 bucket** mein
- Browser ke backend requests **API Gateway** ke through → **Lambda** → **SQS queue** par trigger → agents call → sab **Aurora** se data

> **Clerk kya hai:** managed authentication/user-management service — sign-up, login, sessions, subscription plans sab handle karta hai. Week 1 mein SaaS app ke liye set kiya tha.

### Step 1: Clerk setup (good news — reuse!)

Instructions Clerk dashboard par naya subscription plan/account banane ko kehti hain — **par zaroorat nahi**, kyunki **Week 1 ka SaaS application setup reuse** kar sakte ho (wo "SaaS" naam se hai; baad mein rename kar sakte ho). Naya banana ho toh dashboard par bana lo, warna purana SaaS repo khol ke uska `.env` use karo.

**`.env` file banao `front end` directory mein** (dhyan: `front end` mein, parent mein nahi):

```bash
# front end/.env   (NOT in parent — in front end app!)
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_test_...      # public key (PK se shuru)
CLERK_SECRET_KEY=sk_test_...                       # secret key (SK se shuru)
# ... baaki Clerk variables jaisa instructions mein diya hai, copy-paste
```

- **`NEXT_PUBLIC_...`** prefix Next.js ko batata hai ki yeh variable **browser** mein expose hona safe hai (public). Secret key kabhi public-prefix nahi.
- File ka naam **`.env`** hi hona chahiye, aur **`front end`** folder mein hi — yeh common galti hai.

### Step 2: Root `.env` mein Clerk JWKS URL

Project **root** directory (Alex root) ke `.env` file mein ek **server environment variable** add karo — **Clerk JWKS URL** (transcript mein "JDBC URL" bola gaya, par yeh actually Clerk ka **JWKS URL** hai — JSON Web Key Set, jisse backend Clerk ke JWT tokens verify karta hai):

```bash
# Alex root/.env  (server-side)
CLERK_JWKS_URL=https://<your-app>.clerk.accounts.dev/.well-known/jwks.json
```

Week 1 wala actual value use karo, ya Clerk app se le lo (instructions batati hain kahan milega). Iske baad **moment of truth** ke kareeb pahunch jaate hain — "let's go do this."

> **Background — JWKS:** jab Clerk user ko authenticate karta hai, wo ek signed **JWT** issue karta hai. Backend (API Lambda) us token ka signature verify karne ke liye Clerk ki **public keys** chahiye, jo **JWKS endpoint** (`/.well-known/jwks.json`) par milti hain. Isi se backend bharosa karta hai ki request kisi authenticated user se aayi hai.

---

## 📋 Key Concepts

| Concept | Matlab |
|---|---|
| **Front end + API layer** | "Front end" se matlab Next.js UI + backend API Lambda dono |
| **Next.js (static export)** | React framework; static HTML/JS/CSS files banata hai S3 hosting ke liye |
| **S3 (static website)** | Object storage jahan front-end ki static files rakhi jaati hain |
| **CloudFront (CDN)** | Edge locations se static site globally + fast serve karta hai |
| **Backend API Lambda** | UI ko populate karne wala Lambda jo Aurora query karta hai |
| **API Gateway** | Front door for APIs — front end directly Lambda nahi, ye call karta hai; rate-limit/throttle |
| **CORS** | Browser ko cross-origin backend call karne ki authority dena |
| **Clerk** | Managed auth + subscriptions (Week 1 SaaS setup reuse) |
| **`NEXT_PUBLIC_` prefix** | Next.js mein browser-safe (public) env variable marker |
| **Clerk JWKS URL** | Public keys endpoint jisse backend Clerk JWTs verify karta hai (root `.env`) |
| **Each agent = separate Lambda** | Scalable, production agentic pattern — tool call → alag serverless service |

---

## 💼 Backend Dev Ke Liye Note

Backend dev ke liye yahan do important production patterns hain. **(1) Static front end + CDN**: SPA/Next.js ko **S3 + CloudFront** par host karna ek classic cost-effective, infinitely-scalable pattern hai — koi web server nahi, sirf static assets edge par cached. Tumhara API state-bearing backend alag rehta hai. **(2) API Gateway in front of Lambda**: kabhi bhi Lambda ko seedha internet par expose mat karo — Gateway ko auth, throttling, rate-limiting, CORS, request validation ki **single choke point** banao. Yeh tumhare nginx/Kong/Envoy gateway ka managed serverless equivalent hai. Auth ke liye **JWKS-based JWT verification** seekho: stateless tokens, signature public keys (JWKS endpoint) se verify, no DB session lookup per request — yeh scalable auth ka standard hai. Aur `.env` mein public vs secret separation (`NEXT_PUBLIC_` prefix) yaad rakho — client bundle mein kabhi secret leak na ho.

---

## ✅ Takeaway

- Aaj front end (Next.js static → S3 → CloudFront CDN) **aur** backend API Lambda (Aurora query) add ho raha hai, sab **API Gateway** ke peeche
- Core production lesson: **har agent ek alag Lambda/service** hai — planner ke tool calls alag serverless functions hit karte hain (scalable, common pattern)
- Front end **directly Lambda nahi**, **API Gateway** call karega (rate limiting + throttling) — aur **CORS** sahi set karna padta hai
- **Clerk auth** Week 1 SaaS setup se reuse: `front end/.env` mein publishable + secret keys (`NEXT_PUBLIC_` public ke liye), root `.env` mein Clerk JWKS URL
- `.env` `front end` folder mein hi banana hai, parent mein nahi — common galti

---

<details>
<summary>📜 Full Transcript (English)</summary>

And welcome back. I am, I am looking forward to today. It is week four. It is day three. It is the day that we complete the build out of the capstone project by adding on the front end. It's not the end of the capstone project because we still have to make it enterprise grade, but it's going to be a lot more built out in the course of the next day. So one more time to remind you what Alex, the financial planner, is, although I think you're pretty familiar with this now, SaaS commercial application to be a financial planner with a subscription ability for users. We built the research agent last week, and then two days ago, we built out the database capability using Aurora V2, serverless. And yesterday, which was a big day. Yesterday, we built out five different agents running on Lambda to orchestrate the process of doing financial planning for one of our users. And today we're going to be adding the front end. But when I say front end, I really mean like the front end and the back end, the front end and the API layer that it will call to. And you're pretty familiar with the agent diagram by now, but I'm going to show it to you one more time. And I do hope by now this is really clicking. Yesterday we built those four. There's four. There's five blue boxes in the middle. The agent deployment the planner that orchestrated amongst the tagger which remember was through more of a workflow, just a series of Python code to orchestrate the calling of tagger many times and then using tools, calling out to reporter, charter and retirement. We also built that yellow queue, the SQS. We built the ability to have a queue. That planner listened on and we tested that out. And of course, all of them used Bedrock Frontier model running on bedrock. We're using Nova. Hopefully you're trying out OSS 120 and it's using our database Aurora serverless v2. And you'll note what I haven't included on this diagram is that of course it was tapping into everything we did last week. We also had SageMaker and bedrock that way in the mix as well. So there's a whole side of this which is layered on the on the right, perhaps that I'm not showing here as well that you hopefully have in the back of your mind too. And again, I want to make the point that one of the things that makes this production grade is that we didn't just take a piece of software that had, like OpenAI agents SDK code, using tools to call other agents in one runner in one await runner run. Uh, but rather the way it worked is that each of those tool calls resulted in a call to a different lambda serverless function. So really, you can imagine each of these blue boxes, each of these agents is like a totally separate, uh, API. It's a totally separate deployed service running serverless on AWS. And the tool calls in planner were able to call out to different Lambda functions, and it didn't need to be an agent that could have just been Python code, or it could have been doing something completely different. It didn't know that. It just knew it was using its tool. But this approach of deploying each agent as is a separate lambda. Serverless function, is A, is a is an excellent, scalable approach and a very common approach for deploying production strength agentic systems. Okay, so hopefully you've already got that one. I really hammered at home 100 times. Uh, and you've seen it in the code and hopefully that's all clicking for you. So what are we doing today? We are of course adding on these two things. On the top left there. We're adding on our front end, which is going to be a Next.js app that we will we will deploy, we will put that Next.js app. We will we will make it create a static website, and then we will deploy that to S3. And then we will make a CloudFront distribution so that it's pushed out to, to the internet. We'll also have a backend API, another Lambda function that can that can be something that the front end can call to in order to populate itself. And of course I'm not showing it here, but that that Lambda API can also, uh, query the Aurora serverless database, of course, to retrieve information that will be shown in the UI. So that's how this all fits together. And you hopefully remember as well that one of the technicalities that's that's that's difficult is we have to be careful about cause about making sure that we've got the right cross origin setup so that that browser, that front end has the authority to be calling the back end. And there's another technicality that you also hopefully remember. It won't be directly calling Lambda. It will be calling the API gateway. And the API gateway is definitely the way to do this in an enterprise robust way, because it's something that we can configure with with rate limiting and throttling to make sure that that API isn't abused. So we'll be doing that as well. It's all great best practices. Let's get to it. And here we are back in cursor the Alix project, which are the project we'll be in. And we're going to go into guides and we're going to guide seven front end. Open the preview. Here it is building Alex's front end. So here's another of these diagrams that is a little bit more detailed than the one I had before. You can see a few things which are worth pointing out. One is of course, we're bringing back Clark. I didn't even mention that in the previous diagram, but we're going to have Clark to be doing our auth, which we know well from all the way back in week one. Uh, and then our web pages will be deployed through the CloudFront distribution. Uh, the CDN stands for Content delivery network is what sort of thing CloudFront is. Uh, and, uh, in order to get that data, it will be using static files. It will have put in an S3 bucket. And when it makes the when the browser makes the backend requests, they'll be coming through API gateway. And that will be coming through to our Lambda. And that will be putting trigger on the SQS queue which is calling our agents. And all of this is getting data from Aurora. So that is what we have. And the first step is to get going with Clark. And there I have some good news. So the instructions tell you how to go to the clerk dashboard and set up a new subscription plan account for users to come into your product. But of course, the good news is that none of that is necessary, because we already did this in week one for the SaaS application, and we can reuse exactly the same setup. Just it's just called SaaS. And you can always change change the name in the future if you want to. But for now, let's just stick with what we've got. So you could, if you want, go into the dashboard and set up a new account there or a new application. But why not just open the SaaS repo that you built before? Go to the env file and find your various keys. And now we can just configure that for ourselves now. So you need to create a file in the front end directory. So in this directory there needs to be a file called env. Be careful about this. And that needs to to look like this. It needs to have a next public plug publishable key with the PK. That's the public one. Next. Sorry. Then just Clark's secret key with the secret key that begins ESC. And then just copy and paste in the rest of this so that it's got those other variables set. So be sure this needs to be called EMV and it needs to be right there in front end, not in the parent but in front end in our app. So go and do that and then we will move on to, to uh, getting close to a moment of truth. The next step is to edit the EMV file in the Alex, the root directory, the project root. So this is a server environment variable and put in that Clark JDBC URL. You remember that, uh, take the one that you actually have from week one. Take it and put it in that file. Or you can always go, if you already cleared out that repo, then of course you can go to the Clark app and take it from there. Uh, and there are the instructions of where to find it, but that URL needs to go in your EMV file. And with that, we should be ready to put the show on the road. Uh, let's go do this.

</details>
