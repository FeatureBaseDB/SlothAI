import config
import confluent_kafka
from confluent_kafka.admin import AdminClient, NewTopic

class Kafka:
    """
    A Singleton class for managing Kafka connections and topics.

    This class ensures that there is only one instance of Kafka throughout
    the application and provides methods to interact with Kafka producers.

    Attributes:
        addr (str): The Kafka broker address.
        task_topic (str): The name of the Kafka topic for task processing.
        admin_client (AdminClient): An AdminClient instance for managing Kafka topics.
        initialized (bool): A flag to track if the Kafka client has been initialized.

    Methods:
        getProducer(): Returns a Kafka Producer instance for producing messages.

    Usage:
        kafka_instance = Kafka()  # Create an instance of the Kafka class.
        producer = kafka_instance.getProducer()  # Get a Kafka Producer for sending messages.
    """

    def __new__(self):
        if not hasattr(self, 'instance'):
            self.instance = super(Kafka, self).__new__(self)
        return self.instance

    def __init__(self):
        if not hasattr(self, 'init'):
            print("DEBUG: initalizing kafka client and topics...") if config.debug else None
            self.addr = config.task_queue_addr if hasattr(config, "task_queue_addr") else "localhost:9092"
            self.task_topic = config.task_queue_name if hasattr(config, "task_queue_name") else "sloth"
            self.dead_letter_topic = config.dead_letter_queue_name if hasattr(config, "dead_letter_queue_name") else "sloth-dlq"
            self.admin_client = AdminClient({'bootstrap.servers': self.addr})
            Topics = [self.task_topic, self.dead_letter_topic]

            # create topics that don't exist
            __topic_list = self.admin_client.list_topics(timeout=10).topics
            __new_topics = []
            for topic in Topics:
                if topic not in __topic_list:
                    __new_topics.append(NewTopic(topic, num_partitions=1, replication_factor=1))

            if len(__new_topics):
                future = self.admin_client.create_topics(__new_topics)
                [v.result() for _, v in future.items()] # make sure they were created
            
            self.init = True

    def getProducer(self):
        return confluent_kafka.Producer({'bootstrap.servers': self.addr})
    
    def getConsumer(self):
        return confluent_kafka.Consumer({'bootstrap.servers': self.addr, 'group.id': 'sloth-consumers'})
