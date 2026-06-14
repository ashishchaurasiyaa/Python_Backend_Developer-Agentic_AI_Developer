# L16 — Adding User Authentication to Production AI Apps with Clerk

> **Week 1 · Day 3** · ⏱️ ~9 min

---

## 🎯 TL;DR

Clerk integration ka code part: app ko **`<ClerkProvider>`** mein wrap karte hain, business idea generator ko ek **protected route** (`product.tsx`) mein move karte hain, `index.tsx` ko sign-in wala landing page banate hain (`<SignedIn>`/`<SignedOut>` components), back end mein **`fastapi-clerk-auth`** se route protect karte hain, JWKS URL aur teeno keys Vercel par set karte hain, aur `vercel dev` se locally test karte hain.

---

## 🗣️ Hinglish Explanation

### Step 5: `_app.tsx` ko ClerkProvider mein wrap karo

Pehla code change — `pages/_app.tsx` (front-end ka entry/root component) ko overwrite karte hain. Yeh kya karta hai:

- **`<ClerkProvider>`** naam ka React component import karta hai.
- Poori application ko is provider mein **wrap** karta hai.

Yeh React ka **Context Provider pattern** hai: provider tree ke top par hota hai, aur uske andar ke saare components Clerk ki functionality (current user, sign-in state, etc.) access kar sakte hain — har component ko manually props pass kiye bina.

```tsx
// pages/_app.tsx
import { ClerkProvider } from "@clerk/nextjs";
import type { AppProps } from "next/app";
import "../styles/globals.css";

export default function App({ Component, pageProps }: AppProps) {
  return (
    <ClerkProvider>
      <Component {...pageProps} />
    </ClerkProvider>
  );
}
```

> Ed openly bolta hai: "front-end log jaante hain main ise thoda oversimplify kar raha hoon" — par concept clear hai: **sab kuch ClerkProvider mein wrap, taaki auth state har jagah available ho.**

### Step 6: Protected route `product.tsx` banao

`pages/` mein nayi file **`product.tsx`** — yeh ek **protected route** hai, yaani sirf logged-in users access kar sakte hain. Isme business idea generator ka **pura content** hai jo pehle `index.tsx` mein tha:
- Top par `"use client"` directive (client-side component).
- Wahi **React Markdown** component.
- Wahi **streaming** code (events stream back karne wala).

Matlab generator ki saari "meat" ab `product.tsx` mein chali gayi.

### Step 7: `index.tsx` ko landing page banao

Ab `index.tsx` (jo pehle pura generator tha) ko ek chhota **landing page with sign-in** bana dete hain. Generator content `product.tsx` mein move ho gaya, toh `index.tsx` ab relatively short hai.

Ed perspective deta hai: **pehle (Clerk jaise tools se pehle) sign-in page khud banana ek hafte ka kaam tha — social auth ke saath toh mahine bhar ka.** Ab yeh minutes ka kaam hai. Page ki saari "meat" do components mein hai:

- **`<SignInButton>`** — sign-in trigger karta hai.
- **`<SignedIn>`** — iske andar ka content tab dikhega jab user **logged in** ho.
- **`<SignedOut>`** — iske andar ka content tab dikhega jab user **logged out** ho.

Clerk **automatically** decide karta hai React tree ka kaunsa part dikhana hai, current auth state ke hisaab se.

```tsx
// pages/index.tsx (landing page — simplified)
import { SignInButton, SignedIn, SignedOut } from "@clerk/nextjs";

export default function Home() {
  return (
    <main>
      <SignedOut>
        <h1>Generate your next big business idea</h1>
        <SignInButton mode="modal" />
        {/* "Get started free" + "Sign in" — dono same kaam */}
      </SignedOut>
      <SignedIn>
        {/* logged-in users ko product page / generator dikhao */}
      </SignedIn>
    </main>
  );
}
```

> Ed dekhta hai ek deprecated cheez use ho rahi hai — bolta hai shayad farak nahi padta, par chaaho toh delete kar do taaki deprecated code na rahe.

### Step 8: JWKS URL ko `.env.local` mein daalo

Yaad hai pichle lecture mein Clerk dashboard (Configure → API keys → right side) se **JWKS / JWT URL** copy kiya tha? Ab use **`.env.local`** mein add karo:

```bash
# .env.local mein add karo
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_test_...
CLERK_SECRET_KEY=sk_test_...
CLERK_JWKS_URL=https://your-app.clerk.accounts.dev/.well-known/jwks.json
```

> ⚠️ Ed warning deta hai: **"You have to get these things identical. No mistakes or you will be pulling your hair out later."** Env var names aur values exactly match karne chahiye.

### Step 9: Back-end dependency — `fastapi-clerk-auth`

Back end (`requirements.txt`) mein ek aur dependency add karo — **`fastapi-clerk-auth`** — yeh back-end code hai jo ensure karta hai sirf logged-in users hi hamare route ko access kar sakein:

```text
fastapi
uvicorn
openai
fastapi-clerk-auth
```

> Ed ka fun aside: wo "route" ko British style mein "root" bolta hai (New York mein rehte hue bhi) — Americans "rowt" bolte hain.

### Step 10: Back-end `index.py` ko protect karo

`index.py` ko replace karte hain. Changes:

- **`fastapi-clerk-auth`** se cheezein import hoti hain.
- Route define karte waqt kuch **credentials** inject hote hain (FastAPI dependency injection ke through), jo ensure karta hai sirf logged-in users access kar sakein.
- Ek line hai jo **user ID ko credentials se nikalti hai** — yeh abhi use nahi hoti, par dikhane ke liye hai: agar tumhari logic depend kare ki kaun logged in hai (jaise subscription plan check karna — jo Day 3 part 2 mein aayega), toh yahan kar sakte ho.
- **Chhota bug fix:** streaming back ka tareeka thoda improve hua hai taaki formatting properly aaye (pehle kabhi-kabhi formatting toot jaati thi).

```python
from fastapi import FastAPI, Depends
from fastapi_clerk_auth import ClerkConfig, ClerkHTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import StreamingResponse
from openai import OpenAI
import os

clerk_config = ClerkConfig(jwks_url=os.environ["CLERK_JWKS_URL"])
clerk_auth = ClerkHTTPBearer(config=clerk_config)
client = OpenAI()

app = FastAPI()

@app.get("/api/generate")
def generate(creds: HTTPAuthorizationCredentials = Depends(clerk_auth)):
    user_id = creds.decoded.get("sub")  # <-- abhi use nahi, par dikhane ke liye:
    # subscription plan/feature checks yahan ho sakte hain

    def event_stream():
        completion = client.chat.completions.create(
            model="gpt-5",
            messages=[{"role": "user", "content": prompt}],
            stream=True,
        )
        for chunk in completion:
            yield chunk.choices[0].delta.content or ""
    return StreamingResponse(event_stream(), media_type="text/event-stream")
```

`Depends(clerk_auth)` ka matlab: har incoming request mein valid JWT hona chahiye, warna FastAPI 401 reject kar dega. Yeh **dependency injection** ka classic auth pattern hai.

### Step 11: Teeno keys Vercel par set karo

`.env.local` mein keys local hain — par Vercel (cloud) ko bhi yeh chahiye. Teeno (publishable key, secret key, JWKS URL) ko Vercel par set karte hain. Har ek ke liye ek command:

```bash
vercel env add NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY
vercel env add CLERK_SECRET_KEY
vercel env add CLERK_JWKS_URL
```

Har command poochegi value (paste karo, exactly `.env.local` jaisa) aur environments (Production/Preview/Development). **Sab environments select karne ke liye `A` press karke Enter** (ya space + enter multiple baar).

> ⚠️ Phir wahi warning: key ka **naam exactly yeh hona chahiye** aur **value `.env` se exact match** — galti hui toh "trouble."

### Step 12: Locally test karo with `vercel dev`

```bash
vercel dev
```

Yeh **pehli baar** kar rahe hain. **Important catch:** `vercel dev` locally sirf **JavaScript part** chalata hai — **Python code locally nahi chalta**. Toh LLM part test nahi hoga, par hum check kar sakte hain ki Clerk se **connection** ho raha hai ya nahi.

App `localhost:3000` par chalta hai. `Cmd+Click` karke kholo:
- UI neat dikhta hai — "Generate your next big business idea... Harness the power of AI..."
- Ed already logged in hai → **sign out** karta hai → **logged-out page** dikhta hai: "Get started free" + "Sign in" buttons (dono same kaam karte hain).
- Click karne par **"Sign in to SaaS"** modal aata hai, "don't have an account? Sign up" option ke saath.
- Tum apna account bana sakte ho, aur wo account **Clerk dashboard** par dikhega (Ed ke paas already 2 Gmail accounts the).
- Ed apne Gmail se log in karta hai → "Here I am" — successfully logged in.

---

## 📋 Key Concepts

| Concept | Matlab |
|---|---|
| **`<ClerkProvider>`** | Root component jo poori app ko wrap karke auth state har jagah available karta hai (React Context pattern) |
| **Protected route** | Page (`product.tsx`) jo sirf logged-in users dekh sakte hain |
| **`<SignedIn>` / `<SignedOut>`** | Conditional components — Clerk auth state ke hisaab se kaunsa dikhana hai khud decide karta hai |
| **`<SignInButton>`** | Sign-in flow trigger karne wala Clerk component |
| **`fastapi-clerk-auth`** | Back-end library jo FastAPI route ko JWT verify karke protect karti hai |
| **`Depends(clerk_auth)`** | FastAPI dependency injection — request mein valid JWT na ho toh 401 |
| **`creds` / user ID** | Decoded JWT se user identity nikalna; subscription/feature logic ke liye |
| **JWKS URL** | Public keys ka endpoint jisse back end JWT signatures verify karta hai |
| **`vercel env add`** | Env var Vercel cloud par set karne ka command (per environment) |
| **`vercel dev`** | Locally run — sirf JS part chalta hai, Python nahi; Clerk connection test ke liye useful |

---

## 💼 Backend Dev Ke Liye Note

Back-end perspective se yeh lecture **auth middleware via dependency injection** ka textbook example hai: `Depends(clerk_auth)` ek FastAPI dependency hai jo har request par JWT ko JWKS public keys se verify karta hai aur fail hone par 401 deta hai — bilkul wahi pattern jo tum custom `verify_token` dependency ya FastAPI security utilities (`OAuth2PasswordBearer`, `HTTPBearer`) se likhte. Decoded token se `sub` (subject = user ID) nikaal kar tum **authorization** (kis plan/feature ka access hai) implement kar sakte ho — authentication (kaun ho) vs authorization (kya kar sakte ho) ka clean separation. JWKS-based verification stateless hai: back end ko Clerk se har request par baat karne ki zaroorat nahi, sirf cached public keys se signature verify karta hai. `vercel dev` ki limitation (Python locally nahi chalta) yaad rakho — Vercel Python functions ko ek serverless runtime mein deploy-time par build karta hai, isliye full integration test deploy ke baad hi hota hai; local mein sirf front-end + auth handshake verify hota hai. Env var parity (`.env.local` ↔ `vercel env`) maintain karna classic config-drift bug ka source hai — dono jagah identical rakho.

---

## ✅ Takeaway

- **App ko `<ClerkProvider>` mein wrap karo** — auth state har component ko available (React Context pattern)
- Generator ko **protected route** (`product.tsx`) mein move karo; `index.tsx` banao landing page **`<SignedIn>`/`<SignedOut>`** components ke saath — Clerk khud decide karta hai kya dikhe
- Back end: **`fastapi-clerk-auth`** + **`Depends(clerk_auth)`** se route protect; decoded creds se user ID nikaal sakte ho (subscription logic ke liye)
- **Teeno keys** (publishable, secret, JWKS URL) `.env.local` AUR Vercel (`vercel env add`) dono jagah set karo — **exact match zaroori**, warna debugging ka dard
- **`vercel dev`** locally sirf JS chalata hai (Python nahi) — Clerk sign-in/sign-out handshake test ho jaata hai

---

<details>
<summary>📜 Full Transcript (English)</summary>

Okay. Next up we're going to take this bit of code right here in step five. And we're going to overwrite our underscore app dot TSX in pages our front end code. So go in here and paste this in. And what is this doing exactly. It's importing a react component called clerk provider. And it's wrapping our entire application in this clerk provider. And this is a way that you can have all of your react components be able to have a sort of shared the the ability to access the functionality in this clerk provider. Um, and I've garbled that a little bit in front end. People that know all about react would be like, well, that's that's slightly oversimplified, but you get the general idea. We've wrapped everything in the clerk provider. Okay, back we go. Next we're going to create a new page, uh, called product TSX. And this is going to be a protected route, which means it's going to be a page which is only available to people that are logged in. and that's going to be called product TSX. And it's going to be in pages. And we have used client at the top there. And it's quite a long page. But it is it's really got the whole content of our business idea generator. So in pages new file, uh, and it's called product TSX. This format that combines TypeScript and HTML. You'll, you'll see that it's got that same markdown component. It's got the same code to stream back events, uh, and uh, save that. Otherwise it is the same. All right. Back we go. Uh, and now we're going to change index TSX to be a new landing page with sign in. A whole thing to do with, with, with signing in. Uh, so let me just take this. And for people that have built this the, the original way before, there were things like Clark, like this was a lot of work. Like this would be like a week's worth of work to build your own sign in page, maybe several weeks worth of work, especially with social auth that that could be like a months worth of work. Uh, but, uh, it's not going to be month's worth of work. Uh, we're going to go to index TSX, which used to be the the whole page. We've moved most of this to products. And now putting in this page, it's relatively short. And really all of the the meat of this page are in these components like sign in button and signed in this component signed in means this is what will show if um, if this is uh, if we've selected if the user is signed in, then this is the part that will be displayed. If the user is not signed in, then the signed out part will show. And automatically Clark is going to handle which parts of this react tree gets shown. And I can see I'm using something which is deprecated there. I don't think it matters, but you can feel free to delete that so that we don't have deprecated code in there. And that all looks good. Okay, so back to the instructions. All of this is done, and now it's time for us to collect that JDBC URL that I showed you a second ago and add it to EMV local. So I'm going to go and do that right now. You remember where to collect it from the configure and the API keys. And then it's over on the right hand side. Collect that and then put it in env local looking exactly like that. You have to get these things identical. No mistakes or you will be pulling your hair out later. Uh all right I'll go do that and see you in a second. Okay. Now it's time to update our dependencies for the back end code, which is in this file requirements.txt. We've just got to add one more in here, the fast API clerk auth, which is the back end code to make sure that only logged in users can access our root. Uh, so we go to requirements.txt and paste it in there. I realized I used the British word root where where the Americans here will be saying root. I can't bring myself to say root. I've lived in New York for a long time, but I still say root and router and the routing from, uh, from from next year's. Uh, okay. So, um, back to the preview. Um, and now we're going to change our index.py. Our backend route. Uh oh. Go away. I don't want to have an update tonight. Uh, we'll have, uh, the backend routes that is going to, um, uh, check that the user is logged in, but otherwise it will be the same. So let's go back to the index.py. Here it is. And replace all of that. Okay. So let me just quickly talk through this. So what's happened here from uh fast API clerk auth, which is the library that handles making sure that we are only logged in. Users use it. We're importing a bunch of things here. And then when we define our route API, we're asking to be passed in some credentials. And we're using this way of making sure that only people who are logged in are able to access this route. Um, and other than that, this is all exactly the same. There is this line here that's not used anywhere. I've got this in here so you can see how you could actually get the user ID out of these credentials. So if you had some logic that depended on who's logged in, this is where you could do it. And it includes you'll find out later on we have subscription plans. You could actually find out what subscription plan they're on and use that to give them access to some functionality and not to others. Okay. Now the very people who are very alert will notice there is a little tiny change here as well, which is I've slightly improved the way this streams back to fix a bug. That meant that sometimes the formatting wasn't all coming through properly. If your formatting wasn't coming through, then with this bug fix, it's going to look a bit better. We will see. Uh, otherwise this is identical. Uh, and so save that, go back to our instructions, see where we are. Um, okay. We've now got to add these three keys that we already saved in a EMV file. We've got to add them to Vercel. cell. So we're going to run each of these three commands. And then we're going to paste in the key as it is in the EMV file. And then select all environments to set it each time which you remember. You press A and enter. Or you can press space and enter lots of times and have to do that for all three. And you mustn't make mistakes here. The key needs to be the key name has to be this name, and the value needs to be the value from EMV. And if you get that wrong, then there's going to be trouble. So don't get it wrong. Uh, and, uh, I will see you in a minute when I've done that myself. Okay. Hopefully you've done that and you did it flawlessly. So all will be well. Hopefully I did too, because if I made a mistake, then you're not going to let me forget it. Uh, but I think I got it right. Okay. Uh, and now we're going to, to run it locally by typing vercel dev. And we've actually not done this before because when you run this locally, it's only going to be able to run the JavaScript part locally. It's not going to run the Python code locally. Uh, so we can't test like the LM part of it, but we will be able to test whether we're connecting to Vercel or not. So here we go. We've deployed it. It's running on localhost on port 3000. So I should be able to command click on this and up it comes. And here we go. Here it is. So first of all check out how neat this looks. Uh, generate your next big business idea. Harness the power of AI to discover innovative business opportunities tailored for the AI agent economy. Uh, so, um, here we go. Now, I'm already logged in. Uh, it knows me already. Hang on. Let me sign out. Uh, this is what you should see. Uh, this is the logged out page. Uh, there's a get started free and a sign in button which do the same thing. They bring you to this sign in to SaaS name of our application, and they don't have an account. Sign up. And what you can now do is experiment with this. Create an account, and you'll be able to see that account appearing on your Clark page like you saw. I already had two set up from my couple of my Gmail accounts, but I could come in now using my my Gmail account. It will log in. Here I am.

</details>
