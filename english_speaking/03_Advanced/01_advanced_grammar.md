# 🧠 Advanced Grammar — conditionals, passive, reported speech, gerunds

Yeh file un grammar structures ke baare mein hai jo aapko *intermediate se senior-level English* tak le jaate hain. Interview mein, design discussion mein, ya code review mein jab aap "agar yeh hota toh woh hota" type baatein bolte ho — yahi structures aapko fluent aur professional banate hain. Har section mein formula + use + bahut saare examples hain.

---

## 1. 🔀 The Conditionals (agar... toh...)

Conditionals = "if" wale sentences. English mein 4 main types hote hain + ek "mixed". Indian speakers yahan sabse zyada slip karte hain kyunki Hindi mein tense ka concept thoda alag hai. Dhyaan se padho — yeh interview mein bahut aata hai.

### Quick reference table

| Type | Use (kab) | If-clause | Main clause | Hindi feel |
|------|-----------|-----------|-------------|------------|
| Zero | General truth / facts | present simple | present simple | hamesha hota hai |
| First | Real future possibility | present simple | will + verb | ho sakta hai (real) |
| Second | Unreal / imaginary present | past simple | would + verb | agar hota (kalpana) |
| Third | Unreal past (regret) | had + past participle | would have + p.p. | agar hua hota |
| Mixed | Past cause → present result | had + p.p. | would + verb | tab woh hua hota toh ab... |

### Zero conditional — general truths

> Formula: **If + present simple, present simple**

Use: facts, science, automatic results. Hindi: "agar yeh, toh hamesha woh."

- If you **heat** water to 100°C, it **boils**.
- If the cache **expires**, the system **fetches** fresh data.
- If you **don't commit** your code, it **stays** only on your machine.

### First conditional — real future

> Formula: **If + present simple, will + base verb**

Use: ek real situation jo future mein ho sakti hai. Yeh sabse common hai daily work mein.

- If the build **passes**, we **will deploy** tonight.
- If you **send** me the logs, I **will debug** the issue.
- If the latency **increases**, we **will add** a caching layer.

> ❌ Common mistake: "If you will send me the logs, I will debug."
> ✅ Correct: "If you **send** me the logs, I will debug." (if-clause mein "will" nahi aata!)

### Second conditional — imaginary present/future

> Formula: **If + past simple, would + base verb**

Use: kuch jo *real nahi hai* abhi — kalpana, advice, ya politely hypothetical baat. Interview mein "what would you do if..." ka jawab isi mein dete ho.

- If I **were** the tech lead, I **would prioritise** observability.
- If we **had** more time, we **would refactor** this module.
- If the team **were** smaller, communication **would be** faster.

> ❌ Common mistake: "If I was you, I would..."
> ✅ Correct (formal): "If I **were** you, I would..." (subjunctive "were" sabhi persons ke liye — yeh educated English ka mark hai).

### Third conditional — unreal past (regret / hindsight)

> Formula: **If + had + past participle, would have + past participle**

Use: jo ho chuka hai uske baare mein "kaash aisa hota". Postmortem meetings ki language!

- If we **had added** monitoring, we **would have caught** the bug earlier.
- If I **had reviewed** the PR carefully, we **wouldn't have shipped** that regression.
- If they **had load-tested** it, the outage **would not have happened**.

### Mixed conditional — past cause, present result

> Formula: **If + had + past participle, would + base verb**

Use: past ka action, present ka result. Bahut natural lagta hai jab sahi use karo.

- If we **had documented** the API, new devs **would understand** it now.
- If I **had learned** Go earlier, I **would be** more comfortable with this codebase today.

---

## 2. 🛠️ The Passive Voice

Passive voice = jab action important hai, *kaun ne kiya* utna important nahi. Tech writing, documentation, aur postmortems mein passive bahut use hota hai kyunki yeh neutral aur professional lagta hai (blame kisi par nahi).

> Structure: **subject + form of "be" + past participle (+ by ...)**

### When & why to use passive

| Reason | Example |
|--------|---------|
| Doer unknown / unimportant | The server **was restarted** at 2 AM. |
| Focus on the result, not the person | The bug **was fixed** in the last release. |
| Neutral / blame-free tone | Mistakes **were made** during deployment. |
| Process / documentation style | The data **is validated** before it **is stored**. |

### Active ↔ Passive conversion

| Tense | Active | Passive |
|-------|--------|---------|
| Present simple | The team **deploys** the app. | The app **is deployed** by the team. |
| Past simple | A junior dev **wrote** the script. | The script **was written** by a junior dev. |
| Present perfect | We **have released** v2. | v2 **has been released**. |
| Future | We **will migrate** the DB. | The DB **will be migrated**. |
| Modal | Someone **must review** the code. | The code **must be reviewed**. |

> ❌ Overusing passive: "It is believed by us that the system is to be improved by the team."
> ✅ Better: "We believe the team should improve the system." — Active is usually clearer in *speech*. Use passive deliberately, not by accident.

**Speaking tip:** Interview mein apne kaam ke baare mein active voice use karo ("I built", "I led", "I designed") — yeh ownership dikhata hai. Passive ("it was built") tab use karo jab process describe kar rahe ho.

---

## 3. 🗣️ Reported (Indirect) Speech

Reported speech = kisi ki baat ko *apne shabdon* mein bolna, quotes ke bina. Standups mein "He said the API is down" type sentences — yeh roz lagte hain.

### Tense backshift rule

Jab reporting verb past mein ho (said, told), toh original tense ek step **peeche** chala jaata hai.

| Direct speech | Reported speech |
|---------------|-----------------|
| "I **am** busy." | He said he **was** busy. |
| "I **work** here." | She said she **worked** there. |
| "I **am working**." | He said he **was working**. |
| "I **fixed** it." | She said she **had fixed** it. |
| "I **will** call." | He said he **would** call. |
| "I **can** help." | She said she **could** help. |
| "I **have** finished." | He said he **had** finished. |

Time/place words bhi badalte hain: now → then, today → that day, tomorrow → the next day, here → there, this → that.

> Note: agar baat **abhi bhi sach hai** (general truth), backshift optional hai. "He said the Earth **is** round" — fine.

### say vs tell — yeh Indians ko bahut confuse karta hai

| Verb | Pattern | Example |
|------|---------|---------|
| **say** | say (something) — **no person** directly | He **said** that the build failed. |
| **tell** | tell **somebody** (something) | He **told me** that the build failed. |

> ❌ Common mistake: "He **said me** that..." / "He **told** that..."
> ✅ Correct: "He **told me** that..." OR "He **said** that..."

**Rule of thumb:** *tell* ke baad hamesha ek person chahiye (tell me, tell the team). *say* ke baad seedha person nahi (say **to** me — yeh chalta hai).

### Reported questions

Questions report karte waqt word order **statement jaisa** ho jaata hai (no inversion), aur "?" hat jaata hai.

- Direct: "Where **is** the config file?" → Reported: She asked where the config file **was**.
- Yes/No questions ke liye **if / whether** use karo: "Is it deployed?" → He asked **if** it **was** deployed.

> ❌ "He asked where is the file."
> ✅ "He asked where the file **was**."

---

## 4. ➕ Gerunds vs Infinitives (-ing vs to)

Yeh shayad sabse "silently wrong" area hai Indian English mein. Kuch verbs ke baad **-ing** (gerund) aata hai, kuch ke baad **to + verb** (infinitive). Iska koi pakka logic nahi — patterns yaad karne padte hain.

### Verbs followed by GERUND (-ing)

enjoy, avoid, finish, consider, suggest, recommend, mind, keep, practise, deny, postpone, risk, involve

- I **enjoy debugging** complex issues.
- We should **avoid coupling** these modules.
- He **suggested refactoring** the service.
- The migration **involves rewriting** the schema.

### Verbs followed by INFINITIVE (to)

want, need, decide, plan, hope, agree, promise, manage, offer, refuse, learn, expect, afford, fail

- We **decided to migrate** to microservices.
- I **managed to fix** it before the demo.
- The team **agreed to adopt** the new standard.
- She **offered to mentor** the juniors.

### After prepositions → always GERUND

- I'm interested **in learning** Kubernetes.
- He's good **at solving** tricky bugs.
- Thanks **for reviewing** my PR.

> ❌ "I look forward to **meet** you." (after "to" here, which is a preposition!)
> ✅ "I look forward **to meeting** you." — "look forward to" mein "to" preposition hai, isliye -ing.

### Verbs that take BOTH — with a meaning change

| Verb | + gerund | + infinitive |
|------|----------|--------------|
| **stop** | stop doing (band karna) — *I stopped coding* (coding rok di) | stop to do (rukna taaki) — *I stopped to code* (rukke code kiya) |
| **remember** | remember doing (yaad hai kiya) | remember to do (yaad rakhna karna) |
| **try** | try doing (experiment) | try to do (koshish) |
| **forget** | forget doing (bhulna kiya) | forget to do (karna bhul jaana) |

- "**Remember to deploy** the hotfix." (yaad se deploy karo)
- "I **remember deploying** it last night." (mujhe yaad hai maine deploy kiya)

---

## 5. 🌫️ Subjunctive — "I wish / If only / I'd rather"

Yeh structures *unreal* ya *desired* situations ke liye hain. Inhe sahi bolna aapko polished aur fluent dikhata hai.

### I wish / If only

| Pattern | Meaning | Example |
|---------|---------|---------|
| wish + **past simple** | present ke baare mein regret | I **wish I had** more time. (abhi time nahi hai) |
| wish + **past perfect** | past ke baare mein regret | I **wish I had reviewed** the code. (review nahi kiya tha) |
| wish + **would** | irritation / change chahiye | I **wish** the build **would** stop failing. |

- **If only** I **had known** about the deadline! (kaash mujhe pata hota)
- I **wish I were** more confident in meetings. ("were", not "was" — subjunctive)

### I'd rather (= I would prefer)

| Pattern | Example |
|---------|---------|
| I'd rather + base verb | I'**d rather work** from home today. |
| I'd rather + **someone + past** | I'**d rather you didn't** push to main directly. |

> ❌ "I'd rather to work from home."
> ✅ "I'd rather **work** from home." (no "to" after "would rather").

### Suggest / recommend / insist + that + base verb (formal subjunctive)

- I recommend **that the team adopt** (not "adopts") code reviews.
- The manager insisted **that he be** present in the meeting.

---

## 6. 📦 Advanced Articles & Determiners — edge cases

Articles (a/an/the) Indian speakers ke liye lifelong battle hai (Hindi mein articles hote hi nahi). Yahan kuch tricky cases.

| Rule | ❌ Wrong | ✅ Right |
|------|---------|---------|
| Uncountable nouns → no "a" | I need **an** information. | I need **some information** / a piece of information. |
| General plural → no "the" | **The** developers are creative. (in general) | **Developers** are creative. |
| Specific → use "the" | We hired developers for **a** project. | We hired developers for **the** project (specific one). |
| Job title after "as" | He works as **the** developer. | He works as **a** developer. |
| Institutions (general purpose) | I go to **the** office daily. | I go to **the office** (specific) / **to work** (general). |
| Unique things | Sun rises in east. | **The** sun rises in **the** east. |

Common uncountables jo Indians galti se plural/countable bana dete hain:
**information, equipment, software, feedback, advice, research, work, progress, knowledge, staff, furniture, traffic.**

> ❌ "Please give me feedbacks / informations / advices."
> ✅ "Please give me **feedback / information / advice**." (ye plural nahi hote!)

**"a few / few" aur "a little / little":**

| Word | Meaning | Example |
|------|---------|---------|
| a few | thode (positive) | We have **a few** options. (kuch hai) |
| few | bahut kam (negative) | **Few** people understand this. (lagbhag koi nahi) |
| a little | thoda (positive) | I have **a little** time. |
| little | bahut kam (negative) | There is **little** hope. |

---

## 🎤 Practice (zor se bolo)

Inhe **zor se, clearly** bolo. Pehle padho, phir bina dekhe repeat karo. Tense par dhyaan do.

1. "If the tests pass, we **will deploy** to production this evening." *(first conditional)*
2. "If I **were** the architect, I **would split** this monolith into services." *(second conditional)*
3. "If we **had set up** alerts, we **would have caught** the outage in minutes." *(third conditional)*
4. "The migration **was completed** overnight and the data **was validated** automatically." *(passive)*
5. "He **told me** that the API **was** down, and she **said** the team **was** working on it." *(reported + say/tell)*
6. "I **enjoy debugging**, but I **decided to delegate** the boring parts." *(gerund + infinitive)*
7. "Please **remember to deploy** the hotfix — I **remember deploying** the wrong branch last time." *(meaning change)*
8. "I **wish I had** more time to refactor, and **if only** I **had documented** this earlier." *(wish + subjunctive)*
9. "I'**d rather you didn't** push directly to main; let's use a feature branch instead." *(I'd rather)*
10. "I need **some information** and a little more **feedback** before I commit." *(uncountable nouns)*
11. "She asked **whether** the deployment **was** finished and where the logs **were** stored." *(reported question)*
12. "We **recommend that every PR be reviewed** by at least one senior engineer." *(formal subjunctive)*

**Mini speaking task (60 seconds):**
Apne ek real project ke baare mein bolo aur in 3 structures ko zaroor use karo:
(a) ek **third conditional** ("If we had ___, we would have ___"),
(b) ek **passive sentence** ("___ was deployed / was built ___"), aur
(c) ek **I wish** sentence ("I wish I had ___").
Record karke suno — tense backshift aur "if-clause mein will nahi" rule check karo.

---

← [README](../README.md)
