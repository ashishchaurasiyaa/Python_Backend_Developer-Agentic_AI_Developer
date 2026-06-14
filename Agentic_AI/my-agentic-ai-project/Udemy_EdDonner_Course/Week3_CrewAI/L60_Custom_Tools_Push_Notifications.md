# L60 — Day 3: Custom Tool Development — JSON Schema & Push Notifications

> **Week 3 — CrewAI** · ⏱️ ~9m · 🎥 Lecture 60 of 131
> **Instructor:** Ed Donner · **Lecture ID:** 49821193

---

## 🎯 Ek Line Mein (TL;DR)

Stock Picker crew ko run karke results dekhe, aur phir pehla **custom tool** banaya — ek **PushNotificationTool** jo **pydantic schema** (`args_schema`) + `_run()` method se define hota hai aur **Pushover** se user ko push notification bhejta hai; ye tool **stock_picker agent** ko de diya.

---

## 📝 Hinglish Explanation (Detailed)

- **main.py ka run() function**: Ed ne default template ka run function delete karke ek simple `run()` likha — inputs me sirf `sector = "technology"` pass kiya (current date ki zaroorat nahi thi), phir `stock_picker.crew().kickoff(inputs=...)` call kiya aur result print kar diya.
- **Crew run kiya**: Terminal kholke (Ctrl + backtick), project folder me jaake **`crewai run`** chalaya.
- **Autonomy ka trade-off**: Ed ne warn kiya ki **hierarchical/autonomous crew process** by nature thoda **unpredictable** hota hai — manager apne hisaab se tasks assign karta hai, kabhi wapas news/analyst ya researcher ke paas jaata hai, aur kaafi time le sakta hai. Machine bhi heavy chug karti hai. Ye autonomous agentic AI ka **plus bhi hai aur minus bhi** — humara process pe control kam hota hai.
- **Result**: Crew ne **Anthropic** ko recommend kiya (funny — OpenAI model hi processing kar raha tha!), aur do runners-up reject kiye — **Peregrine** (security company) aur **Circle** (crypto company).
- **Outputs folder**: Decision file, research list, aur trending companies list — sab **JSON format** me, kyunki humne **structured outputs** (`output_pydantic`) se schema enforce kiya tha. Schema-conforming, properly formatted results mile.
- **Manager ne kaam sahi kiya**: Misgivings ke bawajood hierarchical process ne process theek follow kiya aur stock pick mila (disclaimer: real trading ke liye nahi hai!).
- **Ab bells & whistles — Custom Tool**: `src/stock_picker/tools/` folder scaffolding me pehle se hota hai, jisme **`custom_tool.py`** ek typical template layout ke saath aata hai. Ed ne usse rename karke **`push_tool.py`** banaya.
- **Custom tool ka pattern (2 parts)**:
  1. **Pydantic input schema** — `PushNotificationInput(BaseModel)` jisme ek field `message: str` hai with description *"A message to be sent to the user"*. Ye define karta hai ki tool ko **kya arguments** milenge.
  2. **Tool class** — `PushNotificationTool(BaseTool)` with:
     - `name = "Send a push notification"`
     - `description = "This tool is used to send a push notification to the user"`
     - `args_schema = PushNotificationInput` (yehi LLM ko batata hai arguments ka JSON schema)
     - **`_run(message)`** method — actual logic yahan hota hai.
- **`_run()` me Pushover**: Wahi **Pushover** code paste kiya jo prior week (Week 1/2) me use hua tha — `.env` me `PUSHOVER_USER` aur `PUSHOVER_TOKEN` chahiye. Message push hota hai aur tool "ok" return karta hai.
- **Tool ko agent se attach karna**: `crew.py` me `PushNotificationTool` import karke **stock_picker agent** ke `tools=[...]` me daal diya — bas itna hi! (Cursor ne autocomplete se already suggest kar diya tha.)
- **Dobara run**: Is baar crew ne **Circle** recommend kiya (pichli baar ka runner-up), aur Ed ko **actual push notification** mila phone pe — tool successfully invoke hua.
- **Day 3 recap — 3 nayi cheezein** jo pehle se alag thi:
  1. **Structured outputs** — tasks JSON schema conform karte hain (`output_pydantic`).
  2. **Hierarchical process** — sequential ki jagah, manager (LLM model name ya manager agent) tasks assign karta hai; iske good aur bad dono dekhe.
  3. **Custom tool** — khud ka tool likha (push notification) aur agent ko arm kiya.
- **Aage kya**: Stock picker abhi khatam nahi — kal ek aur bell & whistle add hoga, aur uske baad next project — **developer agent** (coder).

---

## 🔑 Key Concepts / Important Terms

| Term | Simple Hinglish Meaning |
|------|--------------------------|
| **Custom Tool** | Khud ka likha tool jo agent invoke kar sakta hai — `BaseTool` subclass + pydantic input schema + `_run()` method |
| **`args_schema`** | Tool class ka attribute jo pydantic `BaseModel` point karta hai — LLM ko tool ke arguments ka JSON schema batata hai |
| **`_run()`** | Tool ka actual execution method — schema ke fields iske parameters bante hain |
| **`name` / `description` (tool)** | LLM ke liye human-readable hint ki tool kya karta hai aur kab use kare |
| **Pushover** | Simple push-notification service — `PUSHOVER_USER` + `PUSHOVER_TOKEN` env vars se phone pe message bhejta hai |
| **`tools/` folder** | CrewAI scaffolding me auto-generated folder with `custom_tool.py` template |
| **Structured outputs** | `output_pydantic` se task ka result enforced JSON schema me aata hai |
| **Hierarchical process** | Manager (LLM ya agent) autonomously decide karta hai kaunsa task kis agent ko jaaye — powerful par less predictable |
| **`crewai run`** | CLI command jo crew project ko kickoff karta hai |

---

## 💡 Backend Dev Ke Liye Note (aapke liye)

- **Custom tool = typed function endpoint**: `args_schema` (pydantic) + `name`/`description` + `_run()` ka pattern bilkul **FastAPI route** jaisa hai — pydantic model request body validate karta hai, docstring/description OpenAPI docs ban jaata hai. Yahan "client" ek LLM hai jo schema padhke JSON arguments generate karta hai — isliye description quality directly tool-calling accuracy pe asar daalti hai.
- **Underscore convention**: Aap `run()` nahi, **`_run()`** override karte ho — `BaseTool.run()` ek template method hai jo validation/error-handling wrap karta hai, jaise Django ke `View.dispatch()` ke neeche aap `get()/post()` likhte ho.
- **Side-effect tools ko least-privilege do**: Push tool sirf `stock_picker` agent ko diya, sab agents ko nahi — wahi principle jaise production me write-scope credentials sirf usi service ko dete ho jisko zaroorat hai. Autonomous manager unpredictable hai, to blast radius chhota rakho.
- **Hands-on lab**: Is lecture ka code khud chalane ke liye `Practical/lab3_stock_picker.py` run karo (is repo me, `uv run` se chalta hai, Groq pe free via LiteLLM). Note: hamare labs course se thoda alag hain — self-contained code-style (YAML scaffolding nahi), aur SerperDev ki jagah **free Wikipedia search tool** use hota hai; push notification ka custom-tool pattern (pydantic schema + `_run`) wahi hai.

---

## 🧠 Takeaway (yaad rakho)

1. Custom tool banane ka recipe: **pydantic input schema** → `BaseTool` subclass with `name`, `description`, `args_schema` → **`_run()`** me logic.
2. Tool ko agent se jodna ek-line ka kaam hai — `crew.py` me import karke agent ke `tools=[...]` me add karo.
3. Hierarchical/autonomous process **kaam karta hai but unpredictable** hai — manager apne hisaab se route karta hai, time variable hota hai.
4. Structured outputs ki wajah se outputs folder me **schema-conforming JSON** files milti hain — downstream parsing reliable.
5. Day 3 ke 3 pillars: **structured outputs + hierarchical process + custom tool** — ye combo aage ke projects me baar-baar use hoga.

---

<details>
<summary>📜 Full English Transcript (original, click to expand)</summary>

Okay. Well, it remains for us to write the the main the run function in here. I deleted the default template one that's there usually, and I'm replacing it here with a simple run. The crew we're going to pass in the sector as technology. We don't actually need a current date in there at all. That will do fine. We don't use current dates and the result is stock_picker kickoff passing in the inputs. And then we will print results at the end. So there we go. This is our starting point. I think we should give this a whirl okay here we go. So we're going to bring up our terminal as usual with control and the tick. And then we're going to go into our third folder. And we are going to go into the stock picker. And we're going to type crewai run to kick it off.

And now here's the thing. It's going to be interesting to watch this. The crew process is, by its very nature, a little bit less predictable than we might want. It is autonomous and it goes off and does its own thing, and that can involve all sorts of searching around and using multiple agents. It can sometimes go back to do some news and analysts and then using the researcher, and it can take quite a while as it goes through its processing. And my machine is chugging away like crazy, as will yours. And it's both. The great thing, and perhaps the downside of autonomous agentic AI, that we have a bit less control over how this process is followed, and so I will let it do its thing. I will break and come back when it completes its recommendation.

And here we have it. It actually completed pretty much right as I was pausing there. So it was quite quick. It made a decision to recommend Anthropic and it says, which was interesting because it was OpenAI that was doing this, this processing, which is and it turns down a couple of a security company, Peregrine and a crypto company, Circle, and we can look in our outputs folder where we'll see that this decision is shown. And we'll also find a research list here. And also the trending companies list. And these of course are in the JSON format that conforms to our schema. So we are seeing here the proper formatted results because we required that by using structured outputs. And so despite my misgivings about the autonomous framework it actually performed really well. It did just go through the process. It should do. The manager that we'd set up had some autonomy in how it assigned out the tasks, but it did so well and as a result, we did indeed achieve a stock pick recommendation, which is not intended for real trading decisions, which is in this case for Anthropic.

All right, it's time to make our solution have a few more bells and whistles. First of all, we're going to add a tool. You'll see if you look in the source folder in the stock picker folder that's generated for you that there's already a folder called tools that the people at Crew have kindly made for us. And there's one in there called custom tool that has a kind of typical layout for these sorts of, of tools. And we are going to change the name of custom tool, and we're going to make it into push tool. So let's do rename and make this a push underscore tool dot py.

So the way that it works if we look in here is that you'll see that there is a when you set up a custom tool you have to first describe using a pydantic object, the schema of what will be passed in to your custom tool. And then you end up writing an underscore run method, which is going to take that schema as its parameters. So to make that feel more real, I'm going to, uh, actually implement that. And let's just start with a couple of, uh, imports here and now. So we're going to have a push notification input which will be a subclass of base model. And we're going to change the description that this is uh what is the meaning of this input. It's going to be a message to be sent to the user okay. And now instead of an argument we're going to say message. That's what we're going to call it. And the description will be the message to be sent to the user. That seems pretty clear. Okay. So that is then defining the schema for our tool. It's in other words this here is actually going to be message to to correspond with that. That's what we will run when the tool is invoked.

So uh we will um give it a name. So first of all we should change the class to be push notification tool. There we go. Thank you. Cursor. The name let's say is going to be send a push notification and the description is going to be this tool is used to send a push notification to the user. That seems pretty decent to me. Okay. And the schema for the args. This is where we say what kind of arguments do we need you to pass in. Well, that's exactly the schema that we've just defined right here. So it is something which just has a single argument message. And there you go. You see we've written a run method with a single input message. And that is going to actually send a push notification. And how do we send a push notification. We use the fabulous Pushover tool. And hopefully in your environment you have Pushover user and Pushover token set in your env file from prior week and then I just used I've just pasted in exactly the same code we have from the prior week, and we will push this message to the user and then return that that was okay. So that is our push notification tool.

Now we have to put it to good use. Well this should be pretty easy actually. We're back in the crew.py module and we add in an import to import in the push notification tool. Now which of our agents do we want to be able to do this. We want the stock picker agent to be the one that will have this power the stock picker. You can see Cursor of course already tells us that's exactly what we want. We want the stock picker to be able to call the push notification tool. That's as simple as that.

All right. With that, let's go and run this. We'll do that right away. We will bring up this. We will clear what we have here. And we will just call crewai run and give it a whirl. Let's see what happens. I will let this run and I'll be right back. And here we go. It's completed. It's this time recommending Circle, which was one of the runners up last time. And I can assure you, you can see it right here that I did indeed get a push notification about the, the the opportunity, which is great. So it is working. And that then is the extra piece that we've added into this.

So just to recap, we built this agent framework and the three things that are different than the way we've done it before. First of all we've used structured outputs. So we've required that tasks respond conforming to a JSON schema that we set. Secondly, instead of using the sequential process, we use the hierarchical process, which means that we can either pass in an LLM by model name or by passing in an agent that will take care of assigning the tasks to the agents. And we did that. And we saw, I think, both the good and the bad of doing so. And then thirdly, we added a custom tool, a tool that we wrote ourselves. And it's a familiar one. It was to send a push notification. And we armed an agent with that ability and it pulled it off successfully.

And so that then is wraps up this day's project. We've got lots more to go. And in fact, tomorrow and in the next day before we move on to the next project, I do want to add one more bell and whistle to this project too. So we're not completely through with the stock picker either, so stay tuned for that. But again, to recap, we just did structured outputs, custom tools and hierarchical process. And tomorrow we're going to we are going to add a little bit extra to stock picker but then also work on the next project, the developer agent. And I'm really excited about that one. Good old Crew is coming through strong. See you then.

</details>

---
*Source: Official Udemy lecture transcript (auto-captions, lightly cleaned). Notes in Hinglish for self-study.*
