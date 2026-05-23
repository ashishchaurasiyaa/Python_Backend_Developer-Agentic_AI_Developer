# Operator Program (Subscriber)
# Fanout exchange se connected
# Temporary + exclusive queue
# Message print karta hai

import pika
connection = pika.BlockingConnection(pika.ConnectionParameters(host='localhost'))
channel = connection.channel()

#Fanout exchange
channel.exchange_declare(exchange='alert_broadcast', exchange_type='fanout')

# Temporary Exclusive Queue
result = channel.queue_declare(queue='', exclusive=True)
queue_name = result.method.queue

#Bind queue with exchange
channel.queue_bind(exchange='alert_broadcast', queue=queue_name)

print("[Operator] Waiting for messages...]")

def callback(ch, method, properties, body):
    print(f"[Operator] Received alert: {body.decode()}")
channel.basic_consume(queue=queue_name, on_message_callback=callback, auto_ack=True)

channel.start_consuming()