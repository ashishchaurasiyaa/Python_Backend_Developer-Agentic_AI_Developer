# L122 — Adding Code Execution Tools and Observability to AWS Bedrock Agents

> **Week 4 · Day 5** · ⏱️ ~9 min

---

## 🎯 TL;DR

Looper mein Bedrock ka **managed Code Interpreter tool** (`execute_python`) add karte hain taaki agent Python chala ke apni solution validate kare; system prompt + red-print cosmetics update karte hain, re-deploy karke train problem ko 4:06 PM par accurately solve dekhte hain. Phir AWS console mein **Observability** section kholke sessions/traces/errors dekhte hain — pata chalta hai rate-limit auto-retries ki wajah se hi sab slow tha. Yeh course ka **last lab** hai.

---

## 🗣️ Hinglish Explanation

### Managed tools — Bedrock ka built-in Code Interpreter

Ed bolta hai bas ek aur cheez add karni hai: Bedrock Agent Core ke **managed tools** mein se ek — **Code Interpreter**. Yeh ek AWS-provided sandboxed environment hai jahaan agent **Python code actually run** kar sakta hai (math/data validate karne ke liye). Tumhe sandbox infra manage nahi karna — AWS karta hai.

### Step 1: Code Interpreter import + tool banao

`looper.py` mein **imports ke neeche** yeh add karo:

```python
import json
from bedrock_agentcore.tools.code_interpreter_client import CodeInterpreter

# Code interpreter abhi sirf US West 2 mein chalta hai
code_client = CodeInterpreter("us-west-2")

@tool
def execute_python(code: str) -> str:
    """Execute Python code in the code interpreter."""
    response = code_client.invoke("executeCode", {
        "code": code,
        "language": "python",
    })
    # response stream se output nikaalo
    for event in response["stream"]:
        result = event.get("result", {})
        output = result.get("content", [])
        return json.dumps(output)
```

Breakdown:

- **`CodeInterpreter("us-west-2")`** — code interpreter client banata hai. Note: yeh (abhi ke liye) **sirf `us-west-2`** mein available hai — wahi ek region jahaan yeh chalta hai.
- `code_client` = wo cheez jo asal mein code run karti hai. Par Strands ko ek **tool** chahiye — toh hum `execute_python` wrapper banate hain.
- `execute_python` apne input `code` ko `code_client.invoke("executeCode", {...language: "python"})` se chalata hai, output stream se nikaal ke return karta hai.

> 🧠 **Managed vs custom tools**: Pichhle lecture ke to-do tools **custom** the (humare apne Python functions). Code Interpreter ek **managed/built-in tool** hai — AWS ka sandbox. Dono ko Strands same tarah `tools=[...]` list mein consume karta hai.

### Step 2: Juicier system prompt

```python
SYSTEM_PROMPT = """You are given a problem to solve. \
You also have access to an execute_python tool to run Python. \
Your plan should include solving the problem without Python and then \
writing Python code and running it to validate your solution. \
To use the execute_python tool to validate your solution, you must have \
a task on your to-do list prefixed with 'Write Python code to'."""
```

- Agent ko bolo: pehle **bina Python** problem solve karo, phir **Python code likh ke run karke validate** karo.
- Validation ke liye to-do list mein ek task hona chahiye jo **"Write Python code to"** se prefixed ho.
- Ed bolta hai exact wording zaroori nahi — experiment karo.

### Step 3: Cosmetic — coding steps red mein print

Print method update karo taaki "Python" waale to-dos **red** mein dikhein (sirf insight ke liye, cosmetic):

```python
# get_todo_report() ke andar, har item ke liye:
if "python" in item.description.lower():
    line = f"\033[31m{line}\033[0m"   # ANSI red
```

- Agar description mein "python" hai toh red ANSI color. *"Just because it's going to look cool."*

### Step 4: Tool register karo

```python
# pehle:  tools = [create_todos, mark_complete, list_todos]
tools = [create_todos, mark_complete, list_todos, execute_python]
```

- Bas `execute_python` ko list mein add kar do. Ab agent ke paas: create_todos, mark_complete, list_todos, **execute_python**.

### Step 5: Re-deploy aur test

Entry point same (`looper.py`) — configure dobara karne ki zaroorat nahi, bas:

```bash
uv run agentcore launch
uv run agentcore invoke '{"prompt": "A train leaves Boston at 2pm traveling 60 miles an hour. Another train leaves New York at 3pm traveling 80mph toward Boston. Where do they meet?"}'
```

Same train challenge, par ab Python tool ke saath:

1. Agent **7 to-dos** banata hai (pehle 6 the).
2. Last to-do **"Write Python code to validate the solution"** — **red** mein print (humari cosmetic ki wajah se).
3. To-dos cross off hote hain; piche Claude rate-limits par ferociously retry kar raha hai (Ed is baar running commentary skip karta hai).
4. **Result: 4:06 PM** — is baar **zyada accurate** answer! (Interesting: usne Python use karne se *pehle* hi yeh answer nikaal liya tha, par managed tool ka use successful dikha.)

**Success** — deployed agent jo managed tool use karke cloud par chal raha hai.

### Step 6: Observability — traces dekho

Final step: AWS console mein observability check karo.

1. AWS console → confirm **IAM user (`ai-engineer`)** (top-right).
2. Service → **Bedrock Agent Core** → left menu **Observability**.
3. Yahaan dikhega (agar L119 mein enable kiya tha):
   - **Agents** list — `first` (jo banaya tha) aur `Looper`.
   - **Sessions** — har invocation ki session.
   - **Traces** — agent ne kya-kya kiya (OpenAI Agents SDK ke traces jaisa).
   - **Errors & throttles** — counts.
4. Ek **trace** kholo → **spans** dikhte hain (har step/tool-call ek span).
5. Ed ko bahut **red spans** dikhte hain → click karke dekha → **rate-limit errors** with **retries** — agent **continually retry** karta raha jab tak success na mila.

> 🔍 **The insight**: Yeh trace se confirm hua ki Looper slow kyun tha — rate-limit errors + auto-retries. Ed ne pehle socha tha "queuing", par trace ne sach dikhaya. Despite all the trouble, system **surprisingly robust** raha (retry-until-success). Yeh exactly observability ki value hai — bina trace ke yeh chhipa rehta.

Traces mein code tools, `mark_complete` calls, sab kuch dikhega — padho, samjho, different info explore karo Bedrock Agent Core observability page par.

### Course wrap-up + assignment

Yeh **course ka last lab** (last day, last week) hai. Ed ka verdict: Agent Core "does what it says on the tin" — agar tum uske **scaffolding** mein rehne mein comfortable ho, toh AWS par agent deploy karne ka isse easy tareeka nahi.

**Assignment (Ed ka suggestion)** — ek **"Sidekick" co-worker agent** banao:
- Ek **Next.js front-end** local app jo agent ko drive kare (terminal ki jagah UI).
- Doosra managed tool add karo — **browser automation tool** — taaki agent web bhi browse kar sake (code-run + browse dono).
- Isme yeh **to-do list loop** bhi hai (jo Agentic course ke Sidekick mein nahi tha), single-agent loop ke saath.
- Bana ke `community_contributions/` mein daal ke **PR bhejo** — Ed khud try karna chahta hai.

---

## 📋 Key Concepts

| Concept | Matlab |
|---|---|
| **Code Interpreter (managed tool)** | Bedrock ka sandboxed environment jahaan agent Python run karta hai; sirf `us-west-2` |
| **`execute_python` tool** | `CodeInterpreter` client ko wrap karne wala Strands `@tool` |
| **Managed vs custom tools** | Managed = AWS-provided (code interpreter, browser); custom = tumhare apne functions |
| **System prompt steering** | "without Python, then validate with Python" + "Write Python code to" prefix rule |
| **ANSI red print** | Cosmetic — "python" waale to-dos red mein, insight ke liye |
| **Observability / traces / spans** | Console mein sessions, traces (per-step spans), errors/throttles dekhna |
| **Auto-retry visible in traces** | Red spans = rate-limit errors jise agent retry-until-success karta raha |
| **Sidekick assignment** | Next.js UI + browser tool + to-do loop = AWS-hosted co-worker agent, PR to community |

---

## 💼 Backend Dev Ke Liye Note

Backend dev ke liye Code Interpreter ek **managed sandbox-as-a-service** hai — yeh wahi pattern hai jahaan tum untrusted code ko isolated runtime (gVisor/Firecracker/container) mein chalate ho, par AWS ne isse ek API call (`code_client.invoke("executeCode", ...)`) bana diya. Region-pinning (`us-west-2`) ek real production constraint hai: cross-region latency aur data-residency soch ke architecture banao. Sabse valuable backend lesson **observability** hai: yeh distributed tracing hai (spans = OpenTelemetry-style trace tree, jaise Jaeger/X-Ray). Ed ka "I thought it was queuing but traces showed rate-limit retries" ek textbook example hai ki **logs/metrics akele kaafi nahi — traces hi root cause dikhate hain**. Production agents mein yeh non-negotiable hai: bina traces ke retry-storms, throttling, aur silent slowness invisible reh jaate. Aur "robust because it retries until success" ek double-edged sword hai — retry hona resilience hai, par unbounded retries cost + latency spike de sakte hain, toh production mein backoff + max-retries + alerting chahiye.

---

## ✅ Takeaway

- Bedrock ka **managed Code Interpreter** ek tool ke roop mein add hota hai (`execute_python` wrapping `CodeInterpreter("us-west-2")`) — sirf us-west-2
- System prompt se steer karo: "pehle bina Python solve, phir Python likh ke validate" + "Write Python code to" prefixed to-do
- Re-launch ke baad agent ne train problem **4:06 PM** accurately solve kiya, managed tool use karke
- **Observability** (console → Bedrock Agent Core → Observability) = agents/sessions/traces/spans/errors; red spans ne reveal kiya ki slowness = rate-limit auto-retries
- Last lab — assignment: Next.js UI + browser-automation managed tool + to-do loop = "Sidekick" co-worker agent, phir `community_contributions/` mein PR

---

<details>
<summary>📜 Full Transcript (English)</summary>

Okay, we have just one more thing to do to this. We're going to add in one of the the managed tools, one of the tools that comes with bedrock. We're going to add in the code interpreter. So what we're going to do is it's going to be really simple. We're going to add in one more tool right under the imports. We're going to add this. So let's go back to looper.py under these imports here. Add this. It's got another import. It imports the code interpreter and also JSON. And then what we do here is we create a code client code interpreter in US West two, which I believe right now at least it has to be US West two. That is the only place where this code interpreter runs. And we're then going to create a new tool. So the code interpreter is the thing that actually runs the code. But we have to create the tool that we will give to strands. Um, and this tool is will call it execute Python. We could call it whatever we want and we give it a comment. Execute Python code in the code interpreter. Uh and we call this code client. We call invoke execute code and language Python, and we pass in whatever came in in our input to this function. And then this is some stuff to get back the output and return it. All right. That is our execute Python code function I just did save. If you saw that let's go back here. Let's change the system prompt to give it a little bit of a juicier, beefier system prompt. Here we go. Paste save. So I'm saying you're given a problem to solve. Same as before. You also have access to execute Python tool to run Python. Your plan should include solving the problem without Python and then writing Python code to validate your solution. I should probably say Python code and running it to validate your solution. To use the execute Python tool to validate your solution, you must have a task on your to do list prefixed with write python code to uh and now blah blah blah. So of course you don't need to have exactly the system prompt. You can play around with it as you wish. but I think this is going to be an intriguing way for us to see the to do list and Python execution in action together. Okay, back we go to the Readme. There's just a couple more things to do. Uh, so we want to update the print method so that when it's doing coding, it will print it in red so that we just get a little bit more insight into this. This is just a cosmetic change, really. Look, if it's a if Python is in the description, then we put it in red just because it's going to look cool. Um, okay. And then the only final step is to replace the tools call with this. We're just going to add in execute Python as a tool. Uh so where do we do the tools. Right here. We're just going to put in there comma execute Python just as cursor as telling us okay. So now the agent is equipped with creative DOS mark complete list to DOS and execute Python. All right back here we go. It's now a matter of doing. You've run agent or launch. Did I save? Yes, I did, so I can just run this. And off it goes. And I will see you a second when this is deployed. And we will be able to give this a whirl. Okay. So we're going to give it the same as before. Exactly the same challenge. This time it's equipped with a tool to run Python code. So here we go. Uh let me see. It says it needs to, uh, solve the problem step by step. It's giving itself, uh, seven to do's. The first one is to identify the given information. Just like before. These look pretty similar, but it ends with a step to write Python code to validate the solution. Uh, which is a printed in red because of that little extra thing that I did. Uh, and so this is really cool. And I'm not this time going to sit here to give you the running commentary for the next minute. While I believe Claude is ferociously retrying with rate limits behind the scenes, but I will, I will I will just look at that. Look at that as it crosses things off. It's so great. I hope you've got the same experience. You're seeing this happening, and I will come back in a second when this is complete and we'll see what answer we get. And there we go. It completed. Hopefully yours did too. And I do believe we got yes. 4:06 p.m.. We got a more accurate answer this time, although it came up with that answer before it even used the Python tool. But but so interesting. But but there we go. It's able to use the managed tool as well. We have success. We have a deployed agent using tools all running in the cloud on AWS. That's pretty awesome. And the final step in in our sheet here is that we just want to go and go, go and look at the observability, which will have us go back to the AWS console as your IAM user, go to the Bedrock Agent Core service and look at observability. Let's go and do that now. So here we are in AWS console check. It's the IAM user. On the top right we go to Bedrock Agent Core. There it is. Click there. And now here on the left is observability. So we can go into this and check out what we can see. Uh so as long as you configured everything then you should see stuff like this. I've got a couple of agents, got some sessions, some traces, some error and throttles. Stuff happening here are the agents. Uh, this is, uh, the, uh, first that we did, and then this is Looper, uh, which which we just built and got a couple of sessions, a couple of traces, and. Yeah, you can click on sessions to view the the different sessions you had. You can see I'm getting lots of errors and throttles and stuff and go to traces to look more at the actual traces that, uh, that have been left by, by the agent. A bit like the traces we get in OpenAI agents SDK. So if we come in to to one of these traces, we see, uh, all of this, uh, spans. And this is where I mentioned you could see a lot of for me, I get a lot of these red things here. If I click on that, uh, I'm getting a rate limit error that's coming from this, uh, with some, some retries, and it's, uh, continually retries until it gets through, which is great. Uh, so it's surprisingly robust given given how much, uh, trouble I've given it. So I'm very happy to see this. Uh, and it's interesting. And I didn't even realize that this retrying was happened. I, I'd noticed how slow it was, and I thought, I wonder why it's so slow. Maybe there's some queuing thing happening. Uh, but it didn't occur to me that I was getting rate limit errors, and it was automatically retrying until I brought up the traces and saw this. So, uh, very, very insightful. And anyway, you may have a better tracer than me, but you should take a look through it and have a look at some of what's going on. Take a look at the, uh, the code tools that are getting the mark complete and so on. everything running away and read through your traces. As always, get a good sense of it and have a look at the different bits of information that you can review on the observability page of Amazon Bedrock Agent Core. And that is a rather satisfying wrap on our last lab of our last day, of our last week. And I hope you're impressed by AWS Bedrock Agent Core. It definitely is what it says on the tin. Easy to get your agent deployment out there. And as I say, as long as you are comfortable sticking within the kind of scaffolding that it's set for you, then I can't imagine an easier way to get something deployed out onto AWS services. So I think it's a great entrance to the market and I look forward to playing with it. My suggestion for you is do a quick assignment to take this further, so you could build a local front end app using Next.js, just so you could drive it from a from a screen, unless you enjoy using the terminal, in which case you can you can keep doing that the code style experience, but add in the other managed tool, the browser automation tool, so that it can do that as well as running code, and then turn this into something which is like a co-worker for you. I like to call it a sidekick. My on my Agentic course, we build out a sidekick agent, and you could do this here, but it's a sidekick running on AWS and using its managed tools. And it would also, of course, now have this to do list, which we didn't do last time. And being a single agent loop, which is which is which is. So yeah, easy and cool to see this happening. So build all of that, make a sidekick. And since you happen to already be in the production repo, what could be easier than just taking your your agent and plonking it in to community contributions. There it is. Put it in community contributions. Send a PR. I would love some wonderful agent called deployments examples in here that others can then take, and I would like to try it out myself. So please do that. That would be great.

</details>
