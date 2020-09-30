
from dpytool.IoT.hamqttclient import HAMqttClient
from datetime import datetime
import logging

class Publisher(HAMqttClient):

    def __init__(self, simulate = False):
        super().__init__(clientClass = 'dbackup', publishState = False)
        self.__simulate = simulate

    @property
    def simulate(self):
        return self.__simulate

    def publishState(self, job, state):
        topic = self.formatTopic(f'{job}/state')
        logging.debug(f'Publishing state {topic}:{str(state).lower()}')
        if not self.simulate:
            self.publish(topic, str(state).lower())

    def publishLastGood(self, job, lastGood):
        topic = self.formatTopic(f'{job}/lastgood')
        if isinstance(lastGood, datetime):
            dateStr = lastGood.strftime( "%Y-%m-%d")
        else:
            dateStr = str(lastGood).lower()
        logging.debug(f'Publishing last good {topic}:{dateStr}')
        if not self.simulate:
            self.publish(topic, dateStr)
        
