# L76 — SageMaker vs Bedrock: Deploying Custom AI Models in Production

> **Week 3 · Day 3** · ⏱️ ~8 min

---

## 🎯 TL;DR

Yeh lecture conceptual hai — **SageMaker vs Bedrock** ka clean side-by-side: Bedrock = frontier models ka managed API router (Claude/Nova), SageMaker = data scientist ka full MLOps platform jahan tum apne ya open-source models build/train/tune/deploy karte ho. Saath mein **MLOps** aur **model drift** ka matlab, aur Alex ke data-ingest plan ka teaser (text → vector → S3 Vectors).

---

## 🗣️ Hinglish Explanation

### Amazon SageMaker kya hai

**SageMaker** AWS ki core AI service hai jo **end-to-end machine learning lifecycle** sambhalti hai — model **build → train → deploy → production rollout** tak. Do main capabilities:

1. **Training side** — fine-tuning jobs chalana, experiments track karna, models train karna.
2. **Hosting/inference side** — trained ya pre-built models ko **scalable, production-grade endpoints** par deploy karna.

Is course mein hum **training side ko touch nahi karenge** — hum SageMaker ko sirf **inference mode** mein use karenge taaki ek **open-source model** deploy kar saken. Lekin agar tumne Ed ka companion **LLM Engineering** course kiya hai (jahan fine-tuning sikhaya jata hai), toh wahan trained models yahan deploy kar sakte ho — courses ek dusre se nicely connect karte hain.

Background context (transcript se aage): SageMaker ek **managed ML platform** hai — matlab AWS underlying compute (GPU/CPU instances), scaling, aur infrastructure ka jhanjhat sambhalta hai, tum sirf model aur config dete ho. Yeh AWS ka **flagship data-science offering** hai, sirf ek API endpoint nahi.

### MLOps — yeh term ka matlab

**MLOps = DevOps for Machine Learning.** Jaise DevOps software delivery ko repeatable/automated banata hai, MLOps **ML model lifecycle** ko repeatable aur bulletproof banata hai. Ismein aata hai:

- **Experiment tracking** — kaunsi training run, kaunse hyperparameters, kaunsa result — sab record.
- **Versioning** — data versions + model versions + training configs, taaki kabhi bhi purane "cut" / experiment par wapas ja sako.
- **Automated retraining** — naye data par models ko dobara train karna.
- **Production monitoring** — deployed models real-world mein kaisa perform kar rahe hain, track karna.

⚠️ Ed bolta hai **MLOps ek ambiguous term hai**, do tarah use hota hai:
- **Umbrella meaning** — kuch log poore is course ko (Vercel/AWS/GCP/Azure par AI deploy karna) MLOps bolte hain, kyunki yeh sab **platform engineering for AI** hai.
- **Specific meaning (zyada common)** — sirf **model deployment lifecycle** manage karna: data/model versioning, experiment tracking, production monitoring, retraining. Is sense mein SageMaker hi **AWS ka MLOps suite** hai.

### Model drift — yeh kyun important hai

**Model drift** = waqt ke saath model ki performance **degrade** hone ka phenomenon, kyunki duniya badalti rehti hai par model purane data par train hua tha. Ed ka classic example: **Covid se pehle** train hue models ke vocabulary mein "Covid" jaisa important word nahi tha — pandemic ke baad un models ki performance giri kyunki wo naye reality ko samajh nahi paaye. Fine-tuning with latest data is gap ko bhar deta hai.

MLOps ka kaam: **drift detect karo → performance drop dekho → retrain karke correct karo.** SageMaker is poore cycle ko support karta hai (experiment tracking, model registry, endpoint monitoring, retraining automation).

### Bedrock vs SageMaker — side-by-side

Yeh lecture ka core hai. Dono AI services hain par bilkul alag use-cases:

| Pehlu | **Bedrock** | **SageMaker** |
|---|---|---|
| **Objective** | Foundation/frontier models ko **API ke through** use karna | Apne / open-source models **build, train, tune, deploy** karna |
| **Models** | Pre-trained frontier models — Anthropic ka **Claude**, AWS ka **Nova range**; limited curated selection | **Koi bhi Hugging Face model**, ya apna custom-trained model |
| **Level** | High-level, "router for frontier models" | Low-level, detailed, hands-on |
| **Work involved** | Super simple — bas config, aur endpoint use karo | Zyada involved — model + infra khud setup karte ho |
| **Deployment approach** | **Managed endpoints** jo ready milte hain (W2 mein digital twin ke liye use kiya) | **Apne customized endpoints** jo tum khud build karte ho |
| **Kab use karein** | Frontier models se build kar rahe ho, scaled inference chahiye | Custom/open-source model deploy/train/scale karna ho, tight control chahiye |

Ed ka **killer analogy**:
> **Bedrock** = OpenAI ka Python client library use karna jaisa — bas call karo, ho gaya.
> **SageMaker** = Hugging Face code use karna jaisa — bonnet (hood) uthaake engine ko khud dekhna, configure karna, deploy karna.

Aur ek important observation: W2 mein jab humne SageMaker endpoints list kiye the, toh **empty square brackets `[]`** mile the — koi endpoint nahi tha. Is week hum **apna pehla endpoint** banayenge jo scalable hoga aur jiska hamare paas tight control hoga.

### Alex ka data-ingest plan (teaser)

Ab capstone project **Alex** (agentic financial planner SaaS) ki taraf. Ed clarify karta hai timeline:

- **Next week (W4)** — Alex ka **agentic platform** build hoga aur AWS par deploy hoga.
- **Is week (W3)** — Alex ka **data side**: SageMaker + thoda data engineering.

Vision: Alex ko ek aisa platform banana hai jo **constantly seekhta rahe** — financial markets, retirement planning, financial planning ke latest developments. Iske liye **data pipelines** chahiye jo Alex ko continuously naya info de saken aur use **vector data store** mein save kar saken.

**Aaj ka step** (data engineers ke liye treat): text lo → use ek model se **vector** mein convert karo → us vector ko **S3 Vectors** mein store karo (yeh AWS ka special storage hai vectors ke liye — agle lectures mein detail). Iske liye **open-source embedding model** ko **SageMaker endpoint** par deploy karenge.

```
[ Text ]  →  [ SageMaker endpoint (open-source embedding model) ]  →  [ Vector ]  →  [ S3 Vectors ]
```

### Standard background (transcript se aage)

- **Embedding / vector** — text ko numbers ke ek fixed-length array (vector) mein convert karna jahan **meaning** capture hoti hai. Similar meaning wale text ke vectors aaspaas hote hain. Yeh **RAG** (Retrieval-Augmented Generation) ki neenv hai — relevant info dhoondhne ke liye.
- **Endpoint** — ek live, network-accessible URL/service jise tum call karke model se inference le sakte ho.
- **Open-source model** — Hugging Face jaise hubs par freely available models (weights download kar sakte ho), proprietary frontier models ke ulta.

---

## 📋 Key Concepts

| Concept | Matlab |
|---|---|
| **SageMaker** | AWS ka end-to-end ML platform — build/train/tune/deploy + MLOps suite |
| **Bedrock** | Frontier models (Claude, Nova) ka managed API — config karo aur use karo |
| **Inference mode** | Trained model ko sirf prediction/output ke liye chalana (training nahi) |
| **MLOps** | DevOps for ML — versioning, experiment tracking, monitoring, retraining |
| **Model drift** | Waqt ke saath model performance girna (duniya badli, model purana) |
| **Model registry** | Models ke versions store/track karne ka central place |
| **Endpoint** | Live network service jise call karke model se inference milta hai |
| **Embedding/Vector** | Text ka numeric representation jo meaning capture karta hai (RAG ka base) |
| **S3 Vectors** | AWS ka naya vector storage — bucket jaisa, par vectors ke liye |

---

## 💼 Backend Dev Ke Liye Note

Backend engineer ke liye yeh **build vs buy** wali classic architecture decision hai. **Bedrock** ek **managed SaaS API** ki tarah hai (jaise tum Stripe ya Twilio call karte ho — kuch operate nahi karna, bas integrate). **SageMaker** ek **self-managed / PaaS** approach hai (jaise tum apna service ek container par deploy karke uska compute, scaling, monitoring sambhalte ho). Decision rule wahi hai jo backend mein hota hai: standard need + low ops appetite → managed (Bedrock); custom requirement + control chahiye → self-host (SageMaker). **MLOps** ko apne **CI/CD + observability stack ka ML version** samjho — model registry ≈ artifact registry, model drift monitoring ≈ production metrics/alerting, retraining ≈ scheduled jobs. Embedding endpoint ko ek **stateless microservice** ki tarah treat karo: input text, output vector, scale-on-demand.

---

## ✅ Takeaway

- **Bedrock = frontier-model API router (managed)**; **SageMaker = build/train/deploy your own or open-source models (hands-on)** — yeh course ka most important distinction hai
- Analogy lock karo: Bedrock ≈ OpenAI client library; SageMaker ≈ Hugging Face under-the-hood code
- **MLOps = DevOps for ML** (versioning, experiment tracking, monitoring, retraining); ambiguous term hai — umbrella ya model-lifecycle-specific dono sense mein use hota hai
- **Model drift** real problem hai (Covid example) — monitor karo aur retrain karo
- Is week ka focus: Alex ka **data ingest** — text → SageMaker embedding endpoint → vector → S3 Vectors

---

<details>
<summary>📜 Full Transcript (English)</summary>

So Amazon SageMaker is one of AWS core services for AI projects. And in particular, it's for end to end machine learning model deployment from building to training to implementing and rolling out models into production. And it's there both, as I say, for the training side and for the hosting side. It's both running the sort of fine tuning jobs and then deploying them in a way that is scalable production grade. Uh, and we're not going to be covering training directly on this course. We're going to be using this for deploying open source models in inference mode. But if you've taken my companion LLM engineering course so that you are familiar with fine tuning models, then for sure you could experiment with that side of it too and actually deploy a fine tuned model. It should the the courses should connect nicely there. And it's very much SageMaker is designed for MLOps. MLOps, which we'll talk more about in just a minute, is is about the whole sort of process of being a DevOps person from a machine learning point of view. So it's all about things like tracking different experiments, versioning your data and your models, automated retraining of models and monitoring models in production, making sure that the full ML process is repeatable and bulletproof. That's what SageMaker is all about. So you're probably thinking right about now, okay, but what's what's bedrock then? But wasn't bedrock all about deploying models? What's the difference between bedrock and SageMaker? Well, let me let me clarify. So bedrock versus SageMaker give you the the side by side comparison. So the objective of bedrock is to allow you to take foundation models, frontier models, models like Claude's Anthropic or the Nova range from AWS and be able to use them through an API. It's like a sort of, uh, router for frontier models that will be billed to your AWS account with a well-known, scalable API. SageMaker is much more low level. Detailed. SageMaker is about building and training, tuning and deploying your own ML models or open source models. So what are these models? Again, in Bedrock's case, these are pre-trained models from Amazon itself and from partners like anthropic. Limited selection of major model providers SageMaker is really it's very it's very much like hugging face. And it lets you use any hugging face model. But it's about either building your own model or training your own model, or using a prebuilt model like a like a hugging face model. Open source model and using that in your ML pipelines. And in terms of what the work involved, typically bedrock is super simple. It's just a sort of configuration thing and you're off. You're using an endpoint for for Claude or whatever. Uh, as we discovered in week two, SageMaker, it's definitely it's more involved. We're not going to go that deep with it. We're going to use it to run an open source model. but I'm going to give you a good feel for how much there is to learn about SageMaker. Should you wish. And in terms of the deployment approach with bedrock, you just simply get access to managed endpoints that you just use, as we did in week two with SageMaker. You create your own customized endpoints. We just listed them a second ago, and there were none of them empty square brackets. But we will have an endpoint that we will build ourselves and it will be scalable and something that we have very tight control over. And so so when do you typically use it. So you use bedrock if you are building using frontier models and for, for scaled inference, just as we did with the twin. But SageMaker is is much more about having your own model that you are. It's a custom model or an open source model that you want to deploy, potentially train and scale. It is a more of a of a hands on experience working directly with the models. So hopefully that gives you some kind of feel for for the pretty different use cases between the two. Are you? Maybe this is oversimplifying, but maybe you could think of bedrock as using, like the OpenAI Python client library. And SageMaker is more like using hugging face code when you're lifting up the bonnet and looking at it under the hood, at the actual engine itself and being able to configure it and deploy it. That's what we'll be doing with SageMaker. As I say, we'll be barely scratching the surface. It is a wonderful rabbit hole to explore more should you wish. And now I use the term MLOps before. And let me let me just quickly drill down, peel back the onion a bit on that term. MLOps. So first off, I should say that it is one of these ambiguous terms that's used in different contexts. Sometimes people would refer to this entire course, everything we're doing on this course as being MLOps, because it's all about sort of operationalizing agentic AI and generative AI, deploying to AWS, deploying to GCP and Azure and Vercel. These are all practices related to platform engineering for AI projects. So in a way, sometimes people do use it as an umbrella term to refer to everything that we're doing, but it's probably more common for it to be used specifically in the context of managing model deployments themselves. It's like DevOps for machine learning, managing the lifecycle of a model. So it's about things like tracking the versions of data, the different model versions, the different configurations that you've used for your training so that you can you can always go back if you need to, to a different, different cut to a different experiment. It's about monitoring how your models perform in production. And there's something known as model drift, which is the effect that over time, as as the world changes, as something happens, like like, say, Covid happened a few years ago, models that were trained prior to Covid didn't have like Covid as as an important word in the vocabulary. And so of course, that's an example of something which which fine tuning afterwards with the latest data will make a big difference. And the model's performance will sort of degrade after Covid if it wasn't already aware of the pandemic. Uh, so that's an example of of model drift happening. As models age and detecting that, seeing your performance drop and correcting for it is a is an important DevOps MLOps activity. And SageMaker itself very much is is the platform for MLOps. It lets you track experiments. It has a model registry which is where you can version your different models. It has endpoints with with different monitoring for endpoints and automations for retraining. So so that is the SageMaker is like the MLOps suite. And with that introduction we're going to go back to our lab and start working in earnest on Alex. And now I should say that next week is going to be when we actually build out the Agentic platform behind Alex and deploy it to AWS. What we'll be doing this week is the data side of Alex. So this is a time when I'm going to cover both SageMaker and also data engineering a little bit. So the data engineers amongst you are going to enjoy this. We're going to be talking about data ingest. We want Alex to be a platform that is constantly learning about the latest developments in financial markets, in the field of retirement planning and financial planning generally. And we want it to be always, always learning. And so we want to build data pipes so that Alex is always able to to to get new information and be able to store it in a vector data store so that those are the building blocks we're going to be creating this week. And we're going to start today with just being able to to call a model to take some text, some information and turn it into a vector and store that vector in something called S3 vectors, which is a place to store this kind of information. So, so the first step we have, the SageMaker part of the puzzle is going to be all about turning text into vectors, using an open source model that we all have deployed to a SageMaker endpoint. With that, let's go and do it.

</details>
