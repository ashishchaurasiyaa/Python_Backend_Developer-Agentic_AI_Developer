# L77 — Day 3: Tool Calling — Conditional Edges & Tool Nodes

> **Week 4 — LangGraph** · ⏱️ ~12m · 🎥 Lecture 77 of 131
> **Instructor:** Ed Donner · **Lecture ID:** 49821349

---

## 🎯 Ek Line Mein (TL;DR)

LangGraph me tool calling do jagah handle hoti hai — **`bind_tools()`** se LLM ko tools ka JSON automatically milta hai, aur **`ToolNode`** + **conditional edge** (`tools_condition`) se model ka tool-call request actually execute hota hai; Week 1 wala manual "if finish_reason == tool_calls" loop ab framework khud sambhalta hai.

---

## 📝 Hinglish Explanation (Detailed)

- **Same graph, ab tools ke saath**: Ed pichle lecture wala hi chatbot graph bana raha hai, lekin is baar usme **tools** add ho rahe hain. Ek chhota change — is baar **State object Pydantic nahi, `TypedDict`** hai.
  - Dikhne me almost identical: bas `BaseModel` ki jagah **`TypedDict` ka subclass**. Baaki same — `messages` field jo **`Annotated`** hai, list hai, aur annotation LangGraph ko batata hai ki **`add_messages` reducer** use karna hai. Pydantic prefer karte ho to wo bhi chalega — ye bas dusra style hai.
- **Tool calling ke 2 alag points** (ye mental model pakdo, pura lecture isi pe hai):
  1. **Model ko call karte waqt** — yahan tools ka pura **JSON schema** banana padta hai ("ye tool hai, ye parameters hain") taaki model ko pata ho wo kya kar sakta hai. Week 1 me ye haath se likha tha.
  2. **Model ke respond karne ke baad** — check karna padta hai ki **`finish_reason == "tool_calls"`** hai ya nahi, phir tool call ko unpack karke actual Python function run karna (Week 1 ka lamba `handle_tool_call` method yaad karo — if-statement ya dynamic function lookup).
- **Point 1 ka LangGraph/LangChain solution — `bind_tools()`**:
  - `ChatOpenAI` (LangChain ka OpenAI wrapper) banate hain, phir **`llm_with_tools = llm.bind_tools(tools)`** — ek nayi LLM version jo har call pe **automatically tools ka JSON build karke pass karti hai**.
  - Ye LangChain ki "magic" hai — saara JSON nonsense abstract ho gaya. **Flip side**: implementation hide ho jati hai, **debugging thodi mushkil** ho sakti hai. Lekin positive clearly heavy hai — ekdum simple ho gaya.
  - **Chatbot node** ab bas itna hai: `return {"messages": [llm_with_tools.invoke(state["messages"])]}` — invoke `llm` pe nahi, **`llm_with_tools`** pe.
- **Point 2 ka solution — `ToolNode`**:
  - Graph me ek **second node** add hota hai jiska naam `"tools"` hai — ye ek **special, pre-canned node type** hai: **`ToolNode(tools=...)`**.
  - Create karte waqt use batana padta hai ki **kaunse tools** uske paas hain. Invoke hone par ye dekhta hai ki **koi message tool call request kar raha hai ya nahi** — agar haan, to wo **tools ko actually run** karta hai (unbundling + function calling, sab handle).
- **Edges — yahan twist hai**:
  - Chatbot → tools ka edge **normal edge nahi** ho sakta, kyunki hum **hamesha** tools call nahi karna chahte — sirf tab jab model ne tool-call response diya ho. Matlab edge ke saath ek **"if" attached** hai.
  - Isliye ye **conditional edge** hai: `add_conditional_edges(node_name, condition, ...)` — node ka naam, condition function, aur target node dete ho.
  - Condition bhi **pre-canned** hai: **`tools_condition`** — ye literally check karta hai ki finish reason tool calls hai ya nahi. Ed ka classic quote: *"tool calling is just an if statement"* — **ye conditional edge hi wo if statement hai**.
- **Subtle but critical point — wapas wala edge**:
  - **`tools` → `chatbot` ka normal edge bhi banana zaroori hai**, kyunki tool run karne ka **result wapas chatbot me feed** hona chahiye taaki LLM processing continue kare.
  - Ed bolta hai — ek baar bata diya to obvious lagta hai, lekin khud se yaad nahi aata. **Agar ye edge bhool gaye to cheezein ajeeb tareeke se fail hongi** (silent weirdness, clear error nahi). Elegant hai, lekin debugging hard bana sakta hai.
- **Graph picture** (compile + visualize karne par):
  - `START → chatbot` (solid edge).
  - `chatbot → tools` — **dotted line** = conditional (sirf jab `tools_condition` true ho).
  - `tools → chatbot` — **solid line** = tool run hua to result hamesha wapas jayega.
  - `chatbot → END` — dotted, kyunki **LangGraph automatically END node add kar deta hai** kisi bhi unresolved condition ke liye (tool call nahi hua to naturally END).
- **Demo run** (Gradio UI me, function ka naam `chat` rakha consistency ke liye):
  - Prompt: *"Please send me a push notification with the current USD to GBP exchange rate."*
  - Ambitious ask — **2 tool calls ek hi shot me**: pehle **web search** se rate nikalna, phir **push notification** bhejna.
  - Result: notification aayi — "current USD GBP exchange rate is 0.78" — aur Google pe verify kiya, sahi tha. Dono tools chale, graph ne loop sambhala.
- **LangSmith me trace**:
  - Pura graph execution **LangSmith** me dikhta hai — 4 seconds laga (red me highlight). Andar jaakar dikhta hai: search call hua ("current USD to GBP exchange rate"), result wapas aaya, phir `tools_condition` ke through **send push notification** call, phir final answer.
  - Ed ka homework: khud run karo, dono tools call karwao, aur **LangSmith me trace karke convince ho jao** ki calls actually hue.

---

## 🔑 Key Concepts / Important Terms

| Term | Simple Hinglish Meaning |
|------|--------------------------|
| **TypedDict state** | Pydantic `BaseModel` ka alternative — `TypedDict` subclass; `Annotated` + reducer same tarike se kaam karta hai |
| **`add_messages` reducer** | `Annotated` ke through bataya gaya reducer jo naye messages ko purani list me append karta hai (overwrite nahi) |
| **`bind_tools()`** | LLM ka tool-aware version banata hai — har invoke pe tools ka JSON schema automatically build + pass hota hai |
| **`llm_with_tools`** | `bind_tools()` se bana wrapper LLM — chatbot node isi pe `invoke` karta hai |
| **`ToolNode`** | Pre-canned LangGraph node — message me tool-call request detect karke assigned tools ko actually run karta hai |
| **Conditional edge** | Edge with an "if" — sirf condition true hone par traverse hota hai (dotted line in graph diagram) |
| **`tools_condition`** | Pre-canned condition function — check karta hai ki model ka finish reason tool calls hai ya nahi |
| **tools → chatbot edge** | Wapas wala solid edge — tool ka output chatbot me feed hota hai; bhoole to weird failures |
| **Auto END node** | LangGraph har unresolved condition ke liye END node khud add kar deta hai |
| **LangSmith trace** | Graph execution ka full trace — har node, tool call, timing dekh ke debug kar sakte ho |

---

## 💡 Backend Dev Ke Liye Note (aapke liye)

- **Conditional edge = state machine ka guarded transition**: agar aapne kabhi workflow engines (Airflow ka `BranchPythonOperator`, ya Spring State Machine ke guards) use kiye hain, `tools_condition` exactly wahi hai — transition pe predicate. Aur `tools → chatbot` ka mandatory return edge ek **feedback loop** hai, matlab ye pure DAG nahi balki **cyclic graph** hai — yahi LangGraph ka USP hai DAG-only tools ke against.
- **`bind_tools()` = decorator/middleware pattern**: jaise aap ek HTTP client ko retry/auth middleware se wrap karte ho bina call-sites change kiye, waise hi LLM wrap hota hai — har `invoke` pe tool schemas inject. Trade-off bhi wahi: **abstraction leaks par debugging opaque** — isliye LangSmith trace ko APM (Datadog traces) ki tarah treat karo.
- **`TypedDict` vs Pydantic**: yahan validation ki zaroorat nahi, sirf type hints + `Annotated` metadata chahiye reducer batane ke liye — `TypedDict` lighter hai (no runtime validation overhead), Pydantic stricter. Same trade-off jo aap DTO vs dataclass me karte ho.
- **Hands-on lab**: is lecture ka code khud chalane ke liye `Practical/lab2_tools_checkpointing.py` run karo (is repo me, `uv run` se chalta hai, Groq pe free via langchain-groq `ChatGroq`). Hamare lab me course se ek difference: **LangSmith tracing skip** hai (key nahi) aur web search ke liye SerperDev ki jagah **free Wikipedia search** tool use kiya hai — concepts (bind_tools, ToolNode, tools_condition) bilkul same hain.

---

## 🧠 Takeaway (yaad rakho)

1. Tool calling ke **2 touchpoints**: (1) model ko tools ka JSON dena → `bind_tools()`, (2) model ka tool-call response execute karna → `ToolNode`.
2. **Conditional edge + `tools_condition`** = Week 1 ka manual `if finish_reason == "tool_calls"` — ab framework ka pre-canned if statement.
3. **`tools → chatbot` wapas wala edge mat bhoolna** — tool ka result LLM me wapas jana zaroori hai, warna weird failures.
4. LangGraph **END node automatically** add karta hai unresolved conditions ke liye — dotted line = conditional, solid = always.
5. Abstraction se code simple, lekin debugging ke liye **LangSmith trace** (ya hamare lab me verbose printing) ka sahara lo.

---

<details>
<summary>📜 Full English Transcript (original, click to expand)</summary>

Okay. So now we're going to build the same graph that we did last time. But we're going to add in some tools. Uh, so um, one small change I'm going to make though is this time for the state object. We're not going to use a Pydantic object. We're going to use a typed dict. And it looks almost identical. It's just a it's a subclass of TypedDict instead of pydantic base model. Um, but otherwise the same thing. Messages field. It's annotated. It's a list. And this is telling LangGraph that we're going to use the add messages reducer as a way of reducing. Otherwise it's just the same. So you can stick with Pydantic if you'd prefer, but this is a different way of doing it.

Uh, so then we start the graph builder right there. And now we have something different. So it's worth keeping in mind, in your mind that when when we work with tools, there's actually two different places in our code that typically we have to worry about tools. And I've explained this up here first of all, when we're, when we're, uh, making the call to the model, to OpenAI. That's the point at which we have to look at our tools and create all of that JSON nonsense. All of the stuff to describe what the tool is, so that when we prompt the model, it knows what it can do. So that's one piece of work that has to happen. And then another piece of work is when the model then responds. We have to test to see whether is the finish reason tool calls. And if so then we have to do that stuff, which was the quite long winded handle tool call uh, method in the first week where we unpacked the tool call and then we did some clever stuff. You can either have just an if statement, or you can have something clever that goes and finds the function and calls it. But that whole piece of the puzzle, the, uh, receiving the message to call a tool from the model, is like another place where you have to do all of your coding. Those are the two points, and we'll see both those points separately in how we have to handle this with LangGraph.

So this is the first one. When we create the model this is the ChatOpenAI object which is the LangChain wrapper around calling OpenAI. We also, once we've created it, we make another version of LLM, which is LLM with tools, which is after calling bind tools to the LLM. And this is just some nice sort of magic, which is going to then figure out what are the tools that it can call and make sure that whenever we call that model, whenever we call this version of the model, it's going to to provide all of the tools it can do. So it's one of those examples. This is really powerful. It's LangChain here. And it's LangChain being really nice, making it simple to package away all of that JSON stuff and do it for us by abstracting around an LLM to have an LLM with tools which whenever you call it, it's going to automatically pass in all the tools it can call. The flip side of that is that it's it's sort of hiding from us some of the implementation and some of what's going on which which can be which can make it hard to debug and things. But but you certainly I mean hopefully you see the positives very much. It's really easy. That is done that now. Whenever we call LLM with tools, it's going to automatically handle the the building of that JSON and the parsing it in.

And so look look how simple this is. This is our chat bot function. This is our node our function for the chat bot which just as before we return messages. And then what we've got here is we just call invoke but not on the LLM but on the LLM with tools that knows already about those tools. It will build the JSON, it will parse the JSON in as the tools. So it's really clever. And then we add that node.

And then there's this line here. This is part two. This is the other thing. This is handling the results back. So what's happening here is that we added that chatbot node. We're adding a second node called tools. And it is a special type of node. It's a ToolNode. And when you create a tool node you have to tell it okay. What are these tools. What is it that you do? And this tool node is basically like a canned node that when it's invoked, it's going to see whether any of the message is asking to call one of the tools that it's been assigned, that it was passed to it when it was created. That's the job of the tool node, and if so, it will run them. So one more time, this piece of code here is handling the request to the LLM and packaging up the tools JSON. And this node here is handling what happens if a if there is a tool request, it's handling the unbundling of the request and the actual calling of the tool function. And if any of that didn't make sense, I think it hopefully will do very shortly.

We're going to create the edges now and again a little bit more complicated than before. So there is an edge which is going from the chat bot to the tools from this node, which is the actual chat bot, the LLM with tools to the thing that calls tools to the node that actually runs the different tools we need to connect those two. But that connection, it's a connection which which has like an if attached to it. We don't want to always call tools. We only want to call those tools if the model has returned a response that the finish reason is tool calls. We had to like code that ourselves in week one. If finish reason is tool calls so that if has to be included in here because it's only if that's true. It's only if the model returns that it wants to call tools that we actually want to to call this node. And so and so that is why when you look at this edge, it's not a normal edge. It's called a conditional edge, which means it's an edge that's only triggered in certain conditions. And like an if statement and you give it the node name, you give it the condition and you give it the the node that would then be called. And that condition called tools condition is again pre-canned with LangGraph. And of course it looks to see if the finish reason is tool calls. And so that is what. That's exactly what that does. So when I used to say that, that, uh, at the end of the day, tool calling is just an if statement. This is the if statement. This thing here is handling that if statement. And if the if statement is true then then it's calling a node called tools.

Uh all right. And then the, the uh there's one more quite subtle point here, which is that you also have to make an edge between tools. Back to chatbot again, because the result of this, the result of running the tool, the output needs to get fed back into the chatbot and it needs to continue processing from there. So this is subtle and, and, uh, you know, once, once I've said it, it's probably obvious, but it's one of those things that if I hadn't said it, it's not something that would naturally have occurred to you. And if you don't do it, then things will go wrong in strange ways. So it's one of those times. Again, it's elegant, it's neat. It's great that LangGraph does that, but it can make it a bit harder to debug.

All right. And then we're going to add that start edge. And then we're going to. Compile and picture it. And this will hopefully bring this together for you. Start goes to chat bot. This is a conditional line. If if the finish reason is is a tool call then it will come here because the tools condition will be true. Then it will it will be responsible. This node is a canned node that's responsible for calling the tools that are relevant. And then the results comes back. And this is a solid line because if it's got here it should always come back. And this is a dotted line because only in the event that this didn't happen then it will come to end naturally. LangGraph automatically adds an end node for any any unresolved condition like that. And so that is our graph. And I hope that seeing that graph has made it come together for you. So the two places where tools are incorporated. One is the chatbot itself. We're using the LLM with tools and the other is in the conditional branch and this tools node itself.

Well, I think it's enough chit chat. We should get on and run this thing. So here we go. We're going to. Oh, I think I'll make this consistent with how we've done it before. We'll call this chat not invoke graph. But it is. It is how we should think of it really. So we're going to um, we're going to, to bring up a gradio screen and we're just going to call it let's see if this works. Okay. So I'm going to say hi there. Hello. How can I assist you today. Well I'm going to do something fun here. I'm going to say uh, please send me a push notification with the current US dollar to great British pound exchange rate. So I'm hoping that it's going to look up the exchange rate, uh, by doing a web search, find it out, and then send me a push notification. This is ambitious. 2 to 2 tool calls in one shot. Get that out of me and we'll see. Uh, we'll see how it does. So it's going. It's off, it's pausing. It's as you heard it certainly sent me something. The current USD GBP exchange rate is 0.78. Well, I happen to have a Google screen sitting over here. Let's bring this into view. There you will find the current US dollar GBP exchange rate is indeed 0.78. So that's cool. That's cool. I hope you agree. Sorry. Get that out of your way. I hope you agree. Uh, it's interesting to see that this has happened and that it's achieved this.

And what we can see here is that we can come into LangSmith and see the outcome of this. I'm interested that it's put that in red the four seconds that it took us. So let's go into this and see more. Please send me a push notification with the current USD GBP exchange rate. So we can see that that you can see the whole graph playing out here. And it's fascinating to see, uh, the, the, um, let's scroll down. It's doing a search right here. Click here current USD to GBP exchange rate. And that's the the result that came back. Um, this was from, from from doing the search just as we expected. And then it came back to a tools condition to a send push notification. Uh, and uh, back came the uh, the, the answer. And then that was the, uh, the conclusion. Um, there we go. And that's how it responded. So there we see the full, uh, the full chain of, of, uh, discussion happening within LangSmith and how you can come in and debug this and see what's going on and see, indeed convince yourself that it did call the couple of tools. And this was great fun, and I hope you'll do the same thing. Come in now and run this and let it call both tools go into LangSmith and trace through to make sure that you can also see all of these calls happening, uh, just just as we did right here.

</details>

---
*Source: Official Udemy lecture transcript (auto-captions, lightly cleaned). Notes in Hinglish for self-study.*
