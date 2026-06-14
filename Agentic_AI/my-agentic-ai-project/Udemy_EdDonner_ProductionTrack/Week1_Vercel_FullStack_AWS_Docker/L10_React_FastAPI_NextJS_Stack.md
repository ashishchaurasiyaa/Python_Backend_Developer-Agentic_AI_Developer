# L10 — Building Full-Stack AI Apps with React, FastAPI, and NextJS

> **Week 1 · Day 2** · ⏱️ ~13 min

---

## 🎯 TL;DR

Lab se pehle ka final theory chunk: **React** (component-based declarative frontend), **Next.js** (React ke upar framework — routing, transpiling, bundling), aur Python backend options (Django/Flask/**FastAPI**) ka tour. Plus course ka **repo strategy** — har week ka alag repo, aaj `production` repo clone karke nayi `sass` app banayenge.

---

## 🗣️ Hinglish Explanation

Ed maan raha hai ki bahut talking ho rahi hai aur log action chahte hain — bas thode aur slides, mainly frontend ke baare mein, phir poora din lab lab lab. Yeh lecture us frontend/backend stack ko properly set up karta hai jo poore course mein use hoga.

### React kya hai

**React** ek JavaScript **frontend framework** hai jo **component-based** hai. Iska matlab tumhara UI chhote-chhote reusable **building blocks** (components) se bana hota hai. Har component apne andar teen cheezein package karta hai:

- **Markup** (kya dikhega — HTML jaisa structure)
- **Styles** (kaisa dikhega)
- **Logic** (kaise behave karega — JavaScript/TypeScript)

In components ko assemble karke poora user interface banta hai.

#### Declarative ka matlab

React **declarative** hai — yeh sabse important concept hai. Tum yeh **nahi** likhte ki "jab X badle toh screen par Y update karo" (woh imperative style hai). Iske bajaye tum sirf **describe** karte ho: *"agar duniya ki state aisi hai, toh UI aisa dikhna chahiye."* Bas. Baaki React sambhalta hai.

Behind the scenes React ka jaadu yeh hai:

1. Jab bhi koi **state** badalti hai, React tumhara component code **dobara call** karta hai taaki naya UI description mile.
2. Poora screen redraw **nahi** karta (woh clumsy/flickery lagega).
3. Iske bajaye React purani DOM (Document Object Model — browser ka in-memory page representation) aur nayi description ko **compare** karta hai (isse "diffing" / virtual DOM kehte hain), aur sirf **wahi parts update** karta hai jo actually badle hain.

Purane zamane mein tumhe khud yeh saara logic likhna padta tha — "kya badla, ab DOM mein kahan-kahan touch karna hai." Ab nahi. Tum poora screen describe karo, React figure out kar lega ki kya update karna hai. Yeh **ingenious** hai.

#### Props aur State — React ke do core concepts

| Concept | Matlab |
|---|---|
| **Props** (properties) | Upar wale (parent) components se neeche (child) components ko **pass** ki gayi information. Yeh control karti hai ki child component khud ko kaise present kare. Ek-tarfa flow: top → down. |
| **State** | Component ke andar ki **current status/data** jo user ko dikh rahi hai. Jab state badalti hai, React screen redraw kar deta hai. Component khud apni state manage karta hai. |

Abhi abstract lag raha hai — examples mein clear ho jaayega (lab mein `idea` naam ki ek state piece dekhoge).

#### JSX / TSX

**JSX** (JavaScript XML) aur **TSX** (TypeScript XML) special file types hain — yeh **HTML aur JavaScript/TypeScript ka hybrid** hain. Code likhte-likhte achanak HTML markup aa jaata hai. Pehli baar weird lagta hai. Example:

```tsx
function Greeting() {
  const name = "Ed";          // yeh TypeScript hai
  return <h1>Hello, {name}!</h1>;  // yeh achanak HTML jaisa — yeh TSX
}
```

Is format se pehle, log JavaScript code mein HTML ko **strings** ke roop mein force karte the — bahut clumsy. JSX/TSX ne isse elegant aur easy bana diya. Course mein **TypeScript + TSX** har jagah use hoga; thodi aadat ho jaayegi.

#### Rich ecosystem aur component libraries

React ka ecosystem bahut **rich** hai — countless frameworks aur ready-made components jo tum bas screen par "throw" kar sakte ho. **Component libraries** = poore suites of pre-built components jo aapas mein achhe se kaam karte hain:

- **Material UI** — shaayad sabse famous
- **Chakra** — increasingly popular

In se UI bahut fast ban jaata hai.

### Next.js — React ke upar ka framework

**Next.js** ek **application framework** hai jo React ke **upar** bana hai. Yeh kai dusre frameworks ko ek saath laata hai taaki tum React ke saath turant productive ho jaao — "hit the ground running." Mazedaar baat: Next.js ko **Vercel** ne hi banaya hai (wahi Silicon Valley, developer-centric company jiske platform par hum Day 1 par deploy kiye the). Isliye Next.js + Vercel ek dusre ke saath perfectly fit hote hain.

Next.js out-of-the-box bahut functionality deta hai:

#### Routing — Pages Router vs App Router

**Routing** = woh functionality jo control karti hai ki jab user app ke alag-alag sections par click kare, toh **kya draw ho**. Next.js mein routing ke **do** implementations hain:

| Router | Pehchaan | Notes |
|---|---|---|
| **Pages Router** | `pages` naam ki subdirectory hoti hai | Simpler, most trusted, sabse common. Pehle yahi tha (only option). |
| **App Router** | `app` naam ki directory hoti hai | Newer, more powerful, ab Next.js ka **recommended** approach. |

**Is course ki strategy:** Week 1 mein **Pages Router** se shuru karenge — **kyunki** jo authentication framework use hoga (Week 1 Day 3, Clerk) woh **sirf Pages Router** ko support karta hai. Ed ne pehle App Router se sab banaya tha, phir auth ki wajah se sab nikaal kar Pages Router mein dobara likhna pada — "to my detriment." Week 2 mein App Router use karenge taaki dono ka exposure mile, phir shaayad wapas Pages Router par aayenge.

#### Client-side vs Server-side rendering

Pages render hone ke do tareeke:

- **Client-side rendering (CSR)** — JavaScript **browser mein** chal kar final webpage banata hai. Traditional, simpler approach.
- **Server-side rendering (SSR)** — JavaScript **server par** chal kar final HTML banata hai, phir woh client ko bhej deta hai. Increasingly common, par debate hai (SEO/performance pros, complexity cons).

**Course ka choice:** Client-side — simpler hai aur hamare setup (Python backend, JS frontend) ke saath better fit. SSR mein interested ho toh padh lena.

#### Transpiling aur Bundling

Next.js ke do important tooling concepts:

- **Transpiling** — modern TypeScript ko **vanilla JavaScript** mein convert karna. Browsers modern TypeScript directly support nahi karte, isliye Next.js behind-the-scenes advanced TS ko plain JS mein badal deta hai.
- **Bundling** — saari converted JS ko efficient **bundles** (packed files) mein daalna jo browser ko bheja jaata hai.

Tumhe inke baare mein sochne ki zaroorat nahi — tum bas badhiya TypeScript likho, Next.js baaki sab sambhal leta hai.

### Python Backend Frameworks — Django vs Flask vs FastAPI

Ed maanta hai ki zyaadatar log backend developers hain (woh khud bhi), toh JS frameworks naye lag sakte hain par Python frameworks familiar honge. Teen major:

| Framework | Style | Detail |
|---|---|---|
| **Django** | Heavyweight, "batteries included" | Sab kuch packaged: **ORM** (Object-Relational Mapping — Python objects ↔ database tables), authentication, templating, yahan tak ki ek built-in **admin UI**. |
| **Flask** | Micro-framework (opposite extreme) | Super simple — bas API routes lagao, requests handle karo. Jaldi shuru hota hai, par sab kuch add-on karna padta hai (apni libraries choose karke combine karo). |
| **FastAPI** | Bich ka, modern, super popular | Async-heavy. **Starlette** (web toolkit) + **Pydantic** (schema/data validation) ke upar bana. Routes define karna easy, API endpoints serve karne ke liye optimized. |

> **ORM kya hai (background):** Object-Relational Mapping — ek layer jo tumhare Python class objects ko SQL database rows mein automatically map karti hai, taaki tumhe raw SQL na likhna pade (e.g. Django ORM, SQLAlchemy).

> **Pydantic kya hai:** Ek Python library jo data **schema** describe karti hai — tum classes mein type hints likhte ho, Pydantic incoming data validate aur parse kar deta hai. Agentic course wale ise achhe se jaante hain. FastAPI iska built-in use karta hai routes aur request/response bodies define karne ke liye.

**Course ka choice:** **FastAPI** — modern, fast, aur LLM-era ka favourite. Poore course mein yahi backend rahega.

### Repo Strategy — yeh course alag kyun hai

Pichhle courses mein **ek hi repo** tha — `git clone` karo, poore course bhar wahi use karo. Is baar **har week ka alag repo** hoga. Reasons:

1. **Production realism** — production apps banate waqt tum naye repos set up karna, scratch se build karna seekhoge. **Ek repo = ek application** — yeh real-world pattern hai.
2. **GitHub Actions / CI-CD** — baad mein repo khud ko deploy karega jab tum `git push` karoge (dev par, phir promote to production). Iske liye **one repo per deployment** chahiye. (Pros bolenge "monorepos se bhi ho sakta hai" — sahi hai, par woh over-complicate karega; hum simple rakhenge.)

#### Aaj ka flow

1. **`production` repo clone karo** — yeh course ka main repo hai, isme `week1` folder hai jisme har **day** ki instructions hain. Day 1 mein hum isi repo ko online padh chuke the.
2. Aaj **scratch se nayi repo banayenge** — naam **`sass`** (software as a service), kyunki hum ek commercial app banayenge jisme baad mein subscription + authentication aayega.

`production` repo mein teen helpful folders:

- **`week1/`** — har din ki step-by-step instructions (markdown)
- **`guides/`** — bahut saare self-study guides (Docker, frontend, git/GitHub, command-line basics, etc.). Is course mein **bahut peripheral info** aayegi, toh yeh guides "more important than ever" hain — haath mein rakho.
- **`community-contributions/`** — troubleshooting tips ya apni banayi repos share karne ke liye. Ek markdown file banao apne naam + jo kiya uske saath (apni repo link karo), aur Ed ko **PR** (Pull Request) submit karo. Guides mein PR kaise karte hain woh likha hai.

Bas itni admin. Ab seedha lab mein — "roll up your sleeves and I will see you in cursor."

### Aaj ke din ka roadmap (Day 2)

- **Aaj (Day 2):** Pehla frontend + backend app — ek **business idea generator**.
- **Day 3:** User **authentication** (sign-in) + **subscription** add karenge.
- **Day 4:** Proper business functionality — toy se aage, ek real **SaaS app deployed to Vercel**.
- **Day 5:** Wahi sab **AWS** par deploy karenge (Docker + App Runner).

Sab kuch sirf pehle week mein.

---

## 📋 Key Concepts

| Concept | Matlab |
|---|---|
| **React** | Component-based, declarative JS frontend framework — UI building blocks se banta hai |
| **Declarative UI** | Tum describe karo "UI aisa dikhe", React khud figure karta hai kya update karna |
| **Props** | Parent → child pass ki gayi properties (top-down information flow) |
| **State** | Component ki current data/status; badalne par React redraw karta hai |
| **JSX / TSX** | HTML + JavaScript/TypeScript ka hybrid file format |
| **Component library** | Pre-built components ka suite (Material UI, Chakra) |
| **Next.js** | React ke upar ka framework — routing, transpiling, bundling out-of-box (Vercel ne banaya) |
| **Pages Router** | Next.js routing — `pages/` folder; simpler, course Week 1 mein use hoga |
| **App Router** | Next.js routing — `app/` folder; newer, recommended, Week 2 mein |
| **CSR vs SSR** | Final page browser mein bane (client) vs server par bane (server-side) |
| **Transpiling** | Modern TypeScript ko vanilla JavaScript mein convert karna |
| **Bundling** | Converted JS ko efficient packed bundles mein daalna |
| **Django / Flask / FastAPI** | Python backends — heavyweight / micro / modern-async |
| **FastAPI** | Starlette + Pydantic par bana; course ka chosen backend |
| **ORM** | Object ↔ database table mapping (raw SQL se bachata hai) |
| **One repo per app** | Production strategy — har week/app ka alag repo (CI/CD ke liye) |

---

## 💼 Backend Dev Ke Liye Note

Python backend dev ke liye yeh lecture ek **mental model bridge** hai. Tum FastAPI, Flask, Django ka comparison shaayad jaante ho — yahan naya part frontend side ka mental model hai. React ka **declarative + diffing** model bilkul wahi pattern hai jo tum backend par **idempotent / desired-state** systems mein dekhte ho (jaise Kubernetes ya Terraform: "yeh end state chahiye" — system reconcile karta hai). Props/state ko request-scoped immutable inputs vs mutable session/component state ki tarah socho. Next.js ka **transpile + bundle** step tumhare Python world ke build artifacts (wheel/Docker image banane) ka JS equivalent hai. Sabse practical takeaway: **one-repo-per-deployment** discipline — yeh CI/CD pipelines ko simple rakhta hai (ek repo = ek deployable unit = ek set of GitHub Actions), jo tum apne microservices mein bhi follow kar sakte ho. FastAPI ka Pydantic-first design tumhare liye comfortable hoga — request/response contracts type-safe hote hain, ekdum API-first backend practice.

---

## ✅ Takeaway

- **React = declarative, component-based frontend** — UI describe karo, React diffing se sirf changed parts update karta hai; props (top-down) aur state (component data) core hain
- **Next.js = React + framework goodies** (routing, transpiling, bundling); course Week 1 mein **Pages Router** (auth framework ki majboori) use karega
- **FastAPI** course ka backend hai — modern, async, Starlette + Pydantic par bana; Django (heavy) aur Flask (micro) ke bich ka sweet spot
- **Repo strategy badli hai** — har week/app ka **alag repo** (production realism + CI/CD); aaj `production` repo clone karke nayi `sass` app banayenge
- `production` repo ke teen folders yaad rakho: `week1/` (instructions), `guides/` (self-study), `community-contributions/` (PRs)

---

<details>
<summary>📜 Full Transcript (English)</summary>

Now, if you're thinking there's a lot of talking going on in this and you're wanting to get to action, never fear. We're about to get to action. Give me one more second. A couple more slides, particularly the front end. People are probably getting pretty bored at this point. But we'll get there. We'll get there. Uh, react a few words about what react is. It is, of course, this this kind of JavaScript front end framework that is component based. It's made of building blocks, the building blocks. Each block has kind of markup and styles and logic packaged together in such a way that you can assemble user interfaces by bringing together these different components. It's what's called declarative, which means the way that you write a piece of react is you just describe what your UI should look like given a particular state of the world, given a state of your of your, uh, of your information, this is how the UI should be represented. And the way react works behind the scenes is that it's every time any state changes, it's recalling your code to figure out what you now think the UI should look like. And it doesn't redraw the whole UI because that would look really clumsy on the screen, but it automatically looks at what's changed in the Dom before you change the state and afterwards. And then it only updates the parts of the UI that have changed. And that's really ingenious. In the old days, you had to write tons and tons of logic when something changed to try and figure out what on the UI had to be updated. And you don't need to do that anymore. You simply describe the whole screen and the react framework takes care. Every time something changes of figuring out what needs to be updated on your UI. And react has two concepts that you'll see come through when we use it quite a lot, and they're known as props and state props is short for properties, and this represents information about your user interface that gets passed down from higher level components down to the smaller components, and controls the way that they should present themselves. Those are called props properties. Don't worry if it sounds abstract. It will hopefully come together when you see examples and then state is exactly what it sounds like. That is representing the kind of information, the state, the status of the information that you're presenting to the user. Uh, and that's, that's something which your components are responsible for managing and react figures out how to redraw your screen as state changes JSX and TSX, uh, for JavaScript and TypeScript, are special types of document that are a kind of hybrid between HTML and between JavaScript and TypeScript. Jsts are their acronyms. Uh, and and when you'll see it, you'll see it's kind of curious. It's like a mixture of the two. There's some HTML in there and then suddenly some code in there. And it's just this really convenient format. Before this format existed, you had to have lots of basically lots of lots of JavaScript or TypeScript code that kind of forced in strings with with different bits of markup at various points. And it was very clumsy and JSX TSX are just nice, elegant ways of doing it. That makes your life easy. And you'll see we'll be using TypeScript TSX everywhere. And uh, you'll get you'll get very comfortable with it once you've seen it a thousand times. And then the other thing about the world of react is that it can't be stated enough. It's such a rich ecosystem. There are so many frameworks, react frameworks, react components that you can include and then just throw onto your screen, uh, it makes it just really easy to plug and play different components. And there are component libraries which are suites of components. Material UI is maybe the most famous. There's one called chakra that's becoming increasingly popular. These these are whole libraries full of different components that will work nicely together. And you can use to build a user interface very quickly indeed. All right. So now to complete the picture, let me tell you about Next.js, the application framework that's built on top of react. And it brings together a number of other frameworks so that you can just hit the ground running with react. And Next.js is actually built by vessel, the company behind the cloud AI deployment that we did yesterday and that we're going to do again today. Uh, and it's a Silicon Valley based, very developer centric company that came up with Next.js. And Next.js is great because it brings so much functionality out of the box. Good to go. It includes two different implementations of something called a router routing functionality. And this is the functionality that controls when a user clicks on different sections of your application. What what gets drawn routing around your application. The first of them is known as the pages router. And you can tell you're in this this world when you have a subdirectory called pages, and this is the simpler of the two approaches. It's the most trusted. It's very common indeed. The other one is called app router. And you can tell because you have a directory called app and it's the newer flavor, it's more powerful. It's also now recently become the recommended approach to use by Next.js themselves. Now for this course we're going to mix and match. We're going to start this week by using the pages router. Because one of the frameworks we're going to use for for authentication only supports the pages router, as I discovered, to my detriment, when I built it all with the router, I had to pull it all out. But but anyways, that's just one of those things. So that's an example. Pages router is more supported because it used to be the only one. Uh, so we'll start with that next week. We'll probably use router. So you've got some exposure to that as well. And then we might come back to pages router. We will see pages themselves can be rendered the the JavaScript can be converted into the final form, either in the browser on the client side, or it's becoming increasingly common to actually have JavaScript running on your server side and create the final web page on your server, and then serve that up to the client. There's there's tons of arguments for and against doing it that way. For this course, we're going to stick with the client side approach, which is the more traditional approach and is simpler and is going to fit better with what we're doing. But if you're interested, then do read up about server side. And Next.js includes a lot of tooling to do things. There's something called Transpiling, which is what it's called when you convert. We're going to be using TypeScript and writing with modern TypeScript. And not all browsers actually, browsers don't support that. And the way it actually works is that behind the scenes, Next.js will convert this advanced TypeScript into vanilla JavaScript, and that's what gets sent to the browser in an efficient way where it's all packed together. And that process is known as bundling. When all of your, your, your nice TypeScript gets turned into vanilla JavaScript and put into nice bundles. And you don't need to know about any of that. All you focus on is writing great TypeScript, and Next.js handles everything else for you. Now, I do imagine most of the people taking this course are familiar with backend development. Like me, I'm actually a backend type so that Java, the JavaScript frameworks might be somewhat new. I'm sure you've heard of them. All the Python backend frameworks you're probably very familiar with, but let me just place them out there. The three that you hear about a lot, Django is the most heavyweight of them. It's the one that is very much what people call batteries included, meaning that it comes with tons of functionality packaged in like an ORM, an object relational mapping that goes from your Python code to your database authentication stuff. Templating. It even has its own UI for admin. Then flask is the opposite. Extreme flask is known as a micro framework because it's super simple. It just deals with the basic like putting your API routes, handling the requests. It's really quick to get started with a flask app, but you do need to add things on. You need to pick and choose other frameworks to combine with it. And then somewhere in the middle between these two, but super popular at the moment for good reason is fast API. Fast API is modern. It uses a lot of async. Uh, it's built on very popular, uh, libraries, starlet and pedantic, which anyone's been on. The agent course knows pedantic only too well. A great framework for describing, uh, schema behind objects, and it's built into fast API. That's how you define your routes, and it's very much optimized for writing a server, which is all about servicing API endpoints and fast API is what we'll be using throughout this course. And it's incredibly popular these days. Okay. And then a final piece of admin before we get to our lab. And then the rest of today will be lab lab lab. But admin. Okay. So the repo situation, how I'm going to handle code for this course is a little bit more involved than previous courses for very good reason. So my previous courses there's been one repo for the course. And so you do a git clone and you get the repo. And that's what you use for the entire duration of the course. But it's not going to be that simple this time. There's basically going to be a different repo for every week of the course. Uh, and part of the reason for that is that since we're building production apps, I want you to get used to the whole process of setting up a repo for a project and building it from scratch, and one repo representing one application. There are also some more basic reasons that we're going to be using things like GitHub actions, which is how you have a repo be able to deploy itself to production when you do a git push or to development, then then you promote the production. And in order to do that, of course, we need to have the the one repo for deployment. And the pros amongst you will say, well you don't have to, you can have monorepos, you can do all sorts of clever stuff, but that would overcomplicate it and it's not what we want. So that's why I'm doing it this way. So for this week we're going to start. There's going to be one main repo called production. And the first step that we're going to go and do is git clone that repo. So you have a local copy on your disk of the repo. That's called production. And we're then going to go and build another repo for for today's course it contains a folder called week one which has instructions for each day. And that's what we used of course. Uh, yesterday when we when we looked at the day one, we went to this repo on GitHub and read those instructions. And today we're going to create a new repo from scratch. It's going to be called SaaS for software as a service, because we're going to build like a commercial app, which is eventually going to have subscription and, and authentication, all sorts of great stuff. It also has a guides folder with a bunch of self-study guides. And this is more important than ever, because there's going to be so much peripheral information. We're going to cover around things like Docker and front end and all the rest of it. There's going to be a lot of extra information for you to go and do some more research if you want, so please keep those guides to hand. I think they'll come in really handy. And it also has a community contributions folder, and I've been thrilled with the way people have contributed so much to the other courses. This one's a bit different. It's harder to to imagine how we do community contributions, when a lot of what we're going to be doing is going to be setting things up. And so what I'm going to suggest is that when you set things up, when you have something to share, which could be a troubleshooting tip, or it could be a whole repo that you've set up. You could write your own little markdown file with with your name in it, and with what you've done, and put that in community contributions, perhaps linking to your own repo, and then submit that as a PR to me. There'll be instructions in the guides. If this is this all is new language to you. Instructions on how to do a PR. Um, and I'm hoping that people will be able to, to submit contributions. It's just going to be like a page, a markdown page describing what they've done, linking to their repo or troubleshooting tip. And that way we'll be able to keep up this, this culture of community contributions coming into this repo, even in a slightly different setting of doing production projects. All right, that's enough of the admin stuff. It's time now for us to go to the lab and get get going with some coding. So roll up your sleeves and I will see you in cursor.

</details>
