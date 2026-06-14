# L28 — Containerizing Your AI App: Docker Images for Production Deployment

> **Week 1 · Day 5** · ⏱️ ~9 min

---

## 🎯 TL;DR

Apna pehla Docker image banate hain: ek **multi-stage `Dockerfile`** jo Node se static front end build karta hai, phir Python slim image mein backend + static files pack karta hai, health check aur uvicorn ke saath. `docker build` se image banate hain, phir `docker run` se locally container chalakar app live dekhte hain.

---

## 🗣️ Hinglish Explanation

### Docker kya hai aur kyun? (background)

**Docker** ek containerization platform hai. Ek **image** = ek self-contained "blueprint" jismein tumhara app + uske saare dependencies + OS libraries packed hote hain. Ek **container** = us image ka chalta hua instance (ek running process). Fayda: *"works on my machine"* problem khatam — jo image tumhare laptop par chali, wahi bilkul same AWS par chalegi.

- **Dockerfile** → recipe/description jo batati hai image kaise banegi (step-by-step instructions)
- **Docker image** → built artifact (immutable blueprint)
- **Docker container** → image se launch hua running instance
- **Docker Hub** → public registry jahan ready-made base images milte hain (e.g. `node:22`, `python:3.12-slim`)

### Step 1: `Dockerfile` banao — ek MULTI-STAGE build

Project root mein ek file `Dockerfile` (exactly yahi naam, no extension) banao. Ed ka Dockerfile actually **do images** banata hai — pehla **temporary** (sirf front end build karne ke liye), doosra final wala. Yeh "multi-stage build" pattern hai jo final image ko chhota aur clean rakhta hai.

```dockerfile
# ---- Stage 1: Front end build (temporary image) ----
FROM node:22 AS frontend
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
ENV NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=$NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY
RUN npm run build           # Next.js static export -> out/ folder

# ---- Stage 2: Final image (Python backend + static front end) ----
FROM python:3.12-slim
WORKDIR /app

# Python dependencies install karo
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Backend code copy karo
COPY api/server.py .

# Stage 1 se built static front end copy karo
COPY --from=frontend /app/out ./static

# Health check — container apne /health ko regularly hit karega
HEALTHCHECK --interval=30s --timeout=5s \
  CMD curl -f http://localhost:8000/health || exit 1

# Server port 8000 par chalega
EXPOSE 8000
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]
```

Line-by-line intuition (Ed bolta hai "don't worry, samajhna zaroori nahi, feel aana chahiye"):

1. **`FROM node:22 AS frontend`** → Docker Hub se Node v22 base image lo, isse "frontend" naam ka temporary stage banao.
2. Ismein env variable set karke **`npm run build`** chalao — yeh Next.js ko bolega static front end (HTML/JS/CSS) generate kar do (jo humne pichle lecture mein `output: export` se setup kiya).
3. **`FROM python:3.12-slim`** → ek alag, lightweight Python 3.12 base image se final image shuru karo (slim = chhoti, faster).
4. **`pip install -r requirements.txt`** → saare Python packages install karo.
5. **`COPY api/server.py .`** → backend file copy karo.
6. **`COPY --from=frontend ...`** → temporary frontend stage se built static site uthao aur `static/` folder mein "plonk" karo (yahi `server.py` serve karega).
7. **`HEALTHCHECK`** → container periodically apna `/health` endpoint hit karke khud ki sehat check karega.
8. **`EXPOSE 8000` + `CMD uvicorn ...`** → port 8000 par server launch karo. `server:app` matlab `server` module ka `app` object; host `0.0.0.0` (sab interfaces), port `8000`.

File ko **save** karo (white blob = unsaved).

### Step 2: `.dockerignore` (best practice)

`.gitignore` jaisa hi — yeh batata hai konse files Docker build mein **exclude** karne hain (bade/unwanted files na ghuse). Strictly required nahi, par achhi practice:

```
node_modules
.next
.git
.env
.vercel
*.md
__pycache__
```

### Step 3: Environment variables load karo (helper script)

Build ke time `.env` se secrets ko terminal environment variables mein load karne ke liye Ed ne ek chhota script diya hai (Mac/Linux ka alag, Windows ka alag). Yeh bas `.env` padh ke `export` kar deta hai:

```bash
# Mac / Linux — ek naye terminal mein chalao:
export $(grep -v '^#' .env | xargs)
```

Chalane ke baad saare env vars terminal mein set ho jaate hain — "bam, done".

### Step 4: Image BUILD karo 🐳

```bash
docker build -t consultation-app \
  --build-arg NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=$NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY \
  .
```

Yeh command Dockerfile ko padh ke step-by-step image banata hai:
- requirements copy + `pip install`
- `npm run build` (front end static build)
- static files ko `static/` mein copy
- final image ready

Pehli baar **2-3 minutes** lagenge (har step run hoga). Docker har step ko **cache** karta hai, isliye dobara chalane par instant hoga (Ed ka case).

⚠️ **Do warnings** aayenge build ke end mein — yeh complain karte hain ki hum env secret ko officially Docker container mein use kar rahe hain. Par yeh galat chinta hai: woh key actually **"publishable key"** hai (naam mein hi "public" hai), public hona safe hai. In dono warnings ko **safely ignore** karo.

Result: tum ab ek **self-defined Docker image** ke proud owner ho jo backend + front end dono package karta hai.

### Step 5: Container RUN karo (locally) 🚀

Ab image se ek chalta hua container banate hain:

```bash
docker run -p 8000:8000 \
  -e CLERK_SECRET_KEY=$CLERK_SECRET_KEY \
  -e CLERK_URL=$CLERK_URL \
  -e OPENAI_API_KEY=$OPENAI_API_KEY \
  consultation-app
```

- `-p 8000:8000` → container ka port 8000 host ke port 8000 par map karo
- `-e ...` → runtime environment variables (secrets) pass karo
- `consultation-app` → image ka naam

Container start hota hai, apne `/health` root ko hit karke "main theek hoon" confirm karta hai, aur running ho jaata hai. Browser mein `http://localhost:8000` kholo:

```bash
open http://localhost:8000
```

Aur — tada — user interface aa jaata hai. **Yeh app tumhare local box par ek Docker container ke andar chal rahi hai**, front end render ho raha hai, aur Clerk recognize karta hai ki tum already logged in ho. Pehla Docker container live!

### Pura flow summary

1. `Dockerfile` banao (multi-stage: Node build → Python final)
2. `.dockerignore` banao
3. `.env` ke secrets terminal mein load karo (helper script)
4. `docker build -t consultation-app .` → image banao (warnings ignore)
5. `docker run -p 8000:8000 ...` → container chalao
6. Browser → `localhost:8000` → app live locally

---

## 📋 Key Concepts

| Concept | Matlab |
|---|---|
| **Docker image** | App + dependencies + OS ka self-contained blueprint (immutable) |
| **Docker container** | Image ka running instance (ek live process) |
| **Dockerfile** | Recipe jo describe karti hai image kaise banegi |
| **Docker Hub** | Public registry of base images (`node:22`, `python:3.12-slim`) |
| **Multi-stage build** | Ek temporary stage (front-end build) + ek final stage (slim, clean) |
| **`FROM ... AS`** | Base image + named build stage |
| **`COPY --from=stage`** | Pichle stage se artifacts uthana (built static site) |
| **`HEALTHCHECK`** | Container apne `/health` ko khud check karta hai |
| **`.dockerignore`** | `.gitignore` jaisa — build se files exclude |
| **`docker build` / `docker run`** | Image banana / container chalana (`-p` port map, `-e` env vars) |
| **Publishable key warning** | Clerk public key safe hai — warning ignore karo |

---

## 💼 Backend Dev Ke Liye Note

Yeh ek production-grade containerization pattern hai jo har backend dev ko aana chahiye. **Multi-stage build** ka point yeh hai ki Node toolchain (jo sirf build ke liye chahiye) final image mein nahi jaata — final image sirf `python:3.12-slim` + tumhara code + static assets hota hai, isliye chhota, fast-pulling, aur kam attack-surface wala. Note karo `python:3.12-slim` choose karna (`python:3.12` ya `latest` nahi) — slim variant Debian ke minimal base par hota hai, image size dramatically kam. `HEALTHCHECK` Docker-native hai aur orchestrators (ECS/k8s) ise read karte hain. Secrets ko **build-time `--build-arg`** vs **run-time `-e`** mein distinguish karna critical hai: publishable (public) key build mein baked ho sakti hai (front end ko chahiye), par secret keys (Clerk secret, OpenAI key) **kabhi image mein bake mat karo** — woh hamesha runtime par inject karo, jaisa `docker run -e` mein dikhaya gaya.

---

## ✅ Takeaway

- **Image = blueprint, container = running instance**; `Dockerfile` = recipe
- Multi-stage build: Stage 1 Node se front end build, Stage 2 Python slim mein pack — chhoti clean image
- `docker build -t consultation-app .` (pehli baar 2-3 min, phir cached/instant)
- Clerk **publishable key warnings safely ignore** karo — woh public hai
- `docker run -p 8000:8000 -e ...` → `localhost:8000` par app locally live ho jaati hai

---

<details>
<summary>📜 Full Transcript (English)</summary>

All right. This is now the big moment when we get to create our own Docker image, starting with the Docker file. So in this step I've got a Docker file written right here. So let me copy all of this text. Remember the docker file is the description of how to create a Docker image. So we're now going to go to the project root and make a new file. And we're going to call it Dockerfile exactly like that. And paste it in there. And here it is. All right so let me just explain this Docker file. Now some people will have used Docker files many times before. And this will be old hat. Some people. This is the first Dockerfile you've ever seen. And this is going to blow your mind. Uh, and don't worry. Get intuition. You don't need to understand this. You just have to get a feel for it. So this set of instructions is actually going to end up creating two different Docker images. One of them we're only using temporarily. And we begin with the temporary one. So this from command says I want you to connect to something called the Docker Hub, which is a well known repository of existing Docker images, and use something as a starting point. I want you to use a node version 22 Docker image as your starting point, and then I want to run a few commands, which includes setting an environment variable and then running npm run build. And that's the command you may remember, which we've set up so that that will generate a static version of our website of our front end. Based on what we built in Next.js. It's going to ask Next.js to turn it into a static set of files. Okay, that's now been done. Now I'm going to work on the Docker image. I'm going to start with a version of Python 3.12, a slim, a very simple version of it, using an existing Docker image that's out there. And I'm going to adapt it. What am I going to do? Well, I'm going to start by pip installing all the packages in my requirements.txt. So everything's ready. I'm going to copy in my file API slash server dot Pi, which has my backend, and then I'm going to copy across from the temporary image that I just built a moment ago. I'm going to copy across this static website, and I'm going to plonk it in this new image I'm creating. You follow me here. And then I'm going to have this thing called a health check, which is going to be able to hit our health endpoint regularly. And then finally I'm going to say port 8000 is where I'm going to be running my server. And then I'm going to start up my server by making the command uvicorn. I'm going to say it's in the server module, the app, uh, class. And then I set my, my host and my port port 8000. And that will launch our web server listening on port 8000 within this Docker image. And so this then completes the definition of our of our Docker file, which defines the Docker image that we want to create. You can see it's not been saved yet I'm going to save it. And now this is saved. And now I'm going to do a quick best practice of creating a file called dockerignore. Not strictly required here, but this these have files that get excluded from building the Docker image. So new file dockerignore. It's a similar concept to a git. Ignore and paste in those files and save. And that's done. Okay. Uh there is now we're going to now go ahead and build a Docker image from this Docker file. So there's a script here, one for people on Mac and Linux and one for people on windows, which is very simple. All this does is it takes the environments that we set up in the env file, and it actually sets those as environment variables in our terminal. So if I open a new terminal here and I just run this script on a mac where I am when I run this, bam, it's done. Those environment variables are now set. Okay. And now this is the command I'm going to run this docker build command. So for you to have this straight. What this command does is it's going to take the Docker file, and it's going to use that to build a new Docker image as described in that file. And when I run this stuff starts to happen. And in my case it's very quick because I've already run it and it's able to use the thing that's run before. In your case, it will take longer because it will need to do each of the different steps. And you can see here how it's cached, the various different steps. But what it will need to do is copy in the requirements, run pip install to install everything on the Python side and then it will copy across. It will do a run npm run build which builds your your front end server, and then it will copy across those front end that static website from app out into static. And that means we've now used npm run build to build a static front end. And we've copied that into our server. And finally that is then running or getting ready to run. And at the end here, you'll see there are two warnings. And these warnings are warning you that we are using a, an environment, uh, secret that we're using it officially in our Docker container. And it's worried about that. But actually it's wrong to worry. This is in fact, it's even called a public publishable key. This key is something that can be public. It's okay to use this. So this warning, these two warnings can be safely ignored. You should expect them and ignore them. And that concludes we have just successfully built a Docker image from our Docker file. Uh, and as part of it, we created another Docker container and then ran it in order to be able to build our Docker image. But that is now done. It is built. It probably took 2 to 3 minutes for you. And then if you run it a second time, it will be instant like me. And congratulations, you're now the proud owner of a Docker image that you have defined and described that packages the back end and front end of this app, and what remains to be done next is to actually run it to make a Docker container out of this image. Let's give that a whirl. Are you excited? I hope you're excited. We're about to launch first Docker container. You probably forgot what our app even does now. It seems like such a long time ago. Uh, here it is. This is the docker run command for Mac and for windows. I'm going to run it on my Mac. Copy that command, paste it in the terminal. Let's see our Docker container come to life. It's using our image that's called consultation app. It started it and it's apparently running uh and it called its own health root to make sure it's okay. Let's launch and see what we have here. Uh, we'll say open. Okay. That's a good sign. That's our user interface. So just to make sure that you've really got this, this is running on my local box in a Docker container. This is the front end. And it's, it recognizes that I'm already logged in.

</details>
