# L05 — Course Overview: Building Production AI Systems Across 4 Weeks

> **Week 1 · Day 1** · ⏱️ ~8 min

---

## 🎯 TL;DR

4-week curriculum ka full unveil: **W1** SaaS on Vercel→AWS (auth+subscription+healthcare app), **W2** AWS deep-dive (Lambda, Bedrock, Terraform, GitHub Actions), **W3** multi-cloud (Azure/GCP) + SageMaker + data pipelines + MCP, **W4** multi-agent production + observability/security + **capstone: agentic financial planner SaaS**. Tooling philosophy: transferable choices — Terraform (not CDK), Clerk (not AWS auth).

---

## 🗣️ Hinglish Explanation

### Course structure: 4 modules = 4 weeks, har week 5 days

Ed apne classic format mein course ko **4 modules** (har week ek) mein organize karta hai, aur har week ke **5 days** alag components cover karte hain. Ab week-by-week breakdown:

### Week 1 — SaaS project: zero se internet tak

Jo abhi chal raha hai. Is week hum:

1. **App build up** karenge — **front end + back end** architecture
2. **Authentication** add karenge (users login kar sakein)
3. **Subscription** add karenge (billing/payments)
4. Ek **healthcare SaaS app** banayenge (week ka main project)
5. Deploy karenge — **pehle Vercel par, phir pehli baar AWS par**

Yaani ek hafte mein complete SaaS lifecycle: code → auth → billing → cloud. Isi liye Ed ne bola tha Week 1 sabse intense hai.

### Week 2 — AWS deep-dive: platform engineering

Poora week **AWS architecture** par drill-down:

- **Digital Twin project ka Mark 2** — Ed ke previous course (Agentic Track) ka project, ab production-grade naya version
- **Amazon Bedrock** — AWS ka managed LLM service (foundation models ko API se access karna, OpenAI ko replace karke)
- **Terraform** — **Infrastructure as Code (IaC)**: infrastructure ko code files mein define karna, manually console mein click karne ki jagah
- **GitHub Actions** — **CI/CD**: git push → automated build → automated deploy

End result: ek **robust production deployment pipeline**. Jo AWS components hands-on nahi karenge, unke baare mein bhi learn karenge.

### Week 3 — Multi-cloud + AI infra mix

Sabse varied week — *"a slew of different activities"*:

- **New project: Cybersecurity Analyst** (chhota but really cool project — isko blue tile nahi mila diagram mein, par count hota hai)
- **Azure aur GCP deployment** — dono par **MCP servers** ke saath deploy karenge, taaki teeno major providers dekh liye hon
- **AWS SageMaker** — AWS ka ML platform (custom models host/train karna; Bedrock se zyada control)
- **Data engineering** — **ingest pipelines** banana (data ko process karke store karna)
- **Vector stores** — **S3 Vectors** use karke (embeddings storage for RAG/agent memory)
- **MCP servers** ke saath agent deploy karna — agent ke peeche MCP-served tools/data

### Week 4 — Agentic AI in production + Capstone

Grand finale:

- **Multi-agent system** build aur production deploy
- **Capstone project** + front end
- **Observability, monitoring, security** — Ed inhe agentic AI deployments ke **3 crucial aspects** bolta hai
- **Agentic AI platforms** (jaise managed agent runtimes) — very hot topic right now

### Capstone: Agentic Financial Planner SaaS 💰

Course ka flagship project — ek **commercializable product**:

- **SaaS product** — users sign up karte hain
- User apne **accounts, investments, equity portfolios, retirement accounts** ki details enter karta hai
- System **portfolio rebalancing advice** deta hai, decisions suggest karta hai, **retirement prospects** analyze karta hai
- **Multiple agents working in concert** — fully functioning agentic app
- Ed ka push: apne elements add karo, spice it up, **actually deploy + maybe monetize** karo

### Colored tiles ka matlab (curriculum diagram)

Ed ke curriculum grid mein har day ek tile hai, color-coded:

| Color | Matlab |
|---|---|
| 🟡 **Yellow** | DevOps / platform engineering concerns (majority — as promised L03 mein) |
| 🔵 **Blue** | Projects — healthcare app, Digital Twin Mk2, capstone (+ cyber project, jise blue square nahi mila) |
| 🟣 **Purple** | Primarily AI concerns (Bedrock, SageMaker etc. — though unme bhi DevOps kaafi hai) |

Total **4 projects** milte hain course mein. Aur Ed ka L03 wala point yahan visually confirm hota hai — purple squares hain, par yellow dominate karta hai.

### Scope: kya IN hai, kya OUT hai

Production deployment ki duniya **gigantic** hai — Ed deliberately scope limit karta hai, aur uske **tooling choices ka philosophy ek hi hai: transferability**:

- **AWS primary** — GCP/Azure sirf touch honge, detail mein nahi
- **Terraform > AWS CDK** — CDK popular hai par AWS-lock-in hai; Terraform same techniques se **AWS, GCP, Azure teeno** handle karta hai. Isliye Terraform.
- **Clerk for authentication** — AWS-specific auth componentry (Cognito-type) ki jagah Clerk, jo har platform ke saath kaam karta hai
- **Front end + Docker = surface level only** — code milega ready-made, par yeh apne aap mein poore disciplines hain. Ed **self-study guides** dega; naye logon ko guides par time spend karna chahiye. Aur pro tip: front end mein stuck ho toh **LLMs are really great at front end code**.

**Ed ka meta-goal:** tumhe specific tools nahi, **general ability** dena — same principles ko naye providers/APIs/components par khud research karke apply kar pana. Ek pattern bahut baar repeat hoga, alag-alag flavors mein — wahi repetition transferable skill banati hai.

Aur lecture ke end mein: *"I've been talking for far too long"* — ab wapas hands-on, apne simple production app mein **AI spice** add karne ka time (next lecture mein OpenAI integration).

---

## 📋 Key Concepts

| Concept | Matlab |
|---|---|
| **W1: SaaS week** | Front end + back end + auth + subscription + healthcare app → Vercel, phir AWS |
| **W2: AWS week** | Digital Twin Mk2, Bedrock, Terraform IaC, GitHub Actions CI/CD |
| **W3: Multi-cloud week** | Azure + GCP (MCP servers), SageMaker, ingest pipelines, S3 Vectors, cyber project |
| **W4: Agentic week** | Multi-agent deployment, capstone, observability/monitoring/security, agent platforms |
| **Capstone** | Agentic financial planner SaaS — portfolio rebalancing + retirement advice, multi-agent |
| **Bedrock** | AWS ka managed foundation-model API service |
| **SageMaker** | AWS ka ML platform — custom model training/hosting (Bedrock se deeper control) |
| **Terraform** | Cloud-agnostic Infrastructure as Code — isliye CDK ki jagah chosen |
| **AWS CDK** | Amazon ka IaC tool — popular par AWS lock-in, isliye skip |
| **Clerk** | Cross-platform authentication service — AWS-specific auth ki jagah |
| **Tile colors** | Yellow = DevOps, Blue = projects (4 total), Purple = AI concerns |

---

## 💼 Backend Dev Ke Liye Note

Yeh roadmap ek **production-ready backend dev ka upgrade path** hai. Week 2 tumhara sweet spot hoga — Terraform + GitHub Actions wahi IaC/CI-CD muscle hai jo senior backend roles demand karte hain; agar yeh pehli baar kar rahe ho, is week ko sabse zyada effort do. Tooling philosophy bhi note karo — **vendor-neutral choices (Terraform over CDK, Clerk over Cognito)** wahi architectural thinking hai jo system design interviews mein "avoid vendor lock-in" ke roop mein poocha jaata hai. Capstone (financial planner) resume ke liye gold hai: multi-agent + Aurora-class DB + observability + security ek hi deployed project mein — ise apne flavor ke saath publicly deploy karna seriously consider karo.

---

## ✅ Takeaway

- 4 weeks = **SaaS (Vercel→AWS) → AWS deep (Bedrock/Terraform/CI-CD) → multi-cloud+SageMaker+pipelines → multi-agent+capstone**
- **4 projects**: healthcare SaaS, Digital Twin Mk2, cybersecurity analyst, agentic financial planner (capstone)
- Tooling mantra = **transferability**: Terraform (not CDK), Clerk (not AWS auth), AWS-depth + GCP/Azure-breadth
- Front end aur Docker **surface-level** — self-study guides milenge; front end mein stuck ho toh LLM se karwa lo
- Observability + monitoring + security = agentic deployments ke **3 crucial aspects** (Week 4 mein detail)

---

<details>
<summary>📜 Full Transcript (English)</summary>

And now I'm excited to unveil our four week curriculum to become production grade. As usual with with my courses, I've organized this into four modules or different modules for each week. And the first week is focused on building a SaaS project that you deploy onto the internet, including things like authentication and subscription. The second week, we're going to be focusing on AWS drilling down on platform engineering for an AI project deployed on AWS. And we'll cover a whole set of different concerns with AWS, leaving you so that you can deploy your own stuff on AWS. And at least learn about the other components that we don't touch. And this is going to include infrastructure as code and CI CD. In the third week this is a slew of different activities related to AI projects. We're going to first of all take a look at Azure and GCP so that you've looked at all the major providers. We're going to focus on data engineering building ingest pipes. We're going to look at vector stores and MCP so that you could deploy an agent with MCP servers behind them. And then in the fourth week, we turn to Agentic AI. We're going to build and deploy a multi-agent system in production, and that will lead to the capstone project and the conclusion of the four weeks. And so each of these four boxes represents a module a week of of us learning together on this journey. And each week has five days representing the different components of the course. And the first week, what we're in right now is going to allow us to build up an app, have a front end and back end, have authentication subscription, and then build a healthcare SaaS app and deploy it first to Vercel and then our first deployment to AWS. In the second week, we're going to talk about AWS architecture. We're going to revisit a project from one of my previous courses, The Digital Twin, and we're going to make a new version of that. We're going to use bedrock, and then we're going to add in Terraform infrastructure as code and GitHub actions so that we've got a really robust production deployment pipeline. Week three is the sort of mixed mixture of lots of things. We're going to have a new project, the cyber security Analyst, which is really cool. We're going to deploy on Azure and GCP, both using MCP servers. We're then going to use AWS SageMaker and then have data ingest pipelines using S3 vectors and with an MCP server. And then the final week, a gigantic AI in production is when we'll talk about multi-agent deployments. We'll work on the capstone project, including a front end. We're going to add in observability, monitoring and security, three crucial aspects of AI and agentic AI deployments. And then we're going to end by talking about Agentic AI platforms, which is a really cool thing for us to look at. And also very hot right now. The capstone project that we'll be working on is going to be a product which should be ready to be commercialized. You can add in your own elements to it and maybe even monetize it. The idea is that it is an agentic financial planner for. It's a SaaS product that users can sign up for, can enter in details about their accounts, their investments, their equity portfolios, their retirement accounts. And it will then be able to rebalance to advise on how they could rebalance their portfolio and decisions they could make and their retirement prospects. So it's a fully functioning Agentic app, with different agents working in concert to be able to to add value and be something that could be useful for our user community. And hopefully you'll be able to spice it up, adding your own dimensions and actually deploy it. So this is what I have in store for you. You may be wondering what the different colored tiles represents. The yellow tiles are tiles which are primarily related to DevOps to platform engineering concerns. The blue tiles represent our projects, our healthcare app, Digital Twin Mark two and the capstone project. And what's not shown here, that the cyber project is a small project, so it didn't get a blue square. We're doing too many other things, but that is also a project to we have four, four projects for you. And the purple squares represent times when we're primarily looking at AI concerns. And now you might be forgiven for saying that today we haven't exactly yet looked at AI concern, but the day is young. We will get there. Uh, but but also this ties back before I told you that only 20% would be AI. And you can see here there are plenty of purple squares. I will say that even the AI stuff like bedrock and SageMaker, it's still a lot of DevOps work involved there. But nonetheless, there's there's AI for sure, in the purple squares. And at the end of this, when you've completed these four weeks and you've built your own projects, which is super important and done the assignments, then you'll be well deserving of this cup at the end of here. Uh, and uh, but in all seriousness, you would have got to a point where you will have carried you've completed that skill set, so you are then able to independently deploy commercial LM products Gemini and Agentic AI into production yourself. All of that's going to be for you four weeks from today. So hopefully you appreciate that. This course has a fairly comprehensive scope, quite significant scope. But I'm here to tell you that whilst it does the world of production deployment is absolutely massive. It's gigantic. And so there is a lot of stuff that's not in scope by, by, by extension. And just just to be specific, we primarily work on AWS. As I said, we touch on many of the others. That means we're leaving out going into detail on things like GCP and Azure. We are going to focus on the industry standard, the most transferable skills. So for example, when it comes to infrastructure as code, I'm not going to work with Amazon CDK, which is quite popular, but that does tie you into Ruined AWS and I want, I want what I teach to be as transferable as possible. So I will stick with Terraform, which is super popular and which allows us to use the same techniques for AWS and GCP and Azure. So Terraform is the one I pick. And I use similar kinds of decisions at various points for when it comes to to authentication. We stick with Clark, which we can use across the board. We don't we don't go with the with the AWS componentry. I touch on things like front end development and stuff like using Docker containers, but only at a surface level. You could have entire courses, and there are many courses on front end development and on Docker. And in fact there are many levels of courses on front end development. It's a whole discipline of its own, and I'm really going to be scratching at the surface of this. I'm going to give you some self-study guides, and for those new to it, I urge you to spend time on the guides. They should be super helpful for you. Uh, but I'm not going to go deep and the code will be there. It's not like we'll need to write front end, but when it comes to changing it, you might find yourself getting stuck quickly. Turns out llms are really great at that. But yeah, consider it to be touching the surface of all of the peripheral, uh, activities that we'll be doing, like front end development. My overall goal is to give you the tools so that you can apply the same principles that we work on to other kinds of components, to other providers, to other APIs. Once we've done this many times over in different ways, hopefully you've got the kind of general ability to do a bit of research yourself, to look up a service and decide to integrate it in, because you can apply what you've learned here to to other kinds of examples. So that's that's my, my, my general goal. And that is why I need to set your expectations, that what we're going to cover in scope is going to be a small subset of everything that's out there when it comes to the world of prod deployment. Okay. I've been talking for far too long. It's time for us to do some stuff. Let's go back now and add some AI spice to our simple production application.

</details>
