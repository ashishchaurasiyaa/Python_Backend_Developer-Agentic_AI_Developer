# L118 — Building Production AI Agents with Amazon Bedrock AgentCore

> **Week 4 · Day 5** · ⏱️ ~11 min

---

## 🎯 TL;DR

Amazon Bedrock AgentCore ki terminology demystify: yeh teen cheezein hain — **AgentCore** (5 services + 2 tools ka umbrella), **AgentCore SDK** (Python runtime wrapper jo kisi bhi agent framework ko wrap karta hai), aur **AgentCore Starter Toolkit** (CLI scaffolding/deploy tools). Plus **Strands** (Amazon ka lightweight open-source agent framework). Final lab mein hum Strands + AgentCore se ek **single-agent-with-a-loop** toy banayenge.

---

## 🗣️ Hinglish Explanation

### AgentCore ka confusing naam — teen cheezein

Ed shuru se clarify karta hai — **Amazon Bedrock AgentCore** actually **teen alag cheezein** hai jo ek naam ke neeche aati hain.

#### 1. AgentCore (the umbrella)

Pehla part bas **AgentCore** kehlata hai (abhi `AgentCore (Preview)`, jaldi sirf AgentCore / Bedrock AgentCore). Yeh purane **Bedrock Agents** ko replace karta hai — woh ab gaya, ab AgentCore hai.

Yeh ek **suite of services** hai — ek umbrella name jiske neeche bahut saari cheezein milke AgentCore banati hain. As of now:

- **5 AWS services**
- **2 managed tools** jo tum apne agents ko de sakte ho

(Bahut new hai, toh jab tum dekho tab aur services/tools ho sakte hain.)

#### 2. AgentCore SDK

Dusra part — **AgentCore SDK**. Jab koi "AgentCore" bole, context ke hisaab se woh SDK ki baat kar raha ho sakta hai (par normally "SDK" suffix lagta hai). Yeh ek **Python runtime library** hai jo tum use karoge agents banane ke liye jo AgentCore mein run honge.

Crucial point: **yeh agent framework nahi hai**. Yeh ek **lightweight wrapper** hai jo **kisi bhi agent framework ko wrap kar sakta hai** — OpenAI Agents SDK, Google ADK, CrewAI, LangGraph, jo bhi. Phir woh AgentCore ka part ban jaata hai agar tum AgentCore SDK use karo.

Ed analogy deta hai: yeh **AutoGen Core** jaisa hai (Agentic course se) — AutoGen ab kam discuss hota hai, par AgentCore yahan kuch similar try kar raha hai — ek **framework-agnostic wrapper** jo agents ko AgentCore par dalne ke liye hai.

#### 3. AgentCore Starter Toolkit

Teesra part — **Amazon Bedrock AgentCore Starter Toolkit**. Yeh ek **CLI** (command-line interface) hai — jaise `aws configure` ek CLI tool hai. Yeh commands ka set hai jo:

- AgentCore ke around **scaffolding / plumbing** lagata hai
- Tumhare agents ko AgentCore par **deploy** karta hai
- AgentCore par agents ko **operate / run** karta hai

Toh yeh saare command-line utilities hain jo AgentCore ke around banaye gaye hain.

```bash
# AgentCore Starter Toolkit CLI ka flavour (concept)
agentcore configure      # scaffolding set up
agentcore launch         # agent ko AgentCore par deploy
agentcore invoke         # deployed agent ko run/test
```

> **Recap:** Teen cheezein — **AgentCore** (5 services + 2 tools), **AgentCore SDK** (AutoGen-Core-jaisa Python wrapper), **AgentCore Starter Toolkit** (CLI scaffolding/deploy). Agar koi "AgentCore" bole, teeno mein se kuch bhi ho sakta hai — clarify karna padta hai.

### ⚠️ Pricing — zaroor dekho

Ek **pricing page** hai jise Ed strongly urge karta hai dekhne ke liye. Abhi **free** hai kyunki preview mein hai, par sirf kuch hafton ke liye. Tum tak pahunchte-pahunchte almost certainly **paid** ho chuka hoga. Ed ko nahi pata exact pricing kya hogi, isliye **khud check karo** — costs surprise na karein. Aaj sirf chhota fun project banayenge, par costs par hamesha nazar.

### Strands — Amazon ka agent framework

Ek aur terminology — **Strands** (full name: **Strands Agents**). Yeh **Amazon ka apna agent framework** hai — real ek. **OpenAI Agents SDK jaisa** hai, aur actually bahut similar dikhta hai.

Ed apni preference batata hai: woh OpenAI Agents SDK ko pasand karta hai kyunki woh **lightweight aur simple** hai. Strands bhi waisa hi hai — lightweight aur simple, agar kuch toh aur bhi zyada lightweight/simple. Ek aur step aage le gaye. Bahut easy to work with, **low barrier to entry**. Similar to OpenAI Agents SDK aur Google ADK.

Interesting note: AWS ne Strands ko **Amazon/AWS/Bedrock branding nahi di** — yeh "Amazon Bedrock Strands Agents" nahi, bas **"Strands Agents"** hai. Website par bhi bas Strands Agents, koi framework branding nahi. Lagta hai AWS chahta hai Strands ek **plain open-source agent framework** lage, AWS ka commercial offering nahi.

Aur AWS emphasize karta hai ki AgentCore **Strands ke saath acche se kaam karta hai par Strands zaroori nahi** — OpenAI Agents SDK, LangGraph, CrewAI, Google ADK kuch bhi chalega. Even **bina kisi LLM ke** — sirf Python code ke beech conversation ke liye bhi AgentCore use kar sakte ho (phir se AutoGen Core jaisa — agents ke around production scaffolding jo ek-doosre se communicate karte hain).

Aaj ke lab ke liye hum **Strands** use karenge taaki ek alag agent framework dekho.

### 5 Services aur 2 Tools — detail

Ab Ed har service explain karta hai (as of today):

#### Services

1. **Runtime** — yeh service tumhara **agent code leta hai aur usko deploy + run manage** karta hai, doosre agents se connect karna aur unke beech messages bhejna. Yeh hi **core scaffolding** hai poore agent deployment ke around

2. **Identity** — **IAM** tumhare liye sambhalta hai. Agents ke permissions ko **simplify** karta hai, ensure karta hai ki woh wahi kar sakein jiski permission hai — **aur kuch nahi** (least privilege)

3. **Memory** — usual **short-term aur long-term memory** manage karta hai:
   - **Short-term** = conversation history
   - **Long-term** = database mein persisted memory
   - Yeh easily karne ki tooling deta hai

4. **Gateway** — **tools** ke baare mein. Tumhe tools ko **build, deploy, discover, aur connect karne ka scale par** facility deta hai — **MCP** (Model Context Protocol) use karke. Kisi bhi existing tool ya service (jaise ek **Lambda** service) ko **MCP ke through agent ka tool** bana deta hai. Yaani functionality ko agents ke liye available banane ka aasan tareeka

5. **Observability** — AgentCore se associated **AWS mein built-in observability tooling**

#### Tools (2 managed)

Ye **paid services** hain (abhi free, jaldi paid). Ye wahi pehle do tools hain jo OpenAI ke paas the managed tools add karne se pehle:

1. **Browser tool** — agents ko online jaake cheezein karne deta hai, **browser automation** (jaise **Playwright**) ke through browser drive karna

2. **Code Interpreter** — ek tool jo **Python code run** kar sakta hai agent ke behalf par. Point yeh nahi ki agent Python *likh* sake (koi bhi LLM Python generate kar sakta hai) — point yeh hai ki yeh ek **environment** hai jahan Python code **safely, sandboxed** chal sakta hai (no doubt ek **Docker container** mein). Complete hone par result agent ko wapas pass hota hai — toh agent build + run karke problems behtar solve kar sakta hai

### AWS aur simplicity — surprising

Ed comment karta hai: bas itna hi hai AgentCore. AWS ne clearly **"keep it simple"** philosophy follow ki hai, aur yeh dikhta hai — jo AWS ke liye **unusual** hai (woh simple-keeping ke liye famous nahi). Docs mein dikhta hai ki unhone care liya hai ki yeh **quick to run aur relatively lightweight** ho. Naam complicated hain, par usse aage straightforward hai.

### Final lab teaser — single agent with a loop

Chalo test karte hain — AgentCore se kuch banayenge, ek hi din mein. Yeh ek **toy** hoga (bada project alag baat hai), par enough taaki real sense aaye.

Toy banate waqt Ed ek **insightful comparison** karega — Week 4 Day 1 par jo **agent architectures** discuss kiye the unko revisit:

- Humne **multi-agent architecture** banaya tha (Alex — definitely multi-agent)
- Iske contrast mein hai **single agent with a loop** approach
- Yeh zaroori nahi ki multi-agent se kam powerful ho — kuch situations mein ek single-agent-with-loop **outperform** kar sakta hai
- Beech mein bhi cheezein hain — **single agent with subagents** (grey area)
- Generally, ek **single agent with a to-do list** se bahut kuch ho sakta hai

Toh aaj hum AgentCore mein yahi banayenge — **single agent with a to-do list** — aur dekhenge minutes mein ho sakta hai ya nahi. Iske saath final week, final day ka **final lab** aata hai.

> **Single agent with a loop vs multi-agent:** Single-agent-with-loop ek hi LLM ko ek **reasoning loop** mein chalata hai (think → act/tool → observe → repeat) jab tak task complete na ho — ek to-do list maintain karta hua. Multi-agent mein specialized agents alag-alag roles handle karte hain aur orchestrate hote hain. Single-agent simpler, less coordination overhead; multi-agent better separation of concerns. Dono valid — task ke hisaab se choose karo.

---

## 📋 Key Concepts

| Concept | Matlab |
|---|---|
| **AgentCore** | Umbrella suite — 5 AWS services + 2 managed tools; purane Bedrock Agents ko replace karta hai |
| **AgentCore SDK** | Python runtime library — framework-agnostic wrapper (AutoGen Core jaisa), kisi bhi agent SDK ko wrap karta hai |
| **AgentCore Starter Toolkit** | CLI tools — scaffolding, deploy, aur agents operate karne ke liye |
| **Strands (Agents)** | Amazon ka lightweight open-source agent framework — OpenAI Agents SDK jaisa, bina AWS branding |
| **Runtime (service)** | Agent code deploy + run manage karta hai, agents ke beech messaging |
| **Identity (service)** | IAM/permissions simplify karta hai agents ke liye (least privilege) |
| **Memory (service)** | Short-term (conversation) + long-term (DB-persisted) memory tooling |
| **Gateway (service)** | Tools ko MCP ke through build/deploy/discover/connect; Lambda ko tool banana |
| **Observability (service)** | AgentCore se built-in AWS observability |
| **Browser tool** | Managed tool — agents online jaake browser automation (Playwright-style) karein |
| **Code Interpreter** | Managed tool — Python code safely sandboxed (Docker) run karke result wapas dena |
| **Single agent with a loop** | Ek agent + to-do list, reasoning loop mein chalta hai — multi-agent ka alternative |

---

## 💼 Backend Dev Ke Liye Note

AgentCore ke teen-part structure ko backend lens se decode karo: **AgentCore SDK** = ek thin abstraction/adapter layer (tumhare existing agent code ko ek standard interface mein wrap karta hai — bilkul jaise tum kisi vendor ko abstract karne ke liye adapter pattern use karte ho), **Starter Toolkit** = deployment tooling (CLI jo IaC/CI ka kaam karta hai — `aws configure` jaisa), aur **AgentCore** = managed runtime + sidecar services. Notice karo ki ye 5 services exactly woh production concerns hain jo tumne poore course mein manually wire kiye: **Runtime** = compute/orchestration (Lambda/App Runner), **Identity** = IAM, **Memory** = state store (Redis/DB), **Gateway** = service-to-tool exposure via **MCP** (jo basically tools ke liye ek standard RPC/discovery protocol hai — Lambda ko bina rewrite kiye tool bana deta hai), **Observability** = tracing/metrics. Yaani AgentCore tumhari poori Week 1-4 wiring ko managed primitives mein package kar deta hai. Code Interpreter especially backend-relevant hai: yeh ek **sandboxed execution environment** (Docker container) hai untrusted/generated code chalane ke liye — yeh security-critical design hai (kabhi bhi LLM-generated code ko apne main process mein eval mat karo). Aur "single agent with a loop" pattern wahi hai jo tum ReAct/agentic loop ke roop mein jaante ho — ek stateful loop jo tools call karta hai jab tak terminal condition na aaye; multi-agent se simpler hai jab tak strong separation of concerns ki zaroorat na ho.

---

## ✅ Takeaway

- **AgentCore = teen cheezein:** AgentCore (5 services + 2 tools umbrella, purane Bedrock Agents ka replacement), **AgentCore SDK** (framework-agnostic Python wrapper, AutoGen Core jaisa), **Starter Toolkit** (CLI scaffolding/deploy)
- **5 services:** Runtime (deploy/run), Identity (IAM), Memory (short+long term), Gateway (tools via MCP), Observability. **2 tools:** Browser + Code Interpreter (sandboxed Python)
- **Strands** = Amazon ka lightweight open-source agent framework (OpenAI Agents SDK jaisa, bina AWS branding) — aaj ke lab mein use hoga
- AgentCore **framework-agnostic** hai (koi bhi agent SDK, ya bina LLM bhi) — AWS ne ise unusually **simple** rakha hai
- ⚠️ **Pricing page zaroor dekho** — abhi free (preview), jaldi paid hoga
- Final lab: **single agent with a loop + to-do list** banayenge — multi-agent ka powerful alternative

---

<details>
<summary>📜 Full Transcript (English)</summary>

Okay with that introduction, let's talk about Amazon Bedrock Agent Core and start by explaining this terminology. Uh so what what is Amazon Bedrock Agent Core and what does it have such a confusing name. Uh, maybe we'll all get so used to Agent Core that it will roll off the tongue in the future. And you wonder why make such a fuss about the name? Um, so it's three different things. So the first of them is just called Agent Core. Uh, confusing. Um, and right now it's called Agent Core. Brackets. Preview brackets. Uh, but I imagine very soon it will just be called Agent Core uh, or Bedrock Agent Core. And this replaces something that used to be around called bedrock agents. That is the old thing that's gone. It's now Bedrock Agent core. So Bedrock Agent Core is it's a suite of services. It's like an it's an umbrella name for a bunch of things that together in aggregate make up agent core. And that is five AWS services SES, plus two managed tools that come along as well that you can give your agents. And again, since this is all very, very new, by the time you're watching this, there might be more services and more tools. But as of right now, as of today, it's five services, two tools, and they are the essential ones. And together that whole thing is called Agent Core. There is also something called Agent Core SDK. And depending on the context, when you say Agent Core, you might be referring to Agent Core SDK. But normally when it's talked about it has SDK after it. And Agent Core SDK is a Python runtime library that we will be using, which allows you to build agents that will run in Agent Core. Um, and so, so it's like a, an agent framework. But but it's not an agent framework. The agent Core SDK is something that can wrap any agent framework. You can build agents in OpenAI agents SDK in Google, ADK in crew in Landgraaf in any of these. And you can then have that be part of Agent Core corps. If you use the Agent Corps SDK. So it's like a lightweight wrapper around other agents. And for people who have taken my agent course, this might sound slightly familiar. And you're right, it's a similar concept to Autogen Corps. Remember that Autogen, which, uh, seems to have sort of fizzled in terms of people talking about it. It's definitely, uh, the least talked about of all of the different frameworks that I covered before. Uh, Agent Corps is maybe trying to do something similar here. It's it's like a, um, agnostic to the agent framework wrapper around agents in order to put them on agent corps. Hopefully you're with me. That is the agent corps SDK. Different to agent Corps itself. All right. And then the third thing, the third piece that makes it up is this. It's called the Agent core Starter toolkit. The Amazon Bedrock agent core starter toolkit. Uh, it's uh, so this this is a command line interface, a CLI. It's a series of commands that you type, just like AWS configure is a CLI, a command line, uh, tool. Uh, the Agent Core Starter Toolkit is a set of command line tools that puts the scaffolding. The kind of plumbing around what you're doing with Agent Core. And then it will deploy your agents to Agent Core, and it will operate your agents on agent Core so it can it can run them. So it's all of the sort of utilities, the command line utilities built around agent core. And so there they are. There's agent core itself, the five services and two tools. There is the agent core SDK, Python libraries that are a bit like Autogen core that that wrap agents, and then agent core Starter toolkit, the scaffolding tools, those are the three big pieces of of agent Core and the different bits of terminology. And if someone says Agent Core, they could be talking about any one of those three things, and you normally have to ask them to clarify, just to make sure you know exactly what they're talking about. But I guess we're all going to get used to this terminology in time, and it won't seem so. So alien. Uh, there's this page is the pricing page, and I would strongly encourage you and urge you to go and take a look at it. Right now, it is free because it's still in preview, but it's only going to be free for another few weeks. So almost certainly by the time you see this, it will no longer be free. So I don't know what the pricing is going to be. So I do urge you to go and have a look at this. We're only going to be doing something small and fun today, but nonetheless always important to keep an eye on the costs. Uh, don't let don't let it surprise you. So be sure that you're aware of the pricing. Uh, and then there's one more piece of terminology, one more thing to know about. And you might have already if you knew about this already, you're like, so why haven't you mentioned strands? So strands or the full name is strands agents is Amazon's agent framework. It's their real. It's their agent framework. It's like OpenAI agents SDK. And in fact it's very like OpenAI agents SDK. When you see it, you'll see that it's very similar. It's anyone that knows my my views on these things. Notice that I really like OpenAI agents SDK because it's lightweight and simple and strands is the same. It's also lightweight and simple. In fact, if anything, it's even lighter weight and even simpler. They've taken it another step, and so it's very easy to work with. And so for the stuff we'll do today, we will use strands so that you see a different agent framework. And it's going to be super easy because yeah it really is very very low barrier to entry. Um, and it's similar in that way to, as I said, OpenAI agents SDK and also to Google ADK. Uh, that is strands. It's interesting to note that AWS hasn't branded strands with any of with Amazon or AWS or bedrock. So it's not like Amazon Bedrock Strands agents. It's it's just called strands agents. And if you go to their website, at least as of now, it's just strands agents with without that kind of framework and branding. So they obviously I think they really want to make a thing about strands just being another open source agent framework. It's not a commercial offering from AWS, and they also go out of their way to emphasize that agent Corps works nicely with strands, but it doesn't have to work with strands. You can use Agent Core. As I already said 100 times, you can use Agent Core with OpenAI agents SDK, with with Landgraf, with crew with Google ADK. And they've got plenty of examples of all of them. In fact, you can use Agent Core without any MLM at all. You can use it just to have like conversation between Python code if you wished. As you will see, it's again rather like Autogen core. It's more of the scaffolding around agents in production communicating to each other. Okay, so what are these five services and two tools as of today that come packaged with Agent Core? So here are the services. First of all, runtime is the service that that takes your agent code and is able to deploy it and manage running the agent, connecting to other agents and sending messages between them. So it's really the scaffolding to use that word again around the whole agent deployment. Identity is the thing that takes care of IAM for you, so that you don't have to simplifying the IAM or the permissions associated with your agents, and making sure that they can do what they are allowed to do. And no more. Memory is about managing the usual short term and long term memory. The conversation history and also longer term memory persisted in a database and giving you tooling to be able to do that easily. On the subject of tooling, gateway is all about tools. It's about allowing you to build and deploy and discover and connect to tools at scale. Using MCP. It allows you to to take any existing tool or service, like like a Lambda service, and convert it into being a tool that your agent can use through MCP. So it's a way to make functionality available to your agents easily. And that is the gateway service. And then finally, observability is some observability tooling built into AWS associated with Agent Core. And Agent Core comes with a couple of tools, maybe more by the time you see this. But as for me, right now, there's two managed tools that you can use from your agents. They are, of course, paid services, so you will pay to use them. They're free right now, but they will soon be paid. And these two tools are the same as the first two tools OpenAI had before they added a bunch of managed tools. But one of them is a browser tool that lets you, uh, basically have your agents be able to go online and do things, drive a browser through browser automation software like playwright, and the other is a code interpreter, which of course is a tool that can run things like Python code on your agent's behalf. And this is again, it's not about your agent being able to build Python code, because agents can can just do that out of the box. Any LLM can generate Python. The point here is that this is an environment where Python code can be run safely in a sandboxed way. No doubt in a Docker container. And then when it completes, that result is passed back to the agent, allowing the agent to solve problems more effectively because it can build and run code. And that is all there is to agent core. And when I say that, I mean it. AWS has clearly had a philosophy of keeping things simple with this framework, and it shows. And I have to say that is unusual for AWS. They are not known for keeping things simple. It's rather the opposite to what you and I have experienced for the last couple of weeks, but I will. I will tell you that that if you look through the docs, you can see that they've taken great care to make sure that this is quick to get running and relatively lightweight. Aside from the complicated names of things, it's pretty straightforward from that point on. And let's put that to the test. Let's have a shot at building something with Agent Core and see if we can't do it all in one day. Uh, and it's going to be a toy because we're not going to have obviously it would be a bigger project to make something big, but it's going to be enough of a toy to give you a real sense of this? And I thought whilst building the toy, there's something else that we could do that I think would be really insightful and I think you'll enjoy a lot, which is to take a quick look back to the first day of this week when we talked about the different agent architectures, and I talked about multi-agent architectures, which is really what we built, which is definitely what we built this week with Alex. Um, but also that there is this, this contrasting way of approaching things with a single agent with a loop. And it's not the case that that is necessarily less powerful than a multi-agent architecture. In fact, there are some situations where it can outperform a multi-agent architecture. And there's stuff in the middle when you have a single agent with Subagents and it becomes a bit of a grey area, but but generally speaking, you can do a lot with a single agent with a to-do list. And so that is what we're going to just build now in Agent Core and see if we can't do it in a matter of minutes. And with that, that brings us to the final lab, the final lab on the final day of the final week. Let's go do it.

</details>
