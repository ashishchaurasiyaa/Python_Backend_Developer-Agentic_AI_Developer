# L95 — Day 2: Advanced Agent Chat — Multimodal & Structured Outputs

> **Week 5 — AutoGen** · ⏱️ ~9m · 🎥 Lecture 95 of 131
> **Instructor:** Ed Donner · **Lecture ID:** 49821599

---

## 🎯 Ek Line Mein (TL;DR)

Week 5 Day 2 me hum **AutoGen AgentChat** me deeper jaate hain — **MultiModalMessage** se images ko conversation me bhejte hain, aur **structured outputs** ke liye sirf `output_content_type=` me ek **Pydantic model** pass karte hain, bas — reply seedha typed Python object ban ke aata hai.

---

## 📝 Hinglish Explanation (Detailed)

- **Recap — AutoGen ke multiple layers:** Ed phir se yaad dilate hain ki AutoGen ek cheez nahi hai:
  - **Autogen Core** — agents ke interact karne ka infrastructure (low-level).
  - **Autogen AgentChat** — Core ke upar bana, **CrewAI / OpenAI Agents SDK jaisa** high-level framework. Aaj ka focus yahi hai.
  - Uske upar **Studio** (no-code/low-code platform) aur **Magentic-One** (Microsoft ka ready-made tool) — ye course me cover nahi honge.
- **Day 1 recap:** humne core concepts dekhe the — **models, messages, agents** — lekin **teams** abhi tak nahi. Aaj ek step deeper.
- **Aaj ke topics (rapid fire):**
  - **Multimodal** conversations — text ke saath **images** bhejna (course me pehli baar, naya concept).
  - **Structured outputs** — purana jaana-pehchana "old chestnut".
  - **LangChain tools ko wrap karke AutoGen se call karna** — kyunki LangChain ka tool ecosystem bohot bada hai, ye access milna luxury hai (agle lecture me hands-on).
  - **Teams** — quick whirl.
  - Ek **special guest entry** bhi hai end me (surprise demo).
- **Lab setup:** Week 5, Day 2 ka notebook — imports me hi `load_dotenv()` shove kar diya hai taaki seedha kaam shuru ho.

### 1) Multimodal Message — image + text ek saath

- Ek **URL** hai jo Ed ki website ki image ko point karta hai (AI ki duniya me enter karne wali evocative picture — workspace + whimsical doorway).
- Image ko **PIL (Python Image Library)** se open karte hain, fir usse ek **AutoGen Image** object banate hain.
- Ab pehle jahan **TextMessage** use karte the, wahan analogous **`MultiModalMessage`** banate hain:
  - `content` ek **list** hai — usme ek text prompt ("Describe the content of this image in detail") **aur** image object dono hain.
  - `source="user"` — yaani Ed khud.
- Bhejne ka tareeka bilkul same: **model client** banao (GPT-4o-mini), ek **AssistantAgent** banao (naam: "describer" / description agent) with system message *"You are good at describing images"*, fir `on_messages()` me multimodal message + **cancellation token** pass karo.
- Reply ko markdown me print karte hain — model ne image ko sahi pakda: brightly colored stylized space, workspace + otherworldly doorway, "limitless possibilities of AI". Models ko **markdown natively** aata hai, isliye headings/sections ke saath sundar response aaya. "It definitely got the joke."

### 2) Structured Outputs — sirf ek parameter ka khel

- Ek **Pydantic BaseModel subclass** banate hain: `ImageDescription` — 4 fields:
  - `scene` — overall scene briefly,
  - `message` — image kya point convey kar rahi hai,
  - `style` — artistic style,
  - `orientation` — portrait / landscape / square (ye thoda **meta-understanding** maangta hai — model ko image ke baare me analytically sochna padega).
- Har field pe **`pydantic.Field`** se description di gayi hai — yahi LLM ke liye instructions ban jaati hain.
- Use-case: structured data ko **UI pe dikhana, catalog karna, SQL database me likhna** — isliye free-text nahi, schema chahiye.
- Code me **sirf ek change**: AssistantAgent banate waqt **`output_content_type=ImageDescription`** pass karo. Bas. Same model client, same prompt.
- Ab `on_messages()` ka reply seedha **`ImageDescription` ka instance** hota hai — aisa lagta hai jaise model ne Python object return kiya ho.
- **Behind the scenes (Ed clear karta hai):** ye sab **JSON** hi hai — Pydantic model ek JSON spec me convert hota hai, model JSON return karta hai, aur wrapper code us JSON se object populate kar deta hai. Magic nahi, plumbing hai.
- Output ko **`textwrap`** se nicely print kiya — scene, message, style sab crisp aaye, aur `orientation` = **landscape** bilkul sahi identify hua.
- **Fun observation:** image me AI ka koi obvious hint nahi tha sivaye ek chhote se "AI" likhe hue text ke — model ne wo pakad ke description me include kiya. Impressive.
- **Asli point:** structured outputs AutoGen me itne easy hain ki bas type declare karo, aur schema-conformant data wapas milta hai jisse aage processing kar sakte ho.

---

## 🔑 Key Concepts / Important Terms

| Term | Simple Hinglish Meaning |
|------|--------------------------|
| **Autogen Core** | Low-level infrastructure layer — agents ke interaction ka foundation |
| **Autogen AgentChat** | Core ke upar bana high-level framework — CrewAI/OpenAI Agents SDK jaisa |
| **Studio / Magentic-One** | No-code platform aur Microsoft ka ready tool — stack ke top par, course me skip |
| **MultiModalMessage** | TextMessage ka bhai — `content` list me text + image dono jaate hain |
| **AutoGen Image** | PIL image se banaya gaya AutoGen ka image wrapper object |
| **PIL** | Python Image Library — standard image open/manipulate library |
| **AssistantAgent** | AgentChat ka workhorse agent — model client + system message + (optional) tools |
| **output_content_type** | AssistantAgent ka param — Pydantic class do, typed object reply me lo |
| **Pydantic Field** | Har field ki description — LLM ke liye field-level instruction ban jaati hai |
| **Cancellation token** | on_messages() call ke saath pass hone wala token — run cancel karne ka handle |
| **Structured outputs** | LLM se free text nahi, fixed schema (JSON → Pydantic object) me jawab lena |

---

## 💡 Backend Dev Ke Liye Note (aapke liye)

- **`output_content_type` = response_model pattern:** ye bilkul FastAPI ke `response_model=` jaisa hai — aap contract declare karte ho, framework serialization/validation handle karta hai. Under the hood wahi JSON schema + parse-into-Pydantic flow hai jo aap OpenAI structured outputs ya `instructor` library me dekh chuke ho — AutoGen ne bas isse ek constructor param bana diya.
- **Pydantic `Field(description=...)` yahan dual-purpose hai:** normally aap isse OpenAPI docs ke liye use karte ho; yahan wahi description **LLM ka prompt** ban jaati hai. Schema = prompt engineering. Field descriptions ko API docs jitni hi seriously likho.
- **MultiModalMessage ka `content: list` design** waise hi hai jaise Kafka me ek message envelope me mixed payload types — message type dispatch downstream agent decide karta hai ki kya karna hai. Day 4-5 me jab Autogen Core ka **RoutedAgent + type-based dispatch** aayega, ye message-type thinking kaam aayegi.
- **Hands-on lab:** is lecture ka code khud chalane ke liye `Practical/lab2_primary_evaluator.py` run karo (is repo me, `uv run` se chalta hai, Groq pe free via `OpenAIChatCompletionClient` + `base_url` + `ModelInfo`). Difference: hum AutoGen **0.7.5** use karte hain (course 0.5.1, same API family), aur Groq ke free models pe multimodal vision limited hai isliye lab structured outputs (`output_content_type`) pe focus karta hai — concepts same hain.

---

## 🧠 Takeaway (yaad rakho)

1. AutoGen 3-layer stack yaad rakho: **Core (infra) → AgentChat (CrewAI-jaisa) → Studio/Magentic-One (no-code)** — course Core + AgentChat pe hai.
2. Image bhejni ho to **MultiModalMessage** banao — `content` list me text + AutoGen Image, baaki flow TextMessage jaisa hi.
3. Structured output ke liye **sirf `output_content_type=PydanticClass`** — reply seedha typed object aata hai.
4. Ye "Python object return" ek illusion hai — **andar sab JSON** hai: schema jaata hai, JSON aata hai, wrapper object populate karta hai.
5. **Field descriptions hi LLM instructions hain** — `orientation` jaisi meta-analytical field bhi sahi nikli (landscape), kyunki description clear thi.

---

<details>
<summary>📜 Full English Transcript (original, click to expand)</summary>

And welcome to week five, day two, when we get deeper into Autogen agent chat. So as a reminder, I'd like to show these things a couple of times. Autogen which is multiple different things. There's Autogen core, which is the kind of infrastructure for agents interacting. There is Autogen agent chat, which is a thing that's quite like crew and OpenAI agents SDK. And then built on top of that are things we will not be looking at the no code, low code platform studio and their particular tool Magentic one. But we are going to be talking about Autogen and today it's more on Autogen agent chat. And you remember we talked about the core concepts of models and messages and agents and we got to see them all. And we didn't actually talk about teams. Today we're going to take it a little bit deeper. We always like to take it one more step deeper. But most of this is going to be concepts pretty familiar to you.

We're going to talk about going multi-modal. Uh, that's that's I guess new. We haven't really done that before. So that's going to be a new one to try out. We're going to talk about structured outputs, which is an old chestnut that you know well. We're going to look at something interesting. We can actually wrap tools in LangChain so that we can call LangChain tools from Autogen, which is going to be super convenient, especially as we're quite experienced with LangChain tools now. And because there's an enormous ecosystem of so many tools to choose from. So this is quite a luxury to have access to this. And then since we put teams up there, we better look at teams. So we're going to give that a quick whirl as well. And then there's a special guest entry as well. Something else just to put out there that I will show you that might entertain you. All right that's enough. Let's go do it.

Okay. So we are in. So we're in week five. We're going to the second lab for the second day. Week five, day two. Autogen agent chat. Going deeper. So I've got a bunch of imports, including I've shoved load dot env into the imports as well so we can get on with stuff. All right. So I'm going to start by showing you how you can have like a multi modal conversation which isn't just about text, but you can send pictures along with the text and have that be part of it. So we've got here that we've got a URL, and that URL is linking to an image from my website. And then we're going to open that image using a very standard Python images library. The Python image library is what PIL stands for. And we're going to to create an autogen image from that and then take a look at it. So here it is. It's a cool picture that's meant to be evocative of sort of going into the world of AI.

So we're now going to create a multi-modal message. So you remember in the past we've had text message. Well, this is analogous. It's a MultiModalMessage and it has content which has a list. It has like a bit of text to describe the content of this image in detail. And then it's got the image and the source is user. That would be me. So just running that is all it takes to create a multi-modal message. And then sending that to GPT 4o mini is just as simple as doing exactly what we did before. We create the model client and then we create an assistant agent. I'm calling it the describer or the real name description agent. The model client you pass in, of course, which is the LLM, the system message. You are good at describing images. Fair enough. And then uh, then the user prompt, of course is right there. And then the we pass in that multimodal message and we also just say the cancellation token. And then we will print that markdown version of the reply. And this will take, take a little while because it's got to take in that image and it's got to get back all of the response from it. So I have to let this sentence run on quite a bit to see what we get back.

And here it is. Uh, not too bad. Uh, so you'll see that it has worked. Uh, the image depicts a brightly colored, stylized space that combines elements of a workspace with whimsical, otherworldly doorway. And then we've got, of course, because models are great at markdown, that's what they love. That's that's one of the languages they speak natively. You get the room setting, furniture, doorway, decorative elements. The overall, the image cleverly intertwines a workspace focused on technology and coding with imaginative and vibrant elements that evoke the limitless possibilities of AI. So it definitely got the joke. It understood what the image was about, and it did a fine job of describing it. And that is an example of a multi-modal message with Autogen.

And then for my next trick, I'm really going to throw things at you rapid fire today because you know, much of this stuff we're going to do structured outputs, something you know well. And it made it very easy in Autogen. It really is. So this is a subclass of the Pydantic base model called image description. So that's what I'm calling it. And it's a class that I'm going to want to populate with the answer from the LLM. And so I give it four fields scene, message, style and orientation, which is how I want the model to describe the image in a particular structure. Perhaps I'm going to put that on my on my on my user interface. Perhaps I'm going to catalog it in some way, write it into a SQL database. So I then use pydantic Field to be able to describe each one. The scene is briefly overall scene in the image message, the point that the image is trying to convey style, the artistic style and orientation. So we're going to going to ask it a more kind of analytical question about like, what is this, a portrait image, a landscape image, or a square image, which requires it to have a slightly more, uh, more of a meta understanding of what it's looking at? Uh, so, uh, we'll see how it can fare with this. So this is the pydantic object that we want it to populate.

And here is the code. Uh, as before, we create the model client, the the GPT 4o mini. And then this is our agent. It's it's again the description agent, same model client, same prompt and this is the only change output_content_type equals and we pass in the pydantic object. Super simple. It's made it just that we state what we want. And so what we now, what we expect is that when we call on messages, the same, same thing that you use to invoke, to use the term, uh, the same thing you used to to call this LLM, um, what comes back? The reply we expect to simply be a type of this object. It's going to have replied with this object. And remember, it feels as if the model is able to reply with a Python object. And what's going on behind the scenes. I know you know this. It's all just JSON. This is converted into some sort of a JSON spec, and the model returns JSON and the wrapper code then populates this object from the JSON.

Okay, let's run that. We're doing the same the same image again, which means I should have run it while I was prattling away so I wouldn't have to fill the dead air with my nonsense. But it's done. And what we've got back. I just printed it. It is indeed an image description object. It is an instance of this and you can see scene is populated. Let's let's print this out nicely. So I'm using this thing called textwrap that prints something that's formatted, uh, to, to wrap around at the end of a certain number of characters. We'll print the scene, the message, the style and the orientation. Uh, here it all is. Uh, it's nice and crisp, scene a colorful and imaginative interior of a room showcasing a workspace and a door leading to a vibrant portal message. The image conveys the theme of creativity and the potential of AI, suggesting a gateway to new possibilities. Style A vibrant, illustrative style with bold colors and exaggerated features, giving it a surreal and playful appearance and orientation landscape. It correctly identified the basics that this is in fact a landscape picture.

Uh, if we come back to the picture as well, I will point out something quite clever, which is I only realised, actually now talking about this with you, that, uh, nowhere on here. It's not clear why it sees this as something to do with AI. And the answer is, you can see because the writing AI is up here, that's the only clue, I think, unless I'm missing something obvious, that's the only clue that that is what this diagram this is taken from, from a, from a course I did, which is about, you know, the doorway, the what it means to go into the world of AI and, uh, the, uh, um, yeah, it's funny that I'd given this course and I'd had this as my, my image for it, and so I'd had AI in there. And it's funny that it spots that and includes that in the, in the description. Very, very impressive I've got to say. But that wasn't the point of this. The point of this was to show you that we can use structured outputs easily, and we can get back our data. That is according to this schema. And this would allow us to go in and do more processing with this if we needed to.

</details>

---
*Source: Official Udemy lecture transcript (auto-captions, lightly cleaned). Notes in Hinglish for self-study.*
