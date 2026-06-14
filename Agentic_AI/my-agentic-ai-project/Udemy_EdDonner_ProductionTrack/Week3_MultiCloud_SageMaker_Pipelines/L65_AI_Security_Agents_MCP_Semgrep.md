# L65 — Building AI Security Agents with MCP Servers and Semgrep Integration

> **Week 3 · Day 1** · ⏱️ ~10 min

---

## 🎯 TL;DR

Cyber project ka structure tour + foundation setup: **Semgrep** account banao, uska **App Token** + OpenAI key `.env` mein daalo. Phir back end deep-dive — FastAPI server jo **OpenAI Agents SDK** ka "Security Researcher" agent banata hai, ek **MCP server (Semgrep)** spawn karta hai jisme sirf `semgrep_scan` tool exposed hai (static tool filter), aur **structured output** (SecurityReport) deta hai.

---

## 🗣️ Hinglish Explanation

### Cyber repo ka structure

`cyber` repo simple hai — chaar top-level cheezein:
- **`backend/`** — FastAPI server (UV project)
- **`frontend/`** — Next.js app
- **`terraform/`** — IaC for deployment
- **`week3/`** — documentation/guides (Day 1 aur Day 2 ke parts). Yeh `cyber` project sirf **Day 1 & 2** ke liye hai.

Guides ka breakdown:
- **Day 1** → teen parts (Day 1 thoda lamba hai). Part 0 = "getting started" (basics/setup), Part 1 = Azure, etc.
- **Day 2** → do parts (faster).

Aaj **Part 0** se shuru — Azure aur GCP dono ke liye common foundation.

### Project kya karta hai

Ek **AI-powered web app** jo **Python code ki security vulnerabilities** analyze karta hai. Section 1 ("setting up the project") wahi steps hain jo pichhle lecture mein kar diye (repo clone, four directories inspect) — toh seedha **Section 2** par.

### Semgrep kya hai aur account setup

**Semgrep** ek bahut well-known **static code analysis (SAST)** tool hai jo code ko vulnerabilities ke liye scan karta hai — SQL injection, hardcoded secrets, unsafe `eval`, etc. patterns ko pakadta hai bina code chalaye. Semgrep ka ek **API hai aur free** hai, isliye hum ise use karenge (MCP server ke through).

Account setup (yeh kaam zindagi mein million baar karna padta hai — API/account banane ki muscle memory):

1. **semgrep.dev** kholo → "Meet your new AI AppSec engineer" → **Accept all cookies** → **Try it for free**.
2. **Sign up with GitHub** recommended (slick + simple — GitHub account toh hai hi).
3. Login ke baad → **Settings** → **Tokens** → **Create new token**.
4. Token banate waqt **dono scopes check karo**: pehla (default checked) **plus Web API** wala bhi check karo. (Sirf default chhod doge toh API call fail karegi.)
5. Token ko note kar lo — abhi `.env` mein daalna hai.

⚠️ Ed warning deta hai: jo token video mein dikhe usse kabhi use mat karna — internet par expose ho gaya. Apna fresh token banao.

### `.env` file banao

`backend` (ya root) mein right-click → **New File** → `.env`. Do keys daalo (spelling **bilkul exact** — ek letter galat nahi):

```bash
OPENAI_API_KEY=sk-...your-openai-key...
SEMGREP_APP_TOKEN=your-semgrep-api-token
```

Confirm karo `.env` **`.gitignore`** mein hai — Cursor mein file **dark gray** dikhegi, matlab git mein accidentally commit nahi hogi. Yeh standard secrets hygiene hai.

### `airline.py` — scan ka target (self-test)

Back end mein ek `airline.py` module hai — ek chhota airline chatbot assistant (Ed ke LLM Engineering course se). Yeh **intentionally vulnerable** code hai — yahi file hum AI ko analyze karne denge. Video pause karke khud dhoondho kaunsi cheezein "eyebrows raise" karayengi (hint: aage SQL injection aur `eval`-style arbitrary code execution nikalti hai).

### `uv run` se locally chalane ka prep

Naya terminal kholo, basics verify karo (obviously install hone hi chahiye is point tak):

```bash
node --version    # Ed: v24
npm --version
```

### Back end deep-dive — `server.py` (FastAPI)

Back end ek clean **UV project** hai, course ke saare principles follow karta hai. `server.py` = **FastAPI server** jisme:

1. **CORS middleware** — cross-origin requests allow karne ke liye (frontend alag origin se call karega).
2. **Pydantic classes** — request/response validation + structured output ke liye.
3. **OpenAI Agents SDK** use hota hai (is course mein nahi padhaya jaayega — docs beautifully written hain, ya Ed ke doosre courses dekho).

**Agent banana:**
- Naam: **"Security Researcher"**
- Kuch **instructions** (prompts) diye jaate hain
- Model: **GPT-4.1 mini**
- Ek **MCP server**: `semgrep_server`
- **`output_type`** = `SecurityReport` (structured outputs)

**SecurityReport structure** (Pydantic):
- `executive_summary` — overall summary
- `issues` — list of identified issues, har issue mein:
  - `title`
  - `description`
  - `code_fix` — suggested fix
  - `cvss_score` — 0 se 10 (CVSS = Common Vulnerability Scoring System, severity ka standard numeric measure)
  - `severity` — critical / high / medium / low

**`run_security_analyst` function:**
- OpenAI **traces** use karta hai (observability — agent ne kya kiya, OpenAI dashboard par dekh sakte ho).
- `async with` context manager se **MCP server start** karta hai.
- Agent create karke **`Runner.run(...)`** call karta hai.
- Output ko **`SecurityReport`** ke roop mein return karta hai.

```python
# Conceptual shape (server.py)
async def run_security_analyst(code: str) -> SecurityReport:
    with trace("security_analysis"):
        async with semgrep_mcp_server() as mcp_server:
            agent = Agent(
                name="Security Researcher",
                instructions=SECURITY_PROMPT,
                model="gpt-4.1-mini",
                mcp_servers=[mcp_server],
                output_type=SecurityReport,
            )
            result = await Runner.run(agent, code)
            return result.final_output
```

**FastAPI routes:**
- Ek route jo `run_security_analyst` ko call karke `SecurityReport` return karta hai.
- Ek **health check** route (good practice — load balancers/cloud isse "container alive hai?" check karte hain).
- Kuch **test code** (Ed bola check-in se pehle hata sakta hai).
- Aur — Week 1 jaisa — server **static website** bhi serve karta hai (Next.js front end compile hoke static banta hai, FastAPI use serve karta hai).

### Modular separation — `context.py` aur MCP module

Ed code ko cleanly split karta hai (Week 2 ka pattern):
- **`context.py`** — Security Researcher ke **prompts** aur prompts banane ki info.
- **MCP servers ek alag Python module** mein. Yahaan sirf ek MCP server hai:
  - Parameters: `SEMGREP_APP_TOKEN` `.env` se uthaata hai.
  - MCP server **2-minute timeout** ke saath create hota hai.
  - **Static tool filter** use hota hai — OpenAI Agents SDK ka recent feature jo control karta hai ki **kaunse tools agent ko milein**. Semgrep ke paas bahut saare tools aate hain, par hum sirf **ek** dete hain: **`semgrep_scan`**. Toh agent sirf scan kar sakta hai, aur kuch nahi.

```python
# Conceptual shape (MCP module)
semgrep_params = {
    "command": "...",  # semgrep MCP launcher
    "env": {"SEMGREP_APP_TOKEN": os.environ["SEMGREP_APP_TOKEN"]},
}

semgrep_server = MCPServerStdio(
    params=semgrep_params,
    client_session_timeout_seconds=120,   # 2-minute timeout
    tool_filter=create_static_tool_filter(
        allowed_tool_names=["semgrep_scan"]   # sirf yeh ek tool
    ),
)
```

### MCP + serverless ka important insight

Ed copy-paste nahi kara raha — focus **deploy karna** hai, code likhna nahi. Sabse interesting cheez: **ek agent jo MCP server spawn karta hai use kaise deploy karein?**

- **Lambda / serverless functions** par yeh **bahut mushkil** hai — serverless functions **separate processes spawn karne ke liye design nahi** hain. Wo bas ek function ki tarah behave karne ke liye hain. Hoops jump karne padte hain.
- **Containers iske liye ideal hain** — Docker container ek "box within the box" hai. Container ke andar **kuch bhi** ho sakta hai (subprocess spawn including), jab tak properly defined ho.
- Isliye: **agar agent MCP servers spawn karta hai, toh simplest start = Container Apps (CaaS)** — exactly yahi hum karne wale hain (ACA + Cloud Run).

---

## 📋 Key Concepts

| Concept | Matlab |
|---|---|
| **Semgrep** | Free static analysis (SAST) tool — code ko vulnerabilities ke liye scan karta hai bina chalaye |
| **Semgrep App Token** | API token (Web API scope checked karna zaroori) — `.env` mein `SEMGREP_APP_TOKEN` |
| **`.env` + `.gitignore`** | Secrets locally; dark gray = git-ignored, accidentally commit nahi hoga |
| **OpenAI Agents SDK** | Agent + tools + MCP + traces wala framework (plain client se aage) |
| **Security Researcher agent** | GPT-4.1 mini agent, Semgrep MCP equipped, structured output deta hai |
| **SecurityReport** | Structured output Pydantic model — summary + issues (title/desc/fix/CVSS/severity) |
| **CVSS score** | 0-10 vulnerability severity ka standard numeric measure |
| **Static tool filter** | Agents SDK feature — agent ko sirf chuninda tools dena (yahaan `semgrep_scan` only) |
| **MCP timeout** | Server start ke liye 2-min `client_session_timeout_seconds` |
| **Traces** | OpenAI observability — agent ke steps dashboard par dikhte hain |
| **MCP + serverless problem** | Serverless processes spawn nahi karta; container "box-in-box" ideal hai |

---

## 💼 Backend Dev Ke Liye Note

Yeh lecture ek backend dev ke liye **agentic backend ka anatomy** dikhata hai. Notice karo ki yeh bilkul tumhari familiar FastAPI service jaisa hai — routes, Pydantic models, CORS, health check, modular `context.py` — sirf "business logic" ki jagah ek **agent orchestration layer** hai. Teen production-grade patterns yahaan seekhne layak hain: (1) **`output_type` se structured outputs** — LLM se reliable JSON nikalna, free-text parse karne se kahin behtar; tum yeh Pydantic se already karte ho, ab agent isse enforce karta hai. (2) **Static tool filter = least privilege** — agent ko sirf utne hi tools do jitne chahiye, exactly waisa hi jaise tum IAM mein minimal permissions dete ho; yahaan Semgrep ke 30+ tools mein se sirf `semgrep_scan` exposed hai, attack surface chhota. (3) **Subprocess-spawning workloads ka deployment** — yeh ek classic backend ops gotcha hai: serverless (Lambda/Functions) ephemeral, single-purpose execution maanta hai aur child processes ko handle nahi karta; jaise hi tumhara service `subprocess`/`stdio`-based dependency spawn karta hai (MCP stdio server, headless browser, ffmpeg, etc.), tumhe **container** chahiye. Yeh decision tree (function vs container) production architecture ka core hai.

---

## ✅ Takeaway

- **Semgrep account** banao, **App Token (Web API scope on)** + **OpenAI key** `.env` mein daalo (exact spelling, git-ignored)
- Back end = FastAPI + **OpenAI Agents SDK** "Security Researcher" agent (GPT-4.1 mini) + Semgrep **MCP server**
- **Structured output** `SecurityReport` (summary + issues with title/desc/fix/CVSS/severity)
- **Static tool filter** se agent ko sirf **`semgrep_scan`** tool milta hai — least-privilege pattern
- Key insight: **MCP-spawning agent ko serverless par chalana mushkil; container ideal** (box-within-a-box)

---

<details>
<summary>📜 Full Transcript (English)</summary>

So here we are in the cyber project. You can see it's got a very simple directory structure back end, front end, terraform and then week three which is of course our documentation for the week, our guides which has day one and day two where only this, this project cyber is just for days one and two. And day one has three parts and day two has two parts. Day one is going to be a little bit longer than day two. Day two will go, go faster. We've got we've got a fair bit to do. So let's start by opening the preview of what I'm calling part zero, because it's kind of getting ourselves up and running and with some basics that will apply for both Azure and then GCP. Okay. So day one part zero getting started with this project. So we're going to build an AI powered web application that analyzes some Python code for security vulnerabilities. And the first step, the first section setting up the project just tells you to do exactly what we already did. So it'd be a bit meta if we if we somehow hadn't done this and we were in, in in this section. But it goes without saying, we've done this, we've opened it, we've inspected these four directories. We're already on section two. Okay. So we're going to be using a agent that is equipped to handle cybersecurity analysis. And we're going to be doing this by using a tool called Semgroup, which is a very well known tool for analyzing code for security vulnerabilities. And Semgroup has an API and it's free. And so that is what we're going to do right now. We're going to set up a Semgroup account. Setting up these accounts and API's is is something that one has to do a million times. And so hopefully you'll, you'll, uh, Barrett, this time when we quickly set up this account so that we can use that MCP server, which is going to be a lot of fun. So let's do that right now. So the first thing to do is to go to Semgroup dot like that. Click there. Up it comes. Meet your new AI Appsec engineer and we'll say accept all cookies right there. Uh, and, uh, there is a try it for free button. And that's the place to go to set this up. Uh, and I'm already logged in, so it's already come in. But the first thing that it does is it asks you if you'd like to sign up with GitHub, and I suggest that you do that because that makes it nice and simple. So you obviously have a GitHub account already. And so go ahead and do that. That seems to be super slick to me. And then you come down here and go to settings. And from settings you can then go to tokens. And in tokens this is where you can create a new token. And the only thing to bear in mind when you create a new token is to make sure you check the both the leave. Leave this first one checked, but also check the web API as well. And this is a token which I am not going to create. Uh, so that uh, since I just exposed it to the internet. Uh, so that's not a, not a token and you should never do that. Uh, but I do have some valid tokens that I've created and tested, and this should work. Great. Keep note, of course, of that key, because we're just about to go and put it in our EMV file. In fact, we can do it right now. I can just click back here. So go back in here, create a EMV file by right clicking and into that EMV file. You should then uh. This gives you the instructions to do just what I was exactly telling you. And you should. Then in your EMV file right click new file and then put two keys, open ai API key and put your open AI key and Semgroup app token spelled just like that. Exactly like that. You can't be a letter wrong. And then paste in precisely your Semgroup API token that you just created. I know by this point you get it. You know about these API keys. You know they have to be perfect. So do that. And uh, then you should be in great shape. It's in the dot git ignore. So you'll see that it will go like dark gray like this, which is your indication that it's not going to get accidentally checked into git. Okay. Nice. Onwards. All right. We're now going to run the app locally to test it. Just before we do I want to point out this this file here this Python module airline.py and this if I, if I open this right now this is a piece of Python code which is going to do a little airline chatbot assistant that I do believe I cover in my LLM engineering course at some point. Um, and there's some code in here and you might want, if should you wish to take a moment to review this code in airline.py and see if you can spot a few potential cyber security know knows or even just just things that you might it might make you pause for thought because that this is the challenge, this this page here, this is the challenge that we are going to give our AI to try and analyze and see, have a browse through it. And as a little self test, put the video on pause and see if you can find a few things that would certainly, uh, cause you to raise your eyebrows. Okay. And then with that, come back here again for us to give this a try. Okay. And now let's bring up a new terminal window. And we're just going to check that we have node. I mean obviously you have node. You've got to this point I have 24. And check that you've got you've but obviously you've got you've to have a. Yeah. Get that right. There we go. Uh obviously I have as I say obviously I've got yes I do obviously have you've to have gotten to this point but there's how to install it if you need it. Okay. So uh, the way that this is organized is, is very logical. Back end is a nice back end that you will be, uh, pleased to see follows all of our principles. It's a UV project. It's got a server.py. The server.py is a fast API server, and that fast API server, uh, has the cause nonsense in it. And then it has a little bit of, uh, of pedantic classes set up. People from the, uh, a course will be very familiar with this stuff. It uses OpenAI agents SDK. We're not going to cover that on this course, but you get the docs are beautifully written. You can look it up yourself if you're not already familiar with it from my other courses. But we create an agent called the Security Researcher. Uh, it's the name of it. We give it some instructions. Uh, we're going to use GPT for one mini, and we have an MCP server that we're providing called Semgroup server. And the output type this is structured outputs is going to be a security report. And so the security report which is defined right here is something which has an executive summary and a list of identified issues. And those issues uh include a title description code fix a Cvss score, which is a score from 0 to 10, and then a severity critical high, medium or low. And here it is. So we uh, we have some code to, to create the agent. We have run security analyst. And this is something which uses OpenAI's traces. Uh, it then does the async with to to start a use a context manager to start our MCP server. It creates an agent. It calls runner dot run. Uh, and uh, it then returns the output as a security report and that gets returned. This is the fast API route that we're using right here. And we also have a good old health check as we should. And we have, uh, some test code in here. Uh, I might I might remove that before I check it in. Some of this is extra stuff. And then at the bottom, once again, just as we did in week one, we have this server responsible for serving up the static website as well. We're going to have a Next.js front end. And this is going to return the static website. So this is all in server dot Pi. And you can see I've done something that I like to do, which is that I've separated out a module for context in context dot pi. Remember we did this in week two as well. This has the prompts for the security researcher. There we go. And uh, the, uh, some information to build the prompts. And we have our MCP servers in a separate Python module as well. There's only one MCP server here. It is. The parameters is, uh, we get the Semgroup app token from the EMV file. This is the MCP parameters. If you're not sure about MCP, then, uh, you could check out my course if you wish, or just go along with the flow and come back to it later. Um, and so this this is the, uh, the parameters that we use, uh, and, uh, this is where we create the MCP server with those parameters with a two minute timeout, and we use, uh, something called the static tool filter. This is a recent feature added to OpenAI agents SDK, which allows you to constrain which tools get used, uh, when rather than giving access to all of the different MCP tools We're only giving you access to one of them. And Semgroup comes with a lot, and we're only going to give it one called Semgroup scan. So that's all it can do. So I appreciate I'm not I'm not coding it or not having you copy and paste because it's going to be about deploying this in practice. And the super interesting thing is how you go about deploying an agent that can spawn an MCP server. And you can do that with Lambda and with these serverless functions. But it's really hard because the serverless functions are not designed to spawn separate processes. That's not that's not really how they're used. They're meant to just be a function. So you have to jump through some hoops to get that to work. But it's an ideal use case for using containers because absolutely a Docker container, it's at the box within the box. Anything can happen within that box as long as it's defined properly. And that's why if you've got an agent that's going to spawn MCP servers, the simplest way to start is to use container apps, which is just what we're going to do.

</details>
