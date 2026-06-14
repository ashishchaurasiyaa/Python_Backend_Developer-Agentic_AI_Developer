# L22 — Day 5: LLM Tool Calls Demystified — How to Process and Execute Function Requests

> **Week 1 — Foundations** · ⏱️ ~6m · 🎥 Lecture 22 of 131
> **Instructor:** Ed Donner · **Lecture ID:** 49771327

---

## 🎯 Ek Line Mein (TL;DR)

Jab LLM bolta hai "mujhe ye tool chalana hai", to humein ek **`handle_tool_calls()`** function likhna padta hai jo LLM ke **JSON response** se tool ka naam + arguments nikaal kar actual Python function chalata hai — aur Ed dikhate hain ki ye saara "tool calling magic" asal mein bas ek **glorified if statement** hai.

---

## 📝 Hinglish Explanation (Detailed)

- **Context:** Pichle lecture mein humne tools ka **JSON schema** banaya tha jo LLM ko bheja jaata hai. Ab LLM apne response mein bol sakta hai — *"main ye tool run karna chahta hoon"*. Ye lecture course ka **most important aur most complex part** hai — yahan samajhte hain ki us request ko **process aur execute** kaise karte hain.

- **`handle_tool_calls()` function — core idea:**
  - Ye function ek **list of tool calls** leta hai (LLM ke response se).
  - Har tool call ko **loop** mein process karta hai, function run karta hai, aur har result ko ek **results list** mein add karke return karta hai.
  - **Note:** typically model ek baar mein **ek hi tool** call karta hai, lekin construct **multiple tool calls** support karta hai — isliye loop zaroori hai.

- **LLM se kya wapas aata hai?**
  - Response ek **structured output** hai — **JSON** jo ek object (`tool_calls`) mein parse ho chuka hai. Isi liye Ed bolte hain ki tool calling **structured outputs ke bahut analogous** hai.
  - Us object se hum do cheezein nikaalte hain:
    - **`function.name`** → **tool name** (kaunsa function LLM chalana chahta hai)
    - **`arguments`** → us function mein daalne waale **parameters** (JSON string, jo strip/parse karte hain)

- **The promised if-statement:**
  - `if tool_name == "record_user_details"` → `record_user_details(**arguments)` call karo
  - `elif tool_name == "record_unknown_question"` → `record_unknown_question(**arguments)` call karo
  - Jo bhi function se wapas aaya, use **messages list** mein (tool result ke roop mein) add kar do — wahi return hota hai taaki LLM ko output mile.

- **Sneaky trick — `globals()` se dynamic dispatch:**
  - Ye if-statement dekh kar lagta hai: *"string match karke same naam ka function call kar rahe hain — Python mein koi reflection trick nahi hai kya?"* — **haan, hai.**
  - **`globals()`** ek dictionary deta hai jisse global scope ka koi bhi function **naam (string) se lookup** kar sakte ho: `tool = globals().get(tool_name)` → fir `tool(**arguments)` se directly call.
  - Ed live demo karte hain — "This is a really hard question" run karke **push notification** phone par aati hai. Trick kaam karti hai.
  - Is trick se `handle_tool_calls()` rewrite ho jaata hai — **ab koi if-statement nahi**, dynamic lookup + call.

- **Reality check — "It's a glorified if statement":**
  - Ed warn karte hain: ye trickery dekh kar mat socho ki kuch magical ho raha hai. End of the day, hum bas **text (string) ko function name se map** kar rahe hain aur wo function call kar rahe hain. **Glorified if statement, nothing more.** Tool calling mein koi mystery nahi hai.

- **Good news — frameworks ye sab handle karte hain:**
  - Week 1 ke baad **kabhi bhi ye manually nahi karna padega** — OpenAI Agents SDK, CrewAI, LangGraph jaise **frameworks** JSON plucking aur function dispatch khud handle karte hain.
  - Frameworks asal mein isi boilerplate ko wrap karne ke liye bane the.
  - Lekin ye foundation isliye zaroori hai — jab frameworks use karoge, to **exactly pata hoga ki under the hood kya ho raha hai**.

---

## 🔑 Key Concepts / Important Terms

| Term | Simple Hinglish Meaning |
|------|--------------------------|
| **Tool Call** | LLM ka response jisme wo bolta hai "ye function, in arguments ke saath chalao" — JSON form mein |
| **`handle_tool_calls()`** | Hamara function jo LLM ke tool-call requests ko loop karke actual Python functions execute karta hai |
| **Structured Output** | LLM se aaya JSON jo ek parsed object ban jaata hai — tool calling isi pe based hai |
| **Tool Name + Arguments** | Response ke do parts: kaunsa function chalana hai, aur kya parameters dene hain |
| **`globals()`** | Python ka built-in dict jo global scope ke functions ko string-name se lookup karne deta hai (reflection trick) |
| **Dynamic Dispatch** | String se function dhundh kar call karna — if-statement ka elegant replacement |
| **"Glorified if statement"** | Ed ka punchline: tool calling = text ko function se map karna, bas. Koi magic nahi |
| **Frameworks** | CrewAI, LangGraph, etc. — ye saara JSON-to-function plumbing automatically karte hain |

---

## 💡 Backend Dev Ke Liye Note (aapke liye)

- **`globals()` trick = dispatch table pattern.** Aap production mein shayad explicit dict use karte ho (`HANDLERS = {"record_user_details": record_user_details}`) — wahi pattern hai jo Flask/Django URL routing ya Celery task registry mein dikhta hai. `globals()` quick demo ke liye theek hai, lekin real code mein explicit registry safer hai (arbitrary global function call hone ka risk nahi).
- **Tool call ka loop bilkul webhook handler jaisa hai:** event aaya (JSON payload) → `type`/`name` field dekho → matching handler dispatch karo → result wapas bhejo. LLM tool calling mein bas "caller" ek model hai, HTTP client nahi.
- **`arguments` JSON string hota hai** — `json.loads()` + `**kwargs` unpacking. Production mein yahan **Pydantic validation** lagani chahiye, kyunki LLM ke generate kiye arguments pe blind trust = untrusted user input pe blind trust.
- **Hands-on:** is lecture ka code khud chalane ke liye ye lab run karo — `Practical/lab4_career_agent.py` (uv run se chalega, Groq-free).

---

## 🧠 Takeaway (yaad rakho)

1. **Tool calling = 3 steps:** LLM ka JSON response parse karo → tool name + arguments nikaalo → matching Python function call karke result messages mein wapas daalo.
2. **Loop rakhna zaroori hai** — model usually ek tool call karta hai, lekin construct multiple supports karta hai.
3. **`globals()[tool_name](**args)`** se if-statement hata sakte ho — dynamic dispatch via reflection.
4. **Magic kuch nahi hai** — tool calling ek **glorified if statement** hai: string → function mapping.
5. **Week 1 ke baad frameworks ye sab karenge** — lekin ab tumhe exactly pata hai ki wo andar kya kar rahe hain.

---

<details>
<summary>📜 Full English Transcript (original, click to expand)</summary>

So this next part is the most important part. It's also probably the most complex. Now you're comfortable with the fact that we are going to be sending this JSON to the LLM and giving it the option to reply when it generates its response. It can opt to say that it wants to run one of these tools. It wants to run this tool or it wants to run this tool. So the next thing that we've got to do is write a function which is going to handle what happens when the LLM responds and says, yes, I do want to run this tool. Please run it and provide me with the output. So that is the purpose of this function that I've written right here called handle_tool_calls. And it's a function which takes a list of tool calls. And it will run them. And it will add the responses to the results that it returns.

So it has a loop. It loops through these tool calls. Typically a model will only call one tool at a time. But actually the construct supports multiple tools being run. And so we want to support that here. So we do that. So we loop through all of the tool calls. We look at this. What's come back in this tool call. And I should say this is actually it's a structured output. It's JSON coming back from the LLM that's been put into an object. And so this is one of the reasons why I said it's very analogous to structured outputs. So back has come this JSON object is in the form of an object tool_calls. And we are going to look at the function name that it's providing back in that response. And we are going to be calling that the tool name. And that is the name of the function it wants to call. And it also provides us with the parameters, the arguments that should be put into that function. And we can strip them out like this. And so I'm then just going to print we're calling this tool.

And what comes next is an if statement. Just like I promised you. We say if the tool name is record_user_details. If it wants to call this tool, then we call the function that's called record_user_details. And we pass in the arguments. But conversely if the tool is this tool record_unknown_question right here in the JSON. Then we call the function called record_unknown_question. And we pass in the parameters. And then we add in whatever came back from that function call into the list of messages. And that's what we return. So that is the extent of the handle_tool_calls function. And as I told you it's got this if statement. So hopefully this is more concrete for you. You see that coming together. And if not come and look through this and get comfortable with it.

Okay. And what I've got next is something a bit sneaky. When you look at this you might think to yourself, this is a bit dumb. We've got this thing that looks for a string and then calls a function with the same name and looks for a different string, and calls a function with the same name. Now we know that Python is full of magic stuff. Isn't there a way in Python to do a sort of reflection thing, and just call that function with the same name as that string? And the answer is yes, of course there is. And this is one way of doing it that works in this particular situation. There is this thing called globals which gives you a dictionary which you can use to look up any function which is in the global scope. And so I can use that to look up a function called record_unknown_question. And that will give me the actual function record_unknown_question. And I can then call it like that. This is a really hard question. So if I run this it should send a push notification to my phone. Let's see. Yep, that seemed to work. I see recording this is a really hard question. So that works. Let's do it again. Ah, it makes it worth it. Pinging when I get emails. So, uh. Yeah. There you see that this trickery works.

And of course, that means that I can rewrite the handle_tool_calls function and do it this way so that now basically there's no more if statement. I've got that cunning piece of logic in there that plucks out the right function and then dynamically calls that function like that. And I can see that it would be better to do this for sure. So, um, yeah, this obviously gives us a workaround to having the if statement that we had before. But I don't want you to think for one minute that that means that this isn't just a glorified if statement, because that's all it is. Sure, we've got some trickery to use a dictionary to look up that has got around having to list things out. But at the end of the day, it's still the same thing. We're just taking some text and we're using that to map to a function name, and we're calling that function. It's a glorified if statement, nothing more.

So that's how this works. And I hope that this now gives you a bit of perspective of what's going on. The good news is you're never going to have to do this again after week one, because all of the other frameworks take care of this kind of stuff for you. You don't need to futz around with plucking out JSON and turning it into function calls. That's exactly what these frameworks did. It's people that wrote stuff like this and thought, you know what? It would be easy just to put this into a nice little framework so that people don't have to worry about this anymore. So you won't have to worry about it anymore after this. But I wanted this to give you a real perspective on how it works, what's going on so that you've got that foundation, and when you actually get to use the frameworks, you know exactly what it's actually doing.

</details>

---
*Source: Official Udemy lecture transcript (auto-captions, lightly cleaned). Notes in Hinglish for self-study.*
