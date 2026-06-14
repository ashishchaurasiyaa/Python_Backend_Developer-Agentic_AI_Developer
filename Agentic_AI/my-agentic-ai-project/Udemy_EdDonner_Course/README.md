# 🤖 The Complete Agentic AI Engineering Course — Hinglish Notes

> **Instructor:** Ed Donner · **Platform:** Udemy
> **Course:** AI Engineer Agentic Track: The Complete Agent & MCP Course
> **Total:** 132 lectures · 6 weeks · ~17.2 hours *(Udemy update: naya lecture L02b add hua)*
> **Notes style:** Har lecture ka transcript + detailed **Hinglish** explanation (1 `.md` per lecture)

---

## 📚 How these notes work

Har lecture ke liye ek `.md` file hai jisme:
1. **TL;DR** — ek line mein lecture ka summary
2. **Hinglish Explanation** — pura concept Hindi+English mein samjhaaya hua
3. **Key Concepts** — important terms aur definitions
4. **Backend Dev Note** — aapke Python backend background se connect
5. **Takeaway** — yaad rakhne wali baatein
6. **Full Transcript** — original English transcript (reference ke liye)

---

## 🧪 Practical (Hands-On) Track

Theory ke saath **runnable code** bhi — har week ka apna `Practical/` folder (sab labs **Groq pe free** chalte hain, live-tested ✅):

| Week | Labs | Runbook |
|------|------|---------|
| 1 | 5 labs — raw LLM calls, chaining, judge, gradio chatbot, career agent, agent loop | [Week1 Runbook](Week1_Foundations/Practical/PRACTICAL_RUNBOOK.md) |
| 2 | 4 labs — Agents SDK basics, sales agents + handoffs, guardrails, **deep research** | [Week2 Runbook](Week2_OpenAI_Agents_SDK/Practical/PRACTICAL_RUNBOOK.md) |
| 3 | 4 labs — CrewAI debate, financial researcher (custom tool), stock picker (pydantic), **engineering team** | [Week3 Runbook](Week3_CrewAI/Practical/PRACTICAL_RUNBOOK.md) |
| 4 | 4 labs — LangGraph basics (state/nodes/edges), tools + checkpointing (SQLite memory), worker-evaluator loop, **Sidekick** | [Week4 Runbook](Week4_LangGraph/Practical/PRACTICAL_RUNBOOK.md) |
| 5 | 4 labs — AgentChat basics (tools+DB), primary-evaluator team, AutoGen Core (RPS game), **agent creator** | [Week5 Runbook](Week5_AutoGen/Practical/PRACTICAL_RUNBOOK.md) |
| 6 | 4 labs + 5 FastMCP servers — MCP intro, **apna MCP server**, multi-server memory+market, **🏆 Trading Floor capstone** | [Week6 Runbook](Week6_MCP/Practical/PRACTICAL_RUNBOOK.md) |

Project root se chalao, e.g.: `uv run Udemy_EdDonner_Course/Week6_MCP/Practical/lab1_mcp_intro.py`

## 🗺️ Course Map

| Week | Theme | Framework | Lectures | Folder |
|------|-------|-----------|----------|--------|
| 1 | Foundations | Raw LLM calls + agentic patterns | 27 | `Week1_Foundations/` |
| 2 | OpenAI Agents SDK | OpenAI Agents SDK | 21 | `Week2_OpenAI_Agents_SDK/` |
| 3 | CrewAI | CrewAI (low-code) | 19 | `Week3_CrewAI/` |
| 4 | LangGraph | LangGraph | 23 | `Week4_LangGraph/` |
| 5 | AutoGen | Microsoft AutoGen | 17 | `Week5_AutoGen/` |
| 6 | MCP | Anthropic Model Context Protocol | 24 | `Week6_MCP/` |

---

## ✅ Progress Tracker

### Week 1 — Foundations (28 lectures)
- [x] **L01** — Day 1: Autonomous AI Agent Demo — Using N8n to Control Smart Home Devices `(7m)`
- [x] **L02** — Day 1: AI Agent Frameworks Explained — OpenAI SDK, Crew AI, LangGraph & AutoGen `(12m)`
- [ ] **L02b** — 🆕 Your Path to Becoming a Proficient AI Engineer (course-update mein add hua) `(4m)`
- [x] **L03** — Day 1: Agent Engineering Setup — Cursor IDE, UV & API Options `(12m)`
- [x] **L04** — Day 1: Windows Setup for AI Development — Git, Cursor IDE & UV `(21m)`
- [x] **L05** — Day 1: Setting Up Your Mac for AI Projects — GitHub, Cursor IDE & OpenAI API Key `(20m)`
- [x] **L06** — Day 1: Building Your First Agentic AI Workflow with OpenAI API `(18m)`
- [x] **L07** — Day 1: Introduction to Agentic AI — Multi-Step LLM Workflows + Autonomy `(2m)`
- [x] **L08** — Day 2: Building Effective Agents — LLM Autonomy & Tool Integration `(6m)`
- [x] **L09** — Day 2: 5 Essential LLM Workflow Design Patterns `(9m)`
- [x] **L10** — Day 2: Understanding Agent vs Workflow Patterns `(7m)`
- [x] **L11** — Day 3: Orchestrating Multiple LLMs — GPT-4o, Claude, Gemini & DeepSeek `(10m)`
- [x] **L12** — Day 3: Multi-LLM API Integration `(10m)`
- [x] **L13** — Day 3: Comparing LLM APIs — OpenAI Client Library with Claude, Gemini `(13m)`
- [x] **L14** — Day 3: Multi-Model Orchestration — Evaluate AI Responses `(11m)`
- [x] **L15** — Day 3: Connecting Agentic Patterns to Tool Use `(1m)`
- [x] **L16** — Day 4: Comparing AI Agent Frameworks — Simplicity vs Power `(7m)`
- [x] **L17** — Day 4: Resources vs. Tools `(8m)`
- [x] **L18** — Day 4: Build a Web Chatbot That Acts Like You — Gradio & OpenAI `(10m)`
- [x] **L19** — Day 4: Using Gemini to Evaluate GPT-4 Responses `(13m)`
- [x] **L20** — Day 4: Building Agentic LLM Workflows — Resources, Tools & Structured Outputs `(1m)`
- [x] **L21** — Day 5: Building Your Career Alter Ego — Function Calling with Push Alerts `(8m)`
- [x] **L22** — Day 5: LLM Tool Calls Demystified `(6m)`
- [x] **L23** — Day 5: Building AI Assistants — Tools for Unknown Questions `(3m)`
- [x] **L24** — Day 5: Creating & Deploying an AI Agent — Chat Loop to HuggingFace Spaces `(11m)`
- [x] **L25** — Day 5: Deploying Career Conversation Chatbots to Gradio `(9m)`
- [x] **L26** — Day 5: Foundation Week Wrap-up `(2m)`
- [x] **L27** — Day 5 [Extra]: Building Your First Agent Loop with OpenAI Tools from Scratch `(13m)`

**🎉 WEEK 1 COMPLETE — 27/27 original lectures + 5 practical labs done!** *(L02b naya promo lecture hai — 4 min, dekhna optional)*

### Week 2 — OpenAI Agents SDK (21 lectures)
- [x] **L28** — Day 1: Understanding Async Python `(12m)`
- [x] **L29** — Day 1: OpenAI Agents SDK Fundamentals `(5m)`
- [x] **L30** — Day 1: Agent, Runner, and Trace Classes `(9m)`
- [x] **L31** — Day 1: Vibe Coding — 5 Essential Tips `(7m)`
- [x] **L32** — Day 1: OpenAI Agents SDK Core Concepts `(1m)`
- [x] **L33** — Day 2: Build AI Sales Agents with SendGrid `(7m)`
- [x] **L34** — Day 2: Concurrent LLM Calls — Asyncio for Parallel Execution `(9m)`
- [x] **L35** — Day 2: Converting Agents into Tools `(6m)`
- [x] **L36** — Day 2: Agent Control Flow — Handoffs vs. Agents as Tools `(8m)`
- [x] **L37** — Day 2: From Function Calls to Agent Autonomy `(7m)`
- [x] **L38** — Day 2: Agentic AI for Business — Sales Outreach Tools `(1m)`
- [x] **L39** — Day 3: Multi-Model Integration — Gemini, DeepSeek & Groq `(8m)`
- [x] **L40** — Day 3: Implementing Guardrails & Structured Outputs `(10m)`
- [x] **L41** — Day 3: AI Safety in Practice — Guardrails `(5m)`
- [x] **L42** — Day 4: Building Deep Research Agents — Web Search Tool `(9m)`
- [x] **L43** — Day 4: Building a Planner Agent — Structured Outputs with Pydantic `(8m)`
- [x] **L44** — Day 4: End-to-End Research Pipeline `(10m)`
- [x] **L45** — Day 4: Deep Research Agent — Parallel Searches with AsyncIO `(4m)`
- [x] **L46** — Day 5: Modular AI Research System with Gradio UI `(12m)`
- [x] **L47** — Day 5: Deep Research App — Gradio Visualization `(4m)`
- [x] **L48** — Day 5: Deploying Smart Research Agents — Gradio & HuggingFace `(4m)`

**🎉 WEEK 2 COMPLETE — 21/21 lectures + 4 practical labs done!**

### Week 3 — CrewAI (19 lectures)
- [x] **L49** — Day 1: Crew AI Framework — Collaborative AI Agent Teams `(6m)`
- [x] **L50** — Day 1: Agents, Tasks & Processing Modes `(8m)`
- [x] **L51** — Day 1: Crew AI & LiteLLM — Multiple LLMs `(5m)`
- [x] **L52** — Day 1: Setting Up a Debate Project with GPT-4o mini `(9m)`
- [x] **L53** — Day 1: AI Debate System Using Crew AI `(12m)`
- [x] **L54** — Day 1: Building AI Debate Systems — Compare LLMs `(2m)`
- [x] **L55** — Day 2: Tools, Context & Google Search Integration `(6m)`
- [x] **L56** — Day 2: Multi-Agent Financial Research Systems `(11m)`
- [x] **L57** — Day 2: Web Search — Knowledge Cutoff Problem `(6m)`
- [x] **L58** — Day 3: Crew AI Stock Picker `(7m)`
- [x] **L59** — Day 3: Pydantic Outputs in Crew AI `(9m)`
- [x] **L60** — Day 3: Custom Tool Development — JSON Schema & Push Notifications `(9m)`
- [x] **L61** — Day 4: Crew AI Memory — Vector Storage & SQL `(12m)`
- [x] **L62** — Day 4: Crew AI for Coding Tasks `(8m)`
- [x] **L63** — Day 4: Python-Writing AI Agent `(6m)`
- [x] **L64** — Day 5: Building AI Teams — Collaborative Development `(10m)`
- [x] **L65** — Day 5: Collaborative AI Agent Development — Stock Trading `(8m)`
- [x] **L66** — Day 5: Trading Application Using GPT-4o & Claude `(9m)`
- [x] **L67** — Day 5: From Single Modules to Complete Systems `(9m)`

**🎉 WEEK 3 COMPLETE — 19/19 lectures + 4 practical labs done!**

### Week 4 — LangGraph (23 lectures)
- [x] **L68** — Day 1: LangGraph Explained — Graph-Based Architecture `(10m)`
- [x] **L69** — Day 1: Framework, Studio, and Platform Components `(6m)`
- [x] **L70** — Day 1: LangGraph Theory — Core Components `(10m)`
- [x] **L71** — Day 2: Managing State in Graph-Based Workflows `(6m)`
- [x] **L72** — Day 2: Define State Objects & Use Reducers `(7m)`
- [x] **L73** — Day 2: Creating Nodes, Edges & Workflows `(6m)`
- [x] **L74** — Day 2: Building an OpenAI Chatbot with Graph Structures `(4m)`
- [x] **L75** — Day 3: Super Steps & Checkpointing `(6m)`
- [x] **L76** — Day 3: Langsmith & Custom Tools `(7m)`
- [x] **L77** — Day 3: Tool Calling — Conditional Edges & Tool Nodes `(12m)`
- [x] **L78** — Day 3: Checkpointing — Memory Between Conversations `(9m)`
- [x] **L79** — Day 3: Persistent AI Memory with SQLite `(6m)`
- [x] **L80** — Day 4: Playwright Integration — Web-Browsing AI Agents `(9m)`
- [x] **L81** — Day 4: AI Web Assistants — Playwright, LangChain & Gradio `(8m)`
- [x] **L82** — Day 4: LLM Evaluator Agents — Feedback Loops `(9m)`
- [x] **L83** — Day 4: Worker-Evaluator Implementation `(10m)`
- [x] **L84** — Day 4: Building an AI Sidekick `(9m)`
- [x] **L85** — Day 5: Add Web Search, File System & Python REPL `(6m)`
- [x] **L86** — Day 5: LangChain Tool Integration — AI Sidekick from Scratch `(10m)`
- [x] **L87** — Day 5: Graph Builders & Node Communication `(9m)`
- [x] **L88** — Day 5: Isolated User Sessions in Gradio `(6m)`
- [x] **L89** — Day 5: Inside AI Feedback Loops `(12m)`
- [x] **L90** — Day 5: AI Assistant Upgrades — Memory, Clarifying Questions `(4m)`

**🎉 WEEK 4 COMPLETE — 23/23 lectures + 4 practical labs done!**

### Week 5 — AutoGen (17 lectures)
- [x] **L91** — Day 1: Microsoft Autogen 0.5.1 Explained `(8m)`
- [x] **L92** — Day 1: AutoGen vs Other Frameworks `(6m)`
- [x] **L93** — Day 1: AutoGen Agent Chat — Tools & Database `(10m)`
- [x] **L94** — Day 1: Models, Messages & Agents `(1m)`
- [x] **L95** — Day 2: Advanced Agent Chat — Multimodal & Structured Outputs `(9m)`
- [x] **L96** — Day 2: Primary and Evaluator Agents `(14m)`
- [x] **L97** — Day 2: Headless Web Scraping — MCP Server Fetch `(8m)`
- [x] **L98** — Day 3: AutoGen Core — Distributed Agent Communications `(5m)`
- [x] **L99** — Day 3: Message Handlers & Dispatching `(9m)`
- [x] **L100** — Day 3: Agent Registration and Message Handling `(9m)`
- [x] **L101** — Day 3: Standalone Agents — Rock Paper Scissors `(7m)`
- [x] **L102** — Day 4: Distributed Runtime — Architecture `(3m)`
- [x] **L103** — Day 4: Distributed AI Agents with gRPC Runtime `(10m)`
- [x] **L104** — Day 4: Cross-Process Communication `(4m)`
- [x] **L105** — Day 5: Agents That Write & Deploy Other Agents `(5m)`
- [x] **L106** — Day 5: Agent-to-Agent Messaging `(11m)`
- [x] **L107** — Day 5: Autonomous AI Agents that Collaborate `(12m)`

**🎉 WEEK 5 COMPLETE — 17/17 lectures + 4 practical labs done!**

### Week 6 — MCP (24 lectures)
- [ ] L108 — Day 1: Intro to MCP — The USB-C of Agentic AI `(7m)`
- [ ] L109 — Day 1: Understanding MCP Hosts, Clients, and Servers `(9m)`
- [ ] L110 — Day 1: Using MCP Servers with OpenAI Agents SDK `(8m)`
- [ ] L111 — Day 1: Node-Based MCP Servers & Tool Access `(5m)`
- [ ] L112 — Day 1: Agent That Uses Multiple MCP Servers `(11m)`
- [ ] L113 — Day 1: MCP Marketplaces & Security `(3m)`
- [ ] L114 — Day 2: Building Your Own MCP Server `(5m)`
- [ ] L115 — Day 2: Wiring Business Logic into Your MCP Server `(6m)`
- [ ] L116 — Day 2: Creating Client Code to Use Your MCP Server `(12m)`
- [ ] L117 — Day 2: Wrap-Up — Capabilities of Your Custom MCP Server `(1m)`
- [ ] L118 — Day 3: Types of MCP Servers and Agent Memory `(8m)`
- [ ] L119 — Day 3: Brave Search API — MCP Server Calling the Web `(9m)`
- [ ] L120 — Day 3: Integrating Polygon API for Stock Market Data `(5m)`
- [ ] L121 — Day 3: Advanced Market Tools — Paid Polygon Plan `(6m)`
- [ ] L122 — Day 4: Launching Our Agent Trading Floor `(8m)`
- [ ] L123 — Day 4: UI for Trading Activity `(11m)`
- [ ] L124 — Day 4: How Trading Agents Operate and Make Decisions `(7m)`
- [ ] L125 — Day 4: Portfolio Management with Four Autonomous Agents `(10m)`
- [ ] L126 — Day 5: Which Agent Framework Should You Pick? `(9m)`
- [ ] L127 — Day 5: Key Settings and Launching the Trading System `(6m)`
- [ ] L128 — Day 5: Advice for Selecting Agentic Frameworks `(8m)`
- [ ] L129 — Day 5: 10 Essential Lessons for Building Agent Solutions `(8m)`
- [ ] L130 — Day 5: Course Recap and Final Goodbye `(7m)`
- [ ] L131 — Bonus Lecture: Your Exclusive Links `(3m)`

---

*Notes auto-generated lecture-by-lecture from the official Udemy transcripts. Last updated: **ALL MATERIALS COMPLETE 🎓** — **132/132 lecture notes** (incl. naya L02b) + **25 tested labs** + **5 custom MCP servers** + 6 runbooks. Weeks 1–5 lectures done; Week 6 (L108–L131) materials ready — finish karke course poora karo!*
