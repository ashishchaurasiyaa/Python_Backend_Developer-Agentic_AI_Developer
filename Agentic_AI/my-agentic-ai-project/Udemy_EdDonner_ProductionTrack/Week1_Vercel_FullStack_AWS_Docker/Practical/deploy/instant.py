"""
instant.py — Vercel deploy ENTRYPOINT (Ed Donner Week1 Day1 instant deploy)
===========================================================================
Yeh deploy/ bundle ka asli shippable FastAPI app hai jise `vercel .` deploy
karta hai. Iska content lab1_instant_deploy.py ke routes se match karta hai
(same /, /health, /info) — par yeh file deliberately CHHOTI aur dependency-free
rakhi gayi hai (no TestClient/uvicorn imports) taaki Vercel ka @vercel/python
runtime ise turant import kar ke serverless function bana sake.

KAISE DEPLOY (runbook me detail; short version):
    cd .../Practical/deploy
    cp requirements-vercel.txt requirements.txt   # Vercel `requirements.txt` padhta hai
    npm i -g vercel        # Vercel CLI (npm package) — ek baar
    vercel login           # signup wale method se (Google/GitHub/etc.)
    vercel .               # current folder deploy -> Production URL milega

PHIR (L02): pehla deploy PRIVATE hoga (Deployment Protection ON). Public karne
ke liye Vercel dashboard -> Settings -> Deployment Protection -> Vercel
Authentication toggle OFF -> Save. Incognito window me URL kholke verify karo.

COST: is hello-world app ke liye Vercel Hobby (free) plan par $0.
"""

from fastapi import FastAPI

# MODULE-LEVEL `app` — @vercel/python isi naam ka ASGI app dhoondta hai.
app = FastAPI(title="instant-prod", version="1.0.0")

APP_NAME = "instant-prod"


@app.get("/")
def read_root():
    # Ed ka classic Day-1 moment — browser me yeh JSON dikhega.
    return {"message": "live from production"}


@app.get("/health")
def health():
    # Light health probe — load balancers / uptime monitors isi ko poll karte.
    return {"status": "ok"}


@app.get("/info")
def info():
    return {
        "app": APP_NAME,
        "version": "1.0.0",
        "note": "This is the Vercel-deployable base app (Week1 Day1 instant deploy).",
        "llm": False,
    }
