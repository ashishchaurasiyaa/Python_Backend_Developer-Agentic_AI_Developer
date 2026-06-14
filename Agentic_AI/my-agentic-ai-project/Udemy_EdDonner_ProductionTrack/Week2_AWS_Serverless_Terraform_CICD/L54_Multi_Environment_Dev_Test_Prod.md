# L54 — Multi-Environment AI Deployments: Dev, Test, and Production Setup

> **Week 2 · Day 4** · ⏱️ ~11 min

---

## 🎯 TL;DR

Same `deploy.sh` script ko ab **`test`** workspace ke saath dobara chalakar ek poora **parallel, isolated test environment** khada karte hain (dev + test ek saath coexist), aur phir optional **production deployment** karte hain — **Route 53** se ek custom domain register karke (one-time, ~$15), aur Terraform se SSL certificate + DNS records + Nova Pro model wale `prod` environment ko hook up karte hain.

---

## 🗣️ Hinglish Explanation

### Part 1: Test environment — same script, alag parameter

Ed "mind blow" karne wala hai: wahi `deploy.sh` script, par ab **`dev` ki jagah `test`**:

```bash
./scripts/deploy.sh test
```

Kya hoga: bilkul wahi process — package build, Terraform run — par ab **`test` workspace** selected. Toh saare resources `-test` ke saath banenge (`-dev` nahi). Result: ek **doosra parallel "universe"** — poora AWS infra (Lambda, API Gateway, S3 buckets, CloudFront) — jo dev se **completely independent** hai. Dono coexist karte hain kyunki har jagah naam alag hai (`twin-dev-*` vs `twin-test-*`), aur independently hooked up hain.

> 🔐 Pro tip (Ed se, "exercise for the viewer"): Ek **really professional** approach yeh hai ki **alag-alag IAM users** ho har environment ke liye — taaki **permissions isolation** ho (test user dev ke resources touch na kar sake). Ed ne yeh nahi kiya, but yeh best practice hai. Production systems mein yeh standard pattern hai — least-privilege per environment.

Phir wahi 5-min CloudFront wait → "Deployment complete!" → CloudFront URL.

**Verification:**
- Test ka CloudFront URL kholo → digital twin. "Do you like cheese?" poocho → micro model handle karta hai ("I'm not allergic, but I'm just not a fan"). ✅
- Ek doosre tab mein **dev** ki conversation chal rahi hai. Dono parallel chal rahe hain — dev URL CloudFront distribution `...e0` par, test `...LR` par. **Alag** CloudFront distribution, **alag** API Gateway, **alag** Lambda, **alag** S3 buckets. Poora infra alag.
- **Console proof**: Lambda mein `twin-dev` *aur* `twin-test` dono dikhte hain. CloudFront mein do distributions — ek `twin-test-frontend-<id>`, ek `twin-dev-...`. Do isolated, fully separate, live environments.

> 🧠 Workspace ka magic: Terraform workspaces alag **state files** maintain karte hain. Ek hi `main.tf` code, par `dev` aur `test` ki resources ka tracking alag — isliye ek dusre ko overwrite nahi karte. Yeh "ek code, N environments" IaC ka core power hai.

### Part 2: Production deployment (optional, paid)

Ed **step 7 skip karke step 8 (optional)** par jaata hai — **production deployment with a custom domain**.

**Optional kyun?** Kyunki ismein paisa lagta hai — AWS nahi, balki **domain registration** ki cost (jo AWS bas pass-through karta hai). Normal `.com` ~**$15/year**. Worth it agar tum apne digital twin ko apni URL dena chahte ho, ya bas DNS/domain hook-up ka experience lena chahte ho.

> 💡 Alternatives: Agar tumhare paas already domain hai jisme web pages serve ho rahe hain, toh tum is app ko **iframe** se embed kar sakte ho — domain setup se easier. Par Ed kehta hai full domain setup "great practice" hai, toh wo karega.

#### Step A: Domain register karo — Route 53 (root user, console)

**Route 53** AWS ki **DNS aur domain registration** service hai (naam "53" = DNS ka port 53). Yeh ek **one-time, manual** step hai, aur **root user** se karna hai (IAM user se nahi) — kyunki billing/account-level action hai.

> 🧠 DNS recap: DNS internet ka phonebook hai — `digitaltwin.com` jaise human-readable naam ko IP/endpoint se map karta hai. "Domain registration" = tum us naam ke maalik bante ho. "DNS records" (A, CNAME, etc.) batate hain ki kis naam ka traffic kahan jaaye.

Root user (Ed dikhata hai top par "Ed" likha hota hai) se Route 53 kholo:

1. **Register Domains** → check availability (e.g. `edwarddigitaltwin.com`). Mile toh ~$15.
2. Apna pasand ka domain select karo → registration questions bharo.
3. AWS free **privacy/WHOIS protection** deta hai (personal info chhupata hai).
4. **Email verify** karo, kuch der **wait** karo → registered domain ready.

Ed ka apna domain already registered hai: **`edwarddigitaltwin.com`** (dobara register nahi karega — "too much"). Bas yahi ek manual step chahiye — baaki saare **DNS records Terraform** karega.

#### Step B: `prod.tfvars` banao

Production ke liye defaults override karne ko ek naya config file:

```hcl
# prod.tfvars — production environment overrides
project_name      = "twin"
environment       = "prod"
bedrock_model     = "pro"                 # Amazon Nova Pro — still super cheap, ~Claude Haiku jitna
use_custom_domain = true
domain_name       = "edwarddigitaltwin.com"   # tumhara registered domain
```

Ed **Nova Pro** model use karta hai prod ke liye — "still the same or slightly cheaper than Claude Haiku, so still very cheap." Aur `domain_name` apne registered domain par set.

> 🧠 Amazon Nova family: AWS ke apne foundation models on **Bedrock** — Nova Micro (sabse sasta, text-only), Nova Lite, Nova Pro (zyada capable). Dev/test ne `micro` use kiya (sasta), prod ne `pro` (better quality, abhi bhi affordable).

#### Step C: `main.tf` mein sab pehle se ready hai

Sabse impressive: humein prod ke liye extra Terraform likhne ki zaroorat nahi. `main.tf` mein already configured hai (conditionally, `use_custom_domain` ke basis par):

- **SSL/TLS certificate** acquire karna (HTTPS ke liye — likely **ACM, AWS Certificate Manager** se)
- **DNS records** set karna (domain ko CloudFront se point karna)
- CloudFront distribution ko custom domain + cert se attach karna

```hcl
# main.tf ka prod-specific hissa (conceptual — use_custom_domain par conditional)
resource "aws_acm_certificate" "twin" {
  count             = var.use_custom_domain ? 1 : 0
  domain_name       = var.domain_name
  validation_method = "DNS"
}

resource "aws_route53_record" "twin" {
  count   = var.use_custom_domain ? 1 : 0
  zone_id = data.aws_route53_zone.twin[0].zone_id
  name    = var.domain_name
  type    = "A"
  alias {
    name                   = aws_cloudfront_distribution.frontend.domain_name
    zone_id                = aws_cloudfront_distribution.frontend.hosted_zone_id
    evaluate_target_health = false
  }
}
```

Ed emphasize karta hai: DNS records + certificates manually setup karna **"a lot of work"** hai — par Terraform yeh sab automatically kar dega.

#### Step D: Deploy prod

```bash
./scripts/deploy.sh prod
```

(Note: yeh `prod.tfvars` ki wajah se prod model + custom domain pick karega.) Wahi flow:
1. Lambda zip rebuild.
2. Terraform AWS resources create — par ab **extra**: certificate setup + **DNS records for `digitaltwin.com`**.
3. End mein deploy script **CORS configuration** update karta hai taaki wo naye custom domain se match kare (yaad hai wo "really long if-statement" CORS logic Terraform script mein).
4. Phir wahi 5-10 min CloudFront wait.

Yeh teesra environment hai (dev + test + prod), par **prod different hai** — iska apna hostname/custom domain bhi hai.

---

## 📋 Key Concepts

| Concept | Matlab |
|---|---|
| **`./scripts/deploy.sh test`** | Same script, `test` workspace → poora parallel isolated test environment |
| **Parallel environments** | dev + test simultaneously live, alag CloudFront/API GW/Lambda/S3 — fully independent |
| **IAM isolation (best practice)** | Ideally har env ka alag IAM user → permission isolation (Ed ne nahi kiya, exercise) |
| **Route 53** | AWS ki DNS + domain registration service (port 53 = DNS) |
| **Domain registration** | One-time, manual, **root user** se; ~$15/year; free WHOIS privacy |
| **`prod.tfvars`** | Production overrides — `environment=prod`, `bedrock_model=pro`, custom domain |
| **Amazon Nova Pro** | Bedrock ka capable-but-cheap model (~Claude Haiku jitna), prod ke liye |
| **ACM / SSL certificate** | HTTPS ke liye TLS cert — Terraform conditionally acquire karta hai |
| **DNS records (A/alias)** | Domain ko CloudFront se point karna — Terraform automate karta hai |
| **CORS update for domain** | Deploy script end mein CORS ko custom domain se match karta hai |

---

## 💼 Backend Dev Ke Liye Note

Yeh lecture **multi-environment promotion strategy** ka practical demo hai — har backend dev ke career mein central concept. Key insights: (1) **Ek hi codebase/script, parameter se environment switch** — yeh "twelve-factor app" philosophy hai: config environment se aata hai, code identical rehta hai. Tumhare Django/FastAPI deployments mein bhi yahi hona chahiye — `dev`/`staging`/`prod` ek hi image se, env vars/config files se differentiate. (2) **IAM isolation per environment** — Ed jise "exercise" bolta hai, wo production mein **non-negotiable** hai: alag AWS accounts ya IAM roles per env, taaki ek galat command prod ko na touch kare (blast-radius containment). (3) **Cert + DNS automation** — manually SSL cert lena, DNS records set karna, CloudFront attach karna sach mein painful hai; Terraform/ACM/Route 53 ka combo isse declarative bana deta hai. Backend mein jab bhi tum "custom domain + HTTPS" sunoge, yeh teen pieces yaad rakhna: cert (ACM), DNS (Route 53), aur edge/CDN attachment (CloudFront). (4) **CORS-per-environment** — har env ka CORS origin uske apne frontend domain se match hona chahiye; yeh full-stack security ka detail hai jo accidental cross-origin access rokta hai.

---

## ✅ Takeaway

- `./scripts/deploy.sh test` ne ek **parallel, fully isolated test environment** banaya — dev aur test ek saath live, completely separate infra
- Workspaces ki wajah se `twin-dev-*` aur `twin-test-*` resources coexist karte hain bina collision
- **Production = optional + paid**: **Route 53** se domain register karo (root user, one-time, ~$15), baaki Terraform handle karta hai
- `prod.tfvars` se prod overrides: `environment=prod`, **Nova Pro** model, custom domain
- Terraform automatically **SSL cert (ACM) + DNS records** setup karta hai, aur deploy script end mein **CORS** ko custom domain se match karta hai
- Best practice (Ed ne skip kiya): har environment ka **alag IAM user** for permission isolation

---

<details>
<summary>📜 Full Transcript (English)</summary>

And now I hope to completely blow your mind, because now I'm going to do this wonderful thing of running our deployment script a second time, but with a different parameter. I'm going to do dot slash scripts, slash deploy, but instead of writing the word dev, I'm going to write the word test and press enter. And what it's going to do now, as I'm sure you've guessed, is it's going to go through and do the same thing again. Package everything up, run Terraform again. But now we've got the different workspace selected, the test workspace. And that means that all of our resources will be created with dash test in the name rather than dash dev. And that means that we're going to get a second parallel setup of this entire world, this this universe on S3, on AWS. I mean, with all the different AWS components all connected together, uh, and the two of them will will be able to, to coexist, uh, and they'll be completely independent from each other because they have different names everywhere. One of them has dash dev and one of them has dash test and they'll be hooked up independently. Two separate environments. Now, while it's doing this, one pro thing that we have not done, is that a really professional way of doing this is actually to have different IAM users set up for your different environments, so that actually we'd be we'd be logging in as a different user and we'd have sort of permissions isolation between them. And we've not done that. That's one that I'll leave as an, as an exercise for the, for the, for the viewer. Uh, but we are setting up a parallel test environment. We're back at the point where it's going to take five minutes. And so, uh, and hopefully you are too. And so both of us will now take our five minute jump in the future. And I'll see you when it's done. Well, here we go. Done again. Deployment complete CloudFront URL right here. Okay. Let's see what happens if we click on this. Open up comes the browser. Here is the digital twin. Hi there. Let's see what it says. As a lambda function that's spinning up. And there it goes. Uh uh, do you like cheese? See how it handles this? Ah ha ha. I'm not allergic, but I'm just not a fan. It gets it right. Uh. Very nice. Uh, and so you can see I've got another tab here. This is the conversation we just had with our development. One. Um, uh, we'll ask it. Do you like cheese? Uh. Why not? Uh, and so you can see we're having two conversations in parallel with, uh, two different, uh, twins running on different URLs. This one is one. CloudFront distribution ends e zero, this one ends LR different CloudFront distribution. Uh, different uh uh, API gateway, a different lambda and different S3 buckets. The whole infrastructure is different. But once again, you don't need to take my word for it. We can go to AWS. We can go into the console and we're signing in of course, as the IAM user. Always. Let's which one should we pick? Let's pick lambda. Uh, why not go into Lambda. And what we'll see here is that there is a twin dev. And there's also a twin test. Uh, there's two of them. And we can go to, uh. Uh. Yes. CloudFront distribution. Here it is. Here's CloudFront. And we should see there's two distributions. One of them is called. One of them is is, uh, connected to twin test front end and then and then our ID and one of them is, uh, twin dev. And so we have our dev distribution and our test distribution. These two are separate, isolated environments, completely separate. We've just deployed two environments, and they are live on the internet. Okay, so now, uh, I am going to, um, uh, skip part seven. We're going to come back to part seven because I'm going to the optional part eight, which is optional should you wish. And it's about making a production deployment. Uh, so here we go. Uh, production deployment with a custom domain, a domain name of your choice. Now, the reason this is optional is that that costs something. And it's not even AWS charging you now, it's I mean, AWS does charge you, but they're just passing on the costs that it costs to to register a domain name. But I feel like this might be something that you feel is deserving of a domain name, either because you like the idea of having a digital twin with its own URL, or just because it is a good experience to have to register your own domain in this way and to hook it up to a live production environment. But you might have your own domain already, in which case this will show you how to do that too. Um, but and, and also, of course, if you, if you have your own domain name already and you're already serving web pages through it, then you can just embed, uh, this, this page is like an iframe or something. So there's there's other ways of doing it that would be a bit easier than setting up a domain. But this is a great practice. It's a great thing to do. And we're going to do it. I'm going to do it for me. You can watch along and should you wish, you can do it yourself too. Um, and this will need us to use the console. The the actual setting up of the domain is a one time thing. Uh, but we will be using Terraform to connect us to the domain. Uh, but to do things like DNS records, if you're familiar with them, all of that set up, the DNS configuration will all be terraformed. But the registering of the domain, the one time thing and the spending. What is it, $15 usually for, for, for for a normal dotcom that we are going to do ourself and we're going to do it as a root user, not as a IAM user. And we're going to be doing it in route 53, which is AWS name for their service for domain registration and DNS entry. Let's go over and do that now. So here I am signed in as my root user, which you can tell because it says Ed up there and it should have your root name right up at the top there. And we're going to go to route 53. Uh, and uh, here it is. And route 53 is where you can set up your domains. And I've already set one up. And I'm not going to set up a second one. That would be too much. So that's why I'm going to tell you what I did. I'm going to go in here. It's called Digital twin. Uh, and uh, the way that you set one up is you press Register Domains and you can then check availability. So I could do like Edward Digital twin digital twin and search for that domain and see if that exists. It does exist and it is $15. That's how much it will set you back if you want to get Edward Digital Twin, which unless your name is Edward, in which case, uh, good name. Um, but otherwise that wouldn't be a great choice for you. But do find a domain that you like, should you want to do this and then select it, and then it makes you fill in a few questions, uh, which is part of the registration process. Um, and I think they do like that domain name cover up thing things so that your privacy is protected, which AWS offers for free. I think at least they did to me. Um, and once you've gone through that, there's then a period you have to wait, and you also have to verify your email, and then you will have a registered domain and it will look just like that. And once you've done that, uh, we're in great shape. That's all that you need to to configure. You don't need to do all the DNS records and all the stuff if you're familiar with this, that's again, it's a lot of work. It's like setting up a whole ton of services from from scratch. But Terraform wonderfully is going to handle all of that for us right now. Okay, so we're back in our code again. And, uh, what we now have to do is create a new configuration file called prod vars. So this overrides the default in the case that we're in production. Um, because of this environment right here. So so we go in to Terraform and right click and do new file and do prod vars. There it is. And we paste in this. Here we go. Project name is twin. Environment is prod. And we're going to use you know what for. This is production. So I'm going to use Pro up Amazon Nova Pro which is still super cheap. It's still the same or slightly cheaper than than Claude Haiku. So it's still very cheap. Everything else. And then. Uh yourdomain.com. This better be my actual domain editor. Sorry. Which is editor digital twin. Com okay, there it is. I don't know how it knew that, but that's cursors magic. Um, add digital twin. Com I think that's right. If it's not right then then then shout so that I know, uh, um, okay. And I think that should be it. This is all we have to do somehow, amazingly, because I believe that everything's already set up for us. Let me check my instructions, make sure that is it. Uh, and that's because we did already define this. If I go to the, um, main.tf, you'll see that that down here already is all this stuff. It sets up a certificate, an SSL certificate. It gets that, it gets it sets DNS records. Uh, look at all this configuration that happens. And I tell you, I don't know if you've done this before yourself, if you've done this sort of infrastructure work to set up DNS records and certificates, certs and stuff. Uh, for, for a hostname, it's it's a lot of work. And Terraform is going to do it all for us. Uh, so let's open up a new terminal and let's do dot slash scripts, slash deploy dot shell. And that should be it. Let's give it a whirl. I'm almost nervous. Uh, and as before, we know what happens. The deploy script starts by rebuilding the zip file of our lambda function. And the deploy script is then going to hand over control to terraform, and the deploy script takes over at the very end And to upload the right static site to S3. So it's all happening. The AWS resources are being created. You can imagine it just clicking around all of those screens. We've already got the full development environment and the full test environment. And now we are adding our third environment, the prod environment. But it's a bit different. It also has a hostname. And remember, it's going to have to come back at the end and make sure that our Cors configuration is set up to match that digital twin. Uh, you remember that really long that that sort of if statement thing, uh, that was uh, that, that was in the Terraform script. Um, that's, that's all got to happen as well. So a lot has to happen again. We've got the five minutes so you can see, look, it's it's, uh, it just created the, uh, it's doing the cert stuff. You can see that it's setting up the DNS records for digital twin. Com. Uh, so all is happening, uh, the distribution, of course, still 5 to 10 minutes. So once more into the future with us. I'll see you then.

</details>
