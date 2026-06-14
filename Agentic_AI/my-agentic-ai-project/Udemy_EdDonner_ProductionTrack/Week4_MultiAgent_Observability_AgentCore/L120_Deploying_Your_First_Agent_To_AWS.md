# L120 — Building and Deploying Your First AI Agent to AWS in Minutes

> **Week 4 · Day 5** · ⏱️ ~10 min

---

## 🎯 TL;DR

Hum `first.py` mein ek ~10-line Strands agent likhte hain, locally `uv run` + `curl` se test karte hain, phir `agentcore configure` + `agentcore launch` ke do commands se usse poori container-based AWS deployment par bhej dete hain — minutes mein. Phir ek `@tool` (square root) add karke re-deploy karke dikhate hain ki tools add karna kitna trivial hai.

---

## 🗣️ Hinglish Explanation

### Clock starts now — ab actual coding

Ed clarify karta hai: ab tak sab **one-time setup** tha. Ab "the clock starts" — yeh asli kaam hai, aur dekho yeh kitna chhota hai.

### Step 1: `first.py` — pehla agent

`finale/` mein **New File** → `first.py`. README se code paste karo:

```python
from bedrock_agentcore import BedrockAgentCoreApp
from strands import Agent

app = BedrockAgentCoreApp()
agent = Agent()

@app.entrypoint
def invoke(payload):
    user_message = payload.get("prompt")
    result = agent(user_message)
    return result
```

> ⚠️ **Save karo!** White blob tab par dikhna band hona chahiye (`Cmd+S`/`Ctrl+S`). Ed har baar yaad dilata hai.

Code breakdown:

- `from bedrock_agentcore import BedrockAgentCoreApp` — platform ka Python client. (Couple imports jo abhi use nahi ho rahe — ignore karo, baad mein aayenge.)
- `from strands import Agent` — Strands se sirf `Agent` import.
- `app = BedrockAgentCoreApp()` — Agent Core app instance. Yeh tumhare code ke around ek **server wrapper** banata hai jab deploy hota hai.
- `agent = Agent()` — ek naya Strands agent. **Zero config** — default model (Claude on Bedrock) khud pick ho jaata hai.
- `@app.entrypoint` — decorator jo bolta hai *"yeh hai entry point — jab koi message deployment par aaye, yahaan aana chahiye."*
- `def invoke(payload)` — single function. `payload` ek dict hai. Usme `prompt` field dhundho (`payload.get("prompt")`), uski value ko `user_message` banao.
- `result = agent(user_message)` — **Strands ki khoobsurti**: agent ko bas call karo message ke saath. Isse simple kya ho sakta hai? Yeh LLM ko call karta hai aur reply leke aata hai.
- `return result` — wahi result wapas bhej do.

> 🧠 **Strands vs OpenAI Agents SDK**: Strands itna minimal hai ki `Agent()` ka koi mandatory config nahi — model, tools, system prompt sab optional. `agent(message)` ek **callable** hai jo seedha LLM call kar deta hai. OpenAI Agents SDK mein `Runner.run(agent, input)` likhna padta hai; yahaan agent khud callable hai.

### Step 2: Locally test karo

Pehle deploy nahi — **locally** dekho ki scaffolding kaam karti hai:

```bash
# finale/ folder mein
uv run first.py
```

Bahut kuch dikhega nahi — yeh **bas baith jaayega**, kyunki `BedrockAgentCoreApp` ne ek **local server start** kar diya hai (jaise FastAPI/uvicorn) jo `localhost:8080` par sun raha hai. Server running rehne do, **naya terminal** kholo:

```bash
curl -X POST http://localhost:8080/invocations \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Hello? Can you hear me?"}'
```

- `curl` = HTTP request banane ka utility.
- `POST` `localhost:8080/invocations` par — yeh wahi route hai jise `@app.entrypoint` handle karta hai.
- Body ek JSON dict: `{"prompt": "..."}` — wahi `prompt` field jise hamara `invoke()` dhundhta hai.

Response aata hai:

> *"Hello! Yes I can hear you in the sense that I can read and understand your text message. I'm Claude, an AI assistant. How can I help you today?"*

Bas! Local pe chal gaya. `Ctrl+C` se server band karo. **Par yeh sirf local hai** — asli kaam AWS par deploy karna hai (jo normally weeks/days lagta hai... ya yahaan minutes).

### Step 3: `agentcore configure` — deployment prepare

```bash
# finale/ mein, confirm karo
uv run agentcore configure -e first.py
```

`-e` = entry point file. Yeh kuch questions poochhega — **sab defaults accept karo** (Enter dabate jao):

- ECR repository → default (container yahaan push hoga)
- `pyproject.toml` → default (UV project detect kar liya, deps yahin se)
- IAM stuff → default

Configure ke baad **3 nayi files** ban jaati hain (Ed ne inhe ignore kiya, tumhe khud banengi):

```text
finale/
 ├── Dockerfile                 # container kaise build hoga
 ├── .dockerignore              # build se kya exclude karna
 └── .bedrock_agentcore.yaml    # Agent Core deployment config
```

> 🧠 **ECR recap**: Elastic Container Registry = AWS ka Docker image storage (Docker Hub jaisa, par private + AWS-integrated). `agentcore launch` image build karke yahaan push karta hai, phir wahaan se runtime usse pull karta hai.

### Step 4: `agentcore launch` — DEPLOY 🚀

Configure ke baad CLI bolega "ab `agentcore launch` karo" — par kyunki yeh UV project hai, `uv run` prefix zaroori hai:

```bash
uv run agentcore launch
```

Pichhe-pichhe bahut kuch hota hai — terminal mein dekho:

1. **ECR repository created** — image ka ghar.
2. **Queuing → Provisioning → Build (CodeBuild)** — container build hota hai.
3. **Build complete → Launching Bedrock Agent Core** — runtime spin up.
4. **Done** — deployed!

Yeh sab **minutes** mein. Ed astonished hai: *"AWS ne kuch streamlined aur simple banane ki thaani thi, aur unhone crush kar diya."*

### Step 5: Cloud par invoke karo

```bash
uv run agentcore invoke '{"prompt": "Hello? Can you hear me?"}'
```

Ab yeh message **local nahi**, balki **AWS cloud** mein chal rahe container (App Runner-jaisi runtime) ko jaata hai. Wahaan agent message receive karta hai, **Bedrock par Claude call** karta hai, aur same reply wapas aata hai. Ek **full containerized AWS deployment** — sirf minutes mein. *"A week's worth of work in like a minute."*

> 🧠 **Behind the scenes**: container build → ECR push → IAM setup → App Runner-jaisi runtime par deploy → message routing. Yeh sab `launch` ne automatically kar diya.

### Step 6: Ek tool add karo

Strands mein tool add karna trivial hai — OpenAI Agents SDK jaisa, par aur kam. `first.py` mein **imports ke just neeche** (file ke ekdum top par nahi):

```python
import math
from strands import tool

@tool
def take_square_root(number: float) -> float:
    """Calculate the square root of the given number."""
    return math.sqrt(number)
```

- `@tool` decorator (Strands se import) function ko ek **agent tool** bana deta hai.
- **Docstring/comment** = tool ka description, jo LLM ko batata hai ki yeh tool kab use karna hai.
- **Type hints** (`number: float -> float`) se Strands tool ka schema banata hai.

Phir agent line ko update karo taaki usse tool mile:

```python
# pehle:  agent = Agent()
agent = Agent(tools=[take_square_root])
```

Save karo. Bas — *"creating an agent, but saying you have these tools."*

### Step 7: Re-deploy aur tool test

Configure dobara karne ki zaroorat nahi (entry point same hai), bas:

```bash
uv run agentcore launch
uv run agentcore invoke '{"prompt": "Use your tool to calculate the square root of 1234567 to 3 decimal places"}'
```

- Fresh deployment hota hai (build → launch).
- Invoke par agent **tool call** karta hai (yeh kaam wo bina tool ke nahi kar pata).
- Answer: **√1234567 ≈ 1111.111** — Ed calculator se verify karta hai, sahi nikalta hai.

Yeh dikhata hai: tool add karna + re-deploy karna seconds ka kaam hai, aur sab kuch cloud par chal raha hai.

---

## 📋 Key Concepts

| Concept | Matlab |
|---|---|
| **`BedrockAgentCoreApp`** | Python client; deploy par tumhare code ke around server wrapper banata hai |
| **`@app.entrypoint`** | Decorator jo `invoke(payload)` ko deployment ka entry point banata hai |
| **Strands `Agent()`** | Zero-config agent; `agent(message)` callable seedha LLM call karta hai |
| **`uv run first.py`** | Local server `localhost:8080/invocations` par chalata hai testing ke liye |
| **`curl POST /invocations`** | Local agent ko `{"prompt": ...}` JSON bhej ke test karna |
| **`agentcore configure -e`** | Deployment prepare; Dockerfile + .dockerignore + .bedrock_agentcore.yaml banata hai |
| **`agentcore launch`** | Container build → ECR push → runtime deploy, sab automatic, minutes mein |
| **`agentcore invoke`** | Cloud-deployed agent ko message bhejna |
| **`@tool`** | Strands decorator jo function ko agent tool banata hai (docstring=description, type hints=schema) |
| **ECR** | AWS ka private Docker image registry jahaan agent image push hoti hai |

---

## 💼 Backend Dev Ke Liye Note

Backend dev ke liye yeh ek **complete CI/CD-in-a-command** experience hai. `agentcore configure` ko `docker init` + IaC scaffolding samjho (yeh Dockerfile + deployment YAML generate karta hai), aur `agentcore launch` ko `docker build && push && deploy` pipeline samjho — par ek line mein. Local-test flow bilkul standard hai: `BedrockAgentCoreApp` ek ASGI-jaisa server expose karta hai, tum `curl` se `POST /invocations` hit karte ho — yeh wahi pattern hai jo tum FastAPI app ko `curl` karne mein use karte ho. `payload.get("prompt")` ek classic request-handler hai. Tools waala part — `@tool` + type hints + docstring — function calling/JSON-schema generation ka syntactic sugar hai (Pydantic-style introspection). Production lens se: yeh fast iteration deta hai (code change → re-launch → invoke), par har `launch` ek full image rebuild hai, toh real systems mein tum layer caching aur build times ka dhyaan rakhoge.

---

## ✅ Takeaway

- Ek complete agent ~10 lines: `BedrockAgentCoreApp` + Strands `Agent()` + `@app.entrypoint def invoke(payload)`
- Local test: `uv run first.py` (server on :8080) → naya terminal → `curl POST /invocations` with `{"prompt": ...}`
- Deploy 2 commands: `uv run agentcore configure -e first.py` (defaults) → `uv run agentcore launch` → cloud par `uv run agentcore invoke`
- `configure` 3 files banata hai (Dockerfile, .dockerignore, .bedrock_agentcore.yaml); `launch` ECR + CodeBuild + runtime sab handle karta hai
- Tool add karna trivial: `@tool` + type hints + docstring, phir `Agent(tools=[...])` — re-launch karke seconds mein cloud par tool live

---

<details>
<summary>📜 Full Transcript (English)</summary>

So just to be clear, everything that we've done up to this point has been a one time setup. This is now going to be coding agents. So the clock starts now in terms of the actual work we have to do. Let's do this. So first of all we are going to make a new file in this directory called first Pi. For our first ever agent on Agent Core. And we're going to put in this code right here. So I'm going to copy that code copy to the clipboard within finale new file. Call it first dot pi. There it is. Paste in the code. And now let's look at it. So there's a couple of imports that we don't use because we're going to use them. So so ignore look the other way for those. So we we import this bedrock agent core app from the Python client library. And from strands we just import agent okay. We create a new instance of the app and we create a new agent. All right. So far so good. Now we then have a decorator which is saying this is the entry point to for for our agent world, this is where things will begin. If a message is received by our deployment, it should come in here. And it's got a single simple, uh, function called invoke. It takes a payload. And what that's going to do, it's going to take that payload and look and see if that payload has a field called prompt in it, and if so, it will suck out whatever value we have for the word prompt. And we'll call that the user message. It then look how simple a strands is. You just call the agent with the message this is the agent. Call it with the message. What could be simpler than that. And we get back a result and we will return that result. This is it. This is the extent of it. Okay. It's time for us now to give this a try. First of all, locally before we deploy. All right. So we go back to preview, uh, and have a look at what we do next. We just do UV run first dot pi. That is really it. So let's here it is. Make sure you've saved it. Make sure the white blob has gone here. And now we're just in finale. We're just going to run UV run first dot pi. Let's see what happens. Very little happens. It sort of sits there. Okay. That's because a server is running. Go back here again. What are we going to do next? We're going to leave that server running and open a new terminal in cursor and send this message. So what does this do. It's curls. So that's the utility that makes an HTTP request. It's going to post locally to to localhost 8080 invocations. And it's going to post something like a Python dictionary with prompt or a JSON dictionary prompt is the key and the value is hello? Can you hear me? Uh so that's going to come in here. That's this thing is looking for something in the field prompt. So this seems good. So let's take this code. And so I said open a new terminal like this. Come in here and paste in that curl. Nice. What happens. Hello. Yes I can hear you in the sense that I can read and understand your text message. I'm Claude, an AI assistant. How can I help you today? Ha ha. Very nice. Okay, so that just worked. And before we get too excited, I'm just going to command C that it's not as if a whole lot happened. This is running locally on our computer. It shows us that the scaffolding is nice. We can run things locally. We haven't deployed anything. That's clearly a bigger deal. We've got to deploy everything to AWS. So we know that that takes that takes weeks. Uh, or at least days. Okay. Let's do that. Okay. Here we go. We're going to run UV run agent core configure minus E which is this is going to be the entry point first.py. All right. So from the finale directory be sure that you're in the finale directory. Make that run. So it's now going to ask us a few questions that we are going to do. The defaults to everything. Default for that. Default for the ECR repository. Remember that that's where the containers get deployed. Because this builds a container default for Pyproject.toml. It recognizes we have a UV project. And so it's using that for our dependencies and then default for whatever the IAM stuff it wants to build. And that just happened. So, uh, what you will also notice when you do this is that it will create a few files that I've just ignored, so they won't be already there for you. It created a Docker file, a Docker ignore, and a bedrock agent core YAML. They will all have been created and you can go and check them out if you wish to. Uh, but uh, it's now telling us that all we have to do is do Agent core launch. In fact, we have to do slightly more than that. We have to do. You've run Agent Core launch because I've done this as a UV project. So? So don't ignore what it's telling you. UV run agent core launch is the right way to do it. Uh, let's do this. Okay, here we go. You've run agent core launch. Lots of stuff happening. Launching. Things are happening. Provisioning. So take a look through when you do this. Uh, hopefully you're doing it with me. This. This is one project that you can do along with me because it's that that simple. Uh, it's created an ECR repository. So. So you can see that ECR repository. Remember the Elastic Container Registry, uh, where containers get built and deployed. So, so it, uh, has put it, um, in there. It's been, uh, queuing, provisioning, build complete launching. Bedrock agent core launching, launching, launching. And it's done. And it now tells us that we can we can we can, uh, it's been, uh, deployed. A container has been built and deployed, and we can run, uh, Agent Core invoke. And again, the trick is to do it with UV. So so what we do is this UV run agent core invoke uh with a prompt as before prompt. Hello? Can you hear me? And just in case you're in any doubt, hear what this is going to do is it's going to send this message to AWS running in the cloud where there are now container containers running. Uh, well, a container running, which is like App Runner, there's like an app runner running there containing our code. And let's see what happens if we just run this. Things are heating up and what comes back is again. Hello. Yes, I can hear you in the sense I can read and understand your message. I'm glad. How can I help you today? That's identical, I think. Uh, so I can't understate this. This is unbelievable. This just made a full deployment to AWS of a containerized app, and we called it. And we got back an answer and it called Models on Bedrock. And literally it's been a few minutes. It's been a few minutes. It really is that easy. I feel like AWS has set out to make something that was streamlined and simple, and they have crushed it. It really is phenomenal. Uh, so I you can tell I'm gushing away, but I'm really, really impressed with this. But it's time for us to to beef it up and give it some more functionality. So yeah, I put here okay. Goodness. Do you realize everything that happened? We built a container, deployed it to ECR, set up all the IAM stuff, deployed it to something like App Runner and sent it a message. And it's like a week's worth of work in like, a minute. Uh. It's crazy. All right. Enough. Enough with my, uh, overenthusiasm for this. Okay, we're going to add in a tool. Um, so this is really a feature of strands that it's that it's really, really nice and simple. It's like open AI agents SDK, but but even even more, uh, simplistic. So here's a tool we're going to add. Uh, we'll put it right up at the top of first dot pi. Uh, let me show you. Here's first dot pi. So right up at the top here before these two lines here. So just under the imports, not right at the top, just under the imports. Um, a tool we decorate it with at tool, which I imported already. It's called take square root. It takes a float. And the comment says calculate the square root of the given number and it returns math dot square root of that number. That's a pretty simple tool right? Okay. Back we come to the readme. Uh, so we now just want to change agent equals agent to this agent is agent tools equals take square root. Okay. And it couldn't be simpler. This line here We just replace it like that and save. That's it. So now we're creating an agent. But when we create the agent we're saying that you have these tools again it's like OpenAI agents SDK, only less. Um all right what's next? Are there lots of steps next? No there aren't. We just need to run this. You've run Agent Core launch, which is going to do a fresh deployment. Let's do that. Off it goes. See all the stuff that's happening? It says, uh, starting code, build, build. This may take several minutes. Uh, but it doesn't take several minutes. Maybe because it's still early days that, um, uh, AWS, um, agent core. Bedrock agent core, uh, is is still quite underutilized. Um, but everything is happening launching Bedrock Agent Core. So this time we're going to run Agent Core Invoke. And for the prompt we're going to say use your tool to calculate the square root of 123456, 7 to 3 three decimal places, and hopefully that's something that it wouldn't be able to do without having access to the tool. So that's the post we're going to make. Looks good to me. Let's give it a try. Let's see what happens. So this is being sent out to AWS where our container app is being spun up. Our agent is receiving that message. It's then going to call the tool. And apparently the square root of one two, three, four, five, six, 7 to 3 decimal places is 1111.111. Well, we'll see about that. See my old human approach? Well, not really human approach, is it? Uh, one. Two. Three. The old school way. Square root and equals. And it does appear to have got it right. Uh, and rounded it properly to. Yes, that does seem to be the right answer. We'll give it to Claude. Uh, and so this is, again, just a wonderful sign of being able to so easily add a tool and deploy that agent to the cloud. And it's all just working, and it's still only been a few minutes.

</details>
