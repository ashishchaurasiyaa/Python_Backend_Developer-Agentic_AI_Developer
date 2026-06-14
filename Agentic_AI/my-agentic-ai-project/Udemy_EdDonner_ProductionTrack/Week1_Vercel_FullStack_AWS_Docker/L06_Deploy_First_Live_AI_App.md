# L06 — Deploy Your First Live AI App with OpenAI and Vercel Integration

> **Week 1 · Day 1** · ⏱️ ~12 min

---

## 🎯 TL;DR

Instant gratification ka **part 2** — pichli baar humne sirf string return karne wala FastAPI app Vercel par chadhaya tha; ab usme **OpenAI (GPT-5 nano) ki LLM call** add karke pehla *sachcha* AI product production mein deploy karte hain. Flow: OpenAI key banao → `vercel env add` se key chadhao → `requirements.txt` mein `openai` add → `instant.py` mein LLM call → `vercel .` redeploy.

---

## 🗣️ Hinglish Explanation

### Recap: hum kahan hain

Yeh `week1` → **"day one part 2.md"** instructions follow kar rahe hain — *instant gratification project part two*. Part 1 (L01) mein humne `instant.py` + `requirements.txt` + `vercel.json` se ek FastAPI app deploy kiya tha jo bas `"Live from production!"` return karta tha. Ab usme jaan daalte hain: ek real **LLM call** taaki website production par GPT-5 se ek welcome message generate kare.

### Step 1: OpenAI API key banao (ya skip karo)

Hum **OpenAI ki API** ko call karenge — specifically **GPT-5**. Yahan Ed do important baatein clear karta hai:

1. **Cost reality** — OpenAI API *super sasti* hai. Jo calls hum karenge wo *ek cent ke fraction* mein ho jaayengi. Par OpenAI ek **$5 ka upfront payment** maangta hai jiske against tum *pay-as-you-go* draw down karte ho. Yeh chhoti si entry barrier kuch logon ko bore lagti hai.
2. **Alternatives exist** — agar $5 nahi daalna, toh **free/cheap alternatives** hain (jo upfront payment nahi maangte). Ye sab `guides` folder ki guide mein documented hain. Wahan likha hoga kaise apni setup change karni hai. Bas concept samajh ke apply kar do.

Ed ki salah: OpenAI ke saath chipke raho agar ho sake — kyunki industry mein **OpenAI bahut common hai**, aur key setup + key handling + direct usage ka experience valuable hai. "$5 well spent" — aur wo $5 tum sach mein kharch nahi kar rahe, bas deposit hai jo lambe time mein dheere-dheere use hoga.

> **Background — ChatGPT product ≠ OpenAI API.** ChatGPT ek *subscription product* hai (monthly fee, web/app interface). OpenAI **API** ek *developer interface* hai jise tum code se call karte ho aur per-token/per-call charge hota hai. Dono alag billing hain. Yeh confusion bhi guide mein cover hai.

#### Key banane ka exact flow

1. **platform.openai.com** par jao (yeh developer platform hai, ChatGPT nahi) → sign up karo. Sabse fast: **Google se authenticate** karo. (Kabhi-kabhi ek extra button — "create an organization" — click karna padta hai.)
2. **Billing** page par jaake **$5 minimum** daalo. ⚠️ **Auto-recharge OFF rakho** — taaki agar galti se paisa khatam ho jaaye toh aur charge na ho. (Is course mein tum us $5 ke aas-paas bhi nahi pahunchoge.)
3. **API keys** page → **"Create new secret key"** → key copy karo. Key aam taur par `sk-proj-` se start hoti hai (company setups mein kabhi alag bhi).

#### Key save karne ka trap (zaroor padho)

- Key ko **password manager** mein save karna best hai.
- Agar text editor mein save kar rahe ho toh **plain text editor** use karo — **Microsoft Word ya fancy word processor MAT use karo**. Wo "smart" formatting karte hain: simple dash `-` ko *long dash* (em-dash) bana dete hain, quotes ko curly bana dete hain. Isse key corrupt ho jaati hai aur kaam nahi karti.
- Poore course mein hum **dozens of keys** banayenge — yeh skill pakki karni padegi. Ek typo = key kaam nahi karegi, aur **debugging** karni padegi.

### Step 2: Key ko Vercel mein add karo (`vercel env add`)

Key ko code mein **kabhi hardcode mat karo**. Yeh ek **secret** hai jo backend par environment variable ke roop mein rehni chahiye. Vercel CLI se:

```bash
vercel env add OPENAI_API_KEY
```

Yeh command Cursor ke terminal mein chalao (`instant` folder ke andar). Phir CLI interactively poochega:

1. **Value?** → apni key paste karo. ⚠️ Exactly paste karo — `sk-proj-` se start, **end mein koi space na ho**.
2. **Kaunse environments?** → **saare teen** select karo (Production, Preview, Development). Shortcuts:
   - **`a`** dabao → teeno circles bhar jaati hain → **Enter**, ya
   - **Space** se ek-ek toggle → arrow-down → space → … → **Enter**

Agar galti ho jaaye toh dobara same command chala ke theek kar lo, no problem. Bas: **teeno environments** ke liye key set honi chahiye.

> **Background — environment variables aur 3 environments.** Cloud platforms tumhare app ko alag-alag *stages* mein chalate hain: **Development** (local dev), **Preview** (har branch/PR ka temporary URL), **Production** (live site). Har stage ke apne secrets ho sakte hain. Hum sab mein same key daal rahe hain. Runtime par yeh key `os.environ["OPENAI_API_KEY"]` se code ko milti hai — OpenAI library by default isse khud uthata hai.

### Step 3: Dependency add karo — `requirements.txt`

Ab `requirements.txt` mein **openai** add karo:

```
fastapi
uvicorn
openai
```

**Ed ka famous rant (yaad rakho):** yeh `openai` Python library **koi LLM code nahi rakhti**. Yeh ek **open-source convenience utility** hai — bas ek nice Python wrapper jo:

- ek **HTTP request** banata hai OpenAI ke web endpoint ko,
- aur jo JSON wapas aata hai usse **clean Python objects** mein convert kar deta hai.

Bas itna. Code khula hua hai, tum padh sakte ho. Aur **bonus**: yeh wahi `openai` library aksar **doosre LLM providers** ko bhi call kar sakti hai (Gemini, Groq, OpenRouter, local Ollama, etc.) — bas `base_url` aur key badal do. Isiliye guide mein jo alternatives bataye gaye hain, wo bhi **isi `openai` package** ko use karte hain, sirf ek alag LLM provider par point karte hue.

### Step 4: Application code — `instant.py`

GitHub se naya code copy karke `instant.py` mein **select-all → paste** karo:

```python
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from openai import OpenAI

app = FastAPI()


@app.get("/", response_class=HTMLResponse)
def read_root():
    client = OpenAI()

    message = (
        "You're on a website that's just been deployed to production "
        "for the first time. Please reply with an enthusiastic "
        "announcement to welcome visitors to the site, explaining that "
        "it's live on production for the first time."
    )

    messages = [{"role": "user", "content": message}]

    response = client.chat.completions.create(
        model="gpt-5-nano",
        messages=messages,
    )

    reply = response.choices[0].message.content
    reply = reply.replace("\n", "<br/>")

    html = f"""
    <html>
      <head><title>Live in an instant</title></head>
      <body>{reply}</body>
    </html>
    """
    return html
```

Line-by-line samjho (yeh classic OpenAI chat-completions pattern hai):

1. **`client = OpenAI()`** → lightweight utility ka instance banata hai jo OpenAI ko internet par call karega. Constructor mein key nahi di — library **`OPENAI_API_KEY`** env var (jo humne Vercel par set kiya) khud uthata hai.
2. **`message`** → hamara **prompt**. Yahan hum GPT-5 ko bol rahe hain: "tum ek aise website par ho jo abhi pehli baar production mein deploy hui hai — ek enthusiastic announcement likho." *(Isse freely change kar sakte ho — snarky, formal, serious, jo chaho.)*
3. **`messages`** → list-of-dicts format jo har LLM engineer jaanta hai: `{"role": "user", "content": ...}`. (Foundations chahiye toh Ed ka LLM Engineering course dekho.)
4. **`client.chat.completions.create(...)`** → actual API call. **`model="gpt-5-nano"`** = GPT-5 ka sabse lightweight/sasta variant. `messages` pass kar di.
5. **`response.choices[0].message.content`** → response mein ek `choices` list aati hai; humein sirf **first choice** chahiye, uske andar `message.content` mein assistant ka text hota hai.
6. **`reply.replace("\n", "<br/>")`** → kyunki hum yeh text HTML page mein dikha rahe hain, **newlines (`\n`) ko `<br/>` tag** se replace karte hain taaki blank lines properly render hon.
7. **`html`** → ek normal HTML page string — `<title>Live in an instant</title>` aur `<body>` mein reply. Yahi return hota hai (`HTMLResponse` ke roop mein, taaki browser raw HTML samajhe).

⚠️ **SAVE KARO!** (`Cmd+S` / `Ctrl+S`) — warna kuch nahi chalega. Ed instinctively save kar leta hai, par tum alert raho.

### Step 5: DEPLOY — `vercel .`

```bash
vercel .
```

Vercel build chalata hai (Python serverless function + dependencies install). Build complete hone par **preview URL** milta hai.

### Result: pehla live AI product 🎉

URL par `Cmd+Click` (Mac) / `Ctrl+Click` (Win) → browser khulta hai → thoda time lagta hai (LLM call live ho rahi hai) → phir GPT-5 ka enthusiastic announcement screen par: *"Welcome to our brand new site… now live in production for the very first time! 🎉 … real users, real data, our real working product."*

Thoda exaggerate hai (abhi koi real data/product nahi), par tumne ek **LLM ko production mein call hote hue, internet par deploy hote hue** dekh liya — exactly jaisa promise kiya tha.

### ⚠️ Preview vs Production + $5 protect karna

Do important caveats Ed deta hai:

1. **Yeh "production" nahi hai — yeh "Preview" hai.** Vercel iss deploy ko technically *Preview* maanta hai. Asli production version banane ka ek alag tareeka hai (`vercel --prod`) — par wo poora hafta aage cover hoga. Filhaal: yeh internet par hai, koi bhi access kar sakta hai, LLM call karta hai. Kaafi hai.
2. **$5 ko safeguard karo.** Yeh URL **public** hai — jab tak tum Vercel settings mein **authentication ON** nahi karte, internet par koi bhi tumhare deployment ko hit karke tumhari OpenAI key se calls kar sakta hai (yaani tumhara paisa kharch). Vercel settings mein jaake deployment ko **sirf apne tak** restrict kar do (Vercel authentication ke peeche).

---

## 📋 Key Concepts

| Concept | Matlab |
|---|---|
| **OpenAI API key** | `sk-proj-...` secret jisse tum OpenAI ko apni identity prove karke calls karte ho |
| **platform.openai.com** | Developer platform (ChatGPT product se alag) — key, billing, usage yahan |
| **$5 upfront + auto-recharge OFF** | Pay-as-you-go deposit; auto-recharge band rakho taaki overspend na ho |
| **`vercel env add OPENAI_API_KEY`** | Secret ko Vercel ke 3 environments (Prod/Preview/Dev) mein add karna |
| **`openai` library** | Open-source HTTP wrapper — *koi LLM code nahi*; doosre providers ko bhi call kar sakta hai |
| **`client.chat.completions.create`** | Chat completion API call — model + messages do, response milta hai |
| **`gpt-5-nano`** | GPT-5 ka lightest/sasta variant |
| **`response.choices[0].message.content`** | Assistant ka text response nikalne ka standard path |
| **messages list-of-dicts** | `[{"role": "user", "content": ...}]` — LLM conversation ka standard format |
| **Preview vs Production (Vercel)** | `vercel .` = Preview deploy; asli prod alag command/flow se hota hai |

---

## 💼 Backend Dev Ke Liye Note

Python backend dev ke liye yeh lecture do solid production habits sikhata hai. **Pehla — secrets management**: key ko code/`requirements`/git mein kabhi nahi, balki ek **environment variable** ke roop mein platform ke secret store mein (`vercel env add`). Yeh wahi pattern hai jo tum AWS Secrets Manager / SSM Parameter Store / Kubernetes Secrets mein dekhoge — abhi chhota version. **Dusra — dependency hygiene**: `openai` ko `requirements.txt` mein pin karna (baad mein versions pin karna seekhoge) taaki deploy reproducible ho. Architecturally, yeh ek **server-side LLM proxy** hai: browser kabhi OpenAI ko directly call nahi karta (warna key leak ho jaaye); request backend (FastAPI) par aati hai, backend secret key ke saath LLM ko call karta hai, aur safe response return karta hai. Yeh "BFF / API-key-on-the-server" pattern har production LLM app ki neenv hai. Aur Ed ka cost-discipline point note karo — public endpoint + auth off = open wallet; production mein **rate limiting + auth** har LLM-backed endpoint par chahiye.

---

## ✅ Takeaway

- Pehla *sachcha* AI product live: FastAPI endpoint ab **GPT-5 nano** ko call karke welcome message generate karta hai
- **Secret kabhi hardcode nahi** — `vercel env add OPENAI_API_KEY` se 3 environments mein daalo; library env var khud uthata hai
- `openai` library = sirf ek **HTTP wrapper** (LLM code nahi); chahe to doosre providers bhi isse call ho sakte hain
- Core pattern: `client.chat.completions.create(model=..., messages=[{"role":"user","content":...}])` → `response.choices[0].message.content`
- `vercel .` = **Preview** deploy (asli prod alag); aur **auth on karke $5 protect karo** — public endpoint sabki pahunch mein hota hai

---

<details>
<summary>📜 Full Transcript (English)</summary>

So here I am back in GitHub on the website github.com slash. We're going to week one and week one is day one dot part 2.md, which is our instant gratification project part two. So look, the first step is to set up an OpenAI API key because we're going to be making calls to OpenAI to GPT five. And I realize that for some people, many of you probably already have OpenAI keys. And you can just skip step one. Some of you do not. And some of you may not want to have OpenAI keys because OpenAI, whilst it is super cheap to call the OpenAI API, it's a fraction of a cent for any call that we'll be making. And certainly in this part, the they do require a $5 up front payment that you pay as you go against. And and obviously that can be a bore if you do lots of these APIs. And so I do understand that's not for everyone. And so there are alternatives including free and cheap alternatives that don't require the $5 upfront, and I will make sure that they're all carefully noted in the docs. You should be able to find this well documented in the guide in the guides folder that will go through, uh, all of the different alternatives that you've got. Assuming that if you do that, it will tell you how you can change what we do here. Just make sure you understand it and then apply that. But otherwise, if you're sticking with the OpenAI approach and it's good to get some experience with OpenAI because it's so common in industry and knowing how to set up a key and work with the keys and use them directly makes a lot of sense. I think it's $5 well spent. Uh, and of course, you're not really spending it. You're just putting it down and you will spend it over a long period of time. Uh, but if you're ready to do that, then the way to do it is you first visit platforms, OpenAI, which is where you go to sign up for an account. If you're confused about the difference between ChatGPT the product which has a subscription, and using the API, then that's also covered in the docs. Um, but if you do this, if I bring up a new incognito tab and go there. Then when you go here, you can sign up. You'll then sometimes you have to click on one more button. That's something like something to create an organization or something. But it should be pretty clear how you sign up. And you can authenticate with Google as the fastest way to do it or with anything. Um, and then once you've you've come through that, there's a link here to the page where you can add your $5 minimum payment, make sure auto recharge is not set so that if for some reason you spend that money, you won't spend any more. But you should not get close to spending that money on this course. Um, and then you need to create a new API key going to this link and you select Create secret new secret key. Your key will start src proj dash. Sometimes it doesn't. In some situations if you're part of a company. But almost always it starts with that. Copy that to your clipboard. Uh, it's also of course, important to save that somewhere safe. If you have a password manager, it's a great place to have it. If you do choose to save it in in a in a text editor, be sure to use not a fancy one like Microsoft Word or Notepad. That might change some of the characters, like it might change dash to a long dash and things like that. So avoid using a fancy word processor. Use a text editor only, uh, if you want to save your key. That's a common trap. Um, there's lots of traps in creating keys. I'll try and put some of them down in the docs, but we're going to be creating so many keys over the next few weeks that this is something that you're going to have to get good at. And if something goes wrong and you somehow get a typo in your key, it's not going to work. You'll have to get good at diagnosing and debugging that. But at this point, I'm going to assume that you have created an OpenAI account and you have your own OpenAI API key, which is how you'll identify yourself to OpenAI so that you can make calls. And it's time for us to add that key to Vercel. And so in the instructions you'll see here that the command is vercel env add OpenAI API key which we're going to run in cursor. So I'm going to copy that. I'm then going to bring up cursor. Here we are right where we left it in the instant project. Hang on I'm just going to make this a bit smaller. So it's got a bit more room for that. And I'm going to paste in that command. And when I do that it's now going to ask me for the value of that where I will now paste in my key. But of course I'm not going to do that on camera or you're all going to see my key. So I'm going to do that right now, and I will see you in a second. And you probably just experienced that. You have to choose once you've pasted in your key carefully making sure you you've pasted exactly your key, starting ESC, proj dash and no spaces on the end. The key. Once you've done that, you then have to select which environment it applies to. And we want to select all the environments. And you do that either by pressing the button A as it prompts you. And then all three little circles fill in. And then you press enter. Or you can press space to select each one. And then a cursor key down space down space and then enter, uh, either of those ways. Once you've once you've played around with it, with it, it'll be clear what's going on. Make sure that you've set that key for all three environments, and if you made a mistake, you can just come back and do it again. No problem. All right. So we've done that. We have just set environment variables with vassal. And it was pretty easy. And now let's go back to the instructions to see what's next. Next up we are going to update our dependencies. So you remember we created requirements.txt identifying which Python packages we which libraries we depended on. We have fast API and Uvicorn. We're now going to add in open AI. All right. That's that's getting interesting. We're adding our uh, AI uh, Python client library to requirements.txt. And probably many of you have heard my my rant on this before, but it's just important. I will say it one quick time. This open AI Python library that we're adding in here does not contain any LLM code. The code this is an open source package which OpenAI has made available to us all, and it is simply convenient. Python code A utility that wraps making web calls to a web endpoint. And that's all it is. And it's open source. You can look at the code, it just constructs an HTTP request. And what comes back, it turns them into nice Python objects, a convenient utility. And as many of you know, you can use that utility to talk not only to an OpenAI model, but to many other providers as well. In fact, almost all of them also support using this same utility to call their LLM. Um, and so in my guide where I explain how you can use others, it still ends up using the same OpenAI package that we have right here, just pointing it at a different LLM provider. Okay. Now let's go and add in our code. Okay. Let's go back to the instructions then. Uh, so from from GitHub. Now it's time to update our application code. I'm copying this code. We're now going to go back to cursor and select instant dot pi and then select all here and paste in the new code. All right let's talk about what this code is doing. So again we're using fast API. We've got only one function which is what will get called if someone requests this route. Uh path this this this route. Uh and what is it going to do? It starts by creating a new instance of OpenAI. This is the lightweight Python utility that will wrap a call to OpenAI over the internet. We have a message. The message is our is our prompt that we're going to use. And that prompt is you're on a website that's just been deployed to production for the first time. Please reply with an enthusiastic announcement to welcome visitors to the site, explaining that it's live on production for the first time. So that is the message that we're giving now. You can change this. Feel free to change this to whatever message makes best sense to you for your first true AI deployment, something that's going to generate a message for you. I realize this is hardly a valuable product at this point, but nonetheless, it is, as I promised, a gen AI product on the internet. So we take that message. We put it into the list of dicts that you may be very familiar with, something where there's a role user and the content is the message. This is completely new to you. You might want to check out my LLM engineering course the first couple of weeks just to get the foundations. And then response is client completions create something that's probably very familiar to to to to many of you, the model that we will pick will be the lightest weight version of GPT five, GPT five, nano, and we'll pass in our messages. And for what comes back we will take response dot choices zero. Their only is going to be the one choice. That's that's what you do. And then you call dot message content. And we'll just make one little, little correction to that. If there's any enter a carriage return in there. We'll replace it with an HTML tag for an empty line, a BR slash, so that empty lines will show properly. And then we will make a new new string called HTML, which is going to have something that is probably familiar to most of you, but it has the normal structure of an HTML page with a title live in an instant, and the body will be this reply. That's what we will. We will return. Make sure I think I've already done it instinctively, but you must make sure you save this page. Always, always be alert to saving. Otherwise nothing's going to happen. So save this page and I don't need to look back on the instructions to know what's coming next. What comes next is we're going to type vessel dot and deploy this. Uh, let's see what happens. Okay. Here we go. So let me give us some more room here and let's type vessel dot. And off it goes. Well, it's doing its thing. It's building. Hopefully we are about to have our first AI project live on the internet, and it will have been worth all this fanfare. Okay, there we go. Let's go and have a look at our preview. It's right here. I'm going to command click and open. And here it comes. It's taking a bit of time. And look at this. Let me expand this for you. Ha. Welcome to our brand new site with a lovely emoji. Now live in production for the very first time, we're thrilled to announce that our production deployment is live! This live. This milestone means real users, real data, and our real working product. So GPT five has enthusiastically given this nice introduction. It is perhaps a little bit of a stretch, given that this website doesn't actually add real data or a real working product, but nonetheless, it's full of unbridled enthusiasm, just as we requested. And hopefully you've twisted this. Maybe you've asked for a snarky announcement. Maybe you've you've had something that's very formal, very serious. But whatever. You have seen an LM be called in production and be deployed up here. And you may have noticed, if you were looking, that this isn't actually what vassal considers production. This is what it calls a preview. And there is a way to actually make it be the production version of it. But never fear, we have an entire week ahead of us. We will be getting to all of that. As far as we're concerned, this is on the internet, accessible to anybody, and calls and LM and produces this kind of response. And if you want to make sure that you safeguard that $5 that you put on there, you might want to go back into the vessel settings and make sure that this is only available to, to yourself. That has to go through the vassal authentication. But while you have that authentication off, anyone on the internet will be able to use your first generative AI deployment.

</details>
