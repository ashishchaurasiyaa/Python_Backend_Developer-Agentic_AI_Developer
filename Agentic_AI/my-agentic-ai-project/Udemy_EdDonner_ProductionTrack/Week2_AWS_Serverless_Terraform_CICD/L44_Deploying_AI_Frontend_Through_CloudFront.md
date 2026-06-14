# L44 — Deploying AI Frontend Through CloudFront for Global Distribution

> **Week 2 · Day 2** · ⏱️ ~10 min

---

## 🎯 TL;DR

Next.js front end ko **static export** banakar **S3** par upload karte hain, phir uske upar **CloudFront** (global CDN) distribution laga ke poori duniya mein fast serve karte hain. Front end ka `fetch` call ab localhost ki jagah real **API Gateway** endpoint par jaata hai.

---

## 🗣️ Hinglish Explanation

### Recap: hum kahan khade hain

Ab tak Week 2 mein humne backend (digital twin chat agent) ko AWS par deploy kar diya hai — **Lambda** function + **API Gateway** + **S3** (conversation memory ke liye). Ab front end ko production mein le jaana hai aur usse real backend se connect karna hai. Yeh lecture front end ki deployment ka core hai.

Architecture jo hum bana rahe hain:

```
Browser → CloudFront (CDN, global)
            → S3 bucket (static Next.js site: HTML/JS/CSS)
Browser → API Gateway endpoint → Lambda (FastAPI backend) → S3 (memory)
```

### Step 1: Front end ko real backend se jodo (`twin.tsx`)

Pehle **API Gateway** ka URL chahiye. AWS console mein API Gateway par jaao, apni Twin API ka **invoke URL** copy karo (yeh public endpoint hai jahan backend reachable hai).

Front end code `components/twin.tsx` mein ek `fetch` call hai jo abhi `localhost:8000` (local dev backend) ko hit karti hai. Use real endpoint se replace karo — `/chat` route par POST karna hai:

```tsx
// PEHLE (local development)
const response = await fetch("http://localhost:8000/chat", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ message, history }),
});

// AB (production — real API Gateway endpoint)
const response = await fetch(
  "https://<your-api-id>.execute-api.<region>.amazonaws.com/chat",
  {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, history }),
  }
);
```

Isi line ki wajah se ab browser local server nahi, balki internet par live AWS backend se baat karega.

### Step 2: Static export enable karo (`next.config`)

**Next.js** by default ek dynamic Node.js server expect karta hai (SSR — server-side rendering). Lekin hum ek **pure static site** (sirf HTML/JS/CSS) chahte hain jo kisi bhi simple file host — jaise S3 — par chal jaaye, bina Node server ke. Iske liye Next ko **static export mode** mein daalna padta hai.

`next.config` (ya `next.config.ts`) abhi empty/no-config hai. Usme export config paste karo:

```ts
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "export",          // poora site static dump banao
  trailingSlash: true,
  images: { unoptimized: true }, // static export par Next image optimizer nahi chalta
};

export default nextConfig;
```

`output: "export"` hi wo magic switch hai jo Next ko bolta hai: server mat banao, ek `out/` directory mein saari static files generate kar do.

### Step 3: Static build banao

Terminal kholo, **front end folder** mein jaao, aur build chalao:

```bash
npm run build
```

Yeh **optimized production build** banata hai aur ek **`out/`** directory create karta hai. Andar dekho — pure traditional web files honge:

- `index.html` — home page
- `404.html` — not-found page (yeh humne front end configure karte waqt set kiya tha)
- JavaScript bundles, CSS, assets

Yeh sab TypeScript/Next.js code se **derive** hua hai aur **kisi bhi browser** par chalega — koi Node runtime ki zaroorat nahi. Yahi static export ka faayda hai.

### Step 4: S3 par upload karo (AWS CLI)

Pichle week humne `aws configure` chalaya tha (access key + secret + region set), isliye CLI ab authenticated hai. Front end folder se yeh command chalao:

```bash
aws s3 sync out/ s3://twin-frontend-<your-account-id>/ --delete
```

Breakdown:
- **`aws s3 sync`** → local folder aur S3 bucket ko sync karta hai (sirf changed/new files upload, smart)
- **`out/`** → source: humari static build directory
- **`s3://twin-frontend-<account-id>/`** → destination bucket. Bucket naam globally unique hona chahiye, isliye account ID suffix lagta hai
- **`--delete`** → jo files local build mein nahi hain par bucket mein padi hain, unhe hata do (bucket ko build ka exact mirror banao)

Enter dabate hi static site S3 par upload ho gaya.

### Step 5: Direct S3 test (static website hosting)

Pehle direct test — bina CloudFront ke:

1. S3 console → apna **front end bucket** kholo
2. **Properties** tab → neeche **Static website hosting** section
3. Wahan ek **endpoint URL** milega (`http://twin-frontend-...s3-website-<region>.amazonaws.com`)
4. Use naye browser tab mein kholo

Site load hoti hai: *"Hi there. What's on your mind today?"* — front end aur backend dono mil ke kaam kar rahe hain. Browser front end ko S3 se le raha hai, aur jab message bhejte ho to woh API Gateway → Lambda backend hit karta hai. Live!

### Step 6: CloudFront distribution kyun chahiye

Direct S3 access architecture ke hisaab se galat hai. Hum chahte hain browser **CloudFront** ke through aaye, direct S3 nahi.

**CloudFront kya hai?** AWS ka **global Content Delivery Network (CDN)**. Concept:
- Tumhari files **edge locations** (duniya bhar ke 400+ data centers) par cache ho jaati hain
- User jis location ke paas hai, wahin se content milta hai → **kam latency, fast load**
- Origin (S3) par load kam, HTTPS automatic, DDoS protection layer milta hai

### Step 7: CloudFront distribution banao

Pehle S3 static website endpoint copy karo (Step 5 wala URL). Phir:

1. AWS console → **CloudFront** service kholo
2. **Create distribution** → name: `twin-distribution` → Next
3. ⚠️ **CRITICAL — origin type "Other" chuno, S3 nahi.** Kyunki hum ek **S3 static-hosted website** use kar rahe hain (S3 REST API nahi). Galat option chunne par kaam nahi karega
4. **Origin domain name**: apna S3 endpoint paste karo **bina `http://`** ke (custom origin), jaise:
   ```
   twin-frontend-<account-id>.s3-website-<region>.amazonaws.com
   ```
5. ⚠️ **CRITICAL — "Customize origin settings" → HTTP only chuno.** S3 website endpoint sirf HTTP serve karta hai (HTTPS nahi). Agar "HTTPS only" ya "Match viewer" rakha to fail hoga
6. **WAF (Web Application Firewall)** prompt: AWS poochhega enable karna hai? Yeh Amazon ka **upsell** hai — DDoS protection deta hai par tumhe abhi zaroorat nahi. **"Do not enable"** chuno (jaise flight booking par "no, mujhe extra insurance nahi chahiye"). Company chahe to baad mein le sakti hai
7. Connection timeout 10s default theek hai → **Create distribution**

### Step 8: Deployment wait (5–10 min)

CloudFront ab status **"Deploying"** dikhayega. Yeh **5 se 15 minute** le sakta hai (Ed ke liye 10 min se kam) kyunki distribution **poori duniya ke edge locations** par push ho rahi hai — bada kaam hai. Jab status **"Deploying" → "Enabled"** ho jaaye, tab hum good shape mein hain. Agle lecture mein isi distribution ko test karenge aur CORS configure karenge.

---

## 📋 Key Concepts

| Concept | Matlab |
|---|---|
| **CloudFront** | AWS ka global CDN — files edge locations par cache, fast worldwide delivery, HTTPS |
| **Static export** | Next.js `output: "export"` — server ki jagah pure HTML/JS/CSS `out/` folder banata hai |
| **`npm run build`** | Production build + `out/` directory (index.html, 404.html, JS, CSS) generate karta hai |
| **`aws s3 sync out/ s3://...`** | Local build folder ko S3 bucket se mirror karta hai; `--delete` extra files hatata hai |
| **S3 static website hosting** | S3 bucket ko simple HTTP website ki tarah serve karne ka mode (Properties tab) |
| **Origin (CloudFront)** | Wo source jahan se CDN content laata hai — yahan S3 website endpoint, type "Other" |
| **HTTP only origin** | S3 website endpoint sirf HTTP deta hai, isliye CloudFront origin ko HTTP-only set karna zaroori |
| **WAF** | Web Application Firewall — optional paid DDoS protection, abhi skip |
| **`twin.tsx` fetch** | Front end ka backend call — localhost se badal kar real API Gateway endpoint |

---

## 💼 Backend Dev Ke Liye Note

Python backend dev ke liye yahan do important takeaways hain. Pehla: **front end ka API base URL ek deployment concern hai** — hardcoded `localhost:8000` production mein kaam nahi karega. Real apps mein yeh URL ek **environment variable** se aata hai (`NEXT_PUBLIC_API_URL`) na ki hardcoded; yahan course simplicity ke liye direct edit kar raha hai, par production mein env-based config use karna. Doosra: **CloudFront + S3 pattern** classic "static front end, separate API backend" architecture hai — yeh wahi decoupling hai jo tum FastAPI + React projects mein dekhte ho. CDN tumhare static assets ko serve karta hai (jahan latency aur caching matter karti hai), jabki dynamic logic alag API tier (API Gateway → Lambda) par rehta hai. `aws s3 sync --delete` ko ek deployment step samjho jo CI/CD pipeline mein automate hota hai (Week 2 Day 5 mein GitHub Actions se yahi hoga). Aur CORS ka jo issue agle lecture mein aayega — woh seedha is decoupled architecture ka natural consequence hai: front end aur backend alag origins par hain.

---

## ✅ Takeaway

- Front end ka `fetch` localhost se **real API Gateway endpoint** par switch karo — `/chat` POST route
- `next.config` mein **`output: "export"`** daal ke Next ko static site banao, phir `npm run build` → `out/` folder
- `aws s3 sync out/ s3://<bucket> --delete` se static site S3 par upload, S3 static-hosting se direct test
- **CloudFront** S3 ke upar global CDN layer hai — origin type **"Other"** + **HTTP only** dono critical hain
- CloudFront deploy hone mein **5–10 min** lagte hain (worldwide push); status "Enabled" hote hi ready

---

<details>
<summary>📜 Full Transcript (English)</summary>

Okay. So for this next step, first go back here again to the gateway. And just copy this URL here. Copy that into your clipboard. This is the endpoint for the Twitter API gateway. All right you've done that. Then go back to the instructions. So we're going to update the front end code in components twin TSX. You remember I showed you this line of code that was the actual line that's actually calling the back end. We're going to change that. So instead of calling localhost 8000 it's going to it's going to actually call the real the real web service itself the API. So let's go in and do that right now. So this is in the front end code. It's in other components twin TSX. And now we're going to look in TSX for that fetch. It's right here near the top. And we're going to replace all of that with the actual endpoint itself. Uh I managed to add an extra empty line there, but that looks better to me. There we go. You see that? This URL right here is where we want to be posting slash chat. So that's looking good to me. Back to the instructions we've updated to TSX. Okay, we now need to change next config so that static exports are allowed so that we can generate a static dump of the whole website. So next config. Let's find that. Here it is. Change it with this new you can see it's got no config. It's empty. We're going to paste in and export config. There it is. Done. Okay back to the instructions. Next up it's time to build a static export. So we do that by bringing up a terminal by going to the front end. Uh, which is I think this one right here. Here it is. And now we're going to do, uh, the, uh. Sorry. We don't need to do that. We need to, um, do npm run build. And off it goes building, and it's going to build an optimized production build. It's going to create an out directory there. You see the out directory has been created and it has all of the files in it, the static files for our whole website. So if you open this up you can see in here there's a whole bunch of files that are HTML, JavaScript, CSS for our website that's been derived from the TypeScript from the Next.js app that we wrote in this more modern code. And this is all traditional that will work on on any browser. And there is an index.html and a 440. And that might jog your memory because we set that up when we were configuring our front end. Okay. So this has been completed and now it's time to upload this to S3. So, uh, what we what we do here, we're in the front end directory. This AWS command will work because in the previous week we did AWS configure that set up AWS for us. So we are now going to upload our front end to our static site. And you do that with this command AWS S3 sync out slash the output directory. And then we're going to have our front end bucket name. So we do S3 colon slash slash. And we now have to give it our bucket name. Now do you remember what the bucket name was. It was twin dash front end dash. And now you put in your entire, uh, ID and then you finish this off and then we will press enter. So we put in the ID and then a slash at the end. Dash dash delete means delete. If it's a it can be removed when not in the build. And then press enter. And it's done. It just uploaded the static site to our S3 bucket. Okay, it's time to test it. Uh, so first of all, uh, we, uh, we need to, uh, go to the S3 bucket and then properties and static website hosting. Let's go and give this a try. We go here to the S3 bucket. We find our front end bucket. There it is. Properties. We go down to static hosting which is near the bottom. And we're going to look for this URL right here. And let's launch it in a separate browser. This is going to work. Look at that. Look at that. It comes up. We've got ourselves a static site. Hi there. What happens now? Drumroll. Something's happening. Somewhere machinery is in action. A long pause and there we go. Hi, Ed. Great to see you. What's on your mind today? There we go. We have a front end and a back end, that's all working together. The front end is being accessed by a browser and the back end is coming through. And we should check that the, uh, that maybe we'll check the memory works later when all of the pieces are together. Because there's something missing here. We're connecting directly to an S3 bucket. And that wasn't the architecture. The idea is we want to put this under CloudFront distribution so that we're connecting through CloudFront. So we've tested that this works by accessing directly the web pages. What we now want to do is see if we can get it to run through CloudFront okay. So what we're going to do is first get the endpoint that we just got. Now the static website endpoint that we just tested. We will copy that. And we are then going to go and create a CloudFront distribution called Twin Distribution. So let's go ahead and get get this show on the road. So back over here we need to start by going to. This is where we're currently on the twin front end bucket. We need to copy this endpoint. Copied done. All right. Now we're going to go and look for CloudFront. Here is CloudFront the global content delivery network. And we are going to create a CloudFront distribution distribution name. We're calling it twin distribution. I think let me just check uh twin distribution. And then next okay twin distribution. And then next. Okay. Now this is something to watch out for because of the way we're doing this. It's a it's a special kind. It's an S3 static hosted site. We have to press other, not S3. Just one of those things to know. And then I believe we're going to fill in the the origin field is choose a paste your S3 endpoint without the HTTP like that in the origin domain name. So let's go and do this origin domain name. Custom origin like this, but without the HTTP like that, that's what it has to look like. And now there's something super important we have to make sure that it is HTTP only have to go in here to customize origin settings and choose HTTP only. Otherwise this won't work. So you need to do that and see if we need to do anything else here. Um, let me just see. So uh critical HTTP only. And then um origin name. Or you can leave that auto generated and then it looks fine. Okay. I think everything else should be default. Let's have a look. Let's go back over here and just just take an eye on this. All looks good. Next. Uh, yes. So this prompts you to enable web application firewall, which is something that could protect you against things like, uh, DDoS attacks. Now, this is basically an Amazon upsell. You don't need to do that. Not in our case. Unless your company wants to pay for these extra security protections. The very fact that it forces you to say no gives you a little clue. It's a bit like when you're buying a flight and the airline wants you to say, no, I do not need your extra insurance. Uh, so we do that, we check out all of this. Everything looks fine. Connection timeout of 10s is fine. We just need to, uh, hopefully that it's set to be HTTP only. And then we say create distribution. And now it is going and creating our CloudFront distribution. And over here it says deploying. And that is our sign that deployment is in process. And this are in progress. And this is something which actually takes like 5 to 10 minutes to deploy a CloudFront distribution. And that's because it's been pushed out all over the world. So we have to to accept the fact that it takes a few minutes, because it's not an easy thing for it to do at all. Uh, so yes, wait 5 to 15 minutes. It says here, but it's never taken more than ten minutes for me. But but you never know. And when it's done, it's going to change from deploy to enabled. And that is when we're in good shape.

</details>
