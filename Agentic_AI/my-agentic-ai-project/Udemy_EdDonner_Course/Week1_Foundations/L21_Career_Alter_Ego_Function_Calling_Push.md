# L21 — Day 5: Building Your Career Alter Ego — LLM Function Calling with Push Alerts

> **Week 1 — Foundations** · ⏱️ ~8 min · 🎥 Lecture 21 of 131
> **Instructor:** Ed Donner · **Lecture ID:** 49771207

---

## 🎯 Ek Line Mein (TL;DR)

Week 1 ka **big project shuru** — aapka **personal career alter ego** (website pe aapke professional history ke questions answer karne wala agent), jisme **tool use / function calling** pehli baar live aata hai: do Python functions (**record_user_details**, **record_unknown_question**) ko **JSON schema** mein describe karke LLM ko diya jaata hai, aur ye tools **Pushover** se aapke phone pe **push notifications** bhejte hain.

---

## 📝 Hinglish Explanation (Detailed)

- **Day 5 = Week 1 ka last day** — ab time hai **big project** unveil karne ka: aapka **personal career alter ego** for your website, jo aapke **professional history** ke baare mein questions answer karega.
- **Ek baar phir reminder:** is poore week mein **koi framework nahi** — hum **directly models se interact** kar rahe hain. Ye **foundational knowledge** deta hai ki under the hood kya chal raha hai, taaki jab clever frameworks (jo sab abstract kar dete hain) use karein, tab aapko pata ho behind the scenes kya ho raha hai.
- **Lab 4 — "Professionally You":** pehla big project, aur isme **tool use** finally appear hota hai (pichle lecture mein theory cover hui thi, ab code).
- **Pushover — phone pe push notifications ka simple tool:**
  - **Twilio** (SMS) ab regulation ki wajah se kaafi mushkil ho gaya hai — khud ko ek text bhejna bhi painful. **Pushover super simple aur free** hai (pehla month free, uske baad tiny amount).
  - Setup: account banao → **2 keys milti hain: user + token** → dono **.env file** mein daalo → phone pe **Pushover app** install karo.
  - Code side: `load_dotenv()` se pushover **user** aur **token** load hote hain, plus push notifications bhejne ke endpoint ka **URL**.
  - **`push()` function** = bas ek **`requests.post`** us URL pe, data mein **user token, app token, aur message**. Bas itna hi — "this is how all things should be, just super simple."
  - Ed demo karte hain — `push("Hey")` chalate hi phone pe notification aati hai. SMS regulations ki tension ke bina code se khud ko notify karna — **aage ke projects mein bhi use hoga**, isliye install kar lo.
- **Do "innocent looking" functions — jo tools banenge:**
  - **`record_user_details`** — record karta hai ki koi user **in touch hona chahta hai** (email + name + notes ke saath). "Record" ka matlab: **phone pe push notification** bhejta hai ("recording interest from...") aur return karta hai ki record ho gaya.
  - **`record_unknown_question`** — record karta hai jab user koi aisa **question pooche jo LLM answer nahi kar paya** ("recording question asked that I couldn't answer..." push hota hai).
  - Idea: in dono functions ko **LLM ke tools** banana hai, taaki agent khud decide kare kab inhe call karna hai — aur aapko **turant pata chale** (phone pe) jab koi lead aaye ya koi question miss ho.
- **"Tool use is just JSON and if statements"** — aur ab ye live dikhega:
  - Har function ke liye ek **JSON blob** banta hai jo us function ki **capability describe** karta hai:
    - **name**: `record_user_details`
    - **description**: *kab use karna hai* — "Use this tool to record that a user is interested in being in touch and provided an email address." **Yahi description LLM use karta hai decide karne ke liye** ki tool appropriate hai ya nahi.
    - **parameters**: `email`, `name`, `notes` — har ek ki apni **description**, `email` **required**, aur **no additional properties**.
  - Ye JSON **OpenAI ko bheja jaata hai** — hum keh rahe hain: *"tumhare paas ye ability hai; agar chalana hai to mujhe batao, main run karke answer dunga."* Yani LLM apne **response mein decide** karta hai ki tool call karna hai ya nahi — **execute hum karte hain**.
  - **`record_unknown_question`** ka JSON bhi same pattern: name, description, aur ek hi property — **`question`** (string, "the question that couldn't be answered").
  - Note: ye JSON kaafi **verbose / boilerplate** hai — **agent frameworks yahi sab automatically generate** karte hain, isliye aage aapko ye haath se nahi likhna padega. Par ek baar khud likhna = samajh pakki.
- **Practical tip:** notebook mein **saare cells run karo** — function define karna bhool gaye to baad mein **NameError** aayega. Classic Jupyter gotcha.
- **Final step — tools list:** dono JSON blobs ek **list** mein jaate hain, har entry: `{"type": "function", "function": <json>}`. `print(tools)` karne pe ek bada boilerplate JSON blob dikhta hai — names, descriptions, parameters sab.
- **Kyun JSON?** Kyunki **LLMs JSON samajhne mein bohot acche hain** — unke **training data** mein JSON bharpoor hai. Isliye tools describe karne ki "language" JSON hai.

---

## 🔑 Key Concepts / Important Terms

| Term | Simple Hinglish Meaning |
|------|--------------------------|
| **Career Alter Ego** | Aapka AI version jo website pe aapke professional background ke sawaal answer kare — Week 1 ka big project. |
| **Pushover** | Simple + (initially) free service jo code se aapke phone pe **push notifications** bhejta hai (Twilio/SMS ka aasan replacement). |
| **`push()` function** | Bas ek `requests.post` Pushover endpoint pe — data mein user key, token, message. |
| **`record_user_details`** | Tool/function: user ka email+name+notes record kare aur phone pe push bheje (lead capture). |
| **`record_unknown_question`** | Tool/function: jo question LLM answer nahi kar paya, use push notification ke through record kare. |
| **Tool JSON schema** | Function ka packaged description (name, description, parameters, required) jo LLM ko bheja jaata hai taaki wo decide kare tool call karna hai ya nahi. |
| **Description field** | Schema ka sabse important hissa — LLM **isi text se decide** karta hai ki tool kab use karna hai. |
| **`tools` list** | `[{"type": "function", "function": {...}}, ...]` — final blob jo API call mein jaata hai. |
| **"JSON + if statements"** | Ed ka mantra: tool use mein koi magic nahi — JSON se describe karo, response mein tool call aaye to if/dispatch se run karo. |

---

## 💡 Backend Dev Ke Liye Note (aapke liye)

- Tool ka JSON schema dekhte hi aapko **OpenAPI/Swagger spec** yaad aayega — same idea hai: `parameters`, `required`, `additionalProperties: false`. Farak itna ki consumer ek **LLM** hai, aur **description field hi prompt hai** — wahi routing decide karti hai, isliye use API doc ki tarah nahi, **decision rule** ki tarah likho.
- `push()` = plain **webhook-style POST**. Pushover ko aap apne stack ke kisi bhi alerting integration (PagerDuty/Slack webhook) ka personal, zero-infra version samjho — agent ke side effects ko observe karne ka cheapest channel.
- Ye boilerplate JSON haath se likhna ek hi baar karna hai — production mein aap **Pydantic models se schema auto-generate** karoge (frameworks andar yahi karte hain). Par manual version samajhna = framework debugging mein superpower.
- **Hands-on lab:** is lecture ka code khud chalane ke liye ye lab run karo — `Practical/lab4_career_agent.py` (uv run se chalta hai, Groq-free).

---

## 🧠 Takeaway (yaad rakho)

1. **Big project = career alter ego** — website pe aapka professional Q&A agent, with real tool use, **bina kisi framework ke**.
2. **Pushover** se ek simple `requests.post` mein phone pe push notification — leads aur missed questions ka instant alert.
3. **Do tools:** `record_user_details` (lead capture) aur `record_unknown_question` (gap detection) — dono push notification bhejte hain.
4. **Tool = function + JSON schema:** name, description, parameters, required. LLM sirf **decide** karta hai tool call karna hai ya nahi — **run aap karte ho**.
5. Schema ka **description field** hi LLM ka decision criteria hai; aur ye saara boilerplate aage **frameworks auto-generate** karenge.

---

<details>
<summary>📜 Full English Transcript (original, click to expand)</summary>

Well, they say time flies when you're having fun. And that seems to be happening because we already have reached the last, last of the days of the first week, day five, and it's time to unveil our big project, which, as you know, is your own personal career alter ego for your website, answering questions about your professional history. And I want to say one more time that last time we talked about the different agentic frameworks and how there are simple ones and complex ones. Everything we're doing this week is with no framework at all. We are interacting directly with models, which is incredibly important because it gives you that foundational knowledge about what's actually going on under the hood, so that when we start to build on all sorts of clever frameworks that abstract us away, you have good insight into what's really going on behind the scenes. But that's the end of the intro. It's now time to go straight to the lab, because for today, it's going to be a ton of coding. Let's get to it.

And here we are back in Cursor. And we go back into the first week, foundations. And now we're on lab 4 for the first big project. "Professionally You", I'm calling it. It's going to be your personal career alter ego, and it's going to include tool use, as promised. I know we covered it in the last lecture, but it's going to now make its appearance.

First, I want to introduce you to a nifty little tool called Pushover, which people from my last course will remember fondly. It is a nice little tool, and I have to have my phone off silent because we're going to be using it. So I do apologize if I get things like text messages and stuff, but it's important, as you will see. Pushover is a cute tool that lets you send push notifications to your phone. If you're used to using something like Twilio that lets you send text messages — Twilio used to be very easy to use, but now there's so much regulation around SMS that it's actually quite hard to get things together to send even yourself a text message. Pushover is super simple, and it's free. At least I think for the first month — I'm now paying some tiny amount, but it's free for the first month, so you've got plenty of time. You simply go to Pushover and it's super clear. You set up an account on the top right, you get an API key — and you actually get two: you get like a user and a token, and you have to put that in your file so that it's going to be available here. And you also install an app on your phone called Pushover, which I have sitting right there.

And the reason you do that — if I do run a few imports right here and now, I'm going to do the usual load_dotenv, which is going to include my Pushover user and token now, and I'm going to create the OpenAI library. All right. So my Pushover user is in that field, my token is in that, and this is the URL of the endpoint for sending push notification messages. And so this function here, push, is all it takes. Basically, you just do a requests.post to that URL, to that endpoint, and you pass in some data. And that data has the user token, the token token, and the message itself that you want to push to your phone. And that's the end of it — nothing more. I mean, this is how all things should be: just super simple. So I should be able to run this function here. "Hey." And it should come up on my phone right now. There you go. I hope you heard that loud and clear. I'll do it again. There we go. And I see "Hey" twice. And that is a cool way to be able to notify yourself of things through code without having to worry about SMS regulations and things like that. Okay, that's Pushover. Please install it when you have a moment, because we're going to use it not just this time, but we're going to use it in other projects as well. It's a useful thing to be able to do.

Okay. Now I'm going to introduce you to two innocent-looking functions. One of them is called record_user_details and the other is called record_unknown_question. And these are two tools that I'm going to want to equip our LLM with so that it can do these things. It's going to be able to record if a user wants to be in touch with us, and it's going to be able to record if a user asks a question that it doesn't know how to answer. And by record, what I mean is it's going to send a push notification to my phone so I know immediately if someone does that. And so it's going to say that it's recording that someone — a person with this email and these notes — and it's going to return that it recorded. So that's a useful thing to be able to do. And if it gets a question it doesn't know, it's going to push, recording that a question was asked. Why don't we make this a bit more descriptive: "that I couldn't answer". There we go. So now it's nice and clear: "recording interest from". There we go.

Okay, so the idea is we want to turn these into tools that our LLM can use. Now remember I told you that at the end of the day, tool use is just JSON and if statements, and that is what you're going to see right now. Here is some JSON. It's quite long JSON, it's quite verbose. And one of the things that the agent frameworks do is they sort of do all of this for you automatically. So you won't have to worry about this again, because a lot of this stuff is very boilerplate, a lot of standard JSON. But this JSON right here, record_user_details_json, is a blob of JSON that refers to this function. It describes the capability of being able to call that function. It gives it a name, record_user_details. It says why might you want to do that: "Use this tool to record that a user is interested in being in touch and provided an email address." And then we specify the parameters. There's one called email, one called name, one called notes — look, here it is: email, name and notes. And we give each one a description. And we say that email is required and that there aren't additional properties.

So you may be wondering what this is about. The thing to keep in mind is that this is the information that's going to be sent to OpenAI. We're going to say to it: you have the ability to do this; tell me if you want me to run it for you, and I'll tell you the answer. So that's what's going on here. It's like a packaged way of describing what this function does in JSON format, so that the LLM can decide in its response whether or not it wants to actually call this tool. And then very similar for record_unknown_question: we give it a name, the name of the function, we give it a description — and this is what the LLM will use to decide whether or not it's appropriate to use this tool. And then we say that it has one property, question, which is a string: the question that couldn't be answered. And that is the end of that. Let's run this and run this. Okay. If I run everything — I didn't run the functions themselves. It's always: if you fail to run things, then you're going to get a NameError later. It's something to watch out for. So always come back and make sure that you've run all of your cells.

Okay. Final step for this is that we're going to put both of these blobs of JSON into a list of tools. Type is "function" and the function is that function. So now this blob of JSON is a big blob of JSON. Let's have a look at it. Print tools. And you're going to see — actually, what happens if I just do it like this? That might look better. There we go. It does look better. This is what tools now is: it is this big chunk of JSON, boilerplate JSON, which describes the two functions that we're providing, with a name, a description, the parameters, and so on. And this — putting things in JSON — is a language that LLMs are good at understanding, because it's in lots of their training data. And so that's going to help us to be able to interact with OpenAI.

</details>

---
*Source: Official Udemy lecture transcript (auto-captions, lightly cleaned). Notes in Hinglish for self-study.*
