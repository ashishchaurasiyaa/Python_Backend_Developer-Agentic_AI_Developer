# L14 — Day 3: Multi-Model Orchestration — Evaluate AI Responses

> **Week 1 — Foundations** · ⏱️ ~11m · 🎥 Lecture 14 of 131
> **Instructor:** Ed Donner · **Lecture ID:** 49771149

---

## 🎯 Ek Line Mein (TL;DR)

Pichle lecture mein 6 alag-alag **LLMs** ne ek hi question ka answer diya tha — ab is lecture mein ek **judge LLM (o3-mini)** se un sab responses ko **evaluate aur rank** karwate hain, **strict JSON output** ke saath. Ye hi **"LLM-as-a-Judge"** / **evaluator pattern** hai — multi-model orchestration ka core building block.

---

## 📝 Hinglish Explanation (Detailed)

- **Setup recap:** Pichle lecture se humare paas do Python lists hain — `competitors` (model names: GPT-4o-mini, Claude, Gemini, DeepSeek, Groq pe Llama 3.3, Ollama pe Llama 3.2) aur `answers` (har model ka response). Ab inhe manually padh kar judge karna **tedious** hai — to kyun na ye kaam bhi ek **LLM se hi karwaya jaye**?

- **Data ko pair karna (`zip`):**
  - `for competitor, answer in zip(competitors, answers):` se dono lists ko **saath-saath iterate** kar ke har model ka naam aur uska answer print kiya.
  - Cursor ne tab-complete se pura code likh diya — Ed yahan AI-assisted coding ka flow bhi dikhate hain.

- **Ek combined string banana (`enumerate`):**
  - Saare answers ko ek single string `together` mein collect kiya — format: `"Response from competitor 1"`, `"Response from competitor 2"`, etc.
  - `enumerate(answers)` use kiya taaki index bhi mile (manual `count += 1` ki zaroorat nahi), aur **index + 1** kiya taaki competitor numbering 1 se start ho, 0 se nahi.
  - Ed se live ek **mistake** hua jo print karne par pakda gaya — lesson: **intermediate outputs hamesha print/inspect karo**, prompt blindly LLM ko mat bhejo.

- **Judge prompt design (sabse important part):**
  - Prompt: *"You are judging a competition between {N} competitors. Each model has been given this question... Your job is to evaluate each response."*
  - **Respond in JSON, and only JSON** — expected format: `{"results": ["best competitor number", "second best", "third best", ...]}` — sirf **rank numbers**, model names nahi.
  - Phir saare competitors ke responses prompt mein paste kiye, aur end mein: *"Do not include markdown formatting or code blocks."*
  - **Kyun?** Kyunki models ko output ke around ```` ```json ```` **code fences** add karne ki aadat hai — ye explicit instruction se **pure JSON** wapas milta hai jo directly parse ho sake.
  - Python tricks mention hue: **triple quotes** (multi-line string block) aur **f-string mein `{{` double curly braces** — taaki literal `{` string mein aaye, code ki tarah interpret na ho.

- **Important detail — anonymized judging:**
  - Judge ko **model names nahi bataye gaye**, sirf competitor numbers — taaki **bias na ho** (judge khud OpenAI ka model hai, aur competitor #1 bhi GPT-4o-mini hai — interesting test ki kya wo apne family ke model ko favour karega).

- **Judge call:**
  - Judge prompt ko standard **messages list** structure mein daala aur judge model choose kiya: **o3-mini** — ek **reasoning model**, thoda pricier, lekin evaluation jaise task pe zyada "attention" deta hai.
  - Cheap option bhi chalega (GPT-4o-mini) — **Vellum leaderboard** pe cost/quality compare kar sakte ho.

- **Results parse karna:**
  - Response **perfect JSON** mein aaya → `json.loads()` se dict banaya → `results` key pluck ki → `enumerate` se iterate kar ke har rank number se 1 subtract kiya aur `competitors` list mein lookup kar ke **best-to-worst ranking** print ki.

- **Final ranking (unscientific, fun results):**
  1. **Gemini 2.0 Flash** 🥇
  2. **GPT-4o-mini**
  3. **Llama 3.3** (Groq)
  4. **DeepSeek**
  5. **Claude 3.7**
  6. **Llama 3.2** (Ollama, local) — "flailing", jo answer aadha chhod kar give up kar gaya tha
  - Note: judge (o3-mini) ne apne hi family ke GPT-4o-mini ko top par **nahi** rakha — anonymization kaam kar gayi.

- **Isse scientific kaise banaye (exercise idea):**
  - Sirf ek judge pe depend mat karo — **har competitor se rankings nikalwao aur averages lo** (ensemble of judges / voting). Ye single-judge approach se zyada robust hai.

- **Lab ka asli homework:**
  - Identify karo ki is example mein kaunse **agentic workflow patterns** use hue (hint: ek se zyada hain — ek **hybrid/mish-mash** ho sakta hai; diagrams wapas dekho).
  - Phir apni pasand ka **ek aur pattern add karo** is mix mein, aur **community contributions** folder mein **PR** bhejo (tip: push se pehle notebook ke **outputs delete** karo, aur sirf community-contributions folder mein hi push karo).

- **Lab ke do goals the:**
  1. Alag-alag **APIs experiment** karna — dekhna ki **OpenAI API format** kitne saare models pe chalta hai (Anthropic ko chhod kar), basic API structure aur prompts samajhna.
  2. **Models ke beech orchestration** — ek question, multiple models ke answers, ek aur model se evaluation; bada problem chhote problems mein todna; thodi **autonomy** (pehle model ne khud question choose kiya tha).

- **Commercial implications (universally applicable):**
  - Ye pattern **har jagah** lagta hai — same request ko **multiple LLMs ko bhejna**, responses **evaluate** karna, **best select** karna (ya top-2 select kar ke feedback dena).
  - Iska fayda: **robustness aur accuracy** badhti hai, aur harder problems solve hote hain.
  - Examples: summarization, email writing, document generation, **business requirements document** — kisi bhi generative task pe "send to multiple models → vote on best outcome" technique **aaj hi apne projects mein** laga sakte ho.

---

## 🔑 Key Concepts / Important Terms

| Term | Simple Hinglish Meaning |
|------|--------------------------|
| **LLM-as-a-Judge** | Ek LLM se doosre LLMs ke outputs evaluate/rank karwana — manual review ki jagah |
| **Evaluator / Evaluation pattern** | Agentic pattern jisme ek model output generate karta hai, doosra model uski quality judge karta hai |
| **Multi-model orchestration** | Ek hi task multiple models ko bhejna aur unke outputs ko combine/compare/select karna |
| **Anonymized judging** | Judge ko model names na batana (sirf numbers) — taaki self-bias na aaye |
| **Structured output (JSON-only)** | Prompt mein strictly bolna "respond in JSON only, no markdown/code blocks" taaki output programmatically parseable ho |
| **Code fence problem** | Models ka habit ki JSON ke around ```` ```json ```` wrap kar dete hain — explicit instruction se rokna padta hai |
| **o3-mini** | OpenAI ka reasoning model — judge ke role ke liye choose kiya kyunki evaluation pe zyada soch-samajh kar kaam karta hai |
| **Ensemble of judges** | Ek judge ki jagah multiple models se rankings le kar average/vote karna — zyada scientific evaluation |
| **`zip()` / `enumerate()`** | Python idioms — do lists ko saath iterate karna / index ke saath iterate karna (prompt assembly mein use hue) |
| **Vellum leaderboard** | Model pricing/performance compare karne ki site — judge model choose karne ke kaam aayi |

---

## 💡 Backend Dev Ke Liye Note (aapke liye)

- **LLM-as-a-Judge = automated code review pipeline:** Jaise CI mein ek service doosri services ke outputs validate karti hai, waise hi yahan ek model doosre models ke responses score karta hai. Single judge = single approver (bias risk); ensemble of judges = multiple reviewers + majority vote — wahi quorum/consensus thinking jo distributed systems mein use karte ho.
- **"JSON only, no code blocks" abhi prompt-level hack hai** — production mein aap isi jagah **Pydantic + structured outputs / `response_format`** use karoge (jaise API response ko schema se validate karna). `json.loads()` pe blind trust mat karna — ye exactly wahi problem hai jaise untyped external API response parse karna; validation layer zaroori hai.
- **Anonymized judging** = blind A/B testing. Judge ko model identity dena waisa hi hai jaisa A/B test mein users ko variant ka naam bata dena — evaluation bias inject ho jata hai. Numbers-only ranking design deliberate hai.
- **Hands-on:** is lecture ka code khud chalane ke liye ye lab run karo → `Practical/lab2_multi_model_judge.py` (`uv run` se chalta hai, Groq-free setup).

---

## 🧠 Takeaway (yaad rakho)

1. **Multiple models ke outputs ko manually judge karna scale nahi karta — ek judge LLM use karo** (LLM-as-a-Judge pattern).
2. **Judge prompt mein strict JSON format mandate karo** aur explicitly bolo "no markdown formatting or code blocks" — warna parsing tootegi.
3. **Judge ko model names mat do, sirf anonymous numbers** — self-family bias se bachne ke liye.
4. **Ek judge unscientific hai** — robust evaluation ke liye multiple judges se rankings le kar average/vote karo (ensemble).
5. Ye "fan-out to N models → evaluate → select best" pattern **universally commercial** hai — summarization, email, BRD, kisi bhi generative task pe robustness/accuracy badhane ke liye aaj hi laga sakte ho.

---

<details>
<summary>📜 Full English Transcript (original, click to expand)</summary>

Okay, so it's time to evaluate who did best and what better way to evaluate who did what best than to use an LLM for this task. It would be tedious to have to read through all of these and decide. First, let's just understand where we are. So we had two lists. One was called competitors and one was called answers. I love the way Cursor does that. And so we can just print them out and we'll see that we've got these two lists. There they are. These are our competitors. I hope you recognize them. And these are their answers.

So one thing that's nice to do right now, it would be sort of nicer to be able to pair these up and say which one is which. There's a really useful Python function called zip that is worth knowing about. It's like a pro thing to use, and you can iterate through these two collections together like this. I can say for — look, haha, what am I doing here? I just pressed tab. You can say for competitor and answer. Those are the two we want to be iterating through, competitors and answers in. And if you say zip(competitors, answers), then it will just iterate through these two lists together. And competitor and answer will have each one. And it's written all the code for me. That's exactly what I wanted to do. So if I do this now, you'll see that it's printing each competitor and its answer one after another. Very nice.

Okay, but let's bring it together into one string called together. And I also wanted to show another construct here called enumerate. If you have a list like answers, a list of things, and you want to iterate through them, but you also want to track the index number as you do — people that don't know about enumerate often have a kind of count equal zero, count plus equals one in your loop. Not needed. Enumerate is a nice little trick. You can say for index, comma, answer in enumerate(answers), and then you will just step through. And so we will say response from competitor. And we're going to add one to the index so that the first one is competitor number one rather than competitor number zero, which just doesn't sound as nice. So we run that and then, why don't I just show you what that looks like? But I'm sure you believe me. It looks like this. And if I print it, we'll see it looking a bit more pleasant than that. Here you go. So you can see response — oh, look at that. There's a mistake. Just as well I did print it, isn't it? That's the benefit of printing these things. You do that, then you get to see what's going on and see what's happening. Wow. Okay. I hope you caught that. That's embarrassing. But I think I'll keep it. So you get to see that not only can one make mistakes, but this gives you a great way to inspect what's going on and see what's happening. So when I print that now, we see response from competitor one. And presumably down below it will have response from competitor two.

All right. So now we're going to have a new bit of text. You are judging a competition between that many competitors. Each model has been given this question. Your job is to evaluate each response. And there is the — we say we want you to respond in JSON and only in JSON and follow this format: a JSON with results and then a competitor number, a second best competitor number, third best competitor number, and so on. And here are results from the competitors. And now respond with the JSON with the ranked order of the competitors. Nothing else. Do not include markdown formatting or code blocks.

So just a few things to point out about this. First of all, you may not be familiar with the triple quotes. If you use triple quotes in a Python string, you get to have an entire block of text without needing lots of quote marks and pluses and things. So this is a nice trick for a block of text. It's also, of course, used for docstrings, so I'm sure you have come across it before. Another thing to know is that I've sort of assumed you're familiar with f-strings before, but one nice trick to know is that if you actually want to have a curly brace within your string, then you can do that by having two curly braces in an f-string. So that's why there are two curly braces here, because we actually want one curly brace to appear in the string itself. We don't want this to be interpreted as code.

All right. So with that, if I print this to show you what on earth I'm prattling away about, what you should see is: you're judging a competition between six competitors. Each model has been given this question. Your job is to evaluate. Here is how to give us the results. And here are the responses from each. And there you see it in there. I'm also going to mention, you see at the end here I say do not include markdown formatting or code blocks. It's always worth doing that. Otherwise these models love to add in a little extra JSON tag around things. So if you use this text then you make sure you get pure JSON back.

Okay, so now that we've got this all set up, we're going to put this into messages. And then we're going to call an LLM and get our results. Let's do that. Okay. It's judgment time. So we're going to put this judge text into a messages list as usual with the normal structure. And now let's choose a judge. So I'm picking o3-mini, a little bit pricier I think than some of the others. So you should check the Vellum leaderboard. And you may want to just go with a cheap one, like using GPT-4o-mini. I'm going to go with o3-mini because we're going to try and have something that really pays attention to this. Now, I realized the first competitor in the list is GPT-4o-mini, and so it's a bit — that some of the same OpenAI models are judging themselves. And it'll be interesting to see whether it thinks that the model from its own family is the winner, and we're not telling it the model names, we're only giving it a rank number, so it's not going to know. So we'll see how number one fares. Actually, number one's answer did look really good. So it might do very well. We will see. But we're letting o3-mini make the call. Let's see how it does. Off it goes. It's thinking about it. It's taking its time. It's doing some reasoning. And here's the answer. So it doesn't put GPT-4o-mini at the top. It puts model number three. And you probably remember AI model number two was Anthropic; model number three, I forget — was it DeepSeek? We'll soon find out.

So we are now going to load this, which has come back in perfect JSON just as we wanted. We're going to load it into a dictionary. We're going to pluck out results. So now we're going to have this. We're going to iterate through it using again this enumerate approach. For each one we're going to look at this string and subtract one and look it up in the competitors list and print the results. So if you're following me, this is just going to print out from best to worst the names of the models in our results. Drum roll please. Here we go. So it was Gemini 2.0 Flash. That is our winner. And GPT-4o-mini came second. Llama 3.3 came third and then DeepSeek and then Claude 3.7. But bottom of the list was the flailing Llama 3.2 that kind of gave up halfway. So there are the unscientific results of our judgment. Of course, it will be great fun for you to try this in a more scientific way. For example, you could have each of the different competitors come up with the rankings and then use that to take averages. That kind of thing would be a rather more interesting way of assessing it than just simply going with whatever o3-mini tells us.

So anyway, this was a really interesting experiment designed to show you how you can collaborate between LLMs. So hopefully you were paying attention during this and the last lecture, and you've been able to identify which agentic workflow patterns were used in this example. Pattern or patterns? There might be a couple. If you're not sure, then go back through it and have a think and look back at the diagrams. And it might be some sort of hybrid or mish-mash between a couple of them. And the exercise for you: first of all, do that. And then secondly, please pick one of the patterns that interests you and add that to this mix.

The goal of this lab was twofold. First of all, to experiment with different APIs and see for yourself how the OpenAI API is used so frequently across many models, except Anthropic, and also to experiment with the sort of the basic API structure and the prompts. And the second goal was to experiment with this orchestration between models: asking a question, having multiple models answer, getting another model to assess the output. All this stuff is about interactions between models, dividing up a bigger problem into smaller problems, and a little bit of autonomy in terms of coming up with whatever question the first model wished to. So, yeah, add another agentic design pattern. I'd love to see it. And then once you've done that, consider doing a PR and putting it in community contributions. There'll be instructions in the resources on how to do that. A good tip is to note to delete outputs of your notebook before you do it, so there's not lots of junk in there. And be sure that you're only pushing things in that community contributions folder. There'll be instructions. It'll be fabulous to see what you're doing, and to see some interesting design patterns added in to this kind of exercise.

And then final thought for this lab is about commercial implications. I do want to always bring it back to how you can think about this in a commercial setting. And to be honest, it's hard to be specific here because this is so universally applicable. Really, any time that you have something that you want to generate something, you want an LLM to take care of, these kinds of patterns — being able to send the same request to multiple LLMs, being able to then evaluate responses and either select the best or perhaps select a couple of best ones, or use that to give feedback. All these kinds of patterns are used to increase the robustness and the accuracy of models, and to be able to solve harder and harder problems. So really this is, as I say, universally applicable. So you should be able to pick whatever commercial problem you can think of that you're applying AI to, whether it's a summarization kind of problem or a generative problem — writing an email, building a document, writing a business requirements document — and you can think of how you could apply these kinds of techniques. Sending the request to multiple models. Voting on the best outcome. This is something that you should be able to apply to your projects right away.

</details>

---
*Source: Official Udemy lecture transcript (auto-captions, lightly cleaned). Notes in Hinglish for self-study.*
