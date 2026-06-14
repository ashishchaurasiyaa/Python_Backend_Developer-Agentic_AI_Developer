# L97 — Exploring Multi-Agent Architecture: Tools and Structured Outputs

> **Week 4 · Day 2** · ⏱️ ~5 min

---

## 🎯 TL;DR

Backend folder explore karte hain — har agent directory ki ek consistent structure hai (`lambda_handler.py`, `agent.py`, `templates.py`, `package_docker.py`, UV project). Ed ek homework deta hai: paanchon agents ke code padho aur note karo kaun tools use karta hai, kaun structured outputs.

---

## 🗣️ Hinglish Explanation

### Backend folder ka tour

Ed Alex ke `backend` folder mein le jaata hai. Yahan kayi directories hain:

- **Familiar (W2/W3 se)**: `ingest`, `researcher` (research agent), `database` (kal banaya).
- **Naye agent directories (aaj ke star)**: `charter`, `planner`, `reporter`, `retirement`, `tagger`.

### Har agent directory ki SAME structure

Ed `retirement` kholta hai example ke liye — ek agent ki structure samjho, sabki samajh aayegi. Common files:

| File | Kaam |
|---|---|
| **`lambda_handler.py`** | Lambda par deploy hone wala module. Isme `lambda_handler()` function hai — yeh Lambda har invocation par call karta hai (W2 se familiar) |
| **`agent.py`** | Asli agent functionality — yahan agent banta hai (LLM call + tools + structured outputs). Plus data-prep ka code |
| **`templates.py`** | Prompts ka text — **context engineering** ka key part yahan hota hai (agent.py ke saath) |
| **`package_docker.py`** | Python module jo Lambda ko **zip** mein package karta hai, Docker container use kar ke |
| **`observability.py`** | Abhi ignore karo — baad mein aayenge |
| **UV project files** | `pyproject.toml` + apna virtual env — har agent ek alag UV project hai |
| **test files** | `test_simple.py` + `test_full.py` — baad mein |

### Framework: OpenAI Agents SDK + Bedrock via LiteLLM

Ed agent functionality ke liye **OpenAI Agents SDK** use karta hai — "my favorite" — par bolta hai **framework matter nahi karta** (recall: context engineering). Koi bhi chalega.

- Yahan koi fancy SDK features use nahi kar rahe — sirf ek **agent call** (LLM call), **tools**, aur **structured outputs**. Yeh teen cheezein har framework support karta hai.
- **OpenAI Agents SDK Bedrock se LiteLLM ke through baat karta hai** — yahi mechanism hai. CrewAI bhi LiteLLM use karta hai. Bahut saare frameworks identical hain is matter mein.

> **LiteLLM kya hai**: ek lightweight adapter library jo 100+ LLM providers (OpenAI, Bedrock, Anthropic, etc.) ko ek hi unified OpenAI-compatible interface deti hai. Toh tum `bedrock/<model-id>` likh ke OpenAI Agents SDK ko Bedrock par point kar sakte ho bina apna provider-specific code likhe.

### `package_docker.py` — Docker se Lambda zip kyun?

Yeh Docker **container** nahi hai — yeh ek Python module hai jo Lambda ko ek zip mein pack karta hai (jaise `retirement-lambda.zip`), aur packaging ke liye Docker container use karta hai. Kyun?

- Lambda ek **Linux server** par chalta hai. Agar tum apne Mac/Windows par directly package karoge toh native dependencies wrong platform ke liye build ho sakti hain.
- Toh AWS ke special Docker image (Lambda-compatible Linux environment) mein packaging hoti hai — guaranteed compatible artifact.
- W2 mein yahi kiya tha, par tab **shell script + PowerShell script** the (Windows + Mac alag). Ab sab **Python code** mein hai — ek hi module dono platforms par chalta hai. Better approach.

### 📝 Homework / Exercise

Ed pause deta hai. Tumhe paanchon agent folders (`charter`, `planner`, `reporter`, `retirement`, `tagger`) ka code khud padhna hai aur note karna hai:

1. Har agent **kaise create hota hai**?
2. Kaun-kaun **tools** use karta hai?
3. Kaun-kaun **structured outputs** use karta hai?

> **Tools recap**: agent ko functions/APIs dena jise wo runtime par call kar sake (e.g. database query, market data fetch). **Structured outputs recap**: LLM ko force karna ki wo ek defined JSON schema (e.g. Pydantic model) ke hisaab se output de — free text nahi, parse-able structured data.

Ed ka spoiler-free hint: alag-alag agents alag patterns use karte hain — koi plain (sirf instructions), koi structured output, koi tools. Aglе lecture mein answers compare karenge.

---

## 📋 Key Concepts

| Concept | Matlab |
|---|---|
| **Agent directory structure** | Har agent: lambda_handler + agent.py + templates.py + package_docker.py + UV project |
| **`lambda_handler.py`** | Lambda entrypoint — `lambda_handler()` har invocation par call hota hai |
| **`agent.py`** | Agent creation code (LLM call + tools + structured outputs) |
| **`templates.py`** | Prompt text — context engineering ka core yahan |
| **`package_docker.py`** | Lambda ko Docker se zip mein package karne wala Python module |
| **OpenAI Agents SDK** | Ed ka chosen framework — par framework matter nahi karta |
| **LiteLLM** | Adapter jo SDK ko Bedrock se connect karta hai (`bedrock/<id>`) |
| **Tools vs Structured Outputs** | Tools = callable functions; Structured outputs = JSON-schema-forced response |
| **UV project** | Har agent apna alag UV/pyproject + venv |

---

## 💼 Backend Dev Ke Liye Note

Yeh ekdum clean microservice-style monorepo layout hai jo backend dev pehchanega: har agent ek self-contained "service" hai apne `pyproject.toml`, venv, handler, aur deploy-packaging ke saath — bilkul jaise tum har microservice ko apne dependencies + Dockerfile + entrypoint ke saath rakhte ho. `package_docker.py` ka Docker-based packaging wahi "build in a Linux container so the artifact matches the runtime" lesson hai jo tum native deps (psycopg, numpy, etc.) wale Lambda/containers mein face karte ho — local Mac wheel Lambda Linux par nahi chalti. Aur "framework matter nahi karta" point repeat hota hai: OpenAI SDK vs CrewAI sirf LiteLLM ke upar thin wrappers hain — tumhari real engineering tools, schemas aur handler boundaries mein hai, framework choice mein nahi. Homework approach bhi solid practice hai: naya codebase samajhne ke liye ek representative module deeply padho, fir pattern baaki par apply karo.

---

## ✅ Takeaway

- Har agent directory ki **consistent structure**: `lambda_handler.py` + `agent.py` + `templates.py` + `package_docker.py` + UV project
- **OpenAI Agents SDK** chosen hai par framework matter nahi karta — sirf agent call + tools + structured outputs use ho rahe hain
- SDK Bedrock se **LiteLLM** ke through connect hota hai (CrewAI bhi yahi karta hai)
- `package_docker.py` Lambda ko **Docker-based Linux packaging** se zip karta hai (cross-platform Python, W2 ke shell/PowerShell scripts se better)
- **Homework**: paanchon agents padho — kaun tools use karta hai, kaun structured outputs

---

<details>
<summary>📜 Full Transcript (English)</summary>

So next up, what I've got is something which is a bit of an exercise for you, uh, which is going to be some, some reading. A reading assignment, as you will see. It will make sense in a second. I want to take you to the back end folder in Alex. Open it up and you'll see a number of directories here. Some of them you know very well. You already know, of course, from last week like ingest and, uh, researcher, our research agent. So those you're familiar with and you're also familiar with database because that's what we worked on yesterday. So you know these ones. But there's a bunch of them that are new. And the ones we'll look at right now are of course, charter and planner and reporter and and retirement and tagger. Those are the new the agent directories. Let's pick one. Let's, let's pick a retirement and open it up and have a look at what it contains. And what you'll find is that each of these subdirectories, each agent directory has very similar structure. So once you get the structure of one of them you've got them all. So first of all it has a Python module called Lambda Handler, and you hopefully remember that from week two. This is the Python module that will get deployed to Lambda, and which when you come into it and have a look at it, you'll see that it has a bunch of stuff, but most importantly it has lambda handler as a function. This is the function that will get called on our lambda process, on our on our lambda serverless deployment instance every time it is invoked. So that is our lambda handler function. We have a separate class called agent Pi, which is where we're putting our actual agent functionality. And I'm using OpenAI agents SDK for our agent functionality in this in this course. And I'm using that because that's my favorite. But it really doesn't matter. You could use any one. We're not using any of the clever features of OpenAI agents SDK. We're just using an agent call, an LLM call. And we're using tools, of course, and we're using structured outputs, of course. And all of the agent frameworks support that. OpenAI agents SDK integrates with bedrock via light LM, and that's how we're going to be doing it. So does crew AI. Same thing. Also uses light LM so many of these frameworks are exactly the same. And you could use any that is not important, but the code itself is in agent py. This is where is the code. There's some other stuff to do with with preparing the data. But then ultimately it's got the code that creates the agent right here. There's also a separate class called templates. And templates.py is where I've put the text that will get used in the prompts. It's the key part of context engineering that happens there along with agent py. So templates for each of these directories is where that happens. Each of them is of course a UV project in its own right. So it's got its own like UV and its own Pyproject.toml. We'll see here somewhere. And there it is. And it's got its own virtual environment in here too. And each of them has a file called package_docker.py and package docker. Um it's not it's not a Docker container. It's a Python module which is able to package up lambda into a zip file. This one is called retirement lambda zip. And it does that using a Docker container to do the packaging. And why does it use a Docker container? Because we want to make sure that we package this for a Lambda instance for for a Linux server. So we use a special Docker container to do that for us Docker image that AWS has produced. And this is something we also did in week two. So hopefully you remember this and you're like, yeah, I remember that. Uh, so this is this is a great technique I think if I remember right, yes. When we did it in week two, we had lots of scripts that we had. We had like a shell script and a PowerShell script. This time we're doing it all in Python code, which makes life easier for us because we don't need to have a windows version and a mac version. You can just run it by running this module in this UV folder. So this is possibly a better way of doing it. So these are all the different classes. And ignore observability.py for now. That's one that we'll be coming back to. Um yes you could you could pretend that's not there. So these these are the classes. And I also there's also some testing classes I'm going to come back to in a second. But first the exercise for you, the exercise is now to go into each of these folders. Look through each of the each of the five. And I want you to see how are the agents created and which of them use tools and which of them use structured outputs. And take a little note, and then we will come back in a second and uh, compare notes and see if you found that correctly. See, see which what agent does what and how they use tools and structured outputs to achieve their task by looking in the implementations of agents in each of those five directories and put me on pause. Go and do that and we'll come back in a minute to compare notes.

</details>
