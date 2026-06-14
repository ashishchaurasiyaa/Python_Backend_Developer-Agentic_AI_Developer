# L98 — Building Multi-Agent Financial Systems: Code Review and Architecture

> **Week 4 · Day 2** · ⏱️ ~12 min

---

## 🎯 TL;DR

Homework ki answer-key: charter aur retirement **simple agents** hain (no tools, no structured outputs), tagger **structured outputs** use karta hai, reporter ke paas ek **tool** (get_market_insights) hai, aur planner sab ko **tools ke through orchestrate** karta hai. Bonus lesson: tagger ko planner agentic-loop mein nahi, balki plain **Python workflow** se chalaya jaata hai.

---

## 🗣️ Hinglish Explanation

Ed homework ke jawab ek-ek karke deta hai. Saath mein ek recurring theme: **Claude Code ne kaafi agents ko over-engineer kar diya tha, aur Ed ko unhe simplify karna pada** — ek bada production lesson.

### 1. Charter agent — simplest (no tools, no structured outputs)

`charter` ka kaam: JSON charts banana. `create_agent` function sab setup karta hai — par ismein **na tools, na structured outputs**. Bas **instructions + model**. Itna hi kyunki hume sirf JSON format mein charts generate karwane hain, jo instructions se hi achhe se describe ho jaata hai.

> **Claude Code horror story #1**: Ed ne kaafi code Claude Code se generate karwaya. Charter ke liye Claude ne **massively over-engineer** kiya — tools + structured outputs + extra complexity, aur tools khud complicated the. Ed ko sab samajhna aur **pare back** karna pada simplicity tak — jo turned out reliable + easy. Lesson: *LLMs se code generate karwana powerful hai, par unke kaam ko critically watch karo — wo bahut confident hote hain, tests bana ke "success" declare kar dete hain, par tumhe verify karna padta hai.*

### 2. Retirement agent — simple agent, heavy prep

`retirement/agent.py` mein input-prep ka bahut code hai — ek rich context build hota hai jisme bahut information + ek **simulation** (Monte Carlo) hoti hai. Par **agent khud simple hai**: no tools, no structured outputs (empty tools). Sirf portfolio context ke basis par text generate karta hai.

### Bedrock + LiteLLM integration (worth a look)

`lambda_handler.py` mein agent banta + use hota hai. Bedrock se connect karne ka idiom:

```python
import os
from agents import Agent
from agents.extensions.models.litellm_model import LitellmModel

bedrock_region = os.environ["BEDROCK_REGION"]
bedrock_model_id = os.environ["BEDROCK_MODEL_ID"]

# LiteLLM ko Bedrock region AWS_REGION_NAME env var se chahiye
os.environ["AWS_REGION_NAME"] = bedrock_region

# OpenAI Agents SDK + LiteLLM ko bedrock par point karo: "bedrock/<model-id>"
model = LitellmModel(model=f"bedrock/{bedrock_model_id}")

retirement_agent = Agent(
    name="Retirement Specialist",
    instructions=retirement_instructions,
    model=model,
    tools=[],          # no tools
)
```

Key point: **`AWS_REGION_NAME`** wo env var hai jo **LiteLLM** Bedrock region ke liye expect karta hai (sab LiteLLM docs par documented hai). `bedrock/` prefix + model ID se SDK Bedrock se baat karta hai.

> **Claude Code horror story #2**: Retirement ke liye Claude ne ek tool banaya tha Monte Carlo simulations retrieve karne ke liye. Ed ne pucha: *"agar data hamesha context mein rahega hi, toh callback-tool ka point kya hai?"* — answer: **koi nahi**. Tool ka sense tab hai jab data conditionally chahiye. Ed (half-joking) confess karta hai ki Claude Code use bahut gussa dilata hai jab wo same mistake repeat karta hai 😅.

### 3. Tagger agent — structured outputs

`tagger` structured outputs ka example hai. Pattern:

```python
from pydantic import BaseModel
from agents import Agent, Runner

class InstrumentClassification(BaseModel):
    region: str
    asset_class: str
    sector: str
    # ... etc — JSON spec jise model ko follow karna hai

instrument_tagger = Agent(
    name="Instrument Tagger",
    instructions=tagger_instructions,
    model=model,
    output_type=InstrumentClassification,   # <-- structured output
)

result = await Runner.run(instrument_tagger, input_text)
classification = result.final_output_as(InstrumentClassification)
```

`output_type=InstrumentClassification` agent ko force karta hai ki output is JSON spec ke conform kare. Yeh OpenAI Agents SDK ka idiomatic structured-output way hai. Isse model ki "smarts" use karke instruments ko sector/region/asset-class se tag karte hain.

> **Pro move (optional)**: tagger ko **Polygon.io MCP server** se equip kar sakte ho taaki wo polygon query kar ke lookups kare. Par tab Lambda se **App Runner** par move karna padega (MCP server spawn karne ke liye) — yeh W3 se aata hai. Abhi Ed bharosa kar raha hai ki Nova ke paas khud itni expertise hai instruments tag karne ki.

### 4. Reporter agent — has a tool

`reporter` ke paas ek tool hai: **`get_market_insights`**. Yeh tool **S3 Vectors** query karta hai market insights ke liye — jo data hamara researcher agent (W3) constantly likh raha hai. Yahi **"connecting the dots"** hai: last week (researcher → S3 Vectors) + this week (reporter padhta hai). Baaki same Bedrock-via-LiteLLM approach. Prompts Nova + tool use karke user ke financial prospects ka report likhwate hain.

### 5. Planner agent — the orchestrator (uses tools extensively)

Yeh sab ko jodta hai. Function tools `@function_tool` decorator se banaye gaye hain (function → callable tool, JSON blob auto-generate). Teen tools planner ke paas:

```python
from agents import Agent, function_tool, RunContextWrapper

@function_tool
async def invoke_reporter(ctx: RunContextWrapper[JobContext], ...):
    """Invoke the Reporter agent to write a portfolio report."""
    ...

@function_tool
async def invoke_charter(ctx: RunContextWrapper[JobContext], ...):
    """Invoke the Chartmaker agent to create portfolio visualizations."""
    ...

@function_tool
async def invoke_retirement(ctx: RunContextWrapper[JobContext], ...):
    """Invoke the Retirement agent for retirement planning."""
    ...

planner_agent = Agent(
    name="Planner",
    instructions=planner_instructions,
    model=model,
    tools=[invoke_reporter, invoke_charter, invoke_retirement],
)
```

**`RunContextWrapper` trick**: Ed `run_context_wrapper` use karta hai job ID ko functions ke beech pass karne ke liye — taaki har called function jaane kaunsa task run ho raha hai. Yeh OpenAI Agents SDK ka clean, documented way hai. Easy/hacky alternative globals tha (jo Claude ne pehle kiya tha, aur Ed ne "cuss words ke saath" reject kiya).

### Wait — 3 tools? Tagger kahaan gaya? (Workflow vs Agentic)

Planner mein sirf **3** tools dikhte hain (reporter, charter, retirement) — par planner toh 4 agents call karta tha. Tagger kahaan?

**Answer — yeh critical architecture insight hai:**

- Reporter/charter/retirement → **autonomous orchestration**. Planner khud decide karta hai kaunsa call karna hai (LLM-driven). Yeh **agentic** part hai.
- Tagger → **code orchestration**. Database mein dekhna ki kaun-se instruments untagged hain, fir har ek ke liye tagger call karna — yeh ek **deterministic loop** hai, jo "feels like it should be Python code". Toh ise `Runner.run` ke bahar plain Python mein likha hai.

`lambda_handler.py` ke `run_orchestrator` mein:

```python
async def run_orchestrator(...):
    # Pehle: deterministic Python workflow — untagged instruments tag karo
    await handle_missing_instruments(...)

    # Phir: autonomous agentic part
    planner_agent = build_planner_agent(...)
    result = await Runner.run(planner_agent, input_text)
    return result
```

`handle_missing_instruments` plain Python hai: dekhta hai kuch tag hona baaki hai kya, hai toh **tagger Lambda function** ko call karta hai (jo tagger agent chalata hai).

> **Bada lesson**: Yeh ek **agentic workflow** hai (code-orchestrated), not **autonomous agent architecture**. Jab kaam better code se orchestrate hota hai (deterministic loop), toh code use karo. Jab "kaunsa agent kya kare" autonomous decision chahiye, toh tools/LLM use karo. Dono ko mix karna pro design hai.

---

## 📋 Key Concepts

| Concept | Matlab |
|---|---|
| **Charter** | Simple agent — instructions + model only, JSON charts generate karta hai |
| **Retirement** | Simple agent (empty tools), heavy input-prep + Monte Carlo simulation |
| **Tagger** | Structured outputs — `output_type=InstrumentClassification` (Pydantic) |
| **Reporter** | `get_market_insights` tool — S3 Vectors se researcher ka data padhta hai |
| **Planner** | Orchestrator — `@function_tool` se reporter/charter/retirement call karta hai |
| **`output_type` / `final_output_as`** | OpenAI Agents SDK ka structured-output idiom |
| **`@function_tool`** | Function ko agent tool mein convert karne wala decorator |
| **`RunContextWrapper`** | Functions ke beech job ID share karne ka clean way (globals nahi) |
| **`bedrock/<id>` + AWS_REGION_NAME** | LiteLLM ko Bedrock par point karne ka tarika |
| **Agentic workflow vs autonomous** | Tagger = code loop; reporter/charter/retirement = LLM-driven tools |

---

## 💼 Backend Dev Ke Liye Note

Sabse important takeaway backend dev ke liye: **"when something should be code, write code."** Untagged instruments ke liye ek deterministic `for` loop ko LLM-driven tool-call mein convert karna anti-pattern hai — predictable, cheap, testable kaam ko mehenge non-deterministic LLM call mein wrap karna. Yeh wahi judgment hai jo tum daily lagate ho: kya yeh business logic hai (code) ya genuinely fuzzy decision (LLM)? `RunContextWrapper` ka globals-over-context rejection bilkul request-scoped context vs global mutable state ka classic backend debate hai — concurrent invocations mein global state race conditions deta hai, isliye context-passing right hai. Aur "Claude over-engineered, maine pare back kiya" — yeh code review discipline hai: AI-generated code ko utni hi scrutiny do jitni kisi junior dev ke PR ko; tools/tests/complexity jo justify na ho usse hatao. Confident-sounding code != correct code.

---

## ✅ Takeaway

- **Charter + Retirement** = simple agents (no tools, no structured outputs); **Tagger** = structured outputs; **Reporter** = ek tool; **Planner** = orchestrator with 3 tools
- Bedrock connect: `LitellmModel("bedrock/<model-id>")` + `AWS_REGION_NAME` env var (LiteLLM docs)
- **Tagger** ko planner ki autonomous loop mein nahi, plain Python `handle_missing_instruments` workflow se chalaya jaata hai — "when it should be code, write code"
- **AI-generated code ko critically review karo** — Claude ne charter + retirement ko over-engineer kiya tha; simplicity zyada reliable nikli
- `RunContextWrapper` se job ID pass karo, globals se nahi — clean, concurrent-safe context-passing

---

<details>
<summary>📜 Full Transcript (English)</summary>

Okay. How did that homework assignment go? Let's let's go through together and see if you got this right. So we'll start with one of the easiest ones I think charter. That's a pretty simple one making JSON charts. Let's have a look at the agents and have a look at this. Uh, so uh charter has this, this create agent function that gets everything set up. And basically if you look through this, you'll see that it doesn't use tools or structured outputs. If you look through this and compare it with the lambda handler, you'll see at the end of this that basically this is a really simple agent that just has instructions and a model. There's nothing. And that's because all we need this to do is to generate charts in JSON format. And we can describe that. Well, now I'll tell you, I use Claude code to generate a lot of this code. And this was an example of where Claude code did a horrible job. Claude code Massively overengineered this and built something super complex with with both tools and structured outputs and with with lots of extra complexity. And the tools were really complicated themselves, and it took me a while to figure out everything that it had done, and to pare it back to the simplicity that was needed, which was just to take some instructions and generate the right JSON, which turned out to be really easy and really reliable. So it's a great example of how you can use Llms to generate code, but you need to watch what they do carefully and critically, and they can be so confident when they generate code and generate tests and declare success. And it's up to you to go back and check. And and honestly, they often make a big meal of it. And you need to be to be aware of that and watch out for it. So I had to rewrite a bunch of this and pare it back. And that is the new charter, which is nice and simple and it works. And then you probably saw the other one that was pretty simple is retirement. If we go into retirement to Agent Pie, you'll see that there's quite a lot more here to prepare the inputs for retirement and to build like a really, uh, important context, which contains a lot of information and does like a simulation and so on. But aside from that, the agent itself is a perfectly simple agent. It doesn't have any tools and it doesn't have any structured outputs. No tools, empty tools. Uh, and that's really all that there is to this agent. Uh, and if we go back to Lambda handler, we'll see where that agent actually gets created and gets used. Uh, sorry. Back up here. Um, and, uh, yeah, there we go. It's just a retirement agent, and it takes a model and the tools are empty. And again, I will tell you, this is another example of where Claude Code went to town with this one, and I had to reel it back and make it significantly simpler. One other thing I will mention, actually, while I'm here is that, uh, the, uh, it's worth taking a quick look at the code to to integrate with bedrock. Uh, we take the bedrock region, uh, and, uh, we then this is how you you set the light level model with OpenAI agents SDK, and we pass in bedrock slash and then the model ID, and that is what we use to make sure that OpenAI agents SDK talks to bedrock. So just check out this code here if you're interested in how that works. And you need to know that AWS region name is the environment variable, that light LM expects to be your bedrock region. And all this is documented on On Light Lm's page through OpenAI agents SDK. So it's all just by following the docs, but it might be worth checking this out at some point. So as I say, this is also a simple agent. And again, Cloud Code made a meal of it. It built a tool to be called to retrieve the different, uh, Monte Carlo simulations. And I had to say to it, this is always in the context you're looking at data, that's always going to be in the context. So there's no point to have a tool. I asked the question, is there a point in having a tool that you call back and then include that in the context if you're always going to be using the tool? And the answer is no. As a side note, I have to say, as I'm, I'm a I'm a super friendly person. I'm very amiable and don't often get annoyed with people. But for some reason Claude Code brings out this monster, this demon in me. I don't know if you've had the same experience, if it's just me, but I get I get really angry with Claude code when it does something, particularly when it when it forgets and does the same mistake again. Like like making, like making a meal out of these agents. I really lost my temper. So I. Hopefully you don't have the same experience as me, but as as you'll see, some of what Claude code does is magical later. But with this stuff, it overengineered it a lot. Anyways, moving on. Next up we're going to look at tagger. And tagger is an example of one that uses structured outputs. So you can see that we've got a we create our agent our instrument tagger and we call runner run. But we pass sorry. When we're creating the agent we pass in an output type of instrument classification. And when we return result it's returned at final output as. So this is the idiomatic OpenAI agents SDK way of doing structured outputs. That's what we're using to force this model, this agent, to produce information that conforms to this JSON spec instrument classification. And if you look back up here, you will see that this this spec allows us to generate something which is going to be, uh, the perfect way to, to do things like allocate, uh, a sector against a different financial instrument. So we're going to allow, uh, the intelligence, the smarts of the model to correctly tag these different instruments. Now as to make this more efficient or have more expertise. You could of course equip it with a with with, say, a polygon IO, MCP server that would allow it to be able to to query polygon and do the looking up. That would be a pro move and should you wish to, it would be great to do that. Of course you'd have to move from this being Lambda to being app runner in order to be able to spawn that MCP server, but you know how to do that from from last week. So by all means, you could take that on as a really cool challenge. But for this, I'm just relying on the fact that Nova has enough expertise to be able to tag instruments on its own using structured outputs. And now we're going to the reporter agent. Let's go to this one. And reporter agent you'll see is one that is going to have a tool I believe. There it is. The tool is called Get Market Insights. And you might be wondering what what that tool does. Of course that's going to be the tool that's going to query our S3 vectors to get insights about what's happening in the market based on the information that our researcher is constantly writing in there. So that is the tool that we use for our reporter, and that is how we're connecting the dots of what we built last week with what we're building this week. But otherwise, this should be familiar to you using the same approach to connect to bedrock through light. LM and we're also writing our prompts that you can read through to see how this is, uh, how this is using Nova and the tool to be able to write a report about your financial prospects. And then last but definitely not least, is the planner. This is the one that brings it all together. So this has a it uses tools extensively. It has a series of uh of function tools. This is using the open AI agents SDK decorator function tool to turn a function into, into a tool that you can call. It builds the JSON blob associated with this function. And you can see that we've got these three functions that it's going to call for reporter, charter and retirement. Um, and you might have a little question for me there, but I'll come to that in just a second. You'll notice that what I've got here, I'm using this little trick, uh, I'm passing in this thing called the run context wrapper. And this is like, a little maybe this is one gimmick of OpenAI agents SDK that I'm using here, that you can you can look up, but this is a way that you can pass information around between the different functions. That's kind of like associated with the agent. And I use this to pass the job ID around so that each of the different functions we call can know the task that's being run. So it's sort of pro thing to do. There were there's easier hacky ways of doing it with globals, which is in fact how Claude did it the first time I did this, and I had to tell it tell it off angrily. Uh, but that's not the right way to do it. Uh, which I said with some cuss words to Claude. Uh, but instead you should use the the, the. This approach, which is nicely documented and is a clean way of doing it. But you don't need to get sidetracked by that. We want to focus on the deployments rather than the the nitty gritty of implementation. Uh, but other than that, you can see that these tools are set up reporter, charter and retirement. And then we go ahead and build our agent. So the thing that you're probably thinking is, okay, but those I see three agents listed here. And I thought that you said that there were four agents that the planner was calling. What's happened to tagger? And the answer is, well, actually, the way we handle that is a bit different. I will show you that now. So here's the thing. These three tools we're equipping our planner agent with is allowing it to be autonomous in its planning for the activities that the agents will take care of. It's going to figure out does it want to call the reporter? Does it want to call the charter and then the retirement planning and do it as it wishes as the overall orchestrator of this activity. In addition to this, we want to look in the database at any instruments that are missing being being tagged by things like their geography and their different types of financial instrument that they are. And we're going to want to call the tagger agent for each of them. Now that's quite a complicated loop. And it's something which feels like it should be Python code. So it makes more sense just to write that as Python code outside the scope of this runner run. Let me show you. If I go to lambda handler dot pi, I'm now in the actual in the function run orchestrator that actually runs this. And you'll see here is that the part that does the, the, the the builds the agent and then does the runner run. But before that there's this line up here that runs handle missing instruments. And that is just a Python call and handle missing instruments in and agents. If we go to handle missing instruments, it's up here somewhere. Here it is. Handle missing instruments. It's just a bunch of Python code that looks through and sees if anything needs to be tagged. And if it does need to be tagged, then it calls the tagger lambda function, which will call the tagger agent. So this is an example of an agent workflow, not an agentic AI or autonomous agent architecture. It's just an agentic workflow. We're just doing that for the tagger purposes, and it's a great example of when you have something that that is better orchestrated by code, then you should do it that way. So for the tagging of instruments, we orchestrate by code. And when it comes to the autonomous part of this, the figuring out which agent is going to do what, that part is orchestrated autonomously through tools. And if you didn't follow all that, it really doesn't matter. I just wanted to give you some insight into the decisions that I made as I built out this genetic architecture.

</details>
