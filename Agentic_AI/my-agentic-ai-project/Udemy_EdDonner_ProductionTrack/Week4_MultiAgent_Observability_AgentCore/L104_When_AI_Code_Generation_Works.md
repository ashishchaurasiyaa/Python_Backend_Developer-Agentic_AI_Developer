# L104 — When AI Code Generation Works vs Fails in Production Apps

> **Week 4 · Day 3** · ⏱️ ~10 min

---

## 🎯 TL;DR

Ed humein **Alex** (AI financial advisor SaaS) ka pura Next.js frontend + FastAPI backend locally chalakar dikhata hai — landing page, dashboard, accounts, advisor team — sab Claude Code se generated. Real lesson: **LLMs boilerplate frontend/backend par kamaal karte hain, par naye/complex agentic code par struggle karte hain**.

---

## 🗣️ Hinglish Explanation

### Demo: Alex ka frontend live (locally)

Ed `Cmd+Click` karke local app kholta hai aur **landing page** aata hai — "Alex, AI financial advisor — your AI powered financial future". Sab kuch (including copy/marketing text) **Claude Code ne up-front likha**. Page par teen feature cards hain "Meet your AI advisory team" wale, hover effect, "Start your analysis" button, aur ek **fake "Watch demo" button** (abhi kuch nahi karta — future ke liye placeholder).

Yeh app **Clerk authentication** se hooked hai — wahi Clerk jo Week 1 SaaS app mein use kiya tha. Ed **Sign In** dabata hai → Google account choose karta hai → seedha **dashboard** par aa jaata hai.

### Dashboard screen — naya empty user

First-time login isliye dashboard empty hai. Components:
- **Disclaimer** — "This is not official financial advice" (Ed ne specifically add karwaya — legal safety ke liye, jaisa har financial product mein hota hai).
- **Portfolio value**, **number of accounts**, **asset allocation**, **last analysis** ke cards.
- **Settings** section — naam set karo ("Donna"), **Save Settings** → upar ek **toast message** "Settings saved successfully".
- **Target retirement income** — annual income 80,000 set karo. **Locale formatting** lagi hai (Ed ne ask kiya tha) — Europe mein `80.000`, US mein `80,000` dikhega.
- **Asset distribution slider** — North American exposure 80% par drag karo, toh doosra slider **automatically neeche** chala jaata hai (kyunki total 100% rehna chahiye), aur **pie chart smoothly animate** hoke in ho jaata hai. Ed bolta hai "I didn't tell it to do any of this" — Claude ne khud achha UX banaya.

### Accounts tab

Pehle "no accounts found" — clean empty state. Ek **"Populate test data"** button hai (Ed ne baad mein spec dekar add karwaya, initially nahi tha). Dabane par "populating test data → populated successfully" aur ek **test portfolio** spin ho jaata hai:
- 3 accounts: **Brokerage account**, **Roth IRA**, **401(k) long term**.

> **US retirement terms** (Ed bhi UK se aaya, baad mein US move kiya):
> - **401(k)** = employer-sponsored tax-deferred long-term savings plan.
> - **Roth IRA** = individual retirement account (employer na de toh khud kholo); post-tax contributions, tax-free growth.
> - **Brokerage account** = general taxable investing account.
> Ed kehta hai apni location ke hisaab se set karo taaki sense bane.

**Edit button** dabane par "loading account details" → 401(k) account khulta hai positions ke saath: **BND** (total market bond), **IWM**, **QQQ** (Nasdaq), **SPY** (S&P 500), **VTI** (Vanguard Total Index). Yeh values **Polygon API** se aati hain (server real prices calculate karta hai). Ed **IBM** ki position add karta hai — typeahead mein IBM nahi tha, par "if not in database, added automatically" — 10 IBM shares add ho jaate hain (price "N/A" abhi).

### Advisor team tab

Yahan "team of specialist agents" ka mention hai jo milkar comprehensive analysis denge. Abhi "no analysis — press to start your first analysis". Ed run **nahi** karta kyunki yeh sab **locally deployed** hai — agents actual mein Lambda par chalte hain, local machine par nahi. Yahan sirf **Next.js frontend + API layer** dikh raha hai.

### Asli sabak: LLM code generation kab kaam karta hai, kab nahi

Yeh course ka core insight hai. Ed full-stack app ko **properly** deploy karna sikha raha hai — frontend + backend + API layer, sab hold together. Aur ek important observation:

```
AI-generated code achha tha:
  ✅ Frontend (Next.js, color schemes, components, animations)
  ✅ Backend boilerplate (simple API → database calls)

AI-generated code struggle kiya:
  ❌ Agentic part (agents on Lambda, tools, structured outputs)
```

**Kyun?** Frontend aur boilerplate backend **standard, repetitive** cheez hai jo production apps mein common hai — LLM ke training data mein iske **tons of examples** hain. Color schemes, framework scaffolding, CRUD routes — yeh sab LLM ke liye easy hai. Frontend ki difficulty asal mein "bahut saara stuff" (scaffolding) hai, jisme LLM expert hai.

Lekin **agentic stuff naya territory** tha:
- **OpenAI Agents SDK** — sirf is saal (last few months) aaya.
- Use kiya gaya **LiteLLM** ke through **Amazon Bedrock** se attach karke — yeh combo bhi mahine-do mahine purana.
- **OpenAI OSS model** — LLM ko iska pata hi nahi tha ki yeh exist karta hai.
- **Rate limit errors** par Claude **stuck** ho gaya, **over-engineer** kiya, **tool calling** ka "real mess/meal" bana diya.

Matlab: jahan training data mein examples kam hain (naya, complex, non-boilerplate), wahan LLM struggle karta hai. Toh **LLM side** Ed ko khud bahut mehnat karke build karna pada.

### Time math — Claude Code ka real ROI

Ed honestly batata hai:
- **Agentic/LLM part**: agar akele karta toh ~1 week. Claude Code ke saath **~2 weeks** lage — yaani Claude ne **value subtract** kiya (damage kiya, debug karna pada).
- **Frontend + API part**: Claude Code se **~1.5 din** mein banke ready, working, gorgeous. Khud karta toh kam-se-kam **2 weeks** (looks polish karne mein).
- **Net result**: aggregate mein Claude Code ne pure project ka **~60% time** mein kaam karwa diya (yaani ~40% time bacha).

**Takeaway philosophy**: Apna time **agentic/LLM ki hard stuff** par lagao — wahi asli challenge hai. Dashboards aur backend routes par LLM ko free hand do, wo unme "field day" karta hai (easy).

---

## 📋 Key Concepts

| Concept | Matlab |
|---|---|
| **Alex** | Capstone SaaS — agentic AI financial advisor (Next.js + FastAPI + Lambda agents) |
| **Clerk auth** | Week 1 wala same authentication — Google sign-in, user management |
| **Toast message** | Top par chhota transient notification ("Settings saved") |
| **Locale formatting** | Number format region ke hisaab se (US `80,000` vs EU `80.000`) |
| **401(k) / Roth IRA / Brokerage** | US retirement/investing account types |
| **Polygon API** | Real-time market data source — share prices/portfolio values |
| **Boilerplate code** | Standard repetitive code (CRUD, scaffolding) — LLM isme expert |
| **OpenAI Agents SDK** | Naya agent framework (is saal release) — LLM training data mein kam examples |
| **LiteLLM + Bedrock** | LLM ko Bedrock se attach karne ka adapter — recent, LLM struggle |
| **LLM code ROI** | Boilerplate = huge win; novel/complex agentic = often slower with AI |

---

## 💼 Backend Dev Ke Liye Note

Yeh lecture ek backend dev ke liye **AI-assisted coding ka realistic mental model** deta hai. Tum jante ho FastAPI CRUD routes likhna mechanical hai — Claude is "high-example-density" zone mein super-fast hai, toh boilerplate (CRUD, Pydantic schemas, DB session plumbing, Next.js client pages) generate karne do. Par jahan tum **novel infra glue** likh rahe ho (e.g., LiteLLM→Bedrock adapter, SQS-triggered Lambda agents, structured-output tool calling on a brand-new SDK), wahan LLM training-data scarcity ki wajah se hallucinate/over-engineer karega — yahan **tum drive karo, AI assist kare**. Practical rule: AI ko **well-trodden patterns** do, aur **bleeding-edge integration** par khud architecture control rakho. Yeh hi "60% time saved overall, but net-negative on the hard 10%" wala tradeoff hai.

---

## ✅ Takeaway

- Alex ka **frontend + backend + API layer** full-stack, locally chal raha hai — Clerk auth, dashboard, accounts, advisor team sab Claude Code generated.
- **LLMs boilerplate frontend/backend par excel karte hain** (training data mein tons of examples), **naye/complex agentic code par struggle** karte hain (kam examples).
- Claude ka net ROI: agentic part par **slower** (1 week → 2 weeks), frontend par **massive win** (2 weeks → 1.5 din); overall **~60% time**.
- Apni energy **agentic/LLM hard stuff** par lagao; dashboards/CRUD AI ko de do.
- Yeh Week 1 (Clerk auth, pages router) + Week 2 (deployment) ka **convergence** hai — agla step production deploy.

---

<details>
<summary>📜 Full Transcript (English)</summary>

Okay. Are you excited? Here we go. Command. Click here. And. Whoa! Up immediately comes this landing page. Alex, AI financial advisor. Uh, your AI powered financial future. And again, I'm maybe refine this a bit. I tweaked this a bit, but almost all of this, including the copy, including, uh, all of this was just written by Claude code just up front. And it's a great landing page with these three things here with meet your AI advisory team, a nice little hover effect there with some some highlighting. Uh, start your analysis. A fake watch demo button that does nothing, which is for future, uh, and we're going to be able this is this is all going to be hooked up to Clark. And we'll see whether it just works locally. Can I press the sign in button and sign in, using the same credentials that we did for the SaaS app all the way back in week one? Let's give it a shot. I press sign in, I go to Google, I'm going to choose my Google account. I don't need to. It already knows it. And bam! We come in to a dashboard and. Goodness gracious. Let me let this sink in for you for for for a minute. What you're looking at here, this this is a new empty user because I'm logging in for the first time. You're seeing here the the dashboard screen. There's a disclaimer that I did ask it to add in here to say don't. This is not official financial advice. There's this dashboard has a portfolio value a number of accounts asset allocation and last analysis. Uh and we can we've got we've got various settings here. So I can say my my name is Donna and then I can press save settings. Settings. Save successfully. A little toast message up at the top. And that is now my name I can make the target retirement income. What do I want? Annual income of 80,000 would be great. That would be nice. See that? Lovely formatting. That was another little, little thing I added to it to ask it to have locale formatting. Uh, so if you're in Europe, you may see the 80 .000 and then save settings and then check this out. Look at this. If I want to change the North American distribution, I want 80% of my portfolio to be North American exposure. As I drag it, look at how the other one automatically drags down. And I'll put that to 80%. And look at how that pie chart animates in. It's gorgeous. I didn't do any of that. I didn't tell it to do any of this all first time. This is a beautiful, professional, polished website. I gotta tell you, it's amazing. Uh, and there comes the toast, and it all looks great. So this this is the the landing page and the dashboard page of our Next.js app, and it's all hooked up to the API. It's saving in the database. When we make these changes. These are all getting persisted in our database by calling that fast API route. Uh, it's all and which is calling localhost 8000. So it's all running locally on my computer and it will be on your computer, but it's all working front to back which is super impressive. And now if I move over to accounts, you'll see that we've got some some details here. There's no accounts found. It looks it looks quite, quite clean and empty. But I've got this little populate test data button again. This is something I asked it to add afterwards. So it didn't do this initially. I had to give this some some spec, but then it did it and I pressed that button. It says populating test data populated successfully and bam! Everything appears just like that. We suddenly have a test portfolio with some cash in there and some portfolios in here too. With some positions. There's three accounts, a brokerage account, a Roth IRA, and a 401 K long term. And if you don't know what any of that means, I don't. I'm not surprised, nor did I, until I moved to the US. These are all US retirement words that everyone says over here that I've never heard of when I came here, 401 K being the name of their tax deferred long term savings plan, and a Roth IRA being a similar kind of investment account that you can have yourself if your employer doesn't. So these are different kinds of retirement accounts. You should set this up to, to reflect your location so that it makes sense to you. But this is showing these three accounts. And there's there's like an edit button here. What do you think. What do you think this will do anything. What happens if I press the edit button. Let's find out I press the edit button loading account details. And here is this 401 K account. It's got some, uh, BND is total market bond positions. I don't know what IWM is, but I'm sure someone does. QQ. Is the Nasdaq right? I think Spy is S&P and VCI is the Vanguard Total Index. So this is a nice portfolio that's been set up. These values will have been coming from polygon. So our server will have been will have been uh calculating the actual values of these. So they should be real. Uh and we can come in, we can edit them, we can remove them, we can add a position if we want. Let's add a position in IBM. You see, it's got like a typeahead there, but it doesn't have IBM. If the system is not in our database, it will be added automatically. We'll put in ten IBM shares and in they come. And for the time being it shows price na uh, and uh, then we can go on to the advisor team. This is where we see a team of specialist agents that will work together to provide comprehensive analysis. Look at this. Uh, there's no analysis. Please press this to start your first analysis. And we won't do that because this is all deployed locally. It can't actually run at the agents. All we're doing here is looking at our next JS front end, and it's attached to our, uh, our API layer on the back end. And so that those, those are the pieces that are in place right now. Uh, and I gotta tell you, I think it's, uh, it's sensational and particularly how, how easy it was to build this. But not only was it so easy to to to build it with, with, with Claude, which is, of course, not the main point of this course. The main point is that we've deployed it in a way running locally. That is a full stack application done properly with a front end and a back end and an API layer, and it's all holding together. And as a side note, it is perhaps important to observe that that the AI generated code was good not just for front end, but for front end and back end, where the back end was that simple boilerplate API calls to a database. And so you might wonder, okay, so why is it that llms are so good at generating that code for that kind of that part of our production app? But it wasn't good at building the agentic part that the the agents running on Lamda services. And the answer is that the, the front end and the back end that it's generated is reasonably standard boilerplate stuff that's similar in many production applications. And it's the kind of thing that that Llms excel at generating, because there's tons of examples in their training data. They know how to apply color schemes, they know how to build these different frameworks. And a lot of what makes Front End difficult is just a lot of stuff, a lot of scaffolding to put in place. And that's stuff that llms find really easy. And the boilerplate backend and API routes it also finds really easy. When it came to the Agentic stuff, we were we were definitely working in new territory. We were dealing with with all sorts of stuff around tools and structured outputs. We were using OpenAI agents SDK, which has only come out this year, in the last few months, and we were using it with the light LLM attachment to Amazon bedrock. And that's only been out for like like a month or two. So there's very little example in its training data. And just giving it one example, which I gave it in, in its sort of prep materials, wasn't enough for it to generalize easily. And there was too much using things like OpenAI OSS model. It found that really difficult. It didn't know anything about it. It didn't know it existed. When we started to get rate limit errors, it got stuck. It overengineered things. It made, as I say, a real meal over the tool calling a total mess. Uh, and it's because this, this is, this is much more complex. It's not boilerplate. It's new. So it doesn't have as many examples in its training data. And it's the kind of areas where llms struggle. So the LLM side of this was something that we had to I had to put a lot of work into and build myself. In fact, I would say that that was one example where I think if I were doing it on my own, that would have taken me about a week of coding. Doing it with Claude code actually subtracted value. It took me about two weeks because it did a lot of damage, and it took a long time to debug and figure out what on earth was going on. So it actually took me longer. But building what you're seeing here, the front end and API, that took about a day and a half. That's it for all of it to be there. Running, working, looking great a day and a half. And I tell you, if I had built this myself, I could have done it. I know how to code front end. I could have done it. But to get it looking like this would have been at least two weeks, maybe more. Uh, it would have. It would have been a long time. And so if you do all of the maths end to end, whilst Claude code was a lot worse than the server in aggregate, I managed to save about about, uh, I guess it was about it took about 60% of the time that it would have taken if I hadn't been using Claude code. And I think that's a really sensible, uh, kind of benchmark to keep in mind, at least based on, on this experience, but always understanding that there are some things that it's really good at using llms and some things where it will struggle. You should spend your time focusing on the the agentic stuff, the LLM work. That's the really hard stuff, and building out this kind of of dashboard and the back end routes, that stuff that Llms, uh, have have a field day with it's it's easy for them.

</details>
