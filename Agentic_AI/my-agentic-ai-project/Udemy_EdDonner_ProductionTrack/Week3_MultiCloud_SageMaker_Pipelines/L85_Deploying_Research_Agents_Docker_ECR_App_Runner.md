# L85 — Deploying AI Research Agents with Docker, ECR, and App Runner

> **Week 3 · Day 5** · ⏱️ ~10 min

---

## 🎯 TL;DR

`terraform init` ke baad chicken-and-egg problem solve karte hain — pehle `terraform apply -target` se sirf **ECR repo + IAM** banao, phir Researcher ka Docker image build karke ECR par push karo (`deploy.py`), tabhi App Runner service deploy ho sakti hai. Beech mein researcher code (`context.py`, `servers.py`, `server.py`, `Dockerfile`) ka tour.

---

## 🗣️ Hinglish Explanation

### `terraform init` — hamesha yahin se shuru

```bash
terraform init
```

Yeh Terraform project ko initialize karta hai — providers (AWS) download karta hai, backend setup karta hai. Pehli baar thoda time lega.

### Chicken-and-egg problem aur uska solution

Yahan ek classic deployment puzzle hai:

- Hum apne Researcher service ka **Docker image** banayenge aur use **ECR (Elastic Container Registry)** par deploy karenge. (ECR yaad hai Week 1 se — AWS ka private Docker image registry, Docker Hub ka AWS version.)
- **Lekin** image push karne ke liye pehle ECR **repository** hona chahiye.
- Aur **App Runner service** ko deploy karne ke liye pehle image ECR mein hona chahiye.

Toh problem: pura Terraform ek saath nahi chala sakte (kyunki abhi container nahi hai), aur container nahi bana sakte (kyunki ECR setup nahi hai). **Chicken aur egg.**

**Solution (sabse simple):** `terraform apply` ko sirf **kuch hisson** par restrict karo — `-target` flag se. Pehle sirf **ECR repository + zaroori IAM permissions** banao:

```bash
terraform apply -target=aws_ecr_repository.researcher -target=aws_iam_role.researcher
# (actual target names module ke hisaab se — ECR repo + IAM roles)
```

Plan dikhega → `yes` → bas ECR aur IAM ban jaate hain.

> Terraform ek **warning** dega: *"Applied changes may be incomplete. The plan was created with a -target option... not suitable for routine use."* Yeh expected hai — humne jaan-boojh kar partial infra banayi hai. "Method to our madness."

### Terraform code ka quick tour

Terraform file mein (top se bottom) yeh blocks hain:
1. **Providers** — usual AWS provider config
2. **ECR repository** — yeh abhi banaya
3. **IAM stuff** (pehla set) — abhi banaya
4. **More IAM** — permissions
5. **App Runner service** ("researcher") — **baad mein** banega, ECR par image push hone ke baad
6. **More IAM** — App Runner ke liye
7. **Scheduling part** — EventBridge scheduler (lecture 87 mein enable hoga)
8. Aur IAM + scheduling ka thoda aur

### Researcher code tour — `backend/researcher/`

`backend/researcher/` directory mein kaafi kuch hai: `Dockerfile`, MCP servers, context, aur `server.py`, plus deploy + test scripts. Ed ka standard pattern — modules mein separate karna:

#### `context.py` — prompts aur instructions

Yeh module saari **text templates** alag rakhta hai. Iska main function: `get_agent_instructions()` — yeh agent ka **system prompt** return karta hai. Agent ko 3-step role brief milta hai:

1. **Web research karo** — kisi source par navigate karo, `browser_snapshot` se content padho
2. **Brief analysis** karo
3. **Database mein save** karo — `ingest_financial_document` tool use karke

Important: current **date** pass kiya jaata hai taaki agent ko exactly pata ho aaj kya date hai (warna LLM apni training-cutoff date use kar sakta hai). System message + instructions + user prompt sab yahin define hote hain.

```python
# context.py (reconstructed)
from datetime import date

def get_agent_instructions() -> str:
    return f"""You are a financial research agent.
Today's date is {date.today().isoformat()}.

Your job, in three steps:
1. Research the web: navigate to a source and use browser_snapshot to read content.
2. Do a brief analysis — be quick and concise.
3. Save it to the database using the tool ingest_financial_document.

Be fast, be brief. Do not wander."""

def get_research_prompt(topic: str) -> str:
    return f"Research this topic and store your findings: {topic}"
```

#### `servers.py` — Playwright MCP server

Yeh module ek single, critical **MCP server** define karta hai: **Playwright**. Yeh agent ko **headless browser** (container ke andar Chrome) se internet surf karne ke tools deta hai.

Key arguments:
- Latest Playwright MCP server
- `--headless` — koi visible browser window nahi (server par GUI nahi hota)
- Custom **user-agent** — taaki websites bot block na karein, proper surfing ho sake
- Path handling — taaki AWS par deploy ho ya locally, dono jagah kaam kare (Ed bolta hai yeh "agonizing few days" ka result tha — paths/setup ka futzing brutal hota hai jab tak solve na ho)

```python
# servers.py (reconstructed)
from agents.mcp import MCPServerStdio

def get_playwright_server() -> MCPServerStdio:
    return MCPServerStdio(
        params={
            "command": "npx",
            "args": [
                "@playwright/mcp@latest",
                "--headless",
                "--user-agent=Mozilla/5.0 ...",
            ],
        },
    )
```

#### `server.py` — actual agent + FastAPI service

Yeh dono modules ka use karke **agent** banata hai aur ek **FastAPI service** expose karta hai. Main method: `run_research_agent(topic)`.

- Yahin **Bedrock region** set hota hai — OSS ke liye `us-west-2` rakho.
- **Model selection** — Ed Amazon **Nova** use kar raha hai (reliable), par dusra option OSS 120B hai. OSS try karne ke liye us line ko uncomment karo aur region `us-west-2` karo.
- **Tracing** enabled — OpenAI ki built-in observability.
- **MCP server** create + agent ko pass.
- Agent ko **context** (system prompt) + **selected model** + **`ingest_financial_document` tool** (jo hamare ingest Lambda ko call karta hai) + **Playwright MCP** milte hain.
- Phir `Runner.run(...)` se agent loop chalta hai.
- Ek **health check** route aur scheduler-related routes bhi hain.

```python
# server.py (reconstructed sketch)
from fastapi import FastAPI
from agents import Agent, Runner, function_tool
from context import get_agent_instructions, get_research_prompt
from servers import get_playwright_server

app = FastAPI()

# Bedrock region for the model call
BEDROCK_REGION = "us-east-1"   # OSS ke liye: "us-west-2"

# Model choice — Nova reliable; OSS exciting but tool-calling bug risk
MODEL = "litellm/bedrock/us.amazon.nova-pro-v1:0"
# MODEL = "litellm/bedrock/openai.gpt-oss-120b-1:0"   # uncomment + region us-west-2

@function_tool
def ingest_financial_document(text: str) -> str:
    """Call the ingest Lambda via API Gateway to vectorize + store in S3 vectors."""
    ...

@app.post("/research")
async def run_research_agent(topic: str):
    async with get_playwright_server() as mcp:
        agent = Agent(
            name="Researcher",
            instructions=get_agent_instructions(),
            model=MODEL,
            tools=[ingest_financial_document],
            mcp_servers=[mcp],
        )
        result = await Runner.run(agent, get_research_prompt(topic))
        return {"result": result.final_output}

@app.get("/health")
def health():
    return {"status": "ok"}
```

Ed encourage karta hai: prompts experiment karo, instructions change karo, MCP servers add/change karo.

### Deployment ke do tools

#### 1. `Dockerfile` — image ki recipe

Yeh Docker image banata hai. Steps:
1. **Node** install (Playwright ke liye)
2. **Playwright + Chromium** install (headless browsing)
3. **UV** install (Python package manager)
4. Finally **Uvicorn** launch karke `server.py` ko **port 8000** par run karo

Sahi **platform** use karta hai (AMD64 vs ARM mismatch se bachne ke liye).

```dockerfile
# Dockerfile (reconstructed)
FROM --platform=linux/amd64 python:3.12-slim

# Node for Playwright
RUN apt-get update && apt-get install -y nodejs npm

# Playwright + Chromium
RUN npx -y playwright@latest install --with-deps chromium

# UV — fast Python package manager
RUN pip install uv
COPY . /app
WORKDIR /app
RUN uv sync

EXPOSE 8000
CMD ["uv", "run", "uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]
```

#### 2. `deploy.py` — build + push script

Week 2 mein shell + PowerShell scripts the; Week 1 mein Python module. Yeh phir se Python hai. Kaam:
1. `terraform/4` folder se **ECR repo URL** padhna (jo abhi-abhi partial apply se bani)
2. ECR par **login**
3. `docker build --platform ...` se image banana
4. Image ko **ECR par push** karna

```python
# deploy.py (reconstructed sketch)
import subprocess, json

# 1. Terraform output se ECR URL nikaalo
ecr_url = json.loads(
    subprocess.check_output(["terraform", "output", "-json"], cwd="../../terraform/4")
)["ecr_repository_url"]["value"]

# 2. ECR login
subprocess.run("aws ecr get-login-password | docker login --username AWS "
               f"--password-stdin {ecr_url}", shell=True, check=True)

# 3. Build
subprocess.run(["docker", "build", "--platform", "linux/amd64",
                "-t", ecr_url, "."], check=True)

# 4. Push
subprocess.run(["docker", "push", ecr_url], check=True)
```

Agle lecture mein yeh script chala kar push dekhenge, phir full `terraform apply`.

---

## 📋 Key Concepts

| Concept | Matlab |
|---|---|
| **`terraform init`** | Providers download + backend setup; project ki shuruaat |
| **Chicken-and-egg** | ECR chahiye image ke liye, image chahiye App Runner ke liye — circular dependency |
| **`-target` apply** | Sirf chunni hui resources banao (ECR + IAM); incomplete-plan warning expected |
| **ECR** | AWS ka private Docker image registry |
| **`context.py`** | System prompt + instructions + date + research prompt |
| **`servers.py`** | Playwright MCP server (headless Chrome, custom user-agent) |
| **`server.py`** | FastAPI service + agent (Bedrock region/model, tracing, tool, MCP) |
| **`Dockerfile`** | Node + Playwright/Chromium + UV + Uvicorn on port 8000 |
| **`deploy.py`** | ECR URL padho → login → `docker build` → push |
| **Nova vs OSS** | Nova reliable; OSS exciting par tool-calling bug — code switchable |

---

## 💼 Backend Dev Ke Liye Note

Chicken-and-egg problem har infra-as-code engineer ko milti hai — ECR/registry ko app deploy se pehle **bootstrap** karna padta hai. Production mein iske teen common patterns: (a) `-target` se partial apply (jaise yahan, quick par "not for routine use"), (b) ECR ko ek **separate "bootstrap" Terraform stack** mein nikaalna jo pehle chalta hai, ya (c) CI pipeline mein build-and-push step ko apply se pehle ordering karna. Code organization bilkul standard backend hygiene hai: `context.py` (prompts/config), `servers.py` (external integrations), `server.py` (web layer + business logic) — yeh **separation of concerns** hai, bilkul jaise tum FastAPI app mein `routers/`, `services/`, `repositories/` alag rakhte ho. `Dockerfile` mein `--platform=linux/amd64` woh detail hai jo Apple Silicon (ARM) par build karke x86 cloud par deploy karte waqt "exec format error" se bachata hai — ek classic gotcha. Aur Playwright/Chromium ko container mein bundle karna matlab tumhara agent **self-contained browser automation** carry karta hai — heavy image, par portable.

---

## ✅ Takeaway

- `terraform init` → fir **chicken-and-egg**: pehle `terraform apply -target` se sirf **ECR + IAM** banao (incomplete-plan warning expected)
- Researcher code = `context.py` (prompts/date), `servers.py` (Playwright MCP, headless), `server.py` (FastAPI agent: Bedrock region+model, tracing, ingest tool, MCP)
- **Nova** reliable fallback; **OSS 120B** uncomment + `us-west-2` se try karo
- `Dockerfile` = Node + Playwright/Chromium + UV + Uvicorn:8000, `--platform=linux/amd64`
- `deploy.py` = ECR URL padho → login → `docker build` → push; phir full `terraform apply`

---

<details>
<summary>📜 Full Transcript (English)</summary>

Okay. It's our moment. Terraform init. Remember, that's how it always starts. Terraform init. And it's done. It will take a little bit longer for you. The first time to set up the project. Okay. So this is a bit confusing. We're going to do something different now and Terraform is going to complain about it. We have to do things in a certain order. We're going to be building a Docker image of our app runner service of our researcher. And we're going to want to deploy that to ECR to the Elastic Container Registry. If you remember that it's like swapped out somewhere in your mind from week one. If you remember ECR, we're going to be doing that again. Uh, but before we can do that we need to have created the repository. And this is a bit of a chicken and egg situation. We can't run our Terraform code to create everything because we don't yet have a container, and we can't yet create the container because we haven't set up ECR. So there's various solutions for this, but this is the simplest one we can ask. We can do a terraform apply, but only for two pieces of our building block in Terraform, just for the ECR, the repository and the permissions. So if I just go now to the Terraform code itself so that this will be a little bit more meaningful if I take you through this quickly, this Terraform code, it contains the usual providers. Then it's got something to set up the ECR repository. That's what we need. We're going to run that right now. Uh, but ahead of time we're going to run the IAM stuff that we need. Uh, and then uh, more IAM stuff, uh, all this fun IAM stuff. And then this is the actual app runner service called researcher. And we're going to do that later only after we've actually deployed our container to ECR. Uh, and then some more IAM stuff. And this is now the scheduling part that we'll come to later. So some scheduling stuff, some more stuff, IAM stuff for that and a little bit more scheduling stuff and that is it. So with all of that background, I think you now know what's going on. We're going to begin with this Terraform apply, which is only going to deploy as it says, the ECR repository and IAM roles. Let's run this and see what happens. It's going to do the planning and ask me to say yes. I'll say yes. And it's now going to go and create all this stuff and it's done. Success. We have created our ECR and you can see if you look here that it's it's giving a warning. Applied changes may be incomplete. This plan was created with a minus target option. Uh this is suitable not suitable for routine use. It's very cross with us. But we did have a rationale. There was a method to our madness. Uh, we did it because we only wanted to partially create the infrastructure. So that now we can build and deploy the researcher. Okay, so before we do this, let's go and look at the code. It is in backend and it's in researcher. And it's right coming up right here in this directory, and there's a fair bit going on. There is, of course a Dockerfile to build a Docker container. There's MCP servers, there's context and then there's server Pi. And then there's also a deploy script. And there's a couple of test scripts too. I will just give you a quick tour of them now. So you're probably familiar now with the way that I like to do these things that I've got a context Pi and an MCP Pi, the two modules where I separate out the context that will be telling our agent and the MCP servers. Let's just quickly look at each of these just to get a sense for it. But I'll let you review this in your own time as well. This context Pi is where I separated out the templates, the text that we'll be using. And this has get agent instructions. It's going to respond with the uh with what we would want to brief our agent with basically the system prompt, uh, and it informs it what its role it gives it the critical instructions. Three steps. Do some research on the web, uh, navigating to a source and using browser snapshot to read the content. Number two brief analysis and number three saving it to the database using the tool. Ingest financial document. And I make sure to pass in the date so that it absolutely knows what the current date is. And it sticks to that date. And then, uh, yeah, there's lots of stuff here about being quick and brief. Uh, and uh, there is, uh, the research prompt that is passed in. So this is where we're putting the system message, the instructions and the user prompt in context, dot pi and then servers dot Pi is where we define the single MCP server that we're going to be using. And it's a pretty critical one. It is playwright for people familiar with this. And this is going to be, uh, these are the arguments that we'll use, which is making sure that we're using the latest MCP playwright server headless. So it's not trying to bring up a browser. Uh, and we're using a user agent to make it most likely to be able to surf the web properly. Uh, and, uh, yeah, we've got a little bit of stuff here to make sure that it can work, either when it's deployed on AWS or when it's deployed here. And as you can imagine, this kind of futzing around with these sorts of paths and things was was the result of some agonizing few days, which, uh, is the kind of thing that you have probably had to struggle with for some strange, crazy reason of your own for your setup. Uh, and these kinds of things can be brutal until you finally solve them. But but this is one I finally solved. But this this, uh, module MCP servers is the one that responds with this MCP server for allowing our agent to be able to browse the web headless using a Chrome on, on its box, on in its container. Uh, and do some research according to our instructions, as laid out in context. And so with this, that brings us to server.py, which is where we actually create the agent that's going to take advantage of these two modules. And of course, I should say an important part of this is for you to come in and experiment and try changing some of these prompts. Change the instructions. You could also try changing the MCP servers or adding more. So going into Server.py this is the the actual um, the agent itself is going to create a fast API service. Uh, and we are going to have this method here run research agent taking in a topic. And basically this this is where you go to change the region that will be used for your bedrock call. So change this here to be US West two or whatever region you want to pick for your bedrock call, uh, make this be what you want. Uh, and then this is where I am choosing Amazon's Nova model, but that here is the other option. So should it be ready? Should you be willing to experiment with the OSS? 120 uh, then you should uncomment this line and use that model instead and change this to us West two. And that will give you the ability to try out the, uh, the new OpenAI model, which would be very exciting. But it may have this problem with tool calling that I've experienced. Uh, but if it doesn't, then congratulations. And then you can, uh, call uh, we then go ahead and call the agent. So we're using traces. As I mentioned, this is how we're going to take advantage of OpenAI's built in observability framework to trace what's going on. We're going to create our MCP server. We're going to call the agent. We're going to pass in the context the system prompt that I showed you a minute ago. We're going to pick the model that we just selected here. We're going to have a tool to ingest a financial document that is going to basically call our lambda function and we're passing in our MCP server. The playwright MCP. And then we're going to call run a run and have it off. There's going to be a health check. Uh, and uh, that's this is some, some other stuff that might be called by the scheduler. We will see. And this is just test, test stuff that's remaining. Uh, that's it. That is the code. So that is our server dot pi. And now I'm going to talk to you about how we will get to deploy this. And now we have two things to show you that actually manage the deployment. One of them is our Dockerfile. This is the thing you remember that creates the Docker image. It's the recipe for creating the Docker image. And basically it installs node and then it installs playwright and chromium. It installs UV. And then finally it launches Uvicorn and runs our app server. Uh, the, the server Pi that we just looked at on port 8000. So that is our Docker file. And it makes sure to use the right kind of platform. And now let me show you deploy.py. This is a pretty long script. You remember in in week two we actually had a shell script and a PowerShell script to do our deploy. But all the way back in week one, I think we had a Python module to do it, and this is pretty similar. But the first thing it has to do is figure out what did we just create. So it's got some stuff here that connects, that looks in our for researcher folder in Terraform and gets the URL of our ECR repository. And then we log in and then you can see all this other stuff. We then build the Docker image by by calling Docker build minus minus platform. Uh and then we will go and push that image to ECR. And you can look through this, but you'll also see it running in just a second and you'll see exactly what it has to do. Let's go and do that now.

</details>
