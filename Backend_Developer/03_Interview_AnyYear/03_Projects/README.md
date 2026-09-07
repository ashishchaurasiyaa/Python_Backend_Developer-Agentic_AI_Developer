# 03_Projects — Portfolio Project Specifications

Ten end-to-end backend project specs, each with a matching `<name>_starter/` folder to build from.

⚠️ **Status check first:** the specs are all complete, but 9 of the 10 starters are scaffolds — a `main.py`/`manage.py` full of TODOs (29–58 markers each), not working code. Only [`08_FastAPI_OpenAI_RAG_Backend_starter/`](08_FastAPI_OpenAI_RAG_Backend_starter/) is actually built out (routers, retrieval, db, docker-compose, Makefile). Don't assume a starter runs — open it before you commit interview prep time to it.

| # | Spec | Project | Starter status |
|---|---|---|---|
| 1 | [`01_FastAPI_Multi_Tenant_SaaS.md`](01_FastAPI_Multi_Tenant_SaaS.md) | Multi-Tenant SaaS API Platform | TODO scaffold |
| 2 | [`02_FastAPI_RealTime_Whiteboard.md`](02_FastAPI_RealTime_Whiteboard.md) | Real-Time Collaborative Whiteboard | TODO scaffold |
| 3 | [`03_FastAPI_URL_Shortener_Scale.md`](03_FastAPI_URL_Shortener_Scale.md) | URL Shortener at Scale (Bitly-clone) | TODO scaffold |
| 4 | [`04_FastAPI_WhatsApp_Lite_Chat.md`](04_FastAPI_WhatsApp_Lite_Chat.md) | WhatsApp-lite Chat Backend | TODO scaffold |
| 5 | [`05_Django_Banking_Fintech.md`](05_Django_Banking_Fintech.md) | Banking / Fintech Backend | TODO scaffold (no Django project even started) |
| 6 | [`06_Django_HR_Payroll.md`](06_Django_HR_Payroll.md) | HR & Payroll Management System | TODO scaffold (no Django project even started) |
| 7 | [`07_Django_Food_Delivery.md`](07_Django_Food_Delivery.md) | Food Delivery Backend (Swiggy/Zomato-lite) | TODO scaffold (no Django project even started) |
| 8 | [`08_FastAPI_OpenAI_RAG_Backend.md`](08_FastAPI_OpenAI_RAG_Backend.md) | FastAPI + OpenAI RAG Backend | ✅ **Built** — the one to harden first |
| 9 | [`09_Realtime_AI_Chat_App.md`](09_Realtime_AI_Chat_App.md) | Real-Time AI Chat App (ChatGPT-style) | TODO scaffold |
| 10 | [`10_MCP_Server_FastAPI.md`](10_MCP_Server_FastAPI.md) | MCP Server for FastAPI (AI Tool Platform) | TODO scaffold |

## Pick one (or two), go deep

Ten half-built projects are worth less in an interview than one that's tested, observable, and deployed. Recommended pair for a well-rounded portfolio: **03 URL Shortener at Scale** (FastAPI, read-heavy scaling story) + **05 Django Banking/Fintech** (Django, transactional-integrity story). Harden 08 first if you want a single AI-forward project instead.

[`STUDY_PLAN.md`](../../../STUDY_PLAN.md) Part A, Week 4 (Capstone Deploy) walks through hardening one project as the proof-project — auth, tests, migrations, Docker, deployed, README with architecture notes.
