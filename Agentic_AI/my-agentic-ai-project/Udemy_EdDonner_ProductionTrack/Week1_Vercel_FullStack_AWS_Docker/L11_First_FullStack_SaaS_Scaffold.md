# L11 — Building Your First Full-Stack AI SaaS with NextJS and FastAPI

> **Week 1 · Day 2** · ⏱️ ~10 min

---

## 🎯 TL;DR

Lab shuru: `production` repo ko `git clone` karke Cursor mein kholo, instructions padho, phir `npx create-next-app sass --typescript` se ek **TypeScript Next.js app (Pages Router + Tailwind + ESLint)** scaffold karo. Aaj banane wala app = **business idea generator**.

---

## 🗣️ Hinglish Explanation

"Welcome to the lab for day two. I love the labs." Ab pure hands-on mode.

### Step 1: `production` repo clone karna

1. Browser mein **github.com** kholo, **ed-donner/production** repo par jaao (yahi course ka main repo hai — abhi tum video se zyada cheezein dekhoge kyunki Ed sab push kar dega). git/GitHub naye lagte hain toh `guides/` mein guide hai — foundational knowledge zaroori hai.
2. Green **Code** button → **HTTPS** tab → repo URL ko **clipboard par copy** karo. (Yeh URL repo ko clone karne ke liye hai.)
3. **Cursor** kholo (ya koi bhi IDE — VSCode/Windsurf/PyCharm, sab chalega; Cursor VSCode ka fork hai).

> **git clone kya karta hai (background):** `git clone <url>` remote repo ki ek **complete local copy** banata hai — saara code + poori git history. Iske baad tum offline kaam kar sakte ho aur `git pull`/`git push` se sync rehte ho.

### Step 2: Terminal kholna aur sahi directory mein jaana

Cursor mein terminal toggle karne ke shortcuts:

- **`Ctrl + ` `** (backtick) → terminal on/off
- **`Ctrl + Shift + ` `** → ek **naya** second terminal (right side par terminals ka stack ban jaata hai)

Abhi hum `instant` folder (Day 1 wala) mein hain. Hume **ek directory upar** `projects` folder mein jaana hai:

```bash
cd ..
```

> **Important warning — cloud folders se bacho:** Apni `projects` directory ko **iCloud (Mac) / OneDrive (Windows)** ke andar **mat** rakho. Reasons:
> - Code already **GitHub par replicate** ho raha hai — double replication ki zaroorat nahi.
> - Cloud sync IDE/git ke saath conflicts, weird file-locking, aur performance issues create karta hai.
>
> Critical nahi hai par strongly recommended ki `projects/` plain local disk par ho.

### Step 3: Repo clone karna

`projects` directory mein hote hue:

```bash
git clone https://github.com/ed-donner/production.git
```

Pehli baar **authentication** maang sakta hai (GitHub login/token). Ho jaane par `cd` karke andar jaa sakte ho:

```bash
cd production
ls
```

Ab tum ek **local copy** ke "proud owner" ho.

### Step 4: `production` ko project ke roop mein kholna

1. Cursor mein **File → New Window**
2. **Open Project** button → `projects` directory mein navigate → **production** folder select → **Open**
3. Naya window khulta hai with `production` project open
4. Left mein **Explorer** (file tree) dikhega — na dikhe toh **View** menu se kholo. AI chat panel band kar do (clean look)

Andar **`week1`** directory hai — usme har **day** ki ek file hai. Day 1 wali do files hum pehle online dekh chuke. Aaj **Day 2** se shuru.

#### Markdown preview kholna

`day2` file par click karne se **raw markdown** (ugly format) dikhta hai. Isliye:

- File par **right-click → Open Preview**
- Properly rendered markdown aa jaata hai

> Kabhi-kabhi Cursor ek **markdown extension** install karne ko bole — woh prompt aaye toh install kar lo. Usually built-in hota hai, prompt nahi aata.

Ab "Day 2" instructions screen par hain — yeh hamari **recipe** hai.

### Plan of Attack (Week 1 ka roadmap, dobara)

| Day | Kya banayenge |
|---|---|
| **Day 2 (aaj)** | Pehla **frontend + backend** app — business idea generator |
| **Day 3** | **Authentication** (sign-in) + **subscription** add |
| **Day 4** | Proper **business functionality** — toy se aage ek real SaaS, **Vercel** par deployed |
| **Day 5** | Sab kuch **AWS** par deploy |

### Aaj ka app: Business Idea Generator

Ek simple app jo **LLM** se ek **naya business idea** generate karta hai (generative text — wahi cheez jisme LLMs best hain). Ed encourage karta hai: ise apna banao — koi aur cheez generate karwana ho toh prompt badal do. "Twisting things around, making it your own is what this course is all about." Pehle as-is chalao, phir experiment.

#### Tech stack (aaj)

- Modern **React frontend**, **Next.js** se bana
- **Pages Router** (App Router nahi — auth ki wajah se)
- **TypeScript**
- **FastAPI Python backend** se connect
- **Streaming** — AI ka response jaise-jaise aaye, nicely render ho (yeh agle lecture/Day mein refine hoga)
- **Deployed to production** (Vercel)

### Step 5: Naya Next.js project scaffold karna — `create-next-app`

1. Naya terminal kholo
2. Ek directory upar `projects` mein jaao:

```bash
cd ..
```

3. **Pre-requisite: Node installed hona chahiye** — yeh Day 1 par install kiya tha. Day 1 skip kiya toh `create-next-app` kaam nahi karega; pehle Node install karo.

> **create-next-app kya hai (background):** Yeh ek official Next.js scaffolding tool hai (ek **node command**) jo poori application boilerplate ek command mein set up kar deta hai — folder structure, config files, dependencies, sab. `npx` (npm ke saath aata hai) latest version ko bina permanently install kiye chala deta hai.

```bash
npx create-next-app sass --typescript
```

- **`create-next-app`** → "mere liye poori application set up karo"
- **`sass`** → app/project ka naam (Software as a Service — commercial app jisme subscription hoga)
- **`--typescript`** → JavaScript ki bajaye **TypeScript** variant

#### Interactive prompts ke jawab

`create-next-app` kuch sawaal poochta hai — exact answers:

| Question | Answer | Kyun |
|---|---|---|
| Which **linter** would you like? (**ESLint**) | **ESLint** (Yes) | Linter = code quality rules checker; ESLint comprehensive hai |
| Would you like to use **Tailwind CSS**? | **Yes** | Styling framework — bahut easy bana deta hai (aage detail) |
| Would you like a **`src/` directory**? | **No** | Bade projects ke liye structure detail karta hai; hume zaroorat nahi |
| Would you like to use the **App Router**? (recommended) | **No** | Auth framework App Router support nahi karta — **Pages Router** chahiye |
| Would you like to use **Turbopack**? | **No** | Fast packaging framework, par aage ek special cheez karni hai isliye traditional approach |
| Would you like to **customize the import alias**? | **No** | Default theek hai |

> **Linter kya hai:** Ek tool jo tumhare code ko **rules** ke against check karta hai (style, common mistakes, unused vars) bina chalaye. **ESLint** JavaScript/TypeScript ka standard linter hai.

> **Tailwind CSS kya hai:** Ek **utility-first CSS framework**. Purane din mein tumhe lambi-lambi CSS likhni padti thi (styling "ek strange dark art" hai). Tailwind ready-made utility classes deta hai (jaise `text-2xl`, `font-bold`, `p-4`) jo simple descriptions hain — tum bas markup mein class names laga ke style karte ho. Mimic/copy-paste karke aage chalega.

> **Turbopack kya hai:** Next.js ka naya, super-fast bundler (Webpack ka successor). Yahan intentionally skip kiya jaa raha hai kyunki Day 2 ke end mein kuch special (Vercel auto-detection) karna hai jo traditional setup ke saath fit hota hai.

#### Result

Sab install ho jaata hai aur app **`/Users/<you>/projects/sass`** par ban jaata hai (note: koi `OneDrive`/`iCloud` path nahi — plain local disk). Tum ab apne Next.js app ke "proud owner" ho. Agla step: ise Cursor mein **naye window** mein kholo (jaise `production` ko khola tha).

---

## 📋 Key Concepts

| Concept | Matlab |
|---|---|
| **`git clone <url>`** | Remote repo ki complete local copy (code + history) banata hai |
| **Code → HTTPS → copy** | GitHub par clone URL paane ka tareeka |
| **`Ctrl + ` `** | Cursor mein terminal toggle (backtick, apostrophe nahi) |
| **`Ctrl + Shift + ` `** | Naya additional terminal kholna |
| **Cloud folder warning** | `projects/` ko iCloud/OneDrive mein mat rakho (double-sync/conflicts) |
| **Open Preview** | Markdown file par right-click → rendered version dikhata hai |
| **`npx create-next-app`** | Ek command mein poori Next.js app scaffold karta hai |
| **`--typescript`** | TypeScript variant chuno (JS ki jagah) |
| **ESLint** | Code-quality linter (rules ke against check) |
| **Tailwind CSS** | Utility-first CSS framework — class names se styling |
| **Pages Router** | `create-next-app` mein App Router ko **No** bolke chuna jaata hai |
| **Turbopack** | Next.js ka fast bundler — yahan skip (special end-of-day reason) |

---

## 💼 Backend Dev Ke Liye Note

Python backend dev ke liye yeh lecture **JS-world ke tooling parallels** establish karta hai. `npx create-next-app` tumhare Python world ke `cookiecutter`/`django-admin startproject`/`fastapi` template-generators jaisa hai — ek command mein opinionated boilerplate. `npx` ko `pipx run` ki tarah socho (install kiye bina ek package chalaana). **ESLint** = `ruff`/`flake8`/`pylint` ka JS equivalent; **Tailwind** ka utility-class approach tumhe shaay-d naya lage par yeh inline-config-over-stylesheet philosophy hai. Sabse practical: **cloud-sync folders se bacho** — yeh advice tumhare Python virtualenvs/`node_modules` par bhi double lagti hai, kyunki bade dependency trees iCloud/OneDrive ko choke kar dete hain aur git index corruption tak ho sakta hai. Aur dhyaan do: scaffolding ke deliberate "No"s (src dir, Turbopack, App Router) yeh dikhate hain ki **production setup mein har default ka conscious choice hota hai** — blindly defaults accept mat karo, downstream constraints (yahan auth framework) ko aage soch ke decide karo.

---

## ✅ Takeaway

- **Lab flow:** `production` repo → green **Code → HTTPS → copy** → terminal mein `git clone` → Cursor mein **New Window → Open Project**
- `projects/` directory ko **iCloud/OneDrive ke bahar** rakho; markdown instructions **right-click → Open Preview** se padho
- App scaffold: `npx create-next-app sass --typescript` — pre-requisite **Node** (Day 1)
- Prompt answers: **ESLint Yes, Tailwind Yes, src No, App Router No (Pages Router chahiye), Turbopack No, alias No**
- Aaj ka target: **business idea generator** — Next.js (Pages Router, TS, Tailwind) frontend + FastAPI backend + streaming, deployed to Vercel

---

<details>
<summary>📜 Full Transcript (English)</summary>

Oh, welcome to the lab for day two. I love the labs. So the first thing I've done is I've brought up a web browser and I have gone to github.com. GitHub.com. And this is where we've already been. But this is where we're going for this production repo, which is the repo for the whole course. We'll be making lots of specific ones. And you'll see a lot more than this, because I haven't pushed everything to GitHub yet. And if you're not sure about GitHub and git, there's a guide on that. Please do read the guide. It's important to have that foundational knowledge. So when you're here you go to the green code button. You click here and you choose Https for for. And you copy this to the clipboard. And this is copying a link to this repo into your clipboard. And then once you've done that open up cursor. You don't need to use cursor for this course. You can use any IDE that you like. Uh any if you use any other VS code clone. This is a fork of VS code. It's going to look really similar so you can use VS code itself. Cursor windsurf, anything like that. But also you can use PyCharm or whatever, whatever you like. Anyways, I'm just in the same instant project that we used last time. You can be in any project in cursor, and I'm going to open a terminal in which you can do by pressing Ctrl and then the Backtick button, and up comes a terminal that that toggles on and off the terminal. Like this. It's also worth knowing if you press Ctrl shift Backtick, you get a second new terminal that appears and there's like a stack of terminals over on the right here. So that's just something to to to keep in mind. I often do that. It's more useful to open a terminal. Now, right now we're in a directory called instant. And I want to go up one to to my project's directory which is right here. And you probably have a similar projects directory. If not you might want to create one. And again there's a guide that talks you through some, some of this sort of command prompt stuff. Um, and one thing to keep in mind is that your project's directory. It's best if that's not part of a cloud directory like OneDrive. If you're a windows person or iCloud, if you're a mac person, it's best not to have this be on your iCloud or OneDrive, not to have that in in your path. Um, for for this directory, because you don't actually want to replicate your projects up to the cloud because it's already replicated to GitHub. You don't want to do sort of multiple replications. And there are some other reasons too, but that's one of them. Uh, so it's not super critical, but better if you don't have your project's directory as a OneDrive or an iCloud subdirectory. Okay. So we're in projects, and what I'm now going to type is git clone. And then the name of the production repo. There it is. And I press enter. The first time you do this you might have to do some authentication stuff, but it should all come back here. And you've now cloned the repo and you can CD into it and to see that it's all there. There is the production repo, and I'm imagining you'll see a lot more, because I'll have built that out by the time you see it. And you're now the proud owner of a local repo, a local copy of the repo, and we're going to open that as a project. So within cursor, go to the file menu and choose New Window. And then you press the Open Project button. And you navigate within your project's directory to production. And then press open. Once you've once you've opened up a production. But because I've already done that actually, I will show you. Just so you see, you press open project, you go into projects and then you find the production folder. Look how many projects I've got hanging around from different things I've done here. Go into production and then you press open and at this point it opens it up as a new window. Like this. You've now opened the production project. Uh, and so on the left here is the explorer. If you don't see this file Explorer, then you can open that from the view menu. If you have an AI chat here, you can you can exit out so that it looks nice and clean. And there's a week one directory. You should have more directories too. Uh, I only just have the week one here. When I open up the week one directory, you'll see that there are different files for each day of the week of week one. You may remember that we've already looked at a couple of these online, and we're going to be starting today with day two. Now if I click on day two, I see this rather ugly format, which is the sort of raw markdown. So you have to remember to right click on it and say open preview. And when you do that, it should come up really nicely like this. And now we're seeing the proper markdown version of this page. It's just possible that you might have to install a cursor extension, a markdown extension that will prompt you, and you might have to install that. I don't think so, but if it does prompt you that you need to install an extension to see the preview, then then by all means do that. But I think this should just come up right away. I think that that's built in. So here it is. This is our instructions for day two. And it's quite enough chit chat. Let's get to it. Let's let's follow this recipe and build ourselves a SaaS AI application. So the plan of attack is that for today we're going to build our first front end back end application tomorrow in day three. We're going to juice it up quite a lot by adding in user authentication so users can sign into it and even subscription. And then in day four we're going to add in some proper business functionality. It's fairly simple. That will take it below the sort of toy that we're going to build today. Uh, and that will, that will complete by day for a business SaaS application deployed to Vercel and day five. We're then going to take all of that and deploy it to AWS. We're doing all of that in our first week. All right. So let's let's get into it. So we're going to build today a business idea generator. Uh pretty simplistic app that allows you to generate a new business idea using an LLM to do the generation generative text being what they're good at. And by all means you can change this to be doing something a bit different. Like if there's something else that you'd like to ask the LLM that it could generate, then then, then go for it. Twisting things around, making it your own is what this course is all about. So please do see the freedom to be changing this as you want. Uh, but first maybe get it to work as it is, and then. And then start playing with it. Okay, so we're going to be using a modern react frontend built with Next.js. We'll be using the pages router, not the app router. We'll be using TypeScript. It's going to be connecting to a fast API Python backend. We're going to be using streaming so that what comes back from the AI looks really nice as it appears. Uh, it's going to render nicely and it's going to be deployed to production. Okay. So here we go. Are you ready for this? The first thing we're going to do is is open up a new terminal, which I'm going to do like this. And now we're going to create a new project. So we're going to create a like a new repo. So we start by going back up a directory. So we're now in our projects directory. And the next thing we're going to do is run this command which is going to create a new application for us using uh create next app. And so uh, we'll, we'll uh, we'll do that in just a second. And just to check, you need to have installed node before we do this next step. Uh, and installing node was actually something we did on day one. So if you skip day one for some reason you missed installing node. And this isn't going to work unless you already have node. So you do need to install node js on your platform. And then you can run this command. Remember you should be in the projects directory your your directory that has all of your different projects in it. So this command is a node command create next app which means set up an entire application for me. You give it a name. We're calling it sass. Sass the word for software as a service. It means like a commercial application that users will pay subscription to have access to. Business users and that minus minus TypeScript. This is saying that we want the TypeScript variation, not the original JavaScript variation. Okay, so I run this and ask me some questions. First of all, which linter would you like a linter or something? Which which has some rules to check your coding to make sure that it's good. Uh, es lint is quite comprehensive, and we're going to pick that. Would you like to use tailwind CSS? I haven't talked about tailwind, but we will talk about it a lot. Tailwind is a fantastic framework of styling. It makes styling your pages incredibly easy. Much much easier than than than the old days. Uh, so yes, we'll definitely use tailwind. Would you like to put your code inside a source directory that makes the directory structure perhaps, uh, more detailed, better for really large projects, but we don't need that, so no to that. Would you like to use the app router recommended. Well, we'd love to use the app router, but it turns out that that won't work this week because it won't go with our authentication framework. So no, we're going to use the pages router. The original pages router. So we say no to that. Would you like to use turbo PAC which is something which which is a really fast packaging framework. We're not going to use it this time because because of something special we're going to do at the end. So so just say no. We're going to have a traditional approach. And would you like to customize the input alias? We'll say no to that too. And everything is being installed for us. And any second now it will be. I'll be able to congratulate you on being the proud owner of your own Next.js app. So that's already happened. It's been created at users projects for you. It'll be your projects directory and then sass. See how there's not not a OneDrive or an iCloud in there. We're just on the on the computer itself. Uh, and that's been created with a whole bunch of stuff. And the next thing to do is to go and open that in cursor, just like we just did for production, so that we're opening up a new window with this project.

</details>
