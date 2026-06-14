# L13 — Day 3: Comparing LLM APIs — Using OpenAI Client Library with Claude, Gemini & ++

> **Week 1 — Foundations** · ⏱️ ~13m · 🎥 Lecture 13 of 131
> **Instructor:** Ed Donner · **Lecture ID:** 49771147

---

## 🎯 Ek Line Mein (TL;DR)

**OpenAI ka Python client library** sirf ek **lightweight HTTP wrapper** hai — aur kyunki OpenAI ka endpoint format **de-facto industry standard** ban gaya hai, aap **same client + alag `base_url` + alag API key** se Gemini, DeepSeek, Groq aur local Ollama sab ko call kar sakte ho; sirf **Anthropic (Claude)** apni alag SDK/format use karta hai.

---

## 📝 Hinglish Explanation (Detailed)

- **Anthropic / Claude — ek alag API:**
  - Sabse pehle Ed **Claude 3.7 Sonnet (latest)** se same question puchte hain.
  - Anthropic ki API **slightly different** hai — `anthropic` Python library ka naya client instance banate hain, aur call hota hai `claude.messages.create(...)` (OpenAI ke `chat.completions.create` se alag).
  - Ek important difference: **Anthropic `max_tokens` mandatory** banata hai — generation kahan stop hoga uski upper limit deni hi padti hai. **OpenAI mein ye optional** hai.
  - Baaki sab same pattern: model name + messages do, response wapas lo, display karo. Claude ka answer **zyada concise** tha (shayad isliye faster bhi), clear aur well-articulated.

- **Gemini — surprise! OpenAI ke code se call hota hai:**
  - Google Gemini ko call karne ke liye Ed **OpenAI ki hi client library** use karte hain — pehli baar dekhne par confusing lagta hai.
  - **Key insight:** OpenAI library koi LLM ya neural network nahi hai — ye bas ek **lightweight wrapper** hai jo ek **well-known structure** (lists of dicts wale messages) ko **HTTP request** mein convert karke ek endpoint pe bhejta hai.
  - OpenAI ke endpoints itne popular ho gaye ki **almost sab providers ne same spec ke compatible endpoints** offer kar diye — **sirf Anthropic exception** hai (aaj ke examples mein).
  - OpenAI ne apni client library mein **`base_url` parameter** open kar diya — matlab aap bol sakte ho "OpenAI ko contact mat karo, Google ke endpoint pe jao."
  - Google ka compatible endpoint URL **`...openai...`** pe end hota hai — ye Google ka official OpenAI-compatible endpoint hai. **Google ki key + Google ka base_url + OpenAI ka client = kaam ho gaya.**
  - Model: **Gemini 2.0 Flash** — same `create` call, same response structure. Answer kaafi **lengthy** tha, with **mitigation strategies** aur end mein ek **ethical assessment framework** — kaafi solid.

- **DeepSeek — full-size 671B model, OpenAI library only:**
  - DeepSeek ko call karne ke kaafi tareeke hain, lekin yahan **full-sized DeepSeek model (671 billion parameters)** use ho raha hai jo DeepSeek khud host karke API deta hai.
  - DeepSeek ke paas **apni client library hai hi nahi** — wo officially bolte hain "**OpenAI ki library use karo**, bas humara base_url daal do."
  - Do common models: **`deepseek-chat`** aur **`deepseek-reasoner`** (famous **R1** model). Ed yahan **reasoning model use nahi** kar rahe — fair comparison ke liye sab **chat models on even footing** hain.
  - DeepSeek ne sabse **lengthy answer** diya — frameworks ke saath, Gemini jaisa robust.

- **Groq (Q wala, K wala nahi!) — speed demon:**
  - **Groq** = fast inference provider jo **specialist custom hardware** (LPUs) pe open-source models chalata hai.
  - Unki apni library bhi hai, lekin **OpenAI-compatible endpoint** bhi hai (URL mein bhi "openai" word hai) — same pattern: key + base_url.
  - Model: **Llama 3.3 — 70 billion parameters** — itna powerful ki Ed kehte hain ye **purane Llama 3.1 405B ke on-par ya better** hai.
  - Itna bada model, lekin **Groq pe answer 1-2 second mein** aa gaya — yahi Groq ka USP hai: **blazing fast inference**.

- **Ollama — local LLM, zero API cost:**
  - **Ollama** ek **local service** hai — aapke computer pe chalta hai aur **localhost pe ek web endpoint** deta hai jo **OpenAI-compatible** hai.
  - Andar **highly optimized C++ code** hai jo **open-source models locally** run karta hai.
  - Install simple hai: ollama.com se download → install → browser mein **`localhost:11434`** kholo → "**Ollama is running**" dikhna chahiye.
  - Agar nahi dikhe: Cursor restart karo, ya terminal mein **`ollama serve`** chalao.
  - ⚠️ **"Ignore me at your peril" warning:** **Llama 3.3 (70B)** — wahi model jo Groq pe chalaya — **local machine ke liye bahut bada hai** (~40-60GB+). Ollama ka default recommendation hone ki wajah se log galti se download karke apna **poora system resources kha** baithe hain. **Mat chalao locally!**
  - Instead use karo: **Llama 3.2 (3B)** ya **Llama 3.2:1b** — aur bhi options: **Qwen** (Alibaba), **Gemma** (Google ka small open-source), **Phi** (Microsoft), aur **DeepSeek distilled** versions (jo actually Qwen/Llama models hain jo DeepSeek ke synthetic data pe train hue).
  - **Rule of thumb:** locally **7-8B ya usse chhota** — best **1.5B–3B** range.
  - Notebook mein **`!ollama pull llama3.2`** — `!` prefix matlab ye Python nahi, terminal command hai.
  - Call karna: **same OpenAI client**, `base_url` = localhost URL, **API key kuch bhi chalega** (convention: `"ollama"` likh do) — bas **model name wahi ho jo pull kiya hai**.
  - Result: **Llama 3.2 (3B)** ne **mediocre job** kiya — point 0.3 ke baad "bore" ho gaya. Chhote model ki **limits** dikh gayi is tough question pe, lekin answer "perfectly pleasant" tha.

- **Aage kya:** ab sab answers collect ho gaye (competitors + answers lists mein) — next lecture mein in sab ko **judge** karenge.

---

## 🔑 Key Concepts / Important Terms

| Term | Simple Hinglish Meaning |
|------|--------------------------|
| **OpenAI client library** | Koi AI nahi — bas ek lightweight Python wrapper jo HTTP calls karta hai ek known endpoint format pe |
| **OpenAI-compatible endpoint** | Industry-standard API spec — Gemini, DeepSeek, Groq, Ollama sab isi format ke endpoints dete hain |
| **`base_url`** | OpenAI client ka parameter jisse aap usko kisi aur provider ke endpoint pe point kar sakte ho |
| **Anthropic API** | Claude ki apni alag SDK — `messages.create`, aur `max_tokens` mandatory hai |
| **`max_tokens`** | Generation ki upper limit — Anthropic mein required, OpenAI mein optional |
| **DeepSeek chat vs reasoner** | `deepseek-chat` = normal model; `deepseek-reasoner` = famous R1 reasoning model (671B full-size) |
| **Groq (Q wala)** | Custom hardware (LPU) pe super-fast inference provider — Grok (xAI) se alag cheez hai |
| **Ollama** | Local service (C++ optimized) jo open-source models aapke machine pe chalata hai, `localhost:11434` pe OpenAI-compatible endpoint ke saath |
| **Distilled models** | Chhote models (Qwen/Llama) jo bade model (DeepSeek) ke synthetic data pe train hue — "knowledge transfer" |
| **`ollama pull <model>`** | Model ko locally download karne ki command |

---

## 💡 Backend Dev Ke Liye Note (aapke liye)

- **Ye pure API design ka lesson hai:** OpenAI ka chat completions spec waise hi de-facto standard ban gaya jaise **S3 API** object storage ka bana (MinIO, R2, GCS sab S3-compatible endpoints dete hain). Client library = thin HTTP adapter; `base_url` swap = same interface, different implementation — classic **Strategy pattern** at the infra level.
- **Anthropic = wo ek vendor jo standard follow nahi karta** — jaise kisi ek third-party ka REST API thoda alag contract maangta hai (`max_tokens` required = ek extra mandatory field in the request schema). Production mein iske liye aap ek adapter layer likhte ho; aage course mein frameworks (LangChain, etc.) yahi abstraction dete hain.
- **Ollama ko aise socho jaise local Postgres/Redis container:** ek daemon jo `localhost:11434` pe listen karta hai, API key sirf placeholder (auth nahi hai locally). Dev/testing ke liye free + private inference — lekin memory budgeting matters: 70B model load karna = OOM, waise hi jaise prod-size dataset laptop pe load karna.
- **Hands-on:** is lecture ka code khud chalane ke liye ye lab run karo — `Practical/lab2_multi_model_judge.py` (uv run se chalta hai, Groq-free).

---

## 🧠 Takeaway (yaad rakho)

1. **OpenAI client library sirf ek HTTP wrapper hai** — `base_url` badal kar Gemini, DeepSeek, Groq, Ollama sab call ho jaate hain. Ek interface, multiple providers.
2. **Anthropic akela exception hai** — apni SDK (`messages.create`) aur **`max_tokens` mandatory**.
3. **Groq (Q) = same Llama 3.3 70B model, lekin custom hardware pe seconds mein answer** — fast inference as a service.
4. **Ollama pe locally sirf chhote models chalao (1B–8B)** — Llama 3.3 70B locally chalane ki galti mat karna, system hang ho jayega.
5. **Model size matters:** 3B Llama 3.2 ne tough question pe mediocre answer diya — capability vs cost/size ka trade-off hamesha yaad rakho.

---

<details>
<summary>📜 Full English Transcript (original, click to expand)</summary>

So next up we're going to ask Anthropic and we're going to ask Claude 3.7 Sonnet latest. So one of the things you'll see here is that Claude's API, Anthropic's API, is slightly different. As before, we're going to create a new instance of the client Python library anthropic. And we're going to call it Claude. You'll see that the API is slightly different. It's claude... create. And again Cursor will fill that in for you. But otherwise we pass in the model name and the messages, and actually Anthropic needs you to specify the maximum number of tokens that's allowed to generate before it stops. OpenAI doesn't require that, but Claude — Anthropic — does. But other than that, this is exactly the same code. We have a model name. We get back the answer, we'll display it. And let's see how Anthropic does when we ask Claude 3.7 Sonnet latest, one of the best models that there are, the same question. So it's interesting that the headlines look kind of similar. It's more concise, which may be why it ran faster. And it seems like it's a pretty clear, well-articulated answer. No surprise.

Okay, so now we're going to use Gemini. We're going to call Google's Gemini to get its answer. And here is the API. And there's going to be a bit of a surprise in here if you're not aware of this. When we set up Gemini, you'll be surprised to see that we do it using OpenAI's code. And that might be super confusing. Like why? How come we're using OpenAI to call Gemini? Well, remember I mentioned to you that this code, OpenAI, there's nothing fancy here. This isn't like an LLM or anything about like a neural network going on. This is a lightweight library that just wraps HTTP calls to an endpoint of a particular structure, a well-known structure that includes passing in lists of dicts and that kind of thing in the form of an HTTP request. And OpenAI built these endpoints, and they became very, very popular. And a lot of people decided that they would offer endpoints with exactly the same format, the same kind of spec as OpenAI. In fact, pretty much everyone has done that. Everyone, that is, apart from Anthropic — at least in today's examples, Anthropic is the only place that hasn't gone with this. But for all of the others, they have done it in such a way that — and kindly, OpenAI opened up their Python client library so that when you create a new Python client instance, you can pass in a base URL. You can say, look, I don't actually want you to contact OpenAI on their endpoints. I would like to switch you to using Google's endpoints. And in particular, Google has an endpoint which you'll see, again somewhat confusingly, ends "openai". And that's because this is Google saying, hey, look, we've got endpoints you can use to call Gemini and they have a particular format. But by the way, we've made special ones that have exactly the same format as OpenAI, and they're served on this URL. So you can use OpenAI's client library. You can pass in our key, the Google key, and tell OpenAI to use our endpoint that's in their format, and that will work great. I hope you followed me there. If not, you're going to pick it up because we're going to do this all the time. What you're going to see is that once we've created Gemini, and we're going to use Gemini 2.0 Flash, we then call gemini... create. It's the same thing. Obviously we pass in the model name and the messages. We get back the response in exactly the same way, using now the structure that you're super familiar with. We'll display the answer. And enough chitter chatter. Let's see what Gemini makes of this — how Gemini 2.0 Flash is able to answer this question. And here we go. You can see, oh, it's quite a lengthy answer. There's a lot in there with mitigation strategies. I don't think I saw that others had that. And then a framework for ethical assessment at the end. So there's lots to like about this one certainly.

All right. Next up is DeepSeek. So there are a lot of different ways to call DeepSeek, which can be confusing. But in this case we're calling the largest, the full-sized version of the DeepSeek model. It has 671 billion parameters. It's a big model, and DeepSeek runs it and provides an API to connect with it. And to use that API, DeepSeek also says you can just use OpenAI's library — just tell it this is the base URL. And as it happens, I do believe DeepSeek only supports the OpenAI library. They don't have their own. They just say, just use OpenAI's. Everyone does. It's great. So that's what we do here. We call DeepSeek using OpenAI's library, and we provide in a key. There are two models that DeepSeek most commonly offers: deepseek-chat and deepseek-reasoner. DeepSeek reasoner is the famous R1 model, and the reason I'm not using it here is that I want everyone to be on an even footing, and we're not going to be using reasoning models for this question, just the chat models. So other than that, it's exactly the same. It's deepseek... create, pass in the model name and the messages, get back the answer, print it. And as before, we're adding it to competitors and to the answers. We'll give DeepSeek a minute to think this one through. I actually do believe that DeepSeek takes longer over this because it does come up with quite a lengthy answer. So I may have to keep this sentence moving for a long time while I'm doing it. You can see that what's coming up is going to be Groq. All right. But let's have a look. Here we go. It is quite a long answer. There are frameworks to consider, a bit similar to Gemini, but looking very robust. All right. So that's DeepSeek.

So as I said, we're now going to come on to Groq. So remember, this is Groq with a Q, not Grok with a K. That means we're dealing with Groq, the provider of fast inference on specialist hardware. They've built their own kind of hardware that's really, really fast at this. And they also support using OpenAI's library. They have their own too, but you can use OpenAI's. You pass in their key and the base URL, which looks like that. And you can see, as with Google, they've got an endpoint which has the word "openai" in it, because it's an endpoint that's designed to be compatible with OpenAI. The model we're going to use is Llama 3.3, the latest, biggest Llama 3 in the Llama 3 series. And it's got 70 billion parameters. It's very powerful. It's very impressive for that size. I believe it's either on par with or even outperforms the 405 billion version of the Llama model from before, from Llama 3.1. So it's a very powerful model indeed. Otherwise this is the same. And of course, this will take a very long time because it's a big model. Of course, it won't take any time at all because it's Groq, and Groq is super fast. Look at all of this that got generated in just a second or two. It is really cool using Groq because it's so, so fast like that. And we're seeing again a lot of stuff that looks familiar now. I guess mitigation strategies come up a lot.

Okay. And the next one — we're going to switch tactic. We're going to move to using Ollama. So just to explain again what Ollama is: it is a local service. It's a piece of software that runs on your local computer. And it provides an endpoint, a web service that you can call, running on localhost. So you'll be able to go to localhost and then some port and be able to talk to it. And the endpoint that it offers is compatible with OpenAI — the same kind of endpoint that we've been using in all of these other examples except for Anthropic. It has that same endpoint. And when you hit that endpoint, it has some highly optimized C++ code to run open-source models locally on your box. And it should be said that it can only run small models, because running it on your box directly — unless you have a really big computer, unless you have like a bitcoin mining rig or a big gaming box — then it's going to be problematic to run a large model. Just small models will work fine, and that's what we'll do right now. So if you don't have Ollama, you can install it, and it's very easy to install. There's a link right here. If you click on that link, it will bring up ollama.com. You press the download button, follow a couple of instructions, and it will be installed. That's all there is to it. Once you follow these instructions, you should be able to go to this here — localhost, my box, at port 11434 — and you should see what I see right here: "Ollama is running". And that tells you that all is well. So if it doesn't say that, you might need to first restart Cursor, maybe even reboot your computer, and then open up a terminal — which you can do with the control and the backtick button like this — and then you can type "ollama serve", and that should then work. And you should then be able to go there and see it running. Here are some other useful commands that you might want to know about for Ollama.

But let me make this very important point that I put a "super important, ignore me at your peril" — because many people ignored it when I said it before, and it's caused people distress. Llama 3.3 — that is the same model that we use with Groq up here — Llama 3.3 is a massive model with 70 billion parameters. It is way too big for most people's computers, including mine, and it takes like 100GB of space — or maybe it's like 60, I'm exaggerating now — but it's big, and it's not something that can fit in the memory of most computers. And unfortunately, Ollama does tend to have that in its sort of default recommended model, which confuses people. And some people have tried to use it, and it completely swallows up all of their computer resources. So steer clear of Llama 3.3 for running on your box. Instead, use a nice model like Llama 3.2, which is a nice few — 3 billion parameters. You can also do an even smaller one, llama3.2:1b. And there's also plenty of other models that are very popular: Qwen from Alibaba Cloud; Gemma is Google's small open-source model; Phi from Microsoft; or DeepSeek has these distilled versions of the model, which are, as I mentioned before — I think they're actually other models, they're Qwen and they're Llama — that have been trained on DeepSeek data, on synthetic data generated by DeepSeek. To see all of the different models, you can go to this models page in Ollama. It's just on this models tab, and you can read about all of the different models that are out there and see the different sizes they come in. And really, 7 or 8 billion or less is best. I'd stick with 1.5 billion or 3 billion if you can — that's the right kind of size.

And once you've done that, you can run "ollama pull" like this. You probably know that putting an exclamation mark in front of a command like this in Jupyter — sorry, this isn't Jupyter, in Cursor — putting an exclamation mark inside a notebook like this means this isn't Python code, this is a command that needs to be run as like a terminal command. And so it runs it in a little terminal right here. So it's worth knowing that trick. So we run "ollama pull llama3.2" to make sure that we've got that model locally. And then finally, finally, here we go. We use the same client library as if we're calling OpenAI, but we're not calling OpenAI. We're calling localhost, our local box — this URL right here. The API key doesn't matter. Something has to be provided, but it can be anything you want. Just put the word "ollama" in — that is what people tend to do. The model name, llama3.2 — that must match whatever you've pulled locally. The model needs to be there. And then the same chat completions create. Let's see what the little Llama 3.2, that's now going to be running on my computer, chugging away through its 3 billion parameters using fast C++ code... And here it is. It's done a slightly mediocre job. It seems to have sort of got bored after 0.3 — it's a .1, .2. And, uh, so, yeah, nice try. But obviously this is a really challenging question, and it may have shown the limits of a smaller model like Llama 3.2. But it's still a perfectly pleasant answer.

All right. When we come back, we're going to actually be starting to look at everything and doing some judging.

</details>

---
*Source: Official Udemy lecture transcript (auto-captions, lightly cleaned). Notes in Hinglish for self-study.*
