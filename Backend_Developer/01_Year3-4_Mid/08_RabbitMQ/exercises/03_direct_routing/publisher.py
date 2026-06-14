import pika
import sys
import random

connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))

channel = connection.channel()

channel.exchange_declare(exchange = 'logs_exchange', exchange_type='direct')

severity = ["Error", "Warning", "Info", "Other"]
messages = ["EMsg", "WMsg", "IMsg", "OMsg"]

for i in range(10):
    randomNum = random.randint(0, len(severity)-1)
    print(randomNum)
    message = messages[randomNum]
    rk = severity[randomNum]
    channel.basic_publish(exchange='logs_exchange', routing_key=rk, body=message)
    print("[x] sent %r" %message)

channel.exchange_delete(exchange='logs_exchange', if_unused=False)

connection.close()





