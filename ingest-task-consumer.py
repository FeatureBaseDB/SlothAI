import json
from web.kafka import Kafka
import config
import requests
import sys

debug = config.debug if hasattr(config, 'debug') else False
topic = config.task_queue_name if hasattr(config, 'task_queue_name') else "sloth"
task_endpoint = config.task_endpoint if hasattr(config, 'task_endpoint') else "http://localhost:8080"
consumer = Kafka().getConsumer()
consumer.subscribe([topic])

# until sigkill
while True:
    # catch exception in processing tasks from the queue
    try:
        # kafka poll loop
        while True:
            msg = consumer.poll(timeout=1.0)
            if msg is None:
                # sys.stdout.write("polling for messages, none found") if debug else None
                continue
            if msg.error():
                raise Exception(f"ERROR: while processing task: key: {msg.key()}, value: {msg.value()}: {e}\n\n")
            else:
                m = msg.value().decode('utf-8')
                j = json.loads(m)
                sys.stdout.write(f"INFO: sending task to be processed: key: {msg.key()}, value: {msg.value()}\n\n") if debug else None
                resp = requests.post(f"{task_endpoint}/tasks/process/{config.cron_key}/{j['uid']}", data=m, timeout=10)
                if resp.status_code != 200:
                    raise Exception(f"ERROR: sending task to processor: {resp.text}")
                sys.stdout.write(f"INFO: task sent for processing: key: {msg.key()}, value: {msg.value()}\n\n") if debug else None
                
    except Exception as e:
        sys.stdout.write(e)
