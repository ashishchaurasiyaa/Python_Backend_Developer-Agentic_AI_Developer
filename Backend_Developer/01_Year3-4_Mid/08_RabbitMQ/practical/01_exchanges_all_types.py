"""
RabbitMQ — All Exchange Types Practical
═══════════════════════════════════════════════════════════════
Run: python 01_exchanges_all_types.py

Prerequisites:
  pip install pika
  docker run -d --name rabbitmq -p 5672:5672 -p 15672:15672 rabbitmq:3-management
  Management UI: http://localhost:15672 (guest/guest)

Topics Covered:
  1. Direct Exchange
  2. Fanout Exchange
  3. Topic Exchange
  4. Headers Exchange
  5. Default Exchange

Note: Pehle Producer run karo, phir Consumer run karo.
"""

import pika
import json
import time
import threading

RABBITMQ_URL = 'localhost'

def get_channel():
    """Connection aur Channel create karo"""
    connection = pika.BlockingConnection(
        pika.ConnectionParameters(
            host=RABBITMQ_URL,
            heartbeat=600,
            blocked_connection_timeout=300
        )
    )
    channel = connection.channel()
    return connection, channel


# ═══════════════════════════════════════════════════════════
# SECTION 1: Direct Exchange
# ═══════════════════════════════════════════════════════════

def setup_direct_exchange():
    """Direct Exchange setup — queues + bindings"""
    conn, ch = get_channel()

    # Exchange declare
    ch.exchange_declare(exchange='order_direct', exchange_type='direct', durable=True)

    # Queues declare
    ch.queue_declare(queue='payment_queue', durable=True)
    ch.queue_declare(queue='inventory_queue', durable=True)
    ch.queue_declare(queue='email_queue', durable=True)

    # Bindings — exact routing_key match
    ch.queue_bind(exchange='order_direct', queue='payment_queue',   routing_key='payment')
    ch.queue_bind(exchange='order_direct', queue='inventory_queue', routing_key='inventory')
    ch.queue_bind(exchange='order_direct', queue='email_queue',     routing_key='email')

    print("✅ Direct Exchange setup done!")
    conn.close()


def direct_producer():
    """Direct Exchange — specific queue ko bhejo"""
    conn, ch = get_channel()
    ch.exchange_declare(exchange='order_direct', exchange_type='direct', durable=True)

    orders = [
        ('payment',   {'order_id': 101, 'amount': 999,  'action': 'charge_card'}),
        ('inventory', {'order_id': 101, 'item': 'Laptop', 'action': 'reduce_stock'}),
        ('email',     {'order_id': 101, 'to': 'alice@test.com', 'action': 'send_confirmation'}),
    ]

    for routing_key, data in orders:
        ch.basic_publish(
            exchange='order_direct',
            routing_key=routing_key,
            body=json.dumps(data),
            properties=pika.BasicProperties(delivery_mode=pika.DeliveryMode.Persistent)
        )
        print(f"📤 Direct [{routing_key}]: {data}")

    conn.close()


def direct_consumer(queue_name: str):
    """Consumer — ek specific queue sun"""
    conn, ch = get_channel()
    ch.queue_declare(queue=queue_name, durable=True)
    ch.basic_qos(prefetch_count=1)

    def callback(ch, method, properties, body):
        data = json.loads(body)
        print(f"📥 [{queue_name}] Received: {data}")
        time.sleep(0.2)  # simulate work
        ch.basic_ack(delivery_tag=method.delivery_tag)

    ch.basic_consume(queue=queue_name, on_message_callback=callback, auto_ack=False)
    print(f"Consumer started — listening on '{queue_name}'")
    ch.start_consuming()


# ═══════════════════════════════════════════════════════════
# SECTION 2: Fanout Exchange
# ═══════════════════════════════════════════════════════════

def setup_fanout_exchange():
    """Fanout Exchange setup"""
    conn, ch = get_channel()

    ch.exchange_declare(exchange='user_events_fanout', exchange_type='fanout', durable=True)

    ch.queue_declare(queue='email_service_queue',   durable=True)
    ch.queue_declare(queue='sms_service_queue',     durable=True)
    ch.queue_declare(queue='analytics_queue',       durable=True)

    # Fanout — routing_key ignored — sab queues ko jaata hai
    ch.queue_bind(exchange='user_events_fanout', queue='email_service_queue')
    ch.queue_bind(exchange='user_events_fanout', queue='sms_service_queue')
    ch.queue_bind(exchange='user_events_fanout', queue='analytics_queue')

    print("✅ Fanout Exchange setup done!")
    conn.close()


def fanout_producer():
    """User signup event — sabhi 3 services ko broadcast"""
    conn, ch = get_channel()
    ch.exchange_declare(exchange='user_events_fanout', exchange_type='fanout', durable=True)

    event = {
        "user_id": 42,
        "event": "user_signup",
        "name": "Alice",
        "email": "alice@test.com",
        "phone": "+91-9999999999"
    }

    ch.basic_publish(
        exchange='user_events_fanout',
        routing_key='',   # fanout mein ignored
        body=json.dumps(event),
        properties=pika.BasicProperties(delivery_mode=pika.DeliveryMode.Persistent)
    )
    print(f"📢 BROADCAST → all 3 services: {event}")
    conn.close()


def fanout_consumer(service_name: str, queue_name: str):
    """Each service independently consume karta hai"""
    conn, ch = get_channel()
    ch.queue_declare(queue=queue_name, durable=True)
    ch.basic_qos(prefetch_count=1)

    def callback(ch, method, properties, body):
        data = json.loads(body)
        print(f"📥 [{service_name}] Processing user event: user_id={data['user_id']}, name={data['name']}")
        ch.basic_ack(delivery_tag=method.delivery_tag)

    ch.basic_consume(queue=queue_name, on_message_callback=callback, auto_ack=False)
    print(f"{service_name} started!")
    ch.start_consuming()


# ═══════════════════════════════════════════════════════════
# SECTION 3: Topic Exchange
# ═══════════════════════════════════════════════════════════

def setup_topic_exchange():
    """Topic Exchange setup with wildcard patterns"""
    conn, ch = get_channel()

    ch.exchange_declare(exchange='app_logs_topic', exchange_type='topic', durable=True)

    # Different queues different patterns sun rahe hain
    queues_patterns = [
        ('all_errors_queue',    '*.error'),      # kisi bhi service ka error
        ('order_all_queue',     'order.#'),      # order se related sab
        ('india_logs_queue',    '#.india'),      # india se related sab
        ('critical_all_queue',  '#.critical.#'), # kahi bhi critical
        ('all_logs_queue',      '#'),            # sab kuch
    ]

    for queue_name, pattern in queues_patterns:
        ch.queue_declare(queue=queue_name, durable=True)
        ch.queue_bind(
            exchange='app_logs_topic',
            queue=queue_name,
            routing_key=pattern
        )
        print(f"  Queue '{queue_name}' bound with pattern '{pattern}'")

    print("✅ Topic Exchange setup done!")
    conn.close()


def topic_producer():
    """Different routing keys bhejo — kahan jaata hai dekho"""
    conn, ch = get_channel()
    ch.exchange_declare(exchange='app_logs_topic', exchange_type='topic', durable=True)

    events = [
        ('order.placed.india',       'Order placed in India'),
        ('order.error',              'Order processing error'),
        ('payment.error',            'Payment gateway error'),
        ('user.login.india',         'User login from India'),
        ('order.cancelled.usa',      'Order cancelled from USA'),
        ('system.critical.error',    'System critical failure'),
        ('user.signup.india',        'New user signup India'),
    ]

    print("\n📤 Publishing Topic Exchange messages:")
    for routing_key, message in events:
        ch.basic_publish(
            exchange='app_logs_topic',
            routing_key=routing_key,
            body=json.dumps({'key': routing_key, 'msg': message}).encode()
        )
        print(f"  [{routing_key}] → {message}")

    print("\nExpected routing:")
    print("  order.placed.india   → order_all_queue ✅, india_logs_queue ✅, all_logs_queue ✅")
    print("  order.error          → all_errors_queue ✅, order_all_queue ✅, all_logs_queue ✅")
    print("  payment.error        → all_errors_queue ✅, all_logs_queue ✅")
    print("  user.login.india     → india_logs_queue ✅, all_logs_queue ✅")
    print("  system.critical.error→ critical_all_queue ✅, all_logs_queue ✅")

    conn.close()


# ═══════════════════════════════════════════════════════════
# SECTION 4: Dead Letter Exchange Demo
# ═══════════════════════════════════════════════════════════

def setup_dlx_demo():
    """DLX setup — failed messages catch karo"""
    conn, ch = get_channel()

    # Step 1: DLX + DLQ pehle banao
    ch.exchange_declare(exchange='dlx', exchange_type='direct', durable=True)
    ch.queue_declare(queue='dead_letter_queue', durable=True)
    ch.queue_bind(exchange='dlx', queue='dead_letter_queue', routing_key='dead')

    # Step 2: Main queue — DLX attach karo
    ch.queue_declare(
        queue='orders_with_dlx',
        durable=True,
        arguments={
            'x-dead-letter-exchange':    'dlx',
            'x-dead-letter-routing-key': 'dead',
            'x-message-ttl':             10000,   # 10 sec TTL
        }
    )
    print("✅ DLX setup done!")
    conn.close()


def dlx_producer():
    """Messages bhejo — kuch fail karenge"""
    conn, ch = get_channel()
    ch.queue_declare(
        queue='orders_with_dlx',
        durable=True,
        arguments={
            'x-dead-letter-exchange':    'dlx',
            'x-dead-letter-routing-key': 'dead',
        }
    )

    orders = [
        {"order_id": 1, "amount": 100,   "type": "valid"},
        {"order_id": 2, "amount": 99999, "type": "invalid"},  # → DLQ
        {"order_id": 3, "amount": 500,   "type": "valid"},
        {"order_id": 4, "amount": 75000, "type": "invalid"},  # → DLQ
    ]

    for order in orders:
        ch.basic_publish(
            exchange='',
            routing_key='orders_with_dlx',
            body=json.dumps(order),
            properties=pika.BasicProperties(delivery_mode=pika.DeliveryMode.Persistent)
        )
        print(f"📤 Order sent: {order}")
    conn.close()


def dlx_consumer():
    """Main consumer — invalid orders ko DLQ mein bhejo"""
    conn, ch = get_channel()
    ch.basic_qos(prefetch_count=1)

    def callback(ch, method, properties, body):
        order = json.loads(body)
        print(f"\n📥 Processing order {order['order_id']} (amount: {order['amount']})")

        if order['amount'] > 10000:
            print(f"  ❌ Amount too high! → Sending to DLQ")
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
        else:
            print(f"  ✅ Order {order['order_id']} processed!")
            ch.basic_ack(delivery_tag=method.delivery_tag)

    ch.basic_consume(queue='orders_with_dlx', on_message_callback=callback, auto_ack=False)
    print("Main consumer started...")
    ch.start_consuming()


def dlq_monitor():
    """DLQ consumer — failed messages monitor karo"""
    conn, ch = get_channel()
    ch.basic_qos(prefetch_count=1)

    def callback(ch, method, properties, body):
        order = json.loads(body)
        print(f"⚠️  DLQ ALERT: Failed order received: {order}")
        # Yahan: alert bhejo, log karo, manual review karo
        ch.basic_ack(delivery_tag=method.delivery_tag)

    ch.basic_consume(queue='dead_letter_queue', on_message_callback=callback, auto_ack=False)
    print("DLQ monitor started...")
    ch.start_consuming()


# ═══════════════════════════════════════════════════════════
# SECTION 5: Priority Queue Demo
# ═══════════════════════════════════════════════════════════

def priority_demo():
    """Priority queue — urgent tasks pehle"""
    conn, ch = get_channel()

    ch.queue_declare(
        queue='priority_tasks',
        durable=True,
        arguments={'x-max-priority': 10}
    )

    tasks = [
        (1,  "Generate monthly report"),
        (3,  "Update user preferences"),
        (10, "URGENT: Security breach detected"),
        (2,  "Send newsletter"),
        (8,  "Process payment refund"),
        (5,  "Update product catalog"),
        (10, "URGENT: Server down alert"),
    ]

    print("📤 Sending tasks (mixed priorities):")
    for priority, task_name in tasks:
        ch.basic_publish(
            exchange='',
            routing_key='priority_tasks',
            body=json.dumps({'task': task_name}).encode(),
            properties=pika.BasicProperties(
                delivery_mode=pika.DeliveryMode.Persistent,
                priority=priority
            )
        )
        print(f"  [{priority:2d}] {task_name}")

    # Consume with small delay — priority sorting dekhne ke liye
    ch.basic_qos(prefetch_count=1)

    def callback(ch, method, properties, body):
        data = json.loads(body)
        priority = properties.priority or 0
        print(f"📥 [{priority:2d}] Processing: {data['task']}")
        time.sleep(0.3)
        ch.basic_ack(delivery_tag=method.delivery_tag)

    print("\n📥 Processing order (highest priority first):")
    ch.basic_consume(queue='priority_tasks', on_message_callback=callback, auto_ack=False)
    ch.start_consuming()

    conn.close()


# ═══════════════════════════════════════════════════════════
# MAIN — Demo Runner
# ═══════════════════════════════════════════════════════════

def run_demo(demo_choice: str):
    """Choose which demo to run"""

    if demo_choice == "direct":
        print("\n=== DIRECT EXCHANGE DEMO ===")
        setup_direct_exchange()
        direct_producer()
        # Consumer run karo — separate terminal mein:
        # direct_consumer('payment_queue')
        # direct_consumer('inventory_queue')
        # direct_consumer('email_queue')
        print("Run consumers in separate terminals!")

    elif demo_choice == "fanout":
        print("\n=== FANOUT EXCHANGE DEMO ===")
        setup_fanout_exchange()
        # Consumers thread mein run karo
        consumers = [
            threading.Thread(target=fanout_consumer, args=("EmailService", "email_service_queue")),
            threading.Thread(target=fanout_consumer, args=("SMSService", "sms_service_queue")),
            threading.Thread(target=fanout_consumer, args=("Analytics", "analytics_queue")),
        ]
        for c in consumers:
            c.daemon = True
            c.start()

        time.sleep(1)  # consumers ready hone do
        fanout_producer()
        time.sleep(2)  # messages process hone do

    elif demo_choice == "topic":
        print("\n=== TOPIC EXCHANGE DEMO ===")
        setup_topic_exchange()
        topic_producer()

    elif demo_choice == "dlx":
        print("\n=== DEAD LETTER EXCHANGE DEMO ===")
        setup_dlx_demo()
        # DLQ monitor thread mein run karo
        dlq_thread = threading.Thread(target=dlq_monitor)
        dlq_thread.daemon = True
        dlq_thread.start()
        # Main consumer thread mein run karo
        consumer_thread = threading.Thread(target=dlx_consumer)
        consumer_thread.daemon = True
        consumer_thread.start()
        time.sleep(1)
        dlx_producer()
        time.sleep(3)

    elif demo_choice == "priority":
        print("\n=== PRIORITY QUEUE DEMO ===")
        priority_demo()

    else:
        print("Available demos: direct, fanout, topic, dlx, priority")


if __name__ == "__main__":
    import sys
    demo = sys.argv[1] if len(sys.argv) > 1 else "fanout"
    run_demo(demo)

    # Usage:
    # python 01_exchanges_all_types.py direct
    # python 01_exchanges_all_types.py fanout
    # python 01_exchanges_all_types.py topic
    # python 01_exchanges_all_types.py dlx
    # python 01_exchanges_all_types.py priority
