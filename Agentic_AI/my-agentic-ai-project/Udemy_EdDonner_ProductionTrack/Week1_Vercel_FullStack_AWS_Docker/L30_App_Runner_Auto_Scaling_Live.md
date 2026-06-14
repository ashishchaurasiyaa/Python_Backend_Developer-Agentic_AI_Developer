# L30 — Deploying Your AI App Live on AWS App Runner with Auto-Scaling

> **Week 1 · Day 5** · ⏱️ ~5 min

---

## 🎯 TL;DR

App Runner config finish karte hain: **port 8000** set karo, ek **auto-scaling configuration** banao (concurrency + min/max instances), aur **health check** (`/health`, HTTP, timeout 5s, interval 20s) add karke **Create & deploy** dabao. Kuch minutes baad app ek live HTTPS URL par AWS par chal padti hai — front end → App Runner backend → OpenAI, sab cloud mein.

---

## 🗣️ Hinglish Explanation

### Context: secrets ho gaye, ab final config

Pichle lecture mein humne 3 secrets (Clerk secret, Clerk URL, OpenAI key) save kar diye. Ab App Runner service ki baaki critical settings:

### Step 1: Port = 8000 (BAHUT important)

Service config mein **Port** field ko **`8000`** karo. Yeh critical hai kyunki hamara uvicorn server container ke andar **port 8000** par sun raha hai (Dockerfile mein `EXPOSE 8000` + `CMD uvicorn ... --port 8000`). Agar port galat hua toh App Runner traffic kahin aur bhejega aur app "down" lagegi.

### Step 2: Auto-scaling configuration

**Auto-scaling** = App Runner load ke hisaab se containers ki sankhya khud badha/ghata sakta hai. Iske liye ek naya **ASC (Auto Scaling Configuration)** banao:

1. **Create new ASC** click karo
2. Name do, jaise **`basic`**
3. **Max concurrency** (ek instance par ek saath kitni requests chalein) → e.g. **10**
4. **Minimum instances** → **1**
5. **Maximum instances** → **1** (Ed yahan max bhi 1 rakhta hai)

Ed ka point: abhi hum **1 hi instance** rakhenge (kabhi 2+ nahi). Par yahi woh jagah hai jahan agar tum highly-scalable platform bana rahe ho, toh max ko bahut bada kar sakte ho — App Runner traffic spike par naye instances spin karke load handle karega, aur idle hone par scale-down. **Add** karke yeh scaling config attach karo.

```text
Auto Scaling Configuration "basic":
  Max concurrency per instance : 10
  Min instances                : 1
  Max instances                : 1   (production scale ke liye yeh badhao)
```

### Step 3: Health check configuration

**Health check** App Runner ko batata hai ki container healthy hai ya nahi. Settings:

- **Protocol**: **HTTP** (TCP nahi)
- **Path**: **`/health`** (yahi route humne `server.py` mein banaya tha — JSON `{"status":"healthy"}` return karta hai)
- **Timeout**: **5** seconds — itna wait karega yeh decide karne se pehle ki request fail hui
- **Interval**: **20** seconds — har 20s mein health check karega

```text
Health check:
  Protocol : HTTP
  Path     : /health
  Timeout  : 5s
  Interval : 20s
```

Logic: agar **5 consecutive checks fail** ho jaayein → "trouble" (unhealthy) maana jaata hai. Agar **kuch successful** ho jaayein → healthy maana jaata hai. (Yeh unhealthy/healthy thresholds standard load-balancer pattern hai.)

### Step 4: Review + Create & deploy 🚀

**Next** dabao → review screen aata hai (secrets bhi yahan dikhte hain, isliye Ed full screen nahi dikhata). Sab kuch verify karo:
- Compute = ¼ vCPU
- Env vars set hain
- Port 8000, scaling, health check theek hain

Sab comfortable lage toh **Create & deploy** button dabao. Deploy mein **kuch minutes** lagenge.

### Result: LIVE ON AWS

Deploy hone par tum ek screen dekhoge jahan service ka status dikhega. Notable cheezein:

- **ARN** (Amazon Resource Name) — Amazon mein har cheez ka unique ARN hota hai. Is App Runner ke ARN mein dikhega: `apprunner`, **region** ka naam, **account ID**, aur baaki details. Format roughly:
  ```text
  arn:aws:apprunner:us-east-1:123456789012:service/Consultation-App-Service/...
  ```
- **Source** — yeh ECR mein padi hui **image** ko point karta hai jahan se yeh service build/run ho rahi hai.

Kuch minutes baad — "as if by magic" — status **Running** ho jaata hai. Service ek live **HTTPS domain** par available hoti hai:

```text
https://<random>.<region>.awsapprunner.com
```

Us URL par click karo — **yeh ab internet par hai, AWS App Runner par, live deployed**. Front end load hota hai, Clerk se sign in karte ho, "Open Consultation Assistant" dabate ho. Patient detail (jaise "headache, told him to take Tylenol") fill karke **Generate summary** karte ho. Ab sab kuch cloud mein whir karta hai:

```text
Static client (browser) 
   → App Runner backend (server.py on AWS) 
       → OpenAI API 
   ← streamed summary back
```

Aur back aata hai doctor's summary + next steps + patient ke liye draft email. **Ek fully deployed application** — subscription + authentication ke saath, Docker container mein, AWS App Runner par live. Congratulations, first live AWS deployment!

### Pura flow recap

1. **Port → 8000** (uvicorn isi par sun raha hai)
2. **Auto-scaling**: new ASC `basic`, concurrency 10, min 1, max 1 (scale ke liye max badhao)
3. **Health check**: HTTP, `/health`, timeout 5s, interval 20s
4. **Next → Review → Create & deploy** (kuch min)
5. Status **Running** → HTTPS URL par app live, end-to-end cloud flow chalta hai

---

## 📋 Key Concepts

| Concept | Matlab |
|---|---|
| **Port 8000** | uvicorn ka listening port — App Runner ko isi par traffic bhejna hai |
| **Auto Scaling Configuration (ASC)** | Load ke hisaab se instances badhane/ghatane ki policy |
| **Max concurrency** | Ek instance par ek saath max requests (e.g. 10) |
| **Min / Max instances** | Kitne containers minimum/maximum chalein (1/1 = no scaling) |
| **Health check** | HTTP `/health`, timeout 5s, interval 20s — container ki sehat monitor |
| **Unhealthy threshold** | 5 consecutive fails = trouble; kuch success = healthy |
| **ARN** | Amazon Resource Name — har resource ka globally unique ID (region + account + details) |
| **App Runner Source** | ECR image jise yeh service run kar rahi hai |
| **Create & deploy** | Service launch button — kuch min mein live HTTPS URL |

---

## 💼 Backend Dev Ke Liye Note

Yeh lecture production deployment ke teen pillars dikhati hai jo har backend dev ko set karne aane chahiye: **port binding**, **auto-scaling policy**, aur **health probes**. Port mismatch (container 8000 par sun raha hai par platform 80 par traffic bhej raha hai) sabse common "deployed but 502" bug hai — hamesha verify karo. Auto-scaling ke do knobs — **concurrency-per-instance** aur **min/max instances** — ko load-test data se tune karna chahiye; min=1 means hamesha ek warm instance (cold start avoid), max=1 means cost-capped par no burst capacity. `/health` endpoint ka design matter karta hai: ise **lightweight** rakho (DB/LLM call mat karo warna timeout par false-unhealthy ho jaayega) — yeh sirf "process zinda hai" check kare. App Runner ka health check effectively ALB target-group health check + Kubernetes liveness probe ka combo hai. ARN samajhna AWS automation (IAM policies, Terraform references, cross-service wiring) ke liye foundational hai — yeh resource ka canonical address hai.

---

## ✅ Takeaway

- **Port 8000 set karna mat bhoolo** — uvicorn isi par sun raha hai, mismatch = app down dikhegi
- Auto-scaling: ASC banao (concurrency 10, min 1, max 1); real scale ke liye **max badhao**
- Health check: **HTTP `/health`, timeout 5s, interval 20s** — 5 fails = unhealthy
- **Create & deploy** → kuch min → live **HTTPS URL** par app AWS par chalti hai
- End-to-end: static client → App Runner backend → OpenAI streaming — sab cloud mein, auth + billing ke saath

---

<details>
<summary>📜 Full Transcript (English)</summary>

Okay, so my secrets have now been saved. They're just up there. Just off of off the top there. And, uh, this here is very important where it says port, you need to change this to 8000, because that is the port that it's listening on. Uh, auto scaling right here. You need to come in here and you need to say create new ASC. Give it a name like I'm going to call this like basic, uh, how many, uh, requests can be running concurrently at any one time? Let's say no more than ten. Let's say the minimum number of instances is one, but the maximum is also one. So we're not going to have more than one of these running ever. But this is where you can have it. So that it could scale up a lot if you were building a platform that needed to be highly scalable. And now we add that that is how this this the scaling configuration for this. And then we add health check information. I've actually already filled this in. But you choose a protocol which you should choose HTTP. Give it a path which in our case should be slash health. Say that we want timeout out of five and an interval of 20. That's saying that it will wait up to five seconds before it decides that this isn't healthy. And every 20s it will do this, uh, if it does them five in a row that fail, then that's considered trouble. If a couple are successful, then that's considered healthy. And that is our health checks that run and this is it. And then you press next. You get to review everything one more time. And that shows my secrets. So I'm not going to do that. But you do that. You'll see everything. Make sure it looks good. It's a quarter of a CPU. Make sure you're comfortable with everything that's going on. You have a sense we are ready to deploy our container to App Runner and then press the button to do this, and I will see you in a second. It will take a few minutes to run. So hopefully you found it was in fact a create and deploy. That was the button to press after you were reviewing the details. And once you press that, you should be looking at a screen like this, except yours should say consultation app service, not consultation App service two because I did already test that. That works. Uh, but here you see it here it's it's it's it's working. It's working to deploy this consultation app service. So this is going to be AWS App Runner, which is able to take the Docker container that we had built, the Docker image that we built that was working when we ran it locally. And we uploaded it to the container registry. And we are now running an app runner service that will use that Docker image that we built and that we know works. So this is still deploying. I'll just point out a couple of things about this screen that you're seeing here. You'll see one of these arns. Remember I mentioned that before. Everything in Amazon has an Arn. Uh and this is no exception. This this app runner is has this Arn. You can see within it. It has app runner. It has the name of the region where it's running. It has the account ID in there too. And then all of the other details about it. Um, and this source here is pointing to the container, the image really in the Elastic Container Registry, uh, which this is being built from, that is the source, the image that is sourced for this particular app runner instance. All right. With that, I will leave this to finish off running. Oh, and as if by magic as I finish this, it has now run. And so this is where it is running. It's running on this domain this Https right here. So this is the moment of truth. I'm going to click on this and see what happens. This is on the internet. This is AWS App Runner. This is our app everybody. This is our app running on AWS deployed live to AWS. I'm going to sign in. I'm going to sign in as my user ID. Here we go. Continue. We're now signed in. We just we just authenticated through Clark. And now I'm going to press the open consultation assistant. This is running on Amazon Web Services. Uh, okay. So, uh, editor Donna was the patient. Well, might as well stick with the try I've got. I've definitely got a headache after all this AWS stuff, uh, complained Of a headache. I told him to take Tylenol. All right. And generate a summary. So now everything is whirring in the cloud. Um, and with any luck, our client, our static client, our client here is now calling the server running in AWS App Runner. And, uh, this is now going to be calling OpenAI. And lo and behold, back comes our summary with the doctor's, uh, summary, the next steps for the doctor and the draft of the email to go to the patient. Me, uh, with the headache. And so I present to you a deployed application along with its subscription and authentication. It is running it's in a Docker container deployed on AWS using AWS App Runner. And you should be looking at this yourself. And may I be the first to congratulate you on a live AWS deployment.

</details>
