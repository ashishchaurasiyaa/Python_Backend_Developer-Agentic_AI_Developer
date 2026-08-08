# DevOps Labs — Runnable Exercises

> `../practical/` me production-quality **reference modules** hain (padhne ke liye — Dockerfile/YAML/HCL text `print()` hoti hai). Yeh folder **chalane** ke liye hai: real Docker containers, TODO stubs jo tum bharoge, aur har lab ka apna verification step — real HTTP requests, real image sizes, real Prometheus queries.

## Setup (ek baar)

```bash
cd Backend_Developer/01_Year3-4_Mid/04_DevOps/labs
docker info                    # Docker daemon chalu hona chahiye
pip install requests           # kuch labs isse use karte hain (stdlib urllib bhi chalta hai)
```

Labs 2 aur 3 ek shared `docker-compose.yml` use karte hain (nginx+backend, prometheus+metrics-app). Labs 1 aur 4 apne containers khud subprocess se chalate/hataate hain — woh khud BUILD aur DEPLOYMENT-GATE ka *process* test kar rahe hain, koi static stack nahi.

## Labs

| # | Lab | Kya sikhata hai | Verify kaise |
|---|---|---|---|
| 1 | [01_docker_multistage_build](01_docker_multistage_build.py) | Multi-stage Dockerfile, non-root user, layer caching | Real `docker build` + `docker run`, HTTP 200 milta hai, aur multi-stage image naive single-stage se meaningfully chhoti hai (`docker image inspect` se size compare) |
| 2 | [02_nginx_reverse_proxy](02_nginx_reverse_proxy.py) | nginx `upstream`/`proxy_pass`, header forwarding | Real request nginx se hoke backend tak jaata hai — response backend ka JSON hai (nginx ka default page nahi), aur `X-Forwarded-For` sahi backend tak pahuncha |
| 3 | [03_prometheus_scrape_and_query](03_prometheus_scrape_and_query.py) | Prometheus scrape config, `/metrics` endpoint, PromQL query API | App ko real HTTP requests bhejo (Counter badhta hai), Prometheus scrape hone do, phir Prometheus ke `/api/v1/query` se exact wahi value nikalo |
| 4 | [04_deployment_health_gate](04_deployment_health_gate.py) | Health-gate decision logic — consecutive checks, promote vs rollback | Dono real scenarios chalao: healthy version → old container retire hota hai; broken version (500 on `/health`) → rollback hota hai aur old container survive karta hai |

Har file me **TODO** blocks hain — pehle khud bharo (Dockerfile template, `nginx.conf`, `prometheus.yml`, ya Python function), phir `python3 0N_....py` chalao. Har lab apna verification khud print karta hai (✅/❌), aur unfilled TODO pe loud, specific error deta hai — kaunsa TODO, kya galat hai.

## Protocol

```
1. Lab file kholo, docstring me OBJECTIVE + TASK padho
2. TODO bharo (Dockerfile string, configs/*.conf, ya Python function —
   reference: ../*.md files)
3. Chalao → ✅ mile to agla lab; ❌ mile to output padho, fix karo
4. Lab ke end me "SOCH" section hota hai — usme diye sawaalon ka
   jawab bolke do. Interview me yahi poocha jaata hai, code nahi.
```

## Folder structure

```
labs/
├── 01_docker_multistage_build.py    # apna build context banata hai, docker CLI subprocess se
├── 02_nginx_reverse_proxy.py        # docker-compose.yml (nginx + backend) use karta hai
├── 03_prometheus_scrape_and_query.py# docker-compose.yml (prometheus + metrics-app) use karta hai
├── 04_deployment_health_gate.py     # apne containers khud subprocess se manage karta hai
├── docker-compose.yml               # sirf Lab 2/3 ke services
├── app/                             # trivial apps jo labs use karte hain (backend, metrics, health)
└── configs/                         # nginx.conf, prometheus.yml — TODO stubs
```

## Troubleshooting

| Problem | Fix |
|---|---|
| `Cannot connect to the Docker daemon` | Docker Desktop / Colima chalu karo (`docker info` se check) |
| Lab 1: build fail ho jaaye | `docker build` ka stderr print hota hai — Dockerfile TODO syntax check karo |
| Lab 2: `docker compose up` haang ho jaaye | `docker compose logs nginx backend` dekho, port `18010` free hai? |
| Lab 3: Prometheus me metric nahi dikhta | http://localhost:19090/targets pe target `UP` hai? TODO 1 (scrape target) check karo |
| Lab 4: dono scenarios fail | `docker ps -a` se dekho `devops-lab04-old`/`-new` ban rahe hain? Port `18041`/`18042` free hain? |
| Purane containers/images clutter kar rahe hain | `docker rm -f $(docker ps -aq --filter name=devops-lab)` |

---

**Related:** [theory files](../) · [reference modules](../practical/) · [Kafka labs](../../07_Kafka/labs/) · [Celery labs](../../09_Celery/labs/)
