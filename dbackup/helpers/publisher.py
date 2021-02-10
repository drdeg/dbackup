
from dpytool.IoT.hamqttclient import HAMqttClient
from datetime import datetime
import logging

class Publisher(HAMqttClient):
    """
    Publisher sends state and last good MQTT messages
    to the broker (if configured)

    Properties
    ----------
    simulate (bool) : Indicates if the publications are only simulated

    Methods
    -------
    publishState(job : str, state : str) : Publishes update on a state for a job
    publishLastGood(job : str, lastGood : str/datetime) : Publishes last good date

    """

    def __init__(self, simulate = False):
        """ Creates the publisher 

        
        Arguments:
        simulate (bool) : Should publish only be simulated
        
        """
        super().__init__(clientClass = 'dbackup', publishState = False)
        self.__simulate = simulate

    @property
    def simulate(self):
        return self.__simulate

    def publishState(self, job, state):
        topic = self.formatTopic(f'{str(job)}/state')
        logging.debug(f'Publishing state {topic}:{str(state).lower()}')
        if not self.simulate:
            self.publish(topic, str(state).lower())
        else:
            logging.debug('^SIMULATED^')

    def publishLastGood(self, job, lastGood):
        topic = self.formatTopic(f'{job}/lastgood')
        if isinstance(lastGood, datetime):
            dateStr = lastGood.strftime( "%Y-%m-%d")
        else:
            dateStr = str(lastGood).lower()
        logging.debug(f'Publishing last good {topic}:{dateStr}')
        if not self.simulate:
            self.publish(topic, dateStr)
        else:
            logging.debug('^SIMULATED^')
