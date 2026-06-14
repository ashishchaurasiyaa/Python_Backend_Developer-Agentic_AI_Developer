# L64 — Day 5: Building AI Teams — Collaborative Development

> **Week 3 — CrewAI** · ⏱️ ~10m · 🎥 Lecture 64 of 131
> **Instructor:** Ed Donner · **Lecture ID:** 49821233

---

## 🎯 Ek Line Mein (TL;DR)

Week 3 ka **final project** shuru — Day 4 wale single coder ko ek poori **engineering team** mein convert karte hain: **engineering lead** (design), **backend engineer** (code), **frontend engineer** (Gradio UI), aur **test engineer** (unit tests) — har ek alag **LLM** (GPT-4o, Claude 3.7 Sonnet, DeepSeek) use karta hai, aur **1:1 task-agent mapping** ke saath sequential pipeline banti hai.

---

## 📝 Hinglish Explanation (Detailed)

- **Bittersweet moment** — ye CrewAI ke saath **last day** (Day 5 of Week 3) hai. Day 4 ke coder project pe build karke usse ek **full engineering team** banayenge — "end on a high".

- **Team structure** — 4 agents:
  - **Engineering Lead** — chill karta hai (kyunki leads yahi karte hain 😄), high-level **requirements** leta hai aur detailed **design** banata hai
  - **Backend Engineer** — design ko implement karke Python module likhta hai
  - **Frontend Engineer** — backend demonstrate karne ke liye simple **Gradio UI** banata hai
  - **Test Engineer** — sab kuch todne ki koshish karta hai, matlab **unit tests** likhta hai

- **Project setup** — Cursor mein terminal kholo (Ctrl + backtick), third directory mein jao, aur `crewai create crew engineering_team` chalao. Options mein **OpenAI + GPT-4o-mini** select karo, token skip karo — standard **directory structure** ready (`src/config/agents.yaml` etc.).

- **agents.yaml — boilerplate delete karke 4 naye agents:**
  - **engineering_lead**: goal = high-level requirements lekar **detailed design** prepare karna backend developer ke liye. Sab kuch **ek single Python module** mein — function/method **signatures** describe karo, module **completely self-contained** hona chahiye taaki test ho sake ya simple UI ban sake. Yahan **templated inputs** aate hain: `{requirements}`, `{module_name}`, `{class_name}` — project ko thoda **configurable** banane ke liye. Backstory: "seasoned engineering lead with a knack for clear and concise designs".
  - **LLM choice for lead** — `llm:` field mein **GPT-4o** ("the big guy"). GPT-4o-mini se bhi chalta hai, lekin bade cousin se **zyada comprehensive solutions** milte hain. **Proper syntax**: provider prefix ke saath — `openai/gpt-4o` (LiteLLM convention).
  - **backend_engineer**: Python engineer jo engineering lead ke design ko implement karta hai. Requirements **dobara pass** hoti hain (design ke saath), plus module/class name. LLM = **`anthropic/claude-3-7-sonnet-latest`** — kabhi-kabhi Claude se **overload error** aata hai (thoda less stable as of recording), lekin **great coding model** hai, is case ke liye perfect.
  - **frontend_engineer**: actually ek **Gradio expert** — backend demonstrate karne ke liye simple **Gradio UI** likhta hai, **all in one file**, backend module ki **same directory** mein. Iske liye bhi **Claude**.
  - **test_engineer**: Ed kehte hain wo word thoda "abuse" kar rahe hain — ye QA engineer nahi, balki Python coder hai jo backend module ke liye **unit tests** likhta hai. Output file naam: `test_` + module name. LLM = **DeepSeek** (`deepseek-chat`) — "shake it up, take a risk" — DeepSeek bhi terrific code likhta hai.

- **tasks.yaml — har agent ke liye ek task (1:1 mapping):**
  - Ed honestly admit karte hain — ye thoda **repetitive** lagta hai, aur yahan **OpenAI Agents SDK zyada straightforward** feel hota hai kyunki usme task ka **separate first-class object** wala extra **indirection** nahi hai. CrewAI ne ye isliye banaya kyunki wo chahte hain aap un situations ke baare mein socho jahan **ek agent ko multiple tasks ki series** milti hai (jo humne pehle ek example mein dekha bhi tha). Lekin yahan phir se **1:1 mapping** hai.
  - **design_task** (→ engineering_lead): requirements lekar detailed design banao. **IMPORTANT instruction**: design **sirf markdown format** mein output karo — warna model seedha code likhna shuru kar deta hai jo hume nahi chahiye. Output file: `{module_name}_design.md` jaisa — **templated tags output file name mein bhi** kaam karte hain, YAML mein kahin bhi substitute ho jate hain.
  - **code_task** (→ backend_engineer): design implement karke Python module likho. Funny moment — Cursor autocomplete ne "coding_task" suggest kiya lekin Ed ne "code_task" likha tha ("I'd like to be unpredictable"). **CRITICAL instruction**: output **only raw Python code** — **no markdown formatting, no code-block delimiters, no backticks** — kyunki models ko markdown output karna **bahut pasand** hai. Agar ye note nahi dala to file ke top pe ` ```python ` aa jayega aur file **valid Python nahi rahegi**. `context: [design_task]` — design ka output is task ko milega.
  - **Mental model (important!)**: **tasks = user prompts**, **agents = system prompts** — aur `context` batata hai ki dusre tasks ki kya information us prompt mein include hogi. Aise hi sab kuch fit hota hai.
  - **frontend_task** (→ frontend_engineer): `app.py` module mein **Gradio UI** likho jo backend class demonstrate kare. Assume **only one user**, UI **simple aur clean** rakho. Phir se "only raw Python" wali warning. `context: [code_task]` — kyunki UI directly wahi backend use karegi jo code_task ne likha — dekhna interesting hoga ki context itna achha carry hota hai ki ye actually kaam kare.
  - **test_task** (→ test_engineer): backend module ke liye **unit tests** likho, **same directory** mein. Raw Python wali instruction phir se. `context: [code_task]` — tests **UI ko nahi**, code ko test karte hain. Output file: `test_{module_name}.py`.

- **Bottom line** — 4 agents, 4 tasks, 1:1 mapping, multi-LLM mix (OpenAI + Anthropic + DeepSeek via LiteLLM), aur context chaining se ek **sequential engineering pipeline** ban jati hai.

---

## 🔑 Key Concepts / Important Terms

| Term | Simple Hinglish Meaning |
|------|--------------------------|
| **Engineering Team Crew** | 4-agent crew: lead (design) → backend (code) → frontend (Gradio UI) → test (unit tests) |
| **`crewai create crew engineering_team`** | CLI scaffolding command — YAML config + boilerplate project structure generate karta hai |
| **Templated inputs** | `{requirements}`, `{module_name}`, `{class_name}` — YAML mein kahin bhi (output file name tak) substitute hote hain |
| **Multi-LLM mix** | Har agent alag model: `openai/gpt-4o`, `anthropic/claude-3-7-sonnet-latest`, `deepseek/deepseek-chat` — LiteLLM provider-prefix syntax |
| **1:1 task-agent mapping** | Har agent ka exactly ek task — Ed mante hain ki yahan OpenAI Agents SDK ka simpler model better lagta hai |
| **Tasks vs Agents (mental model)** | Tasks ≈ **user prompts**, Agents ≈ **system prompts** |
| **`context:`** | Task dependency — pichhle task ka output is task ke prompt mein inject hota hai (e.g. frontend ko code_task ka code milta hai) |
| **"Raw Python only" instruction** | Models markdown backticks dalna **love** karte hain — explicitly mana nahi karoge to output valid `.py` file nahi banegi |
| **Self-contained module** | Design constraint: ek hi Python module, clear signatures — taaki test aur UI dono easily ban sakein |
| **Gradio** | Simple Python UI framework — frontend agent isse one-file demo UI banata hai |

---

## 💡 Backend Dev Ke Liye Note (aapke liye)

- **"Tasks = user prompts, agents = system prompts"** — ye ek line CrewAI ka poora abstraction demystify kar deti hai. `context:` basically ek **DAG dependency** hai jahan upstream task ka output downstream prompt mein template-inject hota hai — aap ise **Airflow DAG with XCom** ki tarah socho, bas payload prompt text hai.
- **"Output raw Python, no backticks" wala hack** production LLM pipelines mein universal pain hai — structured output chahiye to ya to aise prompt-level guards lagao, ya `output_pydantic` jaisa schema enforcement use karo. Code files ke liye prompt-guard hi practical hai kyunki code ka pydantic schema nahi hota.
- **Multi-LLM mixing via LiteLLM** ek architectural pattern hai — design ke liye strong reasoning model (GPT-4o), coding ke liye Claude/DeepSeek, sab ek hi `provider/model` string se swap. Ye database-per-service polyglot persistence jaisi soch hai: har job ke liye best tool.
- **Hands-on lab**: is lecture ka code khud chalane ke liye `Practical/lab4_engineering_team.py` run karo (is repo me, `uv run` se chalta hai, Groq pe free via LiteLLM). Hamara lab course se thoda alag hai: self-contained code-style hai (YAML scaffolding nahi), aur lecture ke multi-provider mix (OpenAI/Anthropic/DeepSeek) ki jagah sab agents free Groq models pe chalte hain — concepts bilkul same: 4 agents, 1:1 tasks, context chaining, raw-Python output guards.

---

## 🧠 Takeaway (yaad rakho)

1. **Single coder → engineering team**: lead designs, backend codes, frontend builds Gradio UI, test engineer writes unit tests — sequential pipeline with `context:` chaining.
2. **Har agent alag LLM** de sakte ho — LiteLLM syntax `provider/model` (e.g. `openai/gpt-4o`, `anthropic/claude-3-7-sonnet-latest`, `deepseek/deepseek-chat`).
3. **Tasks = user prompts, agents = system prompts** — aur `context:` decide karta hai kis task ka output kis prompt mein jayega.
4. **Code-generating tasks mein "raw output only, no markdown/backticks" instruction zaroori hai** — warna ` ```python ` wrapper file ko invalid bana dega.
5. **Templated tags (`{module_name}` etc.) YAML mein kahin bhi chalte hain** — output file names mein bhi — isse crew reusable/configurable banti hai.

---

<details>
<summary>📜 Full English Transcript (original, click to expand)</summary>

Well, this is a bittersweet moment for sure. It is the final day of our journey with Crew. Fifth day of week three. While we complete the work we've got with Crew, and it's going to be a great one. We're going to end on a high. We are going to build on the project we did last time. On day four, we're going to turn our coder into an engineering team. We're going to have an engineering lead depicted here by this person chilling out because, you know, that's what what leads do. Uh, we're going to have a back end engineer. We're going to have a front end engineer, and we're going to have a test engineer seen here as someone that's jumping on top, trying to trying to destroy, trying to break everything that they are given. So this is going to be our team. We're going to really use the crew and CrewAI. Let's get to it.

And welcome back to Cursor. Welcome to our final project for Crew. Let's bring up a terminal with control and the back tick. Let's go into that third directory. And now, of course, it is time to do crewai create crew and it is engineering underscore team is the name of our project. Let's do it. Let's choose the options that it tells us. We want OpenAI. We want GPT-4o mini. And then we skip making a token. And then there we have our directory structure. And now of course we go into engineering team. We go into source, we go into config and we open our agents YAML file. As usual we see the boilerplate ones there the researcher and the reporting analyst.

So what are we going to do. Well we're going to first of all delete what we have here. And we're going to put in our first agent. And our first agent is going to be an engineering lead, the engineering lead for the engineering team directing the work of the engineers. Take the high level requirements described here and prepare a detailed design for the back end developer. Everything should be in one Python module. Describe the function the method signatures in the module. The Python module must be completely self-contained and ready so that it can be tested or have a simple UI built. Here are the requirements. So this is going to be one of our input attributes that we can pass in. The module should be named module name. And the class should be named class name. So we are going to bring in those as well. So we're going to have this be a little bit configurable. And the backstory you're a seasoned engineering lead with a knack for writing clear and concise designs okay there we go.

So so look, I'm going to put on an LLM now and let's have something different to usual. I think we're going to go with GPT-4o. We're going to have the big guy. I've also run this with GPT-4o mini and it runs just fine. So you can do that too if you wish. And you get, you know, you get a bit more comprehensive, extensive solutions if you use its bigger cousin GPT-4o. Okay. And whilst that will work, of course the full way to do it is to show this is openai slash like that with the provider. That is the first of our agents.

Okay. So the next agent is going to be called a backend engineer. So the backend engineer is going to be a Python engineer who can write code to achieve the design described by the engineering lead. So the engineering lead will do the design will lay out the sort of foundations, and the back end engineer will do the coding write Python module that implements the design described by the engineering lead, but will also pass in the requirements again. So it's going to get the requirements along with the design and the module name and class name again. And it's given a decent backstory saying that it's a Python engineer with a knack for writing clean, efficient code. Follow the design instructions carefully. So again, we'll use a different model. We'll mix things up, and this time I suggest we use Claude 3.7 Sonnet latest. Now sometimes we get an overload error from Claude? At least I do. As of now. So it's a little bit less stable, but nonetheless, it's a great coding model. Particularly so. I think it's a good one to use in this case.

All right. Let's also add a front end engineer. And I say front end engineer. But it's going to be a Gradio engineer a Gradio expert who can write a simple front end to demonstrate a back end writer Gradio UI that demonstrates the given back end all in one file to be in the same directory as the back end module, giving the requirements. Giving the back story. A seasoned engineer highly skilled at writing simple Gradio UIs for a back end class. So there we have it. We, uh, explained that the UI needs to be in one module, and we'll use again Claude for this too.

Okay. And one more agent. Our final agent is going to be a test engineer, but I'm slightly abusing the word there. It's not. It's not like a QA engineer. This is going to be a Python coder who knows how to write unit tests for a given backend module, because I want to see unit tests being built out here. So that's what the test engineer is going to do. They're going to create a test which is going to be called test underscore. And the name of the module which will be the backend module. And they're a seasoned QA engineer and software developer who writes great unit tests for Python. Code is the backstory. And you know, for for all of the coding part, we'll use Anthropic. Maybe we should shake it up. Why don't we? Why don't we take a risk? We'll use DeepSeek instead. I'm just going to stick with deepseek chat because deepseek chat is has is also able to write terrific code as well. So we'll we'll stick with that model and that will be our test engineer.

Now it's time for us to go on to the tasks. So look it's a bit repetitive. We're going to have a task for each agent. And it's funny. This is one of those times when it feels like OpenAI's Agents SDK is sort of more straightforward that they don't have this extra indirection, this idea of a task being a separate first class object, because there's a lot of times that you will have this 1 to 1 mapping between a task and an agent. Obviously, Crew has built this up because they really want you to think in terms of situations where you will have series of tasks that will be given to the same agent. And we did see that and at least one of our examples. But in this case, we are again going to have the case that there's going to be a task for each of our agents, and it gives us an opportunity to spell out very clearly what's required.

So the description of the task is to take the high level requirements described and prepare a detailed design for the engineer. This is the design task that, of course, is going to be assigned to our engineering lead. And the output is a detailed design for the engineer. You'll notice that I make it important that it should only output the design in markdown format. Otherwise it just wants to start writing the code, which is not exactly what we want. And here we specify the the output as the module name underscore design. And it's worth noting that you can have these templated tags in the output file name as well. You can have it anywhere in this YAML, and it will get substituted in for the actual name of the the module that we're building here. So that is the design task.

My next one Cursor wants it to be called coding task. But when I wrote it I wrote code task. There we go. Uh, I'd like to be unpredictable. Uh, so the description is write a Python module that implements the design as described by the engineering lead in order to achieve the requirements. And then here I'm saying important output only the Python code without any markdown formatting or code block delimiters or backticks. And that's important because these models love to output markdown. And if you don't put that note in there, it's going to put that tick, tick, tick python at the top of the file, which means it won't be a valid Python file. And it just loves doing that. So unless you really highlight this is important, it's going to do it. And so that is the task. And we're saying context design task, which you remember is going to make sure that that information is made available to it. And generally speaking you can think of the tasks as being the user prompts and the agents as defining the system prompts, and that that's kind of how it all comes together. And this context is showing us what kind of information is going to be included in that prompt from others. Okay. So that is the code task.

How about the front end task. So this is where the plot thickens. The front end has got to write a Gradio UI in a module app.py that demonstrates the given back end class. Assume there's only one user and keep the UI simple and keep the UI clean. So, um, important. Only output the raw Python code again. The agent is the front end engineer agent, obviously. And of course, for its context, it needs to get the output from the code task because it's going to write a user interface, which is going to directly use what the code task has written. So that's going to be very interesting to see how how it's able to keep that context so well that it's actually able to do this.

And then Cursor is correct that the last one is indeed called test task, but it's got a little bit more detail than Cursor was suggesting. Write unit tests for the given back end module and create a test in the same directory. And this is. Got more information one more time about outputting raw Python without clever tags. And of course it also depends on the code task. The unit tests are not going to test the user interface, it's going to test the code. And that will be the output file. And that is it for our tasks our 1 to 1 again between the task and the agent.

</details>

---
*Source: Official Udemy lecture transcript (auto-captions, lightly cleaned). Notes in Hinglish for self-study.*
