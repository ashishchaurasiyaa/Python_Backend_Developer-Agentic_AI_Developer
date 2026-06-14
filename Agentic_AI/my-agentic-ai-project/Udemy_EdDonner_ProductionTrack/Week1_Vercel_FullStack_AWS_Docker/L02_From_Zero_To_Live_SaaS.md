# L02 — From Zero to Live: Deploying Your First AI-Powered SaaS on Vercel

> **Week 1 · Day 1** · ⏱️ ~6 min

---

## 🎯 TL;DR

Deployment ko **publicly accessible** banate hain — Vercel ke **Deployment Protection** (Vercel Authentication) ko off karke — aur phir Ed course ke objectives, dono target audiences (entrepreneur vs enterprise engineer), aur 3 success factors batata hai. Core message: **learning happens by doing**, sirf videos dekhne se nahi.

---

## 🗣️ Hinglish Explanation

### Inspect link: Vercel dashboard ka tour

Pichle lecture mein `vercel .` ke output mein do links the — ek **production URL** aur ek **Inspect** link. Inspect link (Cmd+Click) tumhe **Vercel dashboard** par le jaata hai jahan deployment ka poora detail dikhta hai:

- Deployment ka **preview** (app ka screenshot-style thumbnail)
- Build logs, status, configuration
- **Deployment Configuration** section (expand karna pad sakta hai)

Yeh dashboard production debugging ka pehla stop hai — har deploy ki history, logs, settings sab yahin milte hain.

### Problem: app "live" hai par sab ke liye nahi

Ek catch notice kiya Ed ne: jab tum apne production URL par gaye, tum **Vercel mein signed-in the**. By default Vercel **Deployment Protection** lagata hai — **"Standard Protection"** on hota hai, jiska matlab **Vercel Authentication** enabled hai: *sirf wahi log page dekh sakte hain jo Vercel mein logged in hon aur tumhari team ke member hon*. Toh technically yeh "live on the internet" nahi hai — sirf tum dekh sakte ho.

Yeh ek genuine **production security concept** hai: platforms by default deployments ko protect karte hain taaki adhoore/internal apps accidentally public na ho jayein. Staging environments ke liye yeh feature hai; public apps ke liye isse off karna padta hai.

### Fix: Deployment Protection off karo

Step-by-step:

1. Inspect page par **Deployment Configuration** section expand karo
2. **Deployment Protection** → "Standard protection" par click karo → Settings page khulta hai
3. Wahan **Vercel Authentication** toggle dikhega ("This ensures visitors need to be logged in to Vercel and a member of your team")
4. Toggle **off** karo → **Save** → confirmation milta hai ki setting change ho gayi

### Verify: incognito test

Public access verify karne ka classic trick — **incognito/private window** (jahan koi login session nahi hota):

1. Production URL copy karo
2. Chrome mein **New Incognito Window** kholo
3. URL paste karo → **"Live from production!"** dikh gaya ✅

Ab app genuinely **kisi ke liye bhi** internet par live hai. Yeh verification habit production work mein hamesha kaam aati hai — "mere browser mein chalta hai" aur "public ke liye chalta hai" do alag cheezein hain (cached sessions, cookies, auth states ka difference).

### Course objectives: yeh course kiske liye hai?

Ab thodi si "intro" baat (deploy ke BAAD, Ed style mein). Yeh Ed ka **most intensive course** hai — 4 weeks, fully packed, commercial-grade hands-on projects. Do **target audiences**:

**1. Entrepreneurs** 🚀
Jo apna **SaaS app** internet par deploy karna chahte hain — complete package ke saath:
- **Authentication** (users sign up/login kar sakein)
- **SSL** (HTTPS security)
- **Subscription billing** (log pay karke use karein)
- **Secure aur scalable** infrastructure

Aur surprise: **yeh sab Week 1 mein hi ho jayega** — pehla week sabse intense hai, baaki weeks us foundation par build karte hain.

**2. Enterprise engineers** 🏢
Jo **enterprise-level knowledge** chahte hain — AI ko major cloud providers (**AWS, GCP, Azure**) par **scale aur resiliency** ke saath deploy karna, aur aise roles ke liye apply karne layak expertise.

Aur in dono extremes ke beech ek **continuum** hai — medium-size company mein future growth ke liye deploy karna ho, ya bas **resume beef up** karna ho — spectrum par kahin bhi ho, course tumhare liye designed hai.

### 3 Success factors — course ke end par tum kya kar paoge

1. **Deploy & monetize** apna AI application — technology part solved milega. (Caveat: **product-market fit** Ed nahi de sakta — product, go-to-market tumhara kaam hai. Tech tumhare paas hogi.)
2. **Production-grade AI implement** karna major companies mein — **transferable skills** ke saath. Ed deliberately most common platforms/frameworks pe focus karta hai taaki skills portable rahein.
3. **Job-ready hona** — Ed ne actual job descriptions study ki hain aur khud hiring manager hai. Uske baaki courses bahut kuch cover karte hain, par ek gap tha: **productionization of AI** — wahi gap yeh course bharta hai.

### Ed ki warning: course alone kaafi nahi

Sabse important baat: **sirf videos dekhne se yeh skills nahi milengi.** Ed ka learning philosophy:

- **Do it yourself** — jo Ed karta hai, saath mein karo
- **Fix problems jab aayein** — frustrating hota hai, par *"that's where the real learning happens"*
- **Make projects your own** — changes karo, apna flair add karo, kuch different try karo
- **Assignments complete karo** — har week ke assignments

> *"The part that matters isn't what I do. It's what you do."*

---

## 📋 Key Concepts

| Concept | Matlab |
|---|---|
| **Inspect link** | Vercel dashboard mein deployment details (logs, config, preview) dekhne ka link |
| **Deployment Protection** | Vercel ka default security — deployment ko logged-in team members tak restrict karta hai |
| **Vercel Authentication** | "Standard Protection" ka mechanism — visitors ko Vercel login + team membership chahiye |
| **Incognito test** | Private window se URL kholna = verify karna ki app truly public hai (no cached auth) |
| **SaaS** | Software as a Service — subscription-based hosted app (auth + billing + scale) |
| **Product-market fit** | Log tumhara product chahte hain ya nahi — tech course solve karta hai, yeh nahi |
| **Transferable skills** | Common platforms/patterns par skills jo company-to-company portable hain |

---

## 💼 Backend Dev Ke Liye Note

Deployment Protection wala concept enterprise mein har jagah milta hai — **staging environments ko VPN/SSO ke peeche rakhna, production ko public**. Vercel ka "Standard Protection" wahi pattern hai jo tum AWS mein security groups / Cloudflare Access / OAuth middleware se karte ho. Incognito-test bhi professional habit hai: backend devs isse **auth boundary verification** ke liye use karte hain (authenticated vs anonymous user flows). Aur Week 1 ka promise note karo — auth + SSL + subscriptions ek hafte mein: yeh wahi boilerplate hai jo har SaaS backend mein chahiye hota hai, toh yeh week tumhare liye direct reusable blueprint banega.

---

## ✅ Takeaway

- Vercel by default deployment **protect** karta hai — public app ke liye Settings → Deployment Protection → Vercel Authentication **off** karo
- **Incognito window** = "truly public hai ya nahi" check karne ka standard trick
- Course 2 audiences ke liye: **entrepreneurs** (SaaS deploy+monetize) aur **enterprise engineers** (cloud scale/resiliency) — aur beech ka poora spectrum
- Week 1 sabse intense hai: auth, SSL, subscriptions, secure+scalable — sab pehle hafte mein
- **Real learning = doing**: projects khud banao, problems khud fix karo, assignments complete karo

---

<details>
<summary>📜 Full Transcript (English)</summary>

Now, I appreciate that some of you have seen Vassell before and deployed your own stuff and are probably thinking, ah, this is small potatoes. Uh, but maybe, maybe not yet. Mind blowing. But hopefully for those new to it, you were pleased to see that it's really not that hard. Okay, so if we go back to cursor, in addition to the link to production, there was another link here called inspect. And I just want to take you through that, uh, command. Click to go through that link. This shows us the screen in Vercel where we can look at our deployment. See a little preview of it right here. Now one of the things you might have noticed is that when you went to this web page, you actually had to be signed in to Vercel to be able to access it. And you could argue that it's not really live on the internet if you need to be signed into Vercel, but we can change that if you look down. If you may need to expand this section here, deployment configuration, you'll see that there is deployment protection. Standard protection is turned on. If you click on that it takes us over to the settings page. And you can see that we've got Vercel authentication turned on. This ensures visitors need to be logged in to vessel and a member of our team. So. So unfortunately, probably only us could see this right now, but luckily we can turn this off, press save. And that tells us that it's been changed. And now, for example, uh, we can do something like let's go back here again, copy this URL to our web page, and I'm going to create a new incognito window. Here it is in Chrome. And go and visit this page. And I'm thrilled to see that live from production is being served now to anybody on the internet. So there we are, live on the internet in minutes. And never fear, we'll be coming back to add a healthy dose of artificial intelligence team. Okay, so this is what I have in store for you. We are going to be doing some hardcore learning. This is probably the most intensive of any course that I've made. It's all in four weeks, but I have packed those four weeks in. We're going to be working on some of the juiciest projects I've ever built. Very commercial, very hands on. They're going to be really interesting and quite challenging projects. But at the same time, I'm hoping to make this a lot of fun. That is always that's definitely my my vibe, making sure that it's entertaining as well as educational. And so hopefully you're going to be enjoying it as we go and as we build things that are scalable and resilient and secure. All right. So let me tell you about the objectives, who the course is for and how you'll know you've been successful at the end of it. So there's really two different audiences that I've designed this course for. On the one hand are entrepreneurs. If you are someone that's coming along and you want to take a SaaS app and deploy it online on the internet, it's got authentication, it's got SSL, it's got subscription built in so people can sign up and start paying for it, and it's secure and scalable. Then this course is for you. And in fact, the first week is the most intense week because we're going to do all of that in the first week and then just build on it. Also, if you're someone who's coming at this wanting to get an enterprise level of knowledge on AI being deployed in the cloud for scale and resiliency, so you want to be able to scale an AI on a major cloud provider like AWS and GCP and Azure, and you want to also have the kind of relevant expertise that means that you could apply for roles that need all of that. Then this is also for you. And I'm here to tell you that whilst it is intended for one of those two audiences, there is a whole continuum of people that sit between those two extremes. Maybe you're someone who wants to be an entrepreneur, but right now you're working in a particular company. Maybe you're in a medium sized company, but you want to be able to deploy for future growth and scale. Maybe you'd like to at least beef up your resume so that you're able to apply to the most possible jobs and everything in between. If you are anywhere on that spectrum, then I've designed this course for you. So what will you get out of it at the end? What are the success factors? Well, by the end of this, there are three things that you should be able to do. The first of them is is for the entrepreneur. You should be able to deploy and monetize and make money from your own AI application. Now of course, you'll have to have product market fit. I can't promise you that people will come and pay for it, but if you've built a product and you've got good go to market and people will pay for it, then the technology part will be solved for you. The second thing is that you'll be able to implement production grade AI at major companies, and you will have transferable skills that you can apply to different situations. I focus on transferable skills on the most common kinds of platforms and frameworks, so you will have that capability. And then along with that, you'll be able to apply for roles that have that kind of skill set requirements. So I've taken a careful look at many different job descriptions. And also as a hiring manager in the space myself, I know what people look for. And when I look at the other courses that I've offered, I cover a lot of the bases, but there is one piece that I don't, and that is the productionization of AI. And that is what you will leave this course with. But I have I have something to tell you. This course alone won't do it. You won't get that only from taking the course. You will get that from taking the course and also completing the assignments as we go. I find that the best way to learn is by doing. And you don't do by listening to me yabbering away. You have to do it yourself. That means that that as I go through things, you need to be doing it too. When you get stuck and you hit problems, that's the time to be fixing them and understanding them. Frustrating though it can be. That's where the real learning happens. So you have to complete the projects with me. You have to fix the problems when they happen, and then you have to make the projects your own. Make changes, do something different, add your own flair to the projects as we go, and take on some of the assignments I give you as we go. And that is the real way to learn these these videos and the the stuff I do, that's just that's the foundation. Uh, the part that matters isn't what I do. It's what you do.

</details>
