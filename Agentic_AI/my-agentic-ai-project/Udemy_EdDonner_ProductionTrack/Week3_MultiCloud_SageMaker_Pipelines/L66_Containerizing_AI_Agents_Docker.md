# L66 — Containerizing AI Agents with Docker for Cloud Deployment

> **Week 3 · Day 1** · ⏱️ ~12 min

---

## 🎯 TL;DR

Pehle front end (Next.js, app router with `src/`) tour, phir app ko **bina Docker** locally chalate hain (`uv run server.py` + `npm run dev`) — agent Semgrep MCP spawn karke `airline.py` scan karta hai aur SQL injection + arbitrary `eval` jaisi vulnerabilities pakadta hai. Phir **multi-stage Dockerfile** (node stage front end build → python stage serve) se image build karke container locally run karte hain — bilkul same UI, par ab "box within a box". Container = cloud par bhejne ka tayyar artifact.

---

## 🗣️ Hinglish Explanation

### Front end tour — Next.js with `src/` + app router

Front end ek **Next.js app** hai (app router). Is baar Ed ne create karte waqt **`src` (source) option** use kiya, toh `app` folder ek **`src/` folder ke andar** hai (na ki direct `frontend/` mein, jaise pehle tha). App router use ho raha hai, isliye `app/` folder dhoondho, `pages/` nahi.

- Pichhle weeks: directories direct `frontend/` ke andar.
- Ab: `frontend/src/` ke andar — bas chhota sa change, baaki sab same.
- **`layout`** + **`pages`** files hain. Saara action **pages** mein hota hai. Kuch installed components use hote hain.
- Sab pehle se configured hai — ek clean, simple UI deta hai.

Ed bolta hai UI usne khud nahi banaya — **Claude Code** se banwaya, jisne fabulous kaam kiya (couple of iterations lage). "I don't have the taste to pull off a UI like this."

### Step A: App ko BINA Docker locally chalao

Pehle Docker magic ke bina chalakar dikhayenge ki kaise kaam karta hai.

**Back end chalao:**

```bash
cd backend
uv run server.py
# Listening on port 8000
```

`uv run` = UV (fast Python package manager) project mein script chalata hai, virtualenv auto-handle karta hai. Yeh plain Python server hai — koi container nahi.

**Front end chalao (naya terminal):**

```bash
cd frontend
npm install     # Ed ke liye no-op tha; tumhare liye packages install honge
npm run dev
```

⚠️ **Important gotcha** — front end ko sahi **localhost URL** se kholna hai (terminal do URLs dikhayega — usually `localhost:3000`, na ki network IP wala). Reason: front end aur back end ko hook karne ki "cleverness" hai. Ed bolta hai "take my word for it" — guide mein detail hai.

UI khulta hai — clean Cyber Security Analyst interface.

### App ka end-to-end flow (locally, no Docker)

1. **"Open Python File"** dabao → `airline.py` choose karo → contents UI mein dikhte hain.
2. **"Analyze Code"** button enable hota hai → dabao.
3. Ab pure agentic pipeline chalti hai:
   - **OpenAI Agents SDK** agent launch hota hai.
   - Agent **MCP server spawn** karta hai (separate process on your machine) jo **Semgrep** se connect karta hai.
   - SDK ko sirf **ek tool** (`semgrep_scan`) available hai (static tool filter).
   - Tool launch → Semgrep connect → file par analysis run.
   - Results aate hain → **structured outputs** (SecurityReport) presentable format mein.

**Result:** "Analyzed 2237 characters of Python code. Semgrep found 4 issues, and I identified 1 additional issue" (agent ko prompt mein extra issues add karne ki chhoot di gayi hai).

Issues jo nikle:
- **SQL injection** (classic) — SQL cursor mein values seedhe shove ki gayi thi. User "London" ki jagah quotes close karke dangerous SQL daal sakta hai. LLM agar fool ho jaaye toh havoc.
- **Arbitrary code execution** — `eval`-style expression evaluate ho raha tha → CVSS **9.8/10 (critical)**, shayad sabse bura.
- **Denial of Service** — unrestricted Gradio launch ki wajah se potential DoS (lower severity).

Point yeh nahi ki cybersecurity analyst dikhayein (woh fun commercial project hai) — point yeh hai ki **local deployment kaise dikhta hai**: ek web server + Python backend, front end backend se baat karta hai, backend ek **MCP server (separate process)** spawn karta hai. Local par yeh easy hai. Ab ise **package** karna hai.

Dono servers band karo: har terminal mein **Ctrl+C**. Back end band karte waqt **Semgrep server ka trace** dikhega — proof ki MCP actually chal raha tha.

### Step B: Dockerfile — multi-stage build

Top directory mein **`Dockerfile`** hai. Week 1 ke healthcare app jaisa, par ab tum ise behtar samajhoge. Yeh **do images (multi-stage build)** banata hai:

**Stage 1 — node image (front end build):**
- Node base image use karke front end build hota hai.
- `npm run build` → Next.js ko **static website** mein compile karta hai.
- Sirf output (built front end) chahiye, baaki node toolchain final image mein nahi jaata.

**Stage 2 — python image (serve):**
- Python container banao → **UV install** karo → dependencies ready karo.
- **Critical line**: stage 1 se built front end ko **copy** karo Python container mein.
- **Health check** add karo.
- **Port 8000 expose** karo.
- **Uvicorn** se server run karo.

```dockerfile
# Stage 1: build the Next.js front end
FROM node:24-slim AS frontend-builder
WORKDIR /app/frontend
COPY frontend/ ./
RUN npm install
RUN npm run build          # -> static website output

# Stage 2: Python runtime that serves everything
FROM python:3.12-slim
RUN pip install uv
WORKDIR /app
COPY backend/ ./backend/
RUN uv sync                # install backend deps
# copy the built front end from stage 1 into the python image
COPY --from=frontend-builder /app/frontend/out ./backend/static

HEALTHCHECK CMD curl --fail http://localhost:8000/health || exit 1
EXPOSE 8000
CMD ["uv", "run", "uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Multi-stage build kyun?** Front end banane ke liye Node chahiye, par final running image ko sirf static files chahiye + Python. Multi-stage se final image **slim** rehti hai (Node toolchain bahar reh jaata hai) — chhoti image = fast deploys, kam attack surface.

### Step C: Image build karo aur container run karo

Pehle Docker check karo (naya terminal):

```bash
docker --version      # docker installed hai?
docker ps             # docker running hai? (running containers list karta hai)
```

Agar `docker ps` fail ho → **Docker Desktop** launch karo applications folder se.

**Image build karo** (image ≠ container — Ed clear karta hai, log galti karte hain):

```bash
docker build -t cyber-analyzer .
```

Pehli baar **2-5 min** lagega — base images download, dependencies install, front end build, sab package. Subsequent builds caching se fast.

**Container run karo** (image → running container):

```bash
docker run --rm --env-file .env -p 8000:8000 cyber-analyzer
```

- **`--rm`** → stop hone par container delete ho jaaye (hanging around na rahe).
- **`--env-file .env`** → secrets pass karta hai (OpenAI + Semgrep keys).
- **`-p 8000:8000`** → host port 8000 ko container ke 8000 par map.
- **`cyber-analyzer`** → image naam.

Container start hoke `localhost:8000` par chalega. **No deployments yet** — yeh tumhare local box par ek Docker container hai, ensure kar rahe hain project pehle locally kaam kare.

### Result: same UI, ab box-within-a-box

`localhost:8000` kholo → bilkul **same UI** dikhta hai. Par dhyaan se dekho — ab "front end" alag se nahi chal raha. Front end ko **straight-up static website** mein compile kar diya, aur **ek backend FastAPI server** us static site ko serve kar raha hai. Sab kuch ek container ke andar.

Phir se `airline.py` → "Analyze Code" → GPT-4.1 mini → results. Is baar: "Semgrep found 4 issues and I identified 2 additional issues" (pichhli baar 1 tha — har run thoda alag ho sakta hai; ek extra low-priority "detailed error message" issue intentionally daala gaya tha).

**Asli point:** app ab ek Docker container mein packaged hai jo local box par "box within the box" chal raha hai. Agar sirf local par chalana hota toh front+back separate chalane se zyada benefit nahi. **Real benefit**: ek baar container mein package ho gaya, toh ise **cloud platform par ship karna super easy** ho jaata hai — aur agle lecture mein yahi Azure par karenge.

---

## 📋 Key Concepts

| Concept | Matlab |
|---|---|
| **Next.js with `src/`** | App router wala project jahaan `app/` folder `src/` ke andar hota hai |
| **`uv run server.py`** | UV project mein Python server chalana (virtualenv auto-managed) |
| **`npm run dev`** | Next.js dev server start (front end), sahi `localhost` URL kholna |
| **Local agentic flow** | Backend MCP server (separate process) spawn karta hai, Semgrep scan, structured output |
| **Multi-stage Dockerfile** | Stage 1 node (front end build) → stage 2 python (serve) — slim final image |
| **`npm run build`** | Next.js ko static website mein compile karna |
| **Image vs container** | Image = blueprint; container = running instance of image |
| **`docker build -t`** | Image banana (tag/naam ke saath) |
| **`docker run --rm --env-file -p`** | Container run: auto-delete, secrets inject, port map |
| **HEALTHCHECK / EXPOSE 8000** | Container alive-check + port advertise — cloud ke liye zaroori |
| **CVSS 9.8 (critical)** | Arbitrary code execution (`eval`) — sabse bura vulnerability mila |

---

## 💼 Backend Dev Ke Liye Note

Yeh lecture **production containerization ka gold standard** dikhata hai jo har backend dev ko aana chahiye. Teen cheezein internalize karo: (1) **Multi-stage build** — build-time tools (Node, compilers, dev deps) ko runtime image se bahar rakho. Tumhari final image jitni chhoti, utna fast pull/deploy aur utna chhota attack surface; yeh ek production best-practice hai, optional polish nahi. (2) **"Build once locally, deploy anywhere"** — Ed ka pura workflow yeh hai: pehle plain `uv run` se chalao (debug easy), phir container mein same cheez chalao (`docker run`), phir hi cloud. Jab container locally chalta hai toh cloud par bhi chalega (modulo Apple Silicon platform flag) — yeh dev/prod parity hai jo "works on my machine" bugs khatam karti hai. (3) **Static front end + single backend serving it** — yeh ek classic full-stack production pattern hai: Next.js ko static build karke FastAPI/Uvicorn ke through serve karna, taaki ek hi container/port se pura app mile (alag CDN/origin ki zaroorat nahi). `--env-file .env` se secrets inject karna note karo — production mein yeh secrets manager (AWS Secrets Manager / Azure Key Vault) se aata hai, par mechanism same — env vars container mein runtime par inject hote hain, image mein bake nahi hote.

---

## ✅ Takeaway

- Pehle **bina Docker** chalao (`uv run server.py` + `npm run dev`) — agent Semgrep MCP spawn karke real vulnerabilities (SQL injection, `eval` CVSS 9.8, DoS) pakadta hai
- **Multi-stage Dockerfile**: node stage front end build → python stage serve; final image slim
- **Image vs container** alag cheezein hain — `docker build -t cyber-analyzer .` (image), `docker run --rm --env-file .env -p 8000:8000 cyber-analyzer` (container)
- Container mein front end **static** ban jaata hai, ek FastAPI server use serve karta hai — same UI, "box within a box"
- Local container kaam karta hai = cloud par bhejne ka tayyar artifact (Apple Silicon platform flag ka dhyaan)

---

<details>
<summary>📜 Full Transcript (English)</summary>

And that was looking at the back end. Let's just take a moment to look at the front end. The front end is a Next.js app, of course, and it's a Next.js app. It's got all of the folders you should be familiar with. Actually, this time when I created it, I did use that src the source option so that it created the app folder as it's using app router of course. So we're looking for an app folder, not a pages folder. And that's within a source folder here. So it's just a small change on how we did it before last time. These files, these these directories were immediately within front end. This time they're under a source directory but otherwise very, very similar to what we did before. The same kind of configuration. Everything is already set up for you. It's a nice, very simple app. If it's got the same layout and pages, pages is where the action happens, by all means look through it. But this is it's using a few installed components. Um, and it should just give us this very simple user interface for our cyber security researcher. Okay, back to the instructions. We are now going to open a terminal. And in the terminal we are going to go into the backend directory. Here we go. And we are going to do UV run server dot pi. And that is going to run our Python server. There it goes listening on port 8000. No Docker containers nothing like that. This is simply a Python server. I'm going to show you how it works without any container magic first. We're now going to go and deploy our front end. Let's open a new terminal. Here it is. We go into the front end folder. We're going to do npm install. This won't do anything for me, but for you it should install a bunch of packages that you haven't installed yet. And then npm run dev is how we start the front end. There we go. There is the front end. Now one little thing to watch out for here. You need to launch the front end with this URL localhost. Not with this one. Uh, just because of some cleverness about how this the front end and back end are hooked up together. You can read more about it in the in the guide should you wish, but take my word for it, this is the one to open up. So I click here. Up it comes. And here we are looking at our Cyber Security Analyst. And you'll notice this has got a nice fresh user interface. It's quite clean and pleasant. And I'd like to pretend that I did this user interface myself, but I did not. I asked Claude Code, and Claude Code did a fabulous job. Uh, I did need to iterate a couple of times. Uh, it does take work to get to a good outcome, but the outcome, I think, is terrific. And there's no way I don't have the taste to pull off a UI like this. Anyways, I press open python file, I choose airline.py, I press open. The contents of that file appears right here. The analyze code button has become enabled and I can press that. And this is now launching my agent using OpenAI agents SDK. That is then going to launch my MCP server to connect to Semgroup. It's only going to give one tool available to OpenAI agents SDK to to GPT for one mini. It's going to launch that tool. Launch Semgroup. Connect to Semgroup. Run an analysis on this file. The results will come back. It will use structured outputs to return them in a presentable format, which should appear any second now. And here it is. Here's the results of our analysis. It analyzed 2237 characters of Python code. Semgroup found four issues, and I identified one additional issue because I did. In fact, in the prompt, give our agent the opportunity to add something in extra. Let's take a look through what it came up with and see if it matches what you came up with. So the first one, which was indeed the the horrible one, is that there was a SQL injection vulnerability, which is a classic. I imagine you spotted that there was a something which was executing a SQL cursor which just shoved in there the values, and it means that someone could say their city. They could they could then put the city London and then close quotes and then put all sorts of dangerous stuff in there. If the the LM would be would be fooled into that then you could cause you could wreak havoc. So that was a problem for sure. Uh, there was, I think, an even worse one, perhaps. Uh, it seems like maybe. Maybe not. Uh, there is, uh, yeah. Okay. Uh, more, more more issues here. No, this is the worst one. Good. It did spot the really critical one. Critical 9.8, uh, out of ten is the criticality score. The the Cvss score associated with this one, which is that there was, in fact, something that that evaluated an expression which could allow arbitrary code to be evaluated. Hopefully, when you were reading through that Python file and you saw that you were like, ah ha. So, uh, certainly, Sam grep spotted that with ease. And then there's some of these, these, uh, lower ones, some interesting stuff. It's seen a potential denial of service because of the way that we, uh, just, just, uh, have an unrestricted launch of gradio rounds up the issues. You may have a different set of issues because the ones the LM adds might be different and you could try it with some different models, but but that's not really the point. The idea is to show you when we're running this locally, we just run a web server with a front end. We run our Python backend server, the front end talks to the backend, and that's spawning an MCP server, a separate process running on my computer. That's easy. That is how local deployments work. Now we want to package this up. And so now close those two servers the front end and back end by doing control C in each of those terminals. They both stop when you stop the back end server. Take a look through. You'll see a trace of the Semgroup server running and what it was doing on your computer to prove that it was actually running. But we're going to swiftly move on and look at Docker. So if I start by showing you that in the top directory here we have a Docker file. Let me open that. Here it is. So the Docker file actually will look quite similar to the docker file that we worked on in week one with the healthcare app. It actually it creates two images. The first of them is a node image, which is just going to be used to build the front end package. By this point, you might understand this more closely than you did in week one, perhaps. Uh, so it does an npm run build on our front end. Uh, and uh, this is used to build the output. And then we create a python uh, container and we use that Python container, we install UV, we, we get everything ready and then we do the, the the, we do this important line here which is where we copy in to this Python Docker container. We copy in the built front end app that was created by this first container, the front end container. And this is the one that we then put in a health check. We expose port 8000 and we run Uvicorn to start the server running. That's how it all comes together. That is our Dockerfile. And so with that we can now make this docker file by just running. Get a new terminal window up. Here it comes. Do docker minus minus version to make sure that you have docker installed. Do docker PS to make sure that docker is running that prints any any, any running Docker containers. So you can um, if that fails for some reason, then you should go to Docker Desktop and launch it from your applications folder. And then we're going to build our Docker container by running this. So this is building the image I use. People often do get the wrong words with image and container. It's important to be clear on what you're doing building the image. We've done it. Uh, and mine was very quick because I'd already done it before. Yours will probably take a few minutes. 2 to 5 minutes. It says, uh, and it downloads the base images that they're built from. It installs the dependencies, it builds the front end, and it packages it together. You can see it caching everything, but doing it there very quickly. Uh, and we then need to run the container. So this is taking it from being an image into actually creating and running the container. So this is the line what this is doing is uh this the mm. There means that once it's finished running, once we stop it it will delete it. So it doesn't stay hanging around. It's going to bring it up. It's going to be using our EMV file. It's going to be using the cyber analyzer image. Let's run this. And that is bringing up a Docker container. Right now it's it's started and it's running on this URL right here. So I'm sure you know this. But just to be very clear. So this is a Docker container running on our local box. We've done no deployments yet. We're making sure that the project works locally first. And it's running. It's on our local box. It's on port 8000. We can bring this up and here it comes. Look. It looks rather different. Sorry. It looks rather different. It looks the same. Exactly the same as when we separately just ran the front end and back end server directly at our computer. We're now running them within a Docker container. Or if you're if you're on the ball, we're not really running a front end anymore. We compiled the front end to a straight up static website, and we've got one backend fast API server that served up this static website, and it looks very familiar to us. So once more we will open up airline, we will analyze code. And now in our Docker container we're expecting it's running the same thing just in this box within the box rather than on our computer directly, so to speak. Uh, and with any luck, this is going to be processing. It's going to be going to GPT 4.1 mini. And in just a second I will be back with the results. And here we are. Here are the results. It was literally just a second after I stopped recording. Uh, here they are. And uh, you can see this time it says at the top SendGrid found four issues. Again, you'd imagine it would be the same. And I identified two additional issues. If I remember right last time, it identified one issue. So, uh, this this was when, uh, there's it's just because it's it's, uh, could be a bit different each time you run it. Uh, but, uh, this time it identified two. And so there'll be one more, presumably low priority issue. See if I could spot which one. It didn't. Oh, I think this is the detail. Yes. The detailed error message, the fact. And I intentionally did put in this low priority thing to see if it would care. I think this is the one that it only identified. It only decided to raise this time because it's a trivial kind of problem that almost always isn't actually a problem. But but it mentioned it. So, uh, these are the ones that the agent added over and above the issues that Semgroup found. Anyways, the point was not to show you the cybersecurity analyst, although that is quite a fun commercial project. The point was to show you it packaged in a Docker container running on my local box, but within the Docker container. And if all you were going to do was run it on your local box, then there wouldn't be much of a benefit over having the front end and back end running separately. Of course, the benefit is that once you've packaged it into a Docker container, it is then super easy to ship it off to a cloud platform. And that's what we're going to do with Azure next.

</details>
