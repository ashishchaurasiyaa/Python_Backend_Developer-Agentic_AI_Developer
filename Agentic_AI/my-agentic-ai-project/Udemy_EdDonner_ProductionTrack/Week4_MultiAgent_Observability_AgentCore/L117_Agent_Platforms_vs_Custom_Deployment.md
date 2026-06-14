# L117 — Agent Platforms vs Custom Deployment: When to Use Managed Solutions

> **Week 4 · Day 5** · ⏱️ ~10 min

---

## 🎯 TL;DR

Course ka grand finale topic: **Agent Platforms** — managed, batteries-included infrastructure jisme tum agents minutes mein build aur deploy kar sakte ho (CrewAI Enterprise, LangGraph Platform, Vertex AI Agents, aur naya **Amazon Bedrock AgentCore**). Ed pros (speed, simplicity) vs cons (kam flexibility, vendor lock-in) explain karta hai, aur clarify karta ki enterprise production abhi bhi mostly custom-built (jaise humne course mein kiya) hota hai.

---

## 🗣️ Hinglish Explanation

### Final topic — the grand finale

Ed welcome karta hai "final topic of the final day of the final week" — grand finale. Naya concept: **Agent Platform**.

### Agent Platform kya hai?

Ek **integrated, end-to-end solution** jo tumhe **complete AI agent solutions build aur deploy** karne deta hai **managed infrastructure** par — jahan sab kuch already set up aur organized hai. Tum apna agent code do, platform baaki plumbing (deploy, scale, run) sambhal leta hai.

Ed bolta hai actually **Vercel** (jo Week 1 mein use kiya) ek tarah ka similar concept hai — full agent platform nahi, par usmein agent templates hain aur "build & deploy easy" wali philosophy same hai. Par typical agent platforms specifically **agent deployment ke around oriented** hote hain.

### Examples — agent platforms ka landscape

Ed apne **Agentic course** se reference deta hai jahan in frameworks ko cover kiya tha. Har popular open-source agent framework ka ek **paid managed offering** hai:

| Open-source framework | Managed platform |
|---|---|
| **CrewAI** | **CrewAI Enterprise** (aka Crew Enterprise) — built crew ko deploy karke unki infra par chala sakte ho |
| **LangGraph** | **LangGraph Platform** — LangGraph agents ko cloud par deploy/run karne ka paid product |
| **Google ecosystem** | **Vertex AI Agents** — terminology confusion: Vertex AI Agent Builder, Agent Engine, etc. Pehle LangChain se tightly tied tha, ab apni branding hai. Vertex sabse purana player hai is game mein |

### Aur ek — Amazon Bedrock AgentCore

Ed teaser deta hai: ~1 month pehle (recently) Amazon ne **Amazon Bedrock AgentCore** announce/release kiya. Naam ka tongue-twister. Abhi Ed ke liye **preview** mein hai (Amazon Bedrock AgentCore Preview). Jaldi preview se nikalne ki ummeed hai.

Yeh **AWS ka managed agent platform** offering hai. Bahut excitement hai, relatively new hai, aur kaafi reasons hain like karne ke. Ed bolta hai yeh actually **kai alag cheezon ka combination** hai jo AgentCore branding ke neeche packaged hain — super confusing, Vertex se bhi worse, kyunki similar names wale multiple products hain. Agle lecture mein woh building blocks clearly define karega. Abhi bas yeh samjho ki yeh ek **managed agent platform** hai — yaani cloud provider details sambhalta hai, thoda extra charge karta hai, badle mein **fast, streamlined, easy** banata hai.

### Pros vs Cons — roll your own vs agent platform

Ed honest hai: woh poora course "roll your own" tareeke se padha raha tha, toh kya woh waste tha? Answer: **nahi**. Pros aur cons dono hain.

#### ✅ Pros (agent platform ke)

1. **Time to market amazing** — minutes mein build, deploy aur agents running. Bilkul **Vercel experience** jaisa — quick, simplified, kam decisions
2. **Batteries included** — Ed ne yeh term Agentic course mein CrewAI ke liye use kiya tha. Matlab box mein bahut kuch built-in milta hai, alag se "batteries" khareedne nahi padti — sab andar hai

#### ❌ Cons (agent platform ke)

1. **Sab relatively new hain** (Vertex exception, jo reinvent ho gaya). Ye platforms abhi apni jagah define kar rahe hain, "muscling in." Ed ka observation: in mein se kai ek **monetization strategy** hain:
   - CrewAI, LangGraph jaise incredibly popular **open-source frameworks** hain, par monetization path harder hai. Toh "ek button dabao aur production mein running, small fee mein" — yeh natural monetization route hai
   - **AWS ka case alag** — unhe monetization issue nahi. Unke liye yeh **turf protect** karna hai — agar log Vertex AI use karein toh woh **Google ki infra** par deploy hoga. Amazon chahta hai ki agent-platform game mein woh bhi bada player ho
2. **Less flexibility** — simplification ka flip side. Buttons dabao, deploy ho jaata hai, par **granular control nahi**. Jaise deploy ho gaya, waisa hi chalega
3. **Vendor lock-in** — batteries-included ka flip side. Pasand nahi aayi battery? Swap nahi kar sakte, jo aayi wahi hai. AgentCore ke case mein **Amazon infrastructure mein locked** — observability aur baaki choices Amazon ki
   - **Caveat:** AgentCore actually underlying **agent framework** ke baare mein bahut flexible hai — Amazon ka apna framework use karna zaroori nahi, koi bhi swap kar sakte ho. Amazon yeh baat bahut highlight karta hai. Par **deployment** khud AgentCore ke tareeke se packaged rehta hai
   - **Benefit:** Lambda, IAM, App Runner waale details ki tension nahi — sab automatic. **Downside:** "ye component independently scale karo, ye secret yahan rakho" wala fine-grained control nahi milta

### Bottom line — enterprise abhi bhi custom build karta hai

Ed clear karta hai: aaj ki date mein agent platforms **production deployments ke liye common nahi hain**, especially **enterprise production** ke liye. Jo tareeka course mein padhaya — **AWS services build karna, Terraform use karna, GCP/Azure par karna, fine-grained control** — wahi tareeka enterprises use karti hain. Toh course waste nahi tha (relief!).

Agent platforms apni jagah ke liye lad rahe hain. **Startups** inhe use karte hain — newer products, quick experiments ke liye. Par yeh **full-spec scalable production platform** roll out karne ka primary tareeka nahi hai. Isliye Ed ne ise **end mein teaser** ke roop mein rakha — abhi experience le lo, par yeh core ingredient nahi.

### Analogy

Ed compare karta hai **Heroku** (packaged app deploy) aur dobara **Vercel** se — easy, streamlined, simplified build & deploy. Saari plumbing tumhare liye handle ho jaati hai, koi tension nahi. Par woh hi tradeoff: convenience vs control.

> **Quick background:** **Heroku** ek classic PaaS hai — `git push heroku main` karo, woh app build karke run kar deta hai, koi server config nahi. **Vercel** isi philosophy ka modern serverless version hai. Agent platforms basically yahi DX agentic systems ke liye laa rahe hain.

---

## 📋 Key Concepts

| Concept | Matlab |
|---|---|
| **Agent platform** | Integrated managed infra jisme agents build + deploy minutes mein hote hain |
| **CrewAI Enterprise** | CrewAI ka paid managed deployment offering |
| **LangGraph Platform** | LangGraph agents ko cloud par deploy/run karne ka paid product |
| **Vertex AI Agents** | Google ka agent platform (Agent Builder / Agent Engine) — sabse purana player |
| **Amazon Bedrock AgentCore** | AWS ka naya managed agent platform (abhi preview mein) — kai services ka bundle |
| **Batteries included** | Framework jisme bahut kuch built-in milta hai, alag se setup nahi karna |
| **Time to market** | Idea se production tak ka time — agent platforms isse drastically kam karte hain |
| **Vendor lock-in** | Ek provider ke tareeke/infra mein bandh jaana, swap karna mushkil |
| **Roll your own** | Custom build — AWS services + Terraform + fine-grained control (course wala tareeka) |
| **Monetization strategy** | Open-source frameworks ka paid managed offering = revenue path |

---

## 💼 Backend Dev Ke Liye Note

Yeh classic **build vs buy / PaaS vs IaaS** decision hai, bas agentic flavour mein. Backend dev ke liye intuition seedha map karta hai: agent platform = **Heroku/Vercel/App Engine** tier (fast DX, opinionated, locked-in), jabki "roll your own" = **raw AWS + Terraform** tier (slow setup, full control, portable). Ed ka enterprise observation important hai — jab tumhe **independent scaling, secret management, custom observability, multi-cloud portability** chahiye, PaaS ki convenience tang karne lagti hai, isliye serious production teams IaC route lete hain. Lekin con #1 (monetization strategy) ek sharp engineering-economics insight hai: jab koi open-source tool ek managed tier launch kare, samajh lo unka revenue incentive ab tumhare workload ko **apni infra par rakhne** ka hai — lock-in unintentional nahi, by design hai. Practical takeaway: **prototypes/MVPs ke liye agent platform** (speed jeetti hai), **scale/compliance/cost-at-scale ke liye custom** (control jeetta hai). Aur AgentCore ka framework-agnostic design (koi bhi agent SDK swap kar sakte ho) ek smart anti-lock-in move hai jo isse baaki platforms se differentiate karta hai — par deployment layer phir bhi AWS-bound hai.

---

## ✅ Takeaway

- **Agent platform** = managed, batteries-included infra — agents minutes mein deploy (CrewAI Enterprise, LangGraph Platform, Vertex AI Agents, Amazon Bedrock AgentCore)
- **Pros:** killer time-to-market + batteries-included (Vercel/Heroku jaisa DX)
- **Cons:** kam flexibility, **vendor lock-in**, aur sab abhi new hain (kai toh open-source frameworks ki monetization strategy hain)
- **AgentCore** abhi preview mein hai — kai services ka confusing bundle (agla lecture clarify karega); framework-agnostic hai par AWS-deployment-bound
- **Enterprise production abhi bhi mostly custom-built** hota hai (course wala tareeka) — agent platforms startups/experiments ke liye zyada, par watch this space

---

<details>
<summary>📜 Full Transcript (English)</summary>

And so I welcome you to the final topic of the final day of the final week of the AI and production course, the grand Finale. Let me introduce to you the new topic of an agent platform. What is an agent platform? Are you saying? Why haven't I mentioned it before? So I probably have because it comes up a lot and a lot of people ask about it. But an agent platform is one of these integrated end to end solutions that lets you build and deploy complete AI agent solutions in managed infrastructure, where everything is set up and organized for you. And you might be thinking, okay, wow, that sounds great. And why didn't you tell us about that right back at the beginning? That might have been helpful. Uh, so so the answer is because it has pros and cons, and in some ways, actually vassal that we used is is a sort of it's not a full agent platform, although they do have agent templates. Uh, but it's certainly along those lines. It's a similar concept, but typically agent platforms are very much oriented around a straight up agent deployment. Okay, so you're thinking you have examples for me. I do indeed. So people who took my agent course, we talked about some of these as we went through. So there's platforms like crew, AI, enterprise. If you work with with crew, then they they frequently do mention that whilst crew AI is an open source platform, they do have a paid offering called crew AI enterprise and sometimes branded a bit differently, but mostly Crew Enterprise, which is their their complete managed infrastructure for when you've built your crew, you can then deploy it and have it running on their platforms. The same thing happened with Landgraf when when I taught Landgraf in the Agentic course, I showed you that there was also Landgraf platform, which is their paid product for deploying and running your Landgraf agents on the cloud. And people that work in the Google ecosystem are probably quite familiar with vertex AI agents. And this has quite a terminology confusion. There is vertex AI agent builder and there's vertex AI agent engine, and there's some other variations as well. So there's there's a, there's a whole vocabulary around this. But basically vertex AI has agent capabilities. And this previously I believe was actually quite tied to long chain. And recently they've varied it a bit so that now it's got its own kind of branding. So and it's the one that's been around the longest I think vertex was one of the very first, uh, into this game. Uh, others have taken a bit longer. Um, but, but that is some of the landscape. These are some of the agent platforms that you might have heard of. But wait, I hear you say there is another ah, yes, there is indeed another. So about a month ago, I think for me, very recently Amazon announced and released Amazon Bedrock Agent Core. It's quite a mouthful. Amazon Bedrock agent Core. It's like a tongue twister. Uh, so so that was released recently and it is currently for me in preview. It is Amazon Bedrock agent core preview just rolls off the tongue. Uh, and uh, but but but they and so they say it may it may change. But they're hoping to bring it out of preview quite soon. And this is AWS Managed Agent platform, their agent platform, uh, offering. And it's got quite a lot of excitement and it's relatively new and it's got a lot of reasons to like it. So what exactly is it? Well, actually, that's a good question. Uh, it turns out that that that it is, is, uh, a combination of different things. It's several different things that are sort of packaged together under the Amazon Bedrock Agent Core branding. And it's super confusing. It's actually even worse than vertex AI because they've got a number of different products with very similar names that are easy to get muddled up. And even when you're talking to someone and say, Bedrock Agent Core, you might be referring to different things. So in just a minute, I'm going to come back and very clearly define the different building blocks that make up Amazon Bedrock Agent core. But for the time being, just believe me that it is another of these agent platforms and integrated product for building and then deploying AI agents in a way that is that is managed, which means that you're relying on the cloud provider to take care of the details, and they charge you a bit extra than you having to take care of the details in return for making it fast and streamlined and easy. Okay, so with that, this is a good time for me to tell you what what are what are the pros and cons of adopting something like an agent platform instead of rolling your own? Instead of doing what we've been doing for the last few days? Because it would be quite a bore if that was all a complete waste of time. And you should always use an agent platform. And the answer is you shouldn't always use an agent platform. There are pros and cons and let's cover them now. And I imagine this is going to be pretty obvious stuff that you're expecting me to say. But the pros obviously, first of all, compared to what we've been working on, the time to market is just amazing. Like, you can build something and deploy it and have agents running in a few minutes. It's a bit like the Versaille experience. There's a huge parallels with Versaille. It's really quick to get something out there. It's it's very much simplified. There's much less to worry about. Fewer decisions. And as part of that, it's these all of these frameworks are very much what one would call batteries included. I originally think I used that back when, when in the Agentic course, when we were working with crew to describe crew as a batteries included framework, meaning that you get a lot in the box. It comes, it comes with a lot of stuff built in, so you don't have to go out and buy the batteries separately. It's just it's just all there in it, which is great. So that sounds like some, some, some perfect prose. What can there possibly not be to love? And I know you're all old hands at this, so you know perfectly well what the cons are, but just to go through them anyway. The cons, of course. Uh, actually, this first one's a bit different that you probably know this too, but. But the agent platforms themselves are. They're all relatively new to the field. Uh, perhaps with the exception of vertex, uh, which is sort of reinvented itself. But they're relatively new, and they're clearly kind of looking to define their space and muscling in on their space. And I think in a lot of cases, these are about products trying to find a monetization strategy. So platforms like like Crew and Landgraf, they're incredibly popular open source frameworks. But seeing the path to monetization might be harder. So trying to to follow this, this route and say, look, since you built using a fabulous open source framework, you can also press a button and have that be running in production for a small fee, that that is a natural monetization path. And so I do think a lot of this is about people trying to find that path. Now, obviously AWS doesn't doesn't exactly have a monetization issue. And I suspect for them it's different. It's more about making sure that they they get their turf. They don't want to lose business to other people, because if other people use something like vertex AI, then that will of course be being deployed to Google's infrastructure. So Amazon wants to make sure that they've got a big player in this bag of new agent platforms. So that's one con, but I think the other two cons are the ones you're expecting me to say. One of them, of course, is just the flip side. It's hugely simplified and as a result you get less flexibility. Uh, you press the buttons, it gets deployed, and you don't have the same kind of granular control over what's happening. You're just going along with with the way that it got deployed and that's it. And a very similar point, uh, is that the flip side of the batteries included is that you're kind of locked into that way of doing things. So so if you don't like that kind of battery, you can't you can't swap it out for a different brand. That's what it came with. Uh, so you're sort of locked in in the case of Amazon Bedrock agent core, uh, you're locked in to to the Amazon infrastructure. Of course, that's where it's getting deployed. You're going to be, uh, pretty much locked in to the different choices around things like observability and stuff like that. Now, that's not fully true because, for example, as you'll see, Amazon Bedrock Agent Core is actually very flexible about the underlying agent platform that you use. You don't have to use Amazon's one. You can switch in any of them. And they and they make a big point about saying that a lot. So they've actually gone out of their way to try and give you some flexibility. But still, the deployment itself is very much, uh, sort of all packaged up in the way that Agent Core works. Your the great benefit is you don't have to worry about things like Lambda and IEM and, and, and app Runner and so on. It just all just happens. But the downside is you don't get that kind of of detail of figuring out, all right, I want to be able to scale this independently from this. I want to have these in secrets. I want to do this, that, that just all gets taken care of for you. And so as a result of that, at least as of today, in my experience, these agent platforms are not very common for production deployments. Certainly for enterprise production deployments, it is much more common to do it the way that I've taught it on this course. You'll be pleased. You'll be relieved to hear it wasn't a complete waste of time. That is the way people build enterprise systems. It is by building out AWS services, by using Terraform or doing that on on GCP or Azure, and having the fine grained control over everything that's going on. That's how large scale systems are deployed. These new agent platforms are vying for for their place in the world. I think startups are using them. So so people do it for particularly for, for newer products and for trying things out. But but it's it's not particularly the way that you would roll out a full spec, scalable production platform, which is why I've left it to more of the teaser at the end for us to go play with it now, get some experience with it. But it's not necessarily a core ingredient, but it's definitely worth watching to see what happens with these agent platforms in the future. I might compare it to something like a Heroku. For people that have used Heroku, like a sort of packaged app, or again, to Vercel, it's very much a kind of easy, streamlined, simplified build and deploy. Don't need to worry about all of the plumbing it's taken care of for you.

</details>
