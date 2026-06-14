# L27 — Migrating Your AI App from Vercel to AWS for Production Scale

> **Week 1 · Day 5** · ⏱️ ~9 min

---

## 🎯 TL;DR

Vercel par chal rahi SaaS app ko AWS deployment ke liye reshape karte hain: front end ko **static export** banao, fetch URL ko `/api/consultation` par point karo, aur ek naya **`server.py`** banao jo API + health check + static front end teeno serve kare. Saath mein `.env` mein **AWS region + account ID** add karo.

---

## 🗣️ Hinglish Explanation

### Context: Day 5 part three — same app, naya destination

Pichle din tak hamari healthcare consultation SaaS Vercel par live thi — Next.js front end + FastAPI backend + Clerk auth + subscription billing + OpenAI streaming. Ab Day 5 ka mission hai **same app ko AWS par production-grade banana**. Vercel ne deploy ko trivial bana diya tha; AWS thoda zyada manual hai par usse industrial-strength scale milti hai.

⚠️ **Pehle backup lo.** Ed warn karta hai: yeh `SaaS` folder abhi tak GitHub par push nahi hua, sirf ek local directory hai. Hum ise AWS ke liye **modify (destroy)** karne wale hain. Toh agar Vercel wala version pasand hai, toh folder copy karke kahin `SaaS_Vercel` naam se rakh lo, taaki reference rahe.

Current project structure roughly aisa hai:

```
SaaS/
├── pages/        # Next.js pages (front end, TSX)
├── api/          # backend (index.py — FastAPI)
├── styles/
└── public/
```

### Change 1: Front end ko STATIC website banao (`next.config`)

Vercel par front end **dynamically on demand** serve hota tha (har request par server render). AWS approach mein hum front end ko ek **static export** banayenge — yaani pure client-side HTML + JavaScript + CSS files jo build time par generate ho jaati hain. Phir koi bhi simple server (ya hamara apna backend) inhe serve kar sakta hai.

Iske liye Next.js config file mein `output: 'export'` add karo:

```js
// next.config.js
/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'export',   // pure static site generate karo (HTML/JS/CSS)
};

module.exports = nextConfig;
```

**Static export kya karta hai?** `npm run build` chalane par Next.js poori site ko pre-render karke `out/` folder mein daal deta hai — koi Node server runtime nahi chahiye. Yeh fast, cheap, aur cacheable hota hai. Trade-off: server-side rendering / dynamic routes ki kuch features chali jaati hain, par hamari app client-side fetch karti hai isliye perfect fit hai.

### Change 2: Front end ka fetch URL update karo (`pages.tsx` / `product.tsx`)

Vercel par front end hamesha plain `/api` par POST karta tha. Ab AWS par front end aur backend **same server par** chalenge, isliye route ko specific banana padega — `/api/consultation`.

`pages.tsx` (front end → backend call wali line) mein:

```javascript
// PEHLE (Vercel):
const response = await fetch('/api', { ... });

// AB (AWS):
const response = await fetch('/api/consultation', { ... });
```

Yeh wahi line hai jahan front end backend ko call karta hai. `/consultation` add karke hum route ko explicit aur same-server-friendly bana rahe hain. File save karo.

### Change 3: Naya backend — `server.py` (chunkier version)

Purani `api/index.py` ko delete nahi karte (reference ke liye rakh lete hain) — uski jagah naya **`server.py`** banate hain jo zyada feature-rich hai. Iske andar 4 cheezein hoti hain:

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from openai import OpenAI

app = FastAPI()

# 1. CORS middleware — sirf hamara front end backend ko call kar paaye
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # baad mein tighten karenge
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

openai = OpenAI()

# 2. Main AI route — ab /api/consultation
@app.post("/api/consultation")
async def consultation(request: Request):
    # ... same visit parsing, system prompt, user prompt as before ...
    def event_stream():
        stream = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[...],
            stream=True,
        )
        for chunk in stream:
            delta = chunk.choices[0].delta.content or ""
            yield delta
    return StreamingResponse(event_stream(), media_type="text/plain")

# 3. Health check — AWS isse poochega "app theek hai kya?"
@app.get("/health")
def health():
    return {"status": "healthy"}

# 4. Static front end serve karo (root URL par index.html)
app.mount("/", StaticFiles(directory="static", html=True), name="static")
```

Har piece ko samjho:

1. **CORS middleware** (Cross-Origin Resource Sharing) — yeh ek **security setup** hai jo decide karta hai ki **kaun se origin (website)** hamare backend ko call kar sakte hain. Bina iske, koi bhi dusri website ek fake front end bana ke hamari API ko call kar sakti hai (paise/quota churaane ke liye). Front-end devs ke liye CORS errors "bane of existence" hote hain — abhi loosely set kar rahe hain (`*`), baad mein tighten karenge. Agar samajh na aaye toh as-is use karo aur research karo.

2. **AI logic + streaming** — visit parsing, system/user prompt, OpenAI call, `StreamingResponse` — yeh sab Vercel wale version se **bilkul same** hai. Sirf route `/api/consultation` ban gaya.

3. **Health check route (`/health`)** — ek naya route jo simple JSON `{"status": "healthy"}` return karta hai. AWS (App Runner) ise periodically hit karega yeh confirm karne ke liye ki container zinda aur healthy hai. Yeh production deployment ka standard pattern hai.

4. **Static site serving** — yaad karo, backends sirf API routes nahi, **poora web page bhi serve** kar sakte hain. Yahan agar koi root URL (`/`) hit kare, toh `index.html` (jo humne static build se banaya) serve ho jaata hai. Matlab ek hi backend = API server + health endpoint + front-end host. Sab kuch ek hi process mein.

### Change 4: `.env` file — AWS secrets add karo

Apne purane `.env` (jismein already 4 secrets the) se copy karke shuru karo:

```bash
# Pehle se the (Clerk + OpenAI):
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_test_xxx
CLERK_SECRET_KEY=sk_test_xxx
CLERK_URL=https://your-clerk-domain.clerk.accounts.dev
OPENAI_API_KEY=sk-xxx

# AB NAYE 2 add karo (AWS ke liye):
AWS_DEFAULT_REGION=us-east-1
AWS_ACCOUNT_ID=123456789012
```

- **`AWS_DEFAULT_REGION`** → woh AWS region jo tumhare **sabse paas** hai (latency kam). Jab tum root/IAM account banate ho toh console usually closest region default karta hai. Common choices:
  - Europe → `eu-west-1` (Ireland)
  - India → `ap-south-1` (Mumbai)
  - US West → `us-west-1` / `us-west-2`
  - US East → `us-east-1` (Amazon ka pehla region; Ed yeh use karta hai)
  - "AWS regions" google karo — poori list aur location mapping mil jaayegi.

- **`AWS_ACCOUNT_ID`** → woh **12-digit number** jo console mein tumhari user ID ke paas likha hota hai. Copy karke yahan daalo.

### Quick flow recap

1. `SaaS` folder ka backup banao (`SaaS_Vercel`)
2. `next.config` mein `output: 'export'` add karo
3. `pages.tsx` mein fetch URL → `/api/consultation`
4. Naya `api/server.py` banao (CORS + consultation + health + static serve)
5. `.env` mein `AWS_DEFAULT_REGION` + `AWS_ACCOUNT_ID` add karo

Ab app AWS deployment ke liye prepared hai — agle lectures mein Docker, ECR aur App Runner aayenge.

---

## 📋 Key Concepts

| Concept | Matlab |
|---|---|
| **Static export** | Next.js `output: 'export'` — site ko build-time par pure HTML/JS/CSS files mein convert karna |
| **`/api/consultation`** | Specific backend route — same-server setup mein clear routing ke liye |
| **`server.py`** | Naya FastAPI backend: API + health check + static front-end serving, sab ek mein |
| **CORS middleware** | Security: sirf authorized origins backend ko call kar paayein |
| **Health check (`/health`)** | JSON `{"status":"healthy"}` route — AWS isse container ki sehat check karta hai |
| **Static serving by backend** | Backend root URL par `index.html` serve karke front end host kar sakta hai |
| **AWS region** | Closest datacenter location (e.g. `us-east-1`, `ap-south-1`) — latency ke liye |
| **AWS account ID** | 12-digit unique account identifier, ECR/ARN ke liye chahiye |

---

## 💼 Backend Dev Ke Liye Note

Yeh lecture ek classic backend pattern dikhati hai jo Python devs ko familiar lagega: **single-binary / single-process deployment** jahan ek hi FastAPI app API aur static assets dono serve karta hai (`StaticFiles` mount). Yeh Flask + `send_from_directory` ya Django ke `staticfiles` jaisa hi hai. Vercel ke "front-end alag, serverless functions alag" model se yeh shift important hai — ab tum ek **monolithic container** bana rahe ho jise kahin bhi deploy kiya ja sakta hai (App Runner, ECS, EC2, k8s). CORS middleware ko reverse-proxy/API-gateway ki allow-list ki tarah socho. `/health` endpoint har production backend mein hona chahiye — load balancers, orchestrators, aur uptime monitors isi par depend karte hain (Kubernetes mein yeh `liveness`/`readiness` probe banta hai).

---

## ✅ Takeaway

- AWS ke liye app ko reshape karo: **static front end** + **single backend** jo sab kuch serve kare
- `next.config` → `output: 'export'`, fetch URL → `/api/consultation`
- Naya `server.py` = CORS + AI consultation route + `/health` + static `index.html` serving
- `.env` mein `AWS_DEFAULT_REGION` (closest) aur `AWS_ACCOUNT_ID` (12-digit) add karo
- App ko modify karne se pehle **backup lo** — yeh folder abhi GitHub par nahi hai

---

<details>
<summary>📜 Full Transcript (English)</summary>

Okay, continuing on day five for part three. Getting our application ready, we need to modify our SaaS application to deploy to AWS. Now look, if you quite like the vassal application, then you may want to take a backup of this SaaS folder and put it somewhere else. Because I realize we've not pushed this into GitHub or anything. This is just all just a directory. So. So you might want to copy this and call it SaaS Vassal or something. Just so you have that to hand, because we're about to destroy it as we prepare things to deploy to AWS. So our currently our project should look like this. We've got pages and API and styles and public. So what we're going to do first is make it so that our front end is is written as a static website. We're going to generate the final product that got served up before dynamically on demand. So we're going to uh, create a static export so that now it's pure client. It's just a set of HTML files generated HTML, JavaScript, and stylesheets generated from the Next.js app that we put together. Um, and so we are going to change this file next configure to include the fact that we want it to output an export. So I'm copying this I'm going to next configure. Here it is. And I am going to paste over this. You can see all it's done is it's put this in here which allows us to output this whole site as a static site that can be served up our front end part of it. Okay. Back we go. We've made that first change. All right. We're now going to update our front end calls. Now before we're used to with with the vessel we used to be be always posting to slash API. Now we need to change this. Now we're going to change this to be slash API slash consultation because we need to because we're going to have everything running on the same server. You'll see more in just a second. But what we have to basically do is find this line here which is in the file product TSX, and change it from that to this. We're basically adding slash consultation in into the fetch uh, call. So let's find this. It's in pages TSX. And if we look in here we should be able to find where it's making that call. It's going to be a bit higher. Bit higher. Here we go right here. Fetch events API. This is where it's calling. The front end is calling the back end right here. And we're making that slash API slash consultation. That's the second change I've saved that file. That is done. Okay, back we go. All right. Now we are now going to to make a new backend file called server. And it's basically going to be an alternative to what we have Index.py right now. And it's quite a bit chunkier. Let me do that for you right now and then we'll talk about it. Copy that. And now I go to API. There is Index.py. That's not going to get used anymore. We're going to make a new file. We could just rename that one. But we might as well keep keep that around for reference. We'll make a new file. We'll call it server.py. Here it is. And the contents will be this. Let's, let's take a dig into this to see what's going on. Okay. So some things are the same as before. We start by creating a fast API app. So far so good. We've got something interesting here called Cors middleware. And this is another of those stories. This is another of those rabbit holes we could go down to uh, is about the security setup. That means that only the right front end, uh, is allowed to call our back end, preventing other people from building websites that also call to our back end pretending to be our front end. And we've got something set up here, uh, that is designed to to make sure that we don't block our front end from calling us. And later we're going to put some more controls around this. So I'm not going to go into too much detail on Cors front end. People know this so well because cause errors. It's like the bane of a front end developers existence. Uh, but for others, you can just take this as it is and do some research if you'd like to know more. This is the same as before. The visit is the same as before. The AI stuff is the same as before. Not much changed there. Uh, as is the user prompt for this part. We've changed this route, so it's now slash API slash consultation. Uh, and the actual AI code is exactly the same as is our streaming response. This is all the same. Okay, this is something new. We've got a new route called Slash Health, which is a health check. And it's just going to return. Status is healthy as a JSON object. So that's just something else. And AWS is going to want us to have that. It's going to use this to check that things are going well. And then we've got something else here. And this is kind of interesting. I mentioned way back when we were talking about what backends can do that, that backends can service your APIs and can respond with different API routes with, with different things to do, but they can also serve up a whole static site. They can be your your provider of your web page. And that's what's happening here. If someone asks for slash for just the root, uh, the root URL of our, of our website, then this is going to serve up index.html from our static, uh, site that we are going to build. So this here is something which is allowing our back end to serve the entire front end that we will have generated as a static website. And it can serve that up to someone that hits this root. And if you're not following all of this, get a general flavor for it. Come back later. Play with this yourself. And in time I think this will come together. Some of you have probably seen this stuff before and know exactly what I mean. So that is the new contents of our server dot Pi, our back end serving an API, serving a health check, and also being able to serve a static website for our front end. Okay. Next is to create a dot EMV file which will have our secrets that we'll use for this deployment. And you can start by copying the EMV that you already set up, its mind ones right there that you're already set up for this project before. And it contains, I think, all four of these secrets at the top that you need the next public clerk publisher key, the clerk secret key, the clerk URL, and the OpenAI API key. But now you need to add in two more ones, which are the default AWS region. And now this should be the AWS region, which is closest to you that you want to use as your default. Now, I do believe that when you first signed in as your root account or your IAM account, that place I showed you, it shows the region should default to the one closest to you, but otherwise if you just google AWS regions, there's a AWS page which goes through all of the regions and which ones are closest to different locations. Uh, there's one. If you're in Europe, then I think EU West one, which I think is in Ireland, is a very common choice. There's many Asia Pacific ones. There's one in Mumbai that's that's very common I think as, as is very large. Um, and uh, there's on the West coast, of course, US West one and US West two, uh, very, uh, very much used uh, so these, uh, all the different regions you could pick from, there's a huge number of them. Pick the one that's closest to you, and that should be the one that you go to. On the console and us East one, which was I think the first one that they had, uh, is, uh, the one that is also closest to me and the one that I choose, um, and then AWS account ID this is, of course, the 12 digit number that you took down carefully. Uh, that is on that is written by your user ID in the console that you can copy. So you should put all of those into a dot EMV file. I will go and do that myself right now and see you in a sec.

</details>
