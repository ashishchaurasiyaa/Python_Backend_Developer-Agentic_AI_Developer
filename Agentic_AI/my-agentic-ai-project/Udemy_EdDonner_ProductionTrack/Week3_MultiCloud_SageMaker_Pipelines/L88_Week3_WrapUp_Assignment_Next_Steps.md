# L88 — Week 3 Wrap-Up: Assignment Options & Production AI Next Steps

> **Week 3 · Day 5** · ⏱️ ~9 min

---

## 🎯 TL;DR

Week 3 ka end. Assignment: research pipeline ko 3 mein se kisi (ya multiple) direction mein resilient + richer banao — (1) **more Agentic** (extra MCP servers, context engineering, to-do tools), (2) **more Platform/DevOps** (SQS retries), (3) **more Data** (transform + Supabase external DB). Plus cost-management reminder aur Week 4 capstone ka teaser.

---

## 🗣️ Hinglish Explanation

### Assignment — pipeline ko bulletproof + richer banao

Week 3 ka assignment important hai: jo build kiya hai use **more resilient, more bulletproof, richer in functionality** banana. Teen alag directions — koi ek, ya multiple chuno.

#### Direction 1: Go deeper in Agentic AI

Research agent ko deeper capabilities do:

- **More MCP servers add karo.** Agar Ed ka Agentic AI course liya hai toh **Polygon MCP server** add kar sakte ho — taaki researcher current **stock prices** dekh sake, ya (paid plan par) companies ke **financial documents** collect kar sake. Pretty cool.
- **Context engineering.** Yeh hot phrase sirf prompt engineering se aage hai — agent ko diye jaane wale **saare context** (information) ke baare mein sochna, taaki agent on-track rahe aur achhe outcomes de. (Prompt = ek part; context = saara provided information — instructions, examples, tool results, memory.)
- **To-do list functionality.** Agent ko **to-do list tools** do (khud likho) — agent apni research ka plan banaye, har step ek-ek karke kare. Yeh agent ko zyada thinking aur on-track rakhta hai. **Claude Code** ke experience ko emulate karo — wo bhi to-do list maintain karta hai.

```python
# Idea: to-do list tools (self-written)
@function_tool
def set_todo_list(items: list[str]) -> str:
    """Agent apni research plan ko discrete steps mein break kare."""
    ...

@function_tool
def mark_todo_done(index: int) -> str:
    """Ek step complete mark kare, agent track par rahe."""
    ...
```

#### Direction 2: Go deeper in Platform Engineering / DevOps

Aur AWS services incorporate karo, deployment architecture ko bulletproof banao:

- **SQS (Simple Queue Service)** padho aur add karo. Yeh research + ingest process ke around ek **resilient task management** system de dega — agar kuch fail ho (MCP server gir gaya, Playwright timeout, etc.) toh task **automatically queue hokar retry** ho jaata hai.
- Test: deliberately error hone do (yeh apne aap kabhi-kabhi error karta hai) → dekho yeh **retry + re-run** kar raha hai.

```
EventBridge ──► SQS Queue ──► Lambda/Worker ──► (fail?) ──► back to queue (retry)
                                    │
                                    └─► (success) ──► ingest pipeline
```

SQS yeh banata hai ki transient failures pipeline ko break na karein — **at-least-once delivery + retry** semantics.

#### Direction 3: Go deeper in Data Engineering

Data side par focus:

- Abhi researcher se raw data aa raha hai. Use ek **standard structured format** mein map karo (apna schema banao), aur **external database** mein store karo.
- Example: **Supabase** (free account, API key milta hai). Ek **serverless Lambda function** banao jo ingest se aaye data ko **transform** karke Supabase mein API key se **write** kare. Yeh external DB writing + format transformation dono sikhata hai.

```python
# Idea: serverless function → Supabase external write
import os
from supabase import create_client

supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])

def handler(event, context):
    structured = transform_to_standard_format(event["ingest_data"])  # apna schema
    supabase.table("research").insert(structured).execute()
    return {"statusCode": 200}
```

- **Stretch challenge (1 + 3 combine):** Lambda ki jagah **App Runner + Supabase MCP server** use karke Supabase mein write karo. Yeh agentic + data dono cover karta hai.

### Sharing your work

Ed bolta hai sabse best learning **khud build karke** hoti hai (sun-sun kar ya use type karte dekh kar nahi). Assignment zaroor lo. Success par share karo:

1. **LinkedIn** par post + link, aur Ed ko **tag** karo — wo weigh-in karega.
2. **GitHub PR (best, immortalized):** apne repo ke alawa, course repo ke **community contributions** folder mein ek **Python notebook** ka PR submit karo — apne repo ka link + couple comments + maybe screenshot. Instructions `guides` folder mein hain. Ed use repo mein merge karega, sab students ke saath share hoga.
3. **Community contributions** check karo — dusre students ne kya banaya dekho.

### Cost management reminder

Wrap-up se pehle (jaise har week):
- **Root** se AWS console → **Billing and Cost Management** check karo. Expenses / free-credit consumption par nazar rakho.
- Agar agent har 2 ghante chal raha hai, samjho kitna cost ho raha hai.
- Comfortable nahi ho? `terraform/main.tf` mein `scheduler` ko `false` karke `terraform apply` se scheduling **off** karo.
- Pura researcher infra band karna ho toh **`terraform destroy`**:

```bash
cd terraform/4
terraform destroy   # researcher infra poori band
```

> **Note:** Week 4 mein iss data ka kuch use hoga, par mandatory nahi — baad mein wapas `terraform apply` se bring up kar sakte ho. Comfortable ho toh chhod do running — knowledge build karta rahega (har 2 ya 20 ghante, jo cadence comfortable ho), markets/financial-planner expertise gehri hoti jaayegi, jo Week 4 mein kaam aayegi.

### Week 3 — Mission Accomplished (75%)

Week 3 grueling tha. Recap (week ki shuruaat bhool jaate hain kyunki ingest pipeline par itna time gaya):
- **Day 1:** Cyber project, **Azure** + **GCP** par deploy
- MCP ko **teeno clouds** (AWS + Azure + GCP) ke containers par
- **SageMaker** + **Bedrock** dono cover
- **API Gateway** with apni **API key** + controls (scaling, throttling) — enterprise plumbing
- **Enterprise-grade ingest pipeline** — agents + MCP + Lambda + App Runner + scheduling, large-scale data ingest ready

Day-night, har 2 ghante, autonomous data flowing → vectors stored. **75% — Week 3 done (4 mein se 3).**

### Week 4 teaser

Next week **triumphant** — complete **Agentic AI platform**, capstone ka conclusion:
- **So many agents**, **so many Lambdas**, complex architecture diagram (Ed "blow your mind" karna chahta hai)
- Heavy lifting, juicy building
- Last 25% — generative AI + Agentic AI production expert banne tak

---

## 📋 Key Concepts

| Concept | Matlab |
|---|---|
| **Assignment 3 directions** | Agentic / Platform-DevOps / Data — koi ek ya multiple |
| **Polygon MCP** | Stock prices + financial docs ke liye MCP server (Agentic course se) |
| **Context engineering** | Prompt se aage — saara provided context manage karna, agent on-track rakhne ko |
| **To-do list tools** | Agent ko plan-and-execute capability dena (Claude Code-style) |
| **SQS** | Managed queue — failed research/ingest tasks auto-retry, resilience |
| **Supabase** | Free external Postgres-style DB — structured data write via API key/MCP |
| **`terraform destroy`** | Researcher infra poori band karne ka command |
| **Community contributions** | Course repo folder — notebook PR se kaam share karo |
| **75% milestone** | Week 3 done; SageMaker + Bedrock + tri-cloud MCP + ingest pipeline |

---

## 💼 Backend Dev Ke Liye Note

Yeh wrap-up teen alag **engineering maturity axes** offer karta hai jo har backend dev ke career mein recur karti hain. **Direction 2 (SQS)** sabse pure backend lesson hai: synchronous, fragile pipeline ko **queue-backed, retry-able** system mein convert karna — yeh **decoupling + at-least-once delivery + dead-letter queue** ka classic pattern hai jo production reliability ka backbone hai (dekh lo: idempotency tab zaroori ho jaati hai jab retries aate hain). **Direction 3 (Supabase + transform)** ek **ETL/ELT** mindset hai — raw data ko canonical schema mein normalize karke durable store mein likhna, exactly jaise tum upstream API responses ko apne domain models mein map karte ho. **Direction 1 (context engineering + to-do tools)** agentic-specific hai par yahan bhi backend instinct kaam aata hai: agent ko **structured state** (to-do list) dena = stateless LLM call ko stateful workflow banana, jaise tum ek saga/state-machine design karte ho. Aur **cost discipline** (`terraform destroy` jab nahi chahiye) cloud-native development ki non-negotiable habit hai — idle infra = burning money; IaC ka asli faayda yahi hai ki teardown + rebuild trivial ho jaata hai.

---

## ✅ Takeaway

- Assignment: pipeline ko resilient + richer banao 3 directions mein — **Agentic** (extra MCP/Polygon, context engineering, to-do tools), **Platform** (SQS retries), **Data** (transform + Supabase external DB)
- Best learning = **khud build karna**; kaam **LinkedIn (tag Ed)** ya **community-contributions PR** (Python notebook) se share karo
- Cost discipline: root → Billing check; `scheduler = false` + apply se pause, ya **`terraform destroy`** se poori band (Week 4 mein data use hoga par mandatory nahi)
- Week 3 done = **75%**: Azure + GCP + AWS tri-cloud MCP, SageMaker + Bedrock, API Gateway + key, enterprise ingest pipeline (agents + MCP + Lambda + App Runner + scheduler)
- Week 4 = capstone conclusion — multi-agent platform, many agents + Lambdas, final 25%

---

<details>
<summary>📜 Full Transcript (English)</summary>

And at this point, I want to tell you about your assignment for the end of week three. And it's an important one, and it's going to be about making what we've built more resilient, more bulletproof and richer in functionality. And I'm going to suggest you could take three different directions, one of three different directions or multiple should you wish. So three different directions for your assignment. The first of them is to go in a more agentic direction. Go deeper in Agentic AI. For example, you could add on more MCP servers to your setup. If you've taken my Agentic AI course, we could add on the polygon server so that our researcher is able to look at at current stock prices. Or if you're on the paid plan, it's able to collect financial documents associated with companies. So that would be pretty cool. You could also work more on the context engineering. Context engineering this this hot phrase for not just thinking about prompt engineering, but thinking about all of the information you provide in the context to get the most success from the agent, to keep it on track, delivering good outcomes. So you could work on some context engineering, and you could also add in to do list functionality. This would keep the the agent thinking more and being more on track with what it's meant to do. Give it some tools to be able to set a to do list for how it wants to do its research, and then carry out each step one by one, providing it with to do list style tools that that you can write yourself is is very powerful. Think about how the experience of working with Claude code and try and emulate that in terms of how your agent works. So that's just a bunch of ideas, a few ideas. You could have different ideas, but use those different approaches to give your research agent deeper capabilities. So the second direction you could take this assignment is to go deeper in platform engineering in DevOps. So look at some other AWS services that you could incorporate here. And I'd suggest you read up on SQS for example. This would allow you to put a more resilient task management system around the research and ingest process such that if it fails for some reason, it automatically gets queued to You to retry. So you could put in that kind of bulletproofing around the setup and make sure that works, and then let it have an error. And it tends to have an error on its own sometimes just just because the MCP server goes wrong, the playwright browsing times out, whatever, you'll be able to see it retrying and running again. So that will be making the platform more bulletproof by working on the the platform engineering side of it, the deployment architecture. And then the third way that you could take this further is to look at the data side of it. Go deeper on data engineering. So right now we're bringing in the data from from the researcher. What we could do is map it to some kind of standard format that we come up with some format where there's some structured information that you want, and then store it externally in an external database. For example, you could look at Supabase where you can sign up for a free account, get an API key, and you could have a serverless function that's able to take the data that came from the from the ingest, and then write it out to your super base database externally using your API key. So this will be a great way to to build another Lambda serverless function and to be able to write data externally, also transforming it into a different format. And so that should be should be pretty exciting. If you want to sort of stretch challenge there, then don't use Lambda, use App Runner and use an MCP server. Again, use the super base MCP server to write out to super base. That would be taking on both the one and three, and I would love to see some examples of that. If someone wants to to to to sign up for that. But anyways, you take it come up with something different as well. This is an opportunity to be creative, to think of a different way that you'd like to beef up this data, ingest pipeline and go build it. And I can't stress enough that the very best way to learn is not by listening to me yabbering away, not even by watching me typing furiously, uh, but by building yourself. And so please do take this assignment on. Do go and have a shot at it. And when you're successful, then please share it so we can all take joy in your success. And the way to do that. There's there's many ways. One is to post on LinkedIn and put up a link to it, and if you tag me in that, then I will. Then I will come in and weigh in. But another way and a great way that would that would have have it be immortalized in, in GitHub would be to in addition to putting it onto your own repo, submit a PR with with a Python notebook in the repo in the community contributions folder that links to your repo and gives a couple of comments about it. Maybe the screenshot. Put that in a Python notebook, submit a PR instructions in the guides folder, and then I will bring that into the repo and you'll be sharing it with all students that way. And this is a moment to go and check out that community contributions and see what other students have done. And as a final reminder, as we wrap up, please do go back in as root to your AWS console. Make sure you look at billing and cost management. Keep an eye on your expenses or your how you're consuming your free credits. If you're in a free plan and make sure you're satisfied. Comfortable with that. Uh, if you have your agent running every two hours and doing some research, then that's great. Understand how much that costs. And if you're not comfortable with it, of course, just change in the terraform file in main.tf, change that scheduler to false and do a terraform. Apply again to turn off your scheduling. Uh, and uh, if should, should you wish to not be running this infrastructure for the researcher? For sure you can do a terraform destroy and bring it down. We will be using some of this data next week. But but you don't need to. You can always bring it back up again when that time comes. Uh, but if you're comfortable with it, then leave it running. Let it do its thing. Or you can you can make the schedule like every, every 20 hours or something. If you'd be more comfortable with that, make sure that you're happy with the costs. But then if you are, leave it running. Let it build up its knowledge. Let it get more and more knowledgeable, deeper and deeper expertise about the markets, about being a financial planner, because we will put that to excellent use next week when we build out our full agent tech platform. So look, if you're feeling a little bit exhausted, I don't blame you. We've we've been through a lot together. This has been quite, a quite a grueling week. Uh, it's hard to, to remember that we began it by doing the, the cyber project and deploying that to Azure and GCP because we've been spending so much time working on this data ingest pipeline. The researcher, the agent, MCP and the ingest and vectors. But wow, what? We should be super proud of what we've built. We've built something that is an enterprise grade ingest pipeline. Hopefully you're thinking about things like how that agent could also be calling out to different APIs. There's there's there's so many ways that this is this is enterprise grade and ready for large scale data ingest. And also, yeah, other other things to remember from this week include the way that we built that API with API gateway, with its own API key, and with its own controls around how how it's used, how how much it can be scaled and throttled. So a lot of enterprise plumbing that we've built, and it's been a lot of fun. And certainly I feel super satisfied by by where it is right now and by the fact that that, uh, all all through the day and night, every two hours, it's going to be waking up, stuff is going to be happening, data is going to be flowing, vectors are going to get stored. All of that's happening. Wow. Okay. And with that, it's the moment for me to say 75%. Week three. Mission accomplished. Week three out of the four. 75%. Through we covered SageMaker as well as bedrock. We deployed Mchp to two containers on all of GCP and Azure and AWS. We got so much done. But next week, next week is going to be triumphant. We're going to be building a complete Agentic AI platform. It's our conclusion of our capstone project that's going to be so many agents. It's going to be so many lambdas. It's going to be such a complex architecture diagram. I plan to I wish to blow your mind. You will see it all. It's going to be great. Make sure you get lots of sleep because it's going to be, uh, some, some really heavy lifting, some very juicy building. Next week, as we wrap up our capstone project and we complete the last 25%, the final stretch until you are an expert at generative AI and Agentic AI deployed to production.

</details>
