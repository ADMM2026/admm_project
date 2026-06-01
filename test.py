from kafka import KafkaConsumer
import json

consumer = KafkaConsumer(
    'Tourism.Tourism.accommodations',
    bootstrap_servers=['localhost:9092'],
    auto_offset_reset='earliest',
    group_id=None,  # <-- nessun group, nessun offset committato
    consumer_timeout_ms=10000
)

count = 0
for message in consumer:
    count += 1
    print(f"Messaggio #{count} ricevuto da offset {message.offset}")
    if count >= 3:
        break

print(f"Totale: {count}")
consumer.close()