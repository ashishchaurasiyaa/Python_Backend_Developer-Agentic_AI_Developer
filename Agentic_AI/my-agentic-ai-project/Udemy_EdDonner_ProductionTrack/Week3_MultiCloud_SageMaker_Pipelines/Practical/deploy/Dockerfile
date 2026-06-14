# ============================================================================
# Dockerfile — multi-cloud container image for the FastAPI agent
# ============================================================================
# Yeh WAHI image hai jo local par, Azure Container Apps par, aur GCP Cloud Run par —
# teeno jagah BILKUL same chalti hai (L66 "build once, deploy anywhere"; L73 parity).
# Build/run (L66 ke commands):
#   docker build --platform linux/amd64 -t multicloud-agent -f deploy/Dockerfile .
#   docker run --rm --env-file .env -p 8000:8000 multicloud-agent
# NOTE platform=linux/amd64 (L68/L72): Mac (Apple Silicon = ARM) par bhi amd64 build
# karo, warna cloud (jo amd64 hai) par container crash karega. Best practice: explicit.

# --- base image: chhoti, official Python (L66 stage-2 jaisa) ----------------
# python:3.12-slim => Debian-slim par Python 3.12; full image se bahut chhoti =>
# fast pull/deploy + kam attack surface (production best practice, L66).
FROM python:3.12-slim

# --- uv install: Ed ka package manager (L66 "RUN pip install uv") -----------
# uv = fast Python package/dependency manager; image ke andar deps resolve karta hai.
RUN pip install --no-cache-dir uv

# --- working directory: app yahan rahega (L66 WORKDIR /app) -----------------
WORKDIR /app

# --- runtime deps: lab ko sirf fastapi + uvicorn + openai + dotenv chahiye ---
# (Asli repo me `uv sync` pyproject se sab install karta — yahan ek-file lab hai isliye
# explicit list. --system => image ke system python me install, virtualenv overhead nahi.)
RUN uv pip install --system --no-cache "fastapi" "uvicorn[standard]" "openai" "python-dotenv"

# --- app code copy: sirf lab .py chahiye (Practical/ se build context maano) -
# Build context root se: COPY <src on host> <dest in image>. Yahan lab file ko app/ me
# laate hain taaki uvicorn module ko import path par paaye.
COPY lab2_multicloud_container_deploy.py /app/lab2_multicloud_container_deploy.py

# --- EXPOSE 8000: image batati hai ki yeh port 8000 par sunti hai (L66) -----
# Yeh sirf DOCUMENTATION/metadata hai (actual publish `-p` ya cloud ingress se hota),
# par ACA/Cloud Run isse port detect karne me madad milti hai. Dono clouds 8000 expect.
EXPOSE 8000

# --- HEALTHCHECK: container "healthy?" — GET /health hit karta hai (L66) -----
# curl chahiye, isliye install. --fail => non-2xx par exit 1 => container unhealthy ->
# ACA/Cloud Run replace/restart kar dega. /health sasta hai (koi LLM call nahi) isliye
# baar-baar hit karna safe. Interval/timeout chhote rakhe taaki cold-start ke baad jaldi
# healthy report ho.
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD curl --fail http://localhost:8000/health || exit 1

# --- CMD: container entrypoint = uvicorn 0.0.0.0:8000 (L66 final line) -------
# host 0.0.0.0 => container ke BAHAR se reachable (127.0.0.1 hota to sirf andar). Port 8000
# = wahi jo EXPOSE + cloud ingress expect karte hain. `app` object lab file me defined hai.
# Yahi line lab .py ke `--serve` mode se identical behaviour deti hai => dev/prod parity.
CMD ["uvicorn", "lab2_multicloud_container_deploy:app", "--host", "0.0.0.0", "--port", "8000"]
