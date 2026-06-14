# L46 — Setting Up Amazon Bedrock for Production LLM Deployment on AWS

> **Week 2 · Day 3** · ⏱️ ~10 min

---

## 🎯 TL;DR

Week 2 Day 3 — "purple day" (AI time). **Amazon Bedrock** introduce hota hai: AWS ka managed LLM gateway jisse Nova/Claude/open-source models ko bina apni API keys manage kiye call kar sakte ho. Lab mein **IAM permissions** (Bedrock + CloudWatch full access) attach karke specific **model access** request karte hain (Amazon **Nova** models — micro/lite/pro).

---

## 🗣️ Hinglish Explanation

### Recap: Day 2 ka monster deployment

Kal jo architecture banaya, ek baar phir flow:

```
deploy.py → backend code ko zip mein package
   → Lambda function banaya, zip upload, env vars set (CORS sabse important)
   → S3 bucket "twin-memory-<account-id>" (globally unique naam)
   → Lambda mein S3 memory variable point kiya bucket par
   → API Gateway banaya, Lambda se integrate, /chat POST route set
   → npm run build → static site "out/" → S3 front-end bucket par upload
   → CloudFront distribution → static site worldwide
   → CORS variable update → CloudFront origin allow → sab kaam karne laga
```

Yeh "palaver" tha — Vercel ke comparison mein bahut zyada steps. Vercel (aur waise PaaS — Platform as a Service) amazing hai. Par app maturity ke ek stage par tum **big AWS deployment** ke liye ready ho jaate ho — yeh **industrial strength** hai. Ab AI add karna hai: Lambda code se OpenAI call karne ki jagah **AWS Bedrock** use karenge.

### Amazon Bedrock kya hai

**Bedrock** AWS ka **managed generative-AI service** hai — ek single API jisse tum multiple foundation models (alag-alag providers ke LLMs) call kar sakte ho. Core idea:

- Mostly yeh **LLM calls ke around ek wrapper** hai — Amazon credentials, billing, scaling, security khud handle karta hai
- Tumhe alag-alag providers ke API keys manage nahi karne padte — sab kuch tumhare **AWS account + IAM** se chalta hai
- Ab Bedrock ek **catch-all suite** ban gaya hai: sirf LLM calls nahi, balki **agent platform** (AgentCore — Week 4 mein), guardrails, knowledge bases bhi

**Bedrock vs SageMaker:** Amazon ke do AI products hain.
- **Bedrock** → ready-made foundation models, simple API se serverless inference (yeh week)
- **SageMaker** → full ML platform — apne custom models train/deploy/fine-tune karo, infrastructure control (Week 3 mein)

### Nova models — Amazon ke apne LLMs

Bedrock se tum **huge range** of models access kar sakte ho (open-source Llama, Mistral; Anthropic Claude; OpenAI ka open-source OSS model). Par hum "all Amazon" rahenge aur **Amazon Nova** use karenge. Teen sizes:

| Model | Positioning |
|---|---|
| **Nova Micro** | Sabse sasta, sabse fast — testing ke liye ideal |
| **Nova Lite** | Mid-tier — balanced |
| **Nova Pro** | Sabse capable (aur sabse mehenga Nova) — par phir bhi **Claude Haiku se thoda sasta** |

Nova Pro bhi pretty cheap hai (Anthropic ke cheapest model se bhi neeche), aur Micro **ridiculously cheap**. Defaults Micro/Lite, par Ed khud Pro use karega "why not".

> ⚠️ **Region note:** OpenAI ka famous **OSS (open-source) model** bhi Bedrock par milta hai, par sirf **US-West-2** mein, **US-East-1** mein nahi. (AWS ki partnership Anthropic ke saath hai; Microsoft ki OpenAI ke saath — isliye AWS par OpenAI ka sirf open-source model milta hai, frontier nahi.) Cross-region span thoda extra kaam hai, isliye filhaal Nova (jo har region mein available hai) use karenge.

### Lab Step 1: IAM permissions (hamesha pehle!)

Ed ka mantra: *"It is IAM permissions time. You always have to begin with permissions."*

**IAM (Identity and Access Management)** AWS ka permission system hai. Default deny — koi bhi service tab tak use nahi hoti jab tak explicitly allow na ho. Hum do nayi policies chahiye:

1. **AmazonBedrockFullAccess** — Bedrock use karne ke liye
2. **CloudWatchFullAccess** — logs/metrics dekhne ke liye (CloudWatch = AWS ka monitoring/logging service)

Steps:
1. AWS console mein **root user** se sign in karo (jaise hamesha permission changes ke liye)
2. **IAM** → **User groups** → **twin-access** (woh group jisme humara IAM user hai)
3. **Permissions** tab → **Add permissions** → **Attach policies**
4. Search box mein `bedrock` → **AmazonBedrockFullAccess** tick karo
5. Search `cloudwatch` → **CloudWatchFullAccess** tick karo
6. **Attach policies** → ab group ke paas dono permissions hain

> 💡 **CloudWatch vs CloudFront confusion:** Ed ne pehle galti se socha tha woh CloudFront laga raha hai, par yeh **CloudWatch** hai — bilkul alag service. CloudFront = CDN (content delivery). CloudWatch = monitoring/logs/metrics.

### Lab Step 2: Model access request karo

Permissions group-level hain, par Bedrock mein **har specific model** ke liye alag se access request karna padta hai. Iske liye **IAM user** (root nahi) ke roop mein login karo:

1. AWS console → sign in (top-right par check karo "engineer" user dikh raha — yaani IAM user, root nahi)
2. Search bar mein `bedrock` → **Amazon Bedrock** kholo (bahut saare AI menus dikhenge)
3. Left menu → **Model access**
4. Yahan saare available models dikhенge — open-source, Claude, **Nova** wale
5. **Modify model access** button dabao → teen **Nova** models (Micro, Lite, Pro) ke checkboxes tick karo
6. Page ke bottom tak scroll → **Next** → **Submit**

Kyunki yeh **Amazon ke apne models** hain, access **normally instantly** grant ho jaata hai (page refresh karne par "Access granted" dikhega). Tumhe coffee lene jaana pad sakta hai par usually turant hota hai.

> ⏳ **Note:** Anthropic ke **Claude** models request karoge to thoda time lagta hai (minutes ke order mein). Hum is week Claude use nahi karenge, par chaaho to request kar sakte ho. Refresh karne ke baad teen Nova models ke saamne **"Access granted"** dikhna chahiye. Congrats!

---

## 📋 Key Concepts

| Concept | Matlab |
|---|---|
| **Amazon Bedrock** | AWS ka managed LLM service — single API se multiple foundation models, AWS billing/IAM se |
| **Nova models** | Amazon ke apne LLMs — Micro (sasta/fast), Lite (mid), Pro (best, phir bhi cheap) |
| **Bedrock vs SageMaker** | Bedrock = ready models serverless inference; SageMaker = custom model train/deploy platform |
| **IAM** | Identity & Access Management — AWS ka permission system (default deny) |
| **User group (twin-access)** | IAM group jisme user hai; group par policies attach karo |
| **AmazonBedrockFullAccess** | Bedrock use karne ki IAM policy |
| **CloudWatch** | AWS ka monitoring/logs/metrics service (CloudFront se alag!) |
| **Model access** | Bedrock mein har specific model ke liye alag se access request karna padta hai |
| **Region availability** | Nova har region; OpenAI OSS sirf US-West-2; alag regions span = extra kaam |

---

## 💼 Backend Dev Ke Liye Note

Backend dev ke liye Bedrock ka biggest win **credential management se mukti** hai. Abhi tak tumne OpenAI/Anthropic ke saath `OPENAI_API_KEY` jaisi secrets manage ki hogi — env vars, secret managers, rotation, leak risk. Bedrock mein woh poora layer gayab ho jaata hai: tumhari Lambda ki **IAM execution role** hi authentication hai (AWS SDK automatically credentials resolve karta hai), koi explicit API key nahi. Yeh "principle of least privilege + no long-lived secrets" pattern enterprise mein gold standard hai. Doosra mental model: Bedrock ek **provider-agnostic LLM gateway** hai — ek hi `boto3` client se Nova, Claude, Llama, Mistral switch kar sakte ho sirf model ID badal ke. Yeh vendor lock-in kam karta hai. **IAM-first workflow** ko internalize karo: AWS mein har "X kaam nahi kar raha" debug aksar permission ka missing piece hota hai — pehle execution role/policy check karo. Aur model access ka two-level system note karo: group-level IAM policy (kya tum Bedrock API call kar sakte ho) **plus** per-model access grant (kya tum is specific model ko invoke kar sakte ho) — dono chahiye.

---

## ✅ Takeaway

- **Bedrock** = AWS ka managed LLM gateway — multiple models, no API-key juggling, AWS IAM/billing se authenticate
- Hum **Amazon Nova** (Micro/Lite/Pro) use karenge — sab cheap; Nova Pro bhi Claude Haiku se sasta
- AWS mein hamesha **IAM permissions pehle**: group `twin-access` par **AmazonBedrockFullAccess** + **CloudWatchFullAccess** attach
- Bedrock mein **per-model access** alag se request karna padta hai — Nova instantly grant, Claude thoda slow
- **Bedrock vs SageMaker** distinction yaad rakho: ready models vs custom-model platform (Week 3)

---

<details>
<summary>📜 Full Transcript (English)</summary>

And welcome back. Welcome to production deployment of Gen AI and AI. Week two day three. And it's a purple day, which means one thing. It means it's AI time. This is about Amazon bedrock today. It's when we get back to talking about what it means to deploy AI applications, and we're going to get almost immediately to the lab. But first, just a quick recap of the deployment architecture that we did last, uh, last session yesterday. Uh, if this didn't cause your mind to to to spin like crazy, we started by deploying a Lambda function. Remember, we wrote a script called deploy.py that packaged up our back end code into a zip file. And then we went into Lambda. We created a lambda function. We uploaded the zip file. I uploaded the wrong one the first time, but we uploaded the right. You uploaded the right zip file. Well done. Uh, and you got that code. You set some environment variables, including the all important cause variable. They had to come back to you later. And that was the lambda function up there. We then set up an S3 bucket. An S3 bucket. We had to call it like twin memory and then your account ID, because these things had to be unique across across everyone. We set that up, and then we went back into the Lambda function and updated the course variable. Sorry, not the course. We then updated the S3 variable, the memory variable so that it would point to that S3 bucket. Uh, and then uh we configured an API gateway. Remember doing that. We set up a gateway. Uh, we get integrated it with that lambda function. And we set up the routes, including the slash chat route, which was the post route to be able so that that, uh, the front end would be able to call into that API. And then we, uh, created a static website. We did that by, by calling npm run build and creating a static website. In out. And we set up an S3 bucket. And then we ran a script to upload that out directory to upload it into our front end static site, and then we tested it then and there and made sure that it worked. And it did. And that was surprising and amazing. Uh, and then we set up a CloudFront distribution. This takes that static site and makes it available to the world in a CloudFront distribution. And then we tested it by by getting a front end. And we made sure that the front end could hit CloudFront the distribution and it would get served up the page. And then we made sure that we updated the Cors variable in lambda so that it knew to expect that that CloudFront distribution page, so that then when we made the API call, it all just worked. Uh, and uh, yeah, it felt like quite a palaver. And you compare that to what it was like building an application in Clark. Uh, and you can be forgiven. Sorry, not Clark in vercel. Uh, and you can be forgiven for saying, uh oh. Maybe. Maybe I should just stick with vercel. Uh, and, uh, I hear you. Vercel is amazing. And similar products like that pass products platform as a service. But there comes a point as you as you get through various stages of maturity with your app, that you're ready for the big AWS deployment. And that's what we've done successfully. This is industrial strength. And then there's a but wait, but wait, we want to add in AI. And that means that rather than just writing lambda code that calls OpenAI, we want to take advantage of AWS bedrock. And that is what we're going to do today. And with that intro, it's time for our lab. So here we are in cursor again. And we're in the twin project that you created just a couple of days ago. Here it is. Uh, and it has a week two folder. And that week two folder we copied across from the production repo. And it has days of the week. And we will start with day three right here. And the introduction will tell you that today is all about bedrock. Uh, bedrock, um, mostly is like a wrapper around calling LMS that Amazon will take care of for you and handle the the credentials and the like. There's a lot more that's being added on to bedrock, including its agent platform. So bedrock is a bit of a catchall for a whole suite of AI product within Amazon. There's there's two there's there's bedrock and there's SageMaker, which we'll look at next week. Um, but uh, yeah, for now we're going to be using the LM parts of bedrock, and we're going to be using Amazon's Nova models. So their own models through bedrock you can access a huge range of models as we'll see. But we might as well stick all Amazon. So we will go with Amazon's Nova and give Nova a whirl. There are three sizes micro Lite and Pro, and even Pro is pretty cheap. Pro at the moment is slightly cheaper than the Claude Haiku bottle, the cheap version of Anthropic's models, and that is the most expensive of Amazon's. And the Nova micro is really, really cheap, uh, as I will show you. So we'll be looking at all of those. But before we do any of that, Of course it is. IAM permissions time are Yourn always have to begin with permissions. So we're going to sign in as the root user as we always do. Uh and we're going to find our user group twin Access and add two permissions Amazon Bedrock Full Access and CloudWatch Full Access access to logs. I teased the fact that we're going to look at that I think a couple of days ago, and we didn't, but we will today. We'll look at the logs and we'll attach those policies. Let's go and do that right now. Here we are. This is AWS console. I'm signed in as my root user up there you can see. And we'll go straight to IAM by clicking in. Recently visited IAM and over to user groups and to Twin Access. And we click on the permissions tab. This is where we can set more permissions for this one. And I've actually already got CloudWatch full access on here. I think before I incorrectly thought that it was a CloudFront one two. But no, this is this is CloudWatch. So I'm going to add permissions attach policies. So now do um if I type bedrock in here Amazon Bedrock full Access I tick that one and you will want to type uh CloudWatch uh to get uh Amazon CloudWatch. Um let's see what which one did we want to have here Amazon CloudWatch. Full access full. It's just CloudWatch full access. And tick that to and then click Attach Policies and back. We come here we should see CloudWatch Full Access I now have CloudWatch Full access and CloudWatch full access to uh along with the Amazon Bedrock Full Access. We have permissions for all of these, which is what we're after. So we now have to request to be given permission to access the specific models in bedrock that we want to be able to use. And to do so we need to go in as our IAM user. So let's do that now. Uh, back to the console. Uh, I'm look at that. Isn't that great? Uh, back to the console. AWS Amazon.com, here we are. And sign into console. And I'm already logged in. You might have to log in, but double check. Look up there. Does it say engineer? It does. Okay. Now type bedrock up here Amazon bedrock. Welcome to our first big AI side of Amazon. Uh lots of stuff to do. Look at all these AI menus. Uh, the specific thing that we want to do is model access down here, click there. Um, and this shows you all the different models that you could access through bedrock. Lots of stuff. Plenty of open source models, uh, and Claude and, and, uh, the that here are the nova ones that we want to access. And there's a bunch of others and you can read all about them by by by clicking on their links. The, um, you may notice so one of the models that is offered through AWS is the famous OS model from open AI, the open source OpenAI model. You can't reach the the OpenAI frontier model through AWS. Uh, they have their Microsoft has its partnership with OpenAI. AWS is partnership is with anthropic. So that's that's the models you get here. But you can use the open source models, but they're not available on on US East one. They're available on US West two. Uh, they're only available on on that right now. Maybe by now they'll be everywhere. And we will use that later. But it's a bit more work to be able to span across these different regions. So we're going to stick now with the Nova models, which I believe are available in all regions. So, um, I have already been given access granted because I already requested it. You may not have done, uh, in which case the first thing you need to do is request access, which you do by pressing this Modify Model access button right here. And when you get these Nova models, you should be able to check those three boxes, which I can't because I've already been given access. And then you scroll all the way down to the bottom and you press next. And then it's presumably going to say, yeah, nothing is made. And you can then submit requests to access those models. And because they are Amazon's models, that request is normally granted instantaneously. For me it was when the page refreshed I had access. I don't know, it might take more time for you. You might need to go and get a coffee. Uh, but I think when you're requesting Claude's models, it takes a bit. But not with. Not with this. If you were interested in trying out some of the, uh, anthropic models to, then you could request access for them, because that will take a bit longer. Um, again, just the order of minutes, but we won't use them this week. Okay. And so once you've done that, uh, you've clicked submit, uh, and you've refreshed the page. Uh, maybe wait a minute or two if you need to. You should see access granted against those three Nova models. And congrats.

</details>
