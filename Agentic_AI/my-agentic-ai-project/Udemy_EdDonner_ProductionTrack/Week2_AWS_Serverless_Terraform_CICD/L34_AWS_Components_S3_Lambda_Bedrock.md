# L34 — AWS Cloud Components for Production AI: S3, Lambda, and Bedrock

> **Week 2 · Day 1** · ⏱️ ~7 min

---

## 🎯 TL;DR

Is hafte ke 5 main AWS components ka "biology lesson": **S3** (storage buckets), **Lambda** (functions), **CloudFront** (CDN), **API Gateway** (API management), aur **Bedrock** (LLM wrapping) — plus Amazon vs AWS branding ka chhota raaz.

---

## 🗣️ Hinglish Explanation

### "AWS = biology, LLMs = physics"

Ed ek mental model deta hai: **LLMs ke saath kaam karna physics jaisa hai** — understanding, experimenting, "kaise aur kyun kaam karta hai". **AWS biology jaisa hai** — bahut saara **anatomy, words, acronyms** memorize karna. Ed ko biology kabhi pasand nahi thi, toh AWS use bhi hard work lagta hai. Advice: **terms ko hawi mat hone do** — bas sun lo, jo Ed kare copy karo, time ke saath sink ho jaayega jab S3, Lambda, CloudFront sab "roll off the tongue" karne lagein.

Ab is hafte ke **5 main components**:

### 1. Amazon S3 — Simple Storage Service

> Acronym: **S3 = Simple Storage Service** (teen S).

- Yeh "very simple" hai — bilkul **cloud mein shared drive** jaisa (Google Drive jaisa) jise tumhara software access kar sake.
- **Buckets** mein organize hota hai. Ek **S3 bucket** = ek particular shared drive with ek particular naam. ("Main isse S3 bucket mein daal dunga" — yeh phrase tum bahut sunoge.)
- Bucket ke andar basically **directories aur files** rakh sakte ho — kisi bhi shared drive jaisa.

> **Background:** S3 object storage hai (file storage, block storage nahi). Har object ka ek unique key (path jaisa) hota hai. Highly durable (99.999999999% — "11 nines"), virtually unlimited scale, aur static websites tak host kar sakta hai. Backups, media, data lakes, logs — sab S3 par.

### 2. AWS Lambda — Functions

(Pichle lecture mein cover ho chuka.)

- Cloud par **individual functions** chalte hain.
- Sirf **CPU clock cycles** ka paisa jo tum use karte ho.
- "You're going to get to love it."

### 3. CloudFront — CDN (Content Delivery Network)

> **CDN kya hai?** Internet par bade static files (images, JS files) serve karne ka efficient tarika.

Problem: agar har baar koi news webpage khole (jaise CNN), aur saari images CNN ke origin server (USA mein, ya jahan bhi) se travel karke aayein — yeh **inefficient** hoga, slow.

Solution (CDN idea): bade **static files** (images, JS) ko duniya bhar ke **chhote data centers (edge locations)** par push kar do. Jab user webpage khole:
- Page ka kuch hissa **actual origin server** se aata hai (jaise CNN's news content)
- Par **images jaise static assets** user ke **paas wale local data center** se aate hain → bahut kam travel → super fast.

Yeh service = **CDN**. Amazon ka CDN offering = **CloudFront**.

- CloudFront ke saath kaam karna = ek **CloudFront distribution** banana — yaani app ke assets (images, static site) ko duniya bhar distribute karna.
- Result: user webpage khole toh kuch Amazon origin se, par assets duniya bhar ke CloudFront servers se collect hote hain → fast.

> Ed bolta hai sab samajh na aaye toh koi baat nahi — "we're going to play with it", lab mein better feel aayega.

### 4. Amazon API Gateway

- Ek component jahan tum apne **external APIs manage** karte ho jo duniya ko offer karoge — jo (for example) ek **Lambda function** call karte hain.
- Inke around **instrumentation** laga sakte ho: **rate limiting**, scaling manage karna, etc.

> **Lambda direct vs API Gateway:** Lambda ko aise bhi set kar sakte ho ki outside world seedha use call kare (Function URL), par **best practice** hai aage **API Gateway** lagana — more controls, "more bulletproof", aur enterprise-grade tarika.

(Is lecture mein sirf baat ho rahi hai; actually is hafte aage use karenge.)

### 5. Amazon Bedrock — LLM Wrapping Service

- (Galti se "AWS Bedrock" mat bolna — **Amazon** Bedrock.)
- Yeh Amazon ke **do LLM offerings** mein se ek hai (doosra next week — yaani SageMaker, Week 3).
- Bedrock se tum jaldi **GenAI apps** bana sakte ho **Frontier Models / Foundation LLMs** ko connect karke (Bedrock ke through call).
- Extra features bhi hain — jaise ek **agent platform** andar (baad mein dekhenge — Week 4 ka AgentCore).

> **Background:** Bedrock ek **fully-managed, serverless** service hai jo ek single API ke peeche kai foundation models (Anthropic Claude, Amazon Titan/Nova, Meta Llama, Mistral, etc.) deta hai. Tumhe model host nahi karna padta — API call karo, pay-per-token. Is hafte digital twin ka LLM call Bedrock se hoga.

### Amazon vs AWS branding ka raaz

Ed ne khud notice kiya ki wo "Amazon Bedrock" vs "AWS Bedrock" mein tongue-tied ho raha tha. Amazon apni branding mein **consistent** hai:

- **"Amazon <product>"** branding — do cases:
  1. **Earliest offerings** — jaise **Amazon S3** (bilkul shuruaat mein aaya).
  2. **Consumer-facing products** — jinhe Amazon public ke saamne promote karna chahta hai (sirf "nerds" ke liye nahi). Jaise **Amazon Bedrock** (GenAI offering, prominently promote karte hain).

- **"AWS <product>"** branding — **nerdier offerings** jo hum engineers ke liye hain. Jaise **AWS Lambda**.

> Agar sahi bolna ho toh jaise docs mein likha hai waisa bolo (Amazon S3, Amazon Bedrock, AWS Lambda).

---

## 📋 Key Concepts

| Concept | Matlab |
|---|---|
| **S3 (Simple Storage Service)** | Cloud shared drive; data **buckets** mein, andar directories+files |
| **S3 bucket** | Ek named storage container — object storage, virtually unlimited |
| **Lambda** | Cloud par individual functions; pay per CPU cycle |
| **CDN** | Static assets ko edge data centers par distribute karke fast delivery |
| **CloudFront** | Amazon ka CDN; "CloudFront distribution" banate ho |
| **API Gateway** | External APIs manage — rate limiting, scaling, Lambda ke aage best practice |
| **Bedrock** | Amazon ka managed LLM service — foundation models ek API ke peeche |
| **Foundation / Frontier model** | Bade pretrained LLMs jo Bedrock through call hote hain |
| **Amazon vs AWS branding** | Amazon = earliest/consumer (S3, Bedrock); AWS = nerdier (Lambda) |
| **"AWS = biology"** | Bahut terminology memorize karni — time ke saath sink hoga |

---

## 💼 Backend Dev Ke Liye Note

Ek backend dev ke liye yeh 5 components classic three-tier + AI stack map karte hain: **S3** = blob/object store (jaise tumne kabhi MinIO/GCS use kiya ho — config, uploads, static assets, logs), **Lambda** = stateless request handler (FastAPI route ka serverless avatar — yaad rakho yeh stateless hai, state S3/DB mein), **CloudFront** = reverse-proxy + edge cache (nginx + Varnish ka managed global version), **API Gateway** = API edge layer (auth, throttling, request validation — Kong/nginx ingress jaisa), **Bedrock** = LLM provider behind a managed endpoint (OpenAI client ki jagah `boto3` Bedrock client). Practical insight: production mein **kabhi Lambda ko direct internet par expose mat karo** — hamesha API Gateway aage rakho throttling/auth/WAF ke liye, bilkul jaise tum app server ko nginx ke peeche rakhte ho. Aur Bedrock ka pay-per-token + IAM-scoped access matlab API keys manage karne ka jhanjhat kam (IAM role hi credentials handle karta hai) — backend security ke liye ek bada plus.

---

## ✅ Takeaway

- **5 core components yaad rakho:** S3 (storage), Lambda (functions), CloudFront (CDN), API Gateway (API mgmt), Bedrock (LLM)
- **S3** = cloud shared drive, data **buckets** mein; **CloudFront** = static assets ko duniya bhar edge par distribute karke fast delivery
- **API Gateway** Lambda ke aage lagana **best practice** hai — rate limiting + controls + bulletproof
- **Bedrock** = managed access to foundation/frontier LLMs ek API ke peeche (is hafte digital twin ka LLM yahin se)
- Branding: **Amazon** S3/Bedrock (earliest/consumer), **AWS** Lambda (engineer-facing) — docs ke hisaab se bolo

---

<details>
<summary>📜 Full Transcript (English)</summary>

So we're now going to talk about AWS components a little bit more. Before we get to the to the lab. And I just want to make the point that I do think that, that some of the cloud deployment world is a bit like learning biology. I think of working with LMS. The stuff that is my my greatest forte, I feel, is more like physics. It's more about understanding, experimenting, learning about the way, what, how it works and why it works and that kind of thing. With AWS, there's a lot of learning, there's a lot of anatomy, there's a lot of words and acronyms and stuff to memorize if you want to feel fluent in it. I was never much good at biology at school. I'm sure some of you are brilliant at biology or me. Uh, so so I do, I find it, I find it hard work. And some of you may find it hard work as well. I find learning about LMS rather simpler. Uh, with AWS, as I say, there's there's going to be lots of terminology. And my advice to you is to not let it get to you. Just listen to all these words. Copy what I do expect that it will sink in over time as you start to have like S2 and S3 and Lambda and CloudFront and all these other things just roll off the tongue. But we are now going to have a biology lesson as we get into the AWS components that we'll be using this week. So then I'm going to talk about five of them which are the main five we will use. So Amazon S3, S3 which stands for Simple Storage Service. Uh this is very simple indeed. It is just like having a shared drive, like a Google drive in the cloud that you can access for your software. And it's organized into things called buckets and an S3 bucket. You hear people saying that all the time. I'm going to put that in S3 bucket. And S3 bucket is like one particular shared drive with one particular name that you can access. And in that bucket you can have basically directories and files, just just like any shared drive. That is S3. And of course there's lots of hair, there's lots of complexity around it. But but that's the simple, simple version Lambda we've already talked about. You're going to get to love it. This is individual functions run on the cloud. You only pay for the CPU clock cycles that you use CloudFront. front. Okay. What is CloudFront? So have you heard of something called a CDN? A content delivery network. CDNs are part of the way that the internet works when it comes to to larger files like images and JavaScript files. It would be very inefficient if every time you looked at a web page like a news web page, it was going all the way back to their servers to collect all of the images and bring them back all over the internet from wherever the servers are running in, in the States or wherever that particular site is being hosted. And so there is this idea that for larger files that are static, like images, it's more efficient for, for for companies to push them out to, to smaller data centers all over the world, so that when a user brings up a web page, it loads some of the web page from the actual server itself, like CNN. If you're looking at CNN's at news, but for some of the images, it's just collecting them from a local data center somewhere really near where you're located, so that it only has to travel a little bit. And it's really fast. And when you have a service that someone like CNN can connect with in order to push out their assets, like images to to be located close to everyone all over the world, that service is known as a CDN, a content delivery network, and Amazon offers such a service. And their offering is known as CloudFront. So CloudFront. And when you when you work with CloudFront, it's called making CloudFront distribution. That means being able to take the assets associated with your with your app and be able to distribute them all over the world so that when people bring up a web page, it's collecting. It's talking to to Amazon servers for some things, but it's talking to all these CloudFront servers all over the world to collect your assets. So that is called CloudFront. If you didn't get all of that it doesn't matter because we're going to play with it. You're going to get a better sense for it later. But hopefully you now know three of the Amazon words we'll be doing today. And then the next one is called Amazon API gateway. And this is another Amazon component where you can manage. You can set up the different, uh, External APIs you will offer the world that might then, for example, call a lambda function and put some instrumentation around them so you can manage things like rate limiting them and managing how they scale and so on. Now it happens with Lambda. You can set up lambda so that the outside world can go straight to lambda in some ways, but it is considered a best practice to set up an API gateway. It gives you more controls, it's more bulletproof, and it's more the way you would build an enterprise application. And so that's what we'll be using today. Well, not actually today this week, but we'll be talking about it today. And then last but not least is AWS not AWS Amazon Bedrock. And this this is something which is one of a two different LLM offerings that Amazon has that we'll talk about the other one next week. But bedrock is something which allows you to quickly build JNI apps by connecting to Frontier Models Foundation LMS through bedrock. And it has a number of other features, like it has like an agent platform in there too, that we'll look at at some point. But this is all part of the Amazon Bedrock product, and it's a very minor point. You may have noticed I got tongue tied about Amazon Bedrock versus AWS bedrock. It's interesting that Amazon is quite careful with its branding that some of its products are branded Amazon. And then the product and some of them are AWS and the product, and they are consistent everywhere with it. So just so that you feel native with AWS products, it's worth knowing. Typically the Amazon branding is for some of their earliest offerings, like S3 that that came at the very beginning, Amazon S3. And also they use the Amazon branding for products that they want to be in front of consumers, products which which they want to be out there in the public, not just for us nerds. Uh, and so that would be something like bedrock. They want to really promote bedrock as, as their gen AI offering. So it's Amazon bedrock. But for some of the more the nerdier offerings that are meant for us re engineers, uh, they brand them AWS. So it's AWS Lambda, for example. So there's something to know about, if you're wondering, uh, if you want to get it right then then you should you should stick with the way that they describe it in their docs.

</details>
