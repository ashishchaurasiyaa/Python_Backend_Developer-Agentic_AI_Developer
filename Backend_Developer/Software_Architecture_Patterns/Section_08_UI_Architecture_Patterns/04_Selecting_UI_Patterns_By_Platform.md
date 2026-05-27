# Lecture 4: Selecting UI Patterns by Platform

> *"Let your platform, people, process, and product guide your pattern."*

**Section 8 — UI Architecture Patterns for Apps**

---

## 🎯 Is Lecture Mein Kya Seekhenge?

- **Why platform matters** in UI architecture choice
- **Recap** — MVC, MVP, MVVM, MVU, VIPER
- **Web platform** — patterns + frameworks
- **Mobile platform** — Android + iOS pattern fit
- **Desktop platform** — long-lived sessions + rich UI
- **Decision criteria** — platform, team, testing, tooling, maintainability

---

## 1. Why Platform Matters

### Different Interaction Models

```
┌──────────┬──────────────────────────────────┐
│ Platform │ Primary Interaction              │
├──────────┼──────────────────────────────────┤
│ Web      │ Click, hover, keyboard           │
│ Mobile   │ Touch gestures, swipe, pinch     │
│ Desktop  │ Mouse, keyboard shortcuts,       │
│          │ drag-and-drop, multi-window      │
└──────────┴──────────────────────────────────┘
```

### Different Lifecycles

```
✓ Web — short-lived, mostly stateless per page
✓ Mobile — pause/resume/kill at any time, battery aware
✓ Desktop — long sessions (hours/days), rich memory access
```

### Different Native Capabilities

```
✓ Mobile — sensors, camera, GPS, push, background services
✓ Desktop — file system, multi-monitor, system tray
✓ Web — sandboxed but huge reach
```

### Different Deployment Cycles

```
Web      → ship multiple times per day (CI/CD)
Mobile   → days/weeks (App Store review)
Desktop  → months between releases
```

### Different User Expectations

```
Web users    → fast page loads, responsiveness
Mobile users → fluid animation, offline support
Desktop users→ robust multitasking, keyboard mastery
```

**Pattern choice = designing for the environment your users live in.**

---

## 2. Pattern Recap

```
MVC   → Model-View-Controller     (classic, simple, web-dominant)
MVP   → Model-View-Presenter      (testable, decoupled)
MVVM  → Model-View-ViewModel      (binding-driven, declarative)
MVU   → Model-View-Update         (functional, unidirectional)
VIPER → View-Interactor-Presenter (layered, iOS-clean)
        -Entity-Router
```

---

## 3. Web Applications

### Architectural Drivers

```
✓ Statelessness
   HTTP doesn't carry client state across requests
   → Aligns naturally with MVU / MVVM (explicit state in client)

✓ DOM is a tree of elements
   Modern frameworks treat it as reactive
   → Declarative UI thrives here

✓ Ecosystem diversity
   React, Vue, Angular, Svelte, Solid

✓ Fast deployment
   CI/CD multiple times per day → architecture should support agility
```

### Constraints

```
✗ SEO matters (especially content-driven sites)
✗ Load time = UX
✗ Browser quirks + compatibility
```

### Recommended Patterns for Web

```
┌─────────┬────────────────────────────────────────────┐
│ Pattern │ Fit & Examples                             │
├─────────┼────────────────────────────────────────────┤
│ MVU     │ ★★★★★  React + Redux, Elm                  │
│         │ Unidirectional flow, predictable           │
│ MVVM    │ ★★★★   Angular, Vue                        │
│         │ Two-way binding + templates                │
│ MVC     │ ★★★    Rails, Django, ASP.NET MVC          │
│         │ Server-side rendering still common         │
└─────────┴────────────────────────────────────────────┘
```

### Hybrid in Practice

```
React may follow MVU loop
   + use MVVM-like components (hooks ≈ ViewModel)
   + occasionally MVC on server side rendering layer
```

---

## 4. Mobile Applications

### Architectural Drivers

```
✓ Resource constraints
   Limited memory, CPU, battery
   → No unnecessary rendering, no heavy bg work

✓ Complex lifecycle
   Paused, resumed, rotated, killed by OS
   → Architecture must handle transitions, preserve state

✓ Navigation-driven UX
   Bottom tabs, stack navigators, modals
   → Influences view structure + back stack

✓ Native API access
   Camera, GPS, sensors, push notifications
   → Tight coupling to platform modules

✗ Testing is harder
   Emulators, real devices, OS versions, networks
```

### Recommended Patterns for Mobile

```
┌─────────┬────────────────────────────────────────────┐
│ Platform│ Pattern                                    │
├─────────┼────────────────────────────────────────────┤
│ Android │ MVVM (Jetpack ViewModel + LiveData/Flow)   │
│         │ Compose embraces MVU-like state model      │
│ iOS     │ VIPER (large apps)                         │
│         │ MVVM with SwiftUI                          │
│         │ TCA (Composable Architecture, MVU)         │
└─────────┴────────────────────────────────────────────┘
```

### Why MVVM Won on Android

```
✓ Lifecycle-aware ViewModel survives rotation
✓ LiveData/StateFlow handles reactivity
✓ Data Binding library removes boilerplate
✓ MVP largely replaced
```

### Why VIPER on iOS

```
✓ Strong separation
✓ Each layer testable in isolation
✓ Modular code-bases scale to many teams
✓ Drawback: 5+ files per screen
```

---

## 5. Desktop Applications

### Architectural Drivers

```
✓ Long-running sessions
   Apps stay open for hours, sometimes days
   → Architecture must handle persistent state cleanly

✓ Keyboard + mouse heavy
   Drag-and-drop, context menus, shortcuts
   → Event handling more complex than mobile

✓ Rich components
   Data grids, trees, dropdowns, toolbars
   → Coordinated state across many widgets

✓ Less frequent deploys
   Months between releases
   → Stability + backward compatibility matter
```

### Recommended Patterns for Desktop

```
┌─────────────────┬──────────────────────────────────────┐
│ Framework       │ Pattern                              │
├─────────────────┼──────────────────────────────────────┤
│ WinForms/Java   │ MVC (classic, still widely used)     │
│ Swing/Qt        │ MVC, sometimes MVP                   │
│ WPF / .NET MAUI │ MVVM (native data binding support)   │
│ SwiftUI (macOS) │ MVVM / declarative MVU-like          │
│ Electron        │ Whatever the web stack uses (MVU/MVVM)│
└─────────────────┴──────────────────────────────────────┘
```

### Trend

```
Desktop is modernizing:
   ✗ MVC declining (except in legacy)
   ✓ MVVM dominant in modern frameworks
   ✓ Declarative + state-driven approaches rising
```

---

## 6. How to Decide — The Selection Criteria

### Decision Matrix

```
┌──────────────────────┬────────────────────────────────────┐
│ Factor               │ Lean toward...                     │
├──────────────────────┼────────────────────────────────────┤
│ Reactive UI needed   │ MVU (Redux, Elm, TCA)              │
│ Two-way binding      │ MVVM                               │
│ Server-rendered web  │ MVC                                │
│ Large iOS app        │ VIPER                              │
│ Android (modern)     │ MVVM (Jetpack)                     │
│ Small CRUD app       │ Monolithic MVC                     │
│ Strict separation    │ VIPER / MVP                        │
│ Need testability     │ MVP / MVVM / MVU                   │
│ Team is functional   │ MVU                                │
│ Team is OO           │ VIPER / MVVM / MVP                 │
└──────────────────────┴────────────────────────────────────┘
```

### Five Things to Weigh

```
1. Platform capabilities + constraints
2. Team familiarity + skill set
3. Testing + debugging requirements
4. Tooling + framework support (react→MVU, angular→MVVM, iOS→VIPER)
5. Long-term maintainability
```

### The Mantra

```
Platform • People • Process • Product
        → guide your pattern
```

---

## 7. Cheat Sheet by Stack

```
React          → MVU (Redux/Zustand) or MVVM-ish (hooks)
Vue            → MVVM
Angular        → MVVM (services + components + RxJS)
Svelte         → reactive, MVU-ish via stores
Next.js (SSR)  → MVC on server + MVU on client
Elm            → MVU (it invented it)

Android (new)  → MVVM with Jetpack
Android Compose→ MVU/MVI-style
iOS UIKit      → VIPER / MVVM-C
iOS SwiftUI    → MVVM or TCA (MVU)
React Native   → MVU/Redux dominant
Flutter        → Bloc (MVU-like) or Provider (MVVM)

.NET WPF       → MVVM
.NET MAUI      → MVVM
WinForms       → MVC (legacy)
Qt / Swing     → MVC
Electron       → web stack pattern (MVU/MVVM)
```

---

## 8. Summary

```
✓ Platform strongly influences UI architecture
   Different env → different constraints → different patterns

Web
   ✓ MVU + MVVM dominate
   ✓ MVC still alive on server-side

Mobile
   ✓ Android → MVVM (Jetpack)
   ✓ iOS → VIPER or MVVM (SwiftUI) or TCA

Desktop
   ✓ MVC in legacy frameworks
   ✓ MVVM in modern (WPF, MAUI)
   ✓ Declarative patterns rising

Balance structure with practicality.
No pattern dogmatically — adapt to product + team + platform.
```

---

## 🎤 Interview Q&A

**Q1. Why does React often resemble MVVM despite being described as "just a view library"?**

A: React components with hooks split naturally into UI (return JSX) and state/behavior (useState, useEffect, custom hooks). Custom hooks essentially play the ViewModel role — they expose data and commands to the component. So even without explicit binding, you get a similar separation.

**Q2. Why is MVP largely replaced by MVVM in modern Android?**

A: Jetpack's ViewModel survives configuration changes and integrates with LiveData/StateFlow + Data Binding. MVP required manually pushing updates through view interfaces — Jetpack made that automatic with lifecycle-aware observables, removing MVP's biggest reason to exist.

**Q3. When would you choose VIPER over MVVM in iOS?**

A: For very large apps with complex navigation (10+ developers, dozens of screens, strict testability). VIPER's 5-layer overhead pays off when modularity and strict separation matter more than velocity. For small/medium apps, MVVM is lighter and gets you there faster.

**Q4. Why is MVC still used on the server side of modern web apps?**

A: HTTP is stateless; the server handles a request and returns a response. That maps perfectly to a controller routing input, the model handling data, and the view rendering HTML. Server-rendered apps (Rails, Django) still gain from MVC because the round-trip nature doesn't need reactive state.

**Q5. How do you choose between MVU and MVVM for a new project?**

A: If the framework natively supports two-way binding (Vue, Angular, WPF), lean MVVM. If you need predictable state for complex UIs with many interactions or time-travel debugging (web SPAs, large client apps), lean MVU. Team mindset matters too — functional teams prefer MVU; OO teams often prefer MVVM.

---

## 🔗 Related

- Previous: [03_Offline_First_Sync.md](03_Offline_First_Sync.md)
- Next section: [Section 9 — Architectural Decision-Making](../Section_09_Architectural_Decision_Making/)
