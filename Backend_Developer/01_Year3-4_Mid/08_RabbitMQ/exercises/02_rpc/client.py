"""
RabbitMQ Exercise 02 — RPC Client (Request/Reply over AMQP)
==============================================================
OBJECTIVE: ek "remote procedure call" banao — client ek request bhejta
           hai aur uska SAHI response wapas paata hai (na ki kisi aur
           concurrent in-flight call ka response).

TASK:
  1. TODO 1: request bhejte time reply_to + correlation_id set karo
  2. TODO 2: response aane par verify karo ki yeh TUMHARA hi
     correlation_id hai (RPC client ek hi reply-queue reuse karta hai
     saare calls ke liye — match na kiya to galat jawab mil sakta hai)
  3. Run: pehle server.py chalao (alag terminal), phir python client.py
  4. Ya seedha: python verify.py

Prereq: docker compose up -d   |   pip install pika
"""

import pika
import uuid


def is_my_response(expected_correlation_id, props):
    """Yeh response TUMHARE call() ka hai ya kisi aur concurrent call ka?

    RPC client ek hi reply-queue reuse karta hai SAARE calls ke liye —
    agar do call() overlap ho rahe hon, dono ke responses isi
    on_response() callback se guzarte hain. correlation_id match karke
    hi pata chalta hai kaunsa response kiske call ka hai.
    """
    # ─────────────────────────────────────────────────────
    # TODO 2: sahi comparison likho — True/False return karo.
    #   Hint: expected_correlation_id == props.correlation_id
    return None
    # ─────────────────────────────────────────────────────


class FactRPCClient:
    def __init__(self):
        self.connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
        self.channel = self.connection.channel()

        self.queue_name = 'rpc_client_queue'
        self.server_queue_name = 'rpc_server_queue'
        self.channel.queue_declare(queue=self.queue_name, exclusive=True)

        self.channel.basic_consume(queue=self.queue_name,
                                    on_message_callback=self.on_response,
                                    auto_ack=True)

    def on_response(self, ch, method, props, body):
        match = is_my_response(self.correlation_id, props)
        if match is None:
            print("❌ TODO 2 abhi bharna hai — is_my_response() complete karo")
            raise SystemExit(1)
        if match:
            self.response = body

    def call(self, n):
        self.response = None
        self.correlation_id = str(uuid.uuid4())

        # ─────────────────────────────────────────────────────
        # TODO 1: request properties set karo.
        #   REPLY_TO       = server ko batana hai kis queue pe jawab
        #                     bhejna hai. Hint: self.queue_name
        #   CORRELATION_ID = taaki apna response pehchaan sako.
        #                     Hint: self.correlation_id
        REPLY_TO = None
        CORRELATION_ID = None
        # ─────────────────────────────────────────────────────

        if REPLY_TO is None or CORRELATION_ID is None:
            print("❌ TODO 1 abhi bharna hai — REPLY_TO aur CORRELATION_ID set karo")
            raise SystemExit(1)

        self.channel.basic_publish(
            exchange='',
            routing_key=self.server_queue_name,
            properties=pika.BasicProperties(
                reply_to=REPLY_TO,
                correlation_id=CORRELATION_ID,
            ),
            body=str(n),
        )
        while self.response is None:
            self.connection.process_data_events()
        return int(self.response)


if __name__ == "__main__":
    fact_rpc = FactRPCClient()
    n = 5
    print("Requesting Fact(", n, ")")
    response = fact_rpc.call(n)
    print("Got the response ", response)
