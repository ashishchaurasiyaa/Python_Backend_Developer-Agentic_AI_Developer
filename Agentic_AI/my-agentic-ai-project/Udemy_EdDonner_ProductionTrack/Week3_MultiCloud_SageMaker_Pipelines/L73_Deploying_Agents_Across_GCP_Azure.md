# L73 — Deploying AI Agents Across GCP and Azure with Container Services

> **Week 3 · Day 2** · ⏱️ ~11 min

---

## 🎯 TL;DR

GCP deploy ho gaya — hum live Cloud Run app test karte hain, **OpenAI traces** + **GCP Cloud Run logs** dono jagah observability dekhte hain, phir `terraform destroy` se cleanup. Lecture close hota hai ek important **deployment spectrum** discussion ke saath (PaaS → container-as-a-service → serverless → server → orchestration) aur Week 3 ke "all purple" AI phase (SageMaker, vectors, MCP ingest) ka teaser.

---

## 🗣️ Hinglish Explanation

### Result: Same agent, ab GCP par live

Pichle lecture ka `terraform apply` successfully complete ho gaya — output mein **service URL** mila. URL pe click karte hi hamara **cyber security analyst** browser mein khulta hai, ab GCP par `cyber-analyzer...` URL pe (Azure wala alag URL tha). Ed ke paas ab **chaar parallel deployments** chal rahe the:

1. **GCP Cloud Run** par (yeh wala)
2. **Azure Container Apps** par
3. **Local Docker container** mein
4. **Local frontend + backend** (no Docker) — pure dev mode

Same code, 4 alag environments. Yeh hi container portability ka power hai.

### Live test: Agent ko chalao

```
1. "Open Python file" → ai.py select karo
2. "Analyze code" button dabao
```

Andar kya hota hai (step-by-step):
1. GCP data center (Ed ka `central1` / tumhara apna region) mein **Cloud Run instance spin up** hota hai — container "warm up" hota hai (cold start).
2. Container ke andar **MCP server spawn** hota hai (isliye bada memory wala container chahiye tha).
3. MCP server **Semgrep** se connect karta hai aur Python file scan karta hai.
4. Results aate hain: Semgrep ne **4 issues** dhoonde, agent ne **1 extra** identify kiya — do **high** (jaise `eval` use → critical hona chahiye) aur ek **medium** (input validation). 

> Cold start ki wajah se result aane mein time laga — Ed ne stop dabaya toh turant aa gaya (classic).

### Observability Layer 1: OpenAI Traces

Ed traces tab (OpenAI ki built-in observability platform) pe jaata hai. Naya trace aata hai:
- **Security researcher** agent ne run kiya
- **Semgrep scan** call dikh raha hai (actual MCP tool call)
- Output → agent ka final response with answers

> **Observability matlab** = production mein app ki internal behavior dekhne ki ability — kaunse tool call hue, kya input/output tha, latency kitni. **Traces** ek single request ka end-to-end journey dikhate hain (agent → tool → response). Ed bolta hai *"this is a very important practice"* — production AI mein "kyun aisa hua?" ka jawab traces se milta hai.

### Observability Layer 2: GCP Cloud Run Logs

Traces ke alawa GCP console se bhi dekho:

```
1. console.cloud.google.com → top-left se "Cyber Analyzer" project select
2. Search bar mein "Cloud Run" type → Cloud Run section
3. "cyber-analyzer" service (Terraform ne banaya) pe click
4. "Logs" tab → wahi Semgrep reports jo locally/Azure pe dikhe the
5. "Metrics" tab → memory/CPU usage report
```

Logs mein **MCP server** ki activity dikh rahi hai — same Semgrep output jo locally aur Azure pe aaya tha, ab GCP pe. Metrics mein dikha ki **container ne itni zyada memory use nahi ki** — Ed mazaak karta hai ki shayad itna bada container chahiye hi nahi tha, par **default toh definitely kaafi nahi tha**.

> GCP mein **logging ek bada topic hai** (Cloud Logging) — bahut detail mein ja sakte ho — par quickest path hamesha: Cloud Run → service → Logs.

### Cleanup: `terraform destroy` (HAMESHA!)

```bash
terraform destroy
# poochega: "Do you really want to destroy?" → type: yes
```

Resources running mat chhodo (paisa katega). Destroy ke baad GCP console mein verify karo:
1. Console home → top-left project = Cyber Analyzer
2. Cloud Run → **kuch nahi dikhna chahiye** (cyber-analyzer gone)
3. **Billing** → overview, budgets/alerts, cost table — confirm karo kuch unexpected spend nahi ho raha

> Ed ek pro tip deta hai: GCP console "**compare with AWS and Azure**" naam ka helpful doc suggest karta hai — teeno clouds ki service mapping ke liye handy reference. Aur **Cloud Overview → dashboard** se project ka single-glance health milta hai.

### Deployment Spectrum: Konsa kab? (Important framing)

Ed ne emphasize kiya ki GCP "easy" isliye laga kyunki (a) **Terraform ne heavy lifting ki** aur (b) humne **Cloud Run (container-based)** pick kiya — jo simplest deployment hai jab Docker container ready ho. Phir wo poora **continuum** explain karta hai (simple → complex):

| Tier | Kya hai | Examples | Trade-off |
|---|---|---|---|
| **PaaS (Platform as a Service)** | Fastest deploy; tum sirf code do, platform sab manage kare | Vercel, AWS Elastic Beanstalk, Azure App Service, Google App Engine | Least flexibility — apna build/config customize nahi kar sakte; off-the-beaten-path (jaise custom MCP server) mushkil ho jaata hai |
| **Container as a Service** | Docker container do, platform run kare | Google Cloud Run, Azure Container Apps, AWS App Runner | "Sweet spot" — quick + efficient, especially jab container already ho |
| **Serverless architecture** | Multiple components compose karo (functions + gateway + CDN) | AWS Lambda + API Gateway + CloudFront (Week 2 jaisa) | Zyada flexibility (rate limiting, security, global edge) par zyada thoughtful design chahiye |
| **Server architecture** | Apne servers/VMs manage karo | EC2, VMs | Full control, full ops burden |
| **Container orchestration** | Sabse complex; cluster manage | Kubernetes (EKS/GKE/AKS) | Maximum power + maximum complexity |

**Decision rule**: koi single "best" nahi — tumhare requirements decide karte hain. Agar global distribution (**CloudFront**), API security/rate-limiting (**API Gateway**) chahiye → serverless architecture. Agar bas "quickly build something, deploy to test/prod" → container-as-a-service ka sweet spot. PaaS sabse fast par sabse rigid.

> Iss project mein container-as-a-service ne sweet spot hit kiya: **ek baar Docker build, minutes mein Azure + GCP dono par deploy**.

### Week 3 ka aage ka teaser: "Get ready for purple"

Yeh Day 2 ka end hai — Days 1-2 ka standalone "cyber" project ab done. Aage:
- **No more GCP, no more Azure** — wapas **AWS** par
- **All purple** = AI-focused content (Ed apni color-coding mein AI topics ko purple dikhata hai)
- Topics: **SageMaker**, **vectors** (vector storage/RAG), **data ingest using MCP servers**
- "Get plenty of sleep" — Day 3 se capstone (Alex) shuru.

---

## 📋 Key Concepts

| Concept | Matlab |
|---|---|
| **Cold start** | Cloud Run instance idle se spin-up hone mein lagne wala initial delay |
| **MCP server spawn** | Container startup par Semgrep MCP server launch hona |
| **Observability** | Production app ki internal behavior dekhne ki ability (traces + logs + metrics) |
| **OpenAI Traces** | Built-in trace viewer — agent → tool call → response ka end-to-end journey |
| **GCP Cloud Logging** | GCP ka logging system; Cloud Run → service → Logs sabse quick path |
| **`terraform destroy`** | Saare Terraform-managed resources delete karta hai (cost cleanup) |
| **PaaS** | Platform as a Service — fastest deploy, least flexibility (Vercel, App Engine, App Service, Beanstalk) |
| **Container as a Service** | Docker container do, platform chalaye (Cloud Run, Container Apps, App Runner) — sweet spot |
| **Serverless architecture** | Multiple components (Lambda + API Gateway + CloudFront) — flexibility for security/global |
| **Deployment continuum** | PaaS → CaaS → serverless → server → orchestration (simple → complex) |

---

## 💼 Backend Dev Ke Liye Note

Yeh lecture ka core lesson **"deployment is a spectrum, not a binary"** — har backend dev ko yeh mental model chahiye. Jab tumse koi pooche "isse kaise deploy karein?" toh jawab requirements pe depend karta hai: ek internal tool ke liye Cloud Run/App Runner enough hai (one-command, auto-scale, scale-to-zero = cheap), par ek customer-facing API jise rate limiting, WAF, aur global low-latency chahiye, usse API Gateway + CloudFront wala serverless architecture chahiye. **Over-engineering** (Kubernetes jab Cloud Run kaafi tha) utna hi galat hai jitna under-engineering. Doosra production habit yahan reinforce hua: **two-layer observability** — application-level traces (kya agent ne kya tool call kiya) + infra-level logs/metrics (memory/CPU, container health). Production debugging mein dono chahiye: traces "business logic kyun fail hua" batate hain, infra logs "container OOM hua kya / cold start latency" batate hain. Aur **always destroy** — cost discipline production engineering ki non-negotiable habit hai.

---

## ✅ Takeaway

- **Same Docker container, 4 environments** (GCP Cloud Run, Azure Container Apps, local Docker, local dev) — container portability ka real proof
- **Two-layer observability**: OpenAI **Traces** (agent/tool-call level) + GCP Cloud Run **Logs/Metrics** (infra level) — dono check karo
- **Always `terraform destroy`** + billing console verify — running resources cost karte hain
- **Deployment continuum** yaad rakho: PaaS → container-as-a-service → serverless → server → orchestration; requirements decide karte hain, koi single "best" nahi
- Days 1-2 ka cyber project khatam — ab **wapas AWS, "all purple" AI phase**: SageMaker, vectors, MCP data ingest, aur capstone Alex

---

<details>
<summary>📜 Full Transcript (English)</summary>

Well, here we are. It seems to have run completed successfully. We've got a service URL, which I will, uh, I guess I can just control. Click on it again and open and up it comes. And we are looking at our cyber security analyst. It is running on the cloud but this time it's at Cyber Analyzer blah blah blah dot dot dot. By comparison this one where is it now? Over here is uh, on the Azure container apps, a different URL. Uh, all right. Open Python file. We will uh open air.py and we'll press the analyze code button. And presumably now somewhere in for me your central one, somewhere a Google data center is spinning up. Uh, Cloud run is being launched, which means that that our container that we deployed is, is, is warming up. It's going to spawn an MCP server. Its large enough size that it can run the MCP server, and it's now you know only too well that MCP server is connecting to Semgroup, and it's running our analysis for us for this file. I realized I'm not going to be able to keep it going, but at this time to take you through the time it will take to come up with the results. So I'm going to, uh, I'm still hoping it's going to finish, but it's not. I will be back in one second with the results. Ah, I knew that was going to happen. I should have waited. The second I pressed the stop button, the results came. That's how long it took. Uh, anyway, here are the results. Sure enough, uh, analyzed the Python code. Same grep found for issues, and I identified one extra issue. It says. And here they are the same two highs. There should be a critical. There it is the eval uh, and uh the input validation is the medium one that it probably added in. So there we have it. This is the result of our application, our simple cyber security analyst with an MCP. Server an agent framework deployed now to GCP. You're seeing it here running on GCP with cloud run. And over here we see the same thing. The same thing. It was almost hard to see that I'd changed tabs. But this of course is completely different in that it's running on Azure. Uh also spawning an MCP server using Azure Container apps instead of GCP Cloud Run. And this is it running in a Docker container locally on my box. And this is it running just as a front end and a back end locally on my box for different deployments. One browser. And actually I still have open the traces from before. Let's go over here to traces since we have it right here. Uh, and let's go back to traces. And we should see a new trace has come right up here. Uh, we will go into this, uh, and we can see the security researcher has run the Semgroup scan was right here and presumably we'll see an output there. We have it. And that then resulted in a response coming back from our agent. And this, of course has the answers right there. Uh, so this shows us, again, using the observability platform traces built within OpenAI, uh, to examine the behavior of our agent and look at the actual MCP call itself. And so this is a very important practice to come and do this. But in addition to this we can also go into the GCP console and see what happened according to GCP. Let's go do that. So here we are in the home screen of going to Console.cloud.google.com. And we pick Cyber Analyzer over here. And we can type Cloud run uh to go straight to the cloud run section. That's very similar to to the other two. Uh thank you for that. Uh, here it comes. And you can see that we do have something in here called Cyber Analyzer. This was created by Terraform. We can come into this container and we are now looking at the cyber analyzer cloud run. Uh, we can see that's when I just called it. Um, we can go into its logs and presumably we'll see. Uh, here we go. The same sort of semgroup reports that we saw running from, um, uh, when we ran it in a Docker container locally and also on Azure. And now here on GCP, these are the logs coming from our MCP server, from our agent. Uh, you can see MCP server appearing here in the uh, in the trace. Uh, so this is how you quickly get to logs in Cloud Run. And again logging is a whole big deal in GCP. There's there's a lot of detail we could go to. But the quickest way just as with Azure is to start at Cloud Run. Come in and click on the logs just there. We'll go back to metrics just to see the overall reports here on on on what it's done and how much memory it used up. It actually didn't use that much. But but so maybe I didn't need such a such a big container. But certainly the default wasn't big enough. Uh, so there we have it that is showing the logs in GCP. So we've looked at the observability, the traces in open AI. And we've looked at the logs in GCP. And so back to cursor. You know what's next. We next destroy that so that we don't leave resources running. Here is the terraform destroy command. Copy that. Paste that in and let it do its thing. It's going to ask me to type. Yes. Again. And, uh, here we go. Yes. And it's going to go off now and destroy our infrastructure. And I won't try and talk it through. I'll be quick this time. I'll see you in a second. It's. Ha ha ha ha. I can't win with this, can I? Uh, it's already destroyed. The the infrastructure is destroyed. So we can now go back into the GCP console and search and make sure that nothing remains. So here I am at the Google Cloud homepage, the console home page. Uh, you can see that the cyber analyzer project is selected on the top left. I always have to do that. Uh, I noticed that one of the helpful resources it prompts me for is compare with AWS and Azure. So that's nice that it shows up there. Maybe you see that too, although I'm sure you can search for it. That might be a useful document to have to hand, uh, to compare the three of them. I also, I should point out there's there's lots of great stuff here, but there's, uh, there's a dashboard screen under cloud overview that gives you a nice kind of one sense of one, one, one look at what's going on, uh, in your project. Anyway, we're coming in here because we're going to go to Cloud Run. We want to come back to Cloud Run where we were before, and there's not a whole lot to see here, as we would hope. Nothing going on here. The the cyber analyzer cloud run that used to be here has gone. It's been destroyed. We are pleased to see that there is no news at all. And of course, we should finish by going back to billing. Always important to go back to billing to see what's going on here. Um, and check out, uh, the, the overview. See anything that's being spent, look through things like budgets and alerts, the cost table, anything else that you want to look through to make sure that nothing is spending that you're not expecting and that everything is healthy. And that then would conclude our voyage into GCP. It was it was particularly easy. And I just want to emphasize one more time that the reason it was particularly easy is because Terraform did the heavy lifting for us. And now that you know what's involved in setting everything up through the console, you have some appreciation for that. The other reason it was easy, of course, is that we picked Cloud Run the the Docker container based deployment. And that is the very simplest type of deployment, and it's often a kind of no nonsense. Quickly, let's build something, make sure it works, and then let's deploy it to production using container apps. Cloud run. That's the best way to do it. And actually, that brings up a good point. I shouldn't I shouldn't say it's the best way. That's obviously oversimplifying. It's it's a very, uh, a very quick and efficient way, uh, particularly if you're already working with a Docker container to deploy something quickly to an environment like test or production. The cloud run and Container apps and App Runner on AWS are definitely the go to in that scenario. But there are easier approaches, even easier than that, because there is the platform as a service approach. There's there's there's vessel for for a starter. And then if you're using one of the main providers, then there are, uh, there's Beanstalk and App Service and Google App Engine, which are the fastest to get something deployed. They are the platform as a service. Um, but you have less flexibility. You don't get to sort of build and configure your own app. And I imagine that with things like MCP servers, Vercel has, has like a template Pre-baked with that. But if you're trying to do something on your own that's slightly off, off the ordinary, then then it suddenly becomes much, much harder and you would crave the flexibility that you get with a container as a service like Google Cloud Run. But if you wanted to have even more flexibility, if you wanted to deploy all of your assets separately using something like CloudFront so that it's there located all over the world, and if you wanted to be able to have something like API gateway, where you have security around the use of APIs and rate limiting and so on, then you need to be more thoughtful about your deployment and a deployment architecture like we use last week, which was more of a it was a serverless architecture, but we made use of multiple components in AWS. That is more what you want. So there's no easy answer. There's a continuum from very simple the platform as a service to container as a service through to deploying a serverless architecture and then a server architecture, and then a container orchestration, perhaps the most complex. There's that whole continuum, and which one you pick does depend on your particular requirements. In our case, it really felt like we hit the sweet spot with container apps because we were able to build a Docker container once and deploy it to Azure and GCP in just a matter of minutes. And I think that was terrific. And on that positive note, that brings us to the end of day two of week three, days one and two of week three with their own little separate project, the cyber project that's now done. No more GCP, no more Azure. We're going back to AWS. And we're also going all purple. The rest of this week is AI stuff. It's going to be SageMaker. It's going to be vectors. It's going to be data ingest using MCP servers. Lots to do. Get ready for purple. Get plenty of sleep. Tomorrow we embark on day three.

</details>
