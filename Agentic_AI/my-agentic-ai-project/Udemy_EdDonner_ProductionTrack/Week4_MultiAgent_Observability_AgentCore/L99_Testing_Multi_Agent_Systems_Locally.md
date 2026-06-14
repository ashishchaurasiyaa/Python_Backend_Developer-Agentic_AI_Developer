# L99 — Testing Multi-Agent Systems Locally Before Lambda Deployment

> **Week 4 · Day 2** · ⏱️ ~13 min

---

## 🎯 TL;DR

Deploy karne se pehle do production tricks (tracing + tenacity retries) aur ek **critical architecture insight**: planner ka tool call asli mein dusre **Lambda function** ko serverless call karta hai — yahi distributed multi-agent ka raaz hai. Phir paanchon agents ka `test_simple.py` locally chala ke 5/5 pass karte hain.

---

## 🗣️ Hinglish Explanation

### Trick 1: Tracing everywhere

Ed har orchestrator run ko **trace** ke saath wrap karta hai:

```python
from agents import trace, Runner

with trace("Planner Orchestrator"):
    result = await Runner.run(planner_agent, input_text)
```

Isse OpenAI Agents SDK ke **traces UI** (platform.openai.com/traces) par dikhta hai ki kaun-se messages kahaan bheje gaye — full visibility multi-agent flow ki. Production observability ka pehla layer.

### Trick 2: Tenacity — automatic retries on rate limits

Bedrock par agar requests-per-minute limit exceed ho jaaye toh **rate limit errors** aana common hai. Ed **tenacity** package (popular retry library; alternative `backoff`) use karta hai — ek decorator se function automatic retry karta hai with **exponential backoff**:

```python
from tenacity import (
    retry, stop_after_attempt, wait_exponential,
    retry_if_exception_type,
)

@retry(
    retry=retry_if_exception_type(RateLimitError),   # sirf rate-limit par
    stop=stop_after_attempt(5),                       # max 5 attempts
    wait=wait_exponential(multiplier=1, min=2, max=30),  # exponential backoff
)
async def run_orchestrator(...):
    ...
```

Yeh resilient agentic production solutions ke liye best practice hai — reusable retry logic, sirf rate-limit exception par trigger.

### THE KEY INSIGHT: tool call = serverless call to another Lambda 🔑

Yeh poore week (shayad poore course) ka sabse important point hai. Ed isse "belabor" karta hai.

**Normal multi-agent (jaise Ed ki Agentic AI course mein)**: planner ke tools sub-agents ko **same Python process** mein call karte hain — sab ek hi machine/process par chalta hai.

**Yahan kuch bilkul alag hai.** Jab planner apna tool, e.g. `invoke_charter`, use karta hai:

```python
@function_tool
async def invoke_charter(ctx, ...):
    """Invoke the Chartmaker agent to create portfolio visualizations."""
    # YEH agent code directly call NAHI karta —
    # yeh ek dusre Lambda function ko serverless invoke karta hai!
    response = lambda_client.invoke(
        FunctionName="charter-lambda",
        Payload=json.dumps(payload),
    )
    return parse(response)
```

Toh `invoke_charter` ek **Lambda serverless call** karta hai ek alag endpoint par. Matlab:

- Har agent ek **alag Lambda process** par chalta hai.
- Jab planner apne tools use karta hai, wo **alag-alag Lambda functions** ko call karta hai jo ek-dusre se connect hote hain.
- Charter Lambda "wakes up", apna agent code chalata hai, response wapas bhejta hai.
- Yahi tarika **poora agent orchestra** collaborate karta hai — **across process boundaries, across serverless endpoints**.

**Kyun yeh enterprise-strength hai?** Agar sab ek hi Lambda mein hota (jaise Agentic AI course mein single Python process), toh:
- ❌ distributed nahi hota
- ❌ scalable nahi hota
- ❌ parallel mein Lambda functions ko kaam karte nahi dekh paate

Is design se har agent independently scale + respond karta hai. Yahi W3 ke "ek process" projects se is "across serverless endpoints" setup tak ka bada jump hai.

> Ed bolta hai: agar samajh na aaye toh dobara suno — yeh itna important hai. Code padho `planner/agent.py` mein aur confirm karo ki tools different Lambda functions ko call karte hain, na ki bas dusra agent code.

### Local testing: `test_simple.py` (deploy se pehle)

Har agent directory mein do test files: `test_simple.py` (simple local test, deploy se pehle) aur `test_full.py`. Ed ek-ek karke `test_simple.py` chalata hai:

```bash
# Har agent folder ke andar (UV project)
uv run test_simple.py
```

| # | Agent | Result |
|---|---|---|
| 1 | **tagger** | Vanguard Total Index ko **ETF** classify kiya, DB mein tag + save (structured outputs) ✅ |
| 2 | **retirement** | "Assessment of retirement readiness" text return (no tools, plain chat completion) ✅ |
| 3 | **charter** | Multiple portfolio charts banaye — horizontal bar, sector distribution, geographic exposure (autonomous, par no tools/structured outputs) ✅ |
| 4 | **reporter** | `get_market_insights` tool call kiya (S3 Vectors se), fir Nova se report likha (first 500 + last 200 chars print) ✅ |
| 5 | **planner** | Fake job ID se orchestrate kiya — reporter/charter/retirement call kiye. **Tagger NAHI call hua** (DB mein kuch untagged nahi tha). Output: `Success: True` ✅ |

> Important observations:
> - **Charter autonomous hai bina tools ke** — wo khud decide karta hai kaunse charts banane hain. Tools/structured-outputs na hona autonomy ko nahi rokta.
> - **Planner ka output sirf `Success: True`** — wo pure orchestrator hai, koi content खुद generate nahi karta.
> - Sab **Bedrock → Nova Pro v1** par, OpenAI Agents SDK se managed.

### The whole-system test (parent directory)

Guide step 3.6 par: parent `backend` directory (jismein saare agents hain) khud bhi ek **UV project** hai aur uska apna `test_simple.py` hai. Yeh ek-ke-baad-ek saare 5 agents ke tests chalata hai — poore system ka once-through:

```bash
# backend (parent) directory mein
uv run test_simple.py
# ~1 min — chalta hai: tagger → reporter → charter → retirement → planner
```

Final report:

```
Tagger:     PASS
Reporter:   PASS
Charter:    PASS
Retirement: PASS
Planner:    PASS

5 passed, 0 failed — All tests passed ✅
```

Toh ab: 5 directories, 5 UV projects, har ek ke paas `lambda_handler.py` + `agent.py`, har ek apna task karta hai, sab independently tested + passing. Next step: **package up → deploy to Lambda → test live on internet**.

---

## 📋 Key Concepts

| Concept | Matlab |
|---|---|
| **`trace(...)`** | OpenAI Agents SDK tracing — flow traces UI mein dikhta hai |
| **tenacity** | Retry library — `@retry` decorator + exponential backoff |
| **Rate limit retry** | Bedrock RPM exceed par auto-retry (5 attempts), sirf rate-limit par |
| **Tool = Lambda call** | Planner ka tool ek alag Lambda function ko serverless invoke karta hai |
| **Distributed agents** | Har agent alag Lambda — scalable, parallel, across process boundaries |
| **`test_simple.py`** | Per-agent local test, deploy se pehle |
| **`uv run test_simple.py`** | Test run command (har UV project mein) |
| **Parent backend test** | Whole-system test — saare 5 agents ek saath (5/5 pass) |
| **Charter autonomy** | Bina tools ke bhi agent decide karta hai (autonomous != tools) |

---

## 💼 Backend Dev Ke Liye Note

Yeh lecture distributed-systems engineering hai jise backend dev turant connect karega. "Tool call = Lambda invoke" basically **inter-service RPC over serverless** hai — har agent ek microservice hai apne endpoint ke saath, aur planner ek orchestrator service jo unhe network par call karta hai. In-process function call vs cross-process serverless call ka trade-off wahi monolith-vs-microservices debate hai: distribution se independent scaling + parallelism milta hai, par network latency + failure modes (timeouts, partial failures) aate hain. Isiliye **tenacity + exponential backoff** — yeh wahi resilience pattern hai jo tum kisi flaky downstream service (payment gateway, third-party API) ko call karte time lagate ho; idempotency aur retry sirf transient errors (rate limit) par, permanent errors par nahi. **Tracing** = distributed tracing (jaise OpenTelemetry/Jaeger) ka LLM-version — multi-hop request ko follow karna. Aur "test locally before deploy" + per-service test + whole-system integration test — yeh test pyramid (unit → integration) ka exact mapping hai. Bottom line: agents ko sirf "AI" mat samjho — yeh distributed services hain aur unpe wahi rigor lagao.

---

## ✅ Takeaway

- **KEY INSIGHT**: planner ka tool call asli mein ek **alag Lambda function** ko serverless invoke karta hai — har agent independent, distributed, parallel-scalable (single-process se bada jump)
- **Tracing** har orchestrator run par lagao — OpenAI Agents SDK traces UI mein full multi-agent visibility
- **tenacity** se rate-limit errors par exponential-backoff retry (5 attempts) — production resilience best practice
- Deploy se pehle har agent ko **locally test karo**: `uv run test_simple.py` — sab 5 pass (tagger/reporter/charter/retirement/planner)
- Parent `backend` directory ka whole-system test = **5/5 passed**; ab next: package + Lambda deploy + live test

---

<details>
<summary>📜 Full Transcript (English)</summary>

And I know you want me to hurry up and deploy this and see some action, but I think there's some really good tips and tricks here that I do want to give you some insight into. Uh, two more things to mention to you. One of them is that you'll see that I've used traces carefully everywhere. So if we come back to this here, you'll see that that, uh, when we run the orchestrator, I do it with trace. And there is the planner orchestrator. So that, um, we're always using traces, remember? That means that we're going to be able to see it in OpenAI agents SDK screens. We'll be able to trace what messages are sent to what. The other thing I wanted to mention is right here, uh, is that I'm using a very nice package called tenacity, which is a really simple, cool way to be able to decorate functions that will then automatically retry on different exceptions. So what I wanted to do is, uh, it is quite common to get rate limit errors if you call an LLM and in bedrock, and you exceed a certain number of requests per minute. And so what I've got here, just by using this decorator, is something that will automatically retry this, this run orchestrator, uh, up to five attempts. And you can see that there's like a what they call an exponential back off in terms of how long it waits each time. Tenacity is a great package for this. Another one is actually called backoff. Uh, but I'm using tenacity tenacity here, which is very popular. And, uh, this this just gives you a nice reusable way of having this kind of retry logic, which is a great thing to do, particularly with rate limit errors. I'm just doing it only if there's a rate limit error. So this is a good best practice that you should you should replicate for resilient agentic solutions in production. But there is one more thing to point out, which isn't so much about the code. It's about the whole way this thing works that that might might not be clear to you. You may already get this or not, I don't know. So normally with. With an agentic framework like OpenAI agents SDK, you would have tools to call each of the different sub agents in a multi-agent system, and you would equip your model with those tools, and then it would decide, okay, I'm going to call this tool that's going to call the other agent, which would all happen in in your Python module in your process. There's something very different here. And it's very easy to show you if the, the, uh, the planner agent chooses, for example, to use its tool, its function tool called Invoke Charter. The description is invoke the Chartmaker agent to create portfolio visualizations. What that actually does is it calls this function invoke charter. So you might think this is going to then make a call to to the other agent to to to run the charter. So let's go and look at what Invoke charter does. What invoke charter does is it makes a lambda serverless call. This is this is really the key to everything Maybe to all of this week and maybe more that we are implementing it so that the tool call that OpenAI agents SDK can make makes an external call to another lambda process, another serverless function on a different endpoint. And and that means that basically each of our agents can run a separate lambda processes that each connect to each other. Because when when the planner uses each of its tools, those tools make calls to different lambda serverless processes. And that's how our whole agent orchestra collaborates. It would be possible to build this all in one lambda and just have it be be the same way as I as I built things in the Agentic AI course, where in the same Python module you're just making calls to different agents. But if you did that, then everything would run on one lambda and it wouldn't be distributed, and it wouldn't be scalable and you wouldn't be able to to watch all of your different Lambda functions work in parallel. but this way this is the the the enterprise strength way. Each call to a different agent involves calling out to a different lambda function. So you have different lambda functions for each of your agents. I hope that that made sense. If not, go back and listen to what I just said again, because it's really important. And come back and look at the code. Look at the code in agent, dot py in planner and satisfy yourself that when it's making use of tools, it's actually calling out to different lambda functions, not just a different agent code. And this is such a critical point that I'm going to bring you back to the slide again to show you the diagram to emphasize one more time, we've been looking at the lambda function for the planner and the planner. Lambda function, you remember, has three tools reporter, charter, and retirement. And it also has some code that in a workflow like way makes multiple calls to tagger. But what you saw in that implementation is that when it makes a call, for example, to charter, it's not just directly calling the agent code for charter. Know what it's doing is it's making a serverless API call to a different Lambda to the charter Lambda. And when it calls that the Charter Lambda wakes up and it runs its agent code. So each of these agents are running on separate different serverless endpoints. And each of them are able to to respond separately to requests and process them. And as planner orchestrates these different calls, it's calling out to different lambda functions. And that that is such an essential point, which is why I'm belaboring it. And it's really a big ingredient. This takes us from the kinds of agent projects that were in my Agentic AI course, when everything was running in one Python instance to this, to to in one Python process, to this kind of setup where we are calling across different process boundaries to different serverless endpoints as our agents collaborate to solve planner's business problem. Okay, that's enough chit chat. We're going to get to action. Let's now go into each of these directories. We'll take a look at these. You'll notice that in each of them there are two test files in common. Test Simple and test full. And test simple is the one that is just going to do a simple local test of this code before we even deploy it. So let's give that a whirl right now. So I'm going to come in to Alex. I'm going to go into back end I'm going to start with the let's let's start with the tagger a nice and simple one. And we're going to run this. Remember this is the one that uses structured outputs to classify an instrument like IBM stock or Google stock and classify it by things like its region and the asset class and stuff like that. Let's run our first test. So here we go. I'm going to do a UV run test simple dot pi. And we run it. We're hoping to see that we're going to testing the tagger agent. It's using OpenAI agents SDK. It's going to try and classify the Vanguard Total Index, a very standard fund that people have in their portfolios. It's running bedrock US. Amazon Nova Pro and that's all looks great. It's, uh, hopefully going to come back with some results. And it finished. Uh, so it got a VCR classified as an ETF that was tagged and saved in the database. So we just had a successful test run of the tagger. All right. Next up we're going to go and try out the uh let's try the retirement one that's going to give us some retirement advice. Let's do UV run test simple and see what happens here. Uh so this is again it's going to be running using Nova Pro, the retirement specialist, which I believe has no tools, no structured outputs. It's just generating text based on the portfolio of the test user that we set up moments ago. So this is just a simple chat completions API call that's hopefully going to return a bunch of retirement data by the time I finish the sentence. There we go. Here it is. Assessment of retirement readiness. A whole bunch of stuff that appears to be working. All right. Next up let's look at charter. Uh so charter is the one that's able to make JSON charts. Let's you've run test.py and see what we get if we try out charter. It's also just a chat. Completions. Not what Claude wanted. Claude wanted all sorts of stuff but it is just a chat, completions, which is all that's required and it will hopefully again be calling Nova Pro using bedrock. And I'll take this. Well, it's already done it. It's created it. And you can see it prints out what comes back. It's made a horizontal bar chart. It's made a bunch of different portfolio allocation charts, distribution across industry sectors and geographic exposure. These are all charts that it has decided that it wants to produce. So even though it's an agent and even though it doesn't have tools and it doesn't have, uses structured outputs. That doesn't mean that it can't be autonomous in that it's making decisions about which chart it wants to show. And it seemed to work well. And next up, we'll do the reporter two. Reporter. Pi report is a bit more complicated because it does. This is the one that has a tool that it can use if it wishes to, to look in the S3 vectors at the research and it is using it, it's calling Get Market Insights. So it has decided it does want to get some market insights which it's collecting from the database. Hopefully that's running. It's just run. And now it's it's calling Nova Pro to complete its its report on the users portfolio. And hopefully any minute now we're going to get to see the results of this. And it's a reminder that each of these bits of code will be deployed as a separate lambda function. And here we go. Uh, it's got a bunch of stuff. This is the first 500 characters and the last 200 characters. Uh, and it says apparently this portfolio could be better positioned to achieve desired characteristics. There we go. So that seems to be working fine. Okay, so I hope you're doing this with me. With me, it's super important to test locally before you deploy. And the last one we're going to do is planner, which is the meatiest of the tests you've run. Test. Simple. Dot py is running our planner locally to check that it runs and it tries to call the different tools. So off it goes. Testing the planning orchestrator with this like a fake job ID that it comes up with and off it's going. It's it's calling its functions reporter charter and retirement. And let's come back to, to uh chat completions again. Notice it didn't call tagger because we didn't need anything to be tagged in the database. And we'll give it a few seconds. And there we go. Analysis completed. Success. True. That's it. It doesn't have any output other than that it is just an orchestrator. And it was successful. So what we've shown here is that each of our different lambda functions that will be deployed separately, each has a simple test that can be run locally and that passes. And it's all calling to through bedrock to the Nova Pro V1 model. And it's all being being managed by OpenAI agents SDK. So far so good. And if you're following along on the guide, we're now at step 3.6. The last of these simple tests to show you is that in the in the parent directory, back end, the directory which each of these agents is within. In that parent directory. There is also a test simple file as well. And it's also a UV um folder too. And if I run test simple in the parent directory, it goes through and runs tests for each of the different individual agents. It's running each of the different five tests that we just did, one after another. And this is a way to give the entire system all five agents a once through, which is a good way to check that everything is in good shape, which is happening right now. It's going to take about a minute, and I will see you back in a second. And you've been following along with me, I hope, in which case you also have got to the point now where you see this report. It tested the tagger successfully. The reporter, the charter, retirement and planner passed five out of five, failed zero out of five. All tests passed. So congratulations. You have five different uh, directories, five different UV projects. Each one of them has a lambda handler.py and an agent.py. Each one of them carries out its task, and we've tested each one of them independently. And they all pass. We're in excellent shape. The next step, of course, is now to take this package it up and deploy it to Lambda and try testing it actually out there on the internet. Let's do that next.

</details>
