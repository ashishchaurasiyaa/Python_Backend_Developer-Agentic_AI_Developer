# Modern Topics — Doc 0: AI Tools Landscape (Complete Map) 🗺️

> **Goal:** Saare AI tools ka **ek master reference**. Hazaron tools hain — yaad rakhna impossible. Isliye **categories** yaad rakho, har category me **2-3 leaders** jaano, aur baaki ko same bucket me daal do. Ye doc = wahi map.
>
> Backend/agentic engineer ke liye 🟢 = priority (seekho), 🟡 = aware raho, ⚪ = sirf naam jaano.

---

## 0. Sabse pehle: mental model 🧠

Naye tool dekh ke ghabrao mat. Har AI tool 3 sawaal se classify ho jaata hai:

1. **Output kya hai?** (text / image / video / audio / code / action) → ye **category** decide karta hai.
2. **Modality?** Ek cheez (image-only) ya **multimodal** (text+image+voice ek saath)?
3. **Kaun chalata hai?** Insaan (assistant) ya **khud act karta hai** (agent)?

> 2026 reality: bade models (Claude, Gemini, GPT) ab **multimodal** hain — ek hi tool text+image+voice+code karta hai. Isliye neeche ki categories "main skill" hain, hard wall nahi.

---

## 1. Foundation models (the "brains") 🟢

Ye woh base LLMs hain jin par baaki sab bana hai. Inhe sabse pehle samjho.

| Tool | Company | Khaas baat | Tier |
|---|---|---|---|
| **Claude** (Opus/Sonnet/Haiku, Fable) | Anthropic | Coding, long context, agents, safety | Free + paid |
| **GPT** (GPT-4o/5) | OpenAI | General purpose, ecosystem, plugins | Free + paid |
| **Gemini** | Google | Huge context, Google integration, multimodal | Free + paid |
| **Llama** | Meta | Open-weight, self-host kar sakte ho | Free / open |
| **Mistral** | Mistral AI | Open-weight, Europe, efficient | Free + paid |
| **DeepSeek** | DeepSeek | Strong + cheap, open reasoning | Free + paid |
| **Grok** | xAI | X/Twitter integration, real-time | Paid |
| **Qwen** | Alibaba | Open-weight, strong multilingual | Free / open |
| **Command** | Cohere | Enterprise RAG focus | Paid |

**Interview note:** "model" (Claude) vs "product" (ChatGPT app) — model = engine, product = car. Same engine alag products me chalता hai.

---

## 2. Text & chat assistants 🟢

Daily kaam: likhna, summarize, Q&A, brainstorm.

| Tool | Khaas baat |
|---|---|
| **ChatGPT** | Most popular, plugins, GPTs, voice |
| **Claude (claude.ai)** | Long docs, coding, careful reasoning |
| **Gemini** | Google Docs/Gmail integration |
| **Copilot (Microsoft)** | Windows + Office me built-in |
| **Meta AI / Grok / DeepSeek** | App/platform-specific chat |

---

## 3. Search & research 🟢

Live internet + citations (LLM + web). Plain chat se alag = sources deta hai.

| Tool | Khaas baat |
|---|---|
| **Perplexity** | "Answer engine", citations, Pro search |
| **Gemini / ChatGPT search** | Built-in web search |
| **Phind** | Developer-focused search |
| **Consensus, Elicit** | Academic / research papers |
| **Deep Research** (Claude/Gemini/OpenAI mode) | Multi-step report banata hai with sources |

> Tum already `deep-research` skill use kar sakte ho is session me.

---

## 4. Coding & development 🟢🟢 (TUMHARA core area)

| Tool | Type | Khaas baat |
|---|---|---|
| **Claude Code** | CLI agent | Terminal me agent, multi-file, tum abhi yahi use kar rahe ho |
| **GitHub Copilot** | IDE autocomplete | VS Code/JetBrains inline suggestions |
| **Cursor** | AI-first IDE | Full editor with chat + agent |
| **Windsurf** | AI IDE | Cascade agent flows |
| **Aider** | CLI | Git-aware pair programmer |
| **Codeium / Tabnine** | Autocomplete | Free Copilot alternatives |
| **v0 (Vercel)** | UI gen | Prompt → React/Tailwind component |
| **Bolt / Lovable / Replit Agent** | App builders | Prompt → full running app |
| **Devin** | Autonomous SWE | End-to-end task agent |

**Seekhne ka order:** Claude Code (abhi) → Cursor → ek autocomplete (Copilot). Baaki same idea.

---

## 5. Image generation 🟡

Text → picture. Design/marketing/art.

| Tool | Khaas baat |
|---|---|
| **Midjourney** | Best aesthetics, Discord/web |
| **DALL·E** (ChatGPT me) | Easy, prompt-friendly |
| **Stable Diffusion** | Open-source, self-host, full control |
| **Flux** | New open model, high quality |
| **Adobe Firefly** | Commercial-safe, Photoshop integration |
| **Ideogram** | Text-in-image (posters, logos) accha |
| **Leonardo, Recraft** | Design/asset focused |

---

## 6. Design & UI 🟡

Posters, logos, slides, layouts (image gen + templates).

| Tool | Khaas baat |
|---|---|
| **Canva (Magic Studio)** | Easiest, templates + AI |
| **Adobe Firefly / Express** | Pro design suite |
| **Figma AI** | UI/UX design + AI features |
| **Gamma / Tome** | AI presentations (slides) |
| **Microsoft Designer** | Quick graphics |
| **Galileo, Uizard** | Prompt → UI mockup |

---

## 7. Video & animation 🟡

Text/image → video clips, editing.

| Tool | Khaas baat |
|---|---|
| **Sora** (OpenAI) | Text → realistic video |
| **Runway** | Gen-3, pro video editing tools |
| **Pika** | Short clips, effects |
| **Kling, Hailuo, Veo (Google)** | Strong text-to-video |
| **HeyGen / Synthesia** | AI avatar presenters (talking head) |
| **Descript** | Edit video by editing text |
| **CapCut AI** | Social media editing |

---

## 8. Audio, music & voice 🟡

| Sub-type | Tools |
|---|---|
| **Music generation** | Suno, Udio |
| **Voice / TTS** | ElevenLabs (best), PlayHT, OpenAI TTS |
| **Speech → text (STT)** | Whisper (OpenAI), Deepgram, AssemblyAI |
| **Voice clone / dub** | ElevenLabs, Resemble |
| **Real-time voice agents** | OpenAI Realtime, Vapi, Retell |

> Voice agents tumhare course me hai → `01_voice_agents.md`.

---

## 9. 3D & modeling ⚪

Text/image → 3D objects, scenes (gaming, AR/VR).

| Tool | Khaas baat |
|---|---|
| **Luma AI** | Photo → 3D (NeRF/Gaussian) |
| **Meshy / Tripo** | Text → 3D model |
| **Spline AI** | 3D web design |
| **Rodin, CSM** | 3D asset generation |

---

## 10. Productivity & office 🟡

Roz ke kaam me embedded AI.

| Tool | Khaas baat |
|---|---|
| **Microsoft 365 Copilot** | Word/Excel/PPT/Outlook me AI |
| **Google Gemini (Workspace)** | Docs/Sheets/Gmail |
| **Notion AI** | Notes + DB + AI |
| **Grammarly** | Writing assistant |
| **Otter, Fireflies** | Meeting notes/transcription |
| **Mem, Reflect** | AI note-taking |

---

## 11. Data & analytics 🟢 (backend-relevant)

| Tool | Khaas baat |
|---|---|
| **Julius AI** | Chat se data analysis + charts |
| **Hex / Deepnote** | AI notebooks (SQL+Python) |
| **Excel/Sheets Copilot** | Formula + analysis |
| **ThoughtSpot, Tableau Pulse** | BI + natural language |
| **Text-to-SQL** (Vanna, etc.) | English → SQL query |

---

## 12. AI agents & automation 🟢🟢 (TUMHARA focus)

Tools jo sirf jawab nahi dete — **khud kaam karte hain** (browse, click, API call, multi-step).

| Tool | Type | Khaas baat |
|---|---|---|
| **LangChain / LangGraph** | Framework | Agent + chains + graph orchestration (Level 7) |
| **LlamaIndex** | Framework | RAG + data agents (Level 5) |
| **CrewAI** | Framework | Multi-agent "crew" roles |
| **AutoGen (Microsoft)** | Framework | Multi-agent conversations |
| **OpenAI Agents SDK / Swarm** | Framework | Lightweight agents |
| **n8n / Make / Zapier** | No-code automation | App-to-app workflows + AI steps |
| **AutoGPT / BabyAGI** | Autonomous agent | Early "give goal, it runs" (concept) |
| **Dify / Flowise / Langflow** | Visual builder | Drag-drop agent/LLM apps |
| **MCP servers** | Protocol | Agents ko tools dena (standard) |

**Browser automation (agent ke "haath"):** Playwright, Puppeteer, Selenium, browser-use, Playwright MCP → dekho `06_playwright_browser_automation.md`.

---

## 13. Supporting / infra tools 🟡 (production ke liye)

Agent banane ke peeche ki plumbing — backend engineer ko ye matter karta hai.

| Need | Tools |
|---|---|
| **Vector DB** (RAG) | Pinecone, Weaviate, Qdrant, Chroma, pgvector |
| **LLM gateway / routing** | OpenRouter, LiteLLM, Portkey |
| **Observability / tracing** | LangSmith, Langfuse, Helicone |
| **Eval / testing** | Ragas, DeepEval, Promptfoo |
| **Prompt mgmt** | LangSmith, PromptLayer |
| **Serving / local** | Ollama, vLLM, LM Studio (→ `03_local_serving.md`) |
| **Fine-tune / train** | Hugging Face, Unsloth, Together, Modal |
| **Guardrails / safety** | Guardrails AI, NeMo Guardrails |

---

## 14. "Cover all" reality check ⚠️

- **Naye tools roz aate hain.** Sabhi yaad karna waqt ki barbaadi. **Category + leader** yaad rakho, naya tool aaye to bucket me daal do.
- **80/20 rule:** har category me top 2-3 hi market ka 80% hain. Wahi seekho.
- **Backend engineer priority (🟢):** Foundation models → Coding tools → Agents/frameworks → RAG/vector DB → infra (gateway, observability, serving). Image/video/music sirf **aware** raho (🟡/⚪).

---

## 15. Kisi bhi naye AI tool ko 60 sec me evaluate karo 🎯

```
1. Category?      → kaunse bucket me hai (upar wali 12)?
2. Output?        → text / image / video / code / action?
3. Multimodal?    → ek cheez ya sab?
4. Agent?         → khud act karta hai ya assist?
5. Open/closed?   → self-host kar sakte ho?
6. Tier?          → free / paid / API?
7. Replaces what? → kis purane tool/workflow ki jagah?
```

In 7 sawaalon ke baad koi bhi naya "viral AI tool" tumhe confuse nahi karega.

---

## 16. Up-to-date kaise raho

- **There's An AI For That**, **Futurepedia** — tool directories (browse by category).
- **Hugging Face** — open models + trending.
- **Provider blogs** — Anthropic, OpenAI, Google (model launches).
- **r/LocalLLaMA**, **Latent Space podcast** — practitioner news.

> Goal: har tool try karna NAHI. Category map (ye doc) up-to-date rakhna — naye tool ko existing bucket me fit karna.

---

## TL;DR

- **~12 categories, 3 families:** language & knowledge · creative & media · build & automate.
- **Sab yaad mat karo** — category + top 2-3 leaders yaad rakho.
- **Tumhare liye (🟢):** foundation models, coding tools, agents/frameworks, RAG/vector DB, infra. Baaki aware-level.
- Naya tool aaye → 7-sawaal checklist (§15) → bucket me daal do. Done.

➡️ Related: `06_playwright_browser_automation.md` · `02_computer_use.md` · `01_voice_agents.md` · `03_local_serving.md`
