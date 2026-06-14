# L82 — Testing Your AWS Lambda Vector Ingest Pipeline End-to-End

> **Week 3 · Day 4** · ⏱️ ~6 min

---

## 🎯 TL;DR

Deployed ingest pipeline ko **end-to-end test** karte hain: pehle `test_search` chala ke confirm karte hain ki store khaali hai, phir `test_ingest` se teen documents (Tesla, Amazon, Nvidia) push karte hain, aur dobara `test_search` se confirm karte hain ki tinon vectors mil rahe hain. Day 4 complete — full ingest pipeline (API Gateway + key → Lambda → SageMaker → S3 Vectors) live, course 70% done.

---

## 🗣️ Hinglish Explanation

### Setup: ek warning + test scripts

Pichle lecture mein humne `.env` set up kiya. Ek **important reminder**: har baar jab tum step-3 (`3_ingestion`) ko dobara deploy karte ho, ek **naya API key** generate hota hai. Toh redeploy ke baad `.env` mein latest endpoint + API key dobara daalna padega (warna purani key se 403/auth-fail aayega).

Ab test scripts — `backend/ingest/` folder mein:

| Script | Kaam |
|---|---|
| `test_ingest_s3_vectors.py` | Documents ko ingest endpoint ke through push karta hai |
| `test_search_s3_vectors.py` | S3 Vectors mein search karke dekhta hai kya stored hai |
| `cleanup_s3_vectors.py` | Sab kuch delete karke fresh start (optional) |

### Step 1: Pehle SEARCH (confirm: khaali hai)

Guide bolta hai pehle ingest karo, par Ed ulta karta hai — pehle **search** karke prove karta hai ki store empty hai (taaki baad mein populate hona clearly dikhe):

```bash
cd backend/ingest
uv run test_search_s3_vectors.py
```

Output:

- "List all vectors" → **koi vector nahi** (none)
- Kuch sample searches (e.g. *"electric vehicles"*, *"sustainable transportation"*) → **no results, nothing**

Yeh expected hai — store abhi-abhi freshly created hua hai, khaali hai.

### Step 2: INGEST (teen documents push karo)

```bash
uv run test_ingest_s3_vectors.py
```

Yeh test script kya karta hai:

1. Ingest endpoint (API Gateway → Lambda) ko **call** karta hai (API key ke saath)
2. **Teen documents** push karta hai:
   - **Tesla Inc.** ke baare mein text
   - **Amazon** (multinational technology company) ke baare mein text
   - **Nvidia** ke baare mein text
3. In tinon ko Lambda pipeline ke through pump kiya jaata hai

Pipeline mein har document: API Gateway (key check) → `ingest` Lambda → SageMaker endpoint (text → 384-dim vector) → **S3 Vectors** mein store.

Run hone par output "appeared to run" — abhi confirm karna baaki hai ki sach mein store hua.

```python
# test_ingest_s3_vectors.py (reconstructed shape)
documents = [
    "Tesla Inc. is an American electric vehicle and clean energy company...",
    "Amazon.com is a multinational technology company...",
    "Nvidia Corporation is a technology company known for GPUs...",
]
for doc in documents:
    requests.post(
        ALEX_API_ENDPOINT,
        headers={"x-api-key": ALEX_API_KEY},   # API key auth
        json={"text": doc},
    )
```

### Step 3: Dobara SEARCH (confirm: ab data hai)

```bash
uv run test_search_s3_vectors.py
```

Ab output badal gaya:

- **Teen results** mile — Amazon.com, Nvidia Corporation, aur Tesla
- Har query par teen-teen results (kyunki total sirf teen vectors hain, similarity search sab return kar deta hai)

**Test PASS!** Pipeline kaam kar raha hai.

### Kya saabit hua — full pipeline working

Ed summary deta hai. Humne successfully deploy kiya:

1. **ingest Lambda** — text ke saath call ho sakta hai
2. Call hone par → **SageMaker endpoint** call karta hai → text ko **vector** banata hai
3. Vector ko **S3 Vectors** data store (Alex bucket) mein store karta hai
4. Upar **API Gateway** with **API key** — security + scalability constraints (sahi resource usage)
5. Sab **Terraform se automatically deployed** = bulletproof way

### Architecture diagram (guide mein)

Guide mein neeche ek **detailed architecture diagram** hai (slides wale simple version se zyada detail):

```
[Client / test script]
        │  (calls with secret API key)
        ▼
[API Gateway]  ──(API key auth, quota, throttling)──►
        │
        ▼
[ingest Lambda]  (zip locally banaya, upload kiya)
        │  (invokes)
        ▼
[SageMaker endpoint]  (all-MiniLM-L6-v2  →  384-dim vector)
        │
        ▼
[S3 Vectors  —  Alex bucket]  (vector stored)
```

Flow: client (yahan test script) API Gateway ko secret key ke saath call karta hai → Gateway Lambda ko call karta hai → Lambda SageMaker endpoint ko call karta hai (384-dim vector banta hai) → vector S3 Vectors mein store. **Yahi hamara data ingest pipeline hai.**

### Day 4 complete — aur aage kya

> **Week 3, Day 4 done.** Ingest pipeline taiyaar: Lambda → SageMaker (vectorize) → S3 Vectors. Course **70%** complete (Ed mazaak karta hai ki abhi to 20% jaisa lag raha tha!).

**Kal (Day 5)** — pipeline ko ek step aage: ek **agent** add karenge jo **data gather** karega. Yeh agent **Playwright MCP server** use karega internet se data lene ke liye, phir us data ko **ingest Lambda** ko bhejega — yaani **end-to-end data pipeline**. Ed data engineers ko tease karta hai: ETL tooling se aur bhi extend kar sakte ho — kal isspe baat hogi.

---

## 📋 Key Concepts

| Concept | Matlab |
|---|---|
| **`test_search_s3_vectors.py`** | S3 Vectors mein search/list karke dekhta hai kya stored hai |
| **`test_ingest_s3_vectors.py`** | Documents (Tesla/Amazon/Nvidia) ingest endpoint se push karta hai |
| **`cleanup_s3_vectors.py`** | Sab vectors delete — fresh start ke liye |
| **API key per deploy** | Har `3_ingestion` redeploy par naya key; `.env` update karna padta hai |
| **End-to-end flow** | client → API Gateway (key) → Lambda → SageMaker (384-dim) → S3 Vectors |
| **Similarity search** | Cosine se closest vectors return; sirf 3 vectors the toh queries 3 return |
| **Architecture diagram** | Guide mein full pipeline ka detailed visual (slides se zyada) |

---

## 💼 Backend Dev Ke Liye Note

Yeh lecture ek textbook **integration test** strategy dikhata hai jo har backend dev ko aani chahiye: **arrange-assert-act-assert**. Ed pehle `search` chalake **empty state assert** karta hai (clean baseline), phir `ingest` se data daalta hai (act), phir dobara `search` se **populated state assert** karta hai. Yeh "before-and-after" pattern flaky/false-positive tests se bachata hai — agar tum sirf ingest-then-search karte aur 3 results aate, tumhe pata nahi chalta ki vo abhi aaye ya pehle se the. `cleanup` script tumhara test teardown/fixture-reset hai. Production lens se: yeh teen scripts effectively tumhare **smoke tests** hain jo deploy ke baad chalte hain — exactly jaise CI pipeline mein tum post-deploy health-check/smoke-test stage rakhte ho. Aur API-key-per-deploy ki gotcha note karo: ephemeral credentials wale systems mein test config ko deploy ke baad refresh karna ek classic operational footgun hai — automation mein isse handle karna padta hai (e.g. test script khud `terraform output` se key padhe, hardcode na kare).

---

## ✅ Takeaway

- **Test pattern**: pehle search (empty confirm) → ingest 3 docs (Tesla/Amazon/Nvidia) → dobara search (3 results confirm) = before/after assertion
- **API key har deploy par naya** banta hai — `3_ingestion` redeploy ke baad `.env` refresh karna mat bhoolo
- Full pipeline live aur bulletproof: **client → API Gateway (key) → Lambda → SageMaker (384-dim) → S3 Vectors**, sab Terraform-deployed
- `cleanup_s3_vectors.py` se fresh start; teen scripts effectively post-deploy **smoke tests** hain
- **Day 4 complete, course 70%** — kal Day 5: Playwright MCP wala research **agent** jo internet se data gather karke ingest Lambda ko feed karega (end-to-end pipeline)

---

<details>
<summary>📜 Full Transcript (English)</summary>

Okay, I have done that and I hope you have too. And remember, every time that you do this deploy in step three, it is going to recreate another API key. So you would have to do that again with the latest endpoint and API key. But now it is time for us to test test what's happened and make sure that this works by running some test scripts. And the test scripts are in the back end folder in ingest. There's a there's a couple of scripts we'll use test ingest S3 vectors is going to run a test for us and then test search S3 vectors is going to search to see what's in there. And there is also another little one here that might be useful called cleanup S3 vectors that will delete anything that's there if you want to start absolutely fresh. Uh, so uh, I am going to begin now. And actually it suggests that you start by doing an ingest. But I suggest that we start by doing a search to make absolutely sure that it's going to be empty to start with, and then it's going to be populated. So before I do anything, I'm going to begin by running UV run test search S3 vectors just to show you what we get. If we run this, it's found no results at all. You can see if we just look at this. It lists all vectors. It's found none. And then it does some searches for a few to see what's closest to electric vehicles and sustainable transportation. And it finds no results, nothing for any of these topics. Uh, and it found nothing here, which is what we'd expect, because it's all just been freshly created. Okay. So now we're going to run this UV run test, ingest S3 vectors. Let's just look at what this test does. Look at it here. So it is going to uh call call our uh our endpoint and ingest a document. And uh, let's just see what it's going to ingest. It's going to ingest some text about Tesla Inc, Ink, some text about Amazon, a multinational technology company, and some text about Nvidia. So those three documents are going to be pumped through our Lambda endpoint to see whether or not those end up in our S3 vectors data store. So with that, it's time for us to do UV run test ingest S3 vectors. Let's give this a shot. Well something happened. It appeared to run. Now we see whether it's actually there. Okay, so now we're going to run test search S3 vectors again and see if we find any information about any of those topics. Well we do. You can see right away. That's cool. So uh, when we got back results, it found three results. Uh, it found the Amazon.com stuff, the Nvidia corporation and the Tesla. Uh, and you can see, since we only had three vectors in there that it found That for? For each of them. So, uh, that's that's great. Uh, uh. Test worked. We have successfully deployed now a lambda function. That's our ingest lambda function that can be called with text. And when it's called with text, it will then go off to our SageMaker endpoints. It will turn the text into vectors. And it will store those vectors in a vector data store in S3 vectors a bucket that we have there. And on top of this we have this API, this this gateway that has an API key. And it has various scalability constraints to make sure that we we use the right amount of resources. So this has been deployed in a bulletproof way. It's been automatically deployed using Terraform. And our test scripts have worked well. So so far we're in great shape. And if you scroll a little bit down in the guide, in the setup guide you'll see there's also an architecture diagram. That's again a slightly more detailed version than the simplistic one on. On the slides you can see that we've got our client, which in this case is just a test script, is calling the API gateway using a key that we've set up, a secret key, which is our way of adding security to this process. And that is then calling a lambda function that we deployed. We created a zip locally and uploaded that zip. That lambda function is able to call a SageMaker endpoint that we configured. That's using the all mini lm, l6 v2 model, which then creates 384 dimensional vectors representing the text that it's called with, and that that vector is then stored in S3 vectors in our Alex bucket. Uh, and uh, that is our data ingest pipeline put together. Well, this is great. It's all coming together. That is day four complete. Uh, week three, day four. We have just built our ingest pipeline with, uh, being able to call a lambda function that we use to get some data in and vectorize it by calling SageMaker endpoint, and then putting that vector into S3 vectors data store. And tomorrow we take it a step further by adding in the source of our data, an agent that's able to gather data. It will be using an MCP server to do that. Playwright MCP server getting data. It will be then sending that data to our ingest lambda function. And that's really going to put together this kind of end to end data pipes. And the data engineers amongst you will be thinking of all sorts of ways you could add to that with things like ETL tooling that hopefully we'll talk about briefly. So tomorrow's a big day. I can't wait for it. But first we should celebrate that we are 70% of the way through 70% on the way to production expertise. I felt like just the other day we were like 20% and now it's it's we're somehow soon be approaching the end game. So but but not before a really meaty day. I have in store for you tomorrow and I'll see you then.

</details>
