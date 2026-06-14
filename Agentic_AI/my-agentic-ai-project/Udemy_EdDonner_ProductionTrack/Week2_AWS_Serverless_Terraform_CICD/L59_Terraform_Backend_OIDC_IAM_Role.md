# L59 — Setting Up GitHub Actions for Automated AI Infrastructure Deployment

> **Week 2 · Day 5** · ⏱️ ~9 min

---

## 🎯 TL;DR

Deploy/destroy scripts ke `terraform init` ko **remote backend config** (S3 state bucket + DynamoDB lock) ke saath update karo. Phir ek aur **temporary Terraform file** se **OIDC IAM role** banao — taaki GitHub Actions ko bina long-lived keys ke AWS infra banaane ki permissions milein. Existing OIDC provider ho toh `terraform import`, na ho toh seedha `apply`; resource ARN note karke temp file delete.

---

## 🗣️ Hinglish Explanation

### Step 1: Deploy script ka `terraform init` update karo

`scripts/deploy.sh` mein ek `terraform init` line hai jo Terraform state set up karti hai. Ab ise update karna hai taaki wo **remote backend** (pichhle lecture mein banaaya S3 bucket + DynamoDB lock) use kare. Purani simple line:

```bash
# purana
terraform init
```

Naya version — backend config command-line flags se inject:

```bash
# naya — remote backend ke baare mein bataao
terraform init \
  -backend-config="bucket=twin-terraform-state" \
  -backend-config="key=terraform.tfstate" \
  -backend-config="region=us-east-1" \
  -backend-config="dynamodb_table=twin-terraform-locks"
```

Hum bas extra configuration pass kar rahe hain — Terraform ko bata rahe hain ki state files ke liye **special S3 bucket** aur lock files ke liye **DynamoDB table** set up hai. Yeh us "shared drive" ke baare mein `terraform init` ko inform karta hai.

> **PC/Windows users**: ye change PowerShell deploy script (`deploy.ps1`) mein bhi karo, even though tum script khud nahi chalaaoge — taaki repo complete rahe. (Mac users ko PS version touch karne ki zaroorat nahi, par chaaho toh kar lo.)

Aur **destroy script** bhi same tarah update karo. Is baar Ed poora `destroy.sh` (aur `destroy.ps1`) replace karta hai — naya version backend-aware hai. (Dhyaan: `deploy` aur `destroy` confuse mat karna.)

```bash
# destroy.sh — same backend-config terraform init
cd terraform
terraform init \
  -backend-config="bucket=twin-terraform-state" \
  -backend-config="key=terraform.tfstate" \
  -backend-config="region=us-east-1" \
  -backend-config="dynamodb_table=twin-terraform-locks"
# ... then terraform destroy ...
```

Ab scripts remote shared state ko refer karte hain. Save sab.

### Step 2: GitHub ko AWS access dena — OIDC IAM role

Ab GitHub par wapas. Agla kaam: GitHub Actions ke paas **AWS access** ka sahi tareeka set karna. Yeh cloud providers ke saath kaam karne ki "biology" ka hissa hai — bahut saari setup-stuff.

Problem: GitHub Actions ko Terraform chalaa ke infrastructure banaani hai, toh usko **AWS permissions** chahiye. Remember AWS **IAM** (Identity and Access Management) — users/roles ko permissions deta hai. Hume ek **IAM role** chahiye jo **GitHub Actions assume kar sake**.

Best approach: **OIDC (OpenID Connect)**. Iska matlab GitHub aur AWS ke beech ek trust relationship — GitHub Actions runtime mein ek short-lived token se AWS role assume karta hai, **bina koi long-lived access key/secret GitHub Secrets mein store kiye**. Yeh standard, secure pattern hai (static credentials se kahin behtar — wo leak/rotate-headache ka risk hote hain).

> **IAM role vs IAM user**: user = ek permanent identity with credentials; role = ek assumable identity (no permanent creds) jise koi trusted principal (yahan GitHub Actions via OIDC) temporarily assume karke uski permissions paata hai.

Phir se **temporary Terraform file** ka trick — taaki console mein manually IAM roles/policies na set karne padein. Cursor mein `terraform/` mein new file `github-oidc.tf`:

```hcl
# github-oidc.tf — TEMPORARY: OIDC provider + IAM role for GitHub Actions

# 1. OIDC identity provider for GitHub
resource "aws_iam_openid_connect_provider" "github" {
  url             = "https://token.actions.githubusercontent.com"
  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = ["6938fd4d98bab03faadb97b34396831e3780aea1"]
}

# 2. Role GitHub Actions can assume (trust policy restricts to your repo)
resource "aws_iam_role" "github_actions" {
  name = "github-actions-twin"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = { Federated = aws_iam_openid_connect_provider.github.arn }
      Action = "sts:AssumeRoleWithWebIdentity"
      Condition = {
        StringEquals = {
          "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com"
        }
        StringLike = {
          # owner/repo restriction — sirf tumhara repo assume kar sake
          "token.actions.githubusercontent.com:sub" = "repo:ed-donner/twin:*"
        }
      }
    }]
  })
}

# 3. Attach the policies the role needs (S3, Lambda, API GW, CloudFront, IAM, DynamoDB...)
resource "aws_iam_role_policy_attachment" "github_actions" {
  for_each = toset([
    "arn:aws:iam::aws:policy/AmazonS3FullAccess",
    "arn:aws:iam::aws:policy/AWSLambda_FullAccess",
    "arn:aws:iam::aws:policy/AmazonAPIGatewayAdministrator",
    "arn:aws:iam::aws:policy/CloudFrontFullAccess",
    # ... aur jo policies chahiye
  ])
  role       = aws_iam_role.github_actions.name
  policy_arn = each.value
}

output "github_actions_role_arn" {
  value = aws_iam_role.github_actions.arn
}
```

Ed in IAM policies ke detail mein nahi jaata — *"the great thing about these Terraform scripts is that if this works once, it should work nicely."* Yeh file un saari policies attach karti hai jo role ko chahiye.

### Step 3: Run karo — pehle check, phir import ya apply

Command line kholo, **`terraform` directory** mein jao, **default workspace** confirm karo (dev/test/prod nahi). Phir check karo ki kya yeh OIDC provider **already** exist karta hai:

```bash
# kya GitHub OIDC provider already hai? (ARN mile toh haan)
aws iam list-open-id-connect-providers
```

Ed ke case mein **already hai** (kyunki usne pehle run kiya tha). Agar tumhe ek **ARN** dikhe (AWS resource number), toh provider already exist karta hai — usse Terraform state mein **import** karna padega (warna apply "already exists" error dega):

```bash
# AWS account ID quickly nikaalo
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
echo $ACCOUNT_ID

# Sirf tab chalao jab provider PEHLE se ho — Terraform state mein import
terraform import aws_iam_openid_connect_provider.github \
  arn:aws:iam::$ACCOUNT_ID:oidc-provider/token.actions.githubusercontent.com
```

(`terraform import` existing real resource ko Terraform ke state se "adopt" kara deta hai — taaki Terraform use manage kar sake without re-creating.) Ed ka import "imported successfully" deta hai. **Yeh sirf tab zaroori hai jab tumhare paas provider already ho.**

Ab resources **apply** karo — do scenarios:

- **Scenario A (almost certainly tumhara case)**: OIDC provider exist nahi karta, pehli baar. Bas poora apply chalao (Mac/Windows ke alag versions hain). Sirf apna **GitHub username/repo** replace karna hai (`ed-donner/twin` ki jagah tumhara):

```bash
terraform apply \
  -target=aws_iam_openid_connect_provider.github \
  -target=aws_iam_role.github_actions \
  -target=aws_iam_role_policy_attachment.github_actions \
  -var="github_repo=ed-donner/twin"
```

- **Scenario B (Ed ka case — already imported)**: provider create NAHI karna (kyunki import ho chuka), toh same apply par bina provider create kiye (usne username/repo `ed-donner/twin` se replace kiya). `yes` type karke confirm.

Terraform "magic" karta hai, `yes` confirm, aur jo banana hai ban jaata hai. Ab GitHub ke paas wo backend hai jisse usko GitHub Actions chalaakar infra setup karne ki **permissions** mil gayi.

### Step 4: Role ARN note karo, temp file delete

Verify karne ke liye output dekho:

```bash
terraform output github_actions_role_arn
# arn:aws:iam::<account>:role/github-actions-twin
```

Yeh **ARN important hai** — agle lecture mein GitHub Actions workflow ko batana hoga ki konsa role assume karna hai. Ed ise clipboard mein copy karta hai aur ek note mein bhi rakh leta hai (taaki accidentally overwrite na ho).

Phir temporary `github-oidc.tf` delete kar do (yeh sirf console ke kai screens se bachne ke liye tha):

```bash
rm terraform/github-oidc.tf   # ya Cursor "Move to Trash"
```

Role ARN ka record rakho — agle video mein milte hain.

---

## 📋 Key Concepts

| Concept | Matlab |
|---|---|
| **`terraform init -backend-config`** | init ko remote S3+DynamoDB backend ke baare mein batao |
| **Backend-aware deploy/destroy scripts** | Dono scripts remote shared state use karein |
| **IAM** | AWS Identity & Access Management — kaun kya kar sakta hai |
| **IAM role** | Assumable identity (no permanent creds) jise trusted principal assume kare |
| **OIDC** | OpenID Connect — GitHub↔AWS trust, short-lived tokens, no stored keys |
| **Trust / assume-role policy** | Kaun (yahan ed-donner/twin repo) role assume kar sakta hai |
| **Policy attachment** | Role ko required permissions (S3/Lambda/etc.) dena |
| **`aws iam list-open-id-connect-providers`** | Check karo OIDC provider already hai ya nahi |
| **`terraform import`** | Existing real resource ko Terraform state mein adopt karo |
| **Resource ARN** | Amazon Resource Name — role ka unique ID (workflow mein chahiye) |

---

## 💼 Backend Dev Ke Liye Note

Is lecture ka core security lesson har backend engineer ko aana chahiye: **CI/CD ko long-lived cloud credentials mat do.** Purana (anti-)pattern tha — AWS access key + secret banao, GitHub Secrets mein paste karo, pipeline mein env vars se inject karo. Problem: ye keys non-expiring hain, leak ho sakti hain (logs, fork PRs), aur rotate karna painful. **OIDC federation** isse khatam karta hai — GitHub har workflow run par ek signed JWT issue karta hai, AWS STS use verify karke ek **short-lived (default ~1hr) temporary credential** deta hai role assume karne ke liye. Koi static secret store hi nahi hota. Trust policy ka `sub` condition (`repo:owner/repo:*`) critical hai — ise loose chhoda (e.g. wildcard owner) toh koi bhi repo tumhara role assume kar le, classic privilege-escalation. Python dev ke liye analogy: yeh wahi short-lived-token model hai jo tum OAuth2 client-credentials ya STS `AssumeRole` se backend services ke beech use karte ho. Aur `terraform import` jaanna zaroori — real-world Terraform adoption hamesha greenfield nahi hota; aksar pehle se maujood resources (jaise account-wide OIDC provider jo ek baar hi banta hai) ko state mein bring karna padta hai, warna apply "EntityAlreadyExists" se fail karta hai.

---

## ✅ Takeaway

- Deploy **aur** destroy scripts ke `terraform init` ko **`-backend-config`** (S3 state bucket + DynamoDB lock) ke saath update karo; PС users PS versions bhi
- GitHub Actions ko AWS access do via **OIDC + IAM role** — no long-lived keys (secure, standard pattern)
- Phir se ek **temporary `.tf`** likho jo OIDC provider + role + policy attachments banaaye
- Pehle `aws iam list-open-id-connect-providers` se check; **already hai** → `terraform import`, **nahi hai** → seedha `apply` (apna `owner/repo` daalo)
- **Role ARN note karo** (agle lecture mein workflow ke liye chahiye), phir temp file delete

---

<details>
<summary>📜 Full Transcript (English)</summary>

Okay. So within scripts deployed we've got this line, the Terraform init line that uh that that runs the sets up the, the Terraform status. We need to update this. So, uh, I'm going to, to copy these new lines. This replaces terraform init. Let's put it in there and then say what it does. And PC people you need to do this as well even though you're not going to run this script. Uh, and so I come on in here, let's find where is the Terraform init command. Can you see it? Here it is right here. The script goes into terraform directory and it runs terraform init. I paste this in and this is the new terraform init command. And what are we doing. Well we're just passing in some extra configuration with this command. We're configuring it just to let it know that we've got these special buckets set up for Terraform state files and for the lock files. So it's it's configuring our Terraform init to know about this special shared drive that we set up just for it's purpose Okay. Back here again. Uh, and, uh, we should also update the PowerShell version of it for completeness. Uh, and, uh. Yeah. Uh, Mac, people, you don't need to do this, but you can if you wish to have, like, a complete repo. But. So I'm going to find the terraform init command in the deploy one. Don't confuse, deploy and destroy. Um, and here it is Terraform init. Copy it. Paste in the new version. Save. And that's done. Back to the instructions. We also have to update the destroy scripts as well in the same way. This time I've actually got the entire script to replace. So this is the new destroy file. Copy all of that. There it goes. And copy that into the destroy sh. Select all paste save, and do the same for the windows version. Back to preview. Scroll down. Here it is. Doesn't it look different? Uh. Copy all of this. And there we go. Copy it in the final file to be changed, destroy PowerShell, paste the new version. Save it. And that is a go. Uh, and you can see right here the change. Ha. Okay, so back to the guide. Uh, so we've now we've now updated our scripts so that our deploy scripts are referring to these, these shared drives where we have our Terraform state. It's now time for us to go back to GitHub. And the first thing that we're going to do is going to be about setting up the way that the kind of access that GitHub has to AWS. So it's all part of the biology of working with these cloud providers that there's there's just so much stuff to do. Uh, there's not too much for GitHub actions, but there's still some stuff. And one of them is that remember that you have this whole thing about permissions in AWS, like permissions for IAM user. If Hub is going to have the ability to set up infrastructure running Terraform, then it has to have the right permissions to do this. An IAM role that GitHub actions can use. And so we might have to go in and set up a whole lot of stuff with our, um, with our configuration that set up stuff with AWS. But again, we can use this trick of just writing a temporary piece of Terraform to do it for us and run the Terraform to get around us having to do all this ourselves. So this is a Terraform script to create an IAM role that, that, uh, so that GitHub actions can, can have the powers that it needs. Um, and so I'm not going to talk in a lot of detail about what kinds of actions all these IAM role policies and everything else. And this is the whole list of policies we're giving it. The great thing about these Terraform scripts is that you can trust if this works once it should work nicely. So we're going to go to Terraform directory and set up a temporary file which is called GitHub dash. o DC, the type of authentication, the type of IAM setup that we're doing here. Do that and paste in the infrastructure we want, which contains all of the policies that we need to attach to this user. And now go back to the guide. So we've done all of this. And now we just have to one more time actually run this. Okay. So first of all we bring up a command line. We go to terraform directory. Don't forget to go to terraform directory. We make sure we're in the default workspace. So we're not in dev test or prod. And then we just run this quick command to see whether we already have this particular, uh, policies already set up. In my case I do because I've run this before. And depending on your situation, you probably won't, but you just might do, uh, so do this, this test. If you see an Arn, an AWS resource number like this, then you do have one already. And if that is true, if you do have one already, then we need to import it. So I'm going to do this quickly. I first of all this is just a quick hack to retrieve my AWS account ID, um, which is also in my clipboard. I could have got it from there, but it's nice to have this on hand. So if I echo it, you'll see that that is my account ID. And then this is commented out because you should only run this if you already have the provider. But this is importing that. Uh, and I then have to type in my GitHub repo in the form owner me slash repo twin like that. And it's done imported successfully. Now you won't need to have done that unless you already had one. Okay. Time to apply the resources. So for applying the resources there are two scenarios. One of them scenario A is what is almost certainly applying to you, which is that the Oidc provider did not exist. It's your first time doing this and you just have to run this big apply command here. There's one version for Mac, one version for windows, and the only thing you need to do be careful about is replace this here with your GitHub username and the name of the repo, like slash, uh, or whatever you are using, whatever is your username and your, your, uh, repo name. And this should run nicely. Uh, in my case, it already existed and I imported it. Uh, and so, um, this is what I need to run. I need to run this Terraform apply command right here, which just does the same, but it does not create this provider. Uh, so I'm going to paste in this command, and I'm just going to replace this part here, which is what you should have just done yourself with my name, my, my GitHub name and twin. And that should be it. I run this command. Terraform does its magic. It needs to be to type the word yes. And it's now creating what needs to be created. And it's done. So that has set up the, uh, necessary, um, backend so that GitHub now has permissions to be operating the GitHub actions, to be setting up our infrastructure. And just to confirm that all has gone well, we can now run this Terraform output command like so. And it tells us the name of the Amazon resource which is the the GitHub actions, uh, resource that it's going to be able to use to log in that GitHub actions will be able to use to have the right permissions. And you need to keep note of this because we will use it in just a second. So so I'm going to copy it to my clipboard and hope I don't accidentally copy anything else. Uh, maybe I'll take it, take a note of it somewhere. Um, and then we can remove this GitHub file right here, because this was only a temporary terraform file that we just used to avoid having to go around the various different screens in the AWS console, delete, move to trash. Keep a record of this right here, and I'll see you back in a.

</details>
