# Lecture 4: Micro-frontends & UI Composition

> *"What microservices did to the backend, micro-frontends do to the UI."*

**Section 3 — Distributed Systems & Service Architectures**

---

## 🎯 Is Lecture Mein Kya Seekhenge?

- **What are micro-frontends** — modular thinking for UI
- **Why micro-frontends** — scaling frontend teams
- **High-level architecture** — shell + remotes
- **Frontend routing strategies** — shell, independent, fragment
- **Communication patterns** — URL, events, shared state
- **Shared components** — design systems
- **Deployment models** — monorepo vs polyrepo
- **Composition strategies** — build-time, server-side, run-time
- **Evolution from monolithic SPA** — gradual migration
- **Challenges & best practices**

---

## 1. What Are Micro-frontends?

### Definition

**Micro-frontends = Splitting a frontend application into independently developed, tested, and deployed pieces that compose into a unified user experience.**

### Visual

```
┌───────────────────────────────────────────────────────────────┐
│                        BROWSER                                 │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │              Shell Application (Host)                    │  │
│  │  ┌──────────┐                                            │  │
│  │  │  Header  │ ◄── Loaded from Team A (React 18)         │  │
│  │  └──────────┘                                            │  │
│  │  ┌────────────────────────┬────────────────────────┐    │  │
│  │  │   Catalog              │   Recommendations       │    │  │
│  │  │   (Team B - Vue 3)     │   (Team C - React 17)   │    │  │
│  │  └────────────────────────┴────────────────────────┘    │  │
│  │  ┌──────────┐                                            │  │
│  │  │  Cart    │ ◄── Loaded from Team D (Svelte)           │  │
│  │  └──────────┘                                            │  │
│  │  ┌──────────┐                                            │  │
│  │  │  Footer  │ ◄── Loaded from Team A                    │  │
│  │  └──────────┘                                            │  │
│  └─────────────────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────────────────┘
```

### Core Idea

```
🎯 What microservices do for backend:
   • Split monolith into independent services
   • Each team owns end-to-end
   • Independent deploy & scale

   ↓ Apply same idea to FRONTEND

🎯 Micro-frontends:
   • Split monolithic SPA into pieces
   • Each team owns front + back (full-stack)
   • Independent deploy & scale
```

---

## 2. Why Use Micro-frontends?

### Reason 1: Scale Frontend Teams

```
Small team scenario (1-5 devs):
   ✓ Monolithic SPA works fine
   ✓ Everyone knows the codebase
   ✓ No coordination overhead

Large team scenario (15+ devs):
   ✗ Merge conflicts daily
   ✗ Build times grow (15+ minutes)
   ✗ Deployment coordination painful
   ✗ One team blocks another
   
   → Micro-frontends solve these problems
```

### Reason 2: Team Autonomy

```
Without micro-frontends:
   "Team A wants to upgrade React 17 → 18"
   "But Team B has dependency conflicts"
   "Team C has features pending"
   → Upgrade blocked for months

With micro-frontends:
   Team A: Upgrade their MFE to React 18 ✓
   Team B: Stays on React 17 (no impact)
   Team C: Independent decision
```

### Reason 3: Independent Deployments

```
Old way (Monolithic SPA):
   Tuesday 2 AM: Big release
   ├─ Deploy entire frontend
   ├─ All teams sync
   ├─ One bug = full rollback

New way (Micro-frontends):
   Anytime, multiple times a day:
   ├─ Team A deploys Header v2.1
   ├─ Team B deploys Catalog v3.5
   ├─ Team C rolls back Cart v4.2 → only cart affected
```

### Reason 4: Match Backend Architecture

```
Backend microservices ──► Multiple frontend MFEs
                          
Orders service        ──► Orders MFE      (same team)
Payment service       ──► Payment MFE     (same team)
Search service        ──► Search MFE      (same team)
   
Full-stack team ownership.
```

### Reason 5: Polyglot Frontend

```
Different parts can use different tech:
   • Header: Plain HTML (SEO-critical)
   • Catalog: React (rich interactions)
   • Checkout: Svelte (small bundle)
   • Reports: Vue (charting libs)
   
Right tool for the job!
```

---

## 3. High-Level Architecture

### The Shell + Remotes Pattern

```
┌──────────────────────────────────────────────────────────────┐
│                   SHELL APPLICATION (Host)                    │
│                                                                │
│   Responsibilities:                                            │
│   • Top-level routing                                          │
│   • Authentication / Authorization                             │
│   • Global layout (header, footer)                             │
│   • Loading remote micro-frontends                             │
│   • Shared dependencies (React, design system)                 │
│   • Cross-MFE communication backbone                           │
└──────────────────────────────────────────────────────────────┘
              ▲                  ▲                  ▲
              │                  │                  │
              │  Loads at        │  Loads at        │  Loads at
              │  runtime         │  runtime         │  runtime
              │                  │                  │
   ┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐
   │  Remote MFE #1   │ │  Remote MFE #2   │ │  Remote MFE #3   │
   │                  │ │                  │ │                  │
   │  Catalog         │ │  Cart            │ │  Profile         │
   │  Team A          │ │  Team B          │ │  Team C          │
   │  React 18        │ │  Vue 3           │ │  React 17        │
   │  Own CI/CD       │ │  Own CI/CD       │ │  Own CI/CD       │
   └──────────────────┘ └──────────────────┘ └──────────────────┘
```

### Key Components

```
1. SHELL APPLICATION
   • The "container" everyone sees
   • Loads remotes dynamically
   • Provides global utilities

2. REMOTE MICRO-FRONTENDS
   • Independently built & deployed
   • Loaded into shell at runtime
   • Can use different frameworks

3. SHARED DESIGN SYSTEM
   • Common UI components
   • Distributed as versioned npm package
   • Ensures visual consistency

4. EVENT BUS / SHARED STATE
   • Cross-MFE communication
   • Custom events, Redux, RxJS, etc.

5. SHARED INFRASTRUCTURE
   • CDN for hosting
   • Authentication
   • Analytics
```

---

## 4. Composition Strategies

### Strategy 1: Build-Time Composition

```
Each MFE published as npm package.
Shell installs them as dependencies.

   shell-app/
   ├── package.json
   │   "dependencies": {
   │     "@company/catalog": "^1.2.0",
   │     "@company/cart": "^2.5.0",
   │     "@company/profile": "^1.0.0"
   │   }
   
   At build time: bundled together
   At deploy: single artifact

✓ Simple
✓ Type-safe (TypeScript)
✗ Need to redeploy shell to update MFEs
✗ Not truly independent
```

### Strategy 2: Server-Side Composition

```
Fragments assembled at server/CDN edge.

   Browser requests /catalog
        ↓
   Edge server (Nginx, Varnish, Tailor.js)
        ↓
   ┌─────────────────────────────────────┐
   │ Fetch from MFE servers in parallel: │
   │   • Header HTML from team-a.com    │
   │   • Catalog HTML from team-b.com   │
   │   • Footer HTML from team-a.com    │
   └─────────────────────────────────────┘
        ↓
   Combined HTML sent to browser

✓ SEO-friendly (server-rendered)
✓ Fast first paint
✗ Server-side complexity
✗ Edge caching tricky
```

### Strategy 3: Runtime Composition (MOST POPULAR)

```
Shell loads MFEs in browser via JavaScript.

Approaches:
   • Webpack Module Federation (Webpack 5+)
   • Single-SPA framework
   • iframe-based isolation
   • Web Components

✓ Truly independent
✓ Each MFE deploys separately
✗ More complex setup
✗ Bundle duplication possible
```

### Comparison

```
┌────────────────┬─────────────┬─────────────┬─────────────┐
│  STRATEGY      │ INDEPENDENT │ COMPLEXITY  │ PERFORMANCE │
│                │ DEPLOYMENT  │             │             │
├────────────────┼─────────────┼─────────────┼─────────────┤
│ Build-time     │ ✗           │ Low         │ Best        │
│ Server-side    │ ✓           │ High        │ Best (SEO)  │
│ Run-time       │ ✓           │ Medium      │ Good        │
└────────────────┴─────────────┴─────────────┴─────────────┘
```

---

## 5. Frontend Routing Strategies

### Strategy 1: Shell-Based Routing

```
Shell owns ALL routing.

   URL: /catalog/iphone-15
   
   Shell router:
   ├─ /catalog/* → Load CatalogMFE
   ├─ /cart      → Load CartMFE
   └─ /profile/* → Load ProfileMFE

Inside each MFE:
   Receives only relevant path
   Doesn't manage URL itself

✓ Centralized control
✓ Easy to understand
✗ Shell knows about all MFEs
```

### Strategy 2: Independent Routing

```
Each MFE handles its own routes.

   Shell: 
   ├─ /catalog/* → Mount CatalogMFE (passes /*)
   └─ Catalog manages /catalog/iphone-15, /catalog/laptops, etc.

✓ More autonomy for MFEs
✗ Coordination needed for URL structure
```

### Strategy 3: Fragment-Based (No URL Routing)

```
Multiple MFEs on same page, no route change.

   Dashboard page:
   ┌──────────────────────────────────┐
   │  Sales Widget (MFE A)            │
   ├──────────────────────────────────┤
   │  Inventory Widget (MFE B)        │
   ├──────────────────────────────────┤
   │  Reviews Widget (MFE C)          │
   └──────────────────────────────────┘

✓ No URL coordination needed
✗ Need fragment-level state management
```

### Hybrid Approach (Common)

```
Many real systems mix:
   • Shell does top-level routing
   • MFEs do sub-route routing
   • Some MFEs work as widgets
```

---

## 6. Communication Patterns

### Pattern 1: URL-Based Communication

```
Simplest: use URL/query params.

   User clicks "Add to cart" in CatalogMFE
        ↓
   URL change: /cart?item=123&qty=1
        ↓
   CartMFE reads URL, adds item

✓ Stateless
✓ Works across hard refresh
✗ Limited to route-related data
```

### Pattern 2: Custom DOM Events

```javascript
// CatalogMFE publishes
window.dispatchEvent(new CustomEvent('cart:item-added', {
    detail: { productId: 123, quantity: 1 }
}));

// CartMFE listens
window.addEventListener('cart:item-added', (e) => {
    updateCart(e.detail);
});

// Header (cart badge) also listens
window.addEventListener('cart:item-added', (e) => {
    incrementCartCount();
});
```

```
✓ Decoupled (publisher doesn't know subscribers)
✓ Multiple subscribers
✗ Not type-safe
✗ Can be hard to debug
```

### Pattern 3: Shared State Store

```javascript
// Singleton on window
window.__APP_STATE__ = new ReactiveStore({
    cart: { items: [] },
    user: { id: null }
});

// MFE A
window.__APP_STATE__.dispatch({ type: 'ADD_TO_CART', item: {...} });

// MFE B subscribes
window.__APP_STATE__.subscribe(state => {
    renderCart(state.cart);
});
```

```
✓ Strong consistency
✓ Time-travel debugging
✗ Coupling to store
✗ Tight runtime dependency
```

### Pattern 4: Backend-for-Frontend (BFF)

```
Communication via backend:

   MFE A → BFF A ──┐
                    ├─→ Shared backend service
   MFE B → BFF B ──┘
   
   State synced via backend (single source of truth)

✓ No frontend coupling
✓ Single source of truth
✗ More API calls
```

### Pattern Comparison

```
┌──────────────────┬─────────────┬──────────────┬──────────────┐
│  PATTERN         │ COUPLING    │ COMPLEXITY   │ USE CASE     │
├──────────────────┼─────────────┼──────────────┼──────────────┤
│ URL-based        │ Low         │ Low          │ Navigation   │
│ Custom Events    │ Low         │ Medium       │ Async notify │
│ Shared State     │ High        │ Medium       │ Real-time UI │
│ BFF              │ Low         │ High         │ Data sync    │
└──────────────────┴─────────────┴──────────────┴──────────────┘
```

---

## 7. Shared Components & Design System

### The Problem

```
Without shared components:
   • Team A's "Button" looks different from Team B's
   • Spacing, colors inconsistent
   • Users see fragmented UI
   • Brand identity weakens
```

### The Solution: Design System

```
┌──────────────────────────────────────────────────────────┐
│              @company/design-system                       │
│  (Versioned npm package)                                  │
│                                                            │
│  Components:                                              │
│  • Button, Input, Modal, Card                            │
│  • Form components                                        │
│  • Navigation                                             │
│  • Icons                                                  │
│                                                            │
│  Tokens:                                                  │
│  • Colors, Typography, Spacing                           │
│  • Shadows, Radii, Breakpoints                           │
│                                                            │
│  Distribution:                                            │
│  • Published as @company/design-system                    │
│  • Each MFE installs the version they need                │
└──────────────────────────────────────────────────────────┘
                       ▲
        ┌──────────────┼──────────────┐
        │              │              │
   ┌─────────┐   ┌─────────┐   ┌─────────┐
   │ MFE A   │   │ MFE B   │   │ MFE C   │
   │ v1.2.0  │   │ v1.2.0  │   │ v1.1.0  │
   └─────────┘   └─────────┘   └─────────┘
```

### Best Practices

```
✓ Components should be STATELESS
✓ Use design tokens (CSS variables)
✓ Storybook for documentation
✓ Visual regression tests
✓ Semantic versioning
✓ Gradual rollout (allow version skew)
✗ Don't share runtime state in components
```

---

## 8. Deployment Models

### Monorepo

```
Single repo, all MFEs inside.

monorepo/
├── shell/
├── mfes/
│   ├── catalog/
│   ├── cart/
│   └── profile/
└── packages/
    └── design-system/

✓ Easy refactoring
✓ Shared tooling
✓ Atomic commits
✗ Coupling risks
✗ Slow CI without smart caching

Tools: Nx, Turborepo, Lerna, Bazel
```

### Polyrepo

```
Each MFE in its own repo.

catalog-mfe/    (own repo)
cart-mfe/       (own repo)
profile-mfe/    (own repo)
design-system/  (own repo)
shell-app/      (own repo)

✓ True independence
✓ Independent CI/CD
✗ Code sharing harder
✗ Cross-MFE changes need multi-PR

Best for: Independent teams, polyglot stacks
```

### Hybrid

```
✓ Domain monorepos
   • orders-domain/ (catalog + cart)
   • users-domain/ (profile + auth)
   
✓ Shared monorepo
   • design-system + utilities
```

### Independent CI/CD

```yaml
# .github/workflows/catalog-mfe.yml
name: Deploy Catalog MFE
on:
  push:
    paths: ['apps/catalog/**']  # Triggers ONLY if catalog changes
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Build
        run: |
          cd apps/catalog
          npm install
          npm run build
      - name: Deploy to CDN
        run: |
          aws s3 sync dist/ s3://mfe-catalog/
      - name: Invalidate cache
        run: aws cloudfront create-invalidation \
             --distribution-id $CF_ID --paths "/catalog/*"
```

---

## 9. Webpack Module Federation (Deep Dive)

### What Is It?

```
Webpack Module Federation = Runtime sharing of JS modules
across separately-deployed applications.

Released in Webpack 5 (2020).
The most popular MFE technology today.
```

### Visual

```
┌─────────────────────────────────────────────────────────────┐
│  SHELL APP                                                   │
│                                                              │
│  webpack config:                                             │
│    remotes: {                                                │
│      catalog: 'catalog@http://localhost:3001/remoteEntry.js'│
│      cart: 'cart@http://localhost:3002/remoteEntry.js'      │
│    }                                                         │
│                                                              │
│  At runtime:                                                 │
│    import('catalog/Page') ──► fetches from URL              │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  CATALOG MFE                                                 │
│                                                              │
│  webpack config:                                             │
│    name: 'catalog',                                          │
│    filename: 'remoteEntry.js',                               │
│    exposes: {                                                │
│      './Page': './src/CatalogPage'                          │
│    }                                                         │
└─────────────────────────────────────────────────────────────┘
```

### Shared Dependencies

```javascript
// Shell webpack.config.js
new ModuleFederationPlugin({
    name: 'shell',
    remotes: {
        catalog: 'catalog@http://localhost:3001/remoteEntry.js',
    },
    shared: {
        react: { 
            singleton: true,           // ONE React instance
            requiredVersion: '^18.0.0' // version constraint
        },
        'react-dom': { singleton: true, requiredVersion: '^18.0.0' },
    },
});
```

### Benefits

```
✓ True runtime composition
✓ Shared dependencies (no React duplicates)
✓ Independent deploys
✓ Lazy loading built-in
✗ Webpack-specific (now also in Vite/Rspack)
✗ Learning curve
```

---

## 10. Evolution from Monolithic SPA

### Phase 1: Monolithic SPA

```
ecommerce-app/
└── src/
    ├── catalog/
    ├── cart/
    ├── profile/
    ├── orders/
    └── search/

All in one React app.
Single deployment.
```

### Phase 2: Extract First MFE

```
ecommerce-app/         ←── shell
└── src/
    ├── cart/          (still inside)
    ├── profile/       (still inside)
    └── orders/        (still inside)

cart-mfe/              ←── extracted!
└── src/
    └── CartPage.tsx
    
Now Cart is independent.
Shell loads it via Module Federation.
```

### Phase 3: More Extraction

```
Each domain becomes an MFE:
   • shell-app
   • catalog-mfe
   • cart-mfe
   • profile-mfe
   • orders-mfe
   • search-mfe

Each team owns one.
```

### Phase 4: Full-Stack Team Ownership

```
Each team owns FRONT + BACK:

Team A: Catalog
   ├─ catalog-mfe         (frontend)
   ├─ catalog-service     (backend)
   └─ catalog-db          (data)

Team B: Cart
   ├─ cart-mfe
   ├─ cart-service
   └─ cart-db

Etc.

End-to-end ownership = true autonomy.
```

---

## 11. Challenges

### Challenge 1: Setup Complexity

```
✗ More tooling than monolith
✗ Module Federation config
✗ Shared design system
✗ Cross-MFE communication
✗ Multiple CI/CD pipelines

→ Justify with team scale!
```

### Challenge 2: Visual Consistency

```
Risk: Each team builds slightly differently
   → UI drift
   → Inconsistent UX
   
Solution:
   ✓ Strong design system
   ✓ Visual regression tests
   ✓ Design reviews
```

### Challenge 3: Performance

```
Multiple bundles can cause:
   ✗ Duplicate code (React loaded twice?)
   ✗ Slow first paint
   ✗ Extra network requests

Solutions:
   ✓ Module Federation shared singletons
   ✓ Server-side rendering for first paint
   ✓ Lazy load below-the-fold MFEs
   ✓ HTTP/2 multiplexing
```

### Challenge 4: Versioning

```
What if:
   • Catalog uses React 17
   • Cart uses React 18
   • Both run on same page

→ Conflicts possible!

Strategies:
   ✓ Coordinate major versions
   ✓ Use singleton in Module Federation
   ✓ iframe isolation for incompatible versions
```

### Challenge 5: Debugging

```
Bug in production:
   "Where is this error coming from?"
   
   - Shell? Catalog MFE? Cart MFE?
   - Different teams own each
   - Different release cycles

Solutions:
   ✓ Source maps
   ✓ Error boundaries per MFE
   ✓ Tag errors with MFE name
   ✓ Centralized error tracking (Sentry)
```

---

## 12. Best Practices

### Practice 1: Favor Composition Over Duplication

```
✗ DON'T: Each MFE rebuilds common UI
   → Inconsistent
   → Wasteful

✅ DO: Share via design system
   → Consistent
   → Versioned
```

### Practice 2: Minimize Shared Runtime State

```
✗ DON'T: Global Redux store everyone reads/writes
   → Tight coupling

✅ DO: Isolated state per MFE
   → Events for cross-MFE communication
   → URL for navigation state
```

### Practice 3: Define Clear MFE Boundaries

```
A good MFE:
   ✓ Owns a clear business capability
   ✓ Has well-defined public interface
   ✓ Can be developed in isolation
   ✓ Can be deployed independently

Anti-pattern:
   ✗ MFE that needs others to function
   ✗ MFE without clear ownership
```

### Practice 4: Don't Couple MFEs Tightly

```
✗ MFE A directly imports from MFE B's internals
✗ MFE A depends on MFE B being on page

✅ MFE A uses event bus
✅ MFE A degrades gracefully without B
```

### Practice 5: Start Modular, Then Extract

```
Just like modular monolith for backend:

Phase 1: Monolithic SPA (modularized internally)
Phase 2: Extract first MFE when justified
Phase 3: Gradually extract more
Phase 4: Mature MFE architecture

Don't start with 10 MFEs on Day 1!
```

---

## 13. When to Use Micro-frontends

### ✅ Good Fit

```
✓ Large frontend team (15+ developers)
✓ Multiple product lines share UI
✓ Need different release cycles per area
✓ Backend already microservices
✓ Different parts have different tech needs
✓ Strong design system in place
✓ DevOps maturity exists
```

### ❌ Bad Fit

```
✗ Small team (< 10 devs)
✗ Early-stage product
✗ Simple application
✗ No design system
✗ Limited DevOps
✗ "Microservices, but for UI"
   (cargo culting)
```

### Decision Tree

```
START
  │
  ├─ Frontend team < 10 people?
  │    YES → Monolithic SPA (modularized internally)
  │    NO  → Continue
  │
  ├─ Do you have a design system?
  │    NO  → Build that first
  │    YES → Continue
  │
  ├─ Multiple teams blocking each other?
  │    NO  → Stay monolithic
  │    YES → Continue
  │
  ├─ Backend already microservices?
  │    NO  → Maybe match backend first
  │    YES → Continue
  │
  └─ Consider micro-frontends
```

---

## 14. Tools & Frameworks

### Run-Time Composition

```
✓ Webpack Module Federation (most popular)
✓ Single-SPA (framework-agnostic)
✓ Bit (component-level)
✓ qiankun (Alibaba's framework)
```

### Server-Side Composition

```
✓ Podium (FINN.no)
✓ Tailor.js (Zalando)
✓ Mosaic (Zalando)
✓ ESI (Edge Side Includes)
```

### Iframe-Based

```
✓ Project Mosaic
✓ Web Components (Custom Elements)
```

### Monorepo Tools

```
✓ Nx (most powerful)
✓ Turborepo (Vercel)
✓ Lerna (older but stable)
✓ Rush (Microsoft)
```

---

## 15. Real-World Examples

### Example 1: Spotify

```
✓ Pioneer of micro-frontends
✓ Each "tribe" owns features
✓ Multiple players within one app
✓ Custom-built composition
```

### Example 2: IKEA

```
✓ E-commerce micro-frontends
✓ Different teams own product pages
✓ Shared checkout MFE
✓ Module Federation
```

### Example 3: Zalando

```
✓ Early adopter (Mosaic)
✓ Server-side composition
✓ Multiple country-specific MFEs
```

### Example 4: SAP

```
✓ Luigi framework
✓ Iframe-based isolation
✓ Multi-tenant enterprise UI
```

---

## 16. Summary — Key Takeaways

```
┌──────────────────────────────────────────────────────────────┐
│  ✅ Micro-frontends = modular frontend architecture           │
│  ✅ Independent dev, deploy, and own per piece                │
│  ✅ Shell + Remotes is the dominant pattern                   │
│  ✅ Module Federation is the most popular technology          │
│  ✅ Design system ensures visual consistency                  │
│  ✅ Communication via URL, events, or shared state            │
│  ✅ Not for everyone — significant complexity                 │
│  ✅ Match team scale and backend architecture                 │
└──────────────────────────────────────────────────────────────┘
```

### The Golden Rules

```
1. Start with monolithic SPA (modularized internally)
2. Extract MFEs ONLY when team size demands it
3. Strong design system is non-negotiable
4. Minimize cross-MFE coupling
5. Independent deployments = the goal
6. Match backend service boundaries
```

---

## 🎬 What's Next?

In **Lecture 5**, we'll look at **real-world use cases** for distributed systems — SaaS, fintech, e-commerce, social media — and see how all these patterns come together.

> **Practical file:** [04_Practical_Hands_On.md](04_Practical_Hands_On.md)

---

## 📚 References

- *Micro Frontends* — Cam Jackson (martinfowler.com)
- *Building Micro-Frontends* — Luca Mezzalira
- Module Federation docs (webpack.js.org)
- Single-SPA documentation
- ThoughtWorks Technology Radar (micro-frontends)
