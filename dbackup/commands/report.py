import logging
from typing import List

from ..helpers import StateTracker
from ..helpers import Publisher

from ..job import Job

import dbackup.resultcodes

class Report:

    def __init__(self, publisher : Publisher, stateTracker : StateTracker):
        self.publisher = publisher

        self.stateTracker = stateTracker

    def execute(self, jobs : List[ Job ]) -> int:
        """ Reports the current state of all jobs 
        
        Iterates over all jobs in the config and publishes
        the current state
        """

        # Only check jobs that have both source and dest

        result = dbackup.resultcodes.SUCCESS
        for job in jobs:
            logging.debug('Checking job %s', job)
            try:
                state, lastDate = self.stateTracker.checkJobAge(job.name)
                if not lastDate is None:
                    self.publisher.publishLastGood(job.name, lastDate)
                if state:
                    self.publisher.publishState(job.name, 'finished')
                    self.publisher.publish(f'backup/{job.name}/state', 'finished')
                else:
                    self.publisher.publishState(job.name, 'failed')
            except KeyError:
                logging.warning('No backup found for job %s', job)
                self.publisher.publishState(job.name, 'failed')
                result = dbackup.resultcodes.INVALID_JOB
        
        # Wait for publication before exiting
        self.publisher.waitForPublish()

        return result