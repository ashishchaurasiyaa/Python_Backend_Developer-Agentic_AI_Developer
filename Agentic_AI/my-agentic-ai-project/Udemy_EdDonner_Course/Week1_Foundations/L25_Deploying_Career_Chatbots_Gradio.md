# L25 — Day 5: Deploying Career Conversation Chatbots to Gradio

> **Week 1 — Foundations** · ⏱️ ~9m · 🎥 Lecture 25 of 131
> **Instructor:** Ed Donner · **Lecture ID:** 49771335

---

## 🎯 Ek Line Mein (TL;DR)

Sirf ek command — **`gradio deploy`** — se career conversation chatbot ko **HuggingFace Spaces** par live deploy karte hain (free CPU-basic hardware + secrets ke saath), aur fir Week 1 ke end exercises milte hain: **RAG**, extra **tools**, **evaluator** wapas lana, aur **streaming** add karna.

---

## 📝 Hinglish Explanation (Detailed)

- **Setup:** Ed Cursor ke terminal mein hai, `agents/foundations` directory ke andar — wahi directory jisme **`app.py`** (humara Gradio app) rakha hai. Deployment ke liye bas do words type karne hain: **`gradio deploy`**.

- **`gradio deploy` ka interactive flow** — CLI step-by-step prompts puchta hai:
  - **Title for the app** → "Career Conversations" (Ed ne "Career Conversations 2" rakha kyunki uske paas pehle se ek hai). Ye naam se HuggingFace par ek naya **Spaces repo** create hota hai.
  - **Gradio app file** → default `app.py` hai, bas Enter dabao accept karne ke liye.
  - **Spaces hardware** → **`cpu-basic`** choose karo — ye **free** tier hai, koi payment nahi lagti.
  - **Spaces secrets** → yahan teen secrets daalne hain (env vars jaise):
    1. **`OPENAI_API_KEY`** — naam exactly sahi type karna zaroori hai (galat ho jaye to baad mein edit kar sakte ho, but better to get it right). Ed ne demo mein fake key daali taaki real key leak na ho.
    2. **`PUSHOVER_USER`**
    3. **`PUSHOVER_TOKEN`**
  - Secrets khatam karne ke liye **blank enter** press karo.
  - **GitHub Action for auto-update?** → **No** (default).

- **Deploy ho gaya:** Command run hoti hai aur space ek **URL** par available ho jata hai — `huggingface.co/spaces/<user-id>/career-conversation` jaisa. Pehli baar **build** hone mein ek minute lagta hai.

- **Live demo (deployed chatbot ke saath):**
  - "Hi there" → bot reply karta hai.
  - "Do you have a patent?" → "Yes, I hold a patent" (LinkedIn profile context se answer).
  - User apna **email address share** karta hai → **`record_user_details` tool** trigger hota hai → Ed ke phone par **Pushover push notification** aa jaati hai. Matlab deployed app mein bhi **tool calling end-to-end** kaam kar raha hai.

- **Website embedding:** HuggingFace Spaces ka ek aur fayda — aap apne space ko **apni website mein embed** kar sakte ho (iframe-style). Ed ke website par kai Spaces embedded hain (jaise ek Connect Four game jo alag-alag **LLMs** ke against khela ja sakta hai) — lagta hai jaise uski apni site se serve ho raha hai. Instructions HuggingFace Spaces site par hain. Is tarah aapki website par log aapke **career avatar** se baat kar sakte hain — unknown question aaye to aapko push notification, email mile to woh bhi notify.

- **Week 1 ke real end-of-week exercises (seriously lena hai):**
  1. **Build & deploy it yourself** — ye "future of resumes" hai: ek interface jisse log aapke baare mein chat kar sakein.
  2. **Resources improve karo** — abhi sirf vanilla LinkedIn profile hai. Apne background ki detail, typical career questions ke ready answers — ek **robust knowledge base** banao.
  3. **RAG implement karo** — agar RAG aata hai (Ed ke LLM Engineering course se), to **Chroma data store** daal kar multiple documents se relevant context retrieve karwa sakte ho.
  4. **More tools add karo** — e.g. ek tool jo **SQL query** kare: ek database mein prior answered questions dekhe, aur unanswered questions add kare. Flow: LLM question DB mein daale → aapko push notification → aap answer add karo → bot baad mein user ko answer de. Kaafi interactive system ban jata hai.
  5. **Evaluator wapas lao** — pichle lab mein humne **evaluator** banaya tha, but is lab mein Ed ne use skip kiya (ek lab ke liye bahut zyada ho jata). Ab use add karo taaki har response **professional aur crisp** rahe.
  6. **UI polish + streaming** — Gradio app ko prettier banao (ChatGPT se Gradio tips le sakte ho), aur agar **streaming** aati hai to responses stream back karo.

- **Commercial implications (Ed ka favourite wrap-up):**
  - Ye app already **commercially useful** hai — clients (aur shayad future bosses) attract karne ke liye.
  - Yahi thinking **kisi bhi business AI assistant** par apply hoti hai — agentic AI ka sabse common commercial use case.
  - **Tools** hi woh cheez hai jo ek vanilla website chatbot ko **commercially valuable** product banati hai — jo sirf ticket prices na bataye, balki actually jaa kar **tickets book** kar de.
  - Ye leveling-up aata hai: **tools + structured outputs + prompt mein richer resources**. Apne day job mein dekho kahan aisa **tool-enabled AI assistant** fit ho sakta hai.

---

## 🔑 Key Concepts / Important Terms

| Term | Simple Hinglish Meaning |
|------|--------------------------|
| **`gradio deploy`** | Ek CLI command jo current directory ke Gradio app ko HuggingFace Spaces par deploy kar deti hai |
| **HuggingFace Spaces** | HuggingFace ka free app-hosting platform — Gradio/Streamlit apps ke liye managed hosting |
| **`cpu-basic`** | Spaces ka free hardware tier — is chatbot ke liye kaafi hai (LLM calls to API se hoti hain) |
| **Spaces Secrets** | Deployed app ke env vars — `OPENAI_API_KEY`, `PUSHOVER_USER`, `PUSHOVER_TOKEN` yahan securely store hote hain |
| **Embedding a Space** | Apne HuggingFace Space ko apni personal website mein iframe ki tarah lagana |
| **RAG (Retrieval Augmented Generation)** | Documents se relevant context retrieve karke prompt mein dena — knowledge base ko scale karne ka tareeka |
| **Chroma** | Ek vector data store jo RAG ke liye use hota hai |
| **Evaluator pattern** | Ek dusra LLM jo responses ki quality check karta hai (pichle lab wala — exercise mein wapas lana hai) |
| **Tool-enabled assistant** | Chatbot jo real world se interact kar sake (notify, book, query DB) — yahi commercial value ka difference hai |

---

## 💡 Backend Dev Ke Liye Note (aapke liye)

- **`gradio deploy` = Heroku-style PaaS deploy:** Socho `git push heroku main` ya `flyctl deploy` jaisa — CLI ek remote repo (Space) banata hai, code push karta hai, build pipeline chalti hai, aur app ek managed URL par live ho jaati hai. Secrets ka flow bhi wahi 12-factor pattern hai: **env vars as secrets**, code mein `os.getenv()` se read — aapka local `.env` deploy nahi hota, isliye Spaces secrets mein same names exactly match karna critical hai.
- **`cpu-basic` kaafi kyun hai:** App khud sirf ek thin HTTP/WebSocket layer hai — saara heavy lifting OpenAI API par offload hai. Ye wahi pattern hai jaise aapki FastAPI service jo downstream API call karti hai — compute API provider ke paas hai, aapko bas I/O-bound server chahiye.
- **Exercise wala SQL-tool idea** dhyan se dekho — ye ek classic **async work queue / human-in-the-loop** pattern hai: unanswered question DB mein insert → notification (event) → human answer write → bot future requests serve kare. Aap ise Celery/outbox-pattern ki nazar se design kar sakte ho.
- **Hands-on lab:** is lecture ka code khud chalane ke liye ye lab run karo — `Practical/lab4_career_agent.py` (runnable with `uv run`, Groq-free).

---

## 🧠 Takeaway (yaad rakho)

1. **`gradio deploy`** ek hi command mein app ko HuggingFace Spaces par live kar deti hai — title, `app.py`, `cpu-basic` (free), aur 3 secrets (`OPENAI_API_KEY`, `PUSHOVER_USER`, `PUSHOVER_TOKEN`).
2. Secrets ke **naam exactly sahi** type karo — deployed app inhe env vars ki tarah read karta hai.
3. Deployed Space ko apni **website mein embed** kar sakte ho — "future of resumes": log aapke avatar se chat karein, aapko push notifications milein.
4. End-of-week exercises: **better knowledge base → RAG (Chroma) → more tools (SQL Q&A DB) → evaluator wapas → streaming + UI polish**.
5. **Tools + structured outputs + rich resources** = vanilla chatbot se commercially valuable AI assistant ka difference — yahi agentic AI ka sabse common business use case hai.

---

<details>
<summary>📜 Full English Transcript (original, click to expand)</summary>

Okay, so here I am within Cursor, in the terminal in Cursor. It's a bit confusing. You can see that's this bottom half of the screen. And I'm in — I was originally in the agents directory and I went into the foundations subdirectory. So that's where I am right now. And this is of course the same directory that has app.py. And now I type these two words: gradio deploy. That's it. So when I run that, it's going to create a new Spaces repo for me. And now we need to give it a title for the app. And we're going to call it Career Conversation. But I'm going to call it Career Conversations 2 because I already have a number one. Enter Gradio app file — well, it's app.py that is our Gradio app file, so we can just press enter to accept it as it is. Enter Spaces hardware — so we want cpu-basic. That is the simple, cheap, free — not cheap, it's free — version of Gradio Spaces. You will not have to pay for this.

Any Spaces secrets? And now we have to say yes, there are Spaces secrets. Enter the secret name — so we have to type OPENAI_API_KEY and we have to get this right. If you get it wrong, there is a way to edit it later, but try and not get it wrong. And now we have to enter the actual value, the OpenAI API key. And I'm of course not going to enter my API key right now, otherwise all of you guys will see it right away. But I'll put in a fake key — we'll do SK-dash — and enter a secret name. There are two more secrets that we need to add. Do you know what they are? They are, of course, the PUSHOVER_USER and whatever that is, and the PUSHOVER_TOKEN and whatever that is. And that is it. And it says enter blank to end, so I just press enter and that's it. Create a GitHub Action to automatically update the space? And the answer is no, so I can just press enter to say no. And that is now running and it's done. The space is available at that URL, just like that.

So I should now be able to click on that and launch it and see my space in action. Open — and here it is. It's still building, so it takes a minute to build. But luckily my old one is still running over here, so I'm just going to flip over to that. You can see this is the address: Hugging Face Spaces, my user ID, and then career-conversation. And I can say "hi there", and it's thinking about that, and it says "hello, how can I help you?" I'm going to make sure my phone is on noisy so that we can experience this. "Do you have a patent?" "Yes, I hold a patent." "I'd love to hear more about the patent. Can I get in touch?" "Absolutely, share your email address." "I'm ed at edwarddonner.com." Ha, ha — you like that? So there we go. And it's come through very nicely. And I'm happy to say that I've been alerted about my own email address. So hopefully that is clear for you. You now see that. Hang on — if I take this off, hopefully the other one has now deployed as well. Career Conversations 2 — it's right there. There it is as well. So I now have two career conversations.

So this is how you can interact with a deployed app. And also, Hugging Face gives you a great way that you can just embed this in your own website. So I have a number of Hugging Face Spaces that run on my website — like I've got this Connect Four game that you can play against different LLMs, and this is just a Hugging Face Space. But if you look, it looks like it's just coming from my own personal website. You can do the same thing. The instructions are on the Hugging Face Spaces site. And that way you can have your web page having embedded within it your career conversation, where people can come to your website, they can have a virtual conversation with your avatar about your career, about your interests. If they say something that it doesn't know how to answer, it's going to send you a push notification with the question so that you know it right away. And if they're willing to give their email address, then it's going to notify you with their email address so that you can get in touch. So that is a deployed app that you have running and that you can interact with, and use it as your own personal career avatar.

So I know this was a lot to take in, but I hope that you found it very satisfying — a real application that you can put to good use. There's more information here about how you do that deployment, with the instructions, and now the exercises for you. And this is the real end of week one — exercises that you need to take seriously, because these are important. First and foremost, of course, to state the obvious, you should build this yourself. It's a valuable tool, it's really cool, you should deploy it. It is the future of resumes — an interface you can chat with about yourself.

And next, of course, you should improve the resources that are supplied to the chatbot. This is very vanilla — just a LinkedIn profile. You can add much more detail about your background, you can add in lots of important stuff, and you could give answers to all of the typical career-y kinds of questions, so you can make sure that you've got a really robust knowledge base of data there. If you know how RAG works, you could implement RAG — you could put in a Chroma data store. If you've done my LLM Engineering course, then you know this stuff super well. You could build that in there, and you could have it doing something that has like a bunch of different documents that it's able to refer to in giving good answers with relevant context.

And then you should add in more tools. You could have a tool that can make a SQL query to a database to look at prior questions that can be answered, and a database where it could add in questions that require an answer. So you could have something that's quite interactive, where the LLM is able to add questions to a database, and it can text you — and then it'll send you a push notification, and then you can come in and add the answers, and it will then provide the answers later to the user. So you could add all of that stuff, which would be really interesting.

And then the final exercise for you, of course, is that you may have noticed that whilst in the last lab we built an evaluator, I didn't actually include the evaluator here, because it just felt like that was too much for one lab. But you should now bring that back. Let's have the evaluator in there to make sure that all of the responses that people give are very professional and crisp and do well. So these are all good exercises for you to get involved in. And there's also plenty of user interface stuff you could do to make this nicer. You can make that Gradio app look prettier, for sure — you could just ask ChatGPT to give you some advice on Gradio apps. And if you know how to stream back results — again, if you've taken the other course — then you should add that in, of course, too.

And to wrap this up, I just want to talk about the commercial implications — I always do want to bring it back to that. I mean, the obvious point here is that this is commercially already useful, because you can use it for yourself to attract clients and perhaps even future bosses. But also, you can extend this kind of thinking to any business situation where you are building AI assistants, which is one of the very most common use cases commercially for agentic AI. This ability for it to interact with the real world through tools is what really sets something apart from being just a vanilla chatbot on a website, to being something that is actually commercially valuable. It could be something which doesn't just tell you about ticket prices to travel somewhere, but it can then actually go and interact and book the tickets. That's the kind of leveling up that you get with the use of tools and using structured outputs and providing more resources in the prompt. So this is really the bigger commercial opportunity. Look for ways that you can have this kind of tool-enabled AI assistant, and see how that could be applied in your day job.

</details>

---
*Source: Official Udemy lecture transcript (auto-captions, lightly cleaned). Notes in Hinglish for self-study.*
