# L87 — Automating AI Agent Workflows with AWS EventBridge Scheduling

> **Week 3 · Day 5** · ⏱️ ~9 min

---

## 🎯 TL;DR

Last piece: ek **EventBridge scheduler** har 2 ghante mein ek chhota **Alex Scheduler Lambda** trigger karta hai jo App Runner par research auto-run kick karta hai — pura data pipeline ab autonomous. Enable karna trivial: `scheduler_enabled = true` karo aur `terraform apply`. Phir traces + CloudWatch logs se live evidence dekhna.

---

## 🗣️ Hinglish Explanation

### Architecture diagram — pura picture

`guides` folder mein **architecture diagram** open karke Ed pura granular flow dikhata hai. Ab tak ke simple diagram ka detailed version. Sabse upar ki do pieces hi baaki hain build karne ko:

```
┌────────────────────────────────────────────────────────────────┐
│  EventBridge Scheduler  (cron: every 2 hours)                    │
│         │                                                        │
│         ▼                                                        │
│  Alex Scheduler Lambda  (chhota — sirf research_auto call karta) │
│         │                                                        │
│         ▼                                                        │
│  App Runner (Researcher)  ── OpenAI Agents SDK loop ──┐          │
│         │                                              │          │
│         ▼                                    Playwright MCP       │
│      Bedrock (OSS 120B / Nova on us-west-2)  (headless Chrome)   │
│         │                                                        │
│         ▼  (research results)                                    │
│  API Gateway (REST API + private API key)                        │
│         │                                                        │
│         ▼                                                        │
│  Ingest Lambda  ──►  SageMaker (embed/vectorize)  ──►  S3 vectors│
└────────────────────────────────────────────────────────────────┘
```

### EventBridge Scheduler kya hai?

**Amazon EventBridge Scheduler** ek AWS service hai jo **events** par actions trigger karti hai. Sabse simple use-case: **time-based trigger** — har period ke baad kuch chalao, bilkul ek **cron job** ki tarah, par fully managed (koi server nahi). Hum **har 2 ghante** par schedule set karenge, jo ek Lambda function ko fire karega.

### Alex Scheduler Lambda

Ek bahut simple Lambda: **Alex Scheduler**. Iska ekmaatra kaam — `research_auto` ko call karna, yaani App Runner par ek research run kick karna (wahi run jo lecture 86 mein manually kiya tha). Yeh fire-and-forget hai.

Pura autonomous flow:
1. **Har 2 ghante** EventBridge scheduler wake-up karta hai
2. **Alex Scheduler Lambda** trigger hota hai
3. Lambda **App Runner** ko call karta hai → research run shuru
4. App Runner par **agent** chalta hai, **Bedrock** (OSS/Nova) use karke reason karta hai
5. Agent **Playwright MCP** se web research karta hai
6. Result **API Gateway** (REST API, private **API key** se secured) ko call karta hai
7. Wo **Ingest Lambda** ko trigger karta hai
8. Ingest Lambda **SageMaker** se vectorize karke **S3 vectors** mein store karta hai

### Scheduler enable karna — ridiculously easy

`guide 4, step 6: enable automated research`. Yeh **optional** marked hai kyunki har 2 ghante chalne se **chhota charge** lagega. Comfortable ho toh enable karo, ya thodi der chala kar off kar do.

Sirf ek line badalni hai. `terraform/4/terraform.tfvars` ki last line:

```hcl
# pehle
scheduler_enabled = false

# ab
scheduler_enabled = true
```

Phir bas `terraform apply`:

```bash
cd terraform/4
terraform apply
```

`yes` bolo. Itna hi! Ed bolta hai "seems ridiculously easy, there must be more to it" — nahi, bas yahi hai.

### Scheduler ki Terraform code

Terraform file ke last sections mein AWS scheduler hai. Conditional creation — `scheduler_enabled` `true` ho tabhi resources bante hain:

```hcl
# main.tf — scheduler section (reconstructed)
resource "aws_scheduler_schedule" "alex_research_schedule" {
  count = var.scheduler_enabled ? 1 : 0     # flag se create-or-not

  name = "alex-research-schedule"
  schedule_expression = "rate(2 hours)"     # har 2 ghante

  flexible_time_window { mode = "OFF" }

  target {
    arn      = aws_lambda_function.scheduler[0].arn   # Alex Scheduler Lambda
    role_arn = aws_iam_role.scheduler[0].arn
  }
}

resource "aws_lambda_function" "scheduler" {
  count         = var.scheduler_enabled ? 1 : 0
  function_name = "alex-scheduler"
  # ... calls research_auto on App Runner ...
}
```

`count = var.scheduler_enabled ? 1 : 0` — yeh Terraform ka **conditional resource** pattern hai: flag `true` toh 1 resource banega, `false` toh 0 (yaani kuch nahi). Apply ke baad: **"automated research is running every two hours."**

### Live evidence — leap of faith se proof tak

Apply ke baad tumhe "leap of faith" lena padega — chhod do, baad mein traces dekho, har 2 ghante run dikhega. Par Ed proof dene ke liye **schedule ko 10 minutes** kar deta hai (demo ke liye), aur evidence dikhata hai:

#### 1. OpenAI traces

platform.openai.com → **Logs → Traces** (ya Dashboard → Logs → Traces). Har **10 minute** par researcher chala dikhta hai. Kisi ek trace mein jaao:
- MCP server se navigate kiya
- Kuch web pages dekhe, kuch click kiye
- End mein `ingest_financial_document` tool call karke text ingest pipes ko de diya

Yeh "in the wild" working hai — autonomous, repeated.

#### 2. `test_search.py` — knowledge base growth

```bash
cd backend/ingest
uv run test_search.py
```

Pehle 3 vectors the; ab **10 vectors** dikhte hain index mein. Har search ke 3-3 results — clearly aur information aa rahi hai. Pipeline live, har 10 min stuff ja raha hai.

#### 3. AWS Console — App Runner + CloudWatch logs

1. AWS Console (AI Engineer user) → **App Runner** → **researcher** service kholo
2. Dekho kab deploy hua
3. **View in CloudWatch** → **application logs** → log stream
4. Yahan agent ke log messages ka stream dikhta hai

Logs mein kya dikhega:
- **Successful** runs (stored vectors)
- Kabhi **"max turns exceeded"** error — Ed ka total turns 10 set hai; Nova thoda inferior hone ki wajah se directions stick nahi kar pata, fussing karta rehta hai 10 turns se zyada. (Ed final version mein 20 karega.)
- Kabhi **browser page timeout** — page load slow ho toh stuck

> **Observability ke do jagah (production mein agent dekhne ke liye):**
> - **App Runner CloudWatch log events** → tumhare Python code ka logging (infrastructure-level)
> - **OpenAI Traces** → agent ke detailed metrics, har tool call (agent-level)

### Yeh kya hai — production data pipeline

Ye ek **production-grade data ingest pipeline** hai with: agents + MCP + Lambda + App Runner + scheduling. Imagine karo isse kaise extend kar sakte ho — kisi bhi source se regular cadence par information collect karke apne data pipes ke through daal sakte ho. Har 2 ghante (ya jo bhi cadence) yeh wake-up hokar research karta rehta hai aur S3 vectors mein knowledge build karta jaata hai.

---

## 📋 Key Concepts

| Concept | Matlab |
|---|---|
| **EventBridge Scheduler** | Managed cron — time-based events par actions trigger; "rate(2 hours)" |
| **Alex Scheduler Lambda** | Chhota Lambda jo App Runner par `research_auto` kick karta hai (fire-and-forget) |
| **`scheduler_enabled = true`** | Ek-line flag → `terraform apply` → automation ON (optional, chhoti cost) |
| **Conditional resource** | `count = var.flag ? 1 : 0` — flag se resource create-or-not |
| **`rate(2 hours)`** | Schedule expression — har 2 ghante (demo mein 10 min) |
| **API Gateway + API key** | REST API private key se secured — ingest call ka enterprise plumbing |
| **CloudWatch app logs** | App Runner ka Python logging — infra-level observability |
| **OpenAI Traces** | Agent-level observability — har tool call ka detail |
| **max turns exceeded** | Agent loop limit (10) cross — Nova fussy hone par; 20 tak badha sakte ho |

---

## 💼 Backend Dev Ke Liye Note

Yeh ek **scheduled / batch data pipeline** ka cloud-native version hai jo backend dev cron + worker se banata aaya hai. EventBridge Scheduler = managed cron (koi crontab, koi always-on box nahi); Alex Scheduler Lambda = lightweight **trigger/dispatcher** (kaam khud nahi karta, sirf downstream service ko poke karta hai) — yeh **decoupling** hai, exactly jaise tum ek cron se ek queue/worker ko trigger karte ho. **Conditional resource (`count = ... ? 1 : 0`)** Terraform ka feature-flag mechanism hai — cost-bearing infra ko declaratively on/off karne ka clean tareeka, environment-specific deployments mein bahut kaam aata hai. **Do-layer observability** crucial lesson hai: **infra logs (CloudWatch)** batate hain "service crash/timeout hua?", aur **trace logs (OpenAI)** batate hain "agent ne andar kya socha/kiya?" — production mein dono chahiye, ek se doosre ka root cause nahi milta. **"Max turns exceeded"** ek classic agent **circuit-breaker** hai — infinite loop / runaway cost se bachne ka guard; isko sahi tune karna (10 vs 20) reliability aur cost ka tradeoff hai. Aur **API Gateway + API key** internal service-to-service auth ka simple form hai — even internal calls ko authenticate karna defense-in-depth best practice hai.

---

## ✅ Takeaway

- **EventBridge Scheduler** (managed cron, `rate(2 hours)`) → **Alex Scheduler Lambda** → App Runner research run → pura ingest pipeline autonomous
- Enable trivial: `scheduler_enabled = true` + `terraform apply`; Terraform `count = var.flag ? 1 : 0` se conditional create
- Yeh **optional** hai (chhoti recurring cost) — comfortable na ho toh `false` karke apply, ya `terraform destroy`
- **Do-layer observability**: App Runner CloudWatch logs (Python/infra) + OpenAI Traces (agent tool calls)
- Live proof: 10-min schedule par traces repeated runs dikhate hain, `test_search.py` mein vectors 3 → 10 badhe — enterprise-grade autonomous data pipeline

---

<details>
<summary>📜 Full Transcript (English)</summary>

Well, hopefully you're feeling pretty satisfied with how everything's holding together. We've got a quite sophisticated data pipeline in action, and you're hopefully seeing it working and understanding what's going on. And there's some more things for you to test that will give you even deeper understanding. Uh, looking at checking the health health routes and, and doing some other, more specific tests. But then we've got to the final way. We're going to make it just one step more complicated. And to show you that I'm going to bring up an architecture diagram, uh, which you will find in the guide. So let's go over here into guides and open up architecture. And I just want to summarize. This is the more granular version of that simple architecture diagram I showed you, which is showing you the different pieces in place. We are going to set up something called an EventBridge scheduler, which is an AWS service which is able to carry out respond to events. And one of the simplest ones is to do something after every period of time, like like a cron job. And we're going to do it every two hours, and it can kick off a lambda function. And we're going to have a very simple lambda function called Alex Scheduler, and its only job is basically to call research auto. It is going to kick off an app runner run, just like the one we kicked off a moment ago that we know with my setup is only going to work half the time, but hopefully with your setup works every time and will do for me once the bedrock issue is resolved and I'm back to OSS. Uh, so, uh, that's going to kick off every two hours and that is then going to follow the exactly the process that we have built. Uh, it calls app runner. App runner is is running our agent. Our agent uses bedrock hopefully for you and shortly for me. It's using OSS one A-20b and being reliable on us West two. And it is then going to be calling the, uh, the the API gateway with the rest API with this private key that for security purposes, we've put this API key in. Um, it's going to be doing that. Uh, it's going to be doing that based on the results of this research that is going to be calling our lambda ingest function that we built two days ago now, and that is going to vectorize using SageMaker and store that in S3. So this is the full architecture diagram with these two pieces up here as the last pieces to be built. And hopefully now this architecture diagram completely is clicking for you. And you're familiar with all of these components. All right. With that let's get some scheduling. So here I am in the guides I'm in guide for step six enable automated research. And this is marked as optional because this will kick off our flow every two hours. And so there will be a small charge associated with this. And so only do this if you're comfortable with that. Or you could run it for a bit and then turn it off. Uh so we're going to enable the automated research. And the way to do it is very simple. You go into your terraform.tf vars file in Terraform directory in for researcher there is the file. The last line of that file should right now say scheduler enabled equals false. And change that to true. and I just did that before I pressed record. So that has happened already. And once you've done that, all you need to do is run terraform, apply again. Uh, so we go back in here, we will go to, uh, back back to, to this directory Terraform and back into the fourth directory. And we just simply run terraform. Apply again. It seems ridiculously easy. There must be more to it than this. Uh, and while it's doing its thing, I'm going to say yes. I'm going to show you the Terraform code while it's running so you can see what it's actually going to be doing. If we look in here, you will see that the, uh, last few sections of this is the AWS, uh, scheduler. And you can see here that it's based on whether the, uh, the scheduler is enabled, whether actually go ahead and create this or not. That's what makes this be created. The Alex research schedule, uh, it's being set to be every two hours. And its target is to call a lambda function called scheduler, and this is the lambda function that sets up that, that that lambda function. Uh, this is the IAM related stuff and that is it. And it is happened. And it says here automated research is running every two hours. So just like that, we have kicked it off. Uh, and at this point you will have to take it on leap of Faith. At this point, uh, you will leave this running and you will come back later and look in your traces and you will see that it is running every two hours. And the evidence that I have for it for you now is what you saw in my traces. You saw all of those, uh, previous runs that had happened after I kicked this off. And you will have that same experience yourself. It is now running. You have a live data ingest pipe every two hours. It's waking up, it's doing some research, and it's then calling that whole architecture we were just looking at to bring that through your data pipes and ultimately end up with that in S3 vectors. And you can imagine how you could extend this to so many scenarios where you're collecting information from different sources on a regular cadence and then putting it through your data pipes. So this is a great example of a production grade data ingest pipeline with agents, with MCP, with lambda functions, and also with App Runner. And it doesn't feel real unless I can show you the evidence. And so I changed the schedule to run every ten minutes instead of every two hours. And I've gone into the traces right here. We're in openai.com logs which, which you can also get by going to dashboard and then clicking logs and then clicking traces. We are seeing the tracing coming from OpenAI agents SDK. Sure enough you can see if you look down here that every ten minutes my researcher has been running. And if we click into one of these we get to see the trace. We get to see it's navigated using its MCP server, looked at a few web pages, clicked on a few things, and it's ended by calling the tool ingests financial document, passing the text over to our ingest pipes. And so that is it working in the wild. Let's just go and check and see that it has actually been storing documents. And so back in cursor I'm now going to go into backend and into the ingest directory. You may remember that we have a test search Python script that looks in our vector store and tells us what we've got there. Last time I think we had maybe three in there. Let's see what we have now. So we will do uh, UV test search, I think. There we go. Let's run this and see what happens. All right. There's a bunch of stuff in here. Uh, let's go up to the top of this. Uh, so, um, it's, uh, found, uh, ten vectors in the index. So stuff has been put in there. Uh, and, uh, here we go. Lots of interesting things have been going in there. Three results for one search, three results for another, three results for another search. Uh, and, uh, yeah. Clearly there is more information in here. This is working. It's running every ten minutes. Stuff is going in. Let's take a final look in the AWS console itself, and then we will call it a wrap. And so here I am in the AWS console logged in as AI engineer. Let's look for App Runner. There it is. We want to find the researcher. It's right there. We'll go into it. Here it is. We'll see when it got deployed. And then we can say view in CloudWatch to bring up the logs in CloudWatch. And we'll be able to look at what's going on. And what you'll see is that, oh wait this is this is the metrics for the uh for the deployment. Hang on. Let's go back here again. Let's look at the application logs. View the application logs in CloudWatch. Now let's see if this shows us this log stream right here. This should show us. Yep. This is showing us the stream of log messages from our agent. And what you'll see is that this has been successful. Sometimes sometimes it's having a max turns exceeded error because I've got my my total number of turns set to ten. I think I'll make that up to 20 before I push the final version of this. But but, uh, also, it's almost certainly because this slightly inferior Nova model is struggling to stick to its directions, to try and do things quickly. And so it's just keeping on fussing away until it's done more than ten turns, so you can look back through the logs to see examples of where things are working well and where they're getting in trouble. There's a couple of other times I saw higher up when it gets stuck because a browser page is taking too long. So there's other things that can be corrected for. I think it's this one right here. Uh, so, uh, you can look back and see that it's running. See, it's running every ten minutes. See the ones that are getting successfully stored. And use that to satisfy yourself that your agent is running. Uh, and these are the different places that you would go to to observe your agent in production. You would look at the app runner log events to see what your Python code is logging. And then within OpenAI you go to traces to look at the detailed metrics about your agent operating in production. So I would say we can say that we could tie a bow on the ingest pipes and say, this has been a success.

</details>
