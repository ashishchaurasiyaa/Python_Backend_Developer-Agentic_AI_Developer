# L70 — Day 1: LangGraph Theory — Core Components

> **Week 4 — LangGraph** · ⏱️ ~10m · 🎥 Lecture 70 of 131
> **Instructor:** Ed Donner · **Lecture ID:** 49821325

---

## 🎯 Ek Line Mein (TL;DR)

LangGraph ka core vocabulary — **Graph** (poora agent workflow), **State** (application ka current snapshot, immutable data), **Nodes** (Python functions jo kaam karte hain), **Edges** (Python functions jo decide karte hain agla kaam kya hoga) — plus graph banane ke **5 steps**: State class define karo → **Graph Builder** start karo → nodes banao → edges banao → graph **compile** karke run karo.

---

## 📝 Hinglish Explanation (Detailed)

- Ed pehle expectation set karta hai: **nayi terminology aur naye concepts** aane wale hain. CrewAI wala sab kuch side me rakh do — **compartmentalize** karo. Terminology jaldi cover hogi, aur Ed usse repeat kar-kar ke drill karega taaki second nature ban jaye.

- **Graph** — LangGraph me agent workflows ko ek **graph** ke roop me describe kiya jata hai. CS background walon ke liye familiar concept: ek **tree-jaisa structure** jisme cheezein aapas me connected hoti hain, ek hierarchy jisme ek cheez doosri pe depend karti hai. Workflows ko graph ke roop me represent karna — yahi LangGraph ka **core idea** hai (naam se hi clear hai).

- **State** — application ka **current snapshot**, current "state of affairs". Ye ek **object** hai jo poore application ka state of the world encapsulate karta hai, aur **poori application me share** hota hai. Important: state **information/data hai, function nahi**. LangGraph me state baar-baar use hoga, isliye ye yaad rakhna fundamental hai.

- **Nodes** — graph ke points. Lekin twist ye hai: LangGraph me **har node ek Python function hai**. Pehli baar sunne pe confusing lagta hai kyunki normally graphs me nodes ko "data" samajhte hain — yahan nodes **logic/operations** represent karte hain. Har node:
  - **current state input** me leta hai,
  - kuch **karta** hai (LLM call, koi **side effect** — file me likhna, duniya me kuch change karna),
  - aur ek **updated state return** karta hai.

- **State ko immutable samjho** — aap state object ko **change nahi karte**. State receive karte ho, aur ek **naya state** return karte ho jo pehle wale se different hota hai. Ye functional-style pattern LangGraph ka core hai.

- **Edges** — graphs **nodes aur edges** se bante hain. Edges = nodes ke beech ke **connections** (lines). LangGraph me edges bhi **Python functions** hain jo decide karte hain ki **state ke basis pe agla kaunsa node execute hoga**.
  - **Simple edge**: seedha "ye next chalega". Example: ek node "hello" print karta hai, doosra "goodbye" — connected hain to pehle hello, phir goodbye.
  - **Conditional edge**: kisi condition pe depend karta hai — shayad agla node chale, shayad nahi.

- **One-liner yaad rakho**: **Nodes do the work** (kaam karte hain), **edges choose what to do next** (decide karte hain aage kya hoga). Bas — yahi main terminology hai. Ye samajh gaye to LangGraph ka zyada-tar raasta clear hai.

- Diagram-wise: orange circles = nodes (3 operations), unke beech lines = edges. Ek edge **non-conditional** (top node chala to next pakka chalega, aur first node ka output state ban ke pass hoga), doosra edge **conditional** (kuch situations me bottom-right node chalega).

- **Graph banane ke 5 steps** (aaj sirf theory, code kal — Ed chahta hai ye terminology pehle sink-in ho):
  1. **State class define karo** — state object nahi, **class**, kyunki naye state objects baar-baar create honge. Is class ke saath ek concept juda hai — **reducer** — bahut important, lekin uski detail kal (L71) me.
  2. **Graph Builder start karo** — ye wo cheez hai jisse aap graph ke saare nodes lay out karte ho. Ye sab **upfront** hota hai — abhi kuch run nahi ho raha.
  3. **Node create karo** — ek function jo koi operation represent karta hai.
  4. **Edges create karo** — steps 3–4 repeat ho sakte hain: bahut saare nodes aur edges bana ke aap apne agent system ki **"story" lay out** karte ho. Ye sab system ke live hone se **pehle** — graph **define** karna hai, run karna nahi.
  5. **Graph compile karo** — compile operation graph ko executable form me badal deta hai — phir **kick off** karo aur ye run hota hai.

- **Do-phase mental model** (Ed teen baar repeat karta hai, itna important hai): jab aap LangGraph application run karte ho, **2 phases** hote hain —
  - **Phase 1 (define/meta phase)**: aapka code graph ko lay out karta hai — state class, graph builder, nodes, edges, compile. Ye ek tarah se **runtime pe dynamically program likhne** jaisa hai — hum normally coding me aisa "meta phase" nahi karte.
  - **Phase 2 (execute phase)**: compiled graph ko **invoke** karte ho aur wo actually run hota hai.
  - **Dono phases** aapke application run ka hissa hain.

- Kal (Day 2 / L71) lab me ye paanchon steps ka actual code likhenge aur pehla LangGraph agent banayenge. Agar abhi poora click nahi hua to fikar mat karo — code dekhte hi "easy peasy" lagega.

---

## 🔑 Key Concepts / Important Terms

| Term | Simple Hinglish Meaning |
|------|--------------------------|
| **Graph** | LangGraph me agent workflow ka representation — tree-jaisa structure, nodes + edges se bana |
| **State** | Application ka current snapshot — ek shared object jo "state of the world" encapsulate karta hai; data hai, function nahi |
| **Node** | Graph ka point = ek **Python function** jo state input leta hai, kaam karta hai (LLM call / side effect), aur naya state return karta hai |
| **Edge** | Nodes ke beech ka connection = Python function jo state dekh ke decide karta hai agla node kaunsa chalega |
| **Conditional Edge** | Aisa edge jo condition ke basis pe decide karta hai ki agla node chalega ya nahi |
| **Immutability (State)** | State object ko mutate nahi karte — receive karo, naya updated state return karo |
| **Graph Builder** | Wo object jisse aap upfront nodes/edges lay out karte ho — define phase ka tool |
| **Reducer** | State class ke saath juda important concept (state updates merge karne ka rule) — detail L71 me |
| **Compile** | Defined graph ko executable form me convert karna — uske baad hi invoke/run hota hai |
| **Two Phases** | Phase 1: graph define karna (builder, nodes, edges, compile); Phase 2: invoke karke run karna |

---

## 💡 Backend Dev Ke Liye Note (aapke liye)

- **Builder pattern + DAG/state machine** — graph builder bilkul waise hi hai jaise Airflow me DAG define karna ya SQLAlchemy me query build karke phir execute karna: pehle **declarative blueprint** banao, phir compile/run. Define-then-execute ka ye separation aapko ORM query builders aur Spark ke lazy evaluation se already familiar hai.

- **Immutable state = Redux reducer pattern** — node ek pure-function jaisa hai: `(state) -> new_state`. Ye functional pattern concurrency me bahut kaam aata hai — shared mutable state ke race conditions nahi, har step ka output traceable. Event-sourcing me jaise events se naya state derive hota hai, waise hi yahan har node ek naya state version return karta hai.

- **Edges = routing logic** — conditional edge ko ek dispatcher/router samjho jo response ke basis pe agla handler choose karta hai — `if/elif` chains ya FSM transition tables jaisa, bas first-class graph citizen ke roop me.

- **Hands-on lab**: is lecture ka code khud chalane ke liye `Practical/lab1_langgraph_basics.py` run karo (is repo me, `uv run` se chalta hai, Groq pe free via langchain-groq ChatGroq).

---

## 🧠 Takeaway (yaad rakho)

1. **Graph** = poora agent workflow; **State** = shared snapshot object (data, function nahi).
2. **Nodes Python functions hain** jo kaam karte hain; **Edges Python functions hain** jo decide karte hain agla kya — "nodes do the work, edges choose what to do next".
3. **State immutable treat karo** — node state receive karta hai aur **naya** updated state return karta hai, mutate nahi karta.
4. **5 steps**: State class define → Graph Builder start → Nodes create → Edges create → **Compile** & run. (**Reducer** ka concept L71 me aayega.)
5. LangGraph app ke **2 phases** hote hain: pehle graph **define** hota hai (meta phase, runtime pe), phir compiled graph **invoke** ho ke actually chalta hai.

---

<details>
<summary>📜 Full English Transcript (original, click to expand)</summary>

All right, so let's get stuck in. So before we get stuck in, let me set your expectations. There's going to be terminology. There's going to be some new concepts coming with LangGraph just as we've had in the past. And I realize that it's a bit jarring to say put all the crew stuff to one side, just just put that away. Compartmentalize. We're on to something new now, but it will be quick. We're going to get through the terminology quickly, and I'm going to be drilling it into you by repeating it several times, and then it's going to be second nature and you'll forget all about crew.

All right. So what is the terminology. Here we go. So agent workflows are described in LangGraph speak as a graph. A graph is something that'll be very familiar to people in computer science. But a graph you can think of like a tree structure. It's something which has, uh, I'm about to say the names of the things I'm about to describe, but it has things connected together in, in something which looks a bit like a tree and some sort of a hierarchy where one thing depends on others beneath it. And so this, this idea of representing workflows in this kind of graph way, that is the the core idea of LangGraph as the name gives away.

And then a state. So the state is something that represents the current snapshot, the current state of affairs, the status of your whole application. It's an object that that needs to encapsulate the state of the world. And that object is something which, which, uh, is is shared across the whole application. And it's something very fundamental to LangGraph. So you need to remember state. We're going to be using state a lot. And that's something which is it is uh it's a variable. It's like um it's, it's a, it's information. Um, it's not not a function. It's information.

Nodes are functions. So a node which when people talk about graphs, they talk about nodes. They are the points on the graph. They are the, the, the things that are going to get connected together. The nodes are actually representing a function. Every node is a Python function. And that can be confusing the first time you hear it. Because when you think about graphs, you sometimes think of nodes as being things, as being data connected in some way. But no nodes in a graph are functions. They are Python functions, and they represent a piece of logic, a piece of agent logic, a thing, an operation of some sort. They receive the current state as an input. They do something. They do something that might, might involve calling an LLM. It might involve some sort of a side effect. Changing something, writing something to a file, doing something that affects the world. And then they return an update, an updated state. That's that's what comes afterwards. So they take in a state, they do something and they return a new state. And I should say that the state you should think of as being like an immutable thing, the state object itself. You don't. You don't change it. You receive a state and then you return a new state, which is a difference from the state you had before. So far, you're with me. State and nodes that the the two words.

And then edges. And anyone that's ever looked at graphs will be familiar with the term edges. The edges, of course. The lines. The words I was trying not to say earlier is that graphs consist of nodes and edges. Edges are the connections between the nodes, and edges in the graph are also Python functions. They are Python functions that determine what node should be executed next based on the state, so the state can tell it what happens next. Now there are simple edge connections, which just means that is the next thing to happen. So if you have one node that is a function, the Python function that uh, that prints hello to to the output. And you have another node that prints goodbye. And they're connected. Then it will print hello, and then it will print goodbye. And that's it. But you can have, uh, connections which are conditional, which depend on something happening. And in that case, that would mean that one operation would happen and then subject to the condition, maybe the other one would happen, maybe not. So that is an edge.

And then simply put, nodes are the things that do the work. They are the things that carry out tasks. They do stuff and edges are the things that determine, okay, that stuff was done, what's the next stuff that should be done? And that's all there is to it. That's the that's the main terminology. There are a couple of other things, but this is the core stuff. So if you've got this then you're most of the way there with LangGraph.

And of course it would be nice to show this in some sort of a diagram. And this is the obvious diagram. So no surprise this is what it looks like. These are nodes. Uh, the three orange circles there representing the three nodes, three operations happening in this graph, the edges. I'm trying to show there that one edge is not conditional. It just wants the top node is run, then the next one will run and it will have the state that's passed in will be the result of the, the the output from that first node. And the other edge is meant to show some sort of conditional edge that in some situations the node on the bottom right will run. So again, nodes do the work, edges choose what to do next. So that again is the terminology.

So we are going to build our first graph. We're actually not going to do it today. Today is just a theory. Only one because I'm going to leave the practical for tomorrow. I'm going to let you brew over this. I'm going to let this sort of sink in so that the new terminology is something that's super clear to you. But the five steps to building your graph. Your first graph running it. And it's going to have some more terminology. First of all, you have to define your state class, the class which is going to store state. You don't you don't to create a state object because there'll be new objects created all the time. Uh, and, and so it will define the state class and you'll find out when we actually do this. There's something associated with that state class known as the reducer. And that's a very important concept. But I'm going to leave that concept to tomorrow.

Secondly you start something called the graph builder. And the graph builder is a thing you're going to use to lay out all the nodes in your graph. This is something you're doing up front. Nothing's actually running. It's not like we actually have an agent system that's running. This is all. Before we run the agent system, we first start a graph builder. We then create a node that is one of these functions that's going to represent some operation that we're going to want to happen as part of this LangGraph and then we create some edges and we may repeat steps three and four. We may create lots of nodes and lots of edges to lay out the story. We're laying out the story of what we want our agent system to do, and this is all before it's actually live, before it's doing anything. It's not like we create nodes and edges and then things happen. No, we create nodes and edges as part of defining the graph, describing what this will do. Think of this as a bit like writing a program, but we're sort of doing it dynamically at runtime.

So once we've done that, once at runtime, we've we've described the node, we've created the nodes, we've created the edges. We've laid out our whole agent workflow. We then run an operation called compiling the graph. And that will turn this into something that's ready to be executed. And then we kick it off and it runs. So it is important to get your head around this. What I've described there, this 12345. This is all stuff that that is running when we when we start our our system running, we do this process of defining the state class, starting the graph builder, creating nodes and edges, and compiling the graph. It's almost like part of running our system involves the sort of two phases, a phase when it's like defining itself, laying out the whole workflow, and then a second phase when that actually runs. And so that first phase, we're not really used to doing that when we code. We don't normally have a sort of meta phase when we're describing what it is that we want to do and then running it. But that's how it works with LangGraph, and I hope that's made some sense. I'm going to explain it one more time when we go through this tomorrow. But this is the, uh, this is this is the overall approach that's used for building agentic workflows with LangGraph.

And with apologies for belaboring the point, let me say it one more time. When you run a LangGraph application, when you kick it off, there's two phases. Two things happen. The first thing is that it runs some of your code that lays out the graph that defines what it is that you're trying to achieve with agents. And then once you've done that and that is these five steps here. Once you've done that, you then initiate it. You then run it, you invoke it. And then off this graph runs. And those two phases, both of them are part of running your application. And so what we're going to do next time is go through these five steps. Write code that will do all of this. And then call it. And you will then see the results all in one go. And if this if this is completely clear to you then sorry for saying it three times. Uh, hang on in there. And if this is not completely clicking for you, then then fear not when you see the actual code, I feel like it's going to come together and it's going to be easy peasy. And that indeed is what we're going to do tomorrow. So in day two we will do some actual code. We'll get to the lab. We'll build our first LangGraph agent I can't wait. I'll see you then.

</details>

---
*Source: Official Udemy lecture transcript (auto-captions, lightly cleaned). Notes in Hinglish for self-study.*
