"""
MARKET DATA SERVER (FastMCP, stdio) — Week 6 MCP, Lab 3 ka doosra server (L118-L121).

COURSE vs HUMARA SETUP
----------------------
Course me Ed POLYGON.io ka MCP server use karta hai (L119-L121): wo type (b)
server hai — LOCAL stdio process jo andar se REMOTE Polygon REST API call
karta hai (paid/free API key chahiye, EOD = end-of-day prices milte hain).

Humara FREE substitute: SIMULATED prices. Trick ye hai ki MCP ke nazariye se
agent ko FARAK NAHI PADTA — tool ka naam, args, return shape bilkul wahi hai
jo real Polygon server deta. Agent sirf tools/list dekhta hai aur call karta
hai; data asli hai ya simulated, ye server ka internal detail hai. Yahi MCP
ka asli sabak hai: SERVER SWAP karo, AGENT CODE same rehta hai.

DETERMINISM KA FUNDA: random.seed(f"{symbol}-{date}") — matlab ek hi din me
ek symbol ka price HAR call par SAME aayega (reproducible lab output), par
kal date badlegi to thoda drift aa jayega (realistic feel). Polygon ka EOD
price bhi din bhar fixed rehta hai — same behaviour model kiya hai.

RUN (standalone test): uv run Udemy_EdDonner_Course/Week6_MCP/Practical/servers/market_server.py
(normally lab3 client isse stdio subprocess ke roop me launch karta hai)
"""

import json
import random
from datetime import date, datetime
from pathlib import Path

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("market_server", log_level="ERROR")  # INFO logs stderr par shor karte hain

# Kuch jaane-pehchane tickers ke realistic base prices (USD).
# Unknown symbol aaye to hash se 20-500 ke beech ek stable base nikal lenge.
BASE_PRICES = {
    "AAPL": 228.0,
    "MSFT": 432.0,
    "GOOGL": 178.0,
    "AMZN": 205.0,
    "TSLA": 252.0,
    "NVDA": 138.0,
    "META": 585.0,
}

# Audit log: har quote yahan bhi likhte hain — Lab 3 verify karta hai ki
# market server ne genuinely file banayi (memory.json ke saath doosri JSON).
QUOTES_LOG = Path(__file__).resolve().parent.parent / "output" / "market_quotes.json"


def _quote(symbol: str) -> dict:
    """Ek symbol ka aaj ka deterministic simulated quote banao."""
    symbol = symbol.upper().strip()
    today = date.today().isoformat()
    # Seed = symbol + date => same din, same symbol => SAME price (reproducible).
    rng = random.Random(f"{symbol}-{today}")
    if symbol in BASE_PRICES:
        base = BASE_PRICES[symbol]
    else:
        # Unknown ticker: naam se hi stable base price derive karo.
        base = 20 + (sum(ord(c) for c in symbol) * 7919) % 481
    drift_pct = rng.uniform(-3.0, 3.0)  # chhota daily drift, +/- 3%
    price = round(base * (1 + drift_pct / 100), 2)
    return {
        "symbol": symbol,
        "price": price,
        "currency": "USD",
        "date": today,
        "change_pct_today": round(drift_pct, 2),
        "source": "simulated (course me yahan Polygon EOD hota)",
    }


def _log_quotes(quotes: list[dict]) -> None:
    """Quotes ko append-style JSON log me likho (server-side persistence demo)."""
    QUOTES_LOG.parent.mkdir(parents=True, exist_ok=True)
    log = []
    if QUOTES_LOG.exists():
        try:
            log = json.loads(QUOTES_LOG.read_text())
        except json.JSONDecodeError:
            log = []
    log.append({"at": datetime.now().isoformat(timespec="seconds"), "quotes": quotes})
    QUOTES_LOG.write_text(json.dumps(log, indent=2))


@mcp.tool()
def get_price(symbol: str) -> dict:
    """Ek stock symbol (jaise AAPL) ka aaj ka share price (USD) deta hai."""
    q = _quote(symbol)
    _log_quotes([q])
    return q


# Dict return (list nahi) — ek hi clean JSON text-content banta hai, jo chhote
# models ke liye parse karna easy hai aur empty-content edge cases nahi aate.
@mcp.tool()
def get_prices(symbols: list[str]) -> dict:
    """Kai stock symbols ke aaj ke prices ek saath deta hai (ek hi tool call me, sasta aur fast)."""
    quotes = [_quote(s) for s in symbols]
    _log_quotes(quotes)
    return {"count": len(quotes), "quotes": quotes}


@mcp.tool()
def market_summary() -> dict:
    """Sab tracked tickers ka aaj ka snapshot: sabse mehnga, sabse sasta, average price."""
    quotes = [_quote(s) for s in BASE_PRICES]
    prices = {q["symbol"]: q["price"] for q in quotes}
    cheapest = min(prices, key=prices.get)
    priciest = max(prices, key=prices.get)
    return {
        "date": date.today().isoformat(),
        "tracked": prices,
        "cheapest": {"symbol": cheapest, "price": prices[cheapest]},
        "most_expensive": {"symbol": priciest, "price": prices[priciest]},
        "average_price": round(sum(prices.values()) / len(prices), 2),
    }


if __name__ == "__main__":
    # stdio = stdin/stdout par JSON-RPC. print() yahan BAN hai (stream kharab
    # ho jayegi); isliye saari "output" tool return values ke through jaati hai.
    mcp.run(transport="stdio")
