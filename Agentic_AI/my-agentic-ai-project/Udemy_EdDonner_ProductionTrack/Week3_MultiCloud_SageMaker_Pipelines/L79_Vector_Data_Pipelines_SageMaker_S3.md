# L79 — Building Vector Data Pipelines with SageMaker and S3 for AI Memory

> **Week 3 · Day 4** · ⏱️ ~8 min

---

## 🎯 TL;DR

Day 4 ka conceptual setup: Alex ki **data-ingest architecture** poori tarah samajhte hain — ek **scheduler** har 2 ghante mein ek **App Runner researcher agent** (Bedrock + MCP + Playwright) ko jagaata hai, jo internet se info nikal kar ek **`ingest` Lambda** ko deta hai, jo use **SageMaker embedding endpoint** se vector banwaa kar **S3 Vectors** mein store karta hai. Aaj sirf wahi blue piece (ingest Lambda → SageMaker → S3 Vectors) banayenge.

---

## 🗣️ Hinglish Explanation

### Welcome — aur ek Purple/AI Day

Ed promise karta hai yeh **"juicy" course** hai, aur Alex abhi sirf shuru hua hai. Aaj phir **Purple day / AI day**, aur focus hai **data ingest** — kal deploy kiye **embedding model (encoder)** se vectors banana aur unhe **S3 Vectors** (AWS ka naya storage type) mein store karna.

### Quick recaps

- **Alex** = capstone project, ek **SaaS financial planner**. **Next week (W4)** mein asli agentic platform build hoga.
- **Is week (W3)** = sirf **data ingest** — Alex ko uski **memory / mind** dena financial markets aur retirement planning ke baare mein.
- Setup so far: repo clone kiya; Alex ek local project hai jismein **har deployment step ke liye alag Terraform directories** hain, har ek mein **TF vars** config ke liye. Project root mein ek **`.env`** file hai jo poore project ke **overall secrets** rakhti hai.
- **Sirf ek environment** use kar rahe hain (dev/test nahi) — simplicity ke liye. **No GitHub Actions** is project mein (par tum khud add kar sakte ho — `git push` karke sab roll-out hote dekhna satisfying hai).
- **Kal (Day 3)**: SageMaker ka pehla touch — ek **inference endpoint** banaya **all-MiniLM-L6-v2** sentence-transformers embedding model ke saath, jo text → vector karta hai.
- **Aaj (Day 4)**: **data ingest Lambda function** banayenge jo yeh karega aur result **S3 Vectors** mein store karega.

### Bedrock vs SageMaker (ek baar phir, kyunki repeat se yaad rehta hai)

- **Bedrock** — frontier models (jaise **Nova**, **Claude**) ke saath build karna, scale par inference chalana. Managed API.
- **SageMaker** — **data scientists ka platform**, "DevOps for data scientists". Poora model lifecycle: training, experiments, **versioning models & datasets**, cloud Jupyter notebooks (Colab jaisa), inference endpoints (jo hum use kar rahe hain), aur built-in IDE. Lots to explore.
- **MLOps** — do contexts: (a) umbrella — poora platform-engineering-for-AI; (b) specific (zyada common) — model/data versioning, experiments manage karna. Is sense mein SageMaker = **AWS ka MLOps platform**.
- **Model drift** — models waqt ke saath decay karte hain jaise natural language evolve hoti hai; monitor karo, performance test karo, zaroorat ho toh retrain. SageMaker yeh sab support karta hai.

### Alex ki data-ingest architecture (aaj ka core)

Ed ek **simplified diagram** dikhata hai (zyada complex mermaid diagrams ka saral version). Flow:

```
        ┌──────────────┐
        │  Scheduler   │  (Lambda — har 2 ghante mein jaagti hai)
        └──────┬───────┘
               │ "time hai!" kicks off
               ▼
        ┌──────────────────────────────┐
        │  App Runner: "researcher"     │  (agent ek container mein)
        │   • Bedrock se frontier model │  ← calls Bedrock
        │   • MCP server                │  ← runs Playwright browser
        │   • internet research         │
        └──────┬───────────────────────┘
               │ passes data to ingest
               ▼
        ┌──────────────┐
        │ Lambda: ingest│
        │   1. text →   │ ── calls ──▶  SageMaker embedding endpoint (kal banaya)
        │      vector   │ ◀── vector ──
        │   2. store    │
        └──────┬───────┘
               ▼
        ┌──────────────┐
        │  S3 Vectors  │  (vector + associated text → retrieval ke liye)
        └──────────────┘
```

Step-by-step samjho:

1. **Scheduler** — ek **Lambda function** jo **har 2 ghante** mein "wake up" karti hai aur bolti hai "ab time hai".
2. **App Runner / Researcher** — scheduler ek **App Runner** trigger karta hai jismein **"researcher"** chalta hai — ek **agent ek container mein**. Iske paas:
   - **MCP server** ka access (kyunki Ed alag-alag cheezein try karna chahta hai).
   - Ek **Playwright browser** jo MCP ke through chalta hai — actual research karne ke liye (web pages browse/scrape).
   - **Bedrock** as its model — researcher ek **frontier model** call karta hai (Bedrock ke through), jo phir MCP server ko call karta hai.
   - Ed note karta hai: MCP-server-using researcher ek **interesting way** hai data generate karne ka. Par **tumhare business projects** mein yeh kuch aur ho sakta hai — incoming feeds monitor karna, news releases dekhna, company documents save hote dekhna — koi bhi **event** jo naya data laye.
3. **Ingest Lambda** — researcher jo data nikalta hai (internet search, info found) wo **`ingest`** naam ki Lambda function ko pass hota hai. `ingest` ka kaam: data lo aur **memory mein store** karo.
4. **Text → Vector (SageMaker)** — LLMs ko memory **vector data stores** ke roop mein pasand hai (taaki RAG se relevant info fast retrieve ho). Toh ingest Lambda **kal wale SageMaker inference endpoint** ko call karta hai — open-source sentence-transformers model — text ko vector mein convert karne ke liye.
5. **Store in S3 Vectors** — phir us vector ko **S3 Vectors** mein store karta hai. Ed describe karta hai: yeh **S3 jaisa hai — ek bucket — par vectors store karne ke liye banaya gaya**. Yeh AWS ka **relatively new offering** hai aur **bahut cost-efficient**.

### S3 Vectors vs OpenSearch — cost lesson

Ed apna real experience share karta hai: pehle usne **OpenSearch** use kiya tha (alternative vector store), par wo **kaafi mehnga** nikla — Cost Explorer mein usne **~$50** (plus domain name cost) sirf prior implementation experiment karne mein kharch kar diye, tab samjha ki yeh **cost-efficient nahi** hai is purpose ke liye.

**S3 Vectors** is use-case ke liye **perfect** hai — sasta aur fit-for-purpose. Isliye ingest Lambda **S3 Vectors** use karega vector + associated text store karne ke liye, taaki baad mein **retrieve** ho sake.

> **Background — RAG aur vector store kyun:** LLM ki "memory" usually weights mein frozen hoti hai. Naya/private knowledge dene ke liye hum text ko embed karte hain (vector banate hain) aur store karte hain. Query time par query ko bhi embed karke **nearest vectors** dhoondhte hain (semantic search), un text chunks ko prompt mein daalte hain — yahi **RAG (Retrieval-Augmented Generation)** hai. Isliye vector + uska original text dono store karna zaroori hai.

### Aaj kya banayenge

Pure architecture mein se aaj **sirf ek part**: **ingest Lambda function** jo SageMaker endpoint call kare aur vectors store kare. Diagram mein:
- **Purple piece** (SageMaker endpoint) — **already bana** (Day 3).
- **Blue bits** (ingest Lambda + S3 Vectors wiring) — **aaj aur kal** banayenge.

Scheduler + App Runner researcher (Bedrock + MCP + Playwright) baad mein aate hain. Aaj **simple** — bas ingest path.

---

## 📋 Key Concepts

| Concept | Matlab |
|---|---|
| **Data ingest** | Naya data lena, vector banana, memory (vector store) mein daalna |
| **Scheduler (Lambda)** | Har 2 ghante jaagti hai aur ingest workflow trigger karti hai |
| **App Runner researcher** | Container mein agent — Bedrock + MCP + Playwright se research |
| **MCP server** | Tools/capabilities (jaise Playwright browser) agent ko dene ka protocol |
| **Ingest Lambda** | Data leta hai → SageMaker se vector banwata hai → S3 Vectors mein store |
| **SageMaker endpoint** | text → vector (kal deploy kiya, all-MiniLM-L6-v2) |
| **S3 Vectors** | AWS ka naya, cost-efficient vector storage (bucket-jaisa, vectors ke liye) |
| **OpenSearch** | Alternative vector store — Ed ke liye mehnga (~$50 + domain) nikla |
| **RAG** | Vector se relevant text retrieve karke LLM ko context dena |
| **Model drift** | Waqt ke saath model performance girna — monitor + retrain |

---

## 💼 Backend Dev Ke Liye Note

Yeh ek **event-driven data pipeline** hai — har component backend dev ke familiar building blocks hain. **Scheduler Lambda** = cron job / scheduled task (W3 baad mein EventBridge se). **App Runner researcher** = ek **worker service** jo background job process karta hai. **Ingest Lambda** = ek **ETL transform step** (extract from researcher → transform via embedding → load into S3 Vectors). Architecture ka khoobsurat hissa **loose coupling** hai: scheduler ko nahi pata researcher kya karta hai, researcher ko nahi pata storage kaisa hai — har stage clean interface se baat karta hai (event/payload). Production mein yeh trigger koi bhi ho sakta hai — webhook, queue message (SQS), file-drop (S3 event), CDC feed — pattern same rehta hai. Aur **cost-awareness** (OpenSearch $50 lesson) ek real backend discipline hai: managed services ki pricing model pehle samjho (per-hour provisioned vs per-request serverless) — S3 Vectors yahan jeeta kyunki bucket-style storage idle cost lagभग zero rakhta hai.

---

## ✅ Takeaway

- Aaj **conceptual setup** — Alex ki poori **data-ingest architecture** samajhi
- Flow: **Scheduler (2-hrly) → App Runner researcher (Bedrock + MCP + Playwright) → ingest Lambda → SageMaker (text→vector) → S3 Vectors**
- **S3 Vectors** = AWS ka naya, sasta vector store; **OpenSearch** mehnga nikla (~$50 + domain) — cost lesson
- **Vector + uska text dono store** hote hain taaki RAG se baad mein retrieve ho sake
- Aaj sirf **ingest Lambda → SageMaker → S3 Vectors** (blue bits) banayenge; SageMaker endpoint (purple) kal already ban chuka

---

<details>
<summary>📜 Full Transcript (English)</summary>

Look, I promised you a juicy course. And if you think that this. That Alex is already looking like a juicy project, you ain't seen nothing yet. We're getting more stuck into it today. We've got a lot to cover. Welcome to another Purple day. Another AI day. This is a day in which we're going to be looking at data ingest, in particular using an embedding model, an encoder that we deployed yesterday, uh, to, to create vectors and store them in S3 vectors, a new type of storage that offered by AWS. So let's get to it. First, some quick recaps. So the project we're working on, of course, is Alex, our capstone project, our SaaS financial planner. Next week is when we're really going to be building out Alex, the Agentic AI platform. This week it's all about the data ingest part of it, giving Alex its memory, its mind about financial markets and about retirement planning. We've started our setup by by cloning a repo. We've got Alex as a local project that's got separate Terraform directories for each of the different deployment steps that we'll be taking, and they have TF vars inside them for configuration. And there's also a env file in the project root that has overall, uh, secrets that govern the whole project. We've only got one environment I'm not deploying to dev and test to keep things a bit simpler. No GitHub actions, but you're very welcome to do that yourself if you'd like. And it's so satisfying to be able to do a git push and see it all roll out for you. And yesterday, of course, we we played around with SageMaker for the first time. We made an endpoint, an inference endpoint with an embedding model, a sentence transformers model from hugging face, the all mini lm v2, uh, which is a model you can use to take text and convert it into a vector. And what we're going to be building today is the data ingest lambda function. That will do that and store the results in S3 three vectors and just to be a little bit repetitive, but just sometimes it helps to hear things twice, reminding you of the difference between bedrock and SageMaker. Bedrock, which is about building with frontier models, being able to have, uh, inference that you can run with models like, uh, Nova and Claude and be able to run that at scale, whereas SageMaker is more the platform for data scientists, it's DevOps for data scientists, and it's where you can manage the complete lifecycle of your model development training models, managing different experiments, versioning models and data sets. It has, as we saw, its own kind of Google Colab Jupyter notebooks in the cloud. It's got inference endpoints that we know well because we're using them, uh, and lots of other functionality, including a complete kind of IDE built in. So lots for data scientists to experiment with in SageMaker. We've barely scratched the surface with our deployed SageMaker endpoint. I'd also talked about ML ops. I'd explain that that term can be used in different contexts. It can mean everything that we're doing on this course around platform engineering for AI. It can also be referring more specifically to managing different versions of your models and data, managing your different data science experiments, and that that is more commonly how it's used in that context. And when it's used in that way. SageMaker is one of your go to platforms. That is AWS, ML ops platform. And we talked a bit about model drift, this idea that models can kind of decay in their performance over time as as the natural language of the world evolves and as a result, something you need to to monitor for, to test the performance of your models and then retrain if you need to. And SageMaker is a place that you could do that, and you should go around and experiment with some of the functionality yourself and see if it's something you can you can find useful. You could, for example, if you've taken the LM engineering course, you could take the models that we trained there and look to see how you can incorporate them in SageMaker. So in the last couple of days, I gave you a little teaser of some of Alex's architecture, its deployment architecture, the data ingest side of it. And here's a simplified diagram of what we saw in the slightly more complicated mermaid diagrams. It's going to have Alex is going to have a scheduler, a lambda function that is going to wake up every two hours and say, okay, it's time. And when it does that, what it's going to do is it's going to kick off an app runner. Uh, it's going to to it's going to kick off something called the researcher, which is going to be an agent running in a container. It's going to have access to an MCP server because we want to be trying these different things. Uh, and so it's going to use the MCP server. It's actually going to run a playwright browser to be able to do some research. And what's going to come out of that is some information that it wants to add to its memory. So this is a typical example of a kind of rag process where you have something happening that's going to result in data being ingested. And I thought having a researcher that uses an MCP server is a is a really interesting way to to take this to be generating data. But in your case for your business projects, this might be something that's monitoring incoming feeds. It might be something that's looking at news that's being released or or information documents that are being saved in your company, anything that's causing an event to come in and new data that needs to be stored. And of course, the researcher needs a model to do that. And it's going to use bedrock as its way of calling a frontier model, and which will then call our MCP server. And when it's done that, when it's created some data, it's done a search on the internet, it's found some information it wants to store. It's now got some data that it wants to store in its memory. How is it going to do that? Well, it's going to pass that over to a lambda function called ingest. And ingest is our lambda function that is able to take some data and store it in our memory. And how does it store it in our memory? Well, the way that llms like to have memory of things is using vector data stores so they can retrieve relevant information quickly using Rag processes. And so we want to store it as a vector. So we've got some text from the researcher. We want to turn it into a vector. And the way we will do that is of course using the SageMaker inference endpoint that we deployed yesterday. So we will call out to the open source model the sentence transformers that we have running in SageMaker endpoint to turn it into a vector. And we will then store that vector in a vector store. And we're going to use a service called S3 vectors, which is you can think of like like it's S3, it's a bucket, but it's intended to store vectors. And this is actually a relatively new offering from AWS and it's very cost efficient. I previously used an alternative called OpenSearch that ended up being quite pricey, and you may know that already because you've been seeing it in my Cost Explorer that I spent, I think $70 or something. I think it was $50. There was also the domain name as well. I spent, I think, $50 just experimenting with the prior implementation before I realized that of the various alternatives, that was not cost efficient for certainly for our purposes and S3 vectors is perfect for this. So that is what I'm using. That is what the ingest lambda function will use to store the vector and the associated text, so that it can be retrieved later. So that is the data ingest architecture that we're going to be building today and tomorrow. So what part are we doing today. Well today we're just going to do this part. We're just going to be looking at the ingest lambda function and have it call our SageMaker endpoint and store the vectors. Very simple. These three components we've already built the purple one. Those are the blue bits around it. We're going to build today. And let's get right to it. Let's go back to cursor back into the Alix project Alix Repo and get to work.

</details>
