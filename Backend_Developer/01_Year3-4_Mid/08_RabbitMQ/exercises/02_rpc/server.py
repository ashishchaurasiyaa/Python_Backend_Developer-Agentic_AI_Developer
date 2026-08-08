"""
RabbitMQ Exercise 02 — RPC Server (Fact-orial worker)
========================================================
TASK:
  1. TODO 1: client ne request ke saath jo reply_to + correlation_id
     bheja tha, usse AMQP message properties se nikaalo
  2. Run: python server.py   (client.py ke TODOs bharne ke baad)

Prereq: docker compose up -d   |   pip install pika
"""

import pika


def fact(n):
    if n <= 1:
        return 1
    return n * fact(n - 1)


def on_request(ch, method, props, body):
    # ─────────────────────────────────────────────────────
    # TODO 1: client ne request ke saath do cheezein bheji thi
    #   (client.py ke TODO 1 me):
    #     - kis queue pe reply chahiye     -> props.___
    #     - konsa correlation_id wapas bhejna hai -> props.___
    reply_queue_name = None
    corr_id = None
    # ─────────────────────────────────────────────────────

    if reply_queue_name is None or corr_id is None:
        print("❌ TODO 1 abhi bharna hai — props.reply_to / props.correlation_id nikaalo")
        raise SystemExit(1)

    n = int(body)
    print("called fact(", n, ")")
    response = fact(n)

    ch.basic_publish(exchange='', routing_key=reply_queue_name,
                      properties=pika.BasicProperties(correlation_id=corr_id),
                      body=str(response))
    ch.basic_ack(delivery_tag=method.delivery_tag)


if __name__ == "__main__":
    connection = pika.BlockingConnection(pika.ConnectionParameters(host='localhost'))
    channel = connection.channel()

    queue_name = "rpc_server_queue"
    channel.queue_declare(queue=queue_name, durable=True)

    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(queue=queue_name, on_message_callback=on_request)

    print("Awaiting RPC requests")
    channel.start_consuming()
