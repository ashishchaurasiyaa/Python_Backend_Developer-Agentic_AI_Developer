# Lecture 4: Roles & Responsibilities of a Software Architect

> *"A great architect enables both the system AND the team to thrive."*

**Section 1 — Foundations of Software Architecture**

---

## 🎯 Is lecture mein kya seekhenge?

- **Software architect** kaun hota hai exactly?
- Architect ki **6 core responsibilities**:
  - System Design & Architecture Decisions
  - Technical Trade-offs
  - Stakeholder Alignment
  - Enabling the Team
  - Owning Non-Functional Requirements
  - Mentorship
- **Architect vs Tech Lead** — kya difference hai?
- Great architect banne ke liye **key skills**
- **Common pitfalls** jo avoid karne chahiye

---

## 1. Who is a Software Architect?

### Definition

> **A software architect is a person who defines the technical direction of a system — not just for today, but for how it will evolve over time.**

### The Bridge Role

Architect **bridge** hai do worlds ke beech mein:

```
🟦 BUSINESS WORLD          🟩 ENGINEERING WORLD
   - Business goals         - Code, tools, patterns
   - Cost constraints       - Frameworks
   - Time-to-market         - Infrastructure
   - User expectations      - Best practices
   - Revenue                - Technical debt
            ↓                      ↑
            └──── 🏗 ARCHITECT ────┘
                      │
                      ▼
                 Bridge them!
                 - Translate business needs into technical strategy
                 - Make tradeoff decisions
                 - Communicate both directions
```

### The 3 Spheres of Influence

```
              🏗 Software Architect
                     │
        ┌────────────┼─────────────┐
        ▼            ▼             ▼
┌──────────────┐ ┌──────────┐ ┌──────────────┐
│ Team         │ │Technology│ │ Business     │
│ Enablement   │ │           │ │ Goals        │
├──────────────┤ ├──────────┤ ├──────────────┤
│ • Guide devs │ │ • Make    │ │ • Understand │
│ • Promote    │ │   design  │ │   requirements│
│   best       │ │   decisions│ │ • Balance    │
│   practices  │ │ • Choose  │ │   cost vs    │
│              │ │   tech    │ │   value      │
│              │ │   stack   │ │              │
└──────────────┘ └──────────┘ └──────────────┘
```

### Key Insight

> **Every architectural decision they make has a long-term ripple effect on scalability, maintainability, and team velocity.**

It's NOT just about writing code. It's about:
- Guiding **how code comes together** to solve **real business needs**

---

## 2. Core Responsibilities at a Glance

```
                        🏗 Software Architect
                              │
   ┌──────┬───────┬─────────┼──────────┬────────────┬──────────┐
   ▼      ▼       ▼          ▼          ▼            ▼          ▼
System Stake-  Technical   Team      NFR         Team
Design holder  Trade-offs  Mentor-   Owner-      Facilita-
       Align-              ship      ship        tion
       ment
```

### The 6 Key Responsibilities

1. **System Design & Architecture Decisions** — Structure ka ownership
2. **Making Technical Trade-offs** — Hard decisions ka ownership
3. **Stakeholder Alignment** — Communication ka ownership
4. **Facilitating the Team** — Team enablement
5. **Ensuring Non-Functional Requirements** — Quality ka ownership
6. **Mentoring Developers** — People growth

Let's break each one down.

---

## 3. Responsibility 1: System Design

> **The most visible responsibility.**

### What it Involves

```
┌──────────────────────────────────────┐
│ UI Layer (Web/Mobile Interfaces)      │
└──────────────┬───────────────────────┘
               ▼
┌──────────────────────────────────────┐
│ API Gateway / Controller Layer        │
└──────────────┬───────────────────────┘
               ▼
┌──────────────────────────────────────┐
│ Business Logic / Microservices        │
└──────────────┬───────────────────────┘
       ┌───────┴────────┐
       ▼                ▼
┌──────────────┐  ┌──────────────────┐
│ Database /   │  │ Cloud Infra/      │
│ Data Layer   │  │ Deployment        │
└──────────────┘  └──────────────────┘
```

### Key Activities

**1. Define System Boundaries**
- Kya hai aapke system ke andar?
- Kya hai bahar?
- What integrations exist?
- Components kaise organized hain internally?

**Example:**
- "Order Service owns: orders table, fulfillment logic, status tracking"
- "Order Service does NOT own: payments (separate service), inventory (separate service)"

**2. Choose the Right Architecture Pattern**

```
Question: Which architectural pattern fits?
─────────────────────────────────
Options:
  • Microservices (independent, scalable)
  • Layered (simple, fast to start)
  • Hexagonal (testable, decoupled)
  • Event-driven (reactive, decoupled)
  • Serverless (cost-efficient, scales to zero)

Architect's job: Pick the right one for the context.
```

**3. Make Foundational Decisions**

Early decisions that shape everything downstream:
- ✓ How are APIs exposed? (REST vs GraphQL vs gRPC)
- ✓ How does data flow between services? (Sync vs Async)
- ✓ What's the deployment model? (VMs vs Containers vs Serverless)
- ✓ How do we handle state? (Stateless vs Stateful)
- ✓ How are services discovered? (DNS vs Service Mesh)

**4. Ensure Long-Term Quality**

Design for:
- Today's traffic ✓
- Tomorrow's growth ✓✓
- 3-year vision ✓✓✓

```
Architect mindset:
"This works for 1K users today. Will it work for 1M users in 2 years?"
```

### Architect's Toolkit for System Design

- **Architecture Decision Records (ADRs)** — document the why
- **C4 diagrams** — visualize at different levels
- **Sequence diagrams** — show flows
- **Deployment diagrams** — show infrastructure
- **API specifications** — OpenAPI, AsyncAPI

---

## 4. Responsibility 2: Technical Trade-offs

> **Here's a core truth in architecture: there is no perfect solution.**

### Every Decision Has Trade-offs

```
Architect Decision
       │
       ├── Trade-off → Scalability ↑
       │
       └── Trade-off → Cost ↑

Choose one → get the other.
```

### Common Trade-off Scenarios

**Scenario 1: Performance vs Maintainability**
```
Want blazing fast performance?
→ Optimize for speed
→ Sacrifice some maintainability
→ Hand-tuned algorithms, less abstraction
```

**Scenario 2: Flexibility vs Simplicity**
```
Want highly flexible code?
→ Lots of abstraction layers
→ Sacrifice simplicity
→ More complex codebase
```

**Scenario 3: Scalability vs Cost**
```
Want infinite scalability?
→ Multi-region, auto-scaling, redundancy
→ Sacrifice cost
→ 3x-5x more expensive
```

**Scenario 4: Security vs Velocity**
```
Want bank-grade security?
→ Multi-layer encryption, audits, MFA everywhere
→ Sacrifice development speed
→ Slower feature rollouts
```

### Architect's Job: Make Trade-offs Deliberately

```
❌ Bad architect: "We need to make this fast AND maintainable AND scalable"
✅ Good architect: "Given budget constraints, we prioritize:
                    1. Scalability (most important)
                    2. Maintainability (medium)
                    3. Performance (can revisit later)
                    Trade-off: not as fast as competitors,
                    but easier to onboard new devs."
```

### Decision Process

1. **Analyze options**
   - Technical feasibility
   - Operational impact
   - Financial cost
   - Team capability

2. **Identify trade-offs**
   - What do we gain?
   - What do we lose?

3. **Align with goals**
   - Business priority
   - System constraints

4. **Decide & document**
   - ADR with rationale

5. **Communicate**
   - To business: in business terms
   - To devs: in technical terms

### Architect Doesn't Avoid Trade-offs

> **Good architects don't chase elegance for its own sake. They seek the right balance based on context, constraints, and priorities.**

---

## 5. Responsibility 3: Stakeholder Alignment

> **Architecture doesn't exist in isolation. It's deeply tied to people and priorities.**

### Who Architects Work With

```
                  🏗 Software Architect
                          │
        ┌─────────────────┼──────────────────┐
        ▼                 ▼                  ▼
┌─────────────┐   ┌──────────────┐   ┌──────────────────┐
│ 📈 Business  │   │ 🚀 Product   │   │ 💻 Engineering / │
│              │   │   Management │   │  Dev Teams       │
│ - Goals      │   │              │   │                   │
│ - Budgets    │   │ - Features   │   │ - Feasibility    │
│ - Cost       │   │ - Timelines  │   │ - Implementation │
│ - Risk       │   │ - Priorities │   │ - Constraints    │
└─────────────┘   └──────────────┘   └──────────────────┘
```

### Working with Product Managers

- Understand which features are most important
- Know the timeline pressure
- Discuss priority of NFRs
- Align on what's MVP vs nice-to-have

**Example conversation:**
> PM: "We need user authentication by next month."
> Architect: "OK. For MVP, we can use simple JWT-based auth (1 week). For enterprise customers in Q3, we'd need SSO/SAML (4 weeks). Should we plan for the second now or later?"

### Working with Business Leaders

- Stay in sync with overall goals
- Understand budget constraints
- Know risk tolerance
- Communicate technical implications of business decisions

**Example conversation:**
> CEO: "Can we launch in 5 new countries by year end?"
> Architect: "Yes, but requires multi-region architecture upgrade. Cost will go from $50K/month to $200K/month. Alternative: launch in 2 countries first to validate."

### Working with Developers

- Ensure designs are feasible
- Understand current capabilities
- Make architecture sustainable
- Listen to implementation feedback

**Example conversation:**
> Dev: "This service has 200K LOC and is hard to maintain."
> Architect: "Let's plan a strangler fig migration to split it into 3 services over the next 2 quarters."

### The Translation Skill

Architect's superpower: **Translate between worlds**

```
Business says: "We need to grow 10x"
Architect translates to engineering:
  → "We need to redesign DB sharding
     We need to add caching layer
     We need multi-region deployment"

Engineering says: "We need to refactor this monolith"
Architect translates to business:
  → "Investment of 6 months and $500K
     Will reduce future feature dev time by 40%
     Will improve uptime from 99.5% to 99.95%"
```

### Transparency in Trade-offs

```
✅ Make trade-offs transparent to ALL stakeholders
✅ Document rationale in ADRs
✅ Get buy-in before major decisions
✅ Revisit when context changes
```

---

## 6. Responsibility 4: Enabling the Team

> **A great architect doesn't just design systems — they empower teams to build confidently.**

### Architect's Role with the Team

```
              🏗 Architect
                  │
        ┌─────────┼──────────┐
        ▼         ▼          ▼
   ┌────────┐ ┌──────────┐ ┌─────────────┐
   │ Dev    │ │ Guide-   │ │ Tech         │
   │ Team   │ │ lines    │ │ Enablement   │
   └────────┘ └──────────┘ └─────────────┘
```

### How Architects Enable Teams

**1. Define Clear Architecture Boundaries**

```
"Each microservice owns its own database.
 No service queries another service's DB directly.
 Communication via APIs or events only."
```

This removes ambiguity. Developer knows: kya karna hai, kya nahi karna hai.

**2. Provide Reusable Patterns and Guidelines**

```
Pattern Library:
─────────
✓ Standard REST API template
✓ Error handling middleware
✓ Logging structure
✓ Authentication middleware
✓ Database migration template
✓ Testing template (unit, integration, e2e)
✓ CI/CD pipeline template
```

Developers don't need to invent wheel every time. They follow established patterns.

**3. Reduce Decision Fatigue**

```
Without architect:
Dev: "Which logging library? Which testing framework?
      Which Python version? Which CI tool? Which DB ORM?"
Result: Decision paralysis, inconsistency

With architect:
Dev: "I'll just use the team's standard stack:
      Loguru, pytest, Python 3.12, GitHub Actions, SQLAlchemy"
Result: Faster development, consistent codebase
```

**4. Unblock and Support**

When blockers come up:
- ❓ Technical doubts → architect helps decide
- ❓ Architectural conflicts → architect resolves
- ❓ Cross-team disputes → architect mediates
- ❓ Tool/process issues → architect supports

### Key Insight

> **Architects don't just set the direction — they clear the path.**

---

## 7. Responsibility 5: Owning Non-Functional Requirements (NFRs)

> **NFRs often get overlooked. The architect's job is to make sure they're considered from day one.**

### What are NFRs Again?

Non-functional requirements:
- 📈 Scalability
- ⚡ Performance
- ✅ Availability
- 🔒 Security
- 🔧 Maintainability
- 💰 Cost-Efficiency

(Detail in Lecture 3)

### Why NFRs Get Ignored

```
😱 Common scenario:
"Let's just ship features first. We'll think about
 scalability/security/performance later."

Result:
🔥 6 months later → system collapses under load
🔥 8 months later → security breach
🔥 12 months later → expensive rewrite
```

### Architect's Defense

```
🛡 System Shield (Architect)
        │
   ┌────┼────┬─────────┬───────┬──────────┬───────────┐
   ▼    ▼    ▼          ▼       ▼          ▼           ▼
Scal- Avail- Perfor-  Security Maintain- Cost
ability ability mance              ability  Efficiency
```

The architect **champions** these from day one.

### Architect Activities for NFRs

**1. Make NFRs Explicit Requirements**

```
❌ Vague: "App should be fast"
✅ Clear: "API responds < 200ms at P95, supports 10K RPS,
           99.9% availability, OWASP-compliant"
```

**2. Choose NFR-Aligned Tools**

```
Need scalability? → Stateless services, async messaging, sharded DB
Need security?    → OAuth2, encryption, secure coding, audits
Need maintainability? → Clean architecture, TDD, documentation
```

**3. Call Out NFR Risks Early**

```
Architect in design review:
"This design works for 100K users.
 But you mentioned 10x growth in 2 years.
 We need to plan for sharding now, or pay massive
 refactoring cost later."
```

**4. Build NFR Tests**

- **Load testing** (k6, Locust)
- **Security scanning** (SAST, DAST)
- **Performance benchmarks** (continuous)
- **Chaos engineering** (failure tests)

### Architect Says: "I Own NFRs"

> **The architect ensures NFRs are baked into design — not as afterthought, but as core design driver.**

---

## 8. Responsibility 6: Mentorship

> **Beyond diagrams and decisions, mentorship is a key part of the architect's role.**

### The Architect as Mentor

```
🏗 Senior Architect (Mentor)
         │
         │ Shares knowledge
         ▼
   🧑 Developer (Mentee)
```

```
Developer Career Progression
─────────────────────────
2018: Junior Developer
2019: Mid-level Developer
2021: Senior Developer
2023: Software Architect
```

### What Mentorship Looks Like

**1. Reviewing Designs & PRs**

Not just "approve" or "reject" — explain the **why**:
- "Why this pattern over that one?"
- "Why this naming convention?"
- "Why this trade-off here?"

**2. Sharing Architectural Reasoning**

```
❌ "Use this design"
✅ "Use this design because:
    - It scales horizontally
    - It's tested in production at Company X
    - Team has existing expertise
    - Alternative would require X weeks of learning"
```

**3. Fostering Culture**

Architect builds team culture around:
- Clean code
- Thoughtful design
- Scalable thinking
- Refactoring discipline
- Testing rigor
- Long-term ownership

**4. Building System Thinkers**

Developer mindset evolution:
```
Junior:    "How do I write this feature?"
Mid:       "How does this feature fit in the module?"
Senior:    "How does this module fit in the service?"
Architect: "How does this service fit in the system?
            How will it look in 5 years?"
```

**Architect's job: accelerate this evolution.**

### Key Insight

> **Mentorship means lifting the team so that architecture becomes a shared mindset — not just one person's responsibility.**

The best architectures are built by **teams that think like architects**, guided by an architect who teaches them how.

---

## 9. Architect vs Tech Lead

> **A common question: what's the difference?**

### Key Differences

| Aspect | 🏗 Architect | 👨‍💼 Tech Lead |
|---|---|---|
| **Focus** | System-wide design, long-term vision | Day-to-day execution, sprint planning, code delivery |
| **Scope** | Works across teams, components, sometimes products | Focuses on specific team or feature group |
| **Primary Outputs** | Diagrams, architectural blueprints, tech strategies | Clean, maintainable code, mentoring, backlog execution |
| **Stakeholder Interaction** | Product, business, ops, engineering | Closer to devs and PMs |
| **Decision Style** | Strategic, long-term decisions and trade-offs | Tactical, short-term technical leadership |
| **Time Horizon** | Months to years | Days to weeks |
| **Code Writing** | Less hands-on, prototypes, designs | Code reviews, hands-on dev |

### Visual Representation

```
        🏗 Architect                    👨‍💼 Tech Lead
            │                                │
            ▼                                ▼
    Strategic (months/years)          Tactical (days/weeks)
            │                                │
            ▼                                ▼
    System-wide                       Team-specific
            │                                │
            ▼                                ▼
    Design + Strategy                 Execution + Delivery
            │                                │
            ▼                                ▼
    Cross-team                        Single team
            │                                │
            ▼                                ▼
    Business + Engineering            Engineering + Product
```

### When Roles Blend

```
🏢 Small/growing teams:
   One person wears both hats — architect + tech lead

🏢 Large organizations:
   Clear separation — architects guide system,
   tech leads execute in teams
```

### Overlap Areas

Both can:
- ✅ Mentor developers
- ✅ Conduct code reviews
- ✅ Influence design
- ✅ Make technical decisions
- ✅ Communicate with stakeholders

### Career Progression

```
Senior Developer
       │
       ├──→ Tech Lead (execution focus)
       │       │
       │       └──→ Engineering Manager (people management)
       │
       └──→ Software Architect (design focus)
               │
               └──→ Principal Engineer / Chief Architect
                       (system-of-systems thinking)
```

---

## 10. Key Skills of a Great Architect

```
              🧠 Architect's Mind
                    │
   ┌──────┬────────┬────────┬──────────┬──────────┐
   ▼      ▼        ▼        ▼          ▼          ▼
System Communi- Security Trade-off Pattern    Stakeholder
Design cation   Princi-  Analysis  Recogni-   Alignment
                ples              tion
```

### Skill 1: Deep Technical Knowledge

**Foundation** — but not enough alone.

What architects need to know:
- Multiple programming languages (Python, Go, Java, etc.)
- Databases (SQL + NoSQL + vector + graph)
- Cloud platforms (AWS, GCP, Azure)
- Communication protocols (HTTP, gRPC, GraphQL)
- Architecture patterns (every section of this course!)
- Operating systems, networks, distributed systems theory

**But knowledge alone doesn't make you an architect.**

### Skill 2: System-Level Thinking

> **The ability to see how all the moving parts interact.**

```
Junior developer sees: "This function does X"
Senior developer sees: "This class does X, depends on Y"
Architect sees:        "If we add 10x traffic, this bottleneck
                        cascades to these 5 services and impacts
                        availability of the whole system"
```

**Skills:**
- Visualize entire system at once
- Trace dependencies
- Identify failure modes
- Predict bottlenecks
- See ripple effects

### Skill 3: Strong Communication

Architecture **= 50% technical, 50% communication.**

What architects need to do:
- Explain complex ideas simply
- Tailor message to audience (business, dev, ops)
- Write clearly (ADRs, docs)
- Present persuasively (design reviews)
- Listen actively (gather requirements)
- Negotiate trade-offs

### Skill 4: Decision-Making Under Ambiguity

> **Architecture is ambiguity central. Great architects can decide even when not all answers are clear.**

Reality:
- Future requirements: unknown
- User behavior: unpredictable
- Technology evolution: rapid
- Team capability: variable

**Skills for ambiguity:**
- Make decisions with incomplete info
- Document assumptions
- Plan for change
- Optionality (preserve flexibility)
- Iteration (revisit decisions)

### Skill 5: Business and Domain Awareness

> **Architects understand how technology supports strategy, revenue, and customer experience.**

NOT just "I know Kafka". RATHER: "I know when Kafka helps the business."

**Skills:**
- Understand business model
- Know customer pain points
- Translate features to architecture
- Know revenue impact of decisions
- Balance technical debt vs business value

### Skill 6: Empathy

> **Underrated but critical.**

**Empathy for developers** who maintain the system:
- Will they understand this design?
- Is it easy to debug at 3 AM?
- Does it have good error messages?

**Empathy for users** who rely on it:
- Is it fast enough?
- Is it reliable?
- Is it secure?

**Empathy for ops**:
- Can it be monitored?
- Can it recover from failures?
- Is it observable?

### The Full Architect Profile

```
A great architect:
✓ Knows technology deeply
✓ Thinks systemically
✓ Communicates clearly
✓ Decides under uncertainty
✓ Understands business
✓ Empathizes with humans
✓ Mentors others
✓ Stays humble
✓ Keeps learning
✓ Loves problem solving
```

---

## 11. Common Pitfalls to Avoid

> **Even experienced architects can fall into traps. Watch out!**

```
              🏗 Architect Pitfalls
                       │
   ┌──────┬───────┬────┴──────┬──────────┐
   ▼      ▼       ▼            ▼          ▼
Over-   Ignoring  Silver       Neglect-   Ignoring
engin-  Stake-    Bullet       ing NFRs   Feedback
eering  holders   Thinking
```

### Pitfall 1: Over-engineering

**Symptom:** Designing for every edge case, every future scenario.

```
❌ Bad architect mindset:
"What if we have 1 billion users in 10 years?
 What if we expand to 50 countries?
 What if we have IoT devices?
 Let me add abstractions for all of these!"

Result:
- 6 months building infrastructure for non-existent use cases
- Cloud bill $50K/month for 100 users
- Codebase impossible to onboard onto
```

**Fix:**
- Keep it **simple**
- Solve for **real needs**
- Evolve **as required**
- YAGNI (You Aren't Gonna Need It)

### Pitfall 2: Not Involving the Team

**Symptom:** Architecture in isolation, no team input.

```
❌ Bad architect:
"Here's the architecture. Implement it."

Result:
- Team feels unheard
- Practical implementation issues missed
- Resistance to follow design
- Low buy-in
```

**Fix:**
- **Engage team early**
- Solicit input from devs
- Run design reviews
- Iterate based on feedback
- Build consensus

### Pitfall 3: Ignoring Feedback Loops

**Symptom:** Once design is done, architect disappears.

```
❌ Bad architect:
"Design is shipped. My work is done."

Result:
- Don't see what breaks in production
- Don't know what's slow
- Architecture decisions never validated
- Decisions become outdated
```

**Fix:**
- **Watch production behavior**
- Review metrics
- Investigate incidents
- Refine decisions
- Stay engaged post-launch

### Pitfall 4: Losing Touch with Code

**Symptom:** Architect becomes too strategic, forgets practical reality.

```
❌ Bad architect:
"I haven't coded in 3 years. I just draw diagrams now."

Result:
- Designs are impractical
- Disconnected from team reality
- Lose credibility
- Designs don't account for code-level constraints
```

**Fix:**
- **Stay connected to code**
- Code reviews
- Prototypes
- Pair programming occasionally
- Read code to understand systems

### Pitfall 5: Not Evolving the Architecture

**Symptom:** "We designed it 3 years ago. It's done."

```
❌ Bad architect:
"This architecture worked at 10 users.
 Why should we change it at 10M users?"

Result:
- System creaks under load
- Tech debt accumulates
- Team becomes frustrated
- Eventually requires expensive rewrite
```

**Fix:**
- **Architecture evolves with scale**
- Regular reviews (quarterly?)
- Track architecture metrics
- Plan for refactoring
- "Set and forget" doesn't exist

### Pitfall 6: Silver Bullet Thinking

**Symptom:** "Microservices fixes everything!"

```
❌ Bad architect:
"I read this great article about event sourcing.
 We must implement it everywhere!"

Result:
- Wrong tool for the job
- Complexity without benefit
- Team confused by paradigm shift
```

**Fix:**
- **No silver bullets**
- Every pattern has trade-offs
- Use right tool for right problem
- Question hype-driven decisions

### Summary of Pitfalls

| Pitfall | Symptom | Antidote |
|---|---|---|
| Over-engineering | Adding unneeded complexity | YAGNI |
| Not involving team | Solo architecture | Collaboration |
| Ignoring feedback | Disappearing post-launch | Stay engaged |
| Losing touch with code | No code reviews/coding | Stay hands-on |
| Not evolving | "Set and forget" | Regular reviews |
| Silver bullets | "X solves everything" | Context-aware decisions |

---

## 12. Summary & Key Takeaways

### Architect's Role in One Sentence

> **An architect defines how a system should be built, balances trade-offs, aligns stakeholders, enables the team, owns quality attributes, and mentors developers.**

### Key Insights

1. **Architect is more than diagrams** — it's about people, process, alignment
2. **Lead through design, not control** — architects influence, not dictate
3. **Enable both system and team** — both must thrive
4. **System-level thinking is rare** — develop it
5. **Communication = 50% of the job** — invest in it
6. **Stay humble** — no one knows everything

### Architect's Daily Activities

```
☑ Review designs and ADRs
☑ Pair with developers on tricky problems
☑ Attend product roadmap discussions
☑ Mentor team members
☑ Write/update architecture docs
☑ Investigate production issues
☑ Plan for upcoming features
☑ Evaluate new technologies
☑ Conduct architecture review meetings
☑ Communicate with non-tech stakeholders
```

### What Architects Don't Do (Misconceptions)

```
❌ Sit in ivory tower and design only
❌ Never write code
❌ Have all the answers
❌ Work alone
❌ Only think strategic, never tactical
❌ Just create diagrams
```

---

## 13. Interview Questions

### Q1: "What does a software architect do?"

**Answer:**
"A software architect defines the technical direction of a system — the structure, components, technologies, and patterns. They bridge business goals and engineering execution.

Their main responsibilities are:
1. **System design** — defining boundaries, components, and integrations
2. **Trade-off decisions** — choosing between competing priorities like performance vs cost
3. **Stakeholder alignment** — translating between business, product, and engineering
4. **Enabling the team** — providing guidelines, patterns, and unblocking devs
5. **Owning NFRs** — ensuring scalability, security, performance are baked in
6. **Mentorship** — growing the team's architectural thinking

Beyond the technical work, architects are communicators, decision-makers, and culture-builders."

### Q2: "What's the difference between an architect and a tech lead?"

**Answer:**
"Both are senior engineers, but they have different focus:

- **Architect**: System-wide, long-term, strategic. Works across teams, makes foundational decisions, defines patterns, owns NFRs. Less hands-on coding, more design + alignment.

- **Tech Lead**: Team-specific, short-term, tactical. Owns day-to-day execution, sprint planning, code delivery, mentoring within team. More hands-on coding.

In smaller teams, one person does both. In larger organizations, the roles are distinct — architects guide the bigger picture, tech leads execute within teams.

Both mentor developers, do code reviews, and influence design — but architects look at the forest, tech leads look at the trees."

### Q3: "How do you make architectural decisions when you don't have complete information?"

**Answer:**
"This is one of the hardest parts of being an architect — decisions are made under uncertainty.

My approach:
1. **Gather as much info as possible** — talk to stakeholders, prototype, research
2. **List assumptions explicitly** — document what you're betting on
3. **Identify reversibility** — is this decision easy to change later? If yes, decide and move; if no, invest more in analysis
4. **Preserve optionality** — design so we can pivot if needed
5. **Document the decision** (ADR) — context, rationale, trade-offs, expected outcomes
6. **Set review checkpoints** — when will we revisit this?
7. **Commit but stay open** — don't be paralyzed by perfection

The goal isn't to make perfect decisions — it's to make reasonable decisions with documented rationale that the team can build on."

### Q4: "How do you handle disagreement with stakeholders?"

**Answer:**
"Disagreement is healthy. My approach:

1. **Understand first** — really listen to their concerns. Often they have context I'm missing.

2. **Align on goals** — what are we trying to achieve? Often disagreement is about how, not what.

3. **Bring data** — performance metrics, cost projections, time estimates. Move from opinion to evidence.

4. **Present trade-offs** — 'Option A: faster but expensive. Option B: slower but cheaper. Option C: middle ground.'

5. **Let them decide if business** — if it's a business trade-off (cost vs feature speed), they should decide

6. **Stand firm on technical** — if it's clearly a technical mistake, explain why and propose alternatives

7. **Document the disagreement** — in ADRs, note 'Alternative considered: X. Rejected because Y.'

The goal isn't to 'win' — it's to make the best decision for the system and business."

### Q5: "What's a common mistake architects make?"

**Answer:**
"Several:

1. **Over-engineering** — designing for hypothetical 10x scale before achieving 1x. Often called 'cathedral building'. Better to start simple and evolve.

2. **Not involving the team** — architecting in isolation, then handing diagrams to confused developers. Architecture should be collaborative.

3. **Losing touch with code** — getting too strategic, forgetting practical realities. Designs become impractical.

4. **Silver bullet thinking** — 'microservices fix everything', 'event sourcing fix everything'. Every pattern has trade-offs.

5. **Ignoring feedback loops** — disappearing after design. Architects should watch production, learn from incidents, evolve decisions.

6. **Neglecting NFRs** — focusing on features, ignoring scalability/security/performance until production breaks.

The cure for most of these: **stay engaged, stay humble, collaborate with the team**."

---

## 14. Key Slide References (from PDF)

- 📄 **Slide 35**: Who is a Software Architect?
- 📄 **Slide 36**: Core Responsibilities at a Glance
- 📄 **Slide 37**: Responsibility — System Design
- 📄 **Slide 38**: Responsibility — Technical Trade-offs
- 📄 **Slide 39**: Responsibility — Stakeholder Alignment
- 📄 **Slide 40**: Responsibility — Enabling the Team
- 📄 **Slide 41**: Responsibility — Owning NFRs
- 📄 **Slide 42**: Responsibility — Mentorship
- 📄 **Slide 43**: Architect vs Tech Lead
- 📄 **Slide 44**: Key Skills of a Great Architect
- 📄 **Slide 45**: Common Pitfalls to Avoid

---

## 15. What's Next?

**Lecture 5: Documenting Architecture** — Architects ke decisions ko **document kaise karein**? ADRs (Architecture Decision Records) aur C4 Model ke saath.

➡️ **[Lecture 5: Documenting Architecture (ADRs + C4)](05_Documenting_Architecture_ADR_C4.md)**

---

## 🎓 Related Backend_Developer Curriculum

- [02_Year5+_Senior/01_System_Design/HLD_Theory/Udemy_MasteringSystemDesign/11_Blueprint.md](../../01_System_Design/HLD_Theory/Udemy_MasteringSystemDesign/11_Blueprint.md) — System design framework architects use
- [03_Interview_AnyYear/02_Interview_Prep/](../../../03_Interview_AnyYear/02_Interview_Prep) — Senior interview preparation
- [02_Year5+_Senior/01_System_Design/HLD_Theory/30_SLA_SLO_SLI.md](../../01_System_Design/HLD_Theory/30_SLA_SLO_SLI.md) — Quality contracts architects own
