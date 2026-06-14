# L31 — Day 1: Vibe Coding — 5 Essential Tips for Efficient Coding

> **Week 2 — OpenAI Agents SDK** · ⏱️ ~7m · 🎥 Lecture 31 of 131
> **Instructor:** Ed Donner · **Lecture ID:** 49820399

---

## 🎯 Ek Line Mein (TL;DR)

**Vibe coding** (Andrej Karpathy ka coined term — LLM se code generate karwa ke ad-hoc style mein build karna) productive hai, lekin Ed ke **5 tips** follow karo — good prompts, multiple LLMs se verify, chhote testable chunks, validation, aur variety — warna LLM tumhe **astray** le jayega aur tum 200 lines ke broken code mein stuck ho jaoge.

---

## 📝 Hinglish Explanation (Detailed)

- **Context:** Week 2 Day 1 ka OpenAI Agents SDK wala first foray khatam hua. Yeh ek **sidebar lecture** hai — topic: **vibe coding**.
  - Term **Andrej Karpathy** ne coin kiya tha (ek viral X post mein) — LLM se code generate karwao, thoda tweak karo, aur generate karte raho — is **ad-hoc mode** mein naye frameworks bhi easily navigate ho jaate hain.
  - Ed strongly **encourage** karta hai vibe coding ko — lekin warning: galat tarike se karo toh LLM tumhe **led astray** karega aur tum **stuck** ho jaoge, jo bahut unpleasant hai. Isliye 5 tips.

- **Tip 1 — Good Vibes (prompt quality):**
  - Apna **prompt** acha banao jo **reusable** ho — baar baar use kar sako.
  - **Short answers** maango — LLMs by default **verbose code** likhte hain (har cheez mein exception handlers, long-winded approach). Explicitly bolo: **concise, clean code** chahiye.
  - **Today's date mention karo** prompt mein — bolo "use APIs that are **current as of this date**". Kyunki LLMs ki nasty tendency hai **older APIs** use karne ki (training data mein purane APIs zyada the).

- **Tip 2 — Vibe but Verify (multiple LLMs):**
  - Ek hi LLM ka answer leke chal mat do. **Same question 2-3 LLMs se pucho** — e.g., ChatGPT aur Claude dono open rakho.
  - Dono answers se seekhoge — often ek **too long-winded** ya point miss karta hai, aur doosra **spot on** hota hai. Cross-verification = better answers.

- **Tip 3 — Step Up the Vibe (small chunks):** *(Ed ka favorite tip)*
  - Ed ko students 200 lines ka LLM-generated code bhejte hain — "yeh kaam nahi kar raha, pata nahi kyun". Code mein **telltale signs** hote hain LLM generation ke — unwieldy, multiple bugs.
  - **Wrong way:** ek shot mein 200 lines generate karwana aur phir debug karna.
  - **Right way:** LLM se **function by function**, ~**10 lines at a time** — har piece **independently testable** ho. Problem ko **bite-sized chunks** mein divide karo.
  - **Trick:** agar khud divide nahi kar paa rahe, toh **LLM se hi puchho** — but clearly bolo "code generate MAT karo, sirf batao 4-5 simple steps kya honge jo independently test/verify ho saken". Phir har step ka code alag se generate karwao, **test ke saath** — 10 working lines at a time → end mein 200 **perfect** lines assemble.

- **Tip 4 — Vibe and Validate (cross-check answers):**
  - Ek LLM se answer milne ke baad **doosre LLM** (ya same, but doosra better) ke paas jao: "Maine yeh question pucha, yeh answer mila — confirm karo ki yeh appropriate hai, koi **bug** nahi, aur isse **concise/better-structured/clearer** nahi ho sakta?"
  - Validating LLM often problems detect karta hai ya code cleaner/simpler banata hai.
  - Yeh manually **Evaluator-Optimizer agentic design pattern** ko mirror karta hai — agentic patterns ka leaf nikal ke apni coding mein use karo!

- **Tip 5 — Vibe with Variety (multiple solutions):**
  - Sirf "code generate karo" mat bolo — especially 10-line problems ke liye bolo: "**3 different solutions** do, 3 different approaches".
  - Ho sakta hai jawab aaye "ek hi clear way hai" — but often 3 alag solutions milenge. Yeh model ko **different approaches contemplate** karne ke mode mein force karta hai → **better solutions**.
  - Saath mein **rationale explain** karne ko bhi bolo — model ko sochna padega ki kyun differently approach kar raha hai, aur bonus: tumhe bhi samajh aayega kya ho raha hai.

- **Bonus point (Ed ka implicit 6th tip):**
  - Vibe coding ke baad **hamesha LLM se code explain karwao** agar clear nahi hai — **har single cheez samajhni chahiye** jo code mein ho raha hai.
  - Vibe coding fun/productive/powerful hai, but agar tum follow nahi kar rahe ki actually kya ho raha hai, toh jab kuch galat hoga toh **painful and frustrating** ho jayega. **Stay in touch with what's going on.**

---

## 🔑 Key Concepts / Important Terms

| Term | Simple Hinglish Meaning |
|------|--------------------------|
| **Vibe Coding** | Karpathy ka term — LLM se code generate karwa ke ad-hoc tweak-and-go style mein development karna |
| **Good Vibes (Tip 1)** | Reusable, high-quality prompt banao — concise code maango + today's date dekar current APIs enforce karo |
| **Vibe but Verify (Tip 2)** | Same question 2-3 LLMs (ChatGPT + Claude) se puchho, answers compare karo |
| **Step Up the Vibe (Tip 3)** | ~10-line independently testable chunks mein generate karwao, 200-line one-shot nahi |
| **Vibe and Validate (Tip 4)** | Ek LLM ka answer doosre LLM se review/confirm karwao (manual Evaluator-Optimizer) |
| **Vibe with Variety (Tip 5)** | 3 different solutions + rationale maango — model better approaches explore karega |
| **Evaluator-Optimizer Pattern** | Agentic design pattern jisme ek LLM generate karta hai aur doosra evaluate/improve — Tip 4 iska manual version hai |
| **Stale API Problem** | LLMs training data ki wajah se purane/deprecated APIs suggest karte hain — date-pinned prompt se fix |

---

## 💡 Backend Dev Ke Liye Note (aapke liye)

- **Tip 3 = TDD/unit-testing philosophy applied to LLMs:** jaise tum kabhi 200-line PR bina tests ke merge nahi karte, waise hi LLM se bhi function-level, independently testable units maango — har chunk ka "test ke saath generate karo" bolna matlab red-green-refactor loop LLM ke saath.
- **Tip 4 ka Evaluator-Optimizer pattern** wahi hai jo tum code review process mein karte ho — author ≠ reviewer. Ek LLM generator hai, doosra reviewer; production agent systems mein yeh pattern automated hota hai (Week 1 ke design patterns yaad karo).
- **Stale API problem tumne khud face kiya hoga:** LLM se OpenAI SDK code maango aur woh `openai.ChatCompletion.create()` (deprecated v0.x API) de deta hai. Date-pinning prompt mein dalna == `requirements.txt` mein version pin karne jaisi hygiene, but prompts ke liye.
- **"Problem decomposition by LLM" meta-trick** architecture planning jaisa hai: pehle high-level design (steps list, no code), phir implementation per-module — same discipline jo tum system design mein follow karte ho, ab prompting mein.

---

## 🧠 Takeaway (yaad rakho)

1. **Vibe coding karo, but discipline ke saath** — Karpathy-style ad-hoc generation fun aur productive hai, lekin blind trust = stuck.
2. **Prompt mein concise code + today's date** maango — verbose code aur stale APIs dono avoid honge.
3. **10 lines at a time, independently testable** — 200-line one-shot generation kabhi nahi; decomposition khud LLM se karwa sakte ho (code-free planning step).
4. **Ek LLM ka output doosre LLM se verify/validate karwao** — yeh manual Evaluator-Optimizer agentic pattern hai.
5. **Har generated line samajhna mandatory hai** — explain karwao jab tak clear na ho, warna debugging painful hogi.

---

<details>
<summary>📜 Full English Transcript (original, click to expand)</summary>

So that concludes our very first foray into OpenAI Agents SDK. But before we wrap up week two, day one, I did want to have a second sidebar with you. And this time it's on the entertaining topic of vibe coding, which is a term coined by the legendary Andrej Karpathy, who described this in I think it was an X post that went viral about the way that he was enjoying coding with LLMs and getting so much done in a way that you would sort of let the LLM generate some code and sort of go with it, tweak it a bit, generate some more, and just make so much progress in this sort of mode of working — this ad hoc vibe coding way of navigating around things like new frameworks. So I think this is wonderful and I strongly encourage vibe coding, and I imagine that most of you are very good at it. I did want to give a few tips that I think are important to do it well, because I think it's easy to do vibe coding and to get led astray by LLMs and get yourself in trouble and get stuck, which is very unpleasant. So I have five tips to leave you with, before we get into more detail with OpenAI Agents SDK. And here they are.

First of all, good vibes. It's important to spend time getting your prompt to the LLM to be really good, that you can reuse lots of times. You should ask for short answers. LLMs tend to be quite verbose in the code that they generate; they like packaging everything with lots of exception handlers, and they tend to do things in quite a long-winded way. Try and ask it to come up with concise, clean code, and also mention today's date and say, please make sure that you use APIs that are current as of this date. Otherwise, LLMs have a nasty tendency to use older APIs because that was in a lot of their training data, so explicitly prompt for that.

Vibe, but verify — my second tip. Don't just ask an LLM a question and go with it. Ask a couple of LLMs. So I often ask the same question to ChatGPT and to Claude and have them both up. I ask the question because I'll learn from both of the answers. Often one of them is too long-winded or is missing the point a bit, and one of them will be spot on. And so asking a couple or maybe even three, so that you're verifying what answers you're getting, is a really good technique.

Step up the vibe. So this is saying — I think this is such a great one. This is because I sometimes get students sending me problems. They're saying, I'm stuck with this, and they'll send me some code and it will be like 200 lines of code and they'll say, it's not working, I don't know why. And when I look through the code, it's immediately obvious to me that this is — they've been vibe coding. You can tell there are telltale signs that a lot of this was generated by an LLM, and it's unwieldy, and I can sometimes see a bunch of different bugs in it. And I come back and I say, it's no good. It's no good generating 200 lines of code and then saying it's broken. That's not the way to do it. Rather, you should always try and get LLMs to do things a little piece at a time. Generate function by function. Generate small pieces that are independently testable, like ten lines of code at a time. So you should think of dividing your problem down into small bite-sized chunks and have an LLM do each piece of it. And here's the trick: if you can't think about how you would divide your problem down into ten smaller steps or whatever, you don't need to, because you can ask an LLM to do that. But be very clear — you don't want it to generate code. You say, look, I'm trying to solve the following problem — and you tell it — and say, what I want you to do is tell me what would be the 4 or 5 steps in a solution where each step is a simple, bite-sized chunk that could be tested and verified independently, and get it to come up with those chunks. And then you can ask again LLMs to generate code for each one in turn, along with the way to test it, so that you can make sure that, ten lines of code at a time, you have a working solution, and you've convinced yourself that when you've got each of these, you'll be able to put it together and have 200 perfect lines of code. Okay.

And then the fourth one, vibe and validate. Similar to vibe, but verify. But vibe and validate is saying you can ask a question to an LLM, and then when it gives you the answer, you can go to another LLM — or even the same one, but better to be another one — and say, I asked this question, I've got this answer. Please confirm that that is an appropriate answer and that you can't do anything that's more concise or better structured or clearer, or there are no bugs in this. And by having another LLM go through and validate, it will often detect problems or make it cleaner and simpler. So it's just a nice trick. And in many ways this mirrors — this echoes — the common design pattern of the evaluator-optimizer. But you can just do that manually yourself. So taking a leaf out of agentic design patterns and using it as part of coding.

And then my final one, vibe with the variety, which is: don't just say, can you generate code for this? But particularly if you're only talking about ten lines of code, say, can you give me three different solutions to this — approach it three different ways. And maybe the response will be that there aren't three different ways of doing it, there's only one clear way. But you might get three different solutions, and that will force the model into a mode where it's contemplating different ways of approaching the same problem, and as a result, you might get better solutions. As part of that, you can also ask it to explain itself — explain the rationale — so that you'll get something that will also force it to think through why it's approaching it differently. Plus, as an added benefit, it will explain to you what's going on so that you can really understand this.

And that does sort of lead to an obvious point, which I've not put here, which is that when you do vibe coding, you should always then go back and ask an LLM to explain it clearly if it's not immediately clear to you. Get to a point where you understand every single thing that's going on. Vibe coding is super fun and productive and powerful, but if you're not following what's actually happening, it's going to become painful and frustrating when something goes wrong. So it is important to stay in touch with what's going on. All right, and that is my survival guide to vibe coding, and I hope you'll find that helpful. But other than that, you should definitely do it. It's great fun and it's super productive.

</details>

---
*Source: Official Udemy lecture transcript (auto-captions, lightly cleaned). Notes in Hinglish for self-study.*
