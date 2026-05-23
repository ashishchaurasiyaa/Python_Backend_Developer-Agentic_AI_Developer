# Splitwise / Expense Sharing — LLD
> **Difficulty:** Medium-Hard | **Frequency:** ★★★★★ | **Startup Favorite**

---

## Requirements

```
1. Users add karo — name, email
2. Group create karo — trip, flat, office
3. Expense add karo — "Rahul ne Rs 1200 diye dinner ke liye (3 log)"
4. Multiple split types:
     Equal split     → sab barabar
     Exact split     → exact amounts specify
     Percentage split → percentage specify
     Share-based     → shares specify (2:1:1)
5. Balance check karo — "Main kiska kitna lena/dena hoon?"
6. Settle up — "Rahul ne James ko Rs 400 diye"
7. Debt simplification — minimize number of transactions
8. Expense history — group ya user ke saare transactions
```

---

## Core Concepts

### Debt Graph
```
After expenses, we maintain a net balance graph:
  balance[A][B] = +500  → A owes B Rs 500
  balance[A][B] = -500  → B owes A Rs 500 (same as balance[B][A] = +500)

Debt Simplification:
  Without simplification (3 people, A owes B, B owes C):
    A → B: 100
    B → C: 100
    = 2 transactions

  With simplification:
    A → C: 100
    = 1 transaction (B is middle-man, cut out)

  Algorithm: net balance calculate karo per person
    Positive net = others owe them (creditor)
    Negative net = they owe others (debtor)
    Greedily match largest debtor with largest creditor
```

### Split Types
```
Expense: Rs 1200, 3 people (Rahul, James, Priya)

Equal:       400  | 400  | 400
Exact:       500  | 300  | 400   (manually specified)
Percentage:  50%  | 30%  | 20%   → 600 | 360 | 240
Share:       2    | 1    | 1     → 600 | 300 | 300
```

---

## Full Implementation

```python
from __future__ import annotations
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from typing import Dict, List, Optional, Tuple
import uuid


# ═══════════════════════════════════════════════════════════════
# ENUMS
# ═══════════════════════════════════════════════════════════════

class SplitType(Enum):
    EQUAL      = "equal"
    EXACT      = "exact"
    PERCENTAGE = "percentage"
    SHARE      = "share"


# ═══════════════════════════════════════════════════════════════
# DOMAIN MODELS
# ═══════════════════════════════════════════════════════════════

@dataclass
class User:
    user_id:    str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name:       str = ""
    email:      str = ""

    def __repr__(self): return self.name
    def __hash__(self): return hash(self.user_id)
    def __eq__(self, other): return self.user_id == other.user_id


@dataclass
class Group:
    group_id:   str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name:       str = ""
    members:    List[User] = field(default_factory=list)
    expenses:   List['Expense'] = field(default_factory=list)

    def add_member(self, user: User) -> None:
        if user not in self.members:
            self.members.append(user)

    def __repr__(self): return f"Group({self.name})"


# ═══════════════════════════════════════════════════════════════
# SPLIT STRATEGY — Strategy Pattern
# ═══════════════════════════════════════════════════════════════

@dataclass
class SplitShare:
    """How much each user owes for an expense"""
    user:   User
    amount: Decimal   # exact amount this user owes


class Split(ABC):
    """Strategy interface — how to divide an expense"""

    @abstractmethod
    def calculate(self, total: Decimal, users: List[User], **kwargs) -> List[SplitShare]:
        """Returns list of SplitShare — one per user"""
        pass

    def _round(self, amount: Decimal) -> Decimal:
        return amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


class EqualSplit(Split):
    """
    Divide equally among all participants.
    Rounding: extra paise pehle wale ko
    """
    def calculate(self, total: Decimal, users: List[User], **kwargs) -> List[SplitShare]:
        n           = len(users)
        base_amount = self._round(total / n)
        remainder   = total - base_amount * n

        shares = []
        for i, user in enumerate(users):
            amount = base_amount + remainder if i == 0 else base_amount
            shares.append(SplitShare(user=user, amount=amount))
        return shares


class ExactSplit(Split):
    """Each user's exact amount specified"""
    def calculate(self, total: Decimal, users: List[User], amounts: List[Decimal] = None, **kwargs) -> List[SplitShare]:
        if not amounts or len(amounts) != len(users):
            raise ValueError("Exact amounts required for each user")

        total_split = sum(amounts)
        if abs(total_split - total) > Decimal('0.01'):
            raise ValueError(f"Split amounts {total_split} don't add up to total {total}")

        return [SplitShare(user=u, amount=a) for u, a in zip(users, amounts)]


class PercentageSplit(Split):
    """Divide by percentage"""
    def calculate(self, total: Decimal, users: List[User], percentages: List[Decimal] = None, **kwargs) -> List[SplitShare]:
        if not percentages or len(percentages) != len(users):
            raise ValueError("Percentage required for each user")

        total_pct = sum(percentages)
        if abs(total_pct - Decimal('100')) > Decimal('0.01'):
            raise ValueError(f"Percentages must sum to 100, got {total_pct}")

        shares = []
        running_total = Decimal('0')
        for i, (user, pct) in enumerate(zip(users, percentages)):
            if i == len(users) - 1:
                amount = total - running_total   # Last person gets remainder
            else:
                amount = self._round(total * pct / Decimal('100'))
                running_total += amount
            shares.append(SplitShare(user=user, amount=amount))
        return shares


class ShareSplit(Split):
    """Divide by shares (ratio) — e.g., 2:1:1"""
    def calculate(self, total: Decimal, users: List[User], shares: List[int] = None, **kwargs) -> List[SplitShare]:
        if not shares or len(shares) != len(users):
            raise ValueError("Share values required for each user")

        total_shares = sum(shares)
        result       = []
        running      = Decimal('0')

        for i, (user, share) in enumerate(zip(users, shares)):
            if i == len(users) - 1:
                amount = total - running
            else:
                amount   = self._round(total * Decimal(share) / Decimal(total_shares))
                running += amount
            result.append(SplitShare(user=user, amount=amount))
        return result


class SplitFactory:
    _strategies = {
        SplitType.EQUAL:      EqualSplit,
        SplitType.EXACT:      ExactSplit,
        SplitType.PERCENTAGE: PercentageSplit,
        SplitType.SHARE:      ShareSplit,
    }

    @classmethod
    def get(cls, split_type: SplitType) -> Split:
        return cls._strategies[split_type]()


# ═══════════════════════════════════════════════════════════════
# EXPENSE
# ═══════════════════════════════════════════════════════════════

@dataclass
class Expense:
    expense_id:   str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    description:  str = ""
    total_amount: Decimal = Decimal('0')
    paid_by:      Optional[User] = None      # Who paid
    group:        Optional[Group] = None
    split_type:   SplitType = SplitType.EQUAL
    splits:       List[SplitShare] = field(default_factory=list)
    created_at:   datetime = field(default_factory=datetime.now)
    is_deleted:   bool = False

    def __repr__(self):
        return f"Expense({self.description}: {self.total_amount} by {self.paid_by})"


# ═══════════════════════════════════════════════════════════════
# BALANCE SHEET — Net balances between users
# ═══════════════════════════════════════════════════════════════

class BalanceSheet:
    """
    balance[user_a][user_b] = amount
      +ve → user_a owes user_b that amount
      -ve → user_b owes user_a that amount

    Always maintain: balance[a][b] = -balance[b][a]
    """

    def __init__(self):
        # balance[debtor][creditor] = amount owed
        self._balances: Dict[str, Dict[str, Decimal]] = defaultdict(
            lambda: defaultdict(Decimal)
        )

    def add_expense(self, expense: Expense) -> None:
        """Update balances when expense is added"""
        payer_id = expense.paid_by.user_id

        for split in expense.splits:
            if split.user.user_id == payer_id:
                continue   # Payer doesn't owe themselves

            debtor_id  = split.user.user_id
            amount     = split.amount

            # debtor owes payer
            self._balances[debtor_id][payer_id]  += amount
            self._balances[payer_id][debtor_id]  -= amount

    def remove_expense(self, expense: Expense) -> None:
        """Reverse an expense (soft delete)"""
        payer_id = expense.paid_by.user_id

        for split in expense.splits:
            if split.user.user_id == payer_id:
                continue

            debtor_id = split.user.user_id
            amount    = split.amount

            self._balances[debtor_id][payer_id]  -= amount
            self._balances[payer_id][debtor_id]  += amount

    def settle(self, payer_id: str, payee_id: str, amount: Decimal) -> None:
        """Record a settlement payment"""
        # payer pays payee → payer owes less to payee
        self._balances[payer_id][payee_id]  -= amount
        self._balances[payee_id][payer_id]  += amount

    def get_balance(self, user_id_a: str, user_id_b: str) -> Decimal:
        """
        +ve → a owes b
        -ve → b owes a
        """
        return self._balances[user_id_a][user_id_b]

    def get_net_balance(self, user_id: str) -> Decimal:
        """
        Total net balance for user.
        +ve → user is owed this much (creditor)
        -ve → user owes this much (debtor)
        """
        total = Decimal('0')
        for other_id, amount in self._balances[user_id].items():
            total += amount   # +ve means others owe user, -ve means user owes others
            # Wait — balance[user][other] = user owes other
            # Net = sum of what others owe user - what user owes others
        # Recalculate correctly:
        net = Decimal('0')
        for other_id, amount in self._balances.items():
            if other_id != user_id:
                # amount[user_id] = other owes user
                net += self._balances[other_id].get(user_id, Decimal('0'))
        # minus what user owes others
        for other_id, amount in self._balances[user_id].items():
            net -= amount
        return net

    def get_user_balances(self, user_id: str) -> Dict[str, Decimal]:
        """All non-zero balances for a user"""
        result = {}
        for other_id, amount in self._balances[user_id].items():
            if abs(amount) > Decimal('0.01'):
                result[other_id] = amount
        return result


# ═══════════════════════════════════════════════════════════════
# DEBT SIMPLIFICATION — Minimize Transactions
# ═══════════════════════════════════════════════════════════════

@dataclass
class Settlement:
    from_user: User
    to_user:   User
    amount:    Decimal

    def __repr__(self):
        return f"{self.from_user.name} → {self.to_user.name}: ₹{self.amount}"


class DebtSimplifier:
    """
    Algorithm: Net balance per person → greedy matching

    1. Calculate net balance for each person
       net > 0 → creditor (owed money)
       net < 0 → debtor  (owes money)

    2. Sort debtors (most owe first) and creditors (most owed first)

    3. Greedy match:
       Largest debtor → Largest creditor
       min(debtor_amount, creditor_amount) settle karo
       If debtor fully settled → next debtor
       If creditor fully settled → next creditor
       Continue until all settled

    Time: O(n log n)
    Result: Minimum possible transactions

    Example:
      A owes B: 1000
      B owes C: 800
      C owes A: 600

      Net:  A = -1000 + 600 = -400 (debtor)
            B = +1000 - 800 = +200 (creditor)
            C = +800 - 600  = +200 (creditor)

      Simplified:
        A → B: 200
        A → C: 200
        (3 transactions → 2 transactions)
    """

    def simplify(self, users: List[User], balance_sheet: BalanceSheet) -> List[Settlement]:
        # Calculate net balance per user
        net_balances: Dict[str, Decimal] = {}
        for user in users:
            net = Decimal('0')
            for other in users:
                if other.user_id != user.user_id:
                    # others owe user
                    net += self._balance(balance_sheet, other.user_id, user.user_id)
            net_balances[user.user_id] = net

        # Separate debtors (negative net) and creditors (positive net)
        debtors   = [(uid, -amt) for uid, amt in net_balances.items() if amt < -Decimal('0.01')]
        creditors = [(uid, amt)  for uid, amt in net_balances.items() if amt >  Decimal('0.01')]

        # Sort: largest amounts first
        debtors.sort(key=lambda x: x[1], reverse=True)
        creditors.sort(key=lambda x: x[1], reverse=True)

        user_map = {u.user_id: u for u in users}
        settlements = []

        d_idx, c_idx = 0, 0
        debtors   = list(debtors)
        creditors = list(creditors)

        while d_idx < len(debtors) and c_idx < len(creditors):
            d_id, d_amt = debtors[d_idx]
            c_id, c_amt = creditors[c_idx]

            pay = min(d_amt, c_amt)
            if pay > Decimal('0.01'):
                settlements.append(Settlement(
                    from_user = user_map[d_id],
                    to_user   = user_map[c_id],
                    amount    = pay.quantize(Decimal('0.01'))
                ))

            d_amt -= pay
            c_amt -= pay

            if d_amt < Decimal('0.01'):
                d_idx += 1
            else:
                debtors[d_idx] = (d_id, d_amt)

            if c_amt < Decimal('0.01'):
                c_idx += 1
            else:
                creditors[c_idx] = (c_id, c_amt)

        return settlements

    def _balance(self, bs: BalanceSheet, from_id: str, to_id: str) -> Decimal:
        """How much from_id owes to_id (positive = owes)"""
        return bs._balances[from_id].get(to_id, Decimal('0'))


# ═══════════════════════════════════════════════════════════════
# SPLITWISE SERVICE — Main Facade
# ═══════════════════════════════════════════════════════════════

class SplitwiseService:
    """
    Single entry point.
    Orchestrates: users, groups, expenses, balances, settlements.
    """

    def __init__(self):
        self._users:    Dict[str, User]    = {}
        self._groups:   Dict[str, Group]   = {}
        self._expenses: Dict[str, Expense] = {}
        self._balance_sheet = BalanceSheet()
        self._simplifier    = DebtSimplifier()

    # ─── User Management ─────────────────────────────────────

    def add_user(self, name: str, email: str) -> User:
        user = User(name=name, email=email)
        self._users[user.user_id] = user
        print(f"[SW] User added: {name}")
        return user

    # ─── Group Management ────────────────────────────────────

    def create_group(self, name: str, members: List[User]) -> Group:
        group = Group(name=name, members=list(members))
        self._groups[group.group_id] = group
        print(f"[SW] Group created: {name} ({len(members)} members)")
        return group

    def add_member_to_group(self, group: Group, user: User) -> None:
        group.add_member(user)

    # ─── Add Expense ─────────────────────────────────────────

    def add_expense(
        self,
        description:  str,
        amount:       Decimal,
        paid_by:      User,
        participants: List[User],
        split_type:   SplitType = SplitType.EQUAL,
        group:        Optional[Group] = None,
        **split_kwargs
    ) -> Expense:
        """
        split_kwargs:
          EXACT:      amounts=[400, 300, 500]
          PERCENTAGE: percentages=[40, 30, 30]
          SHARE:      shares=[2, 1, 1]
        """
        strategy = SplitFactory.get(split_type)
        splits   = strategy.calculate(amount, participants, **split_kwargs)

        expense = Expense(
            description  = description,
            total_amount = amount,
            paid_by      = paid_by,
            group        = group,
            split_type   = split_type,
            splits       = splits
        )

        self._expenses[expense.expense_id] = expense
        self._balance_sheet.add_expense(expense)

        if group:
            group.expenses.append(expense)

        print(f"[SW] Expense added: '{description}' ₹{amount} by {paid_by.name}")
        for s in splits:
            if s.user != paid_by:
                print(f"       {s.user.name} owes {paid_by.name}: ₹{s.amount}")

        return expense

    # ─── Delete Expense ──────────────────────────────────────

    def delete_expense(self, expense_id: str) -> None:
        expense = self._expenses.get(expense_id)
        if not expense or expense.is_deleted:
            raise ValueError("Expense not found")
        expense.is_deleted = True
        self._balance_sheet.remove_expense(expense)
        print(f"[SW] Expense deleted: {expense.description}")

    # ─── Settle Up ───────────────────────────────────────────

    def settle_up(self, payer: User, payee: User, amount: Decimal) -> None:
        """Record manual settlement payment"""
        self._balance_sheet.settle(payer.user_id, payee.user_id, amount)
        print(f"[SW] Settlement: {payer.name} paid {payee.name} ₹{amount}")

    # ─── Balance Queries ─────────────────────────────────────

    def get_balance_between(self, user_a: User, user_b: User) -> str:
        """How much user_a owes user_b"""
        amount = self._balance_sheet.get_balance(user_a.user_id, user_b.user_id)
        if amount > Decimal('0.01'):
            return f"{user_a.name} owes {user_b.name} ₹{amount}"
        elif amount < Decimal('-0.01'):
            return f"{user_b.name} owes {user_a.name} ₹{abs(amount)}"
        else:
            return f"{user_a.name} and {user_b.name} are settled up"

    def get_all_balances(self, user: User) -> None:
        """Show all outstanding balances for a user"""
        print(f"\n[BALANCE] {user.name}'s balances:")
        balances = self._balance_sheet.get_user_balances(user.user_id)
        if not balances:
            print("  All settled up! ✓")
            return

        for other_id, amount in balances.items():
            other = self._users.get(other_id, User(name=other_id))
            if amount > Decimal('0.01'):
                print(f"  {user.name} owes {other.name}: ₹{amount}")
            elif amount < Decimal('-0.01'):
                print(f"  {other.name} owes {user.name}: ₹{abs(amount)}")

    def get_group_balances(self, group: Group) -> None:
        """Show all balances within a group"""
        print(f"\n[GROUP BALANCE] {group.name}:")
        shown = set()
        for a in group.members:
            for b in group.members:
                if a == b: continue
                key = tuple(sorted([a.user_id, b.user_id]))
                if key in shown: continue
                shown.add(key)
                amount = self._balance_sheet.get_balance(a.user_id, b.user_id)
                if amount > Decimal('0.01'):
                    print(f"  {a.name} owes {b.name}: ₹{amount}")

    # ─── Debt Simplification ─────────────────────────────────

    def simplify_debts(self, users: List[User]) -> List[Settlement]:
        """
        Minimize number of transactions to settle all debts.
        Use this for group settlement.
        """
        settlements = self._simplifier.simplify(users, self._balance_sheet)
        print(f"\n[SIMPLIFY] Minimum {len(settlements)} transactions needed:")
        for s in settlements:
            print(f"  {s}")
        return settlements

    # ─── Expense History ─────────────────────────────────────

    def get_expense_history(self, group: Optional[Group] = None,
                             user: Optional[User] = None) -> List[Expense]:
        expenses = [e for e in self._expenses.values() if not e.is_deleted]
        if group:
            expenses = [e for e in expenses if e.group == group]
        if user:
            expenses = [e for e in expenses
                        if e.paid_by == user or any(s.user == user for s in e.splits)]
        expenses.sort(key=lambda e: e.created_at)
        return expenses
```

---

## Demo

```python
sw = SplitwiseService()

# ─── Create Users ────────────────────────────────────────────
rahul = sw.add_user("Rahul", "rahul@gmail.com")
james = sw.add_user("James", "james@gmail.com")
priya = sw.add_user("Priya", "priya@gmail.com")
amit  = sw.add_user("Amit",  "amit@gmail.com")

# ─── Create Group ────────────────────────────────────────────
goa_trip = sw.create_group("Goa Trip 2026", [rahul, james, priya, amit])


# ─── Flow 1: Equal Split ─────────────────────────────────────
print("\n" + "="*50)
print("EQUAL SPLIT: Hotel bill")
print("="*50)
sw.add_expense(
    description  = "Hotel — 2 nights",
    amount       = Decimal("4800"),
    paid_by      = rahul,
    participants = [rahul, james, priya, amit],
    split_type   = SplitType.EQUAL,
    group        = goa_trip
)


# ─── Flow 2: Exact Split ─────────────────────────────────────
print("\n" + "="*50)
print("EXACT SPLIT: Dinner (different portions)")
print("="*50)
sw.add_expense(
    description  = "Dinner at beach restaurant",
    amount       = Decimal("2400"),
    paid_by      = james,
    participants = [rahul, james, priya, amit],
    split_type   = SplitType.EXACT,
    group        = goa_trip,
    amounts      = [Decimal("800"), Decimal("600"), Decimal("600"), Decimal("400")]
)


# ─── Flow 3: Percentage Split ────────────────────────────────
print("\n" + "="*50)
print("PERCENTAGE SPLIT: Cab (rahul uses more)")
print("="*50)
sw.add_expense(
    description  = "Cab from airport",
    amount       = Decimal("1200"),
    paid_by      = priya,
    participants = [rahul, james, priya, amit],
    split_type   = SplitType.PERCENTAGE,
    group        = goa_trip,
    percentages  = [Decimal("40"), Decimal("20"), Decimal("20"), Decimal("20")]
)


# ─── Flow 4: Share-based Split ───────────────────────────────
print("\n" + "="*50)
print("SHARE SPLIT: Activities (Rahul does 2, others 1)")
print("="*50)
sw.add_expense(
    description  = "Water sports",
    amount       = Decimal("3000"),
    paid_by      = amit,
    participants = [rahul, james, priya, amit],
    split_type   = SplitType.SHARE,
    group        = goa_trip,
    shares       = [2, 1, 1, 1]    # Rahul: 2/5, others: 1/5 each
)


# ─── View Balances ───────────────────────────────────────────
print("\n" + "="*50)
print("ALL BALANCES")
print("="*50)
sw.get_group_balances(goa_trip)
sw.get_all_balances(rahul)


# ─── Debt Simplification ─────────────────────────────────────
print("\n" + "="*50)
print("DEBT SIMPLIFICATION")
print("="*50)
sw.simplify_debts([rahul, james, priya, amit])


# ─── Settle Up ───────────────────────────────────────────────
print("\n" + "="*50)
print("SETTLE UP")
print("="*50)
sw.settle_up(james, rahul, Decimal("200"))
print(sw.get_balance_between(james, rahul))


# ─── Non-Group Expense ───────────────────────────────────────
print("\n" + "="*50)
print("DIRECT EXPENSE (no group)")
print("="*50)
sw.add_expense(
    description  = "Movie tickets",
    amount       = Decimal("600"),
    paid_by      = rahul,
    participants = [rahul, priya],
    split_type   = SplitType.EQUAL
)
print(sw.get_balance_between(priya, rahul))
```

---

## Debt Simplification — Dry Run

```
Setup:
  A paid 1000 (B owes 500, C owes 500)
  B paid 600  (A owes 300, C owes 300)
  C paid 900  (A owes 450, B owes 450)

Raw debts (without simplification):
  B → A: 500
  C → A: 500
  A → B: 300
  C → B: 300
  A → C: 450
  B → C: 450
  = 6 transactions

Net balance calculation:
  A: received(500+500) - paid(300+450) = 1000 - 750 = +250 (creditor)
  B: received(300+450) - paid(500+300) = 750 - 800 = -50  (debtor, owes 50)
  C: received(300+300) - paid(500+450) = 600 - 950 = -350 (debtor, owes 350)

Simplified (greedy):
  Step 1: Largest debtor C (350) → Largest creditor A (250)
          C → A: 250  (C debt: 350-250=100 left, A settled)
  Step 2: Remaining debtor C (100) → next creditor? A settled.
          No more creditors except... B is -50 also debtor.
          Wait — only A is creditor.
          C → A: 100 (C fully settled)
          B → A: 50  (B fully settled)

Result: 3 transactions (from 6)
  C → A: 250
  C → A: 100  (or combined: C → A: 350)
  B → A: 50
```

---

## Interview Q&A

**Q: "Debt simplification algorithm explain karo"**
> "Net balance calculate karo har person ka — kitna owe karta hai total, kitna receive karna hai. Net positive = creditor (duniya unhe paisa deti hai). Net negative = debtor (woh duniya ko paisa deta hai). Greedy approach: debtors aur creditors alag karo, dono ko sort karo largest first. Largest debtor largest creditor ko pay karo — minimum of the two. Whoever is fully settled, next wale pe move karo. Result: minimum number of transactions. Without simplification N*(N-1)/2 transactions possible. With simplification: at most N-1 transactions. O(n log n) algorithm."

**Q: "Rounding issue — Rs 100 teen log mein equally kaise split?"**
> "33.33 + 33.33 + 33.34 — last person ko remainder milta hai. ROUND_HALF_UP use karo Decimal module se. Running total track karo — last person ko total minus running total milta hai. Yeh ensure karta hai ki sum always exactly total ke barabar hoga. Float use mat karo — 0.1 + 0.2 = 0.30000000000000004 in float. Hamesha Decimal module use karo financial calculations ke liye."

**Q: "Equal vs Exact vs Percentage vs Share — kaunsa design use kiya?"**
> "Strategy Pattern. Split ek abstract base class hai with calculate() method. EqualSplit, ExactSplit, PercentageSplit, ShareSplit — charon alag concrete implementations. SplitFactory string/enum se sahi strategy return karta hai. Naya split type add karna? Ek naya class, zero changes to existing code — OCP. Expense object ko sirf final SplitShare list milti hai — kaise split hua woh usse pata nahi — SRP."

---

## Patterns Used

| Pattern | Where | Why |
|---|---|---|
| **Strategy** | Split types (Equal/Exact/%) | Add new split type without changing core |
| **Facade** | SplitwiseService | Single entry point |
| **Factory** | SplitFactory | String → Split strategy |
| **Observer** | (Extension) Notify members on expense add | Decouple notification |

---

*Last Updated: April 2026 | SDE-2 Interview Prep*
