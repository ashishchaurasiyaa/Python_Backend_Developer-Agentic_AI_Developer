# L42 — Configuring AWS Lambda and S3 for Production LLM Memory Storage

> **Week 2 · Day 2** · ⏱️ ~8 min

---

## 🎯 TL;DR

Lambda ka **timeout 3s → 30s** badhate hain (LLM ke liye), ek **test event** (`/health`) se function verify karte hain, phir **globally-unique S3 memory bucket** (`twin-<account_id>`) banate hain, env var update karte hain, aur Lambda ki **execution role** ko **AmazonS3FullAccess** dete hain taaki function S3 access kar sake.

---

## 🗣️ Hinglish Explanation

L41 mein humne `twin-API` Lambda banaya, code upload kiya, handler set kiya, aur 4 env vars daale. Ab function ko **chalne layak** banate hain (timeout fix), **test** karte hain, aur **S3 memory** properly set up karte hain.

### Recap: 4 env vars confirm

Pehle confirm karo ki chaaron env vars sahi set hain:

```text
OPENAI_API_KEY = sk-...
CORS_ORIGINS   = *
USE_S3         = true          # lowercase t
S3_BUCKET      = twin-memory   # abhi placeholder — is lecture mein badlega
```

### Step 1: Timeout 30 seconds karo

> **Lambda timeout** = max time ek invocation chal sakti hai, uske baad AWS use kill kar deta hai. Default sirf **3 seconds** hai — jo ek **LLM response ke liye bahut kam** hai. Agar timeout 3s rahega toh function obscure errors ke saath fail karega, aur debug karna painful hoga.

1. **Configuration** → **General configuration** → **Edit**.
2. **Timeout** → **30 seconds** → Save.

(Ed yeh on-camera nahi karta kyunki env vars page secrets dikha sakta hai — par General configuration khud secrets nahi dikhata, sirf Environment variables tab dikhata hai.)

### Step 2: Test event banao — `/health`

Function ko bina frontend ke test karne ke liye Lambda ka built-in test feature use karte hain.

1. **Test** tab → **Create new event**.
2. Event name: e.g. `health-check` (Ed `health-check-3` use karta hai kyunki pehle bana chuka).
3. Ek **JSON event** paste karo — yeh AWS ko batata hai ki kaisa request simulate karna hai. Bottom line: yeh hamare FastAPI ke **`/health`** route ko hit karega. (API Gateway-style HTTP event shape):

   ```json
   {
     "version": "2.0",
     "routeKey": "GET /health",
     "rawPath": "/health",
     "requestContext": {
       "http": { "method": "GET", "path": "/health" }
     }
   }
   ```

4. **Save** → **Test** dabao.

Kya hota hai jab tum Test dabate ho:
- AWS yeh JSON Lambda ko deta hai → Lambda function launch hota hai → **FastAPI server start** hota hai (Mangum ke through) → **`/health` route** hit hota hai → response milta hai → function shut down.
- Output: **status `healthy`** (aur kaunsa model use ho raha hai — wo info future ke liye, abhi ignore karo).

Agar healthy signal mile — **kaam kar gaya**. Sirf "I'm healthy" kehne ke liye bahut mehnat lagi, par sab fine hai. Agar healthy nahi mila: **patience rakho**, alum se poocho, sirf Cursor par mat depend karo, khud debug karo — *"that is where the hardest learning happens."*

### Step 3: S3 memory bucket banao — globally unique naam

> **Important S3 quirk:** bucket names **globally unique** hote hain across **saare AWS accounts** — namespaced-to-account nahi. Matlab agar Ed ne `twin-memory` bana liya, toh tum nahi bana paoge ("bucket already exists" error). Isliye har kisi ko ek **random suffix** chahiye.

Common trick: suffix = **apna AWS account ID** (bahut unlikely ki kisi aur ne `twin-<your_account_id>` banaya ho). Agar phir bhi clash ho, koi aur random suffix.

1. Region confirm karo — top-right par dekho (Ed ke liye **us-east-1**). **Lambda ke same region** mein bucket banana zaroori hai.
2. **S3** service → **Create bucket** → **General purpose bucket**.
3. Bucket name: **`twin--<account_id>`** (Ed `twin--` + account ID use karta hai — account ID console mein click→Copy se mil jaata hai).
4. Baaki sab defaults → **Create bucket**.

Bucket ban gaya: `twin-<account_id>` (memory ke liye).

### Step 4: Env var update karo — final bucket naam

Ab Lambda ko batao ki memory kahan hai:

1. Lambda → `twin-API` → **Configuration** → **Environment variables** → **Edit**.
2. **`S3_BUCKET`** ki value `twin-memory` (placeholder) se **final bucket naam** (`twin-<account_id>`) mein badlo → Save.

(Ed off-camera karta hai kyunki yeh page baaki secrets bhi dikhayega.)

### Step 5: Lambda execution role ko S3 permission do

Yeh wo cheez hai jo log AWS ke baare mein "infuriating/pernickety" maante hain. **Lambda function khud bhi ek IAM principal hai** — uske paas ek **execution role** hoti hai jab wo chal raha hota hai. Yeh role par **S3 access permission** hona zaroori hai, warna `get_object`/`put_object` AccessDenied karenge.

> **Execution role** = jab Lambda execute hoti hai tab use jo identity/permissions milti hain. Yeh tumhare IAM **user** ke permissions se alag cheez hai. Tumhare user ko S3 access ho sakta hai, par **function** ko alag se chahiye.

1. Lambda → `twin-API` → **Configuration** → **Permissions**.
2. **Execution role** par click karo (yeh wo role hai jo running ke time milti hai). Kuch cheezein "can't see" dikhe toh ghabrao mat — jo dikhta hai wahi matter karta hai.
3. Right side → **Add permissions** → **Attach policies**.
4. **AmazonS3FullAccess** search karo → tick → **Add permissions**.
5. "Policy was successfully attached to the role" — ho gaya. Ab Lambda ko **running ke time S3 use karne ki permission** mil gayi.

Ed yise "voodoo / biology" bolta hai — bahut kuch yaad rakhna padta hai, par yeh standard AWS pattern hai. Step complete.

---

## 📋 Key Concepts

| Concept | Matlab |
|---|---|
| **Lambda timeout** | Max invocation time; default 3s LLM ke liye kam — 30s karo warna obscure failures |
| **Test event** | Lambda ka built-in tester — JSON event se `/health` hit karke verify |
| **`/health` flow** | Event → Lambda launch → FastAPI start (Mangum) → `/health` → `status: healthy` → shutdown |
| **S3 global naming** | Bucket names saare accounts mein unique — account-ID suffix se uniqueness |
| **`twin-<account_id>`** | Memory bucket ka final unique naam; Lambda ke same region mein |
| **`S3_BUCKET` env update** | Placeholder se final bucket naam — Lambda ko memory location batana |
| **Execution role** | Lambda ki apni runtime identity — user permissions se alag |
| **AmazonS3FullAccess on role** | Bina iske function ka S3 access AccessDenied karega |

---

## 💼 Backend Dev Ke Liye Note

Do cheezein backend engineering ke core lessons hain. **(1) Timeout config**: serverless mein default timeouts aggressive hote hain — LLM/long-running calls ke liye explicitly badhao, aur saath hclient-side/API-Gateway timeout bhi align karo (API Gateway ka apna 29-30s cap hota hai, isliye 30s sweet spot hai). Yeh wahi discipline hai jo tum apne HTTP client/uvicorn worker timeouts mein lagaate ho. **(2) Workload identity / execution role**: yeh shayad sabse important cloud-security concept hai jise backend devs miss karte hain — **compute khud ek principal hota hai**. Lambda → S3 access tumhare user creds se nahi hota; function ki **execution role** se hota hai (yeh AWS STS temporary credentials inject karta hai, koi hardcoded key nahi). Yeh "machine identity" pattern hi sahi tareeka hai — code mein AWS keys mat daalo; role attach karo. Same concept ECS task roles, EC2 instance profiles, GKE workload identity, etc. mein milega. Aur **least-privilege**: yahan `S3FullAccess` shortcut hai; production mein role ko sirf ek specific bucket par `s3:GetObject`/`s3:PutObject` dena chahiye.

---

## ✅ Takeaway

- Lambda **timeout 3s → 30s** karo (Configuration → General) — LLM responses ke liye must, warna obscure failures.
- **Test event** (`/health` JSON) se function verify karo — `status: healthy` milna chahiye; nahi mile toh patiently debug karo.
- S3 bucket names **globally unique** hain — **account ID suffix** lagao (`twin-<account_id>`), aur **same region** mein banao.
- `S3_BUCKET` env var ko final unique bucket naam se update karo.
- **Lambda execution role** ko **AmazonS3FullAccess** do — compute khud ek IAM principal hai, bina permission ke S3 access fail hoga.

---

<details>
<summary>📜 Full Transcript (English)</summary>

Okay, so you promised me you set those four environment variables open API key cause origins to star use S3 underscore capital true lowercase t, or like that S3 bucket twin dash memory. And we are going to come back and change that later, uh, as you will see. All right. Next step is to increase the timeout. So configuration general configuration edit and set the timeout to 30s. Now I can't do this while you watch because I do believe that going there is going to show my environment variables. You'd see my OpenAI API key which is a top secret. So I'll have to trust you to do that yourself. Uh, but what we will do together is the next section in just a second. So be ready to go. We are going to, uh, create a new test event from the test tab, and we are going to run this JSON. So I'm going to copy this in. And then I'm going to go and set my timeout as it's instructed. And see you in a second. Oh no I'm totally wrong. You can go to configuration and doesn't show my secrets yet. I'd have to click on environment variables for that. So configuration general configuration. You can see the default is a three second timeout which is mean and which is not enough for an LLM to respond. So this would cause it to fail. So you need to know to come in and change that timeout to be 30s. If you forget to do that, then it will fail with obscure errors and it will be so hard to know what's going wrong. All right. And now we go over to test. We're going to to create a new event. And the event name will be like I don't know, like health check. I've already created a couple of these. So I'm going to make it like health Check three. But you can just call it health Check. And we're going to to paste in some JSON, which is it tells AWS how to to do this test what we need it to do. But basically the bottom line is we're going to call health, which is one of the routes that our fast API server runs. Uh, and so we've done that. And I'm going to to save this so that we've saved it. That test event was successfully saved. And now I'm going to press test. So what's this going to do. It's going to take this this JSON. And it's going to to apply that to AWS. And what that will do is it will launch our Lambda function. It will start a fast API server. It will hit this route slash health, it will get back the response and then and then shut down that lambda function. All of that's going to happen when I press the test button. Executing function started zero seconds ago succeeded details and it said status healthy. Uh, that's and it also tells us what, uh, what model it's using. But that's, that's from uh, coming in the in the future you can ignore that until later when we get on to that. Um, but uh, the, um, the point is, this works. It might seem like an awful lot of effort just to make something say it's healthy. Uh, it has been a little bit of effort, but, uh, but things are looking good. We're in fine shape. If you haven't got a healthy signal, then I'm sorry. Uh, ask an alum. Stop asking. Cursor. Do some digging. in, debugging, tracking these things down. That is where the hardest learning happens, where the real learning happens. As you go through the pain of solving these problems, you'll get better and better. So, uh, yes, stay patient. That's the most important thing. All right, on with the instructions. We're now moving on to our next Amazon service. And it's going to be our S3 buckets. Now there's something tiresome about S3 buckets, which I guess is probably an advantage in the grand scheme of things. It's that bucket names the name that you give to each of your buckets. They are they are global. They are something which, uh, at least, uh, yeah. Which, uh, anyone can access that bucket. It's not like it's, it's namespaced to your account ID or something like that. So you can't we can't just call these buckets like twin memory, because otherwise, when I've made twin memory, you wouldn't be able to. It would tell you that bucket already exists. So you have to make these things and add on some random ending to it, which is going to be different so that everyone has a different one. Otherwise it's going to error. And once we've done that, we're gonna have to go back and update the environment variable to tell our lambda function where our memory is. What a what a palaver. Uh, now, a typical common trick is to use as the random suffix your account ID, because chances are no one else is going to have called something twin memory and then your AWS account ID. But if you do that, and it turns out somebody has for some reason, uh, then you'll have to come up with some other random suffix. So, uh, but but start with your account ID so we're going to go to S3, we're going to create a bucket and we're going to call it twin dash dash and then some suffix. We're going to make absolutely sure that it's in the same region as our lambda function as everything else. So here we go. We're back in the console. You can always see your region up here by going here to check that we're in US East one for me. And now I'm going to look at S3. I type S3 here scalable storage in the cloud. And here it is I've got a bunch of of of buckets. Oh, I meant to delete that one. Let's leave that one there for now. And, uh, going to create a new bucket. Here we go. Create bucket. General purpose bucket is what we want. Bucket name. So this is where we need to call it twin dash API. Sorry. Twin dash dash. And then give it the name of your account ID which you can quickly access by clicking here. Pressing copy there isn't that convenient. And paste it in there. We're probably not the first people to want the account ID in our bucket name. Uh, and then everything else should be fine. Everything is good. And then create bucket. That's all there is to it. We are now the proud owners of twin Dash. And then our account ID. Very good. Back we go. Next we're going to go to the environment variables and update that S3 bucket environment variable. It used to be called just Twin Memory, and you now need to call it the final name you just came up with. Twin memory. Account ID or whatever. So I'm going to do that because that would definitely show my environment variables and see you back here in a second. Now this next step is the kind of thing that infuriates people about AWS and how pernickety it is about the, the, the IAM about access. We have to make sure that our lambda function, our lambda function has permission to use S3. Now, that might sound completely screwy to you. It might be like what permissions are for humans, but no lambda functions themselves are in there with a role and they have to have permission to access S3. So we're going to have to go to our Lambda function and configure it so that when it's executing, that's a special role it has when it's running that needs to have permission to access Amazon S3 full access. So let's do that. We go back to our uh we're looking in Lambda right now I've gone to Lambda and we're looking at twin API configuration permissions over here. And now you have to know to click on this execution role. That is the thing that is the role of what it will have when it is executing. I realize this sounds crazy complicated. Don't worry that we're being told we can't see some things. What we can see is what matters. That we can add permissions over here on the right. Add permissions. Attach policies. This stuff is some voodoo. This is. This is what I mean by biology. There's so much to learn and remember. But now we have to do this. Amazon S3 full access. We tick here add permission policy was successfully attached to the role. You can see it there. And by the magic of AWS we have just given our Lambda function the permission when it's running when it's executing to use S3. Uh, but uh, it's complicated. So that's the next step. Complete.

</details>
