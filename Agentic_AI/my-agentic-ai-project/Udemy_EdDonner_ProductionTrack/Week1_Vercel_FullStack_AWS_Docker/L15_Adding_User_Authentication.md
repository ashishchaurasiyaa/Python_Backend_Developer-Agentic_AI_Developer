# L15 — Adding User Authentication to Your Production AI Application

> **Week 1 · Day 3** · ⏱️ ~11 min

---

## 🎯 TL;DR

Day 3 ki shuruaat — aaj **authentication aur subscription** add karenge, dono surprisingly easy. Hum **Clerk** (ek lightweight auth platform) ka account banate hain, ek "SaaS" application configure karte hain, Clerk ka SDK + `fetch-event-source` install karte hain, aur publishable/secret keys ko `.env.local` mein securely store karte hain.

---

## 🗣️ Hinglish Explanation

### Welcome to Day 3 + recap

Ed Day 3 shuru karta hai. Aaj ka topic: **authentication + subscription** — sunne mein lagta hai mushkil hoga, par actually bahut easy rahega. Ed warning bhi deta hai: **abhi sab kuch easy lag raha hai (Vercel, Clerk), par yeh permanently aisa nahi rahega.** Agle do weeks mein "big guys" — **AWS, GCP, Azure** — aayenge, jo ek "whole different ball game" hai. Toh abhi enjoy karo.

**Full-stack recap (important foundation):**
- **Front end** = user ke browser mein chalne wala stuff — HTML, CSS, JavaScript.
- **Back end** = server par chalne wali business logic.
- **Connection** = front-end code ek **API call** karta hai server ke ek **endpoint** par; endpoint typically **JSON** return karta hai (humne plain text use kiya, par JSON bhi ho sakta hai). Client us response ko leke decide karta hai page kaise change hoga, aur **React** page ko re-render kar deta hai.

**Hamara stack:**
- **Next.js React** front end (using **pages router**, not app router)
- **Python FastAPI** back end
- **Tailwind CSS** (ton of CSS likhne se bachata hai)
- **Vercel** deployment — preview + production environments

### Repo structure recap (do repos)

Yeh thoda confusing hai, isliye Ed clarify karta hai:
1. **`production` repo** — clone kiya hua; isme saari **instructions** (week1/week2 folders, har din ki guides), **self-study guides** folder, aur **community contributions** folder hain. Yeh documentation/source of truth hai.
2. **`SaaS` repo** — humne **scratch se** banaya; yahan hamara actual app chalta hai.

Ed ne `production` se guides ko `SaaS` mein copy kar liya tha taaki easily reference ho sake. **Community contributions** folder mein students apne notes/code/links daal ke PR bhej sakte hain — Ed ko share karna pasand hai. Weeks 3 & 4 mein aur naye repos aayenge (already setup kiye hue).

### Clerk kya hai aur kyun

**Clerk** ek "simple but powerful authentication platform" hai users manage karne ke liye — **bahut lightweight code** se. Auth ke liye kai options hain (jaise **AWS Cognito** — quite sophisticated, AWS mein built-in), par Ed yahan Clerk choose karta hai kyunki:
- Yeh **incredibly easy** hai.
- Ed ka philosophy: ek tool seekh lo, toh baaki pick up karna fast ho jaata hai. Tumhari team koi aur framework use karti ho toh bhi intuition transfer hoga.
- Naye project ke liye Ed Clerk hi recommend karta hai.

**Auth kaise kaam karta hai (high level):** user sign in karta hai (email ya social auth — Google/GitHub), Clerk use ek **JWT token** deta hai. Front end yeh JWT back end ko bhejta hai har request mein, aur back end verify karta hai ki yeh ek valid signed-in user hai.

> **JWT (JSON Web Token)** kya hai? Ek signed, self-contained token jisme user ki identity claims hote hain (jaise user ID), cryptographically signed taaki tamper na ho sake. Ed bolta hai yeh ek "rabbit hole" hai — deep nahi jaayenge; chahiye toh ChatGPT se pucho. Bas trust karo ki yeh Clerk ki "secret sauce" hai jo auth enable karti hai.

### Step 1: Clerk account banao

1. Clerk website kholo → **Sign up**.
2. **GitHub ya Google** se identify karo (Ed ne Google use kiya).
3. Kuch questions (individual vs work, etc.) answer karo.
4. Phir **Clerk dashboard** par pahunchoge — yahan applications create hote hain.

### Step 2: "SaaS" application create karo

1. Dashboard par **Create application** button dabao (Ed ke paas already bana hua hai, isliye uska direct dikhta hai — tumhare paas create button hoga).
2. Naam do: **SaaS**.
3. Right side par ek **preview** dikhta hai ki sign-in screen kaisa dikhega.
4. Sign-in methods select karo: **Email**, **Google**, aur optionally **GitHub**.
5. **Create application** dabao.

Application open hone par basic details dikhenge. (Ed ke paas "your application has users" message hai kyunki usne already 2 test accounts banaye hain — tumhare paas abhi users nahi honge.)

### Step 3: Clerk SDK + fetch-event-source install karo

Terminal kholo (SaaS project mein), Clerk ka **SDK** (Software Development Kit) install karo:

```bash
npm install @clerk/nextjs
```

> Ed dohraata hai: **npm install = front-end ka pip install.**

Phir ek aur package install karo — **`@microsoft/fetch-event-source`** (Microsoft ne likha hai). Yeh streaming ke liye chahiye **jab authentication in place ho** — kyunki normal browser `EventSource` (SSE) custom headers (jaise auth token) nahi bhej sakta, par yeh library bhej sakti hai:

```bash
npm install @microsoft/fetch-event-source
```

### Step 4: Environment variables — keys samjho

Do environment variables chahiye:
1. **`NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY`** — **public key**, jise koi bhi jaan sakta hai (front end mein expose hota hai; `NEXT_PUBLIC_` prefix Next.js ko batata hai ki ise browser mein bundle karna safe hai).
2. **`CLERK_SECRET_KEY`** — **secret key**, kabhi expose nahi karna (sirf server-side).

### Step 5: Keys aur JWKS URL Clerk dashboard se nikaalo

1. Clerk dashboard → application **SaaS** par click → **Configure** → left mein scroll down → **API keys**.
2. Yahan milenge:
   - **Publishable key** (visible) — copy button se copy karo.
   - **Secret key** (hidden, dots dikhte hain) — copy button real value copy karta hai, dots nahi.
3. **Ek aur important cheez:** yahan ek **JWKS / JWT URL** bhi hota hai (verification ke liye). Ise bhi **copy karke notepad mein rakho** — agle steps (next lecture) mein chahiye hoga. (Yeh URL public keys serve karta hai jinse back end JWT signatures verify karta hai.)

### Step 6: `.env.local` file banao

Project root mein nayi file: **`.env.local`**.

```bash
# .env.local (project root)
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_test_xxxxxxxxxxxxxxxxxxxx
CLERK_SECRET_KEY=sk_test_xxxxxxxxxxxxxxxxxxxx
```

Clerk dashboard se copy ki hui actual keys yahan paste karo (Ed on-camera apni keys nahi daalta — security).

> ⚠️ **`.env.local` ko `.gitignore` mein hona zaroori hai** taaki yeh kabhi repo mein push na ho. Good news: Next.js ka default `.gitignore` already isme `.env.local` rakhta hai. Cursor mein file **faint/greyed** dikhe toh matlab git use ignore kar raha hai (theek hai). Secrets kabhi version control mein commit nahi karne chahiye.

Ed apni keys daalne ke liye thoda break leta hai — agle lecture mein continue.

---

## 📋 Key Concepts

| Concept | Matlab |
|---|---|
| **Authentication** | Yeh confirm karna ki user kaun hai — sign-in/sign-up flow |
| **Clerk** | Lightweight auth platform; email + social login bahut kam code mein |
| **JWT (JSON Web Token)** | Signed token jo user identity carry karta hai; front end → back end bhejta hai verify karne ko |
| **JWKS URL** | Clerk ka URL jisse back end JWT signatures verify karne ke liye public keys leta hai |
| **Publishable key** | Public Clerk key (`NEXT_PUBLIC_...`) — browser mein safe |
| **Secret key** | Private Clerk key — sirf server-side, kabhi expose nahi |
| **`.env.local`** | Local secrets file; `.gitignore` mein hoti hai (Next.js default) |
| **`@clerk/nextjs`** | Clerk ka Next.js SDK |
| **`@microsoft/fetch-event-source`** | SSE streaming jisme custom (auth) headers bhej sakein |
| **Full-stack flow** | Front end API call → back end endpoint → JSON response → React re-render |
| **production vs SaaS repo** | `production` = docs/guides; `SaaS` = actual app code |

---

## 💼 Backend Dev Ke Liye Note

Backend dev ko yahan **JWT-based stateless auth** ka standard pattern dikhega — front end Clerk se token leta hai, har API request ke `Authorization: Bearer <jwt>` header mein bhejta hai, aur back end token ko JWKS public keys se verify karke trust establish karta hai. Yeh server-side session storage avoid karta hai (stateless, horizontally scalable). Note karne layak: `EventSource` (native SSE) custom headers support nahi karta, isliye Clerk-protected streaming ke liye `@microsoft/fetch-event-source` chahiye — agar tumne kabhi auth + SSE combine kiya hai toh yeh gotcha familiar lagega. Secrets management bhi classic backend hygiene hai: `.env.local` + `.gitignore`, public vs secret key separation (publishable browser mein, secret sirf server par) — Twelve-Factor App ka "config in environment" principle. Production mein ye env vars CI/secret-manager (yahan aage Vercel env vars) mein jaate hain, kabhi code mein hardcode nahi.

---

## ✅ Takeaway

- **Day 3 = auth + subscription**, dono Clerk se easy — par yaad rakho, AWS/GCP/Azure (Weeks 2-3) mein deployment "whole different ball game" hoga
- **Clerk** lightweight auth deta hai; user sign-in karta hai → **JWT** milta hai → front end use back end ko bhejta hai verify karne ko
- Install: **`@clerk/nextjs`** (SDK) + **`@microsoft/fetch-event-source`** (auth ke saath SSE streaming ke liye)
- Clerk dashboard → Configure → API keys se **publishable key, secret key, aur JWKS URL** nikalo
- Keys **`.env.local`** mein rakho (Next.js default `.gitignore` ise already ignore karta hai) — secrets kabhi commit mat karo

---

<details>
<summary>📜 Full Transcript (English)</summary>

And welcome back to day three. I'm so happy that you decided to put up with another day of me. I didn't put you off yesterday with our first production deployment or second production deployment. Really? So as a recap, yesterday we built a front end and back end and put it together and deployed it. Today it's about authentication and subscription, two things which which might sound like they're going to be really hard to do, and they're in fact going to be really easy. Uh, this this week is all about particularly using some of these frameworks, like deploying to vercel. So easy to get an app deployed to production. Uh, but please don't think it's always going to be that way. The next couple of weeks we're going to be using the big guys. We're going to be using AWS, GCP, Azure, and it's a whole different ball game. So so prepare yourself for a different universe there. But for now it's going to be very easy indeed. As a quick recap, then last time we built a full stack, as I call it, an app that in that its front end and back end and a front end, of course, is the stuff that runs in the user's browser the HTML, CSS and JavaScript. The back end is the business logic that runs on the server, and you put them together by writing front end code in the browser. That makes an API call to an endpoint on your server, and that endpoint typically responds with JSON. In our case, we responded with plain text, but it can be JSON that goes back to the client, and the client takes that and chooses how that will change the page and react rerenders the page. We used a Next.js react front end. We had a Python fast API backend. We were using the pages router, not the app router. We were using tailwind CSS. Such a great easy way to to avoid having to write tons of CSS stuff. And we were using Vercel cloud AI platform for our deployment, our two environments, our preview environment and our production environment. And then also a quick recap about the situation with the repo. So I know this is a bit muddling, so bear with me. We started by cloning a repo called production um, which has in it all of the instructions for what we're going to be doing this week and next week. And it's got things like the guides in it as well. This, this. As I say, it's the week one folder in there has instructions for each day. And we've created a new repo from scratch called sass. And that's important because I want you to be in the practice of creating something from scratch. We could have had it as a folder within production, but then then it wouldn't have been quite as neat and tidy as this. So that's how we've done it. So you've now got the production repo and the sass repo production with the documentation, and sass is where we are running our app. And I did that trick of copying across the guides so that I can easily reference them, but you can easily switch between the two. Uh, there's a guides folder with self-study guides in the production repo. There's also the community contributions folder. And remember, I'm hoping that as you discover things or as you have your own repos to point to, you'll add like a markdown file in there that's got your name or something like that and write up some notes or what you've done in a link or some code. If you've got code to share, and then a submit a PR. And that would be wonderful to be able to include what you've done to share it with with other students in the community contributions folder. And you should check out now what's in there to see if there's interesting stuff that you can learn from? Uh, in weeks three and four, we're actually going to move to different repos I've already set up. So there are going to be some more repos as well as lots of repos. So I have to stay on top of this and hopefully it won't get confusing. Okay. And uh, today we're going to be using something called clerk, which is a very simple but powerful authentication platform for managing your users with such lightweight code. So there are there are many different platforms for doing this. Actually, AWS has a quite sophisticated user authentication, uh, approach built into it. But we'll be using clerk for this. Um, I as I say, the reason I do this is to show you how clerk Clarke works so that you get intuition for how to do these. You may have a different framework that you're using in your project or that your team is using, but once you've seen how it's done with one, hopefully it'll be quite quick to pick up the others. If you're going to choose something new for your new project, then I would recommend Clarke because it's so very easy, as we will find out right now. And so without further ado, you see much less chit chat. Now we're going straight to practical. Uh, let's go back to the lab and continue working on our business idea generator. But let's give it some user authentication. Okay. So welcome back to Casa, a fabulous place to be. Uh, I'm in the Sass project. Don't get them confused. Uh, and, uh, right, right back where we left off. Um, and I've got this this week, one folder, because I copied it across from the production project. But you could also look back on that if you wish. And I'm going to go to the day three MD and open the preview. So we see how it looks. And there's also a day three part two by the way. We've got two different ones to go through today. And this is all about setting up user Authentication so that users can sign in before they use our precious idea generator. And we're going to be people will be able to sign in just with their email or use some social auth as well if they wish. And this works also by by passing these things called JWT tokens to the backend to confirm that it is a signed in user. JWT is one of these rabbit holes I'm not planning to go down. It's very interesting. There's a lot to learn about. If you want to know more about JWT, ask your favorite AI. ChatGPT will do an incredible job of explaining what it is and how it works. Uh, but you can otherwise just trust that that's part of the of the secret sauce, which allows platforms like Clark to to provide user authentication services. All right. So we're going to start by creating a Clark account. Uh, and we'll go over now to Clark like that where we will click sign up and get things set up. And I brought up an incognito tab here because I'm already signed in to Clark. So I want to show you just briefly the first sign in experience. Uh, so when you first go here, uh, I think you could press the sign in button and it's going to start with a with a control like this and you can say, don't have an account? Sign up, press here to create your free account and you'll then sign up to get started. You can use GitHub or Google to to join Clark. This is to identify yourself. I think I used Google when I came in the first time, asked a few questions about about the fact that I'm doing this individually, not not for work and so on. And after you've answered those questions, you should be at the Clark's, uh, dashboard. And that's the place where you can create an application. Uh, and that is where we'll be able to set up and configure a new application called SaaS. So this is what it looks like for me when I go, because I've already got an account. I have a dashboard button here. And this is what it looks like when I go into my dashboard. And I imagine that that uh, so I've already got I've set up SaaS already. So it goes straight to this, which I imagine is not what you will see. You will see something with it with a create application button on it. And that's what you should press. Uh, see if I can go back to that. Here we go. So you'll see a screen like this. There should be a create application button. That's what you will press I press that create application button. Now you'll call it SaaS like so it's now going to probably complain I already have that now. Uh, and over there it shows a preview of what it's going to look like when people come in. And then let's say that they can come in with an email with Google and maybe with GitHub as well, and then press that create application button. I'm obviously not going to press that myself because I've already done it. It's here. This is what it will be like when you open it up. It won't say, congratulations, your application has users because you won't yet. I've already tested it out with two different versions of me. Uh, but it will come up and you'll see some basic details, uh, and then go back to cursor. Okay. And now back here again, uh, step three is to install Clark's, UX, uh, command line interface, which we're going to do by, uh, sorry, not the SDK, the software development kit, uh, which we're going to do by bringing up a terminal, uh, and then run this command again npm install the front end equivalent of, of a pip install. Uh, and it's now going to install the clerk files. There we go. Done. We're also going to install this nifty thing called fetch event source. Oops I didn't mean to do that. There we go. Click back over there. We're going to install fetch event source here. This is something we need to stream back results with with authentication in place written by Microsoft. Okay. Uh, now there's a couple of environment variables that we need. Uh, one is called the next public clerk publishable key, which is like what they call a public key, which anyone can know associated with your application. And then there's also a clerk secret key. And we'll find them in the clerk dashboard. So let's go over there now. So if we go back to clerk again Um, when you're if you're, you're looking at your application. So it should say SaaS at the top here. If you're in your beginning screen, if it looks like that, you have to click on SaaS to get here. You then click on configure over here, and you scroll all the way down to API keys on the left here. And I realize this is really small, so I make it a bit bigger for you. So we clicked on configure and then clicked on API keys down here. And what you've got here is an a couple. You've got this next public Clark publishable key and also the Clark secret key. Uh, and we can copy them. It's obviously not not showing it which is nice of it. This is the public one that you can see. You copy it by pressing that copy button here. Uh, and while you're here, also take note of this thing here, this JWT URL. I want you to also copy that and put it in a notepad or somewhere. Or you can always come back to this screen. We're going to need that in a minute as well. But for now, copy both of these to the clipboard and it will have copied the real key, Not the dot dot dot dot dot. And then back in cursor. I want you now please to create a file called dot EMV local in your project root. So over here you're going to type new new file dot EMV dot local. There it is. Uh and paste in here those keys. And I'm obviously not going to do it now because then you'll see. But but you should do that for your keys and I will do it in just a second. Uh, when, when I got rid of you. Uh, but, um, the, uh, the, the it also tells you here that it's important to add EMV local into the file called. Gitignore, which makes sure this never gets pushed any repo. But as it happens, it is already in the default. Gitignore that next has built for us. And you can tell that because in cursor it appears in this very, very faint font which means it is ignored along with some other things here which are, which are already taken out. So there it is. I'm now going to put my keys in there, and I'll be back in a moment.

</details>
