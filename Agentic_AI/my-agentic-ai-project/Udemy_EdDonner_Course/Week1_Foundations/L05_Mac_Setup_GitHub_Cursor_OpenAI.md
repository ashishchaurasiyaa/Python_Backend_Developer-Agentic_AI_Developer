# L05 — Day 1: Setting Up Your Mac for AI Projects (GitHub, Cursor IDE & OpenAI API Key)

> **Week 1 — Foundations** · ⏱️ ~20 min · 🎥 Lecture 5 of 131
> **Instructor:** Ed Donner · **Lecture ID:** 49770355

> ✅ **Ye aapke liye relevant hai (aap Mac pe ho).** PC waala [L04](L04_Windows_Setup_Git_Cursor_UV.md) skip. (Aapke `my-agentic-ai-project` mein already `.venv` + `uv.lock` + `.env` hai → aap ye steps cover kar chuke ho, par revision ke liye full hai.)

---

## 🎯 Ek Line Mein (TL;DR)

Mac pe poora dev environment — **5 steps**: (1) repo clone (Terminal + git), (2) Cursor IDE install (drag-drop), (3) UV install + `uv sync`, (4) OpenAI billing ($5) + API key, (5) `.env` file mein `OPENAI_API_KEY` daalna. **Step 5 hi 90% logon ki frustration ki jad hai — dhyaan se.**

---

## 📝 Hinglish Explanation (Step-by-Step)

> Ed khud Mac user hain ("ye mera sweet spot hai"). Terminal kholo: **Applications → Utilities → Terminal** (ya Spotlight se).
> Pehle GitHub repo (course materials mein linked) ka **README zaroor padho** — Mac/Linux setup instructions + API-cost details. Instructions video se zyada clear + updated rehte hain.

### Step 1 — Repo clone karo (Terminal + git)
- Home directory check: `pwd`.
- `projects` directory mein jao (`cd projects`). Na ho toh `mkdir projects && cd projects`.
- **Git check:** `git --version`. Number aaya = installed. Na aaye toh `xcode-select --install` chalao (Mac ke basic developer tools install karta hai).
- GitHub pe sign-in → repo ka green **"Code"** button → **HTTPS** → copy URL.
- `git clone <url>` → **`agents`** folder ban jaata hai = **project root directory**.

### Step 2 — Cursor IDE install karo
- Cursor website → **Sign up** (Ed ne Google + free Pro trial liya) → **Download for Mac** → installer run.
- Mac style: **drag-and-drop into Applications** → open → default setup.
- Cursor mein **Open Project** → `projects/agents` → **Open**.
- Layout: left mein **Explorer** (files/folders, 6 weeks), right mein **AI chat** (X karke band kar do for clean view). Welcome box bhi X.

### Step 3 — UV install karo (⭐ Ed ka favourite step)
- `uv package manager` Google karo ya instructions ka GitHub link → ek single install command.
- Cursor mein terminal kholo: **View → Terminal**, ya **`Control + backtick`** *(Control, Command nahi!)*.
- Install command paste → run (super fast).
- **Cursor quit + reopen** karo (environment variables refresh ke liye).
- Verify: `uv --version`.
- **`uv sync`** chalao → ye `.python-version`, `pyproject.toml`, `uv.lock` padh ke environment build karta hai:
  - Dedicated **Python 3.12** install (3.13 latest hai par saare data-science packages ready nahi) + saare packages.
  - **~3-4 min** (Ed ka cache hone se fast tha; Anaconda ~1 ghanta leta tha).
  - **`.venv`** folder banta hai — standard Python virtual env (Conda jaisa naya tareeka nahi, fully compatible).
  - Aage: `python script.py` ki jagah **`uv run script.py`**.

### Step 4 — OpenAI key + billing (optional but recommended)
- ⚠️ Required nahi — README mein alternatives (DeepSeek/Gemini/Grok) hain. Same process unke websites pe bhi.
- `platform.openai.com` → signup/login.
- **Billing:** Settings → Billing → **Add to credit balance** → **$5 minimum** (course mein sirf few dollars lagega). Kabhi free-token deals bhi hote hain.
- **API key:** API keys → **Create new secret key** → naam (koi bhi) → **Project = default, all permissions** → Create → **copy**.
- **🪤 GOTCHA:** key ko Notepad/text-editor mein paste karke Enter mat dabao — wo hyphens ko "long hyphens" / fancy chars mein badal deta hai → key invalid → debug karna almost impossible (perfect dikhta hai par galat). Seedha `.env` mein paste karo.

### Step 5 — `.env` file (last step, sabse zaroori) 🎯
- Cursor Explorer mein folders collapse → **right-click → New File** → naam **exactly `.env`** (dot + `env`, kuch aur nahi).
- `.env` = environment variables/secrets (passwords, tokens, keys) ki private file. **GitHub mein check-in nahi hoti** — sirf aapke liye.
- Likho **bilkul sahi:** `OPENAI_API_KEY=` *(no quotes, no spaces before/after `=`)*.
  - ❌ Common galti: `OPEN_API_KEY` / `OpenAI key` — **galat**. Exactly **`OPENAI_API_KEY`**.
  - Ed: *"Is course mein shaayad yahi ek jagah hai jahan har letter sahi hona zaroori hai. Setup frustration ka 90% kaaran yahi file hai."*
- `=` ke baad apni real key paste karo → **`sk-proj-...`** se shuru, lambi string (hyphens/underscore intact). Dummy `sk-...123` nahi.
- **`Cmd + S`** se save. ✅ Setup complete!

> Ed: *"Congratulations... I'll see you in the next lecture when we reconvene with team PC."*

---

## 🔑 Key Concepts / Important Terms

| Term | Simple Hinglish Meaning |
|------|--------------------------|
| **`xcode-select --install`** | Mac pe git + basic dev tools install karta hai. |
| **Project root (`agents`)** | Top-level project folder — sab kaam yahin se. |
| **`Control + backtick`** | Cursor mein terminal kholne ka Mac shortcut (Control, not Cmd). |
| **`uv sync`** | Python 3.12 + packages install karke `.venv` banata hai. |
| **`.env` / `OPENAI_API_KEY`** | Secrets file; key ka naam exactly sahi hona must. |

---

## 💡 Backend Dev Ke Liye Note (aapke liye)

- Ye sab aapke liye **revision** hai — aap already `uv`, `.venv`, `.env` use kar rahe ho. Bas Ed ka exact key-naam dhyaan rakho.
- **Python 3.12 pin** important: aapka `pyproject.toml` already `requires-python = ">=3.12"` kehta hai. ✅ Consistent.
- **Security habit:** `.env` ko `.gitignore` mein rakhna confirm karo. (Aapke git status mein `.env` untracked dikh raha — accha, par ensure `.gitignore` mein add ho taaki galti se commit na ho.) 🔐

---

## 🧠 Takeaway (yaad rakho)

1. **5 steps:** Terminal+git clone → Cursor (drag-drop) → `uv sync` → OpenAI $5+key → `.env`.
2. **`Control + backtick`** = Cursor terminal (Mac).
3. **`OPENAI_API_KEY=<key>`** exactly — no quotes/spaces. Yahi 90% problems ki jad.
4. **Notepad trap:** key seedha `.env` mein paste karo.

---

<details>
<summary>📜 Full English Transcript (original, click to expand)</summary>

Well, hello Mac people and Linux people, welcome to your setup video series. If you're a PC user, then what are you doing here? We just set up your environment, you're set, go on to the next lecture. All right, Mac people — I had a rough time with the PC lot. This is my sweet spot. I'm a Mac user, so this hopefully is going to be very easy and fun.

So I'm in a Finder window here. And I've gone into Applications → Utilities to show you that that's where you can find Terminal, to open up a terminal if you're not familiar with that. But I'm going to now assume that you know about this and open up a terminal. Here's one right here, make that a bit bigger for you. So this is where we are going to do some of the next few steps. And we've actually got a five-step process for setting up your environment. And this is the first step, which is about cloning the repo, or getting a copy of the code for the class onto your local box. Now I'm in my home directory here if I do pwd. If you're not familiar with the command prompt, I've included a guide to get you more comfortable, more confident using the command line. It's common for people to have a directory called projects in their home directory where they put all of their work projects. And if you have that, then if you do cd projects, it will go in there. Now it looks like I don't have one, so I have to make one with mkdir projects and then change to projects. And now I'm in my empty projects directory, but you may have a few projects in there.

So the next step is now to bring the GitHub repo here. And so what we now do is we go using our favorite browser to a page where we have the repo, which is linked in the course materials. This is what the repo looks like when you go to GitHub to my name and you see the repo here — here are all of the directories, one for each of the weeks that we have coming up ahead of us, and then some general stuff. And if you scroll down you see something that's known as the project Readme. And it's really important because it's got great stuff in there. And I urge you to read the readme and the things it links to. It begins with some stuff which includes another appeal to LinkedIn with me — I seem to be quite desperate on this front. And then comes the setup instructions. And there's a link for Windows instructions for the other guys. There's a link for Mac and Linux — follow that link to get step-by-step instructions. And to be honest, those instructions are going to be way clearer than this video, and I'm going to keep them updated when people have problems. So that should really be your first place to go, and this video — see it as a video that goes along through it so you get a sense for it. But the Readme also has lots of useful resources and a ton of important stuff on API costs that I urge you to read, because I know this is a sensitive topic.

And I should probably mention that if you've not used GitHub before, you might need to create a new account with GitHub to get to this point. Now, just before we clone this repo locally, I'd like to go back to the terminal window and I just want you to type git --version to check that you've got git installed on your Mac, and it should come up like mine does with a version number. If it doesn't, you might need to run this command: xcode-select --install, which installs some of the basic developer tools on your Mac. I've got a link to that in the setup instructions. I won't do it since I already have Xcode and Developer tools installed.

Okay, so with that, if you're typing git --version, you're getting a number there. You come to the repo, you've signed in to GitHub, there's this green code button on the top right. And you press there. And probably I recommend that at this point you select the HTTPS version. I'm going to pick this version because I have that kind of credential, but you can also pick the other one. And then you copy that into your clipboard by pressing the copy button right there. So once you've copied this text, which is the link to this repo, you then come back to the command line. And in your projects directory there I am, I'm inside users/ed/projects. I'm now going to type git clone, and then the repo link that I've pasted from my clipboard. And I press enter, and in it comes, and it's done. If I now have a look, you'll see that there is a directory called agents. If I go into agents I now see that I have directories for the full project. And I want to mention that where we are right now in this directory — that's in my projects directory, the agents directory — this is known as the project root directory. If you're inside the top level directory of your project of agents, this is the project root. And you'll hear that referred to during the course and generally. But that is step one of the setup complete.

Okay. Welcome to step two of the setup for Mac. We're going to now install Cursor, the IDE, which is great. It is fabulous, and you're going to love it. If you've already got Cursor then of course you can skip this step. Otherwise bring up your favorite browser and go to Cursor. And here we have the screen for installing Cursor. You will need to begin by creating an account using the sign up button if you don't have one already, and it will just guide you through. I use my Google credentials myself, and I selected a Trial Pro plan myself, which is free, at least for now. And I then press download for Mac, which then brings down an installer. I then run that installer and it asks me a couple of questions. I log in and then it installs it. You then drag and drop into applications and you open that up and it will install it. Easy peasy. I selected all of the default setup instructions, nothing special at all. And then you should launch it and you should be in Cursor.

Okay. So once you've opened up Cursor freshly installed, this is what it should look like — a nice big empty screen. And we're going to press the open project button right here. And we're going to then navigate to projects wherever that is — I guess it's going to be at the top, projects and then agents, which is the new folder that we've just installed. This is known as the project root folder. And then we're going to press open. And here it is. Cursor opens up. We've got a nice screen here that's known as the explorer which shows all of the files organized by directories. One of these directories might be open — you can just click the switch to collapse it. There might be a box up here with some sort of welcome to Cursor, blah blah blah — just X out of that extra box on the top left if it's there for you. Over here is a chat screen where you can chat with an AI about your code, and I'm going to suggest for now we X out of that as well to keep things really clean. So what we're looking at now is a nice big area here, and the explorer to look at our directories right here, including the Readme and so on. And congratulations, you are into Cursor. And that is the second step of the instructions completed.

And we are now onto step three of the instructions, which is my very favorite step, where you're going to install UV, the package manager which is so fabulous, so quick and easy to use. I know it's like another new thing to learn, which is always a pain, but I tell you, it's so great. The reason we're doing this is partly because a student on my prior course said, you know, you really should use UV, it's so much better. And so I'd heard of it, I knew it was doing the rounds, but I hadn't actually used it myself until that, and that pushed me to do it, and I've never looked back. And we'll find that many of the AI platforms, the agent platforms, will use UV themselves. So it's going to work out really well for us.

All right. So first step is to install UV. And the way you do that is you bring up a browser window. You can just Google for UV package manager, or you can look at the link that I'll have in the instructions, and you'll see that there is the link to the GitHub. And it has within it some clear installation instructions. You just simply have to run this one command in a terminal, and I will copy that to the clipboard. Now there's actually a new easy way to run things in a terminal because you can do it within Cursor. Here's my Cursor screen again. And there's actually a view menu, and you can go view and then terminal. Or you can press the control button — not the command button, not the one with the squiggle clover on it, but the control button on the bottom left of your keyboard — and then the tick mark on the top left of your keyboard, or at least on my keyboard. And up comes a terminal. And now you can simply paste in that command to run the installation for UV, and it will be super quick and you'll be done. I'm not going to run it because I've already run it. Once you've done that, you might need to close this terminal by pressing the X, and you might actually need to quit right out of Cursor and bring back up Cursor because it needs to refresh its environment variables. But if you've done that, then if you type uv --version, it should give you a version number, which is telling you that all is good, UV is installed.

And with that we are almost ready to go. There is now only one command left. And what is that command, I hear you ask? It is simply to type, at this point, uv sync. And what that's going to do is it's going to look at some of the other files here, like a Python version file and a pyproject.toml and some other things and a uv lock, and it's going to use that to build our environment. And let's see it doing that. Off it goes. Now I told you that it's quick, and you'll see that it was very quick. That is just done. But that's actually quicker than it will be for you, and it's that quick because it does cache things that I've done before. When you do this, it's going to take about three minutes, four minutes, which is still very quick because Anaconda takes like an hour or something. So it's going to be fast, but there is still a lot to be installed, so you'll have to sit back and wait while everything installs, but enjoy the raw power of UV as everything gets built.

And once it's done, what you may notice is that there's a new directory called .venv that's appeared, which is like a traditional Python virtual environment if you know these things. It's created one for this project. And so one of the really nice things about UV is that it's compatible and consistent with all of the other ways you do things in Python. It's not like there's a new sort of thing like Conda. So that's been set up, and now that is going to be the environment that we'll be using from this point onwards. And when you run a Python script, whereas before you might have typed Python and then something, what you're going to type now is uv run and then that same thing, and that automatically makes sure that it runs in that environment. The other thing to mention is that it has installed a dedicated version of Python right for this project. It is in fact a Python version 3.12, whilst the latest version of Python is 3.13. That's not yet — not all data science packages are ready for that yet. So 3.12 is what we're using, and everything will be in that Python. It will have installed it for you if you didn't already have it, and it will be dedicated for this project. UV is really good. It combines this kind of isolated environment with something that is fast and simple, and I very much hope that this will have simply worked for you. And that means that step three is done.

So for step four, we're going to set up a key with OpenAI. Now again I want to emphasize that whilst I do encourage you to be setting up a key with OpenAI and to be using that API, it is not required for this course. And there are alternatives in the Readme. But that's what we're going to do now. I'm going to assume that you are good for this. So you go to platform.openai.com just here. And this brings you to the front screen of OpenAI where you get to set up an account. If you don't have one already, sign up, or log in if you have one. And I'm going to log in because I already have one, log in with my Google credentials. And here we have my account, we're logged in. So there are now two things that we have to do now that we're in OpenAI, and we're going to go and do both of them now — bearing in mind this is not required, you can also do the same thing, this analogous website, for DeepSeek and for many others.

So as I say, it's two steps. The first of them is to go to the settings menu up here and come down to billing. And this is where you set up your billing details. Now you have to apply a credit balance, giving OpenAI some money in advance. And I've given it quite a lot of money right here because I'm doing various different things, and you do not need to give it that much money by any means. There is a minimum top up — they require at least $5 as of right now, but they sometimes have deals. There's something going on down here that you could read about — perhaps there's some deal for free tokens right now. And you can press the Add to credit balance to put in your $5 up front. That's, I believe, required right now. And we'll only spend a few dollars of that on this course, and you have complete flexibility and you can come back and watch to what extent you're spending your credits as we go through. But I suggest doing that, putting in your $5. But bear in mind, if you don't want to, you don't need to.

Once you've done that, you then turn to the API keys part of this, which is where you get to see the key that you've set up that you will use for this project. And if you already have a key, then great, you're in good shape. But I assume you don't, in which case you press this green Create new secret key. You give it a name that just doesn't matter, just for your future reference. And then for projects, be sure to choose default Project and leave it as all permissions, and then press Create Secret Key. It's then going to bring up your key that you'll use. And you can copy it into your clipboard. And we're going to paste it in a moment into Cursor in a place where we were going to use it. Now here's the thing. Here is a nasty gotcha to be aware of. It's very tempting to take your key and paste it into a useful app like notepad or something, but there's a trap there you need to be careful of. Some programs, I think including notepad, if you paste in some text and then press enter, it changes some of the characters in that text to be nicer formatted — like it turns hyphens into long hyphens, and that can be really hard to spot. And that will then basically invalidate your key. Your key will now be a different set of letters or characters, and when you try and use that in your file, it's going to fail, and it's going to be almost impossible to track it down because it's going to look perfect. And it's really frustrating, and a lot of people have had that problem. So I urge you just to copy it into the clipboard and paste it straight into Cursor in the next step. And it is good to keep a copy of it somewhere, just be really careful to make sure you do it in a way that doesn't overwrite your characters.

So there is my public service announcement about things to watch out for with keys. But hopefully you've set up your key, you've copied it to the clipboard, you've maybe made a backup somewhere safe. And now we're ready for the next part. And this is step five of the environment setup, and it's the last step. We're almost completely done. We're back in Cursor again. And I'm just going to press an X here to get rid of that screen, and an X to get rid of my terminal, so we're looking at a nice clean page. Now, down here in the explorer, I've collapsed all these folders. I'm going to right click and say new file at the bottom here. And I'm going to create a new file. And I'm going to give it a very precise name. And you have to give it exactly the same name. If you get this wrong by a single character, then you're going to have problems later. So be careful with this one. It starts with a dot, the period, a full stop, and then the letters E, N, V. And it's got to be called exactly that — .env. And you'll see why later. But basically this is a file which is often used to store environment variables, things that will load into our environment as variables that we'll use for things like passwords and tokens and keys. And it doesn't get checked into GitHub, so it stays as a private file just for you. And it's a common technique for managing these kinds of things. And it's called .env, and it has to be called exactly that.

So what we can now do is type into here a key that we want to remember. And in particular the one that we want to remember is OpenAI's key. And it's OPENAI_API_KEY. And it's actually prompting me right here for it because Cursor is that clever and knows what we're trying to do. And we can just press Tab to fill it all the way in, but I'm not going to do that. I am going to type OPENAI_API_KEY equals — no quote marks, no spaces, no spaces before or after. And people — one common mistake is that sometimes people say OPEN_API_KEY or OPENAI_KEY, but it's not that, it's OPENAI_API_KEY. And it's got to be exactly this. I think this is one of the only things in this course where every letter needs to be right. And so be careful. This is like 90% of the reason that people are frustrated in environment setup — is this very file. All right. What comes next is you simply paste in here exactly the key that came from OpenAI. And it should begin sk-proj- and then a bunch of letters and numbers with maybe an underscore symbol as well. And that should all come there — a bunch of them, not 1234567890 as it has here in Cursor, but a real key. And not "sk-proj and then another sk-proj" or anything like that that some people have done. It's got to be just right. Sorry to go on about it, but this is such a cause of problems. So make sure that that key, the thing that's showing in purple here, is exactly the key that you took from OpenAI. And it should look perfect. And once you've done that, you do Command S to save this file, and you'll be in great shape. And at that point that will then be the end of step five of the environment setup. We will have done environment setup, and we're good to get into the actual project. How about that. So congratulations. Hopefully this is now all going to work. We'll soon find out. I will see you in the next lecture when we reconvene with team PC.

</details>

---
*Source: Official Udemy lecture transcript (auto-captions, lightly cleaned). Notes in Hinglish for self-study.*
