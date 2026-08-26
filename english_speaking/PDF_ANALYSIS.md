# 📚 PDF Analysis — Word Power Made Easy + English Grammar in Use

> Dono PDFs ka detailed analysis, aur unse banaya gaya daily-practice workbook.
> Output file: **[English_Daily_Practice.xlsx](English_Daily_Practice.xlsx)**

---

## 1. Kya-kya mila dono PDFs mein

### 📕 PDF 1 — *Word Power Made Easy* (Norman Lewis, Anchor/Doubleday, 848 pages)

Ye vocabulary ki book hai, par **dictionary nahi** — iska tareeka alag hai.

| Cheez | Detail |
|-------|--------|
| Structure | 19 chapters → **47 numbered "Sessions"** (ek session = ek baithak ka kaam) |
| Sessions with word lists | 43 (baaki 4 test chapters hain: Session 18, 38, 47 + etymology answers) |
| **Teaching words** | **966 unique headwords** (phonetic respelling ke saath) |
| Words per session | avg 22.5 (min 7, max 68) |
| **Roots/prefixes/suffixes** | **295** (`REVIEW OF ETYMOLOGY` tables se) |
| Exercise types | 6 per session: pronounce → match → yes/no → recall → etymology review → chapter review |
| Tests | 3 comprehensive tests × 120 items each |
| Extras | 10 "Brief Intermissions" — grammar, usage, spelling |

**Book ka core idea:** word ko ratna mat, uska **root** pakdo. Ek baar `mis-` (hate) + `anthropos` (man) samajh gaye, to *misanthrope*, *misogynist*, *misogamist*, *misology* — sab ek saath khul jaate hain. Isiliye workbook mein alag **Word Roots** sheet banayi hai.

**Themes (966 words kaise bante hain):**

| Words | Theme |
|------:|-------|
| 170 | Insults & criticism |
| 115 | Flattery & praise |
| 101 | Actions & verbs |
| 86 | Speech habits |
| 78 | Common phenomena |
| 76 | Science & scientists |
| 73 | Liars & lying |
| 69 | Practitioners & professions |
| 65 | Doctors & medical specialists |
| 62 | Personality types |
| 42 | What goes on (verbs) |
| 29 | Personal characteristics |

**⚠️ Iski sabse badi kami — aur ye tumhare liye important hai:**

Book 1949 ki hai (1978 revision). Ye **reading/exam vocabulary** ki book hai, **speaking** ki nahi. `misogamist`, `consummacy`, `laconicity`, `exurbanite` jaise words tum kabhi office mein nahi bologe — bologe to ajeeb lagega.

Isliye workbook ki har row mein maine **`Level`** column daala hai:
- **`core`** → ye bolo. Office aur daily life mein sach mein kaam aata hai.
- **`good`** → samajhna zaroori, bolna optional.
- **`rare`** → sirf pehchano. Bolne mein force mat karo.

Aur har word ka **`Kab bolna hai`** column hai jo seedha bolta hai ki word bolne layak hai ya nahi. Example:
> *consummacy* → "Almost never used — say 'consummate skill' or 'mastery' when you speak."

Ye honest filter book khud nahi deti. 966 words ko blindly ratoge to time waste hoga.

---

### 📘 PDF 2 — *English Grammar in Use* (Raymond Murphy, Cambridge, 5th ed., 392 pages)

Ye actually **grammar** ki book hai (file ka naam `MUCLecture_2022_5217521.pdf` hai par andar Murphy hai). Intermediate level. Self-study ke liye banayi gayi.

| Cheez | Detail |
|-------|--------|
| **Units** | **145** — har unit ek grammar point |
| Layout | Left page = explanation, right page = exercises |
| Grouping | Tenses (1–25), Modals (26–37), if/wish (38–41), Passive (42–46), Reported speech (47–48), Questions (49–52), -ing/to (53–68), Articles & nouns (69–81), Pronouns (82–91), Relative clauses (92–97), Adjectives/adverbs (98–112), Conjunctions (113–120), Prepositions (121–136), Phrasal verbs (137–145) |
| Appendices | 7 — irregular verbs, tense summary, future, modals, short forms, spelling, American English |
| Extras | Additional exercises (302–325), Study guide (326), full answer key |
| **Irregular verbs** | **116** (Appendix 1.4) — V1/V2/V3 |

**Iski taakat:** har point chhota, self-contained, aur exercise ke saath. Answer key bhi hai, to bina teacher ke chal jaata hai.

**Iski kami tumhare case mein:** ye **grammar samajhne** ki book hai, **bolne** ki nahi. Explanations padh ke rule samajh aayega, par mooh se nikalega nahi. Aur ye British book hai — Indian speakers ki specific galtiyan (*"I am working here since 2021"*, *"discuss about"*, *"revert back"*) ye address nahi karti, kyunki wo iska audience nahi hai.

Isliye workbook mein har unit ko **speaking model** mein convert kiya hai:
- **FORMULA** — pattern jo ratt sakte ho
- **Kab use karo** — ek line
- **Hinglish** — turant click hone ke liye
- **Indian-English galti** — `WRONG: ... → RIGHT: ...`
- **6 sentences** — 2 daily life, 2 office, 1 interview, 1 question/negative
- **Bolne ka drill** — us pattern ko zor se practice karne ka tareeka

---

## 2. Extraction mein kya problem aayi (aur kaise theek ki)

Dono PDFs ka text nikaalte waqt ek real bug mila — **PDF ne `fi` / `fl` ligatures drop kar diye the**. Matlab:

| PDF mein aaya | Asli word |
|---------------|-----------|
| `male cent` | **maleficent** |
| `bene ciary` | **beneficiary** |
| `bona de` | **bona fide** |
| `sopori c` | **soporific** |
| `a uent` | **affluent** |
| `persi age` | **persiflage** |
| `in delity` | **infidelity** |
| `in ammation` | **inflammation** |

Agar ye pakda nahi jaata to workbook mein 15 words galat spelling ke saath chale jaate. Maine poori 966-word list ko system dictionary (235,976 words) ke against verify kiya, har suspect word mein dropped ligature wapas insert kar ke test kiya, aur 15 corrupted headwords theek karke unki entries **dobara generate** karayi.

Isi tarah roots ke meanings mein bhi ye damage tha (`in ammation`), wo bhi repair kiya gaya.

---

## 3. Dono books ka gap — jo workbook mein bhara gaya

| Gap | Kis book mein nahi tha | Workbook mein kya kiya |
|-----|------------------------|------------------------|
| Hindi/Hinglish meaning | Dono mein nahi | Har row mein `Matlab (Hinglish)` column |
| Kaunsa word bolne layak hai | Lewis nahi batata | `Level` (core/good/rare) + `Kab bolna hai` |
| Indian-English galtiyan | Murphy address nahi karta | Har grammar model mein `WRONG → RIGHT` |
| Ready-to-speak sentences | Dono mein nahi | Alag **Speaking Sentences** sheet — standup, meeting, interview, phone, daily life |
| Roz kya padhna hai | Dono mein nahi | **Daily Plan** sheet — 97 din ka schedule |
| Revision system | Dono mein nahi | **Revision Tracker** — spaced repetition (next day → +3 din → +1 week → +1 month) |
| Office/tech context | Dono mein general English | Har word aur pattern ke examples mein software-work context |

---

## 4. Ek honest baat

Ye dono books **padhne** ke liye banayi gayi hain — aur tumhara problem padhna nahi, **bolna** hai.

- Lewis ki book se 966 words ratt loge par bologe nahi, to koi fayda nahi.
- Murphy ki 145 units samajh loge par mooh se nahi nikla, to koi fayda nahi.

Workbook isiliye aisa banaya hai ki har row ka ek hi maqsad hai — **awaaz mein bolna**. Har vocabulary word ke 2 sentences hain bolne ke liye. Har grammar model ke 6. Speaking sheet poori ki poori bolne ke liye hai.

**Roz 30 minute, zor se.** Sirf padhoge to 3 mahine baad bhi wahi rahoge.

---

## 🔗 Related

- Workbook: [English_Daily_Practice.xlsx](English_Daily_Practice.xlsx)
- Curriculum: [README.md](README.md)
- Daily routine: [practice/daily_routine.md](practice/daily_routine.md)
- Interview English: [03_Advanced/06_interview_english.md](03_Advanced/06_interview_english.md)

---

### Note on sources

Workbook ka saara content — meanings, Hinglish, example sentences, formulas, drills — **naya likha gaya hai**. Dono PDFs se sirf ye liya gaya hai ki *kaunse words* aur *kaunse grammar points* padhne hain (yaani syllabus), unki wording nahi. Books ka text copy nahi kiya gaya.
