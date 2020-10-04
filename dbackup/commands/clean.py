from dbackup.helpers import getDynamicHost
from dbackup.helpers import Location
from dbackup.helpers import ArgumentError
import shutil
import subprocess
import os
import logging
import re

from dbackup import Job

class Clean:

    def __init__(self, config):
        self.config = config

    def CleanJob(self, job : Job):
        """ Cleans old backups from a job

        Arguments:
            job, str : The config section that describes the backup job to clean

        """

        location = job.dest
        # Determine dynamichost
        logging.debug('Destination location path is ' + location.path)
        
        # List all files in dest folder
        backups = location.getBackups(True)
        
        # Get config parameters
        daysToKeep = int(self.config[job].get('days', fallback=3))
        monthsToKeep = int(self.config[job].get('months', fallback=3))
        logging.debug('Job %s is set to keep %d days and %d months', job, daysToKeep, monthsToKeep)
                    
        if backups is None:
            logging.warning('No backups found for job %s', job)
            return True
            
        # Convert folder names to dates
        allBackups = sorted(backups, reverse=True)
        logging.debug('Backups: ' + ', '.join(allBackups))
        goodBackups = list(filter(re.compile(r'^\d{4}-\d{2}-\d{2}$').match, allBackups))
        #badBackups  = list(filter(re.compile(r'^\d{4}-\d{2}-\d{2}.+$').match, allBackups))
        monthlyBackups = [ d for d in goodBackups if d[8:10] == '01'][0:monthsToKeep]
        dailyBackups = goodBackups[0:daysToKeep]
        logging.debug('Monthly backups: ' + ', '.join(monthlyBackups))
        logging.debug('Daily backups: ' + ', '.join(dailyBackups))
        
        # Figure out which backups to keep and which to remove
        backupsToKeep = set(dailyBackups).union(set(monthlyBackups))
        logging.debug('Keeping: ' + ', '.join(list(backupsToKeep)))
        backupsToRemove = set(allBackups) - backupsToKeep
        
        if backupsToRemove:
            logging.info("Removing outdated backups " + ', '.join(list(backupsToRemove)))
            if location.isLocal:
                for d in backupsToRemove:
                    try:
                        logging.debug('Removing ' + os.path.join(self.config[job]['dest'], d))
                        shutil.rmtree(os.path.join(self.config[job]['dest'], d))
                    except PermissionError as e:
                        logging.error('Permission denied: %s', e.filename)
            elif location.isRemote:
                rmString = '"'+'" "'.join([location.path +'/'+ b for b in backupsToRemove])+'"'
                cmd = sshArgs + location.sshUserHostArgs() + ['rm -rf '+rmString]
                logging.debug('Remote command: '+ ' '.join(cmd))

                try:
                    subprocess.check_output(cmd, stderr=subprocess.PIPE)
                except subprocess.CalledProcessError as e:
                    logging.debug('ssh failed %d: %s' %(e.returncode, e.stderr.decode("utf-8").rstrip()))
                    logging.error('Clean of job %s failed', job)
                    return False
                
            logging.info('Cleaned job %s', job)
        else:
            logging.info('No backups to remove for job %s', job)

            
    def execute(self, jobspec = None):
        """ Cleans a job, i.e. removes outdated backups
        Arguments
        ---------
            jobspec is either a list of jobs or a single job or None to specify all jobs
        """
        for job in self.config.sections() if jobspec is None else [jobspec]:
            if job in self.config.sections():
                logging.info('Cleaning %s', job)
                self.CleanJob(job)
            else:
                raise ArgumentError(f'Job {job} is not found in the configuration')
