# L40 — Migrating AI Chat Apps from Local Storage to AWS S3 and Lambda

> **Week 2 · Day 2** · ⏱️ ~11 min

---

## 🎯 TL;DR

Hum apne FastAPI backend ko refactor karte hain taaki conversation memory **local file system** ke bajaye **AWS S3** mein store ho (Boto3 client se), aur app ko **Mangum** se wrap karke **Lambda-ready** banate hain — phir env aur **IAM permissions** (Twin Access group) set karke AWS deployment ke liye taiyaar.

---

## 🗣️ Hinglish Explanation

Yeh Week 2 Day 2 ki ek lambi build-out series ka pehla lecture hai jisme hum apne "digital twin" chat app ko **purely local prototype** se **AWS production architecture** par migrate kar rahe hain. Plan yeh hai: code ko cloud-aware banao, phir AWS environment (IAM → Lambda → S3 → API Gateway → CloudFront) step-by-step khada karo. Yeh lecture pehle do hisson ko cover karta hai — **(1) backend code update** aur **(2) AWS environment ki shuruaat (IAM)**.

### Pehle samajh lo: ye services hain kya?

- **AWS S3 (Simple Storage Service)** — cloud par **object storage**. Tum "buckets" banate ho, aur har bucket mein **objects** (files) rakhte ho, har object ki ek **key** (path/naam) hoti hai. Yeh file system jaisa lagta hai par actually flat key-value store hai. Highly durable (99.999999999% durability), cheap, aur API se accessible. Hamare app mein har user conversation ek JSON object banega, key hogi `session_id.json`.
- **AWS Lambda** — **serverless compute**. Tum ek function (code) upload karte ho, AWS use tabhi chalata hai jab request aati hai. Koi server provision/manage nahi karna; pay-per-invocation. Idle mein zero cost. Yeh hamare FastAPI server ko host karega.
- **Boto3** — AWS ki official **Python SDK**. Iske through tum Python code se S3, Lambda, etc. ke APIs call karte ho (e.g. `s3_client.get_object(...)`).

### Step 1: `requirements.txt` update

Sabse pehle backend ke dependencies update karo. Bas thode additions — do AWS packages aur **pypdf** (PDF parsing ke liye, taaki baad mein PDF files se context nikal sakein):

```text
fastapi
uvicorn
openai
boto3
pypdf
mangum
```

- **boto3** → AWS API access ke liye Python library
- **pypdf** → PDF files parse karne ke liye
- **mangum** → FastAPI/ASGI app ko Lambda ke andar chalane ke liye adapter (Step 3 mein detail)

Cursor mein `requirements.txt` kholo, sab select karo, naya content paste karo, save.

### Step 2: `server.py` update — S3-aware memory

`server.py` ka naya version paste karo. **Core logic same hai** — abhi bhi OpenAI client use kar rahe hain (`GPT-4.1 mini` model par wapas set kar do; agar tum koi aur provider use kar rahe ho toh apna client rakho). Naya kya hai? Kuch **environment variables** aur **S3-backed conversation storage**.

Naye env variables:

```text
USE_S3       # "true" / "false" — S3 use karna hai ya local file system
S3_BUCKET    # jis S3 bucket mein memory store hogi uska naam
```

Boto3 se S3 client banta hai:

```python
import os
import boto3

USE_S3 = os.getenv("USE_S3", "false").lower() == "true"
S3_BUCKET = os.getenv("S3_BUCKET")

s3_client = boto3.client("s3")

def get_memory_path(session_id: str) -> str:
    # key = "<session_id>.json" — object ka naam S3 mein, ya local file ka path
    return f"{session_id}.json"
```

**`load_conversation` updated** — agar `USE_S3` true hai toh S3 se object laao, warna local file padho:

```python
import json

def load_conversation(session_id: str) -> list:
    key = get_memory_path(session_id)
    if USE_S3:
        try:
            response = s3_client.get_object(Bucket=S3_BUCKET, Key=key)
            return json.loads(response["Body"].read())
        except s3_client.exceptions.NoSuchKey:
            return []
    else:
        # local file system fallback
        if os.path.exists(key):
            with open(key) as f:
                return json.load(f)
        return []
```

Yahan `get_object` ko **bucket name + key** dete hain, aur wahi object (conversation history) wapas aata hai.

**`save_conversation` updated** — pehle local file likhte the, ab `put_object` se S3 mein daalte hain:

```python
def save_conversation(session_id: str, messages: list) -> None:
    key = get_memory_path(session_id)
    if USE_S3:
        s3_client.put_object(
            Bucket=S3_BUCKET,
            Key=key,
            Body=json.dumps(messages),
        )
    else:
        with open(key, "w") as f:
            json.dump(messages, f)
```

Ed ka point: **baaki sab same hai**. Sirf conversation history retrieve/store karne ka tareeka badla — `get_object`/`put_object` (S3) bnaam local file read/write — wo bhi sirf tab jab `USE_S3=true`. Agar env set nahi hua toh purana code path chalta hai, kuch bhi regress nahi hota.

### Step 3: Lambda handler — `lambda_handler.py` + Mangum

Problem: FastAPI ek **ASGI web server** hai jo continuously port par listen karta hai. Lambda ka model alag hai — har request par ek **handler function** call hota hai (event in → response out), koi long-running server nahi. In dono ko bridge karne ke liye **Mangum** chahiye.

> **Mangum** ek open-source library hai jo ek **ASGI app (FastAPI) ko wrap karke Lambda-compatible handler bana deti hai**. Yeh Lambda ke event (API Gateway request) ko ASGI request mein translate karta hai, app chalata hai, aur response wapas Lambda format mein deta hai. (Ed ke mutaabik naam "The Lawnmower Man" movie se aaya — translation ke theme par.)

Backend mein naya file banao — `lambda_handler.py`:

```python
from mangum import Mangum
from server import app   # hamara FastAPI app object

handler = Mangum(app)
```

**Yaad rakho** yeh do naam — module `lambda_handler` aur variable `handler`. Baad mein Lambda ko batayenge: "is module ke `handler` object ko request servicing ke liye use karo." (L41 mein iska "Handler" setting `lambda_handler.handler` banega.)

### Step 4: Locally verify — kuch toota toh nahi

Deploy se pehle local mein confirm karo:

```bash
# backend directory mein
uv add -r requirements.txt          # naye packages install (AWS wala local use nahi hoga, par pypdf hoga)
uv run uvicorn server:app --reload  # backend server start (command guide se le lo)
```

Phir frontend chalao:

```bash
cd frontend
npm run dev
```

Browser mein app ("AI in production") khulega. Ed test karta hai: "Hi there" → twin jawab deta hai → "my name's Alex" → "what's my name?" → "Alex" — memory kaam kar rahi hai. Kyunki `USE_S3` set hi nahi hai (default false), purana local code path chal raha hai. **Kuch regress nahi hua, par ab AWS-ready hain.** Server aur frontend dono band kar do.

### Step 5: `.env` update — AWS coordinates

`.env` already exists (`OPENAI_API_KEY` ke saath). Usme **naye values ADD karo** (purane overwrite mat karna):

```text
OPENAI_API_KEY=sk-...           # already tha
PROJECT_NAME=twin
AWS_ACCOUNT_ID=123456789012
AWS_DEFAULT_REGION=us-east-1
```

- **`AWS_DEFAULT_REGION`** wahi region hona chahiye jo console ke top-right par dikhta hai (apne ke paas wala). Common choices: `eu-west-1` (Europe), `ap-south-1` (Mumbai, India), `us-west-1`/`us-west-2`, `us-east-1` (Ed ka choice, chahe wo London mein ho). Spelling/hyphens bilkul sahi rakho warna baad mein trouble.
- File **save** karo (white blob mat chhodo), key naam careful rakho.

### Step 6: IAM permissions — "Most Amazon projects start with IAM"

> **IAM (Identity and Access Management)** AWS ka permission system hai. Yeh decide karta hai **kaun** (user/group/role) **kya** (service/action) kar sakta hai. Best practice: principle of least privilege.

Hamare paas do tarah ki identity hai:
- **Root user** — account owner, sab kuch kar sakta hai. Sirf account-level setup ke liye use karo (jaise permissions assign karna).
- **IAM user (`AI engineer`)** — day-to-day kaam ke liye limited user.

Flow (root user ke roop mein login karke):

1. AWS console kholo → **Sign in as root user** (Ed ka naam top par dikhta hai — "editor", "AI engineer" nahi — isse pata chalta hai root mein ho).
2. **IAM** service kholo → left sidebar mein **User groups**.
3. **Create group** → naam `Twin Access`.
4. Group create karte waqt do parts hote hain:
   - **Users attach karo** — `AI engineer` user ke checkbox par tick (taaki yeh group us user par apply ho).
   - **Permissions (policies) attach karo** — search box mein har policy type karke checkbox tick karo. (UI thoda janky hai — OK button nahi hota; bas agla search type karo.)
5. Yeh **managed policies** attach karo:

   ```text
   AmazonAPIGatewayAdministrator     # API Gateway use ke liye
   AmazonS3FullAccess                # S3 buckets
   AWSLambda_FullAccess              # Lambda functions
   CloudFrontFullAccess              # CloudFront (CDN)
   CloudFrontReadOnlyAccess          # (dono CloudFront add kar do — extra, par koi harm nahi)
   IAMReadOnlyAccess                 # IAM read (zaroori hai)
   ```

6. **Create group** → yeh automatically `AI engineer` user se link ho jaata hai.
7. Verify: User groups → `Twin Access` par click → user aur saari policies list dikhni chahiye.

Ed ka honest note: yeh **`*FullAccess` policies** real best practice nahi hain — production corporate setup mein tum **exact minimal permissions** dete ho (kaafi headache). Learning ke liye hum FullAccess use kar rahe hain, lekin idea yeh hai ki IAM user kya kar sakta hai usko in services tak **restrict** kar rahe hain. Ab `AI engineer` user ke paas zaroori powers hain.

---

## 📋 Key Concepts

| Concept | Matlab |
|---|---|
| **S3** | AWS object storage — buckets + keyed objects; hamari conversation memory yahan JSON ban ke store hogi |
| **Lambda** | Serverless compute — request par function chalta hai, idle par zero cost |
| **Boto3** | AWS ka Python SDK — `s3_client.get_object` / `put_object` se S3 access |
| **`USE_S3` / `S3_BUCKET`** | Env vars — S3 toggle aur bucket naam |
| **`get_object` / `put_object`** | S3 se object padhna / likhna (bucket + key) |
| **Mangum** | ASGI→Lambda adapter; `handler = Mangum(app)` se FastAPI Lambda mein chalti hai |
| **`lambda_handler.handler`** | Module + variable jise Lambda request servicing ke liye call karega |
| **IAM** | AWS permission system — kaun kya kar sakta hai |
| **Root user vs IAM user** | Account owner (sab kuch) vs limited day-to-day user (`AI engineer`) |
| **User group + managed policies** | `Twin Access` group jisme FullAccess policies, `AI engineer` user se linked |
| **pypdf** | PDF parsing library (future context extraction) |

---

## 💼 Backend Dev Ke Liye Note

Yeh lecture ek classic **12-factor "backing services" refactor** hai: storage ko code se decouple karke ek env flag (`USE_S3`) ke peeche daal diya. Tumhare `load_conversation`/`save_conversation` ek **repository/adapter pattern** ban gaye — same interface, do backends (local FS vs S3). Yeh testability ke liye sona hai: local mein S3 ke bina dev karo, prod mein flip kar do. **Mangum** ka role samjho — yeh wahi kaam karta hai jo `uvicorn`/`gunicorn` local mein karte hain, par Lambda ke event-driven model ke liye: ek ASGI adapter jo HTTP semantics ko serverless invocation mein map karta hai (cold starts, stateless invocations — ye constraints yahan bhi). **IAM** ko apne app ke RBAC se compare karo, par yaad rakho cloud mein **services bhi principals** hote hain (L42 mein Lambda ki execution role dekhoge). `*FullAccess` shortcut prototyping ke liye theek, par production mein least-privilege scoped policies likhna seekhna — exactly wahi discipline jo tum apne API endpoints ke authz mein lagaate ho.

---

## ✅ Takeaway

- Conversation memory ab **S3-backed** ho sakti hai — `USE_S3=true` par `get_object`/`put_object`, warna local file (zero regression).
- **Mangum** FastAPI ko Lambda-ready banata hai: `lambda_handler.py` mein `handler = Mangum(app)` — yeh naam yaad rakho.
- `.env` mein AWS coordinates add karo (`PROJECT_NAME`, `AWS_ACCOUNT_ID`, `AWS_DEFAULT_REGION`) — purane mat overwrite karo.
- **AWS projects IAM se shuru hote hain**: root user se `Twin Access` group banao, `AI engineer` user attach karo, zaroori FullAccess policies do.
- Deploy se pehle hamesha **locally verify** karo ki naya code purana behaviour toda nahi.

---

<details>
<summary>📜 Full Transcript (English)</summary>

Now it's time to update our backend server, starting by updating the requirements.txt with the packages we need. Just a few additions here. Select this, go to requirements.txt, select everything and paste in the new one. We've got a couple of AWS packages and we've got py pdf so that we can in parse PDF files. All right back to the preview. We have a new version of Server.py our backend code. Let's just copy and paste it in and then I'll tell you what's changed here. It all is lots of stuff there. Copy that. Go over to server.py, select everything, paste on top and save. What are we doing here? This code is all the same. We're still using the OpenAI client and you should use your one if you're using something different. Uh, and then we've got a few new environment variables. Use S3 uh, which is true or false S3 bucket, which is going to be the name of an S3 bucket to use for the memory, uh, or memory directories if we're running locally. Uh, and then uh, so Boto3 is the Python library that AWS provides for accessing AWS APIs. And we're using that to get our, uh, S3 client library, uh, which we will be using to access S3. And load conversation has been updated so that if you use S3 is true, then it gets an object from S3. You provide in a bucket name and a key, which is going to be our, our, uh, session ID as before. And that will allow us to bring back that object with that key in this bucket. That is how it works. So, um, we've also got a save conversation which, which, uh, basically calls S3 client Putobject before we called S3 client dot get object. objects. Now we put an object, we pass in the bucket name and we pass in the key, which is the as as before the the session ID um, but that's that session ID is we're putting it into get memory path which is basically session ID, JSON, which is the key, the name of this file. Okay. Uh, otherwise things are pretty similar. Uh, if you look through, nothing much has changed. The only real difference here. Should we make this back to GPT 4.1 mini? Uh, the only difference here is this way of getting the conversation history, using the get object and put object from an S3 bucket instead of us. Uh, just looking in the local file system, if the environment variable use S3 is set to true, that's the change that we've made. So again in the last step we updated our server code so that it would use Boto3 AWS Python client library to access S3 buckets so that it could retrieve our conversation history from S3 buckets. The next step is about changing our server function so it can be used as a lambda function. And there's this library we need to use called Mangum, which is a library which uh, which which wraps a fast API server and allows that to be used in the lambda context, which is slightly different. So this is it's just an open source library. I think it's named after, uh, the the movie The Lawnmower Man. It's, uh, apparently what the library author named it after because it's about translating. Uh, but, uh, so this is, this is what we do. Uh, within back end, we have a Python module called Lambda handler dot pi. And this is what we will set up to be the actual function called by lambda. So uh, let's do that now. So this is going to be called lambda underscore handler. Uh within here new file. Handler dot pi. And if you're not familiar with the word lambda it's spelled with a B in the middle of it, which catches people out sometimes. I sometimes do lambda, but it's lambda. Uh, the Greek letter. The letter looks like that. Um, so, uh, lambda handler. Uh, so we we import this this, uh, Mangum object and we use that. We, we, we import our fast API app and we wrap it like so, and we assign that to a variable called handler and later keep, keep hold of that thought because later we're going to be telling Lambda we want you to take this handler. That's the object in this module, which is going to be the thing responsible for servicing the lambda function request. So keep keep keep an eye out for handler and lambda handler. And now back to our instructions. So we're just going to to update the dependencies and just make sure everything is working locally. Uh before we go ahead and deploy. Let's do that now. Okay. So I'm just going to bring up a terminal. I'm in the backend directory Tree here and I'm going to do a uv add minus r requirements.txt to install those extra packages, although it won't actually use the AWS one, but it should use the pypdf2. And now we will do. We will run the command to start our server. You can just take this from the guide. Off goes our server. Our server is now running. It seems to be successful. Let's go over to our client CD frontend and npm run dev. Let's see what happens. Now we will bring this up. Here it comes AI in production. That's great. Uh, so far so good. Let's say hi there. Hi, Ed. Here. What's on your mind today? Uh, my name's Alex. Sorry, my name's Alex. Nice to meet you. And what's my name? You just mentioned Alex. Nice and straightforward, I like that. Ha! Well, my name is Ed. It's even more straightforward, but I feel like I can't tell my digital twin I'm me, or I get super confused. Uh. All right. So far, so good. So that's working. And of course, because I use S3 is set to false by by. It's not set at all in the environment variable. So it will assume it's not using S3. And as a result it's just following the same code path as before. We haven't broken anything. Nothing's regressed. But we are now all ready for AWS. So again I'm going to stop this server. I'm going to stop the backend. I'm going to close the terminal, go back to our our preview. And we are now launching into part two, set up the AWS environment. So the first thing is to uh it says create env. We already have a env. But we're going to add in a few more things to it. We're going to add in. We've already actually got open AI API key, but we're going to add in project name is twin. And we're going to add AWS account ID and then default AWS region. So you remember this from last time. This needs to match the region that you get on the top right. When you log in that you can you can always change. So that region needs to be the region which is closest to you, the main region that makes most sense for where you are. Uh, the usually that's I think EU West one if you're in most of Europe, unless you're closer to another big one. It's uh, the Mumbai one in Asia Pacific in India is a very common one, and US West one and West two. And of course, for me, it's US East one. Uh, even though I'm in London at the moment, but still US East one is the one that I will pick. And, uh, I'm gonna set that up right now. My EMV file, as should you. And I will see you back here in one second. Don't overwrite the existing things in your env. Just just add the new ones in. See you in a second. And hopefully you've followed all the rules. You save the env file. You didn't let that white blob stay there. You were careful with the names of your keys. You spelt your AWS region correctly with the right hyphens and everything else. Otherwise there'll be trouble. Uh. So now we will do what we always start these things by doing, which is beginning with setting up the IAM permissions. Most Amazon projects start with IAM. So we're going to begin by logging in as root, which requires us to go to the AWS console as before and sign in as our root user. So press the uh let me resize that screen and press the sign into console button. And I've already signed in as the root user. And the way I know is it has my name there. It doesn't say AI engineer, it says editor. And that is why we're in the right place for setting up permissions. So begin by going to IAM and open up your IAM resources. And then go to User Groups. And I want you to press, create Group and create a new group that you're going to call Twin Access I've already set up. So it's here when you press that you hopefully you remember that there's two parts to it. You first assign it to a user, and you should check the box by AI engineer so that this user group applies to AI engineer. And then in the next box down, you get to set the permissions. And you should set a bunch of permissions. And I've got the permissions listed down here. And you will have to add these permissions in. And they are listed in the guide. And you remember you type in the search box each one. And then you check the box. And it's a bit janky because you feel like you should press an okay button. But no, you just type out something else to search for and check that box, and you do it for each of them. You'll see in the list API Gateway Administrator. So we can use the API gateway, S3 Full Access Lambda full access. Actually there are two CloudFront ones, and I don't think it matters, but I put them both in CloudFront and CloudFront access to. I think the instructions only send the first one. I don't think it matters, but you might as well put both in and then I'll read only access as well. You need that one too. So all of these permissions again, you'll see that I've gone with the full access for these. The real best practice with Amazon is to limit this to the precise permissions that you need for your IAM user, but that's probably like a super advanced. Like if you're if you're actually setting up a real corporate project and it's a headache. And since we're doing this as part of learning, I don't want to get bogged down in that as long as you get the idea, we're at least restricting what our IAM user can do to these things. And then when you create that user group, it will automatically be connected with the AI engineer user. And you can come back in by going to user groups and click on Twin Access and double check that it comes up just like mine here with the user. And with all of the permissions listed out just as they are here. And then congratulations, you've given your IAM user AI engineer the powers that it needs.

</details>
