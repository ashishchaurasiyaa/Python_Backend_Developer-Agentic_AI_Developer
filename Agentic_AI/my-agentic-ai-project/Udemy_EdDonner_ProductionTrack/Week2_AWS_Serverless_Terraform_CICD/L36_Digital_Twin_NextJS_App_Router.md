# L36 — Building Your AI Digital Twin: Production Setup with NextJS App Router

> **Week 2 · Day 1** · ⏱️ ~11 min

---

## 🎯 TL;DR

Week 2 ka pehla building lecture: ek **AI Digital Twin** (tumhe future employers ke saamne represent karne wala conversational AI) banane ka setup. Aaj sirf **local version** banayenge — focus **App Router** wale Next.js par + project scaffolding (`backend`, `frontend`, `memory` folders, UV package manager, `requirements.txt`, `.env`).

---

## 🗣️ Hinglish Explanation

### Aaj ka mission: Digital Twin introduce karna

Ed cursor mein **production** project khol ke baith jaata hai. Pehla golden rule yaad dilata hai: hamesha **`git pull`** maaro taaki latest code mile (guides constantly update hote rehte hain). `production` repo ke andar **`week2`** folder hai jisme **5 din ki guides** padi hain. Kisi bhi `.md` file par right-click → **Open Preview** karne se wo formatted, nicely-rendered view mein khulti hai (raw markdown ki jagah).

Aaj hum **AI Digital Twin** banana shuru karenge — ek conversational AI jo tumhe (Ed ko Ed ke case mein) future employers ke saamne represent karega. Aaj sirf **local version** banega, aur khaas focus rahega **memory** par — yaani ek apparently **stateful conversation** LLM ke saath, jahan har baar **poori conversation so far** ko prompt mein pass karke statefulness simulate ki jaati hai (LLM khud stateless hota hai).

### Pages Router vs App Router — Next.js ka core difference

Aaj ka sabse bada naya concept: hum Next.js ke **App Router** mode mein kaam karenge, **Pages Router** mein nahi. Yeh distinction Next.js samajhne ke liye fundamental hai.

**Pages Router (purana, simple model):**
- Ek **`pages/`** directory hoti hai.
- Us directory ki **har file ek route ban jaati hai** — yaani ek URL jo outside world hit kar sakta hai.
- `index.tsx` → main root (`/`)
- `product.tsx` → `/product`
- Yaani: **har web page ke liye ek alag TypeScript file**.

**App Router (modern, recommended):**
- Ek **`app/`** directory hoti hai (na ki `pages/`).
- Andar **`page.tsx`** naam ki ek file hoti hai jo root (`/`) represent karti hai — jab koi main URL hit kare.
- Har dusre page ke liye **alag subdirectory** banani padti hai. Agar `/about` chahiye toh `app/about/` subdirectory banao, aur usme `page.tsx` rakho.
- Yaani: **har web page ke liye ek alag subdirectory** (jisme `page.tsx` ho).

```
# Pages Router                  # App Router
pages/                          app/
  index.tsx     → /               page.tsx          → /
  product.tsx   → /product        about/
  about.tsx     → /about            page.tsx        → /about
                                  product/
                                    page.tsx        → /product
```

App Router zyada **robust applications** ke liye design kiya gaya hai (layouts, server components, nested routing, streaming). Ye ab **going-forwards recommended approach** hai. Ed batata hai ki pichle hafte (Week 1) usse **classic Pages Router** use karna pada tha kyunki App Router **Clerk** ke saath static front-end websites par theek se kaam nahi karta tha. Par Week 2 mein hum **Clerk use nahi kar rahe**, isliye App Router use kar sakte hain — aur karenge.

> Background: Next.js ek React-based full-stack framework hai (Vercel ka banaya hua). File-system based routing iska core feature hai — folder/file structure hi tumhari URL structure decide karta hai, manual route config nahi karni padti.

### Part 1 — Project Setup

**Step 1: Naya project `twin` banao.**
1. Cursor → `File` menu → **Open Folder** → apni `projects` directory mein jao
2. **New Folder** → naam `twin` → **Create** → **Open**
3. Ab ek completely empty canvas hai. AI chat panel band kar do.

Is hafte sab kuch **scratch se** banega — koi existing repo clone nahi karenge. Ye tumhara apna repo hoga, keep karne ke liye.

**Convenience step (guides local mein laana):** Ed left sidebar mein right-click → **New Folder** → `week2` banata hai, phir terminal (``Ctrl + ` ``) mein production repo ke `week2` folder ka content copy karta hai, taaki guides aur project ek hi jagah ho (baar-baar do windows ke beech switch na karna pade):

```bash
# twin project ke root se, ek directory upar jaake production/week2 ka content copy
cp -r ../production/week2/* week2/
```

(Tum drag-and-drop bhi kar sakte ho explorer mein — jo comfortable lage.)

**Step 2: Project directories banao.** Left sidebar mein right-click → New Folder:
- **`backend`** — yahan hamara back end rahega
- **`memory`** — yahan memory files locally store hongi (deploy par yeh **S3** mein jaayengi)

**Step 3: Front end banao (`create-next-app` se).** Naya terminal kholo aur ye command chalao:

```bash
npx create-next-app frontend --typescript --tailwind --app --no-src-dir --eslint
```

Flags ka matlab:
- `frontend` → folder ka naam (yaani `frontend/` mein bnega)
- `--typescript` → TypeScript variant (plain JS nahi)
- `--tailwind` → Tailwind CSS for styling
- `--app` → **App Router** use karo (Pages Router nahi) — yahi wala flag aaj critical hai
- `--no-src-dir` → "use a `src/` directory?" wale sawaal ka automatic **no**
- `--eslint` → linter ES Lint use karo

Interactive prompts par answers:
- create-next-app install karein? → **Yes**
- Which linter? → **ES Lint**
- Use Turbopack? → **No**

Ho jaane par `frontend/` folder ban jaata hai — andar dekho toh telltale **`app/`** folder dikhega, jo immediately confirm karta hai ki hum **App Router** situation mein hain.

Ab structure aisa hai: `backend/`, `frontend/`, `memory/`, aur `week2/` (guides). So far so good.

### Part 2 — Python Package Manager (UV)

Backend Python ke liye hum **UV** use karenge — Ed ka favourite package manager. UV **Anaconda ya direct virtualenvs ka alternative** hai Python dependencies organize karne ke liye. Khaasiyatein:
- **Extremely robust** dependency resolution
- **Bahut fast** — Rust mein likha gaya hai
- Community mein bahut popular ho chuka hai

Install karne ke baad verify karo:

```bash
uv --version          # Ed ko pehle 0.7.9 mila
uv self update        # latest par update (instructions mein nahi par useful)
uv --version          # update ke baad 0.8.13
```

> Background: UV ek single tool mein pip + virtualenv + pip-tools + (kuch had tak) pyenv ka kaam kar deta hai. `uv add`, `uv sync`, `uv run` jaise commands se project-level dependency management deterministic aur fast hota hai.

### Part 3 — `requirements.txt` (backend dependencies)

Ye sirf **environment setup** hai — Ed mazaak karta hai ki "you ain't seen nothing yet", abhi aur setup baaki hai.

`backend/` ke andar (parent directory mein nahi — yahan galti hui toh baad mein **debug karna mushkil** ho jaayega) right-click → New File → **`requirements.txt`**. Guide se packages paste karo. Typically aise dependencies:

```
fastapi
uvicorn
openai
python-dotenv
pydantic
pypdf
boto3
```

⚠️ **Critical warning:** `requirements.txt` ko galti se **parent directory** mein mat banao — sirf `backend/` ke andar. Warna baad mein "snafus" aayenge jinka root cause dhundhna painful hoga. Is course mein file location ke baare mein bahut aware rehna padega.

### Part 4 — Environment Configuration (`.env`)

`backend/` ke andar right-click → New File → **`.env`**. Isme do cheezein:

```bash
OPENAI_API_KEY=sk-...your-key-here...
CORS_ORIGINS=http://localhost:3000
```

Do important baatein:

1. **`OPENAI_API_KEY`** — apni OpenAI key dhundho (shayad kisi purani `.env` file mein ho), copy-paste karo.

2. **`CORS_ORIGINS`** — spelling dhyan se: **CORS** (Cross-Origin Resource Sharing), na ki "cross origins". CORS front-end developers ki **bane ki bani** (bane of their lives) hai. Yeh security control hai jo decide karta hai ki **kaun sa front-end/back-end kis se connect kar sakta hai**. Browser by default ek origin (e.g. `localhost:3000`) ko doosre origin (`localhost:8000`) par requests bhejne se rokta hai jab tak server explicitly "allowed origins" header mein usse permit na kare. Is course mein CORS ke saath bahut careful rehna padega; aage isme detail aayegi. Abhi guide mein jo value di hai wahi exact use kar lo.

**`.env` save karne ke do signs (Ed ka pet peeve):**
- **White blob/dot** tab par = file **unsaved** hai → `Cmd+S` / `Ctrl+S` daba ke save karo. Bahut log `.env` save karna bhool jaate hain aur phir confused hote hain.
- Save karne ke baad ek **"stop" symbol** dikh sakta hai — **ghabrao mat, ye GOOD news hai**. Cursor bata raha hai ki **AI features `.env` file ke liye disabled** hain (tumhari protection ke liye — Cursor `.env` ka content AIs ko bhejna nahi chahta jo usse autocomplete kar dein). Yeh expected aur desirable behaviour hai.

> Background: `.env` files secrets (API keys, DB passwords) rakhne ke liye standard pattern hain. Inhe **`.gitignore`** mein daala jaata hai taaki secrets git/GitHub par accidentally push na ho. Code inhe `python-dotenv` ke `load_dotenv()` se padhta hai.

---

## 📋 Key Concepts

| Concept | Matlab |
|---|---|
| **Digital Twin** | Conversational AI jo tumhe (Ed ko) future employers ke saamne represent karta hai |
| **Stateful conversation** | LLM stateless hai; har call mein poori conversation history pass karke statefulness simulate karte hain |
| **Pages Router** | Next.js purana model — `pages/` mein har file = ek route/URL |
| **App Router** | Next.js modern model — `app/` mein har subdirectory + `page.tsx` = ek route; robust apps ke liye recommended |
| **`page.tsx`** | App Router ka root file (modern `index.tsx`) jo `/` serve karta hai |
| **`create-next-app`** | Next.js project scaffold karne ka CLI (`npx create-next-app`) |
| **UV** | Fast, robust Python package manager (Rust mein likha), Anaconda/virtualenv ka alternative |
| **`requirements.txt`** | Python dependencies ki list — sahi folder (`backend/`) mein honi chahiye |
| **`.env`** | Secrets/config file (API keys, CORS origins) — git-ignored, dotenv se load hoti hai |
| **CORS** | Cross-Origin Resource Sharing — kaun kis origin se connect kar sakta hai, ka security control |
| **white blob** | Cursor tab par unsaved-file indicator — save karna mat bhoolo |

---

## 💼 Backend Dev Ke Liye Note

Tum Python backend dev ho, toh `backend/` + `requirements.txt` + `.env` wala flow already familiar hai — bas yahan ise UV se manage kar rahe ho (pip + venv ka faster replacement). Naya seekhne layak hissa **front-end ka mental model** hai: Next.js App Router ka folder-based routing aapke FastAPI ke decorator-based routing (`@app.get("/about")`) se conceptually milta-julta hai — dono mein structure hi route define karta hai, bas Next.js mein file-system structure use hota hai. CORS ko backend perspective se samjho: yeh **server-side** decision hai (FastAPI middleware mein `allow_origins` set hota hai), browser sirf enforce karta hai. `CORS_ORIGINS` env var isi liye backend ke `.env` mein hai — front-end ka origin whitelist karna server ki zimmedari hai. Local dev mein front-end `:3000` aur backend `:8000` alag origins hote hain, isliye CORS abhi se relevant hai.

---

## ✅ Takeaway

- **Hamesha `git pull`** maaro production repo mein — guides constantly updated rehte hain; `.md` par **Open Preview** se formatted view milta hai
- **App Router vs Pages Router** Week 2 ka core mental model hai: App Router mein har route ek subdirectory + `page.tsx`, Pages Router mein har route ek file
- Project skeleton: `backend/` (server + secrets), `frontend/` (`create-next-app --app`), `memory/` (local conversation storage; deploy par S3)
- **UV** Python package manager use karenge — fast, robust, Rust-based
- `requirements.txt` **sahi folder** (`backend/`) mein rakho aur **`.env` ko save** karo (white blob = unsaved; stop-symbol = AI disabled = good)
- **CORS** spelling-sensitive aur is course ka recurring headache hai — abhi guide ki exact value use karo

---

<details>
<summary>📜 Full Transcript (English)</summary>

And welcome back to cursor. I am looking in cursor at the production project. So you go file new window and select production or Open Production. And remember to always do a git pull explained in the guides to make sure that you have the latest code. And in the production repo there is a week two folder and there's five days worth of guides. And if you right click on day one and do open preview, it will come up in a nice formatted way. So today introducing the twin we are going to build an AI digital twin, a conversational AI that represents you to future employers. And we're going to start today by building a local version that particularly focus on making sure that memory works, so that you can have an apparently stateful conversation with an LLM, which we are using this technique of just passing in the conversation so far. So one of the things that's going to be very different about today is that we're going to be using the app router mode of Next.js. Not the pages router, the more modern app router. So there's a few things to to look for that will be different when we're using the pages router that are keyed to know you're using the pages router is that there is a directory called pages, and every file in that page's directory becomes a root, a URL that the outside world can hit. So index TSX is the sort of the main root. And then product TSX is product and so on. And that's that's the model you look for in the pages router, which is nice and simple. The app router is sort of built more for for more robust applications where there's an app directory contrasting the pages directory. Within the app directory, you have one one file called page TSX that represents your your root. What will happen if someone just hits the main URL and then you have a separate subdirectory inside app for every other page, so you'd have a separate subdirectory. If you had a slash about, then you would need to have a subdirectory called about, and pages in that subdirectory would then serve slash about. So uh. Put put simply you have separate subdirectories for every web page. Whereas with the pages router you just have a separate TypeScript file for every web page. That's perhaps the the most obvious difference that you'll find. But there are there are lots of others. Um, and so, uh, this this is now going forwards the recommended approach, uh, it turned out that that app router didn't work with Clark with, with static front end websites. So I had to use the classic pages router. But we won't be using Clark this week. So we can use App Router. And that's why we will. Okay. It's time to set up our project for this week. The twin project. Let's go and do that now. Okay, so starting with part one project setup, first of all, open cursor or whatever IDE you like and create a new project called twin. So I'm going to go to the file menu. I'm going to say Open Folder. And then here come all my projects I'm in my projects directory. Go there press new folder. Twin is what we'll call this say create and then open and bam! Here we are in our new twin project. I'm going to close down the AI for now. So here we have a completely empty canvas looking at twin. We're going to be building everything in this directory in this project from scratch this week. Uh, we're not going to be cloning an existing repo or anything like that. This will be yours. Your repo to keep. And I'm going to start by opening up a terminal and just for convenience. So the instruction guides are all there in the, in the other in the production repo. But it might be helpful for us here. We can right click and say new folder on the left and let's make a new folder called week two like that. And then in the terminal control Backtick, I can copy in the contents of the week two folder from the production repo. I think I did this last week as well, so I'll do copy, go up a directory, go into the production directory, take the week two folder and copy everything into this week two folder right here. You can also just do this by dragging and dropping in your explorer or whatever, whatever makes you feel more comfortable. But once I've done that, I do this so that we have all of our days here. So we're not going to have to click backwards and forwards between the two. Hopefully that makes sense to you. And now with that open preview for day one again and we're back. We're now in our fabulous new project. Uh, and we are already we've already set up our step one of part one. Okay. We're on to step two. Create the project directories in File Explorer on the left here. Right click new folder and set up a new folder that's called Back End. That's where our back end is going to live. And then right click again new folder and call it memory. This is where our memory files are going to live when we're running it locally. When we deploy they'll be in S3. Okay. And now it's time for us to create our front end in step three, because we have a front end folder to match the back end. And we're going to use create next app to do it. Okay. So I'm going to open a new a new terminal like so or the same terminal and then run this command Npx create next app. Remember that command we did before. We've got a few flags here. We're calling it front end. So it'll be created here with front end. We want a TypeScript variant. We're going to use tailwind again. That as you can probably guess means we're going to be using the app router. And this is just automatically saying no to that question about user source directory. Uh, so it wants to install create next app. We say yes. Which linter will use ES lint. Would you like to use Turbo pack. We'll say no. We'll say no to that as well. And it's all happened. We now have a front end folder as well. And if you look within it, you'll see all sorts of stuff, including the telltale app folder, which tells us immediately we're in an app router situation. So we have a back end, our front end, a memory. And then week two is our guides. So far so good. And then it has like a checkpoint here. Does our setup look like that. Yes it does. Very nice. Okay. Part two is to install a Python package manager. We're going to be using UV which is my favorite package manager. It is so fantastic. It's taken the community by storm. It's everywhere now. So UV is something which replaces. It doesn't replace. It's an alternative to Anaconda, for example, or using Virtualenvs directly to organize your Python dependencies in a very robust way. And UV is not only extremely robust, it's also very fast. It's written in rust. Um, and anyone that's been on my genetic course knows it only too well. Here's where to install it. These instructions are beautifully written. Uh, and so you should be able to follow this. You don't need anything more from me. Although I do have in here the the commands to follow. But you'll also get them straight from there. There are alternative instructions. If any of these give you problems when you're done, you should be able to come in here and do UV minus minus version and we'll see. I have UV 0.7.9. You can actually it's not in the instructions but you can do UV self-update if you wish. And that will update onto the latest version of UV. Let's see what we're on now checking for updates. Success. Look at that. So now if I do UV minus minus version I'm on the latest version, naught .8. 13. Great. So. And look at the instructions. Naught .5. naught. Now we're a fair bit on for that. That is part two. Done. It's onwards to part three. You're probably starting to feel like that didn't lie. This really is just going to be environment setup. And you ain't seen nothing yet. Wait for it. All right. So next up we're going to create a requirements file for installing Python packages within the backend directory. So in backend right click here new file. And you know the thing is if you make any mistakes here like if you put this requirements.txt in the parent directory instead of in here, then you're going to get snafus later. And it might be hard to figure out why. So I tell you this is going to be you're going to have to be really aware of what's going on. Uh, so I'm going to copy this. These are the packages that we depend on. Paste it in here and I save. And that is done. Onwards. Okay. Next create an environment configuration. So within back end we want to create a dot EMV file. Okay new file dot EMV. And in that EMV file we're going to have two things. We're going to have open AI API key equals. And we're going to put something there. And then there's another 12 I just saw let's go back and have a look at it. And it's one that's going to take a little bit of explanation. It's cause origins. And be sure to spell this right. Not cross origins but cause origins. Cause I remember I mentioned it before. I think it is the bane of front end developers lives. Cause is all about the security controls around, uh, which, uh, what what back end or front end is allowed to connect to, uh, and it is a headache and we are very careful with it on this course. And at some point I'll talk more about chords, but for now, just go along with it. Uh, in this preview file, sorry, we'll just take exactly what it says there. This is going to be the value to use in our EMV file. And now you have to go and find your OpenAI API key. If you're not sure where to find it, then presumably it's in another EMV file that you've used. Copy it. Paste it in here. You need to save that white blob. There is a sign that you haven't saved this type of symbol here. If I save now, you get this. This, uh, stop symbol. That is good news that. Don't worry about that. That's telling you a good thing. It's telling you that AI features are disabled for the EMV file, which is for your own protection, because cursor doesn't want to be sending the contents of this file to AIS to fill it in. So don't worry about that, that sign. But but do worry about a white blob. That means you need to save your EMV file. You wouldn't believe how many people forget to save their dot env file. I'm going to go and do that right now, and I will come back when my key is safely in there.

</details>
