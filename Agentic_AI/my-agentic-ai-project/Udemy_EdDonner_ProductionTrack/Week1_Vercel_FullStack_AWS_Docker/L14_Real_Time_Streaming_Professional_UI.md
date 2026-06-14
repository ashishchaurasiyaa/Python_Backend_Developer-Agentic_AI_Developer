# L14 — Adding Real-Time Streaming and Professional UI to Your LLM App

> **Week 1 · Day 2** · ⏱️ ~10 min

---

## 🎯 TL;DR

Day 2 ko finish karte hue hum apne business idea generator mein **real-time streaming** (SSE) add karte hain taaki LLM ka output token-by-token aaye, phir **React Markdown** + Tailwind se output ko professional dikhne wala banate hain — aur ek nayi cheez seekhte hain: Vercel ke **preview vs production** environments.

---

## 🗣️ Hinglish Explanation

### Recap: hum kahan the

Day 2 mein ab tak humne ek full-stack app banaya — **Next.js (pages router) front end** + **Python FastAPI back end** — aur usse Vercel par deploy kiya. App ek "business idea generator" hai: button dabao, GPT-5 ek naya AI agents business idea generate karta hai. Lekin abhi tak do problems hain:

1. **Streaming nahi hai** — pehle pura response generate hota hai, phir ek saath screen par aata hai. User ko lambe time tak khaali screen dikhti hai (GPT-5 thinking models slow hote hain).
2. **Output plain text hai** — koi formatting nahi, ugly dikhta hai.

Aaj dono fix karenge. Ed bolta hai instructions mein `vercel --prod` suggest hota hai, par wo **strictly required nahi** — hum already production mein deploy kar chuke hain. Pehle streaming + styling add karenge.

### Step 1: Markdown packages install karo (front end)

React ki sabse badi taakat uska **huge ecosystem** hai — har cheez ke liye off-the-shelf library milti hai. Markdown ko ek front-end widget mein render karne ke liye hum kuch npm packages install karte hain. SaaS folder ke andar:

```bash
npm install
```

> 💡 Ed ka analogy: **"npm install for front-end people is like pip install for back-end people like me."** Node Package Manager (npm) JavaScript world ka pip hai — `package.json` mein listed dependencies download karke `node_modules/` mein daal deta hai.

Yeh command React Markdown aur related packages (jaise `remark`/`rehype` plugins) install karega.

### Step 2: `index.tsx` update — streaming handle karna

Ab front-end page ko update karte hain taaki wo server se **streaming data** ko handle kare. GitHub instructions se naya `index.tsx` copy karke purane ko select-all karke replace karte hain.

Naye code mein do important cheezein hain:
- **Streaming handling** — server se data tukdo (chunks) mein aata hai, code use incrementally screen par dikhata hai jaise jaise aata hai.
- **React Markdown component** — ek ready-made React component jo plain text ki jagah markdown leta hai aur use nicely formatted HTML (headings, bullets, bold) mein convert karke dikhata hai.

```tsx
import ReactMarkdown from "react-markdown";

// ...streaming loop ke andar accumulate kiya hua text:
<ReactMarkdown>{generatedText}</ReactMarkdown>
```

Yeh **classic React pattern** hai — koi heavy cheez khud likhne ki bajaye ecosystem se ek tested component utha lo.

### Step 3: Tailwind plugin install karo

Markdown component ko sahi se kaam karne ke liye ek plugin chahiye. Instructions mein ek aur npm install command hai — terminal mein wapas jaake chalao:

```bash
npm install
```

Instructions mein har Tailwind class ka chhota description bhi hota hai — Ed kehta hai padh lo, intuition aa jaayega ki har class kya karti hai. (**Tailwind** ek utility-first CSS framework hai — alag CSS file likhne ki jagah tum directly HTML/JSX mein `text-lg`, `font-bold`, `px-4` jaise small utility classes lagate ho.)

### Step 4: Back end `index.py` update — SSE streaming

Ab back end ko update karna hai taaki wo client ko results **stream** kare. Naya `index.py` paste karte hain. Key changes:

- **OpenAI client call** mein `stream=True` pass hota hai — iska matlab API pura response ek saath nahi, balki token-by-token bhejti hai.
- FastAPI se hum **`StreamingResponse`** return karte hain — yeh ek special FastAPI type hai jo data ko continuously bhejne deta hai.
- Underlying transport **SSE (Server-Sent Events)** hai — ek standard tareeka jisse server client ko ek hi long-lived HTTP connection par events push karta rehta hai.

```python
from fastapi.responses import StreamingResponse
from openai import OpenAI

client = OpenAI()

@app.get("/api/generate")
def generate():
    def event_stream():
        completion = client.chat.completions.create(
            model="gpt-5",
            messages=[{"role": "user", "content": prompt}],
            stream=True,  # <-- token-by-token streaming on
        )
        for chunk in completion:
            delta = chunk.choices[0].delta.content or ""
            if delta:
                yield delta  # har token client ko push karo
    return StreamingResponse(event_stream(), media_type="text/event-stream")
```

> **SSE vs WebSocket:** SSE ek-tarfa (server → client) streaming ke liye perfect hai aur plain HTTP par chalta hai — LLM token streaming ka classic use case. WebSocket two-way hota hai (chat jaisi cheezein), par yahan zaroorat nahi.

### Step 5: Preview environment par deploy 🚀

Ab deploy:

```bash
vercel .
```

Yahan **ek naya important concept** aata hai. Vercel ke paas multiple environments hote hain:

| Command | Environment | Kab |
|---|---|---|
| `vercel .` | **Preview** | Pehli deploy ke baad har baar |
| `vercel --prod` | **Production** | Jab production par bhejna ho |

- **Pehli baar** jab tum koi project deploy karte ho → wo automatically **production** mein jaata hai (jaise Day 1).
- **Subsequent deploys** `vercel .` se → **preview** environment mein jaate hain. Production wala purana URL chalta rehta hai, naya code alag preview URL par dikhta hai.

Yeh **safe iteration** ka pattern hai — naye changes preview par test karo, jab confident ho tabhi production par push karo. Deploy hone ke baad terminal mein **preview** URL aata hai; `Cmd+Click` karke kholo. GPT-5 thinking karta hai (slow), phir output **nicely streaming** aata hai — scroll se bhi fast! (Agar `gpt-4.1-nano` ya `gpt-4o` jaisa fast model hota toh aur turant aata.)

Note: preview mein abhi bhi **markdown render nahi ho raha** — "hold that thought," Ed bolta hai, abhi styling baaki hai.

### Step 6: Professional styling — traditional HTML styles wapas laao

Yeh thoda "janky" hai. **Tailwind ek problem create karta hai:** wo apni saari modern utility classes add karta hai, par saath hi standard HTML element styles (jaise `h2`, `h3` ke default look) ko **hide/reset** kar deta hai — kyunki Tailwind world mein un default styles ki zaroorat nahi hoti. Lekin **hamare React Markdown component** ko un traditional styles ki zaroorat hai (markdown `# Heading` ko `<h2>` banata hai, jisko proper styling chahiye).

Solution: traditional HTML element styles ko **manually wapas add karo**. `styles/globals.css` (public mein NAHI — `styles` folder mein) ke **end mein** paste karo — jo already hai usse replace mat karo, sirf add karo:

```css
/* globals.css ke end mein — traditional element styles wapas laana */
h2 { font-size: 1.5rem; font-weight: bold; margin: 0.5rem 0; }
h3 { font-size: 1.25rem; font-weight: 600; margin: 0.4rem 0; }
ul { list-style: disc; padding-left: 1.5rem; }
/* ...baaki standard styles... */
```

### Step 7: Prompt ko markdown ke liye encourage karo

`index.py` mein prompt ko update karte hain taaki LLM markdown formatting use kare:

```python
prompt = (
    "Reply with a new business idea for AI agents, formatted with "
    "headings, subheadings, and bullet points to really make it irresistible."
)
```

> Ed ka punchline: **"LLMs love generating markdown — but with something like this, it'll be irresistible. It's going to desperately generate markdown."** Models naturally markdown ki taraf jhukte hain; explicit instruction dene se guaranteed ho jaata hai.

### Step 8: Final `index.tsx` polish

Aakhir mein `index.tsx` ko ek aur baar update karke aur sundar bana dete hain — fancy gradients, "AI-powered innovation at your fingertips" heading, pulsing animations, etc. Ed openly admits: **"I am a terrible front-end coder... this was mostly generated by Claude Code with me tweaking here and there."** Front-end log isse improve kar sakte hain aur community contributions mein share kar sakte hain.

### Step 9: Production par deploy 🎉

Ab seedha production par:

```bash
vercel --prod
```

`vercel .` → preview, `vercel --prod` → straight to production. Deploy hone ke baad URL kholo. Ab dikhta hai:
- **Fancy UI** — "AI-powered innovation at your fingertips", "Generating business idea" pulse karta hua (Tailwind animation).
- **Nicely formatted markdown** — proper headings, organized bulleted sections, yahan tak ki ek "team blueprint" section bhi.
- Idea wahi hai — *"AI agents as a service for SMB operations"* — par ab professional dikhta hai.

**Reminder:** abhi app par Vercel ka authentication wrapper laga hai (Day 1 wala), toh sirf tum (Vercel mein logged in) ise access kar sakte ho. Internet par expose karna ho toh Vercel → app → Settings se kar sakte ho — par abhi zaroorat nahi, aage isse aur behtar banayenge.

### Aage kya (Day 2 wrap-up)

- **Day 3:** authentication, sign-in + subscription — log paise de paayenge!
- **Day 4:** app ko beefier banaake ek **healthcare SaaS** mein convert karenge.
- **Day 5:** script completely badlegi — Vercel ke bajaye **AWS** par deploy karenge, dono ko compare karenge.

Ed celebrate karta hai: **tum course ka 10% complete kar chuke ho** — aur yeh foundation hi sabse important hissa hai.

---

## 📋 Key Concepts

| Concept | Matlab |
|---|---|
| **Streaming (SSE)** | Server token-by-token data push karta hai ek long-lived HTTP connection par — LLM output incrementally dikhta hai |
| **`stream=True`** | OpenAI API ko bolta hai pura response ek saath nahi, chunks mein bhejo |
| **`StreamingResponse`** | FastAPI type jo continuous data stream client ko bhejta hai |
| **React Markdown** | Off-the-shelf React component jo markdown text ko formatted HTML mein render karta hai |
| **Tailwind CSS** | Utility-first CSS framework — small classes (`text-lg`, `font-bold`) directly JSX mein |
| **Preview environment** | `vercel .` ka target — safe testing, production URL untouched rehta hai |
| **Production environment** | `vercel --prod` ka target — live, public-facing version |
| **`globals.css`** | Global stylesheet; yahan traditional HTML element styles wapas add kiye (Tailwind unhe reset karta hai) |
| **npm install** | Front-end ka "pip install" — package.json dependencies download karta hai |

---

## 💼 Backend Dev Ke Liye Note

Python backend dev ke liye sabse meaningful hissa **`StreamingResponse` + `stream=True`** ka combination hai. Yeh exactly wahi generator-based streaming pattern hai jo tum FastAPI mein normally use karoge: ek Python generator (`yield` karta hua) ko `StreamingResponse` mein wrap karte ho, aur FastAPI use SSE (`text/event-stream`) ke through client tak push karta hai — backpressure aur chunked transfer-encoding khud handle karta hai. OpenAI ka `stream=True` ek lazy iterator return karta hai jisko tum directly `for chunk in completion` se consume karte ho — ek bada response buffer karne ki zaroorat nahi, memory-efficient. Production mein dhyan rakho: streaming responses ke saath **timeouts, proxy buffering (nginx `proxy_buffering off`), aur client disconnect handling** important hote hain. Preview-vs-production environment split bhi familiar lagega — yeh staging/prod separation ka lightweight version hai, bas yahan deploy ek command hai.

---

## ✅ Takeaway

- **Streaming = `stream=True` (OpenAI) + `StreamingResponse` (FastAPI) over SSE** — token-by-token output, better UX for slow models
- **React Markdown + Tailwind** se LLM output professional dikhta hai — par Tailwind default HTML styles reset karta hai, isliye `globals.css` mein traditional styles wapas add karne padte hain
- **`vercel .` = preview, `vercel --prod` = production** — pehli deploy production mein jaati hai, baaki preview mein; safe iteration ka pattern
- **Prompt mein explicitly "use markdown with headings and bullets" bolo** — LLM "desperately" formatted output deta hai
- Front-end perfect hona zaroori nahi — Claude Code / LLM se generate karke tweak karna bilkul valid hai; tum course ke **10%** par ho aur yeh foundation aage sab kaam aayega

---

<details>
<summary>📜 Full Transcript (English)</summary>

But wait, there's more. As they say, we've got a bit more to do to finish off today. Uh, the the instructions suggest that you do a vassal minus minus prod. It's actually not required. We've already deployed to production. But. But you can do it if you wish. We'll do it again in a minute. I just want to add in real time streaming, which I said we would do, and that that was actually not not yet streaming. Um, and I also want to show the results in markdown looking more elegant than they just looked. So first of all, we've got a few packages to install. And I mentioned that one of the great things about react is how there are such a huge ecosystem of different libraries. Here's a bunch that allow us to show markdown, uh, in, in a front end widget. So I'm just going to within in the sass folder, I'm going to run that npm install function, and it's going to go ahead and install a bunch of node packages. They've all happened. And now we're going to update index dot TSX. Let me close that. Get out of the way there. We're going to update index dot TSX to make that a bit juicier. Here it is. Copy that. Go to index dot TSX, select all and paste. And the main thing that's different here is that it's handling the streaming back of information from the server. Nicely you can look through this code if you want to see how this works. And it's also got something that uh, uses a plugin, a component called React Markdown, which gives us a nice formatted, um, component that can take markdown instead of just text. Um, and it's a classic example of the kind of react component you can take off the shelf. Okay, so that's Index.ts. Let's go back to the instructions. And next, it's also got a little description here of the different tailwind classes that we're using and how you can interpret them. Uh, we do also need to actually install a plugin so that this is going to work properly. So we'll go back to the terminal, run that npm install npm install for backend people like me is like pip install for front end people. Uh, and, uh. All right, back we go. Here. Okay. And now we just have to, of course, update the backend index.py so that it streams back results to the client. So let me copy that. I'm going to index.py over here. Select all of this, paste in the new version and take a look at it. You can see that it's client completions passing in stream equals true. And with what comes back, we stream it back to the front end by returning a streaming response, which is a fast API type. We will automatically be using this, this, this, uh, type this this thing called SE, which is a way that servers can stream back results to the client. Okay, now, uh, we can just, uh, deploy it and see how that works. So let's bring up this do vessel. Dot. Spell. Vessel. Right. Vessel dot. As I say this time, because it's the second time that we're doing it, it's not going to deploy it to production. It's going to deploy it to a different environment. That's called preview. So then production, the link from earlier will continue to be the original version. And preview is going to show this newer version. And we'll stick at preview until we've done the new version. And then we'll push that to production. And that gives you the sense of how you can have multiple environments with vessel and be able to move between them. The first time you ever deploy for a project, it goes to production and then subsequent times are going to preview first. So let it do its thing and I will see you when this completes. All right. That's done. And now as before I command click on preview I press open up. It comes and it says loading. GPT five does take a long period of thinking. First, if we were using something like, uh, for one nano or for zero, then. But here we go. Look at that. Streaming comes very nicely. Streaming faster than I can scroll, but it is indeed streaming back. And you might be interested to see there's no markdown there, but don't worry. Hold that thought. Hold that thought. We will come back to it. Okay, back we come. Close the terminal. Let's go on to the professional styling section. So the first thing we need to do is a bit janky. We need to take a bunch of styles that are standard HTML styles and put them at the end of our styles. And the reason we need to do this is subtle. Uh, tailwind adds all of these new styles, but it also hides the original standard styles like H2 and H3 because they're not needed anymore in a tailwind world. But we are using these because of our markdown component. So for it to look proper, we actually have to include all of these traditional styles so we can go to sorry, not public into styles and into globals. And at the end here we can just paste all of these traditional styles, just put it in at the end. Don't don't replace what's there. We need what's already there. But add that in there okay. And after doing that, uh, we also want to update the prompt in Index.py to encourage the LM to use markdown nicely. So if I go up to index.py I'm going to overwrite this here, this prompt to something which says reply with a new business idea for AI agents formatted with headings, subheadings, and bullet points to really make it irresistible. Llms love generating markdown, but with something like this, it will be irresistible. It's gonna it's gonna desperately generate markdown. Okay. And then finally we're just going to update index dot TSX to look a little bit nicer. This is index dot TSX. So we will take all of this and go to index dot TSX. Select all paste save done. Uh and you can look through this look at some front end code in your own time. Uh, I don't mind telling you I am a terrible front end coder. I have very little sense of style when it comes to front end. Uh, my my wizardry with Lmms does not translate to react, but, uh, llms are great at it. And so, in fact, this was mostly generated by Claude code with me doing a bit of tweaking here and there. Uh, no surprise. Um, but I'm sure front end people on this will be able to do much better. And I look forward to seeing your designs. Uh, please do share them. Okay, back to the back to the instructions. Uh, and we're ready to deploy. Uh, and this time, we'll just deploy all the way to production. So this is this is the command Vercel dot deploys to the preview environment. Vercel minus minus prod goes straight to production. And just so that we've tried that too. We will do that. Um, sorry. Copy that properly. Bring up the terminal. Paste that in there. Off it goes and I will see you in a second with the results. Okay. And it's deployed to production as before. I will click here to open this up and to see what we have. And you can see first of all it looks fancy. It looks fancy. Check this out. AI powered innovation at your fingertips. Generating business idea like pulses on and off. You can see the tailwind styling that achieves that. While it's thinking. We're hoping for nice markdown formatted business idea. Here it comes. What we can see is some nice heading stuff. Sometimes the headings are bigger and nice organized, bulleted, uh, sections with lots of information here. Uh, and even a team blueprint I just saw. Let's just see what the, the basic idea is. It's the same idea AI agents as a service for SMB operations. I guess operations is the new angle here. So there you have it. This is the business idea generator, uh, deployed to production. You may remember from day one that right now it's got the, uh, vessel authentication security around it so that only you will be able to use this logged into vessel. But you probably remember, you can go into vessel, go to this app, go to the settings page to to expose it to the internet. Should you wish this particular app of yours to be exposed out there to everybody. But you don't need to, because we're going to make this a lot better in the next few days. But congratulations on having your first polished front end, back end, full stack application deployed to the internet using an LM, presenting streaming back information, and presenting it in a nicely styled professional way. Well, congratulations! A lot of what we covered today will form the foundation of what is to come. We've deployed a full stack app. We've got it in two different environments, a preview and a production environment deployed using Vercel that makes it so easy to have these kinds of fast API backend, Next.js front end and deploy them really quickly. So what's ahead? So tomorrow we're going to add authentication, sign in and subscription. People will be able to pay for our business idea generator. And then on day four we're going to make it a beefier app by making it into like a healthcare SaaS app. And on day five, we will change the script completely. And instead of deploying to Vercel, we'll deploy it to AWS, which will change everything, and we'll be able to compare and contrast those two. So much to come. But before we get to all that, let's take a moment to celebrate that you are already somehow 10% of the way through this course. Or maybe you're feeling exhausted. Maybe you think, goodness, it's 90% still to go. But no, this is such an important 10%. Uh, and it's going to get juicier and juicier. Congratulations on being 10% towards being an expert in production deployment, and I will see you tomorrow.

</details>
