# L18 — Adding Authentication and Billing to Production AI Applications

> **Week 1 · Day 3** · ⏱️ ~11 min

---

## 🎯 TL;DR

Day 3 ka wrap-up: hum `product.tsx`, `index.tsx` update karte hain taaki **Clerk** subscription status check kare — agar user subscribed nahi hai toh Clerk ki auto-generated **pricing table** dikhe, agar hai toh idea generator. Production deploy karke pura flow (Google + Apple social auth → subscribe with test card → access premium) live test karte hain.

---

## 🗣️ Hinglish Explanation

### Context: kahan se aaye, kahan ja rahe hain

Pichle teen lectures (L15–L17) mein humne **Clerk** add kiya — pehle user authentication (sign-in/sign-up, social auth), phir billing/subscription plans setup kiye Clerk ke dashboard mein. Ab is lecture mein hum **frontend code ko update** karte hain taaki wo subscription state ko respect kare, aur phir **production mein deploy karke poora end-to-end flow** test karte hain. Yeh Day 3 ka final lecture hai.

Recall: **Clerk** ek drop-in auth + billing platform hai. Pehle ke zamane mein user authentication (passwords, sessions, OAuth with Google/Apple/GitHub) + payment integration (Stripe) banana ek **multi-month, multi-person project** hota tha. Clerk yeh sab ready-made React components + hooks ke through 1 din mein de deta hai. (Iske jaise aur bhi hain — Auth0, Supabase Auth, NextAuth — par yeh course Clerk use karta hai.)

### Step 1: `product.tsx` ko subscription-aware banao

`pages/product.tsx` ka pura content replace karte hain. Naya code thoda bada hai. Iska core ek Clerk component hai — **`<Protect>`**:

```tsx
import { Protect, PricingTable } from "@clerk/nextjs";

export default function ProductPage() {
  return (
    <Protect
      plan="premium_subscription"
      fallback={
        <div>
          {/* Agar user ke paas plan nahi hai toh yeh dikhta hai */}
          <PricingTable />
        </div>
      }
    >
      {/* Yeh tabhi render hota hai jab user ka 'premium_subscription' plan active ho */}
      <IdeaGenerator />
    </Protect>
  );
}
```

Samjho yahan kya ho raha hai:

- **`<Protect plan="premium_subscription">`** — Clerk ko bolta hai "is content ko sirf tab dikhao jab logged-in user ka `premium_subscription` plan active ho".
- ⚠️ **CRITICAL gotcha**: `plan` ka value **exactly match** karna chahiye us **plan ID** se jo tumne Clerk dashboard mein banaya tha. Agar tumne "premium subscription" ki jagah kuch aur naam diya tha, toh wahi ID yahan likhni hogi. Mismatch = protection kabhi pass nahi hogi.
- **`fallback={...}`** — protection fail hone par (user logged out ya unsubscribed) yeh UI dikhta hai. Isme Clerk ka **`<PricingTable />`** component hai.
- **`<IdeaGenerator />`** — yeh hamara actual product UI hai (wahi business-idea generator jo abhi tak banate aaye hain). Yeh tabhi render hota hai jab protection pass ho jaaye.

**`<PricingTable />`** ek aur Clerk magic component hai: yeh **automatically** tumhare dashboard mein configured plans (free + premium, prices ke saath) ko ek side-by-side comparison table ke roop mein render kar deta hai. Tumhe pricing UI khud likhni nahi padti — Clerk apne backend data se generate karta hai (isiliye yeh hamesha sahi price dikhata hai).

File save karna mat bhoolo (white blob = unsaved).

### Step 2: `index.tsx` (landing page) update karo

Landing page (`pages/index.tsx`) mein subscription/pricing **preview** information add karte hain. Iska content bhi replace karte hain. Dhyaan dene wali baatein:

- Ek **signed-in section** hai — yeh tab dikhta hai jab user logged in ho (Clerk ke `<SignedIn>` / `<SignedOut>` components se control hota hai).
- Ek **pricing preview** hai jo prices show karta hai.

⚠️ **Important subtlety**: yeh landing-page pricing preview **hum hand-code karte hain** — yeh Clerk se generate nahi hoti. Ed ki video mein yeh hard-coded price dashboard ke actual price ($100/month) se **match nahi karti**. To do for you: isse update karke apne actual Clerk price se match karna. Yaad rakho — **landing page ka pricing = tumhara code (galti ho sakti hai); `/product` page ka `<PricingTable />` = Clerk-generated (hamesha sahi)**.

### Step 3 (optional): Stripe connect karna

Code mein ek section hai jahan agar tum **"for reals"** real payments chahte ho, toh tum **Stripe** connect kar sakte ho. **Stripe** duniya ka sabse popular payment-processing platform hai — cards, subscriptions, invoices, refunds sab handle karta hai, aur developers ise iske clean API ke liye bahut pasand karte hain. Clerk billing internally Stripe ke saath integrate ho sakta hai.

Is lecture mein hum **test billing provider** hi rakhte hain (Clerk ka built-in test mode jisme fake "test cards" chalte hain — koi asli paisa nahi katta). Production ke liye tum Stripe enable karke real revenue le sakte ho.

### Step 4: Production deploy karo

```bash
vercel --prod
```

Build ko ek minute do, phir production URL kholo. Pehle landing page aata hai with the nice subscription panel.

### Step 5: End-to-end test — existing user (subscribed)

1. **Sign in** click → **Google account** se continue → logged in.
2. Top-right par **Manage account** → **Billing** tab → dikhta hai "premium subscriber" (Ed ne pehle hi test subscription le li thi, fake Visa number test-mode mein stored hai).
3. **Access Premium features** dabao → kyunki user (a) logged-in hai aur (b) paid subscriber hai, protection pass → **idea generator** load hota hai → GPT-5 se business idea stream hota hai. Working!

### Step 6: End-to-end test — brand new user (Apple Sign In + subscribe)

Ab ek naya user simulate karte hain jiska koi subscription nahi:

1. **Sign in** → **Apple authentication** choose karo → Apple ID enter karo.
2. **Two-factor authentication** (2FA) aata hai → verification code (e.g. `632102`) enter → "Verifying trust" → done.
3. 🔑 **Clever trick — "Hide my email"** choose karo. Wajah: agar tum apna asli Gmail share karte, toh **Clerk smart hai** — wo pehchaan lega ki yeh email pehle Google auth se sign-in kar chuki hai, aur dono identities ko **same user ID** se associate kar dega (account linking). Naye user ka clean test karne ke liye, Apple ka "Hide my email" relay address use karte hain taaki Clerk ek **naya user** banaye.
4. "Verify human" (CAPTCHA) → back to app.
5. Ab `premium_subscription` protection **fail** hoti hai (kyunki yeh naya user unsubscribed hai) → Clerk ka **pricing table** dikhta hai with free vs premium options.
6. **Choose my plan** → **Subscribe** → checkout aata hai with **test card**.
7. Pehle Ed annual plan (expensive) select karta hai, phir cancel karke **billed monthly $100/month** choose karta hai → **Subscribe** → **Pay with test card** → "$100" → "Payment was successful from the test card" → **Continue**.
8. Ab user subscribed hai → **Access Premium features** → idea generator → business idea generate ho gaya. Complete new-user signup + subscribe flow working!

### Summary: poora flow ek nazar mein

Jab user `/product` visit karta hai:

```
User visits /product
        │
        ▼
Clerk checks subscription status (<Protect plan="premium_subscription">)
        │
   ┌────┴─────┐
   │          │
No subscription   Has subscription
   │          │
   ▼          ▼
<PricingTable>   Show <IdeaGenerator>
(Clerk-generated)
   │
   ▼
Payment flow (Clerk billing → test card OR real Stripe)
   │
   ▼
Now subscribed → idea generator unlocked

(Users can also manage subscriptions later via "Manage account" → Billing)
```

Ed baar-baar emphasize karta hai: yeh sab **pehle months ka kaam tha** — full social auth + Stripe integration. Clerk (aur iske jaise tools) ne ise trivially easy bana diya hai. 15% course complete! Kal Day 4 — app ko ek real **business functionality** denge (healthcare vertical).

---

## 📋 Key Concepts

| Concept | Matlab |
|---|---|
| **`<Protect plan="...">`** | Clerk component — content sirf tab render karta hai jab user ka woh plan active ho; warna `fallback` dikhata hai |
| **plan ID matching** | `<Protect>` ka `plan` value dashboard ke plan ID se exactly match karna mandatory; mismatch = always fails |
| **`<PricingTable />`** | Clerk auto-generates pricing UI dashboard plans se — hamesha sahi price; hand-code nahi karna padta |
| **`fallback`** | Protection fail hone par dikhaya jaane wala UI (yahan pricing table) |
| **`<SignedIn>` / `<SignedOut>`** | Clerk conditional components — login state ke hisaab se UI dikhate hain |
| **Test billing provider** | Clerk ka test mode — fake test cards, no real money; production mein Stripe se replace |
| **Stripe** | Sabse popular payment processor (cards, subscriptions, refunds); Clerk billing iske saath integrate hota hai |
| **Account linking** | Clerk same email ko alag-alag auth providers se associate karke ek hi user ID rakhta hai |
| **"Hide my email"** | Apple relay address — naya distinct user banane ke liye, taaki Clerk account-link na kare |
| **`vercel --prod`** | App ko production environment mein deploy karne ka command |

---

## 💼 Backend Dev Ke Liye Note

Python backend dev ke liye yeh lecture **authorization (authz) vs authentication (authn)** ka clean live example hai. `<Protect plan="premium_subscription">` essentially ek **entitlement check** hai — exactly waisa hi jaisa tum FastAPI mein ek dependency banate ho:

```python
def require_premium(user = Depends(get_current_user)):
    if "premium_subscription" not in user.active_plans:
        raise HTTPException(403, "Subscribe to access")
    return user
```

Farak sirf yeh hai ki Clerk yeh check **frontend pe declaratively** kara raha hai. Par **golden rule yaad rakho**: client-side `<Protect>` sirf UX hai — koi bhi attacker frontend bypass karke directly tumhara `/api` route hit kar sakta hai. Production mein **backend par bhi** subscription/entitlement verify karna chahiye (Clerk ke server-side SDK / JWT claims se). Lecture ne abhi tak `creds` (Clerk credentials) backend ko pass kiya hai — wahin par entitlement enforce karna chahiye, sirf UI gating par bharosa mat karo. Account-linking concept bhi note-worthy: identity de-duplication (ek user ke multiple OAuth providers ko ek canonical user record se map karna) har serious auth system ka core problem hai.

---

## ✅ Takeaway

- **`<Protect plan="...">`** subscription-gated content ka core hai — plan ID dashboard se **exactly** match hona chahiye, warna kuch render nahi hoga
- **`<PricingTable />`** Clerk khud generate karta hai (always-correct price); landing-page ka hand-coded price galat ho sakta hai — usse manually sync karo
- Test billing provider = fake cards, no real money; production ke liye Stripe enable karo
- "Hide my email" trick se naya distinct user test kiya — Clerk warna same email ko account-link kar deta
- Full social auth + billing jo pehle months lagte the, ab Clerk ke saath 1 din mein — **15% course complete**

---

<details>
<summary>📜 Full Transcript (English)</summary>

So now we're going to update our code to expect this. So in the products page we're going to make an update so that it knows to check that uh that, that we are uh, subscribed to the product before we use it. So this is product, uh, let's take all of this. It's, uh, there's quite a lot to it now, as you can see, uh, product TSX, which is under pages. Here we go. Product select all paste it in and you can see what's if you take a look here uh, you can see this this protect tag here. Protect element um which says which is tied to the plan premium subscription. So this needs to match exactly the plan ID that you set up in Clark. If you didn't use premium subscription, then whatever you did use must go here. Uh, then there's a fallback to pick a different plan, uh, and a pricing table, but otherwise, uh, the this is all this fallback is what happens if if the protection fails. But if the protection succeeds, then it will have the idea generator will be shown. And the idea generator is basically what comes up here. It is this object here, idea generator, which is itself the user interface that we're used to for our product. So this I am going to save right now okay. And finally we're going to update the landing page with some of the subscription information. So that landing page is indexed. So I take what I've got here. And we are going to paste that into Index.ts select all paste save. And if you look through this you'll see a few things to look out for. Um this is if you're if you are signed in, um, and this is where the subscription information, the pricing preview is laid out. Uh, so you'll see that there's some information in there. But all in all, it's very simple. Anyone that's built like a subscription system before is probably used to this being a lot of work, taking a lot of time, and it's pretty neat that this is all fairly easy as long as it works, see if it works. Uh, so there is one, um, section here. And if you wanted to, how you could connect stripe if you wanted to go. Really? For reals. But we're not going to do that. We're just going to keep the test billing provider. But but as I say, that's certainly, uh, up to you should you wish to have a proper payment system. But given this, we are now going to deploy this to production and see whether or not in just a day, just a few hours, we have built something which has subscription plans, attached a billing system as well as the user authentication system too. So we'll give it a minute to build and then we'll go and give it a whirl. Okay. And here I go. I'm going in to launch the production application. Here it comes. Uh, and it comes up right away with the, uh, the nice little panel here. Now, you can see that that hard coded in index in this sort of preview where the prices which don't actually match what I, what I put in the back end. So we need to update this to show whatever pricing you actually put in, Clark. In this case $100 a month. Uh, this is not being generated by Clark, but but you'll see that there is another one that is, uh. And I can now sign in. I can come in with my Google account, and here we go and continue. And we are in. But when I go to access premium, first of all, if I click here, I can see there's a manage account. And uh, right here, if I go to billing, you'll see that I am already a premium subscriber because I tested this already and I subscribed. And it's got a fake visa number in there because we're on the test version so we can set this up. And, uh, this is all all set up, and I've paid them and you'll see that that detail is all there. So this is my account profile, which is all set up. And I can now press Access Premium features because I'm logged in and because I'm logged in and I'm a paid subscriber, I get through to the product itself. It's all working. It's generating the business idea. And let's see what happens at the end of this. As GPT five is, uh, furiously figuring out what to do. See if we get the same, same idea again. We have got nice headings this time, which is good to see. Uh, autonomous next agent Nexus, agent studio, autonomous AI agent network for SMB automation. It seems to be the same, same idea with a slightly different framing of it. Uh, but it looks great. I like the look of this. Uh, it all seems to be working very nicely indeed. Hopefully you've had to subscribe first and then you've got this. Uh, but I think, uh, you will hopefully be impressed by how straightforward it's been to add subscription functionality to our AI product. So let's also try and sign in with a new account that doesn't have a subscription plan. So if I press sign in, I'll go in with an Apple authentication, try and sign in to my Apple account. I'll need to enter my Apple ID, uh, which which is just my Gmail account. There it is. Uh, Apple.com fill in. Uh, and, uh, I can continue with passcode and do this. Okay. And let's see what happens. Now I'm getting two factor authentication. Hang on. Oh, I can just allow it myself. Uh, um, and, uh, enter this verification code. This is a bit. So 632102. 632102. Verifying trust. Okay. Done there. Uh, let's do hide my email for a very subtle reason, which is that Clark is smart enough. If I shared my email, uh, my gmail gmail.com, Clark will recognize that I've already signed in with Google auth, and it will just associate all these authors and it won't create a new user ID. So I have to do this to make sure that I get signed in as a new user. Here we go. Oh verify human. And we're back over here. So it's saying that the premium subscription again it's showing this and I press on choose my plan and we get this screen here, which is where we can choose the free version or the premium subscription. And I can press subscribe. And if I do this, it comes up with a pay, with a test card, with a card number. And I can then choose this rather expensive. Maybe we should come out of this and just do do a monthly instead. So we'll come out of the checkout. We'll go to billed monthly $100 a month. What a bargain. Press subscribe for $100 a month. And now we do pay with test card. Pay $100. Uh, and you can see it's got the test card number. Press that. And payment was successful from the test card. Continue. And now we're in access premium features. And we've just subscribed to the plan. Uh, we first of all, we authenticated with my Apple ID, which is kind of cool to see all of that working perfectly. Then we came in, we subscribed, and we've gotten ourselves a business idea because we're paying the $100 a month. Uh, what a great bargain. $100 a month for this idea. And that is showing the complete new user sign up flow and the and the subscribing flow. All working with our clerk app. Well, that was a lot that we went through. I hope you enjoyed that. I was a little bit, uh, flummoxed by the Apple signing process, but happy that it worked, uh, and that you saw everything coming together as a quick summary of what we just just saw when the user visits the slash product, uh, part of our application clerk is checking our subscription status. If we don't have a subscription, it's showing that pricing table component. Those that that thing you saw with the two prices side by side was generated by clerk, not by us. We wrote the code that was on the landing page with the wrong price. Uh, but we wrote that code. The one we saw with the table with the right price was generated by clerk. Uh, if they already have a subscription, we just show the idea generator. But if not, then. Then we go through a payment flow which is handled by clerk billing. And there was that test approach to user test card. But it could be done with real billing and it could be optionally through stripe. And then users can also manage the subscriptions. You saw that earlier when I went in as my main user. So that was a lot that we got done. And again, I know I've said this several times, but it's true. This is the kind of thing that used to take so long to do. This would be a several month project, typically for several people to build the whole user authentication with social auth, and then build in something like stripe integration. And Clark makes that super easy. And there are there are several others like it. So, uh, hopefully you now feel like you can use that for your own apps and you know, how to deploy in production with subscription and with, uh, the different subscription plans and user authentication. And that's it. That concludes day three of the course. We've just done both parts of it, authentication and subscription. And it went so quickly. If you feel like it was a bit overwhelming, go back through. Read the code. You only need to feel a flavor for what's going on with the front end code, but you need to have a good sense of how it all fits together. So do take a look through it. Make it your own. Change it up. Push it out there. Post on LinkedIn. If you post these things on LinkedIn and tag me, then I'll weigh in. Of course I'll give it a try myself. I love doing that. I give, I give people's apps that post up with me on LinkedIn all the time, and I'd love to see yours. So. So please do that tomorrow. We're going to then change this to actually have some business functionality. Again, it's going to be super simple for now. But but your mission is going to be to make it more sophisticated. And we're going to pick healthcare. It's a super interesting vertical where there's so much opportunity to apply AI. It's coming up tomorrow. For now, you need to take a moment to celebrate that you are 15% on your way to production expertise. 15% you are crushing it. We're going through it so fast and I will see you for day four tomorrow.

</details>
