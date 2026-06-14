# L113 — Real-Time Agent Monitoring and the Security Risks of Production AI

> **Week 4 · Day 4** · ⏱️ ~10 min

---

## 🎯 TL;DR

Observability section wrap karte hain ek `watch_agents` script se jo **CloudWatch logs ko real-time tail** karta hai aur har agent ka output alag color mein print karta hai (monitoring, observability nahi). Phir security ke naye angle par jaate hain: **Agentic AI / MCP servers ke information-security risks** — aur Simon Willison ka **"lethal trifecta"** introduce karte hain (private data + untrusted content + external communication), with the GitHub MCP vulnerability as a teaser.

---

## 🗣️ Hinglish Explanation

### `watch_agents` — CloudWatch logs ko real-time tail karna

Observability section khatam hone se pehle ek aur chhota gem. Ed ke paas ek script hai: **`watch_agents`**, jo **backend directory** mein hai. Run karna:

```bash
# backend directory mein
uv run watch_agents
```

Yeh script **AWS CLI** ko call karke **CloudWatch** mein log hone wale logs ko dekhne ka ek doosra tarika hai.

**Monitoring vs Observability** ka difference yahan phir relevant:
- Pichle lectures (Langfuse) — **observability** (deep insight, traces, scores)
- `watch_agents` — yeh zyada **monitoring** hai (real-time log tailing), observability nahi
- Ed bolte hain *"it looks cool"*, isliye end ke liye bachaya

Background mein **CloudWatch** kya hai: AWS ka centralized logging + metrics service. Lambda functions automatically apne logs CloudWatch mein bhejte hain (log groups + log streams). `watch_agents` AWS CLI se in logs ko **tail** karta hai (continuously latest logs follow karta hai).

### Demo — colored logs flowing

Script chala ke Ed dashboard par jaate hain → **Advisor Team** → new analysis kick off karte hain ("find out what's going on with our investments").

Jaise hi analysis chalti hai, `watch_agents` **constantly logs tail** karta hai aur **har agent ke logs alag color mein** print karta hai. Ed kehte hain unke saare courses ka final project aksar "different colored logs from different agents" se khatam hota hai — *"I guess that's my thing"*.

Logs mein dikhta hai (top se):
1. **Observability config check** — "Langfuse setup complete"
2. **Polygon.io se market prices fetch** — financial data API
3. **Reporter running** — apni report bana raha hai
4. **Planner ne invoke kiya** — reporter, charter, retirement
5. Ek **interesting error** dikhta hai — yeh wo Langfuse code se related hai jo ek **variable/result track** karne ki koshish kar raha tha. Current Langfuse + OpenAI Agents SDK integration is variable tracking ko allow nahi karta. Ed ko ummeed hai yeh jaldi fix hoga. **Error kuch nahi rokta** — bas wo result properly track nahi ho pata
6. **Charter** finish hota hai → JSON for charts
7. **Retirement** → 10s wait at end
8. Wapas **Planner** → charter completed → retirement lambda invoke
9. **Planner ka 15-second wait** for flush (yeh wahi `time.sleep` hack hai) — "final, final, final part"
10. Planner finishes → duration + memory size track

Phir screens par results dikhte hain: overview, retirement, charts. Sab logs ke through flow hota dikhta hai. Yeh CloudWatch se aata hai — bas logs dekhne ka ek aur tarika, production mein sab kuch observe karne ka.

### Security — naya angle: Agentic AI / MCP risks

Ab Ed gear shift karte hain. Pehle security mein humne **general cloud security** dekhi — IAM permissions, JWT, etc. Par security ka ek doosra side bhi hai: **agents ke specific security concerns**.

**Agentic AI** aur khaaskar **MCP servers** ki amazing success ne kuch significant naye risks introduce kiye hain. MCP (Model Context Protocol) servers agents ko nayi functionality dete hain — par yeh risks bhi laate hain.

Ek tarah se: **MCP server chalana ek `pip install` jaisa hi hai** — kisi open-source package ka code chala rahe ho. Tum agent ko functionality de rahe ho, aur yeh ensure karna padega ki wo functionality secure hai.

### Pehla concern — accessibility / education problem

Pehla problem: **MCP servers itne easy hain access karna** ki technically kam savvy log bhi ek MCP server le ke Claude se attach kar sakte hain. Phir Claude usse use karke functionality kar sakta hai.

Jaha koi `pip install` karna nahi jaanta, wahan wo **suddenly doosron ka code apne computer par chala raha hai** — bina samjhe. Yeh ek **education problem** hai:
- MCP server authors par **trust** karna zaroori
- Jaanna ki tum agent ko **kya functionality** de rahe ho

### Doosra concern — Simon Willison ka "Lethal Trifecta"

Ek aur deep security concern. Ed **Simon Willison** ka reference dete hain — wahi banda jisne wo blog post likhi (pelicans riding bikes wale SVGs), ek great LLM writer. Simon ne deeply dekha ki LLMs ko MCP servers dene se kaun se naye problems aate hain — recent issues jaise **Supabase MCP server** aur famously **GitHub MCP server** ke.

Simon ka insight: ek situation hoti hai jab model ke paas **teen abilities** hon — aur agar **teeno** maujood hon, toh naye tarah ka security risk khulta hai. Inhe Simon ne bola **"lethal trifecta"** (Google karo, blog post great aur funny hai — ek presentation thi jo unhone blog kiya).

#### Trifecta ka pillar 1 — Access to private data

Agent (ya MCP server) ke paas **private data tak access** ho — data jo public domain mein nahi hona chahiye.
- **Bahut common** hai
- **Alex ke liye?** Haan, definitely. Alex users ka **private equity portfolio** access kar sakta hai — yeh confidential hai. ✅ Hit.

#### Trifecta ka pillar 2 — Access to untrusted content

Agent ke paas **untrusted content** tak access ho. Iska matlab: prompt text jo **tumne (developer ne) nahi likha** — bahar se aaya prompt jo agent tak pahunch jaaye.
- Untrusted content = aisa text jo software developers ne agent framework ke liye nahi likha
- Ed bolte hain Alex ke liye iske baare mein socho (next lecture mein answer)

#### Trifecta ka pillar 3 — Ability to communicate externally

Kya agent ke paas **bahar (external third party) ko information bhejne** ki ability hai?

Simon ka point: agar in teeno mein se **1 ya 2** hon, toh zaroori nahi koi naya security loophole ho. Par agar **teeno** hon, toh trouble shuru ho sakti hai.

### Teaser — GitHub MCP server vulnerability

Ek famous example: **GitHub MCP server** jisme ek vulnerability/loophole tha. Yeh next lecture mein detail mein samjhaaya jaayega — par idea yeh hai ki teeno trifecta ingredients ek saath aane se ek real-world exploit possible hua.

---

## 📋 Key Concepts

| Concept | Matlab |
|---|---|
| **`watch_agents`** | Backend script — AWS CLI se CloudWatch logs ko real-time tail karta hai, colored per agent |
| **Monitoring vs Observability** | Monitoring = real-time logs/metrics dekhna; Observability = deep insight + traces |
| **CloudWatch** | AWS ka centralized logging + metrics service; Lambda logs yahan jaate hain |
| **Polygon.io** | Financial market data API jo agents market prices fetch karne ko use karte hain |
| **MCP server** | Model Context Protocol server — agents ko nayi functionality deta hai (pip install jaisa risk) |
| **Education problem** | MCP itne easy hain ki non-technical log bhi anjaane mein doosron ka code chala dete hain |
| **Lethal Trifecta** | Simon Willison ka concept — 3 abilities saath = security risk |
| **Pillar 1: Private data** | Agent ke paas confidential data access (Alex: user portfolio) |
| **Pillar 2: Untrusted content** | Bahar se aaya prompt text jo developer ne nahi likha |
| **Pillar 3: External communication** | Agent ki bahar third party ko data bhejne ki ability |
| **Simon Willison** | LLM writer/researcher — lethal trifecta concept ke author |

---

## 💼 Backend Dev Ke Liye Note

`watch_agents` = `kubectl logs -f` ya `aws logs tail --follow` ka custom wrapper — real-time log tailing jo har backend dev `tail -f` se jaanta hai. Yahan AWS CLI ke `logs tail` command ke peeche multi-stream aggregation + per-source coloring hai. CloudWatch log groups/streams ko apne ELK/Loki/Splunk stack ka AWS-native equivalent samjho. Yeh monitoring layer (real-time, reactive) observability layer (Langfuse, analytical) se complement karta hai — production mein dono chahiye.

Security part backend dev ke liye sabse valuable hai. **Lethal trifecta** ka concept SQL injection / SSRF / data exfiltration ki tradition ka extension hai: private data access + attacker-controlled input + outbound channel = exfiltration vector. Tum yeh teen-pillar lens har system par laga sakte ho — koi bhi service jo (1) secrets/PII padhti hai, (2) untrusted input leti hai, aur (3) external egress kar sakti hai, wo data-leak risk rakhti hai. MCP server ko **untrusted dependency** treat karo — bilkul jaise tum naye npm/pip package ko supply-chain risk maante ho. Principle of least privilege (scoped tokens, network egress controls, separate creds per scope) yahan bhi apply hota hai. Next lecture mein GitHub MCP exploit dikhega — wo ek textbook prompt-injection + privilege-confusion case hai jo har AI-integrating backend dev ko padhna chahiye.

---

## ✅ Takeaway

- **`watch_agents`** script CloudWatch logs ko real-time tail karke har agent ke output ko colored print karta hai — yeh **monitoring** hai (Langfuse = observability)
- Logs mein observability setup, Polygon.io market fetch, agent flow, aur ek harmless Langfuse-tracking error dikhta hai (kuch rokta nahi); end mein 15s flush wait (time.sleep hack)
- **Agentic AI + MCP servers** naye security risks laate hain — MCP server chalana `pip install` jaisa hai, aur "easy access" ek education/trust problem hai
- **Lethal Trifecta** (Simon Willison): (1) private data access + (2) untrusted content + (3) external communication — teeno saath = real security risk
- Question to hold: kya **Alex** ke paas teeno pillars hain? (private portfolio = haan; baaki next lecture mein) — GitHub MCP vulnerability teaser ke saath

---

<details>
<summary>📜 Full Transcript (English)</summary>

Well, I hope that long fuse brought you much joy, and you felt like a true ML ops person while you dug in to your agent conversations. All right, so that's pretty much wraps up the observability section, especially if you spent some quality time with it. But there's one more tiny nugget to show you one more thing, which is that I have a little script to demo to you called Watch Agents, which is in the backend directory. If you go into the backend directory and you type, you've run watch agents. This shows you it's going to call the AWS cli as another way to look at the log information that's being logged to CloudWatch. So this is really more about monitoring than observability. But it looks cool. So I wanted to leave it till the very end. All right so this is running. And you might say well I'm not sure that it does look cool. It looks kind of boring to me. You could be forgiven for saying that. But let's go to our dashboard, this beautiful screen, and let's go to the advisor team and kick off a new analysis. We'd like to find out what's going on with our with our investments, please. And while we do so, we will look back at this and oh, something just happened. Uh, it actually is constantly tailing the logs and printing the logs from each of the different agents, and it will print the report from each agent with a different color here. And people who've been on my courses before, they all seem to end the final project. The final part ends with something logging with different colors from different agents. I don't know why. I guess that's my thing. Uh, so you can see if I scroll up, you'll see the planner doing doing first of all. Uh, well, first, at the very top, you'll see that it checks the observability configuration, sets up Lang fuse set up complete. And now you'll see that, uh, it's doing the fetching of market prices from polygon IO. And then it's making its, uh, it's its report right here. The reporter is running and um, uh, let's go see. See it doing this. This is where planner evoked reporter evoked charter and invoked retirement. And this is this is that going, uh, you'll see this little error here, which is an interesting one. This is it's reporting the fact. I don't know if you remember, I had some longview's code to track that variable. The, the, the, the results that I wanted to track. And the current way that Lang fuse is working with open AI agents SDK doesn't allow you to do that. I'm hoping that's something that they will fix shortly. So by the time you run this, that error might not be there. And you may find that that result is getting properly tracked in Lang Fuse. But it doesn't matter. The error doesn't stop anything. You can just see the charter just finished and it responded with its JSON for the charts. And, uh, retirement is just here. And you'll see this purple at the end is the, the the traces finishing up. Um, and now we're back to planner again. Charter completed successfully. It's evoking the retirement lambda. Uh, so we'll let that one go. And. Here we see the retirement information coming through. It's in it's waiting 10s at the end. And we're now back to planner again. Planner is now doing its 15 second wait for the flush to complete. This is the final, final, final part. We'll give it its 15 seconds. Uh, this is the hack that I put in to make sure that all of the the observability Finishes planner just finished. It tracks its duration, the memory size. And then now, if we turn back to the screens, we'll see that the results are showing with the overview, the retirement and the charts that we just saw coming through in our log. So there was a lot to follow there. You're probably like, what's going on? Uh, but it's cool to see this. It's cool to see the different colors of the different ports coming from our logs. Uh, as this as this all comes out as it flows from our different agents. Uh, and so this is giving you yet another view. It's again, it's coming from CloudWatch, but it's another way of looking at your logs. Another way of observing everything that's going on in production. Well, I promised you a substantive day and I hope you agree I delivered. I realized I did a lot of talking, but also I showed you stuff, I showed you monitoring, and I showed you observability in the wonderful form of languages, which I hope you enjoyed. And also, of course, that script at the end with agents logging in color, because that's how we do it. Uh uh, so we, we did a lot of stuff when we talked about security. We focused on the kind of pretty general cloud security, like IAM permissions and about JWT and stuff like that. There is another side of security as well, which is being very mindful of some of the kinds of security concerns people have with agents in particular. And so I thought it was worth spending one second on that. There are a lot of concerns about the new information security risks posed by Agentic AI and in particular, the the, uh, amazing success of MCP servers, which allows you to equip agents with new functionality, brings about some significant risks, and it's important to understand what those risks are. Now, on the one hand, running an MCP server is not much different from doing a pip install of any open source package and running that code You're equipping an agent with the ability to use this functionality, and you need to make sure that that functionality is secure. And so the first the first thing that people, people think about is what what are the new security risks. What what what is the problem? One problem is that MCP servers are so easy to access that even people who aren't necessarily as technically savvy as you and me can easily just get an MCP server and attach it to Claude. And then Claude can start using it to do functionality. And where someone might not know how to pip install a package, they can suddenly be running other people's code on their computer. So that's definitely an education problem. And that's something where we need everyone to be aware of the need to trust the authors of MCP servers and know the detail of what kind of functionality you are equipping an agent with. But there's something else as well. There is another security concern that's worth digging into, and that is something which I'm going to show you now. I'm going to use the words of Simon Willison, who is the the person that wrote a blog post I showed you earlier this week, which he. He's the guy I mentioned likes to make. Uh llms draw pictures of svg's of pelicans riding bikes, and he's a great writer and has so much to say about Llms. And he was was looking deeply at what what are the issues that have emerged as a result of giving models, giving Llms access to MCP servers? What new problems do they introduce? Particularly thinking about recently, there's been some problems with Superbase MCP server and famously with a GitHub MCP server. And what his his insight is that there is a situation when you give when when you're in a situation when a model has three different abilities, and if you have all three of those abilities, then that can open up new kinds of security risk. And let me tell you about what they are. And then we'll, we'll, uh, think about it a bit. And I also want to ask you the question of do we have those three in the case of Alex. So have that in the back of your mind. And because there's three of them, Simon described them as the lethal trifecta. And if you Google that, you can read his blog post. And it's great and super funny. It was actually a presentation that he gave that he then blogged about afterwards. So the first of them is an MCP server that has or just just generally an agent, an agent that is given the ability to access private data. So any MCP server that is able. One of the things it can do is access data that should not be in the public domain. Um, and obviously that's very common. And yeah, obviously, certainly that is true for us. In the case of Alex. Alex is able to access the private equity portfolio of of the users. So the model does have access to private data. Okay. So that's one of the tenants of the Lethal trifecta. The second of them is access to untrusted content. What does that mean? So that's saying like if if someone is able to type in a prompt, a prompt from the outside that will be able to get in and be something which is sent to this agent. So untrusted content means stuff. Prompt text that we didn't write. As the software developers, you didn't write for your agent framework. So access to untrusted content is something that would be the second pillar. I have a think about whether or not any of that applies for Alex. Is there any is there any case when the user is prompting Alex, the, the, the agent, and then the third tenant is the ability to communicate externally? So does this agent have the ability to send information to an external third party? That is the third. And what Simon explains in the in the post is that if you have 1 or 2 of these three, then you're not necessarily in big, in big trouble in any new kind of security loophole. But if you have all three, then trouble can ensue. And he gives a few examples. But one of them, famously, is an example of a GitHub MCP server that had had a vulnerability, a loophole.

</details>
