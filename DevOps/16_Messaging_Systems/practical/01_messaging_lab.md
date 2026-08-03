# Messaging Systems — Hands-On Lab
**DevOps Track · Phase 16 Practical**

## Prerequisites

Everything here runs locally via Docker — no AWS account needed for the RabbitMQ/Kafka/Redis Streams labs. The SQS lab uses **LocalStack** (a local AWS emulator) so you can practice the exact `aws sqs` CLI commands from the lesson file without any cloud spend or real AWS credentials.

- Docker + Docker Compose
- AWS CLI installed (`aws --version`) — used against LocalStack, not real AWS
- `rabbitmqadmin` or just `rabbitmqctl` via `docker exec` (RabbitMQ management plugin gives you a UI too, at `localhost:15672`)
- Kafka CLI tools (`kafka-topics.sh`, `kafka-console-producer.sh`, etc.) — available inside the Confluent/Bitnami Kafka Docker images via `docker exec`, no separate install needed
- `redis-cli` for the Redis Streams section
- Python 3.10+ with `pika` (RabbitMQ), `kafka-python` or `confluent-kafka`, and `boto3` (SQS) if you want to write producer/consumer scripts instead of pure CLI

---

## Lab 1: RabbitMQ — Exchanges, Bindings, and Routing Keys

**Objective:** Build a working exchange → binding → queue topology and prove routing keys actually control delivery, matching the model in `01_messaging_systems.md`.

**Task:**
1. Start a RabbitMQ container with the management plugin enabled.
2. Declare a `topic` exchange named `orders`.
3. Declare two queues: `orders.created.q` and `orders.all.q`.
4. Bind `orders.created.q` to the `orders` exchange with routing key `orders.created`. Bind `orders.all.q` with routing key `orders.*`.
5. Publish three messages to the `orders` exchange with routing keys `orders.created`, `orders.updated`, and `orders.deleted`.
6. Use `rabbitmqctl list_queues name messages` to show which queue(s) received which messages, and explain why `orders.all.q` got all three but `orders.created.q` got only one.

<details>
<summary>Solution / walkthrough</summary>

```bash
docker run -d --name rabbitmq \
  -p 5672:5672 -p 15672:15672 \
  rabbitmq:3-management
```

```bash
# enable management API access via rabbitmqadmin (bundled in the management image)
docker exec rabbitmq rabbitmqctl list_exchanges name type

docker exec rabbitmq rabbitmqadmin declare exchange name=orders type=topic durable=true
docker exec rabbitmq rabbitmqadmin declare queue name=orders.created.q durable=true
docker exec rabbitmq rabbitmqadmin declare queue name=orders.all.q durable=true

docker exec rabbitmq rabbitmqadmin declare binding \
  source=orders destination=orders.created.q routing_key=orders.created

docker exec rabbitmq rabbitmqadmin declare binding \
  source=orders destination=orders.all.q routing_key="orders.*"
```

```bash
docker exec rabbitmq rabbitmqadmin publish exchange=orders routing_key=orders.created payload="msg1"
docker exec rabbitmq rabbitmqadmin publish exchange=orders routing_key=orders.updated payload="msg2"
docker exec rabbitmq rabbitmqadmin publish exchange=orders routing_key=orders.deleted payload="msg3"
```

```bash
docker exec rabbitmq rabbitmqctl list_queues name messages
# orders.created.q   1   <- only matched "orders.created" exactly
# orders.all.q        3   <- "orders.*" matches one word after "orders." for all three
```

Why: `topic` exchanges match routing keys against binding patterns word-by-word (`.` separated), where `*` matches exactly one word and `#` matches zero or more. `orders.created` is an exact match for the `orders.created.q` binding, but `orders.*` matches any single-word suffix, so all three land there. This is the mechanic behind fan-out-with-filtering patterns in real systems (e.g., an audit-log consumer bound to `#` gets everything, while a specific service only binds to the event types it cares about).
</details>

---

## Lab 2: Kafka — Partitions, Replication, and Consumer Group Rebalancing

**Objective:** Create a replicated, partitioned topic, produce/consume through consumer groups, and observe rebalancing and lag — the core ops mechanics from the lesson.

**Task:**
1. Start a 3-broker Kafka cluster locally via Docker Compose (KRaft mode, no separate ZooKeeper needed on modern images).
2. Create a topic `orders` with 6 partitions and replication factor 3.
3. Describe the topic and identify which broker leads which partition.
4. Start a console producer and send 20 messages with different keys (e.g. `customer-1` through `customer-5`, cycling).
5. Start TWO console consumers in the SAME consumer group (`order-processors`) and watch how partitions split between them via `kafka-consumer-groups.sh --describe`.
6. Kill one consumer mid-stream and observe partition rebalancing — the surviving consumer should pick up all 6 partitions.
7. Check consumer lag with `kafka-consumer-groups.sh --describe --group order-processors` after producing more messages while a consumer is paused.

<details>
<summary>Solution / walkthrough</summary>

```yaml
# docker-compose.yml — 3-broker KRaft cluster (simplified single-compose-file setup)
services:
  kafka1:
    image: confluentinc/cp-kafka:7.6.0
    environment:
      KAFKA_NODE_ID: 1
      KAFKA_PROCESS_ROLES: broker,controller
      KAFKA_LISTENERS: PLAINTEXT://:9092,CONTROLLER://:9093
      KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://kafka1:9092
      KAFKA_CONTROLLER_QUORUM_VOTERS: 1@kafka1:9093,2@kafka2:9093,3@kafka3:9093
      KAFKA_CONTROLLER_LISTENER_NAMES: CONTROLLER
      KAFKA_LISTENER_SECURITY_PROTOCOL_MAP: PLAINTEXT:PLAINTEXT,CONTROLLER:PLAINTEXT
      CLUSTER_ID: "kafka-lab-cluster-id-1"
    ports: ["9092:9092"]
  kafka2:
    image: confluentinc/cp-kafka:7.6.0
    environment:
      KAFKA_NODE_ID: 2
      KAFKA_PROCESS_ROLES: broker,controller
      KAFKA_LISTENERS: PLAINTEXT://:9092,CONTROLLER://:9093
      KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://kafka2:9092
      KAFKA_CONTROLLER_QUORUM_VOTERS: 1@kafka1:9093,2@kafka2:9093,3@kafka3:9093
      KAFKA_CONTROLLER_LISTENER_NAMES: CONTROLLER
      KAFKA_LISTENER_SECURITY_PROTOCOL_MAP: PLAINTEXT:PLAINTEXT,CONTROLLER:PLAINTEXT
      CLUSTER_ID: "kafka-lab-cluster-id-1"
  kafka3:
    image: confluentinc/cp-kafka:7.6.0
    environment:
      KAFKA_NODE_ID: 3
      KAFKA_PROCESS_ROLES: broker,controller
      KAFKA_LISTENERS: PLAINTEXT://:9092,CONTROLLER://:9093
      KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://kafka3:9092
      KAFKA_CONTROLLER_QUORUM_VOTERS: 1@kafka1:9093,2@kafka2:9093,3@kafka3:9093
      KAFKA_CONTROLLER_LISTENER_NAMES: CONTROLLER
      KAFKA_LISTENER_SECURITY_PROTOCOL_MAP: PLAINTEXT:PLAINTEXT,CONTROLLER:PLAINTEXT
      CLUSTER_ID: "kafka-lab-cluster-id-1"
```

```bash
docker compose up -d
docker exec kafka1 kafka-topics.sh --create --topic orders \
    --partitions 6 --replication-factor 3 --bootstrap-server kafka1:9092

docker exec kafka1 kafka-topics.sh --describe --topic orders --bootstrap-server kafka1:9092
# note the Leader column per partition — spread across brokers 1,2,3
```

```bash
# producer with keys — keys determine partition assignment (same key -> same partition, always)
docker exec -it kafka1 kafka-console-producer.sh --topic orders \
    --bootstrap-server kafka1:9092 --property "parse.key=true" --property "key.separator=:"
# type: customer-1:order created
#       customer-2:order created
#       ...20 lines cycling customer-1..5
```

```bash
# two consumers, same group, in two separate terminals
docker exec -it kafka1 kafka-console-consumer.sh --topic orders \
    --bootstrap-server kafka1:9092 --group order-processors

docker exec -it kafka1 kafka-console-consumer.sh --topic orders \
    --bootstrap-server kafka1:9092 --group order-processors
```

```bash
# while both are running:
docker exec kafka1 kafka-consumer-groups.sh --bootstrap-server kafka1:9092 \
    --describe --group order-processors
# each consumer owns ~3 of the 6 partitions
```

```bash
# Ctrl+C one consumer, then re-run the describe command
docker exec kafka1 kafka-consumer-groups.sh --bootstrap-server kafka1:9092 \
    --describe --group order-processors
# after rebalance completes, the surviving consumer owns all 6 partitions
```

```bash
# produce more messages while the survivor is paused/slow, then check LAG
docker exec kafka1 kafka-consumer-groups.sh --bootstrap-server kafka1:9092 \
    --describe --group order-processors
# LAG column shows CURRENT-OFFSET vs LOG-END-OFFSET — this is the #1 metric
# for "is this consumer keeping up," exactly as the lesson states
```

Why this matters: watching a rebalance happen live — partitions visibly moving from a dying consumer to the survivor within seconds — makes "consumer group" a concrete mechanism instead of a definition you memorized. This is also exactly what you'd watch during a real deploy of a Kafka consumer service.
</details>

---

## Lab 3: Production-Style — Producer/Consumer with a Dead-Letter Queue, Prove a Poison Message Lands There

**Objective:** Build a real DLQ setup and PROVE it works by sending a message designed to always fail processing, watching it retry, then land in the DLQ — directly implementing the pattern from the lesson's SQS section (adaptable to RabbitMQ, done here with SQS via LocalStack since that's where the lesson gives exact CLI commands).

**Task:**
1. Start LocalStack via Docker Compose.
2. Create a main queue `orders-queue` and a DLQ `orders-dlq` using the AWS CLI pointed at LocalStack.
3. Attach a redrive policy to `orders-queue` with `maxReceiveCount = 3` targeting `orders-dlq`.
4. Write a small Python consumer script using `boto3` that receives messages but NEVER deletes them (simulating a crashing/failing consumer) — this forces SQS's visibility-timeout-expiry-and-redeliver cycle.
5. Send one "poison" message to `orders-queue`.
6. Run your consumer script in a loop, receiving (not deleting) the message 3 times with the visibility timeout expiring between each. Confirm on the 4th receive attempt the message is GONE from `orders-queue` and has appeared in `orders-dlq`.
7. Set a short visibility timeout (e.g. 5 seconds) so you don't have to wait long between redelivery attempts.

<details>
<summary>Solution / walkthrough</summary>

```yaml
# docker-compose.yml
services:
  localstack:
    image: localstack/localstack
    ports: ["4566:4566"]
    environment:
      - SERVICES=sqs
```

```bash
docker compose up -d
export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test
export AWS_DEFAULT_REGION=us-east-1
ENDPOINT="--endpoint-url=http://localhost:4566"

aws sqs create-queue --queue-name orders-dlq $ENDPOINT
DLQ_ARN=$(aws sqs get-queue-attributes --queue-url http://localhost:4566/000000000000/orders-dlq \
  --attribute-names QueueArn $ENDPOINT --query 'Attributes.QueueArn' --output text)

aws sqs create-queue --queue-name orders-queue \
  --attributes VisibilityTimeout=5 $ENDPOINT
MAIN_URL=http://localhost:4566/000000000000/orders-queue

aws sqs set-queue-attributes --queue-url $MAIN_URL $ENDPOINT \
  --attributes "{\"RedrivePolicy\":\"{\\\"deadLetterTargetArn\\\":\\\"$DLQ_ARN\\\",\\\"maxReceiveCount\\\":3}\"}"
```

```bash
# send the poison message
aws sqs send-message --queue-url $MAIN_URL --message-body "poison-payload" $ENDPOINT
```

```python
# consumer.py — deliberately never deletes the message, simulating a crashing consumer
import boto3, time

sqs = boto3.client("sqs", endpoint_url="http://localhost:4566",
                    aws_access_key_id="test", aws_secret_access_key="test",
                    region_name="us-east-1")
queue_url = "http://localhost:4566/000000000000/orders-queue"

for attempt in range(1, 6):
    resp = sqs.receive_message(QueueUrl=queue_url, MaxNumberOfMessages=1,
                                AttributeNames=["ApproximateReceiveCount"])
    msgs = resp.get("Messages", [])
    if not msgs:
        print(f"attempt {attempt}: no message visible (in flight or moved to DLQ)")
    else:
        m = msgs[0]
        count = m["Attributes"]["ApproximateReceiveCount"]
        print(f"attempt {attempt}: received, ApproximateReceiveCount={count} — NOT deleting (simulated failure)")
    time.sleep(6)   # wait past the 5s visibility timeout before next attempt
```

```bash
python consumer.py
# attempt 1: received, ApproximateReceiveCount=1
# attempt 2: received, ApproximateReceiveCount=2
# attempt 3: received, ApproximateReceiveCount=3
# attempt 4: no message visible   <- SQS moved it to the DLQ after maxReceiveCount=3

aws sqs get-queue-attributes --queue-url $MAIN_URL --attribute-names ApproximateNumberOfMessages $ENDPOINT
# 0

aws sqs receive-message --queue-url http://localhost:4566/000000000000/orders-dlq $ENDPOINT
# the poison-payload message is here
```

Why this matters: this is the single most concrete proof of the lesson's core warning — "without a DLQ a poison message blocks/cycles indefinitely." You've now watched it happen and watched the safety net catch it, which is exactly the confidence an interviewer is checking for when they ask "what happens if a message keeps failing?"
</details>

---

## Lab 4: Troubleshooting — Diagnose and Fix Growing Consumer Lag

**Objective:** Reproduce the "queue depth/consumer lag silently growing while everything looks fine in APM" incident pattern called out in both the Messaging and System Design lesson files.

**Task:**
1. Using the Kafka cluster from Lab 2, create a topic `events` with 3 partitions.
2. Write a producer script that sends 500 messages as fast as possible.
3. Write a consumer that deliberately sleeps 200ms per message (simulating a slow downstream call), consuming from a single-instance consumer group.
4. While the consumer is running, poll `kafka-consumer-groups.sh --describe` every few seconds and record the LAG value over time — confirm it's growing, not shrinking, because production rate > consumption rate.
5. Fix it: scale the consumer group to 3 instances (matching partition count) and re-run, confirming LAG now trends toward zero.
6. Write down (in your own words, 3-4 sentences) what alert/dashboard would have caught this BEFORE a human noticed — tie it back to Phase 19 (Observability).

<details>
<summary>Solution / walkthrough</summary>

```bash
docker exec kafka1 kafka-topics.sh --create --topic events --partitions 3 \
    --replication-factor 3 --bootstrap-server kafka1:9092
```

```python
# producer.py
from kafka import KafkaProducer
p = KafkaProducer(bootstrap_servers="localhost:9092")
for i in range(500):
    p.send("events", key=str(i % 3).encode(), value=f"event-{i}".encode())
p.flush()
```

```python
# slow_consumer.py
from kafka import KafkaConsumer
import time
c = KafkaConsumer("events", bootstrap_servers="localhost:9092",
                   group_id="event-processors", auto_offset_reset="earliest")
for msg in c:
    time.sleep(0.2)   # simulated slow downstream call
    print(msg.offset)
```

```bash
python producer.py &
python slow_consumer.py &

# poll lag every few seconds
watch -n 5 'docker exec kafka1 kafka-consumer-groups.sh --bootstrap-server kafka1:9092 \
    --describe --group event-processors'
# LAG climbs steadily — one consumer processing 3 partitions worth of work
# at 5 msgs/sec (200ms each) can't keep up with a 500-message burst
```

```bash
# fix: scale to 3 consumer instances, one per partition
python slow_consumer.py &   # instance 2
python slow_consumer.py &   # instance 3
# re-run the describe command — LAG now drops roughly 3x faster since all
# 3 partitions are being drained in parallel instead of serially by one consumer
```

**What would have caught this earlier:** a Prometheus alert on Kafka consumer group lag (exported via the Kafka JMX exporter or Burrow) crossing a threshold — e.g. `kafka_consumergroup_lag > 1000 for 5m` — paging before a human notices downstream symptoms (stale data, a business metric that "looks a little off"). This is exactly the Phase 19 point: metrics tell you something's wrong before logs or a customer complaint do, and consumer lag is a first-class metric precisely because APM/error-rate dashboards stay green the whole time this is happening — nothing is erroring, it's just falling behind.
</details>

---

## Self-Check Checklist

- [ ] Can you explain the difference between `direct`, `topic`, and `fanout` RabbitMQ exchanges and give a real use case for each, without looking it up?
- [ ] Can you write a `kafka-topics.sh --create` command with partitions and replication factor from memory, and explain what replication factor 3 actually protects against?
- [ ] Can you explain why more consumers than partitions in a Kafka consumer group leaves some consumers idle?
- [ ] Can you configure an SQS redrive policy (DLQ + maxReceiveCount) via the AWS CLI without referencing docs?
- [ ] Can you explain the visibility timeout tradeoff — too short vs too long — and state the "6x processing time" rule of thumb?
- [ ] Given a growing consumer lag graph with no error-rate spike anywhere, can you explain why that's still an incident?
- [ ] Can you explain when you'd choose Redis Streams over standing up a full Kafka or RabbitMQ cluster?
- [ ] Can you name the one thing RabbitMQ queues do NOT support that Kafka topics do by design (replay of historical messages)?
- [ ] Can you explain why "DLQ depth > 0" should always be an alert, not just a queue you check manually sometimes?
- [ ] Can you describe, end to end, what happens to a message that fails processing 10 times with `maxReceiveCount=3` configured — where does it end up and when?
