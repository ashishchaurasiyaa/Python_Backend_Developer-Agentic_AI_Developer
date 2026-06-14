import pika

# Create a connection say CN
# Create a channel in CN, say CH
# Create the exchange (will not affect if exchange is already there)
# Create the temporary queue, if it does not exist already and associate it with the channel CH exclusively
# Bind the queue with the exchange
# Associate a call-back function with the message queue
# Start consuming the messages


connection = pika.BlockingConnection(pika.ConnectionParameters(host = 'localhost'))

channel = connection.channel()

channel.exchange_declare(exchange='br_exchange', exchange_type='fanout')

result = channel.queue_declare(queue='', exclusive=True)

queue_name = result.method.queue

print("Subscriber queue_name =", queue_name)

channel.queue_bind(exchange='br_exchange', queue=queue_name)

print('[*] waiting for the messages')

def callback(ch, method, properties, body):
    print('[x] %r' %body)

channel.basic_consume(queue=queue_name, on_message_callback=callback, auto_ack=True)

channel.start_consuming()

