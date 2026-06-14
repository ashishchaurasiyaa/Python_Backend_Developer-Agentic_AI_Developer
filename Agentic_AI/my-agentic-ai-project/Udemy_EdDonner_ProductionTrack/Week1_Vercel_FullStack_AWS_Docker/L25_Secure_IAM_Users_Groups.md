# L25 — Setting Up Secure IAM Users for Production AI Deployments on AWS

> **Week 1 · Day 5** · ⏱️ ~10 min

---

## 🎯 TL;DR

Root user se ek limited **IAM user "AI engineer"** banao, phir ek **user group "broad AI engineer access"** banao jisme 4 managed policies attach karo (App Runner, ECR, CloudWatch Logs, IAM-user-change-password). User ko group mein daalo, sign out karo, aur ab **IAM user** se login karo (12-digit Account ID + username + password). Region (e.g. us-east-1) ka dhyaan rakho.

---

## 🗣️ Hinglish Explanation

### Kyun: root se daily kaam NAHI

Ed dohraata hai — **root account daily work ke liye kabhi nahi.** Uske paas "kuch bhi karne" ki power hai, jo daily kaam ke liye galat hai. Iski jagah ek **limited IAM user** banayenge jiska naam **"AI engineer"** hai — yahi agle kuch weeks ka identity hoga. (Ed apne demo mein "AI engineer 2" naam deta hai kyunki uska original pehle se bana hai — tum sirf **"AI engineer"** rakhna.)

Setup ke 4 phases:
```
1. IAM User banao        → "AI engineer"
2. User Group banao      → "broad AI engineer access"
3. Group mein 4 policies attach karo
4. User ko group mein daalo, sign out, IAM user se login
```

### Phase 1: IAM user banao

1. Console search box → `IAM` type karo → **IAM dashboard** kholo (yeh tum bahut use karoge)
2. Left side-nav → **Users**
3. **Create user** (orange button)
4. Username: **`AI engineer`**
5. ✅ "I want to provide users access to the **AWS Management Console**" → **I want to create an IAM user**
6. **Custom password** select karo → ek strong password type karo
7. ☐ **Uncheck** "Users must create a new password at next sign-in" — kyunki tum khud password set kar rahe ho, abhi sahi daal do, baad mein change ki zaroorat nahi
8. **Next** → **Create user** → done

### Phase 2 & 3: User Group + Policies (the "proper way")

Permissions seedha user par bhi add kar sakte the, par usme limitations hain aur humein **bahut saari permissions** add karni hain — isliye **proper way** = pehle ek **user group** banao.

> **User group** = permissions ka ek set jo **multiple users** par apply ho sakta hai. Abhi humara ek hi user hai, par best practice yahi hai.

1. IAM → **User groups** → **Create group**
2. Group name: **`broad AI engineer access`** (Ed demo mein "2" lagata hai, tum nahi)
3. Ab **policies attach** karo — yeh decide karta hai "AI engineer kya kar sakta hai"

⚠️ **Janky UI warning:** har policy ka naam **search bar** mein type karo, phir checkbox tick karo (yellow button **abhi mat** dabao — bas checkbox). Yeh 4 policies attach karo:

```
1. AWSAppRunnerFullAccess              → App Runner par deploy/manage
2. AmazonEC2ContainerRegistryFullAccess → ECR mein Docker images store
3. CloudWatchLogsFullAccess            → logs likhna/padhna
4. IAMUserChangePassword               → khud ka password change
```

(In services ka matlab abhi pata nahi hoga — koi baat nahi, aage "fondly" inse milenge: App Runner = container deploy, ECR = container registry, CloudWatch = logs/monitoring.)

4. Charon checkboxes tick karne ke baad → **Create user group**
5. Group banega aur **AI engineer user usme assign** hoga

Verify: User groups → `broad AI engineer access` kholo → **Users** tab par "AI engineer" dikhega, **Permissions** tab par charon policies. (Ed ke paas zyada hain kyunki woh course aage badhne par aur add karta hai — tumhare paas sirf yeh 4 honi chahiye.)

### Granularity note (pros ke liye)

Ed maanta hai ki **`FullAccess` type policies zaroorat se zyada** dे rahe hain. Real professionals **aur granular** hote hain — AWS bahut fine control deta hai (specific actions/resources). Par abhi ke liye yeh "good enough" hai — hum already kaafi granular hain (specific services hi assign kiye, full admin nahi). **Mental note rakho** ki future mein aur tight kar sakte ho.

### Phase 4: IAM user se login karo

Ab root se **Sign out** karo (top-right). Phir:

1. **aws.amazon.com** → **Sign in to the Console**
2. **IAM user** option select karo (root nahi — root ke liye "Sign in using root user email" alag link hai)
3. Fields bharo:

```
Account ID (12 digit)  → woh number jo Day 5 start mein copy kiya tha
                          (agar nahi kiya, toh root se login karke nikalo)
IAM user name          → AI engineer
Password               → jo tumne set kiya
```

4. **Sign in** → ab tum **AI engineer** ke roop mein andar ho 🎉

### Login ke baad: 2 cheezein dhyaan do

**1. "Access Denied" errors normal hain.** IAM user ke paas sab access nahi — e.g. **cost & usage** dekhne ka access nahi (woh root ka kaam). Jab overall costs/budget dekhna ho ya permissions assign karni ho → **root user se login** karo. Daily kaam **AI engineer** se.

**2. Region — bahut important.**

> **Region** = AWS ka geographical installation (e.g. `us-east-1`). Har region ko **ek alag cloud** samjho — alag services, alag data, independent. Top-right par current region dikhta hai aur change kar sakte ho.

⚠️ Ed ki **bitter personal experience** ki warning: region code ke spelling/hyphens galat mat karo — `us-east-1` mein agar ek hyphen reh gaya (`useast1`) toh **obscure errors** aate hain jinhe dhoondhne mein ghanton lag sakte hain. Tumhara default region tumhare location par depend karta hai (Ed ka US East 1).

Congratulations — IAM user set up, login ho gaya, ready to go!

---

## 📋 Key Concepts

| Concept | Matlab |
|---|---|
| **IAM user** | Limited-permission identity ("AI engineer") jise daily kaam ke liye banaya — root nahi |
| **User group** | Permissions ka reusable set jo multiple users par apply ho; best-practice way to grant |
| **Managed policy** | AWS-defined permission bundle (e.g. `AWSAppRunnerFullAccess`) jo group/user par attach hoti hai |
| **AWSAppRunnerFullAccess** | App Runner (container deploy service) par full control |
| **AmazonEC2ContainerRegistryFullAccess** | ECR (Docker image registry) par full control |
| **CloudWatchLogsFullAccess** | Logs likhne/padhne ki permission (monitoring) |
| **IAMUserChangePassword** | User ko apna password change karne deti hai |
| **Least privilege** | `FullAccess` se aage granular permissions de sakte ho (pro practice) |
| **Region** | AWS geographical installation (us-east-1); spelling/hyphens galat mat karo |
| **Console sign-in (IAM)** | Account ID (12-digit) + username + password se IAM login |

---

## 💼 Backend Dev Ke Liye Note

Yeh lecture seedha **RBAC (role-based access control)** hai jo tum already karte ho. User group = **role**, attached policies = **permission set**, user = **principal** — bilkul Postgres `GRANT ... TO role` ya Kubernetes `RoleBinding` jaisa. "Group pe attach karo, user pe nahi" wala pattern wahi DRY principle hai jo tum DB roles/IAM-in-app mein follow karte ho — permissions ek jagah manage, kai users inherit. `FullAccess` vs scoped policies ka tradeoff bilkul tumhare API scopes/OAuth-scope decisions jaisa hai: shuru mein broad, production-hardening mein tight. Production reality mein tum in managed policies ki jagah **custom least-privilege policies** likhoge (specific actions + resource ARNs + conditions), aur ideally human users ke liye SSO/IAM Identity Center + short-lived roles use karoge bajaaye long-lived passwords ke. "Access Denied is normal" wali baat important hai — agar tumhara CI/Terraform `AccessDenied` deta hai, woh **missing policy** ka signal hai, bug nahi. Aur region pin karna (Week 2 Terraform mein `provider "aws" { region = "us-east-1" }`) — yeh hyphen-typo wali galti config-as-code se avoid hoti hai.

---

## ✅ Takeaway

- **Root se daily kaam mat karo** — ek limited IAM user **"AI engineer"** banao
- **Proper way**: user group **"broad AI engineer access"** banao, usme **4 policies** attach karo (App Runner, ECR, CloudWatch Logs, IAM-change-password), phir user ko group mein daalo
- IAM login ke liye **3 cheezein**: 12-digit **Account ID** + **username** + **password**
- **"Access Denied" normal hai** — cost/budget/permissions ke liye root se login, baaki sab AI engineer se
- **Region** (us-east-1) ka spelling/hyphens bilkul sahi rakho — typo se obscure errors aate hain

---

<details>
<summary>📜 Full Transcript (English)</summary>

So this next part is extremely important. Uh, and is all about IAM identity and access management. This is where we're going to be going in as our root user that we just set up. That for me is called Ed. Uh, and using that to create a new user, a special user called AI engineer that will have limited permissions and that will be the the ID that we'll use during the course of the next few weeks. Now, what I've done here is I've got the AWS console showing on the left. If I click here, you'll see what I mean. We're just the console home. That's what you get after you log in on the right. Sorry. And on the left I've got the, the notes from the, the day five, uh, guide that's in the production repo, uh, to take us through what we're going to do now so you can follow we're on step five right here. So we're on step four, creating the IAM user for our daily work. You should never use your root account for the daily work. It has permissions to do anything. And that's not a good idea. Instead we're going to create a more limited user. Um, and you can see that I'm logged in right now as editor, which is the name of the root user, we're going to create a new user. So we start, as always in the search box in the console. And I'm going to look for the users section. Uh sorry the IAM section I mean of the uh, um, AWS console. And here I am in the IAM dashboard, something that you'll get very used to. And on the IAM dashboard I'm now going to go to the users, uh, part in the side nav. Here we go. And it shows that I have actually already set up a couple of users. You won't have any. And that's what we're going to do now. So you're going to press the orange create user button and you're going to call it AI engineer. And I'll just put AI engineer two for now. Uh, you are going to uh, say yes, I want the user to have access to the console, and I want the user to be an IAM user. Uh, so, uh, that seems good. You're going to select Custom Password and type in a really strong password that you'd like to use right here. And you're going to uncheck. Users must create a new password because you're writing the password. So you might as well get it right now. So you don't need to change it again. And when you're doing that you're next. And then create the user. And that part will be done. And I'm going to cancel because I've already created it of course. And it's called AI engineer okay. Now there are ways that you can add permissions immediately to the AI engineer, but that has some limitations. And we're going to want to add a lot of permissions. So we're going to do this a really proper way. And a proper way is to first create something called a user groups. User groups, which is a set of permissions that can apply to a bunch of users, even though we only have one right now. So go to user groups and we're going to create a user group, and it's going to be called broad AI Engineering Access. So that's what's coming next okay. So I'm going to press create Group right here. And I'm going to call this broad AI Engineer access, which is what you should do. And then I'm going to put the number two because I've already got one. But you don't put the number two, you just stick with broad. AI engineer access. Now you can have as many users as you want in this group. We're just going to have the one user. It'll be the only user you've got. AI engineer that will be part of this group. And then we can attach permissions policies to this user group. And this is where we say what is AI engineer allowed to do. And you are going to be adding four policies. As you see it's actually going to be five. And they're listed here. And the way that you do it, which is a little bit janky, is you type out the name in this search bar here like this first one, it's called AWS App Runner Full Access. And you might not know what. You won't know what that means yet. And you can just drag here to check. There it is. You just check that box. You don't press this yellow button yet. You just check that box. It's kind of odd. Now we'll get the next one. Amazon EC2 Container registry full access. Don't worry what these things mean. We'll get to know them fondly sooner enough. Uh, and now we go back here and we type CloudWatch logs. Full access. Oops. If I spelled this wrong. CloudWatch logs I put log. There we go. There it is. And we tick that. And then we do uh IAM user change password and we tick that uh and now we've got these four things ticked. I actually thought we were going to have to do a fifth, but I guess not. It's just these four. Uh, and with that you then press Create User Group and that will create broad engineer access to and it will be assigned to AI engineer. Uh, sorry. It will create broad AI engineer access without the two because you didn't have a two. Uh, I'm going to cancel because I've already done this. Of course. We'll go back. Continue. And here, let me just show you my user groups. I've got one called broad AI Engineer Access. If I click on it, you can see that it's, it's got it's actually got two users associated with it. You will only have one AI engineer that's on the users tab of broad AI engineer access. The permissions tab has all the permissions. Now I've got a bunch more than you have because I've been adding more. As the course progresses, you should just have the for the AWS app runner, uh, which is right here, full access EC2 container registry, that one there, CloudWatch logs, full access. Uh, there it is. And IAM user uh, change password, which you should also have, which I have elsewhere, but you should have those four. They should be assigned here. Uh, and uh, it should all look pretty good. Now the pros amongst you might point out that giving this full access type of permission, like this one here is perhaps more than is strictly needed. We're giving a bunch of different policies, uh, which which will allow, uh, the IAM user to, to do anything to do with this particular service. And real professionals get more granular than this. AWS gives you very fine granularity about saying what people can and can't do. But I think this is good enough for now. We're getting pretty granular. We're assigning particular services to our AI engineer user, and that's good enough for now. But just keep in mind, keep a mental note of the fact that you can take this further and be even more granular about what your AI engineer user is allowed to do and can't do. But with that, we have now set up this user. We have a username and a password, and we have permissions assigned. And it's time that we can now log into AWS as our IAM user instead of our root. And we begin the process by signing out by going up here and go to sign out. We're done as our root user. All right. And here we are again at the AWS landing page Aws.amazon.com. I'm going to press sign in to console. And this time I'm coming in as IAM user sign in. And you can see that there's there's several fields here. If you were coming in as the root user, you would now instead press sign in using root user email. Now this first thing here is the 12 digit ID that I told you to copy and keep track of later. If you didn't take my advice, you didn't copy it and track it. Then you'll have to go back in and sign in as your root user and then take that ID, but that ID goes here. Uh, and then here is your IAM username. Here is the password that you set. And then you can press sign in. And in you will come. You are in as your IAM user. Uh, this is a time when I will mention one other thing. We are now in as as a IAM user, I'll mention two things. One is that when we're in as our IAM user, we're going to see these errors about access denied all over the place, such as looking at the cost and usage because we don't have access to that as the IAM user as AI engineer. You can see up here we don't have access to that. It's the it's the root user that has access to that. So when you want to see stuff about the overall costs, you need to go in as your root user to do that, to manage your budget and to assign permissions. We are in as the AI engineer, which you can see here, along with our 12 digit ID that you've got, uh, carefully recorded somewhere. You'll also see this here. Now this is really important. This is what's called the region, the AWS region that you're associated with. And the different regions are listed down here. And you can change the user interface to, to change your console so that you're looking at a different region. And each region you can almost think of like it's a different cloud, a different installation that has completely different services and works differently, and your region will depend on where you're located, your default. That would have come up for me. It is US East one, and you'll be on one of the others, and we'll talk more about this later. But it's important to understand that this is where you set what region you're currently looking at in the console. Um, and it's worth getting used now to how you spell these. Like us. Hyphen east. Hyphen one. Because at various points when we use this, if you make any typos in this, like I accidentally left out the hyphen once and you can get obscure errors and it can take ages to find that I speak from bitter personal experience, so don't do that. Uh, so this is where you set the region that you're looking at. This is where we see our ID and our AI engineer. And this is the new the console with only the permissions that we have as AI engineer. And congratulations, you've set up an IAM user. You've logged in as the IAM user for your account and you're ready to go.

</details>
