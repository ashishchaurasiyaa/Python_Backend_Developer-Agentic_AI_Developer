# RabbitMQ Exercises — Runnable Labs

> `../practical/` me production-quality **reference modules** hain (padhne ke liye).
> Yeh folder **chalane** ke liye hai: real broker, TODO stubs jo tum bharoge, aur
> har exercise ka apna `verify.py` jo prove karta hai ki pattern SACH ME kaam kiya
> (sirf "code chal gaya" nahi — actual selective delivery / correlation matching /
> persistence broker se confirm hoti hai).

## Setup (ek baar)

```bash
cd Backend_Developer/01_Year3-4_Mid/08_RabbitMQ/exercises
docker compose up -d                    # rabbitmq:3-management image
docker compose ps                       # healthy hona chahiye (~20s)
pip install pika                        # sync client (yeh saare exercises isi pe hain)

# UI (bahut useful — queues/exchanges/bindings live dekh sakte ho):
# http://localhost:15672   (user: guest / pass: guest)
```

Agar tumhare paas already RabbitMQ chal raha hai (Homebrew service, ya doosra
container) ports `5672`/`15672` pe, docker container **conflict** karega —
`docker compose ps` / `lsof -i :5672` se pehle check kar lo. Agar already koi
RabbitMQ chal raha hai to docker zaroori nahi, seedha exercises chala sakte ho.

Cleanup: `docker compose down -v`

## Exercises

Har exercise do (ya zyada) `publisher`/`subscriber` role files hain — asli
two-terminal AMQP pattern (RabbitMQ Kafka jaisa "ek file me sab kuch" nahi hai,
publisher aur subscriber ALAG processes hote hain). Har folder me ek `verify.py`
bhi hai jo dono roles ko khud chalata hai (background subprocess + timeout) aur
ek hi command se saare TODOs check karta hai.

| # | Exercise | Kya sikhata hai | Verify kaise |
|---|---|---|---|
| 1 | [01_fanout](01_fanout/) | Fanout exchange — routing_key ignore, sabko broadcast | 2 subscribers ko SAARE 4 messages milte hain (dono ka set match) |
| 2 | [02_rpc](02_rpc/) | RPC over AMQP — `reply_to` + `correlation_id` wiring | Client ko SAHI correlated response milta hai; ek "stray" (galat correlation_id) response inject karke prove karte hain ki matching genuinely kaam karta hai |
| 3 | [03_direct_routing](03_direct_routing/) | Direct exchange — exact routing_key match, selective delivery | `routing_key="Error"` sirf Error-bound queues ko milta hai, "Other"-bound koi queue na hone se koi bhi use miss kar jaata hai |
| 4 | [04_topic_routing](04_topic_routing/) | Topic exchange — `*` (ek word) aur `#` (zero+ words) wildcards | `kern.critical`-jaisi key `kern.*`/`#` ko milti hai, `cron.*` ko NAHI — 3 deterministic keys se single-match/multi-match/no-match teeno prove hote hain |
| 5 | [05_durability_confirms](05_durability_confirms/) | Durable queue + persistent message (`delivery_mode=2`) + publisher confirms | Broker ki REAL state management HTTP API se check karte hain: queue `durable=true`, message `delivery_mode=2`, aur ek unroutable+mandatory publish confirms mode me exception raise karta hai |

Har file me **TODO** blocks hain (divider comment + hint + placeholder) —
pehle khud bharo, phir `python verify.py` chalao. Guard-checks hain jo LOUD
fail karte hain agar TODO abhi bhara nahi (❌ specific message ke saath),
warna silent bug ya hang mil jaata.

## Protocol

```
1. Exercise folder kholo, publisher/client.py ke docstring me pehle
   MECHANISM padho (broker andar se kya karta hai — hash-map lookup,
   trie match, x-death header, prefetch — asli AMQP internals), phir TASK
2. TODO bharo (reference: ../practical/ aur ../theory/)
3. python verify.py chalao -> ✅ mile to agla exercise; ❌ mile to output
   padho (specific guidance deta hai kaunsa TODO galat hai), fix karo
4. Verify ke end me "SOCH" section hota hai — usme diye sawaalon ka
   jawab bolke do. Interview me yehi poocha jaata hai, code nahi.
```

Manually do-terminal se bhi chala sakte ho (`python subscriber.py` ek
terminal me, `python publisher.py` doosre me) — `verify.py` sirf automation
hai, koi extra magic nahi.

## Protocol notes (AMQP basics jo har exercise me kaam aate hain)

```
Producer -> Exchange -> (binding rules) -> Queue -> Consumer

fanout  = routing_key IGNORE, saari bound queues ko message
direct  = routing_key ka EXACT match
topic   = routing_key pattern match (`*` = ek word, `#` = zero+ words)

durable=True (queue/exchange)     -> broker restart survive karta hai
delivery_mode=2 (message)         -> disk pe persist hota hai
confirm_delivery() (publisher)    -> broker ne accept kiya, confirm milta hai
mandatory=True (publish)          -> unroutable ho to broker WAPAS bhejta hai
```

## Troubleshooting

| Problem | Fix |
|---|---|
| `pika.exceptions.AMQPConnectionError` | RabbitMQ chal raha hai? `docker compose ps`, ya `rabbitmqctl status` (native install) |
| `verify.py` me subscriber se kuch nahi mila | TODO abhi bhara nahi (❌ output check karo), ya `time.sleep()` window kam pada — broker load pe badha do |
| `PRECONDITION_FAILED — inequivalent arg 'durable'` | Same exchange/queue pehle DIFFERENT durable flag se declare hui thi. Management UI (`localhost:15672`) se delete karo, phir retry |
| Port `5672`/`15672` busy | Koi aur RabbitMQ chal raha hai — `lsof -i :5672` check karo. Docker use kar rahe ho to `docker-compose.yml` me ports remap karo |
| `05` ka verify.py management API se connect nahi hota | Management plugin ON hai? `rabbitmq:3-management` image use karo, ya native install pe `rabbitmq-plugins enable rabbitmq_management` |
| Purana consumer/queue message leke baitha hai | Management UI se queue purge karo, ya `docker compose down -v` (fresh broker) |

---

**Related:** [theory files](../theory/) · [reference modules](../practical/) · [Kafka labs](../../07_Kafka/labs/) · [Celery labs](../../09_Celery/labs/)
