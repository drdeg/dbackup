import logging

from dbackup.helpers import StateTracker
from dbackup.helpers import Publisher

class Report:

    def __init__(self, parent, publisher):
        self.parent = parent
        self.args = parent.args
        self.config = parent.config

        self.publisher = publisher

        self._stateTracker = StateTracker(parent.args.statefile)

    def execute(self):
        """ Reports the current state of all jobs 
        
        Iterates over all jobs in the config and publishes
        the current state
        """

        if not self.args.mqtt:
            logging.warning('Pointless with report if mqtt broker is not specified')
        
        # Connect to MQTT and other publication receivers

        jobList = self.config.sections() if self.args.job is None else [self.args.job]
        # Only check jobs that have both source and dest
        jobList = list(filter(lambda job: 'dest' in self.config[job] and 'source' in self.config[job]), jobList)

        for job in jobList:
            logging.debug('Checking job %s', job)
            try:
                state, lastDate = self._stateTracker.checkJobAge(job)
                if not lastDate is None:
                    self.publisher.publishLastGood(job, lastDate)
                if state:
                    self.publisher.publishState(job, 'finished')
                    self.publisher.publish('backup/{}/state'.format(job), 'finished')
                else:
                    self.publisher.publishState(job, 'failed')
            except KeyError:
                logging.warning('No backup found for job %s', job)
                self.publisher.publishState(job, 'failed')
        
        # Wait for publication before exiting
        self.publisher.waitForPublish()