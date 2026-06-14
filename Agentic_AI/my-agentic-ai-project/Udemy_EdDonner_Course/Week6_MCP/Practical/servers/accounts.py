"""
ACCOUNTS — Pure Business Logic (Lectures L114-L115)
====================================================

Ye file MCP se BILKUL independent hai — sirf plain Python business logic.
Ed Donner course me bhi YAHI pattern hai: Week-3 ke engineering-team capstone
me jo Account class CrewAI ne generate ki thi (humare repo me:
Week3_CrewAI/Practical/output/accounts.py), course usi ko Week-6 me uthakar
MCP server ke peeche laga deta hai. Lesson: MCP server banana = existing
business logic ke upar ek thin "tool wrapper" lagana, logic dobara likhna nahi.

Week-3 wale version se 2 upgrades (L115 me bhi yahi hota hai):
  1. PERSISTENCE — har mutation ke baad state JSON file me save hoti hai
     (output/accounts.json). Kyun? MCP server ek SUBPROCESS hai jo client ke
     saath start/stop hota hai — agar state sirf memory me rahe to har
     restart pe sab uda jayega. JSON file = server restarts ke beech bhi
     state zinda + lab4 (multi-server trader) isi file ko reuse karega.
  2. NAMED ACCOUNTS — ek hi file me multiple users ("Ashish", "Ed", ...) —
     kyunki MCP tools me LLM har call me account ka naam pass karega.

Guards: negative deposit/withdraw mana, balance se zyada withdraw/buy mana,
oversell mana, unknown symbol mana — ValueError raise hota hai jo FastMCP
LLM tak error message ke roop me pahuncha deta hai (LLM phir khud recover
karne ki koshish karta hai — ye dekhna bhi MCP ka maza hai).

Ye file directly nahi chalani — accounts_server.py isko import karta hai.
"""

import json
from pathlib import Path

# ---------------------------------------------------------------------------
# PERSISTENCE PATH — __file__ ke relative, cwd ke nahi!
# MCP server subprocess ka cwd kuch bhi ho sakta hai (client jahan se launch
# kare), isliye JSON ka path is file ki location se compute karte hain:
#   servers/accounts.py  ->  ../output/accounts.json
# ---------------------------------------------------------------------------
ACCOUNTS_DB = Path(__file__).resolve().parent.parent / "output" / "accounts.json"

# Fixed share prices — course me bhi pehle fixed prices se start karte hain,
# baad me (lab4) ek alag market/price server is role ko le leta hai.
SHARE_PRICES: dict[str, float] = {
    "AAPL": 150.0,
    "TSLA": 250.0,
    "GOOGL": 140.0,
    "MSFT": 400.0,
}


def get_share_price(symbol: str) -> float:
    """Symbol ka fixed price return karo; unknown symbol pe ValueError."""
    symbol = symbol.upper().strip()
    if symbol not in SHARE_PRICES:
        raise ValueError(
            f"Unknown symbol '{symbol}'. Available: {', '.join(SHARE_PRICES)}"
        )
    return SHARE_PRICES[symbol]


# ---------------------------------------------------------------------------
# JSON load/save helpers — poora DB ek dict hai: {"ashish": {...}, "ed": {...}}
# Itna chhota data hai ki har mutation pe poori file rewrite karna theek hai.
# (Production me SQLite/Postgres hota — concept wahi: server stateless nahi,
#  state external store me hai.)
# ---------------------------------------------------------------------------
def _load_all() -> dict:
    if ACCOUNTS_DB.exists():
        try:
            return json.loads(ACCOUNTS_DB.read_text())
        except json.JSONDecodeError:
            return {}  # corrupt/empty file — fresh start, crash mat karo
    return {}


def _save_all(db: dict) -> None:
    # NOTE: poori file ek hi baar rewrite hoti hai — single-process teaching demo
    # ke liye theek hai, par concurrent/parallel writers ke saath SAFE nahi
    # (do writes ek doosre ko overwrite kar sakti hain). Real system me DB ya
    # file-locking chahiye. (Yahi limitation lab4 me bhi acknowledged hai.)
    ACCOUNTS_DB.parent.mkdir(parents=True, exist_ok=True)
    ACCOUNTS_DB.write_text(json.dumps(db, indent=2))


class Account:
    """
    Week-3 capstone wali Account class ka persistent avatar.
    balance (cash) + holdings ({symbol: qty}) + total_deposits (P&L baseline).
    """

    def __init__(self, name: str):
        self.name = name.strip()
        self.balance: float = 0.0
        self.holdings: dict[str, int] = {}
        self.total_deposits: float = 0.0  # ab tak kitna cash daala — P&L iske against

    # ----- (de)serialization — JSON <-> object -----
    @classmethod
    def get(cls, name: str) -> "Account":
        """Account load karo; nahi mila to naya bana do (create-on-first-use)."""
        db = _load_all()
        acct = cls(name)
        data = db.get(acct._key())
        if data:
            acct.balance = data.get("balance", 0.0)
            acct.holdings = data.get("holdings", {})
            acct.total_deposits = data.get("total_deposits", 0.0)
        return acct

    def _key(self) -> str:
        return self.name.lower()

    def save(self) -> None:
        """Har mutation ke baad call hota hai — yahi persistence ka raaz hai."""
        db = _load_all()
        db[self._key()] = {
            "name": self.name,
            "balance": self.balance,
            "holdings": self.holdings,
            "total_deposits": self.total_deposits,
        }
        _save_all(db)

    # ----- operations (sab guards ke saath) -----
    def deposit(self, amount: float) -> None:
        if amount <= 0:
            raise ValueError("Deposit amount must be positive")
        self.balance += amount
        self.total_deposits += amount
        self.save()

    def withdraw(self, amount: float) -> None:
        if amount <= 0:
            raise ValueError("Withdrawal amount must be positive")
        if amount > self.balance:
            raise ValueError(
                f"Insufficient balance: have {self.balance:.2f}, asked {amount:.2f}"
            )
        self.balance -= amount
        self.save()

    def buy_shares(self, symbol: str, quantity: int) -> float:
        """Shares kharido; cost return karta hai. Negative balance NAMUMKIN."""
        symbol = symbol.upper().strip()
        if quantity <= 0:
            raise ValueError("Quantity must be positive")
        cost = get_share_price(symbol) * quantity
        if cost > self.balance:
            raise ValueError(
                f"Insufficient balance: need {cost:.2f}, have {self.balance:.2f}"
            )
        self.holdings[symbol] = self.holdings.get(symbol, 0) + quantity
        self.balance -= cost
        self.save()
        return cost

    def sell_shares(self, symbol: str, quantity: int) -> float:
        """Shares becho; revenue return karta hai. OVERSELL mana hai."""
        symbol = symbol.upper().strip()
        if quantity <= 0:
            raise ValueError("Quantity must be positive")
        held = self.holdings.get(symbol, 0)
        if quantity > held:
            raise ValueError(f"Cannot sell {quantity} {symbol}: only hold {held}")
        revenue = get_share_price(symbol) * quantity
        self.holdings[symbol] = held - quantity
        if self.holdings[symbol] == 0:
            del self.holdings[symbol]  # zero-qty entries clean rakho
        self.balance += revenue
        self.save()
        return revenue

    def portfolio_value(self) -> float:
        """Cash + (har holding ka current price * qty)."""
        return self.balance + sum(
            get_share_price(sym) * qty for sym, qty in self.holdings.items()
        )

    def profit_loss(self) -> float:
        """P&L = aaj ki total value - ab tak ka total deposited cash."""
        return self.portfolio_value() - self.total_deposits

    def summary(self) -> dict:
        """Ek dict me poora snapshot — MCP tools yahi return karenge."""
        return {
            "name": self.name,
            "cash_balance": round(self.balance, 2),
            "holdings": self.holdings,
            "portfolio_value": round(self.portfolio_value(), 2),
            "total_deposits": round(self.total_deposits, 2),
            "profit_loss": round(self.profit_loss(), 2),
        }

    def report_text(self) -> str:
        """Human-readable report — MCP RESOURCE (accounts://report/{name}) ke liye."""
        s = self.summary()
        lines = [
            f"ACCOUNT REPORT — {s['name']}",
            f"  Cash balance   : ${s['cash_balance']:,.2f}",
            f"  Holdings       : "
            + (
                ", ".join(f"{q} x {sym}" for sym, q in s["holdings"].items())
                or "(none)"
            ),
            f"  Portfolio value: ${s['portfolio_value']:,.2f}",
            f"  Total deposits : ${s['total_deposits']:,.2f}",
            f"  Profit / Loss  : ${s['profit_loss']:,.2f}",
        ]
        return "\n".join(lines)


def reset_account(name: str) -> None:
    """Testing/demo helper — account ko DB se uda do (idempotent lab runs)."""
    db = _load_all()
    db.pop(name.lower().strip(), None)
    _save_all(db)
