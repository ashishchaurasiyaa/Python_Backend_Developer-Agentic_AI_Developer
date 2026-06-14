# L45 — Testing Your Live AI Agent and Configuring CORS for Production

> **Week 2 · Day 2** · ⏱️ ~6 min

---

## 🎯 TL;DR

CloudFront distribution deploy hone ke baad backend Lambda mein **CORS origin** ko `*` (sabko allow) se restrict karke specific CloudFront URL par set karte hain, phir live digital twin ko internet par test karte hain — memory bhi S3 par JSON form mein verify hoti hai. **Week 2 ka 35% milestone**.

---

## 🗣️ Hinglish Explanation

### Final piece: CORS settings

Front end ban gaya, deploy ho gaya, CloudFront distribution deploy ho rahi hai. Aakhri kaam: backend ko batao ki **requests kahan se aane allowed hain**. Yeh **CORS origin** hai.

**CORS (Cross-Origin Resource Sharing) kya hai?** Browser ki ek security policy. Jab ek website (ek "origin" = scheme + domain + port) doosre origin ki API ko `fetch` karti hai, toh browser pehle backend se poochhta hai: *"Kya tum is origin se request accept karte ho?"* Backend `Access-Control-Allow-Origin` header se jawab deta hai. Agar origin match nahi karta, browser request **block** kar deta hai — yeh user ko CORS error deta hai.

Hamare case mein: front end CloudFront URL par hai, backend API Gateway/Lambda par — **alag origins**. Isliye backend ko explicitly CloudFront origin allow karna padega.

### Problem: `CORS_ORIGINS = "*"`

Abhi backend Lambda mein `CORS_ORIGINS` environment variable **`*` (star/wildcard)** par set hai. Iska matlab **koi bhi, kahin se bhi** humari API use kar sakta hai. Development ke liye theek tha, par production ke liye **security risk** — kisi bhi random website se log tumhari API (aur tumhare LLM costs!) hit kar sakte hain. Isse restrict karna zaroori.

### Step 1: CloudFront URL copy karo

CloudFront console par jaao — distribution ab tak deploy ho chuki hogi (status **"Enabled"**). Distribution ka **domain name** copy karo (jaise `https://d1234abcd.cloudfront.net`). Yahi wo origin hai jise allow karna hai.

### Step 2: Lambda environment variable update karo

1. Lambda console → apni **twin-api** function kholo
2. **Configuration** tab → **Environment variables**
3. `CORS_ORIGINS` variable ko edit karo — `*` ki jagah **poora CloudFront URL** daalo:

```
CORS_ORIGINS = https://d1234abcd.cloudfront.net
```

⚠️ **CRITICAL:** `https://` prefix **zaroor** lagao — pura URL chahiye. Sirf domain dene par ya `https` chhodne par horrible CORS errors aayenge.

> Backend (FastAPI) code mein yeh aise consume hota hai:
> ```python
> import os
> from fastapi.middleware.cors import CORSMiddleware
>
> origins = os.environ.get("CORS_ORIGINS", "*").split(",")
> app.add_middleware(
>     CORSMiddleware,
>     allow_origins=origins,        # ab sirf CloudFront URL
>     allow_methods=["*"],
>     allow_headers=["*"],
> )
> ```

Save karte hi Lambda is naye origin se hi requests accept karega.

> 📝 **Side note (Ed's confession):** is dauraan Ed ne mention kiya ki usne pehle galti se ek **wrong zip package** upload kar diya tha (ek later-day ka bedrock-wala build). Usne use sahi proper zip se replace kar diya — ab Lambda mein correct code hai. Yeh galti agle din (Day 3) ke health-check output mein dikhi thi.

### Step 3: Live test — moment of truth

Yeh "trickiest moment of truth" hai. CloudFront page se distribution URL kholo naye tab mein — yahi tumhari website ka **internet par live address** hai. Digital twin se baat karo:

```
You:  Hi there.
Twin: Hello. Glad you stopped by. What's on your mind today?

You:  My name's Alex.
Twin: Nice to meet you, Alex. What brings you to my site?

You:  What's my name?
Twin: You just told me — it's Alex. Got it locked in. What can I do for you, Alex?

You:  Do you like cheese?
Twin: Ah, the cheese question. I can't stand most cheese. No allergy, just don't like the taste...
```

Memory kaam kar rahi hai (naam yaad rakha), aur twin Ed ke baare mein sab jaanta hai (cheese dislike). **Live, on the internet, worldwide.**

### Yeh sab andar kaise chalta hai (full request flow)

Jab user message bhejta hai:

```
1. Browser → CloudFront URL se static front end load (worldwide edge se instant)
2. User message type → front end fetch() → API Gateway endpoint
3. API Gateway → Lambda function ko invoke
4. Lambda cold? → spin up server (ya hot Lambda already ready ho to instant)
5. Lambda code → LLM call + S3 se memory load → response
6. Response wapas browser tak → screen par dikhता hai
7. Naya conversation S3 memory bucket mein JSON ke roop mein save
```

### Step 4: Memory verify karo (S3)

S3 console → **memory bucket** kholo (yaad rakho do buckets hain: ek front-end static site, ek memory). Andar ek **JSON object** padaa milega. Use kholo:

```json
[
  { "role": "user", "content": "Do you like cheese?" },
  { "role": "assistant", "content": "Ah, the cheese question. Actually, I can't stand most cheeses, no allergies..." }
]
```

Wahi conversation jo abhi hui woh S3 par persisted hai. **Architecture live hai.**

### Milestone: 35% complete 🎉

Yeh tumhara **pehla enterprise-strength AWS deployment** hai — production app, CloudFront ke through worldwide. Ed bolta hai agar "frazzled" feel ho raha hai to normal hai — yeh "AWS frazzle" hai, repeat karne se intuition aayega. Tum ab **35% of the way** ho AI-apps-to-production expertise mein. Yeh ab tak ka **hardest course** tha. Kal (Day 3) **Amazon Bedrock** se LLMs call karenge — AI side wapas aa raha hai.

---

## 📋 Key Concepts

| Concept | Matlab |
|---|---|
| **CORS** | Browser security: ek origin doosre origin ki API tabhi call kar sakta hai jab backend allow kare |
| **Origin** | scheme + domain + port (jaise `https://d123.cloudfront.net`) — CORS ki identity unit |
| **`CORS_ORIGINS = "*"`** | Wildcard — koi bhi site API use kar sakti hai; production mein security risk |
| **Restrict CORS** | `*` ko specific CloudFront URL se replace karo (with `https://`) |
| **`Access-Control-Allow-Origin`** | Backend header jo browser ko batata hai konsa origin allowed hai |
| **Lambda env vars** | Configuration tab mein set; code `os.environ` se padhta hai (CORS, S3 bucket, model) |
| **Memory bucket** | S3 bucket jahan har conversation JSON object ke roop mein persist hoti hai |
| **Request flow** | Browser → CloudFront → (front end) ; fetch → API Gateway → Lambda → S3/LLM |
| **Cold start** | Pehli request par Lambda spin-up hota hai; hot Lambda ho to instant |

---

## 💼 Backend Dev Ke Liye Note

CORS har full-stack backend dev ke liye roz ka dard hai — aur yahan iska production face dikh raha hai. Key insight: **`allow_origins=["*"]` development convenience hai, production negligence.** Production mein hamesha explicit origins whitelist karo, kyunki wildcard ka matlab koi bhi malicious site tumhari authenticated API (aur tumhare paid LLM tokens) abuse kar sakti hai. Notice karo ki yeh config **code mein hardcode nahi** balki **environment variable** se aati hai — yeh 12-factor app principle hai: same code artifact (zip) different environments (dev/staging/prod) mein alag config ke saath chale. FastAPI ka `CORSMiddleware` exactly yahi karta hai — `os.environ` se origins padhta hai. Aur woh `*` ko `.split(",")` karne ka pattern dekho — multiple origins (jaise CloudFront + custom domain) comma-separated diye ja sakte hain. Production debugging tip: CORS errors hamesha **browser console** mein dikhते hain, server logs mein nahi — kyunki block browser-side hota hai. Agar `https://` chhoot jaaye ya trailing-slash mismatch ho, request silently fail hogi.

---

## ✅ Takeaway

- **CORS** decoupled front end/back end ka natural issue hai — backend ko explicitly batao kaun-sa origin allowed hai
- Lambda env var `CORS_ORIGINS` ko `*` se **specific CloudFront URL** par set karo — `https://` prefix mandatory
- Live twin ne **memory** (naam yaad) aur **persona** (cheese dislike) dono nibhaye — full architecture working
- Conversation S3 **memory bucket** mein **JSON object** ban ke save hoti hai — verify karke confirm karo
- Yeh pehla **enterprise-grade AWS deployment** complete — **Week 2 / course 35% done**; agle din Bedrock

---

<details>
<summary>📜 Full Transcript (English)</summary>

I was going to say, are you excited? But you're probably not excited. You're probably exhausted. So we're almost there. We're almost, almost at the bitter end. Uh, we have to update these cores settings. Here's the thing. We now have our final front end. We've built and deployed the thing we're about to test our real distribution, our CloudFront distribution that's happening while we speak. It's in the middle of deploying. The final thing we have to do is we have to tell our backend, this is where you should expect to receive requests from. And that's called the Cors origin. That's telling the backend what is an acceptable place. That could be the origin of this HTTP request. Um, and we've got this Cors origins, which is currently a star in our backend Lambda function. And that's not good. That means that anyone could come in and start using our API wherever they're from. So we need to restrict it. So what we do is we're going to go to the CloudFront, which is probably still busy doing its thing, or it may have finished for you. But this is then if it's, uh, for me, uh, let me see whether it's, uh, it's actually a diploid. It has, it has successfully deployed now for me. So this is the distribution right here. I'm going to copy that. And now I have to go back to my lambda function. Here it is I have to go to to twin API right here. Uh which, which uh where I had accidentally previously uploaded uh, the wrong zip package and more, more up to date zip package with later days. Uh, with the bedrock thing, which I've now put back to being the proper zip package for anyone that saw what happened there. Uh, but it's now got the right zip in it. Everything is good for us. I'm going to go to configuration. I'm not going to click on that because you'll see my API keys. You need to go in there. You need to click on environment variables and update that cause environment variable so that it contains that URL that it's allowed to access. So I'll let you go and do that now and then. Everything should be ready to test. So hopefully you added that cause variable and be sure to include the Https on the front of it. It needs to be the full URL for this to work or you'll get horrible cause errors. So look, this I feel is another of these moments of truth. And I know I say that expression a lot, but I feel like as they go, this is perhaps the trickiest of the moments of truth that we have had so far. An exciting moment for us. We start by going to the CloudFront, uh, page, uh, CloudFront service to look at our CloudFront distribution. There it is. We look at the URL right here. This is where our website is running on the internet. Open a new tab and I go in and we are now going to be talking to our digital twin on the internet. Hi there. And let's see what it has to say. Hello. Glad you stopped by. What's on your mind today? Um, my name's Alex. See if it can. Can. Remember that. Nice to meet you, Alex. What brings you to my site? What's my name? You just told me it's Alex. Got it locked in. What can I do for you, Alex? I love it. I think this digital twin could take over from me any day. Uh. All right, let's say, uh. Do you like cheese? See what it has to say. Ah, the cheese question. I can't stand most cheese. No allergy. Just don't like the taste. It's horrible. It's off milk. Uh, so the digital twin obviously does know all about me, which is great. Uh, it's working wonderfully. It's live. It's on the internet. It's on this URL. It's it's because it's CloudFront distribution. This is all over the world. It will go instantly. And whenever you ask a question that is calling a back end API that hits Amazon API gateway that then forwarded on to Lambda, it starts up our server if there isn't already a hot lambda waiting for us. And then that calls into our code and it all just works. And one more thing for us to see is to come in here and type S3. Let's go into S3 and let's find ourselves the memory bucket. Remember two S3 buckets. One of them has our front end site, our static site, one of them we're using for memory. We go in here and lo and behold, there's a JSON object in here waiting for us. Let's go and have a look at this JSON object. Okay, it's a JSON object. Let's press this open right here and check this out. Here is the question. Uh ah, the cheese question. Actually, I can't stand most cheeses, no allergies, blah blah blah. You can see the JSON form of the conversation that we just had sitting there on S3. This is working. Our architecture is live. Congratulations for pulling off your your first enterprise strength AWS Deployment. Well, I promised you a big day, and I think I delivered. A lot got done. We got a production app deployed to AWS through CloudFront distribution around the world. And congratulations on getting there. If you're feeling a bit frazzled, don't worry about it. That is normal. That is AWS frazzle. We got through a lot. It's gonna sink in. We're gonna we're gonna go through it again. You're going to get to a point where it becomes second nature, and in the meantime, go with it, get the intuition and and keep on going. We've got still lots to do. Uh, but on that topic, this is a moment to say you are now 35% of the way through building your expertise to be, uh, brilliant at deploying AI apps to production 35% of the way through. Massive. Congratulations. This is a big moment. This is definitely the hardest core so far. Uh, and tomorrow we're going to move to to looking at the AI side of it again, thank goodness. We're going to be talking about Amazon bedrock and using bedrock to call Llms. I can't wait and I'll see you then.

</details>
