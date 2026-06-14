# L62 — Automated CI/CD Pipelines for Production AI Apps with Git Deploy

> **Week 2 · Day 5** · ⏱️ ~8 min

---

## 🎯 TL;DR

Pipeline live hai — toh ab ek real code change karke dekhte hain ki auto-deploy kaisa lagta hai: avatar image add karte hain, chat input ka focus-loss bug fix karte hain, favicon + browser tab title sudhaarte hain, aur sirf ek `git push` se sab kuch dev par flawlessly deploy ho jaata hai (4-for-4 green ticks).

---

## 🗣️ Hinglish Explanation

L61 mein humne dekha ki `git push` se deploy hota hai. Ab Ed ek practical demo deta hai: **actual code change → git push → automatic deployment** — yahi CI/CD ki asli value hai. Ek baar pipeline ban jaaye, toh feature ship karna trivial ho jaata hai.

Ed digital twin ko thoda behtar banata hai. Wo Cursor mein **twin repo** kholta hai (jo ab ek proper git repo hai).

### Change 1: Avatar image add karo

Frontend ke **`public`** folder mein ek profile picture (avatar) drop karte hain — jo abhi tak chat ke left side par ek default robot icon dikhata tha.

> Next.js mein `public/` folder static assets ke liye hota hai — jo bhi yahan rakho wo seedha URL se accessible ho jaata hai (e.g. `/avatar.jpeg`). Build ke time yeh as-is serve hota hai, koi processing nahi.

Ed ke paas JPEG hai (PNG nahi), toh wo file ko `avatar.jpeg` naam deta hai aur `public` folder mein paste karta hai (file system se copy-paste).

### Change 2: Twin component update — 2 cheezein

`Twin.tsx` (React component) mein do changes:

1. **Avatar reference** — component ko bolna ki `avatar.jpeg` dhundhe (PNG ki jagah)
2. **Focus bug fix** — wo "tiresome problem" jo shayad irritate kar raha tha: har baar **Enter** dabane par chat input field **focus kho deta** tha, aur dobara click karna padta tha next message bhejne ke liye. Infuriating! Ed ne pehle promise kiya tha ki fix karenge — aur jaan-bujhke isse `git push` auto-deploy demo ke liye save rakha tha.

Ed naya version (basically same + couple of extra parts) `Twin.tsx` mein select-all → paste → save karta hai. Phir **Find & Replace** se `avatar.png` ko `avatar.jpeg` se replace karta hai (comments tak — kyunki uske paas JPEG hai; agar tumhare paas PNG hai toh yeh step skip karo).

### React focus bug — yeh kyun hota hai?

Background: yeh ek classic React gotcha hai. Jab tum form submit karte ho (Enter par), agar component **re-render** hota hai aur input ka identity/key change ho jaaye, ya parent state update se input unmount-remount ho, toh browser **DOM focus** lose kar deta hai. Fix typically yeh hota hai: form submit ke baad input par programmatically `inputRef.current?.focus()` call karna, ya re-render ke dauraan input ko stable rakhna (key na badle). Ed ka naya `Twin.tsx` version yahi handle karta hai — submit ke baad focus wapas input par aa jaata hai.

```tsx
// Concept: submit ke baad focus wapas laana
const inputRef = useRef<HTMLInputElement>(null);

const handleSubmit = async (e: React.FormEvent) => {
  e.preventDefault();
  await sendMessage(input);
  setInput("");
  inputRef.current?.focus();   // focus wapas, click karne ki zaroorat nahi
};

// Avatar bhi default robot ki jagah
<img src="/avatar.jpeg" alt="avatar" />
```

### Change 3: Browser tab title + favicon

Ed notice karta hai ki app **janky** lagta hai — browser tab par title "Create Next App" dikhata hai (default Next.js title), aur **favicon** (tab ka chhota icon) bhi standard Next.js icon hai. Amateur lagta hai. Fix karte hain:

**Favicon hatao**: `app` folder mein default `favicon.ico` hota hai (Next.js ka) — usse **right-click → Delete (Move to Trash)**.

**Title badlo**: `app` folder ke **`layout.tsx`** mein `metadata` hota hai. Title "Create Next App" ko change karo:

```tsx
// app/layout.tsx
export const metadata: Metadata = {
  title: "Donna's Digital Twin",
  description: "An AI career twin for Ed Donner, representing Ed Donner along with recent news",
};
```

**Naya favicon**: apna custom favicon banao (Google par "favicon generator" se endless tools milte hain) aur usse `app` folder mein drag karo. Next.js automatically `app/favicon.ico` ko tab icon ke roop mein use karta hai.

> ⚠️ Ed warning deta hai: **favicons browser dwaara cache** hote hain. Deploy ke baad bhi shayad turant naya favicon na dikhe — browser cache clear hone par hi update hoga.

### Next.js App Router metadata — kaise kaam karta hai

Background: Next.js (App Router) mein `app/layout.tsx` ka `metadata` export `<head>` tags generate karta hai — `<title>`, `<meta name="description">` etc. Yeh SEO aur browser tab ke liye important hai. Aur `app/favicon.ico` ek **file-based convention** hai — Next.js automatically isse `<link rel="icon">` bana deta hai. Isliye custom favicon ke liye bas file replace karni hoti hai.

### Step: Deploy — sirf ek git push

"Itna saara kaam karna padega deploy ke liye?" — Nahi! Bas:

```bash
git status        # changed files dekho: favicon, layout, Twin.tsx, public/avatar
git add .
git status        # double-check — 4 changes ready
git commit -m "Various UI refinements"
git push
```

Push ke baad: kahin internet par GitHub VM spin up karta hai, workflow chalta hai, S3 buckets mein Terraform state dhundhta hai, AWS hit karta hai — sab automatic.

GitHub → **Actions** → "Various UI refinements" workflow running → "deploying to dev" → CloudFront step (hamesha ka slow part) → complete.

### Result — 4 for 4

GitHub Actions par **4-for-4 green ticks**. Workflow → "Deploy to dev" → scroll → **Deployment Summary** → CloudFront URL.

Live results:
- Browser tab: **"Edna's Digital Twin"** (naya title — baaki environments se alag, kyunki sirf dev par push hua)
- Favicon abhi update nahi hua (browser cache — Ed ne warn kiya tha) — kabhi update ho jaayega
- Chat kholte hi **avatar** dikha
- "Hi there" type karke send → avatar thinking mein dikha → aur **focus wapas input par** — ab click karne ki zaroorat nahi!

**UI refinements deployed — flawlessly, 4 out of 4.** Ed point banata hai: itna **incredibly easy** hai — app mein changes karo, `git push`, aur **Bam!** live on the internet, publicly available. Yahi CI/CD ka real-world payoff hai.

---

## 📋 Key Concepts

| Concept | Matlab |
|---|---|
| **`public/` folder (Next.js)** | Static assets — yahan rakhi file seedha `/filename` URL par accessible |
| **`Twin.tsx`** | React component jo chat UI render karta hai |
| **React focus bug** | Submit par re-render se input focus loss — `inputRef.focus()` se fix |
| **`useRef` + `.focus()`** | Programmatically input par focus wapas laana |
| **`app/layout.tsx` metadata** | Browser tab title + description set karta hai (App Router convention) |
| **`app/favicon.ico`** | File-based favicon convention — Next.js auto `<link rel=icon>` banata hai |
| **Favicon caching** | Browser favicon cache karta hai — deploy ke baad turant update na ho |
| **`git push` → auto deploy** | CI/CD ka real payoff — ek push = live production update |

---

## 💼 Backend Dev Ke Liye Note

Backend dev ke liye yeh lecture **developer experience (DX)** ka demonstration hai jo achhi CI/CD se aata hai. Saara heavy lifting (Terraform, IAM, OIDC, workflows) ek baar setup ho gaya — ab feature velocity dramatically badh jaati hai. Yeh exactly woh "**deployment shouldn't be the bottleneck**" philosophy hai jo modern platform engineering follow karti hai. Frontend specifics (React focus bug, Next.js metadata) shayad tumhare daily kaam mein na aayein, par underlying lesson universal hai: jab pipeline reliable ho, tum **small frequent deploys** kar sakte ho (continuous delivery), bade risky big-bang releases ke bajaye. Favicon caching wali baat bhi backend caching principles ko echo karti hai — kuch bhi tum cache karte ho, uska **cache-busting / invalidation** strategy chahiye (yahan static assets ke liye content-hashing ya versioned filenames standard hain). Aur `git status` ko commit se pehle do baar check karna — yeh disciplined habit production safety ke liye valuable hai.

---

## ✅ Takeaway

- **Code change → `git push` → auto deploy** — yahi CI/CD ka real-world payoff hai
- `public/` folder mein static assets (avatar) — seedha `/filename` URL par accessible
- **React focus bug** fix: submit ke baad `inputRef.current?.focus()` — input se focus na khoye
- Browser tab polish: `layout.tsx` metadata se **title**, `app/favicon.ico` se **favicon** — par favicon **browser cache** hota hai
- Ek hi `git push` se 4 changes flawlessly deploy (4-for-4 green ticks) — feature shipping trivial ho gaya

---

<details>
<summary>📜 Full Transcript (English)</summary>

And another thing. Just one more thing to wrap this up. Let's make a change to the code. Let's change something in the code. Do a git push. See it all happen automatically. Let's make our digital twin a bit better. And let's start by adding a little profile. Picture an avatar to appear instead of that little robot on the left. It's a tiny thing, but it's kind of fun. So if you look in front end in, I'm back in cursor, obviously looking at the twin, uh, project, which is now a repo, I can now say looking at the twin repo front end, look at the public folder. Uh, we're going to drop in this folder a new file called avatar, which should be your favorite little profile picture of yourself. I've dropped one right here. I don't have a PNG, I've got a JPEG, so I'm going to make it avatar JPEG. Um, and I'm dropping that in the public folder. Move. There we go. You can copy and paste it from your file system avatar JPEG. And now we're going to update the twin component. And we're actually going to make two changes to the twin component points. We're going to update it to look for avatar or JPEG. And we're also going to fix that tiresome problem that has probably been irritating you that when you're chatting with your twin, every time you press enter, that field loses focus and you have to click back in it again to send your next message. Infuriating. And of course, we should fix it. I mentioned we were going to fix it, and you might have been thinking I forgot about that because it was ages ago, but I didn't forget. This is what I had in store for you fixing it when we do the git push for an auto deploy. All right. So we're going to select this right here this new version. Here it is. Here it is. It's it's I mean it's basically the same just just with those couple of extra parts in it. So I'm now going to go back. It feels like such a long time ago. We were in twin TSX, select all paste and save and now all I have to do myself is just look for avatar PNG and replace it with with avatar JPEG. So let's do avatar dot png. Uh, so I will change even the comments to JPEG. You don't need to do this if you have a PNG file. Uh, where next. And here. And where next? Here. Oopsie. There we go. Selected everything. Jpeg. And one more. Yeah. There we go. JPEG. Done. No more results. Save. All right. It's now avatar JPEG for me. Still PNG for you, I hope. And, uh, that is our change. Okay, back to the guide. Let's see what we're meant to do next. We just meant to commit and push the fix. There's one other change I want to make as well for the other change. Have you noticed? It looks a bit janky that when we bring up our digital twin, the. The title says, like, create next app or something? Um, and it just looks a little bit amateur. And the favicon, the little, uh, icon in the in the browser tab is like a is like a standard. Uh, I think it's a next app kind of icon. We should fix those things right now. So it's actually super easy to fix. Uh, we just come up to the app folder and you'll see in there is a favicon, uh, icon, which let's see what it is that, that is the Next.js. So we want to get rid of that, which we'll just right click and delete it, move to trash. And uh, then there's also a layout page which has within it this title create next app. Let's change that to honor, uh, Donna's digital twin. There we go. That will do. Description. An AI AI career twin for ad Donna. Uh, representing ad Donna. Okay. Along with recent news, cursor thinks, uh, okay, this seems good. Uh, and I just have to. I've also got my, uh, favicon right here. I just made a little, little favicon. If you don't know how to make them, then, then you just Google it. There's, like, endless, uh, tools for this, and I just have to drag that. Let's just collapse some of these other things that are holding me up here. Collapse that. And where does it need to go? It needs to go in the app page. Um, here it is. Favicon goes in the app folder. I mean there it goes. Move in it goes. I should mention when we, when we deploy this favicons get cached by the browser. So this this little extra piece might not actually appear. Uh, but anyways, that's another change for us to make. Uh, so those are a few minor enhancements. What do we do next? Well, we have to do so much work to go and and, uh, prepare everything for deployment. No, we don't. Of course, it's going to be very simple. Git status. Uh, there are the files we've changed. We've we've added the favicon, we changed the layout, we changed TSX, and we put, um, an avatar in it. End public. Right. That's where we were told to put it. Yes. Okay. Good. So now we do uh git add dot git status again. Always worth checking what we see. There are our four changes ready to be made. Git commit. Various UI refinements. And we do a git push and that should be it. Git push. There we go. Off it goes. Somewhere on the internet. GitHub is whirring up and it's setting up its VM. It's running the workflow. It's going to be looking in our S3 buckets for Terraform states. That's going to be hitting AWS. Everything will be happening. Let's go and take a look. I've just quickly I've gone over to GitHub. I've gone to actions. We can see that this is busily running various UI refinements. It's happening deploying to dev. It's been going for a minute. It's currently uh. No doubt. Uh, where are we? It's, uh it's it's moving pretty quickly. It's, uh, in our favorite place. No surprise. Shockingly. And, uh, I will let this do its thing, and I'll be right back with you. Well, here we are, back at GitHub actions again, and we're four for four for green ticks. That's what I like to see. Uh, okay. So now we go into this workflow into deploy to dev. We scroll down, we go to Deployment Summary and we have a CloudFront URL right here. We'll add it in here. First thing you notice right away Edna's digital twin. We've got a different title to the others. As I warned you, the favicon hasn't updated because browsers cached them, but hopefully that will at some point update. But it's cool to see that change immediately there. Hello, I'm interested to see that avatar. Were you expecting that as well? Uh, and now I'll say hi there and we press send that in and you can see my little avatar there as I'm thinking. And you can see we've got focus back there. No more need to click any more. Our UI refinements have been deployed. It worked perfectly flawlessly. Four times out of four. You've just seen how easy it is, how incredibly easy it is to make some changes to the app, do a git push and Bam! They're deployed live on the internet, available publicly. I would say that that is success.

</details>
