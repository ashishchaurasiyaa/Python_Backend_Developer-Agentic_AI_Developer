# L36 — Day 2: Agent Control Flow — When to Use Handoffs vs. Agents as Tools

> **Week 2 — OpenAI Agents SDK** · ⏱️ ~8m · 🎥 Lecture 36 of 131
> **Instructor:** Ed Donner · **Lecture ID:** 49820467

---

## 🎯 Ek Line Mein (TL;DR)

**Agents-as-tools** = request-response — tool call ke baad **control wapas tumhare paas** aata hai; **Handoff** = delegation — tum poora kaam doosre agent ko **saunp dete ho aur control kabhi wapas nahi aata**. Is lecture mein hum ek **Emailer agent** banate hain (subject writer + HTML converter + send tool ke saath) jo sales manager ka **handoff** banega.

---

## 📝 Hinglish Explanation (Detailed)

- **Recap — ab tak kya kiya (Layer 1 & 2)**:
  - Pehle **simple agent workflow**: agents ko plain Python code se orchestrate kiya, **`asyncio.gather`** se 3 email-writers ko **parallel** chalaya, phir ek aur agent se **best email pick** karwaya.
  - Phir **tools**: `function_tool` se ek Python function ko tool banaya, aur **`as_tool`** construct se **agents ko bhi tools mein wrap** kiya.
  - Ye saare tools **sales manager agent** ko diye — usne 3 email producers ko call kiya aur end mein email send ki.

- **Naya construct — Handoff (Layer 3 ka doosra tarika)**:
  - Ek agent ke paas **tools** hote hain aur **handoffs** bhi hote hain — handoffs matlab **doosre agents jinko wo delegate kar sakta hai**.
  - Sunne mein **agent-as-tool jaisa hi** lagta hai — confusing hai — par **2 differences** hain:
  - **Conceptual difference (mindset)**:
    - **Tool** = agent apne kaam ke dauraan ek **chhota feature/helper** use kar raha hai — kaam ab bhi usi ka hai.
    - **Handoff** = agent ek **specialist task ki poori responsibility aur ownership** doosre agent ko de raha hai — "ye job ab tumhara hai".
  - **Technical difference (fundamental, simple)**:
    - **Tools = request-response**: tool call hota hai, result wapas aata hai, aur **control tumhare paas wapas** — tum hi main agent rehte ho aur execution continue karte ho.
    - **Handoff = passing of control**: tumne apna hissa kar liya, ab **control doosre agent ko transfer** — **flow kabhi wapas nahi aata**. One-way delegation.
  - Dono alag situations mein useful hain — par **slightly different constructs** hain, ye distinction yaad rakho.

- **Ab build karte hain — wo agent jo eventually handoff banega**:
  - **Subject Writer agent**: pichle emails mein **subject hi nahi tha**! Iski instructions: "tumhe ek message diya jayega, uske liye aisa **email subject likho jo response milne ke chances badhaye**".
  - **HTML Converter agent**: text email (jisme **markdown** ho sakta hai — LLMs aksar markdown daal dete hain) ko **HTML email** mein convert karo — simple, clear, compelling layout & design (fancy sales emails aaj kal aise hi jaati hain).
  - **Dono ko `as_tool` se tool banaya** — kyunki ye "tool jaisa" kaam hai (subject likhna, format convert karna): `subject_tool` aur `html_tool`.
  - **Teesra tool — `send_html_email`**: pehle wale `send_email` jaisa hi, par ye **subject + body** leta hai aur **SendGrid** se **HTML email** (text nahi) bhejta hai. Reminder: **apna verified sender email** use karo, Ed ka nahi.
  - Ab **3 tools** hain — print karke dekho: **teeno `FunctionTool` dikhte hain**, par underneath **2 actually wrapped agents** hain aur **1 plain function** — `as_tool` sab ko same interface deta hai.

- **Emailer Agent — jisko handoff karenge**:
  - Instructions: "Tum ek **email formatter and sender** ho. Email ki **body** receive karoge. **Pehle** subject writer tool use karo, **phir** HTML converter tool, aur **finally** email send karo."
  - Isme ek **nayi cheez** hai: **`handoff_description`** = `"Convert an email to HTML and send it"`.
    - Ye wo tarika hai jisse ye agent **duniya ko announce karta hai** ki wo kya karta hai — taaki **doosra agent decide kar sake** ki ye handoff useful hai ya nahi.
    - Bilkul **tool description jaisa hi** concept — bas handoff ke liye.

- **Final structure (dhyaan se follow karo)**:
  - Sales manager ke paas: **3 tools** (sales agent 1/2/3 — email writers) + **1 handoff** (**Emailer/Email Manager agent**).
  - Aur confusingly — **us handoff agent ke paas khud 3 tools hain**: subject writer, HTML converter, send HTML email. (Par uske paas **khud koi handoff nahi**.)
  - Ed ka mantra: **confusion ho to PRINT karo** — `print(tools)`, `print(handoffs)` — structure khud dikh jayega: tools mein 3 sales agents, handoffs mein 1 Email Manager jiske andar apne function tools hain.
  - Agle lecture mein isko actually **run** karenge.

---

## 🔑 Key Concepts / Important Terms

| Term | Simple Hinglish Meaning |
|------|--------------------------|
| **Handoff** | Agent ka doosre agent ko **control transfer** karna — poora kaam delegate, flow wapas nahi aata |
| **Agent as Tool (`as_tool`)** | Agent ko tool bana ke use karna — **request-response**, control caller ke paas wapas aata hai |
| **Conceptual difference** | Tool = apne kaam mein chhota helper; Handoff = specialist task ki **ownership transfer** |
| **Technical difference** | Tool call ke baad control **wapas**; handoff ke baad control **gaya so gaya** (one-way) |
| **`handoff_description`** | Agent ka self-intro doosre agents ke liye — "main ye kar sakta hoon" (tool description jaisa) |
| **Subject Writer agent** | Email body se catchy **subject** likhne wala agent (as_tool se tool bana) |
| **HTML Converter agent** | Text/markdown email ko **HTML email** mein convert karne wala agent (as_tool se tool bana) |
| **`send_html_email`** | `function_tool` — subject + HTML body le ke SendGrid se HTML email bhejta hai |
| **Emailer Agent / Email Manager** | Wo agent jisko handoff hota hai — apne 3 tools se format + send karta hai |
| **Print to debug** | `print(tools)` / `print(handoffs)` — structure confuse kare to print karke inspect karo |

---

## 💡 Backend Dev Ke Liye Note (aapke liye)

- **Tools vs Handoffs = sync RPC vs fire-and-forward**: tool call bilkul **HTTP request-response** jaisa hai (call → result → tum continue), jabki handoff **message queue pe task push karke aage badhna** ya **nginx ka request doosre upstream ko proxy_pass** karna hai — response wapas original handler ke paas nahi aata. Architecture decide karte waqt yahi pucho: "kya mujhe result chahiye aage process karne ke liye (tool), ya main bas responsibility transfer kar raha hoon (handoff)?"
- **`handoff_description` = service discovery metadata**: jaise microservices registry mein har service apna capability descriptor publish karti hai, waise hi ye string LLM-router ko batati hai ki kab is agent ko delegate karna hai. Tool ka `description` aur handoff ka `handoff_description` — dono LLM ke liye **routing signal** hain, isliye inhe API docs jitni seriously likho.
- **Uniform interface FTW**: `as_tool` ke baad wrapped-agent aur plain function **dono `FunctionTool`** dikhte hain — yahi **adapter pattern** hai. Caller (sales manager) ko fark nahi padta tool ke peeche function hai ya poora agent — bilkul jaise interface ke against code karna.
- **Hands-on lab**: is lecture ka code khud chalane ke liye `Practical/lab2_sales_agents_handoffs.py` run karo (is repo me, `uv run` se chalta hai, Groq pe free). Note: lecture mein **SendGrid** (account + API key + verified sender chahiye) use hota hai, par hamare labs **OpenAI ki jagah FREE Groq** use karte hain (`OpenAIChatCompletionsModel` + `base_url` trick) aur email-send ko local stub se handle karte hain — SendGrid setup ke bina bhi poora handoff flow seekh sakte ho.

---

## 🧠 Takeaway (yaad rakho)

1. **Agent-as-tool = request-response** — control caller ke paas **wapas aata hai**; **Handoff = delegation** — control **transfer ho jaata hai, wapas nahi aata**.
2. Conceptually: tool = apne job mein chhota helper; handoff = **specialist task ki poori ownership** doosre agent ko dena.
3. **`handoff_description`** se agent doosre agents ko batata hai ki wo kya karta hai — tool description ka handoff-version; routing iske bharose hai.
4. `as_tool` ke baad **agents aur functions dono same `FunctionTool`** dikhte hain — uniform interface, caller ko peeche ka fark nahi padta.
5. Structure confuse kare to **print karo** — tools, handoffs, nested tools — sab inspect karke hi aage badho.

---

<details>
<summary>📜 Full English Transcript (original, click to expand)</summary>

Okay, now to recap. What have we done? We first just used agents to write Python code so that agents could run. We sort of sneakily used the async gather so that we could run multiple in parallel. And then we used another agent afterwards to pick the best email. That was simple. We then use tools to wrap a function so that we could have an agent that calls a function. And we also used the as tool construct so that we could wrap other agents to be a tool. And we provided all of those tools to our sales manager agent. And we let it call three different email producers and then finally send the email at the end. So that's that's hopefully connecting for you, making a lot of sense.

There is one more construct that is in some ways really similar. So it's a bit confusing, but there is a distinction and it's called a handoff. A handoff is something that you can give an agent. An agent has a number of tools, and a number of handoffs, and handoffs are other agents that it can delegate to. So in many ways, that sounds really similar to taking an agent and wrapping it as a tool. An agent as tool is very similar to a handoff. There's a kind of conceptual difference and and a very practical difference. The conceptual difference is that you can you can sort of think of it like there's an agent which either has just the ability to use tools as part of doing its job, or handoff is when it's delegating. It's sort of giving giving responsibility and ownership of a specialist task to another agent. So sort of philosophically, it's a bit of a different mindset. It's not just just using this as a little feature, a little tool to help with its job. It's it's passing an entire job to another agent. But there's a more sort of fundamental, simple technical difference between them, which is that when you're using tools, you can think of that more as a request response. You're calling the tool and control passes back to you, and you continue as the main agent executing in the case of handoffs. You've done your piece, and you are now passing control to the other agent, and the flow does not come back to you again. It's just a passing of control, delegation of control to a different agent. So that's the difference between agents as tools and handoffs. And it's uh, you can you can use either in different situations, but but they are slightly different constructs. So I explain that a little bit here.

And now we're going to make a new agent that eventually is going to be a handoff. So here's the deal. We are going to start by saying that, uh, you are I want a subject writer agent, something that is able to write, construct a subject for a given email body because I don't know if you noticed, but we didn't have subjects on those emails. So we're saying you can write subject for email. When you're given a message. You need to write a subject for an email that's likely to get a response. So that's one instructions. Another instructions is going to be that you can convert a text email to an HTML email, a formatted email, which is how most emails get sent these days, particularly the fancy sales emails. So you will be given a text email. Body might have some markdown because LLMs often put markdown in these things, and you need to convert it to an HTML email with simple, clear, compelling layout and design.

So we're then going to make an agent for the subject writer with those instructions. And we're going to use the as tool approach. This time we're going to make this a tool because it sounds like a tool right. It's just a tool to write a subject. So we're going to have a tool. and that tool is going to be wrapped around this agent. Similarly for the HTML converter, we're going to say, okay, so you're something which is able to write HTML emails. We're going to make you a tool. We're going to turn you into a tool, an HTML tool that's able to do that. All right. Let's oops what have I done. I'm in Cursor land. Undo that. All right. Run that. Great.

Okay. And then we're going to have one more tool which is rather similar to to the prior send email. But I've made this a send HTML email. And it takes a subject and a body. And it sends out an email with the given subject and body to all sales prospects. Again, remember to change this to your verified email sender. Make this some other email than mine please, and then send using SendGrid. And you can see there's just a tiny change here that it sends it as an HTML email, not a text email.

Okay. So then we now have three tools subject HTML tool, and a subject tool that creates a subject, an HTML tool that converts a text email to HTML and the send tool. So two of these are agents. And one of them let's print them. Let's have a look. Tools. Two of them. They're all function tools. Two of them are actual agents wrapped. And one of them is just a function.

Okay, we're almost there. Almost there. So now now we're going to create a separate agent. And this is going to be the agent that we're going to want to hand off to. If you're wondering what I'm where this is all heading. So this agent says you are an email formatter and sender. You receive the body of an email. You first use the subject writer tool, then the HTML converter tool. And finally you send the email. So we call this emailer agent. It has a name, it has instructions. It has tools. It has something new in here. Handoff description. Convert an email to HTML and send it. Now this. This is how this agent will sort of announce itself to the world in case another agent wants to use it. If there's another agent that might want to to do something, this is how it knows whether or not the emailer agent is an agent that might be useful. So that's a sort of framing. It's very similar to the to the tool description. It's a description of what this agent does.

Okay. So if you've been following me you will now be clear that we have three tools. These are the three sales agents. And we have a handoff. We have this thing this this agent which we can hand over control to. And somewhat confusingly, this handoff itself has three tools. Subject writer, HTML converter, and a send HTML email. Are you following this? If not, come back, go through it. Or of course, print. It's always good to print. We should print tools, and we should print handoffs and take a look at what we've got. So this is the tools are just the sales email sales agent one, two and three. And the handoffs is a single agent called the email manager. And this agent we should see itself will have a bunch of tools. It has a handoff description. It doesn't have any handoffs itself. But somewhere in here we should find that it has a few tools. Here they are tools function tool names, subject writer and so on. All right. If any of that's not clear, come back, look through this, print it, get a sense of it and then we will actually run this.

</details>

---
*Source: Official Udemy lecture transcript (auto-captions, lightly cleaned). Notes in Hinglish for self-study.*
