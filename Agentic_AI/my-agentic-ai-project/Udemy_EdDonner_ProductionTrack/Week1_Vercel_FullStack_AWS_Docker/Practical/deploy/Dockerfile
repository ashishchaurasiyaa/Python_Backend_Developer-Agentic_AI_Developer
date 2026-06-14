# =============================================================================
# Dockerfile — Lab 6 "Containerize for AWS"  (FastAPI -> ECR -> App Runner)
# =============================================================================
# YEH KAISE BUILD HOTA HAI (build context = Practical/ folder, ek level upar):
#
#   # Practical/ se build karo, -f se is Dockerfile ka path do:
#   cd Udemy_EdDonner_ProductionTrack/Week1_Vercel_FullStack_AWS_Docker/Practical
#   docker build -f deploy/Dockerfile -t production-ai-app .
#
#   # Apple Silicon (M1/M2/M3) par AWS ke liye Linux/amd64 chahiye (L29 gotcha):
#   docker build --platform linux/amd64 -f deploy/Dockerfile -t production-ai-app .
#
#   # Locally chalao (port map + optional env vars):
#   docker run -p 8000:8000 -e APP_VERSION=1.2.3 -e GROQ_API_KEY=$GROQ_API_KEY production-ai-app
#
# WHY context = Practical/: hamara lab file `lab6_containerize_for_aws.py`
# Practical/ ke root mein hai aur requirements-docker.txt deploy/ mein. Context
# Practical/ rakhne se dono ek hi build mein COPY ho jaate hain. (Detailed ECR
# push + App Runner steps RUNBOOK .md mein hain.)
# -----------------------------------------------------------------------------

# FROM: base image — Docker Hub se python:3.12-slim uthao. "slim" = Debian ka
# minimal variant => chhoti image, fast pull, kam attack surface (full `python`
# ya `latest` se behtar). Yahi se hamari image "build up" hoti hai (L26/L28).
FROM python:3.12-slim

# WORKDIR: container ke andar working directory set karo (banao agar nahi hai).
# Iske baad ke saare COPY/RUN/CMD isi /app folder se relative chalenge — clean
# layout. (Agar yeh na ho to files `/` par bikhar jaati.)
WORKDIR /app

# RUN apt-get install curl: slim image mein `curl` default NAHI hota, par hamara
# HEALTHCHECK (neeche) curl se /health hit karta hai — isliye install zaroori.
# --no-install-recommends => extra packages na aayein (image chhoti); aur same
# layer mein apt lists delete karte hain (rm -rf /var/lib/apt/lists/*) taaki
# image size na badhe. Ek hi RUN mein chain kiya => ek hi (chhoti) cache layer.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# COPY requirements pehle (code se ALAG): Docker har instruction ko ek LAYER
# ke roop mein cache karta hai. Agar sirf requirements-docker.txt copy karke
# pip install karein, to jab tak deps na badlein, yeh layer cache se aata hai —
# code change par dobara pip install nahi hota (build BAHUT fast). Isiliye
# requirements ko code COPY se PEHLE rakhte hain (classic layer-caching trick).
COPY deploy/requirements-docker.txt ./requirements-docker.txt

# RUN pip install: requirements se saare Python packages install karo.
# --no-cache-dir => pip ka download cache image mein store na ho (image chhoti
# rahe). Yeh layer tab tak cached rahega jab tak requirements file na badle.
RUN pip install --no-cache-dir -r requirements-docker.txt

# COPY lab file: ab actual application code container mein le aao. Context
# Practical/ hai, isliye yeh file context-root se milti hai. Ise hum sidha
# /app/lab6_containerize_for_aws.py par rakhte hain taaki CMD ka module-path
# `lab6_containerize_for_aws:app` resolve ho jaaye.
COPY lab6_containerize_for_aws.py ./lab6_containerize_for_aws.py

# EXPOSE: documentation/metadata — yeh batata hai container 8000 par sunega.
# (Yeh khud port publish nahi karta — woh `docker run -p 8000:8000` karta hai —
# par tooling/App Runner ke liye intent declare karta hai.) Hamara uvicorn
# isi 8000 par bind hai; App Runner config mein bhi Port=8000 set karna hai (L30).
EXPOSE 8000

# HEALTHCHECK: container khud apne /health ko regularly hit karke sehat batata
# hai (L28/L30 pattern). --interval=30s har 30s par check; --timeout=5s 5s mein
# jawab na aaye to fail; curl -f non-2xx par fail; fail => `exit 1` => Docker
# container ko "unhealthy" mark karta hai. NOTE: /health super-light hai (koi
# LLM/DB call nahi) taaki timeout par false-unhealthy na ho. curl chahiye, jo
# slim image mein default nahi — isliye upar install kiya gaya hai.
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

# CMD: container start hone par yahi default command chalti hai. uvicorn ko
# `module:variable` deते hain => `lab6_containerize_for_aws:app` (file ka `app`
# FastAPI object). host 0.0.0.0 => sab interfaces par suno (container ke BAHAR
# se reachable — local 127.0.0.1 se ALAG; App Runner ko 0.0.0.0 chahiye), port
# 8000 (EXPOSE + App Runner Port se match). exec-form (JSON array) use kiya
# taaki signals (SIGTERM) seedhe uvicorn tak pahunche — clean shutdown.
CMD ["uvicorn", "lab6_containerize_for_aws:app", "--host", "0.0.0.0", "--port", "8000"]
