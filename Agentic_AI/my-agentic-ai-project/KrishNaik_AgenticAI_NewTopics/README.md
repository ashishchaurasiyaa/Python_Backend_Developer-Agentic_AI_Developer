# KrishNaik Agentic AI — NEW Topics Only

Yeh folder Krish Naik ke free YouTube course **"Complete Agentic AI Course In 10 Hours"** (asal me ~11.2 hrs) ke **SIRF NAYE topics** ke notes rakhta hai — woh topics jo mere existing study repo (Ed Donner ke Udemy courses + Level-wise foundation folders) me **cover NAHI** the.

Matlab: yeh poore 10-ghante course ka dump nahi hai. Course ka jo bada hissa (LangGraph, classic RAG, guardrails, evals etc.) pehle se kahin aur padha ja chuka hai, usko yahan **dobara nahi** likha. Sirf jo genuinely naya tha, woh hi yahan note kiya hai.

> **Course (free):** Krish Naik — "Complete Agentic AI Course In 10 Hours"
> **YouTube:** https://www.youtube.com/watch?v=rV3HJ4LEZ7k (~11.2 hrs)

---

## 📒 Naye topic notes (4)

| Note | Topic | Chapter timestamp | GitHub notebook |
|---|---|---|---|
| [N01_LangChain_V1_Whats_New.md](./N01_LangChain_V1_Whats_New.md) | LangChain V1 — kya naya hai (`create_agent`, models, tools, messages, structured output, middleware) | ⏱️ 00:02:31 | [krishnaik06/Langchain-V1-Crash-Course](https://github.com/krishnaik06/Langchain-V1-Crash-Course) → `updatedlangchain/` |
| [N02_Vectorless_RAG_PageIndex.md](./N02_Vectorless_RAG_PageIndex.md) | Vectorless RAG with PageIndex (tree-search retrieval, no embeddings/vector DB) | ⏱️ 07:10:43 | [krishnaik06/RAG-Tutorials](https://github.com/krishnaik06/RAG-Tutorials) → PageIndex notebook |
| [N03_Deep_Agents.md](./N03_Deep_Agents.md) | Deep Agents (`deepagents` lib: planning, subagents, file-system context — LangGraph par built) | ⏱️ 08:02:11 | Deep Agents notebook (Google Drive — Krish live class) |
| [N04_LLM_Gateways.md](./N04_LLM_Gateways.md) | LLM Gateways (LiteLLM + LangChain): unified API, fallbacks, caching, cost tracking, routing | ⏱️ 10:30:25 | [krishnaik06/Langchain-V1-Crash-Course](https://github.com/krishnaik06/Langchain-V1-Crash-Course) → `llm_gateway_tutorial.ipynb` |

---

## ⏭️ Skipped (already covered) topics

Course me yeh topics bhi hain, par mere paas pehle se detail me padhe hue hain — isliye yahan duplicate nahi kiye. Niche pointer diya hai taaki pata rahe **kuch chhuta nahi**, bas dobara nahi likha:

- **LangGraph** — pehle se `Udemy_EdDonner_Course/Week4_LangGraph` me hai (23 lectures, nodes/edges/state/conditional routing detail me).
- **Classic RAG (chunk → embed → vector DB → cosine retrieval)** — pehle se `Level5_RAG_Vector_Databases/` folder me cover hai. (N02 ka Vectorless RAG isi ka *contrast* hai, replacement nahi.)
- **Guardrails + LLM Evals** — pehle se `Udemy_EdDonner_ProductionTrack/Week4` me hai — Guardrails = lab4, LLM Evals = lab5.

---

## 🧭 Kaise padhe

Yeh notes **self-contained** hain — har note me TL;DR, Hinglish explanation, code, "existing knowledge se connect" aur backend-dev notes hain, toh notebook khole bina bhi samajh aa jaayega. Jin notebooks/transcripts se yeh notes banaye gaye, woh raw extracted source `_sources/` folder me pade hain (e.g. `lcv1_*.txt`, `vectorless_rag.txt`, `deep_agents.txt`, `llm_gateways.txt`) — reference ya verify karne ke liye.
