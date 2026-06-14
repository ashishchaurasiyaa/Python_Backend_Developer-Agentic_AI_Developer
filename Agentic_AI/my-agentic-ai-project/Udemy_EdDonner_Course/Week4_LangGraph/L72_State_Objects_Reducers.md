# L72 — Day 2: Define State Objects & Use Reducers

> **Week 4 — LangGraph** · ⏱️ ~7m · 🎥 Lecture 72 of 131
> **Instructor:** Ed Donner · **Lecture ID:** 49821333

---

## 🎯 Ek Line Mein (TL;DR)

LangGraph ka **Step 1 = State object define karna** — ek Pydantic class jisme fields ko Python ke **`Annotated`** type hint se tag karte hain, aur usi annotation me **reducer** (jaise built-in **`add_messages`**) specify karte hain jo batata hai ki naya state purane state ke saath **kaise combine** hoga; phir **Step 2 = `StateGraph(State)`** se graph builder start karna (class pass hoti hai, instance nahi).

---

## 📝 Hinglish Explanation (Detailed)

- **Welcome back to Cursor + notebooks** — Week 4 LangGraph ki **Lab 1** shuru. Ed kehte hain notebooks ki popularity mixed hai, par is week notebooks + code dono use honge.
- Shuruaat **imports** se, kuch **constants** bhi hain (abhi ignore karo, "silly" hain, baad me use honge), aur hamara favourite **`load_dotenv()`** wapas aa gaya hai.
  - **Interesting point:** Crew week me `load_dotenv()` nahi chalaya tha — kyunki **CrewAI khud `.env` file automatically load** kar leta hai. LangGraph me hume khud karna padta hai.
- **Type hints recap** — `shout` function ka example:
  - `def shout(text: str) -> str:` — yahan `: str` batata hai ki `text` ek **string** hai, aur `-> str` batata hai return type string hai (ya `None` agar kuch return nahi).
  - Agar return type `str` declare kiya hai to `text.upper()` **return** bhi karna padega, warna type checker unhappy. Ye Python ka **optional feature** hai jo engineering me commonly use hota hai.
- **`Annotated` kya hai?** — type hint ke upar **extra metadata** lagane ka tarika:
  - `Annotated[str, "something to be shouted"]` — square brackets me pehle **actual type**, phir koi bhi **extra info/message**.
  - **Python khud is extra info ka koi use nahi karta** — completely ignore karta hai. Ye sirf ek **FYI tag** hai.
  - Par agar ye function/variable kisi **doosre platform** ko diya jaye, to **wo platform annotation padh sakta hai** — aur yahi cheez LangGraph ke liye matter karti hai.
  - Doosra example: `my_favorite_things: Annotated[list, "a few of my favorite things"]` — variable list hai, annotation bas description hai.
- **Reducers se connection** — ab asli baat:
  - Jab hum **State object define** karte hain, har field ko ek **type** dena hota hai.
  - Type ke saath-saath **`Annotated` use karke reducer specify** karte hain — yahi LangGraph ka official technique hai: *"agar LangGraph se reducer use karwana hai, to `Annotated` se batao"*.
  - **Reducer = wo function jo ek state ko doosre state ke saath combine karta hai** (node ka returned partial state + existing state).
- **`add_messages`** — LangGraph ka **out-of-the-box reducer**:
  - Import: `from langgraph.graph.message import add_messages`.
  - Ye ek function hai jise annotation me daal sakte ho — "hey LangGraph, ye reducer use karna".
  - Kaam bilkul **simple/vanilla** hai: assume karta hai field ek **list** hai, aur jab node naye items return karta hai, to unhe **existing list ke saath concatenate** kar deta hai. Bas itna hi — append/merge of lists.
- **Step 1 — State object define karna:**
  - State **koi bhi Python object** ho sakta hai, par sabse common 2 options:
    - **Pydantic object** (subclass of `BaseModel`) — jo pichle 2 weeks se familiar hai.
    - **TypedDict** — Python ka special dictionary jisme keys pehle se specify hoti hain.
  - Course me **Pydantic** use karenge (familiarity ki wajah se).
  - Hamara `State` me sirf **ek field**: `messages` — ek **list of messages** jo **graph me ghoomti rahegi** aur time ke saath **build-up hoti jayegi** (messages add hote rahenge).
  - Definition: `messages: Annotated[list, add_messages]` — list type + reducer annotation.
- **Step 2 — Graph builder start karna:**
  - `StateGraph(State)` instantiate karo.
  - **Bahut important subtlety:** hum `State` ka **instance nahi** bana rahe (koi `State(messages=...)` object pass nahi ho raha) — hum **class/type khud pass** kar rahe hain. StateGraph ko bas pata hona chahiye ki state ka **shape kya hai**.
  - Ye **5 steps** (define state → graph builder → nodes/edges → compile → run) ka building phase hai — abhi agentic framework run nahi hua.

---

## 🔑 Key Concepts / Important Terms

| Term | Simple Hinglish Meaning |
|------|--------------------------|
| **Type hints** | Python ka optional feature — `text: str`, `-> str` se variable/return ka type declare karna |
| **`Annotated`** | Type hint + extra metadata: `Annotated[list, kuch_bhi]` — Python ignore karta hai, par frameworks (LangGraph) padh sakte hain |
| **State object** | Graph ka shared data — koi bhi Python object, commonly **Pydantic BaseModel** ya **TypedDict** |
| **Reducer** | Function jo node ke naye (partial) state ko existing state ke saath **combine** karta hai |
| **`add_messages`** | LangGraph ka built-in reducer — naye messages ko existing messages list me **concatenate** kar deta hai |
| **`StateGraph(State)`** | Graph builder start karna — state ki **class** (type) pass hoti hai, instance nahi |
| **TypedDict** | Python dict jisme allowed keys + unke types pehle se defined hote hain |
| **`load_dotenv()`** | `.env` se API keys load — CrewAI ye khud karta tha, LangGraph me manually karna padta hai |

---

## 💡 Backend Dev Ke Liye Note (aapke liye)

- **`Annotated` = Python ka metadata channel** — bilkul waise jaise FastAPI `Annotated[int, Query(gt=0)]` ya `Depends()` use karta hai, ya SQLAlchemy 2.0 `Annotated` column types. Runtime framework `typing.get_type_hints(include_extras=True)` se metadata nikal leta hai — LangGraph bhi yahi karta hai reducer dhoondhne ke liye.
- **Reducer = Redux ka reducer / DB ka conflict-resolution strategy** — node poora state overwrite nahi karta, sirf **delta return** karta hai, aur reducer decide karta hai merge kaise ho (`add_messages` ≈ `UPDATE ... SET messages = messages || new`). Isi wajah se parallel nodes ek hi field pe likh sakte hain bina last-write-wins ke — jaise event sourcing me events append hote hain, snapshot replace nahi hota.
- **Class vs instance pass karna** — `StateGraph(State)` me type pass karna waisa hi hai jaisa FastAPI me response_model ya SQLAlchemy me model class registry ko dena: framework ko **schema** chahiye, data nahi. Data to runtime pe har super-step me flow karega.
- **Hands-on lab:** is lecture ka code khud chalane ke liye `Practical/lab1_langgraph_basics.py` run karo (is repo me, `uv run` se chalta hai, LLM Groq pe free via `langchain-groq` `ChatGroq`).

---

## 🧠 Takeaway (yaad rakho)

1. **State object = Step 1** of LangGraph ke 5 steps — koi bhi Python object chalega, par **Pydantic BaseModel** ya **TypedDict** standard hai.
2. **`Annotated[list, add_messages]`** — pehla part type (Python ke liye), doosra part reducer (LangGraph ke liye); Python annotation ko ignore karta hai.
3. **Reducer ka kaam:** naya state aane par purane se **combine** karna — `add_messages` simply lists ko concatenate karta hai, isliye messages graph me build-up hote jaate hain.
4. **`StateGraph(State)`** me **class pass hoti hai, instance nahi** — builder ko state ka shape chahiye, actual data nahi.
5. LangGraph me **`load_dotenv()` khud chalana padta hai** — CrewAI ye automatically karta tha.

---

<details>
<summary>📜 Full English Transcript (original, click to expand)</summary>

And a warm welcome back to Cursor. And also we are coming now into week four LangGraph and into lab one. And it's not only welcome back to Cursor, it's also welcome back to notebooks. You know I love these things I know the mixed mixed popularity. Uh with with with others. But but hopefully you'll put up with them for a bit. We'll use code as well this week too. Don't worry.

So we're going to start by doing some imports as we get started. And then we also have some constants. Ignore these for now. We'll use them in a bit. They're silly. Uh and we're also going to have our favorite, uh, little thing here. And you may be wondering why we didn't have that during Crew week. It was absent. And the reason is that Crew just does that for you automatically. Crew uses the env file itself, and so you don't need to run it. Okay.

Now I need to explain something called annotated. So hopefully you're somewhat familiar with things called type hints in Python, an optional feature that is often used in engineering. To give you an example, supposing that we have a Python function called shout that takes some text, and the job of shout is to print the text in uppercase. That seems fairly simple. And let's just shout hello like that. Hopefully no surprise. Hello in capitals comes up. Well, uh, the type hints is when you are clear to Python, uh, what is the type of variable that you're using at each point. So you can say that that text is a string by putting colon str. And you can put here that will return a string or it's not returning anything, it's returning none. But if we also have it, uh, if we leave it like this, oops. If we have it be returning a string, then it will be unhappy. But we would need to then also return text upper as well. And then it will run. So these are called type hints. And they are a useful way of specifying what's going on.

There is a feature that you can use called annotated in which we could type annotated. String comma. And then we can put some message here. Uh, something to be shouted. Uh, and this is something I need to close the square brackets. This is just extra information. That's a sort of FYI that's included in here. Uh, Python doesn't make any use of this at all. But if we are going to provide this function to, to, to another platform or in some other context, someone might want to read how we've annotated it, and that might be useful for someone. So annotations can be used for this purpose of kind of tagging variables to have a purpose. So this should run without any change at all. That is completely ignored. Uh, and it's just just a useful way of adding some extra information in case, in case it matters to somebody else and it is going to matter to somebody else. LangGraph is going to want us to annotate, in order to tell it something. Let's come on to that.

So I explain here again, you could have a variable like my favorite things that could be a list. And you could say that my favorite things, you could actually not just describe it as a list, but say that it is annotated. It's a list. And these are a few of mine I added as an annotation to my favorite things. Uh, so why do I tell you this? Well, it all comes back to these things called reducers. We are about to define our state object. And when we do so we're going to give it a few fields. And when we define those fields we have to give them a type. And when we give them a type, we don't just specify the type, but we use annotated to be able to specify a reducer. If LangGraph is expected to use a reducer, that is the technique use annotated to do that. Um, and that that is what we're going to do.

And as it happens, LangGraph comes with with one out of the box that's very useful for us called add messages. Uh, and that is one that I just imported up here. So if you look up here, one of my imports was from langgraph.graph.message import add_messages. So that is it's like a function. And it's a function that you can, you can annotate with. If you want to say, hey this is the reducer I'd like you to use.

So to make this feel real let me just let's go ahead and define our state. So you remember step one in the in the puzzle is to define the state object. That is what we're doing here. We are going to have a state object. Now state objects. You can define them in many ways. They can in fact be any Python object that you want. It's most common to either have it be a Pydantic object that we met in the last week. Uh, it can be. Or we made it the last two weeks. Uh, it can be a Pydantic object, meaning it's a subclass of base model. It can also be something called a typed dict, which is a particular type of, of dictionary in Python where you specify what the keys need to be. Uh, but but it can also be anything but it is quite common to use either Pydantic objects or typed dicts and we will use Pydantic, since that's something that we're familiar with.

So we are going to have a state object defining the state of our system. And it only has one field and that's called messages. And that is going to store in it a list of messages. And these this list of messages is going to be passed around our graph. And over time it's going to build up as messages get added to it. And so we are going to say that it's it's something that's annotated. It is a list. So it consists of a list of things of messages. And we are going to then because we're annotating it, we can provide an annotation that's ignored by Python, but it can be used by LangGraph. And that annotation is where we get to specify the reducer, the function that will be called in order to combine one state with another. And we're going to use one out of the box called add messages. It is a reducer that is used to add messages. And it's very simple. It's very vanilla. All it does is it assumes this is a list. And if you return something with with and items in the list. It just combines it with everything else in the list before it concatenates these lists together. That's all it does. So hopefully that makes a bit of sense. Uh, if not, then you'll see it'll become clear as we use this exactly what's going on. And and why were the use of this and the reducer and how it's working.

So step one we define the state object. Step two we start the graph builder. And that is just a matter of calling this thing called state graph. Instantiating a StateGraph passing in state. And one thing to to get your head around here is that what I'm passing in there. The thing I've just highlighted. It's not an object I'm not instantiating. I'm not I'm not creating a state and passing that in with with messages and so on. Now I'm passing in the class. I'm passing in the type of thing that represents our state. That is what I'm using to create my state graph. And this is beginning the graph building process. This is part of the five steps before we actually run our agentic framework.

</details>

---
*Source: Official Udemy lecture transcript (auto-captions, lightly cleaned). Notes in Hinglish for self-study.*
