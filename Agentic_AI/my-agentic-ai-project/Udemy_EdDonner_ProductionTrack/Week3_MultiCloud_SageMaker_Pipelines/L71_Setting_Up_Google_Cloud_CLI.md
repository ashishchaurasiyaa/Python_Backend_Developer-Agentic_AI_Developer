# L71 — Setting Up Google Cloud CLI for Production AI Container Deployment

> **Week 3 · Day 2** · ⏱️ ~3 min

---

## 🎯 TL;DR

Short lecture: **Google Cloud CLI (`gcloud`)** install karke `gcloud init` se authenticate karte hain (browser sign-in), Cyber Analyzer project select karte hain, kuch config-check commands chalate hain, aur deployment ke liye zaroori **APIs enable** karte hain — Cloud Run, Container Registry, Cloud Build.

---

## 🗣️ Hinglish Explanation

### Google Cloud CLI install karo

Jaise Azure (`az`) aur AWS (`aws`) ke liye CLI install ki, ab GCP ke liye **Google Cloud CLI** (command line interface). Windows, Mac, Linux teeno ke install instructions hain (usual stuff) — `cloud.google.com/sdk/docs/install` se.

> **`gcloud` CLI** GCP ka official command-line tool hai. Isse tum projects manage, resources deploy, APIs enable, authentication — sab terminal se kar sakte ho. Terraform GCP par deploy karte waqt isi CLI ki authentication use hoti hai (Terraform `gcloud` ke credentials uthata hai).

### `gcloud init` — authenticate + configure

Naya terminal kholo aur:

```bash
gcloud init
```

Ye ek interactive setup chalata hai:

1. **"Welcome! This will take you through... installing, configuring gcloud."**
2. **"Reinitialize the current configuration?"** → **Yes** (chalega)
3. **Account select karo** — Ed ke paas do accounts dikhe, par usne **Option 3: "Sign in with a new Google account"** chuna — kyunki isse browser mein Google credentials daal kar easily ho jaata hai (manually kuch nahi karna padta)
4. Browser khulega → Google credentials → password → **Next** → **Allow** → authenticated!
5. Wapas terminal mein → **"Pick a cloud project to use"** → **option 1: Cyber Analyzer** chuna
6. **Default region** ke liye prompt aaye to instructions follow karke set kar do

Ab tum logged-in ho aur **Cyber Analyzer project** set hai.

### Typical CLI commands — config verify karna

```bash
# 1) Current configuration dikhao
gcloud config list
```

Output: `account` = tumhara account, `project` = cyber-analyzer, region = `us-central1`. 

```bash
# 2) Saare available projects list karo
gcloud projects list
```

Ed ke purane experiments bhi dikhe, par **Cyber Analyzer** wahin tha.

```bash
# 3) Sirf current project dikhao
gcloud config get-value project
```

→ `cyber-analyzer` (expected).

```bash
# 4) Enabled services/APIs test karo
gcloud services list --enabled
```

Abhi enabled services ki list dikhti hai.

### Step: Required APIs enable karo

GCP mein har service use karne se pehle uska **API enable** karna padta hai (Azure ke Resource Providers, ya AWS ki service-enablement jaisa). Container deployment ke liye ye APIs chahiye:

```bash
gcloud services enable \
  run.googleapis.com \
  containerregistry.googleapis.com \
  cloudbuild.googleapis.com
```

Inhe samjho:
- **`run.googleapis.com`** → **Cloud Run** — humare containers run karne ki ability (humara deployment target)
- **`containerregistry.googleapis.com`** → **Container Registry** — Docker images store karne ke liye (AWS ECR / Azure ACR jaisa)
- **`cloudbuild.googleapis.com`** → **Cloud Build** — containers build karne ke liye

> **Cloud Run** = managed serverless containers. **Container Registry** (ya naya **Artifact Registry**) = private image store jahan se Cloud Run image kheechta hai. **Cloud Build** = GCP ka managed build service — Dockerfile se image bana deta hai (CI ka building-block).

Ab account set up aur ready hai — agle lecture mein actually **container build aur deploy** karenge (Terraform se Cloud Run par).

---

## 📋 Key Concepts

| Concept | Matlab |
|---|---|
| **`gcloud` CLI** | GCP ka official command-line tool — auth, project mgmt, deploy, API enable |
| **`gcloud init`** | Interactive setup — account sign-in + project select + config |
| **Browser sign-in (option 3)** | Naye Google account se sign-in — easiest auth route |
| **`gcloud config list`** | Current account / project / region dikhata hai |
| **`gcloud projects list`** | Saare accessible projects list |
| **`gcloud config get-value project`** | Sirf current active project |
| **`gcloud services enable`** | Service ka API enable karna (use se pehle zaroori) |
| **Cloud Run API** (`run.googleapis.com`) | Serverless containers run karne ki ability |
| **Container Registry API** | Docker images store (≈ ECR / ACR) |
| **Cloud Build API** | Managed container build service |

---

## 💼 Backend Dev Ke Liye Note

Backend dev ke liye yeh lecture CLI-based cloud bootstrapping ka standard pattern hai — har provider par "install CLI → authenticate → set active project/account → enable services" ki same sequence (`aws configure`, `az login`, `gcloud init`). `gcloud init` ka browser-based OAuth flow **Application Default Credentials (ADC)** set karta hai — Terraform aur Google client libraries automatically isse credentials uthate hain (env var ya service-account key explicitly dene ki zaroorat nahi local dev mein). Production mein human-login ke bajaye **service account** + key/Workload Identity use hota hai, par local development ke liye `gcloud` user creds perfectly fine hain. **API-enablement** ko opt-in surface-area reduction samjho — GCP mein har project mein 200+ APIs hote hain, default sab disabled; tum sirf woh enable karte ho jinki zaroorat ho (Cloud Run, Registry, Build), jo security aur clarity dono ke liye accha hai. Aur **Cloud Build** ko note karo — agar tum CI/CD bina GitHub Actions ke chahte ho, to GCP-native CI yahin se banta hai (`cloudbuild.yaml` se build → push → deploy pipeline).

---

## ✅ Takeaway

- `gcloud` CLI install karo, phir `gcloud init` se authenticate (browser sign-in sabse easy) aur Cyber Analyzer project select karo
- Config verify karne ke liye: `gcloud config list`, `gcloud projects list`, `gcloud config get-value project`
- GCP mein har service ka **API enable** karna padta hai use se pehle (Azure Resource Providers jaisa)
- Container deployment ke teen zaroori APIs: **Cloud Run** (run), **Container Registry** (image store), **Cloud Build** (build)
- Yeh CLI auth Terraform deployment ke liye foundation hai — agle lecture mein build + deploy

---

<details>
<summary>📜 Full Transcript (English)</summary>

We're now going to install the Google Cloud CLI command line interface, much as we did for Azure and for AWS before that. So there's install instructions for windows, Mac and Linux. It's the usual stuff. Hopefully you'll quickly be able to do that. And then we bring up a new terminal and we're going to run gcloud init. Let's do that new terminal g cloud init. And off it goes. Welcome. This will take you through the process of installing configuring gcloud. Do we want to reinitialize the current configuration. Yep. We might as well do that. Uh, okay. Um, so we want to select an account. Now it shows me here, um, those two accounts, but I find I think it's easier to do option three. Sign in with a Google account. So it opens this up. That way I can just go through my Google credentials in my browser and not have to do anything. So I'm going to type out my password and I'll be right back when I've done that. Okay. Now press next and it comes and say allow. And we're now authenticated. Go back here and this is done. So, uh, it now says pick a cloud project to use. And obviously we want to use project number one, the cyber analyzer. Uh, so that is now set up. We have done Google init. We are logged in to the uh, the, the uh cyber analyzer project, which is set. And uh, also if you're prompted for a default region, then follow these instructions to okay, okay. Next let's just go through some typical CLI commands. This first one will explain our current configuration. Let's try that. Uh so we are account is my account. That's good. And the project is the project and we're in US central one. Excellent. Let's list all available projects. List them out. There they are. I've got some other things that I messed around with in the past, but Cyber Analyzer is right there, which is great. The current project, presumably this is going to work as well and just give us Cyber Analyzer, we hope. Let's see. It does just give us cyber analyzer. Jolly good. And now this one just to test the API. Uh, a bunch of different services that are enabled. Uh, very good. And now we're just going to ask to enable specific APIs that we may use. So we're just going to run this here. And importantly, of course this is running something called uh, run Google APIs, which is cloud run, our ability to run containers and container registry. Uh, and that's something which, uh, is also, uh, should, should sound familiar to you. And then something called cloud build, uh, which, which is, as it says, there will, will allow us to build containers. And so we have now got our account set up and ready, and we are ready to move forwards with actually building our container.

</details>
