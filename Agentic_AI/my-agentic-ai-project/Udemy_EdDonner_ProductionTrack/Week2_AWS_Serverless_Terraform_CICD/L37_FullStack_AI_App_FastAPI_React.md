# L37 — Building Your First Full-Stack AI App with FastAPI and React

> **Week 2 · Day 1** · ⏱️ ~11 min

---

## 🎯 TL;DR

Ab actual code: `me.txt` (personality), ek **FastAPI** server (`server.py`) with `/`, `/health`, `/chat` routes (abhi **no memory**), aur ek **React/Next.js** front-end component (`twin.tsx`) jo `localhost:8000/chat` ko call karta hai. Dono ko run karke browser mein **front-end (3000) + back-end (8000)** ek saath connect karke pehla working full-stack AI app banate hain — par abhi stateless.

---

## 🗣️ Hinglish Explanation

### Step 1: `me.txt` — twin ki personality

Sabse pehle `backend/` mein ek file **`me.txt`** banao — ek chhota description ki tum kaun ho. (Kal isse properly replace karenge, isliye abhi zyada time mat lagao.) Ed Donner ke case mein:

```
My name is Ed Donner and this is my website.
Your goal is to answer questions acting as Ed to the best of your knowledge.
Ed is an AI engineer, a leader and an AI speaker.
Add two or three sentences here describing yourself.
```

Tum apna naam, apni website, aur 2-3 sentences daalo. Ye twin ka **system prompt material** banega.

### Step 4: FastAPI server — `server.py` (no memory yet)

Guide se poora code copy karke `backend/server.py` mein paste karte hain. (Yellow linting squigglies aayengi — kyunki IDE ko abhi environment/packages ka pata nahi; ignore karo, deploy/run par theek ho jaayengi.) Reconstructed server roughly aisa dikhta hai:

```python
import os
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from openai import OpenAI

# 1. Environment variables load karo (.env se: OPENAI_API_KEY, CORS_ORIGINS)
load_dotenv(override=True)

# 2. FastAPI app start karo
app = FastAPI()

# 3. CORS middleware — front-end ko back-end se baat karne do
cors_origins = os.getenv("CORS_ORIGINS", "").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 4. OpenAI client
client = OpenAI()

# 5. Personality load karo (me.txt)
personality = ""
def load_personality():
    global personality
    with open("me.txt", "r", encoding="utf-8") as f:
        personality = f.read()
    return personality

load_personality()

# 6. Pydantic request/response models
class ChatRequest(BaseModel):
    message: str

class ChatResponse(BaseModel):
    response: str

# 7. Routes
@app.get("/api")
def read_root():
    return {"message": "AI Digital Twin"}

@app.get("/health")
def health():
    return {"status": "healthy"}

@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    messages = [
        {"role": "system", "content": personality},
        {"role": "user", "content": request.message},
    ]
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
    )
    reply = response.choices[0].message.content
    return ChatResponse(response=reply)

# 8. Server start (local)
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

Code ka walk-through (jaise Ed batata hai):

1. **`load_dotenv`** — `.env` se environment variables (OpenAI key, CORS origins) load karta hai. (Agar pehle nahi dekha toh Google karo — Ed ke baaki courses mein aaya hai.)
2. **FastAPI server** start hota hai, bilkul pehle jaise.
3. **CORS setup** — yeh wahi "cause business" hai jise Ed abhi skip karta hai par baad mein cover karega. Iska kaam: front-end ko batana ki **all is good**, hamara front-end is back-end se baat kar sakta hai. (Browser security ke liye, server explicitly apne allowed origins declare karta hai.)
4. **OpenAI Python client** banta hai (apna client/provider use karna ho toh replace kar sakte ho).
5. **`load_personality`** — `me.txt` ka content padh ke ek **global variable `personality`** mein daal deta hai.
6. **`ChatRequest` aur `ChatResponse`** — do **Pydantic objects** jo request/response ka shape define karte hain (incoming message, outgoing response).
7. Routes:
   - **`/api`** → simple "AI Digital Twin" return karta hai
   - **`/health`** → `healthy` status return karta hai, taaki monitoring/load-balancer ko pata chale ki sab theek hai (jaise App Runner mein dekha tha)
   - **`/chat`** → message ka response deta hai. Incoming format `ChatRequest` se describe hota hai; `response_model=ChatResponse` se outgoing format. Yahan **koi message history nahi** ho rahi — bas system prompt + user message bhej rahe hain.
8. **Niche `__main__` block** back-end server start karta hai.

> Background — Pydantic: FastAPI request bodies aur responses ke liye Pydantic models use karta hai. Yeh automatic validation + serialization deta hai (galat shape aaya toh 422 error), aur `/docs` par auto Swagger documentation banata hai. `response.choices[0].message.content` — yahi standard OpenAI chat-completions pattern hai LLM ka reply nikaalne ka.

**Save karna mat bhoolo** — white blob = unsaved. Save → `server.py` ban gaya.

### Front-end: `twin.tsx` React component

Ab front-end. Ek component **`twin.tsx`** banega — kaafi verbose code (front-end aksar hota hai). Yeh **`app/` router ke andar nahi** balki ek alag **`components/`** folder mein jaata hai, aur wahan se connect hota hai.

1. `frontend/` mein **New Folder → `components`** banao
2. Uske andar **`twin.tsx`** file banao, guide ka code paste karo

Ed CORS detail skip karta hai par **ek incredibly important line** point out karta hai — jab fetch hota hai, front-end **`localhost` ke port 8000** par `/chat` ko call karta hai:

```typescript
// twin.tsx ke andar — backend ko call karne wali key line
const response = await fetch("http://localhost:8000/chat", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ message: userMessage }),
});
const data = await response.json();
// data.response mein LLM ka reply hai
```

Port **8000** wahi hai jahan humne `uvicorn` se back-end chalaya. Toh front-end **locally connect** karke `/chat` call karega.

**Red squiggly fix — `lucide-react`:** component ke top par ek **red squiggly** dikhta hai `lucide-react` import par. Red squiggly ka matlab: kuch **install karna baaki hai**. Hum ek off-the-shelf React component (`lucide-react` — icons ki library) reuse kar rahe hain, jo abhi installed nahi hai. `npm install` (front-end ka `pip install` equivalent) se theek karo:

```bash
# frontend/ ke andar se
npm install lucide-react
```

Install hote hi red squiggly gayab — sab promising lagne lagta hai.

### App router files complete karna

Ab `app/` ke andar running front-end ke liye files finalize karte hain:

1. **`app/page.tsx`** — yahi serve hota hai jab koi root URL hit kare (modern `index.tsx`). Default file already exist karti hai, toh **overwrite** kar do guide ke version se.

2. **PostCSS config fix** — front-end `postcss.config` mein chhota fix, taaki **latest Tailwind CSS** ka correct/modern approach use ho:

```javascript
// postcss.config.mjs (latest Tailwind ke liye)
const config = {
  plugins: {
    "@tailwindcss/postcss": {},
  },
};
export default config;
```

3. **Global styles replace** — `app/globals.css` ko poora replace karo (select all → paste new) → save.

### Step: Test karo (dono servers chalao)

**Back-end set up + run** (cursor terminal, `frontend/` se `backend/` mein jao):

```bash
# backend/ mein UV project initialize karo
uv init --bare
```

- **`--bare`** flag CRITICAL hai — yeh bina extra unwanted files banaye initialize karta hai. **Bear/bare bhoolne par baad mein problems** aayengi. Yeh `pyproject.toml` banata hai. `python 3.12` matlab Python 3.12 use hoga (na ho toh install kar lega).

```bash
# dependencies add karo (modern pip install -r ka equivalent)
uv add -r requirements.txt
```

- `uv add -r requirements.txt` = `pip install -r requirements.txt` ka modern equivalent. Sab install ho jaata hai — **bahut fast** (Rust ki wajah se).

```bash
# server run karo
uv run uvicorn server:app --reload --host 0.0.0.0 --port 8000
```

App server **off and running**! Guide batati hai ki kya dikhna chahiye, aur wahi dikhta hai.

**Front-end run** (naya terminal — `Ctrl + Shift + ` `` ` ``):

```bash
# frontend/ mein jaake
npm run dev
```

Front-end **first try mein chal jaata hai** (working). Ab `localhost:3000` kholo — drumroll — *"AI in production. Deploy your digital twins. The cloud."* — fancy UI dikhta hai (Ed bolta hai "radio jaisa, bas better").

### Result: stateless full-stack AI app

Test conversation:
- "Hi there" → "Hello, I'm Ed Donner's digital twin. How can I assist you today?" → **OpenAI connect ho gaya!**
- "Hi, my name is Alex" → "Hi Alex, great to meet you!"
- "What's my name?" → "I'm sorry, but I don't have access to that information."

Last reply expected hai — yeh **prove** karta hai ki app set up ho gaya hai, par **memory nahi** hai. Recap:
- Front-end **`localhost:3000`** par serve ho raha hai
- Back-end **`localhost:8000`** par chal raha hai, front-end se call ho raha hai
- Dono apni local machines par chal rahe hain, browser mein aakar combine hote hain
- **Har call ek alag stateless call** hai — conversation hold nahi kar sakta, "that's hopeless"

Agle lecture mein yahi memory fix karenge.

---

## 📋 Key Concepts

| Concept | Matlab |
|---|---|
| **`me.txt`** | Twin ki personality describe karne wali plain-text file (system prompt material) |
| **FastAPI server** | `server.py` — `/api`, `/health`, `/chat` routes; OpenAI ko call karta hai |
| **CORS middleware** | FastAPI middleware jo front-end origin ko back-end se baat karne deta hai |
| **Pydantic models** | `ChatRequest`/`ChatResponse` — request/response ka shape + validation |
| **`/health` route** | Healthy status return karta hai, monitoring/load-balancer ke liye |
| **`twin.tsx`** | React/Next.js front-end component (`components/` mein), `:8000/chat` ko fetch karta hai |
| **`lucide-react`** | Off-the-shelf React icon library; `npm install` se add hoti hai |
| **`npm install`** | Front-end ka `pip install` equivalent |
| **`uv init --bare`** | UV project initialize (extra files nahi banata) — `pyproject.toml` banta hai |
| **`uv add -r requirements.txt`** | `pip install -r requirements.txt` ka modern, fast equivalent |
| **stateless call** | Har request independent — server conversation history yaad nahi rakhta |

---

## 💼 Backend Dev Ke Liye Note

Yeh tumhare comfort zone ka core hai: FastAPI + Pydantic + uvicorn. Notice karne layak production patterns: (1) **`/health` endpoint** — yeh trivial lagta hai par production mein essential hai — load balancers, AWS App Runner, ECS, Lambda health checks isi se decide karte hain ki instance live hai ya replace karna hai. (2) **CORS middleware server-side** configure hota hai (`allow_origins`), browser sirf enforce karta hai — yeh frontend ka problem nahi, **API contract** ka hissa hai. (3) **Stateless design** — `/chat` har request independent treat karta hai; HTTP inherently stateless hai, aur LLM bhi. Conversation memory ko **explicitly** store karna padta hai (agla lecture). Yeh bilkul tumhare REST API design jaisa hai — session state ko bahar (DB/cache/file) mein rakhna padta hai. (4) UV workflow (`uv init --bare`, `uv add`, `uv run`) tumhare `python -m venv` + `pip install -r` + `python` se replace ho raha hai, par 10-100x faster. Production CI/CD mein yeh fast installs build times kaafi kam karte hain.

---

## ✅ Takeaway

- Pehla **full-stack AI app** ban gaya: FastAPI back-end (`:8000`) + Next.js/React front-end (`:3000`), browser mein connect
- **`/health` + `/chat` + Pydantic models** = production FastAPI ka standard skeleton; `/chat` `response.choices[0].message.content` se LLM reply leta hai
- Front-end `fetch("http://localhost:8000/chat")` se back-end call karta hai — port-matching critical hai
- **Red squiggly = kuch install karna baaki** (`npm install lucide-react`); **`npm install` = `pip install`** front-end mein
- UV workflow: **`uv init --bare`** (bare flag mat bhoolo) → **`uv add -r requirements.txt`** → **`uv run uvicorn server:app`**
- App working hai par **stateless** — "what's my name?" yaad nahi rakhta; memory next lecture mein

---

<details>
<summary>📜 Full Transcript (English)</summary>

Okay, now it's time to write some code or copy and paste some code. Uh, so first up we're going to make a file called me dot txt, which is going to be a little description of who who you are. And so back end it's in the back end directory a new file dot txt. And you should replace this. Don't don't spend too much time on this because we're going to do it differently tomorrow. So just make this uh obviously representing Ed Donner on Ed's website. So make this your name, your website. Your goal is to answer questions acting as ed to the best of your knowledge. Ed is a what am I? I guess I'm an I'm an AI engineer, uh, a leader and AI speaker. That gets it right. There we go. Add two, three sentences. I'll let you do that right now. Don't fumble with it while you're watching. Okay, back we go. That was me in in, uh, back end. All right. Now. Step four create a fast API server. But there's going to be no memory. So here we go. We're going to take all of this code right here. We'll talk about it in a second. Take this code. Take this code. There it is. Copy. And where are we going to put this. We are going to put this into a file called server.py in the backend directory. New file server.py in the backend directory paste it in there. Let's take a quick peek. It's a fast API server. Don't worry about the uh, these linting yellow squigglies. That's it's because it doesn't know what what environment we're in. So it's unhappy with them. Doesn't matter though. Uh, so as we're going to load in environment variables using load env, if you're not familiar with that from people from any of my other courses will be then Google it to find out more. We start the fast API server just as before. This stuff is about this cause business, uh, which I will scoot over, but you can look it up too. And at some point we'll talk about. Cause, uh, but this is setting things up, right? So that our front end knows that this is, uh, that all is good and that we can our front end can talk to this back end. Okay, then we're going to create an OpenAI Python client library. You can replace this with your own if you want to use something other than OpenAI. Uh, load personality is simply where we, uh, open the, uh, text and we'll return the contents of me and we'll set that to a global variable called personality. Okay. And then we're going to have a chat request and a chat response as two pydantic objects. We're going to have a route that just a slash API that is just going to say AI digital twin. We're going to have slash health, which is going to return healthy, just status of healthy so that we know that all is well. You remember this something like this from from App Runner. And then we're going to have slash chat, which is where it's going to to respond to a message. And we use this pedantic object to describe the format of object that comes in. And we're going to to, uh, process that and return a response, uh, chat response back again. So and this is where we say the response model is of type chat response. So, uh, what we do is we collect the messages. We're not going to do any message history. We call client chat, create a very well-known API. And then we build a chat response object from response dot choices, zero dot message content. The same old thing that you use a million times to get back a response from an LM. And, uh, that is really it. We then return that and then at the bottom here we just have something that starts the backend server. I you see that white blob there. What does that white blob tells you? I haven't pressed save yet. I press save. And we've just built our server dot Pi. And now back to our instructions. Let's see where we got to. We're now going to create the front end. So we're going to create a component called twin dot TSX. And this is going to be twin TSX. Fair amount of stuff there. Tra la la. Copy all of this. Lots of front end code. Front end is often very verbose. So where does twin TSX go exactly? Let's have a look. It's going into a new folder called components. So we're going to go to the front end. We're going to create a new folder. And we're going to call the folder components. So this is actually not within our app router at all. It's going to be connected from there. Within that, we're going to create this new file called twin dot TSX, twin dot TSX, TypeScript file and paste in our twin. And this causes not about front end. So I'm not going to go through this with you. But you will see, for example, this important, incredibly important line here is when we do the fetch, we're going to connect to port 8000 on localhost and call chat port 8000. You might have noticed was where we ran uvicorn the server. So it's going to connect locally and it's going to call chat. And some of this is stuff that you've seen before. Um, what else should I point out to you. Um, I do want to point out you'll see a red squiggly at the top here with this thing here lucide react. So it means that red squiggly means there's something we still need to install because we are reusing a react component off the shelf. That's going to help us here. And cursors even highlighted some things in red right now. It's unhappy with us. Let's try and rectify that. Uh, back to the instructions on the twin component. Uh, so, uh, after the twin component, we are indeed going to rectify that problem. We are going to need to do this npm install, which remember, is the front end equivalent of a pip install. So we come here we go into front end. You need to install from your next app. And now we're going to do npm install and install this uh lucid react component. And once we've done that any second now this should should realize. There we go. Realize. And the red is gone. And it's all looking very promising. Okay. Get rid of the terminal. It's time for us to finish off the actual files we're going to put within slash app so that we have a running front end. So first up within app we're going to create pages and pages within the app folder is what will get served when someone goes to our root. Uh, just to our URL. So new file page dot TSX. It's like the modern index dot TSX. Oh, it already exists there because there's a default one there. So we just overwrite it, paste it in there. This is our new version. Okay. That is done. Back to the instructions. And now we need to, uh, make a little fix to, uh, the front end postcss config. Let's just make sure that we are using the modern, correct approach for the latest tailwind CSS. Just something to do uh, and back here again and then update the global styles. So we need to replace the global CSS. You remember we had the globals before. Uh we're going to do a complete replace of app globals. There it is. Select all paste on the new one. Save that and that is done. Back we go to the um instructions and it's going to be time to test it. Uh, so, uh, let's let's get to that okay. Time to test. We'll bring up a terminal in cursor. Uh, we're in front end right now. Let's go back up to twin, go into backend. So we're going to create a new um, project. And the right command here is UV init dash dash bear. That stops it creating a whole bunch of files we don't need. If you forget the bear then we're going to have problems later. So don't forget the bear. It's initialized it and it's created like a pyproject.toml. Uh, Python 3.12 means that it will be using Python 312 and it will install one. If you don't already have it, you've add requirements.txt is the modern equivalent of pip install. Uh, sorry, you've add r requirements.txt. Subtext, uh, is the modern equivalent of pip install r requirements.txt. Everything gets installed. Look how fast that was. It's crazy. And now we just run this command here to run our server. And our app server is running. It's off. It's off and running. All right. It's time. Uh, it tells us what we should see. And we do indeed see that. Okay, we now need to open another terminal, which is control shift and the backtick. Here's another terminal. And you see both terminals here. Over here we can now CD to front end. And we can run our front end by doing npm run dev. Is it going to work first time. Is it going to work first time. Looks like it seems to be working first time. Uh, you should see. Yes. Okay. Now we're going to open up our local host. Here we go. Drumroll. Look at that. AI in production. Deploy your digital twins. The cloud. Look how fancy it looks. Very nice. Looks a bit like radio. Just better. Okay, let's say hi there. Let's see if it can connect to OpenAI. Let's take a drumroll. Hello. I'm Madonna's digital twin. How can I assist you today? It works. Hi. Oops. Hi. My name's all right. A name other than Ed. I'm going to be Alex. My name is Alex. Hi, Alex. It's great to meet you. How can I assist you today? Oh, what's my name? What's my name? I'm sorry, but I don't have access to that information. Hopefully you're expecting that. Uh, so this is to show you that we've set something up. We're able to have a chat, we've got a cool front end. We've got a front end and back end coming together in the browser. They're both running on our local machines on localhost. The front end is being served on localhost 3000. The back end is on localhost, 8000 being called by the front end. It's all working, but there's no memory. Every call is a separate stateless call and it can't hold a conversation that's hopeless. Let's fix it.

</details>
