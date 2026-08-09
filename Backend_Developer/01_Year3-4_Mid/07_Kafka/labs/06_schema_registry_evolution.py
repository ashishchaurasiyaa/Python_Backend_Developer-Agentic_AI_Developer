"""
Kafka Lab 06 — Schema Registry & Avro Evolution
================================================
OBJECTIVE: ek schema ko evolve karke apni aankhon se dekho ki (a) message ke
bytes me magic byte + schema id chhupa hai, (b) PURANE v1 messages naye v2
consumer me default ke saath sahi decode hote hain, aur (c) breaking change ko
registry HTTP 409 se publish hone se PEHLE hi rok deta hai.

TASK:
  1. TODO 1: wire format parse karo (magic byte + schema id)
             ← yeh part broker/registry ke BINA bhi chalta hai
  2. TODO 2: subject pe compatibility BACKWARD_TRANSITIVE set karo
  3. TODO 3: v2 me `currency` field add karo — DEFAULT ke saath
  4. TODO 4: consumer ko v2 READER schema do (purane messages me default bhare)
  5. Run: python 06_schema_registry_evolution.py

Prereq:
  pip install "confluent-kafka[avro]"        # labs 01-05 wala aiokafka nahi —
                                             # SR serializers sirf isme hain
  docker compose -f docker-compose.yml -f docker-compose.schema-registry.yml up -d

  Base docker-compose.yml me schema-registry service NAHI hai. Neeche
  COMPOSE_SNIPPET me override file ka poora content hai — usko
  labs/docker-compose.schema-registry.yml naam se save karo.
  (Script khud bhi print kar deta hai agar registry reachable na ho.)

Theory: ../10_schema_registry_avro.md
"""

import json
import struct
import uuid

try:
    from confluent_kafka import Consumer, Producer
    from confluent_kafka.schema_registry import Schema, SchemaRegistryClient
    from confluent_kafka.schema_registry.avro import (AvroDeserializer,
                                                      AvroSerializer)
    from confluent_kafka.schema_registry.error import SchemaRegistryError
    from confluent_kafka.serialization import (MessageField,
                                               SerializationContext)
    HAS_CLIENT = True
except ImportError:                          # pragma: no cover
    HAS_CLIENT = False

BOOTSTRAP = "localhost:9092"
REGISTRY_URL = "http://localhost:8081"
TOPIC = f"lab-schema-{uuid.uuid4().hex[:6]}"     # har run pe fresh subject
SUBJECT = f"{TOPIC}-value"                       # TopicNameStrategy (default)


COMPOSE_SNIPPET = """
# ── labs/docker-compose.schema-registry.yml ───────────────────────────────
# Base compose ko EXTEND karta hai (usme SR nahi hai). Do cheezein karta hai:
#   1. kafka pe ek INTERNAL listener add karta hai — base file sirf
#      "localhost:9092" advertise karti hai, jo container-ke-andar se
#      reachable nahi hai. SR ko kafka:29092 chahiye.
#   2. schema-registry service khada karta hai (port 8081).
#
# Start: docker compose -f docker-compose.yml \\
#                       -f docker-compose.schema-registry.yml up -d
# Check: curl http://localhost:8081/subjects        → []
services:
  kafka:
    environment:
      KAFKA_LISTENERS: PLAINTEXT://:9092,INTERNAL://:29092,CONTROLLER://:9093
      KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://localhost:9092,INTERNAL://kafka:29092
      KAFKA_LISTENER_SECURITY_PROTOCOL_MAP: CONTROLLER:PLAINTEXT,PLAINTEXT:PLAINTEXT,INTERNAL:PLAINTEXT
      KAFKA_INTER_BROKER_LISTENER_NAME: PLAINTEXT

  schema-registry:
    image: confluentinc/cp-schema-registry:7.6.1
    container_name: schema-registry-lab
    depends_on:
      kafka:
        condition: service_healthy
    ports:
      - "8081:8081"
    environment:
      SCHEMA_REGISTRY_HOST_NAME: schema-registry
      SCHEMA_REGISTRY_LISTENERS: http://0.0.0.0:8081
      # prefix = security PROTOCOL (INTERNAL listener ka protocol PLAINTEXT hai)
      SCHEMA_REGISTRY_KAFKASTORE_BOOTSTRAP_SERVERS: PLAINTEXT://kafka:29092
      SCHEMA_REGISTRY_KAFKASTORE_TOPIC_REPLICATION_FACTOR: 1
      SCHEMA_REGISTRY_SCHEMA_COMPATIBILITY_LEVEL: backward

  # UI ko bhi SR dikha do — messages ab decoded dikhenge (http://localhost:8080)
  kafka-ui:
    environment:
      KAFKA_CLUSTERS_0_BOOTSTRAPSERVERS: kafka:29092
      KAFKA_CLUSTERS_0_SCHEMAREGISTRY: http://schema-registry:8081
# ──────────────────────────────────────────────────────────────────────────
"""


# ==========================================================================
# Schemas — Python dicts, taaki TODO 3 me sirf ek field bharna pade
# ==========================================================================

def avro_schema(fields: list) -> str:
    """Avro record schema banao (registry ko string chahiye, dict nahi)."""
    return json.dumps({
        "type": "record",
        "name": "OrderCreated",
        "namespace": "com.shop.events",
        "fields": fields,
    })


V1_FIELDS = [
    {"name": "order_id", "type": "string"},
    {"name": "amount", "type": "double"},
]

# ─────────────────────────────────────────────────────────────────────────
# TODO 3: v2 me `currency` field add karo — string type, aur DEFAULT ke saath.
#   Kyun default? BACKWARD ka matlab: NAYA schema PURANA data padh sake.
#   v1 messages me currency hai hi nahi → reader ke paas default hona hi
#   chahiye, warna resolution error. Bina default = registry 409.
#   Shape: {"name": ..., "type": ..., "default": ...}
#   Default "INR" rakho (verification isi ko check karta hai).
CURRENCY_FIELD = {}        # ← isse bharo
# ─────────────────────────────────────────────────────────────────────────

V2_FIELDS = V1_FIELDS + [CURRENCY_FIELD]

# v3 candidates — dono TOOTNE chahiye, par alag-alag wajah se:
#   BAD   : required field add (koi bhi backward mode reject karega)
#   TRAP  : currency ka default HATA diya. v2 ke against theek lagta hai,
#           v1 ke against nahi → sirf TRANSITIVE mode pakadta hai.
V3_BAD_FIELDS = V2_FIELDS + [{"name": "email", "type": "string"}]
V3_TRAP_FIELDS = V1_FIELDS + [{"name": "currency", "type": "string"}]


# ==========================================================================
# TODO 1 — wire format (infra ke bina verify hota hai)
# ==========================================================================

def parse_wire_format(raw: bytes) -> tuple:
    """
    Confluent wire format:

        byte 0      bytes 1-4              bytes 5..N
        ┌─────────┬──────────────────────┬──────────────────────┐
        │ magic 0 │ schema id (int32 BE) │ Avro binary payload  │
        └─────────┴──────────────────────┴──────────────────────┘

    Returns: (magic, schema_id, payload_bytes)
    """
    magic = raw[0]                    # 0x00 = Schema Registry format

    # ─────────────────────────────────────────────────────
    # TODO 1: schema id aur payload nikalo.
    #   schema id = bytes 1..4, BIG-endian unsigned int32
    #     Hint: struct.unpack(">I", raw[1:5])[0]
    #     (">" = big-endian / network order, "I" = uint32)
    #   payload  = 5th byte se aage sab kuch
    schema_id = None        # ← isse badlo
    payload = b""           # ← isse badlo
    # ─────────────────────────────────────────────────────

    return magic, schema_id, payload


# ==========================================================================
# TODO 2 — subject-level compatibility
# ==========================================================================

def set_subject_compatibility(sr, subject: str) -> None:
    """
    Is subject pe BACKWARD_TRANSITIVE lagao.

    Global default BACKWARD hai (non-transitive) — wo sirf PICHLE version se
    compare karta hai. Long-retention / compacted / replay-hone-wale topic pe
    yeh trap hai: v3-vs-v2 pass ho jaata hai, v3-vs-v1 fail hota hai, aur
    dhamaka tab hota hai jab koi offset 0 se replay karta hai.
    """
    # ─────────────────────────────────────────────────────
    # TODO 2: compatibility level set karo.
    #   Hint: sr.set_compatibility(subject_name=..., level="...")
    #   Level string exactly "BACKWARD_TRANSITIVE" hona chahiye.
    #   (REST equivalent: PUT /config/<subject>  {"compatibility": "..."} )
    pass                    # ← isse hatao aur set_compatibility call karo
    # ─────────────────────────────────────────────────────


# ==========================================================================
# Helpers
# ==========================================================================

def make_serializer(sr, schema_str: str):
    """
    PRODUCTION shape: auto.register.schemas=False.
    Producer ko subject mutate karne ka haq nahi — registration ek CI step hai.
    Yahan serializer sirf schema ka ID LOOKUP karta hai.
    """
    return AvroSerializer(
        sr, schema_str, conf={"auto.register.schemas": False}
    )


def produce_one(serializer, record: dict) -> None:
    producer = Producer({"bootstrap.servers": BOOTSTRAP,
                         "enable.idempotence": True,
                         # macOS pe "localhost" pehle ::1 resolve hota hai aur
                         # broker sirf IPv4 pe listen karta hai → shor macha
                         # dene wale FAIL logs. v4 force karo.
                         "broker.address.family": "v4"})
    value = serializer(record,
                       SerializationContext(TOPIC, MessageField.VALUE))
    producer.produce(TOPIC, key=b"ord-1", value=value)
    producer.flush(10)


def consume_all(deserializer, expected: int) -> list:
    """Raw bytes + decoded dict dono wapas karo."""
    consumer = Consumer({
        "bootstrap.servers": BOOTSTRAP,
        "group.id": f"lab06-{uuid.uuid4().hex[:6]}",
        "auto.offset.reset": "earliest",
        "enable.auto.commit": False,
        "broker.address.family": "v4",
    })
    consumer.subscribe([TOPIC])
    out, polls = [], 0
    try:
        while len(out) < expected and polls < 30:
            msg = consumer.poll(1.0)
            polls += 1
            if msg is None or msg.error():
                continue
            raw = msg.value()
            decoded = deserializer(
                raw, SerializationContext(msg.topic(), MessageField.VALUE))
            out.append((raw, decoded))
    finally:
        consumer.close()
    return out


def effective_compatibility(sr, subject: str) -> str:
    """
    Subject ka effective level.

    Gotcha: agar subject pe override set NAHI hai to
    GET /config/<subject> 404 deta hai (exception!) — tab GLOBAL level lagta
    hai. Yeh production me bhi confuse karta hai: "compatibility to backward
    hai na?" — haan, global se, subject pe kuch set hi nahi tha.
    """
    try:
        return str(sr.get_compatibility(subject))
    except SchemaRegistryError:
        return f"{sr.get_compatibility()} (global — subject pe override nahi)"


def rejected_by_registry(sr, subject: str, fields: list) -> tuple:
    """register_schema try karo — (rejected?, detail) wapas karo."""
    try:
        sr.register_schema(subject, Schema(avro_schema(fields), "AVRO"))
        return False, "ACCEPTED (registry ne rok nahi lagayi)"
    except SchemaRegistryError as exc:
        status = getattr(exc, "http_status_code", "?")
        return True, f"HTTP {status} / error_code {exc.error_code}"


# ==========================================================================
# Verification
# ==========================================================================

CHECKS = []


def check(name: str, passed: bool, hint: str = "") -> None:
    CHECKS.append((name, passed, hint))
    mark = "✅" if passed else "❌"
    print(f"  {mark} {name}")
    if not passed and hint:
        print(f"       → {hint}")


# ==========================================================================
# Offline part — hamesha chalta hai
# ==========================================================================

def run_offline() -> None:
    print("\n[1] Wire format (koi infra nahi chahiye)")

    # Haath se banaya hua frame: magic 0x00 + schema id 42 + dummy payload
    frame = b"\x00" + struct.pack(">I", 42) + b"\x06abc"
    magic, schema_id, payload = parse_wire_format(frame)
    print(f"    frame = {frame!r}")
    print(f"    magic={magic}  schema_id={schema_id}  payload={payload!r}")

    check("TODO 1 — schema id parse", schema_id == 42,
          "struct.unpack(\">I\", raw[1:5])[0] — big-endian uint32")
    check("TODO 1 — payload slice", payload == b"\x06abc",
          "payload raw[5:] hai (magic 1 byte + id 4 bytes ke baad)")

    # Galat magic byte = plain producer ne likha, registry-aware consumer padh
    # raha hai (ya ulta). "Unknown magic byte!" isi ka naam hai.
    bad_magic, _, _ = parse_wire_format(b"\x01\x00\x00\x00\x01xyz")
    check("Non-registry message detect", bad_magic != 0,
          "magic != 0 → yeh message SR serializer se nahi aaya")


# ==========================================================================
# Online part — broker + registry chahiye
# ==========================================================================

def run_online() -> bool:
    """Returns False agar infra reachable nahi hai."""
    sr = SchemaRegistryClient({"url": REGISTRY_URL})
    try:
        sr.get_subjects()
    except Exception as exc:                       # noqa: BLE001
        print(f"\n[skip] Schema Registry {REGISTRY_URL} pe nahi mila: "
              f"{type(exc).__name__}")
        print(COMPOSE_SNIPPET)
        return False

    print(f"\n[2] Registry connected. topic={TOPIC} subject={SUBJECT}")

    # ── v1 register + ek purana message produce ──────────────────────────
    v1_id = sr.register_schema(SUBJECT, Schema(avro_schema(V1_FIELDS), "AVRO"))
    print(f"    v1 registered → schema id {v1_id}")

    set_subject_compatibility(sr, SUBJECT)
    level = effective_compatibility(sr, SUBJECT)
    print(f"    subject compatibility = {level}")
    check("TODO 2 — BACKWARD_TRANSITIVE set", "TRANSITIVE" in level.upper(),
          "sr.set_compatibility(subject_name=SUBJECT, level=\"BACKWARD_TRANSITIVE\")")

    produce_one(make_serializer(sr, avro_schema(V1_FIELDS)),
                {"order_id": "ord-1", "amount": 999.0})
    print("    v1 message produced (purana producer)")

    # ── v2: legal evolution ──────────────────────────────────────────────
    print("\n[3] v2 — field add karke evolve")
    if not CURRENCY_FIELD:
        check("TODO 3 — currency field", False,
              "CURRENCY_FIELD abhi khaali hai — bharo, phir dobara chalao")
        return True

    v2_schema = avro_schema(V2_FIELDS)
    compatible = sr.test_compatibility(SUBJECT, Schema(v2_schema, "AVRO"))
    check("TODO 3 — v2 compatible", bool(compatible),
          "default missing? Bina default field add karna BACKWARD-illegal hai")
    if not compatible:
        return True

    v2_id = sr.register_schema(SUBJECT, Schema(v2_schema, "AVRO"))
    print(f"    v2 registered → schema id {v2_id} (v1 ka id {v1_id} tha)")
    produce_one(make_serializer(sr, v2_schema),
                {"order_id": "ord-1", "amount": 1499.0, "currency": "USD"})
    print("    v2 message produced (naya producer)")

    # ── breaking changes: registry ko rokna chahiye ──────────────────────
    print("\n[4] Breaking changes — registry inhe reject kare")

    bad_rejected, bad_detail = rejected_by_registry(sr, SUBJECT, V3_BAD_FIELDS)
    print(f"    v3-BAD  (required `email` add): {bad_detail}")
    check("Required field add rejected", bad_rejected,
          "Bina default field add = naya reader purana data nahi padh sakta")

    trap_rejected, trap_detail = rejected_by_registry(sr, SUBJECT,
                                                     V3_TRAP_FIELDS)
    print(f"    v3-TRAP (currency ka default hataya): {trap_detail}")
    check("Transitive trap caught", trap_rejected,
          "v2 ke against yeh LEGAL hai — sirf BACKWARD_TRANSITIVE hi v1 ke "
          "against check karta hai. TODO 2 bhara?")

    # ── consumer: purana data + naya reader schema ───────────────────────
    print("\n[5] v2 reader se DONO messages padho")

    # ─────────────────────────────────────────────────────
    # TODO 4: AvroDeserializer ko READER schema do.
    #   Bina reader schema: writer ka shape milta hai → v1 message me
    #   `currency` key hogi hi nahi.
    #   Reader schema ke saath: deserializer writer schema (id se fetch) aur
    #   reader schema ke beech RESOLUTION karta hai → v1 message me
    #   currency="INR" (default) apne aap bhar jaata hai. Yahi "schema
    #   evolution" ka poora point hai.
    #   Hint: AvroDeserializer(sr, <reader schema string>)
    deserializer = AvroDeserializer(sr)        # ← reader schema add karo
    # ─────────────────────────────────────────────────────

    messages = consume_all(deserializer, expected=2)
    if len(messages) < 2:
        check("Dono messages mile", False,
              "Broker se messages nahi aaye — docker compose ps check karo")
        return True

    for i, (raw, decoded) in enumerate(messages, start=1):
        magic, sid, payload = parse_wire_format(raw)
        print(f"    msg{i}: magic={magic} schema_id={sid} "
              f"payload={len(payload)}B  →  {decoded}")

    ids = [parse_wire_format(raw)[1] for raw, _ in messages]
    check("Dono messages ke schema id alag", ids[0] != ids[1],
          "Same id? Dono messages ek hi schema se likhe gaye")

    old_msg = messages[0][1]
    check("TODO 4 — purane message me default bhara",
          old_msg.get("currency") == "INR",
          "v1 message me currency nahi thi. Reader schema pass kiya? "
          "AvroDeserializer(sr, v2_schema)")

    new_msg = messages[1][1]
    check("Naya message apni value rakhta hai",
          new_msg.get("currency") == "USD",
          "v2 producer ne USD likha tha — default se overwrite nahi hona chahiye")
    return True


# ==========================================================================

def main() -> None:
    print(f"\n{'=' * 62}")
    print("Kafka Lab 06 — Schema Registry & Avro Evolution")
    print("=" * 62)

    run_offline()

    if not HAS_CLIENT:
        print("\n[skip] confluent-kafka install nahi hai — online part skip.")
        print('       pip install "confluent-kafka[avro]"')
        print(COMPOSE_SNIPPET)
    else:
        run_online()

    passed = sum(1 for _, ok, _ in CHECKS if ok)
    total = len(CHECKS)
    print("\n" + "─" * 62)
    if total and passed == total:
        print(f"✅ PASS — {passed}/{total} checks green")
    else:
        print(f"❌ {passed}/{total} checks pass. Upar ke ❌ hints padho.")

    print("""
SOCH (bolke jawab do):
  1. "Schema evolve karna hai bina consumers todke" — anchor answer bolo:
     compatibility mode → deploy order → legal changes → CI gate →
     truly-breaking ka playbook. (../10_schema_registry_avro.md)
  2. BACKWARD me consumers pehle deploy hote hain, FORWARD me producers.
     Kyun? Ek line me derive karke dikhao.
  3. v3-TRAP plain BACKWARD me PASS ho jaata. Wo bug production me kab
     phatega — deploy ke din, ya 6 mahine baad? (Hint: replay/compaction)
  4. Ek field ka naam badalna hai (`amount` → `total_amount`). Registry
     rename ko allow nahi karta — do raaste batao.
  5. Schema Registry down ho gaya. Chalte hue pods mar jaayenge ya nahi?
     Naye pods? Farq kyun? (Hint: serializer ka id↔schema cache)
  6. Ek hi topic pe OrderCreated + OrderPaid dono chahiye. Default
     TopicNameStrategy kyun mana karega, aur do fix kya hain?
""")


if __name__ == "__main__":
    main()
