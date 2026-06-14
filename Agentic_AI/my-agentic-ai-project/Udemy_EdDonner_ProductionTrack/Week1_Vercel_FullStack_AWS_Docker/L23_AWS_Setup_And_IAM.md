# L23 — AWS Setup and IAM for Production AI: Your First Cloud Deployment

> **Week 1 · Day 5** · ⏱️ ~11 min

---

## 🎯 TL;DR

Day 5 ka bada din shuru — Vercel se aage badh ke **AWS** par production deploy karenge. Pehla padav: AWS account banao, **root user** secure karo (MFA), apna **12-digit Account ID** note karo, aur **IAM** (Identity and Access Management) ka core concept samjho — root se kabhi kaam mat karo.

---

## 🗣️ Hinglish Explanation

### Aaj ka mood: "big day, needs grit"

Ed seedha bolta hai — Day 5 ek **bada aur thoda frustrating** din hai, lekin AWS jaise major cloud provider par deploy karna **bahut satisfying** hai. Tum "bare metal" ke kareeb ho, aur jo cheez **massive scale** le sakti hai usi par deploy kar rahe ho. Week 1 ki conclusion hai — humne ek SaaS gen-AI product banaya, ab usse **production-grade AWS** par le ja rahe hain.

⚠️ Important framing: **aaj sirf ek AWS preview/teaser hai.** Asli "full AWS week" toh **Week 2** hai jahan hum deep jaayenge. Aaj sirf flavor lena hai — sab kuch yaad rakhne ki zaroorat nahi. Bas comfort develop karo.

### AWS kya hai (quick background)

**AWS = Amazon Web Services** — duniya ka sabse bada cloud provider. Tum servers, storage, databases, AI models, networking — sab "on demand" rent kar sakte ho, apne data center banaye bina. Iske 2 bade competitors jo course mein aage aayenge:
- **GCP** = Google Cloud Platform
- **Azure** = Microsoft ka cloud

In sab mein AWS ka **IAM sabse granular aur sabse grueling** hai — yahi aaj ka main topic hai.

### IAM kya hai aur kyun headache hai

**IAM = Identity and Access Management.** Yeh AWS ka system hai jo decide karta hai **kaun (who) kis cheez (what) ko access kar sakta hai.** Bahut hi **granular aur powerful** hai — pehli baar use karte time **tiresome** lagta hai, par yeh AWS ki **core strength** hai. Aur job market mein "AWS permissions mein slick hona" ek **bada commercial skill** hai — interviews/job descriptions mein expect kiya jaata hai.

Mental model:
- **Identity** = kaun ho tum (user, group, role)
- **Policy** = ek JSON document jo batata hai "in actions par, in resources par, allow/deny"
- IAM in dono ko jodta hai

### Root user vs IAM user — golden rule

```
Root user  = ALL-POWERFUL (kuch bhi kar sakta hai)
           → isiliye PRACTICALLY KUCH MAT KARO isse
IAM user   = LIMITED permissions (sirf jo chahiye wahi)
           → daily kaam isi se
```

Jab tum AWS account banate ho, tumhe ek **root user** milta hai — admin access, saari powers. Lekin yahi khatarnak hai. Ed ka rule: **root user se lagbhag kabhi login mat karo.** Root ka sirf **2 kaam** hai:
1. **Permissions assign karna** — yaani naye (limited) accounts/users set up karna
2. **Budgeting** — spend track karna aur controls lagana

Real production mein tum **kai IAM users** banaoge — har environment ke liye alag, har project ke liye alag, alag-alag roles. Is course mein hum itne finicky nahi honge — sirf **ek user "AI engineer"** banayenge jo poore course ka workhorse hoga. Ed tumhe yeh bhi sikha dega ki **fine-grained permissions** kaise dete hain, taaki future production projects mein khud kar sako.

### LAB: Naya AWS account banao

Day 5 ka guide document **`ed-donner/production` repo** ke `week1` folder mein hai (ya agar tumne SaaS project mein copy kiya hai toh wahan). Ed Cursor mein yeh doc kholta hai bas reference ke liye — aaj zyada coding nahi, mostly AWS console.

Signup flow (agar account nahi hai):
1. **aws.amazon.com** par jao → **Create an AWS Account**
2. Email + password do
3. Account type: **Personal**
4. ⚠️ **Payment info (credit card) DAALNA ZAROORI hai** — AWS bina card ke use nahi hota. Card daalte hi kuch charge nahi hota, par responsibility tumhari hai ki har step ka cost samjho aur track karo.
5. Support plan: **Basic (free)** select karo
6. Ab tumhare paas **AWS root account** hai

💡 **Free credits tip:** AWS naye joiners ko offers deta hai — region-dependent, common ek hai **first 3 months free credits**, students ko extra. Signup ke time yeh padh lo — ho sakta hai is course ki chhoti costs free credits se cover ho jaayen.

### LAB: Root user secure karo (MFA + Account ID)

Ab Ed apne (pehle se bane) account se sign in karta hai:

1. **aws.amazon.com** → **Sign in to the Console**
2. **Root user** select karo → email do → Next → password
3. Kyunki Ed ne pehle se **MFA (multi-factor authentication)** set up kiya hai, authenticator app se code daal ke sign in hota hai

Sign in ke baad, top-right par **Account ID** dikhta hai:

> **Account ID = ek 12-digit number** jo tumhare poore AWS instance ko identify karta hai. Sabhi users isi ke under aate hain.

⚠️ **ISE COPY KARKE KAHIN SAFE JAGAH NOTE KAR LO.** Dropdown arrow → copy-to-clipboard button. Course mein **baar-baar** chahiye hoga (IAM login ke time bhi).

Ab **Security Credentials** par jao (account dropdown se):
- **Assign MFA device** button → MFA set up karo. Ed phone par **authenticator app** use karta hai. Root account ke liye MFA **must** hai — taaki sirf tum hi access kar sako. Sabse sensitive account hai, super secure rakho.
- Apne **account details up to date** rakho

### ARN se introduction

Security credentials page par Ed ek identifier dikhata hai aur warn karta hai:

> **ARN = Amazon Resource Name** — har AWS object ka ek **unique identifier**. Yeh aage poore course mein **har jagah** dikhega — user, role, S3 bucket, Lambda function, kuch bhi. Format kuch aisa hota hai:

```
arn:aws:iam::123456789012:user/AI-engineer
    │   │   │     │           │
    │   │   │     │           └─ resource (type/naam)
    │   │   │     └─ account ID (12 digit)
    │   │   └─ region (kuch services mein blank)
    │   └─ service (iam, s3, lambda...)
    └─ partition (aws)
```

Ed bolta hai "tum ARNs se sick ho jaaoge" — yaani inko dekhna normal ban jayega.

### Final check

Ed ka advice: MFA assign karne ke baad **sign out karo aur dobara sign in karo** — taaki 100% confirm ho jaye ki MFA device sahi kaam kar raha hai aur tum AWS mein aaram se aa-jaa sakte ho.

Aage ke lectures: budget alerts set karna → IAM user banana → Docker → AWS par deploy. App Runner, ECR, CloudWatch jaise services aane wale hain.

---

## 📋 Key Concepts

| Concept | Matlab |
|---|---|
| **AWS** | Amazon Web Services — duniya ka largest cloud provider; servers/storage/AI on-demand |
| **IAM** | Identity and Access Management — kaun kya access kar sakta hai, granular control |
| **Root user** | All-powerful account; sirf permissions assign + budgeting ke liye, daily kaam ke liye NAHI |
| **IAM user** | Limited-permission user; daily kaam isi se ("AI engineer" course ka workhorse banega) |
| **Policy** | JSON document — kis action/resource par allow ya deny |
| **MFA** | Multi-factor authentication — root account ko secure karne ke liye must (authenticator app) |
| **Account ID** | 12-digit number jo poore AWS instance ko identify karta hai; note kar lo |
| **ARN** | Amazon Resource Name — har AWS object ka unique identifier, har jagah dikhega |
| **Region** | AWS ka geographical installation (e.g. us-east-1) — har region ek alag "cloud" jaisa |

---

## 💼 Backend Dev Ke Liye Note

Python backend dev ke liye yeh lecture ek **mindset shift** hai: Vercel par tum sirf code push karte the, AWS par tumhe **infrastructure-level identity** sambhalni hoti hai. Root-vs-IAM ka rule wahi **least-privilege principle** hai jo tum production systems mein already follow karte ho (DB users ko sirf zaroori grants, service accounts ko scoped tokens). IAM policy ko soch sakte ho ek **declarative RBAC config** ki tarah — bilkul jaise Kubernetes RBAC ya Postgres `GRANT` statements. MFA + scoped IAM user = wahi hygiene jo tum SSH keys/secrets manager ke saath rakhte ho. Account ID aur ARN ko **stable references** samjho — future Terraform/CI pipelines (Week 2) inhi par depend karenge, isliye abhi se ek password manager / secure note mein Account ID rakh lo. Yeh "grueling" IAM setup ek baar samajh aane ke baad poore career mein kaam aata hai.

---

## ✅ Takeaway

- **Day 5 = AWS ka teaser**; asli deep dive Week 2 hai — abhi sirf flavor lena hai
- **IAM** AWS ka core hai: kaun kya access kar sakta hai — granular, headache, par valuable job skill
- **Root user se daily kaam mat karo** — sirf permissions + budgeting; baaki sab **IAM user** se
- AWS account banao → **MFA lagao** → **12-digit Account ID note karo** (baar-baar chahiye)
- **ARN** (Amazon Resource Name) har object ko identify karta hai — poore course mein dikhega; MFA test karne ke liye sign out/in zaroor karo

---

<details>
<summary>📜 Full Transcript (English)</summary>

So with any luck, you are now mentally prepared for day five. It's a big day. It's a day that requires, as I say, some grit. But I happen to find using AWS deploying to these major cloud providers to be very satisfying as well. It's a it's a big deal. Uh, and it's exciting to be deploying on something that can take such massive scale and be close to the kind of bare metal of a cloud deployment. Uh, so so it can be enjoyable. And as I've warned you a million times, it can be a bit frustrating. So here we are. We're coming to the conclusion of the first week, the SaaS gen AI product. We're now going to go to production with on AWS. And I do want to make the point that today is going to be about a preview of AWS. Uh, next week is going to be the full AWS week, when we will really go deep on many components. It's going to say every component on AWS. We're not even gonna get close to that. but many of the core components of AWS today. Think of it more as a teaser. Today is a teaser of what's to come. Just to give you that early sense, you don't need to pick everything up. You just need to get a flavor for it. But first, one of the things that one gets very used to with AWS is what's known as IAM identity and access management. It's something that's quite grueling with AWS in particular, more so than the other providers that we'll look at. GCP, Google Cloud Platform, and Azure from Microsoft, but AWS, Amazon Web Services. I realize I haven't said that. I do imagine that everyone does know that that's what AWS stands for. But just in case, uh. Uh, AWS uh, has a very granular, very powerful system for managing who can access what on the AWS platform. And it's quite a headache. The first time that you get to use it. But it is one of the core strengths of AWS. So it's one of these things that's that's, uh, it's it's a it's a mixed blessing. Uh, but generally speaking, I think it is a net positive, but but it's important to understand it. So as I just just said, it is it's very granular and it is it's, it's it's really tiresome when you first use it. But there is a good reason behind it. And it's a great, it's important commercial skill for you to pick this up. I said at the beginning that that, uh, one of the reasons that we, uh, look at AWS is to give you this ability to build software that scales in a big way and also to prepare you for industry so that you have the kind of skill set that you might expect to see in a job description and being slick with AWS permissions. That's that's a that's a big skill. So here's how it works. We're going to start by setting up a new AWS account, assuming you don't already have one, and give you a root user. And the root user is the all powerful user that can do anything and as a result, the all powerful user should in practice do almost nothing. You want to be almost never logged in as the all powerful root user. The only two things that we're going to ever use the all powerful user for. One of them is going to be about assigning permissions, so that we can use it to set up other accounts that have more limited permissions. And that's this is that this is the whole practice of IAM that you don't give your root user abilities. You allow your or at least you don't do things as your root user. You create other accounts, you give them specific permissions. And that's what you do with with those other accounts. We're also going to use the root user for budgeting, to make sure that we are aware of what we're spending and putting various controls around it. So that's the root user. And we then create an IAM user, which is what you call a user with more restricted permissions. Now in an ideal in a in a real production setting, you'd actually create many IAM users with different roles. You might have a different one for each of your environments. You might have different ones for different projects that have access to different things. Now we're going to not be that finickity. We're going to create one user called AI engineer that will be our workhorse for the rest of this course. Uh, and we're going to give that, that user permissions to do all the different things that we're going to need to do during the course as we go. But I'm going to set you up so that if you wish you could give more fine grained permissions, you'll you'll be equipped so that you know how to do it. And you can do that yourself now, or in production or with your own true commercial projects as you build them. Okay. And with that, we're going to go straight to some lab work. We're going to set up an AWS account and set up some of this IAM stuff. And I'm going to begin actually by taking you to to cursor. Not that we're going to be in cursor that much, but we're going to do it so I can show you the day five document, which will be your guide. Uh, and the day five document, which is in the it will be in the Sass project if you copied it there, but otherwise in the production project. Um, this is going to talk us through moving from vessel to AWS for professional cloud deployment. Uh, there's going to be a ton of stuff we're going to go through. You've got a little preview here. We're going to talk about Docker AWS fundamentals. We're going to be doing that using this AWS component called App Runner. Uh, and uh we're also going to be working on protecting the budget the spend. And we'll talk more about whether there's any spend at all in a minute. Um, and you can read through all this, but we will come back to it. So the first thing to do is to sign up for a new AWS account, which I already have an AWS account, but you will go to AWS Amazon.com. You may already have an account, but if not, you'll go there. You'll click to create an AWS account. You'll you'll enter your email and choose a password. You will select a personal account type. Um, and uh, this is the thing, uh, you will need to enter payment information and we will talk about payment in a second. So you'll need to enter a credit card. It is required to use AWS. But you will see every time that we build something that's going to cost money, and you'll be able to make that decision about what you want to do. But it is, as I said at the beginning, it is your responsibility to be understanding it as we go and tracking it. When you first put in your credit card number, of course, nothing is taken at all. But, uh, you should you should make sure that you're understanding every step along the way, everything we're doing as it pertains to any costs. And select a basic support free. And you will now have an AWS root account. As it says here, it's like having admin access. It's got all the powers in the world, but it is dangerous what we're going to do now. We're going to do this together right now because I've already set up this account. We're going to sign in. We're going to look at the security credentials and make sure it's set up properly. And we're also then going to set up some budget alerts. We're going to follow this structure right here. Uh so let's go over now to the AWS screens and do this together. So this is what I get when I go to AWS or Amazon.com. You presumably came here, you went to create accounts and you went through that flow. Now, I should mention that that Amazon has various offers to new joiners. Sign up for AWS, often with free credits, with lots of free offers and plans. And if you're a student, then then you get more. There's there's lots of different ways that AWS will give you credits for signing up your new account, and it probably varies by region. So hopefully you've been able to get yourself a nice deal that's given you a bunch of free credits, as well as knowing that when you first sign up, you get a lot of free stuff. So, uh, that that might mean that you can do some of the things that will cost a few dollars on this course and not pay a dime. So, uh, hopefully you've you've read that as part of setting up your account. But once you've done that, I've already got this. So I'm going to sign in with your account. I'm coming in as a root user. And I'm going to pick my root user account, which is this one right here. There it is. And then I press next. And then I press sign in to come in. And because I've already set up multi-factor authentication which you haven't done yet. Uh, but, but uh, which I have, I can now come on in, go to my authenticator app, type in a number. And sign in. And I'm now signed in as the root user. So up here you can see my account ID. This is the account ID of our our instance that all our users will be under. And you should keep note of this. This is going to be very important for us in a lot of different times during during this course, uh, you can click on that drop down arrow and press that button there to copy it to your clipboard and then paste it somewhere to hand. We're going to need that later. Your Amazon account ID it's a 12 digit number. Uh, and it's a very important number that identifies this this instance. So you can then go to security credentials just here. And this opens up the security, uh, setting. Uh, this is, uh, a place where you can now set up multi-factor authentication by pressing this assign MFA device button. And this is where you can set up a number of different ways that you can have multi-factor authentication. And you do need to set this up for this account. For this root account, you need to be very careful to make sure that only you have access to it. I use an authenticator app on my phone and I've got it tied that way. You need to do the same to make sure that you have this account very secure indeed. And, uh, while we're here, I just mentioned another thing. It's good to make sure your details are up to date. Something that you'll notice here is this identifier, this thing here. Uh, you will see these identifiers all over AWS. You are going to become sick of these. We're going to have so many of these in our journey together for the next few weeks, and are an Amazon resource number. They're going to come up a lot, and it is one unique identifier to any thing on AWS where that thing could be many different types of object. And so it's going to come up a lot. You're going to see arns all over the shop and you're going to get very used to them indeed. All right. So with any luck you've gone through this. You've assigned your MFA device. Then come here and sign out and sign back in again so that you can be absolutely sure that your MFA device is working and that you're getting back in and out of AWS.

</details>
