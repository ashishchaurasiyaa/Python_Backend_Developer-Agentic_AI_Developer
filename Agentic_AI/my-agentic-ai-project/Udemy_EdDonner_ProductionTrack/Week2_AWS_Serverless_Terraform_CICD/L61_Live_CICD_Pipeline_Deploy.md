# L61 — Live CI/CD Pipeline Deploy: From Git Push to Production AI Agent

> **Week 2 · Day 5** · ⏱️ ~12 min

---

## 🎯 TL;DR

Ab moment of truth — `git add` → `git commit` → `git push` karte hi GitHub Actions automatically dev par digital twin deploy kar deta hai. Phir manually `workflow_dispatch` button se **test** aur **prod** environments mein bhi promote karte hain — three-for-three successful deploys, sab live URLs par chal rahe.

---

## 🗣️ Hinglish Explanation

Yeh L60 ka continuation hai — saara setup ho chuka (backend.tf, secrets, deploy/destroy workflows). Ab actually pipeline chala ke dekhna hai ki ek `git push` se kya hota hai. Ed nervous hai kyunki bahut kuch setup hua hai aur kahin bhi ek choti typo sab tod sakti hai.

### Step 1: Git ki current situation dekho

```bash
git status
```

Output dikhayega jo files change hui:
- Do **deploy scripts** (Mac/Linux + PC versions)
- Do **destroy scripts**
- Terraform **`backend.tf`** (jo abhi add kiya)

> Note: `git status` ne `.github/` folder ko explicitly nahi dikhaya kyunki wo ek nayi directory hai — isliye `git add .` ke baad clear dikhega.

### Step 2: Stage, commit, push

```bash
git add .
git status        # ab sab dikhega — deploy + destroy workflows + scripts + backend
```

Ab sab kuch dikhega: destroy aur deploy workflows ready, scripts ke updates, aur backend.

```bash
git commit -m "Add CICD with GitHub actions"
git push
```

Ed mazaak karta hai "could be famous last words — may not work first time." Push ke baad GitHub par chala jaata hai.

### Git aur GitHub Actions ka connection — yeh kaise chala?

Background samajh lo: `deploy.yaml` mein `on: push` trigger tha. Iska matlab — jaise hi koi commit GitHub par push hoti hai (specified branch par), GitHub automatically ek **runner** (ephemeral Linux VM, `ubuntu-latest`) provision karta hai aur workflow chalata hai. Tumhe kuch manually nahi karna — `git push` hi trigger hai. Yahi **CI/CD ka core idea** hai: code change → automatic build + deploy, koi manual intervention nahi.

### Step 3: GitHub Actions tab par watch karo

GitHub par repo kholo → top par **Actions** tab → turant ek workflow run dikhega "Add CICD with GitHub actions" — **yellow** (running). Top-left mein do workflows list honge: **Deploy Digital Twin** aur **Destroy Environment**.

Deploy workflow par click → run par click → "deploying to dev" dikhega, 50+ seconds se chal raha. Click karke **live logs** dekh sakte ho.

Steps jo chal rahe (familiar hone chahiye):
1. **Checked out the code** — repo VM par aaya
2. **Configured AWS credentials** — OIDC se role assume hua
3. **Set up Python**
4. **Installed UV**
5. **Set up Terraform**
6. **Set up Node**
7. **Running the deployment script** ← yeh main hai

Deployment script ke andar (super familiar lab steps):
- **Lambda package build** → **zip** banana ("creating the Lambda deployment package, creating the zip file")
- **Initializing the backend** (S3) → Terraform remote state se connect
- **CloudFront distribution** banana — yeh sabse slow step hai, ~5 minutes leta hai

### CloudFront itna slow kyun?

Background: **CloudFront** AWS ka **CDN (Content Delivery Network)** hai. Jab tum ek CloudFront distribution create/update karte ho, AWS use **duniya bhar ke edge locations** par propagate karta hai (hundreds of POPs). Yeh global propagation hi time leta hai — isliye har deploy mein CloudFront step ~5 min lagta hai. Ed bolta hai wo "future mein jump" karega kyunki itna time wait nahi kar sakta.

### Final steps — frontend build aur invalidation

CloudFront complete hone ke baad:
1. Script ko **bucket name** aur **memory bucket** mil gaya (Terraform outputs)
2. Ab **frontend package build** hota hai — Next.js page **compile** hoti hai with **right fetch URL** taaki frontend sahi backend (API Gateway) ko call kare
3. **CloudFront invalidation** — purana cached content clear karke latest serve karta hai

### CloudFront invalidation kya hai?

CDN content **cache** karta hai performance ke liye. Jab tum naya frontend deploy karte ho, edge caches par purana version pada rehta hai. **Invalidation** = CloudFront ko bolna "is path ka cache hata do, origin se fresh laao." Tabhi users ko latest version dikhta hai.

Deployment summary print hota hai: **Deployment complete** — CloudFront URL, API Gateway, front-end bucket — sab successfully complete.

### Step 4: Live deployment test karo

Deployment summary step kholo → ek chhota report dikhta hai jismein **CloudFront URL** hai. Us link par click → browser khulta hai → **digital twin** aata hai. Ed type karta hai "Do you like cheese?" → meaningful AI response aata hai. **It worked!** Frontend → API Gateway → Lambda → Bedrock (Nova) — poora chain live production mein chal raha.

Ed perspective deta hai: agar pehli baar CI/CD pipeline bana rahe ho, toh yeh bahut kaam laga (Terraform + AWS permissions ka faffing). **DevOps background na ho** ya **Jenkins pipeline** kabhi setup na ki ho, toh shayad andaaza na ho ki yeh kitna grueling ho sakta hai — reliable automated infra+deploy pipeline banana **weeks ka kaam** ho sakta hai. Ek hi din mein sab ho gaya, yeh fantastic hai. Aur agar koi error aaye toh roll up sleeves — typically ek chhoti typo hoti hai jise track karna mushkil hota hai.

### Step 5: Test aur Prod par promote karo (manual)

Dev toh `git push` se auto deploy ho gaya. Par **test** aur **prod**? Wo **manually trigger** karne padte hain (`git push` par nahi).

> Theory: tum GitHub Actions mein clever automation bhi laga sakte ho — jaise PR accept hone par auto-promote — par abhi manual rakhte hain (safety + control).

Manual trigger ka tarika:
1. GitHub → **Actions** → **Deploy Digital Twin** workflow
2. Right side par **Run workflow** button → dropdown
3. Environment select karo (e.g. **test**) → **Run workflow**

### Pehli baar create, baad mein sirf update — Terraform ka magic

Ek important question Ed address karta hai: pehli baar run par humein chahiye ki saara infra **create** ho; subsequent runs par sirf **deploy/update** ho. Yeh kaise kaam karta hai?

**Answer: Terraform state ka magic.** Terraform ke paas state hota hai (remember, ab S3 backend mein). Wo jaanta hai ki kaunse resources already exist karte hain, aur **duplicate nahi banata**. Tum same Terraform script baar-baar chala sakte ho — wo:
- Jo exist nahi karta → banata hai
- Jo exist karta hai → as-is rehne deta hai ya update karta hai
- Kabhi duplicate nahi karta

Yahi Terraform ki asli power hai: na sirf create/destroy, balki **state maintain** karna. "Just trust Terraform" — yahi iska core philosophy hai (idempotency).

### Results — three for three

- **Test deploy** → green tick → "Deploy to test" → deployment summary → CloudFront URL → live, working
- **Prod deploy** → Actions → Deploy Digital Twin → Run workflow → **prod** → Run → green tick → naya tab → "Add Digital Twin" → live on the public internet → meaty response

**Three for three** — dev, test, prod sab successful, sab apne URLs par chal rahe (prod ek public URL par). Ed bolta hai "beginner's luck" — but actually yeh proper setup ka result hai.

Recap dekhne ke liye: Actions tab → Deploy Digital Twin → har run mein steps dikhte hain → "deploy to dev/test/prod" → har ek mein **Deployment Summary** step jahan se URL milta hai. Prod deploy ne ~5 min 29 sec liye (mostly CloudFront).

---

## 📋 Key Concepts

| Concept | Matlab |
|---|---|
| **`on: push` trigger** | Commit push hote hi GitHub Actions auto-runs workflow — CI/CD ka core |
| **GitHub runner** | Ephemeral Linux VM (`ubuntu-latest`) jahan workflow chalta hai |
| **CloudFront (CDN)** | Global edge network — deploy slow (~5 min) kyunki worldwide propagate hota hai |
| **CloudFront invalidation** | Cache clear karke latest content serve karna |
| **Frontend build with fetch URL** | Next.js compile hoti hai sahi backend (API Gateway) URL ke saath |
| **`workflow_dispatch`** | Manual trigger button — test/prod yahin se promote karte hain |
| **Terraform state idempotency** | Same script baar-baar chalao — exist karne wale resources duplicate nahi hote |
| **Deployment summary** | Workflow ka output report — CloudFront URL, API Gateway, buckets |
| **Multi-environment promote** | Dev (auto via push) → test → prod (manual dispatch) |

---

## 💼 Backend Dev Ke Liye Note

Backend dev ke liye yeh lecture **CI/CD ka end-to-end mental model** solidify karta hai. Sabse valuable insight: **Terraform idempotency**. Yeh exactly waisa hi declarative model hai jaisa Kubernetes manifests ya database migrations (kind of) — tum **desired state** declare karte ho, tool **reconcile** karta hai actual vs desired. "Run same script repeatedly without duplication" guarantee hi production-safe automation ki bunyaad hai. Doosra: **environment promotion strategy** — dev auto, prod manual. Yeh deliberate gating hai; production mein tum age chal kar approval gates, manual judgement, ya GitHub Environments + required reviewers add karoge. Aur CloudFront invalidation wali baat backend caching ke principles se relate karti hai — kabhi bhi tum kuch cache karte ho, **invalidation strategy** chahiye warna stale data serve hoga. Ed ka "weeks of work" wala point bhi real hai: jo log Jenkins/ArgoCD/GitLab CI manually setup kar chuke hain wo jaante hain ki reliable IaC + deploy pipeline banana non-trivial hai.

---

## ✅ Takeaway

- **`git add . && git commit && git push`** — bas itne se dev par automatic deploy ho gaya (CI/CD live)
- Workflow ke steps log mein live dikhte hain; **CloudFront** sabse slow (~5 min, global propagation)
- Deploy ke aakhir mein **frontend build (sahi fetch URL ke saath) + CloudFront invalidation** hote hain
- **Test/prod** manual `workflow_dispatch` button se promote karte hain — deliberate safety gating
- **Terraform state idempotency**: same script baar-baar chalao, duplicate resources nahi bante — yahi "magic" hai
- Three-for-three deploys (dev/test/prod) — sab live, prod public URL par

---

<details>
<summary>📜 Full Transcript (English)</summary>

Okay, let's do this. So I bring up a new terminal. I'm nervous. I got to admit, we've done quite a lot. Uh, here we go. New terminal. So, uh, git status tells us the situation. We've got these two deploy scripts, two destroy scripts, and we've got, uh, the Terraform backend that we've added as well. Um, and it doesn't show us here, but we've also got the, the GitHub part of it too. So let's do git add. It doesn't show us. Sorry, because it's just showing us the whole directory there. When we do git add dot. Now we do a git status. We should see everything. Here it is. We've got the destroy and deploy workflow ready to go. And then all of our updates to the scripts and backend. Git. Commit minus m could be famous last words. It may not work. First time. We'll see. And then git push and we'll see what happens. Off it goes. Let's go over to GitHub. So here we are in GitHub again. We come up and now we go to actions at the top here. Press there. And right away we see that there's a workflow that is running called add Cicd with GitHub actions. It's yellow and it's running. And you can see on the top left here there's there's two workflows deploy digital twin and destroy environment. And if I click on that first workflow we can see right here that it is running. And if I click in on this then we come in here and we see it's been running for 50 52 seconds now deploying to dev. Uh, and uh, things are happening and we're hoping that this is going to complete and our twin will have been deployed. Remember, we destroyed all infrastructure. So there's there's no digital twin right now. Uh, and it is hopefully deploying as we speak. Click into it. We can actually see what's going on. We can watch it happening. It's, uh, no surprise. Of course. It's in the cloud distribution part. Let's just scroll up and see what's been happening before this point. Uh, we see in, in in here running the deployment script, we see all of the different tasks. It checked out the code, configured the AWS credentials, set up Python, installed UV set up, Terraform set up node. It's currently running the deployment script. Here you can see all of it going uh, this is super familiar. I hope this is the part where it where it builds the, uh, the Lambda package and then zips it up, creating the Lambda deployment package, creating the zip file, initializing the backend. Uh, S3 uh, and, uh, yes, you can see, see all that's happening. Uh, I'm obviously not going to be able to keep this running commentary going for the full five minutes that it takes to, uh, to, to set up, uh, the CloudFront distribution. So I'll do the usual thing of going to the future. But this is so exciting. I'm going to be to be riveted looking at this and hoping for a home run and a first time deploy live. Fingers crossed. Let's see. So I can't resist giving you like, the live action commentary. It just completed CloudFront. It's going super fast. Uh, and uh, it's just, um, it's now because it's now done the deployment. It's got the bucket name and the memory bucket. But what it now needs to do is, of course, that final step of now building the front end package and deploying that with the right variables so that it has the right fetch URL so that the front end fetches the right back end. So that's what it's just compiled the Next.js page while I watch it. Just uh, this this this will run faster than I can speak. It's just, uh, finished that it got the deployment. Um, it's invalidated CloudFront so that the, the it refreshes with the very latest and it's just saying as the deployment summary, deployment complete CloudFront URL, API gateway, front end bucket and it's all finished successfully complete job. So, uh, I've been following along. You obviously don't need to. What you may well have done is just have gone to this, uh, this, this job, and you'll have seen this list of tasks that all ran successfully. The biggest one, of course, was the five minutes spent mostly configuring CloudFront. And what you can simply do is open up this deployment summary here, and you see a little report of where to go. And this tells you where we will find our running deployment. Let's try that now. So here we go I'm going to press uh link on on this link on the CloudFront URL. Earl. And up comes a digital twin. Uh. Hi there. Does it work? Fingers crossed. Is it going to get to our back end? Is it going to call AWS? And there we go. It worked. It worked. Do you like cheese? Why not? Do you like cheese? Let's see. Ah, there we go. We get a good answer. So. Wow. Ha! Uh, it it just worked. Uh, again. Uh, we this is this is very sophisticated. And if this is the first time that you've built, like, a CI, CD pipeline, you might be thinking this was an awful lot of work. It was a huge amount of configuration and faffing around with with that Terraform stuff and with AWS permissions. But you may not appreciate if you haven't. If you're not from a DevOps background or you haven't gone through and set up like a Jenkins pipeline before, you might not know how grueling this can be. This can be like weeks of work to set up a reliable, uh, process that can deploy build infrastructure automatically and deploy to to to dev like this on doing a git push that kind of thing is really, really hard. And so the fact that we got all of this done during during one day is in fact fantastic. And you should be blown away by by, dare I say it, by how easy this was. It probably didn't feel that easy, but, but but we did get it all done and it worked. And if yours isn't working, got some error, then roll up sleeves. I imagine there's gonna be just something, somewhere so easy. Any any tiny typo can cause a problem and they can be quite hard to track down. So. So that will be something for you. But I'm hoping that you've had the same experience as me here. And it just worked. And it's set up and it's deployed. And that is really, really cool. Uh, and, uh, just to show you one more time, if we if we go back to GitHub actions again, I'm just going to go, go right back. If it's supposing that we were looking at our code right here, we could click on actions. This brings up GitHub actions. Here you see the one the workflow run that we just did. You can see that it's my only run and it was successful. First time a beginner's luck. Uh, and uh I'm going to click on uh Deploy Digital Twin over here to look at the this this workflow. Here it is. It ran nine minutes ago. You can click in on it. Uh, there it is. Deploy to dev. Uh, that took five minutes and 29 seconds. You click into this, you see the different steps. You come down to deployment. Summary. This is where you go to get your URL for this deployment. Okay. Congratulations. Uh, and uh, we will do a little bit more testing. The next thing to show you is that we just deployed to dev by just doing a git push, just doing a git push. And off it went to dev and built the infrastructure. And it's a go. You might be wondering, okay, how about, uh, how do we do test and and prod? Well, we've got that set up. So you have to do that manually. You have to kick that off manually. You manually. You don't have to do anything manual. You have to you have to trigger it manually. Not not on a git push. But of course you can set things up in GitHub actions. You can do clever stuff like when someone accepts a PR review or does something. It can all happen automatically, but for now we are going to do it manually. And the way that you trigger that is that we go we go to GitHub actions over here we go to Deploy Digital Twin. This workflow over on the right here is a button run workflow. We press that drop down. We say that we want to deploy to test. You see how easy this is. And we press Run workflow. And that is now going to run a deployment to test. And one of the things that maybe you're wondering I don't know is uh, okay. But so basically the first time we run this, we want it to create all of the infrastructure subsequent times. We just want it to, to deploy. How is that going to work? And the answer is that that that works. By the magic of Terraform. Terraform automatically has the state. It knows the resources that are there, and Terraform just handles not recreating things when they already exist. So that is just something that we just trust with Terraform. That's that's what it's all about. That that idea, not only is it good at creating and destroying infrastructure, but it's also good at maintaining state. So you can just run the Terraform script again and it knows not to duplicate infrastructure. Uh, that's that's what it's all about. So we're now running the deploy digital twin, uh, to the test environment. And this time I won't get overexcited and give you a running commentary. I will come back in a minute or in five minutes when this has deployed, so we can check it out. And here we are seeing a green tick by deploy digital twin. Uh, so two runs, two green ticks. This is looking good. We go into here we click on deploy to test. We come down to the deployment summary step. Deployment complete. Here's the CloudFront URL. Ready. Drum roll. Click on this. Up it comes. Uh. Hi there. And where we go. It's working. It's working. I'm very happy to see that. Indeed. Okay. And now back to deploy Digital Twin. It's time for us to kick off our production deployment. So back we go. Uh, to, uh, to, to, um, the we'll start with actions and then go to deploy Digital Twin. And then over here we come to run workflow and we're going to choose Production prod. And we press Run workflow and off it goes. Any second now we should see our new workflow running. Is it going to be a hat trick. Am I going to have three for three all successful first time? Uh, we'll soon find out. It's, uh. There it goes. Off it starts. Uh, I will, uh, leave you again. Five minutes for me, a couple of seconds for you, and we'll see if this completes as well. Okay, here we go. Three for three. Uh, am I daring things? Not. Not even going to go in there. I'm just gonna open up a new tab and type add Digital Twin. And here we are. Here we have it. Uh, wow. Uh, this is our digital twin live on the internet. Let's say, uh. Hi there. Uh, check before I. Before I declare victory too early. Let's hope we get back a response. Now, serve me right if we get some failure, but. Well, no, we get a very meaty response indeed. There we go. We have our AI in production deployed three for three. That's really cool. I hope you're having the same experience. I hope that you, now, through the power of GitHub actions, have been able to deploy your latest code to dev, to test and to production. And you, like me, have three apps running here, uh, with uh, one of them being on a public URL. Uh, congratulations.

</details>
