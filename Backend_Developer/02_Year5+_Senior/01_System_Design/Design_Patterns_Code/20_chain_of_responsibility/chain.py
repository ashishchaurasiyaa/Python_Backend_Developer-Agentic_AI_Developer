"""
============================================================
CHAIN OF RESPONSIBILITY — Practical Implementation
============================================================
Run:  python chain.py
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Callable, Any
import time


# ============================================================
# 1. CLASSIC OOP CHAIN
# ============================================================
class Handler(ABC):
    def __init__(self):
        self._next: "Handler | None" = None

    def set_next(self, handler: "Handler") -> "Handler":
        self._next = handler
        return handler   # enables: a.set_next(b).set_next(c)

    @abstractmethod
    def handle(self, request: dict) -> Any: ...

    def _pass(self, request):
        if self._next:
            return self._next.handle(request)
        return None


class AuthHandler(Handler):
    def handle(self, request):
        if not request.get("token"):
            return {"error": "Unauthorized", "stopped_at": "auth"}
        print(f"  [Auth] token valid")
        return self._pass(request)


class RateLimitHandler(Handler):
    BLACKLIST = {"1.2.3.4"}
    def handle(self, request):
        ip = request.get("ip")
        if ip in self.BLACKLIST:
            return {"error": "Too many requests", "stopped_at": "rate_limit"}
        print(f"  [RateLimit] {ip} ok")
        return self._pass(request)


class ValidationHandler(Handler):
    def handle(self, request):
        if "email" not in request.get("body", {}):
            return {"error": "Missing email", "stopped_at": "validation"}
        print(f"  [Validation] body valid")
        return self._pass(request)


class LoggingHandler(Handler):
    def handle(self, request):
        print(f"  [Logging] {request.get('method')} {request.get('path')}")
        return self._pass(request)


class TerminalHandler(Handler):
    """Always at end — actually processes request."""
    def handle(self, request):
        return {"status": 200, "data": f"Handled {request.get('path')}"}


def demo_http_pipeline():
    print("=" * 60)
    print("DEMO 1: HTTP-style request chain")
    print("=" * 60)

    chain = AuthHandler()
    chain.set_next(RateLimitHandler()).set_next(ValidationHandler()).set_next(LoggingHandler()).set_next(TerminalHandler())

    valid_req = {
        "method": "POST",
        "path": "/users",
        "token": "abc",
        "ip": "10.0.0.1",
        "body": {"email": "user@x.com"},
    }
    print("--- Valid request ---")
    print(f"  Result: {chain.handle(valid_req)}")

    print("\n--- Missing token ---")
    bad = valid_req.copy(); bad["token"] = None
    print(f"  Result: {chain.handle(bad)}")

    print("\n--- Blacklisted IP ---")
    bad2 = valid_req.copy(); bad2["ip"] = "1.2.3.4"
    print(f"  Result: {chain.handle(bad2)}")


# ============================================================
# 2. FUNCTIONAL / DECORATOR PIPELINE (Pythonic)
# ============================================================
def auth(handler):
    def wrapper(req):
        if not req.get("token"):
            return {"error": "Unauthorized"}
        return handler(req)
    return wrapper


def rate_limit(handler):
    def wrapper(req):
        if req.get("ip") in {"1.2.3.4"}:
            return {"error": "Too many requests"}
        return handler(req)
    return wrapper


def log_calls(handler):
    def wrapper(req):
        start = time.perf_counter()
        result = handler(req)
        print(f"  [log] {req.get('path')} took {(time.perf_counter()-start)*1000:.2f}ms")
        return result
    return wrapper


@log_calls
@rate_limit
@auth
def get_user(req):
    return {"id": req["params"]["id"], "name": "Ashish"}


def demo_functional_chain():
    print("\n" + "=" * 60)
    print("DEMO 2: Decorator-style chain")
    print("=" * 60)
    print(get_user({"path": "/user", "token": "x", "ip": "10.0.0.1", "params": {"id": 1}}))
    print(get_user({"path": "/user", "token": None}))


# ============================================================
# 3. ATM CASH DISPENSER
# ============================================================
class Dispenser:
    def __init__(self, denom: int):
        self.denom = denom
        self.next: "Dispenser | None" = None

    def set_next(self, d): self.next = d; return d

    def dispense(self, amount: int) -> dict:
        notes = {}
        if amount >= self.denom:
            count = amount // self.denom
            notes[self.denom] = count
            amount %= self.denom
        if amount > 0:
            if self.next:
                sub = self.next.dispense(amount)
                if "error" in sub:
                    return sub
                notes.update(sub)
            else:
                return {"error": f"Cannot dispense remainder {amount}"}
        return notes


def demo_atm():
    print("\n" + "=" * 60)
    print("DEMO 3: ATM Cash Dispenser")
    print("=" * 60)
    d2000 = Dispenser(2000)
    d500 = Dispenser(500)
    d100 = Dispenser(100)
    d2000.set_next(d500).set_next(d100)

    for amount in [3700, 5200, 1530, 100]:
        result = d2000.dispense(amount)
        print(f"  ₹{amount}: {result}")


# ============================================================
# 4. EXPENSE APPROVAL CHAIN
# ============================================================
@dataclass
class Expense:
    amount: float
    description: str


class Approver(ABC):
    def __init__(self, limit: float, name: str):
        self.limit = limit
        self.name = name
        self.next: "Approver | None" = None

    def set_next(self, a): self.next = a; return a

    def approve(self, expense: Expense) -> str:
        if expense.amount <= self.limit:
            return f"  ✅ Approved by {self.name}: {expense.description} (₹{expense.amount})"
        if self.next:
            return self.next.approve(expense)
        return f"  ❌ Rejected: ₹{expense.amount} exceeds all limits"


class TeamLead(Approver):
    def __init__(self): super().__init__(1000, "Team Lead")
class Manager(Approver):
    def __init__(self): super().__init__(10000, "Manager")
class Director(Approver):
    def __init__(self): super().__init__(100000, "Director")
class CEO(Approver):
    def __init__(self): super().__init__(float("inf"), "CEO")


def demo_expense():
    print("\n" + "=" * 60)
    print("DEMO 4: Expense Approval Chain")
    print("=" * 60)
    tl = TeamLead()
    tl.set_next(Manager()).set_next(Director()).set_next(CEO())

    for expense in [
        Expense(500, "Team lunch"),
        Expense(5000, "Conference ticket"),
        Expense(50000, "New laptop"),
        Expense(500000, "Office renovation"),
    ]:
        print(tl.approve(expense))


# ============================================================
# 5. LIST-BASED CHAIN BUILDER
# ============================================================
class ChainBuilder:
    """Build chain from list — useful for dynamic config."""
    def __init__(self):
        self.handlers: list[Callable] = []

    def add(self, handler: Callable):
        self.handlers.append(handler)
        return self

    def execute(self, request) -> Any:
        for h in self.handlers:
            result = h(request)
            if result is not None:
                return result
        return None


def demo_list_chain():
    print("\n" + "=" * 60)
    print("DEMO 5: List-based chain")
    print("=" * 60)

    def check_auth(req):
        if not req.get("token"): return {"error": "No token"}
        return None    # pass to next

    def check_quota(req):
        if req.get("quota_exceeded"): return {"error": "Quota exceeded"}
        return None

    def handle(req):
        return {"data": "processed"}

    chain = ChainBuilder().add(check_auth).add(check_quota).add(handle)

    print(f"  Valid:        {chain.execute({'token': 'x'})}")
    print(f"  No token:     {chain.execute({})}")
    print(f"  Quota gone:   {chain.execute({'token': 'x', 'quota_exceeded': True})}")


# ============================================================
# 6. LOG FILTER CHAIN
# ============================================================
LEVELS = {"DEBUG": 10, "INFO": 20, "WARNING": 30, "ERROR": 40}


class LogFilter:
    def __init__(self, min_level: str):
        self.min = LEVELS[min_level]
        self.next: "LogFilter | None" = None

    def set_next(self, f): self.next = f; return f

    def log(self, level: str, msg: str):
        if LEVELS[level] >= self.min:
            print(f"  [{self.__class__.__name__}] {level}: {msg}")
        if self.next:
            self.next.log(level, msg)   # pass to ALL — middleware variant


class ConsoleFilter(LogFilter):
    def __init__(self): super().__init__("DEBUG")
class FileFilter(LogFilter):
    def __init__(self): super().__init__("INFO")
class AlertFilter(LogFilter):
    def __init__(self): super().__init__("ERROR")


def demo_log_filters():
    print("\n" + "=" * 60)
    print("DEMO 6: Log filter chain (pass-through variant)")
    print("=" * 60)
    chain = ConsoleFilter()
    chain.set_next(FileFilter()).set_next(AlertFilter())

    chain.log("DEBUG", "debug message")
    chain.log("INFO", "user logged in")
    chain.log("ERROR", "database connection failed")


# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    demo_http_pipeline()
    demo_functional_chain()
    demo_atm()
    demo_expense()
    demo_list_chain()
    demo_log_filters()

    print("\n" + "=" * 60)
    print("KEY TAKEAWAYS")
    print("=" * 60)
    print("""
1. Two variants:
   - Short-circuit (first matching handler returns)
   - Pass-through (all handlers run — middleware)
2. Decorator stacks are Pythonic CoR
3. Always include terminal handler
4. Use list/builder pattern for configurable chains
5. Real uses: middleware, ATM, expense approval, log filters
6. Order matters — document and validate at construction
""")
