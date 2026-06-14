# L109 — Monitoring AI Agents in Production with CloudWatch and Dashboards

> **Week 4 · Day 4** · ⏱️ ~12 min

---

## 🎯 TL;DR

Live ALEX run kick off karke hum **CloudWatch logs** mein dekhte hain ki agents (planner → reporter/charter/retirement) ek-doosre ko Lambda functions ke through actually call kar rahe hain, aur phir **Terraform se banaye 2 CloudWatch dashboards** (AI Model Usage — Bedrock/SageMaker; Agent Performance — execution times/errors/throttles) explore karte hain.

---

## 🗣️ Hinglish Explanation

### Monitoring = logging se shuru hota hai

Yeh section servers par "actually kya ho raha hai" ka insight deta hai — aur sabse basic tool hai **logging**. Ed assume karta hai tum Python ka standard logging jaante ho:

```python
import logging

logger = logging.getLogger(__name__)

logger.info("Planner started orchestrating")
logger.error("Failed to fetch market data")
```

ALEX ke agents mein already kaafi logging hai. **Assignment:** apne khud ke aur log messages add karo — "it's even more satisfying when you see your own log messages coming through." Ed ek **structured logging** approach suggest karta hai (optional):

```python
import json, logging

logger = logging.getLogger(__name__)

def log_event(event: str, **kwargs):
    logger.info(json.dumps({"event": event, **kwargs}))

# Usage
log_event("price_update", symbols=16, source="polygon")
```

Structured (JSON) logs ka faayda: CloudWatch mein query/filter karna easy ho jaata hai. Par chaaho toh simple `logger.info(...)` bhi theek hai.

### Step 1: Application kahan chal rahi hai? Terraform output

Pehle application URL nikaalo. Yaad karo:

1. Naya terminal kholo
2. Terraform directory → `7_frontend` folder (yahan front end hai)
3. `terraform output` chalao — yeh saare output variables dikhata hai, jisme **CloudFront URL** bhi hai

```bash
cd terraform/7_frontend
terraform output
# ... cloudfront_url = "https://dxxxx.cloudfront.net"
```

> **Background:** `terraform output` un values ko print karta hai jo tumne Terraform config ke `output` blocks mein declare kiye the (jaise CloudFront domain). Yeh state file se padha jaata hai.

### Step 2: Run kick off karo

CloudFront URL kholo → ALEX UI ("isn't it gorgeous") → **Advisor Team** → **kick off a new analysis**. Ab background mein agents ek-doosre se baat kar rahe hain, kaam ho raha hai, aur yeh sab logs mein dikhna chahiye.

### Step 3: CloudWatch Logs — planner agent dekho

AWS console → **CloudWatch** → **Log Groups**. Har Lambda ka apna log group hai (`alex-planner`, `alex-reporter`, `alex-researcher`, etc.).

> **Background:** **CloudWatch** AWS ka monitoring + observability service hai. Har Lambda function automatically apne `stdout`/logger output ko ek **log group** mein bhejti hai, jisme **log streams** (har execution) hote hain. Yeh metrics, dashboards aur alarms bhi support karta hai.

**Alex Planner** log group kholo → latest log dekho. Ed step-by-step bataata hai kya hua:

1. **Lang... (Langfuse) stuff** dikhta hai upar — yeh agle lecture ka sneak peek hai, abhi ignore karo
2. **Planner Lambda began** → orchestrating shuru ki
3. Pehle check kiya: koi instrument hai jiska **allocation data missing** hai? → "all good", sab ke paas hai, toh **tagger** ko call karne ki zaroorat nahi
4. **"updating instrument prices from market data"** → current prices fetch kiye
5. **Polygon.io** ko call kiya — **16 symbols** ke liye prices fetch (Ed ke paas paid plan hai, isliye heavy hitting OK; free plan par yeh **cached** hota hai)
6. "market price updated" — sab collect ho gaye
7. **Nova Pro** model se chat completion (model name verify kiya)
8. Phir **alag Lambda functions call kiye** — `reporter`, `charter`, `retirement` — yeh proves **tool calling** kaam kar raha hai
9. Aakhir mein: **"plan job completed successfully"** + total duration, memory used

> **Background:** **Polygon.io** ek market-data API hai (stock prices). **Nova Pro** Amazon ka Bedrock-hosted LLM hai. ALEX mein planner ek "orchestrator agent" hai jo doosre agents ko **tools** ki tarah call karta hai (agent-as-tool pattern) — har tool call actually ek alag Lambda invoke hai.

### Step 4: PROVE karo ki agents ek-doosre ko call karte hain

Ed bolta hai tum "suspicious person" ho — log keh raha hai reporter ko call kiya, par kaise believe karein? **Proof:**

1. Planner log mein dhundo kab usne **reporter** invoke kiya — maan lo **19:15** par
2. Wo timestamp yaad rakho
3. **Log Groups** → **Alex Reporter** → 19:15 wala log dhundo
4. Sure enough — reporter usi time kick off hua, apna kaam kiya

Reporter log mein dikhta hai woh **S3 Vectors mein market insights** lookup karta hai — woh expertise jo **researcher agent** ne har 2 ghante par process karke wahan daala tha. Yeh poora connection live dikhta hai, aur phir reporter results **database** mein post kar deta hai.

> **Background:** **S3 Vectors** = vectors ko S3 mein store karne ka cost-effective tareeka (Week 3 mein banaya). Researcher agent EventBridge se har 2 ghante chalta hai, web research karta hai, embeddings banata hai (SageMaker), aur S3 Vectors mein daalta hai — yeh ALEX ka RAG memory hai.

### Step 5: CloudWatch Dashboards — Terraform se banaye

Pehle dashboards console mein manually banate the, par "we know about Terraform now." Isliye Ed ne ek naya folder banaya: **`8_enterprise`** (Day pehle bola tha `7_frontend` last hai, par yeh ek aur add ho gaya).

#### Deploy karna

```bash
cd terraform/8_enterprise

# 1. tfvars example copy karo, sirf region + model name bharo
cp terraform.tfvars.example terraform.tfvars
# terraform.tfvars mein:
#   bedrock_model_id = "..."
#   aws_region       = "us-east-1"
#   bedrock_region   = "us-east-1"

# 2. init + apply
terraform init
terraform apply
```

Yeh **2 dashboards** turant bana deta hai (is baar minutes wait nahi).

#### Dashboard 1 — AI Model Usage (Bedrock + SageMaker)

> "a beautiful look at bedrock"

- **Model invocations** — kitni baar Bedrock model call hua
- **Token usage** — kitne tokens use hue
- **Latency** — response time
- Time range badal sakte ho (12 hours / 1 day / 3 days) — zyada history zyada data dikhati hai
- **SageMaker** metrics bhi — **research agent** har 2 ghante "wake up" hota hai (dot-dot-dot pattern), aur application run ke time bhi SageMaker use hota hai (reporter ko vectors banane ke liye embeddings chahiye). Latency microseconds mein.

Ek dashboard mein dono core data-science platforms (**Bedrock + SageMaker**) ka usage dikh jaata hai.

> **MLOps note (Ed):** ek MLOps person yeh screen hamesha khula rakhta — production mein model usage inspect karne ka tareeka.

#### Dashboard 2 — Agent Performance

- **Agent execution times** (milliseconds)
- **Error rates** — kis agent mein kab error aaya
- **Invocation counts** — kitni baar call hua
- **Concurrent executions**
- **Throttles** — "good to see there's no throttles"
- **Color-coded by agent**: planner, reporter, charter, retirement, tagger — planner sabse zyada time leta hai

> **MLOps / production-support note:** is dashboard se errors drill-in kar sakte ho. Ed reporter ke kuch purane errors dekhke bolta hai woh investigate karega (probably observability build karte waqt aaye the).

Dono dashboards **week 2 wale dashboard** jaisa hi pattern follow karte hain — Terraform code padho aur usse aur dashboards bana sakte ho.

```hcl
# 8_enterprise/main.tf — conceptual CloudWatch dashboard via Terraform
resource "aws_cloudwatch_dashboard" "agent_performance" {
  dashboard_name = "alex-agent-performance"
  dashboard_body = jsonencode({
    widgets = [
      {
        type = "metric"
        properties = {
          metrics = [["AWS/Lambda", "Duration", "FunctionName", "alex-planner"]]
          title   = "Agent Execution Times"
          region  = var.aws_region
        }
      }
      # ... error rate, invocations, throttles widgets
    ]
  })
}
```

---

## 📋 Key Concepts

| Concept | Matlab |
|---|---|
| **Python logging** | `logging.getLogger` + `logger.info/error` — har agent apne events log karta hai |
| **Structured logging** | JSON format mein logs — CloudWatch query/filter easy |
| **`terraform output`** | Deployed resources ki values (jaise CloudFront URL) print karta hai |
| **CloudWatch Log Groups** | Har Lambda ka apna log group; streams = individual executions |
| **Agent-as-tool calls** | Planner doosre agents (reporter/charter/retirement) ko tools ki tarah call karta hai — har call ek Lambda invoke |
| **Cross-log proof** | Planner log ka timestamp use karke reporter log mein same invocation confirm karna |
| **S3 Vectors lookup** | Reporter market insights S3 Vectors se padhta hai (researcher ne 2-ghante par daale) |
| **Dashboard 1: AI Model Usage** | Bedrock invocations/tokens/latency + SageMaker usage, ek jagah |
| **Dashboard 2: Agent Performance** | Execution times, error rates, invocations, concurrency, throttles — agent-wise color-coded |
| **Dashboards via Terraform** | `8_enterprise` folder, `aws_cloudwatch_dashboard` resource — console nahi, IaC se |

---

## 💼 Backend Dev Ke Liye Note

Yeh lecture ek backend dev ke **distributed-tracing instinct** ko AWS-native tooling se connect karta hai. Jo tum local mein `logger.info` + ELK/Grafana se karte the, woh yahan har Lambda ke CloudWatch log group mein automatically flow hota hai — bina koi agent install kiye. **Cross-log correlation** (planner ke 19:15 timestamp se reporter ka log dhundna) bilkul manual distributed tracing hai; production mein iska upgrade hota hai **correlation/trace IDs** — har request ke saath ek ID propagate karo taaki services ke across logs join ho sakein (yeh observability lecture mein refine hoga). **Structured JSON logging** aaj se hi habit banao — CloudWatch Logs Insights mein `fields @timestamp, event | filter event = "price_update"` jaisi queries tabhi chalti hain jab logs machine-parseable hon. Aur key takeaway: **dashboards as code** — `aws_cloudwatch_dashboard` ko apne Terraform mein commit karo, taaki monitoring config bhi reviewable/versioned/reproducible rahe, console ke click-ops par dependent nahi.

---

## ✅ Takeaway

- **Logging foundation hai monitoring ki** — Python `logging` use karo, structured (JSON) logs query-friendly hote hain; assignment: apne logs add karo.
- **App URL `terraform output` se** (`7_frontend` folder, CloudFront URL); run kick off karo Advisor Team se.
- **CloudWatch Log Groups** har agent-Lambda ke logs dikhate hain — planner orchestration, polygon price fetch, Nova Pro completion, tool calls sab visible.
- **Agents truly distributed hain:** planner ke log ke timestamp se reporter ke log mein same invocation cross-verify hota hai; reporter S3 Vectors se researcher ke insights padhta hai.
- **2 Terraform-built dashboards:** AI Model Usage (Bedrock + SageMaker) aur Agent Performance (execution time/errors/throttles, agent-wise) — dashboards-as-code best practice.

---

<details>
<summary>📜 Full Transcript (English)</summary>

Okay, so this is where we really get insight into what's happening on our servers. It's about logging. And I'm sure you're familiar with basic Python logging when you import logging and you can say logger is logging.getlogger. And then you can have logging.info logger dot error and so on. And you probably noticed that I've done a fair amount of logging through the application in various places through our agents. The assignment I have for you is to go and add some more. Go and put in some more log messages, because it's even more satisfying when you see your own log messages coming through. So do that. Think of something that interests you, perhaps some part of the process that you don't know about. Add in some extra logging information because that's what we'll be seeing next. And uh, there's a suggestion you could do it the way that I suggest here by having a bit more structure to it and putting in some more information. You don't have to do that if you don't want to. You could just do logger.info. Uh, but this might give you some some extra ways to see more information. But once you've done that, we're going to now go and kick off a run and then look at some of the logs. Let's do that. So first of all let's go and kick off our application again. Do you remember where your application is even running. Do you remember how to find it? Here we go. We bring up a new terminal like this. We go into the terraform directory. We go into the seven folder which has our front end in it, and we type Terraform output if you remember this. And that tells us the values of our variables which includes our CloudFront variable right here. Unless you actually set up, you went through and you set up a front end, which would be very cool. But if you didn't, then this does it. And here it is. Remember this. Remember our application. Isn't it gorgeous. So we come in, we look again at our portfolio at our dashboard or our accounts. And we come through to the advisor team. And I'm going to kick off a new analysis. Let's do it off. It runs. So what's happening now, of course, is that our various agents are talking to each other. Things are happening. And that means there should be stuff that we can see in our Are logs. So let's go back to AWS and take a look at what's happening. So let's go into CloudWatch and in CloudWatch. Let's look at our log groups. Uh you'll see that there's a fair amount of Alex researcher happening here. And we will come down to see our log groups here. Let's look at the planner log group and we'll see that the planner Alex Planner has been running a fair amount. And this was right now. And let me bring this up and you can come in and see here what's happening in our planner. This is this is what's just just run since I pressed that button. Uh, and you can see that, uh, go to the top of it. Uh, so this was it kicking off. Uh, and, uh, you can see that the first thing it did was, um, we ignore this part here. This is the Lang View stuff coming up. You're getting a sneak peek at something we're going to do in a second, which is great. Uh, but, uh, what we'll see now is that the planner lambda began N and it began orchestrating. It started by checking for instruments that are missing allocation data, but it says all good. All the instruments have allocation data, so there aren't any instruments that need to be tagged with the tagger. But next it says updating instrument prices from market data. So it's doing that. It fetches current prices for this job. And this is now calling out of course to polygon. Uh and it's fetching prices for 16 symbols. Off it goes. It collects all of these. Look at this log messages coming. Is it hits polygon IO I've got the paid plans. It doesn't matter that I'm hitting it a lot with all these different stock prices market price updated. And at that point and by the way, if you're using the free plan then it then it caches it. So all all should be good for you as well. At that point this is completed. It's chat completion with Nova Pro. We checked the model name. And then what's going to happen now is it calls different lambda functions. It calls reporter and charter and retirement telling us that our tool calling is working and we're calling out to these different lambda processes, and then it's coming back. And then if we say resume, let's see if that's if that's the end of this and it's not the end of this. More has happened while I've been yabbering away. The world has not been quiet. Uh, it's all completed. It's finished. It, uh, it presumably had, like, a nice, uh, completion here. Completed, successfully plan a job completed successfully. It tells us. And then at the end here we have, uh, the total duration, the memory used and so on. And so this has given us this real clarity, this ability to see everything that's been happening behind the scenes. And now we know it wasn't just the user interface giving us a nice picture. Stuff was really happening. Agents were really being called. And the logs have given us that insight. Okay, so I hear you. You're impressed. You like this, but you're still suspicious because you're taking my word for it. You're taking the logs word for it that it's calling another agent. This planner agent. We see it says it does, but we don't really know that it does. You're a very suspicious person. Well, luckily, I'm going to be able to prove it to you. Let's see that. So we look in here, we find out where it claims that it was calling one of the other agents. Let's let's say for example reporter. That's perhaps one of the most interesting ones, the one that actually generates the report. So it claims that it invokes reporter at about 1915. So remember that 1915. That's when we're going to go and look now at reporter and see what happens. So we go back to log groups. We find Alex reporter. There is Alex reporter. We come in and here is a log at 1915. Okay. Let's go and have a look. And if we come in here we'll see that sure enough it's been kicked off. It's done its stuff. And what I want to show you, I want to show you that amongst other things, it does, it is going to get market insights. And this is when the reporter agent looks up in S3 vectors. It looks up the expertise that was put there by our researcher when it processes every two hours. So it's kind of cool to show you that that connection right there. And you can look through this and see that it will do it and post back the results. Uh, so to the database. So, uh, it's great to see this. It really gives you that perspective of everything that's happening behind the scenes. And it will hopefully now convince you that these agents really are talking to each other in different lambda, uh, serverless functions and that this is actually running behind the scenes. And that is why when we come here, we end up seeing these fabulous results, uh, because all of these agents really are working feverishly behind the scenes on AWS. And there's just one more thing, which is to show you CloudWatch dashboards. So the, uh, I think we saw this briefly a couple of weeks ago that AWS has the ability to show you summary metrics in dashboards you can build that will bring things together. And in fact, we can set up a dashboard. And you remember we went to AWS screens and we configured them through the console. But we don't do that anymore. We know about Terraform now. So we set up things like this just with Terraform scripts. And that's why I have set up a Terraform script in eight underscore enterprise. I think I said yesterday that when we were doing seven front end, it looked like it was the last one, but there was going to be one a little bit more. And here we have it. Eight enterprise I just created this. So if you open up, uh, it's clear that you open up a terminal and go to Terraform and then into eight Enterprise Directory. Um, the first thing you'll need to do, of course, you remember this so well now is you'll need to take the Terraform example and duplicate it and enter in, I think just the region and the model name. If we look at this, it just needs the bedrock model ID and the AWS region and the bedrock region, just the usual stuff. And then once you've done that and you made your own terraform.tf vars, then you know what to do next. You know what to do next. That's right. Terraform init, terraform init. And it does this. And then terraform apply. And it builds some dashboards. And this time it's not going to be one of me yammering away to wait a few minutes. It's right away. It's created it very quickly. And there's two dashboards for us to look at. Uh, and I can't wait to show them to you. And so here is the first one, the AI model usage. Let's bring this guy up open. Here it comes. And this is a beautiful look at bedrock. The number of, uh, model invocations that we've made. And because we just I just kicked it off a minute ago. Let's let's go back 12 hours instead. Let's see that you'll see that there's a bunch of stuff here been going on. Let's go back a whole day. Uh, so, uh, three days, we'll see even more, I imagine. Look at all that. So this is how many times we we invoked the model on bedrock. This is how many tokens that we used. This is the latency. So we're seeing all of these charts about what's going on. And then here we see SageMaker because of course SageMaker has been running as well our research agent. And you'll see this little dot dot dot dot dot. Because every two hours it's been waking up and there's some stuff you'll see that there's some stuff that isn't every two hours and you're wondering what that is. That's because when we're running the application and it's doing some research, it also needs to use SageMaker. Uh, so uh, you see it there as well. Uh, this is the reporter that we just looked at. It's also needs to to form the vectors. Um, and here is the latency, uh, information in microseconds. Uh, so this is giving us perspective in one dashboard about all of our usage of AWS, uh, core data science platforms, bedrock and SageMaker together in one place in this dashboard. And I encourage you to spend a bit of time looking at this and enjoy looking at the data that we've got. And as an MLOps person, you would probably have this screen up all the time and you'd be able to look at it, make sure nothing surprises you, and use this as a way to be inspecting the use of models in production. But there's a second dashboard as well, and it's this one right here. Agent performance let's open that up. And if this comes up, here we go. Uh, let's also go back like three days or something. So, uh, we've got agent execution times, error rates, how many times they were invoked and concurrently running and throttles. Good to see there's no throttles. Uh, and, uh, yeah. Interesting to see this execution times in milliseconds. Uh, so this this is really showing you how long things are taking. And the great thing is that the color of the different dots, it's colored by the different agent, planner, reporter, charter, retirement and tagger. So you can see them all there. And of course, the planner is the one that takes the most time there. And you can you can see how they all all fit together. And, uh, yeah, this is just just fantastic to see. Of course, again, as a as an MLOps or as a production support person, you would have this up, app be watching this carefully to understand are there any errors? I wonder why reporter had an error back then. Uh oh. Bunch of errors then. Uh, so, uh, that's interesting. Uh, I will be looking into that in a minute. Uh, this is just the kind of thing that we would want to do, uh, to to drill in and find out what's causing an error. I think that was when I was, uh, trying to build something that wasn't working, uh, to do with the observability that we'll do in just a minute. Uh, so so you'll be able to use this as a way to really drill into what's going on in production and to get that perspective. So it's great that we built these two dashboards through Terraform. It's set these two up. That's the dashboard that we built back in week two. Uh, so so these uh, these dashboards you can keep and you can look at the Terraform code or go and do that right now. Look at the Terraform code. And you can use that as a way to build more like it. Um here it is. These are, these are the, uh, the two, um, dashboards that are set up. And you can use this to make more and have this as a way that you can monitor everything that's going on in production in visually like that, in a dashboard.

</details>
