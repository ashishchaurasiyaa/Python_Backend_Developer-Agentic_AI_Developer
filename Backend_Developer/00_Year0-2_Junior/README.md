# 🌱 Year 0–2 — Junior Track (foundations + core stack)

> **Naam "Junior" hai, content nahi.** Yahan PostgreSQL internals, Redlock, OWASP API Top 10,
> mutation testing aur LLM/RAG backends bhi hain — 4-saal wale ke liye yeh **refresh + gap-fill layer** hai,
> beginner course nahi.
>
> **Tumhare liye kaise use karna hai:** poora mat padho. [ROADMAP.md](../../ROADMAP.md) jahan bhejta hai wahi file kholo,
> ya interview se pehle apne weak module ka 🔴 section utha lo.

---

## 📚 12 Modules

| # | Module | Kya | Size |
|---|---|---|---|
| 01 | [Foundations](01_Foundations/) | Linux, OS, networking, git, "pehla API" — sab plain English me | 9 files |
| 02 | [Python Daily](02_Python_Daily/) | 55-day drill + Complete_Theory + Complete_Practical + cheat sheets | 55 days |
| 03 | [Python Tooling](03_Python_Tooling/) | Poetry/uv, Ruff/mypy/pre-commit, packaging | 3 + 1 |
| 04 | [Database / SQL](04_Database_SQL/) 🔴 | **PostgreSQL deep dive** — MVCC, indexing, partitioning, migrations, CDC | 32 + 23 |
| 05 | [MySQL](05_MySQL/) | InnoDB internals, replication, ProxySQL — MySQL wale JDs ke liye | 10 + 7 |
| 06 | [FastAPI](06_FastAPI/) 🔴 | 43 topics — routing se ASGI internals, security, AI backends + **labs** | 43 + 40 + 5 labs |
| 07 | [Django / DRF](07_Django_DRF/) 🔴 | 45 topics + ek asli runnable Django project | 45 + 45 |
| 08 | [Redis](08_Redis/) 🔴 | 19 topics + **5 labs** — caching, rate limiting, Redlock, streams | 19 + 18 + 5 labs |
| 09 | [Caching](09_Caching/) | Patterns + invalidation + stampede + semantic caching | 9 + 9 |
| 10 | [Testing](10_Testing/) | pytest advanced, contract, mutation, **testcontainers** | 9 + 9 |
| 11 | [File Handling](11_File_Handling/) | Uploads, S3 presigned, Pillow, PDF/Excel, pandas ingest | 5 + 5 |
| 12 | [Email + Notifications](12_Email_Notifications/) | SMTP/SPF/DKIM, providers, FCM/APNS, notification system design | 4 + 4 |

🔴 = interview me sabse zyada matter karta hai

---

## 🎯 Interview se 1 hafta pehle — sirf yeh

| Din | Kya | Kahan |
|---|---|---|
| 1 | PostgreSQL: MVCC, isolation levels, indexing, locking | [04 ka 🔴 section](04_Database_SQL/README.md#-interview-ke-liye-pehle-yeh-6-agar-time-kam-hai) |
| 2 | Django ORM + N+1 + transactions **ya** FastAPI async + DI | [07](07_Django_DRF/) · [06](06_FastAPI/) |
| 3 | Redis: caching patterns, rate limiting, Redlock | [08 ka 🔴 section](08_Redis/README.md#-interview-ke-liye-pehle-yeh-5) |
| 4 | Testing: pytest fixtures, kya mock karna hai kya nahi | [10](10_Testing/README.md) |
| 5 | Python core: GIL, async, decorators, memory | [02](02_Python_Daily/) → [Mid: Python Advanced](../01_Year3-4_Mid/01_Python_Advanced/) |

---

## 🧪 Labs (padhna nahi — karna)

| Module | Labs | Infra |
|---|---|---|
| [FastAPI](06_FastAPI/labs/) | 5 TODO-stub exercises | — |
| [Redis](08_Redis/labs/) | 5 exercises | `docker compose up -d` |

**Agla track:** [01_Year3-4_Mid](../01_Year3-4_Mid/) → [02_Year5+_Senior](../02_Year5%2B_Senior/) → [03_Interview_AnyYear](../03_Interview_AnyYear/)
**Roz ka kaam:** [ROADMAP.md](../../ROADMAP.md) · **Log:** [MY_PROGRESS.md](../../MY_PROGRESS.md)
