# L13 — Deploying Full-Stack AI Apps with Next.js Frontend and FastAPI Backend

> **Week 1 · Day 2** · ⏱️ ~11 min

---

## 🎯 TL;DR

Frontend wire-up + deploy: `index.tsx` mein `use client` + `useEffect` + `fetch("/api")` se backend call karke `idea` state set karte hain (Tailwind se styled TSX). `_app.tsx`/`_document.tsx` replace karte hain. Phir **no `vercel.json` zaroorat** (defaults match karte hain) — `vercel link` → `vercel env add OPENAI_API_KEY` → `vercel .` se app **production mein LIVE** ho jaata hai.

---

## 🗣️ Hinglish Explanation

### Step 3: Pehla page banana — `index.tsx`

#### `use client` kyun

Pages Router mein by default components **server aur client dono** par chal sakte hain. Par hamare paas **JavaScript server nahi** hai — hamara server poora **Python FastAPI** hai. Isliye har page file ke top par yeh likhna padta hai:

```tsx
"use client";
```

Yeh ensure karta hai ki page **browser (client) mein hi render** ho, server par nahi.

#### `index.tsx` replace karna

`pages/index.tsx` woh pehla page hai jo serve hota hai jab koi website par aata hai. Default content (jo "Welcome to a new Next app" dikhata hai) ko poora select karke (`Ctrl+A`) delete karo, aur naya code paste karo:

```tsx
"use client";

import { useEffect, useState } from "react";

export default function Home() {
  const [idea, setIdea] = useState("loading...");

  useEffect(() => {
    fetch("/api")
      .then((response) => response.text())
      .then((data) => setIdea(data));
  }, []);

  return (
    <main className="flex min-h-screen flex-col items-center justify-center p-24">
      <h1 className="text-4xl font-bold mb-8">Business Idea Generator</h1>
      <p className="text-lg max-w-2xl text-center">{idea}</p>
    </main>
  );
}
```

#### Yeh code kya karta hai

1. **`"use client"`** top par — sab kuch browser mein render ho.
2. **`useState("loading...")`** — `idea` naam ki ek piece of **state** banata hai, initial value `"loading..."`. (`setIdea` se update hoti hai.)
3. **`useEffect`** — React ka hook jo code ko **"jab zaroori ho"** chalata hai; yahan **page first load** hone par chalega (empty `[]` dependency array ki wajah se sirf ek baar).
4. Andar **`fetch("/api")`** — Next.js/browser ka `fetch` function se **frontend backend ko API call** karta hai. Route `/api` (wahi FastAPI route jo `index.py` mein banaya). Jo response aaye, usse `setIdea(...)` se **state** mein daal dete hain.
5. **`return ( ... )`** — yahan se **TSX magic** shuru: ab tak sab TypeScript tha, achanak `return (` ke baad **HTML jaisa markup** aa jaata hai. Yeh React/JSX ki khaasiyat hai — dono blend ho jaate hain.
   - **Tailwind CSS classes** use ho rahi hain (`className="text-4xl font-bold ..."`) — poori styling likhne ki bajaye descriptive class names. Heading: "Business Idea Generator", phir `{idea}` (state value).
6. **React ka jaadu:** Initial render par screen **"loading..."** dikhayega (state ki initial value). Backend se idea aane par state update hogi, aur React **automatically** sirf us part ko **re-render** karke sahi business idea dikha dega.

Ed glossing over kar raha hai detail — yeh frontend course nahi hai. General idea pakdo: ek **frontend webpage jo client par serve hoti hai, TSX mein likhi hai**. Front-end na ho toh LLM se yeh rejig karwa sakte ho — "they're great at this stuff."

### `_app.tsx` aur `_document.tsx` replace karna

`day2` instructions se code copy karke:

- **`_app.tsx`** → select all → delete → paste. Yeh bas **styles import** karta hai aur app draw karta hai (top-level wrapper).
- **`_document.tsx`** → select all → delete → paste. Yeh **overall page document** describe karta hai — `<html>` tag, `<title>` "Business Idea Generator", description, aur `<body>`. Yahan bhi TSX-within-TypeScript pattern dikhega.

### Step 4: Project configure — `vercel.json` ki zaroorat NAHI

Day 1 par humne **`vercel.json`** banaya tha (Vercel ko batane ke liye: frontend kya, backend kya). **Is baar zaroorat nahi.** Kyun?

> Kyunki humne **saare defaults** use kiye — file naam **`index.py`**, top-level **`api/`** folder, **`requirements.txt`** — yeh sab woh conventions hain jo **Vercel automatically detect** karta hai. Yahi reason tha ki naming exactly waisi honi chahiye thi! Vercel khud samajh jaayega aur "just gonna work."

### Step 5: Vercel se link karna — `vercel link`

Naya terminal window kholo. Vercel CLI Day 1 par install ho chuka (`npm i -g vercel`). Phir:

```bash
vercel link
```

> **`vercel link` kya hai (background):** Yeh local project ko ek Vercel project se **connect/sync** karta hai. Deploy karta nahi — bas association banata hai taaki dono in sync rahein.

Interactive prompts:

| Question | Answer |
|---|---|
| Set up "sass"? | **Yes** |
| Which scope should contain your project? | Default (signup wala group) |
| Link to existing project? | **No** (naya banana hai) |
| What's your project's name? | `sass` |
| In which directory is your code located? | `./` (current — Enter) |
| Modify these settings / additional project settings? | **No** |

Aur project **linked** ho gaya.

### Step 6: OpenAI API key add karna

App ko OpenAI use karne ke liye key chahiye. Day 1 jaisa hi:

```bash
vercel env add OPENAI_API_KEY
```

> ⚠️ Agar paste theek se na ho (kabhi-kabhi hota hai), command **dobara type** karo.
>
> ⚠️ **Naam exactly `OPENAI_API_KEY` hona chahiye** (ya jo bhi tumhara model expect kare). Galti se `OPEN_API_KEY` jaisa kuch likha toh "it ain't going to work and it's going to be really hard to find it." Keys ke saath super careful raho.

Command value maangega — wahan apni key **exactly** paste karo (platform se jaise hai). Phir poochhega **which environments** — **saare** select karo:
- Spacebar + down arrow se ek-ek select karo, **ya** sidha letter **`A`** dabao (sab teen environments fill ho jaayenge — Production, Preview, Development)
- **Enter** to accept

> **Environment variables kya hain (background):** Secrets/config (API keys jaise) ko code mein hardcode karne ki bajaye platform mein securely store karte hain. App runtime par `os.environ` se inhe padhta hai. Vercel inhe encrypted store karta hai aur deploy par inject karta hai.

### Step 7: DEPLOY — `vercel .`

Ab final command:

```bash
vercel .
```

Yeh current directory ko Vercel par **deploy** karta hai. Vercel automatically notice karega:

- **Next.js app** hai → frontend recognize
- **`api/` folder + `index.py`** → FastAPI backend hai
- **`requirements.txt`** → kya install karna hai (Python deps)

Sab handle ho jaata hai.

#### Preview vs Production

Vercel ke do environments:

- **Preview** — production se pehle try-out jagah
- **Production** — actual live

Pehli baar (naya project) seedha **Production** par jaata hai. Baad ke deploys pehle Preview par jaate hain, phir alag command se Production par promote hote hain.

Build chalta hai... aur **deployed to production**.

### Result: LIVE 🎉

Cursor se URL kholne ke liye:
- **Mac:** `Cmd + Click` (Ctrl nahi — woh PC ke liye)
- **PC:** `Ctrl + Click`

Browser khulta hai → **Business Idea Generator** dikhta hai. Pehle **"loading..."** (state ki initial value). Background mein **GPT-5 nano** call ho raha hai → business idea aata hai → **bam**, page automatically update! Ed ko mila idea: *"Nexus agent — an agent-as-a-service platform that lets small/medium businesses deploy autonomous AI agent teams to run end-to-end business processes across their apps with governance, safety and explainability"* — kaafi substantive, with metrics to track.

Sabse important baat: yeh ek **Next.js frontend** hai jo **browser mein** chal raha hai, **deployed to production on Vercel**, **frontend + backend** dono ke saath. Simplistic hai (Ed maanta hai), par yeh **foundation** hai jis par aage build karenge — aur sab **Day 2 par** ho gaya.

---

## 📋 Key Concepts

| Concept | Matlab |
|---|---|
| **`"use client"`** | Page file top par — browser (client) par render karwata hai (JS server nahi hai) |
| **`useState`** | React hook — component state banata hai (`idea`, initial `"loading..."`) |
| **`useEffect`** | React hook — code "jab zaroori ho" chalata hai; yahan page load par ek baar |
| **`fetch("/api")`** | Frontend se backend ko API call (wahi FastAPI `/api` route) |
| **`setIdea(data)`** | Response ko state mein daalna → React auto re-render |
| **TSX blend** | `return (` ke baad TypeScript se achanak HTML markup |
| **`_app.tsx`** | Styles import + app draw (top-level wrapper) |
| **`_document.tsx`** | Overall HTML document — `<html>`, `<title>`, `<body>` |
| **No `vercel.json`** | Defaults (`api/`, `index.py`, `requirements.txt`) Vercel auto-detect karta hai |
| **`vercel link`** | Local project ko Vercel project se connect/sync (deploy nahi) |
| **`vercel env add OPENAI_API_KEY`** | Secret env var add (naam exact + saare environments = `A`) |
| **`vercel .`** | Current folder deploy — pehli baar seedha Production |
| **Preview vs Production** | Try-out env vs live env (subsequent deploys pehle Preview) |

---

## 💼 Backend Dev Ke Liye Note

Yeh lecture full-stack request lifecycle ka clean mental model deta hai: **browser** (`fetch("/api")`) → **Vercel routing** → **FastAPI** (`api/index.py`) → **OpenAI** → wapas state mein. Backend dev ke liye teen production lessons. **Pehla — convention over configuration:** `vercel.json` na chahiye kyunki tumne Vercel ki expected filesystem layout follow ki — bilkul wahi philosophy jo AWS Lambda/SAM, Rails, ya `gunicorn`'s app-discovery mein hai. Naming-as-contract pichle lecture se yahan pay off karti hai. **Doosra — secrets management:** `OPENAI_API_KEY` code mein nahi, platform env var mein. Yeh 12-factor app ka core principle hai — config ko code se alag rakho. Vercel ke teen environments (Prod/Preview/Dev) tumhare staging/prod separation ka equivalent hain; key ko sab mein add karna matlab har environment ko apni copy milti hai (ideally alag keys, par yahan same). **Teesra — promote workflow:** pehla deploy seedha prod, baad ke deploys Preview→promote — yeh exactly woh **deployment gate** pattern hai jo CI/CD mein hota hai (Week 2 mein GitHub Actions se automate hoga). Ek caveat jo tum frontend developer ko batana chahoge: `fetch("/api")` same-origin relative URL hai — kaam karta hai kyunki frontend+backend ek hi Vercel deployment par hain, isliye **CORS** issue nahi aata (Week 2 mein jab frontend CloudFront aur backend Lambda alag origins par honge, tab CORS configure karna padega).

---

## ✅ Takeaway

- Frontend wiring: `index.tsx` mein **`"use client"` + `useState("loading...")` + `useEffect(fetch("/api"))` + `setIdea`** — React initial "loading..." dikha ke baad auto-update karta hai
- `_app.tsx` (styles + app) aur `_document.tsx` (`<html>/<title>/<body>`) replace karo; styling **Tailwind classes** se
- **`vercel.json` ki zaroorat nahi** — defaults (`api/`, `index.py`, `requirements.txt`) Vercel auto-detect karta hai (naming exact hone ka payoff)
- Deploy pipeline: **`vercel link`** → **`vercel env add OPENAI_API_KEY`** (naam exact, `A` = all environments) → **`vercel .`**
- Pehla deploy **seedha Production**; result = LIVE Next.js frontend + FastAPI backend business idea generator — foundation for the whole week

---

<details>
<summary>📜 Full Transcript (English)</summary>

So back in our instructions, we're now on step three creating your first page. So just a bit of description here about the pages router. Uh. So by default the different components that you write can run both on the server and on the client. But because we're not going to have a JavaScript server, our server is all Python fast API. So we have to have this this expression use client at the top of each of our pages page to make sure that it runs in the browser. Okay, so the first thing we're going to do is we're going to replace the default contents of the page index TSX, which is the first thing that gets served up when someone goes to our website. And it's going to be this enormous piece of code right here. So let me copy this and then I'll say a few words about it. It's not that enormous index dot TSX. This is the default page that says, you know, welcome to a new, uh, close that welcome to a new next app. So I press Ctrl A to copy everything and I delete it all. We can just select over it, delete it, and then I'm pasting in the code that we've got. So what does this do. It has use client at the top because we want it to be rendered all in the browser. It's going to to it's got it's got something called use effect right here which is a way of writing some code which should run, uh when, when necessary, whenever react thinks that this needs to run, which will happen when, when the page is first loaded. And basically this this code uses a next function called fetch, which means that the front end will make an API call to the server. And where will it look? It will look at this route here back slash API call slash API. And with what comes up it's going to set that as the idea, uh, which is a state a piece of state on the page. I realize I'm glossing over this, but but again, this isn't a course on front end development, so just get the general ideas because you'll be able to play with this. Or if you're not a front end person, you can use an LLM to rejig this as much as you want. They're great at this stuff. And what you see here is a bit of code that returns a web page. And this is where you see this this idea of TSX happening. This whole everything up to this point has been TypeScript. And suddenly we have return open brackets and then it's just suddenly fallen into HTML. It's weird the way the two sort of blend together. So this is this is now like HTML. It's got a heading. What you're seeing here is using tailwind CSS classes. So rather than writing a whole ton of styling, we're just using class names that describe what we want or the heading business idea generator. And then we just have the idea itself. And the magic of react is it's going to show something which will initially say the word loading. And then once that has been loaded from the back end, it will automatically update with the right business idea. Okay, if you're not following the detail here, it doesn't matter. I want you to get an idea that we've got a front end web page that's going to be served on the client, and it's written in this TSX language. And we'll see so many more of these over time that you're going to get you're going to get hardened to this. Okay. Time to go back to the instructions. We now just have to write this underscore app TSX file. So again just copy this go to app dot TSX select everything and paste in the new version. Just something that imports our styles and draws our app. And then back to the instructions again. Scroll down. And now finally we need to to rewrite this underscore document TSX which is the overall description of the page. Select that. And now I'm going to go to document TSX. Click here, select all delete paste in the new version. And here it is. This is the overall document with an HTML tag. Again see the way this is HTML like within TypeScript. It's got a title business idea generator a description. And then the body goes in here. Okay back to the instructions again. It's now time for us to configure the project. We're going to be deploying again to Vercel. You remember in day one we created a file called vessel JSON that described how we wanted Vercel to think about this page, what's the front end, what's the back end, and so on. We don't need to do it this time. And the reason is because we've used all of the defaults, we've used index.py, and we've used everything that Vercel knows to expect. It will automatically detect all of this and just. It's just gonna work, which is amazing. Uh, and so, uh, that's what we're gonna do next. We're now going to link this to Vercel so we can have a project in Vercel, and then we're going to deploy it, and we're going to use it, and it's going to be great. Okay. So first of all, bring up another terminal window. Here we have it. Uh, so hopefully we already installed the Vercel command line interface in day one. If you missed day one go and take day one. Uh, assuming you did, uh, you can now type Vercel link, which is a shortcut to saying I want to set up a project in vassal to match project I've got here, and connect the two together so that they are kept in sync. So I say vassal link and it says setup projects sass. And that seems like a good idea for us. Let me just make sure we're following our instructions. Setup and link. Yes, it now says which scope should contain your project. And you probably remember this from last time. Uh, this is just what it calls the the group of projects, and we just pick the default there. Link to existing project. The answer is no. We don't have an existing project for this. We want to create a new one. What's your project's name? Sass seems like a good name for this project. In which directory is your code located? It's right here and bam! It's done. Uh, okay. So, um, do we. It hasn't done. Do we want to modify these settings? Sorry. Uh, no, we don't want to modify these settings. Uh, do you want to change additional project settings? No. And it's linked now. I declare victory too early now. Bam! It's done. We've created the project and it is linked. Okay. Step six. We now have to add our OpenAI API key. We want to make sure that we can we can use OpenAI. And we did this before. So you'll probably remember this. But the way I'm going to do it is running this command vessel env add OpenAI API key and oh, it didn't paste nicely. If that ever happens to you, then don't do it that way. You may have to retype that particular command vessel env add OpenAI API key. And I know I said it before, but just say it again. It needs to be called exactly OpenAI API key, or it needs to be called whatever your model is expecting if you're using something else, if you make a mistake here, if you call it open API key or something like that, it ain't going to work and it's going to be really hard to find it. So be super careful with these keys. Uh, okay. And when I do this, it's going to ask me for the value. And this is where you will paste in exactly your key, uh, just as it is from the platform itself. And obviously I'm going to have to do that without you here. Otherwise you'll all see my key and you'll bankrupt me. So I'm going to go and do that. When you enter in your key, it's going to ask you which environments and you want to to select them all, which you can do by pressing the spacebar and down button repeatedly, or just the letter A fills in for all three environments and then enter to accept that. And I will see you right back here when I've done that myself. And assuming that you've done all of that, there's only one thing left to do which is to type vessel and then dot. And this is now I'm going to press enter to kick it off. This is now going to take this directory and ask for cell to deploy this as a new cloud AI app. And the cell will notice that we've got everything set up. Notice we've got a Next.js app. It's going to recognize everything here. It's going to see the API folder and Index.py. So it knows we have a fast API backend. It's going to see our requirements.txt. So it knows what we need to install to make that work. And it's going to do all of this. And with Vercel you have a couple of different environments that gets deployed to you have something called the preview, which is a place where where you can try things out before they go to production, and there's production itself. And because we're doing this for the first time with a new project, it's going to go straight to production. When we do this in subsequent times, it's going to put it on the preview first, and there's a separate command to deploy it to production. But this is going to be going straight to production. And it's building it at the moment. And it has deployed it to production. And the next thing we're going to do is open it up in production. Okay. So here we go. Drum roll please. Uh, the way you can do it quickly in from from cursor is you can press down on a mac. It's control and click. And I suspect on a PC it will be, uh, sorry on a mac, it's command and click. And I suspect on a PC it will be control. Uh, and then I press open and here we go. It opens something up, and it's a business idea generator. This is a fancy front end. It's showing loading, which you may remember, is what the state is set to before it's successfully loaded. With any luck, it is currently calling GPT five nano, which is coming up with a business idea and bam, here is a business idea. It's quite a substantive business idea. I'm not sure if it's any good or not. Uh, but there's a lot there with metrics to track and so on. The Nexus agent, an agent as a service platform that lets small, medium sized businesses deploy autonomous AI agent teams to run end to end business processes across their apps with governance, safety and explainability. Yeah, that seems seems like a great app. Seems like a good time for it. Uh, and uh, here's a very, very robust description of it. But most importantly, this is running in a front end, a Next.js app, and it's running in, in the browser. It's deployed to production. This is running as a production app on vessel with a front end and back end. And whilst it is quite simplistic, I will be the first to admit. The main point is that this is a foundation that we can use to build and build on top of, and we've done it all on day two.

</details>
