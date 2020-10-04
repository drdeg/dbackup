import configparser
import logging

from dbackup.helpers import checkAge
from dbackup.helpers import StateTracker

class CheckJob:

    def __init__(self, parent):
        self.parent = parent
        self.config = parent.config
        self.args = parent.args

        self._stateTracker = StateTracker(parent.args.statefile)

    def execute(self, jobspec = None ) -> bool:
        """ Checks the age of job(s)

        Iterates over all jobs and checks if they are too old. Output
        is simply printed to stdout

        Returns True if all jobs are good. If any job is bad, False is returned.

        """

        jobspec = self.args.job

        assert jobspec is None or isinstance(jobspec, str)

        goodJobs = []
        badJobs = []
        if jobspec is None:
            # Iterate over all jobs in the config

            # Filter only jobs that have both dest and source
            jobs = list(filter(lambda job: 'dest' in self.config[job] and 'source' in self.config[job], self.config.sections()))

        else: 
            # Assume jobspec is a string
            jobs = [jobspec]

        for job in jobs:
            
            if self._stateTracker.checkJobAge(job):
                goodJobs.append(job)
            else:
                badJobs.append(job)

        if badJobs:
            logging.warning('Bad jobs detected: ' + str(badJobs))
            print('BAD: ' + ', '.join(badJobs))
            return False
        else:   # No bad jobs
            logging.info('All jobs are OK: ' + str(goodJobs))
            print('OK: ' + ', '.join(goodJobs))
            return True