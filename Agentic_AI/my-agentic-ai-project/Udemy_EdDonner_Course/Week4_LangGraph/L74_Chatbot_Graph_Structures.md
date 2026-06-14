# L74 — Day 2: Building an OpenAI Chatbot with Graph Structures

> **Week 4 — LangGraph** · ⏱️ ~4m · 🎥 Lecture 74 of 131
> **Instructor:** Ed Donner · **Lecture ID:** 49821339

---

## 🎯 Ek Line Mein (TL;DR)

Pehla **real LLM-powered LangGraph example** — ek **chatbot node** jo **ChatOpenAI** ko invoke karta hai, **START → chatbot → END** wala simple graph, Gradio UI ke saath — lekin demo dikhata hai ki har `graph.invoke()` fresh hota hai, isliye **conversation memory nahi hai** (woh kal **checkpointing** se aayega).

---

## 📝 Hinglish Explanation (Detailed)

- Pichle lecture ka "silly example" (random adjectives wala) jaan-bujh ke bina LLM ke tha — point ye prove karna tha ki **nodes ko LLM call karna zaroori nahi hai**, node bas ek Python function hai jo state leta hai aur naya state return karta hai. Ab us hi 5-step recipe mein **real LLM** plug karte hain.

- **Step 1 — State define karo:** wahi pattern — ek state class jisme **`messages`** field hai (Annotated + reducer wala idea pichle lectures se). Phir us state se **`StateGraph` builder** banate hain.

- **Step 2 — LLM banao via `ChatOpenAI`:** ye construct **LangChain** se aata hai — LangGraph ka **sibling** project (same company, LangChain ecosystem). Important nuance jo Ed clear karta hai:
  - **LangChain ke LLM wrappers use karna optional hai** — tum directly OpenAI SDK call kar sakte ho, ya **OpenAI Agents SDK** bhi use kar sakte ho node ke andar. Node ke andar kya hota hai, LangGraph ko farak nahi padta.
  - Lekin LangChain use karna **simpler** hota hai aur **zyada-tar community examples LangGraph + LangChain** combo hi use karte hain — isliye course mein bhi yahi approach.

- **Step 3 — Chatbot node banao:** ek function `chatbot(old_state) -> new_state`:
  - **`llm.invoke(old_state.messages)`** — old state ke `messages` field ko LLM mein pass karo (`invoke` LangChain/LangGraph ka standard verb hai).
  - LLM ka **response** ek naye state object ke `messages` field mein daal ke **naya state return** karo (functional style — old state mutate nahi karte).
  - `graph_builder.add_node("chatbot", chatbot)` se ye node graph mein register ho gaya.

- **Step 4 — Edges:** `START → chatbot` aur `chatbot → END`. Bas — linear, single-node graph.

- **Step 5 — Compile + visualize:** `graph_builder.compile()` se runnable **graph** milta hai, aur diagram mein clearly dikhta hai: **start → chatbot → end**.

- **Gradio ke saath wiring:** chat function ek **initial State** banata hai (user ke messages ke saath), phir **`graph.invoke(initial_state)`** call karta hai, result print + Gradio mein show. "Hi there" bolne par **actual OpenAI call** hota hai — koi silly adjectives nahi.

- **Message objects dikhe console mein:** user ka input **`HumanMessage`** object ke roop mein, aur OpenAI ka reply **`AIMessage`** object ke roop mein — ye LangChain ke standard message types hain jo `messages` list mein flow karte hain.

- **Bada catch — memory nahi hai:** har Gradio turn par hum **graph ko fresh invoke** kar rahe hain, state mein sirf current message hai, **history nahi**. Live demo:
  - "My name's Ed" → "Nice to meet you, Ed!"
  - "What's my name?" → "Sorry, I don't have access to your personal data." 🤦
  - Matlab graph **context retain nahi** kar raha — har invoke ek **stateless, isolated run** hai.

- **Teaser for tomorrow:** ye memory problem kal solve hogi (spoiler: **checkpointing** — MemorySaver etc.), saath mein **tools** wapas aayenge aur kuch aur cheezein bhi. Aaj ka takeaway: basic LLM graph banana ab trivially easy hai, asli value memory + tools layering mein hai.

---

## 🔑 Key Concepts / Important Terms

| Term | Simple Hinglish Meaning |
|------|--------------------------|
| **ChatOpenAI** | LangChain ka OpenAI chat-model wrapper — LangGraph node ke andar LLM call karne ka convenient tareeka. |
| **LangChain (sibling of LangGraph)** | Same ecosystem ka abstraction library — optional hai, par community examples mostly LangGraph + LangChain hi use karte hain. |
| **Chatbot node** | Function jo `old_state` leta hai, `llm.invoke(old_state.messages)` karta hai, aur response ke saath **naya state** return karta hai. |
| **`invoke`** | LangChain/LangGraph ka universal "run it" verb — LLM par bhi (`llm.invoke`) aur compiled graph par bhi (`graph.invoke`). |
| **HumanMessage / AIMessage** | LangChain ke typed message objects — user input vs LLM response, dono `messages` list mein store hote hain. |
| **START → chatbot → END** | Is lecture ka pura graph — single node, do edges, compile, done. |
| **Stateless invoke** | Har `graph.invoke()` fresh run hai — bina checkpointing ke koi conversation history carry nahi hoti. |
| **Memory problem** | "What's my name?" fail hua kyunki state mein history nahi thi — kal **checkpointing** se fix hoga. |

---

## 💡 Backend Dev Ke Liye Note (aapke liye)

- **Stateless HTTP handler analogy:** ye graph bilkul ek **stateless REST endpoint** jaisa hai — har request (invoke) fresh, koi session nahi. "What's my name?" fail hona waisa hi hai jaise session middleware ke bina login state expect karna. Kal ka **checkpointer (MemorySaver/SqliteSaver) + `thread_id`** combo exactly **session store + session ID** ka role play karega — DB-backed session vs in-memory session jaisa hi mental model.

- **Node = pure function, LLM = injected dependency:** chatbot node `old_state -> new_state` pure function hai jisme LLM ek dependency ki tarah use hota hai. LangGraph ko parwah nahi ke andar ChatOpenAI hai, raw OpenAI SDK hai, ya Agents SDK — wahi **ports-and-adapters** thinking: graph orchestration layer hai, LLM client swappable adapter.

- **`HumanMessage`/`AIMessage` = typed DTOs:** raw dicts ki jagah typed message classes — wire format (`role: user/assistant`) ke upar ek typed layer, jaise tum Pydantic models ko raw JSON ke upar rakhte ho. Reducer (`add_messages`) in objects ki list ko append-merge karta hai.

- **Hands-on lab:** is lecture ka code khud chalane ke liye `Practical/lab1_langgraph_basics.py` run karo (is repo me, `uv run` se chalta hai, **Groq pe free** via `langchain-groq` ChatGroq — `ChatOpenAI` ki jagah). Hamare labs course se thode alag hain: **LangSmith tracing skip** (key nahi hai) — baki is lecture me Serper/Playwright nahi hai to koi aur difference nahi.

---

## 🧠 Takeaway (yaad rakho)

1. **5-step recipe + real LLM:** State define → graph builder → `chatbot` node (jo `llm.invoke(messages)` karta hai) → edges (START→chatbot→END) → compile. Bas, working OpenAI chatbot graph ready.
2. **LangChain optional hai** — node ke andar koi bhi LLM client chalega (raw SDK, Agents SDK), par `ChatOpenAI` simpler hai aur community examples isi pattern par hain.
3. **Node hamesha naya state return karta hai** — old state mutate nahi hota; response `messages` field mein jaata hai (`HumanMessage` in, `AIMessage` out).
4. **Har `graph.invoke()` stateless hai** — bina memory ke chatbot apna naam tak yaad nahi rakhta ("What's my name?" fail).
5. **Kal:** checkpointing se memory + tools ki wapsi — yahi LangGraph ki asli value unlock karega.

---

<details>
<summary>📜 Full English Transcript (original, click to expand)</summary>

Okay, now it's on to a proper example that we'll use with LangGraph. Just take the obvious. The reason I showed you the silly example was because I wanted to show that nodes don't need to have calls to LLMs, and they still do what they're meant to do. But now we are going to add an LLM. So we start by defining the state. We create a graph builder with that state. And now we create an LLM, a real LLM, using ChatOpenAI. So ChatOpenAI is a construct from LangChain, the sibling to LangGraph. Uh and that's what we'll be using to connect with our LLM.

And now you don't need to use LangChain's LLMs for this. You can use any LLMs. You could directly call the LLM yourself. You could also, uh, use maybe OpenAI Agents SDK. But it does make things a bit simpler sometimes if you use LangChain, and most of the community examples of course go from LangGraph to LangChain. So it's it's easy to do it that way. And that's what we'll do for here.

So we're going to create a new node called chatbot node. It takes an old state and it returns a new state. And what does it do? Well, it takes the the LLM and it invokes on that LLM. So it's again it's the LangChain LangGraph word invoke, uh, passing in the messages from old state. So old state has a messages field and that is what we pass in. And then for the new state, it creates a new state object which contains within it, as in its messages field, it contains the response. And we return the new state. And we add that node called chatbot, uh, into our graph builder. Done.

Now we'll add some edges from start to chatbot, from chatbot to end. Done. And now we will compile our graph. Step five. And we'll look at the graph. And sure enough, it goes start to chatbot to end.

And then we put it all together in a simple Gradio chat function. It takes an initial state, which is a state object set up with these messages like so. We then call graph dot invoke to actually call our graph. We print the result and we will also show the results back in Gradio. So here it is. And I can say hi there. And it's actually calling OpenAI. Now it's not using our silly adjectives. And you'll see down here that there's the user message and the response coming in these objects, this HumanMessage object that is coming back. Sorry, that HumanMessage is my "Hi there". I mean, there should be an AIMessage. There it is. There is the AIMessage, which is the response actually coming from OpenAI.

But one thing that's worth noting is that if I continue this conversation, every time we are invoking this graph, and you will see what you have probably already suspected, which is that we're not actually keeping track of any history here. Let's see that in action. Uh, if I, uh, say, um, "My name's Ed." "Nice to meet you, Ed. How can I assist you today?" "What's my name?" "I'm sorry, but I don't have access to your personal data." So there's a sign that it's not able to keep context. And you can see it yourself if you read the information that's going to and fro.

So because we've just got this simple graph that we were invoking each time, there's nothing particularly interesting happening here. And the state, uh, is just, just contains that, that, uh, doesn't contain the history or anything. So, uh, that's one of the things that we clearly need to address. And the good news is that we will indeed address it. But the bad news is not until tomorrow. But we'll also address things like tools, our old favorite, along with a couple of other things. So, uh, look forward to it. I'll see you then.

</details>

---
*Source: Official Udemy lecture transcript (auto-captions, lightly cleaned). Notes in Hinglish for self-study.*
