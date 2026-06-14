"""
ACCOUNTS MCP SERVER — FastMCP Wrapper (Lectures L116-L117)
===========================================================

L114-L117 ka EXACT pattern: existing business logic (accounts.py) ko MCP
tools me WIRE karna. Dhyan se dekho — is file me KOI business logic NAHI
hai. Har tool bas accounts.py ke function ko call karta hai. Yahi separation
course ka core lesson hai:

    accounts.py        = WHAT (business rules — MCP-agnostic, unit-testable)
    accounts_server.py = HOW EXPOSED (MCP protocol boundary — thin wrapper)

FastMCP decorators kya magic karte hain:
  @mcp.tool()     — function ka NAME + DOCSTRING + TYPE HINTS se JSON schema
                    auto-generate hota hai. Jab client list_tools karega,
                    LLM ko YAHI docstrings dikhengi — isliye docstrings ko
                    "LLM ke liye prompt" samajh ke likho, comments nahi!
  @mcp.resource() — tools ACTIONS hain (LLM decide karta hai kab call karna),
                    resources DATA hain (GET-jaisa, read-only, host/client
                    context me inject karta hai). URI template {name} se
                    parameterized resource banta hai.

Transport: stdio — ye server koi port nahi kholta. Client (lab2) isse
subprocess ki tarah launch karega aur stdin/stdout par JSON-RPC baat karega.
Isliye yahan print() KABHI mat karna — stdout protocol ka channel hai,
print karoge to JSON-RPC corrupt! (Debugging ke liye stderr use karo.)

Directly chalane ka matlab nahi hai (chalega, par stdin pe wait karega):
  uv run Udemy_EdDonner_Course/Week6_MCP/Practical/servers/accounts_server.py
Asli istemal: lab2_custom_accounts_server.py isse spawn karta hai.
"""

from mcp.server.fastmcp import FastMCP

# Same folder me hai, aur 'uv run <abs path>' script ki dir ko sys.path me
# daal deta hai — isliye plain import kaam karta hai.
from accounts import Account, get_share_price as _price_lookup, SHARE_PRICES

# Server ka naam — client side pe identification ke liye dikhta hai.
mcp = FastMCP("accounts_server")


# ---------------------------------------------------------------------------
# TOOLS — 7 actions jo LLM apni marzi se call kar sakta hai.
# Type hints (str, float, int) se FastMCP JSON schema banata hai; LLM ko
# pata hota hai kaunsa argument kis type ka chahiye.
# ---------------------------------------------------------------------------

@mcp.tool()
def get_balance(name: str) -> float:
    """Account holder ke naam se uska current CASH balance (USD) batata hai.
    Agar account exist nahi karta to 0.0 milega (account create-on-first-use hai)."""
    return Account.get(name).balance


@mcp.tool()
def deposit(name: str, amount: float) -> str:
    """Account me cash (USD) deposit karta hai. Amount positive hona chahiye.
    Naya balance confirm karke batata hai."""
    acct = Account.get(name)
    acct.deposit(amount)
    return f"Deposited ${amount:,.2f} into {acct.name}'s account. New cash balance: ${acct.balance:,.2f}"


@mcp.tool()
def withdraw(name: str, amount: float) -> str:
    """Account se cash (USD) withdraw karta hai. Balance se zyada withdraw
    allowed NAHI hai — error milega."""
    acct = Account.get(name)
    acct.withdraw(amount)
    return f"Withdrew ${amount:,.2f} from {acct.name}'s account. New cash balance: ${acct.balance:,.2f}"


@mcp.tool()
def buy_shares(name: str, symbol: str, quantity: int) -> str:
    """Account ke cash se shares kharidta hai (symbols: AAPL, TSLA, GOOGL, MSFT).
    Agar cash kam hai to purchase reject ho jayegi (negative balance mana hai)."""
    acct = Account.get(name)
    cost = acct.buy_shares(symbol, quantity)
    return (
        f"Bought {quantity} {symbol.upper()} for ${cost:,.2f}. "
        f"Cash left: ${acct.balance:,.2f}. Holdings: {acct.holdings}"
    )


@mcp.tool()
def sell_shares(name: str, symbol: str, quantity: int) -> str:
    """Account ki holdings se shares bechta hai. Jitne shares pass hain usse
    zyada bechna (oversell) allowed NAHI hai."""
    acct = Account.get(name)
    revenue = acct.sell_shares(symbol, quantity)
    return (
        f"Sold {quantity} {symbol.upper()} for ${revenue:,.2f}. "
        f"Cash now: ${acct.balance:,.2f}. Holdings: {acct.holdings}"
    )


@mcp.tool()
def get_portfolio(name: str) -> dict:
    """Account ka poora portfolio snapshot deta hai: cash balance, holdings
    (symbol -> quantity), total portfolio value, total deposits aur profit/loss.
    Summary dene se PEHLE ye tool zaroor call karo."""
    return Account.get(name).summary()


@mcp.tool()
def lookup_share_price(symbol: str) -> float:
    """Kisi share symbol ka current price (USD) batata hai.
    Supported symbols: AAPL, TSLA, GOOGL, MSFT."""
    return _price_lookup(symbol)


# ---------------------------------------------------------------------------
# RESOURCE — read-only data endpoint, URI template ke saath.
# Tool vs Resource ka farq (L117): tool ko LLM khud call karta hai (model-
# controlled), resource ko HOST application context ke liye fetch karta hai
# (application-controlled) — jaise Claude Desktop me attachments. URI me
# {name} parameter hai: accounts://report/ashish, accounts://report/ed ...
# ---------------------------------------------------------------------------
@mcp.resource("accounts://report/{name}")
def account_report(name: str) -> str:
    """Account holder ka human-readable report (balance, holdings, value, P&L)."""
    return Account.get(name).report_text()


if __name__ == "__main__":
    # stdio transport = stdin/stdout par JSON-RPC. Yahi default bhi hai,
    # par explicit likhna course ki aadat hai — taaki yaad rahe ki transport
    # ek CHOICE hai (stdio / sse / streamable-http).
    mcp.run(transport="stdio")
