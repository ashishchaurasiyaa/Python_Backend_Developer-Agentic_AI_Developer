# L71 — Day 2: Managing State in Graph-Based Workflows

> **Week 4 — LangGraph** · ⏱️ ~6m · 🎥 Lecture 71 of 131
> **Instructor:** Ed Donner · **Lecture ID:** 49821329

---

## 🎯 Ek Line Mein (TL;DR)

LangGraph mein **state immutable** hota hai — node kabhi old state ko modify nahi karta, hamesha **naya state object return** karta hai; aur har field pe optional **reducer function** laga sakte ho jo LangGraph ko batata hai ki new state ko current state ke saath kaise **combine** karna hai — yahi trick **parallel nodes** ko safely run karne deti hai.

---

## 📝 Hinglish Explanation (Detailed)

- **Recap (repetition se yaad hota hai)** — LangGraph mein ek **agent workflow** (agent system run karne ka ek particular pattern) ko ek **graph** ke roop mein represent kiya jata hai — tree structure jaisa.
  - **State** = system ka **current snapshot**, "state of the world" kisi bhi point pe.
  - **Nodes** aur **edges** dono **Python functions** hain.
  - **Nodes kaam karte hain** — actual work jo consequences rakhta hai (LLM call, tool call, etc.).
  - **Edges decide karte hain** ki node run hone ke baad **aage kya hoga** (next kya).
- **Head-twister wali baat (phir se)** — jo **5 steps** hain, wo sab **code run karte waqt, agents run hone se PEHLE** hote hain. Matlab ek **"pre-thing"** hai jise **graph building** kehte hain — pehle layout banao ki kya karna hai, phir use **kick off** karke actually karwao. Ye do alag phases hain: **build time** vs **run time**.
- **5 steps ek baar phir:**
  1. **State class define** karo — kaunsi information maintain hogi.
  2. **Graph builder** start karo.
  3. **Node(s)** create karo.
  4. **Edge(s)** create karo — sab kuch hook up karne ke liye.
  5. **Graph compile** karo — ab "ready for primetime".
- **State is IMMUTABLE — ye lecture ka core point hai:**
  - **Immutable** ka matlab: ek baar object create karke values assign kar di, to uske **contents kabhi change nahi karoge** — usko **mutate** nahi karna.
  - **Kyun?** Kyunki state system ka ek **snapshot** represent karta hai. Tum chahte ho ki **kabhi bhi us snapshot pe wapas ja sako**. Agar state ke contents change ho jaayein, to wo snapshot maintain hi nahi rahega.
- **Concrete matlab — node function ka contract:**
  - Node ka function simply **state input mein leta hai, state output mein return karta hai**.
  - Lekin jo return hota hai wo ek **different object, different instance** hota hai — incoming state nahi.
- **Example: `my_counting_node`** (artificial but clear):
  - State mein bas ek field hai: `count` (ek number).
  - Function `old_state` leta hai → `old_state.count` read karta hai → usme **+1** karta hai → **old state mein set NAHI karta** → ek **naya State object** banata hai, naye state ka `count` = incremented value, aur wahi **naya object return** karta hai.
  - Ed jaan-bujh ke point ko belabor kar rahe hain — ye dhyan nahi rakha to **"all sorts of traps"** mein fasoge.
- **Ek aur complication: REDUCERS:**
  - State ke **har field ke liye optionally ek special function** specify kar sakte ho — isko **reducer** kehte hain (technical naam).
  - Tum LangGraph ko bata rahe ho: "is field ke liye ek reducer hai."
  - **Reducer ka job:** jab bhi tum **new state return** karte ho (old state pe based new version), LangGraph is reducer function se decide karta hai ki tumhare new state ke us field ko **current state ke saath kaise combine** kare.
- **"Par kyun? Hum khud hi field update kar sakte hain na?"** — yahi obvious sawaal hai, aur answer hi asli magic hai:
  - Reducer ki wajah se graph **multiple nodes ek saath (parallel) run** kar sakta hai.
  - Sab nodes apna-apna state return kar rahe hain, aur **koi risk nahi** ki ek node ka result doosre node ki progress ko **overwrite** kar de.
  - Jis field pe reducer laga hai, LangGraph **behind the scenes alag-alag states ko combine** kar lega — yahi **clever trick** hai jo safe parallelism allow karti hai.
- Abhi ye thoda abstract lag raha hai to tension nahi — **code mein ye concrete ho jayega**; hum actually ek reducer use karenge aur clear hoga ki kyun zaroori hai aur kaise help karta hai.

---

## 🔑 Key Concepts / Important Terms

| Term | Simple Hinglish Meaning |
|------|--------------------------|
| **State** | System ka current **snapshot** — "state of the world" at any point; graph ke through flow karta hai |
| **Node** | Python function jo **actual kaam** karta hai (consequences wala work); state leta hai, **naya** state return karta hai |
| **Edge** | Python function/connection jo decide karta hai ki node ke baad **next kya** hoga |
| **Graph building** | Wo "pre-thing" — 5 steps jo **agents run hone se pehle** hote hain; layout banana, phir kick off karna |
| **5 Steps** | 1) State class define, 2) Graph builder start, 3) Nodes banao, 4) Edges banao, 5) Compile |
| **Immutable** | Object create hone ke baad uske contents **kabhi change nahi** karte — mutate nahi karna |
| **Mutating** | Kisi existing object ke contents change karna — LangGraph state ke saath ye **kabhi mat karo** |
| **Reducer** | Field-level special function jo LangGraph ko batata hai ki **new state ko current state se kaise combine** karna hai |
| **Parallel nodes** | Multiple nodes ek saath run ho sakte hain; reducers ensure karte hain ki koi kisi ki progress **overwrite na kare** |

---

## 💡 Backend Dev Ke Liye Note (aapke liye)

- **Immutable state = event sourcing mindset, not CRUD:** node function `old_state -> new_state` exactly waise hi hai jaise Redux reducers ya event-sourced aggregates — tum row ko `UPDATE` nahi karte, naya snapshot append karte ho. Isi wajah se LangGraph baad mein **checkpointing/time-travel** de pata hai: har super-step ka snapshot preserved rehta hai, jaise DB snapshots/WAL se point-in-time recovery.
- **Reducer = merge strategy for concurrent writers:** ye wahi problem hai jo tumne DB mein dekhi hai — do transactions same row pe likhein to **last-write-wins data kha jata hai**. Reducer ek declarative conflict-resolution function hai (jaise CRDTs ya `ON CONFLICT DO UPDATE`), jisse parallel nodes (fan-out) bina lock ke safely same field mein contribute kar sakte hain. Code mein ye `Annotated[list, add_messages]` jaisa dikhega — type hint ke andar metadata, jo LangGraph runtime padhta hai.
- **Build time vs run time** ko Airflow se map karo: DAG definition (graph building, 5 steps) vs DAG run (agent execution). `compile()` tak sirf blueprint ban raha hai — koi LLM call nahi hua.
- **Hands-on lab:** `Practical/lab1_langgraph_basics.py` (is repo me, `uv run` se chalta hai, Groq pe free via `langchain-groq` `ChatGroq`) — is lecture ka code (State class, immutable nodes, reducer wala counting example) khud chalane ke liye ye lab run karo.

---

## 🧠 Takeaway (yaad rakho)

1. **State immutable hai** — node kabhi incoming state ko mutate nahi karta; hamesha **naya state object** banakar return karta hai.
2. **Node ka contract:** state in → (kaam karo) → **new** state out. `old_state.count + 1` ko naye object mein daalo, old mein set mat karo.
3. **Reducer** = per-field combine function jo tum LangGraph ko declare karte ho — wo decide karta hai ki returned state current state ke saath **kaise merge** ho.
4. **Reducers hi parallel nodes possible banate hain** — multiple nodes ek saath chalein to bhi koi kisi ki progress overwrite nahi karta.
5. **Graph building (5 steps) pehle hota hai, agent execution baad mein** — define state → builder → nodes → edges → compile.

---

<details>
<summary>📜 Full English Transcript (original, click to expand)</summary>

And we're back. I left you with a day for the LangGraph ideas to marinate, and hopefully they have marinated well, and you're now ready to actually go and do something. But as always, I do like to repeat a couple of times because repetition helps with these things. So one more time in LangGraph an agent workflow, a particular pattern for how you will run an agent system is represented as a graph. Like a tree structure, use state to represent the current snapshot of affairs, the state of the world at any one point, and you build nodes and edges which are Python functions, and a node decides how to go from one state to another, and edges or nodes do the work, they actually carry out something which has consequences and edges decide what to do next. Once a node has run.

And you'll remember I talked about five steps, and I tried to make it clear that the thing that's a bit of a like a head twister is that these five steps that I'm talking about, they all happen when you run your code, and they happen before you can even run your agents. So when you run your code, there is this prething that has five steps in it, and then the agent running and that prething is what would be called graph building that that is laying out what you want to do, and then you kick it off to actually do it. And those five steps, of course, you define your state class describing the information that will be maintained. You start the graph builder. You then create a node or many. You create edges to hook it all up or many. And then you compile the graph and you're now ready for primetime.

All right. So I want to get a little bit deeper about the state before we get to the code. The final thing before the code so state is what's known as immutable. It's a word that that people like to say a lot and hopefully know what it means. But you might not. So let me be very clear. What it means to be immutable is that you will never change the contents of this object. It is something which, once you've created it and assigned the values to it, it keeps those values. And you don't ever do what's called mutating it, which is changing it. And, and that's, that's important because, uh, state is something which is going to represent a snapshot of the system. You want to be able to always go back to that snapshot. It's something which which in itself, if the contents of that state changes, you wouldn't be able to maintain that snapshot.

Uh, so just to get concrete on what that means, what that means is that if you when you write the function for a node, that function is going to be a function which quite simply receives a state as its input and it returns a state as its output. And the thing that it returns is different, a different object, a different instance of state than the one that came in. So in this example called my counting node, let's imagine that we have a state object. And the only thing that it has is a field called count. And count is something which is a number that counts. Uh, and the purpose of my counting node is to add one to count. So I realize this is quite artificial, but just to give you a clear sense of it. So this is a function, my counting node. It takes a state, old state. It it collects the count that is stored within old state. Old state dot count. It adds one to it and then it doesn't return like the old state object doesn't try and set count in old state. No, it creates a new state object and sets the new state's count to be this incremented count and it returns that new state object. And I realize I'm belaboring the point as I often do, but it's an important one, and you need to keep this in mind. And otherwise you'll get in all sorts of traps.

So there's one more complication for each of the fields in your state. You can optionally specify a special function to be associated with that field. And you're specifying this to LangGraph. You're saying to LangGraph, hey, I want you to know that for this field in my state, it's a special field that has a reducer, this function called a reducer. Reducer is the technical name for this kind of function. And the job of the reducer function is that when you ever update, when you ever return a new state, I was going to say update the state, but that might be confusing. Whenever you return a new state, which is a new version based on an old state, you've done something. You've returned a new state. LangGraph can use this reducer function to decide how to combine each the specified field in your new state with the current state, you see that. So it can use this function called a reducer, so that if you have a field maybe it's count, maybe it's a different field. It would use that to combine it with the old state.

Now, now that I've said that, you're probably thinking about that for a second and you're like, hang on, why, why, why would you need to do that? We've got a node like this. We've got the old state. We can do that ourselves. We can just simply update the field in whatever way we want. Why do we need to specify a reducer function separately? Well, here's why. Because this means that that graph can run multiple nodes at the same time. They can all be running and they're all returning state. And there's no risk that one node runs and it overwrites the progress that a different node made at the same time. If for any field that has a reducer like this, it will always be able to work, they'll be able to combine different states behind the scenes. And that's that's the kind of that's the clever trick that allows that to be so. So you'll see when if this is seeming a little bit abstract, it's going to be concrete. When we look at the code, we will indeed use a reducer. And it's going to be super clear why we need to do that and how it helps.

</details>

---
*Source: Official Udemy lecture transcript (auto-captions, lightly cleaned). Notes in Hinglish for self-study.*
