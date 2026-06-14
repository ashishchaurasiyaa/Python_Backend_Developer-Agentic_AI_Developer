# L66 — Day 5: Trading Application Using GPT-4o & Claude

> **Week 3 — CrewAI** · ⏱️ ~9m · 🎥 Lecture 66 of 131
> **Instructor:** Ed Donner · **Lecture ID:** 49821243

---

## 🎯 Ek Line Mein (TL;DR)

Engineering team crew (GPT-4o lead + DeepSeek coder + Claude 3.7) ne ek **YAML typo debugging** session ke baad pura **trading platform** generate kiya — design doc, `accounts.py` module, unit tests, aur ek surprisingly polished **Gradio UI** — sab `crewai run` se, aur Ed ka live raw reaction: "I'm astonished".

---

## 📝 Hinglish Explanation (Detailed)

- **Pichli setup ki fix se shuru:** Ed ne notice kiya ki config me **module name aur class name** missing the — `accounts.py` module aur `Account` class. Ye crew ke task inputs ka part hai jo engineer ko batata hai ki exactly kya naam ke files/classes banane hain.
- **tasks.yaml me bugs:** Sirf wahi nahi — **tasks YAML me stray tabs** the, kuch cheezein properly formatted nahi thi. **YAML indentation-sensitive hota hai**, isliye ye silent killer hai.
- **Debugging ka pain — framework trade-off:** Jab Ed ne run kiya to crash hua, aur error message **bahut obscure tha** — ek lamba stack trace jisse turant samajh nahi aata ki problem kya hai. Ed ko khud carefully dhundhna pada. Uska honest point: **CrewAI jaisa framework sign up karne ki "deal" yahi hai** — out of the box bahut kuch milta hai (memory, code execution, agent orchestration), lekin trade-off ye hai ki **bahut kuch hidden hai**, aur jab cheezein tootti hain to debug karna mushkil hota hai kyunki behind-the-scenes kya ho raha hai wo opaque hai.
- **Run karna:** `engineering_team` directory me jaake **`crewai run`**. Sabse pehle **engineering lead** (GPT-4o) design banata hai.
- **Ollama warning:** Agar aap free service ke liye **Ollama** try kar rahe ho, to ye challenge **Ollama ko max tak stretch karega** — local models ke liye ye bahut hard task hai, limited success milegi. Aise case me Ed ke **`example_output` folder** ke saved results dekhke seekhna better hai. **GPT-4o-mini** se ye fine chalega.
- **Multi-model pipeline chalti hai:** Design ke baad code **Python engineer (DeepSeek)** ke haath me jaata hai — DeepSeek thoda slow hai, pura run **~5 minutes** laga.
- **Output folder ka review:**
  - **Design document** — markdown me, method signatures ke saath. ✅
  - **`accounts.py`** — top pe `get_share_price()` dummy function (Apple, Tesla, Google ke liye seeded prices), `Account` class with deposit/withdraw, docstrings, comments, price × quantity calculations, success/failure ke liye `True`/`False` return. Ed ko ek **"pro move"** bhi dikha: `get_holdings()` ek **copy return karta hai** (mutable internal state expose nahi karta) — Ed bola wo khud bhi ye nahi sochta!
  - **`test_accounts.py`** — proper unit test scaffolding, plenty of assertions. ✅
  - **`app.py`** — frontend, jo Claude 3.7 (frontend dev agent) ne likha.
- **App ko chalana:** `output` folder me jaake **`uv run app.py`** (uv environment me ye `python app.py` ka equivalent hai). Pehle **`No module named gradio`** error aaya → **`uv add gradio`** se dependency add ki → phir app start ho gaya.
- **Raw reaction — UI surprisingly accha:** Gradio UI me **tabs** the — *Account Management*, *Trading*, *Reports* — sections nicely grouped aur organized. Ed: *"This isn't a simple user interface, this is a really good user interface."* GPT-4o-mini se pehle aisa polish nahi mila tha.
- **Live testing:**
  - Account create kiya (`ed`, $10,000 deposit) → holdings empty. ✅
  - 1 Apple share buy → cash balance down, portfolio value still $10,000 (cash + shares), holdings me 1 share @ $150. ✅
  - **Error handling test:** Tesla share sell kiya jo paas nahi tha → *"Insufficient shares to sell"* error. ✅
  - Apple share sell → success, holdings wapas empty, **transaction history** me deposit, buy, sell sab dikha. ✅
- **Conclusion:** Ye koi rehearsed demo nahi tha — Ed ne pehli baar live run kiya aur result expectations se upar nikla. **GPT-4o + Claude 3.7 + DeepSeek ka collaboration** ne ek genuinely impressive full-stack app bana diya. Ed example outputs me mini-version bhi daalega comparison ke liye.

---

## 🔑 Key Concepts / Important Terms

| Term | Simple Hinglish Meaning |
|------|--------------------------|
| **`crewai run`** | Scaffolded crew project ko chalane ka CLI command — pura agent pipeline kick-off karta hai |
| **tasks.yaml stray tabs** | YAML me galat indentation/tabs → obscure stack trace; YAML config ka classic silent failure |
| **Framework trade-off** | CrewAI se bahut kuch free milta hai (memory, code exec, orchestration), lekin internals hidden hone se debugging painful |
| **Multi-model crew** | Alag agents pe alag LLMs — GPT-4o (lead/design), DeepSeek (backend coder), Claude 3.7 (frontend) — sab LiteLLM ke through |
| **`example_output` folder** | Ed ke saved run results — Ollama users ke liye "watch and learn" fallback |
| **`get_share_price()` dummy** | Test ke liye seeded fake price function (AAPL, TSLA, GOOGL) — real market API ki jagah |
| **Holdings copy return** | `get_holdings()` internal dict ka copy return karta hai — mutable state leak nahi hota (defensive copying) |
| **`uv run` / `uv add`** | uv environment me script chalana / dependency add karna — `python` + `pip install` ka uv equivalent |
| **Gradio tabs UI** | Generated frontend me Account Management, Trading, Reports tabs — agent ne khud organize kiya |

---

## 💡 Backend Dev Ke Liye Note (aapke liye)

- **YAML config ka dark side aapne production me dekha hoga** — Kubernetes manifests ya CI pipelines me ek stray tab = cryptic failure. CrewAI me bhi same: `tasks.yaml` ka formatting error ek lamba unhelpful stack trace deta hai. Framework abstraction jitna deep, error surface utna opaque — ye wahi trade-off hai jo aap ORM vs raw SQL me jaante ho.
- **`get_holdings()` ka copy return karna defensive copying hai** — wahi pattern jo aap `@property` me internal `dict`/`list` expose karte waqt use karte ho (`return dict(self._holdings)`). Interesting baat: LLM ne ye khud kiya, bina bole. Generated code ko review karte waqt aise idioms quality ka signal hote hain.
- **Multi-model routing = LiteLLM ka kamaal** — har agent ke `llm` field me alag provider string (`openai/gpt-4o`, `deepseek/...`, `anthropic/claude-3-7...`) aur LiteLLM unified interface handle karta hai. Ye microservices me API gateway pattern jaisa hai: ek interface, multiple backends.
- **Hands-on lab:** is lecture ka code khud chalane ke liye `Practical/lab4_engineering_team.py` run karo (is repo me, `uv run` se chalta hai, Groq pe free via LiteLLM). Hamare labs course se thoda alag hain: self-contained code-style (YAML scaffolding nahi — to ye lecture wala stray-tabs wala dard hi nahi hai), aur Docker code-execution ki jagah generated code ko hum khud compile + unittest karte hain — lecture ka "uv run app.py" wala manual verification step humne lab me programmatic bana diya hai.

---

## 🧠 Takeaway (yaad rakho)

1. **YAML config errors = obscure stack traces** — CrewAI me `tasks.yaml` ke stray tabs ya missing fields cryptic failures dete hain; carefully validate karo.
2. **Framework deal:** out-of-the-box power (memory, code execution, orchestration) ke badle debugging opacity milti hai — ye trade-off consciously accept karo.
3. **Multi-model crews kaam karte hain:** GPT-4o (design) + DeepSeek (backend) + Claude 3.7 (frontend) ne milke ~5 min me full-stack trading app bana di.
4. **Ollama/local models is level ke task pe struggle karenge** — complex multi-file code generation ke liye frontier models chahiye; GPT-4o-mini minimum viable hai.
5. **Generated code ko hamesha run karke verify karo** — Ed ne UI me buy/sell/error-handling sab manually test kiya; eyeballing kaafi nahi hai.

---

<details>
<summary>📜 Full English Transcript (original, click to expand)</summary>

Ah, not so fast, you say. You notice that I'm missing the setting? The module name and the class name, which we also have to do. There we go. Module name is accounts.py and the class name is Account. And actually that wasn't the only mistake also in tasks' YAML. I had some missing. I had some stray tabs going on, that some of these things weren't formatted properly. And I'll tell you, the reason I found that out is because I tried to run this and it failed. The error message I got was quite obscure. It was like some long stack trace and it was not immediately obvious what was wrong. And I think, you know, I had to go through quite carefully and look for problems. And I sort of had a clue about the kind of thing I was looking for. But I can imagine if you're new to using Crew, then that could be quite a painful experience because there's not many clues given to where to go.

And I really think that that is the kind of — that's the deal that you make signing up for a framework like this: you get a lot out of the box, you get a lot of head start. Think of the memory stuff that we did last time and the whole way that this fits together and the code execution stuff. I mean, it's amazing, but what you are trading off is the fact that some stuff is hidden from you. And when things go wrong, it can be harder to debug and figure out what's actually happening behind the scenes.

But anyway, with all of that, it should be time now for us to actually give this a try. So we go into our directory, we go into engineering team and we get ready to run. `crewai run`. Okay, here we go. And it's off. Thinking. Okay, the engineering lead is starting off. The engineering lead, of course, that is GPT-4o, the way I have it set up. You may have picked a different model. You may even be trying with Ollama. Now, I will say that if you are trying it with Ollama, if you're looking for the free service, I do imagine that this will stretch Ollama to the max. This is going to be a very, very hard challenge, and depending on which model you pick underneath Ollama, you may have limited success with this. This may be a case of where you have to watch what I'm doing here, and I'm saving the results in example output folder so that you can have that to hand. And you know, this might give you something to watch and learn from rather than running it yourself. But if you want to try it with GPT-4o mini, that should work just fine.

Anyway, we can see that it's done the design. It's now in the hands of the Python engineer, and I know that this can now take a couple of minutes. In fact, I think last time it took about five minutes to run all the way through. And that wasn't with DeepSeek. And DeepSeek can be a bit slower. So we'll see what happens. I will be right back in a minute.

Okay. It just finished. It's exciting. I guess it did take about five minutes, I think. Let's have a look at what was produced in the output folder. So I guess, well, there's a lot of files there. That's a good start. Let's start with the design document. It is indeed in markdown. It's — let's get rid of this terminal — it's got certainly like a design written out there and it's got like method signatures and things. That seems great. And now the big guy, accounts.py. Okay, so it's got the get share price dummy at the top, which is what we wanted, to return a share price for Apple, Tesla and Google as example to seed it. Okay. Class Account. That's good. And it's got the right kinds of setups: deposit accounts, withdraw accounts, with comments, with docstrings. Okay. That looks good from eyeballing. I'm seeing good looking stuff. Obviously we'd expect to see price times quantity. And then I see they're going to return false or return true depending on whether it was successful or not. That's interesting. Okay. And yeah, this all looks pretty comprehensive, doesn't it? Calculate profit or loss. Get the holdings takes a copy. That's a pro thing to have done. I wouldn't have even thought of that if I was doing it myself. That of course is the right thing to do. Okay. Very nice. This looks very comprehensive. This looks like the code we're looking for.

Let's look at the test accounts. Sure. I mean, these are the kinds of tests you'd expect, plenty of assertions in here. That's great. And that's the right kind of scaffolding around a unit test. And there is an app.py. But we're not going to look at that app.py, because we're going to look at it in a whole different way when I'm back. Let's try this.

Okay. So I've gone into a terminal now as we try out the code written by our engineering team, by our front end developer. We're going to go into the folder called output. Here we are. Now I imagine that we're going to need to install Gradio. I imagine if we just do app.py it's going to have an import failure. Let's try this: `uv run app.py`, which you remember, `uv run` is the equivalent of Python when you're using a uv environment. Let me see. No module named Gradio. Okay, so I have to do `uv add gradio`. And it's now added. And now we try this again: `uv run app.py`. Okay. It's thinking, it's doing its stuff. Thinking, thinking, hasn't crashed. It's loading the various Gradio dependencies right now, I believe. Okay. So it started a Gradio app. This is kind of crazy. Follow the link. Okay. Here we go. Here is a user interface.

Okay. So first of all, the first thing I'll notice — this is, you're getting like a raw reaction video here. I'm like astonished. You can see that it's done a Gradio UI with these tabs: Account Management, Trading and Reports. That's cool. So create an account. I get to give it a user ID, so I guess I'll call it ed. Initial deposit, we'll put that in. I'll press create account. Account created for ed with initial deposit of 10,000. And there we go. Holdings: no holdings. All right. Fine. Now we go over to — I guess I can withdraw and add. That's cool. I'll go to trading. We'll do symbol Apple, quantity one, buy shares. And here we go. Successfully bought one share of Apple at — let's zoom out a bit. There we go. So the user is ed. That's now my cash balance, that's come down. The portfolio value is of course the full amount because I've spent some money but I've bought equivalent Apple shares. That's calculating that right. And there's the holdings: one share at 150 each. That's great.

Let's go over to reports. Portfolio value is 10,000. Profit loss zero. Current holdings. Is there transaction history? Deposit and buy shares. This is great. This is so cool. I can't believe this. This isn't a simple user interface. This is a really good user interface. Look at the way things are organized into groups and are, like, nicely laid out. I'm kind of surprised about this because actually, in the past I've used GPT-4o mini, and it's not looked as good as this. It's worked for sure, but this is a sharp user interface with tabs, with sections organized quite nicely.

And I guess we better — let's try selling a share of Tesla that we don't have. Quantity one, sell shares. Error: insufficient shares to sell. Okay, we get an error message. Now let's try selling an Apple share. Sell share. Successfully sold one share of Apple. And now we have no holdings. And if we go and look at our transactions, hopefully we'll see that we both bought and sold. Transaction history: buy one share of Apple, sell one share of Apple.

Well, I've got to tell you, this is astonishing. There's — this isn't a fake. I haven't run this in advance to see this before. You're getting my raw reaction. And it's definitely surpassing my expectations in terms of this being a nice user interface. Like, if I had built this, I would be quite pleased with it. I'm, frankly, I'm astonished. So that's a great conclusion. I will be sure to make sure I'll put some examples in example outputs. I'll try and put one with mini so you can see a more raw user interface and then something like this. And yeah, it's really amazing to see. So a collaboration between GPT-4o and Claude 3.7 and DeepSeek to build this platform with, frankly, a really impressive user interface. Wow.

</details>

---
*Source: Official Udemy lecture transcript (auto-captions, lightly cleaned). Notes in Hinglish for self-study.*
