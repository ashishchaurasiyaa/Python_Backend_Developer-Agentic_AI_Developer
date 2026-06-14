# L112 — LLM-as-a-Judge Pattern with Langfuse Observability in Production

> **Week 4 · Day 4** · ⏱️ ~11 min

---

## 🎯 TL;DR

Reporter agent ke lambda handler mein **LLM-as-a-judge** pattern wire karte hain: judge score deta hai, hum usse **Langfuse score + event** mein register karte hain, aur agar score 0.3 (30%) se kam ho toh **guardrail** report ko block karke generic error message bhej deta hai. `terraform apply` se observability env vars roll out karke, live run chala ke, Langfuse mein traces/timeline/judge score explore karte hain.

---

## 🗣️ Hinglish Explanation

### LLM-as-a-judge pattern

Naam se hi clear hai — **`judge`**. Yeh ek classic pattern hai jisme hum **ek model ka use karte hain doosre model ki performance judge karne ke liye**. Pichle lecture mein humne `judge` module banaya (evaluate function + Evaluation structured output). Ab dekhte hain ise **reporter agent ke lambda handler** mein kaise use karte hain.

### Reporter ka lambda handler — entry point

Lambda handler reporter agent ka entry point hai. Pehle ek important cheez:

```python
from tenacity import retry, retry_if_exception_type, wait_exponential

@retry(
    retry=retry_if_exception_type(RateLimitError),
    wait=wait_exponential(...),
)
def run_reporter(...):
    ...
```

**Tenacity** ek Python retry library hai. Yahan `@retry` decorator lagaya hai taaki agar **rate limit error** aaye toh automatically retry ho jaaye. Yeh hamesha achhi practice hai — LLM APIs (Bedrock/OpenAI) rate limits hit karte rehte hain, toh exponential backoff ke saath retry karna chahiye.

### Judging logic — observability mode mein

Reporter agent run hota hai aur ek **final output** deta hai. Ab naya code:

```python
# Reporter agent chalao
result = await Runner.run(reporter_agent, task)
response = result.final_output

if observability_enabled:
    # Langfuse mein "judge" naam ka span banao
    with observe.start_span(name="judge") as span:
        # pichle lecture wala evaluate() function
        evaluation = await evaluate(
            instructions=reporter_instructions,
            task=task,
            output=response,
        )
        score = evaluation.score / 100      # 0-100 ko 0-1 mein convert
        feedback = evaluation.feedback

        # Langfuse mein score register karo (track karne ke liye)
        span.score(name="judge", value=score, comment=feedback)

        # Ek observation/event bhi banao
        observability.create_event(
            name="judge",
            metadata={"score": score, "feedback": feedback},
        )

        # ----- GUARDRAIL -----
        if score < MIN_SCORE:   # MIN_SCORE = 0.3
            log.error(f"Guard against score: too low ({score})")
            response = (
                "I'm sorry, I'm not able to generate a report "
                "for you. Please try again later."
            )
```

Step by step:
1. **Observability mode** on ho toh ek **span** banate hain `judge` title ke saath. (Span = trace ke andar ek sub-operation, jaise distributed tracing mein.)
2. `evaluate()` call karte hain — wahi function jo pichle lecture mein banaya tha — reporter ko bheji gayi instructions, task, aur uska response pass karke.
3. Jo **score** wapas aata hai (0-100), usse **100 se divide** karke 0-1 range mein laate hain (kyunki Langfuse scores aksar 0-1 mein hote hain). Aur **feedback** bhi le lete hain.
4. **`span.score(...)`** — yeh ek **Langfuse command** hai jo score register karta hai taaki hum use track kar saken.
5. **`observability.create_event(...)`** — Langfuse mein ek event/observation banate hain ki yeh judging hui.

### Guardrail — score < 0.3 toh block

Yeh hai asli guardrail:

```python
if score < 0.3:   # 30% se kam
    log.error("score too low — guarding")
    response = "I'm sorry, I'm not able to generate a report for you. Please try again later."
```

Agar score **0.3 (30%) se kam** hai, toh yeh problem hai. Hum:
- Ek **error log** karte hain ki score bahut low aaya
- Reporter agent ne jo financial report banayi thi usse **wipe out** kar dete hain
- Uski jagah ek generic message daal dete hain: *"I'm sorry, I'm not able to generate a report for you. Please try again later."*
- Yahi user ko bheja jaata hai

Toh yeh **LLM-as-a-judge + guardrail** ka classic example hai — kharab analysis ko user tak jaane se rokna, aur saath hi observability se score track + event create karna.

### Extra events — debugging/visibility ke liye

Ed ne kuch extra events bhi push kiye Langfuse mein:

```python
observability.create_event(name="Reporter started!")
observability.create_event(
    name="Reporter about to run",
    metadata={"job_id": job_id, "clerk_user_id": clerk_user_id},
)
```

- `"Reporter started!"` — ek simple event
- `"Reporter about to run"` — `job_id` aur `clerk_user_id` (Clerk authentication se user ID) ke saath

Yeh sab extra messages Langfuse mein push hote hain taaki hum sab kuch hota hua dekh saken.

### Ek aur step — `terraform apply` zaroori!

Ed ko yaad aata hai: *"Ah, not so fast!"* Test karne se pehle ek aur step:

```bash
terraform apply
# yes
```

Kyunki humne **environment variables badle** — observability on kiya + Langfuse credentials daale. Jab tak `terraform apply` nahi karte, **AWS ko iska pata hi nahi**.

Terraform ki ek khoobsurti: **sirf agents folder mein** env vars badle hain — wahi ek jagah hai. Toh us agent folder mein `terraform apply` karo, yes bolo, aur wo **sirf env-var change** turant roll out kar deta hai. Yeh kaafi fast hota hai.

### Live run — Alex front end se

Deployment complete hone ke baad **Alex** front end (jo "such a beautiful front end" hai) par jaate hain. Ed ek **bug** spot karte hain: top-right par "Last analysis: Never" dikha raha hai, jabki analysis hui thi. Wo bolte hain isse fix karenge — ya tum fix kar sakte ho, ya wo Claude se karwa lenge.

**Advisor Team** par jaake **new analysis** kick off karte hain. Ab agents run karte hain. Yeh thoda **lamba** lagta hai kyunki:
- Ed ka **`time.sleep` hack** ab active hai (~15 seconds extra flush ke liye)
- Plus har agent mein ek **10-second sleep** hai
- Total ~25 seconds extra

Result: ek nice summary, retirement projection, aur charts.

### Langfuse tour — home screen

Run khatam hone ke baad Langfuse mein:

**Home screen** par dikhta hai:
- **Retirement agent, charter agent, planner orchestrator, reporter agent** ke traces
- Traces by time — Ed ne setup ke baad **77 traces** kiye
- **Model costs: $0** — par yeh galat-sa lagta hai! Reason: **costs Bedrock/AWS mein track hote hain**, wo Langfuse tak report nahi hote. Toh cost info Langfuse mein nahi milti (shame). Par baaki sab milta hai.

### Tracing — asli action

**Tracing** section mein jaake (last 30 minutes filter karke):
- Har **row** ek alag **trace** hai (ek alag agent report)
- Beech mein wo **hard-coded events** bhi dikhte hain — "Reporter started", "Reporter about to run"
- Saare agent traces yahan dikhte hain — planner orchestrator, reporter, charter, retirement — sab abhi-abhi ke

**Charter agent** mein dive karo:
- Last row par click → **tokens in/out**, model used, inputs (prompting), output (JSON set of charts)

**Retirement agent** bhi same trickery se inputs/outputs dikhata hai.

**Planner orchestrator** (sabse interesting):
- Yeh start hota hai → phir **reporter, charter, retirement** ko invoke karta hai (3 tool calls) → phir complete
- Upar **Timeline** switch on karo → dikhta hai ki teeno tools/agents **parallel mein** evoke hue, around the same time complete hue, phir finish

### Reporter agent — judge ka asar

**Reporter agent** trace sabse rich hai:
- `Get Market Insights` call karta hai → response deta hai → phir **judge** mein jaata hai → judge agent chalta hai → completion → **judge event** register hota hai
- Timeline par: pehle market insights, phir run, phir judging

**Judge event** padho:
- Score: **85** (0.85)
- Feedback: *"comprehensive and well structured, covers all requirements. However the report lacks the market context from the Get Market Insights tool which was instructed to be included."*
- Ed khud is feedback se thode unsure hain — *"who knows? but that is the decision"*
- 85% guardrail ke 30% threshold se comfortable margin se upar hai — toh report **pass** ho jaati hai

### Langfuse mein aur kya hai

Ed mention karte hain Langfuse mein bahut kuch aur bhi hai:
- **Scores** track/register karne ki jagah
- **LLM-as-a-judge** ko Langfuse ke andar configure karne ki facility — yaani Langfuse khud ek LLM (paid API) se connect karke judge chala sakta hai (platform-level)
- **Annotations** aur **datasets** bhi daal sakte ho

Ed encourage karte hain ki Langfuse mein "get lost" ho jao, multiple runs karo, agents ke beech conversations padho, aur production mein agents ke real flow ka deep insight pao.

---

## 📋 Key Concepts

| Concept | Matlab |
|---|---|
| **LLM-as-a-judge** | Ek model se doosre model ki output ki quality evaluate karwana |
| **Tenacity `@retry`** | Python retry library — rate-limit error par exponential backoff se auto-retry |
| **Span** | Trace ke andar ek named sub-operation (yahan `judge`) |
| **`span.score(...)`** | Langfuse command — ek trackable score register karna |
| **`create_event(...)`** | Langfuse mein observation/event push karna (debugging visibility) |
| **Guardrail** | Quality-gate — score < 0.3 toh report block, generic error bhejo |
| **`terraform apply`** | Env-var changes (observability on, Langfuse creds) AWS par roll out karna |
| **Trace** | Ek complete agent operation ka record (inputs, outputs, tokens, model) |
| **Timeline view** | Langfuse mein dikhata hai kaun sa agent/tool kab aur kitne parallel mein chala |
| **Model cost $0 issue** | Cost Bedrock/AWS mein track hota hai, Langfuse tak report nahi hota |
| **Clerk user ID** | Clerk auth se aaya user identifier, events mein metadata ke roop mein |

---

## 💼 Backend Dev Ke Liye Note

LLM-as-a-judge + guardrail = classic **validation/quality-gate middleware** ka LLM avatar. Backend mein tum response ko user tak bhejne se pehle business rules, schema validation, ya content moderation lagate ho — yahan ek doosra LLM hi "validator" hai, aur fail hone par hum response ko safe fallback se replace kar dete hain (graceful degradation). Score ko 0-1 mein normalize karna aur ek threshold (`0.3`) se gate karna bilkul ek **circuit-breaker / health-check threshold** jaisa hai.

`tenacity` retry + exponential backoff har production backend dev ko aana chahiye — external API (LLM, payment gateway, third-party) calls hamesha idempotency + retry + backoff ke saath wrap karo, aur sirf transient errors (rate limit, 5xx) par retry karo, 4xx par nahi. Langfuse ka span/score/event model OpenTelemetry ke **spans + attributes + events** ke barabar hai — agar tum APM (Datadog, Honeycomb) use karte ho toh mental model same hai. Aakhri practical insight: **config change ke baad deploy zaroori** (`terraform apply`) — env vars badalna code badalne jitna hi real change hai; IaC mein yeh ek `apply` step hai, jo CI/CD pipeline mein automate hota hai. Aur cost-tracking gap (Bedrock cost Langfuse mein nahi aata) ek reminder hai ki observability tools cross-system attribution mein gaps rakhte hain — billing/cost monitoring alag layer (AWS Cost Explorer) se aata hai.

---

## ✅ Takeaway

- **LLM-as-a-judge**: reporter ke output ko ek judge agent se score karwao, score ko 0-1 mein normalize karo, Langfuse mein `span.score` + event register karo
- **Guardrail**: score < 0.3 (30%) → report wipe karke generic "try again later" message bhejo; user ko kabhi low-quality analysis na jaaye
- Env-var/observability changes ke baad **`terraform apply` zaroori** — sirf agents folder par, fast roll-out (sirf env vars)
- Live run ~25s lamba hai (time.sleep hack + per-agent 10s sleep); Langfuse home par 77 traces, par **model cost $0** dikhega (Bedrock cost Langfuse tak nahi aata)
- Langfuse **tracing + timeline** se dekho: planner teeno agents ko parallel invoke karta hai; reporter ka trace judge flow + 85% score + feedback dikhata hai — comfortably guardrail pass

---

<details>
<summary>📜 Full Transcript (English)</summary>

And you probably realize it from the name judge. This is a classic example of the pattern known as LM as a judge, where we're using a model to judge the performance of another model. So I'm going to lambda handler for the reporter agent. This is the entry point. And if we come in here by the way you'll notice the the tenacity retry. So that if a rate limit is hit a rate limit error then it will automatically retry. Always a good practice as we said. So this is the reporter agent that is then run and it comes up with a final output. But look there's something new here. If we're in observability mode then I create something called a span with judge as the title. I then uh, I call this evaluate function. This is exactly the function I showed you a second ago with the instructions that were sent to the reporter, the task that was sent to the reporter, and its response. The score that I get back, I divide that by 100. So it's now between 0 and 1, because I asked the agent for between 0 and 100 and I take the feedback. And now I'm going to to to register this score span. Score. This is a long fuse command to register a score that we'll be able to track. And I also make an observation and I say observability create event. So I'm calling. Fuse to register this event that this judging happened. Uh and I've also got this little test here. And this is my guardrail. If score is less than some minimum level, I'm saying guard against score. Let's look at that. That is 0.3. If the score is less than 0.3 less than 30%, then that is a problem. And I log an error that it got too low and I overwrite the response. The financial report that the reporter agent came up with. I wipe it out and I replace it with, I'm sorry, I'm not able to generate a report from you for you. Please try again later. And that is what will be sent back to the user. So this is an example of an LM as a judge with a guardrail to prevent bad analysis from going to the user. Uh, and also using observability to track this and to register the score and create an event. Uh, and so that that is our code for doing that. Uh, I also put in another couple of events just so we could see them. I have reporter started exclamation mark as an event. Uh, and I think I also log, I make an event to say that it was it's, uh, it's running with, with the username as well. Somewhere here. Here it is. Reporter about to run. And I give it the job ID and the clerk user ID as well so that we're making another event here. So these are all extra messages that I'm pushing into lang views so we can see them all happening. All right. Those are the changes I've made. That is the observability code. That is the LM as a judge, the guardrail and the score and the events that I added into Lang Fuse. It's time for us to kick this off on the user interface and then go and take a look in lang views. Let's do it. Ah, not so fast, you're thinking. There's one more step to be done before we go and try this out. You know what I almost missed there? You got it. Yes, yes. All right, we have to. Of course. Go and do a terraform apply. Because we changed the environment variables to turn on observability and to put in our Lang views credentials. And until we do a Terraform apply. AWS doesn't have a clue about this. So we have to go into Terraform. And one of the beautiful things about Terraform, that a really nice way that we've set everything up, is that all you have to do is go into that agent's folder. This is the only place where the environment variables have changed. So inside this we can just type terraform apply and it will just make that change immediately to roll out just the change to the environment variables that we made. And we'll say yes and off it goes. Uh it's now going to do that deploy. It's going to make any changes it needs to make. We'll let it do its thing. And when it's done, it should be pretty quick. Uh, we'll then, uh, we'll then then go and bring up our Alex front end and we will kick off a run. And here we are back in Alex. The front end. It just completed the deployment. Such a beautiful front end. So wonderful. Uh, I do notice looking at our beautiful front end, that there is a bit of a bug. I spot that it says last analysis. Never on the top right, even though there was analysis. So I will look to fix that pronto. But if you see this, if I didn't fix it, you can go and fix it for me right now. Or at some point I will get ratty with Claude again and have it do it. Uh, but in the meantime, you can take another. Just take a moment to look through these fantastic screens and see all of the great work that we've done and imagine everything that's going on with the API layer to surface all of this information to us. And then when we're ready, we go to the advisor team and we kick off a new analysis. And now it is running out there. And, uh, all of our agents are picking up, and you'll notice that it took a little tiny bit longer than it did before because of course, we've now got my time dot sleep hack in there. Uh, and, uh, so we'll be just, uh, 15 seconds longer than it was before. Uh, actually, more than that, because each of the agents has a ten second sleep in it. Uh, so I guess it's 25 seconds in total longer than it used to be, but it will finish. And when it's finished, we'll be able to go into long fuse the observability framework and see what we can make of our agent activity. And here we have the results of our run. We've got a nice little summary here. We've got a retirement projection here. And if we go to the charts we've got a bunch of useful charts as well. And with that, it is time for us to go to Lang Fuse and see what we can see. Uh, I had to flick. I want to show you the home screen first. Uh, we get to see in the home screen. Now, I've run this once or twice before, so I see probably more than you're seeing right now. We get to see that there are a bunch of traces from the retirement agent, the charter agent, the planner orchestrator, and the reporter agent. We get to see the traces by time. I've done 77 traces since I set this up a few days ago. Uh, and, uh, the model costs, you'll see, is zero, which would be nice. Unfortunately, the models haven't cost us zero. It's that model costs are being tracked in bedrock, uh, and through AWS that doesn't get reported back to Lang views. So we don't actually get the cost information and Lang views, which is a shame. But we do get all of this other stuff. Uh, and now once you've done that, you turn to tracing, which is where the action happens. So I know there's a lot to take on if I, if I, uh, change this to just the last 30 minutes. Here we go. So, uh, what you see here, this is just the trace from the run that I just did. Each row represents a different trace, which is a different, uh, agent report, if you like. Um, and intermingled with that as some of the events that I had coded, I hard coded that you saw. So this is the planner Orchestrator. And then a couple of events the reporter started. Reporter about to run, if you remember that. And then the reporter. The charter and retirement. So these are all of our agent tracers being shown here in Lang Flow all from the past 30 minutes. All that just ran now. All right. Let's dig into the actual tracers themselves. Let's start with the charter agent I click into that. Up comes here the actual information. If I click down on this last row we can get to see right here things like the the tokens in and out. The model that was used. We can see the inputs that came in. This was the prompting and this was the output which is indeed a JSON set of charts. It has been working and we can click on the retirement agent and see that up and do the same, the same trickery and get to see what came in and out. So we can use this as a way of really understanding what are the different inputs and outputs, how are the the conversations happening between our different agents. And then we can click on the planner orchestrator. This is our planner agent. And we can see with this one that it gets started. And then it invokes the reporter, the charter and the retirement. The three tool calls that it makes which is great to see. And then it completes. So this is this is a really nice way of seeing everything that's going on and getting tons of detail about it. And there's also this little switch up here timeline. And if I turn that switch on then. And I think we're going to have to try and see how I resize this a bit. You get to see like this, this timeline at the top here about what's happening when. And see that that pretty quickly it, it evoked the three different tools, the three different agents at the same time in parallel. And they all completed around here. And then it finished off. Uh, and so that gives you a good sense of, of all of the activities that are happening against the timeline. And you can see a similar timeline for each of these, but the other ones are a little bit more boring. Uh, it's this one, that planner that's the most fun. All right. And then last but not least, we'll take a look at the the reporter. And so now looking into the reporter agent, you can see there that this is the flow that it ran that it's called Get Market Insights, that it came back and gave its response. But that then went into judge and judge ran the judge agent that I showed you a minute ago and got back a completion and then registered a judge event. You can see that on a timeline and see I'll scroll over to the right how it first gets its market insights. It runs and then it does its judging. Let's go back to this view again and we can read the judge event. It gives a score of 85.85. It's comprehensive and well structured. It covers all requirements. The the however the report lacks the market context from the Get Market Insights tool which was instructed to be included. So it wasn't exactly I guess I'm not sure about that evaluation. It's saying that it should have included more information that it got from the markets, from using its tool in the final report, uh, which I guess maybe that's fair feedback. Uh, who knows? But that is the decision. It's 85%, which means it's good enough to make it through our guardrail at 30% by a comfortable margin. But this is where we can see the results. And this is where we can we can see the score that came back and see that it's registered here. And that is the tour of Lang views. There's lots more to play with. There's a place where you can actually register and track the different scores that you do. There's you can set up LM as a judge is where you can actually configure, uh, an LM within Lang views and connect it to a paid API and have Lang views running the LM as a judge functionality. Uh, as, as a platform, um, there's annotations and there's data sets that you can put in here as well. Uh, and I would encourage you to spend some time getting getting lost in lang views, learn about all the things you can do and get insight. Run your run a few times. Look through the conversation that's happening between your agents, and get that deep understanding and deep insights into the real flow of your agents in production.

</details>
