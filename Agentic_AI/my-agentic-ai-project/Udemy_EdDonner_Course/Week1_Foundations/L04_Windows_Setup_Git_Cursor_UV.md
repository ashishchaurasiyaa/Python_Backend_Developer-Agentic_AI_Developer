# L04 — Day 1: Windows Setup for AI Development (Git, Cursor IDE & UV Package Manager)

> **Week 1 — Foundations** · ⏱️ ~21 min · 🎥 Lecture 4 of 131
> **Instructor:** Ed Donner · **Lecture ID:** 49770331

> ⚠️ **Mac/Linux user ho? Ye lecture SKIP karo → seedha [L05 (Mac setup)](L05_Mac_Setup_GitHub_Cursor_OpenAI.md) pe jao.** Ye sirf Windows/PC waalon ke liye hai. (Aap `my-agentic-ai-project` pe Mac+UV already chala rahe ho, toh steps familiar honge.)

---

## 🎯 Ek Line Mein (TL;DR)

Windows pe poora dev environment setup — **5 steps**: (1) repo clone (git), (2) Cursor IDE install, (3) UV install + `uv sync`, (4) OpenAI billing + API key, (5) `.env` file banakar key daalna.

---

## 📝 Hinglish Explanation (Step-by-Step)

> Sabse pehle: GitHub repo (course materials mein linked) kholo aur **README zaroor padho** — ismein Windows/Mac/Linux setup instructions hain jo "living document" hain (update hote rehte hain). Video sirf "bring it to life" karta hai; likhe instructions zyada bulletproof hain.

> **⚠️ PC Gotchas (setup-PC guide ke top pe):** (a) Windows ka **260-character filename limit** — agar on hai toh off karo, warna lambe filenames fail. (b) **Antivirus** kabhi installation mein interfere karta hai — guide ke steps follow karo.

### Step 1 — Repo clone karo (Git)
- **PowerShell** kholo (Start menu → "PowerShell").
- `projects` directory mein jao (na ho toh `mkdir projects` home directory mein).
- Git check: `git --version`. Na ho toh Git website se Windows installer download karo (PowerShell restart / kabhi PC restart lagta hai).
- Repo ke green **"Code"** button → HTTPS → URL copy.
- `git clone <url>` → `agents` folder ban jaata hai. Yahi **project root** hai.

### Step 2 — Cursor IDE install karo
- Cursor download (Windows) → executable run → agreement accept → install location choose (C ya D drive).
- Desktop icon + **PATH** changes (isliye baad mein **naya** command prompt chahiye).
- Install → finish → launch → "cursor" command-line shortcut enable → **Privacy mode** select (logging off).
- Free **Cursor account** banao.
- Cursor mein **Open Project** → `agents` folder select karo → ye project root. Left mein **Explorer** (6 weeks ke folders: foundations → MCP), right mein **chat** (LLM se baat).

### Step 3 — UV install karo (⭐ best part)
- **Astral** company ka UV (setup instructions mein linked). Extremely fast package manager.
- Windows install command PowerShell mein paste karo → installs.
- **Shell restart karo** (`exit` → naya PowerShell) — warna PATH update nahi hoga.
- Verify: `uv --version`.
- Cursor mein terminal kholo (View → Terminal, ya `Ctrl + backtick`).
- **`uv sync`** chalao → ye environment build karta hai: dedicated Python version install + saare packages.
  - Anaconda mein ye **1–1.5 ghante** le sakta tha; UV mein **~2-3 min**. 🚀
  - `.venv` folder ban jaata hai (virtual environment).
  - Aage scripts ko `python script.py` ki jagah **`uv run script.py`** se chalao (auto us env mein).

### Step 4 — OpenAI key + billing
- (Already key hai ya OpenAI pe paisa nahi kharchna? Ye step **skip** karke DeepSeek/Gemini/Grok/OpenRouter use karo — setup instructions mein hai.)
- `platform.openai.com` → login/signup.
- **Billing:** Settings → Billing → credit add karo. **$5 minimum** (pay-as-you-go). *(International cards kabhi dollar charge reject karte hain → DeepSeek / Grok / OpenRouter alternatives.)*
- **API key:** API keys section → **Create new secret key** → name do → **Project = default, all permissions** → Create → **copy to clipboard**.
- **🪤 PRO TIP (bada trap):** key ko Notepad/Word jaise app mein paste mat karo — wo hyphens ko "long hyphens" / special chars mein badal dete hain → key fail → ghanton debugging. Seedha agle step (.env) mein paste karo.

### Step 5 — `.env` file banao (final step)
- Cursor Explorer mein top-level pe right-click → **New File** → naam **exactly `.env`** (dot se shuru, sirf "env"). *(Specific reason baad mein.)*
- `.env` = project-specific **environment variables / secrets** rakhne ka standard tarika. Source code mein check-in nahi hota, private rehta hai.
- Likho: **`OPENAI_API_KEY=`** (Cursor autocomplete dummy bhar dega — tab mat dabao) → apni real key paste karo (ESC se shuru, long string, hyphens intact).
- Baaki keys bhi same tarah: `DEEPSEEK_API_KEY=...`, Grok/OpenRouter, etc.
- ⚠️ **Yahi 1 chhota step zyaadatar setup problems ki jad hai** — typo mat karna.

> ✅ Ho gaya! Setup complete. **Mac waala next video skip karo.** Sab fir saath milenge.

---

## 🔑 Key Concepts / Important Terms

| Term | Simple Hinglish Meaning |
|------|--------------------------|
| **Project root** | `agents` folder — sab kaam yahin se. |
| **`uv sync`** | Project ke hisaab se Python + packages install karke `.venv` banata hai. |
| **`uv run <script>`** | Script ko us venv mein chalata hai (`python` ki jagah). |
| **`.env`** | Secrets/API keys rakhne ki private file (git mein nahi jaati). |
| **OPENAI_API_KEY** | Sabse important env var — key sahi paste karna critical. |

---

## 💡 Backend Dev Ke Liye Note (aapke liye)

- Aap ye sab already jante ho (git clone, venv, `.env`). Bas Ed ka flow = **Cursor + `uv sync` + `.env`**. Aapke `my-agentic-ai-project` mein already `.env`, `.venv`, `uv.lock` hain — toh aap step 3–5 cover kar chuke ho.
- **`.env` ka "secret reason" (Ed baad mein batayenge):** `python-dotenv` / framework `load_dotenv()` se auto-load hota hai — isliye naam exactly `.env` hona chahiye. Aap `main.py` mein already `from dotenv import load_dotenv` use kar rahe ho. ✅

---

## 🧠 Takeaway (yaad rakho)

1. **5 steps:** clone → Cursor → `uv sync` → OpenAI key+billing → `.env`.
2. **UV = minutes, not hours** (vs Anaconda).
3. **API key copy karke seedha `.env` mein** — Notepad trap se bacho.
4. Mac user = ye skip, L05 dekho.

---

<details>
<summary>📜 Full English Transcript (original, click to expand)</summary>

Well, if you're a PC person, then you've come to the right place. This is for you. If you're not a PC person, then get out — you're not welcome here. All right, with that out of the way. Hello. This is the video when we actually get to set up your environment, and there are going to be five steps to doing this. The sixth one will be somewhat optional. There will be a sixth step, but the five main steps we are going to do, and they are going to be covered in my repo very clearly. And let's start by going there. We're going to go to the repo that is linked in the course materials. It's at GitHub. And here it is. And when you go there you see the different directories, the different folder structure that we have. And if you scroll down you get what's known as the readme, the set of information that comes with the course. And I ask you, I plead with you, to read the readme. I put a lot of care into the readme. It's got lots of great stuff in there, so do take a look through it and it will set you up to be successful. In addition to another link to my LinkedIn (I'm starting to sound a bit desperate about this), there's also lots of useful things, and most importantly, there's links to the setup instructions — the Windows setup instructions, the Mac and the Linux ones. And I'm not going to take you through them right now because this will be a living, breathing document that I will keep updated as people hit problems. But you should go through that and have that side by side. If anything, that's going to be better than this video. See this video as bringing it to life, but the instructions will be bulletproof.

So it's time for step one. And just before starting step one, I do want to draw your attention to a section at the top of the setup PC guide that's called gotchas, and it has a few of the common traps that can happen when setting things up for PCs. One of them is an insidious problem with Windows sometimes being set up to not allow names of files longer than 260 characters. And if that is set on your system, then you need to unset it so you are allowed longer filenames. And that's something which there are instructions for how to do. Another common trap is around antivirus software that can interfere with the installation. So there's some steps there as well. So please do look at those gotchas because they will set you on a good path.

All right. Step one is about cloning the repo using git. And to get started, if you go to the start menu and you then type PowerShell, you should be able to open up a PowerShell. Let me get rid of the other one that's running here. So here is a PowerShell. And this is like for running commands in the command line. If you're new to this, one of the guides in the guide folder in the repo contains a guide for using the command prompt that will put you in good shape. But I'm imagining at this point you are familiar. So you know that there could be a projects directory. Most people have created a projects directory, which you should go into. If you don't already have a projects directory, then you should create one with mkdir projects within your home directory. So you will then have, like I do, a projects directory within your home directory. And if I look at the contents of it, it has my LLM engineering folder from my other course, and it has some test folder. And it is this folder that we're going to clone our new repo into. First we need to check that we have git installed — git for code management. And you can do that by typing git --version. And we'll see that I do indeed have git installed. If you don't have git installed and that has an error message, then you can go to Git's website (there's a link in the setup instructions), go to downloads and to Windows, and you can click here to download the latest version for Windows. And the installation instructions should be crystal clear. You might need to open up a fresh PowerShell — always worth knowing that you might need to do that, and sometimes you need to restart your computer. Super annoying, but hopefully not. You should be able to type git --version and see git in there.

Okay, so the next thing to do is to actually clone the repo. So we go to the repo itself. The first thing we do is we go to this green button on the top right of the repo, and you click this code button. You select HTTPS and you'll see the web address of this repo. And you press the "copy URL to the clipboard" button. And there we go, I have copied it. And now you come here to the PowerShell. Now again I'm in my projects directory. So you're in your home directory, then your project subdirectory. If your C drive is quite full, then you might want to do this on your D drive. Just make sure you're within a projects directory. And you simply type git clone and then paste in there the web address of the GitHub repo. And when we press enter, that runs, does its thing, and it's done. And if I look at that directory, you'll now see that agents is there. I can now go into that directory, agents, and look at it. And here are all of the directories within the repo. And this folder that we're in right now, which is projects\agents — this is what's sometimes known as the project root directory. And that means that we have completed step one of the five-step process.

Okay. So we go right away to Cursor to look at the Cursor IDE, a fabulous platform, and download it and install it if you don't already have it. You can just press the download for Windows button. It will download the executable and you can then run it, and you'll get this setup screen. A familiar kind of setup — accept the agreement, choose where you want it to install, and I choose the C drive, but you could put it on the D drive if you're running out of space. And then next, and then we will create a desktop icon and add it to Windows Explorer. And note that it will make changes to path, which means that we will need to bring up a new command prompt for this to take effect. And then we will install that. So it will now install Cursor on my PC so that we can use this platform. And cursor has now installed. So I can press finish, and it should now be installed and launching on my PC. There we go. It just took a moment. And we can just keep with all of these basics. And I'm going to select to use the word cursor if I want to run it from the command line and say yes okay. And then continue. And I'm going to have it in privacy mode — I'm not going to be logging what I do. And you are all set. So now you can sign up for a Cursor account, which is free, and you just press that sign up button and follow the process.

And so here we are in Cursor. It started, I've signed in, I've actually got a pro trial. And we're looking at the first screen. And I can press Open Project. And what I can now do is navigate — I'm going to go to "This PC" and then to my C drive and then to users and "add" and then projects, which is where my projects are. And here is agents. And this you'll recognize as the directories that we cloned from our repo. And what I can do now is just press this select folder button, which is saying I want this agents folder to be my project root folder. And it opens up. This is your first look inside Cursor. We've got our directories down here. You've got a welcome screen up here — I'm going to X out the welcome screen. And now here we have something called the explorer on the left which has all of our directories. We've got a chat ability to chat with an LLM on the right — I'm also just going to close that down. And what we're looking at here is the code. And in fact, this navigator on the left is showing you a different directory for each of the six weeks of the course, from foundations through to MCP. And if we open this swizzle here, you'll see all of the contents of the first week, foundations, where we are right now.

Okay. We're racing ahead to part three of the setup. Part three, of course, is time for UV, which I'm so excited to show you. So we start by just looking for UV package manager. You'll find it's also linked in the setup instructions. Astral is the name of the company that makes UV. Here it is. And it is an extremely fast package manager, as it tells you. So to install for Windows, you simply run this in a PowerShell. And so I've pressed on Windows, I'm now going to press this copy button to copy that in. And I'm now going to go to a PowerShell. And I'm going to run that command. So here we go. We'll let it do its thing. It's now installing UV. And that appears to have already happened. And it's telling you you can either restart your shell to take this into the path, or you can run those commands. We're going to restart our shell. If we type exit to get rid of that shell, and we start a new shell — and you must remember to do this, otherwise it won't work. So PowerShell again. And now we should have access to UV. And so we can type uv --version. And there we have UV installed on the machine.

Now I'm going to show you this next part within Cursor. Here is Cursor — I actually quit Cursor and reopened it again for the same reason that we did that with a PowerShell, to reset the path variables. And within Cursor, I'm going to go to the view menu and choose terminal. It's also Control and the backtick to bring up a new PowerShell within Cursor, which is a useful thing to do. And that's how we'll do it mostly on this course. And within here, if I do a dir, you'll see the contents of that directory. I'm now just simply going to do the command uv sync, which is my way of telling UV that I want to build an environment consistent with what I have in this directory. And I do that. And what we're seeing now is it's building the environment, and it's actually beginning by installing Python, a dedicated version of Python 3.1-something, which is the version for this project, and it's now installing the packages. Now, people who are familiar with Anaconda know that this process of building a full-specced, isolated environment with the right version of Python is something that can take up to an hour, and sometimes on some systems it was taking an hour and a half to build this environment on their computers. What you'll find is that it's a different story with UV. It's running remarkably quickly, and I'm hoping it's going to finish by the time I finish this sentence. But if not, then I may put you on pause and come right back again, because it literally takes a minute or two and it will be done.

Okay, so it did take about another three minutes, but I didn't lie — it's quick. It's very quick and it's very impressive. And the big news is that that's it. There isn't any more of the kind of configuration management part. Those packages have been installed. If I look in this directory, you'll see that there is in fact going to be a new folder, .venv. It's created a virtual environment. For people that know about Python virtual environments, it's built one, and that now exists in this folder, and that's all there is to it. And going forwards, if we want to run a Python script — whereas you might normally type Python and then the name of a Python script — you now would type uv run and then the name of the script, and it will automatically run it in that environment. And everything else is the same. The environment is built. It's as simple as that. We're pretty much good to go.

And we're now in the end game. We're at step four of the instructions, and it's smooth sailing from here. The next step is to set up a key with OpenAI so that you can use OpenAI directly. If you already have a key, you can just skip this step. If you don't want to be spending money on OpenAI, there are alternatives. As I say, you will find them in the setup instructions and the readme and linked in the guides. So please do follow those instructions. But I do assume that most people are okay to spend a few dollars (it's quite cheap) on using OpenAI, because the power of these frontier models is going to allow us to do great things. And of course, you can use DeepSeek or Google's Gemini or Grok as a straight replacement for any of these.

Okay, so I go to a browser and I go to platform, which is where you get into the API side of OpenAI. And the first thing that you may need to do is sign up. I have already got an account so I can just log in, but you may need to come in and sign up. If I log in, I can come in with my Google credentials. And here I am logged in as me to the OpenAI developer platform. Now there are two things that you need to do. One of them is about setting up billing, and one of them is getting an API key. And we'll do them both now. So in order to set up your billing, you go to the settings menu up here, and then you go down to billing right here. And this is where you choose to put in a credit balance. You can see I've got quite a large credit balance — I seem to spend quite a lot of money on different projects with OpenAI, but this course will only cost you a few dollars. The way that it works is that you do need to put in an amount up front, and $5 as of today is their minimum. So you'll need to put in that $5 and then you spend against it. For people internationally, I know that sometimes OpenAI can be a bore about charging because they charge in dollars and some credit cards don't accept an international charge like that. So there is some nonsense to get around with that. And as I say, there's alternatives like DeepSeek if you want it. Some students use Grok (with a Q at... a "Grok" which is also a great option). And you can also use something called OpenRouter that's quite popular, particularly with international students, because you can set up an OpenRouter account and it will route through to the different models. So these are all different approaches for you, and they work almost exactly the same way. There'll be some sort of billing page like this where you get to choose to top up, and you press add to credit balance to top up with a credit card, and you put in the minimum $5. We won't need any more than that, for sure.

Okay. And so once you've done that, you then have to go to the API keys section. And this is super important. And this is where you get to set keys that will be how you will access this API from your computer. And the way that you'll do that is you'll press create new secret key. You'll put in any name you want — you can call it just to remember it in the future. Make sure that you select project. You have a default project, so it's for everything. Have all permissions, and then press Create Secret Key, and you will get a new key. And you can copy it into your clipboard. And you have to do that to make sure that you preserve it, because we're about to make use of that API key. Now here's a pro tip to be really careful about. When you copy that key into the clipboard, you might be tempted to paste it into another application like a notepad that you will then copy and paste it somewhere else. But there's a trap there. Sometimes these kinds of word processors, when you paste in the key, they'll mess around with it in some way. They'll replace hyphens with long hyphens because they look better in text, and they may replace some characters with international characters that are right for your locale. And if they do that, your key won't work, and it's going to take you ages to figure out what's happened. So be careful of that. Don't do that. I suggest copying it to the clipboard and then immediately doing the next step we're going to do, which is actually using it in our project. So keep that trap in mind. If you do want to paste it somewhere to keep it for your records, then be careful to paste it into a kind of tool that's not going to mess around with the API key.

All right, I hope that makes sense. I hope you've now created your API key. And you've got it nice and safe, and you've recorded it somewhere where it's not messing with the characters, and we're ready to put this to good use. And this is it. We've reached the final step of setting up. Thank goodness. We're back in Cursor. And I've actually pressed X on the PowerShell that was here, so we've got a nice clean screen here on the left. This is the explorer — I've collapsed all of these so that you just see the top level explorer. And what I'm now going to do is right click here and say new file. And I've now got a new file I'm creating at the top level. Make sure that it's at that top level. And I'm going to call it something very specific. And you have to call this file exactly the same thing. And that thing begins with a dot, a period, a full stop as we say in England, and then the letters E and N and V. So it's called dot env, and it has to be called exactly that for a very particular reason that we'll get to later. But as long as you've called it dot and nothing else, then you're in great shape. So that is the name of this file. A dot env file is a common way that people put in environment variables that they want to set just for the purpose of this project, and they will be environment variables that will contain what we sometimes call secrets, or things that we don't want to be public. We don't want it to be checked into source code. We want it to be something that is just for us, kept private, that we will use. And we can just put things in this file of the form of a key name equals and a value, and that will become an environment variable, as you will see.

And in particular, there's one key that we really care about. And you have to do this exactly right. If you make a typo in this, then it's not going to work and it's going to be really frustrating. So try to be really careful with this. I'm going to type "open" and you can see that already the cursor knows what I want to do. See how it's filling it in for me. I could just press Tab to do what it wants, but I'm not going to press tab — you will see, because it's got a dummy key in there, not the key that we want. OPENAI_API_KEY equals. And you can see it's prompting me there, "sk-" dash dash and a number. Now what I want to put in here is something that will indeed start sk-proj and it will have a number, but it's going to be a long number, and it's going to be the thing that I just copied into my clipboard from the previous screen from OpenAI. You need to now paste that key right here, and it's got to look just right. It's got to start sk- and then be followed by that long number and letters, and it's got to have those hyphens in them just as they are. And this is — of the people that struggle with environment setup, most of the problems end up just being this one tiny step. So please get it right.

So hopefully you've done that and you've put that in there and it's got a key in there. Now, if you're using other platforms like DeepSeek, then this is exactly what you will do — the same thing. You'll just put in here deepseek and it will... there we go, it fills it in for me. DEEPSEEK_API_KEY equals. And you might have something else. You might be using Grok the inference platform, or OpenRouter, or any of the others. Any keys that you've got, you simply put them in here like that, and we will use them later. So with any luck, you've put in OPENAI_API_KEY equals and it's got your real key in there, which means that the setup is complete. Many congratulations. That's the painful part over, as long as it all works — and we'll find out. Please skip the next video, which is going to be for the Mac people, the next lecture, and then we will reconvene after that. And I'm so excited to get started.

</details>

---
*Source: Official Udemy lecture transcript (auto-captions, lightly cleaned). Notes in Hinglish for self-study.*
