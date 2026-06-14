# L92 — Setting Up Aurora Serverless Database for Multi-Agent AI Systems

> **Week 4 · Day 1** · ⏱️ ~10 min

---

## 🎯 TL;DR

Hands-on: guide 5 follow karke Alex ka database deploy karna. **IAM** mein ek custom **Alex RDS policy** banao (JSON), usse **Alex Access** group mein attach karo, baaki standard policies add karo, phir **`aws rds describe-db-clusters`** se permissions verify karo. Phir `terraform/5_database` mein jaake `terraform.tfvars` set karke **`terraform init` + `terraform apply`** chalao — Aurora Serverless v2 (~$43/month) stand up ho jaata hai.

---

## 🗣️ Hinglish Explanation

### Guides folder + Guide 5

Cursor (Ed bolta hai "Cursa") mein Alex project khol ke **guides folder** kholo. Yahaan kaafi guides hain — aaj **guide 5** dekhna hai jo **database aur shared infrastructure** ke baare mein hai. Markdown preview kholne ke liye: file par **right-click → Open Preview**.

Guide ki shuruaat "Why Aurora Serverless v2" section se hoti hai (L91 ka recap + Neptune/DocumentDB/Timestream jaise extra mentions). Ek **architecture diagram** bhi hai (diagram dikhne ke liye ek **plugin install** karna pad sakta hai — Week 3 mein bataya tha):

```
[User] → [API Gateway] → [API Lambda]
                              ↓
        ┌──── Planner agent (orchestrator) ────┐
        ▼        ▼         ▼          ▼
     tagger   reporter   charter   retirement
        └──────────── all use ──────────────┘
                    [Aurora DB]
```

### Prerequisites

Steps 1–4 ready hone chahiye (pehle ho chuke). Ed clarify karta hai: pichle week ka **data ingest pipeline ek alag project** hai — Alex framework ko "educate" karega par **strictly required nahi**. Agar wo band kar diya toh bhi chalega; agar chalu rakha (S3 mein vectors update hote rahein) toh agent framework zyada knowledgeable / deeper financial expertise wala hoga. Bina uske bhi yeh week proceed ho sakti hai.

### Step 1: IAM — custom policy banao

*"Our exploits will begin with IAM where it always does."* Process:

1. AWS console mein **root user** ke roop mein jao
2. **Costs check** karo (always) — billing & cost management. (Ed ne course banaane mein bahut paisa kharch kiya; tum apna budget carefully watch karo.)
3. **IAM → Policies → Create policy**
4. **JSON tab** par click karo aur ek lambi policy paste karo (guide se), naam: **`Alex RDS policy`**
5. **Next → Save**

JSON policy structure (concept) — RDS aur RDS Data API actions allow karti hai:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "rds:*",
        "rds-data:*",
        "secretsmanager:GetSecretValue"
      ],
      "Resource": "*"
    }
  ]
}
```
> (Actual policy guide mein lambi hai — yeh shape samajhne ke liye reconstruction hai.)

### Step 2: Policy ko group mein attach karo

1. IAM → **User groups** → **Alex Access** (yeh group pehle setup hua tha)
2. **Permissions** tab → **Add permissions → Attach policies**
3. Apni custom **`Alex RDS policy`** attach karo
4. Guide mein listed **baaki standard policies** bhi add karo

Ed reminder deta hai: Week 3 mein usne yeh list pehle dikhayi thi aur kaha tha "head start ke liye ye sab pehle hi add kar lo" — agar kar liya toh pehle se hongi. Warna ab add karo. **Janky interface** — har policy ko manually check karna padta hai, aur clear nahi hota ki pehle se checked yaad rakhta hai ya nahi. **Bottom-right par Save.** Phir wapas aakar verify karo ki full list guide se match karti hai.

### Step 3: Permissions verify karo (IAM user ke roop mein)

Guide reminder: **root se sign out karke apne IAM user se sign in** karo — kabhi root mein logged-in mat raho.

Naya terminal khol ke:

```bash
aws rds describe-db-clusters
```

- Abhi koi cluster nahi hai → **empty list** return hona chahiye (yahi chahiye)
- Aur agar tum aisa command chalao jo arguments maange, toh ek standard message aata hai "what arguments are required" → matlab tumhare paas **RDS Data API commands** ka access hai, yaani **rds-data permissions** mil gaye

### Step 4: Terraform se Aurora deploy karo

Beauty yeh hai ki har din ki Terraform directory **alag** hai, toh hum existing infrastructure mein add kar sakte hain.

1. Alex directory mein `terraform` folder mein jao, phir `5_database` mein:

```bash
cd terraform          # Mac: forward slash; Windows: backslash
cd 5_database
```

2. Andar ek file hai **`terraform.tfvars.example`** — isme `aws_region`, `min_capacity`, `max_capacity` hain. Ise **copy → paste → rename** karke real `terraform.tfvars` banao (jo check in hoga). Yeh practice hamesha karo:

```bash
cp terraform.tfvars.example terraform.tfvars
```

3. **`terraform.tfvars` edit karo** — apne region ki values set karo (Ed ke liye `us-east-1`), baaki capacity values jaise hain waise rehne do:

```hcl
aws_region   = "us-east-1"
min_capacity = 0.5   # ACUs — leave as-is
max_capacity = 2     # ACUs — leave as-is
```

> **Cost estimate ~$43/month** agar yeh chalta rahe. Ed bolta hai: bahut lag sakta hai, par roz **`terraform destroy`** se bring-down kar sakte ho aur sirf use ke time chalao → kuch hi dollars. Credits ho toh shayad kuch bhi na lage.

### Step 5: main.tf samjho, phir apply

`terraform apply` se pehle **`main.tf`** dekho (infrastructure khud). Iska tour:

- **Providers** (hamesha pehle)
- **Random password create** karna + **Secrets Manager** mein DB credentials store karna
- **Default networking** build hoti hai (worry nahi karna)
- Aurora ko sahi **security group** dena
- **min/max capacity** = scaling configuration
- Password = wo random password
- **Backup + maintenance window** — yeh enterprise-caliber deployment ka sense deta hai (regular backups)
- **RDS cluster instance** — Aurora engine + version
- **IAM stuff** — sab permissions ensure karne ke liye

Phir:

```bash
terraform init    # state vars setup; pehli baar 1-2 min lag sakte hain
terraform apply   # plan dikhata hai, "yes" maango
```

`apply` plan dikhata hai → **yes** bolo → creation shuru. Aurora cluster + sab defined infra stand up hone mein **kuch minutes** lagte hain. Ed agle video mein milta hai jab ho jaaye.

---

## 📋 Key Concepts

| Concept | Matlab |
|---|---|
| **Guide 5** | Database + shared infra build karne ki instructions (markdown preview) |
| **Alex RDS policy** | Custom IAM policy (JSON) — RDS + rds-data + secretsmanager actions |
| **Alex Access group** | IAM user group jisme custom + standard policies attach hoti hain |
| **`aws rds describe-db-clusters`** | Permissions verify — empty list = sab sahi |
| **rds-data permissions** | RDS Data API access (HTTP se SQL chalane ke liye) |
| **terraform.tfvars** | Region + min/max capacity values (example se copy karke real banao) |
| **min/max capacity (ACU)** | Aurora Serverless v2 ka scaling range |
| **main.tf** | Actual infra — providers, secrets, networking, security group, backup, RDS cluster |
| **terraform init / apply** | State setup / actual creation (yes bolna padta) |
| **Secrets Manager** | DB credentials (random password) securely store hoti hain |

---

## 💼 Backend Dev Ke Liye Note

Yeh lecture pure **infrastructure-as-code + least-privilege IAM** workflow hai jo har backend engineer ko aana chahiye. **Custom IAM policy ko group par attach karna** = role-based access control (RBAC) — user ko direct permissions dene ke bajaay group ke through manage karo, scalable hai. **`describe-db-clusters` se smoke-test** karna = deploy se pehle credentials/permissions verify karna, jaise tum healthcheck endpoint hit karte ho.

Terraform side: **`terraform.tfvars.example` → `terraform.tfvars`** wala pattern bilkul `.env.example → .env` jaisa hai — secrets/region-specific config repo se bahar, sirf example check in. **`main.tf` mein random_password + Secrets Manager** = secrets ko code mein hardcode na karke runtime par generate karke vault mein daalna (12-factor config). **min/max ACU** = autoscaling bounds (jaise k8s HPA min/max replicas). Aur **`terraform destroy` daily** = ephemeral environments ka discipline — dev infra ko sirf zaroorat ke time up rakhna, cost control ke liye. Production mein tum yeh state ko remote backend (S3 + DynamoDB lock) mein rakhoge, par concept wahi.

---

## ✅ Takeaway

- **IAM pehle**: custom `Alex RDS policy` (JSON) banao → `Alex Access` group mein attach karo → standard policies bhi add karo
- **Verify**: `aws rds describe-db-clusters` → empty list = permissions sahi (rds + rds-data)
- Root se sign out, **IAM user** se kaam karo — kabhi root mein mat raho
- `terraform/5_database` mein `terraform.tfvars.example` ko copy karke region set karo (min/max capacity as-is)
- **`terraform init` → `terraform apply`** → Aurora Serverless v2 stand up (~$43/mo; destroy/apply se cost control)
- `main.tf` zaroor padho — random password, Secrets Manager, security group, backups = enterprise deployment ki jhalak

---

<details>
<summary>📜 Full Transcript (English)</summary>

And how great it is to be back in Cursa. Here we are in the Alex. Of course, I'm going to open the guides folder where you see a bunch of guides here, and we are going to look at, of course, guide five, uh, which is about the database. And I open the preview, right click and open preview to read our instructions for today. Building our database and shared infrastructure. It begins with a section why Aurora serverless v2. And there's a bunch of information about it. I mentioned a couple of others I didn't say before, like Neptune, which is the graph database. I think I mentioned DocumentDB already. Timestream is there time series one? And this is this is why we pick Aurora serverless v2. So let's keep going. Uh, there is then a diagram to show you a little bit about the architecture we're going to be building. Remember you may need to install a plugin to be able to see this diagram. I think I mentioned that last week. But we'll have a user they'll be able to use an API gateway. And this is going to be using the API Lambda. And then we will have four agents and a financial planner agent that orchestrates that were all using Aurora as their database. So, uh, prerequisites make sure that you are ready to go with steps 1 to 4, which we already did. It's probably worth me mentioning that what we did last week with the data ingest pipeline is something of a separate project. In a way, it's all going to be to be educating this agent framework, but it's not strictly a requirement. So if you shut that down and you want to move on from that, that's fine too. Your agent framework here will be more knowledgeable. It will have deeper financial expertise. If you do complete last week's course and you you have that project running and constantly updating the vectors in S3, but it's not strictly necessary. You can proceed with this week without it. All right? But as is so often the case, our exploits will begin with IAM where it always does. We need to go in to AWS console as the root user. It will also be a good time to check on costs. Always do that. Navigate to policies, create a new policy and click on the JSON tab and create this rather long policy right here. And then click next. And then save it with that policy. So let's go and do that. Now I'm going to select all of this. And then we will go in and do that together. So here I am in the AWS console I quickly do a quick check up there. It's my name. It's the root user. It's always a good moment to go to billing and cost management to check out what's happened to my costs. I've been spending lots of money building this course. I hope you're grateful. Hopefully you will not be spending this kind of money, and you will be obviously reporting your budget and watching it carefully to make sure that you don't do this. Uh, so what we're now going to do is go to IAM, which is where everything to do with security happens to do with access. So we now want to go to policies on the left. We go to policies and we are going to create a policy which I've already created. It's called Alex RDS policy. So I'm going to open this up to show it to you. But you will have followed the instructions to create it, and then you will have selected the JSON. And you can see what I've got here is pasting in that text that you saw then. So this is creating the policy. Uh, that is this, this RDS policy for Alex. And then be sure to save that and check that you can come back in and see it here just like this. And then as it explains in the instructions, you next go to user groups and you find Alex Access, which is the group we set up before. And you can come in here and go to permissions and you can add your Alex RDS policy, the custom policy that we just created. And add that in here as by going to add permissions and attach policies. And then there are a bunch of other policies for you to add as well. Listed there. And you might have already done this because if you remember way back in week three, I showed you I had this list here, and I said, by the way, you could get a head start by adding all of these in here and hopefully you did that. And so you may already have them, but if not, take a look at this list here, or look at the instructions. And by going to add permissions and attach policies, then select with that slightly janky interface when you have to check each one. And it's not clear that it's remembering what you already checked. And then you save on the bottom right. And then you should come back here and see this full list of policies which should should match the guide. And then we are good to go. Okay. So here we are back in cursor. And we now come to verify permissions. Uh so it also reminds us to sign out and sign back in as your IAM user so that you never leave yourself signed in as root. Okay. So we'll bring up a new cursor Cassette terminal. There we go. And now we're going to do AWS RDS describe-DB-clusters. And let's see what we have here. So we don't have any database clusters. It should return an empty list which is what we want. And if we run this then we should just get a standard little message uh, that tells us. Uh, yeah. What what, um. Arguments are required, which just tells us that we do have access to the data API commands. So we have the RDS data permissions, we have the permissions that we need. And it's now time for us to deploy our serverless database. And of course, the glorious thing about the way that we've built this with separate Terraform directories for each of the days of this course, is that we can do this in a way that we can just add this to the infrastructure we've already got. So in the Alex directory I can change to the Terraform directory again. Uh and I would do it directory by directory. This, this command is of course a mac command. Windows. You need the backslash instead of this. So I go CD Terraform to go into terraform directory and then go into the five database directory which is also we can come over here Terraform and then five database. And you can see in here there's a file called Terraform. Let me just click on that to show it to you. It's something which has uh an AWS region, a min capacity and a max capacity. And you should basically leave that as it is. So the first thing to do is to right click on this and do do copy and then paste and then rename the file that you pasted as Terraform vars. So it is now your real terraform.tf vars that you will check in. Um, although this one isn't going to have too much about it that we'll worry about, but still, it's worth doing this practice. So do that. Copy. Copy the Terraform.tf example to terraform.tf vars. And now edit and set the values to be the ones for your region. For me, it's us East one and then leave these as they are. Now, uh, the the estimate for this right now is $43 per month. If you if you leave it like this and you might think that sounds like a lot of money, but remember, you can bring down this infrastructure every day if you wish. And you can monitor the spend and only have it up when you're using it through the Terraform destroy command that we will do later. So you should only keep this running while you need it and only spend a few dollars. And anyway, you may have credits if you've signed up for an account, so hopefully this may cost you little to nothing. All right. But with that, it's time for us to run the Terraform commands. And so I'm in the five underscore database that this folder here within Terraform this is where I am. And I've made my version of Terraform.tf vars. And I'm now first of all going to run Terraform init. And that's going to be very quick for me because I've run it before Terraform init. And for you this may take a minute or two. Well it sets up all of the state variables and so on. And then I type Terraform apply to actually kick off uh, construction. But before I do, of course we should actually look at main.tf, which is the infrastructure itself. So let's quickly take a look at this. It begins with the providers as always. Uh, then we've got some stuff that creates a password. We use the Secrets manager to store credentials for our database. Uh, and as always, look through this and make sure that that you're comfortable with things. There's some stuff to do with having a default, uh, networking that gets built for us, so we don't need to worry about that. Um, then there's lots of stuff about giving the right security group to Aurora. Uh, read through all of this stuff. You can see all of the, um, the, the, the the min capacity. And max capacity is for our scaling configuration. The password is going to be this random password that was created. Uh, and we're then going to have a backup and maintenance period. This is the kind of thing that's so valuable to look at, because this gives you a sense of what it takes to have enterprise caliber deployment with things like regular backups. Uh, and, um, yeah. Then you can look at the, the, the RDS cluster instance that we're using, the Aurora engine and version, and then you can see some IAM stuff to make sure that we have permissions to everything that we need to be able to do. And that is our Terraform infrastructure. And with that we're ready to terraform apply. And so I run Terraform apply. It thinks for a bit while it works everything out. And it tells me the plan of what it will do. And it asks me to say yes. And when I say yes, off it goes. Creating stuff. And this does take a few minutes to set up all of our infrastructure, our Aurora cluster, and everything that was defined in that Terraform file. And I will let it do its thing, and I will see you in the next video when it's done.

</details>
