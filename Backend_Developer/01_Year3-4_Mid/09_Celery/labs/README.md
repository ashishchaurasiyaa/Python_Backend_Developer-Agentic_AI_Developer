# Celery Labs — Runnable Exercises

> `../practical/` me production-quality **reference modules** hain (padhne ke liye). Yeh folder **chalane** ke liye hai: real broker + worker, TODO stubs jo tum bharoge, aur har lab ka apna verification.

## Setup (ek baar)

```bash
cd Backend_Developer/01_Year3-4_Mid/09_Celery/labs
docker compose up -d                      # Redis (broker+backend) + Flower
pip install "celery[redis]"
```

**Har lab me DO terminal chahiye:**

```bash
# Terminal 1 — worker (yahan task logs dikhenge)
celery -A tasks worker --loglevel=info --concurrency=2

# Terminal 2 — lab script
python 01_basics_states.py
```

Flower UI: **http://localhost:5555** — tasks, workers, queues, retries live dikhte hain. Labs karte time isse khula rakho, samajh dugni ho jaati hai.

Cleanup: `docker compose down -v`

## Labs

| # | Lab | Kya sikhata hai | Worker command |
|---|---|---|---|
| 1 | [01_basics_states](01_basics_states.py) | `.delay()` vs direct call, AsyncResult, states, result backend | default |
| 2 | [02_retries_backoff](02_retries_backoff.py) | `self.retry()` vs `autoretry_for`, backoff + jitter, FAILURE state | default |
| 3 | [03_queues_canvas](03_queues_canvas.py) | Queue routing (urgent vs bulk), chain / group / chord | `-Q high,default` |
| 4 | [04_acks_late_prefetch](04_acks_late_prefetch.py) | Worker crash → task khota hai ya redeliver, prefetch trap | `--concurrency=1` |

[tasks.py](tasks.py) shared app hai — Lab 02 aur 04 ke TODOs usi file me hain.

## Protocol

```
1. Lab file ka docstring padho (OBJECTIVE + TASK)
2. TODO bharo — reference: ../theory/ aur ../practical/
3. Terminal 1 me worker, Terminal 2 me script chalao
4. ✅ mile to agla; ❌ pe worker ka log padho (asli error wahan hota hai)
5. Har lab ke end me "SOCH" sawaal — bolke jawab do. Interview me
   code nahi, yehi trade-off questions poochhe jaate hain.
```

## Troubleshooting

| Problem | Fix |
|---|---|
| Task PENDING pe atka hai | Worker chal raha hai? Terminal 1 dekho. `-A tasks` sahi hai? |
| `ConnectionError: Error 61 connecting to localhost:6379` | `docker compose ps` — redis up hai? |
| Lab 03 me urgent task slow | Worker `-Q high,default` ke saath start kiya? |
| Code badla par purana chal raha | Worker restart karo — Celery code hot-reload nahi karta |
| Purane tasks queue me pade hain | `docker compose down -v && docker compose up -d` |

---

**Related:** [theory](../theory/) · [reference modules](../practical/) · [Kafka labs](../../07_Kafka/labs/) · [RabbitMQ exercises](../../08_RabbitMQ/exercises/) · [Django+Celery integration](../../../00_Year0-2_Junior/07_Django_DRF/31_celery_django_integration.md)
