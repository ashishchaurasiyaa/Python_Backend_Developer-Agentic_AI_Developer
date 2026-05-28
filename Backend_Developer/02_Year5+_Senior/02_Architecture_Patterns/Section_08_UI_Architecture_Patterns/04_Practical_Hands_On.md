# Lecture 4 — Practical Hands-On: Selecting UI Patterns by Platform

> **Theory file:** [04_Selecting_UI_Patterns_By_Platform.md](04_Selecting_UI_Patterns_By_Platform.md)

---

## 🎯 Is Practical Mein Kya Banayenge?

Same feature ("user profile screen") built three ways for three platforms:

1. ✅ **Web** — React with hooks (MVU/MVVM-ish)
2. ✅ **Android-style** — Python pseudo-code mimicking Jetpack MVVM
3. ✅ **iOS-style** — VIPER skeleton in Python
4. ✅ **Decision worksheet** — fill in for your own project

By end: aap apne project ke liye **right pattern justify** kar sakte ho.

---

## 1. Project Structure

```
platform_patterns_demo/
├── web_react/
│   ├── package.json
│   ├── src/
│   │   ├── store.js           # Redux store (MVU)
│   │   ├── slices/
│   │   │   └── profileSlice.js
│   │   ├── components/
│   │   │   └── Profile.jsx    # View
│   │   └── App.jsx
│   └── README.md
│
├── android_pyjetpack/         # Python pseudo-code mimicking Jetpack
│   ├── viewmodel.py
│   ├── repository.py
│   ├── activity.py            # The "View"
│   └── livedata.py
│
├── ios_viper_py/
│   ├── (uses Section 8 lecture 2 viper_python)
│   └── README.md
│
└── DECISION_WORKSHEET.md
```

---

## 2. 🌐 Web — React + Redux (MVU)

### `web_react/src/slices/profileSlice.js`

```javascript
import { createSlice, createAsyncThunk } from '@reduxjs/toolkit'

// MVU: Message = action, Update = reducer, Model = state
export const fetchProfile = createAsyncThunk(
    'profile/fetch',
    async (userId) => {
        const res = await fetch(`/api/users/${userId}`)
        if (!res.ok) throw new Error('User not found')
        return await res.json()
    }
)

const profileSlice = createSlice({
    name: 'profile',
    initialState: { data: null, loading: false, error: null },
    reducers: {
        clear(state) {
            state.data = null
            state.error = null
        },
    },
    extraReducers: (builder) => {
        builder
            .addCase(fetchProfile.pending, (s) => { s.loading = true; s.error = null })
            .addCase(fetchProfile.fulfilled, (s, a) => { s.loading = false; s.data = a.payload })
            .addCase(fetchProfile.rejected, (s, a) => { s.loading = false; s.error = a.error.message })
    },
})

export const { clear } = profileSlice.actions
export default profileSlice.reducer
```

### `web_react/src/store.js`

```javascript
import { configureStore } from '@reduxjs/toolkit'
import profileReducer from './slices/profileSlice'

export const store = configureStore({
    reducer: { profile: profileReducer },
})
```

### `web_react/src/components/Profile.jsx`

```jsx
import { useEffect } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { fetchProfile, clear } from '../slices/profileSlice'

export default function Profile({ userId }) {
    const dispatch = useDispatch()
    const { data, loading, error } = useSelector((s) => s.profile)

    useEffect(() => {
        dispatch(fetchProfile(userId))
        return () => dispatch(clear())
    }, [userId, dispatch])

    if (loading) return <p>Loading...</p>
    if (error) return <p>❌ {error}</p>
    if (!data) return null
    return (
        <div>
            <h2>{data.name}</h2>
            <p>✉ {data.email}</p>
        </div>
    )
}
```

### Why This Is MVU/MVVM-ish

```
✓ Store         → Model
✓ Action        → Message
✓ Reducer       → Update
✓ Component     → View (binds to state via useSelector)
✓ Custom hook   → ViewModel-ish layer (if extracted)
```

---

## 3. 📱 Android-style — Python "Jetpack" MVVM

### `android_pyjetpack/livedata.py`

```python
class LiveData:
    """Simplified LiveData: observable value + observers."""

    def __init__(self, value=None):
        self._value = value
        self._observers = []

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, new):
        self._value = new
        for cb in self._observers:
            cb(new)

    def observe(self, callback):
        self._observers.append(callback)
        callback(self._value)
```

### `android_pyjetpack/repository.py`

```python
class UserRepository:
    """Single source of truth — abstracts DB + network."""

    _data = {
        1: {"id": 1, "name": "Alice", "email": "a@x.com"},
        2: {"id": 2, "name": "Bob",   "email": "b@x.com"},
    }

    def fetch(self, user_id):
        return self._data.get(user_id)
```

### `android_pyjetpack/viewmodel.py`

```python
from .livedata import LiveData
from .repository import UserRepository


class ProfileViewModel:
    """Lifecycle-agnostic. No View knowledge."""

    def __init__(self, repo: UserRepository):
        self._repo = repo
        self.profile = LiveData(None)
        self.loading = LiveData(False)
        self.error = LiveData(None)

    def load(self, user_id):
        self.loading.value = True
        self.error.value = None
        data = self._repo.fetch(user_id)
        self.loading.value = False
        if data is None:
            self.error.value = "User not found"
        else:
            self.profile.value = data
```

### `android_pyjetpack/activity.py`

```python
from .viewmodel import ProfileViewModel
from .repository import UserRepository


class ProfileActivity:
    """The 'View' — observes LiveData."""

    def __init__(self):
        self.vm = ProfileViewModel(UserRepository())
        self._bind()

    def _bind(self):
        self.vm.profile.observe(self._render_profile)
        self.vm.loading.observe(self._render_loading)
        self.vm.error.observe(self._render_error)

    def _render_profile(self, p):
        if p:
            print(f"👤 {p['name']}\n   ✉ {p['email']}")

    def _render_loading(self, on):
        if on:
            print("⏳ loading...")

    def _render_error(self, msg):
        if msg:
            print(f"❌ {msg}")

    def on_create(self, user_id):
        self.vm.load(user_id)


if __name__ == "__main__":
    a = ProfileActivity()
    a.on_create(1)
    print("---")
    a.on_create(999)
```

### Run

```bash
python -m android_pyjetpack.activity
```

### Why This Mirrors Jetpack MVVM

```
✓ ViewModel       → Jetpack ViewModel (survives config changes)
✓ LiveData        → LiveData / StateFlow
✓ Repository      → Repository pattern
✓ Activity        → Observes, never directly modifies state
✓ Survives rotation → just reattach observers in real app
```

---

## 4. 🍎 iOS-style — VIPER (Reuse Lecture 2 Code)

The VIPER skeleton we built in [Lecture 2 — Practical](02_Practical_Hands_On.md#4--viper-skeleton--user-profile-module) is the iOS-style implementation. Re-run it to compare:

```bash
python -m viper_python.main
```

### Side-by-Side: Same Feature, Three Patterns

```
┌──────────┬──────────────────────────────────────────────┐
│ Platform │ Files Touched to Add 1 Field to Profile     │
├──────────┼──────────────────────────────────────────────┤
│ React    │ 2 (slice, component)                        │
│  (MVU)   │                                              │
├──────────┼──────────────────────────────────────────────┤
│ Android  │ 3 (model, viewmodel, layout/binding)        │
│  (MVVM)  │                                              │
├──────────┼──────────────────────────────────────────────┤
│ iOS      │ 5+ (entity, interactor, presenter, view,    │
│  (VIPER) │     view-model struct)                       │
└──────────┴──────────────────────────────────────────────┘
```

This is exactly the trade-off: **simplicity vs structure**.

---

## 5. 📋 Decision Worksheet

### `DECISION_WORKSHEET.md`

```markdown
# UI Architecture Decision — Project: ____________

## 1. Platform
- [ ] Web (SPA)
- [ ] Web (server-rendered)
- [ ] Android
- [ ] iOS
- [ ] Cross-platform (React Native / Flutter / MAUI)
- [ ] Desktop (WPF / Electron / Qt / SwiftUI macOS)

## 2. Scale / Complexity
- [ ] Simple CRUD (< 10 screens)
- [ ] Medium (10–50 screens)
- [ ] Large (50+ screens, many teams)

## 3. Team Strength
- [ ] Mostly functional / Redux experience
- [ ] Mostly OO / classical OOP
- [ ] Mixed
- [ ] Junior-heavy (favors simpler patterns)

## 4. Testing Priority
- [ ] Critical — need 80%+ UI logic coverage
- [ ] Important — main flows tested
- [ ] Light — manual QA mostly

## 5. Tooling / Framework Native Support
- [ ] Two-way data binding available (MVVM ideal)
- [ ] Strong state-management story (MVU ideal)
- [ ] Templates / server-side rendering (MVC ideal)

## 6. Lifecycle Complexity
- [ ] Rotation / process death (mobile)
- [ ] Long-running session (desktop)
- [ ] Short-lived (web page)

## 7. Recommended Pattern
> Based on above ☐ MVC  ☐ MVP  ☐ MVVM  ☐ MVU  ☐ VIPER  ☐ Hybrid

## 8. Justification (write 2–3 sentences)
_____________________________________________________________________
_____________________________________________________________________
```

---

## 6. ✅ Hands-On Checklist

```
□ Ran React + Redux profile (MVU)
□ Ran Python Jetpack-style profile (MVVM)
□ Ran VIPER profile (from Lecture 2)
□ Counted files per pattern for the same feature
□ Filled in DECISION_WORKSHEET for your current project
□ Justified the pattern in 2–3 sentences
```

---

## 🔗 Next

- Next section: [Section 9 — Architectural Decision-Making](../Section_09_Architectural_Decision_Making)
