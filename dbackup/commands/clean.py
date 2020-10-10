from typing import List

from ..helpers import getDynamicHost
from ..location import Location
from ..helpers import ArgumentError
import shutil
import subprocess
import os
import logging
import re

from ..job import Job

import dbackup.resultcodes

class Clean:

    def __init__(self, simulate = True):
        self.simulate = simulate

    def CleanJob(self, job : Job):
        """ Cleans old backups from a job

        Arguments:
            job, str : The config section that describes the backup job to clean

        """

        assert isinstance(job, Job)
        job.dest.simulate = self.simulate
        assert job.dest.isRemote != job.dest.isLocal

        logging.debug('Destination location path is ' + job.dest.path)
        logging.debug('Destination is local:'+str(job.dest.isLocal))
        
        # List all files in dest folder
        backups = job.dest.getBackups(True)
        
        # Get config parameters
        logging.debug('Job %s is set to keep %d days and %d months', str(job), job.daysToKeep, job.monthsToKeep)
                    
        if backups is None:
            logging.warning('No backups found for job %s', job)
            return True
            
        # Convert folder names to dates
        allBackups = sorted(backups, reverse=True)
        logging.debug('Backups: ' + ', '.join(allBackups))
        goodBackups = list(filter(re.compile(r'^\d{4}-\d{2}-\d{2}$').match, allBackups))
        #badBackups  = list(filter(re.compile(r'^\d{4}-\d{2}-\d{2}.+$').match, allBackups))
        monthlyBackups = [ d for d in goodBackups if d[8:10] == '01'][0:job.monthsToKeep]
        dailyBackups = goodBackups[0:job.daysToKeep]
        logging.debug('Monthly backups: ' + ', '.join(monthlyBackups))
        logging.debug('Daily backups: ' + ', '.join(dailyBackups))
        
        # Figure out which backups to keep and which to remove
        backupsToKeep = set(dailyBackups).union(set(monthlyBackups))
        logging.debug('Keeping: ' + ', '.join(list(backupsToKeep)))
        backupsToRemove = set(allBackups) - backupsToKeep
        
        if backupsToRemove:
            logging.info("Removing outdated backups " + ', '.join(list(backupsToRemove)))
            job.dest.deleteChild(list(backupsToRemove))
                
            logging.info('Cleaned job %s', job)
        else:
            logging.info('No backups to remove for job %s', job)

            
    def execute(self, jobs : List[ Job ] ) -> int:
        """ Cleans a job, i.e. removes outdated backups
        Arguments
        ---------
            jobs is a list of jobs to clean
        """
        result = dbackup.resultcodes.SUCCESS
        for job in jobs:
            logging.info(f'Cleaning {job}')
            if not self.CleanJob(job):
                result = dbackup.resultcodes.CLEAN_FAILED
        return result
