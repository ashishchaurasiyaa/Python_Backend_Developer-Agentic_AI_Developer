# L112 — Day 1: Agent That Uses Multiple MCP Servers

> **Week 6 — MCP** · ⏱️ ~11m · 🎥 Lecture 112 of 131
> **Instructor:** Ed Donner · **Lecture ID:** 50767611

---

## 🎯 Ek Line Mein (TL;DR)

Pehli baar ek **agent ko do MCP servers ek saath** diye jaate hain — **Playwright (browser automation)** + **filesystem (disk write)** — aur agent khud internet browse karke banoffee pie recipe dhundh kar Markdown file me likh deta hai; phir **MCP marketplaces (mcp.so, Glama)** aur **MCP server security** (pip install jitna hi risk) pe discussion hoti hai.

---

## 📝 Hinglish Explanation (Detailed)

- **Setup — sirf tools list karna kaafi nahi:** Pichle lecture me humne MCP server spawn karke uske tools list kiye the. Ab actual kaam karwayenge — ek **agent jo in tools ko use kare**.

- **Agent instructions:** Agent ko bola gaya — *"You browse the internet to accomplish your instructions... including accepting cookies, clicking 'Not Now'. If one website isn't fruitful, try another. Be persistent."* Yaani agent ko **autonomous web browsing** ke liye prep kiya gaya hai — cookie banners, popups sab khud handle kare.

- **Do MCP servers, same context manager pattern:** Wahi **async context manager** (`MCPServerStdio`) use hota hai jo pehle tools list karne ke liye use kiya tha — params pass karo, **timeout yaad rakho**. Ye **dono servers** ke liye kiya jaata hai:
  - **Filesystem MCP server** — disk pe files likh sakta hai (sandbox folder me)
  - **Playwright MCP server** — browser ko **fine-grained control** karta hai (navigate, click, etc.)

- **Agent creation — `mcp_servers` parameter (key idea):** Agent ka naam **"investigator"**, instructions wahi, model **GPT-4.1 mini** (latest and greatest us waqt). Magic line: pehle hum `tools=[...]` directly pass karte the — ab uski jagah **`mcp_servers=[...]`** pass karte ho. **OpenAI Agents SDK khud in servers ko query karke unke tools discover karta hai** aur agent ko capabilities de deta hai. Bas — itna hi complicated hai. Ye hai MCP integration ka poora "framework code".

- **Run flow — Week 2 wala hi pattern:** (1) Agent banao, (2) **trace** set up karo (OpenAI UI me track karne ke liye), (3) **Runner** call karo. Assignment: *"Find a great recipe for banoffee pie, then summarize it in Markdown to banoffee.md"*.

- **Banoffee pie tangent 😄:** Ed ka British pride moment — banana + toffee pie, British invention, "we Brits aren't known for cooking but banoffee pie is amazing". (Ed khud kuch nahi paka sakta except banoffee pie!)

- **Live run — kya hota hai:**
  - Agent MCP servers **spawn** karta hai, ek **browser window pop up** hoti hai screen pe
  - Agent **BBC Good Food** pe jaata hai (khud samjha ki ye British dish hai!) — page title se dikh raha hai ki banoffee pie recipe mil gayi
  - Kabhi-kabhi agent ko **actually clicking/navigating** karte hue dekh sakte ho
  - **Sandbox folder me `banoffee.md`** ban gaya — yaani **dusra MCP server (filesystem)** bhi use hua disk pe likhne ke liye
  - **Mission accomplished** — ek hi agent ne do alag MCP servers coordinate karke task complete kiya

- **Trace inspection (OpenAI Traces UI):** Trace me dikhta hai:
  - Har MCP server ke **MCP tools list** hue
  - **`browser_navigate`** tool use hua web page kholne ke liye
  - File tools — kisi wajah se ek **`read_file`** hua, phir **`write_file`** se recipe likhi gayi
  - Lesson: **hamesha trace check karo** — sahi tools, sahi tarike se use ho rahe hain ya nahi.

- **The "aha moment" — MCP Marketplaces:** MCP ki asli excitement tab samajh aati hai jab pehli baar **MCP marketplace** dekhte ho — websites jahan saare available MCP servers listed hain:
  - **mcp.so** — bahut popular. Featured list me Playwright MCP server bhi hai (publisher: **Microsoft** — legit hone ka signal). Har server ke **integration params** aur **tools list** dikhte hain.
  - **Explore tab** — categories ke hisaab se search/filter: **Research & Data: ~4000 servers**, Browser Automation: 68, Knowledge & Memory: 34 (agent ko yaad rakhna sikhane ke alag-alag tarike), Calendar managers: 19, aur sabse bada — **Developer Tools: 7344**! (Categories me overlap hoga, but scale ka idea milta hai.)
  - **Glama** — dusra popular marketplace. Ye har server ko **security, license permissiveness, aur quality** ki **ratings** deta hai — vetting ke liye helpful.

- **Security — bada important topic:**
  - **Core concern:** MCP server **tumhare computer pe chalta hai** — tum **kisi aur ka code apne box pe run** kar rahe ho. (Remote/hosted MCP servers ke liye alag se **authentication** ka system hai, but local case zyada common hai.)
  - **Ed ka key framing:** MCP server chalana **bilkul `pip install` ya `npm install` jitna hi risky hai** — open source code download karke run karna. Na zyada, na kam.
  - **Due diligence checklist:** Publisher kaun hai (Microsoft/Anthropic = probably safe), **GitHub stars**, **active community**, good feedback, security reviews — wahi sab jo PyPI package ke liye karte ho.
  - **Docker option:** Kuch MCP servers **Docker container** ke andar run kar sakte ho — extra security isolation milta hai.
  - **Asli worry — non-technical end users:** Concern zyada un logon ke liye hai jo **Claude Desktop** jaise apps me MCP servers add karte hain bina vetting skills ke — wo GitHub repo check karna nahi jaante. Developers (hum) ke paas ye skills hain.
  - **Practical tip:** Glama ki security ratings padho, unke tests samjho — starting point ke taur pe rule bana sakte ho: **sirf "triple-A" rated servers hi use karoonga**.

---

## 🔑 Key Concepts / Important Terms

| Term | Simple Hinglish Meaning |
|------|--------------------------|
| **`mcp_servers` parameter** | Agent banate waqt `tools=` ki jagah MCP servers ki list pass karo — SDK khud tools discover kar leta hai |
| **Playwright MCP server** | Microsoft ka MCP server jo browser ko fine-grained control karta hai (navigate, click, cookies accept) |
| **Filesystem MCP server** | MCP server jo sandbox folder me files read/write karta hai |
| **Multiple MCP servers** | Ek agent ko ek se zyada servers dena — agent khud decide karta hai kaunsa tool kab use karna hai |
| **Trace** | OpenAI UI me agent run ki step-by-step recording — kaunse tools list hue, kaunse call hue |
| **MCP Marketplace** | Websites (mcp.so, Glama) jahan hazaaron ready-made MCP servers browse/search kar sakte ho |
| **mcp.so** | Popular marketplace — categories me 7000+ developer tools, 4000 research servers |
| **Glama** | Marketplace jo security, license, quality ki ratings deta hai |
| **MCP security** | Server = kisi aur ka code tumhare machine pe; risk wahi jo `pip install` ka hai — due diligence zaroori |
| **Docker isolation** | MCP server ko container me chalana — extra security boundary |

---

## 💡 Backend Dev Ke Liye Note (aapke liye)

- **`mcp_servers=[...]` vs `tools=[...]` — dependency injection ka feel:** Pehle tum har tool ka JSON schema khud likhte the; ab SDK **runtime pe `list_tools` query** karke schemas auto-discover karta hai — bilkul jaise OpenAPI/Swagger spec se client auto-generate hota hai. Tool registry ab server ki responsibility hai, client ki nahi.
- **Security framing tumhare liye familiar hai — supply-chain risk:** MCP server install karna = unaudited PyPI/npm dependency add karna. Wahi threat model: typosquatting, malicious maintainer, transitive trust. Tumhara existing instinct (stars, publisher, lockfiles, Docker sandboxing) directly apply hota hai — Ed yahi keh raha hai, bas MCP context me.
- **Trace = distributed tracing for agents:** `read_file` ka unexpected call trace me dikhna wahi cheez hai jo tum Jaeger/Datadog me dekhte ho — agent ka har tool call ek span hai. Non-deterministic systems me observability optional nahi, mandatory hai.
- **Hands-on lab:** `Practical/lab3_memory_market_servers.py` (is repo me, `uv run` se chalta hai, Groq pe free) — **is lecture ka code khud chalane ke liye ye lab run karo**. Note: lecture ke npx wale servers (filesystem + Playwright) ki jagah hamare labs me **Python FastMCP servers** hain (`servers/` folder me) — Playwright skip kiya hai, aur paid APIs ki jagah free substitutes (memory server + simulated market server) use hote hain; concept (ek agent + multiple MCP servers) bilkul same hai.

---

## 🧠 Takeaway (yaad rakho)

1. Agent ko MCP tools dene ke liye bas **`mcp_servers=[server1, server2]`** pass karo — OpenAI Agents SDK khud tools query karke agent ko de deta hai.
2. Ek agent **multiple MCP servers ko coordinate** kar sakta hai — Playwright se browse kiya, filesystem se `banoffee.md` likha — bina ek line custom tool code ke.
3. **Trace hamesha check karo** — kaunse tools list hue, kaunse call hue, expected behaviour hai ya nahi.
4. **Marketplaces (mcp.so, Glama) = MCP ka asli "aha moment"** — hazaaron ready-made servers (7344 sirf developer tools me!).
5. **MCP server chalana = `pip install` karna** — same supply-chain risk, same due diligence (publisher, stars, community, Glama security ratings, Docker isolation).

---

<details>
<summary>📜 Full English Transcript (original, click to expand)</summary>

Okay, so you're probably thinking, all right, I get it. We can create something that spawns a server and that tells us a bunch of tools, but that doesn't sound much fun. We want it to actually do stuff, and that's what we'll get to right now. So we are now going to make just a quick example of an agent that will use these tools. So here we go. Here are some instructions for our agent. You browse the internet to accomplish your instructions. You're highly capable of browsing the internet independently to accomplish your task, including accepting cookies. Clicking not now. If at one website it's a fruitful try another. Be persistent until you've solved your assignment. So that's a nice set of instructions to prep our server.

So we now again use this same context manager as before, the one we used to collect the names of tools. We pass in the parameters we want. And again remember that timeout. And we'll do it for both of our MCP servers, the file one MCP server, the one that can write to the disk, and the Playwright one that can control a browser in a fine grained way. And we will create an agent and it is called investigator. We give it those instructions, we'll give it that model. We might as well. Let's change this to be the latest and greatest GPT 4.1 mini. And then look, this is it. You then pass in a collection of MCP servers. You might remember in the past that you passed in. You could pass in tools directly in here. Well, rather than tools you can pass in MCP servers. And OpenAI Agents SDK will query these for understanding their tools and provide those capabilities to this investigator agent. And that is as complicated as it gets. That's how we equip our agents to be able to use these tools.

And now, if you remember, do you remember the OpenAI Agents SDK once you've created the agent? That was step one. Step two is you set up a trace so that we can track this in the UI. And then we call runner. And what is the assignment that I'm going to give our agent? I'm going to say find a great recipe for banoffee pie. Then summarize it in Markdown to banoffee.md. And you may be wondering what on earth is banoffee pie? And I think it's a tragedy that you're wondering that. Banoffee pie. Us, us, us Brits, we're not well known for our cooking. Let's face it, we're not necessarily the purveyors of the great delicacies of the world, but banoffee pie is something that I think we invented, and it's really amazing. And I think it's a great shame that more people don't know about it. And so that's why I'm doing you this service, by having this be the thing that we are going to have an agent go off and investigate on our behalf.

And so with that, let's give this a whirl. Okay. We will run this and off it goes. And a few seconds go by, thinks about this request for us. It's spawning these MCP servers and a browser window has just popped up on my computer. Move it! There we go. So it appears to have gone to BBC Good Food. So it obviously does know that this is something British and something is happening behind the scenes. It's thinking about this. You can see from the title of this page that it has indeed located a banoffee pie recipe. So this is the result of the MCP server running. It is driving Playwright. We don't know everything that's doing behind the scenes, but sometimes you get to see it actually like clicking around and navigating. But I suspect, yes, we will find that it has indeed found a recipe for banoffee pie. And from just a quick look at this, I tell you that I'm hopeless at cooking. I can cook nothing. I can hardly cook a boiled egg, but I can cook banoffee pie. I know I can cook, I know how to make banoffee pie. And from a first glance at this, I think that this probably is a legit version of banoffee pie.

But most importantly, we need to look in our sandbox and open the preview of this file and confirm that, sure enough, it has used the other MCP server. So not only has it used one MCP server to navigate the internet and locate a recipe for banoffee pie, but it's also used the other MCP server to then write that to disk. And here it is on my computer. So I would say that is mission accomplished. We have used our first two MCP servers.

And you probably remember from week two what comes next. We want to go and look in OpenAI at our trace so we can see what happened behind the scenes. So go in the usual link, up comes traces. Go in to investigate and see what happened, and we'll see that. Of course, it listed the MCP tools associated with each of its MCP servers, and it then used the browser navigate tool to be able to navigate the web page. Yours may look different. You may have more action there. And it then used the file tools. For some reason it did a read file, but then it did the write file to write out the banoffee pie recipe in there, and that shows the interactions between the tools. You should look at it, check it's behaving as you expect. Check it's using the right tools in the right way.

So the aha moment when you realise what makes MCP so exciting is when you first see an MCP marketplace. That's what we're going to do right now. The marketplaces are websites where you can see all the MCP servers that are out there available for you to equip your agent with, and mcp.so is a very popular one, a very common one. Let's go in here. This is launching the marketplace. We see a bunch of different MCP servers in their featured list, including the Playwright MCP server that we just used. And if we go into this, we can look at it. We can see that it has the parameters that we use to integrate with it. There you can have a look at the tools that you can call if you use it. You can see it was created by Microsoft, by the way, which gives you a sense that it's probably legit. And look through all of the information about the tools that it can run.

And if you press the explore tab in the main navigation, then you get to see the sort of search and filter. Over here you can see the different MCP servers in the different categories. And this is where you should get like a wow feeling. There's 4000 in the research and data category. 68 browser automation. Knowledge and memory — equipping your LLM, your agent, to be able to remember things in different ways, 34 of them. 19 different calendar managers and then lots of monitoring visualization. I think somewhere here is developer. That's really the really big category that has tons and tons of MCP servers, but developer tools. Here we go, 7344. So, and I imagine there's some overlap between these categories. But it gives you a sense that there's so much to pick from. There's so much that you can explore here for equipping your agents.

And now let's go and look at a couple of other marketplaces. So the next link I have here is to Glama, which is another popular server marketplace. And you come in here and click on the every MCP server link. And you get to see the ones on Glama. And they also have ratings for security, how permissive the licensing is, and the quality. And you can read about how they come up with this. And that's helpful for assessing the security of these. And again you see the volumes involved. There's a lot of these out there.

Now security brings up a great point. And there's obviously a lot of concern in the community about the security of MCP servers. Because when you run an MCP server, it is running on your computer, running on your box. There is a whole thing about authentication of MCP servers. And again, that's talking more about when you're connecting to a remote MCP server, a hosted or managed MCP server running somewhere else. And then there's ways that you can authenticate with that server. But in this case, and typically most of the time you're running an MCP server, you're running somebody else's code on your computer. And so at first blush, you might say, okay, that's a real concern. And it is. But it's important to keep something in mind. Ultimately running these MCP servers, it's like doing a pip install or an npm install. You are installing open source code on your computer, and that is as dangerous as just doing a pip install of someone else's code. That's what you're doing. The open source community. Of course, it is something where you are signing up for some information risk that you need to manage, and that means that you need to do your due diligence on the tools that you use, just as you would any package that you pip installed from PyPI. It's exactly the same thing.

If it's, of course, a package that's published by Microsoft or Anthropic, then you're probably in good shape. If it's not, then you want to do the usual kind of investigation. You want to check that there's lots of git stars in the GitHub repo, that there's an active community, and that it has good feedback, and that you are satisfied with the kind of security reviews that have happened for that MCP tool. And so MCP servers are only as safe as any code that you directly download and run on your computer, and you need to be very cognizant of that. Of course, there are some MCP servers that you can configure to run inside a Docker container, and that does give you some extra security controls there. But ultimately, you should always be doing your security review by doing your own research of the publisher of this server and of the information about it, and looking into the code and the repo to satisfy yourself that this is something you want to run.

One of the reasons that people are concerned about MCP server security is that people who aren't technologists, people who are just end users, have the ability to add MCP servers to things like Claude Desktop. And that's more worrying because they don't have the same kinds of skills that you and I have. They don't know how to go and track something down in GitHub, make sure it's got a community, make sure that they have a good feeling about the publisher. So when it comes to you and me, we've got this knowledge. We know how to vet packages — open source packages that we install. And so we can do that kind of due diligence. The concern is more where end users are just adding these to Claude and they don't necessarily have those skills. And so that's an important distinction to make. But in addition to that, if you're looking at something like Glama, then you can look at the ratings that they give it for security. And you can read about the kinds of tests that they carry out that means that they're comfortable giving it the A grade. And you can decide that, as a starting point, you're only going to take MCP servers that get three sets of A's on the Glama marketplace.

</details>

---
*Source: Official Udemy lecture transcript (auto-captions, lightly cleaned). Notes in Hinglish for self-study.*
