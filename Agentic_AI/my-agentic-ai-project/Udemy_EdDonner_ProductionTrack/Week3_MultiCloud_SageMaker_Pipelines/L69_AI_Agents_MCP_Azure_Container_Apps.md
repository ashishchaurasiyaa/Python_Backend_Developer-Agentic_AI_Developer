# L69 — Deploying AI Agents with MCP Servers to Azure Container Apps

> **Week 3 · Day 1** · ⏱️ ~10 min

---

## 🎯 TL;DR

`terraform apply` complete — cyber-security agent ab **Azure Container App** par LIVE hai, container ke andar Semgrep MCP server spawn karke. Hum live test karte hain, Azure portal mein resources + **Log Stream** dekhte hain, **OpenAI Traces** se observability dekhte hain, costs check karte hain, aur `terraform destroy` se sab kuch saaf kar dete hain.

---

## 🗣️ Hinglish Explanation

### Welcome to the other side — deployment done

Pichle lecture ka `terraform apply` complete ho gaya — ek **Azure Container App** deploy ho gaya, aur uska **URL** mil gaya. `Cmd+Click` karke kholo → wahi familiar **cyber security analyst** app, par ab URL `azurecontainerapps.io` dikha raha hai (yaani cloud par chal raha hai).

### Live test: poori chain cloud par chalti hai

1. App mein **"Open Python file"** → `airline.py` select karke open
2. **"Analyze code"** press

Ab dekho is button ke peeche kya hota hai — **end-to-end agentic flow, poora cloud par**:

1. Request Azure-deployed container par jaati hai
2. Container ke andar agent ek **Semgrep MCP server** ko **standard IO** par spawn karta hai (yaani container ke andar ek child process)
3. Wo MCP server humare `SEMGREP_APP_TOKEN` se **Semgrep cloud** se connect hota hai
4. Semgrep code par security analysis chalata hai, results wapas bhejta hai
5. Agent un results ko leta hai aur apni analysis banata hai (apne thoughts bhi add kar sakta hai)

Thodi der lagti hai (Ed ne ek lambi sentence drag ki par result tab tak nahi aaya 😄), phir result aata hai: *"Semgrep found 4 issues and I identified one issue."* Expand karke familiar vulnerabilities dikhte hain.

> **Teen jagah chal chuka hai ye app:** (1) local box par plain front-end/back-end, (2) local box par Docker container ke andar, (3) ab **Azure** par deployed Docker container ke andar — har jagah MCP server spawn ho raha hai. Yahi **portability** ka proof hai.

### Azure portal mein resources dekhna

Cursor se Azure portal par jao:

1. **Resource Groups** → apne resource group (`cyber-analyzer`) par click
2. Andar jo objects bane:
   - `cyber-analyzer` — **Container App** khud
   - **Container Apps Environment**
   - **Container Registry** (ACR)
3. **Logs** option ek advanced component hai — yahan tumhe query-style monitoring banana padta hai (KQL — Kusto Query Language). Ed bolta hai ye humara tarika nahi — **simpler way** hai.

### Simpler logs: Log Stream

Container App par click karo → wo "running" dikhega, region "East US", subscription, URL etc. Phir:

1. Left side **Monitoring** ke neeche → **Log Stream**
2. Display ke liye **Historical** choose karo
3. Pichle ek ghante ke **live application logs** dikhte hain

Logs mein tum dekh sakte ho ki app ne **Semgrep CLI** call kiya — yahi wo **spawned MCP server** hai humare app container (Docker container) ke andar, jo Semgrep chala raha hai, vulnerabilities dhundh raha hai, results wapas agent ko bhej raha hai, phir server process khatam. Ye real-time bhi dekh sakte ho — agent chalao aur logs aate hue dekho. Pretty cool.

> **KQL note:** Azure ka Log Analytics queries ke liye **Kusto Query Language** use karta hai (SQL jaisa par alag). Powerful hai par sikhne mein time lagta hai — isliye quick debugging ke liye Log Stream zyada easy hai.

### Doosri (aur bahut useful) jagah: OpenAI Traces

Logs ke liye ek bilkul alag jagah hai — **Azure se koi lena-dena nahi**. Yaad karo, agent ka code likhte waqt humne usse `with trace(...)` **context manager** mein wrap kiya tha — taaki logging/observability information report ho.

**OpenAI Agents SDK** ek built-in observability framework ke saath aata hai jise **Traces** kehte hain. Ye OpenAI platform mein built-in hai. (Ye popular observability tools jaise **MLflow** aur **Langfuse** ke saath bhi hook ho sakta hai, par yahan hum out-of-the-box wala Traces use kar rahe hain.)

```python
from agents import trace

with trace("Security Analyst"):
    result = await Runner.run(agent, user_input)
```

OpenAI platform → **Traces** section mein:
- Saare "security researcher" runs dikhte hain — chahe local box par alag configs mein, chahe Azure par deployed
- Kisi trace mein click karo → poori observability tree milti hai
- Dikhega: **Semgrep scan** run hua (yahi MCP server hai), uska **input** kya gaya, aur **output** (Semgrep ke results) kya aaya
- Wahi output agent ne use karke final response banaya jo humein mila

Ed ka point: **"This is where observability meets cloud deployment."** OpenAI Traces jaise tooling se tumhe agent workflow ke andar deep insight milta hai, aur saath mein container environment ke logs bhi milte hain — dono ka combination = production observability.

### Costs check karna (zaroori!)

Azure portal → **Cost Management** (search bar mein bhi type kar sakte ho):

1. **Budgets** → pehle setup kiye budgets dikhte hain (Ed ne $10 ka rakha tha) — ek progress bar dikhata hai ki budget ka kitna use hua
2. **Cost Analysis** (Reporting & Analytics ke neeche) → detailed screens:
   - Accumulated cost
   - Subscriptions breakdown
   - **Daily costs** chart — din-ba-din spend

Ed ke case mein roz **$0.17** lag raha tha (usne galti se ek mahine se container chalu chhod diya tha 😅). Mostly ye free credits se cover hota hai, par **regularly check karo** ki spend expected hai.

### Cleanup: `terraform destroy`

Agar aaj kuch cents bhi kharch hue to ab environment band karne ka time hai. Usi terminal mein jahan env vars loaded hain aur Azure workspace selected hai:

```bash
terraform destroy \
  -var "openai_api_key=$OPENAI_API_KEY" \
  -var "semgrep_app_token=$SEMGREP_APP_TOKEN"
```

Confirm karne ke liye `yes` type karna padega (poora "yes" — teeno letters). Destroy mein **kaafi time** laga — Ed ko ~8-9 minute lage. Ghabrao mat agar slow ho.

Verify: Azure portal → **Resource Groups** → `cyber-analyzer` resource group ab bhi dikhega **par bilkul empty** — kyunki humne resource group Terraform se pehle banaya tha (wo bas bahari framework hai), uske andar ke saare resources destroy ho gaye. Toh ab koi paisa nahi lagega.

### Day 1 wrap-up

Ye Week 3 Day 1 ka end hai — bahut kuch hua:
- Ek cyber security app (pre-built tha, par tour kiya)
- **Locally** chalaya
- **Container mein locally** chalaya
- **Terraform se Azure par deploy** kiya (Azure account setup + sab kuch)
- App ek **MCP server** use karti hai
- Bonus: **OpenAI Traces** observability framework se dekha ki MCP server call hua, aur log messages mein bhi (local Docker + Azure dono mein)

Ed: Terraform se environments **up/down** karna kitna easy hai — AWS console se kitna mushkil tha, Azure mein to console touch hi nahi kiya. **55% journey complete — half se zyada!** Kal **Google Cloud Platform (GCP)**.

---

## 📋 Key Concepts

| Concept | Matlab |
|---|---|
| **Azure Container App (live)** | Deployed app — URL `azurecontainerapps.io` par chalta hai |
| **MCP server spawn** | Agent container ke andar Semgrep MCP server ko standard IO par child process ke roop mein chalata hai |
| **Standard IO transport** | MCP server se communication stdin/stdout par (network port nahi) |
| **Azure Resource Group** | Resources ka logical container — saare cyber-analyzer resources yahan |
| **Log Stream** | Container App ke real-time/historical logs dekhne ka simple tarika |
| **KQL (Kusto Query Language)** | Azure Log Analytics ka query language — powerful par advanced |
| **OpenAI Traces** | OpenAI Agents SDK ka built-in observability framework |
| **`with trace(...)`** | Context manager jo agent run ko trace/log karta hai |
| **MLflow / Langfuse** | Popular observability tools jinse Traces hook ho sakta hai |
| **Cost Management** | Azure ka cost dashboard — budgets, daily cost charts |
| **`terraform destroy`** | Saare deployed resources tear down karna (cost bachane) |

---

## 💼 Backend Dev Ke Liye Note

Backend dev ke liye yeh lecture **production observability ka 360° view** hai. Do complementary layers samjho: (1) **infrastructure logs** (Azure Log Stream) — container kya kar raha hai, process-level, jaise tumhare app ke `stdout`/`stderr` ya CloudWatch logs; aur (2) **application/agent traces** (OpenAI Traces) — agent ke andar LLM calls, tool calls (MCP Semgrep), inputs/outputs ka structured tree, jaise distributed tracing (OpenTelemetry/Jaeger) jo tum microservices mein use karte ho. `with trace(...)` context manager ek span-style instrumentation pattern hai — agent SDK isse auto-capture karta hai, aur MLflow/Langfuse jaise backends mein export kar sakta hai (vendor-agnostic observability). MCP server ko **standard IO** par spawn karna ek important deployment detail hai: tumhe alag network service deploy nahi karni padti — agent process khud child process spawn karta hai, jo containerized deployment mein perfect fit hai (ek hi container, no extra ports). Aur **`terraform destroy`** ko ephemeral-environment discipline ki tarah dekho — production cost control ka core hai, aur preview/PR environments (spin up → test → tear down) ka foundation.

---

## ✅ Takeaway

- Deployed agent poori chain cloud par chalata hai: Azure container → spawned Semgrep MCP server → Semgrep cloud → results → agent analysis
- **Do observability layers**: infra logs (Azure Log Stream) + agent traces (OpenAI Traces) — dono milke production picture dete hain
- `with trace(...)` se OpenAI Traces mein har LLM call aur tool call (MCP) ka input/output dikhta hai
- **Costs regularly check karo** — Cost Management → Daily costs; free credits ke baad bhi spend monitor karna habit banao
- `terraform destroy` se ek command mein poora environment teardown — Day 1 done, 55% journey complete

---

<details>
<summary>📜 Full Transcript (English)</summary>

And welcome to the other side. Here we are. The Terraform apply has completed and an Azure Container app has been deployed. And here is its URL. Let's command and click into here and open and up comes a cyber Security analyst. It looks very familiar to us, but this time the only big change is the URL, which of course is showing Azure Container apps. All right open Python file and select airline.py and open. And there it is. And now press Analyze code. So again this is this is running on the cloud. This is deployed to Azure. The container that this is running in is now spawning an MCP server. So it's, it's uh running uh Semgroup MCP container over standard IO on that box in this container. And that is then going to connect to Semgroup using our token. And it's then going to run analysis on this code, bring back results. And our agent is going to use that to come up with its analysis of our code, potentially adding in some of its own thoughts as well. And I tried to drag along that sentence so that it would be done by the time I finished and I wasn't successful. It's taking a bit of time, but hopefully fingers crossed this is there we go. It's a sem grep found for issues and I identified one issue. That's great. Let's expand this a little bit and have a look. And we see the familiar issues. There they are. This is working. We have deployed successfully to Microsoft Azure. And you'll see nicely here that we have one running on my local box as just a front end back end. We have one running on my local box in a container in a Docker container. And this is when that Docker container has been deployed to Azure and is running the same way, including running the MCP server. That is success. And I hope that you are looking at this too. And so now back in cursor. We're just going to finish off the instructions by going back to the Azure portal to see what's being created. Go into the Azure portal. Here we go. I'm already logged in, I think, so it'll take me straight through to the dashboard screen that you get. I'm going to go to resource groups. I'm going to click on my only resource group, Cyber Analyzer. And here are the new Azure objects that we've created. The resources we've got cyber analyzer itself a container app container apps environment and the registry. If we go into logs, you get into this very advanced component where you can set up different ways of monitoring the, the app. And, and you have to build it like a query. Not not in classic, but you go into activity log and there's a lot of advanced tooling around searching for queries. That's not how we'll do it. There is a simpler way to do it. Go back to resource groups. Back in here again, we'll look actually at our cyber analyzer itself the container app. Click on that. Up it comes. Here it is. It's running. It's in East us under this subscription. That's the URL. If we want to bring it back up again the environment. And that's the link to where we just were. What we're going to do is we're going to come down to the left here under monitoring there's a option log stream. We come up with this. And for the display we're going to go historical. And we get to see the logs coming out of our application in the last hour in this case. And you'll see that it's run something. You can see the log messages as it calls Semgroup Semgroup CLI. This is the spawned MCP server within our app container, within our Docker container, running Semgroup and finding, uh, the vulnerabilities that it wants to, to respond to. Uh, and uh, back comes the results and it finishes the server process and back comes the results, uh, to our agent. So it's pretty cool to go in here and see these log messages happening within Azure. And you can also see them real time and then run your agent and see it happening, uh, while while it runs. And that that is us looking on the portal at, at the results of our deployment. And when we're talking about logs, there's a completely different place we can go that's also very useful indeed. And it's got nothing to do with Azure. You may remember that when we were writing the code for the agent, I wrapped it in a context manager with trace so that logging information is reported. The OpenAI agents SDK framework. For people familiar with this, maybe it comes with an observability framework called traces, and it also allows you to to hook that up to popular observability frameworks like MLflow and Lang views. But we can just use the one that comes out of the box with OpenAI agents SDK that's built into the OpenAI platform called traces. And here it is. And you can see the security researchers that have been running, whether it's on my local box at a couple of different configurations or whether it's deployed to Azure. And if we click into this, we can see the traces, the observability we get from running this on the cloud. And you'll see, lo and behold, the Semgroup scan was run. This is the MCP server. And we'll see the input that went into it. And we can see the output, the results from Semgroup giving us the information that we wanted. And that was then used by our agent to come up with the response that we were expecting. Uh, that we that we got back, uh, and so this this is a super important activity. This is this is where observability meets cloud deployment, using tooling like OpenAI's traces. That gives you that deeper insight into what's happening in your agent workflow, along with the logs coming from your container environment. And finally, it's important to come into the Azure portal and go and look at costs. So cost management again up comes cost management. You can also type cost management in the search bar up here. Uh here we are in the cost management section of Azure. One quick thing to do is to click on budgets to look at the budgets we set up earlier. You only set up one. I've got a few that are all I think the same thing. But you see a little progress bar that shows you how far you are going towards that budget. You might have set yourself maybe $10 like me, or maybe $2, uh, and you can look into the spend there. If you go into cost analysis under Reporting and Analytics, there's much more detailed screens here. There's things that you can look at an accumulated cost, um, a, uh, subscriptions. Visualize your cost and daily costs. Let's go into daily costs. And this is going to show me charts of day by day how much I am spending on my Azure infrastructure. And you can see that each day I'm spending $0.17. And this has been running for all of this month because I kicked off the cyber analyzer a month ago and I left it running, which is, uh, since I didn't use it that time is probably not a smart idea. Uh, but, uh, there it's been running and I had stopped it, and now it's running again. And this gives you a sense of your costs, which are probably all going towards your free credits that you've already got as part of your new account. But anyway, keep an eye on them, make sure they're what you expect. And if you've spent a few cents today, then now would be a good time for us to talk about bringing down the environment, which we will do next. And so here we are back in Casa again. And now we're going to destroy our Terraform environment by running the same command. And obviously in the same, uh, command prompt where I've loaded my environment variables and I have the Azure workspace selected. Or you can just repeat those commands from earlier and I run, Terraform, destroy to bring down the environment and free up the resources or let it do its thing and see you in a second. And of course, I had to press yes, type it out or all three letters for it to start the destruction. And it then actually took quite a long time. I think it took about 8 or 9 minutes to destroy all this. So. So don't worry if it takes a long time. It it appears to destroy, but it has destroyed. That has been successful. And now, one more time, let's go back to the portal to check. And here I am back in the Azure portal. I'm going to go to resource groups up here. And there is an a cyber analyzer resource group there. But when we open it up, we are pleased to see that it's completely empty. We didn't. We created the resource group before we even started the the Terraform stuff. So that that was just the sort of outer framework, but there's no resources within it. They got destroyed properly and so we won't be spending anything. Uh, hopefully you have the same experience. And this just goes to show how easy it is to use Terraform to bring up and bring down environments like that. Remember how hard it was through the AWS console? We haven't even had to do that with Azure. And that's a wrap to the day one of week three. We got an awful lot done. We we built a cyber security app, or at least it was pre-built. But we did a quick tour through it and hopefully a lot of it made sense to you because it's quite similar to the other apps we built. We ran it locally, we ran it in a container locally, and then we use Terraform to deploy it to Azure. After setting up an Azure account and going through all of that, and it uses an MCP server, and just as an extra bonus, we even went into the observability framework that traces framework in OpenAI to see that the MCP server was called. And we also saw that in the log messages, both in the Docker container locally and when it was deployed to Azure as well. So that's a lot to get done on day one of week three. Congratulations. That means you are 55% on the way through the journey. More than halfway. We are well on our way towards production expertise. See you tomorrow for Google Cloud Platform.

</details>
