# L61 — Day 4: Crew AI Memory — Vector Storage & SQL

> **Week 3 — CrewAI** · ⏱️ ~12m · 🎥 Lecture 61 of 131
> **Instructor:** Ed Donner · **Lecture ID:** 49821197

---

## 🎯 Ek Line Mein (TL;DR)

CrewAI ka **memory** feature sirf chand lines of code mein **5 types of memory** de deta hai — **short-term** (Chroma vector DB + RAG), **long-term** (SQLite), **entity** (vector DB), **contextual** (in teeno ka umbrella) aur **user memory** — bas memory objects banao, `Crew(memory=True, ...)` set karo, aur jin agents ko yaad rakhna hai unpe `memory=True` laga do; end mein memory ka matlab bas itna hai ki **prompt mein zyada relevant context shove** ho raha hai.

---

## 📝 Hinglish Explanation (Detailed)

- **Recap — CrewAI project ke 5 steps** (Ed phir se drum-in karte hain):
  1. **`crewai create crew <project_name>`** — scaffolding banata hai (directories + files).
  2. **YAML files** (`agents.yaml`, `tasks.yaml`) fill karo — agents aur tasks define karne ke liye.
  3. **`crew.py`** module mein **decorators** se agents/tasks ke instances banao, crew create karo — yahin **structured outputs** (schema-conforming) aur **tools** aate hain: CrewAI ke remote tools jaise **Serper**, aur **custom local tools** jaise push notification wala.
  4. **`main.py`** update karo — inputs set karo jo YAML ke **`{curly}` templated fields** mein jaate hain.
  5. **`crewai run`** se chalao.

- **Aaj ka topic: CrewAI ka `memory` feature.** Ye CrewAI ka ek **prescriptive / opinionated** feature hai. Memory ka matlab: har LLM call pe **contextual information provide** karna.
  - **Manual way:** tum khud variables store karke tasks create karte waqt pass kar sakte ho.
  - **Framework way:** CrewAI out-of-the-box building blocks deta hai.
  - **Pro:** jaldi up-and-running, unki design thinking free mein milti hai.
  - **Con:** learning curve hai, aur ye **obscure** karta hai ki prompts ke peeche actually kya ho raha hai — framework adopt karne ka classic trade-off.

- **CrewAI ke 5 types of memory:**
  1. **Short-term memory** — recent interactions ko **vector database** mein store karta hai, **RAG (Retrieval Augmented Generation)** style. Currently executing agents ko **recent relevant info** access karne deta hai. (RAG na bhi aata ho to course ke liye chalega — bas code daal ke run dekhna hai.)
  2. **Long-term memory** — zyada **important information** ko **SQL database** mein store karta hai, longer-term recall ke liye — time ke saath **knowledge build up** hota hai.
  3. **Entity memory** — short-term jaisa hi; **people, places, concepts** ke baare mein facts ko **RAG database** mein store karta hai, **vector similarity search** ke liye, taaki context mein include ho sake.
  4. **Contextual memory** — Ed kehte hain ye thoda **misleading naam** hai; ye actually short-term + long-term + entity memory ka **umbrella term** hai jo sab ek saath query ho ke LLM prompt ke context mein pass hota hai. CrewAI ye sab abstract kar deta hai — bas chand lines of code.
  5. **User memory** — **user-specific info** store karne ke liye. Ye **odd one out** hai: CrewAI concept support karta hai, par querying aur prompt mein insert karna **mostly tumhare upar** chhoda hai (manual manage karna padta hai). Ed ko lagta hai future mein isme aur build karenge.

- **Trade-off reminder:** bahut kaam behind-the-scenes hota hai — benefit bada hai, par **visibility kam** — agar kuch galat jaye to **debug karna harder** hai.

- **Code — stock picker project mein memory add karna** (Cursor mein, `crew.py`):
  - **Imports:**
    - `from crewai.memory import LongTermMemory, ShortTermMemory, EntityMemory`
    - `RAGStorage` class (memory.storage.rag_storage se) — vector-based retrieval ke liye.
    - `LTMSQLiteStorage` (long_term memory storage se) — SQL storage ke liye.
  - **Crew banane wale function mein 3 objects create karo:**
    - **`ShortTermMemory`** → `RAGStorage` ke saath — **provider = OpenAI** + ek **embedding model** (text se vectors banane ke liye; koi bhi model substitute kar sakte ho), type `short_term`, aur ek **path** jahan vector store banega — under the hood **Chroma** use hota hai (Ed ka favourite, LLM engineering course walon ko pata hoga).
    - **`LongTermMemory`** → simply `LTMSQLiteStorage` ka instance, same `memory/` directory mein ek **SQLite db file** ka path.
    - **`EntityMemory`** → ye bhi `RAGStorage` object — same provider + embedding model, memory folder mein.
  - **Crew creation pe:** `memory=True` set karo aur teeno objects pass karo — `long_term_memory=...`, `short_term_memory=...`, `entity_memory=...`. Bas, "very challenging... not challenging at all."

- **Do chhote extra changes — agent level pe memory:**
  - **`trending_company_finder`** agent → `memory=True` (taaki naye companies surface kare, repeat na kare).
  - **`financial_researcher`** → **memory NAHI** — kyunki hum chahte hain wo **har baar fresh research** kare.
  - **`stock_picker`** → `memory=True` — kyunki **same stock dobara recommend** nahi karna.
  - **YAML prompts bhi align karo:** prompts mein already likha tha "don't recommend the same stock twice", "surface new companies" — **instructions ko memory ke saath align** karna final zaroori step hai.

- **Ed ka key insight (demystify):** memory abstractions bhale "magical" lagein, **end of the day memory = prompt mein zyada stuff shove karna** — prior conversations / retrieved info input mein include hoti hai taaki LLM ko knowledge mile. No magic.

- **Run (`crewai run`) ka result:**
  - Project mein ek **`memory/` directory** create hui — andar **Chroma database** (short-term + entity) aur **SQLite database** (long-term) ban gaye.
  - Run thoda **lamba chala** ("around the houses"), is baar **Microsoft** recommend kiya. (Disclaimer: real decisions ke liye use mat karo!)
  - Memory ke use ki **visibility kam** thi (kya context pass hua wo nahi dikha), par data stores **build aur populate** hote dikhe.

- **Stock picker project ka wrap-up — kya kya dekha:**
  - **Structured outputs** (pydantic schema)
  - **Homegrown custom tool** + **Serper** tool
  - **Hierarchical process** (sequential nahi)
  - Aur ab **memory** — teeno main types ke saath. CrewAI functionality ka **nice tour** complete.

---

## 🔑 Key Concepts / Important Terms

| Term | Simple Hinglish Meaning |
|------|--------------------------|
| **Memory (CrewAI)** | Framework ka opinionated feature jo LLM calls mein automatically relevant context inject karta hai |
| **Short-term memory** | Recent interactions ka vector-DB (Chroma) store — RAG style retrieval current execution ke liye |
| **Long-term memory** | Important info ka **SQLite** store — lambi avadhi ka recall, knowledge build-up |
| **Entity memory** | People/places/concepts ke facts ka vector store — similarity search se context mein aata hai |
| **Contextual memory** | Umbrella term — short-term + long-term + entity sab query ho ke prompt context bante hain |
| **User memory** | User-specific info — CrewAI support karta hai par querying/insertion mostly manual (odd one out) |
| **RAG (Retrieval Augmented Generation)** | Vector similarity se relevant text retrieve karke prompt mein daalna |
| **`RAGStorage`** | CrewAI ki storage class — provider + embedding model + path leke vector store banati hai |
| **`LTMSQLiteStorage`** | Long-term memory ke liye SQLite-backed storage class |
| **Embedding model** | Text ko vectors mein convert karne wala model (yahan OpenAI provider ke through) |
| **Chroma** | Open-source vector database jo CrewAI short-term/entity memory ke under-the-hood use karta hai |
| **`memory=True` (Crew)** | Crew-level switch — memory objects ke saath pass karo to system on ho jata hai |
| **`memory=True` (Agent)** | Per-agent switch — sirf un agents ko do jinhe yaad rakhna chahiye (researcher ko nahi!) |

---

## 💡 Backend Dev Ke Liye Note (aapke liye)

- **Memory = automatic context injection, koi magic nahi.** Architecture-wise ye waise hi hai jaise web app mein request handler ke pehle middleware session/user data load karke context mein attach kar de — yahan "session store" ek vector DB (Chroma) + SQLite hai, aur "attach" ka matlab prompt string mein retrieved chunks append karna. Debugging mushkil isliye hai kyunki final prompt tumhe dikhta nahi — ORM ke generated SQL na dikhne jaisa pain.
- **Storage choices familiar lagenge:** short-term/entity = **embeddings + Chroma** (RAG pattern — semantic similarity pe retrieve), long-term = **plain SQLite file** (structured recall). Same project folder mein `memory/` dir ban jata hai — yani local state, koi external infra nahi; `.gitignore` karne layak artifact samjho.
- **Per-agent `memory=True` ek design decision hai, blanket switch nahi** — researcher ko stateless rakha (har baar fresh research, jaise cache-bypass), picker/finder ko stateful (dedup ke liye, "same stock twice mat do"). Aur prompts (YAML) ko memory ke saath align karna padta hai — memory sirf data deta hai, behaviour instructions se aata hai.
- **Hamare labs mein** `memory=True` skip kiya gaya kyunki default **OpenAI embeddings** chahiye hote hain (hamari OpenAI key invalid hai) — alternative ke roop mein **Google embedder** (`embedder={"provider": "google", ...}` with Gemini embedding model) configure kiya ja sakta hai.

---

## 🧠 Takeaway (yaad rakho)

1. CrewAI memory ke **5 types**: short-term (vector/RAG), long-term (SQLite), entity (vector), contextual (in teeno ka umbrella), user (mostly manual).
2. Setup = 3 objects (`ShortTermMemory` + `RAGStorage`, `LongTermMemory` + `LTMSQLiteStorage`, `EntityMemory` + `RAGStorage`) → `Crew(memory=True, ...)` mein pass karo.
3. **Agent-level `memory=True` selectively do** — jise yaad rakhna hai (picker/finder) haan, jise fresh kaam karna hai (researcher) nahi.
4. **Memory = prompt mein zyada relevant context shove karna** — abstractions ke peeche bas yahi hai; isliye YAML instructions ko bhi memory-aware banao.
5. Framework trade-off: setup **bahut easy** (Chroma + SQLite free mein), par **visibility/debuggability kam** — prompts ke peeche kya gaya, nahi dikhta.

---

<details>
<summary>📜 Full English Transcript (original, click to expand)</summary>

And week three. Day four is a go. Let's get started. So last time we did a stock picker and we just have a little tiny bit more to put into that. And then we're going to move on with our next project. A developer agent. But first another repetition. I hate to repeat these things, but sometimes it's good to drum it in. Building a Crew project involves five things. First of all, crewai create crew. The name of the project to set up your crew, build those directories and those files. Number two, you find the YAML files for your agents and tasks, and you fill them in to define your agents and tasks. Number three, you go to the crew.py module, which is where you actually create the instances. And you use decorators to identify the agents and tasks that you'll be using. And then you create your crew itself. And this is where you can have structured outputs to make sure that the outputs conform to a schema. And you can use tools, both tools like Serper, that Crew provides for us that run remotely, and then custom tools that we build locally, like the thing that sends a push notification. And then number four, you update main.py to set any inputs so that we can pass something in, configure the fields that are templated with the curlies. And finally we run with crewai run and off goes our project.

So I now want to cover a feature of Crew called memory. And this is a feature that is a bit more prescriptive, a bit more opinionated in the Crew framework. Memory, of course, is talking about how you provide information, contextual information to LLMs each time you call them, and you can implement that yourself just by storing variables and then passing them in when you do things like creating tasks so you can do it the sort of manual way. But the Crew framework also comes with some building blocks that lets you use their constructs around memory out of the box, and that comes with pros and cons. The pro is that you get up and running quickly, and you can use a lot of the thinking that they put behind this. The con is that there's there's a learning curve, and it obscures some of the detail of how prompts actually work behind the scenes. So as as with many times when you're adopting a framework like this, it's something to be aware of the benefits and the trade offs of doing so.

But let's say that we are going to embrace Crew's way of handling memory and talk about what it actually does. Well, it has five different types of memory, five different frameworks that you can include. And one of them is called short term memory. And this is just about storing recent interactions using a vector database in in a in a RAG way. If you're familiar with retrieval augmented generation. And you don't need to be for this course because we're just going to put the code in there and see it run. But if you do know, then this will make more sense. So this will allow agents to access recent relevant information when they are currently executing. And then a different concept called long term memory is when more important information is stored in a SQL database for longer term recall to build up knowledge over over a longer period of time. And then there's something called entity memory that's very similar to short term memory, actually. It's it's basically when there's things about people, places and concepts, then those can also be stored in a RAG database for vector based similarity search and to be included in the context. And then there's Crew describes this as another kind of memory. But I think it's a bit misleading. I think what they call contextual memory is just a sort of umbrella term for the short term, long term and entity memory that can all together be queried and passed in as context when prompting an LLM and Crew abstracts all this away from you. So it's just going to be a few lines of code to have all of these types of memories running. But in doing so, as I say, big benefit. A lot of work happens behind the scenes. And perhaps also there the trade off is that you've got less visibility into it. So if things don't go the way you want, then it's a bit harder to debug and figure out what's going on. And then there is another kind of memory called user memory, which is to store user specific information. And actually, at least as of now in Crew, this is a concept that they support and have some frameworks around, but it's mostly left up to you to be querying user memory and then inserting it into the prompt or providing it at the right time. So user memory is a bit of an odd one out here, and I suspect that they're looking to build more into that in time. And for now, for the code that we're about to look at, we're just going to really look at contextual memory. So short term long term and entity memory and seeing how we can incorporate that into our stock picker solution.

And so we're back in the stock picker project in Cursor. And we are looking at the crew.py module. And I'm going to start by putting in some new imports in here, which are interesting ones from crewai memory. We're going to import long term memory short term memory and entity memory. The three types we'll be working with. And I do believe you can also have user memory in there too. But then you have to manually manage it yourself. And then from memory storage rag storage, we're importing a class called RAGStorage for vector based retrieval. And with that we're also going to import from long term memory LTMSQLiteStorage object like that a class. All right. So that's a few things that we're now going to put to good use.

We're now going to go to the crew function the function that creates the crew within this this module. And you can see where we made our manager. And we've got a few more things to make. So we are going to to want to be creating a short term memory a long term memory and an entity memory. And we're going to do them one by one. So let's start by saying that the short term memory, which is the one that we'll begin with, short term memory is going to be something which has RAG storage. We we come up with a provider which is OpenAI, and a model, an embedding model to generate vectors from text. And we'll be using this one. And you can substitute in whatever models you would like here. It's going to be short term. And we give it a path to where we'd like it to create that memory, that vector store as memory. And it will use Chroma as it happens, something which people who've taken my, uh, LLM engineering course know very well. I love Chroma. All right, so that's the short term memory. Let's also create some long term memory. So here it is. The long term memory is going to be just simply creating an instance of this of this class LTMSQLiteStorage. And we'll give that also a place to go. We'll make a database file also in the same directory. So that's the long term memory object. And now finally, thirdly, we're going to create a, uh, entity memory object. So entity memory is going to be an entity memory object. It's also going to be a RAG storage object. We give the provider and the embeddings model and we put it in the memory folder. So here we have our three types our short term memory our long term memory and our entity memory.

And now we get to the place where we create our crew. And now it's going to be very challenging. It's not going to be challenging at all. We're going to say memory equals true. And we are going to then just do exactly that. That's all you need to do. You set the long term memory the short term memory and the entity memory. And we are almost done with memory. Just just as simple as that. And I said almost because there is just one or rather two very small extra changes we need to make. We need to go back up in the module to where we created these agents the trending company, the financial researcher and the stock picker. And we need to give them memory. Now what we want is for the trending company finder to have memory. And we just do it by saying memory equals true. We don't actually want the researcher to have memory because we want it to go and do research every time. But we do want the stock picker to have memory, because we don't want it to recommend the same thing more than once. And I don't know if you remember, but in the prompts, in the YAML files, I said a couple of times, uh, don't, don't recommend the same stock twice and things like that. And, and surface new companies for the for the trending company finder. And that would normally be the final change you need to make is go back and make sure that your instructions and your YAML files are very clearly making sure that it will take advantage of memory. Because remember, whilst memory, these abstractions are trying to make memory seem quite magical and taken care of for you. At the end of the day, memory just means more stuff shoved into the prompt, more relevant context put into the prompt so that when you call an LLM it has knowledge. It's in the input is included information about prior conversations or about prior information that it retrieved.

So with that we have set up set up the memory. And we are now going to bring up our terminal and then run this. And so as usual I go into already in the stock picker. So all I have to do is type crewai run and we'll be good to go. Let's see what happens. So just right off the bat, we expect it to be able to take advantage of memory without needing anything more. What we should see is it should create a memory directory in here. And it just has there is a memory directory. Stuff is going on. My computer is hard at work and I can see already within memory there is a Chroma database that's being created. There is a long term memory. If I expand this, there is indeed a database that's been a SQLite database that's been created there. And so things are happening and we can see that, that, uh, various companies are being surfaced by the market watcher and more is going on and we will, uh, let this thing run. My computer's hard at work, and I will see you when we have a conclusion.

And that definitely took a bit longer. It was going around around the houses a little bit, but it completed it. Recommended Microsoft this time. Remember, don't use this for real decisions. But it was, uh, entertaining to see it at work and bouncing around between the different agents. And whilst we don't have as much visibility into what's happening in terms of its use of memory and what context got provided, we can see that it's certainly built and populated different data stores and both the short term memory, the long term memory and the entity memory in the RAG Chroma data store that's been created there. And the main point I want to get across is that, of course you can see the benefits of what this brings us. It was so easy to set up quite a complex situation, multiple types of memory with both vector similarity queries and SQL queries too. And we didn't need to know anything about it. We simply created the objects. The short term long term entity memory objects passed them in. And then we told our agents we turned memory on by saying memory equals true for the agents that we wanted to remember things. And that is a wrap on the stock picker project. We saw a lot of different aspects of CrewAI with this project. We reminder, we saw structured outputs. We saw our own homegrown tool as well as Serper. We also used the not the sequential but the hierarchical process. And now we have added in the memory feature all, all the three main types of memory in there as well. And that is a nice tour of a lot of the functionality in Crew.

</details>

---
*Source: Official Udemy lecture transcript (auto-captions, lightly cleaned). Notes in Hinglish for self-study.*
