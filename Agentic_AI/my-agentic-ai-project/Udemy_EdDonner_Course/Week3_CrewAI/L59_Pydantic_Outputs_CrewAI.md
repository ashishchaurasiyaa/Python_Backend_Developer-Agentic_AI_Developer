# L59 — Day 3: Pydantic Outputs in Crew AI

> **Week 3 — CrewAI** · ⏱️ ~9m · 🎥 Lecture 59 of 131
> **Instructor:** Ed Donner · **Lecture ID:** 49821185

---

## 🎯 Ek Line Mein (TL;DR)

Stock Picker project mein **pydantic BaseModel** classes banakar tasks ko **`output_pydantic`** se bind karte hain taaki har task ka output ek fixed **JSON schema** mein aaye, aur crew ko **`Process.hierarchical`** + ek alag **manager agent** (`allow_delegation=True`) ke saath chalate hain.

---

## 📝 Hinglish Explanation (Detailed)

- Ab cheezein **juicy** ho rahi hain — Stock Picker project ka actual crew code likhna shuru. Pehla goal: **structured outputs** use karna, yaani har task se ek **particular JSON schema** ke hisaab se information lena, taaki agents se jo data chahiye wo **robust, "on rails"** tarike se mile.
- Iske liye (jaise pehle dekha tha) **pydantic `BaseModel` ki subclasses** banate hain jo describe karti hain ki humein kya chahiye:
  - **`TrendingCompany`** — class docstring/explanation: *"a company in the news attracting attention"*. Fields: **`name`**, **`ticker`**, **`reason`** — har field ke saath ek **description**. Ye descriptions hi agents/tasks ko **guide** karti hain ki exactly kya produce karna hai.
  - **`TrendingCompanyList`** — bas ek wrapper class jismein single field **`companies: list[TrendingCompany]`** hai. Isse ek task ka result **multiple trending companies** ka organized list ban jaata hai.
- Research ke liye same pattern repeat:
  - **`TrendingCompanyResearch`** — *"detailed research on a company"*. Fields: **`name`**, **`market_position`**, **`future_outlook`**, **`investment_potential`**. Field ka naam + description dene se agent **forced** hota hai wahi information apne response mein produce kare — agent behavior guide karne ka bahut clever tarika.
  - **`TrendingCompanyResearchList`** — saari companies ke research objects ka list.
- **Naming lesson (important):** Ed ne pehle version mein in classes ko *"newsworthy companies"* bola tha — wo concept crystal clear nahi tha aur reliability kam thi. **Consistent, simple, common terminology** use karo (har jagah "trending companies") — isse LLM ka output zyada reliable hota hai.
- Ab **crew class `StockPicker`** define karte hain — **YAML files** (agents.yaml, tasks.yaml) ko refer karke, aur scaffolding ka baaki auto-generated "gunk" delete karke scratch se build karte hain.
- **Agents (3 + 1 manager):**
  - **`trending_company_finder`** — **`@agent` decorator** ke saath, config se Agent return karta hai, aur **`SerperDevTool`** use karta hai taaki internet pe trending companies dhundh sake.
  - **`financial_researcher`** — same pattern, config + **Serper tool** (research ke liye web search chahiye).
  - **`stock_picker`** — Cursor ne suggest kiya tha ki isme bhi SerperDev tool daal do, par **zarurat nahi** — stock picker ko saari information pehle hi mil chuki hoti hai, use search ki need nahi. (Lesson: har agent ko har tool mat do.)
- **Tasks:**
  - **`find_trending_companies`** — config se Task banata hai, aur **`output_pydantic=TrendingCompanyList`** field set karta hai. Matlab: ye task **must** us schema-conforming JSON output kare. **Yahi CrewAI mein structured outputs karne ka tarika hai.**
  - **`research_trending_companies`** — config + **`output_pydantic=TrendingCompanyResearchList`** — research forced hota hai us schema mein aane ke liye.
  - **`pick_best_company`** — best company select karta hai; simple task, koi pydantic constraint dikhaya nahi gaya.
- **Manager agent (4th agent, special handling):**
  - Humne 3 agents banaye the par 4th bhi tha — **manager**. Ise `@agent` decorator waali general list mein **nahi** daalte, kyunki wo task pe kaam karne wale workers mein se nahi hai — use **separately create aur handle** karte hain (ek alag variable ke roop mein).
  - Manager agent mein **`allow_delegation=True`** set karte hain — CrewAI ko batata hai ki ye agent doosre agents ko kaam **delegate** kar sakta hai. Ed ke words mein ye **OpenAI Agents SDK ke "handoff" ka equivalent** hai.
- **Crew creation (`def crew`):**
  - `Crew(agents=self.agents, tasks=self.tasks, process=Process.hierarchical, verbose=True, manager_agent=manager)` return karte hain.
  - **`self.agents` / `self.tasks`** — decorators waale agents/tasks automatically collect ho jaate hain.
  - **`Process.hierarchical`** (sequential nahi!) — matlab ek **LLM decide karega kaunsa agent kaunsa task karega**.
- **Alternative:** alag manager agent banane ki jagah sirf **`manager_llm="gpt-4o"`** (ya koi bhi LLM) bhi de sakte ho. Dono kaam karte hain, par Ed ne paya ki **manager ka role describe karne ka mauka milne se performance thodi better** hoti hai — though *"neither works perfectly, it's an adventure"* — autonomous AI ke challenges ki interesting jhalak.
- **Cost note:** manager ke liye Ed **GPT-4o** (bada model) use kar raha hai, **GPT-4o-mini nahi** — thoda pricey, par manager mission ke saath **zyada coherent** rehta hai. Budget tight hai to 4o-mini bhi chalega.

---

## 🔑 Key Concepts / Important Terms

| Term | Simple Hinglish Meaning |
|------|--------------------------|
| **Structured outputs** | Task ka output ek fixed JSON schema mein force karna — "on rails" data extraction |
| **pydantic `BaseModel`** | Schema define karne ki class; field names + descriptions hi LLM ko guide karte hain |
| **`output_pydantic`** | Task ka wo parameter jisse output kisi pydantic class ke schema se bind hota hai — CrewAI mein structured output ka tarika |
| **Wrapper list class** | `TrendingCompanyList` jaisi class jismein ek field `companies: list[...]` hota hai — ek task se multiple items lene ke liye |
| **Consistent terminology** | Classes/fields mein simple, common, consistent naam ("trending" everywhere) — reliability badhata hai |
| **`@agent` / `@task` decorators** | Methods ko mark karte hain; `self.agents` / `self.tasks` mein auto-collect hote hain |
| **`SerperDevTool`** | Google-search tool — sirf un agents ko do jinhe web search chahiye |
| **Manager agent** | Alag se banaya gaya 4th agent jo kaam delegate karta hai; general agents list mein nahi jaata |
| **`allow_delegation=True`** | Agent ko doosre agents ko kaam saunpne ki permission — OpenAI SDK ke handoff ka equivalent |
| **`Process.hierarchical`** | Sequential ki jagah ek LLM/manager decide karta hai kaunsa agent kaunsa task kare |
| **`manager_agent` vs `manager_llm`** | Ya to full manager agent do (role describe karke — better), ya bas ek LLM naam (shortcut) |

---

## 💡 Backend Dev Ke Liye Note (aapke liye)

- **`output_pydantic` = response_model pattern:** Bilkul FastAPI ke `response_model=` jaisa hai — endpoint (yahan task) jo bhi kare, output validated pydantic object mein aayega. Field descriptions yahan sirf docs nahi, wo **prompt ka hissa** ban jaati hain — schema hi prompt engineering hai.
- **Wrapper list class kyun?** Top-level JSON array ki jagah `{"companies": [...]}` object — same reason jaise API responses mein bare arrays avoid karte ho (extensibility + LLM JSON-object mode friendly). DTO design ki aadat yahan directly kaam aati hai.
- **Hierarchical process = orchestrator pattern:** Sequential pipeline (jaise Celery chain) vs hierarchical (ek dispatcher/manager jo runtime pe routing decide kare). Manager ke liye bada model lena waisa hi hai jaise load balancer/scheduler ko beefier instance dena — coordination failure sabse mehenga failure hota hai.
- **Hands-on lab:** is lecture ka code khud chalane ke liye `Practical/lab3_stock_picker.py` run karo (is repo me, `uv run` se chalta hai, Groq pe free via LiteLLM). Hamare labs course se thoda alag hain: self-contained code-style (YAML scaffolding nahi), aur SerperDev ki jagah **free Wikipedia search tool** use hota hai — concepts (pydantic outputs, hierarchical process, manager agent) same hain.

---

## 🧠 Takeaway (yaad rakho)

1. CrewAI mein structured output ka tarika: pydantic `BaseModel` class banao (fields + descriptions) aur Task mein **`output_pydantic=YourClass`** set karo — output schema pe "on rails" ho jaata hai.
2. Multiple items chahiye to wrapper class banao (`TrendingCompanyList` with `companies: list[TrendingCompany]`).
3. **Consistent, simple naming** (classes, fields, descriptions) LLM reliability directly badhati hai — "newsworthy" se "trending" pe switch karne se output better hua.
4. Manager agent ko `@agent` list se **bahar** rakho, `allow_delegation=True` do, aur crew mein `process=Process.hierarchical` + `manager_agent=` pass karo. (Shortcut: `manager_llm=`, par described manager better perform karta hai.)
5. Manager ke liye **bigger model (GPT-4o)** use karo — coherence ke liye worth it; aur har agent ko har tool mat do (stock picker ko Serper ki zarurat nahi thi).

---

<details>
<summary>📜 Full English Transcript (original, click to expand)</summary>

And now it gets juicy. Now we're going to go to Crew and we're going to start building a bunch of different things. So the first thing is that I want us to use structured outputs. In other words, we are going to ask our different tasks to be providing information according to a particular JSON schema as a way of making sure we're getting the information that we want from these agents in a robust sort of way that is kind of on rails. And so, as you probably remember, the way to do that is to create classes that are subclasses of BaseModel and use this as a way of describing what we want.

So let me give you an example. Let's make a class that's called TrendingCompany. And so this is a subclass of BaseModel. We give it an explanation. It's a company in the news attracting attention. And then we set up name, ticker and reason. And we give them descriptions like this. And you can see this is a way of laying out the information that we're going to want to be gathering. And it helps guide the agents and the tasks to produce information that we want. And now I'm going to make a second class. That is basically just a list of these. So it's called TrendingCompanyList. And it contains a single field, companies, which is a list of these objects. It's a way to organize it so that one task can result in a bunch of trending companies. So far so good.

We're going to do pretty much the same thing again for our research. So we're going to have a TrendingCompanyResearch schema. Here it is. So again it's a pydantic class, a class that is a subclass of BaseModel. And it's detailed research on a company. It has a name, market position, future outlook and investment potential. And by giving the fields with that name and with that description, we are going to force the agent to produce that information in its response. And so it's a really clever way of making sure that we guide the agent's behavior. And similarly we're going to add a list, TrendingCompanyResearchList, a detailed list of all of the research on the companies, and it's a list of TrendingCompanyResearch objects, of these objects with these descriptions.

And again, I find it helpful to be mindful that you use consistent, clear terminology. I used to — my first version of this, I called these newsworthy companies, and I was just introducing concepts that weren't crystal clear in terms of what I was going for. And this has helped make it more reliable, using simple and common terms and using them consistently.

Okay, now it's time to define our crew, our class StockPicker. And as usual we look at the YAML files. We bring them in here. And I've deleted the rest of the gunk that it auto generates so that we can build this ourselves from scratch. And we're going to start by creating our trending company finder agent, which I'll do like this. And we need to give it of course the decorator @agent like that. So this is a trending company finder. It's going to return an agent configured with the config and we're going to use a tool which will be — let me tidy this up for you. There we go. It's going to use the SerperDev tool as before so that it can look for trending companies on the internet. That seems pretty good.

All right, let's make our second agent. And this second agent is going to be our financial researcher agent. And so let's see, we're going to want to again use Serper. So we're going to have it look at the config again for the financial researcher and the tools. All right. That seems good. And it has suggested — Cursor has kindly suggested that we do this, which seems good to me, except we don't really need this. We don't need to have the SerperDev tool in there, because the stock picker has been given all of its information, it's not going to need that at all. All right. So that is the definition of our three agents.

Let's go on to defining our tasks. Okay. So it's time to define the first of our tasks. And the first task is the task to find trending companies using the trending company finder. And here it is. Find trending companies is creating a task. This is the config. And we also have this field output_pydantic. And that is telling it that this task needs to output some JSON in the schema that conforms to TrendingCompanyList. And that of course is this object right here. So we are constraining it to make sure that it produces something in that format, which is exactly what we want. And so this is the way that you do structured outputs in Crew. And now the research trending companies task. This is going to again be hooked up to the right config. And this of course is going to create the TrendingCompanyResearchList pydantic object. So here we go. If we look back up, this is, of course, this object right here. A list of research results. So we are saying this task to research is going to be forced to produce information that conforms to that schema. And that way we know we're going to get research. Hopefully you're following along with this. If not then do look at the code and try this out for yourself. We're almost done. We're just going to add in the best company picker, which is right here, and which is going to select the best company. And that's an easy one, an easy one to end with. And now we've got left to do is actually create our crew.

All right. Time to create the crew. We've made the agents. We've made the tasks. Here is the crew. You may be thinking to yourself, we only created three agents. Did we have a fourth agent? Yes, we did, but that fourth agent is a bit different. It's the manager, and we don't want that to be in the list of the general agents that are going to be working on the task at hand. We're going to want to create this separately and handle it separately. So we create our manager agent like this, just as a separate variable, manager, an agent that has the config that's called manager. And we also use this field allow_delegation equals true. That is telling Crew that we want it to be able to delegate to other agents. That would be the equivalent of the handoff in the OpenAI Agents SDK.

All right. And so now it just remains for us to actually return our crew from this function here, from def crew. And we're going to do it like this. Return Crew. The agents is self.agents. And that is the three agents with the decorators above. Those are the agents that form this team, this crew. The tasks are the tasks that we defined. We're now saying the process is Process.hierarchical, not Process.sequential. And that means that we are going to assign an LLM to figure out which agent does what task. Verbose is true. And this is where we specify the manager agent. It's the agent we created right here. We could just create that agent right there in the code. But it's a bit neater to do it this way and that is the end of it.

Now there is actually an alternative here. You don't need to create a separate manager agent. You can actually say manager_llm equals and just define an LLM like GPT-4o or something. But um, I found it perform slightly better if I get the opportunity to describe the role of the manager. But both did work. But as you'll see, neither works perfectly. Haha. It's an adventure. As I say, it's a very interesting insight into some of the challenges of autonomous AI, but still it works better if you define the manager separately. And one other point I'll make is that in defining that manager, I don't know if you spotted this, but I'm actually using GPT-4o, not GPT-4o mini. I'm using the bigger version, which means it's slightly more pricey, so you can make that 4o-mini if you'd prefer, but I found that that helped it stay more coherent with the mission at hand. So anyway, that is defining the crew.

</details>

---
*Source: Official Udemy lecture transcript (auto-captions, lightly cleaned). Notes in Hinglish for self-study.*
