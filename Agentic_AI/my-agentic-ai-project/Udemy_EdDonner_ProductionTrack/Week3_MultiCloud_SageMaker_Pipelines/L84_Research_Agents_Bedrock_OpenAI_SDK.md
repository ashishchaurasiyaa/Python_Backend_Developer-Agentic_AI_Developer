# L84 — Building AI Research Agents with Bedrock and OpenAI SDK on AWS

> **Week 3 · Day 5** · ⏱️ ~8 min

---

## 🎯 TL;DR

Project Alex ka chautha guide shuru — hum ek **Researcher service** banayenge jo OpenAI Agents SDK se agents orchestrate karega, **AWS Bedrock** par chalega, aur **Playwright MCP server** se internet research karega. Pehle Bedrock par naye models (OSS 120B + Nova) ka access request, phir `.env` aur `terraform.tfvars` setup.

---

## 🗣️ Hinglish Explanation

### Context: Project Alex aur guide 4

Yeh Week 3 ka **Day 5** hai aur hum apne capstone-prep project **Alex** (agentic financial planner ka data backbone) ke chauthe guide par hain. Pre-requisite: guides 1 se 3 complete hone chahiye (jisme S3 vectors, SageMaker embedding endpoint, aur ingest Lambda ban chuke). Aaj ka mission: ek **Researcher service** banana jo ek **App Runner app** ke roop mein deploy hoga.

Iska kaam:
1. **OpenAI Agents SDK** se agents ko **orchestrate** karna
2. **AWS Bedrock** ko LLM provider ke roop mein use karna
3. Ek **Playwright MCP server** se diye gaye topic par internet search karna
4. Research ko ingest karna → vector banana → **S3 vectors** mein store karna (pehle bane ingest service ke through)

### OpenAI Agents SDK + Bedrock — yeh combo kyun?

Thoda confusion natural hai: agar hum **Bedrock** use kar rahe hain (jo AWS ka managed LLM service hai), toh **OpenAI** kaise beech mein aaya? Samjho:

- **OpenAI Agents SDK** sirf ek **orchestration framework** hai — agents define karo, tools do, MCP servers attach karo, aur ek agent loop chalao. Yeh SDK kisi bhi OpenAI-compatible endpoint se baat kar sakta hai, sirf OpenAI ke apne models tak limited nahi.
- **Bedrock** AWS ka fully-managed service hai jo bahut saare foundation models (Anthropic Claude, Amazon Nova, Meta Llama, ab OpenAI ke open-source models bhi) ek hi API ke peeche serve karta hai. Bedrock **API keys khud handle** karta hai — tumhe har model provider ka alag key manage nahi karna padta.
- Toh architecture: **OpenAI Agents SDK (orchestration)** → **Bedrock (model inference)**. SDK ka agentic power (tool calling, MCP support, tracing) + Bedrock ki managed, secure model access.

### Bedrock model access request karna

Bedrock par har foundation model use karne se pehle **model access request** karna padta hai (ek baar ka approval). Aaj do models ke liye:

#### 1. OpenAI OSS 120B (naya, exciting model)

Yeh OpenAI ka **open-source** model hai (`gpt-oss-120b`). Do "catches" Ed batata hai:

- **Catch 1 — Region:** Yeh model abhi sirf **US West 2 (Oregon)** region mein available hai. Toh access US West 2 mein hi request karna padega.
- **Catch 2 — Bug:** Kuch din pehle Bedrock mein ek bug aa gaya jo OSS 120B par **tool calling** ko block kar deta hai (agentic kaam ke liye tool calling critical hai). Ed bolta hai shayad jab tum yeh karoge toh fix ho chuka hoga. Iss liye fallback ke roop mein **Amazon Nova** use karenge jo abhi kaam kar raha hai. Code dono ke beech switch karne ki facility dega.

Steps (root user ke roop mein AWS console):
1. AWS Console → as **root** sign in
2. (Optional but recommended) **Billing and Cost Management** check karo — budget expectation ke hisaab se hai ya nahi
3. **Amazon Bedrock** kholo
4. Top-right region ko **US East (N. Virginia)** se badal kar **US West 2 (Oregon)** karo — yahan sabse zyada models available hain
5. Left sidebar (bottom) → **Model access** → **Modify model access**
6. Scroll karke **OpenAI gpt-oss-120b** dhundo (aur **gpt-oss-20b** bhi tick kar lo — chhota variant)
7. Dono boxes tick → bottom-right **Next** → request
8. Ed ke experience mein OSS model **almost instantly** approve ho gaya

#### 2. Amazon Nova (reliable fallback)

Nova models (Pro, Lite, Micro) Amazon ke apne foundation models hain. Inka access tumne pehle hi request kar liya hoga (Twin weeks mein), par double-check:

1. Apne primary region (Ed ke liye **US East 1**) mein raho
2. Bedrock → **Model access** → **Modify model access**
3. **Amazon Nova Pro, Lite, Micro** — teeno checked hone chahiye (agar already "Access granted" hai toh skip)
4. **Next** → request — yeh definitely instant approve hota hai

> **Important note:** Yeh OSS/Nova models **free open-source** hain aur Bedrock key handle karta hai — yeh OpenAI ke paid GPT models jaisa nahi. Cross-region kaam karta hai: App Runner service kisi bhi region mein ho sakta hai (Ed ka US East 1), aur wo **US West 2 par Bedrock ko call** kar sakta hai — koi problem nahi.

### `.env` file mein OpenAI API key add karna

Ek aur confusing step: hum Bedrock se ja rahe hain, phir OpenAI API key kyun chahiye?

**Reason — Tracing.** OpenAI Agents SDK out-of-the-box **tracing/observability** deta hai (platform.openai.com par traces dikhte hain). Traces dekhne ke liye SDK ko ek valid OpenAI API key chahiye — sirf **authentication/login** ke liye, inference ke liye nahi. **Koi paisa kharch nahi hota** (zero balance par bhi chalega); key sirf traces ko platform se link karti hai.

`.env` file mein (jisme part 3 se already API endpoint + API key hai) apni OpenAI key add karo:

```bash
# .env (already present from part 3)
API_ENDPOINT=https://...your-ingest-api-gateway-url...
API_KEY=your-ingest-api-gateway-key

# ADD THIS — sirf tracing ke liye
OPENAI_API_KEY=sk-...your-real-openai-key...
```

`src...` placeholder ko apni asli OpenAI key se replace karo (kisi aur env file se utha lo).

### Terraform infrastructure setup

Researcher ki infra Terraform se banegi. Terminal kholo aur Terraform-for-researcher directory mein jao:

```bash
cd terraform/4   # researcher ke liye 4th terraform module
```

Iss directory mein ek **`terraform.tfvars.example`** file hai. Use copy karke apni asli tfvars banao:

```bash
cp terraform.tfvars.example terraform.tfvars
```

`terraform.tfvars` mein yeh **5 fields** set karo:

```hcl
# terraform.tfvars
aws_region    = "us-east-1"        # tumhara default AWS region (NOT bedrock OSS region)
openai_api_key = "sk-..."          # wahi key jo .env mein daali
api_endpoint  = "https://...ingest-api-gateway-url..."   # .env se
api_key       = "your-ingest-api-gateway-key"            # .env se

scheduler_enabled = false          # abhi OFF rakho — end mein ON karenge
```

Field-by-field:
- **`aws_region`** → tumhara default deployment region. Yeh Bedrock OSS wala region NAHI hai — wo region code mein alag se specify hoga.
- **`openai_api_key`** → tracing key (`.env` wali).
- **`api_endpoint`** + **`api_key`** → ingest service ke API Gateway endpoint + key, exactly Terraform string format mein (quotes ke saath).
- **`scheduler_enabled = false`** → yeh ek **EventBridge scheduler** banata hai jo har 2 ghante mein research kick karta hai. Abhi OFF; lecture 87 mein ON karke pura pipeline live dekhenge.

Sab set karne ke baad agle lecture mein `terraform init` se shuruaat hogi.

---

## 📋 Key Concepts

| Concept | Matlab |
|---|---|
| **Researcher service** | App Runner app jo agent chalata hai, web research karta hai, aur results ingest karta hai |
| **OpenAI Agents SDK** | Orchestration framework — agents, tools, MCP, tracing; OpenAI-compatible kisi bhi endpoint se kaam karta hai |
| **AWS Bedrock** | Managed multi-model LLM service; keys khud handle karta hai, cross-region callable |
| **OSS 120B** | OpenAI ka open-source model on Bedrock — sirf US West 2, tool-calling bug ka risk |
| **Amazon Nova** | Amazon ke apne models (Pro/Lite/Micro) — reliable fallback |
| **Playwright MCP** | MCP server jo headless browser se internet browse/research karne ke tools deta hai |
| **OpenAI API key (tracing)** | Sirf traces dekhne ke liye; inference nahi, paisa nahi |
| **`terraform.tfvars`** | Region + keys + endpoints + scheduler flag — `.example` se copy karke banao |
| **`scheduler_enabled`** | EventBridge cron flag; abhi `false`, end mein `true` |

---

## 💼 Backend Dev Ke Liye Note

Yeh setup ek classic **provider-abstraction + secrets-management** pattern hai jo backend dev rozana dekhta hai. OpenAI Agents SDK ko ek **HTTP client wrapper** ki tarah socho jo OpenAI-compatible interface expose karta hai — Bedrock ko ek alag base URL ke peeche plug karna ditto wahi cheez hai jaise tum apne service mein swappable database driver ya payment gateway rakhte ho. **Tracing key vs inference key** ka distinction important hai: ek hi vendor ke do alag credentials, do alag purposes (auth/telemetry vs actual model calls) — exactly jaise tum APM (Datadog/New Relic) ka key alag rakhte ho aur DB password alag. Aur `terraform.tfvars` = tumhara environment config file (12-factor app ki tarah), jisme secrets aur region-specific config code se bahar rehte hain. `scheduler_enabled` ek **feature flag** hai — cost-bearing background job ko default OFF rakhna production safety ki best practice hai.

---

## ✅ Takeaway

- **Researcher service** = App Runner + OpenAI Agents SDK (orchestration) + Bedrock (inference) + Playwright MCP (web research) → S3 vectors
- Bedrock par **OSS 120B** (US West 2, tool-calling bug risk) aur **Nova** (reliable fallback) ka access request karo; cross-region calling allowed hai
- `.env` aur `terraform.tfvars` dono mein **OpenAI API key** chahiye — sirf **tracing** ke liye, koi paisa nahi lagta
- `terraform.tfvars` ke 5 fields: `aws_region`, `openai_api_key`, `api_endpoint`, `api_key`, `scheduler_enabled = false`
- Pre-req: guides 1–3 done hone chahiye; scheduler abhi OFF — end mein turn on karenge

---

<details>
<summary>📜 Full Transcript (English)</summary>

And we're back in cursor and we're back in Project Alex. And we're going into the guides folder, and we're going to the fourth guide to get this show on the road. So before starting make sure we've done guides 1 to 3. We certainly have. And what we're doing today is we're going to be building the Researcher service, an app runner app that is going to use OpenAI agents SDK to orchestrate agents. It's going to use AWS bedrock, and we're going to be using an MCP server, a playwright MCP server to search the internet for a given topic. And we will then ingest that topic. We will convert it to a vector, store it in S3 vectors using our ingest service. Uh, that is what I have in store for you. But first we have to request access to the right bedrock models. Remember when we did this before? We're going to do it again to get some new models. And here's the thing. So the model that we're going to use is going to be exciting. It's going to be the new ish open source model from OpenAI called OSS 120, but there's a few catches with this. One of them is that that model, at least as of today, is only available on US West two, a particular region. So we're going to have to set it up in that region to have access to it. But there is a second catch, which is a slightly more tiresome one, which is that I had this whole thing working two weeks ago beautifully. But just in the last few days, there's been a bug introduced in bedrock. That means that it won't work with this model. Uh, it doesn't allow tool calling on the OSS 120 model, which is very tiresome. Now, I'm rather hoping that by the time you take this, that will have been fixed and the code will show OSS 120 B, so I'm still going to show you how to set it up. But for now, for when I show it to you, I'm going to be using the Nova model because that one is working. And I'll have code which allows us to switch between the two so you can pick whichever one works best. And of course, you've already requested access to Nova in the twin weeks, so you already have that one set up anyway. All right. But for now, we're going to go back to the AWS console. I'm going to go in as root, and we're going to go and request access to the this model OSS 120. And I'll also show you the Nova model as well, which I'll keep in in US East one for me. Uh, but and you should keep that in your region. Let's let's go right now to the AWS console as root. And here I am signed in to the AWS console. And you can check out that I'm in there as root. And since you're in those root this would be another one of those moments to why not go and check out the cost and the billing and cost management to make sure your budget is just as you expect it. But we won't do that again now because I've done that enough. Instead, we will go to bedrock. Let's go straight to bedrock. Here it is Amazon bedrock. And the first thing I want to show you, you can see up there it's already showing the region is us East. Let's change the region to be US West two, which is where the largest number of models are available. I do believe here they are. So this is showing all of the models. It's even mentioning to us that that, uh, GPT OS one, TB and TB are available in Amazon bedrock. It's not mentioning that there are these problems with it right now. Uh, but, uh, there we go. Hopefully they'll they'll have gone, as I say. So put this to to Oregon to us West two, come down here to model access on the bottom left. Click here. And then you press Modify Model Access. And these checkboxes appear here. And this is where you can scroll down and find somewhere down here OpenAI OS 120 b. And you might as well request access to 20 B as well. Request access by ticking both of those boxes, and then you would press the button on the bottom right I believe there it is next. And then you would you would request that. And in my experience, the OS model was was approved almost instantly. And at the same time, just in case you skipped this before, go to your region, which for me is US East one and make sure you press Modify Model Access. Find the Amazon models. Here they are. Nova Pro, light and Micro. Make sure these three are checked unless it already says Access granted. Then check those boxes. Go back down to the bottom and next and request that access. And that should definitely be instant. And at the end of that you will now have access to Amazon's Nova models in US East one. Hopefully you don't need them. And also the OSS one, A-20b and A-20b open source models available in US West two. And when you have that access, I will give you a second to do that and then we will reconvene. All right. So hopefully now the proud owner of Approved Model Access don't let the power go to your head. So some quick notes about this. Uh, the OSS models only available at least as of now in US West two. Your app runner service can be in any region. Mine will be in US East one and it will connect across US West two. That is not a problem. And if you're using the the Nova models in the same region, that's great too. Uh, this is not the same as as as like GPT models. These are these are free open source and bedrock handles the key. Okay. Next up we're going to make a quick change to the dot env file. The dot env file already has the API endpoint and the API key that we set back. In part three we're going to add in the OpenAI API key your own OpenAI API key uh, which which you should take from another env file that you have somewhere and put it in here. Replace the src dot dot dot with your true OpenAI API key. And you might be wondering why on earth do we need to do that? We're going through bedrock. Bedrock already handles this sort of key stuff. Well. The reason is because we're still going to be we're going to be using the OpenAI agents SDK in order to connect to bedrock, because we want to use that agent power. Uh, and OpenAI agents SDK comes with that tracing functionality, you remember out of the box. But to be able to see those traces in the platform, you do have to have a key set. I don't believe you need to spend any money at all, you can have zero balance. But in order to be able to log in and see your traces, you need to have your OpenAI API key set. And so that's the only reason we're doing it. No, no money will be spent. It's only there to allow us to trace. So with that we are ready to start building our Terraform infrastructure. Okay. And the first step is let's open a terminal window. We're going to navigate to the Terraform for researcher directory. So Terraform for researcher okay. And now in this directory there's going to be this Terraform.tf example I can show you this here too. Let's go into the Terraform directory into four. And you'll see that there is this Terraform.tf example. And I also already have this file that you will not yet have. And when you run this copy command, it's going to copy the example file into your TF vars okay. And into this file you are going to set these five fields here. So first of all you're going to set your AWS region. This is not yet your bedrock the one you're using for OSS. We will come back to that. We're going to code that somewhere specifically. This is just your default AWS region that you use. Next up your OpenAI API key. You just put that in your env file. You need to put it here as well. Next up your API endpoint and your API key. Take them from the env file and put them in here in this format. In this Terraform format with quotes with with exactly as it is here. And then finally the last one here. Leave it as it already is in the file scheduler enabled equals false. This is where we're going to to build infrastructure to wake up every two hours and kick this process off. But we're going to start with it off, and we're going to turn it on at the end and see it in all its glory. All right. So go ahead and do all of that and I will do it with mine. And I'll see you in a second.

</details>
