# L18 — Day 4: Build a Web Chatbot That Acts Like You — Gradio & OpenAI

> **Week 1 — Foundations** · ⏱️ ~10m · 🎥 Lecture 18 of 131
> **Instructor:** Ed Donner · **Lecture ID:** 49771193

---

## 🎯 Ek Line Mein (TL;DR)

Is lecture mein hum ek **web chatbot** banate hain jo **aapke jaisa behave karta hai** — apna **LinkedIn PDF** + **summary.txt** ko ek **system prompt** mein daal kar LLM ko "aap" banaya jata hai, aur **Gradio** se chand lines mein ek chat UI launch kar dete hain. Ye ek **professional avatar / alter ego** hai jo aapke career ke sawaalon ka jawab deta hai.

---

## 📝 Hinglish Explanation (Detailed)

- **Setup — `me` directory:** Cursor mein wapas, Week 1 ke **Lab 3 (Day 4)** mein. Foundations folder ke andar ek **`me/` directory** hai jisme do files hain:
  - **`linkedin.pdf`** — Ed ke LinkedIn profile ka PDF export. LinkedIn pe jaake **"..." (ellipsis) menu → download profile as PDF** se milta hai.
  - **`summary.txt`** — bas do sentences Ed ke baare mein.
  - **Aapka TODO:** in dono files ko **apni** files se replace karo — apna LinkedIn PDF (ya resume PDF), aur summary mein apne baare mein kuch likho, ek **fun fact** bhi daalo. Ed assure karta hai — ye data **aapke control ke bina kahin nahi jayega**.

- **Abhi tools nahi:** Hum **tools** ki baat kar chuke hain, lekin actual tool-use **kal (Day 5)** aayega. Aaj sirf **groundwork** lay kar rahe hain.

- **Imports — teen key packages:**
  - **`openai`** — already familiar.
  - **`pypdf2`** — PDF files **parse** karne ki popular library. (PDF se raw text nikalna.)
  - **`gradio`** — Ed ka favourite. Wo khud ko "horrible front end engineer" bolta hai, lekin Gradio se **data science UIs** bahut aasani se ban jate hain — beautiful front ends, minimal code.
  - **Tip:** kisi bhi library ke liye "quick guide" chahiye toh **ChatGPT/Claude se poochh lo**; packages ka actual home **PyPI** (Python Package Index) hai — wahan search karke GitHub repos vagaira dekh sakte ho.
  - Side note: imports mein ~14 seconds lage kyunki Gradio bahut kuch load karta hai. **Virtual environment** top-right mein set hona chahiye (Cursor kernel selection).

- **PDF se text nikalna:**
  - `load_dotenv()` + **OpenAI client** initialize karo.
  - **`PdfReader`** banao, LinkedIn PDF pe point karo, har **page** pe `extract_text()` call karke sab text ek `linkedin` variable mein jod do. Bas — itna simple.
  - `print(linkedin)` karke verify karo ki text sahi nikla (output truncate hota hai notebook mein).
  - Phir **`summary.txt`** load karo (PC users ke liye encoding ka dhyan — guide mein covered, e.g. `encoding="utf-8"`).
  - Ek **`name`** variable set karo — apna naam daalo.

- **System prompt vs User prompt — naya concept:**
  - Ab tak hum sirf ek **user prompt** bhejte the. Lekin actually **do alag prompts** specify kar sakte ho:
    - **System prompt** = overall **instructions** — task ka context, response ka **format**, aur **tone** set karta hai.
    - **User prompt** = user ka actual sawal.
  - Ye **separation of concerns** yahan bahut kaam aata hai.

- **System prompt ka content (persona engineering):**
  - "**You are acting as {name}**" — LLM ko bola jata hai ki wo aap ho.
  - "You're answering questions on that person's **website**, particularly questions related to their **career, background, skills and experience**."
  - "Represent {name} for interactions on the website **as faithfully as possible**."
  - **Tone setting:** "Be **professional and engaging**" — system prompt mein tone set karna best practice hai.
  - **Hallucination guard:** "**If you don't know the answer, say so**" — ye bahut achha prompting context hai.
  - Phir **summary** aur **LinkedIn profile** ka pura text system prompt mein **inject** kiya jata hai, **markdown-style headings/tags** ke saath structure dene ke liye.
  - End: "With this context, please chat with the user, **always staying in character** as {name}."
  - `print(system_prompt)` karke check karo — Ed bolta hai **print statements daal kar har step verify karo**, comfortable raho.

- **Gradio ka working model — callback function:**
  - Gradio ke saath kaam karne ka pattern: ek **callback function** likho jo Gradio tab call karega jab user kuch type kare.
  - Function signature: **`chat(message, history)`** —
    - `message` = user ka abhi ka naya message,
    - `history` = saare prior messages, **OpenAI format** mein hi (list of role/content dicts).
  - Function ke andar:
    1. **OpenAI-style list of dicts** banao: pehle `{"role": "system", "content": system_prompt}`,
    2. phir Gradio se aayi **history** append karo,
    3. phir abhi ka user **message** daal do,
    4. **`openai.chat.completions.create(model="gpt-4o-mini", messages=...)`** call karo,
    5. **`response.choices[0].message.content`** return karo — yahi chat mein next reply ban jata hai.

- **UI launch — 2 lines:**
  - **`gr.ChatInterface(chat).launch()`** — bas. Function pass karo (callback), `.launch()` bolo, aur browser mein **chat UI** ready.

- **Demo — chatbot Ed ban gaya:**
  - "Hi there" → "Hello, welcome to my website. How can I assist you?"
  - "**What is your greatest accomplishment?**" → bot ne **Nebula co-found karna** bataya (generative AI + proprietary LLMs se talent sourcing transform karna) — bilkul legit, **true** answer.
  - "**What is a challenge you encountered and needed to overcome?**" (tough interview-style sawal) → bot ne **JP Morgan se apni company start karne ke transition** ki challenge batayi — LinkedIn mein shayad implied tha, lekin **spot on** answer.
  - **Result:** chand minutes mein humne ek chat interface banaya, usse personal resources se **arm** kiya, aur ab wo **professional avatar / alter ego** ki tarah career questions ke jawab de sakta hai.

---

## 🔑 Key Concepts / Important Terms

| Term | Simple Hinglish Meaning |
|------|--------------------------|
| **Gradio** | Python library jo minimal code mein web UI (especially chat/data-science interfaces) bana deti hai — `gr.ChatInterface(fn).launch()` |
| **System Prompt** | LLM ke liye overall instructions — context, persona, tone, format set karta hai; conversation bhar constant rehta hai |
| **User Prompt** | User ka actual sawal/message — har turn pe naya |
| **PyPDF2** | Popular library PDF parse karne ke liye — `PdfReader` se pages ka text extract karo |
| **PyPI** | Python Package Index — open-source Python packages ka official home |
| **Callback function** | Wo function jo Gradio user-input aane par call karta hai — `chat(message, history)` pattern |
| **`history`** | Gradio se mila prior messages ka list, OpenAI ke role/content format mein |
| **Persona / Professional Avatar** | LLM ko system prompt + personal data dekar "aap" ki tarah act karwana |
| **"If you don't know, say so"** | Hallucination kam karne ka simple prompting trick — system prompt mein explicitly likho |
| **Context stuffing** | LinkedIn PDF + summary ka pura text seedha system prompt mein daal dena (RAG ka sabse basic precursor) |

---

## 💡 Backend Dev Ke Liye Note (aapke liye)

- **Gradio = FastAPI + frontend, ek line mein.** `gr.ChatInterface(chat).launch()` internally ek web server (FastAPI/Starlette based) spin karta hai aur aapka function ek **request handler/callback** ban jata hai — bilkul route handler jaisa, bas routing/HTML Gradio handle karta hai. State (chat history) **client-side se har request pe wapas aati hai** — yani handler **stateless** hai, same as a well-designed REST endpoint.
- **System prompt injection = config/context layer.** LinkedIn + summary ko system prompt mein stuff karna sabse naive form hai of "grounding" — production mein yahi cheez **RAG** (retrieval + context window management) ban jati hai jab data context limit se bada ho. Abhi ke liye: prompt is just a string template — f-strings se build hota hai, Jinja template render karne jaisa.
- **`messages` list = append-only event log.** Har turn pe `[system] + history + [new user msg]` rebuild hota hai aur **pura** API ko jata hai — LLM API stateless hai, "session" aapko khud reconstruct karni hai. Ye pattern aapke event-sourcing/replay mental model se exactly match karta hai.
- **Hands-on lab:** is lecture ka code khud chalane ke liye ye lab run karo — `Practical/lab3_gradio_chatbot.py` (runnable with `uv run`, Groq-free).

---

## 🧠 Takeaway (yaad rakho)

1. **System prompt** = instructions/persona/tone (constant), **user prompt** = actual question (per turn) — separation of concerns.
2. Personal data (LinkedIn PDF + summary) ko system prompt mein inject karke LLM ko **apna avatar** banaya ja sakta hai — "always stay in character as {name}".
3. **"If you don't know the answer, say so"** — ye ek line hallucinations ko significantly kam karti hai; hamesha daalo.
4. **Gradio** ka pattern: `chat(message, history)` callback likho → `gr.ChatInterface(chat).launch()` → full chat UI ready; history OpenAI format mein hi aati hai.
5. Tools abhi nahi — ye **Day 5 ka groundwork** hai; aaj sirf persona + UI, kal isme tool-calling judega.

---

<details>
<summary>📜 Full English Transcript (original, click to expand)</summary>

And here we are back in Cursor and I've collapsed all the folders. But I'll go back into the foundations folder and to lab three. Lab three for week one, day four, which is where we are. So this is where things get interesting. So I have a directory called "me" within foundations, and within "me" I've put some files. One of them is called LinkedIn. And LinkedIn is — I see it's not, I don't think I can open it in here. I imagine this doesn't like being a PDF. Nope. So you will have to take my word for it. What this is, is a PDF version of my LinkedIn profile. And you can just get that from within LinkedIn. You can go into LinkedIn and click on one of the dot dot dot ellipsis menus and download your profile as a PDF. And that's what I did. And I've put it right here as LinkedIn PDF. And I've also got a summary text which is just called summary.txt. And it's just two sentences about me. And those two things are in "me".

And the to-do for you as you do this lab is to replace these documents with something about you. The LinkedIn should be your LinkedIn PDF profile or a PDF of your resume or anything like that. The summary — put some stuff about you and include some extra, some fun stuff. A fun fact about you, something that you would like people to know about you, and all will become clear. Don't worry, it's not going to go anywhere without your control. But this will hopefully become clear very soon.

All right. So if we go back to the lab. So as I said, we're not going to actually use tools just yet, even though we've been talking about them. Tools is going to come tomorrow. We're going to lay the groundwork. Okay. So I'm now going to import a few packages — OpenAI, you know well, but PyPDF2 and Gradio you might not know. Gradio, prior students of mine will know well, because you know that I am super — I adore Gradio. I am passionate about this platform. I am a horrible front end engineer and Gradio is something that can make beautiful front ends, even for someone terrible like me. It's really great. It's a way to build data science user interfaces very easily indeed. We will do that, but I won't cover it in any detail. PyPDF2 is an example of a popular library for parsing PDF files, and if you want to know more about these, you can simply ask ChatGPT to write you a quick guide on them if you ever want to. To get the right kind of popular resource for doing something, you can just ask Claude or ChatGPT if you want. The actual place they come from is called PyPI. And this is the package index. This is where open source Python packages live. And you can go there and search for different packages, look at their GitHub repos and find out more about them that way as well.

All right. But I'm going to import these. And by the way, I already set up here on the top right — I had made sure that my virtual environment was set. It's taking a bit of time there. I guess it's Gradio that needs to load in a bunch of things, and it's done — 14 seconds to do all of those imports. I guess a lot was happening. All right. So now we load our env and we initialize the OpenAI client library.

So look at this. I now simply create a PDF reader and I point it at my LinkedIn PDF. And I read in the pages calling page extract text. And I just bring it all together. And that's as simple as that. So now this LinkedIn variable — let's just print that LinkedIn variable so we can see it. Print LinkedIn, and you'll see a whole bunch of stuff about me, and the output is truncated. So you're only seeing a little bit about me. But there's more than you would need to know right there. But since you're surely already connected with me on LinkedIn, you know all this already. Then, here I am going to load in the summary text about me. This is needed for PC users sometimes — and if you're not from... yeah, I'm sure you are familiar with this, but it's covered in the guide. And then I'll set a variable called name to my name. And you should set that to be your name.

All right. And now, so one thing we didn't talk about before is system prompts and user prompts. And they are fairly commonplace now. So you probably know that we've always been just prompting with a single user prompt up to now. But you can actually specify two different prompts. The system prompt is intended to be more the overall instructions that sets the context for the task at hand, and the format and the way it should be responded to, and then the user prompt is the actual question coming from the user. And in this case, it will be handy for us to separate out these two concerns.

So for the system prompt I'm saying: you are acting as name. So this will be me, and it will be you. You're answering questions on that person's website, particularly questions related to their career, background, skills and experience. Your responsibility is to represent them for interactions on the website as faithfully as possible. You're given a summary of their background and LinkedIn profile, blah blah blah blah blah. Be professional and engaging. So this is about setting the tone, which is a good thing to do in a system prompt. And then "if you don't know the answer, say so" is very good prompting context to give. Okay. So then I'm adding in the summary using that summary variable. And I'm also putting in the LinkedIn profile. And I'm using markdown tags to kind of show this as sort of headings. And then I end with: with this context, please chat with the user, always staying in character as you.

All right. Now the plot thickens. Now you know what — the game I'm playing here, you know what we're doing. Let's run that and let's just print that so we see what the system prompt actually looks like. And here we go. You can see it's just true to form, exactly as we were expecting. And it will have within it, of course, the stuff about me and the LinkedIn PDF contents and so on, and hopefully yours will have yours. And you should put in some print statements to check it. Make sure you're very comfortable with everything happening so far.

So we're about to use Gradio to bring up a user interface that will allow us to chat based on an LLM that's armed with this system prompt. And the way you work with Gradio is you need to write a function which will be like a callback function that Gradio will call back to when it needs to do some processing, when a user has typed something in. And the style of this particular callback function is a style where you write a function called chat, which takes a message that the user is typing in — a message being sent — and the history of all prior messages, which comes in OpenAI's format. And what we need to do is call an LLM and return the response from the LLM to go in the chat.

So I'll let you look through this to convince yourself that what I'm doing is the right thing. But basically I build an OpenAI-style list of dictionaries. I begin with the system prompt — role system, content the system prompt. I add in the history from Gradio, and then I bung in this user's message that's just come in right now. I then call OpenAI dot create for GPT-4o mini with exactly these messages, and I return the response choices zero message content. So this should all be stuff that's fairly familiar to you.

And then using Gradio is beautifully simple. You just call — in this case we want a chat, and so you can call ChatInterface. We tell it the function that we've written so it knows it can call this as the callback. And we ask it to launch. And when I run that, I get an interface like this. And I can say "hi there". "Hello, welcome to my website. How can I assist you?" And so I can say something like, "what is your greatest accomplishment?" And we'll see what it says. "I consider my greatest accomplishment to be the co-founding of Nebula, where we're leveraging generative AI and proprietary LLMs to transform how people source and engage talent." Fantastic. And it's also talking about the company I founded as well. So it's a very legit, very good answer. I think it's probably true, which is always a good thing.

And so very nicely handled. Let's say, "what is a challenge that you encountered and needed to overcome?" It's a hard kind of professional question that you might be asked in an interview. Okay. "One of the significant challenges I faced during my transition from a successful career at JP Morgan to starting my own company..." — and this is all very true. I don't know how it got that from my LinkedIn profile. I guess it must be somewhere or something that's kind of implied within it. But I mean, it happens to be spot on. So this is a very good answer. And so wonderfully, in the space of just a few minutes, we've built a chat interface and we've used resources to arm it with information about me so that it's able to act as me and be like a professional avatar, an alter ego for me in answering questions about my career.

</details>

---
*Source: Official Udemy lecture transcript (auto-captions, lightly cleaned). Notes in Hinglish for self-study.*
