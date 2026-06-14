# L01 — Instant AI Deployment: Your First Production App on Vercel in Minutes

> **Week 1 · Day 1** · ⏱️ ~14 min

---

## 🎯 TL;DR

Course ki shuruaat objectives/intro se nahi — **instant gratification** se hoti hai: pehle hi lecture mein hum ek FastAPI app ko **Vercel** par production mein deploy kar dete hain, sirf 3 files (`instant.py`, `requirements.txt`, `vercel.json`) aur 3 commands (`npm i -g vercel`, `vercel login`, `vercel .`) ke saath.

---

## 🗣️ Hinglish Explanation

### Ed ka style: pehle deploy, baad mein baatein

Yeh Production Track (Ed ke curriculum ka **course #6**) ka Day 1 hai. Normally courses objectives, curriculum, logistics se shuru hote hain — Ed bolta hai *"that's not my jam"*. Hum seedha kuch **production mein deploy** karenge, phir theory hogi. Agle 4 weeks ka mission: **AI ko production-grade banana**.

Instructions GitHub repo mein hain — `github.com` par **ed-donner/production** repo, uske andar `week1` folder, file **"day one instant gratification"**. Do important disclaimers Ed deta hai:

1. **Repo constantly updated hota hai** — jo tum dekhoge wo video se richer/different ho sakta hai. Don't panic, wo improved version hai.
2. **Websites region/time ke hisaab se alag dikh sakti hain** — screen ke cues padho, figure out karo, stuck ho toh Udemy par message karo.

### Step 1: Vercel kya hai aur signup

**Vercel** ek cloud platform hai (Next.js banane wali company ka product) jo **build aur deploy** ko ridiculously easy bana deta hai. Tum code do, Vercel khud build karta hai, **serverless infrastructure** par deploy karta hai, HTTPS URL de deta hai — koi server provision nahi, koi nginx config nahi, koi SSL certificate manually nahi. Concept samjho:

- **Traditional deployment**: VM lo → OS setup → Python install → gunicorn/uvicorn chalao → nginx reverse proxy → SSL → monitoring. Ghanton ka kaam.
- **Serverless (Vercel-style)**: code push karo → platform har request par ek **serverless function** spin karta hai → auto-scale, pay-per-use, zero idle servers.

Signup flow:
1. Vercel link kholo → **Sign Up** → "I'm working on personal projects" select karo (Hobby/free plan)
2. Naam do → Continue
3. Authentication choose karo — **Google / GitHub / GitLab / Bitbucket** — *"pick your poison"*. (GitHub recommended hai practically, kyunki baad mein repo-based deploys easy ho jaate hain.)

### Step 2: Cursor IDE install + project banao

**Cursor** ek AI-powered IDE hai jo **VSCode ka fork** hai (Windsurf bhi VSCode fork hai). Agentic Track wale already familiar hain. Koi bhi IDE chalega — VSCode users ko sab kuch same lagega.

1. cursor.com → **Download** (Mac/Windows auto-detect) → installation wizard mein defaults select karo
2. Cursor kholo → `File > New Window` → **Open Project** button
3. Home directory mein `projects` folder (convention hai), uske andar **New Folder** → naam `instant` → **Open**
4. AI chat panel band kar do — abhi AI se baat nahi karni, sirf files banani hain

### Step 3: FastAPI app — `instant.py`

**FastAPI** ek modern Python web framework hai — ek **app server** jo web requests ka jawab Python code chala kar deta hai. Yeh ASGI-based hai (async support built-in), type hints use karta hai, aur auto docs (`/docs` par Swagger UI) generate karta hai. Flask ka modern, faster cousin samjho.

Explorer mein right-click → **New File** → `instant.py`, aur GitHub instructions se code paste karo:

```python
from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def read_root():
    return "Live from production!"
```

Breakdown:
- `app = FastAPI()` → application object banta hai jo saari routes hold karta hai
- `@app.get("/")` → decorator bolta hai: jab koi **GET request** root route (`/`) par aaye, toh yeh function chalao
- Function string return karta hai → FastAPI use JSON response bana ke bhej deta hai

⚠️ **SAVE KARNA MAT BHOOLO!** Ed specifically warn karta hai — yeh Google Doc nahi hai, auto-save nahi hota. `Cmd+S` (Mac) / `Ctrl+S` (Windows). Tab par **white blob/dot** dikhe matlab unsaved file hai. Aadhe "kuch kaam nahi kar raha" wale issues unsaved files ki wajah se hote hain.

### Step 4: `requirements.txt`

Yeh file Python package dependencies list karti hai — deploy ke time Vercel isse padh ke `pip install` karta hai:

```
fastapi
uvicorn
```

- **fastapi** → framework khud
- **uvicorn** → **ASGI web server** jo FastAPI app ko actually serve karta hai. FastAPI sirf framework hai (request handling logic); uvicorn wo server hai jo network port par sunta hai aur requests ko app tak pahunchata hai. Locally tum `uvicorn instant:app` chalate, Vercel par platform yeh handle karta hai.

### Step 5: `vercel.json` — deployment configuration

Yeh file Vercel ko batati hai ki **kya build karna hai aur requests kahan route karni hain**:

```json
{
  "builds": [
    { "src": "instant.py", "use": "@vercel/python" }
  ],
  "routes": [
    { "src": "/(.*)", "dest": "instant.py" }
  ]
}
```

Do sections (Ed bolta hai intuition develop karo):
- **`builds`** → "`instant.py` ko `@vercel/python` runtime se build karo" — yaani Python serverless function banao
- **`routes`** → "`/(.*)`  — yaani **koi bhi incoming path** — usse `instant.py` ko de do". Regex `(.*)` sab kuch match karta hai, toh saari requests hamare FastAPI app par jaati hain, aur FastAPI internally apni routing karta hai

### Step 6: Node.js install

Ruk — Python app ke liye **Node** kyun? Kyunki **Vercel ka CLI tool ek npm package hai**. Node = server-side JavaScript runtime; **npm** = Node Package Manager (Python ke pip jaisa, JS world ke liye).

1. nodejs.org → official download page → Mac/Windows choose karo, **defaults + latest version** recommended
2. Cursor mein **terminal** kholo: `View > Terminal` ya `Ctrl + ` ` (backtick — apostrophe nahi!)
3. Verify karo:

```bash
node --version    # Ed ko v24.4.1 mila — tumhara newer ho sakta hai, koi dikkat nahi
npm --version
```

Dono version numbers print hue = Node installed.

### Step 7: Vercel CLI install, login, aur DEPLOY 🚀

```bash
npm i -g vercel
```

`-g` = global install, taaki `vercel` command kahin se bhi chale. **Warnings aayengi — ignore karo.** Ed ka golden rule: *"be somewhat immune to warnings"* — note kar lo (debugging mein clue mil sakta hai), par unse daro mat. Errors alag cheez hain, warnings normal hain.

```bash
vercel login
```

Wahi method choose karo jisse Vercel par signup kiya tha (Google/GitHub/etc.) — browser khulega, authenticate karo.

Ab **the moment of truth** — confirm karo ki terminal `instant` folder mein hai, phir:

```bash
vercel .
```

(`.` = current directory deploy karo.) CLI interactive questions poochta hai:

| Question | Answer |
|---|---|
| Set up and deploy? | **Y** (yes) |
| Which scope? | Default — "\<Your Name\>'s projects" (signup ke time bana tha) |
| Link to existing project? | **N** (no — fresh project hai) |
| What is your project's name? | `instant` (dobara kar rahe ho toh `instant2` — naam unique chahiye) |
| In which directory is your code located? | `./` — bas **Enter** dabao |
| Change additional project settings? | **N** |

Phir Vercel kaam karta hai: do cheezein create hoti hain — `.gitignore` file aur `.vercel` folder (project metadata; `.gitignore` usse git se exclude karta hai). Build chalti hai, aur output mein **"Production"** ke saath ek **URL** aata hai.

### Result: LIVE FROM PRODUCTION

Terminal mein URL par `Cmd+Click` (Mac) / `Ctrl+Click` (Windows) → browser khulta hai → screen par **"Live from production!"**. Tumne abhi-abhi internet par ek app deploy kar diya — minutes mein.

Haan, abhi yeh "AI app" nahi hai — bas ek string return karta hai. Par yeh **foundation** hai: isi base par hum pehla production AI app deploy karenge. Small steps.

---

## 📋 Key Concepts

| Concept | Matlab |
|---|---|
| **Vercel** | Cloud platform jo build+deploy instantly karta hai — serverless, auto-SSL, auto-scale |
| **Serverless deployment** | Server provision nahi karna; platform har request par function chala deta hai, pay-per-use |
| **FastAPI** | Modern async Python web framework — routes define karo, JSON auto-handle hota hai |
| **uvicorn** | ASGI web server jo FastAPI app ko serve karta hai (framework ≠ server) |
| **requirements.txt** | Python dependencies ki list — deploy par `pip install` isse hota hai |
| **vercel.json** | Vercel config — `builds` (kya build karna) + `routes` (requests kahan bhejni) |
| **Node.js / npm** | Server-side JS runtime / uska package manager — Vercel CLI npm se install hota hai |
| **Cursor** | AI-powered IDE, VSCode ka fork |
| **`vercel .`** | Current folder ko Vercel par deploy karne ka command |
| **`.vercel` folder** | Project link metadata (auto-created, git-ignored) |

---

## 💼 Backend Dev Ke Liye Note

Python backend dev ke liye yeh lecture ek **deployment paradigm shift** hai. Tum FastAPI already jaante ho — naya part yeh hai ki `uvicorn` ko khud chalane ki jagah Vercel tumhare app ko **serverless function** mein wrap kar deta hai. `vercel.json` ko nginx config + Dockerfile + systemd unit ka ultra-light replacement samjho: `builds` = "image kaise banegi", `routes` = "reverse-proxy rules". Yeh PaaS approach (Heroku-style DX, lambda-style execution) prototypes/MVPs ke liye killer hai; baad mein Week 1 Day 5 par hum same app ko Docker + AWS App Runner par le jaayenge — tab traditional containerized deployment se comparison clear hoga. Abhi note karo: **cold starts, stateless functions, no background workers** — serverless ki classic constraints yahan bhi apply hoti hain.

---

## ✅ Takeaway

- **Deploy first, theory later** — Day 1 par hi production deployment ho gaya: 3 files + 3 commands
- File trio yaad rakho: `instant.py` (FastAPI app) + `requirements.txt` (fastapi, uvicorn) + `vercel.json` (builds + routes)
- `npm i -g vercel` → `vercel login` → `vercel .` — bas yahi deployment pipeline hai
- **Files SAVE karo** (white blob = unsaved) aur **warnings se immune raho** — yeh do habits poore course mein bachayengi
- GitHub repo (ed-donner, production) hamesha video se zyada updated hota hai — wahi source of truth hai

---

<details>
<summary>📜 Full Transcript (English)</summary>

This is a big moment. This is the start of the juiciest course I've ever made. Welcome to the beginning of generative AI and Agentic AI in production week one, day one. The next four weeks are about taking AI and putting it into production, making it production grade. But wait, before we get started, I must stop you right there. It is super important in these kinds of courses to begin with. Objectives, introduction, curriculum, logistics to set you up for success. But no, people have taken my courses before. Know that that is not my style. It's not my jam. We will not start with objectives or introduction or curriculum or logistics. We will start with instant gratification by getting straight into it. Let's go ahead. Before we do any talking, let's deploy something to production right now. And so let's get to it. Instant gratification. We're going to begin in a web page in a GitHub web page at this site it's github.com. And I'm going to put this link wherever I possibly can. So you find it easy to find this link. It should be in the Udemy resources. If you can't find it then you might have to type it in, but it will be there somewhere. Look for it. Editor Donna production. That's the repo in GitHub and go into the folder called week one and then look at the file called day one instant gratification. And let me tell you two things right away. First thing is that what you see when you do this might look different to what I've got in the videos. And that's because I constantly update this as people have any kind of snafus doing this. I will keep it up to date and keep it with the latest information. So what you see when you do this might be richer than what I do here. It will only be improved, so don't worry if it looks a bit different. Also, as we go through these instructions, when you do it, if you have a slightly different experience on a different website, then don't worry about it. It's possible that in different regions, some of these websites look a bit different. It's also possible that they've changed over time. See if it fits. Easy to figure out what you're supposed to do. Just read the cues from the screen and try and just follow along. Figure it out and if not, then message me in Udemy and we'll figure it out together. All right, with that in mind, let's get to instant gratification. We are going to make a production deployment in a matter of minutes. All right. Step one is to sign up for something called vercel. You may be wondering what Vercel is. You'll see it in just a second. Follow this link here to vercel. Let's have a look. Vercel is something which allows you to build and deploy on the cloud. It's an incredibly easy to use cloud infrastructure service that lets you build and scale AI apps and deploy them really, really quickly. All right. The first thing we're going to do is click sign up. Up here it says your first deploy is just a sign up away. I'm going to set I'm working on personal projects. I give myself a name. I say continue and you now get to an authentication screen where you can choose to authenticate using Google, using GitHub, GitLab, if you have that, Bitbucket, if you have that pick your poison, go through, sign up for an account, and then follow the rest of the instructions that are on the GitHub page so that you now have your own Vercel account and you're now hopefully a proud owner of your own Vercel account. Next step is to install the IDE that we will use, which is cursor. Uh, for those that were on my Agentic course you're already very familiar with this. For others, here are the instructions to install cursor. If you'd rather use a different IDE. That's that's totally fine for sure. Uh, any IDE will do. And of course, if you use something like VSCode, cursor is itself a fork of VSCode, as is windsurf, so it will be very familiar to you. basically the same instructions. So visit cursor and over here is cursor. And then you can press the download button. Or for me it's download for Mac OS. If you're on windows you'll see download for windows. And there are then instructions to set up your cursor account. But you're basically selecting the defaults through the installation wizard. And then when you get to the end of that, it will be time to open up cursor in a terminal and create a new project, which you do by clicking on the, the new, uh, and then we will create one called instant. And we'll do that together right now. So when you open up cursor, it might look just like this. Or you might have to go to file and then new window to see it looking just like this. And when it does you press the open project button. And up comes like a dialog like this. And now we want to create our project somewhere. It's normal to have a folder called projects within your home directory. So that's what I'm going to do on a PC. The experience is slightly different. This is a mac, but I'm sure you're used to these these kinds of dialogues to pick and you create projects if you don't have it using the new folder button. And then then what you now do is now that I'm in this, this directory, I'm going to create a new folder and I'm going to call my new folder instant, which is going to be the name of our project right now. Here it is. We're in a folder called instant. And now I say open. And that means that we've created a new fresh project called instant that's ready for us to work in. I'm going to close this screen here, this chat, because we're not going to chat with the AI. We're looking right here at the Instant Project in cursor and looking back at our instructions that are in GitHub. We're now on step three, which is to create a fast API application. I imagine that most of you have come across fast API, but those that haven't. This is a Python server that acts as an app server. So it can it can respond to different web requests by running Python code. And in this case, this is a simple piece of, of a simple server that we'll look on a route, just the slash route. And if something calls that slash route it will return the text live from production. So we can copy this to the clipboard by pressing the little copy symbol there. And we're now going to go back into cursor to create a new file called instant.py. Okay, let's do it. Let's go over to cursor right now. Here it is on the left. Here is this very blank file area. If this isn't showing for you, you might need to go to the view menu to open the explorer to see this. And from here I can right click and say new file and I will call it instant.py instant.py. There it is. And over on the right hand side I'm now going to paste in our code. And there it is. And I'm going to save it. Remember to save people sometimes forget to save files and get super confused when nothing works. Uh, this isn't like a Google doc. You do have to save. It's, uh. I think control s on a windows PC. It's command S on a mac. Be sure to save. You can tell if there's a white blob here that it hasn't saved. Now it has saved. All right. Onwards. Next is an easy one. It's to create a requirements.txt file with this contents. So we copy this file we go back to cursor. Here it is. And now over here we right click new file. We'll call this requirements.txt and our requirements.txt which is where you list your Python package dependencies. And we have two of them fast API itself. And then uvicorn which is going to act as our web server and we save the file. Did you see the blob? See the blobs gone. Command S or control S to save the file. And then we'll go back to the instructions again. Next instruction is to create a file called Vercel. And this is where we tell vessel the The configuration of what it is that we're building. And again, we'll copy it. I'm not going to spend much time going through this. You can check it out, see if you can get some intuition for what it's doing. Vercel dot JSON new file. Vercel dot JSON. There it is and paste in the contents. See the blob that's just there because I haven't saved it. And now I command s ctrl s and it is saved. And you can see here that this JSON has two sections a section on builds and a section on routes that you can see it's going to with, with any anything that's passed in it will be looking at the instant.py Python module to address that. Okay. Let's go back now to the instructions. All right. We're almost there. It's going well. We're on to step six installing node. I imagine many of you have node already installed in your system. If you don't then welcome to the world of node of server side JavaScript. So please then head to the official node download page here. And when you click on that, this will come up. And you can then choose whether you're on Mac or Windows and just I'd suggest sticking with the defaults unless you know otherwise and follow the instructions. Uh, or you can also just download here and installer if you prefer, using installers for your system and for your type of platform. Uh, and I would personally just pick the latest version of node, get that installed and then to check that it's installed, come back to cursor. Now the first thing we want to do is bring up a terminal in cursor. And that's something that you may already know how to do. You can do it from the view menu. You can also do it by holding down the control button and pressing the back tick. Not an apostrophe, but a back tick. And when you do that, up comes a terminal like this. And I should now be able to type node minus minus version. And if I do that I should get that I have version 24 .4.1. Installed on my system and I can also do npm minus minus version, the node package manager and get that number there. You might not get the same version, you might have a more recent version, but all of that is a good sign that you have node installed on your system and that it's time for step seven. Okay, here we go. First step, we have to install vercel using this npm command so that node will install vercel. So I copy that I go over to cursor I'm in this terminal again I'm going to paste in that command and it's going to install vercel on my machine. So while that's running we'll think about the next thing. The next command that we're going to uh, to run is going to be. And by the way, uh, warnings are things that you will encounter a lot on this course. And generally speaking, don't worry about warnings. Note them in case something goes wrong. And it might have given you a clue, but otherwise be somewhat immune to warnings. They happen all the time. Uh, so next thing to do is to do vercel login. That was next on the instructions if you saw it. And when we do that it's going to say login. It's going to let us choose a different mode. Uh and I'm now going to, to do that myself. And you should follow the mode that you used to sign up for vercel. And then, uh, I will see you in a second. Once you're logged in. And now for what we call in the business, the moment of truth, we type vercel space dot making sure that we're currently in the folder instant, which is our project folder. All right. Set up and deploy projects instances. Say yes. Uh, y enter. Which scope should contain your projects? Uh, and, uh, that seems good. Edward Donner's projects. That was a scope that I set up. Uh, the default scope when creating my Vercel account. So hopefully it will give your name and projects in much the same way. That was just from just going through the default screens when signing up for vassal. All right. Uh, link to existing project. Yes. No. So say no, because we're setting up a new project in vassal from scratch. What is your project's name? So call it instant if you happen to be doing this the second time, you could call it instant two. Whatever you want to give it a new name. All right. In which directory is your code located? It's right here. So Dot is the name of the current directory. So we just press enter. Do you want to change additional project settings. And we'll say no. And off it goes. It's created a file two files. You can see a file called. Gitignore which you may know about. And it's created a folder called vassal which presumably contains. Gitignore it's ignoring vassal uh and it's doing stuff. There's things happening uh, and it says that it has deployed. Uh, so next up, let's go and have a look at what we've got. All right. So here we have some information about what's just been deployed. And you'll see that there's the word production. And after that you should see a URL which looks suspiciously like an internet URL. And now, uh, with uh, for a mac, you hold down command and click on this. I think on a PC it would be control and click uh, it should prompt you to follow the link. I'm going to do that right now and click on this. And it's asking me if I want to open it, I do want to open it. And what we're looking at here, everybody is a browser looking at the internet with live from production showing there from something we just deployed to production online. Now, you could be forgiven for saying this is not perhaps yet an AI app per se. Uh, it is just something which is saying live from production, but small steps. This is the basis. This is the first step that we will use to be deploying our first production AI app. Uh, I will see you in the next video.

</details>
