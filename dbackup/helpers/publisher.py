
from dpytool.IoT.hamqttclient import HAMqttClient
from datetime import datetime

class Publisher(HAMqttClient):

    def __init__(self):
        super().__init__(clienClass = 'dbackup', publishState = False)

    def publishState(self, job, state):
        topic = self.formatTopic(f'{job}/state')
        self.publish(topic, str(state).lower())

    def publishLastGood(self, job, lastGood):
        topic = self.formatTopic(f'{job}/lastgood')
        if isinstance(lastGood, datetime):
            dateStr = lastGood.strftime( "%Y-%m-%d")
        else:
            dateStr = str(lastGood).lower()
        self.publish(topic, dateStr)
        
