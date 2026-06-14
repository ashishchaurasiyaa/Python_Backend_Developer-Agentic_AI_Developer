# L35 — Building Your Digital Twin: AWS Lambda + Bedrock Architecture Setup

> **Week 2 · Day 1** · ⏱️ ~11 min

---

## 🎯 TL;DR

Is hafte ka project unveil: **Digital Twin Mk2** — ek chatbot jo tumhe recruiters/managers ke saamne represent kare. Full deployment architecture (Lambda + S3 memory + API Gateway + Next.js static site on S3 + CloudFront + Bedrock LLM), plus AWS grind survive karne ke debugging/LLM tips. Aaj sirf **local build**, deployment kal.

---

## 🗣️ Hinglish Explanation

### Project unveil: Digital Twin

Is hafte ka project = **Digital Twin**. Jinhone Ed ka **Agentic course** kiya tha, unhone already ek banaya tha (waha "career alter ego" naam tha).

**Yeh kya hai?** Ek **chatbot jo tumhe outside world ke saamne represent kare** — "the future of the resume". Website par resume rakhne ki jagah, ek chatbot rakho jo tumhare bare mein, tumhari career history, interests sab jaanta hai. **Recruiters ya hiring managers** us se questions pooch sakte hain ki tum kaun ho, kya karte ho, kis cheez mein interested ho. Aur tum use **prep** kar sakte ho taaki wo better aur better answer de.

> **"Digital Twin Mk2":** Yeh Agentic course wale se ek bada step aage hai. Kuch functionality (jaise **tool use**) yeh course mein nahi karega — wo **assignment** hoga (un logon ke liye jinhone Agentic course kiya). Agar tumne Agentic course nahi kiya, toh tension nahi — **scratch se naya version** banayenge, "Mk1" hone ki zaroorat nahi.

### Deployment architecture — full picture

Ed warn karta hai: yeh "unwieldy" lagega (bunch of boxes with AWS components) — par "rest assured, next week it's 5x worse". Toh yeh easy-peasy hai comparatively. Architecture do halves mein:

#### 🟦 Backend (blue boxes)

1. **Lambda function** — digital twin ki **business logic** handle karta hai. Hiring manager ke request ka jawab deta hai (background, interests, proudest accomplishment, etc.). Pehla component.

2. **S3 bucket called `memory`** — conversation track karne ke liye.

   > **Kyun zaroori hai (key AI concept):** Har LLM call **completely stateless** hai — LLM ko pichli baat ka kuch nahi pata. Agar chahte ho ki LLM **conversation ka context** rakhe, toh **har call par poori conversation so far** dobara bhejni padti hai. Toh hum yeh conversation **S3** mein store karenge — `memory` bucket ke andar **har user conversation ke liye alag file**. Lambda is bucket ko access karta hai.

3. **API Gateway** — outside world ko andar aane deta hai, Lambda function ko call karne ke liye, taaki user LLM se conversation kar sake.

Yeh teen blue boxes = **backend**.

#### 🟩 Frontend (green/static)

4. **Next.js app → static website export.** Week 1 mein dekha tha ki Next.js se ek **static website** export ho sakti hai (HTML + JavaScript + CSS, jo TypeScript + Tailwind se generate hoti hai).

5. **S3 bucket called `frontend`** — yeh static site doosre S3 bucket par rakhi jaayegi. (Ab **do S3 buckets**: `memory` backend ke liye, `frontend` frontend ke liye.)

6. **CloudFront distribution** — static site ko ek **asset** maan ke duniya bhar distribute kiya jaayega, taaki koi bhi apne paas wale data center se jaldi access kar sake.

#### 🔗 Frontend + Backend kaise milte hain?

Same as Week 1 Day 5 (jo tab fully explain nahi kiya tha). Jahan dono milte hain wo jagah hai → **user ka browser**.

Flow (step-by-step):
1. User ek **URL** par jaata hai — yeh **CloudFront distribution** ka web address hai.
2. URL enter karte hi browser **poori static site collect** karta hai aur render karta hai → chatbot UI dikhta hai (digital twin se conversation karne ki ability).
3. User kuch type karta hai → static site ek **API call** karti hai → wo call jaati hai **API Gateway** par.
4. API Gateway → **Lambda business function** hit karta hai → LLM se chat hoti hai, **memory** S3 bucket se conversation context lete hue.

#### 🟪 Missing piece — LLM!

"Kya kuch reh gaya? Yes — LLM!" Lambda business logic ek **LLM call** karta hai, aur yeh **Bedrock** (Amazon's LLM-wrapping service) se hota hai. Screen par jo **purple** hai (purple = AI) wo Bedrock hai.

Yeh hai **Digital Twin Mk2** ka full deployment architecture. "It's not so bad." Yeh poora hafta isi ko build karne mein jaayega.

### Reality check — yeh "one massive environment setup" hai

Ed honest hai: yeh poora hafta basically **environment setup** hai ("everyone's favorite part"). Suggestions:

1. **Pehle dekho, phir karo** — Ed ko karte dekho, phir **setup guides** follow karke khud sab set karo.
2. Bahut **copy-paste** hoga — code type nahi karenge. Yeh labs/notebooks jaisa nahi jahan code inspect karne ko hota hai; yeh "busy work" jaisa lagega.
3. **Repetition se muscle memory** banao — Ed suggest karta hai kuch cheezein 2-3 baar karo taaki AWS components familiar ho jaayein. "It's biology — there's some learning."

### Guides aur LLM se debugging tips

- **Guides padho aur check karte raho** — Ed unhe update karta rehta hai jaise students problems hit karte hain. Itne possible systems hain ki bahut tarike se mistake ho sakti hai.
- **Community contributions** par troubleshooting tips dekho.
- **Docs** par nazar rakho.
- **LLMs use karo** — Cursor mein agents, ya **Claude Code** (Ed bolta hai "I love cloud code, I use it a lot").

**Effective LLM debugging ke liye tricks (jab atak jao):**
1. **Context do:** "Main is course par hoon, main guide number 3 par hoon, please guides 1, 2, 3 padho taaki samajh aaye main kahan hoon." — taaki agent ko exact pata ho tum kya kar rahe ho.
2. **Error paste karo** — jo error mila wo dikhao, check karne ko bolo. Agents AWS commands aur GitHub commands chala sakte hain, toh research karwa sakte ho.
3. **⚠️ Most important — jo bole uspe blindly trust mat karo!** "This is the path to despair." Jo wo bole use **check karo** — unless obvious ho (jaise "tumne us-east-1 galat spell kiya" → "oh sahi" → fine). Par agar wo koi **theory** deta hai, ya extra parameter add karta hai, toh **must verify** — kyunki LLMs **hallucinate** karte hain aur kabhi-kabhi immediate problem ko mediocre tarike se solve karte hain.
4. **Challenge karo:** "kya tumne X aur Y socha? Yeh sahi nahi lag raha. Are you sure?" — treat them like **an eager junior assistant** jiske paas bahut time hai aur jo bahut internet search karta hai aane se pehle. Yeh mental model rakho warna side-track ho jaaoge, painful hoga.

**Aur tips:**
- **Ed khud questions ke liye available hai** — usually hours mein respond karta hai (jab tak sota/travel na kar raha ho). Bola yeh course uske baakiyon se zyada hard hai, toh debugging strategies par zyada time spend karne ko suggest karega.
- **AWS official paid support plan** bhi option hai agar chahiye.
- **Sabse important: patience.** "Oodles of patience." Environment setup irritating ho sakta hai, par jab sab aata hai toh "so satisfying".

### Aaj ka lab — sirf local twin

Ed bolta hai: chalo lab par, wapas Cursor par. **Aaj sirf twin ko LOCALLY build karenge** — koi actual AWS deployment **aaj nahi**, par sab kal ke "showtime" ke liye ready ho jaayega.

---

## 📋 Key Concepts

| Concept | Matlab |
|---|---|
| **Digital Twin (Mk2)** | Chatbot jo tumhe recruiters/managers ke saamne represent kare — "future of resume" |
| **LLM statelessness** | Har LLM call independent; context ke liye poori conversation har baar bhejni padti |
| **S3 `memory` bucket** | Conversation history store — har user ki alag file (Lambda access karta) |
| **S3 `frontend` bucket** | Next.js static site (HTML/JS/CSS) host karne ke liye |
| **Lambda business logic** | Request handle + Bedrock LLM call + memory read/write |
| **API Gateway** | Browser → backend ka entry point (Lambda call karta) |
| **CloudFront distribution** | Static site duniya bhar fast deliver — user yahin connect karta |
| **Bedrock (purple = AI)** | Lambda se LLM call wrap karta hai |
| **Browser = join point** | Front+back end browser mein milte hain (static site → API call) |
| **LLM debugging mindset** | Agent = eager junior; sab verify karo, blindly trust mat karo |

---

## 💼 Backend Dev Ke Liye Note

Yeh architecture ek textbook **serverless full-stack pattern** hai — ek backend dev ke liye samajhna trivial hai agar tum tiers ko map karo: static frontend (S3 + CloudFront) = "JAMstack" CDN-served SPA; API Gateway + Lambda = stateless API tier; S3 `memory` = poor-man's session/state store (DynamoDB ya Redis ki jagah, kyunki conversations chhoti aur cheap hain). Sabse important backend lesson yahan **statelessness handling** hai: Lambda khud stateless hai aur LLM bhi stateless hai, toh **conversation state externalize** karna padta hai — yeh exactly wahi pattern hai jo tum stateless REST APIs mein session store (Redis/DB) ke saath use karte ho. Production mein S3-as-session-store ke caveats yaad rakho: eventual consistency (ab S3 strong read-after-write deta hai, par concurrent writes par last-write-wins race ho sakti hai), aur per-request read/write latency. Ed ka LLM-debugging advice ("verify everything, treat it like a junior") ek senior engineer ki code-review discipline hi hai — generated infra config (IAM policies, CORS, bucket policies) **kabhi blindly apply mat karo**, kyunki yahin security holes aur 3am pages aate hain.

---

## ✅ Takeaway

- **Project = Digital Twin Mk2** — recruiter-facing chatbot; tool use Agentic-course grads ke liye assignment hai, baaki scratch se banayenge
- **Architecture:** browser → CloudFront (frontend S3 static site) → API Gateway → Lambda (business logic) → Bedrock LLM + S3 `memory` bucket
- **LLM statelessness** core hai — conversation har user ki alag file mein S3 par store hoti hai aur har call par bheji jaati hai
- Yeh hafta "one massive environment setup" hai — guides follow karo, repeat karke muscle memory banao, **oodles of patience** rakho
- LLM se debug karo par **sab verify karo** — agent = eager junior jo hallucinate kar sakta hai; aaj sirf **local build**, deployment kal

---

<details>
<summary>📜 Full Transcript (English)</summary>

And now let me unveil to you the project we'll be working on throughout this week. The digital twin people who took my Agentic course will have already built a digital twin. I think I called it your career alter Ego in that course, which is basically a chat bot which is there to represent you to the outside world. It's like the future of the resume. Instead of having a resume on your website, you have like a chat bot that knows about you and your career history and your interests, and recruiters or managers can interact with that to ask questions about what you and what you might be interested in. And you can you can prep it and make it be better and better at answering the kinds of questions people might want to ask. Now I'm calling this digital twin Mark two, because it's like a big step ahead of what I did in the Agentic course, although some parts of it, I'm not going to do some of the functionality, which in terms of things like tool use, which is going to be an assignment for you if you took the Agentic course. Uh, but so it's going to be Mark two. But don't worry if you didn't. If you haven't taken the genetic course, you don't have a mark one you don't need to. We're gonna also be starting from scratch with the new version. So what is this going to do? Okay, I'm going to tell you about the deployment architecture of the digital twin and this deployment architecture. It's going to look a bit unwieldy if you've not seen these sorts of things before. There's going to be a bunch of boxes with different AWS components on them. But I'm here to tell you, rest assured, however unwieldy this looks, it's going to be like five times worse next week. So. So you better be able to withstand this one. Because because this this is this is easy peasy compared to what I have in store for you. But here we go. This is the deployment architecture that we're going to be building this week for our digital twin. So the digital twin begins with lambda functions that we'll write one lambda function which will handle the business logic of digital twin. It's something which can basically respond to a request by from a hiring manager about to chat with you about what you might be interested in working on, or what your background experience, your proudest accomplishment, or whatever. So that's the first first component using Lambda. It is going to need to keep track of the conversation which it's having with the user. And as you hopefully know from using Llms, every call to an LLM is completely stateless. It has no knowledge of what was said before. If you want an LLM to be able to apparently have a conversation where it keeps the context of the conversation, you need to supply the full conversation so far every time you call the LLM. And we're going to store that in S3. There's going to be an S3 bucket called memory. And in that S3 bucket we're going to have separate files for each of the different user conversations. That'll be in an S3 bucket that Lambda will access. So far so good. We are going to build API gateway that is going to allow the outside world to come in and call our lambda function and be able to, uh, be be used that in order to have a conversation with our LM and that those blue boxes make up the backend of our system. That was the back end. Let's talk about the front end. So look, we built a Next.js app. You remember from last week that one of the things we can do with that is export a static website that represents our front end. And we will do that. And we will put that static website, a set of HTML, JavaScript and CSS that's generated from the TypeScript and tailwind and all the rest of it that generated static website. We will go and put that on an S3 bucket, another S3 bucket called front end. So we now have like a two S3 buckets. One is called memory used by the back end and one is called front end uh, and is used by the front end. And then we will deliver that to CloudFront. We will set up a CloudFront distribution, and that means that our static site will be considered an asset that will be distributed around the world, so that anyone can quickly access it from a data center that's near to them. That's our front end. So now we have a front end and a back end. How do these two things come together? Well, it's actually the same as day five of last week, although I didn't necessarily explain it in full detail, but the place where the front end and back end comes together is in fact the browser, the user's browser. The user starts by going to a web address or URL, and it will be the web address of our CloudFront distribution. So when they enter in that web address, basically they will collect the entire static site and they will render that in the browser. The browser will display the full web page, which will show like a chat bot, ability to have a conversation with your digital twin. And when they enter in something into that, that browser, into that static website, it will make an API call, and the place it will go with. That API call is of course API gateway, and that means that it will go through hit our Lambda business function and it will indeed chat with them, taking memory from the S3 bucket with memory. And that is how the front end and the back end fits together. Is there anything missing from this? We've forgotten anything. Anything at all. Can you think? Yes. We forgot to mention the LM. The LM does feature here. Our lambda business logic is going to make a call to an LM, and it's going to do that by using a service called bedrock, which is Amazon's service for for wrapping LM calls. So there is some purple. Remember purple is for our AI. There is some purple on this screen. And it's it's for bedrock. There it is. And that is our full deployment architecture for the digital twin Mk two. It's not so bad. Uh, that's that's what we'll be doing throughout this week, and it's all going to come together. So before we go to the lab one final time to remind you that this is going to be somewhat tiresome for you, basically, this entire week is one massive environment setup. Everyone's favorite part of this course of my previous courses, anyway. Uh, so, uh, I suggest that you follow along. You watch me do it first, and then afterwards you go through the the guides that that I have, which are like set up guides and you just just go through and set everything up and look, I'm going to be honest, it's a lot of like copying and pasting. It's lots of we won't be typing out any code. And it's not like labs where they're not like notebooks where the code is there for you to inspect and look at. It's going to be setting up all these different bits of code. So it's going to feel like a lot of busy work. Um, but this this is where you'll do the learning and you may need to do some repetition like I, do, sometimes suggest that you do these things a couple of times over as a way to build the muscle memory and really get so familiar with these AWS components. Again, it's biology. There's some learning. Uh, I don't like learning. Uh, I mean, I like understanding, I don't like having to memorize. And there's some of that. Uh, so, uh, read the guides. Uh, check check them. Because I update them as as you hit problems. And there's going to be problems because there's so many possible systems out there, so many ways to to to make a mistake. Uh, I will be, uh, adding things to the guides to help explain. So keep an eye on the guides. Keep an eye on community contributions for any extra troubleshooting tips from students. Uh, do keep an eye on the docs. Use LMS so in cursor. If you're using cursor, use use agents. If you use cloud code. I love cloud code. I use it a lot. Then use that too. And there are some tricks for how to use it effectively when you get stuck. When something goes wrong. First of all, tell them to read the guide. Say I'm doing a course on blah blah blah. I'm on guide number three. Please read guides one, two and three to understand where I am. Make sure you tell it to do that so it knows exactly what you're trying to do. Show them the error that you've got. Paste that in there and get them to go and check. They can run AWS commands. They can run GitHub commands. So you can tell these agents to go and do some research for you. But most importantly, do not trust what they tell you. This is the path to despair. What they tell you needs to be checked. Unless it's unless it really lands with you. Unless it's something obvious. You know, they say, hey, you've spelt us East one wrong, and you're like, oh, so I did then fine, do that. But if it's something where they have a theory, they add on an extra parameter somewhere, you must check it because they do often hallucinate. And they also often they just sort of solve an immediate problem in a, in a very mediocre way. And so check it. Challenge them. Say, have you really thought about x and Y that this doesn't feel right to me? Are you sure? Like B treat it like an eager junior assistant junior coder who has a lot of time on their hands and does tons of internet searching before they come and talk to you. So keep that mental model in mind. Otherwise you can easily get taken off on a side track and it can be very painful. So. So they are hard workers. They are. They need to be validated. And then finally remember I am here for questions. I'm always, always around. I respond quickly, uh, often within hours, unless I'm sleeping or traveling, in which case it's whenever I stop sleeping on traveling, uh, but I respond quickly. As I said at the very beginning, it's going to be much harder than my other courses. I'm usually quite quick to to debug and find problems. It's going to be harder for me this time, and I am going to suggest that you spend more time trying to figure out strategies for debugging, unless I know what the problem is. In which case, of course, I'll tell you right away. Uh, so so I'm going to be probably suggesting some of that and giving you resources. There are also I mean, I think AWS has a paid plan if you want to get like AWS official support. And I'm sure that that those guys could sort out anything. Uh, so you've got other options available for you if you want it. But but I would say this should set you up. And probably more important than any of this, more important than LMS and me and everything else is patience. Oodles of patience. This this is a grind environment setup can can feel, uh, quite, quite irritating. So have have patience when it comes together. It's so satisfying. And that's where we'll be in a few days time. And with that, let's go to the lab. Let's go back to cursor. Let's get started. Let's build ourselves for for today we're going to just build the twin locally. We're not going to do any actual AWS deployment today, but it's going to be all ready for showtime tomorrow. But let's go and do that right now.

</details>
