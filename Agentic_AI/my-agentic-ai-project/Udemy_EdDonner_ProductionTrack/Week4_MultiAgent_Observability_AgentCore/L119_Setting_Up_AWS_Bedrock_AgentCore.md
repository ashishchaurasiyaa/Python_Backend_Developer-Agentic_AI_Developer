# L119 — Setting Up AWS Bedrock Agent Core for Production AI Deployments

> **Week 4 · Day 5** · ⏱️ ~7 min

---

## 🎯 TL;DR

Course ka grand finale shuru — hum wapas `production` repo mein aate hain, naya `finale` directory kholte hain, aur **Amazon Bedrock Agent Core** ka one-time IAM + observability setup karte hain (Agent Access group, 3 policies, Claude Sonnet model access, observability enable). Yeh poora lecture sirf **setup** hai — coding agla lecture se.

---

## 🗣️ Hinglish Explanation

### Wapas ghar — `production` repo aur `finale` folder

Yeh course ka **last day, last lecture-block** hai. Ed humein cursor mein wapas le aata hai — usi `production` repo mein jahaan W1 mein course shuru hua tha (`ed-donner/production`, jo tumne local drive par clone kiya tha). Ab repo mein do nayi cheezein hain:

1. **`community_contributions/` folder** — students ke submissions se bhara hua (Ed ne PR-based community work invite kiya tha; finale ke baad tum bhi yahaan apna agent daal sakte ho).
2. **`finale/` directory** — yahi aaj ka playground hai. Andar ek **`README.md`** hai (repo root wale README se alag). Cursor mein ispe right-click → **Open Preview** karo taaki rendered markdown dikhe (raw markdown nahi). Yeh README humein step-by-step guide karega.

> 💡 **Pro-level instructions**: Ab tak 4 weeks ho gaye, tum AWS console ke expert ho. Toh Ed detailed clicks nahi dega — sirf high-level direction. Yeh "graduation moment" hai.

### Bedrock Agent Core kya hai (background)

**Amazon Bedrock Agent Core** AWS ka naya (preview-stage) managed platform hai jo **AI agents ko production mein deploy** karne ke liye banaya gaya hai. Concept: tum apna agent code likho, ek command chalao, aur AWS khud container build karke, ECR par push karke, App Runner-jaisi serverless runtime par deploy kar deta hai — **bina tumhe Docker/IAM/networking manually touch kiye**.

Agent Core ke main pillars (docs mein grouped hain, thoda confusing layout):

- **Runtime** — jahaan tumhara agent container actually chalta hai (serverless).
- **Memory** — persistent state/conversation memory managed by AWS.
- **Gateway** — tools/APIs ko agent se connect karne ka bridge.
- **Identity** — auth/permissions handling.
- **Observability** — traces, sessions, errors dekhne ke liye (OpenAI Agents SDK ke tracing jaisa).
- **Built-in (managed) tools** — code interpreter, browser automation jaise ready-made tools.

Ed ka honest take: yeh framework abhi **immature** hai. Marketing page par bade customers prominent nahi hain (AWS usually high-street brand names dikhata hai), aur docs apni hi terminology consistently use nahi karte — kabhi "Bedrock Agent Core", kabhi "Starter Toolkit" (URL mein bhi `bedrock-agentcore-starter-toolkit` dikhta hai). *"It's like an LLM — we need better context."*

### Step 1: One-time IAM setup

Ed ne pehle bola tha "Agent Core ko IAM ki zaroorat nahi" — chhota correction: **ek baar, beginning mein** IAM karna padta hai, phir kabhi nahi chhuna.

1. AWS console mein **root user** ke roop me sign in karo (top-right par confirm karo ki root ho).
2. Pehle **costs** check kar lo — koi surprise charges na hon.
3. **IAM** → **User groups** → **Create group** → naam `Agent Access`.
4. Is group ko **`ai-engineer` user** se attach karo (wahi IAM user jo course bhar use kar rahe ho).
5. **Teen policies** attach karo (checkboxes — thoda janky UI):
   - `AmazonBedrockFullAccess`
   - `AWSCodeBuildAdminAccess`  *(Agent Core CodeBuild se container build karta hai)*
   - `BedrockAgentCoreFullAccess`
6. Apply button dabao.

```text
IAM
 └── User groups
      └── Agent Access   (attached to: ai-engineer)
           ├── AmazonBedrockFullAccess
           ├── AWSCodeBuildAdminAccess
           └── BedrockAgentCoreFullAccess
```

> 🧠 **IAM recap (background)**: IAM = Identity and Access Management. **Users** = identities (insaan ya app). **Groups** = users ka bundle jisme policies attach hoti hain (har user ko alag-alag permission dene ke bajaye). **Policies** = JSON documents jo batate hain "kaunse AWS actions allowed hain kaunse resources par". Best practice: root user sirf account-level admin ke liye, daily kaam IAM user se.

### Step 2: Claude Sonnet 4 model access

Bedrock par foundation models **on-demand available nahi hote** — pehle access **request** karna padta hai. Agent Core internally Claude (Anthropic ka model) call karta hai, toh:

1. Bedrock console → bottom-left ke paas **"Request access to models"** button (AWS bol raha hai yeh UI jaldi improve karenge).
2. **Claude Sonnet 4** ke liye access request karo — apne primary region mein **aur** possibly **`us-west-2`** mein (preview ke kaaran kuch cheezein sirf us-west-2 mein chalti hain).
3. Approval aane par hi agent kaam karega.

> ⚠️ Yeh region quirk preview-version-specific ho sakta hai; aware raho ki agar invoke fail ho toh model access ya region check karo.

### Step 3: Observability enable karo

Ab **IAM user (`ai-engineer`)** ke roop mein switch karo (root nahi).

1. AWS console → service search → **Amazon Bedrock Agent Core** ("rolls off the tongue" — Ed ka sarcasm).
2. Left menu mein neeche **Observability** par click karo.
3. Pehli baar yeh bolega: *"Aapke paas observability access nahi hai. Enable karna chahte ho?"* — **Enable/activate** karo.
4. Yeh batayega ki activation ke kuch minutes baad hi effective hoga.
5. **Cost note**: ek checkbox hota hai jo bolta hai "sirf 1% traces sample karo" — yeh checked rakho, isse observability **free** rehta hai. (Costs verify khud karo, kyunki yeh space tezi se badal raha hai.)

Bas — IAM + config khatam. Ab coding ke liye ready.

### Reading material (optional, baad ke liye)

`finale/README.md` mein useful links diye hain:
- **Marketing page** — "Agent Core kya hai" overview.
- **User guide** — sabse useful: examples + API reference (par yeh asal mein Starter Toolkit ke baare mein hai).
- **Python SDK** docs.
- **Toolkit CLI** writeup.

### UV project setup

`finale/` folder mein Ed ne ek **UV project** pre-configured kar rakha hai. **UV** ek super-fast Python package/environment manager hai (pip + venv + poetry ka modern replacement, Rust mein likha). `pyproject.toml` mein sirf **4 dependencies** hain:

```toml
# pyproject.toml (finale/) — dependencies
dependencies = [
    "bedrock-agentcore",            # Python client library (poore platform ka naam)
    "strands-agents",               # AWS ka agent framework (W4 ka star)
    "bedrock-agentcore-starter-toolkit",  # CLI — agents up/down karne ke liye
    "pydantic",                     # structured data (needs no introduction)
]
```

- **`bedrock-agentcore`** — Python client jisse code mein `BedrockAgentCoreApp` import hota hai.
- **`strands-agents`** — AWS ka **Strands** agent framework. OpenAI Agents SDK jaisa, par aur bhi minimal — agle lecture mein dekhoge kitna simple hai.
- **`bedrock-agentcore-starter-toolkit`** — CLI jo `agentcore configure / launch / invoke` commands deta hai.
- **`pydantic`** — data validation/structured outputs.

Environment ready karne ke liye terminal mein:

```bash
# production repo se start, finale mein cd karo
cd finale
uv sync
```

`uv sync` `pyproject.toml`/lockfile padh ke saari dependencies install kar deta hai aur virtual env bana deta hai. Ed ka already synced tha toh kuch naya nahi hua — tumhara fresh download karega. **Bam — environment ready.**

---

## 📋 Key Concepts

| Concept | Matlab |
|---|---|
| **Bedrock Agent Core** | AWS ka managed platform AI agents ko production mein deploy karne ke liye (preview-stage) |
| **`finale/` directory** | `production` repo mein course ka last lab folder — apna README aur UV project |
| **Agent Access group** | IAM user group with 3 policies (Bedrock Full, CodeBuild Admin, AgentCore Full) |
| **Model access (Bedrock)** | Foundation models pehle request karna padta hai — Claude Sonnet 4, region-sensitive |
| **Observability** | Agent Core mein traces/sessions/errors dekhne ka pillar — enable karna padta hai, 1% sampling = free |
| **Strands (strands-agents)** | AWS ka ultra-minimal agent framework, OpenAI Agents SDK se bhi simple |
| **UV / `uv sync`** | Fast Python env manager; `pyproject.toml` se deps install karta hai |
| **CodeBuild** | AWS service jo Agent Core ke piche container image build karta hai |

---

## 💼 Backend Dev Ke Liye Note

Ek backend dev ke nazariye se, Agent Core ka pitch **"managed PaaS for agents"** hai — jaise Heroku/Cloud Run ne web apps ko deploy karna trivial banaya, waise hi yeh agent containers ke liye karta hai. Tum IAM groups+policies ka pattern pehchanoge: yeh classic RBAC hai — group = role, policy = permission set, user = principal. `AWSCodeBuildAdminAccess` ki zaroorat is liye hai kyunki Agent Core CI-style image build pipeline trigger karta hai (CodeBuild = AWS ka managed build server, GitHub Actions runner jaisa). Model-access-by-request waala flow ek **provisioning gate** hai — production mein quota/access ko pehle se request karna planning ka part hota hai. Aur observability ka 1%-sampling toggle classic **distributed tracing cost-control** hai (Datadog/Jaeger mein bhi sampling rate set karte ho). Abhi sab **one-time infra setup** hai — agla lecture se actual code.

---

## ✅ Takeaway

- Finale `production` repo ke `finale/` folder mein hai — README ko **Open Preview** karke follow karo
- One-time IAM: `Agent Access` group → `ai-engineer` user → 3 policies (Bedrock Full, CodeBuild Admin, AgentCore Full)
- Claude Sonnet 4 model access request karo (region/us-west-2 ke liye aware raho); Observability enable karo (1% sampling = free)
- UV project pehle se setup hai — `cd finale && uv sync` se 4 deps (bedrock-agentcore, strands-agents, starter-toolkit, pydantic) install
- Agent Core abhi immature hai (inconsistent docs, preview), par streamlined deployment ke liye banaya gaya — coding ab shuru

---

<details>
<summary>📜 Full Transcript (English)</summary>

Well, here we are back in our old friend cursor for the final time. But I have an even bigger surprise for you. We're back in the production repo where we began. We're in the repo called production that hopefully you get cloned. It's on your local drive. You can open it up. And here we are in production. The only difference you have, I hope, is that you have a community contributions folder that is brimming with submissions from students that I can't wait to see. Uh, but there is something else here. That is where we are going right now, which is that there is a directory called finale. Uh, hopefully you didn't see it before now. And now you're seeing it and you're like, oh, there's a finale. Open up the directory called finale. And there is a readme, not to be confused with the readme, a readme in finale that you should right click on and say Open Preview so that you are looking at this, the finale, the AWS Bedrock Agent core finale of the course. And uh, as always, if you're looking at it in cursor, which you should be, you need to right click and say Open Preview if you don't see it looking like this. Okay, welcome. Let's get started. The first thing we're going to do is IAM. I know I said that Agent Core doesn't have iam. There's some. There's a one step IAM we have to do at the very beginning of you using Agent Core. And then we won't need to touch IAM again. So, uh, since since you were so experienced with this. Now I don't need to give detailed instructions. I can give pro level instructions. We're going to sign in to the AWS console as the root user. Go to IAM, go to user groups. Create a new user group called Agent Access. Make sure that it's applied to the AI engineer user and attach these three policies Amazon Bedrock Full Access, AWS Code Builder Admin Access, and Bedrock Agent Core Full Access. Let's go do that right now. And here we are signed into AWS. Check up on the top right that you're in as your root. Take a quick look at the costs. Make sure there's no surprises. And then start by going to IAM are old. So we know it so well. So we're now going to go to user groups over here and you can see I've already set up agent access. You'll be pressing create Group to do this. If I open this up, you'll see that I've assigned it to the username AI engineer. And it has permissions. And here they are. It is the three that I just told you. Amazon bedrock Full Access, AWS Codebuild Admin Access, and Bedrock Agent Core full Access. So you attach the policies. You've gone something similar to this. Attach policies. You've done the three checkboxes for those three a bit janky. And then and then press the button to apply it. So with that there is then a couple more little bits of of IAM admin. Uh, the first of them is that uh, well you do you do also actually potentially need to access have request access to Claude sonnet form model in your region. Um and maybe in US west two depending exactly on how things pan out. So keep a keep aware of this. It depends on a few things. And this may be just a temporary thing right now with the preview version. But I had to request access and get access to Claude Sonnet for model, and you might do as well. And you know how to do that, right? You go to bedrock. You press that button on the near the bottom left to request access to models. Although the screen claims they're going to be improving that user interface very soon, I hope so. All right. And once you've done that, uh, the the final thing to do is to come in as your IAM user and let's go and do that right now. All right. So here we are. I'm in now as AI engineer. I come over here and I'm going to do Amazon Bedrock Agent Core. There it is. Amazon bedrock agent core rolls off the tongue. Here we are in Agent Core. That's what it looks like. You remember I told you about the, uh, the memory gateways, identity, runtime and observability and then built in tools. They've grouped them together. It's a bit confusing. Whatever. Uh, I want you to click on observability down here, and I'm not going to click on it right now because I don't want to spoil the show. But you're going to click on that. And the first screen you're going to see is, is probably going to tell you that you don't yet have access to observability. Do you want to turn it on? And it tells you that it won't be effective for a few minutes after you turn it on. But you should do that. You should activate it. There is a note about costs there. It says to me that it's free as long as I keep. I keep a box checked about only taking 1% of traces or something. So I did leave that box checked. So I believe it is free. You should do the same. You should double check that you're comfortable with any costs associated with observability, particularly as this is a changing space. So once you've done that, you've requested access to observability. That is the end of our IAM and configuration stuff. For now, we can get started. First thing I'm gonna ask you to do is do a bit of reading, just so that you're well prepared for this. This is optional. You can come back to it later, but I've got some useful links for you. There is the main, like the marketing page for Amazon which is this, this page right here, which is like the, uh, all about what it is and things. And you can see if you look down here, something I noticed is that as of now, their customers, it's not as if they have like I guess. Yeah, I suppose these are quite large, but it's not as prominent as many of AWS customers, you often see big high street names, uh, which is a sign, I think, again, that this is still an immature framework. It's not it's not got the kind of traction that others may have. Uh, then this is the user guide. This is very useful. This is this is really where you can you can live this has, uh, the user guide with all the information. It has examples and an API reference. The terminology is confusing because whilst this describes itself as the Amazon bedrock agent core, uh, this this user guide is really about the starter kit. Uh, so there is some in fact, you can even see the Bedrock Agent core Starter Toolkit is in the URL. We're in that section of their docs. So again they don't use their own terminology consistently. So it's not always clear, uh, what context you're in. It's like like an LLM we need better context. Uh, so you have to sort of figure it out from the information you're given. Again, just like Llms do. All right. Uh, so then, uh, there's a couple more links that we've got here. There's the Python SDK and the toolkit, uh, CLI write up itself, so I will let you browse around that should you wish to. Uh, and I'm then I also want to introduce you to the UV project. So I've set up a UV project in this folder. So you already have that. Uh, it's got I only added these four dependencies bedrock agent core, uh, which is the Python client library, again with the name of the whole thing, uh, strands agents, that is the AWS Agent Framework library. So we're going to play with that right now and see it. And it's really simple bedrock agent core starter toolkit that is the CLI. Those are the commands to stand things up and down and pedantic needs no introduction. Uh, so if we, uh, bring up a new terminal and we start in production, if we CD into finale, here we are. Uh, in here, you should be able to do a UV sync. And when you do that, mine's already synced, so it doesn't do anything but for you, that will then load in the dependencies and bam, you've got yourself an environment already set up.

</details>
