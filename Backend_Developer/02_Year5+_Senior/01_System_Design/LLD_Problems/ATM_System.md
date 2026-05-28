# ATM System LLD

## Quick Reference Card
```
Pattern Used    → State Machine + Strategy (cash dispensing)
Core Challenge  → State transitions, Cash dispensing algorithm, Security
Key States      → IDLE → CARD_INSERTED → PIN_ENTERED → AUTHENTICATED → TRANSACTION → DISPENSING
Interview Hook  → "Denomination greedy algorithm + State Pattern"
```

---

## PART 1: HINGLISH — Samjhne ke liye

### 1.1 Kya hai?

ATM System mein:
- **Card authentication** — PIN verify karo (3 tries, phir lock)
- **Transaction** — withdraw/deposit/balance/transfer
- **Cash dispensing** — denominations ka greedy algorithm
- **State machine** — security ke liye strict state transitions

**Denomination Algorithm:**
- Withdraw ₹4500 
- Available: [2000, 500, 200, 100]
- Greedy: 2×2000 = 4000, 1×500 = 500 → Total ₹4500 in 3 notes
- Minimize note count!

### 1.2 Code

```python
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from datetime import datetime
import threading
import uuid
import hashlib

# ===== ENUMS =====

class ATMState(Enum):
    IDLE = "IDLE"
    CARD_INSERTED = "CARD_INSERTED"
    PIN_ENTERED = "PIN_ENTERED"       # PIN verify ho raha hai
    AUTHENTICATED = "AUTHENTICATED"   # Successfully logged in
    SELECTING_TRANSACTION = "SELECTING_TRANSACTION"
    DISPENSING = "DISPENSING"
    OUT_OF_SERVICE = "OUT_OF_SERVICE"

class TransactionType(Enum):
    WITHDRAW = "WITHDRAW"
    DEPOSIT = "DEPOSIT"
    BALANCE_INQUIRY = "BALANCE_INQUIRY"
    CHANGE_PIN = "CHANGE_PIN"
    MINI_STATEMENT = "MINI_STATEMENT"

class TransactionStatus(Enum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    PENDING = "PENDING"

# ===== BANK ACCOUNT =====

@dataclass
class BankAccount:
    account_id: str = field(default_factory=lambda: f"AC{str(uuid.uuid4())[:8].upper()}")
    holder_name: str = ""
    pin_hash: str = ""          # SHA256 hash of PIN (never store plain)
    balance: float = 0.0
    daily_limit: float = 25000.0
    daily_withdrawn: float = 0.0
    last_withdrawal_date: str = ""
    is_locked: bool = False
    failed_attempts: int = 0
    max_failed_attempts: int = 3
    
    def verify_pin(self, pin: str) -> bool:
        """SHA256 hash compare karo"""
        return hashlib.sha256(pin.encode()).hexdigest() == self.pin_hash
    
    def record_failed_attempt(self):
        self.failed_attempts += 1
        if self.failed_attempts >= self.max_failed_attempts:
            self.is_locked = True
    
    def reset_failed_attempts(self):
        self.failed_attempts = 0
    
    def can_withdraw(self, amount: float) -> tuple[bool, str]:
        if self.is_locked:
            return False, "Account locked. Contact bank."
        if amount > self.balance:
            return False, f"Insufficient balance. Available: ₹{self.balance}"
        
        today = str(datetime.today().date())
        if self.last_withdrawal_date == today:
            if self.daily_withdrawn + amount > self.daily_limit:
                remaining = self.daily_limit - self.daily_withdrawn
                return False, f"Daily limit exceeded. Remaining: ₹{remaining}"
        
        return True, "OK"
    
    def debit(self, amount: float):
        self.balance -= amount
        today = str(datetime.today().date())
        if self.last_withdrawal_date != today:
            self.daily_withdrawn = 0
            self.last_withdrawal_date = today
        self.daily_withdrawn += amount

@dataclass
class Card:
    card_number: str        # Last 4 digits dikhao only
    account_id: str
    expiry: str             # "MM/YY"
    is_valid: bool = True
    
    def masked_number(self) -> str:
        return f"**** **** **** {self.card_number[-4:]}"

# ===== TRANSACTION =====

@dataclass
class Transaction:
    txn_id: str = field(default_factory=lambda: f"TXN{str(uuid.uuid4())[:8].upper()}")
    account_id: str = ""
    txn_type: TransactionType = TransactionType.WITHDRAW
    amount: float = 0.0
    balance_after: float = 0.0
    status: TransactionStatus = TransactionStatus.PENDING
    timestamp: datetime = field(default_factory=datetime.now)
    atm_id: str = ""
    notes_dispensed: Dict[int, int] = field(default_factory=dict)  # denomination → count

# ===== CASH DISPENSER (Strategy) =====

class CashDispenser:
    """
    ATM ki cash tray — denominations manage karta hai
    
    Greedy algorithm: sabse bada note pehle use karo
    """
    
    def __init__(self):
        # denomination → count (2000, 500, 200, 100, 50)
        self._notes: Dict[int, int] = {
            2000: 20,
            500:  30,
            200:  50,
            100:  100,
        }
        self._lock = threading.Lock()
    
    def get_available_cash(self) -> float:
        return sum(denom * count for denom, count in self._notes.items())
    
    def can_dispense(self, amount: float) -> tuple[bool, str]:
        if amount > self.get_available_cash():
            return False, f"ATM has insufficient cash. Max: ₹{self.get_available_cash()}"
        if amount % 100 != 0:
            return False, "Amount must be in multiples of ₹100"
        return True, "OK"
    
    def dispense(self, amount: float) -> Optional[Dict[int, int]]:
        """
        Greedy denomination algorithm
        
        Returns: {denomination: count} or None if can't dispense
        
        Example:
        amount = 4700
        Available: {2000:20, 500:30, 200:50, 100:100}
        
        2000: 4700 // 2000 = 2, remainder = 700
        500:  700 // 500 = 1, remainder = 200
        200:  200 // 200 = 1, remainder = 0
        
        Result: {2000:2, 500:1, 200:1} = ₹4700 in 4 notes
        """
        can, msg = self.can_dispense(amount)
        if not can:
            return None
        
        with self._lock:
            result = {}
            remaining = int(amount)
            
            # Sorted denominations (largest first)
            for denom in sorted(self._notes.keys(), reverse=True):
                if remaining <= 0:
                    break
                
                notes_needed = remaining // denom
                notes_available = self._notes[denom]
                notes_to_use = min(notes_needed, notes_available)
                
                if notes_to_use > 0:
                    result[denom] = notes_to_use
                    remaining -= denom * notes_to_use
            
            if remaining > 0:
                # Greedy failed — can't make exact amount
                return None
            
            # Actually deduct from tray
            for denom, count in result.items():
                self._notes[denom] -= count
            
            return result
    
    def load_notes(self, denomination: int, count: int):
        """ATM restock karo"""
        self._notes[denomination] = self._notes.get(denomination, 0) + count
        print(f"[ATM] Loaded {count}x ₹{denomination} notes")
    
    def get_note_count(self) -> Dict[int, int]:
        return dict(self._notes)

# ===== BANK SERVICE (simulates backend) =====

class BankService:
    """
    Real mein: bank ka core banking API call hota hai
    Yahan: in-memory simulation
    """
    
    def __init__(self):
        self._accounts: Dict[str, BankAccount] = {}
        self._cards: Dict[str, Card] = {}
        self._transactions: List[Transaction] = []
    
    def create_account(self, holder_name: str, pin: str,
                       initial_balance: float = 10000.0) -> tuple[BankAccount, Card]:
        account = BankAccount(
            holder_name=holder_name,
            pin_hash=hashlib.sha256(pin.encode()).hexdigest(),
            balance=initial_balance
        )
        
        card = Card(
            card_number=f"4111{str(uuid.uuid4().int)[:12]}",
            account_id=account.account_id
        )
        
        self._accounts[account.account_id] = account
        self._cards[card.card_number] = card
        return account, card
    
    def get_account(self, account_id: str) -> Optional[BankAccount]:
        return self._accounts.get(account_id)
    
    def get_account_by_card(self, card_number: str) -> Optional[BankAccount]:
        card = self._cards.get(card_number)
        if not card:
            return None
        return self._accounts.get(card.account_id)
    
    def get_card(self, card_number: str) -> Optional[Card]:
        return self._cards.get(card_number)
    
    def save_transaction(self, txn: Transaction):
        self._transactions.append(txn)
    
    def get_mini_statement(self, account_id: str, n: int = 5) -> List[Transaction]:
        account_txns = [t for t in self._transactions if t.account_id == account_id]
        return sorted(account_txns, key=lambda t: t.timestamp, reverse=True)[:n]

# ===== ATM (State Machine) =====

class ATM:
    """
    Main ATM class — state machine implementation
    """
    
    PIN_ATTEMPTS_ALLOWED = 3
    SESSION_TIMEOUT_SECONDS = 60
    
    def __init__(self, atm_id: str, bank_service: BankService):
        self.atm_id = atm_id
        self.bank_service = bank_service
        self.cash_dispenser = CashDispenser()
        
        self._state: ATMState = ATMState.IDLE
        self._current_card: Optional[Card] = None
        self._current_account: Optional[BankAccount] = None
        self._pin_attempts: int = 0
        self._lock = threading.Lock()
    
    # ---- State Transitions ----
    
    def insert_card(self, card_number: str) -> str:
        with self._lock:
            if self._state != ATMState.IDLE:
                return "Please finish or cancel current session"
            
            if self._state == ATMState.OUT_OF_SERVICE:
                return "ATM is out of service"
            
            card = self.bank_service.get_card(card_number)
            if not card:
                return "Card not recognized"
            
            if not card.is_valid:
                return "Card is blocked/expired. Contact bank."
            
            account = self.bank_service.get_account(card.account_id)
            if not account:
                return "Account not found"
            
            if account.is_locked:
                return "Account locked due to multiple failed attempts. Contact bank."
            
            self._current_card = card
            self._current_account = account
            self._pin_attempts = 0
            self._transition(ATMState.CARD_INSERTED)
            
            return f"Welcome! Please enter your PIN. Card: {card.masked_number()}"
    
    def enter_pin(self, pin: str) -> str:
        with self._lock:
            if self._state != ATMState.CARD_INSERTED:
                return "Please insert card first"
            
            if len(pin) != 4 or not pin.isdigit():
                return "Invalid PIN format. Enter 4-digit PIN."
            
            if self._current_account.verify_pin(pin):
                self._current_account.reset_failed_attempts()
                self._transition(ATMState.AUTHENTICATED)
                return (f"PIN verified! Welcome {self._current_account.holder_name}.\n"
                        f"Balance: ₹{self._current_account.balance:,.2f}\n"
                        f"Choose: 1.Withdraw 2.Balance 3.Mini Statement 4.Exit")
            else:
                self._pin_attempts += 1
                self._current_account.record_failed_attempt()
                remaining = self.PIN_ATTEMPTS_ALLOWED - self._pin_attempts
                
                if remaining == 0:
                    self._eject_card()
                    return "Account locked! Too many wrong PINs. Please contact bank."
                
                return f"Wrong PIN. {remaining} attempt(s) remaining."
    
    def withdraw(self, amount: float) -> str:
        with self._lock:
            if self._state != ATMState.AUTHENTICATED:
                return "Please authenticate first"
            
            # Validate amount
            if amount <= 0:
                return "Invalid amount"
            if amount % 100 != 0:
                return "Amount must be in multiples of ₹100"
            
            # Account check
            can_withdraw, reason = self._current_account.can_withdraw(amount)
            if not can_withdraw:
                return reason
            
            # Cash check
            can_dispense, reason = self.cash_dispenser.can_dispense(amount)
            if not can_dispense:
                return reason
            
            self._transition(ATMState.DISPENSING)
            
            # Dispense cash
            notes = self.cash_dispenser.dispense(amount)
            if not notes:
                self._transition(ATMState.AUTHENTICATED)
                return f"Cannot dispense exact amount ₹{amount}. Try different amount."
            
            # Debit account
            self._current_account.debit(amount)
            
            # Save transaction
            txn = Transaction(
                account_id=self._current_account.account_id,
                txn_type=TransactionType.WITHDRAW,
                amount=amount,
                balance_after=self._current_account.balance,
                status=TransactionStatus.SUCCESS,
                atm_id=self.atm_id,
                notes_dispensed=notes
            )
            self.bank_service.save_transaction(txn)
            
            self._transition(ATMState.AUTHENTICATED)
            
            notes_str = ", ".join(f"{count}x₹{denom}" for denom, count in sorted(notes.items(), reverse=True))
            return (f"Dispensing ₹{amount:.0f} ({notes_str})\n"
                    f"Remaining balance: ₹{self._current_account.balance:,.2f}")
    
    def check_balance(self) -> str:
        with self._lock:
            if self._state != ATMState.AUTHENTICATED:
                return "Please authenticate first"
            
            return f"Available Balance: ₹{self._current_account.balance:,.2f}"
    
    def mini_statement(self) -> str:
        with self._lock:
            if self._state != ATMState.AUTHENTICATED:
                return "Please authenticate first"
            
            txns = self.bank_service.get_mini_statement(self._current_account.account_id)
            
            if not txns:
                return "No transactions found"
            
            lines = ["=== Mini Statement ==="]
            for t in txns:
                sign = "-" if t.txn_type == TransactionType.WITHDRAW else "+"
                lines.append(f"{t.timestamp.strftime('%d/%m %H:%M')} {sign}₹{t.amount:.0f} "
                              f"Bal:₹{t.balance_after:.0f}")
            return "\n".join(lines)
    
    def eject_card(self) -> str:
        with self._lock:
            return self._eject_card()
    
    def _eject_card(self) -> str:
        self._current_card = None
        self._current_account = None
        self._pin_attempts = 0
        self._transition(ATMState.IDLE)
        return "Card ejected. Thank you!"
    
    def _transition(self, new_state: ATMState):
        print(f"  [ATM] {self._state.value} → {new_state.value}")
        self._state = new_state
    
    def get_status(self) -> str:
        cash = self.cash_dispenser.get_available_cash()
        return (f"ATM {self.atm_id}: {self._state.value} | "
                f"Cash: ₹{cash:,.0f}")

# ===== DEMO =====

def demo():
    print("=" * 50)
    print("ATM SYSTEM DEMO")
    print("=" * 50)
    
    bank = BankService()
    atm = ATM("ATM001", bank)
    
    # Setup accounts
    ashish_acc, ashish_card = bank.create_account("Ashish Kumar", "1234", 50000.0)
    priya_acc, priya_card = bank.create_account("Priya Sharma", "5678", 5000.0)
    
    print(f"Ashish card: {ashish_card.masked_number()}")
    print(f"Priya card: {priya_card.masked_number()}")
    
    # Normal withdrawal
    print("\n--- Normal Withdrawal ---")
    print(atm.insert_card(ashish_card.card_number))
    print(atm.enter_pin("1234"))
    print(atm.withdraw(4700))   # Greedy: 2×2000 + 1×500 + 1×200
    print(atm.check_balance())
    print(atm.mini_statement())
    print(atm.eject_card())
    
    # Wrong PIN
    print("\n--- Wrong PIN (Account Lock) ---")
    print(atm.insert_card(priya_card.card_number))
    print(atm.enter_pin("0000"))  # Wrong
    print(atm.enter_pin("1111"))  # Wrong
    print(atm.enter_pin("2222"))  # Wrong → LOCKED
    
    # Denomination test
    print("\n--- Denomination Algorithm ---")
    dispenser = CashDispenser()
    for amount in [2000, 2700, 4500, 11600]:
        notes = dispenser.dispense(amount)
        if notes:
            notes_str = " + ".join(f"{c}×₹{d}" for d, c in sorted(notes.items(), reverse=True))
            print(f"  ₹{amount} = {notes_str}")
        else:
            print(f"  ₹{amount} = Cannot dispense")
    
    print(f"\n{atm.get_status()}")
    print("\n[Demo Complete]")

if __name__ == "__main__":
    demo()
```

---

## PART 2: ENGLISH — Interviewer ko bolne ke liye

### 2.1 Key Design Points

**State Machine:**
```
IDLE → CARD_INSERTED → AUTHENTICATED → DISPENSING → AUTHENTICATED → IDLE
                   → (wrong PIN x3) → IDLE (card ejected)
```

**Denomination Greedy Algorithm:**
```python
# Greedy: use largest denomination first to minimize note count
remaining = 4700
2000: 4700//2000=2 → use 2, remaining=700
500:  700//500=1  → use 1, remaining=200
200:  200//200=1  → use 1, remaining=0
Result: {2000:2, 500:1, 200:1} ← 4 notes total (optimal)
```

**Security:**
```
PIN stored as SHA256 hash (never plain text)
3 wrong attempts → account locked
Session timeout → auto-eject
Card masked on display (**** **** **** 1234)
```

### 2.2 Common Follow-up Q&A

**Q1: What if ATM dispenses cash but bank API fails?**
> "Two-phase commit pattern: (1) Reserve amount in pending state, (2) Dispense cash, (3) Confirm debit. If step 3 fails, reconciliation job at end of day compares ATM cash log vs bank records. Physical ATM logs every dispense with timestamp — used for dispute resolution. In practice, bank API is called BEFORE dispensing, not after."

**Q2: How do you prevent concurrent transactions on same account from 2 ATMs?**
> "Pessimistic locking on account record in core banking: SELECT ... FOR UPDATE. The lock is held for the entire transaction (verify balance → debit → confirm). Distributed lock via Redis for non-DB scenarios. Idempotency key: each ATM transaction has unique ID — if same ID processed twice, second is rejected."

**Q3: Denomination algorithm edge case?**
> "Greedy fails when only small denominations available. Example: need ₹300 but only have ₹200 notes → greedy gives 1×200=200, remaining=100, no ₹100 → fail. Solution: dynamic programming or backtracking for exact change. In practice, ATMs stock multiple denominations to avoid this. Greedy works 99% of cases."

---

## Interview Cheat Sheet

```
30-second pitch:
"ATM uses State Machine: IDLE → CARD_INSERTED → AUTHENTICATED → DISPENSING.
PIN stored as SHA256 hash. 3 wrong PINs → account locked.
Cash dispensing: greedy algorithm — largest denomination first.
Daily withdrawal limit tracked per calendar day."

Key security rules:
- PIN: SHA256 hash stored, never plain text
- 3 failed PIN attempts → account lock
- Card eject on session complete or timeout
- Amount multiples of ₹100 only
```
