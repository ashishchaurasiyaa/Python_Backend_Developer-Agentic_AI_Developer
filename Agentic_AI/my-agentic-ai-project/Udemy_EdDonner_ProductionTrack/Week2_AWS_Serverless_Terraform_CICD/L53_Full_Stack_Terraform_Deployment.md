# L53 — Automating Full-Stack AI Deployment with Terraform and AWS

> **Week 2 · Day 4** · ⏱️ ~9 min

---

## 🎯 TL;DR

Pehle ek skipped step fix karte hain — **`outputs.tf`** define karna (CloudFront URL waghaira outputs ke liye) — phir **moment of truth**: `terraform init` chala ke `./scripts/deploy.sh dev` se poora dev environment (Lambda, API Gateway, S3 buckets, CloudFront) ek hi command mein live deploy karte hain, aur AWS console mein Lambda/S3 ke andar jaake verify karte hain ki memory aur sab kuch sach mein kaam kar raha hai.

---

## 🗣️ Hinglish Explanation

### Step 0: Ek skipped step — `outputs.tf`

Ed admit karta hai ki excitement mein wo **"step five" skip kar gaya** — outputs file. Yeh banana zaroori hai.

Terraform mein **outputs** wo values hoti hain jo `apply` ke baad print hoti hain (aur dusre tools/scripts read kar sakte hain). By convention file ka naam **`outputs.tf`** hota hai (par koi bhi naam chal jaata hai — Terraform saari `.tf` files ko "scrunch together" karke ek hi config banata hai).

Terraform folder mein `outputs.tf` banao:

```hcl
# outputs.tf — environment up hone ke baad jo attributes bahar aayenge

output "cloudfront_url" {
  description = "CloudFront distribution ka URL — yahin jaakar app khulega"
  value       = aws_cloudfront_distribution.frontend.domain_name
}

output "api_gateway_url" {
  description = "API Gateway endpoint — frontend isi ko call karta hai"
  value       = aws_apigatewayv2_api.twin.api_endpoint
}

output "memory_bucket" {
  value = aws_s3_bucket.memory.bucket
}
```

Sabse important output: **CloudFront URL** — yeh wo address hai jahan jaake live app dikhega. Yaad rakho: deploy script (L52) ne `api_gateway_url` output ko hi read karke frontend env var mein inject kiya tha. Toh outputs sirf "print" ke liye nahi, automation ke liye bhi critical hain.

### Step 1: `terraform init` (manually, ek baar)

Ed Terraform directory mein jaata hai aur init chalata hai:

```bash
cd terraform
terraform init
```

`terraform init` providers (yahan AWS provider) aur modules download karta hai, backend setup karta hai. Output mein "installing the right stuff" dikhta hai. **Yeh sirf ek baar manually chalta hai** — baaki saari Terraform commands (`apply`, workspace select) **script** chalata hai, tum manually nahi. Ed bolta hai: "you won't get to type `terraform apply` yourself, but you saw where it was in the script" (L52 mein).

### Step 2: The moment of truth — `./scripts/deploy.sh dev`

Ab Terraform folder se ek directory upar (`twin/` root) jaake script chalate hain. `chmod +x` (L52) ki wajah se yeh ab executable hai:

```bash
cd ..                       # 'twin' directory mein wapas (Terraform se ek upar)
./scripts/deploy.sh dev     # workspace = dev → poora dev environment
```

Last argument **workspace ka naam** hai: `dev`, `test`, ya `prod` — script inhi teen words mein se ek expect karta hai. `dev` dene ka matlab: ek poora **"universe"** ban jaayega jisme har resource ka naam `twin-dev-*` hoga (`twin-dev-s3`, `twin-dev-memory`, `twin-dev-frontend`, etc.).

Script chalte hi kya hota hai (Ed real-time describe karta hai):

1. **"Deploying..."** — script `backend/` mein package banata hai. `backend` folder mein ek **Lambda package zip** ban jaati hai.
2. Phir **Terraform stuff** chalta hai — console mein dikhta hai resources create ho rahe hain: **S3 buckets, CloudFront distributions** — sab live ban rahe hain jab hum dekh rahe hain.
3. **CloudFront ka wait** — yaad hai manually console mein CloudFront distribution **5-10 minutes** leta tha aur refresh dabate rehte the? Terraform isse **polling** se handle karta hai — har **10 seconds** par batata hai "still creating", aur yeh 5-10 min tak chalega. Ed bolta hai "fast forward into the future" (par tum khud chala rahe ho toh wait karo).

> 🧠 Day 2 ki appreciation: Ed kehta hai agar tum Day 2 ki manual journey se nahi guzre hote (console mein har resource hath se banaya), toh is automation ki "magic" appreciate nahi karte. "You'd think it's just a script — but you know that it sucks and it's difficult, and this is making it easy."

### Step 3: Deployment complete — verify in browser

5-10 min baad **"Deployment complete!"** aur **CloudFront URL** print hota hai (yeh `outputs.tf` ka wahi output jo last-minute add kiya). Link follow karo:

- Browser khulta hai → **digital twin** dikhta hai. ✅
- "Hi there" type karo → cheap **micro model** se response aata hai. Yeh us API ko call kar raha hai jo **abhi-abhi Terraform ne banaya** (yaad rakho humne pichhle saare resources delete kar diye the — toh yeh definitely fresh Terraform-created hai).
- **Memory test**: "My name's Alex" → phir "What's my name?" — model thoda confuse hota hai (micro bahut chhota hai), par conversation history clearly recall karta hai ("you mentioned your name was Alex"). Memory working. 🎉

Ed: "We just did, like, a whole day's worth of work of setting up and configuring in one short script."

### Step 4: AWS Console mein verify (proof)

Browser se convince ho gaye, par console se bhi proof lete hain. **IAM user** (R user) se sign in karke:

- **Lambda** → ek function `twin-dev-API` dikhta hai — yeh Terraform ne banaya. Code set hai, **environment variables** check karo:
  - `BEDROCK_MODEL_ID` = `micro`
  - `CORS_ORIGINS` = CloudFront distribution ke saath match karta hua (taaki sirf wahi origin allowed ho)
  - S3 memory bucket name + `USES_S3 = true`
- **S3** → bucket `twin-dev-memory-<accountId>`. Andar ek **JSON blob** (kyunki sirf ek conversation hui). Kholo → wahi confusing "Alex" conversation, aur name JSON mein clearly present. **Memory really working — it's going into S3.** ✅

> 💡 Naming pattern note karo: `twin-dev-API`, `twin-dev-memory-<accountId>`. Workspace naam (`dev`) har resource mein inject — isliye dev/test/prod parallel coexist kar sakte hain.

### Bade picture: Terraform vs. manual

Jo Day 2 mein poora din laga (console mein S3, Lambda, API Gateway, CloudFront, IAM roles, CORS sab hand se), wo ab ek `./scripts/deploy.sh dev` mein automatically ho gaya. Yeh **reproducible, repeatable** hai — yahi IaC ka core value hai.

---

## 📋 Key Concepts

| Concept | Matlab |
|---|---|
| **`outputs.tf`** | Terraform outputs (CloudFront URL, API Gateway URL, bucket names) — print bhi hote hain, scripts bhi read karte hain |
| **Convention naming** | `.tf` files ka naam (outputs/variables/main) sirf convention hai; Terraform sab merge kar deta hai |
| **`terraform init`** | Providers/modules download — ek baar manually chalta hai |
| **`./scripts/deploy.sh dev`** | Poora dev environment ek command mein build + provision + push |
| **Workspace = "universe"** | `dev`/`test`/`prod` — har resource ka naam `twin-<ws>-*`, fully isolated |
| **CloudFront polling** | Terraform 5-10 min CloudFront creation ko har 10s poll karke handle karta hai |
| **Lambda env vars** | `BEDROCK_MODEL_ID`, `CORS_ORIGINS`, S3 bucket, `USES_S3` — Terraform inject karta hai |
| **CORS_ORIGINS** | CloudFront URL se match — sirf authorized frontend hi API call kar sake |
| **S3 memory verification** | Conversation JSON blob bucket mein — proof ki memory persistent hai |

---

## 💼 Backend Dev Ke Liye Note

Yeh lecture **end-to-end deploy + verify discipline** sikhata hai jo har backend engineer ko aana chahiye. Do takeaways: (1) **Outputs ko first-class samjho** — wo sirf vanity print nahi hain, downstream automation (frontend env injection) ka contract hain. Tumhare Terraform outputs ko ek API/interface ki tarah treat karo. (2) **"Deploy ke baad verify karo, sirf script success par bharosa mat karo"** — Ed deliberately console mein jaakar Lambda env vars, CORS config, aur S3 memory blob check karta hai. Production mein yeh habit invaluable hai: green checkmark ≠ correct behavior. CORS_ORIGINS ko CloudFront URL se match karna ek classic full-stack security detail hai — agar `*` chhod do toh koi bhi origin API hit kar sakta hai. Naming convention (`twin-dev-API`) bhi note karo: environment ko har resource name mein bake karna observability aur cost-attribution (tagging/filtering by env) ke liye crucial hai. Yeh wahi pattern hai jo tum prod systems mein dekhoge — service-env-component.

---

## ✅ Takeaway

- **`outputs.tf`** mat bhoolo — CloudFront URL, API Gateway URL, bucket names; yeh deploy script bhi consume karta hai
- `terraform init` ek baar manually; baaki (`apply`, workspace) sab script chalata hai
- **`./scripts/deploy.sh dev`** ne poora full-stack dev environment (Lambda + API Gateway + S3 buckets + CloudFront) ek command mein live kar diya
- CloudFront ka 5-10 min creation Terraform automatically poll karke handle karta hai
- Browser + **AWS console** dono se verify: Lambda env vars (`micro`, CORS, S3), aur S3 mein conversation JSON blob = memory really working

---

<details>
<summary>📜 Full Transcript (English)</summary>

Oops. Did you spot my intentional error there? I, uh, I seem to have skipped step five in my haste to get to using Terraform. Uh, which would be a mistake. Step five defining the outputs file Terraform outputs needs to be done as well. Maybe you did it already and you're thinking, why didn't I do that? Uh, you should have told me. So. I copy this file and we go into our Terraform directory. You'll see that I did not create that right click new file. And this one is called outputs. Remember in practice, all these TF files get get scrunched together by Terraform. The outputs file is just by convention you call it outputs TF. You can call it whatever you want. But this defines the different um attributes that will that will come out, uh, once the whole environment is up and running. And there they are. Things like the most importantly, the CloudFront URL, that is the URL CloudFront distribution that we'll be able to go to. Um, but these are the variables that come out of the end. All right. Okay. Again Another moment of truth. Moment of truth. Let's let's do this. So we start by going into the Terraform directory. CD Terraform. Okay. And now the first of the Terraform commands which is terraform init. Okay. Are you ready for this Terraform init. And this is what we're expecting to see. Okay. It's installing the, uh, the the the right stuff seems promising. And once it's done this, we're then going to kick off our deploy. That's going to be the moment when we, when we run this. And all of the other Terraform commands that we have to run are going to be run by our script, not by us. So you won't get to type Terraform, apply yourself. But you saw where it was in the script. Okay. So that that was successful. Um, and uh, it seems to be happy. So we're now going to go up a directory when it says CD twin, it means be sure that you're in the directory called twin, which is one up from Terraform. And now we go into and now that that's it. And this is how you, you kick off a script. We can do this now on a mac because we, we did that chmod command. That means that this is now an executable. So I type dot slash scripts slash deploy SSH. And now after this we put the namespace that we want to use the workspace. Sorry that is like a namespace. And that should be the word dev test or prod. Because our script is designed to look for one of those three words. And that will allow us to set up an entire parallel environment of all of those different bits of infrastructure for each of those, uh, different workspaces. And the name of each thing is going to be twin dash, dev dash, uh, S3 or whatever, or memory or front end, uh, twin dash, test dash and so on. So I'm going to do the word dev, which means we're going to get a, a whole universe created for us with dev as the workspaces for that environment, for our development environment. And let's do it. So it's it's going to say it's saying deploying. Uh, it's too fast for me to give a, a commentary, but it's running that script that packages things up in back end. So if I look in back end right now, uh, um, here we go. It is creating this Lambda package. Um, and it just made a zip file and it's now this is running the Terraform stuff. You're seeing it creating all of these different resources, S3 buckets, CloudFront distributions. It's all happening while we watch. Uh, this is extremely exciting. And I feel I feel like if you hadn't been through the journey of day two of this week, you wouldn't appreciate the heavy lifting that's going on. You would, uh, you'd think, okay, so it's just a script, but, you know, everything that's happening and you know that it sucks and it's difficult. And this is making it easy. Now, one of the things you may remember is that actually getting the cloud distribution, uh, up there took 5 to 10 minutes of waiting and we just had to keep pressing refresh. And you might have wondered, how is the Terraform script going to handle the fact that we have to wait until that completes? And now you're seeing it, handles it by polling and by telling you every 10s that it's still creating, and it's going to do this for the next 5 minutes or 10 minutes. Even so, this is another time when I'm going to suggest that you fast forward into the future. Unless you're running this yourself, in which case which you should be. So you'll be having to wait. Wait 5 to 10 minutes and I will see you when it completes. And hopefully we have a complete infrastructure built just like that. Okay. Well, what do you think? Is it going to work first time? Here's what I see. I hope you see something very similar. We've got all of the positive outputs here. Deployment, complete exclamation mark and the CloudFront URL. This is one of the outputs from the outputs file that I slipped in the last minute that I almost skipped. Uh, okay. I'm going to follow this link and drumroll please. Here we go. Open up it comes. Well we're seeing a digital twin. That's a great sign. Let's say hi there. And this is using that very cheap model, I think. So it should be. Uh, there we go. It's working. That's just called an API that we just created. Remember we deleted all of the resources. So this is all definitely created by Terraform a whole environment. All of the steps that we took has just happened automatically. And we've just got back a response. I guess we should check that the memory is working. Um, my name's Alex. Uh, see if this this works. Uh, um, what's my name? Ah ha ha. Looks like I can record. Uh, it's got the models too small to handle this. I'm pretty sure we've got memory. Um, how can we possibly, uh. Let me just try it again. My name's Alex. How did I introduce myself just then? Let's try this. Introduce myself then. A bit of a mix up, but you mentioned your name was Alex. That's good enough. Let's not confuse the micro. Uh, the model, uh, with this perplexing conversation. The bottom line is it's got the conversation history. This stuff is working. Terraform deployed. We just did, like, a whole day's worth of work of setting up and configuring in one short script. And, uh, you should now test this and satisfy yourself. Convince yourself that this is, in fact, working. But we can do more than convince ourselves that this thing is working. We can go to the AWS console. We can go in, sign in as our R user, and we can go and have a look at Lambda and see what's there. And what we'll find is that there is a lambda function called twin dash dev dash API. That is the version that's just been created by our function, uh, by by our Terraform script. Sorry. And we can come in and we can see it all here. We'll see that the code has all been set up. You could go in and convince yourself that environment variables have been set, uh, including uh, the, uh, all of the right variables, including let's let's go and take a look. Let's go into environment variables. And we'll see here the bedrock model ID is micro. The cause origins has been set to match the CloudFront distribution that it made at the end. The S3 bucket is a bucket going into memory and uses three is true. Let's go and have a look at that S3 bucket. Let's just check that everything is really working here. Go back to search for S3, bring up S3. Uh, here is a twin dash dev dash memory and then the account ID at the end of it. Let's select that. Let's go into it and then let's uh, go into this JSON blob right here. And this one JSON blob, because we only had one conversation, let's open it and just see the confusing conversation about Alex. And the name is right there. It's working. It's really working. This is going in S3. The the all these resources are there. You can go and check all of them. They will all be there. This is terrific.

</details>
