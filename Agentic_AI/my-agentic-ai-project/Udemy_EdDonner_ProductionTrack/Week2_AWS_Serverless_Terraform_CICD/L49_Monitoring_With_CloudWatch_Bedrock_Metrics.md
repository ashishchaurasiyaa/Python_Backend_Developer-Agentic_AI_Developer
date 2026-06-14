# L49 — Monitoring Production AI with CloudWatch and Bedrock Metrics

> **Week 2 · Day 3** · ⏱️ ~8 min

---

## 🎯 TL;DR

**CloudWatch** kholke hum proof dhoondhte hain ki twin sach mein Bedrock Nova call kar raha hai — Lambda metrics (invocations, duration, errors), Bedrock metrics (invocations, input/output tokens, latency), aur logs dekhte hain, ek **twin dashboard** banate hain, aur Lambda page ke **Monitor tab** se quick metrics access karte hain. Yeh Week 2 Day 3 ka wrap hai.

---

## 🗣️ Hinglish Explanation

### Kyun: "trust but verify"

Pichle lecture mein twin Nova se baat kar raha tha, par Ed bolta hai — "tum trusting type nahi ho, evidence chahiye". Kya pata abhi bhi OpenAI hi call ho raha ho, bas thoda zyada chatty ho gaya? Isko **prove** karne ka tareeka hai AWS ka monitoring pillar: **CloudWatch**.

**CloudWatch kya hai?** AWS ka central **observability service** — yeh saari services se **metrics** (numeric time-series), **logs** (text output), aur **events** collect karta hai. Har AWS service automatically CloudWatch ko metrics push karti hai. Yahan se tum dashboards, alarms, aur log queries bana sakte ho.

### Step 1: Lambda metrics dekho

1. AWS Console → **CloudWatch**
2. Left sidebar → **All metrics**
3. Namespaces list mein **Lambda** chuno
4. **By Function Name** chuno (vs. "By Resource")
5. Apna function **twin API** dhoondho

Yahan available Lambda metrics:

| Metric | Matlab |
|---|---|
| **Invocations** | Function kitni baar call hua |
| **Duration** | Har invocation kitne ms chala |
| **Errors** | Kitne calls fail hue |
| **Throttles** | Concurrency limit ki wajah se kitne calls reject hue |
| **Concurrent executions** | Ek time par kitne instances parallel chal rahe the |

Upar charts mein time-series dikhta hai — poora history dekho ya **last hour** par zoom in karo. Yeh Lambda function ki poori visibility deta hai.

### Step 2: Bedrock metrics dekho (asli proof)

CloudWatch ka chart "timeline" sticky hota hai — jo bhi metrics tum select karte ho, sab ek hi graph par superimpose hote rehte hain. Wapas **All metrics** par jaake ab **Bedrock** namespace chuno:

1. **All** → **Bedrock**
2. **By Model ID** chuno
3. Apna model — **Nova Lite** — select karo
4. Available metrics: **Invocations**, **Input token count**, **Output token count**, **Invocation latency**

Yeh sab pehle wale Lambda graph par superimpose ho jaate hain. Bedrock events dhoondho, ek example dekho:

```text
Bedrock — Amazon Nova Lite
  Invocation latency   : ~1000 ms   (≈ 1 second response)
  Input token count    : 4800 tokens
  Output token count   : 134 tokens
  Invocations          : 1
```

**Yahi proof hai.** CloudWatch khud bol raha hai ki Amazon Nova Lite call hua tha. Agar OpenAI hota toh Bedrock namespace mein koi metric nahi aata. (Tokens count: input bada — system prompt + history; output chhota — ek jawab.)

### Step 3: Logs dekho

CloudWatch left sidebar → **Log groups**. Yahan har Lambda function ka ek log group hota hai (naam pattern `/aws/lambda/<function-name>`). **twin API** wala log group chuno → ek recent **log stream** kholo → zaroorat ho toh **Display** → **Expand all rows**.

Logs mein dikhega:

```text
START RequestId: ...
... (incoming request handling) ...
END RequestId: ...
REPORT RequestId: ...  Duration: 1023 ms  Billed Duration: 1100 ms
       Memory Size: 512 MB  Max Memory Used: 180 MB
```

- **Duration vs Billed Duration** — actual run time vs jiska tumse paisa liya gaya (rounded up).
- **Max Memory Used** — kitni memory actually use hui (right-sizing decide karne ke liye useful).

Humne abhi extensive logging add nahi kiya (basic hai), par production mein yahin tum apne structured logs bhejoge.

### Step 4: Dashboard banao

CloudWatch top → **Dashboards** → **Create dashboard** → naam **twin dashboard** → **Create dashboard**.

Phir widgets add karo:

1. **Bedrock line widget** — By Model ID → Nova Lite → input tokens, output tokens, invocations, latency → ek line chart ban jaata hai.
2. **+** button → **Lambda line widget** — By Function Name → twin API → duration + invocations → kab aur kitni baar call hua dikhata hai.
3. **Errors number widget** — phir se Lambda → By Function Name → twin API → **Errors** metric, par widget type **Number** chuno (line nahi). Label de do "twin API errors". Result: ek bada **0** — exactly jo dekhna chahte hain, koi error nahi.

Ab tumhare paas ek custom twin dashboard hai jahan ek nazar mein twin ki health dikhti hai. Production mein yahi pattern scale karta hai — ek dashboard per service/team.

### Step 5: Lambda ka Monitor tab (sabse quick)

Yeh bahut saari info Lambda page se directly mil jaati hai:

1. **Lambda** → **twin API** kholo
2. **Monitor** tab par jao
3. Yahan **pre-configured CloudWatch metrics** auto-show hote hain — invocations, duration, errors, etc. (chahe toh inhe apne dashboard par bhi daal sakte ho)
4. Neeche **CloudWatch logs** ka quick access — most recent aur most expensive invocations bhi dikhte hain

Yeh sabse fast tareeka hai ek single Lambda function ke logs aur visuals dekhne ka.

### Wrap: Week 2, Day 3 done

- Amazon Bedrock ko AWS deployment mein add kiya — chhote-chhote changes se sab kaam kar gaya.
- Lambda re-upload practice ho gayi (jo itna mushkil nahi nikla).
- Nova models use kiye.
- CloudWatch se **prove** kiya ki sach mein Nova via Bedrock call ho raha hai.

**Kal (Day 4): Terraform.** Ab tak humne sab manually console mein click-click karke banaya — aage **Infrastructure as Code (Terraform)** se poora twin environment code se banayenge. Ed kehta hai yeh manual journey ek "rite of passage" thi taaki tum Terraform ki value samjho.

---

## 📋 Key Concepts

| Concept | Matlab |
|---|---|
| **CloudWatch** | AWS ka central observability service — metrics + logs + dashboards + alarms |
| **All metrics** | CloudWatch screen jahan namespace (Lambda/Bedrock) se metrics browse karte ho |
| **By Function Name** | Lambda metrics ko function-wise filter karna |
| **By Model ID** | Bedrock metrics ko model-wise filter (e.g. Nova Lite) |
| **Bedrock metrics** | Invocations, input/output token count, invocation latency — Nova call ka proof |
| **Lambda metrics** | Invocations, Duration, Errors, Throttles, Concurrent executions |
| **Log groups / streams** | Per-function log storage; START/END/REPORT lines + duration/memory |
| **Dashboard** | Custom panel of widgets (line charts + number widgets) for at-a-glance health |
| **Monitor tab** | Lambda page ka built-in CloudWatch metrics + logs shortcut |

---

## 💼 Backend Dev Ke Liye Note

Backend dev ke liye yeh lecture **observability ka foundation** hai. CloudWatch ka triad — metrics, logs, dashboards — wahi mental model hai jo tum Prometheus + Grafana + Loki/ELK se jaante ho, bas managed AWS-native form mein. Do production habits notice karo: (1) **proof via metrics, not faith** — "model X call ho raha hai" claim ko Bedrock token-count metrics se verify karna exactly wahi rigor hai jo tum DB query counts ya cache hit-rate se latency claims verify karne mein lagate ho. (2) **REPORT line ka Billed Duration + Max Memory Used** Lambda right-sizing ke liye gold hai — agar 512 MB allot kiya par max 180 MB use hua, toh memory ghatao (cost girega, par dhyan: Lambda mein CPU memory ke saath scale hota hai, toh kabhi-kabhi zyada memory faster + sasta padta hai). Agla step jo lecture mein nahi par production-critical hai: in metrics par **CloudWatch Alarms** banao (e.g. Errors > 0 ya p99 latency > 3s par SNS notification) — taaki dashboard dekhne ki bajaye system khud tumhe page kare. LLM apps mein token-count metric par alarm cost-runaway detect karne ka sabse cheap tareeka hai.

---

## ✅ Takeaway

- **CloudWatch → All metrics → Bedrock → By Model ID → Nova Lite** = proof ki sach mein Bedrock call ho raha hai (token counts + latency dikhte hain)
- Lambda metrics: invocations, duration, errors, throttles, concurrency — function health ka full picture
- **Log groups** mein REPORT line se Billed Duration aur Max Memory Used milte hain (right-sizing + cost ke liye)
- Apna **twin dashboard** banao: line widgets (Bedrock tokens/latency, Lambda duration) + number widget (errors = 0)
- Lambda ka **Monitor tab** sabse quick built-in metrics + logs access deta hai
- Day 3 wrap; kal Day 4 mein **Terraform (Infrastructure as Code)** se poora environment code se banega

---

<details>
<summary>📜 Full Transcript (English)</summary>

But I know you. You're not the trusting sort. You want evidence that we're calling Nova? It's not clear. Maybe it's still calling OpenAI. Just in a more chatty kind of way or something. We need to see what's going on. And that is a great moment for us to dive into. CloudWatch, the monitoring side of AWS, which will give us exposure to everything going on. So from the AWS console we're going to go to CloudWatch. We're going to go to all metrics. And we're going to start by looking at some metrics associated with our Lambda function. So let's do that right now. Um and there are a bunch of different ways you can get to this actually. But but let's start with with CloudWatch. Here is CloudWatch. And we start by going to all metrics on the left. And then in all metrics we can see all these different things we can choose from. We are going to begin by looking for Lambda which is right here. And within Lambda we can choose uh by resource or by function name. Let's go by function name. Let's choose the. You can see there's a few more functions that we're going to have coming up soon. Uh, but we are going to try and not get too lost in this and find an API. And we can see errors, duration, concurrent executions and invocations and throttles. And this is showing us everything that's gone on on the twin MPI, uh, in the last whatever this is. And we've got this nice little charts up here that can tell us what's happening, and we can look back in time, or we can really zoom in on the last hour to see what's been going on. And this will give you all the visibility into what's happening with your Lambda function. Okay. And now to look at the bedrock metrics. Let's see what's been going on there. You click up here somewhere and you navigate your way to all so that we can come back to bedrock. It's kind of confusing, but it shows on this timeline all the metrics that you've checked. So you get to see everything together. So we're now coming into bedrock. I'm going to choose by model ID, and I can choose to say I want to see Nova Lite, the model I chose, how many invocations, input tokens and output tokens and latency. And now that information is being superimposed on this diagram along with other things. So we're looking for, um, these bedrock, uh, events down here. Um, and uh, let's see if we can find them. Uh, here we go. So here's an example right here. Uh, you can see that bedrock, uh, a bit hard to show you, that sort of green one there is saying that bedrock was called the latency. Uh, I presume that's 1000 milliseconds to look like a second to come up with this. And you can see that the input token count was 4800. And you can see the output token count was 134 tokens. Uh, and the invocations was one. So this shows you how, first of all, there is your proof. Uh, if you didn't believe me, we did, in fact, call Amazon Nova Lite. And we did so because CloudWatch tells us so. And this shows you how you can add different metrics and see them on this timeline that you can then control up here so that you can see everything laid out together based on what you check down here, and by navigating around these menus here starting from all. So that's the way that you put everything together into your metrics and see what's going on in your AWS world. So you can also see logs in a convenient way from CloudWatch. You just on the left here in this sidebar you go to Log groups and then you can pick something that that we would be interested in, like twin API, which is presumably all that you see. And then you can look at these different times when it made some log information. Pick one of them and up it will come. You may need to click display and uh, expand all rows to see it quite the way I've seen it. But you'll see in here things like the requests coming in and then how long it took to respond to the requests and how much that was billed as and memory and memory used, and some other interesting bits and pieces along the way. So this is showing us our login. We haven't put much extensive logging in, but this is where you could go. And you can also set up dashboards as well, which can be useful in CloudWatch. You go to dashboards at the top here. Create a dashboard. We'll call our dashboard twin dashboard. Create dashboard. Here we have it. And we are now going to have a line on our on our dashboard. Let's do one from bedrock. Let's go with model ID and let's put on our line the things that we care about input tokens, output tokens uh invocations and latency. Here we go. We now have a line chart on our dashboard showing this. Let's also add something with a plus button here. Let's add lines that are related to Lambda. So we go into our lambda section. There it is. We'll say um by function name, and we'll go with the twin API. Let's see. Let's go for, uh, duration invocations and have that as a widget on here. There we go. That's when when how long it took and how often it was. It was called. Um. And then let's add one more. Let's add something about errors but not have it be a line. Let's have it be a number, a number to show us the number of errors. Next. So we pick lambda again which is scroll down. It's a lot to navigate here. Uh lambda uh by function name to an API. Again where are you. There you are twin API. And we want to say twin API errors. So this will be the number of errors. And there we go a big old zero. That's what we like to see. No errors from Lambda. Um okay. I think that's probably enough to show you a dashboard. So this would now be our twin dashboard, and you could build your own dashboard so that you could be watching out for how often your twin is called and what's going on. And finally, I do want to show you you can get a lot of this information from the Lambda page itself to in quite a nice way. So if I go to Lambda and I then bring up our twin API here, there is a monitor tab right here. And when you go to that you get a bunch of CloudWatch metrics automatically configured and showing for you. You could of course put this on the dashboard that you're creating as well, but it shows you invocations, duration and so on. Uh, and you also get down below it your CloudWatch logs that you can access immediately as well, the most recent and the most expensive. Um, and then there's some other stuff here. Uh, but but this, I think, is the quickest way to access your logs and visuals associated with any one lambda function. And that is a wrap for week two. Day three. We just added Amazon Bedrock to our are AWS deployment, and it just all worked really nicely with just a couple of changes here and there. It was also a good way to practice re-uploading your Lambda function, which wasn't that hard, and everything seemed to be nice, and we were able to use the Nova models to boot, which was good. And then we were able to use CloudWatch to convince ourselves that we were in fact calling the Amazon Nova models via bedrock. So that's a big moment. Uh, I promise you a lighter day. And it was a bit lighter. We made great progress. Tomorrow is a huge deal. We are now going to move to using Terraform infrastructure as code to build the entire twin environment. And it's going to be like, oh, why don't we just start with this? Uh, but this was important. It was a rite of passage. It was something that you had to go through so that you would. I did it all so that you would appreciate how great Terraform is. Uh, and so that will be the fare for tomorrow. Uh, I'm really, really looking forward to showing you what Terraform can do. Uh, and I will see you then.

</details>
