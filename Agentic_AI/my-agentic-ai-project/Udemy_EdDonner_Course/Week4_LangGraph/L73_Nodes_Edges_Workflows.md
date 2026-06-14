# L73 — Day 2: Creating Nodes, Edges & Workflows

> **Week 4 — LangGraph** · ⏱️ ~6m · 🎥 Lecture 73 of 131
> **Instructor:** Ed Donner · **Lecture ID:** 49821335

---

## 🎯 Ek Line Mein (TL;DR)

Is lecture me hum pehla **node** (ek simple Python function jo **old state leta hai aur new state return karta hai**) banate hain, **`add_edge`** se **START → node → END** wire karte hain, graph **compile + display** karte hain, aur **`invoke()`** se chalate hain — aur dekhte hain ki **reducer** behind-the-scenes messages ko **HumanMessage/AIMessage** me package kar deta hai. Sabse badi baat: **graph ka LLM se koi lena-dena nahi hai** — node bas ek function hai.

---

## 📝 Hinglish Explanation (Detailed)

- **Node creation = ek function likhna.** Yaad rakho, LangGraph me **node ek function hota hai**. Ed ek function banate hain `our_first_node` jo **old state** input me leta hai aur **new state** return karta hai.
- **State immutable hai** — hum old state ko **mutate nahi karte**. Is example me to old state ko touch hi nahi kiya gaya (IDE me grayed out dikh raha hai kyunki unused hai) — ye unusual hai, bas demo ke liye.
- **Node ke andar kya ho raha hai:**
  - Ek string `reply` banai jaati hai = **random noun** + word "are" + **random adjective** (jaise "muffins are haunted").
  - Us reply ko **OpenAI-style message structure** (role/content dict) me daala jaata hai.
  - **Naya State object instantiate** hota hai in messages ke saath, aur wahi **new state return** ho jaata hai. Bas — node done.
- **`graph_builder.add_node("first_node", our_first_node)`** — node ko officially graph me register karne ka tarika. Ek **naam** dete ho aur **function** pass karte ho.
- **Edges banana — `graph_builder.add_edge()`:**
  - `from langgraph.graph import START, END` — ye **constants** hain jo workflow ke **beginning aur end** ko signify karte hain.
  - Do edges: **START → first_node** aur **first_node → END**. Simple linear flow.
- **Step 5 — graph compile karna:** `compile()` matlab "hum done hain, ye raha hamara workflow". Compile ke baad graph ko **visually display** bhi kar sakte ho — START → first_node → END ka neat diagram dikhta hai.
- **Graph run karna — Gradio chat function ke through:**
  - Gradio chat function user ka **current message + history** leta hai aur next output return karta hai.
  - Andar: message ko **OpenAI format** me convert karo → us se **State object** banao → **`graph.invoke(state)`** call karo → result print + return karo.
  - **`invoke` keyword important hai** — yahi word **LangChain** me bhi use hota hai. LangGraph me graph ko state ke saath invoke karte ho, aur graph execute hoke result deta hai.
- **Demo output:** "Muffins are haunted", "Penguins are sparkly", "Pickles are untrustworthy" — ek **"silly language model"** jo random noun+adjective pick karta hai. One-sided funny conversation.
- **Point of the demo:** Ed deliberately LLM use NAHI kar rahe — dikhane ke liye ki **graph setup ka LLMs se koi necessary connection nahi hai**. Node bas ek function hai jo state in, state out karta hai. LLM optional hai.
- **Reducer ka hidden kaam:** result print karne par dikhta hai ki messages plain strings ki list nahi hai — wo **`HumanMessage`** aur **`AIMessage`** objects ki list hai (LangChain ke constructs).
  - Pehle Ed ne kaha tha ki reducer (**`add_messages`**) bas list me **concatenate** karta hai — but full story ye hai ki wo **packaging bhi karta hai**: user ka text → `HumanMessage`, response → `AIMessage`.
  - Ye LangGraph ka behind-the-scenes magic hai — humein manage nahi karna padta, hum bas advantage lete hain.
- **Recap:** super simple State (messages ke saath) + super simple node (old state in, new state out) + edges + compile + invoke = working LangGraph app, bina kisi LLM ke.

---

## 🔑 Key Concepts / Important Terms

| Term | Simple Hinglish Meaning |
|------|--------------------------|
| **Node** | Graph ka ek step — bas ek **Python function** jo old state leta hai, new state return karta hai |
| **Immutable state** | Old state ko mutate mat karo — hamesha **naya state object** banakar return karo |
| **`add_node(name, fn)`** | Graph builder me node register karne ka method — naam + function |
| **`add_edge(a, b)`** | Do nodes ke beech connection — control flow a se b jaayega |
| **START / END** | `langgraph.graph` ke **constants** — workflow ka official entry aur exit point |
| **Compile** | "Graph done hai" declare karna — compiled graph hi run hota hai, aur display bhi ho sakta hai |
| **`invoke(state)`** | Compiled graph ko state ke saath execute karna — LangChain wala hi word |
| **HumanMessage / AIMessage** | LangChain ke message wrapper classes — reducer plain text ko inme **package** kar deta hai |
| **Reducer (`add_messages`)** | Sirf concatenate nahi — messages ko proper LangChain message objects me bhi convert karta hai |
| **Gradio chat function** | `(message, history) -> reply` signature wala function jo `gr.ChatInterface` me pass hota hai |

---

## 💡 Backend Dev Ke Liye Note (aapke liye)

- **Node = pure function, state = immutable** — ye functional programming / Redux pattern hai: `(oldState) -> newState`, kabhi in-place mutation nahi. Aap jaise Redux reducers ya FP-style services likhte ho, bilkul wahi discipline. Mutation avoid karne se LangGraph parallel super-steps me race conditions se bachta hai.
- **START/END constants + add_edge** = explicit DAG wiring, jaise Airflow me `task_a >> task_b` karte ho. Compile step ko ek **build/validation phase** samjho — jaise SQLAlchemy ka metadata `create_all` ya ek state machine ka definition freeze hona, runtime se pehle.
- **`add_messages` reducer ka auto-packaging** (str → `HumanMessage`/`AIMessage`) ek ORM type-coercion jaisa hai — aap raw dict/string do, framework usse typed objects me normalize kar deta hai. Debug karte waqt yaad rakho: `result["messages"]` me strings nahi, **message objects** milenge (`.content` attribute use karo).
- 🧪 **Hands-on lab:** is lecture ka code khud chalane ke liye is repo ka **`Practical/lab1_langgraph_basics.py`** run karo (`uv run` se chalta hai, Groq pe free via `langchain-groq` ChatGroq). Hamare labs course se thode alag hain (LangSmith tracing skip, paid tools ki jagah free alternatives) — but is lecture me waise bhi sirf pure-Python node hai, koi external service nahi.

---

## 🧠 Takeaway (yaad rakho)

1. **Node = function**: old state in, new state out — **immutable**, old state ko mutate nahi karna.
2. **Edges START → node → END** wire karte hain (`langgraph.graph` ke constants), phir **compile** karke graph display/run hota hai.
3. **`invoke(state)`** se graph execute hota hai — wahi word jo LangChain me hai.
4. **Graph ka LLM se koi rishta zaroori nahi** — random noun+adjective wala "silly language model" bhi valid LangGraph node hai.
5. **Reducer sirf concatenate nahi karta** — text ko **HumanMessage/AIMessage** objects me package bhi karta hai, behind the scenes.

---

<details>
<summary>📜 Full English Transcript (original, click to expand)</summary>

Okay. So here we are looking at our node creation. Remember a node is a function. So we're going to create a function. It's called our first node. It takes an old state and it returns a new state. Its states are immutable as we say. And so we are not going to do anything. We're not going to come and mutate old state. In fact, you may see from the way that it's grayed out here that we don't actually touch old state, which is unusual, but just for this example. So what are we actually going to do? So we're going to make a string called reply. And that reply is going to be some random word choice of a noun. And then the word are and then a random choice of an adjective. And we're going to create one of these kinds of message structures, an OpenAI familiar message structure, and put that into messages. We're going to say that the new state is another, a new state class. We're going to instantiate it passing in this messages. And we are going to return that, the new state. And that is the end of our first node. And we then call graph dot add node. This is how we officially add it to the graph that is being built. We give it a name, we call it first node, and we pass in the function, the function that represents the node called our first node. Okay. So we're going to run that cell.

And now we're coming on to look at creating our edges. So you can see here that I now call graph builder add edge to add a couple of edges. And you'll see that these words start and end there. So what are they? Well, these are things that we've imported at the top from langgraph.graph. They are constants START and END. And of course they signify the beginning of our workflow and the end of it. And so here what we say is we want an edge to take us from the start to our first node. And then we want another edge to go from the first node to the end. Okay, that sounds logical doesn't it? So we'll run that.

And now with that we get to step five, which you'll remember is compiling the graph. It's saying we're done. This is our workflow. And we can now display it. This is rather nice, a quick way to show visually what it is we're talking about. And hopefully this will be no surprise. We've got a start going into our first node going into our end. What could be easier? That's lovely. Okay, so we've done the five steps, which is of course the first part of running a LangGraph system. We've compiled our graph and we've done it by adding nodes and edges. It's now time to run it.

Okay. And what we're going to do is to run it. We're going to create a Gradio chat function. Why not. Remember Gradio chat functions take the user's current input and the history of prior inputs, and it's meant to respond with the next output. That's just what you do with a Gradio chat function that we're going to pass into Gradio's chat interface right there. So that's what we have to do. So what do we want to do? Well, we're going to turn the message into a standard OpenAI format and put that into a message. We're then going to create a state object with that as the message. We are then going to invoke our graph. And this is the key word invoke. You may be familiar with it because it's the word in LangChain as well. So you invoke a graph in LangGraph with the state in order to get the result. And that's what's going to execute our graph. And what will come out will be the result. And we will print it and we will also return it. And that will come out of our chat function.

And so with that let's run this and see what happens. Well, we have a Gradio UI. That's good. Let's say hi there. Muffins are haunted. Is that so? Penguins are sparkly. You don't say. Penguins are outrageous. For real. Pickles are untrustworthy. Ha ha ha. You get the idea. Uh, so, uh, this is the results of our small language model that is picking a random noun and adjective. And I show you this, if you're wondering what on earth are you doing — I'm doing it to show that the graph setup has nothing to do with LLMs necessarily. The node is just a function, in this case a silly function, but it's a function there and it's taking in a state and it's returning a state, and it doesn't need to have anything to do with LLMs.

Now down here, I'm printing the result of this. And let me just show you that print statement. Uh, we're printing what's coming back from calling invoke on the graph. And I want to point out that it may be something a bit different to what you're expecting, because it's not messages with just a list of strings. It's got a list of these things called HumanMessage, which you may know from LangChain work. It's like a construct to package things up. And this is of course the result of the reducer running. And when I said before that the reducer simply concatenates things into a list, I wasn't telling the full story, because it also does some of this packaging up that comes with LangGraph. So if it just takes the text that's come back, it knows how to package it into a HumanMessage in terms of the things that I was saying, and an AIMessage in terms of muffins are haunted and penguins are sparkly and the like. So this is some of the stuff happening behind the scenes as a result of LangGraph, which doesn't really matter to us. We're taking advantage of that.

But we just wrote a simple, a super simple state. Uh, super simple node. We made a state that contained messages. We made a node — we take in an old state, we return a new state which is using this random sentence, and it works. We can invoke our graph and get a response, and we can have a conversation, or rather one-sided conversation, with a silly language model. All right, let's do something more sensible.

</details>

---
*Source: Official Udemy lecture transcript (auto-captions, lightly cleaned). Notes in Hinglish for self-study.*
