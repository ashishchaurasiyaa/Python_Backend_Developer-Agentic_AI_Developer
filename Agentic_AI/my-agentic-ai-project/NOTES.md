# 📚 Agentic AI Learning Notes - Day 1

> **Goal:** Backend Developer → Agentic AI Engineer
> **Date Started:** May 2026
> **Current Stage:** Foundation Complete ✅

---

## 📋 Table of Contents

1. [Learning Roadmap](#-learning-roadmap)
2. [UV - Modern Python Package Manager](#-uv---modern-python-package-manager)
3. [Project Setup](#-project-setup)
4. [Virtual Environment](#-virtual-environment)
5. [API Keys Setup](#-api-keys-setup)
6. [LangChain Basics](#-langchain-basics)
7. [First LLM Code](#-first-llm-code)
8. [Python Best Practices](#-python-best-practices)
9. [Resources](#-resources)
10. [Next Steps](#-next-steps)

---

## 🗺️ Learning Roadmap

### Course Strategy
**Main Paid Course:** AI Engineer Agentic Track by Ed Donner (₹399)
**Free Foundation:** Krish Naik YouTube videos

### Free Videos (Foundation)
1. **Generative AI Crash Course With Langchain (3 hours Hindi)**
   - URL: https://www.youtube.com/watch?v=7qqGnuRrWxg
   - Covers: LangChain basics, Agents, Tools, Memory
   - GitHub: https://github.com/krishnaik06/Langchain-V1-Crash-Course

2. **Complete RAG Crash Course (2 hours)**
   - URL: https://www.youtube.com/watch?v=o126p1QN_RI
   - Covers: RAG, Vector DBs, Document loaders
   - GitHub: https://github.com/krishnaik06/RAG-Tutorials

### Paid Course
**AI Engineer Agentic Track: The Complete Agent & MCP Course**
- URL: https://www.udemy.com/course/the-complete-agentic-ai-engineering-course/
- Rating: 4.7/5 (40,000+ reviews)
- Price: ₹399
- Covers: OpenAI Agents SDK, CrewAI, LangGraph, AutoGen, MCP
- 8 real-world projects

---

## ⚡ UV - Modern Python Package Manager

### What is UV?
- **UV** = Ultra-fast Python package & environment manager
- Built in **Rust** (10-100x faster than pip)
- Made by **Astral** (Ruff creators)
- Replaces: `pip` + `venv` + `pip-tools` + `pipx` + `virtualenv`

### Why UV over pip?
| Feature | pip + venv | UV |
|---|---|---|
| Speed | Slow | ⚡ 10-100x faster |
| Lock file | Manual | Built-in |
| Python version mgmt | No | Yes |
| Setup | Multi-step | One command |

### Installation
```bash
# Mac/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Verify
uv --version
```

### Essential UV Commands

| Command | Purpose |
|---|---|
| `uv init <name>` | Create new project |
| `uv venv` | Create virtual environment |
| `uv python pin 3.12` | Pin Python version |
| `uv python list` | List available Python versions |
| `uv add <package>` | Install package |
| `uv add --dev <package>` | Install dev dependency |
| `uv remove <package>` | Uninstall package |
| `uv run python <file>` | Run code (without activating venv!) |
| `uv sync` | Install from lock file |
| `uv lock` | Update lock file |
| `uv tree` | View dependencies tree |
| `uv pip list` | List installed packages |

---

## 🏗️ Project Setup

### Steps Used
```bash
# 1. Project banaya
uv init my-agentic-ai-project
cd my-agentic-ai-project

# 2. Python 3.12 pin kiya
uv python pin 3.12

# 3. Virtual environment banaya
uv venv

# 4. Activate kiya
source .venv/bin/activate
```

### Files Created
| File | Purpose |
|---|---|
| `.venv/` | Virtual environment (isolated Python) |
| `.python-version` | Python version pinned (3.12) |
| `pyproject.toml` | Project config + dependencies |
| `uv.lock` | Exact package versions (reproducibility) |
| `main.py` | Main code file |
| `README.md` | Project documentation |
| `.gitignore` | Files to ignore in git |

---

## 🐍 Virtual Environment

### What is it?
- **Isolated Python environment** for each project
- Different projects can use different package versions
- Prevents conflicts

### Activation Indicator
```bash
# Activated dikhega isse:
(my-agentic-ai-project) youngmanindia@MacBook ...
```

### Activate/Deactivate
```bash
# Activate
source .venv/bin/activate

# Deactivate
deactivate
```

---

## 🔑 API Keys Setup

### Groq (FREE) - Recommended for Learning

**Steps:**
1. Visit: https://console.groq.com/
2. Sign up with Google
3. Sidebar → "API Keys"
4. "Create API Key" → Copy
5. Format: `gsk_xxxxxxxxxxxxx`

**Pros:**
- ✅ 100% FREE
- ✅ No credit card needed
- ✅ Ultra-fast inference
- ✅ Llama 3.3 (70B) available

### OpenAI (Paid - Later)
- Visit: https://platform.openai.com/
- $5 minimum top-up required
- Best quality (GPT-4)

### Other FREE Alternatives
| Service | URL |
|---|---|
| **Google Gemini** | https://aistudio.google.com/apikey |
| **HuggingFace** | https://huggingface.co/settings/tokens |
| **Ollama (Local)** | https://ollama.com/ |

---

## 📄 .env File

### Purpose
- Store sensitive API keys
- Keep them out of code
- Never commit to Git

### Current .env File
```env
GROQ_API_KEY=gsk_your_actual_key_here
```

### Security Rules ⚠️
```bash
# .gitignore mein add karna ZAROORI hai
echo ".env" >> .gitignore
echo ".venv/" >> .gitignore
```

**NEVER:**
- ❌ Hardcode API keys in code
- ❌ Commit `.env` to Git
- ❌ Share API keys publicly

---

## 🔗 LangChain Basics

### What is LangChain?
- **Framework** to build LLM-powered applications
- Connects LLMs with: tools, memory, databases, APIs
- Industry standard for AI apps

### Packages Installed
```bash
uv add langchain langchain-groq python-dotenv
```

| Package | Purpose |
|---|---|
| `langchain` | Core framework |
| `langchain-groq` | Groq integration |
| `python-dotenv` | Load .env files |

---

## 💻 First LLM Code

### Working Code (`main.py`)
```python
from dotenv import load_dotenv
from langchain_groq import ChatGroq

# .env se API key load karo
load_dotenv()


def main():
    # LLM initialize karo
    llm = ChatGroq(model="llama-3.3-70b-versatile")

    # Message bhejo
    response = llm.invoke("Hello! Kya tum Hindi mein jawab de sakte ho?")

    # Response print karo
    print("🤖 AI Response:")
    print(response.content)


if __name__ == "__main__":
    main()
```

### Run Command
```bash
uv run python main.py
```

### Expected Output
```
🤖 AI Response:
जी हाँ, मैं हिंदी में जवाब दे सकता हूँ।
```

---

## 🤖 Current Groq Models (2026)

| Model Name | Use Case | Speed |
|---|---|---|
| **`llama-3.3-70b-versatile`** | ⭐ Best general use | Fast |
| `llama-3.1-8b-instant` | Quick replies | ⚡ Ultra-fast |
| `llama-3.2-3b-preview` | Very fast, simple | ⚡⚡ Fastest |
| `mixtral-8x7b-32768` | Long context (32K) | Medium |
| `gemma2-9b-it` | Google's Gemma | Fast |

### Common Errors
**Error:** `model_decommissioned`
**Fix:** Update to `llama-3.3-70b-versatile`

---

## ✨ Python Best Practices Learned

### 1. Always use `if __name__ == "__main__"`
```python
def main():
    # Your code here
    pass

if __name__ == "__main__":
    main()
```

**Why?**
- Code sirf direct run pe execute hota hai
- Import karne pe execute nahi hota

### 2. Remove Unused Imports
```python
# ❌ Bad
from openai.resources import responses  # Unused

# ✅ Good - Only import what you use
from langchain_groq import ChatGroq
```

### 3. Use Functions for Reusability
```python
# ✅ Good - Reusable function
def get_ai_response(user_message: str) -> str:
    """Get AI response for user message."""
    llm = ChatGroq(model="llama-3.3-70b-versatile")
    response = llm.invoke(user_message)
    return response.content
```

### 4. Type Hints (Modern Python)
```python
def add(a: int, b: int) -> int:
    return a + b
```

### 5. Environment Variables for Config
```python
# .env
GROQ_MODEL=llama-3.3-70b-versatile

# main.py
import os
model = os.getenv("GROQ_MODEL")
```

---

## 🔬 Technical Flow (What Happens Behind Scenes)

```
Your Code (main.py)
       ↓
load_dotenv() → Load GROQ_API_KEY from .env
       ↓
ChatGroq() → Connect to Groq cloud
       ↓
llm.invoke("Hello...") → Send message over internet
       ↓
🌐 Groq Cloud → Llama 3.3 (70 BILLION parameters)
       ↓
Model processes Hindi → Generates Hindi response
       ↓
Response returns → response.content
       ↓
Terminal prints output ✨
```

---

## 📊 Progress Tracker

```
[████████████░░░░░] 60% Foundation Complete

✅ UV Package Manager
✅ Project Setup
✅ Virtual Environment
✅ API Keys (Groq)
✅ LangChain Installation
✅ First LLM Code Running
✅ Hindi AI Response Working

🔄 Next: Agents & Tools
⏳ Multi-Tool Agents
⏳ Memory & Context
⏳ Structured Output
⏳ Middleware
⏳ RAG (Video 2)
⏳ LangGraph
⏳ CrewAI + AutoGen + MCP (Paid Course)
```

---

## 📚 Resources

### Courses
- **Free:** [Krish Naik - LangChain Hindi (3hr)](https://www.youtube.com/watch?v=7qqGnuRrWxg)
- **Free:** [Krish Naik - RAG Crash Course (2hr)](https://www.youtube.com/watch?v=o126p1QN_RI)
- **Free Playlist:** [Agentic AI with LangGraph](https://www.krishnaik.in/playlist/PLZoTAELRMXVPFd7JdvB-rnTb_5V26NYNO)
- **Paid:** [Ed Donner - Agentic AI Course (₹399)](https://www.udemy.com/course/the-complete-agentic-ai-engineering-course/)

### Documentation
- **UV Docs:** https://docs.astral.sh/uv/
- **LangChain Docs:** https://python.langchain.com/docs/
- **Groq Docs:** https://console.groq.com/docs/

### GitHub Repos (Code)
- **Krish Naik LangChain:** https://github.com/krishnaik06/Langchain-V1-Crash-Course
- **Krish Naik RAG:** https://github.com/krishnaik06/RAG-Tutorials

### Free LLM APIs
- **Groq:** https://console.groq.com/
- **Google Gemini:** https://aistudio.google.com/apikey
- **HuggingFace:** https://huggingface.co/settings/tokens

---

## 🎯 Krish Naik Video Progress (3-Hour Video)

```
✅ 00:00 - Introduction To The Series
✅ 00:03 - Creating Virtual Environment (UV)
✅ 00:16 - API Keys Creation
✅ 00:29 - LLM Model Integration
🔄 01:06 - Building Agents And Tools  ← CONTINUE HERE
⏳ 01:37 - Building Agents With Multiple Tools
⏳ 01:53 - HumanMessage AIMessage SystemMessage
⏳ 02:14 - Structured Output With LLM
⏳ 02:40 - Short Term Memory
⏳ 02:51 - Middleware Implementation
```

---

## 🚀 Next Steps Plan

### Today/Tomorrow
- [ ] Continue Krish Naik video from 01:06 (Agents & Tools)
- [ ] Build a simple tool-using agent
- [ ] Code along with video

### This Week
- [ ] Complete full 3-hour LangChain video
- [ ] Start RAG Crash Course (2 hours)
- [ ] Build "Chat with PDF" mini project

### Next Week
- [ ] Complete RAG video
- [ ] Buy Ed Donner course (₹399)
- [ ] Start CrewAI, LangGraph, AutoGen, MCP

### Month 1 Goal
- [ ] Build 2 portfolio projects
- [ ] Master LangGraph
- [ ] Understand all major frameworks

### Month 3 Goal
- [ ] Apply for Agentic AI Engineer jobs
- [ ] Target: ₹20-30 LPA roles

---

## 💡 Key Concepts Learned

### What is an LLM?
**LLM (Large Language Model)** = AI model trained on massive text data
- Examples: GPT-4, Llama 3.3, Claude
- Can understand and generate human language
- Used as the "brain" of AI applications

### What is LangChain?
**Framework** that connects LLMs with:
- Tools (calculator, web search, APIs)
- Memory (conversation history)
- Documents (PDFs, websites)
- Other AI models

### What is an Agent?
**AI Agent** = LLM + Tools + Decision-making
- Can take actions (not just chat)
- Uses tools when needed
- Plans multi-step tasks

### What is Agentic AI?
**Agentic AI** = Multiple agents working together
- Collaborate on complex tasks
- Each agent has specialized role
- Future of AI applications

---

## 🛠️ Useful Commands Quick Reference

### UV Commands
```bash
# Project
uv init <project-name>
uv venv
uv python pin 3.12

# Packages
uv add <package>
uv remove <package>
uv add --dev pytest

# Run
uv run python main.py
uv run jupyter notebook
```

### Git Commands (For Later)
```bash
git init
git add .
git commit -m "Initial setup"
```

### Common Python Imports
```python
# Environment
from dotenv import load_dotenv

# LangChain
from langchain_groq import ChatGroq
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
```

---

## 🐛 Errors Faced & Solutions

### Error 1: Model Decommissioned
```
groq.BadRequestError: model `llama-3.1-70b-versatile` has been decommissioned
```
**Solution:** Use `llama-3.3-70b-versatile` instead

### Error 2: Module Not Found
```
ModuleNotFoundError: No module named 'langchain_groq'
```
**Solution:** `uv add langchain-groq`

### Error 3: API Key Not Found
```
ValueError: GROQ_API_KEY not set
```
**Solution:**
1. Check `.env` file exists
2. Check `load_dotenv()` is called
3. Restart terminal

---

## 📌 Important Files in Project

```
my-agentic-ai-project/
├── .venv/                  # Virtual environment (don't touch)
├── .python-version         # Python version pinned
├── .env                    # API keys (NEVER commit!)
├── .gitignore             # Files to ignore
├── pyproject.toml         # Project config
├── uv.lock                # Locked dependencies
├── main.py                # Main code
├── README.md              # Project docs
└── NOTES.md               # ← This file (your study notes)
```

---

## 🎓 Final Words

**Aaj ka achievement:** Backend Developer se AI Engineer ki taraf pehla pakka kadam! 🚀

**Mantra:**
> "Code daily. Build daily. 1 hour per day = AI Engineer in 3 months."

**Remember:**
- Consistency > Intensity
- Build projects > Just watching videos
- Document everything (like these notes!)
- Ask questions when stuck

**Next time start karne se pehle ye file open karo — refresh ho jayega! 💪**

---

*Last Updated: Day 1 Complete | Status: Foundation Built ✅*

---

# 📅 DAY 2 UPDATE - Multi-Provider Setup Complete

## ✅ Day 2 Achievements

```
✅ Anthropic SDK installed (langchain-anthropic)
✅ Google Gemini SDK installed (langchain-google-genai)
✅ Multi-provider comparison code working
✅ Both Groq + Gemini returning quality responses
✅ Hindi (Devanagari) responses from Gemini
✅ Production-ready folder structure (generativeai/)
```

## 🤖 Verified Working Models (May 2026)

| Provider | Model | Status |
|---|---|---|
| **Groq** | `llama-3.3-70b-versatile` | ✅ Working |
| **Gemini** | `gemini-2.5-flash` | ✅ Working |
| **OpenAI** | `gpt-4o-mini` | ⏳ Not added (paid) |
| **Anthropic** | `claude-haiku-4-5` | ⏳ Not added (paid) |

## ⚠️ Deprecated Models (DON'T USE)

```
❌ llama-3.1-70b-versatile  → Use llama-3.3-70b-versatile
❌ gemini-2.0-flash-exp     → Use gemini-2.5-flash
```

## 💎 Key Insight: 9 Skills Needed for Agentic AI Backend Dev

(From Gemini's detailed analysis - my personalized roadmap)

### ✅ Already Have (Backend Dev - 4.3 years)
1. **API Design** - FastAPI/Django expertise
2. **Database Management** - PostgreSQL/MongoDB
3. **Security** - Auth, RBAC, JWT
4. **System Design** - Microservices, scaling
5. **Async Programming** - asyncio, Celery
6. **Message Queues** - RabbitMQ, Redis

### 🔄 Need to Learn (Agentic AI)
1. **LangChain** - Started ✅
2. **LangGraph** - Production agents orchestration
3. **Vector Databases** - ChromaDB (installed!)
4. **Multi-agent Systems** - CrewAI (installed!)
5. **MCP Protocol** - Latest 2026 trend (installed!)
6. **Tool Calling** - Core of agents
7. **RAG** - Retrieval Augmented Generation
8. **Agent Memory** - State management for agents

**Gap:** Only 8 new skills to add to existing 6 → Very achievable!

## 🎯 Provider Selection Strategy

```
Development/Learning:  Groq (FREE, fast)
Production:            Gemini (FREE, detailed)
Critical Production:   Anthropic Claude (paid, best quality)
Backup:                Multiple fallbacks
```

## 📦 All Installed Packages

```python
# Core LangChain ecosystem
langchain==1.3.2
langchain-core==1.4.0
langchain-classic==1.0.7
langchain-community==0.4.2
langchain-text-splitters==1.1.2

# Provider integrations
langchain-groq==1.1.2       # FREE
langchain-google-genai==4.2.3  # FREE
langchain-openai==1.2.2        # Paid
langchain-anthropic==1.4.3     # Paid

# Production agents
langgraph==1.2.2               # Industry standard
langgraph-checkpoint==4.1.1
langgraph-prebuilt==1.1.0
crewai==1.14.5                 # Multi-agent

# Vector DB
chromadb==1.1.1                # RAG

# MCP Protocol (2026 trend)
mcp==1.26.0

# Utilities
python-dotenv==1.2.2
pydantic==2.12.5
```

## 🚀 Project Structure (Updated)

```
my-agentic-ai-project/
├── .venv/                          # Virtual environment
├── .env                            # API keys (Groq + Gemini)
├── main.py                         # Main code
├── generativeai/                   # Generative AI tutorials
│   ├── langchainintro.py          # Multi-provider test
│   └── multi_provider.py          # Provider comparison
├── NOTES.md                        # Daily progress
├── LLM_INTEGRATION_GUIDE.md       # Complete reference
├── pyproject.toml                  # Project config
└── uv.lock                         # Locked dependencies
```

## 📊 Day 2 Progress

```
[██████████████████░░] 90% Foundation Complete!

✅ Multi-provider working
✅ Hindi + English responses
✅ Production-ready code structure
🔄 Next: Building Agents And Tools (Krish Naik 01:06)
```

---

*Day 2 Complete | Multi-Provider Mastery ✅*
