# L111 — Advanced LLM Observability with Langfuse and Production Guardrails

> **Week 4 · Day 4** · ⏱️ ~10 min

---

## 🎯 TL;DR

Observability ek naya discipline hai — "monitoring on steroids" — jo agents ke andar deep insights deta hai. Is lecture mein hum **Langfuse** (ek popular open-source observability platform) set up karte hain Alex financial planner ke liye, Terraform vars mein API keys daalte hain, aur dekh te hain ki Ed ne kaise ek `observe` wrapper + ek **LLM-as-a-judge** (`judge` module) backend mein chhupa rakha tha.

---

## 🗣️ Hinglish Explanation

### Observability kya hai — aur monitoring se kaise alag hai

Pehle samajhna zaroori hai ki **observability** kya cheez hai. Ed ise bolte hain *"monitoring on steroids"* — yaani normal monitoring se kaafi aage. Yeh ek naya discipline hai jo specifically **agents ko monitor** karne ke context mein ubhar ke aaya hai.

Difference samjho:
- **Monitoring** → predefined metrics dekhna: CPU, memory, error count, latency. Tum pehle se jaante ho kya measure karna hai.
- **Observability** → system ke internal state ko uske external outputs (logs, traces, metrics) se infer karna. Tum *unknown-unknowns* bhi pakad sakte ho — yaani aise problems jinke baare mein tumne pehle socha hi nahi tha.

Agents ke liye observability ka matlab: **har LLM call, har tool invocation, har agent-to-agent conversation** ka deep insight. Tum dekh sakte ho:
- **Performance** — kaun sa agent kitna time le raha hai
- **Model drift** — model ka behavior time ke saath badal raha hai kya
- **Token usage / cost** — kitne tokens kharch ho rahe hain
- **Conversations** — agents aapas mein kya bhej rahe hain, inputs/outputs kya hain

Hum already thoda observability dekh chuke hain — **OpenAI Traces** application, jo OpenAI Agents SDK ke saath aata hai. Lekin ek aur richer platform hai jo bahut popular hai: **Langfuse**. (Transcript mein "Lang Views" / "Lang Fuse" bola gaya — wo actually **Langfuse** hai.) Ed bolte hain agar tumne pehle **MLflow** ya koi aur tool use kiya hai toh wo bhi is category mein aate hain, par Langfuse ek bahut hi loved platform hai.

### Langfuse account set up karna

Langfuse ek **open-source LLM engineering platform** hai. Sign-up flow:

1. Langfuse website kholo → **Sign Up** button dabao (agar account nahi hai)
2. Sabse pehle ek **organization** banao — defaults ke saath chal jaayega
3. **Free plan** select karo — yeh important hai, paisa nahi lagana
4. Ek **project** banao — naam `alex-financial-planner` (ya jo bhi pasand ho) rakho
5. Project banne ke baad **home screen** par pahunch jaaoge

Ed home screen jaanboojh kar nahi dikhate — bolte hain *"it will give too much away"* — wo chahte hain tum khud explore karo.

### Teen API keys — bottom-left Settings se

Langfuse ke andar (bottom-left → **Settings** → **API Keys**) teen cheezein milengi:

| Key | Prefix | Kaam |
|---|---|---|
| **Public Key** | `pk-...` | Client-side identification |
| **Secret Key** | `sk-...` | Server-side authentication |
| **Host** | URL | Langfuse server ka address (cloud region ke hisaab se badalta hai) |

⚠️ **Gotcha:** UI mein keys ulte order mein dikh sakti hain — yaani secret key pehle aur public key baad mein. Toh **dhyaan se** — public key hamesha `pk` se shuru hoti hai, secret key `sk` se. Ed khud admit karte hain ki unhone yeh galat kiya tha. Galat key galat naam ke saath daal di toh sab fail ho jaayega.

### Terraform vars mein keys daalna

Ab wapas jaao apne **Terraform directory** mein — specifically **"number six agents"** wala folder (Alex ka agents stack). `terraform.tfvars.example` file mein dekho — end mein kuch variables **commented out** the. Inhe **apni real tfvars file mein** uncomment karo (example file mein nahi!):

```hcl
# terraform.tfvars  (apni real file mein, example mein nahi)

langfuse_public_key = "pk-lf-xxxxxxxxxxxxxxxx"   # PK se shuru
langfuse_secret_key = "sk-lf-xxxxxxxxxxxxxxxx"   # SK se shuru
langfuse_host       = "https://cloud.langfuse.com"  # UI mein dikhega

# OpenAI key bhi chahiye — neeche explanation
openai_api_key      = "sk-xxxxxxxxxxxxxxxx"
```

### "OpenAI key kyun? Hum toh Bedrock use kar rahe hain!"

Yeh ek interesting gotcha hai. Hum Bedrock + **Nova models** use kar rahe hain (AWS ke apne LLMs), phir bhi **OpenAI API key** chahiye. Kyun?

Kyunki hum **OpenAI Agents SDK ki tracing functionality** use kar rahe hain — wo tracing infrastructure hi Langfuse tak data bhejti hai. Toh framework ko OpenAI key chahiye apne tracing pipeline ke liye, chahe actual LLM calls Bedrock par ja rahe hon.

Achhi baat: **paisa nahi lagega**. Ek free OpenAI account banao, API key nikalo — **minimum balance ki bhi zaroorat nahi**. Ed bolte hain *"not a dime, nada"*. Key sirf logging/observability ke liye chahiye, billing ke liye nahi.

### Ed ki "mischievousness" — chhupa hua `observe` wrapper

Ab Ed apni "shararat" reveal karte hain. Agar backend ke agent folders dekho (jaise `planner`, `reporter`, etc.), toh har ek mein ek module hai: **`observability`**. Yeh module Langfuse ko set up karta hai — **lekin sirf tab jab `langfuse_secret_key` Terraform environment variables mein maujood ho**. Pehle tumne keys set nahi ki thi, isliye saara observability code **chup-chaap ignore** ho raha tha. Ab keys daal di toh activate ho jaayega.

Andar kaise kaam karta hai:
- **OpenAI Agents SDK** ka tracing use hota hai as a **pass-through** — pehle OpenAI Traces ko, phir aage **Langfuse** ko log karta hai
- OpenAI Agents SDK ki docs mein yeh setup describe kiya hua hai — *"a little bit of a dance"*, thodi awkwardness hai
- Tumhe **Logfire** set up karna padta hai — yeh **Pydantic AI** ka ek open-source library hai — aur Logfire ko bridge ki tarah use karke data Langfuse tak pahunchta hai
- Ed bolte hain yeh code **unhone khud likha** (agent se nahi banwaya) — par tum bas reuse kar sakte ho, kaam karta hai

### `with trace` vs `with observe` — Lambda handler mein

Lambda handler mein do cheezein hain:

```python
# OpenAI Agents SDK ka built-in tracing — OpenAI Traces ko log karta hai
with trace("planner-orchestrator"):
    ...

# Ed ka wrapper — Langfuse ko behind-the-scenes set up + configure karta hai
with observe():
    # jo bhi yahan hoga wo Langfuse mein output hoga
    ...
```

- `with trace(...)` → OpenAI Agents SDK ke saath aata hai, automatically sab kuch **OpenAI Traces** ko log karta hai
- `with observe()` → Ed ka custom wrapper. Bas isse wrap kar do, aur Langfuse automatically set up + configure ho jaata hai, aur saara output Langfuse mein chala jaata hai

Ed proud hain is design pe — *"I think it's neat"* — kyunki yeh Langfuse output karna bahut simplify kar deta hai.

### Ek "evil" `time.sleep` — Lambda + background threads ka problem

`observe` wrapper ke end mein ek thoda **hacky** cheez hai: ek `time.sleep`. Production code mein `time.sleep` daalna common nahi hai, par yahan zaroori tha. Yeh `finally` block ke baad aata hai — yaani Lambda execution ke bilkul **end** mein chalta hai.

```python
try:
    # agent ka kaam
    ...
finally:
    # cleanup
    ...
# end mein — observability ko flush hone ka time dena
if langfuse_enabled:
    langfuse.flush()       # gracefully bhejne ki koshish
    langfuse.shutdown()    # graceful shutdown
    time.sleep(SOME_SECONDS)  # hacky par zaroori
```

**Problem kya hai?**
- **Lambda** ek process spin karta hai tumhara kaam karne ke liye
- Kaam khatam hone par AWS **turant abruptly** us server ko band kar deta hai — yeh hardware ke liye efficient hai (sirf jitna compute use kiya utna pay)
- **Lekin** observability ek **alag background thread** mein chalti hai jo log messages pump karti rehti hai
- Agar AWS process ko beech mein hi kaat de, toh observability ka data feed ruk jaata hai — messages Langfuse tak nahi pahunchte

`flush()` aur `shutdown()` graceful shutdown ke liye recommended hain, par Ed ko wo akele reliably kaam nahi kar paye — isliye saath mein `time.sleep` bhi daalna pada. Yeh sirf **Lambda services ke end** ko affect karta hai (thodi extra delay), aur tabhi hota hai jab Langfuse settings on hain.

### Guardrails — `judge` module (LLM-as-a-judge ka seed)

Ab elegant part. Ed ne ek agent par extra guardrail laga — **reporter agent** (kyunki yeh shayad sabse important hai). Iske liye ek module banaya: **`judge`**.

`judge` ek simple **LLM call with structured outputs** hai. Ed ne ise bhi khud likha (agent se nahi) — backend stuff mein structured output reliably khud likhna easy hai.

```python
from pydantic import BaseModel
from agents import Agent, Runner

# Structured output — judge isi format mein respond karega
class Evaluation(BaseModel):
    feedback: str   # rationale PEHLE — explainable AI ke liye
    score: int      # 0 se 100

EVAL_INSTRUCTIONS = (
    "You are an evaluation agent that evaluates the quality of a "
    "financial report from a financial planning agent. You'll be "
    "provided with the instructions that were sent to the analyst "
    "and its output, and you must evaluate the quality."
)

async def evaluate(instructions: str, task: str, output: str) -> Evaluation:
    judge_agent = Agent(
        name="Judge",
        instructions=EVAL_INSTRUCTIONS,
        output_type=Evaluation,   # classic structured outputs
        model=...,                 # Bedrock Nova etc.
    )
    prompt = (
        f"Original instructions: {instructions}\n"
        f"Task sent to analyst: {task}\n"
        f"Output produced: {output}"
    )
    result = await Runner.run(judge_agent, prompt)
    return result.final_output   # Evaluation object
```

Key design choices:
- **`feedback` before `score`** — Ed ka classic trick. Model ko pehle apna **rationale** dene ko bola jaata hai, phir score. Isse **explainable AI** milta hai: hum dekhenge score *kyun* diya gaya
- **`output_type=Evaluation`** → structured outputs guarantee karta hai ki model isi Pydantic format mein respond karega
- `evaluate()` ko teen cheezein milti hain: original **instructions**, original **task**, aur **output** jo aaya — aur wo ek `Evaluation` object lautata hai

Yeh hamara **judge** hai jo kisi pichle agent ke response ko investigate kar sakta hai. Next lecture mein dekhenge ise actually use kaise karte hain (LLM-as-a-judge pattern + guardrail).

---

## 📋 Key Concepts

| Concept | Matlab |
|---|---|
| **Observability** | "Monitoring on steroids" — system ke internal state ko logs/traces/metrics se infer karna; unknown-unknowns pakadna |
| **Langfuse** | Popular open-source LLM observability platform (transcript: "Lang Views/Fuse") |
| **OpenAI Traces** | OpenAI Agents SDK ke saath built-in tracing app |
| **MLflow** | Ek aur ML observability/tracking platform (alternative) |
| **Public/Secret/Host keys** | Langfuse credentials — `pk-`, `sk-`, aur server URL |
| **`with observe()`** | Ed ka custom wrapper jo Langfuse ko auto set-up + configure karta hai |
| **`with trace(...)`** | OpenAI Agents SDK ka built-in tracing context |
| **Logfire** | Pydantic AI ki open-source library — Langfuse tak data pahunchane ka bridge |
| **`time.sleep` hack** | Lambda ke end mein observability background thread ko flush hone ka time dena |
| **`judge` module** | LLM call with structured outputs — kisi report ki quality evaluate karta hai |
| **Structured outputs** | `output_type=PydanticModel` — model ka response guaranteed format mein |
| **Explainable AI** | Score se pehle rationale/feedback maangna — taaki score ka reason pata chale |

---

## 💼 Backend Dev Ke Liye Note

Backend dev ke liye observability ek familiar concept hai — yeh **distributed tracing** (Jaeger, OpenTelemetry, Datadog APM) ka LLM-world version hai. Jaise tum ek HTTP request ko microservices ke beech trace karte ho with spans, waise hi yahan har agent call ek span/trace banta hai. Langfuse = LLM-specific APM. `with observe()` wrapper bilkul ek **context manager / middleware** jaisa hai — tum business logic ko ek tracing context mein wrap kar dete ho, jaise Flask/FastAPI mein request-scoped instrumentation.

Do production lessons jo seedhe transfer hote hain: (1) **`langfuse_secret_key` ki presence se feature toggle** — yeh classic **feature-flag-by-env-var** pattern hai; code hamesha shipped rehta hai par activate tabhi hota hai jab config maujood ho. (2) **Lambda background-thread flush problem** — serverless mein koi bhi async/background work (telemetry, log shippers, fire-and-forget tasks) tab khatra hai jab runtime abruptly freeze/kill kar de. Yahan `flush()` + `shutdown()` + `time.sleep` ka jugaad hai; real-world mein yeh **graceful-shutdown / SIGTERM handling** ka problem hai jo har stateless container/Lambda mein dekha jaata hai. `judge` module = ek **validation layer** jo response ko user tak jaane se pehle quality-gate karta hai — bilkul jaise tum API response ke liye schema validation ya business-rule checks lagate ho.

---

## ✅ Takeaway

- **Observability ≠ monitoring** — observability deep, unknown-unknown-catching insight deta hai; agents ke liye yeh ek naya discipline hai
- **Langfuse** set up karo: free plan, organization + project banao, teen keys nikalo (`pk-`, `sk-`, host) — UI mein ulta order ho sakta hai, dhyaan se daalo
- Terraform vars mein keys uncomment karo (real file mein, example mein nahi); **OpenAI key bhi chahiye** tracing pipeline ke liye — free, paisa nahi lagta
- Ed ka `with observe()` wrapper (Logfire bridge ke saath) Langfuse output ko ek line mein simplify kar deta hai; ek `time.sleep` hack Lambda ke flush problem ko handle karta hai
- `judge` module = structured-output LLM call jo report quality evaluate karta hai; **feedback before score** = explainable AI — yeh next lecture ke LLM-as-a-judge + guardrail ki neev hai

---

<details>
<summary>📜 Full Transcript (English)</summary>

So observability is like a whole new discipline that's come up in the context of monitoring agents. It's like a way of doing monitoring on steroids. It's about having really deep insights into what's happening with your MLM activity and being able to monitor it for everything from performance and model drift and every every aspect of the performance of your agents in production. And we've already seen some observability because we've looked in the OpenAI traces application, which is like an observability platform. But there's an even richer one called Lang Views that's incredibly popular. There's a bunch of them. Maybe you have experience with MLflow or one of the others. Lang views is definitely a very popular one, I love it. Uh, let's, uh, let's have a look at it. Here it is, open source engineering platform. Uh, and, uh, let's go into this, uh, you should press the sign up button to, to join when you do. If you, if you don't already have an account because you are surely AR lang views enthusiasts like me, but if you don't, then sign up and give yourself. I think when you sign up, you first have to give it an organization. Make sure that you choose the free plan and then you pick. You have to create an organization that you can just stick with the defaults. And once you've done that, you set up a project which you can call, uh, Alex, uh, financial planner, uh, or whatever you want to call it. And once you've done that, you will arrive at the home screen and, uh, yeah, I'm not going to show you the home screen because it will it will give too much away. You'll see all the stuff right away. And I want you to to see it, experience it for yourself. So once you've done that, we'll go to the code and take a look at the changes we need to make. So within Lang views you should have been able to find I think it's on the bottom left and settings, uh, some API keys. And in particular there are three API keys. There is the Lang views public key, the lang views secret key, and the Lang views host. And the public key begins PK and the secret key begins SK. And I think that they might appear the other way up. It might start with secret key in the UI. So just be absolutely sure that you put the right key with the right name. Public key begins PK. So what we're going to do now is go back into our Terraform directory for number six agents. We're going to go back to that again. And if you look in your Terraform vars if I go to the example file, you'll see at the end there that there were a bunch of these variables that were commented out. And you should uncomment them and uncomment them in the real file, not in the not in the example file, but in your file. Right? Right here. Uncomment them and in your public key put in the Pq1 you see, I see. Be sure this is the one that starts PK. Uh, you're probably guessing I got this wrong. Uh, and then langfield secret key. Get that? The one that starts SK and then the host. And for me, it's, um. Make sure you know what that is. It shows it in the UI? And then one other little gotcha is that you also need an OpenAI API key. And you might say what? Why is that? We're not using OpenAI. We're using bedrock and we're using Nova models. Well therein is a story. We are still going to be tracing using OpenAI agents, SDKs, tracing functionality, which is going to send it on to Lang Views. Uh, and you need to have an OpenAI API key, but you don't need any money on the account you can have. It's completely free. Set up an OpenAI account if you don't have one already. Uh, for free, get an API key. You don't need even the minimum balance. Nothing. Nada. Uh, and be able to put in your API key in here as well. And it won't cost a dime. Uh, it will be there and important for our logging, for our observability. So first, come in and make all of those changes, and then I will see you back here. Next, I have to show you what I've done. And you've got a little. You've caught wind of this in a couple of places. You've seen my mischievousness. Uh, so if we look in back end and we look at the different agent folders, like we take our friend planner, you'll see that in each one there is a module called observability. Uh, and it's something which, uh, has allowed us to set up lang views and to observe that lang views is set up, and it only does it if the lang views secret key is in the Terraform environment. Variables. So because you hadn't set it up until now, all of this code was ignored. And now the we are using OpenAI agents SDK and we're using, uh, that as a sort of pass through to then log to Lang views. And you'll find that OpenAI agents SDK has docs that describes how to do this on their, on their website. It's a little bit of a dance. Uh, we're going you have to, to, to a little bit of awkwardness. You have to set up something called Log Fire, which is an open source library from pedantic AI. Um, and use Log Fire as your way to get these, these, uh, this information to Lang views. So there's a little bit of gumph in here. You don't need to worry about it too much because you can just reuse this. This works, which is great. Uh, and this wasn't written by an agent. I had to write this myself. Uh, and what it means that you can do is if we then go to lambda handler with this in place, what we we we have. So we already have, uh, this with trace planner orchestrator. This this is something that comes with OpenAI agents SDK. It means that we're immediately logging everything to the OpenAI traces. But if we take anything that we do and we wrap everything in with observe, then that has set up lang views behind the scenes, and that will make sure that this all gets outputted to Lang views. So just by virtue of the fact that we have with observe like that and that's bringing in this this observe right here that automatically sets up and configures lang views for you. So so I wrote this little piece here. I think it's neat. And it means that it really simplifies your ability to be outputting to lang views. Now there is one thing about this that is a little bit a little bit hacky, uh, which is at the end here, you'll see there's something quite, quite evil a time. It's not common to put time.sleep in production code, but it turned out that this was required in this case, and this is coming after a finally, which means this is something that happens at the very, very end of your lambda executing. And why, you may wonder, is there a time.sleep in here? And the reason is because lambda, when it runs, it's something that starts up a process to carry out what you need to do. And at the end of it, AWS immediately stops abruptly stops that server from running and the that's of course very efficient for your hardware. And you only you only pay for the compute that you use. The problem is that observability is something that happens in another thread in the background pumping log messages. And if Amazon cuts it short, then it can stop this feed of data that's coming from your observability framework. Now there are some recommended things to do like flush and shutdown. That's meant to allow it to shut down gracefully, but I wasn't able to get that to work reliably without also having a sleep in there too. So this is a little bit hokey. It only affects the end of the Lambda services. It's just an extra delay I put in there. It only happens if you've got the long fuse settings set on, but if you do, it will take a little bit longer to make absolutely sure that it gets to write out all of the messages. That's all that's going on. You can look the other way now. Nothing to see here. So sure, I was a bit hacky with that time.sleep, but you're going to forgive me because I did something quite elegant and nice when it comes to guardrails. So I picked one of the agents. I picked the the reporter agent because it's perhaps the most important of them. And I put in some extra stuff here, beginning with judge. Judge is a very simple module that I wrote this one myself because it was it was quicker. And with this back end stuff it's more reliable, I find, to do it myself than to use code. Uh, so this is simply an LM call with structured outputs. So I want judge to respond with an evaluation. This is a pedantic class that I create and it has feedback. And then a score where score is from 0 to 100. It's feedback on it's going to be given, uh, what was sent to another agent. And the response and it's going to give its feedback and its score. And as the trick that I mentioned before, I'm asking it for its feedback, for its rationale, before it gives the score. And that way we have explainable AI. We're going to see a score and we're going to know why it gave the score that it did. And then this is my my main function evaluate. It is given some original instructions a task and the output. And it comes up with an evaluation as a result of that. And so I say as the instructions, you're an evaluation agent that evaluates the quality of a financial report from a financial planning agent. Uh, you'll be provided with the instructions that were sent to the analyst and its output, and you must evaluate the quality. And so it's given the original instructions, the original task and the output that came back. And it responds. It's given the output type must be evaluation. And then uh, here I have results. Final output as an evaluation object that is classic structured outputs. Making sure that the model will respond in this format. And this is our way of having a judge that's able to investigate a prior agent response. Now let's see how we actually use this judge.

</details>
