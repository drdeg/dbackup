import configparser
import logging

from ..helpers import checkAge
from ..helpers import StateTracker

from typing import List

from ..job import Job

import dbackup.resultcodes

class CheckJob:

    def __init__(self, stateTracker : StateTracker):

        self._stateTracker = stateTracker

    def execute(self, jobs : List[ Job ] ) -> bool:
        """ Checks the age of job(s)

        Iterates over all jobs and checks if they are too old. Output
        is simply printed to stdout

        Returns True if all jobs are good. If any job is bad, False is returned.

        """

        assert jobs is not None

        goodJobs = []
        badJobs = []

        for job in jobs:
            
            if self._stateTracker.checkJobAge(job):
                goodJobs.append(job)
            else:
                badJobs.append(job)

        if badJobs:
            logging.warning('Bad jobs detected!' + ', '.join(map(lambda job : str(job),badJobs)))
            print('BAD: ' + ', '.join(map(lambda job : str(job),badJobs)))
            return dbackup.resultcodes.BAD_JOBS
        else:   # No bad jobs
            logging.info('All jobs are OK: ' + ", ".join(map(lambda job: str(job), goodJobs)))
            print('OK: ' + ', '.join(map(lambda job: str(job), goodJobs)))
            return dbackup.resultcodes.SUCCESS