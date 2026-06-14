# L20 — Building Healthcare AI Apps with FastAPI and Structured Prompts

> **Week 1 · Day 4** · ⏱️ ~8 min

---

## 🎯 TL;DR

Lab time: healthcare consultation assistant build karte hain. Frontend dependencies install (`react-datepicker`), FastAPI backend ko ek bada **system prompt** + **Pydantic `Visit` model** ke saath rewrite (GET → POST endpoint), aur frontend pages (`app.tsx`, `_document.tsx`, `product.tsx`) update — date picker, form fields, streaming. Ek step baaki.

---

## 🗣️ Hinglish Explanation

### Setup: guides aur preview

Cursor mein SaaS project kholte hain, **week one guides** open karte hain (yeh production repo mein bhi milenge), aur **Day 4 ki preview** dekhte hain. Hum bana rahe hain: **healthcare consultation assistant** jo doctor ke consultation notes ko input le, professional summaries generate kare, actionable next steps banaye, aur patient-friendly emails draft kare.

### Step 1: Frontend dependencies install karo

Naye frontend packages chahiye. Terminal kholo (`Ctrl + backtick`) aur ek-ek karke install karo:

```bash
npm install react-datepicker
npm install --save-dev @types/react-datepicker
```

- **`react-datepicker`** — ek off-the-shelf React component jo calendar/date-picker UI deta hai.
- **`@types/react-datepicker`** — iske TypeScript **type definitions** (`--save-dev` because yeh sirf development/compile-time pe chahiye, runtime pe nahi). TypeScript projects mein har JS library ke types chahiye hote hain warna compiler complain karta hai.

Ed ka point: **pre-React zamaane** mein ek date picker banana ek chore tha (tons of manual JavaScript). Aaj `npm install` karke ek component drop kar do — bas. Yeh React ecosystem ki power dikhata hai.

### Step 2: Backend API rewrite — bada system prompt + Pydantic model

`api/index.py` ko poora replace karte hain. Yeh **pehle wale jaisa hi** hai (still OpenAI, still streaming), par do major changes:

**(a) Bada, structured system prompt:**

```python
SYSTEM_PROMPT = """You are provided with notes written by a doctor from a patient's visit.
Your job is to summarize the visit for the doctor and provide an email reply
with exactly three sections with the headings:

1. Summary for the doctor's records
2. Suggested next steps / actions
3. Draft patient-friendly email reply
"""
```

Yeh prompt LLM ko exact format dictate karta hai — teen named sections, Markdown headings ke saath. Ed honestly bolta hai: **Agentic course wale jaante hain ki ek behtar tareeka hota — structured outputs** (LLM se JSON return karwana ek schema ke hisaab se, phir wo JSON frontend ko bhejna). Par yahan **ek step at a time** — abhi sirf Markdown headings mein response. Tum chaaho toh isse structured outputs mein upgrade kar sakte ho (recommended improvement).

**(b) Pydantic `Visit` model + POST endpoint:**

```python
from pydantic import BaseModel
from fastapi import FastAPI
from fastapi.responses import StreamingResponse

class Visit(BaseModel):
    patient_name: str
    date_of_visit: str
    notes: str

app = FastAPI()

@app.post("/api")
def summarize(visit: Visit, creds = Depends(get_clerk_credentials)):
    user_prompt = f"""
    Patient name: {visit.patient_name}
    Date of visit: {visit.date_of_visit}
    Notes: {visit.notes}
    """
    # ... OpenAI call with SYSTEM_PROMPT + user_prompt, stream back
    return StreamingResponse(...)
```

Yahan ke key concepts:

- **Pydantic `BaseModel`** — `Visit` ek Pydantic class hai (`from pydantic import BaseModel`). Pydantic ek Python object ka **schema** describe karta hai: kaun se fields, kaun se types. Yeh ek dictionary jaisa hai **par real typed attributes** ke saath. Yahan teen fields: `patient_name`, `date_of_visit`, `notes`.
- **GET → POST**: Pehle endpoint GET tha; ab **POST** hai kyunki hum body mein data (visit object) bhej rahe hain. (GET requests body nahi rakhte conventionally; jab client structured data submit karta hai toh POST use hota hai.)
- **FastAPI ka magic**: jab tum endpoint signature mein `visit: Visit` likhte ho, FastAPI **automatically**:
  1. Sahi route build karta hai.
  2. Incoming POST body ko ek JSON object ke roop mein expect karta hai.
  3. Us JSON ko parse karke **automatically `Visit` object populate** kar deta hai (validation + type coercion ke saath).
  
  Tumhe `request.json()` se manually values nikalne nahi padte. Yahi wajah hai log FastAPI ko itna pasand karte hain.
- **`creds`** — pichle se jo Clerk credentials argument tha wo bhi yahan hai (auth ke liye). To `visit` (first arg) + `creds` dono FastAPI handle karta hai.
- Phir `user_prompt` mein visit ki saari details (`patient_name`, `date_of_visit`, `notes`) bhar ke, `SYSTEM_PROMPT` + `user_prompt` **GPT-5 nano** ko bhejte hain aur **stream back** karte hain — exactly jaise pehle. Aur kuch nahi badla.

### Step 3: Frontend files update — `app.tsx`

`pages/app.tsx` (ya `_app.tsx`) update karte hain. Sirf ek **import** add hua:

```tsx
import "react-datepicker/dist/react-datepicker.css";
import DatePicker from "react-datepicker";
```

Yeh date-picker CSS aur component import karta hai. Ed ka observation dohraata hai — itni aasani se off-the-shelf React component (calendar) add ho gaya. Pre-React era mein yeh bahut JavaScript ka kaam tha.

### Step 4: `_document.tsx` — title aur heading

`pages/_document.tsx` ko paste karke page title aur heading badalte hain:

- Title/heading → **"AI-powered medical consultation summaries"** / **"Healthcare consultation assistant"**.

(`_document.tsx` Next.js ka special file hai jo HTML document ki `<html>`/`<head>`/`<body>` structure define karta hai — yahan page-level metadata set hota hai.)

### Step 5: `product.tsx` — asli meat of frontend changes

`pages/product.tsx` ko naye product se replace karte hain. Yeh kaafi bada hai — frontend code unwieldy lag sakta hai, par **zyaadatar boilerplate** hai. Ed kuch cheezein highlight karta hai (baaki khud explore karna):

- **React state** — frontend variables jinpar UI depend karta hai. State change hote hi React **automatically relevant UI parts refresh** karta hai. Yahan teen state vars: `patientName`, `visitDate`, `notes`.
  ```tsx
  const [patientName, setPatientName] = useState("");
  const [visitDate, setVisitDate] = useState(new Date());
  const [notes, setNotes] = useState("");
  ```
- **Streaming handling** — pehle ki tarah hi, response ko stream karke progressively dikhana.
- **Forms** — patient name input, date-of-visit picker, consultation notes textarea. React components bahut readable hote hain:
  ```tsx
  <textarea name="notes" required rows={8} ... />
  ```
  (text area, name `notes`, required, 8 rows.)
- **DatePicker** — off-the-shelf component, bas declare karo aur usse needed info do:
  ```tsx
  <DatePicker selected={visitDate} onChange={(d) => setVisitDate(d)} />
  ```
- **Main render** — title, heading, aur Clerk `<PricingTable />` **fallback** (agar signed-in nahi) vs **form** (agar signed-in). Yeh wahi `<Protect>` pattern hai jo L18 mein dekha tha.

Bas — frontend code updated. **Ek step baaki** (next lecture: landing page + requirements.txt fix + deploy).

---

## 📋 Key Concepts

| Concept | Matlab |
|---|---|
| **`react-datepicker`** | Off-the-shelf React calendar component; `npm install` se drop-in date picker |
| **`@types/...` (`--save-dev`)** | TypeScript type definitions for a JS library — compile-time only dependency |
| **System prompt** | LLM ko exact output format dictate karta hai — yahan 3 named Markdown sections |
| **Structured outputs** | Better approach (LLM → JSON via schema); abhi skip, future improvement |
| **Pydantic `BaseModel`** | Python object ka typed schema — fields + types; dictionary jaisa par real attributes |
| **`Visit` model** | `patient_name`, `date_of_visit`, `notes` — request body ka shape |
| **GET → POST** | Structured data body bhejne ke liye POST endpoint chahiye |
| **FastAPI auto-parsing** | `visit: Visit` likho → FastAPI khud JSON parse + validate + object populate kare |
| **React state (`useState`)** | UI-driving variables; change hote hi React relevant UI refresh karta hai |
| **`_document.tsx`** | Next.js special file — HTML document structure + page metadata |

---

## 💼 Backend Dev Ke Liye Note

Yeh lecture ka backend core tumhare bilkul comfort zone mein hai: **Pydantic + FastAPI request modeling**. `class Visit(BaseModel)` likh ke endpoint signature mein `visit: Visit` daal dena — yeh FastAPI ka killer feature hai jo manual `request.json()` parsing, type-checking, aur validation eliminate kar deta hai (Pydantic invalid input par automatically 422 return karta hai). GET → POST switch bhi sahi REST semantics hai: body-carrying data POST/PUT mein jaata hai, GET idempotent + cacheable read ke liye. Ek production-grade note jo Ed deliberately defer karta hai: **structured outputs**. Markdown headings parse karna fragile hai (LLM heading text drift kar sakta hai); production mein tum LLM ko ek Pydantic `response_format` schema do taaki wo guaranteed-valid JSON return kare jise tum directly `Summary(**data)` mein load kar sako — no string parsing, no surprises. Yeh exactly wahi reliability concern hai jo backend devs ko LLM integrations mein sabse pehle hit karta hai. Baaki sab (streaming response, auth creds dependency) standard FastAPI patterns hain.

---

## ✅ Takeaway

- `npm install react-datepicker` + `@types/react-datepicker` — TypeScript projects mein har JS lib ke types chahiye (`--save-dev`)
- Backend rewrite ka core: **bada system prompt** (3 fixed sections) + **Pydantic `Visit` model** + **POST endpoint**
- **FastAPI magic**: `visit: Visit` signature → automatic JSON parse + validate + object populate; no manual extraction
- Ed openly bolta hai **structured outputs** behtar hote (JSON schema), par "one step at a time" — future improvement
- Frontend mostly boilerplate: React `useState` (patient name, date, notes), streaming, forms, date picker, `<Protect>` fallback pattern

---

<details>
<summary>📜 Full Transcript (English)</summary>

And welcome back to cursor. And here we are in the Sass project I open up the week one guides. These will be in the production repo as well. And I'm going to open the preview on day four. So we get to see what we're doing here. We're building a healthcare consultation assistant. As I told you, it's going to take the doctor's consultation notes as input, generate professional summaries, create actionable next steps, uh, draft patient friendly emails. All right. So let's start then with step one. We've got some new front end dependencies to install and we use npm install for that. Let me take this first one here I'll copy that. I'm going to bring up a new terminal. Here it is. And now I'm going to paste that in. There it goes and it installs. And now we'll do the second one here which is the associated types. And I paste that there. And I run and that installs two okay. Now let's hide the terminal. It's time for us to update the backend API. So basically it's the same backend API. Except now we're going to have some more detailed prompting. So let me copy this and paste it in and then we'll talk it through. There it is. Okay. So over we go to the API. And this is something which is going to replace the the index dot pi which is right here. So I select all and I paste. And let me quickly explain this to you. So it's it's very similar to before. We're still using OpenAI. Uh and the main difference here is that we have a bigger system prompt. You're provided with notes written by a doctor from a patient's visit. Your job is to summarize the visit for the doctor and provide an email reply with exactly three sections with the headings. And here are the three sections. Now, uh, the people from, say the, the uh, my agent of course, will know well that a nicer way of doing this will be to have it reply with structured outputs, and then take that JSON and return it to the front end. But I want to take things a step at a time. If you if you want to update this to use structured outputs and to respond with JSON, that would be a much better implementation and I would encourage you to do so. But for now we're just going to have it respond in markdown with these headings. Um, and uh, so then otherwise things are very similar. We've changed it from being a get to being a post endpoint. So this is now a post to API. Uh, and uh, also that we've got in addition to the, the creds that we had before, which is the credentials coming from Clark, we have another argument here, visit which is an object of type visit and visit. Here is a pedantic object. That means that it is a subclass of base model. Pedantic base model. Just got to the top. Show you. There we go. There's. It's imported from pedantic import base model. And that means that this is one of these pedantic classes that's used to describe the schema of a Python object. Its purpose is to describe what a Python object which fields it should have. It's similar to a dictionary, except you're using real attributes that have a type. So we've got, in this case a patient name, a date of visit, and notes as the three bits of information here that form this visit object. And we've got that here as the first argument for this endpoint. And the magic of fast API is that when you do it this way, fast API just builds the right route and expects the right JSON object to be provided in this post, and it will automatically populate this Pydantic object. Visit with all of the right fields, so you don't need to worry about how this JSON object comes in the request, and how to pluck out the values and put them into a Python object. Fast API handles all of that for you, and that's why people love it. Okay, so with that out we can just use visit in our code. This user prompt for populates the the information um and the the patient's name date of visit and their notes. And that is what we will send to uh, to to GPT five nano. The system prompt that we wrote above the user prompt, which has got all these details that were passed in in the visit object, and then we stream back results exactly as we did before. Nothing else has changed. Okay. And now we're on to changing the front end. First of all, before we change the the actual pages themselves, we're going to update those two front end files and documents to to reflect some of the changes here. So start with app TSX. Let's go to find app TSX and pages. There it is. And replace here. And all we've done is added in this import. We're importing something called React Date picker which is something that we just npm installed which is going to give us a date picker, a calendar. And it just this is a great example of how easy it is to get off the shelf react components to add something like a date picker to your web page. In the days before react, it would be a chore to have a date picker. There would be a lot of JavaScript involved in that. And now it's it's it's just so easy. All right. Back here again. And now we're going to go to the document TSX. And we're going to use that change the page title and heading. Here's document dot TSX. Let's paste. There we go. AI powered medical consultation summaries. Healthcare consultation assistant. Okay. And now back to the instructions. And now the meat of the front end changes. We're going to update the products with our new product. And I will take all of this. And now there's a fair bit more uh, front end code can look quite unwieldy sometimes. There's a, there's a there's a lot to it. Uh, but much of this is boilerplate. Go over to product TSX and replace everything with our new product. Let's just take a look at a few things, but this is an exercise for you to look through it. So there's this idea of of of state which are the variables which are front end. Depends on that. React will automatically refresh the relevant parts of the UI as state changes. And we've got a patient name, a visit date and notes. Um, and then we've got stuff to do with the streaming, which as much as we had it before, uh, and, uh, this is how we're handling the streaming back. And then this is where we have these forms for the patient name, the date of visit, the consultation notes. You can see this is you can see how how very easy to read these react components are. It's a text area. It's called notes. It's required. It's got eight rows. Um, and uh, it's got, got all of the information here. I also want to show you the date picker. The date picker. This is the react component that we've taken off the shelf for picking dates. And you just say you want a date picker and you, you give it the, the information that you need. Um, okay. And, and this is the, the, the main part of it, this is where it has the title, the heading, the pricing table as this is sorry, this is the fallback if we're not, uh, signed in and this is the form if we are. Okay. So that is the front end code updated. We're closing in. We've got one step to go.

</details>
