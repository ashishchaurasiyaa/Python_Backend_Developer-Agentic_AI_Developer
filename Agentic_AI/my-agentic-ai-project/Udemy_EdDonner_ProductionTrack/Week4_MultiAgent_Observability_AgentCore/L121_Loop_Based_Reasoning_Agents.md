# L121 — Building Production AI Agents with Loop-Based Reasoning Systems

> **Week 4 · Day 5** · ⏱️ ~12 min

---

## 🎯 TL;DR

Hum "Looper" banate hain — ek agent jise 3 simple to-do-list tools (`create_todos`, `mark_complete`, `list_todos`) + ek system prompt deke "Claude-code-jaisa" step-by-step reasoning loop mil jaata hai. Yeh dikhata hai ki to-do-list waali mystique actually sirf kuch lines of code hai. Deploy karke ek train-meeting math problem solve karke live watch karte hain.

---

## 🗣️ Hinglish Explanation

### "Looper" — reasoning loop ka raaz

Ed ek "more powerful" agent introduce karta hai jise wo **Looper** kehta hai. Idea: tumne Claude Code/agents ko dekha hai jahaan wo ek **to-do list** banate hain, ek-ek step tick karte hain, aur lagta hai jaise koi gehra process chal raha hai. Yeh super-powerful lagta hai — par Ed "recipe ke ingredients" dikhata hai aur tum bologe *"bas itna hi?"* Reality: ek agent ko bas **kuch tools do jo ek to-do list manage kar sakein**, aur system prompt mein bol do "plan banao, steps karo" — loop ban jaata hai.

### Step 0: `first.py` delete karo (important!)

```text
first.py → Move to Trash
```

> ⚠️ Ed strongly warn karta hai: agar `first.py` delete nahi kiya toh **baad mein trouble** hogi (do entrypoint files confuse karengi). Trash se wapas la sakte ho, par abhi hata do.

### Step 1: `looper.py` banao

`finale/` mein **New File** → `looper.py`. README ka content paste karo (save karna mat bhoolo — white blob).

Imports:

```python
from bedrock_agentcore import BedrockAgentCoreApp
from strands import Agent, tool
from pydantic import BaseModel
```

### Step 2: To-do item model (Pydantic)

```python
class ToDoItem(BaseModel):
    description: str
    completed: bool = False
```

- Sirf ek **Pydantic class** — `description` (string) + `completed` (bool). Bas yahi ek to-do list item hai.
- **Pydantic recap**: `BaseModel` se inherit karke tum typed, validated data structures banate ho — JSON serialization free milti hai, jo LLM tool I/O ke liye perfect hai.

### Step 3: State + system prompt

```python
todos: list[ToDoItem] = []   # simple class/module variable as state

SYSTEM_PROMPT = """You were given a problem to solve by using your to-do tools \
to plan out the steps and then carrying out each step in turn. \
Now use your to-do list tools, create a plan, carry out the steps, \
and reply with the solution."""
```

- **`todos`** — ek simple module/class-level list jo state rakhti hai. Ed bolta hai: Agent Core ki **Memory** section is state ko persistent + better-managed bana sakti hai, par abhi ke liye yeh plain list kaafi hai.
- **System prompt** — agent ko bolta hai: to-do tools se plan banao, har step karo, phir solution do.

### Step 4: Pretty-printer (sirf formatting, koi tool nahi)

```python
def get_todo_report() -> str:
    lines = []
    for i, item in enumerate(todos, start=1):
        if item.completed:
            lines.append(f"{i}. ~~{item.description}~~")   # strikethrough
        else:
            lines.append(f"{i}. {item.description}")
    return "\n".join(lines)
```

- Yeh **tool nahi** — bas ek Python utility jo poori to-do list ko nicely format karti hai.
- Completed items par **strikethrough** lagti hai, har item ke aage **number** (1-indexed) print hota hai.
- Isse hum **aur agent dono** to-do list ko padh sakte hain. *"Nothing clever here."*

### Step 5: Teen tools (yahi asli kamaal hai)

```python
@tool
def create_todos(descriptions: list[str]) -> str:
    """Add new to-dos from a list of descriptions and return the full list."""
    for desc in descriptions:
        todos.append(ToDoItem(description=desc))
    return get_todo_report()

@tool
def mark_complete(position: int) -> str:
    """Mark complete the to-do at the given position (starting from 1) and return the full list."""
    todos[position - 1].completed = True       # 1-indexed -> 0-indexed
    return get_todo_report()

@tool
def list_todos() -> str:
    """Return the full list of to-dos."""
    return get_todo_report()
```

- **`create_todos`** — strings ki list leta hai, har ek se ek `ToDoItem` banata hai, phir report return karta hai. Agent bas strings ki list pass karke poora plan set kar deta hai.
- **`mark_complete`** — given position (1 se shuru) ka to-do `completed=True` karta hai. `position - 1` is liye kyunki list 0-indexed hai. Ed ne **1-indexing** chuni kyunki LLMs aksar 0-index karte hain (kyunki bahut code 0-indexed hota hai), jisse confusion ho sakta hai; printer bhi numbers 1 se dikhata hai. *(Ed ne ise zyada test nahi kiya — tum experiment kar sakte ho.)*
- **`list_todos`** — bas poori report return karta hai.

> 💡 Ed ka observation: `mark_complete` shायad zaroori bhi nahi, kyunki har tool already `get_todo_report()` return karta hai (agent ko har baar list dikh jaati hai). Tum 2 tools tak ghata ke experiment kar sakte ho.

### Step 6: Agent banao + entrypoint with streaming

```python
tools = [create_todos, mark_complete, list_todos]
agent = Agent(system_prompt=SYSTEM_PROMPT, tools=tools)

app = BedrockAgentCoreApp()

@app.entrypoint
async def invoke(payload):
    user_message = payload.get("prompt")
    async for event in agent.stream_async(user_message):
        if "data" in event:
            yield event["data"]          # stream text back as it comes
        else:
            yield get_todo_report()      # non-text event = probably a tool call
```

- Tools ko list mein daal ke `Agent(system_prompt=..., tools=...)` banao.
- `invoke` thoda **richer** hai is baar — yeh **stream back** karta hai taaki text aate-aate print ho.
- Jab event text **nahi** hota (matlab agent koi **tool call** kar raha hai), tab hum `get_todo_report()` yield karte hain — taaki hum **piche chal rahi to-do list ko "spy"** kar sakein jab agent kaam kar raha ho. (Claude khud to-do list reply nahi karega; hum behind-the-scenes dekh rahe hain.)
- Poora code "ek-doh screens" mein fit ho jaata hai, zyaadatar boilerplate. *"Couldn't be simpler."*

### Step 7: Configure + deploy (no local test — "be brave")

Entry point change hua, toh configure dobara:

```bash
# finale/ mein
uv run agentcore configure -e looper.py
# yes, yes, yes, yes (sab defaults)
uv run agentcore launch
```

Ed local test skip kar deta hai — *"let's be brave, deploy right away."* Launch is baar thoda zyada time le sakta hai (Looper bada hai), par phir bhi ~1 minute mein done.

### Step 8: Invoke — train problem live solve

```bash
uv run agentcore invoke '{"prompt": "A train leaves Boston at 2pm traveling 60 miles an hour. Another train leaves New York at 3pm traveling 80mph toward Boston. Where do they meet?"}'
```

Live dekho kya hota hai:

1. Agent bolta hai *"I need to solve this train problem step by step. Let me create a to-do list."*
2. **6 to-dos** plan ho jaate hain:
   1. Determine distance between Boston and New York
   2. Set up the problem with variables
   3. Write equations for each train's position
   4. Find when the trains meet
   5. Solve the meeting time
   6. Verify the answer makes sense
3. Ek-ek karke **cross off** hote hain (strikethrough). Pehla: distance ≈ **200 miles** (standard assumption jab specified nahi).
4. Equations likhta hai, positions equal karke solve karta hai...
5. **Final answer: ~4 PM** (Ed bolta hai actually ~4:06 PM zyada precise hoga).

> 🐢 **Slow kyun?** Ed notice karta hai ki yeh slow hai. Reason: wo **rate-limit errors** hit kar raha hai aur agent **automatically retry** kar raha hai (har step multiple baar try). Tumhare paas zyada Claude quota ho toh fast hoga. Ironically, slowness se "thinking ho raha hai" ka feel zyada aata hai. (Yeh retry behavior agle lecture mein observability traces mein confirm hoga.)

### The big reveal

Claude-code-jaisi to-do-list "mystique" ab demystified hai — yeh sirf **kuch tools + ek system prompt** hai. Aur yeh poora reasoning-loop agent **AWS par deployed**, internet par live, minutes mein ban gaya.

---

## 📋 Key Concepts

| Concept | Matlab |
|---|---|
| **Looper / reasoning loop** | Agent jo to-do list bana ke step-by-step plan execute karta hai (Claude-code jaisa) |
| **To-do tools (3)** | `create_todos`, `mark_complete`, `list_todos` — yeh teen tools loop ko enable karte hain |
| **`ToDoItem` (Pydantic)** | `description: str` + `completed: bool` — ek to-do item model |
| **System prompt as driver** | "plan banao, steps karo" prompt hi loop behaviour trigger karta hai |
| **`get_todo_report()`** | Formatting utility (tool nahi) — completed items strikethrough, 1-indexed |
| **1-indexing choice** | `mark_complete` 1 se shuru (LLM 0-index confusion avoid karne ke liye), `position-1` internally |
| **`agent.stream_async` + yield** | Text stream karo; non-text event = tool call → to-do report yield karke "spy" |
| **Auto-retry on rate limits** | Rate-limit errors par Strands/agent khud retry karta hai (slowness ka kaaran) |
| **`configure -e` re-run** | Entry point badalne par configure dobara chalana padta hai |

---

## 💼 Backend Dev Ke Liye Note

Yeh lecture ek backend dev ke liye **"agentic loop = state machine + tool calls"** ka demystification hai. To-do list ek **shared mutable state** (module-level `todos` list) hai jise tools mutate karte hain — yeh exactly waisa hai jaise tum ek service mein ek in-memory store rakhte ho. Real production mein yeh **stateless container** + persistent store (Agent Core Memory, ya DynamoDB/Redis) hota — Ed bhi yahi hint deta hai. `mark_complete` ka 1-vs-0 indexing waala design decision ek classic **off-by-one/API-contract** issue hai: tum apne tool ke interface ko LLM ke liye least-surprising banate ho, jaise tum kisi external client ke liye API design karte ho. Streaming entrypoint (`async for ... yield`) bilkul SSE/chunked-response pattern hai (FastAPI `StreamingResponse` jaisa). Aur auto-retry-on-rate-limit ek **resilience pattern** hai jo framework free deta hai — production mein tum isse exponential backoff + circuit breaker se augment karoge. Bottom line: "magic" reasoning loops architecturally simple hain — tools + prompt + state.

---

## ✅ Takeaway

- Reasoning loop = **3 to-do tools + ek system prompt** — koi rocket science nahi
- `first.py` zaroor delete karo before `looper.py` (do entrypoints trouble dete hain)
- State ek simple module-level list (`todos`); Pydantic `ToDoItem` (description + completed); `get_todo_report()` pretty-prints with strikethrough + 1-indexing
- Streaming entrypoint: text yield karo, tool-call ke time `get_todo_report()` yield karke to-do list "spy" karo
- Entry point badla → `agentcore configure -e looper.py` dobara → `launch` → live deployed loop agent ne train problem ~4 PM solve kiya (slowness = rate-limit auto-retries)

---

<details>
<summary>📜 Full Transcript (English)</summary>

Okay, onwards, onwards. Now to a more powerful agent that I have called the Looper. For reasons that are probably clear to you, but if not, they'll be even clearer in a minute. Uh, let's get rid of this terminal to get out of our way. Uh, okay. So first step, and this is an important one. If you don't do this, there'll be trouble later is to delete first dot pi. You've probably just got attached to first dot pi. Uh, you can always like, like bring it back again from your trash bin afterwards. But for now I'm going to delete it. Move it to trash. It's gone. It's history. Um, okay. And now we're going to create a new file called Looper. And we're going to give it all of this content. So I'm just going to take this, put it in my clipboard. And then I will, uh, go through it with you. So within finale uh, new file called looper pi looper dot pi paste in. Let's take a look at this code. All right. So again and remember to save you see that white blob. That white blob is saying you haven't saved me. Command S or control S on a PC and it is saved okay. So we're going to import the Bedrock Agent Core app. We're going to have Agent and Tool again from strands pedantic classes and we're off. Okay. Let me let me walk you through this, this code. So I imagine all of you or most of you like me, have had the experience of talking, interacting with an agent with one of these loops where it thinks things through and it ticks things off a list, and it gives you this, this, this eerie sense that you're dealing with something that has a whole process behind it. And you probably think that's super powerful, like Cloud code being the classic example. Imagine how much work must have gone into making that actually work. Uh, well, I have news for you. This is like one of those moments when I show you the ingredients behind a recipe and you're like, is that all? Uh, it turns out it's actually really ridiculously simple. To make this work, you just need to have a few tools which you give to an agent, which give it the ability to manage a to do list. And I'm sure that there are a whole ton of implementations out there that you can use, and there's no doubt MCP servers and all sorts of good stuff. In fact, I know there's one that anthropic made. There's lots of them out there, but it's just a few lines of code to make one, and doing it yourself gives you that real, raw sense of how very simple it is. So check this out. I'm going to have a only one pedantic class called to do item, and all it has is a description which is a string and completed, which is a bool. Whether or not the task is completed and that is it. That is my to do list item. Okay. Then I'm going to have one of the nice things about the Bedrock agent core is that you can just use like a class variable like this. You can see in the memory section of the docs how you can have this be persistent and have it be managed in a better way. But for our purposes right now, this is going to work just fine. So system prompt, you were given a problem to solve by using your to do tools to plan out the steps and then carrying out each step in turn. Now use a to do list tools. Create a plan, carry out the steps and reply with the solution. Okay, I'm now this. This isn't a tool. This is just a Python utility here. Get to do report. This iterates through all of the all of the things in to do's and will print each of them what they what they are in a nice way. And if it's been completed, it's going to print it with, with like a, like a strikethrough. So this is just a formatting thing so that we can look at the to do list and so can our agent. So don't, don't uh there's nothing clever here okay. But what is clever are these three tools. And you know, what can I tell you. These are really simple. Look how short they are. Three tools, that's all. There are no more than three tools. One of them is called create to dos. It takes in a list of strings, add new to dos from a list of descriptions, and return the full list. So for each description, it adds in one of these to dos and it returns the report that we just made. Wow. Okay, so that we're going to give we're gonna equip our agent with this tool so that it can set up a to do list just by passing in a list of strings. And then another tool is mark complete. Mark complete the to do at the given position starting from one and return the full list. You have to be careful about this starting from one, because many agents naturally like to be zero indexed because so much code is. But that would, that would, uh, could get confusing because of the first item and so on. So I decided to start from one. And I also have in this printer it prints the number by each one just to avoid any confusion. But I didn't test this particularly thoroughly. This was just something I did first time. So you could definitely play with this and experiment with it and see see if it's better or worse with a different index. But this worked well. So what this does is it checks that that everything is right. And uh, if so it just takes that to do. See that index minus one. Because number number one would be at zero index and it sets completed to true and it returns again the full list. And then the final tool is just called list to Dos, and it just simply returns the full list. That's all it does. Uh, so with this, we have equipped our agent with three things create a DOS and Mark complete. And actually, this is hardly necessary because it gets the to do report every time. So I don't know if this is even needed. Uh, you could experiment with just taking this off and just having two tools that might be completely fine. All right. And so what we do now is we put those three tools into our tools list and we create an agent, the system prompt. We pass in the tools we pass in and that's it. That's the end of this little project by I've got again the invoke, which just takes a payload which looks in prompt to take the user prompt. And then here I've just got something that's a little bit more because I wanted to stream back and have it print as it streams back. And any time that it's doing something that isn't streaming back, it's probably calling a tool. So just to make it look more fun, I have it return the full to do list so we can see the to do list behind the scenes. The agent won't actually be replying. Claude won't be replying with a to do list, but we'll be able to spy and see what's going on with that to do list while we watch. And that's that's the end of the code. Look, it all fits on like one and a half screens and most of it is boilerplate. It really couldn't be simpler than that. Well, it's one thing for it to be simple. It's another thing for it to work. So that's that's the next thing to try. And of course we should first test it locally and then we should deploy and test it remotely. I'm lying. Let's not bother with the local. Let's just deploy right away. Let's be brave. We'll be brave. So we have to do this configure step again because we've changed our entry point. So let's bring up a new terminal. Here it comes. We go into remember to CD into finale. And then we're going to run configure minus entry point to Looper dot pi. And we say yes and yes and yes and yes. And it's configured all right. And now we have to, uh, go back to the readme. Um, here it is. And see the next thing to do, which is you've run Agent core launch. Okay. Drumroll. Off it goes. Stuff is happening. It's using Looper. Will it work? First time? It might take a little bit longer this time, so it'll give us some tension, some expectation. Launching bedrock agent core. So. All right, I will I will let it do its deployment. It probably will take a minute this time. And I will see you back here in one second. Hopefully you're running this as well. And you're seeing what I'm seeing. And you're about to have a deployed agent on the internet with tools. Uh, it's done already. Okay, uh, let's go ahead and run this. So, uh, yeah, I will walk you through what we're going to ask it. Okay. So here is going to be our prompt. We're going to do UV run agent core invoke prompt. A train leaves Boston at 2 p.m. traveling 60 miles an hour. Another train leaves New York at 3 p.m., traveling 80mph toward Boston. Where do they meet? That's a nasty little challenge. So let's take this and paste it in here and see what happens. So this is exciting. I need to solve this train problem step by step. Let me create a to do list and look at that. Six to do's have been planned and it's already done. The first one it's been crossed off. Determine the distance between Boston and New York. So scroll up and you can see, uh, the the what? It says I need to do list to organize my approach. You can see it's to do's determine the distance, set up the problem with variables. Write equations for each train's position. Find when the trains meet. Solve the meeting time. Verify the answer makes sense. So that's that's a lot for it to do. Uh, and you can see it's, uh, it's, uh, cross them off. It just it just, uh, came up with something, uh, complete. The distance between Boston and New York is approximately 200 miles. A standard assumption for this kind of problem when not specified. Okay, that sounds very reasonable to me. So let's cross that off. And now it's doing the right equations for each train's position as a function of time. Now, one thing you might notice is that it's not exactly speedy. And you might wonder what's going on. How come it's taking so long? I wondered that too. I will tell you. Uh, here we go. It's got. It's written the equations that tb the time distance between the city and there's the equations. Uh, what's taking the time is actually a silly answer that, uh, I'm actually, I believe I'm hitting rate limit errors and the agent is automatically retrying. Uh, and later we will we will see if that's true or not. Uh, but I think we'll find that that, uh, and maybe for you, you don't have rate limit errors because you've got more ability to use Claude, and you'll be getting it much, much faster. But it's slow because it's trying each of these multiple times. Okay, fine. When the trains meet by setting positions equal and we are almost through our to do list, it makes it more fun that it takes longer because it really feels like there's a there's stuff going on. Otherwise, I think it would be so fast that you wouldn't really get this sense that that thinking is going on. It is now, uh, presumably it is on to do step five, solving for the meeting time. That is the real, uh, hardcore part of all of this. Let's see what it has over. It's just done that. It's now verifying. It's solved. Uh, you can see here it set up these equations. Um, yeah. It looks like it's, uh. Yeah. Multiplying minus by minus and getting a plus. That's good, that's good. 62 is 218 minus eight. Very nice. Verify that the answer makes sense is the final step that it's on in this thought process. Uh, and uh, yeah I hope that you're as, uh, blown away by this as I am. Uh, and again, one of the things that's so fascinating about this is that some of the mystique about Claude code and the way that it's able to think things through and show these to do lists, is taken away because it's so clearly just a few lines of code to build this kind of to do list functionality and have something that can, that can run with this sort of thought process. So it's in the final step. Now verifying the answer makes sense. And then we will see what answer it actually gives us. Uh here we go. Here comes the final answer. The two trains meet at 4 p.m., which is about right, I believe. Uh, I think it's 406. Would be more precise. I think I think, uh, but you can see it's crossed everything off, and it looks fantastic. There is a result in a matter of minutes. We have an agent loop. We built an agent with a loop that is carrying out a reasoning thought process, solving a problem step by step, and we're able to watch it happening. And all of this is running deployed to AWS. Uh, and it's been just so easy.

</details>
