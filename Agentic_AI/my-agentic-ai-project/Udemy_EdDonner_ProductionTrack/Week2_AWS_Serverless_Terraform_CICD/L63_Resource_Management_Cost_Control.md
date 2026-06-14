# L63 — Resource Management and Cost Control for Production AI Systems

> **Week 2 · Day 5** · ⏱️ ~13 min

---

## 🎯 TL;DR

Week 2 ka grand finale — CloudWatch se monitoring review, **AWS Resource Explorer** se saare twin resources dekhna, phir **destroy workflow** se dev/test/prod ko cleanly destroy karna, aur **Billing & Cost Management** check karna. Ed honest reveal bhi karta hai (uske bhi reds aaye the), assignment deta hai, aur Week 2 wrap karke Week 3 (Azure/GCP/SageMaker/vectors/MCP) ka teaser deta hai.

---

## 🗣️ Hinglish Explanation

Yeh **Week 2 Day 5 lab ka wrap-up** hai. Itna saara infrastructure bana liya — ab cleanup aur cost-discipline activities. "Putting AI into production" ka ek important hissa yeh bhi hai ki tum apne resources ko track karo aur destroy karo jab zaroorat na ho, warna bill badhta rehta hai.

### Activity 1: CloudWatch se monitoring (IAM user ke roop mein)

Apne **IAM user** ke roop mein log in karke **CloudWatch** dekho:
- Bedrock ke through **Nova** ke invocations (calls)
- **Lambda logs**
- Apne different environments (dev/test/prod) mein kya-kya ho raha hai

> Background: **CloudWatch** AWS ka observability service hai — metrics, logs, alarms. Har Lambda invocation ke logs CloudWatch Log Groups mein jaate hain. Bedrock model calls ki bhi metrics yahan dikhti hain (invocation count, latency, tokens). Yeh tum debug aur monitor karne ke liye use karte ho.

Yeh pehle bhi dikhaya gaya tha — ab tum expert ho jaane chahiye.

### IAM user vs Root user — important distinction

Ed ab **root user** ke roop mein log in karta hai (top-right par naam dikhta hai). Yeh significant hai:

- **Root user** = AWS account ka super-admin (account banane wale email se associate). **Sab kuch** kar sakta hai — billing, account close, etc. Best practice: root ko **rarely** use karo, sirf wo cheezein jo IAM user nahi kar sakta.
- **IAM user** = limited-permission identity jise tum daily kaam ke liye use karte ho.

Kuch cheezein (jaise billing ke certain views) root access maangti hain — isiliye Ed yahan root use kar raha hai.

### Activity 2: AWS Resource Explorer

Ek naya tool — **AWS Resource Explorer** — jo poore account ke **saare resources ka overview** deta hai. Ed "twin" search karta hai:

```
Resource Explorer → search: "twin"
```

Dikhta hai:
- dev/test/prod ke resources
- S3 buckets
- Lambda functions, API Gateways, CloudFront distributions
- "lots of different things" — ~35 resources twin-related

> Background: **Resource Explorer** ek search service hai jo cross-region, cross-service tumhare resources index karta hai. Bina har service console alag-alag khole, ek jagah se sab dikh jaata hai. Cleanup/audit ke liye perfect.

### Activity 3: Destroy environments (destroy workflow se)

35 resources ko console se ek-ek karke delete karna bahut time lega. Better: wahi **destroy GitHub workflow** use karo jo L60 mein banaya tha (jo `destroy.sh` script call karta hai).

GitHub → **Actions** → **Destroy Environment** workflow (abhi tak run nahi hua) → click.

**Dev destroy:**
1. Environment select karo / type karo confirmation (`dev`) — yeh ek safety check hai taaki galti se destroy na ho
2. **Run workflow**
3. Run par click → steps dekho → "running the destroy script"
4. CloudFront par hang (hamesha ka slow part) → "destruction complete" → "environment dev has been destroyed"

**Test destroy:** same — type `test` → Run → success.

**Prod destroy:** type `prod` to confirm → Run → success.

**Three successful destroys** (dev, test, prod). Workflows list mein ab dikhta hai: 3 original deploys + UI refinements push + 3 destroys.

### Verification — sab gone?

Browser mein purane CloudFront URLs hit karo → **"page cannot be displayed"** (dev, test, prod sab) — confirm ho gaya ki environments destroyed.

Phir wapas Resource Explorer (root user) → search "twin" → pehle ~35 the, **ab 13 resources** bache.

### 13 resources kyun bache? Yeh expected hai

Ed explain karta hai — yeh ek-ek karke:

| Bacha hua resource | Kyun bacha |
|---|---|
| **CloudWatch Logs** | Logs hang around karte hain — yeh fine hai, history rakhne ke liye |
| **DynamoDB lock table** | Terraform locks ke liye — one-time setup, kisi environment se tied nahi |
| **IAM role** | GitHub Actions ke liye banaya tha — environment-independent |
| **S3 bucket (Terraform state)** | Remote state backend — environment-independent |
| Dashboard / misc | Ed ke alag setup se (tum ignore kar sakte ho) |

Yeh sab **one-time, not-environment-associated** infra hai jo GitHub Actions ke liye setup kiya tha — isse **delete nahi karna** (warna pipeline tut jaayega). Actual environment resources (Lambda, S3, CloudFront, API Gateway × 3 environments) **poori tarah destroy** ho gaye.

⚠️ **Cost note**: Terraform state ke yeh resources (S3, DynamoDB) **thoda-bahut cost** karte hain agar tum free period mein nahi ho — par bahut hi tiny. Agar twin project se **completely done** ho, toh inhe bhi delete kar sakte ho.

### Activity 4: Billing & Cost Management

AWS console mein **Billing and Cost Management** kholo — yeh **regular habit** honi chahiye:
- Apne **costs** dekho, ek chart jo dikhata hai kis cheez par paisa kharch ho raha hai
- Confirm karo ki **expected** hi hai
- **Cost analysis** se breakdown dekho — kya kitna cost kar raha hai
- Agar koi **unexpected cost** ho → us resource ko dhundh ke delete karo

Yeh **healthy cost/budget management** ka part hai. Ed ke numbers shayad other reasons se badh rahe ho, par tumhare nahi badhne chahiye.

### Honest reveal — six greens ka sach

Ed clean aata hai: usne aisa dikhaya jaise sab **first time perfect** chala (6 green checks), par sach yeh hai — yeh uska **first time nahi** tha is project par. Course prep ke dauraan usne ise kai baar setup/run kiya, aur **plenty of reds** dekhe. Code pehli baar likhte waqt bahut mistakes hui.

Encouragement: agar tum Terraform/GitHub Actions se cursing kar rahe ho (hopefully Ed se nahi 😄), toh **that's par for the course** — yahi normal hai, aur isi struggle mein **real learning** hota hai. Jo log first-try green pe lucky the, unse tumne **deeper expertise** gain ki.

Aur ek aur reveal: "one week" ka curriculum actually use **ek week se zyada** laga properly working banane mein. Har week beefy hai — agar tumhe bhi week se zyada laga, toh surprise nahi.

### Week 2 ka full recap

Ed poore week ka summary deta hai:
1. **Day 1**: Different architectures discuss → digital twin app **with memory** banaya
2. **Day 2-3**: AWS console se deploy → **serverless architecture** (Lambda + S3 + API Gateway + CloudFront)
3. **Day 4**: **Terraform** scripts likhe — 3 mirror environments (dev/test/prod) create + destroy
4. **Domain + DNS**: registered domain name use kiya, DNS config + **SSL certs** setup
5. **Day 5**: **GitHub Actions** se sab automate — `git push` to deploy, environments promote, environments destroy
6. **AI piece**: **Amazon Bedrock** + **Nova foundation models** + conversation history

Ed ka philosophy: "putting AI into production" mein AI involved hai (AI lens se dekha), par **bahut saara kaam core platform engineering** hai. Wo aapko throughout AI lens ke saath le gaya.

### Assignment

Jinhone Ed ka **AI (Agentic) course** liya tha, unhone ek digital twin banaya tha jo **Gradio app** thi (koi production capability nahi), par usme **tools** the — jaise:
- Question na aaye toh **look up / record** karna ki answer nahi pata tha
- **Push notification** bhejna
- Contact details record karna

**Assignment**: ab is production LLM app ko beef up karo (Agentic course liya ho ya nahi):
- Tools add karo (smarter banao)
- Ek **S3 bucket** se questions record karo jinke answer LLM ko nahi pata
- Past answers look up karo
- Contact details record karo
- Us S3 bucket ko **Terraform scripts** mein add karo aur **GitHub Actions** se deploy karo

Goal: production par deployed digital twin ek **fully functional, powerful** twin ho. Repo share karo expertise dikhane ke liye. Troubles ho (especially coding) → Ed ko message karo. Successfully deploy karne par **LinkedIn par post** karo aur Ed ko tag karo — wo try karega, comment karega, community mein amplify karega.

### Week 3 ka teaser

Congratulations — **halfway** through, Week 2 survive kiya. Going forward: **no more clicking around consoles** — sirf Terraform. Week 3 mein:
- **GCP** + **Azure** (multi-cloud)
- **SageMaker** (custom ML models)
- **Vectors** (vector pipelines/RAG)
- **MCP** (Model Context Protocol)

Bahut zyada "AI-ish" week hoga. Core platform engineering tum ab expert ho — ab **more AI** ka time hai. Aur Ed ek **Udemy rating request** karta hai (community build karne mein bada farak padta hai).

---

## 📋 Key Concepts

| Concept | Matlab |
|---|---|
| **CloudWatch** | Observability — Lambda logs, Bedrock/Nova invocations, metrics, alarms |
| **IAM user vs Root user** | IAM = daily limited identity; Root = super-admin, rarely use (billing ke liye) |
| **AWS Resource Explorer** | Account-wide resource search — cross-region/service overview, audit/cleanup ke liye |
| **Destroy workflow** | GitHub Actions manual workflow jo `destroy.sh` chala ke environment cleanly destroy karta hai |
| **One-time vs environment resources** | State bucket/DynamoDB/IAM role bache rehte hain; Lambda/S3/CloudFront/API GW destroy ho jaate hain |
| **Billing & Cost Management** | Costs track karna, unexpected charges dhundhna — regular healthy habit |
| **Serverless architecture (recap)** | Lambda + S3 + API Gateway + CloudFront |
| **Domain + DNS + SSL** | Registered domain, DNS config, SSL certs (prod) |
| **Assignment** | Tools + S3 question-logging + push notifications add karke twin beef up karna |

---

## 💼 Backend Dev Ke Liye Note

Backend dev ke liye yeh lecture **operational discipline** sikhata hai jo production engineering ki rooh hai. Teen cheezein internalize karo: (1) **Cost awareness** — cloud mein har idle resource paisa khaata hai; "destroy when done" aur regular billing review production teams ki standard practice hai (FinOps). (2) **Resource lifecycle** — IaC (Terraform) ke saath environments ephemeral ban jaate hain: spin up, test, tear down. Yeh exactly preview/PR environments ka pattern hai jo mature teams use karti hain. (3) **One-time bootstrap infra vs ephemeral infra** ka distinction critical hai — state backend (S3+DynamoDB) ko galti se destroy karna pipeline tod deta hai; isiliye usse environment resources se alag rakha jaata hai. Aur Ed ka honest "mujhe bhi reds aaye the" — yeh growth mindset DevOps mein zaroori hai; debugging Terraform state drift aur YAML typos real-world skill hai. IAM user/root separation bhi least-privilege ka core principle hai jo tum apne backend systems mein bhi apply karte ho.

---

## ✅ Takeaway

- **CloudWatch** se Lambda logs + Bedrock invocations monitor karo; **Resource Explorer** se account-wide resources audit karo
- **Destroy workflow** se dev/test/prod cleanly destroy — IaC ka beauty: ephemeral environments
- 13 resources bache rehte hain (state bucket, DynamoDB locks, IAM role, logs) — yeh **one-time bootstrap infra hai, delete mat karo**
- **Billing & Cost Management** regularly check karo — unexpected charges dhundh ke delete karo (FinOps habit)
- Honest reality: **reds normal hain**, struggle mein real learning hai; assignment = twin ko tools + S3 logging se beef up karo
- Week 2 done (serverless + Terraform + domain/DNS/SSL + CI/CD + Bedrock/Nova) — Week 3 = Azure/GCP/SageMaker/vectors/MCP

---

<details>
<summary>📜 Full Transcript (English)</summary>

And so there's a few activities for us to do to wrap up, after this amazing week and a huge amount of infrastructure we've built. First of all, you should yourself go in as your IAM user and look at CloudWatch and use that as a way to track things like the calls, the invocations of the of Nova through bedrock and look at the logs, look at the lambda logs, satisfy yourself of everything that's going on across your different environments. We showed how to do that before, so you should now be an expert at that. And so so go do that. And then what I want to share with you is, is another AWS thing which for which we need to go in as the root user. I have logged in here as the root user. Look at the top right. You can see it's my name. We are indeed in as the root. And I'm going to search now for something new, a new one we're going to look at which is going to be the AWS Resource Explorer. Um, this is something we can do to get an overview of all of the different AWS resources that we currently have running. And I'm going to type twin so that we can have a look at all of the different twin related resources. You can see. There's some for tests, there's some for prod, there's some for dev, there's S3 buckets, there's there's all sorts of stuff going on, lots of different things that we have running related to our twin. And with that, the next thing in store for us is to get rid of them. Let's destroy them all. We could go through this console and spend an awfully long time destroying them all. Or we could use that other convenient GitHub workflow that we set up, which just calls our destroy script that we wrote before. Let's do that. So back we are in GitHub GitHub actions. Uh, and we're going to go to this is this is all of our workflows that we're seeing right here. We're going to go to the destroy environment workflow. Here it is. It's not been run yet. We're going to click here. And we're going to start by destroying the dev environment. It's one of these tabs here that's running. Let's look at that. This environment destroy. We have to type the environment name again to destroy it. A little check that we've got in there clicking to run the workflow. Off it goes. In a second, this screen should refresh to show that it's running, and when it does so I'll click in on it so we can watch it anxiously. There it is. Click on it. Here it goes. Click in on it again to see the steps that are going on. It's running the destroy script right now. Look at it. I'm not touching anything. If you think that I'm running this, this is a machinery in in motion. And as usual, it's going to get hung up on CloudFront, which is where it takes time. Look at all that so much stuff happening, destruction complete and that all finished. And it does say environment dev has been destroyed. That's another successful job for us. Okay so back to GitHub actions uh, to destroy. Look at that. Now we're five greens. Uh, can I make this a complete home run? Next up, time to destroy the test Environment. Test. Test. Run. Workflow. And off we go. Destroying test. See you in a second. And you're probably getting bored of this by now. But sure enough, the second one ran successfully. So now we just come on in. We do run workflow. Now it's time for us to kick off the production destruction prod. We type prod again to confirm the destruction, press the workflow button, let it do its thinking and I will see you back in a minute. And there we have it. Production also destroyed three successful destroys run for dev and Test and Prod. And so if we go to all of our workflows here, we have the the three original deploys, the UI refinements push and the three destroys. All looking good. And presumably if we now come over here and try and hit this, we get a page cannot be displayed. We try and hit this page can't be displayed and page cannot be displayed. And you get the message. Page cannot be displayed. We have success. And now if we go back to AWS in as the root user, go into the AWS Resource Explorer and search again for twin. I think it was like 35 or something. Resources. Before there's now 13 resources. There's still some resources. Why why is that you ask? Well, unless you already know why that is. Uh, first of all, there's some logs here and logs may hang around. That seems like a fine thing. And then the other stuff is the DynamoDB with the the Terraform locks and the role that we set up. And the S3 bucket. This is the kind of one time not associated with any environment, but set up for GitHub actions, and we wouldn't want to delete that. So that is all still here along with this thing here is from a different, different setup I did. You can ignore that one. And there's also that dashboard that I set up. Now these Terraform states that these do these do cost something. If you're not on your free, uh period then there is a tiny, tiny charge associated with them. So should you be completely done with the twin project? You can go out and and delete all of these as well. Um, but it is really very, very small. Um, but otherwise you can see for sure we're down to the bare bones. We're down to like the configuration stuff, the actual environments, the, the real Lambda, S3, CloudFront, and API gateways associated with our three environments have all been completely destroyed, and the resources is the right place to do this, to find it out. And just before we leave the AWS console, there's something else that we should do that you should always do every so often, which is come in and look at billing and cost management, billing and cost management. And my numbers are probably ticking up for various other reasons, but yours should not be, uh, you should come into this. You should see your costs. You should see a little chart here of what you're spending money on. And you should be absolutely sure that it's what you expect, that everything is looking good. You can always come in and analyze your costs. You can see what's costing what, if anything, is costing anything. And if you have anything that is costing that you're not expecting, then go in and delete it. And that is part of your healthy cost management, budget management that you should do on a regular basis. Okay. With that, that that really does conclude the lab for today. It was quite a long lab but but wow we got a lot done. Let's go back for the wrap up. Now look, I've got to come clean with you. I hope that you got six green checks right there. And you have had full success first time round, and I made out as if I did, too. But as you probably guessed, that's not entirely accurate. It. Whilst it is true I did have six greens there, I'm not perhaps completely revealing the fact that this is not my first time running this particular project. Uh, but that in preparation for this course, I of course set this up and ran it a couple of times. And believe me, I've had my fair share of reds. Uh, and, uh, I have, I have, but my head against the wall, as you probably have had to to. But I was writing all of that, that code the first time and made plenty of mistakes along the way. So it is. It's something. It's an experience. You get better and better at it. That's where the real learning happens. So if you've been cursing, uh, hopefully not cursing me, but cursing, cursing, Terraform and GitHub actions all, all the last few days, then that's par for the course. That's what it takes. And as a result, you now have deeper expertise than your friends who happen to get lucky and have green. First time you did better than them. Uh, and I should also reveal that while I've talked about this week as if it's a one week, uh, part of the course, uh, it took me way longer than a week to get everything working properly. And so this this is definitely. It feels like this whole course every week is really beefy. And we got so much done. And if it took you a lot longer than a week, then, then I'm not surprised. I think it's a week. If you really did, did very little else for a week. Uh, there's a lot packed in. But anyways, we built a digital twin app with memory in day one. After talking about different architectures, we then deployed it to AWS using the AWS console that involved building a serverless architecture using Lambda. S3 API gateway CloudFront. And we wrote Terraform scripts to create and destroy three different mirror environments where the production environment. We also used a registered domain name and set up the DNS configuration associated with that, including SSL certs. And then we automated everything with GitHub actions so that we can git push to deploy. We can promote between environments and we can destroy environments. That is what we got done this week. Wow. Oh and yes we also were using Amazon Bedrock and we connected with Amazon's Nova Foundation models. There were some AI. There were some AI in this. Uh, so as before to to make the point that putting AI into production has AI involved through an AI lens. But a lot of the work is like core platform engineering stuff. But hopefully I've taken you through this always with that AI lens. like the conversation history as well. And this brings me to the assignment for you. So some of you may have taken my AI course and already built a digital twin that had nothing like the production capability. It was a Gradio app, but what it did have was things like the use of tools to be smarter. So if the person asks a question that it doesn't know, it's able to look it up and record. It's able to look up the record. The fact that it didn't know the answer, it's able to send a push notification. And we also record some some of the details. And my suggestion for you is now is your opportunity to go and beef up this, this, uh, llm this, this application, whether or not you've taken the Agentic course, you should still be able to dig in and get this done, add in some tools, uh, perhaps use an S3 bucket to record questions that the LLM doesn't know the answers to, and to look up what's been answered in the past, and also to record contact details and add that S3 bucket to your Terraform scripts and deploy with GitHub actions. Do everything back to front so that the, the the digital twin that you have deployed to production on your public URL is a fully functional, powerful digital twin. And you can share that repo so that everyone can see your expertise. And if you have any troubles doing that, particularly adding in that extra functionality, then message me. That's what I'm there for, particularly when it comes to coding. That's where I can really help quickly. So do get in touch. And when you successfully do this and you deploy your digital twin, whether or not you've added more functionality, please post about it on LinkedIn, get people excited about it. And if you tag me and say, look at my digital twin, uh, the I will weigh in, I will jump in and I will try it out, of course. Uh, and then I'll weigh in with some comments. And that way it amplifies what you've done around the community and to other people that I'm connected with and generally on LinkedIn helps shine a spotlight on your achievements and your expertise. And with that, congratulations on getting to halfway to Completing and surviving week two. What a week. Uh, Congratulations on that now. My editor would kill me if I didn't just mention the fact that if you have a moment to go in and rate this course on Udemy, it makes an enormous difference. That's how it's one of the main ways Udemy decides whether or not to show this course to other people. And it's it's so big to to build a community around the course and getting people hearing about it is, is the biggest part of the challenge. So racing the course makes a massive difference and I'd be super, super grateful. So, uh, yes, please. Uh, and with that, that does finally bring us to the wrap up for week two. This is where we are. Look at all those filled in boxes. It's been an enormous week. Going forwards. We will only use Terraform. No more clicking around consoles for us next week. I've got GCP, I've got Azure, I've got SageMaker, more AI. We've got some vectors and we've got MCP. There's so much to look forward to. It's a lot more AI ish. Next week you'll be pleased to hear Core Platform Engineering. You're now an expert. It's time for more AI. It's time for week three. I'll see you then.

</details>
