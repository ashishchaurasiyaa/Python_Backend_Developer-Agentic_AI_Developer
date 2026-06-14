# L31 — From Vercel to AWS: Deploying Production LLM Apps at Scale

> **Week 1 · Day 5** · ⏱️ ~6 min

---

## 🎯 TL;DR

Day 5 + Week 1 ka recap aur reassurance: Vercel ka deploy "almost too easy" tha, AWS "almost the opposite" — IAM, policies, ECR, App Runner, CloudWatch sab terminology overwhelming lag sakti hai, par ghabrao mat. Recap: Next.js (TS, pages router, Tailwind) front end + FastAPI backend + Clerk auth/billing → Docker container (static front end backend mein baked) → ECR → App Runner. Assignment: app ko beef up karo, Vercel + AWS dono par deploy karo, root user se costs check karo. **Tum 25% expert ho gaye!**

---

## 🗣️ Hinglish Explanation

### "Deer in headlights" — ghabrao mat

Ed pehchanta hai ki AWS ke baad bahut log overwhelmed feel kar rahe honge — "deer caught in headlights". Message: **don't worry, go with it.** Yeh information **absorb** karne ke baare mein hai, ek baar mein master karne ke baare mein nahi. AWS bahut bada hai. Repeat karo, practice karo, time ke saath cheezein clear hongi.

**Contrast jo tumne mehsoos kiya:**
- **Vercel** → itna easy tha ki "too good to be true" laga. Code push, live in minutes.
- **AWS** → almost opposite. "User ID set karne ke liye itni mehnat kyun? Yeh saare policies, user groups, permissions attach karna... ECR kya hai, App Runner kya hai, CloudWatch kya hai?" — terminology ka pahaad.

Yeh normal hai. Overwhelm ko zyada hawi mat hone do. (Ed mentions: humne **CloudWatch** abhi tak nahi dekha — agar chaho toh wahan click karke apni app ki logging dekh sakte ho, woh aage aayega.)

### Week 1 ka quick recap — humne kya banaya

Ek **healthcare consultation SaaS** banaya, end-to-end production tak:

1. **Front end** — React, **Next.js** framework par
   - **TypeScript** variant (JavaScript nahi)
   - **Pages router** (App router nahi)
   - **Tailwind CSS** for styling
2. **Backend** — **FastAPI** (Python)
3. **Auth + billing** — **Clerk** (user authentication aur subscription plans)
4. **AI** — **OpenAI** call, results **stream** karke wapas bheje
5. **Packaging** — sab kuch ek **Docker container** mein:
   - Front end ko ek **static front end** mein compile kiya
   - Use backend ne serve kiya — front + back ek hi container mein
   - Locally test kiya — front + back saath chale, kaam kiya
6. **Deploy to AWS**:
   - Container ki **image** ko **ECR** (Elastic Container Registry) par push kiya
   - **AWS App Runner** par deploy kiya — AWS ka simplest container-to-cloud approach, live jaane ke easiest tareekon mein se ek

```text
Week 1 Architecture:
  [Next.js TS + Tailwind front end]  --static build-->  served by
  [FastAPI backend] --calls--> [OpenAI (streamed)]
        |
        +-- all packaged in --> [Docker image]
                                      |
                          push --> [AWS ECR]
                                      |
                          deploy --> [AWS App Runner]  ==> live HTTPS
```

Ed reminder deta hai: aisa laga jaise poora week sirf **configuration** (AWS console, permissions, IAM) tha — par end mein ek **LLM** zaroor involved tha. OpenAI ko call kiya, results stream kiye. Yeh AI-in-production ka groundwork hai.

### Cost check — abhi karo (best practice)

Ek **great practice** abhi karne ki: **root user** se login karo (IAM AI engineer se nahi) aur **Billing and Cost Management** section dekho. Is point par koi material cost nahi hona chahiye, par ye habit zaroori hai — regularly costs verify karna production engineering ka core discipline hai. Sab theek dikhe, confirm karo.

### Assignment

1. **App ko beef up karo** — zyada functionality add karo (jaisa Day 4 mein kaha)
2. **Vercel par deploy karo** — ab yeh "heartbeat" mein ho jaayega, super easy
3. Deep breath lo, phir **AWS par deploy karo** — ab jab sab setup ho chuka hai (IAM, permissions — yahi hardest part tha), toh baaki steps (Docker build → ECR push → App Runner deploy) "not that hard once you've done it a couple of times". Bas karke dekho.
4. **Results ko repo mein daalo**, link share karo, aur **community contributions** mein post karo taaki Ed dekh sake
5. **Bonus idea**: ise ek real SaaS product bana lo — kuch healthcare contacts / doctor's offices ko pitch karo ki yeh automated assistant unki practice ko zyada efficient banayega. "That would be really cool."

### Week 1 closing

Yeh ek **massive Day 5** tha (Ed ne Day 4 ke baad warn kiya tha). Dimag fry ho gaya hoga, par bahut kuch seekha. Week 1 conclude:

- Ek SaaS product banaya
- Production mein deploy kiya
- Vercel par easy, AWS par "quite traumatic" — par pahunch gaye
- Result: **live, scalable, robust, monitorable** — ek **industrial-strength AWS deployment**

Tum ab **production deployment expert banne ke raaste par 25%** ho. Week 2 mein AWS waters mein "big old plunge" — ready raho.

### Pura recap flow

1. Overwhelm normal hai — absorb karo, repeat karo, practice karo
2. Stack: Next.js (TS/pages/Tailwind) + FastAPI + Clerk + OpenAI streaming
3. Packaging: static front end → backend → Docker container (locally tested)
4. Deploy: image → ECR → App Runner (live HTTPS)
5. **Root user se costs check karo** (abhi)
6. Assignment: beef up → Vercel deploy → AWS deploy → community contributions par share

---

## 📋 Key Concepts

| Concept | Matlab |
|---|---|
| **Vercel vs AWS contrast** | Vercel "too easy", AWS config-heavy par industrial-strength |
| **Next.js (TS, pages router, Tailwind)** | Front-end stack: React framework, TypeScript, pages routing, Tailwind CSS |
| **FastAPI** | Python backend framework |
| **Clerk** | User authentication + subscription billing |
| **Static front end in container** | Front end compile karke backend ne serve kiya, ek hi Docker container |
| **ECR** | Elastic Container Registry — image yahan push hui |
| **App Runner** | Simplest AWS container-to-live-website service |
| **CloudWatch** | AWS logging/monitoring (abhi nahi dekha, aage aayega) |
| **Root vs IAM user** | Billing/costs root user se check; daily work IAM user se |
| **25% milestone** | Course ka Week 1 = production-deployment expertise ka 25% |

---

## 💼 Backend Dev Ke Liye Note

Yeh recap ek important architectural lesson reinforce karta hai: **PaaS (Vercel) vs IaaS/managed-container (AWS)** trade-off. Vercel = fast DX, low control, vendor-managed everything; AWS = steep setup (IAM, ECR, networking) par full control, multi-service composability, aur enterprise-grade observability (CloudWatch). Production backend engineer ko dono samajhne chahiye aur context ke hisaab se choose karna chahiye — MVP/prototype ke liye PaaS, scale/compliance/cost-control ke liye AWS. **"Single container, front + back baked together"** pattern jo Week 1 mein bana, woh Week 2 mein evolve hoga: front end CloudFront/S3 par alag, backend Lambda/API Gateway par alag (true serverless decomposition). Cost-check discipline ko ignore mat karo — production mein un-monitored AWS spend (idle App Runner instances, orphaned ECR images, NAT gateways) sabse common surprise bill hai; billing alerts/budgets set karna foundational hygiene hai. Aur note: poora "config-heavy" week effectively ek LLM ko production-serve karne ke liye tha — infra hamesha business logic ka enabler hai, end nahi.

---

## ✅ Takeaway

- **Overwhelm normal hai** — AWS bada hai, absorb + repeat + practice karo, ek baar mein master nahi
- Week 1 stack: Next.js (TS/pages/Tailwind) + FastAPI + Clerk + OpenAI streaming, ek Docker container mein → ECR → App Runner (live HTTPS)
- **Root user se Billing & Cost Management abhi check karo** — kaisi bhi material cost nahi honi chahiye, par habit zaroori
- Assignment: app beef up → Vercel deploy (easy) → AWS deploy (ab setup ho chuka) → community contributions par share
- **25% expert** ho gaye — Week 2 mein AWS ka "big plunge" aa raha hai

---

<details>
<summary>📜 Full Transcript (English)</summary>

Well, I imagine some of you are feeling a bit like a deer caught in headlights with everything that just happened so much. And yeah, I'm here to tell you, please don't worry. Go with it. This is going to be about absorbing more information as we go. There is a lot to AWS. I feel like you might have seen the enormous contrast. It was so easy to deploy to Vercel and get something running. It was almost too easy. It almost felt like that was too good to be true. Uh, and really cool to experience that. And then AWS is almost the opposite experience. It's like, why is it so hard just to set up a user ID just to have access to all this permission stuff, these user policies and then attaching all these policies, user groups? I mean, there's so much terminology. What is ECR and App Runner and CloudWatch and all these other things. Uh, and so uh, yeah, I'm, I'm here to tell you, uh, don't don't let it become too much. We didn't even look at CloudWatch yet but but we're going to uh and that's something that if you wanted to, you could take a click around and see some of the logging that you can see in in CloudWatch there as well. Um, but it's a very quick recap to what we did. We built a front end. Uh, it was a react front end using the Next.js application framework. It's using the TypeScript variant rather than JavaScript. We use the pages router, not app router, and we use tailwind CSS. We built a backend using fast API. We used Clark for user authentication and for subscription plans. And then we packaged everything into a Docker container. And we did it with this approach of having the front end be compiled into like a static front end, and have it be served up by the backend, all in one nice Docker container that we tested locally. And it worked. We could run our front end and back end together in a Docker container running locally. And then we took that container, or to be precise, we we took the image and we pushed that to the the Elastic Container Registry. And then we deployed to AWS App Runner. AWS is simple approach for deploying containers to the cloud. One of the simplest ways to go live on AWS. And we did it. Congratulations, and maybe worth mentioning again, I guess that there was an LLM in here. We we we called OpenAI and we streamed back results. So, uh, whilst it felt like this was all configuration, like we were in AWS console all week long, like clicking here, setting up permissions, uh, but there was an LLM involved at the end of it. So hopefully this has given you some some groundwork. If this feels a lot then do go back through again. Do some some some revision of this. Click around the AWS console. A great practice to do right now is to go back in as your root user and look at the costs. There should be no material costs at this point, but it's a great practice to do so. Please do it right away. Log in as the root user. Check that the cost screens, uh, cost and billing, billing and cost management, uh, section. And make sure that everything looks good. And then the assignment for you. The assignment, of course, as I said in day four, is to go and beef up this app, go and make it have more functionality, more functionality, and then deploy it to Vercel. And that's going to be super easy. You're going to do it in a heartbeat. It's so easy. And then take a deep breath, prepare yourself and deploy it to AWS. Now that you've set everything up, that's really the hardest part is all this configuration, all the IAM stuff, all these other parts. The final steps of just building the Docker container, pushing it to ECR and then building the building and deploying your app runner. That's just it's not that hard once you've done it a couple of times. So that's what you have to do now. You have to go through and do it. And please do put your results in in a repo and link to them and put that in community contributions so I can see the work you've done and the different ways you build this app. And wouldn't it be cool if you actually turned this into a proper SaaS product? Contact a few, uh, healthcare, uh, contacts, a few doctor's offices and see if you can't pitch to them. You're amazing. uh, automated assistant that can help their practice be more efficient. That would be really cool. Anyway, that concludes a massive day five. I warned you, after day four, the day five will be a lot. Your brain might be fried, but you've learned so much. It concludes week one. We built a SaaS product. We deployed it to production. It was pretty easy to go to vassal. It was. It was quite traumatic putting it on AWS. But we got there. We got it done. It's live, it's scalable, it's robust, it can be monitored. Uh, this is a industrial strength deployment onto AWS. And you should be super proud with your progress. I am so happy to tell you that you are 25% through being an expert in production deployment. And I'm really excited. Now to launch into week two. You've you've already you've dipped your toe into the AWS waters. And next week we're going to take a big old plunge. So so so be ready for that. And I'm really excited for it. And I'll see you for week two.

</details>
