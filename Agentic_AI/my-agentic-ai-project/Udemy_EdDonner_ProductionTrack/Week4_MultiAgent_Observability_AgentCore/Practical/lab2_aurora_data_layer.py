"""
LAB 2 — Aurora Serverless data layer for the multi-agent system (Repository pattern)
====================================================================================
Title: Multi-agent financial app ko ek REAL relational store chahiye — users / accounts /
       holdings. Hum ek REPOSITORY abstraction banate hain jiske peeche DO backend hote hain:
         1) AuroraDataApiBackend -> LAZY boto3 `rds-data` execute_statement (RDS Data API,
            DB_CLUSTER_ARN + DB_SECRET_ARN par) — REAL cloud path, Data API call ka SHAPE
            dikhata hai (HTTP SQL, koi persistent connection nahi).
         2) SqliteBackend       -> stdlib sqlite3 (DEFAULT offline path), bilkul SAME interface.
       Agents ko farak nahi padta andar kaun chala — yahi repository pattern ka point hai.
       Bina kisi key / AWS / boto3 / network ke bhi pura chalta hai aur EXIT 0 karta hai.

KYA SEEKHENGE (what concepts):
- KYUN Aurora Serverless v2 spiky AGENTIC workloads ke liye (L91):
    * Agentic jobs BURST-Y hote hain — kabhi 0 requests, kabhi achanak 50 parallel agent runs.
    * Aurora Serverless v2 ACUs (Aurora Capacity Units) ko AUTO-SCALE karta hai (min..max),
      aur idle par near-zero tak SCALE-DOWN — yaani 24/7 peak-capacity instance nahi chalana.
    * PAY-FOR-CAPACITY model: tum use ki gayi ACU-hours ke paise dete ho, na ki fixed box ke.
      Startup ko sasta, enterprise ko bina downtime ramp-up — dono fit (L91 ka core point).
- RDS DATA API kya hai aur Lambda ke liye PERFECT kyun (L92/L93):
    * Data API = HTTP-over-SQL. Tum `rds-data:ExecuteStatement` call karte ho cluster ARN +
      Secrets Manager secret ARN ke saath. Koi host/port/password/persistent TCP connection NAHI.
    * Lambda + RDS ka classic PAIN: har cold-start ek naya DB connection kholta hai; concurrency
      spike par connections EXHAUST ho jaate (max_connections limit). Data API HTTP request-response
      hai — connection pool maintain karne ka jhanjhat hi nahi. Serverless ke liye made-for-each-other.
    * Auth IAM + Secrets Manager se (password code me nahi) — isliye host/port nahi, ARNs chahiye.
- CONNECTION-MANAGEMENT pain in serverless: traditionally tum SQLAlchemy engine/pool banake reuse
  karte ho. Lambda me execution context freeze/thaw hota hai; pools leak/stale ho jaate. Data API
  is poore problem ko side-step karta hai (stateless HTTP). Yeh lab dono ko side-by-side dikhata.
- REPOSITORY PATTERN: ek interface (`Repository`) + do swappable backends. Agent code sirf
  `repo.get_portfolio(user_id)` bolta — usse pata bhi nahi DB SQLite hai ya Aurora. Test me SQLite,
  prod me Aurora. Yahi "agents do not care which DB" wala decoupling (L94 ka data-model isi ke peeche).
- SCHEMA (L94 simplified): users -> accounts -> holdings. (Ed isko "positions" bolta; task me
  "holdings" — same cheez: ek account me kitne shares of an instrument.) `clerk_user_id` multi-tenant
  isolation ka anchor (har query user se scope ho, warna cross-tenant data leak — prod SaaS ka #1 risk).
- PYDANTIC typed rows: get_portfolio() raw dict-soup nahi, TYPED pydantic models return karta
  (User/Account/Holding/Portfolio) — agents ko structured, validated output milta (L97 ka shape).

KAISE CHALANA (how to run) — CWD = repo root:
    # Default: self-demo (no key / no AWS / no boto3 / no network bhi chalega, exit 0)
    uv run Udemy_EdDonner_ProductionTrack/Week4_MultiAgent_Observability_AgentCore/Practical/lab2_aurora_data_layer.py

    # Demo ke baad local sqlite file rakhni ho (persistence dobara dekhne ke liye):
    uv run Udemy_EdDonner_ProductionTrack/Week4_MultiAgent_Observability_AgentCore/Practical/lab2_aurora_data_layer.py --keep-db

LECTURE MAPPING: Ed Donner "AI Engineer Production Track", Week 4 · Day 1 (L91-L94).
  L91 = DB architecture for production AI — RDS umbrella, Aurora engine, Aurora Serverless v2.
        "Kyun Aurora Serverless v2" (auto-scale ACU, scale-to-near-zero, pay-as-you-go) yahin se.
  L92 = Setting up Aurora Serverless DB — IAM `Alex RDS policy` (rds:*, rds-data:*,
        secretsmanager:GetSecretValue), `aws rds describe-db-clusters` verify, terraform
        5_database apply (min_capacity 0.5 / max_capacity 2 ACU, ~$43/mo). IAM shape niche comments me.
  L93 = Aurora infra + migrations — terraform outputs (cluster_arn + secret_arn) ko `.env` me copy,
        `test_data_api` (RDS client connect), `run_migrations.py` (17 migrations = schema banao),
        `seed_data.py` (22 ETF instruments). Hamara init_schema() = isi "migrations" ka offline analog.
  L94 = Production DB schema + test data — model: users -> accounts -> positions -> instruments
        (+ jobs), clerk_user_id multi-tenancy, `reset_db --with-test-data` (user_001: 3 accounts,
        5 positions). Hamara self-demo isi shape ka offline analog (user + accounts + holdings + query).
  NOTE: Ed deployment par focus karta (Terraform/IAM); yeh lab usi schema ko CODE side se complete
  karta — ek portable Repository jo Data API (prod) aur SQLite (test/offline) dono par chalti hai.

DEPLOY RUNBOOK (real cloud, jab AWS ho): terraform/5_database apply -> outputs (cluster_arn +
  secret_arn) ko `.env` me daalo -> AuroraDataApiBackend khud-ba-khud pick ho jaata hai (DB_CLUSTER_ARN
  set hote hi). init_schema()/upsert_account()/add_holding()/get_portfolio() ka SAME code Lambda
  agents me reuse hota — sirf backend swap. (Har terraform destroy/apply par ARNs badalte => `.env`
  re-copy — L94 ka critical reminder.)

COST: Is lab ko LOCALLY chalana = $0 (stdlib sqlite3, koi boto3/network/AWS nahi). REAL Aurora
  Serverless v2 deploy (L92): min 0.5 / max 2 ACU ~ $43/month agar 24/7 up. Data API requests
  per-million charge (paise me). `terraform destroy` daily karke sirf use-time chalao => kuch hi
  dollars. Credits ho to ~$0. (Yeh lab ek bhi paisa AWS par nahi lagata — sab offline.)
"""

import json
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

# .env load. override=True => .env value shell ki purani value ko jeet jaaye (Ed convention).
# Yahin se DB_CLUSTER_ARN / DB_SECRET_ARN / AWS_REGION uthega (agar set ho) — warna sab None.
load_dotenv(override=True)

# pydantic hamare env me available hai (crewai/langchain transitively laate hain). Typed rows
# isi se — taaki get_portfolio() raw dicts nahi, validated structured output de (L97 ka shape).
from pydantic import BaseModel, Field  # noqa: E402  (load_dotenv ke baad — Ed style)


# ===========================================================================
# Local _data/ dir — sqlite file yahin (clearly-named), repo me ganda na ho.
# ===========================================================================
# WHY ek dedicated _data/ dir: temp files ko ek predictable jagah rakhte hain taaki demo ke
# baad cleanup easy ho (default: delete; --keep-db: rehne do persistence dobara dekhne ke liye).
DATA_DIR = Path(__file__).resolve().parent / "_data"
DEFAULT_DB_PATH = DATA_DIR / "lab2_portfolio.db"


def _now_iso() -> str:
    """UTC timestamp (ISO). DB rows me created_at ke liye — timezone-aware, deterministic shape."""
    return datetime.now(timezone.utc).isoformat()


# ===========================================================================
# ############  TYPED ROWS — pydantic models (L97 ka structured-output shape)  ####
# ===========================================================================
# Repository raw tuples/dicts nahi, in TYPED models me data deti hai. WHY: agents ko predictable,
# validated structure milta hai (galat type => pydantic crash karega, silent corruption nahi).
# Yeh wahi "structured outputs" idea hai jo multi-agent system me har agent ke beech contract banata.

class Holding(BaseModel):
    """Ek holding/position: account ke andar kisi instrument (symbol) ki kitni quantity.
    (Ed isko 'position' bolta — L94. Task me 'holdings' — same entity.)"""
    symbol: str                       # e.g. "SPY", "IBM" — instrument ka ticker
    quantity: float                   # kitne shares (Ed ka example: "10 IBM" => quantity=10)
    avg_cost: float = 0.0             # average buy price (cost-basis ke liye)


class Account(BaseModel):
    """Ek user ka account (brokerage / retirement / savings). Ek user ke MANY accounts (L94)."""
    account_id: str
    account_type: str                 # "brokerage" | "retirement" | "savings"
    holdings: list[Holding] = Field(default_factory=list)


class User(BaseModel):
    """SaaS user — clerk_user_id se keyed (multi-tenant isolation ka anchor, L94)."""
    user_id: str
    clerk_user_id: str
    email: str


class Portfolio(BaseModel):
    """get_portfolio(user_id) ka COMPOSED result: user + uske saare accounts + har account ke
    holdings. Yeh ek hi typed object agent ko poora portfolio context de deta (L95 context-eng.)."""
    user: User
    accounts: list[Account] = Field(default_factory=list)

    def total_positions(self) -> int:
        """Convenience: kitni total holdings (sab accounts milake). Demo print me kaam aata."""
        return sum(len(a.holdings) for a in self.accounts)


# ===========================================================================
# ############  SCHEMA (DDL) — L93/L94 ka 'migrations' ka offline analog  #####
# ===========================================================================
# init_schema() in 3 tables ko banata hai. SQLite aur Aurora/Postgres DDL me chhote farak hote
# (e.g. autoincrement syntax), par hum portable SQL rakhte hain (TEXT keys, explicit columns).
# WHY foreign keys: users -> accounts -> holdings ka relational integrity (orphan holding na bane).
# Yeh wahi normalized schema hai jo Ed ne L94 me dikhaya (positions/holdings -> account -> user).
SCHEMA_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS users (
        user_id        TEXT PRIMARY KEY,
        clerk_user_id  TEXT NOT NULL UNIQUE,   -- multi-tenant key: har query isi se scope ho
        email          TEXT NOT NULL,
        created_at     TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS accounts (
        account_id    TEXT PRIMARY KEY,
        user_id       TEXT NOT NULL,
        account_type  TEXT NOT NULL,           -- brokerage | retirement | savings
        created_at    TEXT NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users(user_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS holdings (
        holding_id   TEXT PRIMARY KEY,
        account_id   TEXT NOT NULL,
        symbol       TEXT NOT NULL,            -- instrument ticker (SPY/IBM...) — L94 simplification
        quantity     REAL NOT NULL,            -- kitne shares
        avg_cost     REAL NOT NULL DEFAULT 0,  -- cost-basis
        created_at   TEXT NOT NULL,
        FOREIGN KEY (account_id) REFERENCES accounts(account_id)
    )
    """,
]


# ===========================================================================
# ############  REPOSITORY INTERFACE — abstraction agents use karte hain  #####
# ===========================================================================
# Yeh "interface" hai (Python me explicit ABC ya bas ek shared method-set). DONO backends isi
# shape ko implement karte hain. Agent code sirf in 4 methods ko jaanta — backend ka naam nahi.
#   init_schema()                              -> tables banao (migrations analog)
#   upsert_account(user, account)             -> user + account create/update (idempotent)
#   add_holding(account_id, holding)          -> ek holding insert
#   get_portfolio(user_id) -> Portfolio       -> typed portfolio compose karke do
# WHY abstraction: test/offline me SqliteBackend, prod Lambda me AuroraDataApiBackend — ZERO
# agent-code change. Yahi "agents do not care which DB" ka concrete implementation hai.


class Repository:
    """Base class (interface). Subclass DONO same 4 methods deti hain. Hum yahaan NotImplemented
    raise karte taaki galti se base ko seedha use karne par clear error mile (contract enforce)."""

    name = "abstract"

    def init_schema(self) -> None:
        raise NotImplementedError

    def upsert_account(self, user: User, account: Account) -> None:
        raise NotImplementedError

    def add_holding(self, account_id: str, holding: Holding) -> None:
        raise NotImplementedError

    def get_portfolio(self, user_id: str) -> Optional[Portfolio]:
        raise NotImplementedError


# ===========================================================================
# ############  BACKEND 1 — SqliteBackend (DEFAULT, offline, stdlib)  #########
# ===========================================================================
# stdlib sqlite3 — koi pip-install, koi network, koi AWS. Yeh hamara DEFAULT path hai taaki lab
# har machine par chale (CI, laptop, is sandboxed env). Interface bilkul wahi jo Aurora wala deta —
# isliye agent code dono ke beech bina change swap ho jaata. Persistence: file-based DB (re-open
# par data wapas milta), jo prod relational store ka faithful chhota analog hai.
class SqliteBackend(Repository):
    name = "sqlite (offline, stdlib)"

    def __init__(self, db_path: Path = DEFAULT_DB_PATH):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)  # _data/ ensure
        # NOTE: har method apna connection kholta+band karta — Lambda-style stateless access
        # ko mimic karne ke liye (no long-lived pool). PRAGMA foreign_keys ON taaki FK enforce ho.

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA foreign_keys = ON")  # SQLite default OFF hai — explicitly ON karo
        return conn

    def init_schema(self) -> None:
        with self._connect() as conn:
            for ddl in SCHEMA_STATEMENTS:
                conn.execute(ddl)
            conn.commit()

    def upsert_account(self, user: User, account: Account) -> None:
        """User + account dono ko idempotently create/update. WHY upsert: agent re-run par
        duplicate-key crash na ho — yeh production data-layer ka common requirement hai.
        SQLite me INSERT ... ON CONFLICT DO UPDATE (UPSERT) use karte hain."""
        ts = _now_iso()
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO users (user_id, clerk_user_id, email, created_at)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(user_id) DO UPDATE SET
                       clerk_user_id = excluded.clerk_user_id,
                       email = excluded.email""",
                (user.user_id, user.clerk_user_id, user.email, ts),
            )
            conn.execute(
                """INSERT INTO accounts (account_id, user_id, account_type, created_at)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(account_id) DO UPDATE SET
                       account_type = excluded.account_type""",
                (account.account_id, user.user_id, account.account_type, ts),
            )
            conn.commit()

    def add_holding(self, account_id: str, holding: Holding) -> None:
        ts = _now_iso()
        # holding_id ko deterministic banate (account+symbol) taaki re-run par duplicate na bane —
        # ON CONFLICT se quantity update ho jaaye (agent buy/sell par quantity badal sakta).
        holding_id = f"{account_id}:{holding.symbol}"
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO holdings
                       (holding_id, account_id, symbol, quantity, avg_cost, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)
                   ON CONFLICT(holding_id) DO UPDATE SET
                       quantity = excluded.quantity,
                       avg_cost = excluded.avg_cost""",
                (holding_id, account_id, holding.symbol, holding.quantity,
                 holding.avg_cost, ts),
            )
            conn.commit()

    def get_portfolio(self, user_id: str) -> Optional[Portfolio]:
        """user_id se poora portfolio compose karo: user -> accounts -> holdings, ek typed
        Portfolio object. Multi-tenant: SAB queries user_id par scoped (cross-tenant leak na ho)."""
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row  # dict-like rows (column name se access)
            urow = conn.execute(
                "SELECT user_id, clerk_user_id, email FROM users WHERE user_id = ?",
                (user_id,),
            ).fetchone()
            if urow is None:
                return None  # user nahi mila — None (agent yahaan "not found" handle kare)
            user = User(user_id=urow["user_id"], clerk_user_id=urow["clerk_user_id"],
                        email=urow["email"])

            accounts: list[Account] = []
            arows = conn.execute(
                "SELECT account_id, account_type FROM accounts WHERE user_id = ?",
                (user_id,),
            ).fetchall()
            for arow in arows:
                hrows = conn.execute(
                    "SELECT symbol, quantity, avg_cost FROM holdings WHERE account_id = ?",
                    (arow["account_id"],),
                ).fetchall()
                holdings = [Holding(symbol=h["symbol"], quantity=h["quantity"],
                                    avg_cost=h["avg_cost"]) for h in hrows]
                accounts.append(Account(account_id=arow["account_id"],
                                        account_type=arow["account_type"], holdings=holdings))
            return Portfolio(user=user, accounts=accounts)


# ===========================================================================
# ############  BACKEND 2 — AuroraDataApiBackend (REAL cloud, LAZY boto3)  ####
# ===========================================================================
# Yeh PROD path hai — RDS Data API (HTTP-over-SQL). Is env me boto3 NAHI + AWS creds NAHI, isliye
# yeh kabhi actually network nahi maarta. Iska kaam: (1) Data API call ka EXACT SHAPE dikhana,
# (2) graceful-degrade — boto3/ARNs missing ho to clean Hinglish note ke saath SqliteBackend par girna.
#
# RDS DATA API ka core call (reference — niche execute_statement me actual shape):
#   client = boto3.client("rds-data", region_name=region)
#   client.execute_statement(
#       resourceArn = DB_CLUSTER_ARN,      # Aurora cluster ka ARN (L93 terraform output)
#       secretArn   = DB_SECRET_ARN,       # Secrets Manager me DB creds (L92/L93)
#       database    = "alex",
#       sql         = "INSERT INTO accounts (...) VALUES (:account_id, :user_id, ...)",
#       parameters  = [ {"name": "account_id", "value": {"stringValue": "..."}}, ... ],
#   )
# Dhyaan: koi host/port/password/connection-pool NAHI. Sirf 2 ARNs + IAM creds. HTTP request-response.
# Yahi Lambda ke liye perfect hai — cold-start par connection kholna/pool manage karna nahi.
class AuroraDataApiBackend(Repository):
    name = "aurora-data-api (boto3 rds-data)"

    def __init__(self, cluster_arn: str, secret_arn: str,
                 database: str = "alex", region: Optional[str] = None):
        self.cluster_arn = cluster_arn
        self.secret_arn = secret_arn
        self.database = database
        self.region = region or os.getenv("AWS_REGION", "us-east-1")
        self._client = None  # lazy boto3 client (pehli zaroorat par banega)

    def _get_client(self):
        """LAZY boto3 `rds-data` client. boto3 missing ho to RuntimeError (make_repository pakad
        ke SqliteBackend par fall karega). WHY lazy: module top par boto3 import => poori file is
        env me crash. Isliye import yahin, try/except me — graceful degrade ka heart."""
        if self._client is not None:
            return self._client
        try:
            import boto3  # noqa: F401  (LAZY on purpose — env me ho bhi sakta, nahi bhi)
        except ImportError as e:
            raise RuntimeError(
                "boto3 missing => RDS Data API use nahi ho sakta. "
                f"AWS not available -> SqliteBackend (offline) fallback. (detail: {e})"
            )
        # REAL client banta (sirf jab boto3 + creds ho). Is offline lab me yahaan pahunchega bhi
        # to invoke par creds na hone se exception aayega — make_repository ne usse pehle hi probe
        # kar liya hoga aur fallback chuna hoga.
        self._client = boto3.client("rds-data", region_name=self.region)
        return self._client

    @staticmethod
    def _param(name: str, value) -> dict:
        """Ek Python value ko Data API parameter dict me badlo. Data API har value ko ek TYPED
        wrapper maangta ({"stringValue": ...} / {"doubleValue": ...}) — yahi uska wire-format hai.
        WHY: Data API JSON-over-HTTP hai, isliye native driver ke types ki jagah explicit typing."""
        if isinstance(value, bool):
            v = {"booleanValue": value}
        elif isinstance(value, int):
            v = {"longValue": value}
        elif isinstance(value, float):
            v = {"doubleValue": value}
        else:
            v = {"stringValue": str(value)}
        return {"name": name, "value": v}

    def _execute(self, sql: str, params: Optional[dict] = None) -> dict:
        """Ek Data API execute_statement wrapper. Named params (:foo) ko typed Data API parameters
        me badalta hai. Yeh function hi 'koi persistent connection nahi, sirf HTTP call' ko embody
        karta hai — har call independent, stateless (Lambda-friendly)."""
        client = self._get_client()
        data_api_params = [self._param(k, v) for k, v in (params or {}).items()]
        # *** YEH hai asal Data API call (is offline env me invoke nahi hoga) ***
        return client.execute_statement(
            resourceArn=self.cluster_arn,
            secretArn=self.secret_arn,
            database=self.database,
            sql=sql,
            parameters=data_api_params,
        )

    def init_schema(self) -> None:
        for ddl in SCHEMA_STATEMENTS:
            self._execute(ddl)  # har DDL ek alag Data API call (HTTP), no transaction-pool needed

    def upsert_account(self, user: User, account: Account) -> None:
        ts = _now_iso()
        # NOTE: Postgres/Aurora me UPSERT same INSERT ... ON CONFLICT syntax leta. Named params
        # (:user_id) Data API ke through bind hote — SQL-injection-safe, driver-level escaping.
        self._execute(
            """INSERT INTO users (user_id, clerk_user_id, email, created_at)
               VALUES (:user_id, :clerk_user_id, :email, :created_at)
               ON CONFLICT(user_id) DO UPDATE SET
                   clerk_user_id = EXCLUDED.clerk_user_id, email = EXCLUDED.email""",
            {"user_id": user.user_id, "clerk_user_id": user.clerk_user_id,
             "email": user.email, "created_at": ts},
        )
        self._execute(
            """INSERT INTO accounts (account_id, user_id, account_type, created_at)
               VALUES (:account_id, :user_id, :account_type, :created_at)
               ON CONFLICT(account_id) DO UPDATE SET account_type = EXCLUDED.account_type""",
            {"account_id": account.account_id, "user_id": user.user_id,
             "account_type": account.account_type, "created_at": ts},
        )

    def add_holding(self, account_id: str, holding: Holding) -> None:
        ts = _now_iso()
        holding_id = f"{account_id}:{holding.symbol}"
        self._execute(
            """INSERT INTO holdings
                   (holding_id, account_id, symbol, quantity, avg_cost, created_at)
               VALUES (:holding_id, :account_id, :symbol, :quantity, :avg_cost, :created_at)
               ON CONFLICT(holding_id) DO UPDATE SET
                   quantity = EXCLUDED.quantity, avg_cost = EXCLUDED.avg_cost""",
            {"holding_id": holding_id, "account_id": account_id, "symbol": holding.symbol,
             "quantity": holding.quantity, "avg_cost": holding.avg_cost, "created_at": ts},
        )

    def get_portfolio(self, user_id: str) -> Optional[Portfolio]:
        """Data API ke records ko parse karke typed Portfolio banao. execute_statement ka result
        {"records": [[{"stringValue": ...}, ...], ...]} shape me aata — usse pydantic me map karte.
        (Is offline lab me yeh path nahi chalta; SqliteBackend wala same kaam karta hai.)"""
        urow = self._execute(
            "SELECT user_id, clerk_user_id, email FROM users WHERE user_id = :uid",
            {"uid": user_id},
        )
        records = urow.get("records", [])
        if not records:
            return None
        # Data API har cell ek typed-dict deta — niche _cell() se raw value nikalte hain.
        r0 = records[0]
        user = User(user_id=self._cell(r0[0]), clerk_user_id=self._cell(r0[1]),
                    email=self._cell(r0[2]))
        arows = self._execute(
            "SELECT account_id, account_type FROM accounts WHERE user_id = :uid",
            {"uid": user_id},
        ).get("records", [])
        accounts: list[Account] = []
        for ar in arows:
            acc_id = self._cell(ar[0])
            hrows = self._execute(
                "SELECT symbol, quantity, avg_cost FROM holdings WHERE account_id = :aid",
                {"aid": acc_id},
            ).get("records", [])
            holdings = [Holding(symbol=self._cell(h[0]), quantity=float(self._cell(h[1])),
                                avg_cost=float(self._cell(h[2]))) for h in hrows]
            accounts.append(Account(account_id=acc_id, account_type=self._cell(ar[1]),
                                    holdings=holdings))
        return Portfolio(user=user, accounts=accounts)

    @staticmethod
    def _cell(cell: dict):
        """Data API ka ek result cell ({"stringValue": "x"} / {"longValue": 3} / ...) -> raw value.
        isNull bhi handle karte. Yeh wahi 'typed wire-format ko Python me wapas' wala unwrap hai."""
        if cell.get("isNull"):
            return None
        for k in ("stringValue", "longValue", "doubleValue", "booleanValue"):
            if k in cell:
                return cell[k]
        return None


# ===========================================================================
# ############  make_repository() — config se backend chuno (provider-abstr.)  ####
# ===========================================================================
# Yahi decide karta hai kaun chalega — bilkul L84 ka provider-abstraction idea, par DB ke liye.
# Rule: DB_CLUSTER_ARN + DB_SECRET_ARN env me set hain => Aurora try karo; boto3/creds missing ho
# to clean Hinglish note ke saath SqliteBackend par giro. ARNs unset => seedha SqliteBackend (offline).
# Caller (agent) ko ek hi Repository milti — usse pata bhi nahi andar kaun chala.
def make_repository(db_path: Path = DEFAULT_DB_PATH) -> Repository:
    cluster_arn = os.getenv("DB_CLUSTER_ARN")
    secret_arn = os.getenv("DB_SECRET_ARN")

    if cluster_arn and secret_arn:
        repo = AuroraDataApiBackend(cluster_arn=cluster_arn, secret_arn=secret_arn)
        try:
            repo._get_client()  # AVAILABILITY probe — boto3 import. fail => fallback
            print("[INFO] DB_CLUSTER_ARN + DB_SECRET_ARN mile => AuroraDataApiBackend (REAL prod path).")
            return repo
        except RuntimeError as e:
            print(f"[INFO] {e}")
            print("[INFO] Aurora unavailable => SqliteBackend (offline, $0) par switch.")
    else:
        # Sabse common offline case — ARNs hi set nahi. Clean note, seedha sqlite.
        print("[INFO] DB_CLUSTER_ARN / DB_SECRET_ARN nahi mile => SqliteBackend (offline, $0).")
        print("[INFO] Real Aurora ke liye: terraform 5_database apply -> outputs ko .env me copy (L93).")
    return SqliteBackend(db_path=db_path)


# ===========================================================================
# ############  Test fixtures — L94 ka 'reset_db --with-test-data' analog  ####
# ===========================================================================
# Ed ka test data: user_001 ke 3 accounts + 5 positions. Hum waisa hi ek chhota fixture banate
# hain (1 user, 2 accounts, kuch holdings) taaki get_portfolio() ka pura output dikhe.
def seed_test_data(repo: Repository) -> str:
    """Ek test user + 2 accounts + holdings populate karo (offline analog of L94 seed). Return user_id."""
    user = User(user_id="user_001", clerk_user_id="clerk_abc123",
                email="alex@example.com")

    brokerage = Account(account_id="acct_brokerage_1", account_type="brokerage")
    retirement = Account(account_id="acct_401k_1", account_type="retirement")

    # WHY upsert pehle (holdings se pehle): FK ki wajah se account pehle exist karna chahiye.
    repo.upsert_account(user, brokerage)
    repo.upsert_account(user, retirement)

    # Holdings — Ed ke ETF examples (SPY etc., L93). Quantity/avg_cost realistic-ish.
    repo.add_holding(brokerage.account_id, Holding(symbol="SPY", quantity=10, avg_cost=420.50))
    repo.add_holding(brokerage.account_id, Holding(symbol="IBM", quantity=25, avg_cost=140.10))
    repo.add_holding(retirement.account_id, Holding(symbol="VTI", quantity=50, avg_cost=230.75))
    repo.add_holding(retirement.account_id, Holding(symbol="BND", quantity=100, avg_cost=72.40))
    return user.user_id


def print_portfolio(portfolio: Optional[Portfolio]) -> None:
    """Ek typed Portfolio ko padhne-layak print karo (agent ko yeh structured context milta)."""
    if portfolio is None:
        print("    (portfolio not found — user_id galat ya DB empty)")
        return
    u = portfolio.user
    print(f"    user      : {u.user_id}  (clerk={u.clerk_user_id}, email={u.email})")
    print(f"    accounts  : {len(portfolio.accounts)}   total holdings: {portfolio.total_positions()}")
    for acc in portfolio.accounts:
        print(f"      - [{acc.account_type:<10}] {acc.account_id}")
        for h in acc.holdings:
            print(f"          {h.symbol:<5}  qty={h.quantity:<7g}  avg_cost={h.avg_cost}")


# ===========================================================================
# SELF-DEMO — `uv run <file>` (no args) yahan. No key / no AWS / no boto3 => exit 0.
# ===========================================================================
# Shape L93/L94 jaisa: schema banao (migrations analog) -> test data seed -> get_portfolio query ->
# print. Phir PERSISTENCE prove karo (DB re-open karke wahi data wapas mile). Phir cleanup, exit 0.
def run_self_demo(keep_db: bool = False) -> None:
    print("\n" + "#" * 76)
    print("#  LAB 2 SELF-DEMO — Aurora Serverless data layer (Repository pattern)")
    print("#  (no key / no AWS / no boto3 / no network bhi OK — exit 0)")
    print("#" * 76 + "\n")

    # --- Fresh start: pichli demo ki sqlite file (agar ho) hata do (clean slate, L94 reset) ---
    if DEFAULT_DB_PATH.exists():
        DEFAULT_DB_PATH.unlink()

    # --- 1) Backend chuno (provider-abstraction) ---------------------------
    print("=" * 76)
    print("[1] make_repository()  — config se backend pick (Aurora prod vs sqlite offline)")
    print("=" * 76)
    repo = make_repository()
    print(f"    chosen backend  = {repo.name}")
    print()

    # --- 2) init_schema (migrations analog, L93) ---------------------------
    print("=" * 76)
    print("[2] init_schema()  — users / accounts / holdings tables (L93 'run_migrations' analog)")
    print("=" * 76)
    repo.init_schema()
    print("    schema ready  -> tables: users, accounts, holdings")
    print()

    # --- 3) seed test data (L94 reset_db --with-test-data analog) -----------
    print("=" * 76)
    print("[3] seed_test_data()  — 1 user + 2 accounts + 4 holdings (L94 test-data analog)")
    print("=" * 76)
    user_id = seed_test_data(repo)
    print(f"    seeded user_id  = {user_id}  (upsert_account + add_holding)")
    print()

    # --- 4) get_portfolio query (typed Portfolio) --------------------------
    print("=" * 76)
    print("[4] get_portfolio(user_id)  — typed Portfolio (agent ko structured context milta)")
    print("=" * 76)
    portfolio = repo.get_portfolio(user_id)
    print_portfolio(portfolio)
    print()
    # JSON dump bhi dikhao — yeh exactly wo shape hai jo agent/Lambda response me jaata.
    if portfolio is not None:
        print("    --- portfolio as JSON (agent/Lambda response shape) ---")
        as_json = json.dumps(portfolio.model_dump(), indent=2)
        for line in as_json.splitlines():
            print(f"    {line}")
    print()

    # --- 5) PERSISTENCE proof — DB re-open karke wahi data wapas mile -------
    print("=" * 76)
    print("[5] PERSISTENCE proof  — naya Repository (DB re-open) se wahi data milta?")
    print("=" * 76)
    if isinstance(repo, SqliteBackend):
        repo2 = SqliteBackend(db_path=DEFAULT_DB_PATH)  # FRESH connection, same file
        portfolio2 = repo2.get_portfolio(user_id)
        ok = (portfolio2 is not None
              and portfolio2.total_positions() == (portfolio.total_positions() if portfolio else -1))
        print(f"    re-open backend = {repo2.name}")
        print(f"    same data?      = {ok}  (re-opened total holdings: "
              f"{portfolio2.total_positions() if portfolio2 else 'n/a'})")
        print("    => file-based sqlite => data persist hua (prod Aurora bhi persist karta, durable).")
    else:
        print("    (Aurora backend active — persistence Aurora cluster me, offline re-open skip.)")
    print()

    # --- Teaching recap: kyun Aurora Serverless v2 + Data API (L91/L92) -----
    print("=" * 76)
    print("KYUN Aurora Serverless v2 + RDS Data API  (L91/L92 recap)")
    print("=" * 76)
    print("- Aurora Serverless v2: ACUs AUTO-SCALE (min..max), idle par near-zero => spiky agentic")
    print("  workloads ke liye perfect; pay-for-capacity (24/7 peak instance nahi chalana).")
    print("- RDS Data API: HTTP-over-SQL (resourceArn + secretArn), koi persistent connection/pool")
    print("  NAHI => Lambda cold-start + concurrency spike par connections exhaust nahi hote.")
    print("- Repository pattern: agents sirf get_portfolio() bolte — backend (sqlite/Aurora) hidden.")
    print()

    # --- Deploy runbook pointer (L92/L93) ----------------------------------
    print("=" * 76)
    print("DEPLOY RUNBOOK  (real cloud — L92/L93)")
    print("=" * 76)
    print("terraform/5_database apply -> outputs (cluster_arn + secret_arn) ko .env me copy ->")
    print("AuroraDataApiBackend auto-pick (DB_CLUSTER_ARN set hote hi) -> SAME 4 methods Lambda")
    print("agents me reuse. (Har destroy/apply par ARNs badalte => .env re-copy — L94 reminder.)")
    print()

    # --- Cleanup (tidy) ----------------------------------------------------
    if isinstance(repo, SqliteBackend) and not keep_db:
        if DEFAULT_DB_PATH.exists():
            DEFAULT_DB_PATH.unlink()
        # _data/ dir agar khaali ho gayi to use bhi hata do (repo saaf rahe).
        try:
            DATA_DIR.rmdir()
        except OSError:
            pass  # dir khaali nahi (kuch aur file) — chhod do
        print(f"[cleanup] sqlite file removed ({DEFAULT_DB_PATH.name}). (--keep-db se rakh sakte ho.)")
    elif keep_db:
        print(f"[keep] sqlite file rakha gaya: {DEFAULT_DB_PATH}")

    print("\n" + "#" * 76)
    print("#  LAB 2 complete. Repository(init_schema/upsert_account/add_holding/get_portfolio)")
    print("#  = sqlite(offline) | aurora-data-api(prod), SAME interface; agents DB-agnostic.")
    print("#" * 76 + "\n")

    raise SystemExit(0)


# ===========================================================================
# MAIN — default self-demo; --keep-db => demo ke baad sqlite file rakho.
# ===========================================================================
if __name__ == "__main__":
    keep = "--keep-db" in sys.argv
    run_self_demo(keep_db=keep)
