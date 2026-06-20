# S — Single Responsibility Principle (SRP)

## Statement (Robert C. Martin)

> *A class should have one, and only one, reason to change.*

The phrase that matters: **reason to change**. Not "do one thing" — that's too vague. A class should serve **one stakeholder** (or one *axis* of change). If marketing changes how reports look AND finance changes how taxes compute, those are two reasons, two classes.

## The bad version — God class

```python
# BAD: User class does auth, persistence, email, and HTML rendering
class User:
    def __init__(self, name, email, password):
        self.name, self.email, self.password = name, email, password

    def hash_password(self):
        import hashlib
        return hashlib.sha256(self.password.encode()).hexdigest()

    def save_to_db(self, conn):
        conn.execute(
            "INSERT INTO users(name,email,pw) VALUES (?,?,?)",
            (self.name, self.email, self.hash_password()),
        )

    def send_welcome_email(self, smtp):
        smtp.send(self.email, subject="Welcome", body=f"Hi {self.name}")

    def to_profile_html(self):
        return f"<h1>{self.name}</h1><p>{self.email}</p>"
```

**Reasons this class will change:**
1. Security team changes the hash algorithm.
2. DBA migrates from SQLite to Postgres.
3. Marketing rewrites the welcome email copy.
4. Frontend team redesigns the profile page.

Four stakeholders, four reasons, one class. Every change risks breaking the others.

## The fixed version

```python
# Pure data
from dataclasses import dataclass

@dataclass
class User:
    name: str
    email: str
    password_hash: str

# Reason 1: hashing
class PasswordHasher:
    def hash(self, raw: str) -> str:
        import hashlib
        return hashlib.sha256(raw.encode()).hexdigest()

# Reason 2: persistence
class UserRepository:
    def __init__(self, conn):
        self.conn = conn
    def save(self, user: User) -> None:
        self.conn.execute(
            "INSERT INTO users(name,email,pw) VALUES (?,?,?)",
            (user.name, user.email, user.password_hash),
        )

# Reason 3: email
class WelcomeEmailer:
    def __init__(self, smtp):
        self.smtp = smtp
    def send(self, user: User) -> None:
        self.smtp.send(user.email, subject="Welcome", body=f"Hi {user.name}")

# Reason 4: rendering
class UserHTMLRenderer:
    def render(self, user: User) -> str:
        return f"<h1>{user.name}</h1><p>{user.email}</p>"

# Orchestrator (a use-case / service)
class RegisterUser:
    def __init__(self, hasher, repo, emailer):
        self.hasher, self.repo, self.emailer = hasher, repo, emailer
    def __call__(self, name, email, raw_pw):
        user = User(name, email, self.hasher.hash(raw_pw))
        self.repo.save(user)
        self.emailer.send(user)
        return user
```

Now each class has **one reason to change**, and `RegisterUser` is the use-case orchestrator (which itself changes only when the *flow* changes).

## How SRP shows up in backend code

| Smell | Fix |
|---|---|
| Django model with `def send_email`, `def export_csv`, `def calculate_tax` | Move each to its own service/manager |
| FastAPI route handler with 300 lines of business logic | Extract to a service class; route just calls it |
| `UserService` that does auth + billing + notifications | Split: `AuthService`, `BillingService`, `NotificationService` |
| One `utils.py` with 80 unrelated helpers | Group by axis: `time_utils.py`, `string_utils.py`, … |

## Common pitfalls

1. **Splitting too eagerly.** A 20-line class with 2 methods rarely needs SRP. Wait for the smell.
2. **Mistaking "do one thing" for "have one method".** SRP is about *reasons to change*, not method count.
3. **Anaemic models.** Pushing SRP too far gives you data bags + 30 services. Some logic *belongs* on the model.

## Self-check

1. State SRP without saying "do one thing".
2. Give 4 different "reasons to change" a `User` class.
3. Why is `RegisterUser` (the orchestrator) not a SRP violation?
4. When is splitting *too eager*?
5. Where does SRP show up in Django REST Framework's design?
