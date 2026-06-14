# L29 — Deploying Dockerized AI Apps to AWS with ECR and App Runner

> **Week 1 · Day 5** · ⏱️ ~12 min

---

## 🎯 TL;DR

Local Docker image ko AWS par le jaate hain: ECR mein **`consultation-app` repository** banao, **AWS CLI** ko access keys se configure karo, Docker ko ECR se authenticate karo, image ko **Linux platform ke liye rebuild** karo (Apple Silicon gotcha!), tag karo, aur ECR par **push** karo. Phir **App Runner** mein ECR image se service create karna shuru karte hain.

---

## 🗣️ Hinglish Explanation

### Plan: local image → cloud → live service

Pehle `Ctrl+C` se local Docker container band karo. Ab production deploy ka rasta:

1. **ECR** (Elastic Container Registry) mein image upload karo
2. **AWS CLI** setup karo (terminal se AWS chalane ke liye)
3. Image build → tag → push to ECR
4. **App Runner** se us image ko live website bana do

### Step 1: ECR repository banao

**ECR (Elastic Container Registry)** = AWS ka private Docker registry, Docker Hub jaisa par tumhare account ke andar. Docker image (blueprint for containers) ko yahan store kiya jaata hai taaki AWS services use deploy kar sakein.

Console mein:
1. AWS console kholo, **AI engineer IAM user** se signed-in confirm karo (root nahi!)
2. Search box mein **`ECR`** type karo → Elastic Container Registry kholo
3. Upar-right mein **correct region** select karo — wahi jo `.env` ke `AWS_DEFAULT_REGION` mein hai (us-east-1 / mumbai / eu-west-1 jo bhi closest)
4. **Create repository** click karo
5. Repository ka naam **exactly `consultation-app`** rakho (baad mein yahi naam use hoga, isliye exact hona zaroori hai)
6. Baaki sab defaults theek hain → **Create**

### Step 2: AWS CLI ke liye access keys banao

**AWS CLI** = command-line interface jisse tum terminal se AWS resources manage kar sakte ho. Isse authenticate karne ke liye **access keys** chahiye.

Console mein:
1. Upar-right apne username (AI engineer IAM user) par click → **Security credentials**
2. Scroll down to **Access keys** section
   - *(Ed note: MFA bhi setup karna chahiye — woh fast move karne ke liye abhi skip kar raha hai, par production mein zaroor karo — koi tumhare IAM user ke roop mein na ghus jaaye)*
3. **Create access key** → **Command Line Interface (CLI)** select karo
4. AWS recommend nahi karta (woh roles prefer karta hai), par CLI ke liye valid use hai → **"I understand the recommendation"** tick karo
5. Description do, jaise `Docker push access` → **Create access key**
6. Ek CSV download karo jismein **two keys** hain:
   - **Access Key ID**
   - **Secret Access Key**
   - Dono carefully note karo (Secret key dobara nahi dikhega!) → **Done**

### Step 3: AWS CLI install + configure

```bash
# Mac:
brew install awscli

# Windows: official AWS CLI installer link se install karo
```

Phir (zaroorat ho toh naya terminal kholo):

```bash
aws configure
```

Yeh 4 cheezein poochega:

```
AWS Access Key ID     : <CSV se paste karo>
AWS Secret Access Key : <CSV se paste karo>
Default region name   : us-east-1     # tumhara closest region
Default output format : <blank / none — Enter daba do>
```

Done — ab CLI tumhare terminal se AWS access kar sakta hai.

### Step 4: Env variables reload + ECR par push

Pehle ensure karo `.env` variables loaded hain (helper script dobara chalao Mac/Windows version):

```bash
export $(grep -v '^#' .env | xargs)   # Mac/Linux
```

**4a. Docker ko ECR se authenticate karo:**

```bash
aws ecr get-login-password --region $AWS_DEFAULT_REGION | \
  docker login --username AWS \
  --password-stdin $AWS_ACCOUNT_ID.dkr.ecr.$AWS_DEFAULT_REGION.amazonaws.com
```

Yeh env variables use karke login karta hai → output: **"Login Succeeded"**.

**4b. Image ko Linux ke liye REBUILD karo — ⚠️ Apple Silicon gotcha!**

Tum soch rahe hoge "phir se build kyun?" — yahan ek **super sneaky** baat hai. AWS Linux backend boxes par chalta hai. Agar tum **Apple Silicon (M1/M2/M3)** par ho, toh tumhari pehle wali image **ARM (Apple Silicon)** ke liye thi — woh AWS par chalegi hi nahi. Isliye specifically **Linux/amd64** ke liye rebuild karo:

```bash
docker build --platform linux/amd64 -t consultation-app \
  --build-arg NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=$NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY \
  .
```

Yeh sabki "battle scars" wali galti hai. Ab poori image scratch se build hogi (pehle cache se ho gayi thi) — front end build, Next.js production export (optimized HTML/JS/CSS static pages), phir final image. Same do warnings aayenge — **ignore** karo.

**4c. Image ko tag karo:**

```bash
docker tag consultation-app:latest \
  $AWS_ACCOUNT_ID.dkr.ecr.$AWS_DEFAULT_REGION.amazonaws.com/consultation-app:latest
```

Ab image ECR repository ke "latest" version ke roop mein marked hai.

**4d. Push to ECR:**

```bash
docker push \
  $AWS_ACCOUNT_ID.dkr.ecr.$AWS_DEFAULT_REGION.amazonaws.com/consultation-app:latest
```

Image upload ho jaata hai — ab ECR mein baith gaya hai, deploy hone ke liye ready.

### Step 5: App Runner service create karna shuru karo

**AWS App Runner** = AWS ka simplest way to deploy a container as a live, scalable website. Tum bas image point karte ho, baaki (provisioning, load balancing, HTTPS, scaling) App Runner handle karta hai.

Recap: humne local-tested image banaya, deploy-ready kiya, ECR par push kiya. Ab App Runner ko bolenge ise live serve karo.

Console mein:
1. **App Runner** search karo → AWS App Runner kholo
2. **Create service**
3. Source: **Container registry** → **Amazon ECR**
4. **Browse** → repository `consultation-app`, tag `latest` select → **Continue**
5. Deployment settings: **Manual** → **Create new service role** → **Next**
6. Service name: **`Consultation App Service`** (Ed `...Service 2` likh raha hai kyunki uska pehla already chal raha hai)
7. **Compute**: bahut slim rakho — **¼ vCPU** + **0.5 GB memory** (lightweight, jitni chahiye bas utni)
8. **Environment variables** set karo — 3 secrets jo runtime par chahiye, `.env` se copy:
   - `CLERK_SECRET_KEY`
   - `CLERK_URL`
   - `OPENAI_API_KEY`
   - Har ek ke liye **Add environment variable** → Plain text → naam type karo → value paste karo

(Agla lecture port, auto-scaling, aur health check config karke deploy karega.)

### Pura flow recap

1. Local container band karo (`Ctrl+C`)
2. ECR repository `consultation-app` banao (correct region)
3. Access keys banao (CLI) → `aws configure`
4. `aws ecr get-login-password | docker login ...` (authenticate)
5. `docker build --platform linux/amd64 ...` (Apple Silicon fix)
6. `docker tag ...` → `docker push ...` (ECR par upload)
7. App Runner → Create service → ECR image → compute + env vars set

---

## 📋 Key Concepts

| Concept | Matlab |
|---|---|
| **ECR** | Elastic Container Registry — AWS ka private Docker image registry |
| **AWS CLI** | Command-line interface to manage AWS from terminal |
| **Access Key ID + Secret** | CLI authentication credentials (CSV se note karo, secret dobara nahi dikhega) |
| **`aws configure`** | CLI ko keys + region + output format ke saath setup karna |
| **`docker login` to ECR** | `get-login-password` se Docker ko private registry mein authenticate |
| **`--platform linux/amd64`** | Apple Silicon par bhi Linux/amd64 image build karna (AWS compatibility) |
| **`docker tag`** | Image ko ECR repository URL + `latest` se label karna |
| **`docker push`** | Tagged image ECR par upload karna |
| **App Runner** | AWS ka simplest container-to-live-website deployment service |
| **Compute (¼ vCPU, 0.5 GB)** | Lightweight machine size — jitni zaroorat utni |
| **Runtime env vars** | Clerk secret, Clerk URL, OpenAI key — App Runner mein inject |

---

## 💼 Backend Dev Ke Liye Note

Yeh ek complete container deployment pipeline hai jo har cloud-deploying backend dev ko aana chahiye. **Sabse important takeaway**: `--platform linux/amd64` — Apple Silicon devs production ko ARM image push kar dete hain aur woh silently fail/crash karti hai. Hamesha target platform ke liye build karo (ya `docker buildx` se multi-arch). ECR ka push flow Docker Hub jaisa hi hai, bas `docker login` ke liye `aws ecr get-login-password` se ephemeral token milta hai (12-hour validity) — yeh long-lived password se zyada secure hai. **Access keys** ki security note karo: yeh long-lived static credentials hain (riskier); production CI/CD mein inhe avoid karke **IAM roles / OIDC** prefer karo, par local dev/CLI ke liye theek hain. App Runner ko PaaS-for-containers samjho — Heroku jaisa DX, par AWS ke andar; ECS/Fargate ki tarah orchestration manage nahi karna padta. ¼ vCPU + 0.5 GB choose karna cost discipline ka achha example hai — over-provision mat karo.

---

## ✅ Takeaway

- ECR = AWS ka private Docker registry; repository naam **exactly `consultation-app`** rakho
- `aws configure` ke liye **CLI access keys** banao (secret key sirf ek baar dikhta hai — save karo)
- **Apple Silicon gotcha**: AWS ke liye `--platform linux/amd64` se rebuild karo, warna chalegi nahi
- Push flow: `docker login` (ECR) → `build --platform` → `tag` → `push`
- App Runner = simplest container deploy; compute ¼ vCPU + 0.5 GB, runtime mein 3 secrets inject karo

---

<details>
<summary>📜 Full Transcript (English)</summary>

All right. Now control C out of this Docker process. It's time to deploy to AWS App Runner. First of all we need to set set up our Docker container in the Elastic Container Registry or rather our Docker image. A Docker image or blueprint for containers needs to go in the Elastic Container Registry. So first things first we need to go back to the AWS console. Let's do that right away. Here we are. Uh let's go to AWS console. Sign in. We're already here. Make sure that it's the AI engineer user, not some other user, and go to the Elastic Container Registry. There it is. I just typed ECR in here. And up came the Elastic Container Registry for us right here. Uh, okay. And, uh, ignore the fact that I already have some things in here, including what we've got right now. Uh, because I may have done this before, but we are now going to upload your container to the Elastic Container Registry. Okay. So first make sure that you've got your right region selected here, whatever region is closest to you. Uh, you can see here there's like, like the, uh, the different US regions, like the West Coast and East coast, there's Mumbai and there is Singapore, and there's there's Canada, there's Europe. I think I mentioned EU West one. I know it's very popular. Uh, so uh, and SA East one. So these are the different regions that you might have selected. Make sure you've got the same one selected that you have in your env file that you've used for this. Then press create repository. Now what we're going to call this is going to be exactly consultation. Consultation dash app. Uh and it's got to be exactly that because we are going to use that later. And I hope it's about to complain to me that I've already got that set up if I've spelt it right. Uh, and then everything else is fine to leave as the default and then press create and I won't because it will throw an error because I've already got one created. And once you've done that, uh, you're set to come back to the instructions. So the next thing we're going to do is to configure the AWS cli, uh, which is the, the command line interface for interacting with AWS from a terminal on the screen. And the first thing we need to do is, uh, go back in as, uh, as to the console again. And we're going to go to the security credentials flag to set up this particular access right here. Uh, so, uh, we'll go over there right now and follow these instructions. So we're back in the AWS console. We're signed in as our IAM user AI engineer. You click up here and you go to security credentials right there like this. And over here on security credentials, you're going to scroll down. By the way, you should set up MFA. I don't have it set up right now because for this course I want to be able to move fast. But I will set it up shortly. And it's a good thing to have it set up. You don't want anyone to even come in as your AI engineer, and you come down to the access keys section and you press Create Access key. You select command line interface. Uh, it recommends not not doing that, but we have every reason to use the command line interface you tick. I understand the recommendations. You give it a value for to describe why you're using it. And you say something like Docker push access and then you press Create access key. And it's going to allow you to download a CSV with those details. And you'll see that there are two keys as part of it. And access key ID and a secret access key. And you need to keep note of both of them that got set up as part of that access key. Okay. And then. And then, uh, click. Done. And now it's time to set up the aws cli. So, uh, if you are on, uh, Mac, there's one instruction. You type this brew install aws, cli windows. You go to that link there and you install it from that link. And then when you're ready we're going to type AWS configure to set this up okay. So here I am I type AWS configure. You might need to to open a new terminal for this to come up. If you've uh only just installed the aws CLI. When I type that up it comes. It wants my access key. And this is where it already knows my access key. So I've done this before. You'll have to paste in your access key that you just took note of your secret access key that you'll also paste in, that you just took note of your default region name. You know this only too well. Now this is going to be whatever region you have selected. I'm going with us. East one output format. Leave that as none. And it's done. You've just set up the AWS command line interface so that you can access AWS from your terminal. Congratulations. Okay. It's time now to push this, uh, this, uh, two to the consultation app, our Docker image. And, uh, the, uh, we've we've already loaded our env variables, but but just just in case you haven't, I'm just going to go back and show you that one more time. I'm going back all the way back here to this app here. And this is the Mac step. I'm going to run this again to make sure that my environment variables are loaded in. And you should do the the windows version if you're on windows. Okay. Um, now back we go. Here we are now going to run the following set of commands to push this, uh, This Docker image to ECR. We're going to do them one by one and then that will be done. And I'm looking of course at the Mac Linux instructions. And directly below this are the PC instructions instead. So first of all we're going to authenticate uh Docker to to ECR. And it is just going to take our environment variables to set them up. So off it goes. It should say that that's logged in successfully. It says login succeeded. All right. We're now going to build our Docker image. Now you might wonder why we're doing this again when we just built our Docker image. And there's a good reason for it. And this this is super sneaky. So listen up. But it's super sticky for Mac users. Uh, you need to, to, to do this. If you're on you need to do this anyway. But particularly for people on Apple Silicon, uh, you need to be aware that, uh, you need to build the Docker container, specifically the Docker image. Sorry, specifically for a Linux backend box, because what you've already built is for Apple Silicon and wouldn't work if that were deployed to AWS. So this is like a sneaky thing that people discover, and everyone has some battle scars from this. If you have an Apple silicon like an like an M1 box, um, but that means we're actually seeing it now. Last time it did it all from the cache, this time it's actually building this. So this is what we didn't get to do together before. But you've already done it before, which is it is building the whole Docker image from scratch. It's right now it's just built the front end. It's now it's sorry. It's now doing the front end export. Uh, there you can see uh, see the export running in Next.js creating an optimized production build. This is the, uh, set of raw HTML, JavaScript, CSS files that can be served up representing our front end. That's all being built now. It's almost done generating the static pages. And then this Docker image will be built and ready to be deployed. So when that's done we're then going to to tag it so that it's marked as a consultation app. Latest. Here we go. It's just completed with the same warnings as before that we can safely ignore. We now run tag. It's now marked as the latest version of consultation app. And finally we push this to ECR. We're now pushing this Docker image to ECR. Off it goes. And I will let that push and I will see you in a second okay. It's done. It's done. All right. So now it is time for us to launch App Runner and actually get this thing going. Uh, if you've been following we've made a Docker image based on the Docker image that we already tested it locally. It works locally. We've now made that ready to be deployed, and we've uploaded it to the Elastic Container Registry. So it's now sitting there, and it's time now for us to tell AWS we want to launch this as as a website served on AWS. So we start by going back to the the console. Here we are. And we search for App Runner. Here is AWS App Runner coming up right now. All right. Uh, you can see I already have some of those running. And then what we're going to do next is uh, we're going to click on Create Service and then choose a container registry and Amazon ECR. Let me uh, do that create service Container Registry. Amazon ECR. Uh, and, uh, that's that's great. Uh, and then we'll click browse and select consultation app and latest browse here. Consultation app. Latest continue. And then deployment settings manual. Create new service roll deployment settings manual. Create new service roll. And then next. The service name that we're to give this is going to be Consultation App Service. And I'm going to call it Consultation App Service two because I've already got service running. Service two. Uh, and then the memory. We're going to have a very slim one. We're just going to have a quarter of a CPU and half a gigabyte, so it's nice and lightweight. Quarter of a CPU, half a gigabyte is set. So it's a very small machine, which is all that's required. And we now have to set the environment variables we're going to have to set if we look down here three environment variables clerk secret key, clerk URL and OpenAI API key that we will take all those three from our env file, which we've just got already ready to hand. And we're going to set them in here by pressing Add Environment variable. Uh it's a plain text. We're going to type out OpenAI API key and then copy and paste from our env file. And I'm going to go and do that now. And I will see you back in one second when I've done that.

</details>
