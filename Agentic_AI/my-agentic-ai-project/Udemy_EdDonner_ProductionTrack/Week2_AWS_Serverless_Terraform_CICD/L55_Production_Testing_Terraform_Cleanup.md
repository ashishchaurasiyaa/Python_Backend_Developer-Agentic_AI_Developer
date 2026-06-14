# L55 — Testing Production AI Deployments and Terraform Cleanup Workflows

> **Week 2 · Day 4** · ⏱️ ~9 min

---

## 🎯 TL;DR

Production deployment live ho gaya — **custom domain par SSL/HTTPS** ke saath Nova Pro twin chal raha hai (teen parallel environments: dev, test, prod). Phir hum **`destroy.sh`** scripts banate hain aur teeno environments ko ek-ek command se cleanly **tear down** karte hain — Terraform khud S3 buckets empty karta hai, CloudFront/cert/DNS sab delete karta hai, sirf registered domain bachta hai. Day 4 (Terraform) complete — course 45% done.

---

## 🗣️ Hinglish Explanation

### Part 1: Production live test

Prod deployment finish ("too good to be true, but..."). **"Deployment complete!"** + CloudFront URL + ek **custom domain** `edwarddigitaltwin.com`.

Recap: ab teen environments live hain — **development**, **test**, **production**. Prod **secure** hai — custom domain par, **SSL certificate** ke saath (HTTPS).

Test:
- Custom domain kholo → digital twin aata hai. Pehli baar Lambda **spin up** ("cold start") mein kuch extra seconds lagta hai.
- "Hi there" → **Nova Pro** response (better quality).
- "Do you like cheese?" → balanced, intelligent answer — model ne infer kiya ki Ed **French food** pasand karta hai (Ed ne explicitly nahi kaha tha) → richer reasoning, kyunki yeh prod par bada model hai.

> 🧠 Lambda cold start: Serverless function jab der tak idle rehta hai toh AWS use "freeze" kar deta hai. Pehli request par container fresh spin hota hai → kuch seconds ki latency ("cold start"). Subsequent requests fast ("warm"). Yeh serverless ka classic tradeoff hai — zero idle cost, par occasional cold-start latency.

**Console proof**: CloudFront mein ab **teen distributions** — `twin-prod`, `twin-test`, `twin-dev`, plus `digitaltwin` (custom domain wala). Total: 3 distributions, 3 Lambda functions, **6 S3 buckets** (har env ke 2: memory + frontend), 3 API Gateways. Sab live, sab parallel. 🎉

### Part 2: Terraform cleanup — `destroy.sh`

Ab wo skip kiya hua **step 7 (delete/destroy)** karte hain. Pehle do scripts banao (`deploy.sh` ki tarah hi, Mac/Linux + PowerShell):

`scripts/` mein naya file `destroy.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

WORKSPACE="$1"   # dev / test / prod

cd terraform
terraform workspace select "$WORKSPACE"

# Terraform pehle S3 buckets empty karta hai, phir destroy
terraform destroy -auto-approve

echo "Environment '$WORKSPACE' completely destroyed!"
```

PC users ke liye `scripts/destroy.ps1` (PowerShell) bhi. Ed mazaak karta hai: **"deploy aur destroy mix-up karna acchi baat nahi"** — confusingly similar naam. Mac/Linux par phir **executable** banao:

```bash
chmod +x scripts/destroy.sh
```

#### Destroy dev

```bash
./scripts/destroy.sh dev
```

Kya hota hai:
1. **Workspace switch** to `dev`.
2. **Pehle S3 buckets empty** karta hai — yaad hai L52/earlier mein, S3 bucket delete karne se pehle **empty** karna padta tha (non-empty bucket delete nahi hota)? **Terraform "is wise to such trickery"** — yeh khud buckets empty kar deta hai pehle.
3. Poora dev environment systematically destroy — har resource ek-ek karke.
4. **CloudFront "our old enemy"** par phir **5 min** (delete bhi slow hai, kyunki edge locations se content remove karna padta hai).

Ed teeno (dev, test, prod) destroy karta hai — "15 minutes for me" — par tum par 3 × 5 min wait nahi thopta.

#### Important: domain bachta hai

Destroy **registered domain ko remove nahi karta** — wo $15 wala domain tumhare paas rehta hai. Destroy karta hai:
- DNS **records** (sab delete)
- SSL **certificates** (delete)
- Saari associated **S3, Lambda, API Gateway, CloudFront** resources (delete)

Sirf **registered domain** bachta hai. Logical hai — domain ek account-level asset hai (tumne paise diye), infra ephemeral hai.

> 💡 Terraform workspace cleanup: Destroy ke baad Terraform suggest karta hai workspace remove karna (`terraform workspace delete dev`) — par yeh sirf **local Terraform state** se hai, AWS resources se koi lena-dena nahi. Ed bolta hai ignore kar sakte ho.

#### Final verification

Teeno destroy scripts "completely destroyed" bolte hain. AWS console → CloudFront → ab **"Get Started" screen** (no distributions). Teeno environments ke saare AWS services Terraform ne **destroy** kar diye. ✅

Ed ka point: ek script se poora multi-service environment **up** (`deploy.sh`) aur ek script se **down** (`destroy.sh`) — **repeatable aur reproducible**. Slowest part hamesha CloudFront (content globally push/remove karna heavy hai), but "forgive it."

### Wrap-up: Day 4 complete

Architecture diagram (jo tumne "memorize" kar liya) — Terraform ne yeh **poora** create kiya, **teen baar** (dev/test/prod), up aur down dono kiya, teen parallel conversations dekhe, console mein resources appear/disappear hote dekhe. **It works.**

Day 4 of Week 2 done. **Terraform "ticked" — resume par add kar lo, tum ab "Terraform person" ho.** Aage **kabhi console mein nahi futzayenge**.

> 📍 Milestone: **45% of the course complete.** Ed acknowledge karta hai yeh week "grueling" raha. Kal: **GitHub Actions** — ek **`git push`** par automatically sab kuch kick off ho jaayega: Terraform run, poora environment build + deploy, on demand. CI/CD ka magic.

---

## 📋 Key Concepts

| Concept | Matlab |
|---|---|
| **Production live** | Custom domain (`edwarddigitaltwin.com`) par SSL/HTTPS + Nova Pro twin |
| **Lambda cold start** | Idle function ki pehli request par extra latency; baad mein warm/fast |
| **3 parallel environments** | dev + test + prod, har ek isolated: 3 CloudFront, 3 Lambda, 6 S3, 3 API GW |
| **`destroy.sh`** | Workspace select + `terraform destroy` — ek command mein poora env teardown |
| **`terraform destroy`** | Saare managed resources delete (declarative cleanup) |
| **S3 auto-empty** | Terraform delete se pehle khud buckets empty karta hai (manual step nahi) |
| **Domain survives** | Destroy DNS records + cert + infra hatata hai, par registered domain rehta hai |
| **Workspace delete ≠ AWS** | `workspace delete` sirf local Terraform state se, AWS resources se nahi |
| **Reproducible up/down** | `deploy.sh` se up, `destroy.sh` se down — repeatable lifecycle |

---

## 💼 Backend Dev Ke Liye Note

Yeh lecture **infrastructure lifecycle management** ka closing chapter hai — aur ek under-appreciated skill: **clean teardown**. Backend devs aksar "deploy" par focus karte hain par "destroy" ignore kar dete hain, jisse **orphaned resources** (bhoole hue S3 buckets, idle Lambdas, dangling CloudFront) **silent cost** add karte rehte hain. Terraform ka `destroy` exactly isi liye powerful hai: state file jaanta hai usne kya banaya, toh exactly wahi clean kar deta hai — koi guesswork nahi. Do practical lessons: (1) **Terraform ka S3 auto-empty** — Terraform dependency graph aur lifecycle ko samajhta hai (non-empty bucket delete nahi hota, toh pehle objects clear karta hai); yeh dikhata hai ki achhe IaC tools ordering/dependencies handle karte hain jo tumhe manually yaad rakhne padte. (2) **Ephemeral vs. persistent assets ka distinction** — domain (account-level, paid, persistent) destroy se bach jaata hai, baaki infra (ephemeral) chala jaata hai; production design mein yeh line clear rakhna crucial hai (databases, registered domains, secrets = persistent; compute, CDN, ephemeral). Aur sabse bada takeaway: **reproducible up/down lifecycle** matlab tum dev/test environments freely create-and-destroy kar sakte ho without fear — yeh fast iteration aur cost control dono enable karta hai. Kal ka GitHub Actions isi `deploy.sh` ko CI pipeline mein wrap karega — yahi reason tha ki L52 mein PC users ko bhi `deploy.sh` rakhna tha.

---

## ✅ Takeaway

- **Production live**: custom domain par SSL/HTTPS-secured Nova Pro twin; 3 parallel environments (dev/test/prod) — 3 CloudFront, 3 Lambda, 6 S3, 3 API Gateways
- **`destroy.sh`** banaya — workspace select + `terraform destroy`, phir `chmod +x`
- Terraform **khud S3 buckets empty** karta hai destroy se pehle (manual step nahi)
- Destroy **registered domain ko nahi** hatata — sirf DNS records, cert, aur infra delete; CloudFront teardown bhi ~5 min
- Console verify: CloudFront ab "Get Started" (zero distributions) — sab cleanly gaya
- **Day 4 done, course 45% complete** — Terraform mastered; kal **GitHub Actions** se `git push` → auto full deploy

---

<details>
<summary>📜 Full Transcript (English)</summary>

Okay. It's finished. This seems too good to be true, but I doubt it will come. Deployment complete cloud CloudFront URL and there is a distribution custom domain add digital twin. Should we give it a try? What? What do we put money on it. Let's see if it works. First time command click open the third digital twin. It's come up. So just to recap this is development. This is test. This is production coming out of digital twins secure with a certificate with SSL. Let's say hi there and let's see if we get a pro response. It's spinning up a lambda the first time. It will always take a few more seconds than usual. And here we go. There is an answer. It's working. I'm gonna just add, if you prefer. I'm thrilled you found your way. It seems all pretty good to me. Uh. Let's try. Uh, do you like cheese? Let's see if we get a substantive answer. Uh, it was very quick. Uh, uh, there we go. It's quite a balanced answer. That's clever that it that it figured out that I like French food and that makes it unusual. I don't think I said that in my in my spiel. Uh, and, uh, yeah, that's just brilliant. That's brilliant. So here we are, deployed to production live at Digital Twin, or you are live on your URL. Congratulations. And we've got three parallel environments all set up, all in, uh, in AWS. One more time. I know you believe me. This time you didn't believe me the first time, but now you believe me. Now you believe me, I know it. But just to double check, let's go to the cloud. Uh, CloudFront distribution. Here we have it. Uh, there they are. There are the three, uh, twin prod, twin test, twin dev, and there's digital twin there as well. Uh, it's all running three distributions. There'll be three lambda functions. There'll be six S3 buckets. Uh, there'll be three API gateways. It's all there. It's all happening. Congratulations to us. Well, I'm super happy. Everything has just worked out like this. And I think it's a really happy that you've got to see all of it. Let's now just go and finish off with that delete stuff. The destroy that we skipped over. Let's go back to the instructions. Uh, down here day four open preview. And we are, uh, somewhere near the end. We just want to do our deleting of the of the steps. Um, there are some best practices here, some troubleshooting. Uh, and, uh, let's go back up to step seven. Here it is. Okay. So step seven begins by defining a couple of scripts, a shell script for for Mac Linux and a PowerShell script for for windows. Let's create this. And here it is. Copy that. And we're now going to go in to the scripts folder, new file, and I'm going to call it destroy. Destroy shell. That's a new script. Paste in that script and save. And then also go back to this this guide and look for the PowerShell. And we must remember to chmod which we'll do next. Uh windows people don't need to chmod. Uh here we go. Take all of this. Copy this. Make a PowerShell script. Mac people don't need to make a PowerShell script, but I will anyway. New file deploy ps1 o deploy destroy ps1. Uh, and paste and mixing up. Deploy and destroy is not a good idea. Maybe I shouldn't have named them. So similarly, uh, some modding to bring this up to that screen chmod plus x to to scripts. Slash destroy. Ah, Destroy shell. Done. Okay, so now let's see if we can bring down the environments as easily as we brought them up. Starting with the development environment. So we will do um, we will do a dot slash scripts slash destroy dev. Let's see if we can bring down the development environment. Switch to the workspace dev. It's first has to empty the S3 bucket. Do you remember the way we. Before we could delete the S3 bucket, we had to empty them. Well, Terraform is wise to such such trickery and it is already deleting those S3 buckets. It's destroying the whole development environment as we watch. It's going feverishly through all the different things, but where it will, uh, become stuck, I do believe, is when we get to the CloudFront distribution, our old enemy. Uh, so again with the five minutes. Uh, but this time, I think I'm not going to bore you with three sets of five minutes. I'm going to do this, and then I'm going to destroy the test environment. And then I'm also going to destroy the prod environment as well. All of that stuff that we did. And it does not, of course, remove the, the, um, domain that we registered that we paid $15 for. We keep hold of that. It destroys all of the records, it destroys the certificates. It gets rid of all that stuff, uh, leaving us only with the registered domain. All of the associated S3, uh, AWS resources will have been removed. Okay. See you in in just a few seconds, but but in, like, 15 minutes for me. Well, all three destroy scripts ran fine and well and says completely destroyed. And what we can now do, by the way, it then gives you something about removing the Terraform workspace, which is just about removing that from from your Terraform, uh, state here that you can ignore that, that that's not about Amazon resources. Let's bring up our, um, usual AWS console. And let's just convince ourselves, if we go back one more time, let's say to the CloudFront, where we just were, where we saw three, and now we are back to the Get Started screen that you probably saw before. Uh, with a CloudFront distribution, there are no CloudFront distributions. All three sets of AWS services have been destroyed by Terraform. So wasn't that easy? Isn't it great? Now we can now bring up and bring down a distribution, a whole, a whole set of services just by running in one script, and it creates everything, and it does make life so simple and so repeatable and reproducible. And the slowest part of it is creating those, uh, cloud CloudFront distributions. But there's a lot going on there. It's pushing out content all over the place. So we have to forgive it for taking a few minutes to do such heavy lifting. Um, but that does complete the day for, uh, instructions. There's a ton of interesting stuff for you to peruse at the end of this document. Um, which includes after after the optional section that I hope some of you have done with the production deployment, there's a bit more about, um, about looking at, uh, the, the workspace and other things. And there's a bit more about about testing and troubleshooting and the like. So you could have a look through all of that. But we will now go back to the slides to wrap up. And so there you have it. This is again our architecture diagram that you have committed to memory. Now after us going through all those console screens, I hope you forgive me for that. Now that you agree that it adds to the magic of appreciating what Terraform does, it created all of what you see here on this, on this diagram. Uh, and it did it three times over for dev test and prod. And we brought them all up and we destroyed them all. And we checked out three different conversations going on in parallel, and we saw all of the resources appearing and disappearing in the console. It works. And with that, that wraps up day four of week two of your journey to being an expert at product deployment. Uh, Terraform is ticked. You can add that to your resume. Uh, you are now Terraform person, and we'll be putting that to great use in the the remaining two weeks. We will not be futzing around with consoles any more. And with that, congratulations. You are now 45% of the way through, although I'd say it seems to have gone fast, but for this week has been quite grueling. So I imagine you're thinking, ah, it's not been going fast, but, uh, but but it's all it's all great from here. Now that we have Terraform, uh, in our toolkit and tomorrow we look at GitHub actions, which is so cool. It's going to allow us to do a git push and automatically something will kick off run everything including terraform, build a whole environment, deploy it the whole lot just for us on demand. Can you believe it? You'll see it tomorrow by.

</details>
