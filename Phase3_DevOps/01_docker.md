# Docker — Multi-stage Builds, Compose, Best Practices

## Quick Concepts
- **Image** = read-only blueprint; **Container** = running instance of an image
- **Dockerfile** defines how to build an image layer by layer
- **Multi-stage builds** reduce final image size by separating build env from runtime env
- **Docker Compose** orchestrates multiple containers (app + db + redis) with a single YAML file
- **Volume** = persistent storage; **Network** = isolated communication between containers

---

## Interview Questions & Answers

### Q1: Docker image aur container mein kya fark hai?
**Answer:**
- **Image** ek read-only template hai — jaise ek class definition. `docker build` se banta hai.
- **Container** ek running instance hai — jaise class ka object. `docker run` se banta hai.
- Ek image se multiple containers run ho sakte hain.
- Container ka state change hota hai (running, stopped, paused), image ka nahi.

```bash
docker build -t myapp:1.0 .       # image banao
docker run -d -p 8000:8000 myapp:1.0  # container chalao
docker ps                          # running containers dekho
docker images                      # images list karo
```

---

### Q2: Multi-stage Dockerfile kya hota hai aur kyun use karte hain?
**Answer:**
Multi-stage build mein ek hi Dockerfile mein multiple `FROM` statements hote hain. Pehla stage build karta hai (heavy tools ke saath), doosra stage sirf binary copy karta hai. Final image sirf runtime mein kya chahiye woh rakhti hai — size 10x+ kam ho jaata hai.

```dockerfile
# Stage 1: Builder (heavy — has pip, gcc, etc.)
FROM python:3.12-slim AS builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --prefix=/install -r requirements.txt

# Stage 2: Runtime (light — sirf app aur dependencies)
FROM python:3.12-slim
WORKDIR /app
COPY --from=builder /install /usr/local
COPY . .
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

### Q3: Docker Compose se multi-container app kaise chalate hain?
**Answer:**
`docker-compose.yml` mein saari services define karo, phir `docker compose up` se sab ek saath start ho jaata hai.

```yaml
# docker-compose.yml
version: "3.9"

services:
  app:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://user:pass@db:5432/mydb
      - REDIS_URL=redis://redis:6379
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_started
    volumes:
      - .:/app

  db:
    image: postgres:15
    environment:
      POSTGRES_USER: user
      POSTGRES_PASSWORD: pass
      POSTGRES_DB: mydb
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U user"]
      interval: 5s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

volumes:
  postgres_data:
```

```bash
docker compose up -d          # background mein start karo
docker compose logs -f app    # live logs dekho
docker compose down -v        # sab stop karo + volumes delete karo
```

---

### Q4: Docker networking kaise kaam karta hai?
**Answer:**
- **bridge** (default): containers ek private network mein hain, `container_name:port` se baat kar sakte hain
- **host**: container host ka network directly use karta hai (Linux only)
- **none**: no networking
- Compose automatically ek network banata hai — isliye `db`, `redis` hostname directly kaam karta hai

```bash
docker network ls
docker network inspect bridge
docker network create my_network
docker run --network my_network myapp
```

---

### Q5: `.dockerignore` kyun important hai?
**Answer:**
`.dockerignore` file bataati hai ki `docker build` context mein kya BHEJNA NAHI hai. Isse:
- Build fast hota hai (context Docker daemon ko transfer hota hai)
- Image mein unnecessary files nahi jaati (`.git`, `__pycache__`, `.venv`, `*.pyc`)

```
# .dockerignore
.git
.venv
__pycache__
*.pyc
*.pyo
.env
.DS_Store
tests/
*.log
```

---

### Q6: Container health check kaise set karte hain?
**Answer:**
```dockerfile
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1
```
Ya Compose mein (already shown above). `docker ps` mein `(healthy)` / `(unhealthy)` dikhega.

---

### Q7: Docker volume aur bind mount mein kya fark hai?
**Answer:**
| | Volume | Bind Mount |
|---|---|---|
| Location | Docker managed (`/var/lib/docker/volumes/`) | Host ka koi bhi path |
| Use case | Persistent DB data, production | Development — live code reload |
| Portability | High | Low (host path hardcoded) |
| Backup | `docker volume export` se easy | Manual |

```yaml
volumes:
  - postgres_data:/var/lib/postgresql/data   # named volume (production)
  - .:/app                                    # bind mount (dev hot-reload)
```

---

### Q8: Production ke liye Dockerfile best practices kya hain?
**Answer:**
1. **Non-root user** use karo security ke liye
2. **Specific base image tag** use karo (`python:3.12-slim`, not `python:latest`)
3. **COPY requirements before code** — layer cache optimize hoga
4. **Multi-stage build** — image size kam karo
5. **.dockerignore** — unnecessary files exclude karo
6. **HEALTHCHECK** add karo
7. **ENV variables** `ARG` se pass karo secrets hardcode mat karo

```dockerfile
FROM python:3.12-slim AS builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

FROM python:3.12-slim
# Non-root user
RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser
WORKDIR /app
COPY --from=builder /install /usr/local
COPY --chown=appuser:appgroup . .
USER appuser
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s CMD curl -f http://localhost:8000/health || exit 1
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## Important Commands Cheatsheet

```bash
# Build
docker build -t myapp:latest .
docker build -t myapp:latest --target builder .  # specific stage tak

# Run
docker run -d --name myapp -p 8000:8000 -e ENV=prod myapp:latest
docker run -it myapp:latest /bin/bash            # interactive shell

# Inspect
docker logs myapp -f --tail 100
docker exec -it myapp /bin/bash
docker inspect myapp
docker stats                                      # live resource usage

# Cleanup
docker rm -f myapp
docker rmi myapp:latest
docker system prune -af                          # sab kuch clean karo

# Registry
docker tag myapp:latest myrepo/myapp:1.0
docker push myrepo/myapp:1.0
docker pull myrepo/myapp:1.0
```
