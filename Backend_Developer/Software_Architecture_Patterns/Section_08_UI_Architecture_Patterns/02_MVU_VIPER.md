# Lecture 2: Unidirectional UIs — MVU & VIPER

> *"Data flows in one direction — predictability, testability, sanity."*

**Section 8 — UI Architecture Patterns for Apps**

---

## 🎯 Is Lecture Mein Kya Seekhenge?

- **Why unidirectional UIs** matter
- **Unidirectional data flow** core concept
- **MVU** (Model-View-Update) — functional, loop-based
- **MVU → Redux** in JavaScript
- **VIPER** (View-Interactor-Presenter-Entity-Router) — iOS clean architecture
- **MVU vs VIPER** comparison
- **Common pitfalls** and how to avoid them

---

## 1. Why Unidirectional UIs?

### The Problem with Traditional Patterns

```
Traditional MVC:
   ┌────────┐      ┌────────────┐      ┌────────┐
   │  View  │ ◄──► │ Controller │ ◄──► │ Model  │
   └────────┘      └────────────┘      └────────┘
   ↓                                       ↑
   └───── direct mutation sometimes ───────┘

Components talk in unpredictable ways.
Hard to trace where a change came from.
Hard to debug.
```

### What Modern UIs Need

```
✓ Predictability — clear cause and effect
✓ Stability — fewer mystery bugs
✓ Testability — feed in state, check output
✓ Traceable data flow
```

### Core Idea of Unidirectional Flow

```
Data moves in ONE direction through a loop:

       ┌──────────┐
       │  State   │
       └────┬─────┘
            │
            ▼ renders
       ┌──────────┐
       │   View   │
       └────┬─────┘
            │
            ▼ emits
       ┌──────────┐
       │ Message  │  (or Action / Event)
       └────┬─────┘
            │
            ▼ handled by
       ┌──────────┐
       │  Update  │
       └────┬─────┘
            │
            └──► new State (back to top)
```

### Where It Came From

```
✓ Web → Elm, Redux
✓ Mobile → VIPER (iOS), Redux (cross-platform)
✓ SwiftUI → declarative state-driven UI
```

---

## 2. Unidirectional Data Flow — Core Concept

```
State = single source of truth
   ↓
View = pure function of State
   ↓
User interaction → Message
   ↓
Update function (only place state changes)
   ↓
New State → back to View
```

### Properties

```
✓ View has NO logic — just renders
✓ View NEVER mutates state directly
✓ Only the Update function can change state
✓ Every state change is traceable to a Message
```

---

## 3. MVU — Model-View-Update

### Origin

**Originated in Elm**, a functional language for building web UIs.

### The Loop

```
        ┌────────────┐
        │   Model    │  (application state)
        └─────┬──────┘
              │
              ▼ render
        ┌────────────┐
        │    View    │  ← pure function of Model
        └─────┬──────┘    no side effects
              │
              ▼ user clicks button / types
        ┌────────────┐
        │  Message   │  e.g., AddTodo("Buy milk")
        └─────┬──────┘
              │
              ▼ update(message, model) → new model
        ┌────────────┐
        │   Update   │  pure function
        └─────┬──────┘
              │
              └──► loops back to top
```

### Three Functions

```python
# pseudo-code

model: Model                                  # initial state

view(model: Model) -> UI                      # pure function

update(msg: Message, model: Model) -> Model   # pure function
```

### Influence

```
✓ Redux (JavaScript)
✓ Vuex (Vue)
✓ NgRx (Angular)
✓ SwiftUI (declarative)
✓ Compose (Android)
✓ The Composable Architecture (TCA, Swift)
```

---

## 4. MVU in JavaScript = Redux

### Mapping MVU → Redux

```
┌─────────────────┬────────────────────┐
│   MVU           │   Redux            │
├─────────────────┼────────────────────┤
│   Model         │   State (in Store) │
│   Message       │   Action           │
│   Update        │   Reducer          │
│   View          │   React components │
└─────────────────┴────────────────────┘
```

### The Redux Flow

```
React Component
   │
   │ dispatch(action)
   ▼
┌──────────────┐
│    Store     │
│ (state tree) │
└──────┬───────┘
       │
       ▼ runs
┌──────────────┐
│   Reducer    │  (state, action) → newState
│ pure function│
└──────┬───────┘
       │
       └──► new state → React re-renders
```

### Benefits

```
✓ Single source of truth (Store)
✓ Reducer = pure function = easy to test
✓ Time-travel debugging (Redux DevTools)
✓ Predictable state transitions
✓ Replay actions like a movie
```

### Modern Trend

```
Newer libs embrace MVU principles:
   ✓ Zustand (simpler, hook-based)
   ✓ Jotai / Recoil (atomic state)
   ✓ React Context + useReducer
```

---

## 5. Why MVU Works So Well

```
✓ Predictable UI behavior
   View is pure function of state → always same render for same state

✓ Easy testing
   No app needed — feed in model + message → check new model

✓ Time-travel debugging
   Replay actions to reproduce any state

✓ Easier bug tracing
   Every state change came from a message → no mystery

✓ Clean separation
   State / View / Logic are decoupled
```

---

## 6. VIPER — View-Interactor-Presenter-Entity-Router

### Origin

**iOS architecture pattern derived from Clean Architecture principles.**

Created to combat "Massive View Controller" syndrome in iOS apps.

### The Five Roles

```
┌────────────────────────────────────────────────────┐
│                                                    │
│  V — View         Renders UI, captures input       │
│  I — Interactor   Business logic                   │
│  P — Presenter    Coordinates View ↔ Interactor    │
│  E — Entity       Plain data model                 │
│  R — Router       Navigation between screens       │
│                                                    │
└────────────────────────────────────────────────────┘
```

### Component Diagram

```
                   ┌──────────┐
              ┌───►│  Router  │ (navigation)
              │    └──────────┘
              │
   ┌─────┐    │    ┌───────────┐    ┌────────────┐
   │User │──►│View│◄────────►│Presenter│◄────►│Interactor│
   └─────┘    │    └───────────┘    └─────┬──────┘
              │                            │
              │                            ▼
              │                       ┌──────────┐
              │                       │  Entity  │
              │                       │  (data)  │
              │                       └──────────┘
```

### Responsibilities

```
View
   ✓ Renders UI
   ✓ Notifies Presenter of user events
   ✗ NO business logic

Presenter
   ✓ Receives events from View
   ✓ Delegates work to Interactor
   ✓ Formats result for View
   ✗ NO business logic
   ✗ NO direct data access

Interactor
   ✓ Contains business rules
   ✓ Talks to APIs, DB, services
   ✓ Returns data to Presenter
   ✗ Knows NOTHING about UI

Entity
   ✓ Plain old data model
   ✗ No logic

Router
   ✓ Handles navigation (screen transitions)
   ✓ Creates next module's stack (V+I+P+E+R)
```

### Use Cases

```
✓ Large iOS apps with complex screens
✓ Teams needing strong separation
✓ Apps where unit-testing every layer is required
```

### Tooling

```
✓ Clean Swift templates (generator)
✓ Generamba (Ruby code-gen for VIPER modules)
```

---

## 7. VIPER Data Flow Walkthrough

### Example: User taps "Login"

```
1. User taps button
        │
        ▼
2. View notifies Presenter
   presenter.loginTapped(email, password)
        │
        ▼
3. Presenter calls Interactor
   interactor.authenticate(email, password)
        │
        ▼
4. Interactor calls API / DB
   apiService.login(...) → returns Token (Entity)
        │
        ▼
5. Interactor returns result to Presenter
        │
        ▼
6. Presenter formats it and updates View
   view.showWelcome(userName)
        │
        ▼
7. If success → Presenter asks Router to navigate
   router.routeToHome()
```

### Why This Separation Matters

```
✓ View doesn't know about API
✓ Interactor doesn't know about UI
✓ Navigation is centralized in Router
✓ Each layer can be mocked + tested independently
```

---

## 8. MVU vs VIPER — Side-by-Side

```
┌──────────────────┬────────────────────┬──────────────────────┐
│  Aspect          │  MVU               │  VIPER               │
├──────────────────┼────────────────────┼──────────────────────┤
│  Origin          │  Functional        │  Object-oriented     │
│  Roots           │  Elm, Redux        │  Clean Architecture  │
│  Style           │  Loop-based        │  Layered             │
│  State           │  Single immutable  │  Distributed across  │
│  Side effects    │  Effects/commands  │  Interactors         │
│  Best for        │  Reactive web UIs  │  Large iOS apps      │
│  Strength        │  Simplicity        │  Modularity          │
│  Cost            │  Less ceremony     │  5+ files per screen │
│  Two-way binding │  Eliminated        │  Eliminated          │
└──────────────────┴────────────────────┴──────────────────────┘
```

### Common Wins

Both eliminate **tangled two-way data binding** — a huge win for maintainability.

### Choose Based On

```
✓ Your platform (web vs iOS)
✓ Team's mindset (functional vs OO)
✓ Need for structure vs flexibility
```

---

## 9. Common Pitfalls

### VIPER Pitfalls

```
✗ Over-engineering — 5 files per feature
✗ Folder explosion without discipline
✗ Boilerplate for simple screens
✗ Premature use on small apps
```

### MVU Pitfalls

```
✗ Bloated reducers full of nested conditionals
✗ Poor state modeling → logic gets messy
✗ Lost simplicity (the very thing MVU was supposed to give)
```

### Shared Pitfalls

```
✗ Forgetting separation of concerns
✗ Sneaking business logic into Views
✗ Leaky abstractions — UI code knowing about API
✗ Tight coupling to framework
```

### Tooling & Discipline

```
✓ MVU needs discipline on Message + State design
✓ VIPER needs consistent project structure + naming
✓ Without that, you keep the complexity, lose the benefits
```

---

## 10. Summary

```
✓ Unidirectional flow brings predictability + testability

MVU
   - Simple loop: Model → View → Message → Update → Model
   - Functional roots
   - Shines in reactive web / declarative UIs
   - Elm, Redux, SwiftUI

VIPER
   - 5 components, clean architecture style
   - Modular + testable
   - Shines in mobile/iOS at scale

Choose based on team, platform, problem domain.
Architecture should serve clarity, not create complexity.
```

---

## 🎤 Interview Q&A

**Q1. Why is unidirectional data flow better than two-way binding?**

A: With unidirectional flow, every state change can be traced to a single message/action processed by a pure function. There's no hidden chain of "A changes, which fires B, which fires C." This makes debugging deterministic and enables features like time-travel debugging.

**Q2. How is Redux related to MVU?**

A: Redux is essentially MVU adapted for JavaScript: Store ≈ Model, Action ≈ Message, Reducer ≈ Update, React Components ≈ View. The same pure-function-driven loop, just renamed.

**Q3. When would you choose VIPER over MVVM in iOS?**

A: VIPER for large apps with complex navigation flows, many screens, and strict testability requirements. MVVM for smaller apps, simple flows, or apps using SwiftUI where binding already gives you a lot. VIPER's 5-file overhead per screen only pays off when complexity justifies it.

**Q4. What is the role of the Router in VIPER?**

A: The Router owns navigation logic — creating the next module's full stack (View, Interactor, Presenter, Entity, Router) and pushing/presenting it. This keeps navigation out of Views and Presenters, making both more reusable and testable.

**Q5. What's "time-travel debugging" and which pattern enables it?**

A: Time-travel debugging lets you step backward/forward through every state change to reproduce bugs. It's enabled by MVU/Redux because the entire app state is reconstructed deterministically from an ordered list of actions/messages applied to an initial state.

---

## 🔗 Related

- Previous: [01_MVC_MVP_MVVM.md](01_MVC_MVP_MVVM.md)
- Next: [03_Offline_First_Sync.md](03_Offline_First_Sync.md)
