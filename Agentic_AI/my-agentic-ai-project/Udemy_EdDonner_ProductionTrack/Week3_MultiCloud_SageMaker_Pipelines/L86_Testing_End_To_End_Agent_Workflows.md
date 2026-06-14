# L86 — Testing End-to-End AI Agent Workflows from Research to Vector Storage

> **Week 3 · Day 5** · ⏱️ ~8 min

---

## 🎯 TL;DR

`uv run deploy.py` se Docker image build hokar ECR par push hota hai, phir full `terraform apply` se App Runner service live (Ed ko ~8 min). Phir pura pipeline test: S3 vectors cleanup → `test_research.py` (agent web research + ingest) → `test_search.py` (vector store verify) → OpenAI traces page par poora agent flow dekhna.

---

## 🗣️ Hinglish Explanation

### Step 1: `deploy.py` chala kar image push karo

```bash
cd backend/researcher
uv run deploy.py
```

Script jo karta hai (pichle lecture mein dekha tha) live chalta hai:
1. **AWS account details** fetch karta hai
2. **ECR URL** dhundhta hai (Terraform output se)
3. **`docker build`** chalata hai — `Dockerfile` recipe ke according: Node install, `pip install uv`, Playwright + Chromium install — sab steps dikhte hain
4. (Ek warning aata hai — **safely ignore**)
5. Container build hokar **ECR par push** hota hai

Yeh thoda time leta hai (build + push). Complete hone do.

### Step 2: Full `terraform apply`

Ab jab image ECR mein hai, App Runner service deploy ho sakti hai. Naya terminal, `terraform/4` mein jao, aur **full apply** (ab koi `-target` restriction nahi — sab kuch deploy):

```bash
cd terraform/4
terraform apply
```

`yes` bolo. App Runner provision hone mein time lagta hai — Terraform bolta hai "3 to 5 minutes" par Ed ko **almost 8 minutes** lage. Success milte hi ek **App Runner URL** mil jaata hai. Service live.

### Step 3: Pura pipeline test — "moment of truth"

#### 3a. S3 vectors cleanup (clean slate)

Pehle vector store ko empty karo taaki test results clearly dikhe ki naya data aaya:

```bash
cd backend/ingest
uv run cleanup_s3_vectors.py
```

`yes` → sab delete. (Yeh **cleanup script** database ko poori tarah wipe karta hai.) Dobara chalao confirm karne ke liye — "no vectors found. Database is already empty." Excellent — clean slate ready.

#### 3b. Research test — agent ko chalao

```bash
cd ../researcher
uv run test_research.py
```

Yeh kya karta hai:
1. App Runner service ka **URL** fetch karta hai
2. **Health check** — service healthy hai
3. Agent ko ek **trending topic** par research generate karne bolta hai
4. Bolta hai "20 to 30s lagega" (Ed ke experience mein zyada bhi lagta hai)

Background mein **live** yeh ho raha hai:
- Agent run ho raha hai
- **MCP server spawn** ho raha hai
- **Playwright browser** load ho raha hai
- Web pages par **navigate** kar raha hai, news collect kar raha hai
- News collect karke **`ingest_financial_document` tool** call karta hai → ingest function → vector store mein save

> **Reality check:** Ed ka pehla run **timeout/bad gateway** error de gaya (App Runner par ~2-minute timeout hai), dusra run fine chala. Yeh **Nova model thoda hit-or-miss** hone ki wajah se — Nova OSS 120B ya Claude jitna strong nahi, kabhi tool calling thodi galat ho jaati hai. OSS 120B ya bade models (Claude) zyada reliable honge. Ed ko ~50/50 success rate mil raha tha.

#### 3c. Search test — knowledge base verify karo

Ab dekho ki research actually store hua ya nahi:

```bash
cd ../ingest
uv run test_search.py
```

Pehle empty tha; researcher chalne ke baad ab vector store mein **stuff** dikhega — trending topics ka data jo researcher ne agent flow se generate karke ingest function ke through daala. Yeh confirm karta hai ki **research → ingest → vector storage** pura chain kaam kar raha hai.

### Step 4: OpenAI traces — andar kya hua dekho

Agar believe nahi ho raha ya detail chahiye, toh **OpenAI traces** dekho:

1. **platform.openai.com** par jao
2. **Logs** click → upar **Traces** click
3. Apne latest runs dekho

Ek trace mein kya dikhta hai (Ed ka 80s wala successful run):
- `list MCP tools` — agent ne available tools list kiye
- `browser_navigate` (multiple times) — alag pages par gaya
- `browser_click` — links click kiye
- `browser_handle_dialog` — dialogs handle kiye
- `browser_snapshot` — page content padha
- Aur **end mein** `ingest_financial_document` tool call kiya → ingest function → ingest flow follow hua

Yeh trace exactly dikhata hai ki **research → ingest** kaise jud-ta hai. Ed bolta hai prompts tighter karke (e.g. "only visit one page") agent ko itna "around the houses" jaane se rok sakte hain. Yahin "behind the scenes" ka real feel milta hai.

### Pura end-to-end flow (visual)

```
test_research.py
      │
      ▼
App Runner (Researcher / FastAPI)  ──health check── ✓
      │
      ▼
OpenAI Agents SDK loop  ──spawn──►  Playwright MCP (headless Chrome)
      │                                  │  navigate / click / snapshot
      │  ◄── web research results ───────┘
      ▼
ingest_financial_document tool
      │
      ▼
Ingest Lambda (via API Gateway)  ──►  SageMaker embed  ──►  S3 vectors
      │
      ▼
test_search.py  ──►  vectors found ✓
      │
      ▼
OpenAI traces  ──►  full step-by-step replay
```

---

## 📋 Key Concepts

| Concept | Matlab |
|---|---|
| **`uv run deploy.py`** | Build + push researcher image to ECR (live build steps dikhte hain) |
| **Full `terraform apply`** | App Runner service deploy (no `-target`); Ed ko ~8 min |
| **`cleanup_s3_vectors.py`** | Vector store poora wipe — clean slate test ke liye |
| **`test_research.py`** | App Runner call → agent web research → ingest tool → vector store |
| **`test_search.py`** | Vector store query — verify data store hua |
| **App Runner ~2-min timeout** | Lambi research par "bad gateway"/timeout aa sakta hai |
| **Nova hit-or-miss** | Chhota model — kabhi tool calling galat; OSS/Claude zyada reliable |
| **OpenAI traces** | platform.openai.com → Logs → Traces — agent ke har tool call ka replay |
| **browser_navigate/click/snapshot** | Playwright MCP tools — agent ka web research toolkit |

---

## 💼 Backend Dev Ke Liye Note

Yeh lecture **integration / end-to-end testing** ka textbook example hai. Notice karo Ed ka pattern: **clean state setup** (`cleanup`) → **action** (`test_research`) → **assertion** (`test_search`) — yeh bilkul tumhare `setUp → act → assert` test lifecycle jaisa hai, bas distributed cloud services par. Production mein yeh **smoke tests / synthetic monitoring** ban jaate hain — chhote scripts jo deploy ke baad pura critical path exercise karte hain. **App Runner ~2-minute request timeout** ek important production constraint hai: long-running agent kaam (multi-page browsing) HTTP request-response model mein fit nahi hota — isliye agle lecture mein EventBridge scheduler + async pattern aata hai (fire-and-forget). **Nova ka non-determinism** woh hai jo har LLM backend dev ko bite karta hai: same input, alag output, kabhi tool calling fail — isliye **retries, timeouts, aur larger/stronger models** production reliability ke liyer matter karte hain. Aur **distributed tracing** (yahan OpenAI traces) tumhara best friend hai jab system multiple services (App Runner → Lambda → SageMaker → S3) mein faila ho — ek hi jagah pura request journey dikhta hai, bilkul Jaeger/Zipkin/Datadog APM jaisa.

---

## ✅ Takeaway

- `uv run deploy.py` → image ECR par push; phir **full `terraform apply`** → App Runner live (~8 min)
- Test sequence: **cleanup** (clean slate) → **`test_research.py`** (agent research + ingest) → **`test_search.py`** (verify vectors)
- App Runner par **~2-min timeout** + **Nova hit-or-miss** = kabhi bad-gateway/timeout; retry ya OSS/Claude use karo
- **OpenAI traces** (platform.openai.com → Logs → Traces) mein `browser_navigate/click/snapshot` aur end mein `ingest_financial_document` dikhta hai — pura agent flow ka replay
- End-to-end chain proven: research → ingest → SageMaker embed → S3 vectors → searchable

---

<details>
<summary>📜 Full Transcript (English)</summary>

So to run the deploy script that we just looked at, we now go to the backend CD backend and the researcher directory. There it is. And we type UV run deploy.py. And this is going to kick off the script we were just looking at. It gets the AWS account details I don't know if you saw that. And there it is. It then finds the ECR URL. It's too quick for me. Let's scroll up. It's now running the docker build using the Docker. Uh, the file that we looked at, the docker file, the recipe for what's to happen. And you can see that it carried out all the steps we looked at installing node, installing uh, pip install UV right there and installing playwright with chromium. It's all happening. Uh, this, um, warning can be safely ignored. Uh, and now it is off building our building our container, which it will upload then to ECR. It's pushing the image to ECR as we speak. So we will let it do that, and I will come back in a minute when it's complete, and we will then be ready to do our Terraform apply. Okay, so after some time that that eventually completes successfully and we're on to the final step of doing our Terraform apply. So let's do that. Let's open up a new terminal. Go back to our setup instructions. Here we have them. So it's time for us. Now that we've deployed it's now time for us to go into Terraform. See Terraform into the for directory and run the full Terraform apply. We no longer restrict this by some targets. We want to deploy everything we say. Yes, and off it goes. It's doing its deploy. And, uh, in a second we should have ourselves a new service. So I will check back in in a second. It'll be a second for you, but it might be a bit longer for me. And I'll talk to you then. And there we go. It did take a few minutes, but it was successful. Here we go. Let's see exactly how long it took. It took seven, almost eight minutes to complete that deployment, but it it created it's finished. And we have a URL and and it's it's been created. Uh, it says it takes 3 to 5 minutes. Uh, mine took more like eight. And now it's time for us to test this full pipeline of research to ingest, to search. So get ready for some testing. All right. So I'm going to open a new window. And so first of all we are going to go back to the uh um back end ingest directory. So CD backend CD ingest. And we're going to run this cleanup script. If you remember this UV run cleanup S3 vectors. And this is going to delete everything I say. Yes. Let's go ahead and delete everything. And I'm not sure if I covered the cleanup script before or not, but this is the one that wipes out the database completely and makes sure it's all empty. I think I did run it just to show you before how it how it created it successfully. Deleted three. Let's let's run it again just to be absolutely sure. It should say successfully deleted. It says no vectors found. Database is already empty. Excellent. All right. Now it is time for us to test our research. Very exciting. I feel like I've not used the word moment of truth, the expression moment of truth for a while. And I feel like this is a moment of truth. So I deserve to be allowed to say it. Uh, so we should now go to the back end researcher directory. So we go up one directory and we go into researcher. There it is. We're now in the researcher directory. And we are going to run UV run test research. Let's give this a shot. Test research dot pi. Off it goes. So it's getting the app runner service. It got the URL. It's healthy. It's now generating research for uh whatever the agent would like to generate research for. It's doing a trending topic. And so it says it will take 20 to 30s. In my experience it sometimes takes longer. And now of course I am using the Nova model and I should say right up front, that Nova model isn't as strong as the OSS model or as Claude, if you're using either of those. And so this is a little bit hit or miss. Sometimes using Nova, it usually seems to work, but just occasionally it goes a bit wrong with its tool calling. But let's see what happens here. It's right now this agent is running. It's spawning an MCP server, it's loading a playwright browser, it's doing some navigation, it's collecting some news. And when it's collecting that news, it's going to use a tool to call the ingest function to then save that news in our vector store. So all of that is happening while I'm talking. And it's definitely taking longer than 20 to 30s. Uh, but hopefully it is about to wrap up. All right. I'm going to have to, uh, to, to to break for a second while I let it think I'll be right back. And I would love to say to you. And that just worked just as soon as I stopped. But it didn't. It waited for a couple of minutes and then it failed with some timeout error, and I ran it a second time. This is the first time it failed with with a bad gateway for URL, which I think is like a long time out. I ran it the second time and it ran fine. So, uh, this is because using Nova is a bit hit and miss. It's not such a big model. Uh, but, uh, I'm very hopeful that you'll be able to use OSS 120. If not, you can also use Claude, should you wish, or any of the larger models, and you'll probably have a rather more successful run of it than me. I seem to get like, I don't know, maybe, maybe it's a bit bit more than 50 over 50 of a result. But anyway, it did just run. And so now we can actually test to see whether or not we've got it in our knowledge base. So to see whether it is, we have to go back into the back end ingest directory. So up one and go into ingest. And now we're going to run this test search S3 vectors. And remember we had emptied our S3 vectors a moment ago. So it was empty. We've now run our researcher. It's gone off to try and find trending topics. And there we can see that there are indeed there is some stuff in there in our knowledge base, in our vector store. This was created by our researcher. It's it's a it's a lot going on. I hope you're following. Uh, and hopefully you're seeing this too. And you're seeing the researcher generating coming up with information through the agent flow and then putting that into the knowledge base through the ingest function. And if you're not sure what's going on or you don't believe me, there's another place where you can find out what's going on. And that is by going to the traces page in OpenAI's platform. So this is a platform openai.com. Or you get to it by clicking on logs, and then you click on traces up here. And you see the traces and you'll see my earlier experiments there. You can look the other way for that, but you'll see these latest two, which are the ones that I just run. This is the one that actually timed out. I guess there's like AA2 minute timeout. Uh, on on the, on the, on that, that uh, app service. Uh, but this one did run in time after 80s. Let's go into it and you'll see that it used, uh, got the list MCP tools, it used browser navigate. Uh, browser navigate again browser, click browser handle dialog browser click. So it was going along. It took a snapshot. There's more to be done here. Uh it really did go to town here. And then at the end it called the Ingest Financial Document tool. And you'll see that that tool is something which calls our ingest function and meant that we we followed the ingest flow. So that's how it all fits together. And this is where you should dig in, bring up the traces, look through this. Satisfy yourself about what's going on. We can probably make it make less of a meal out of this by being tighter on the prompts and tell it you know, only visit one page or something. Just make sure that it doesn't doesn't go all around the houses like this. Uh, but this is where you really get a feel for what's actually happening. Uh, behind the scenes, as our researcher agent uses its MCP tool to to dig around the internet and do some research.

</details>
