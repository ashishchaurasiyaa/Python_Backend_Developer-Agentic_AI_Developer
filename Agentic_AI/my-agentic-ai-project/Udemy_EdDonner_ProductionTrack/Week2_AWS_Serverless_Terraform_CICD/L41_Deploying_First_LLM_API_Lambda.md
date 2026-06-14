# L41 — Deploying Your First Production LLM API on AWS Lambda

> **Week 2 · Day 2** · ⏱️ ~10 min

---

## 🎯 TL;DR

Ek cross-platform `deploy.py` script (Docker se packages build karke `lambda_deployment.zip` banata hai) chala kar code package karte hain, phir AWS console mein **`twin-API` Lambda function** banate hain, zip upload karte hain, **handler ko `lambda_handler.handler`** set karte hain, aur 4 **environment variables** (OpenAI key, CORS origins, `USE_S3`, `S3_BUCKET`) configure karte hain.

---

## 🗣️ Hinglish Explanation

Pichhle lecture mein humne code ko S3-aware aur Lambda-ready (Mangum se) banaya, aur IAM permissions set kiye. Ab actual deployment: code ko **package** karo, Lambda function **banao**, code **upload** karo, aur use **configure** karo.

### Problem: server code Lambda ke liye ready nahi hai

Hamara `server.py` directly Lambda par upload nahi ho sakta. Lambda ko ek **self-contained zip** chahiye jisme **code + saari dependencies** packaged hon. Lambda function apne aap `pip install` nahi karta — tumhe pre-built bundle dena padta hai. To hum kuch commands chala kar yeh zip banayenge, aur in commands ko ek **script** mein package kar denge — common practice.

### `deploy.py` — cross-platform packaging script

Backend mein naya file banao — `deploy.py`. Ed ne ise **sab platforms par chalne wala** banaya hai (thoda verbose, par universal). Yeh karta hai:

1. Backend folder ke andar ek subdirectory `lambda_package` banata hai.
2. Ek **Docker container** mein saare packages build karta hai — yeh ensure karta hai ki binaries **AWS Lambda platform ke liye sahi** hain. **Apple Silicon (M-series) Mac users ke liye yeh zaroori hai** (warna native ARM binaries Lambda ke x86 Linux par toot jaate hain). Doosre platforms ke liye simpler tareeke hain, par Docker wala har jagah kaam karta hai.
3. AWS-compatible Docker image mein **saari dependencies `pip install`** karta hai.
4. Files copy karta hai — `server`, `lambda_handler`, handler, context, resources — aur poori `data` directory bhi.
5. Sab kuch ek zip mein bundle karta hai — **`lambda_deployment.zip`**.

Conceptual shape (logic; exact instructions repo se):

```python
# deploy.py — backend ko package karke lambda_deployment.zip banata hai
import subprocess, shutil, os

PACKAGE_DIR = "lambda_package"

# 1. clean + create staging dir
shutil.rmtree(PACKAGE_DIR, ignore_errors=True)
os.makedirs(PACKAGE_DIR)

# 2+3. Docker container mein dependencies build karo (AWS-correct binaries)
subprocess.run([
    "docker", "run", "--rm",
    "-v", f"{os.getcwd()}:/var/task",
    "public.ecr.aws/lambda/python:3.12",        # AWS Lambda Python base image
    "pip", "install", "-r", "requirements.txt", "-t", f"/var/task/{PACKAGE_DIR}",
], check=True)

# 4. apna code + data copy karo
for f in ["server.py", "lambda_handler.py", "context.py", "resources.py"]:
    shutil.copy(f, PACKAGE_DIR)
shutil.copytree("data", os.path.join(PACKAGE_DIR, "data"))

# 5. zip banao
shutil.make_archive("lambda_deployment", "zip", PACKAGE_DIR)
```

> **Docker yaad dilao:** Docker tumhare code ko ek isolated, reproducible **container** mein chalata hai. Yahan hum ek AWS-provided Lambda base image use karke `pip install` chalate hain, taaki compiled dependencies bilkul ussi OS/architecture ke liye banein jis par Lambda chalta hai. **Docker Desktop running hona chahiye** warna script fail karegi.

Script chalao:

```bash
# backend directory mein
uv run deploy.py
```

Folder par nazar rakho — pehle `lambda_package` folder banega, phir Docker mein `pip install` chalega (Docker isliye taaki AWS ke saath definitely consistent ho), aur aakhir mein **`lambda_deployment.zip`** ban jaayega. Done — ab Lambda ke liye taiyaar.

### Lambda function banao — `twin-API`

Ab AWS console mein **IAM user (`AI engineer`)** ke roop mein login karo (root nahi):

1. AWS console → sign in → account ID, `AI engineer` IAM user se login. **Top-right par "AI engineer" dikhna chahiye** (confirm karo).
2. **Lambda** service search karo. Pehli baar "Welcome to Lambda" screen aayega — **Create function** par jao.
3. **Author from scratch** select karo (basics se banao).
4. Function name: **`twin-API`**.
5. Runtime: **Python 3.12**.
6. Architecture: **x86** (default chhod do).
7. Baaki sab defaults → **Create function**.

Tum apni pehli Lambda ke owner ban gaye — abhi kuch khaas nahi kar rahi, par exist karti hai.

### Code upload karo (Option A / B)

- **Option A (fast internet):** Lambda function par jao → **Code source** → right side **Upload from ▾** → **.zip file** → backend se `lambda_deployment.zip` pick karo → Open → "overwrite existing code" warning → **Save**. ~20MB upload hone mein thoda time lagega; timeout se pehle ho jaaye toh Option B ki zaroorat nahi.
- **Option B (slow internet):** "Upload from" → **Amazon S3** route (zip pehle S3 par daalo, phir Lambda usse uthaaye) — more robust par slower. Pehle A try karo.

Upload ke baad **ek error dikh sakta hai — ghabrao mat**, yeh expected hai (handler abhi set nahi hua). Function update ho jaayega.

### Handler set karo — `lambda_handler.handler`

Lambda ko batana padega ki kis function ko call karna hai. Yaad karo L40 — module `lambda_handler`, variable `handler`.

1. **Runtime settings** tak scroll karo (aasani se miss ho jaata hai) → **Edit**.
2. Default value hota hai `lambda_function.lambda_handler`. Use replace karo:

   ```text
   lambda_handler.handler
   ```

3. **Save**. Error gayab ho jaayega aur ek mini code preview dikhega — yeh ek chhota VS Code jaisa editor hai jisme tum apne uploaded files (context, resources, `data` directory with facts/style, Python packages) dekh sakte ho. Tumne apne box par zip banaya → upload kiya → Lambda ne unzip karke yahan rakh diya.

Yeh **big progress** hai: code Lambda par hai, aur Lambda ko pata hai use kaunsa entry point call karna hai.

### Environment variables — 4 zaroori

Lambda ko local `.env` ka pata nahi, isliye usme **4 env vars** set karne honge:

1. **Configuration** tab → left mein **Environment variables** → **Edit** → **Add environment variable** (har ek key + value):

   ```text
   OPENAI_API_KEY = sk-...           # apni asli key (.env se faithfully copy)
   CORS_ORIGINS   = *                # (note: CORS, "cross" nahi) — abhi star, baad mein refine
   USE_S3         = true             # lowercase t — S3 on
   S3_BUCKET      = twin-memory      # placeholder — baad mein full unique naam set hoga
   ```

   - **`OPENAI_API_KEY`** → LLM access (apni key, top secret).
   - **`CORS_ORIGINS`** → browser CORS allow-list; abhi `*` (sab allow), production mein specific origin (L45 mein refine).
   - **`USE_S3`** → `true` taaki Lambda S3 se memory padhe/likhe.
   - **`S3_BUCKET`** → memory bucket ka naam. Abhi `twin-memory` placeholder hai; L42 mein S3 buckets globally-unique hone ki wajah se isse account-ID-suffixed naam (`twin-memory-<account_id>`) mein badalenge.

Ed tumpe trust karta hai ki **chaaron vars** spelling-perfect aur faithfully copy-paste karoge — galti hui toh debug karna painful hai.

---

## 📋 Key Concepts

| Concept | Matlab |
|---|---|
| **`deploy.py`** | Cross-platform packaging script — `lambda_package` banata hai aur `lambda_deployment.zip` zip karta hai |
| **Docker-based build** | Dependencies AWS Lambda base image mein `pip install` — correct binaries (Apple Silicon ke liye must) |
| **`lambda_deployment.zip`** | Self-contained bundle: code + deps + `data/` — jise Lambda par upload karte hain |
| **`twin-API` Lambda** | Author-from-scratch function, Python 3.12, x86 |
| **Upload Option A / B** | Direct .zip upload (fast) vs S3-staged upload (slow internet) |
| **Handler `lambda_handler.handler`** | Lambda ka entry point — module `lambda_handler`, variable `handler` (Mangum-wrapped app) |
| **Post-upload error** | Handler set hone se pehle expected hai — ghabrana nahi |
| **4 env vars** | `OPENAI_API_KEY`, `CORS_ORIGINS=*`, `USE_S3=true`, `S3_BUCKET` |
| **Lambda code preview** | Mini VS Code — uploaded code/`data` browse karne ke liye |

---

## 💼 Backend Dev Ke Liye Note

Yeh **artifact-based deployment** ka core hai: source code ko ek immutable bundle (`.zip`) mein freeze karke deploy karna — same philosophy jo Docker image ya `pip wheel`/`tar.gz` release artifact mein hoti hai. **Docker-in-build** ka trick critical hai jise har backend dev ko samajhna chahiye: native extensions (e.g. `cryptography`, `pydantic-core`, `numpy`) **platform-specific compiled binaries** carry karte hain — apne ARM Mac par build karoge toh Lambda ke x86 Linux par `Invalid ELF header` / import errors aayenge. Isliye **target platform par build** karo (ya `--platform manylinux...` wheels). **Handler string** ko tum apne WSGI/ASGI entrypoint (`module:app`) ka Lambda-equivalent samjho. Aur env-var-driven config (key, CORS, storage toggle) wahi 12-factor discipline hai — secrets code mein nahi, runtime config mein. Aage chalke (Week 2 Day 4-5) yeh poora manual upload Terraform + CI/CD se automate hoga, isliye abhi har manual step ka "yeh asal mein kya badal raha hai" samajhna future automation ke liye blueprint hai.

---

## ✅ Takeaway

- `deploy.py` chala kar **Docker mein** dependencies build karo → **`lambda_deployment.zip`** banao (Apple Silicon par Docker-build zaroori).
- Console mein **`twin-API`** Lambda banao (author-from-scratch, **Python 3.12**, **x86**) — IAM user se, root se nahi.
- Zip upload karo (**Option A** direct, slow internet par **Option B** via S3); post-upload error expected hai.
- **Runtime settings → handler = `lambda_handler.handler`** set karo — error gayab, code preview aa jaayega.
- **4 env vars** set karo: `OPENAI_API_KEY`, `CORS_ORIGINS=*`, `USE_S3=true`, `S3_BUCKET` (placeholder — baad mein unique).

---

<details>
<summary>📜 Full Transcript (English)</summary>

So what we want to do now is take our server code and upload that to AWS Lambda so that it can run our server code as a Lambda function. Now, the thing is that our server code isn't ideally placed to be to be uploaded to Lambda. We really want it to be, uh, basically a zip file that we could, we can upload with everything packaged together nicely. And so there are a number of commands that we can run, uh, to, to build that zip file. And it's pretty common to package those kinds of commands into a script. And I've done that. And this is a pretty common practice. It's called deploy py. And we're going to put that script in the back end. Now I've made this script to be something that will work on all systems, which means it's a little bit more long winded than perhaps you might need for your system, because you could put something that's specifically for a PC or something. But this, this is something that will work across the board. Um, and so what I do within back end is I do new file and I'm going to create this thing called deploy py. It's a Python script. Paste that in. Here it is. So just to quickly explain what it does, the first thing it does is within the backend folder it creates a new subdirectory called lambda package. Should we should expect to see that appearing. Um and then into that it does a few things. First of all, and this is perhaps, uh, more, um, more careful, more, more robust than is always needed. But I create a Docker container in order to build all the right packages. And this makes absolutely sure that it's right for the AWS platform. And this is actually particularly needed for people who have Macs that are running Apple Silicon. You need to do it this way. For others, there are simpler ways of doing it, but this works on everything. So we run a Docker Docker run. It means that you need to have Docker desktop running. Uh, and it's going to package up, uh, using a Docker container designed for AWS. Um, and we pip install all the, all of the packages that we need. We then copy in files server, lambda handler, handle a context and resources in. We copy in the whole data directory and we zip it up into a zip file, which is called lambda deployment. So we'll expect to see that being created. We should see a whole folder being created and then lambda deployment zip being created. And that is what this script does. And as I say you could just run it line by line at the command line. But it's much nicer to package it up into a script. Let's go and run it. So to run it, I bring up a terminal. I go into back end. If I'm not there already, I keep an eye on this folder because I want you to see the things being created. And I'm going to go UV deploy dot pi. That should be it. And it's telling me that it's creating a folder. And there you can see it's created a folder called Lambda Package. It's currently running the pip installs and I'm doing that in a Docker container. You could just do it directly. If you have an architecture that's that's consistent with AWS, but doing it in Docker means that it will definitely work. It's created a zip lambda deployment. ZIP. And that all completed fine. So that's a nice deployment script. It's packaged everything up, it's made a zip, and we're now ready for Lambda. Okay, it's time to create our first Lambda function. And we do that by going into AWS as our IAM user this time and creating a function called twin API. So let's go and do that. We bring up a browser and here we are at the AWS Amazon.com. On the console I go to sign in to the console, uh, use my account ID, my AI engineer, IAM user and sign in and a double check that everything is good because up at the top right it should say AI engineer. It does. And now over here search for lambda and bring up lambda. And now for the first time you are looking at lambda. Now you might not see this. You're going to see a Welcome to Lambda screen because you've never seen it before. I think it's on the top right is where you can create a function for the first time. Otherwise, if you have ever created before, it's just here to create a Lambda function and we're choosing author from scratch. We're making a lambda function from the basics, and we're going to call it twin hyphen API. Call it twin API. The runtime for this we're going to have a Python 3.12. Python 312 will be our runtime. Select that there, leave the architecture as x86. And this is all we need to do. Everything else is the defaults. Press create function and you will be the owner of your first lambda function. Not doing very much, but it exists. Any second now I will, uh, there we go. All right. And this gives you some information about how to get started successfully created. Let's actually make it do something. So what you do next depends on whether you have a fast internet connection or not I do I'm going to go with option A. If not there's option B which takes you through a slightly slower route to do it in a more robust way. But try option A first and see if it works. It does on on most systems. Uh, so we're going to to go to the lambda function for the one we just created. We're going to look under the code source and upload our zip file. Uh so let's go and do that right now. So go back to my browser. Where are you? There it is. Uh, so, um, here here is the new Twitter API that we just created. We go here. We've already got code sources already selected. And on the right here is this upload from drop down. We click here and we're going to say a zip file. Uh if you had the slower connection you'll have upload it to S3 and you'll be going there. But we're going here. We're going to we're going to be be uh, be brave. Um, and uh, we're going to, uh, press the upload button and we come here and let's see where abouts we are. Are we in the right? We are indeed in twin. We're going to back end again and we pick lambda deployment and we press open and it tells us it's going to overwrite the existing code. And we're going to press save and it's going to load it in. And the first thing that we might see might, might be an error. But it shouldn't worry us. We will let it upload that up. And I guess it's going to certainly take a little bit of time because it's got 20MB to upload. Uh, as long as it does it before it times out, we won't need to do option B, we have. It's done updating the function twin API. Here it comes. This is the error that I told you we would see. And we're good with that. We expect it as you will see. Um, and um everything is looking great okay. So now we have to configure this lambda function so that it knows what it's meant to do. We have to look at the runtime settings and press edit. And we need to change the handler to this so that it knows where to find the code to run. You remember I told you to to make a mental note of lambda handler. The module and handler was the name of the variable in that module. So lambda handler handler is telling it, uh, where it goes to actually run this function. So we need to go to runtime settings and edit back to the browser. Here we go. Runtime settings. You have to scroll down to find runtime settings. It can catch you out. It's just here runtime settings edit. And now we come here. And the default is lambda function lambda handler. So we're going to replace that with this and press save. And when we do that and come back here the error has gone away. Hopefully there we go. And it's showing us a little preview of our code. This is like a little miniature VS code running in here which is kind of cool. Look at this. We could look at like uh, context and uh, resources. This is all the code that, uh, that even should have our data directory. It's called our Python packages. And, uh, well, you can satisfy yourself, but I'm pretty sure we'll find that our data directory will be there. It is data directory with facts and style and so on. So we zipped up everything on our box. We uploaded that zip to Amazon. We unzipped it. It automatically unzipped it into this lambda. So this is our code uploaded right here. And we've told it what it needs to call to be able to actually use this lambda. That's that's big progress. Who said this stuff was hard. It's easy. So the next thing we have to do is set some environment variables on our lambda function because it doesn't know things like our OpenAI API key that we just got set locally on our box. So there are in fact four variables we need to do OpenAI API key cause origins, which we need to set to a star, and we'll come back later and set that. Use S3 should be true and S3 bucket should be twin memory. And actually it's going to need to be something a bit longer than that. But we're going to come back and change it later. So let's do this step by step. So back we go back to, uh, to to this screen to the, uh, to the Lambda function in AWS. And the next thing we need to do is go to configuration and go to on the left hand side here to environment variables. And this is where you add environment variables. And you do it by pressing edit right here. And you press Add environment variable. And you do a key and a value. So like I'm going to say uh open AI API key. And here I'm going to put my API key which I'll take from my S3 file. And I'm going to go and do this now. And I'm going to have to trust you that you are going to put in your four environment variables and you're going to be super careful. Make sure that they're spelt right. Make sure you copy and paste faithfully, and you have the four ones we need to have. It's cause not cross. Uh, make sure you get everything right and I will see you in a second with perfect, pristine environment variables.

</details>
