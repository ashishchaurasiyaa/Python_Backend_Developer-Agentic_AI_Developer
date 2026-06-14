# L115 — Capstone Assignment: Taking Your AI Financial Agent to Market

> **Week 4 · Day 4** · ⏱️ ~7 min

---

## 🎯 TL;DR

Capstone wrap-up: Ed tumhe homework deta hai — **Alex** (multi-agent financial planner) ko teen directions mein se kisi ek mein aage le jao — **Data Engineering**, **MLOps**, ya **Agentic AI** (Ed ki favourite). Goal: Alex ko ek **real commercial product** banao jo actually revenue earn kare, aur community contributions folder mein share karo.

---

## 🗣️ Hinglish Explanation

### Context: hum kahan pahunche hain

Yeh Week 4 Day 4 ka aakhri lecture hai. Pichle char din mein humne **Alex** banaya — ek enterprise-grade multi-agent financial planner SaaS jo AWS par deployed hai (Aurora Serverless DB, 5 agents, FastAPI/Next.js front+back, Lambda, Terraform, CloudWatch monitoring, Langfuse observability, guardrails). Ed bolta hai hum course ke **95%** par pahunch gaye hain. Aaj ki homework assignment se capstone project officially conclude hota hai.

Ed ka core message: Alex sirf ek tutorial demo nahi — yeh ek **"seed", ek "kernel"** hai jisko tum ek real, monetizable product mein convert kar sakte ho. Last week ki tarah, woh teen alag directions deta hai — pick your passion.

### Direction 1: Data Engineering pe deeper jao

Yaad karo Week 3 mein humne **data pipes** banaye the — ek research agent jo online search karta tha aur results ko vector knowledge base mein store karta tha. Problem: abhi woh **random** hai. Bas "any news related to financial planning" search karta hai, koi targeted nahi.

**Improvement idea:** Data pipes ko **portfolio-relevant** banao. Yaani:

1. Agents se input lo — user ke actual portfolio mein kaunse stocks/sectors hain
2. Us hisaab se research topics decide karo (e.g. agar user ke paas Nvidia hai toh semiconductor news search karo)
3. Relevant info knowledge base mein store karo

Yeh basically **Week 3 (data pipelines) aur Week 4 (multi-agent system) ke dots connect karta hai**. Iska technical naam **dynamic / portfolio-aware ingestion** hai — pipeline ka query static nahi, balki downstream consumer (agents) ke context se driven hota hai. Real RAG systems mein yahi pattern hota hai: ingestion ko consumption ke saath align karna, taaki knowledge base mein noise kam aur signal zyada ho.

### Direction 2: MLOps pe deeper jao (sleeves rolled up)

Yeh production reliability/operations wala track hai. Ed ne guide mein jo "substantive monitoring" dikhaya tha usko build-in karo:

- **Apna khud ka monitoring approach develop karo** — sirf default metrics nahi, business-specific metrics define karo
- **CloudWatch alerts** lagao — agar kuch down ho jaaye toh tumhe **alert** mile (email/SMS). CloudWatch AWS ka native monitoring service hai jo logs/metrics collect karta hai aur thresholds par alarms fire karta hai
- **Better guardrails**:
  - **Hard-coded guardrails** (plain Python checks — e.g. output JSON valid hai ya nahi, banned words to nahi)
  - **LLM-as-a-judge guardrails** — output ko ek aur LLM se validate karwana (coherence + alignment ke liye). Ed suggest karta hai **Langfuse** ka tool use karke yeh karna
- **Model drift tracking** — yeh MLOps ka crown jewel hai:
  - Kuch **metrics/values record karo** (e.g. response quality score, latency, judge pass-rate)
  - Unko **Langfuse mein log karo**
  - **Over time track karo** — agar model performance dheere-dheere niche jaa rahi hai (drift), toh tumhe **early head start** mil jaata hai improve karne ka

**Model drift kya hai?** Production mein model ya uske inputs ke distribution badalne se output quality degrade hone lagti hai. Concept drift (world badal gaya) ya data drift (incoming data badal gaya). MLOps ka kaam hai ise continuously detect karna — isliye time-series metrics aur trend analysis chahiye.

### Direction 3: Agentic AI pe deeper jao (Ed ki #1 recommendation)

Ed honestly bolta hai: jo sabse kam "amazing" cheez abhi Alex mein hai woh hai **actual financial advice ki quality**. Nova (Amazon Bedrock ka model) jo output deta hai woh "so-so" hai — Monte Carlo simulation part thoda "dodgy" hai aur uska interpretation average hai.

**Improvements:**

1. **Context engineering** — agent ko real financial planning knowledge se equip karo (ek financial planner ko actually kya pata hona chahiye)
2. **Agent interactions / dependencies** — abhi teen agents **isolation mein** kaam kar rahe hain. Hona ye chahiye:
   - **Retirement agent** ko **report** se information leni chahiye
   - **Charter agent** ko bhi report par depend karna chahiye
   - Yaani agents ke beech **data dependency / handoff** hona chahiye, parallel silos nahi
3. **Deep research pattern** — ek agent topics generate kare, baaki agents un par kaam karein (orchestrator-worker / planner-researcher pattern)
4. **More tools** — real financial planning tools, **Polygon** se live stock prices, company research, retirement projection charts

**Monte Carlo simulation kya hai?** Financial planning mein future returns uncertain hote hain. Monte Carlo method hazaaron random scenarios simulate karta hai (different market returns) aur probability distribution deta hai — "X% chance ki retirement corpus Y se zyada hoga". Agar implementation/interpretation kamzor hai toh advice bhi kamzor hogi — isliye Ed isko fix karne ko bolta hai.

### Commercial angle: Alex ek real product hai

Ed seriously bolta hai — Alex ek **true commercial platform** ban sakta hai, monetizable hai. Important caveats:

- Front par **disclaimer** zaroori hai — yeh qualified financial planner nahi hai. Yeh legally aur ethically critical hai, aur yeh decide karta hai ki tum realistically kitna charge kar sakte ho
- **Subscription tiers** ke liye **Clerk** (Week 1 mein use kiya tha) ki functionality use kar sakte ho — Clerk billing/auth handle karta hai

Ed ka mazak: agar tum monetized product banao, code mat bhejo — **live product ka link** bhejo, woh subscribe kar lega (agar sasta hua), revenue le aayega, aur agar accounts manage kar de toh aur bhi badhiya.

### "Evil trifecta" vs "good trifecta"

Ed callback deta hai — pehle "**lethal/evil trifecta**" discuss hua tha (security risk: untrusted input + private data access + external communication = prompt injection danger). Iske counterbalance mein ye **"good trifecta"** hai: agar tum teeno directions (Data Engineering + MLOps + Agentic AI) touch karo toh ek complete, well-rounded production product ban jaata hai.

### Sharing karna

- **Community contributions folder** mein post karo — **production repo** mein (course ka main repo nahi, balki dedicated *production* repo)
- Ek **markdown file ya Jupyter notebook** mein writeup do
- Product ka **link** share karo

### Teaser

Lecture cliffhanger par khatam hota hai — 95% done, sab kuch "epic" aur "legendary" feel ho raha hai jaise finale aa gaya... par Ed bolta hai "what more could there possibly be? I'm not going to tell you — wait until tomorrow." (Day 5 mein Agent Platforms + Bedrock AgentCore aane wala hai.)

---

## 📋 Key Concepts

| Concept | Matlab |
|---|---|
| **Alex** | Course ka capstone — multi-agent financial planner SaaS, AWS par deployed |
| **Portfolio-aware data pipes** | Research/ingestion pipeline jo agents se input le ke targeted topics search kare (random nahi) |
| **Model drift** | Production mein model performance ka time ke saath dheere-dheere degrade hona |
| **Hard-coded guardrail** | Plain Python validation checks (JSON valid, banned words, injection phrases) |
| **LLM-as-a-judge guardrail** | Output/input ko doosre LLM se coherence + alignment ke liye validate karwana |
| **CloudWatch alerts** | AWS native monitoring — metric thresholds par alarm fire karke notify karna |
| **Context engineering** | Agent ko domain knowledge/info se properly equip karna behtar output ke liye |
| **Agent dependency** | Agents ka isolation chhod ke ek-doosre ka output consume karna (handoff) |
| **Monte Carlo simulation** | Hazaaron random scenarios simulate karke probability-based financial projection |
| **Good trifecta** | Data Engineering + MLOps + Agentic AI — balanced production improvement |
| **Clerk subscription tiers** | Auth/billing tool jisse paid subscription tiers set up karte hain |

---

## 💼 Backend Dev Ke Liye Note

Yeh lecture ek **product/architecture roadmap** hai, code nahi — par har direction ek classic backend engineering discipline se map karti hai. **Data Engineering direction** = ETL/ingestion pipeline ko consumer-driven banana (query parameterization, relevance filtering, vector store hygiene). **MLOps direction** = woh sab jo tum already SRE/observability mein karte ho — metrics emit karo (CloudWatch/Prometheus jaisa), alerting set karo, aur ek naya layer: **drift detection** (time-series quality metrics, jo traditional uptime monitoring se aage jaata hai). **Agentic direction** = system design — abhi tumhare agents **embarrassingly parallel silos** hain; Ed bol raha hai inhe **DAG/pipeline** banao jahan downstream agents upstream output consume karein (basically service-to-service dependency + data contracts). Backend lens se: guardrails = input validation + output sanitization layer, aur LLM-as-judge = ek async validation microservice. Aur commercial angle (disclaimer, subscription tiers via Clerk) yaad dilata hai ki production product mein legal/billing/auth utne hi first-class concerns hain jitna code.

---

## ✅ Takeaway

- Capstone homework: Alex ko **teen directions** mein se kisi ek mein aage le jao — Data Engineering, MLOps, ya **Agentic AI** (Ed ki top pick)
- **Data Eng** = data pipes ko portfolio-relevant banao; **MLOps** = monitoring + CloudWatch alerts + guardrails + drift tracking; **Agentic** = context engineering, agent dependencies, deep research, real tools (Polygon)
- Alex ek **real monetizable product** hai — disclaimer crucial hai, Clerk se subscription tiers laga sakte ho
- Apna kaam **production repo ke community contributions folder** mein markdown/notebook + product link ke saath share karo
- Course 95% complete — Day 5 mein ek "secret" final topic aane wala hai (Agent Platforms + Bedrock AgentCore)

---

<details>
<summary>📜 Full Transcript (English)</summary>

Okay. And so to wrap up our capstone project, it's time for you to take some homework. Your assignment please. Uh, I would like you to take Alex forwards in one of three different directions. Again, as we did last week, uh, and one of them is, again, to go deeper on data engineering, if that is your thing. You remember that when we built the data pipes last week, it's just basically searching online for something interesting. But we did give it the ability to take an input about what it should search for. But but at the moment it's just searching for any, any news related to financial planning. Uh, and that's a bit random. It would be a lot better if it actually got information from the agents about what it should look for related to the user's portfolios, and it researched topics relevant to them and stored that in the knowledge base. And so making the data pipes be relevant to portfolios, connecting the dots between what we did this week and what we did last week, that would be really cool. That would be a big improvement to Alex, and it would be great if you were able to make that and a second direction you could take. It is going deeper on MLOps, so building in the more substantive monitoring that I showed you in the guide. Putting in more monitoring and developing your own monitoring approach. Putting in the the cloud, the CloudWatch alerts so you get alerts. Everything goes down. Putting in better guardrails, both some hard coded guardrails and Python and maybe some llms as a judge. Guardrails, maybe using Lang Views tool to do that, and then tracking model drift. So record some some values, uh, record some metrics, get them in lang views and then track them over time and record what happens to them. So if the model performance is gradually going downwards, you'll get that kind of reporting. You'll get an early head start to improve it. So this is all sleeves rolled up. MLOps really understanding the performance of your models in production. And last and definitely not least, and the one that I hope that some of you sign up for is working on the Agentic AI. It's about improving the financial planner in all the things we did this week. Maybe the thing we didn't look at very much was the actual results that you get. If you look on those pages, what actually came back from Nova. And I got to tell you that of all of the really amazing things I showed you, that is possibly right now the least amazing that the quality of the financial advice it gives is kind of, uh, I think maybe the Monte Carlo simulation part is a bit dodgy, and I think maybe it's interpretation of it is just sort of so-so, and it could be so much better. We should work on the context engineering to equip it with real information about what a financial planner needs to know. There should be interactions between the agents. The three agents are working in isolation, but really the retirement one should be taking in the information from the report. And so, so should the charter. So there should be some some dependency between the agents. And maybe they should be able to do deep research where one of them comes up with some topics and then the others work on it. There's so much that could be done here so that the agent interactions go deeper, get more content, use more tools, maybe have access to to real financial planning tools in order to be able to improve the quality of the results. And I got to tell you something, and I mean this. So seriously, I feel like Alex really is a true commercial platform. Like this is something that could be monetized. Now, obviously there is that disclaimer on the front of it. It's clearly not a qualified financial planner. And that disclaimer is very important to bear in mind to understand what you could realistically charge for this. But nonetheless, you could take this, this, this kernel, this seed, this seed, this starting point, and build on top of this and build something that has deep intelligence. It's able to research, it's able to use tools, it's able to add value and come up with comprehensive financial analysis based on your portfolio. Looking up stock prices in polygon and researching companies using its expertise and building charts that project your retirement earnings. So there's a lot that could be done here if you work on the AI. I believe that this is a is a product that can actually sell. And so you could emerge from this homework assignment with something which is actually able to earn revenue. And that would be a thing. So I'm very excited. I'm very hopeful that people do this AI part and make, make, make the whole Alex platform more rich. And whilst you're doing that, you could also touch on the data engineering side and the MLOps side as well, and do do a good trifecta, uh, to, to counterbalance the evil trifecta from before. Uh, that would be fantastic. And that would give us a real product actually in production and actually earning revenue. And please remember, with whatever you build, we would love to see it. We need to share it. Please do post uh, document a markdown file or a Jupyter notebook. In the community contributions folder of the production repo, not the repo, but the production repo. So we have it all in one place. Uh, and give a link to your product out there. If it's a product that you've monetized, then I suggest you don't give us the code, but you send us a link to the actual product so I can come in, and as long as it's cheap enough, I'll subscribe to it. I'll bring you in some revenue. Uh, and, uh, if it, if it will manage my accounts and, uh, that that would be great. Uh, and of course, you can use Clark's functionality to set up subscription tiers, but this would be a really good way to to share what you've done. If you haven't built a full on commercial product, don't worry, I'd still love to see it. Please do whatever changes you've got and, uh, share a link with your writeup of what you've done. This is going to be the most satisfying part of all of this course will be seeing what people make, how you're able to take this, this seed of a product and take it forwards and make it richer, more powerful. Financial planner A financial planner deployed to production. Oh my goodness, it's been a huge day. That concludes the capstone project. It's an enterprise strength capstone project. We've done so much and I yeah, I feel like I talked a lot today, but this this was this was absolutely the the important material that we needed to cover. It's all been building up to that. Uh, and I hope that, that you really feel knowledgeable now that you've built this expertise. And so you should because the number is 95. We are 95% of the way through. You've you've really imagined what we've got done in, uh, not even four weeks. Uh, it's been huge. And you're probably thinking, wow, this feels like, so conclusive. Like it really feels like we've we've reached a finale. This has felt epic today. It's felt just legendary. What more could there possibly be? Well, I tell you what more there could possibly be, but I'm not going to tell you. You're going to have to wait until tomorrow. I'll see you then.

</details>
