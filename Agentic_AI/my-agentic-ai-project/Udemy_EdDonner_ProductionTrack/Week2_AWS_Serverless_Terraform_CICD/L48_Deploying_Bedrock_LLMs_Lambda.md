# L48 — Deploying Bedrock LLMs to AWS Lambda and Testing Production APIs

> **Week 2 · Day 3** · ⏱️ ~5 min

---

## 🎯 TL;DR

Naye Bedrock code wale Lambda package ko build karke (Docker se), zip banake AWS Lambda mein upload karte hain, health check se confirm karte hain ki model ab **Amazon Nova (Bedrock)** hai, aur phir CloudFront se live twin se chat karke prove karte hain ki paid model **bina kisi API key** ke chal raha hai — kyunki billing AWS account ke through hoti hai.

---

## 🗣️ Hinglish Explanation

### Context: hum kahan hain

Pichle do-teen lectures mein humne digital twin ko AWS par migrate kiya — frontend S3+CloudFront par, backend Lambda par, API Gateway ke through expose. Phir humne OpenAI se hata kar **Amazon Bedrock** (Nova models) par switch kiya code level par. Ab ek hi kaam bacha hai: us naye Bedrock code ko actually Lambda par **deploy** karna aur test karna. Yeh lecture chhota hai — ek "rite of passage" jaisa re-upload exercise.

### Step 1: Lambda package build karo

Backend directory mein naya terminal kholo. Optionally requirements sync kar lo, phir deploy script chalao:

```bash
# backend directory mein
uv add requirements.txt        # optional — up-to-date code ensure karne ke liye
uv run deploy.py               # asli build + zip yahi karta hai
```

`deploy.py` jo karta hai:

1. Ek **Lambda package directory** banata hai jisme saari zaroori files install hoti hain.
2. **Crucial trick:** Python packages ko ek **Docker container ke andar install** karta hai. Kyun? Kyunki Lambda Amazon Linux par chalta hai — agar tum apne Mac/Windows par directly `pip install` karoge toh native (compiled) packages ka binary tumhare OS ke liye banega, Lambda ke Linux runtime par crash karega. Docker container Lambda jaisa environment de deta hai, isliye yeh **super reliable** way hai.
3. Sab kuch zip karke `lambda_deployment.zip` bana deta hai — isme `data/` directory aur relevant Python packages dono saath hote hain.

Zip ke contents dekhne hain toh `lambda_package` folder kholo — usme sab files dikhengi.

### Step 2: Zip ko Lambda mein upload karo (UI se)

Do tareeke hote hain:

- **S3 ke through** (safer, slow connections ke liye recommended) — pehle zip ko S3 bucket mein daalo, phir Lambda usse uthaye.
- **Direct UI upload** (brave way, fast connection ke liye) — directly Lambda console se zip upload.

Ed UI wala fast tareeka use karta hai:

1. AWS Console → **Lambda** → apna function **twin API** kholo
2. **Code** tab → **Upload from** → **.zip file**
3. Backend folder mein jaake `lambda_deployment.zip` select karo → **Open** → **Save**
4. Naya zip (Bedrock code wala) upload hota hai aur server par deploy ho jaata hai

> Note: agar connection slow hai, instructions mein Mac/PC dono ke liye S3-route steps diye hain, ya ek CLI command bhi de rakhi hai jo fast connection par direct upload kar de.

Upload complete hone par green message aata hai: **"Successfully updated the function"**.

### Step 3: Health check se confirm karo

Lambda console mein **Test** tab par jao. Pehle se banaya hua **health check** test event chuno (Ed ke paas "health check three" naam hai, tumhare paas bas "health check" hoga). **Test** button dabao → "Executing function".

Successful hone par response open karo — output kuch aisa:

```json
{
  "status": "healthy",
  "bedrock_model": "Amazon Nova Lite"
}
```

Yahan `bedrock_model` field bata raha hai ki ab code OpenAI nahi, **Bedrock Nova** use kar raha hai. Ed ne **Nova Lite** pick kiya, tum **Nova Micro** pick kar sakte ho — dono Amazon ke chhote/saste text models hain. Jo bhi pick kiya, wahi twin run hone par use hoga.

### Step 4: Live twin ko test karo (CloudFront se)

Do options:

- `curl` se directly **API Gateway** endpoint hit karna, ya
- Seedha **CloudFront distribution** URL kholna (real user experience).

Ed CloudFront wala route leta hai. CloudFront distribution URL kholo (jo tumne pehle save kiya tha), aur twin se chat karo:

```text
You: hi there
Twin (Nova): Hello! ... What would you like to talk about today? Got any questions
            about my career, my courses on Udemy, or the tech stack at Nebula?

You: Do you like cheese?
Twin (Nova): Ah, the age-old question. I must admit, I'm not a big fan of most
            cheeses... but hey, everyone has their preference, right?
```

Observation: Nova kaafi **wordy / perky** hai (OpenAI se thoda zyada chatty). Functionally sab working — ab LLM connection Bedrock Nova ke through ja raha hai.

### Step 5: "Bina API key kaise chal raha hai?" — the AWS magic

Yeh sabse important conceptual point hai. Tumne kahin **OpenAI API key ya secret key** nahi diya — secrets dekhe toh wahan kuch nahi tha. Phir paid model bina key ke kaise chal raha hai?

**Jawab: hum AWS ecosystem ke andar hain.**

- Lambda ek **IAM role** ke saath chalta hai jisme **Bedrock invoke** karne ki permission attached hai (humne pehle yeh role set kiya tha).
- Jab Lambda Bedrock ko call karta hai, AWS andar-hi-andar identity verify karta hai role se — koi explicit API key ki zaroorat nahi.
- Usage ka **bill seedha tumhare AWS account** par aata hai. Yeh "baked into the cloud" feature hai.
- Costs **AWS Billing / Cost Management Center** mein dikhenge (root user se sign in karke). Agar spend tumhare set **budget thresholds** ke upar gaya, toh AWS tumhe **email alerts** bhej dega (humne pehle budgets/alerts set kiye the).

Yeh production AI ka ek bada advantage hai: API keys manage/rotate/leak hone ka jhanjhat nahi, IAM role hi authorization handle kar leta hai, aur billing single AWS invoice mein consolidated rehti hai.

### Quick background refresher

- **AWS Lambda** — serverless compute. Tum code (zip ya container) upload karte ho, AWS request aane par function spin karta hai, auto-scale, pay-per-invocation, koi server manage nahi.
- **Amazon Bedrock** — managed service jo multiple foundation models (Amazon Nova, Anthropic Claude, Meta Llama, etc.) ko ek unified API se serve karta hai. Tum sirf `invoke` karte ho, infra Amazon sambhalta hai.
- **CloudFront** — AWS ka CDN; globally edge locations se content/API serve karta hai, HTTPS deta hai, aur frontend (S3) + backend (API Gateway) dono ko ek hi domain ke peeche route kar sakta hai.
- **IAM role** — ek identity jisme permissions (policies) attach hoti hain; AWS services usse "assume" karke authorized actions karti hain — keys ke bina.

---

## 📋 Key Concepts

| Concept | Matlab |
|---|---|
| **`uv run deploy.py`** | Build script — Docker mein packages install karke `lambda_deployment.zip` banata hai |
| **Docker-based build** | Lambda ke Amazon Linux runtime se match karne ke liye packages container mein install hote hain |
| **lambda_deployment.zip** | Final artifact — code + `data/` + Python packages, Lambda par upload hota hai |
| **Upload from .zip** | Lambda console Code tab se direct zip upload (vs. safer S3 route) |
| **Health check test** | Lambda Test event jo `bedrock_model` field se confirm karta hai model = Nova |
| **Amazon Nova Lite/Micro** | Amazon ke saste, fast text foundation models (Bedrock par) |
| **No API key needed** | IAM role Bedrock invoke authorize karta hai; key ki zaroorat nahi |
| **AWS billing** | Bedrock usage seedha AWS account par bill hoti hai; budget alerts email bhejte hain |

---

## 💼 Backend Dev Ke Liye Note

Python backend dev ke liye yahan do load-bearing practices hain. (1) **Build-environment parity** — `deploy.py` packages ko Docker mein install karta hai taaki binary wheels (e.g. `pydantic-core`, `numpy`, `cryptography`) Lambda ke Linux ABI se match karein. Yeh wahi problem hai jo tum local-dev-vs-prod mein `manylinux` wheels ya multi-stage Docker builds se solve karte ho — "works on my machine" ka classic fix. (2) **Credential-less auth** — IAM role se Bedrock call karna exactly wahi pattern hai jaise EC2/ECS/Lambda par DB ya S3 access dene ke liye role-based auth use karna (e.g. IRSA on EKS, instance profiles). Production mein static API keys env vars/secrets manager mein rakhna risky hai; jab provider AWS-native ho (Bedrock), role-based access best practice hai — no secret to rotate, no secret to leak. Health-check endpoint jo deployed config (model name) return kare — woh bhi ek solid prod habit hai: deploy ke baad smoke test se confirm karo ki sahi version/config live gaya.

---

## ✅ Takeaway

- Lambda re-deploy = `uv run deploy.py` (Docker build + zip) → console se **Upload from .zip** → **Save**
- Deploy ke baad **health check test** chalao — `bedrock_model` field confirm karta hai ab Nova use ho raha hai
- Live test CloudFront URL se: twin ab Bedrock Nova se jawab deta hai (wordy/perky style)
- **Paid model bina API key** chal raha hai kyunki Lambda ka IAM role Bedrock invoke authorize karta hai; bill AWS account par aata hai
- Slow connection ho toh zip S3 ke through upload karna safer hai vs direct UI upload

---

<details>
<summary>📜 Full Transcript (English)</summary>

Next up, it's time to build our Lambda package and upload it all of our new code so that the bedrock code so that it's ready to run in our Lambda function. And this is actually quite easy. It's a repeat of what we did before. Bring up a new terminal. We go to the backend directory and now we just we don't really need to do this, but we could do a UV, add requirements.txt to make sure we've got the up to date code and then UV run deploy.py, which is our uh, our script for deploying and off it goes. And this is now building a directory Lambda package, which contains a bunch of files that are being built by installing them in actually in a Docker container to do that. So it's, it's a super reliable way of doing it. And then when it did that, it zipped it all up to Lambda deployment zip. And that includes all of these files here. It includes our data directory and it includes the relevant Python packages. They're all together in that zip file. You can look at the contents by going into Lambda package. And that's, uh, ready now for us to upload to Lambda. So the instructions here are for uploading via S3, which is the safer way for slower connections. But we're going to be be brave and try and do it this way through the UI. So I'm going to go into Lambda. I'm going to find the twin API and then going to go into code. We're already in code upload from a zip file. And you see the zip file that I'm now going to select is the one that I selected the first time, uh, by mistake. So, so uh, it's already had this in it, but this is the right directory now. So I go into back end, I pick lambda deployment, I say open and save. And it's now uploading this new zip file that includes the bedrock code. And that is what we're going to have uploaded to our server. So we'll give it a second. While it does that, let's go back to the instructions. And these instructions guide you through the the way to do it if if your connection is too slow. Um, with uh, Mac and PC instructions. Um, and you can also run this, this code here instead if you've got a fast connection as well. Okay. So it's now time to test it again. If it's run successfully and we can use the same health check as before. And, uh, this time you should see, like me, it has completed. You see, this green successfully updated the function. So we now go to test. We see that health check three, which for you should just be health check should be there. And when I run this test I press the test button executing function. Hopefully it has permissions to do everything. It's successful. Open this up. It's healthy and it says bedrock model and hopefully yours says Bedrock Model two. This time mine did last time as well because I uploaded the wrong step. But uh, now everything is good. We're at the same point and we both get the bedrock model right here. Amazon Nova Light is the one I picked. You might have picked micro, but either way that that is the one that will be used when we run our twin. Excellent. So far so good. So it's now time to test our twin. And there's. You can test it with curl to go straight to the API gateway should you wish. But I think we're just going to jump straight to testing the twin through CloudFront. So you probably have your CloudFront distribution saved somewhere. Oh of course. I've just got it already open over here haven't I? There it is. That is our CloudFront distribution in a new page. And let's say hi there. And this is the first time it's sir. And I noticed that Nova is quite wordy. So there's quite a lot to it. Uh, lots of stuff there. So what would you like to talk about today? Got any questions about my career, my courses on Udemy, or perhaps the tech stack we use at Nebula? Feel free to ask me anything. I'm all ears. Uh, so it's, like, perky. Like me. Uh, so, uh, let's say. Do you like cheese? Uh. Let's see. Ah, the age old question. I must admit, I'm not a big fan of most cheeses. Uh, so, uh. But, hey, everyone has their preference, right? What about you? Uh, maybe it's a little bit too much of the sunniness. Uh, okay, so that is working. It's going against, uh, it's now going to bedrock, and this is using the Nova models as, as our LM connection. And now you might be wondering. Hang on. But we didn't we didn't give it an API key anywhere. We didn't give it a secret key. When we looked in the secrets, I was sharing my screen with you. You saw everything. So how does that work exactly? How are we using paid models but without a key? And of course, the answer is because we're doing it through AWS. We're in the AWS ecosystem. So it's it's going against our existing AWS account. It's being billed to us. And we will see these costs in the custom billing center in AWS when we sign in, uh, as uh, as with the root permissions. And if that goes above our thresholds, we'll get a bunch of emails telling us, so, uh, that that is all it's all built in, baked in to the AWS cloud environment.

</details>
