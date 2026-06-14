# L72 — Deploying AI Agents to GCP Cloud Run with Terraform Infrastructure

> **Week 3 · Day 2** · ⏱️ ~7 min

---

## 🎯 TL;DR

Pichle Azure deployment ka GCP version: hum ab apne **Docker container (cyber security analyst agent)** ko **Google Cloud Run** par Terraform se deploy karenge — ADC se authenticate karke, GCP Terraform workspace select karke, `terraform plan` → `terraform apply` chala ke. Container as a service ka magic: ek baar build, minutes mein live.

---

## 🗣️ Hinglish Explanation

### Context: Day 2 Part 2 — "cyber" repo, ab actual deploy

Yeh Week 3 Day 2 ka doosra half hai (`cyber` repo, `week3` directory). Pichle steps mein Azure par deploy ho chuka tha; ab **same Docker container** ko **GCP Cloud Run** par bhejna hai. Ed bolta hai — *"by the magic that is Terraform, this should be very straightforward"* — kyunki infra ki saari heavy lifting Terraform automatically kar deta hai. Hamara app ek **cyber security analyst agent** hai jo ek **MCP server (Semgrep)** spawn karke Python code scan karta hai.

### Background: GCP ki building blocks samajhna

- **GCP (Google Cloud Platform)** — Google ka cloud, AWS/Azure ka competitor. Har resource ek **project** ke andar rehta hai.
- **Project ID vs Project Name** — Project Name free-form text hai (jo chaho likho). **Project ID globally unique hota hai aur wahi matter karta hai** — letter-for-letter sahi copy karo, *"there's no room for error with these IDs"*. Hamari project ID hai `cyber-analyzer`.
- **Cloud Run** — GCP ka **container-as-a-service (serverless containers)**. Tum ek Docker image deti ho, Cloud Run usse on-demand chalata hai, traffic aane par **auto scale up** (aur idle hone par **scale to zero**) karta hai. AWS App Runner aur Azure Container Apps ka GCP equivalent. Deployment ka sabse simple, "no-nonsense" tarika jab tumhare paas already ek container ho.
- **`gcloud` CLI** — GCP ka command-line tool (AWS CLI / `az` jaisa).
- **Terraform** — Infrastructure as Code (IaC) tool: tum `.tf` files mein declaratively likhti ho ki kaunse resources chahiye, Terraform unhe create/update/destroy karta hai. Cloud-agnostic — same workflow Azure, GCP, AWS sabke liye.

### GCP Authentication: 3 layers (AWS se simpler)

Ed point karta hai ki GCP/Azure ka auth model AWS se **bahut simpler** hai — AWS mein har cheez IAM mein explicitly define karni padti hai, yahan nahi.

1. **`gcloud auth login`** — tumhare user account ko log in karta hai (browser khulega → allow). Yeh general CLI access ke liye.
2. **Application Default Credentials (ADC)** — `gcloud auth application-default login`. Yeh wo "simple login" hai jo **Terraform (aur koi bhi Google client library) automatically uthati hai** GCP par changes karne ke liye. ADC = standard way jisse libraries credentials dhoondhti hain.
3. **Quota / billing project link** — ADC ko batana padta hai ki kis project ki **billing/quota** ke against actions count hongi.

### Step-by-step: Environment setup

```bash
# 1. PROJECT ROOT mein hona zaroori hai (warna .env nahi milega)
# .env file ko environment variables banao (Mac command):
set -a; source .env; set +a
# (Windows ke liye next cell mein alag command hoti hai)

# 2. Terraform ko project ID batao — TF_VAR_ prefix se Terraform khud uthata hai
export TF_VAR_project_id=cyber-analyzer   # ID letter-for-letter copy karo

# 3. verify (loaded hai ya nahi)
echo $TF_VAR_project_id
```

> **`TF_VAR_<name>` convention**: agar tum koi env var `TF_VAR_project_id` set karti ho, Terraform automatically usse apni variable `project_id` mein inject kar deta hai. Secrets ko `.tf` files mein hardcode karne se bachne ka clean tarika.

### Step-by-step: Terraform directory + workspace

```bash
# Terraform/GCP directory mein jao (Azure aur GCP dono subdirs hain)
cd terraform/gcp

# Terraform initialize (providers download karega)
terraform init

# Workspace banao (pehli baar) — Ed ne already bana liya tha:
terraform workspace new gcp
# Phir select karo:
terraform workspace select gcp
# Double-check (hamesha careful raho):
terraform workspace show          # → gcp
```

> **Terraform workspaces** se ek hi config se multiple isolated **state files** maintain hote hain. Yahan Ed ne `gcp` aur `azure` workspaces alag rakhe hain taaki dono deployments ka state aapas mein na ghulmil jaaye.

### Step-by-step: Authenticate to GCP

```bash
# 1. User login (recently login kiya hoga to optional, par safety ke liye)
gcloud auth login                                    # browser → Allow

# 2. Active project set karo
gcloud config set project cyber-analyzer

# 3. ADC login — yahi Terraform use karega
gcloud auth application-default login                # browser → Continue

# 4. ADC ko billing/quota project se associate karo
gcloud auth application-default set-quota-project cyber-analyzer
# → "Quota project cyber-analyzer was added to ADC"

# 5. Docker ko gcloud credentials use karne do (images push karne ke liye)
gcloud auth configure-docker

# 6. Final sanity check
gcloud config get-value project                      # → cyber-analyzer
```

### `main.tf` mein kya hai (GCP, Azure ke parallel)

Cloud Run ka `main.tf` Azure wale ke saath nicely parallel hai:

- **Google provider setup** — `google` provider, project + region configure.
- **Docker setup** — image build same tarike se, **sahi platform** ke saath (Mac users ke liye important — Mac ARM hai par cloud x86/`linux/amd64` chahta hai, isliye `--platform linux/amd64` build hota hai warna container crash karega).
- **Cloud Run service** — actual service definition, jismein:
  - **CPU & Memory** — Ed yahan ek **gotcha** highlight karta hai: **Semgrep MCP server itself initializing mein kaafi memory consume karta hai**. Agar Cloud Run ko default resources par chhod do, server start hi nahi hoga ("not enough resources"). Isliye memory/CPU explicitly bada rakha gaya hai. (Ed ko yeh debug karne mein time laga tha.)
  - **API keys** — environment variables ke roop mein pass kiye gaye (jaise Azure mein the).
  - **Scaling settings** — min/max instances.
  - **IAM stuff** — kaun service ko invoke kar sakta hai (public access).
- **Outputs** — `service_url`, `project_id`, `region`.

```hcl
# (reconstructed — conceptual shape of terraform/gcp/main.tf)
provider "google" {
  project = var.project_id
  region  = var.region
}

resource "google_cloud_run_v2_service" "cyber" {
  name     = "cyber-analyzer"
  location = var.region

  template {
    containers {
      image = docker_registry_image.cyber.name
      resources {
        limits = {
          cpu    = "2"      # default kaafi nahi tha
          memory = "2Gi"    # Semgrep MCP server ko zyada RAM chahiye
        }
      }
      env { name = "OPENAI_API_KEY" value = var.openai_api_key }
      # ... aur keys
    }
    scaling {
      min_instance_count = 0   # scale to zero
      max_instance_count = 1
    }
  }
}

# Public invoke (IAM)
resource "google_cloud_run_v2_service_iam_member" "public" {
  name   = google_cloud_run_v2_service.cyber.name
  role   = "roles/run.invoker"
  member = "allUsers"
}

output "service_url" { value = google_cloud_run_v2_service.cyber.uri }
output "project_id"  { value = var.project_id }
output "region"      { value = var.region }
```

### Step-by-step: Plan aur Apply

```bash
# Plan — pehle dekho kya banega/badlega (kuch banata nahi, sirf preview)
terraform plan

# Apply — actually infrastructure banao
terraform apply
# Terraform poochta hai: "Do you want to perform these actions?" → type: yes
```

`terraform plan` ek **dry run** hai — sab resources list karta hai jo create honge (Docker image, Cloud Run service, IAM, etc.) bina kuch change kiye. `apply` ke baad famous **"yes"** type karna padta hai, phir Docker image build hota hai (Azure jaisa) aur GCP par infra ban jaata hai. Run smoothly chala — agle lecture mein result dekhenge.

---

## 📋 Key Concepts

| Concept | Matlab |
|---|---|
| **GCP Cloud Run** | Google ka container-as-a-service; Docker image se auto-scaling serverless service (scale-to-zero) |
| **Project ID** | Globally unique identifier (`cyber-analyzer`) — yahi matter karta hai, name sirf cosmetic |
| **`gcloud` CLI** | GCP ka command-line tool |
| **ADC (Application Default Credentials)** | Standard auth jise Terraform/Google libraries automatically uthati hain |
| **`set-quota-project`** | ADC ko batata hai kis project ki billing/quota use karni hai |
| **`configure-docker`** | gcloud creds ko Docker push ke liye wire karta hai |
| **`TF_VAR_<name>`** | Env var jo Terraform automatically apni variable mein inject karta hai |
| **Terraform workspace** | Ek config se multiple isolated state files (yahan gcp + azure alag) |
| **`terraform plan`** | Dry-run preview — kya banega/badlega, kuch change kiye bina |
| **`--platform linux/amd64`** | Mac (ARM) par x86 image build, taaki cloud par chale |
| **Cloud Run memory gotcha** | Semgrep MCP server ko default se zyada RAM chahiye, warna start fail |

---

## 💼 Backend Dev Ke Liye Note

Python backend dev ke liye yeh ek **multi-cloud portability** ka demo hai: **same Dockerfile, same agent code**, sirf alag Terraform config — aur container Azure se GCP par shift ho gaya. Yeh "build once, deploy anywhere" container philosophy hai jo tumhe vendor lock-in se bachati hai. ADC pattern AWS ke explicit IAM role/policy se contrast karta hai — GCP mein local dev creds aur library auto-discovery zyada seamless hai (par production mein service accounts use hote hain, ADC nahi). Aur woh **memory limit gotcha** real production lesson hai: jab tumhara process (yahan Semgrep MCP) startup par memory spike karta hai, default container limits silently OOM-kill kar dete hain — isliye resource limits ko apni app ke actual footprint ke hisaab se tune karna zaroori hai, sirf default par bharosa mat karo.

---

## ✅ Takeaway

- **Cloud Run = container-as-a-service** — ek Docker image do, baaki Terraform aur GCP sambhal lete hain (minutes mein deploy)
- Auth flow yaad rakho: `gcloud auth login` → `set project` → `application-default login` → `set-quota-project` → `configure-docker`
- **Project ID letter-for-letter copy karo** aur Terraform mein **`TF_VAR_project_id`** se inject karo
- Hamesha **`terraform plan`** se preview lo, phir **`terraform apply`** + type **"yes"**; workspace `gcp` confirm karo
- **Resource limits tune karo** — Semgrep MCP server default Cloud Run memory mein start nahi hota, explicitly bada rakho

---

<details>
<summary>📜 Full Transcript (English)</summary>

And welcome to the day two part two point in the week three directory in the cyber repo. I'm going to open the preview of day two, part two, which is when we actually make our Docker container and deploy it. And by the magic that is Terraform, this should be very straightforward. So we'll just bring up a new, uh, terminal. We will check that Terraform is in good shape, but I'm sure it is because we just used it. Uh, we're just going to get the projects list from gcloud. We're going to, uh, make sure that we understand, uh, the which project we're using. Cyber dash analyzer. There is both a project ID and a project name, and the name is like free form text. And the ID has to be unique, and the ID is the one that matters. We'll be using cyber Dash analyzer, which is probably what your one is called. Uh, but if not then then just use use whatever it is called. Uh, okay. So first of all we're going to run something that will just bring the dot env file and make it environment variables. And for this to work, by the way, I should mention you do need to be in the project root directory like that I run this. That's a mac command. There's a PC command in the next cell. And we're also going to set an environment variable called TF for Terraform variable project ID. And what we're going to do is we're going to call this exactly the ID cyber analyzer. Copy that letter for letter. You know there's no room for error with these IDs. There we go. So that's setting that ID. Now my Terraform var project ID is set to Cyber Analyzer. And you can run these checks to make sure they're loaded. But I'm sure they are. And the same for windows. You should run the checks though. Um and then we're going to go into our Terraform directory Terraform and then into GCP this time. Uh, when last time we of course went into the Azure subdirectory. We look over here in Terraform there's a GCP and an Azure directory. Oh and something hung over there from a test I did which we can delete. There we go. That's what you should see just Azure and GCP. Very nice. Uh, okay. So now we're going to do terraform init to set up Terraform. There it is. And then you'll need to run Terraform workspace new GCP. But I've already done that before. So all I need to do is Terraform workspace select GCP. It's done. And now Terraform workspace show because we like being double careful that we're doing everything right. There it is GCP is the workspace. We're in good shape. It's time to authenticate okay. So first of all we're going to log in to gcloud. This is probably not necessary since you've already logged in recently. But we'll just do it just to make sure. In we go allow. And we are authenticated okay. Now we're now going to make sure that we're looking at the project called uh Cyber Analyzer by running this uh, and we actually we already were in Cyber Analyzer, but whatever, we'll we'll run this and that is done. Uh, now what we now want to do is log in using something called the application default credentials, because that is the the simple login which Terraform will be using in order to make changes to GCP. Uh, and again this is quite similar to Azure. And it's just a very much simpler strategy than than AWS where everything has to be very explicit when it comes to to IAM. So this is allowing this application default account to be logged in. Continue. In we go. And what we're now going to be doing. And so these credentials will be used by any library that requests application default credentials ADC which is what Terraform is going to be doing. Uh, you have to tell, uh, Google Cloud that we want to associate this application default account with the quota, uh, with the billing for this project. So a little bit fiddly. Um, but that is saying that, that that is how to associate that, that is basically which billing account Terraform Terraforms actions are going to be associated with. So run that and it says quota project Cyber analyzer was added to ADC. The application default credentials, which can be used by Google client libraries for billing and quota. Uh. And now we run this command so that we can Docker can use these gcloud credentials. So we can push images and we get some message there. And let's just make sure that the application is there we go. We just want to make absolutely sure project is cyber analyzer. There it is. We're in good shape. Everything is authorized properly okay. It's time to run a Terraform command. First let's just look in Terraform folder. You'll see that there is of course an Azure and GCP directory. We are now in GCP land and there is a Main.tf. And the main.tf here is going to look hopefully quite nicely parallel with Azure. And should all be stuff that makes sense to you. Uh, we've got um the, the Google setups. We've got the Docker setup. That's much as before. We've got the Docker image that's built in the same way using the right platform that that is important for Mac people. And this is the cloud run service that's set up. And here are the details of it. It's worth looking at the CPU and the memory. It turns out in fact, and I don't think I mentioned this with the Azure deployment, that the Semgroup MCP server consumes quite a lot of memory and configuring itself. And if you leave it with default resources for cloud run, it doesn't work. There's not enough resources to run the Semgroup MCP server. And that caught me off guard to start with. Uh, so it took me a while to get to the bottom of that, but that's something that's needed here. Um, we're passing in our keys as before. Um, we've got some scaling settings, and then there is some IAM stuff and the, the project ID and region, uh, as, as output, sorry, service URL, project ID and region. Uh, so that is our Terraform setup. And what we can now do is run the plan command so that we can see what will happen when we call Terraform run, Terraform, apply. So here is the Terraform plan command. Uh, and uh this is what we get. So these are the resources that will be created when we run Terraform apply. And uh, it includes everything that we just looked at in that file, including this, this one here, which is, of course, the, the, uh, cloud run itself, the Google cloud run that will be created. So we are all ready to go with Terraform apply command. Okay. Here we go. Copy this. Terraform apply copy. Come here. Paste. And now we have to do the, uh the famous typing. Yes. And off it goes to create infrastructure on Google Cloud. We're hoping for a nice smooth run. Docker image is creating like before. I will, uh, stay glued to the screen, but I will spare you. Me? Uh yabbering away for a few minutes. I will see you in a second.

</details>
