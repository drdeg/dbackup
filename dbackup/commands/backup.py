import configparser
import logging
import os
import shutil
import subprocess

from typing import List

import dbackup.helpers
import dbackup.incomplete
from ..location import Location
from ..helpers import getDynamicHost
from ..helpers import SshError, ArgumentError
from ..helpers import StateTracker

import dbackup.resultcodes

import dbackup.job

class Backup:

    rsyncOpts = ['--delete', '-avhF', '--numeric-ids']

    def __init__(self, publisher, stateTracker = None, simulate = False):
        self.today = dbackup.helpers.today

        self.simulate = simulate

        self.publisher = publisher
        if publisher:
            # MQTT publishing enabled
            logging.debug('MQTT status reporting for backup job is enabled')
            self.publishState = self._publishState
            self.publishLastGood = self._publishLastGood
        else:
            # MQTT publishing disabled
            logging.debug('MQTT status reporting for backup job is disabled')
            self.publishState = lambda a, b : None
            self.publishLastGood = lambda a, b : None

        self._stateTracker = stateTracker

    def _publishState(self, job : dbackup.Job, state : str):
        self.publisher.publishState(job, state)

    def _publishLastGood(self, job : dbackup.Job, date):
        self.publisher.publishLastGood(job, self.today)

    def getLinkTargetOpts(self, location : Location):
        """ Get rsync options for link target

        Scans the destination for suitable link-targets

        Agruments:
            location (str) : The destination location of backups

        Returns a list of RSYNC aruments needed to use the detected link target
        """
        # Get list of backups exculding incomplete
        try:
            backups = location.getBackups(False)
        except SshError:
            logging.warning('Could not determine existing backups at %s', location.path)
            return []

        if backups is None or not backups or len(backups) == 0:
            logging.warning('No backups found at %s', location.path)
            return []
        
        # There is at least one backup
        backupsSorted = sorted(backups, reverse=True)
        
        linkTargetOpts = ['--link-dest='+location.path+'/'+backupsSorted[0]]
        logging.debug("Using link target opts " + str(linkTargetOpts))

        return linkTargetOpts

    def finalizeBackup(self, location : Location, name=None):
        """ Finalize backup removes incomplete suffix from dest 
        
        """

        if name is None:
            name = self.today

        toName = name
        fromName = name + dbackup.incomplete.suffix

        # May raise SshError
        location.renameChild(fromName, toName)

    def invokeRSync(self, rsync):
        """ Make the rsync call """

        result = False
        if self.simulate:
            logging.info("Simulating rsync!")
            result = True
        else:
            try:
                proc = subprocess.Popen(rsync, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
                
                # Wait for the rsync process to exit
                while True:
                    nextLine = proc.stdout.readline().decode("utf-8")
                    if not nextLine:
                        break
                    logging.debug("rsync: "+nextLine.rstrip())
                
                # Wait until the process really finished
                exitcode = proc.wait()
                
                if exitcode == 0:
                    logging.info("rsync finished successfully")
                    result = True
                else:
                    logging.error("Rsync failed")
            except:
                logging.error("Something went wrong with rsync")
        return result

    def execute(self, job : dbackup.Job):
        """
        Arguments:
            job (Job) : The job to backup

        Returns:
        """

        assert isinstance(job, dbackup.Job)

        assert isinstance(job.source, dbackup.location.Location)
        assert isinstance(job.dest, dbackup.location.Location)

        assert self.simulate == job.source.simulate
        assert self.simulate == job.dest.simulate

        logging.info('Starting backup job \"%s\"', job)
        logging.debug('Source is %s', job.source.path)
        logging.debug('Destination is %s', job.dest.path)
        self.publishState(job, 'running')

        # Execute any pre-backup tasks
        # This must be done before source or dest is validated, as the pre-jobs may create them!
        if job.execBefore is not None:
            logging.info("Executing " + job.execBefore)
            os.system(job.execBefore)

        # Verify connection to source and destination
        try:
            if job.source.validate():
                logging.debug('Source location %s is validated', str(job.source))
            else:
                logging.error('Invalid source location %s', str(job.source))
                self.publishState(job, 'failed')
                return dbackup.resultcodes.INVALID_LOCATION

            if job.dest.validate():
                logging.debug('Destination location %s is validated', str(job.dest))
            else:
                logging.debug('Destination location %s is not found. Tryin to create it.', str(job.dest))
                # Try to create target directory if validation failed
                if self.simulate:
                    logging.info(f'Simulated creation of {str(job.dest.path)}')
                else:
                    if job.dest.create():
                        logging.info('Created destination directory %s.', str(job.dest))
                    else:
                        logging.error('Failed to create destination path %s', str(job.dest))
                        self.publishState(job, 'failed')
                        return dbackup.resultcodes.FAILED_TO_CREATE_DESTINATION
                    
        except SshError as e:
            logging.error(e.message)
            return dbackup.resultcodes.SSH_ERROR
        
        # Determine last backup for LinkTarget
        linkTargetOpts = self.getLinkTargetOpts(job.dest)

        # Assemble rsync arguments
        # ssh args are assembled in job class.
        # Remove 'ssh command' from argument list
        rsyncSshArgsList = job.sshArgs[1:] if job.sshArgs[0] == 'ssh' else job.sshArgs

        assert job.cert is not None, "A certificate is required for remote locations"
        if job.source.isRemote:
            rsyncSshArgsList += ['-l', job.source.user]
        elif job.dest.isRemote:
            rsyncSshArgsList += ['-l', job.dest.user]

        # The ssh arguments are specified as a string where each argument is separated with a space
        rsyncSshArgs = ["--rsh=ssh "+' '.join(rsyncSshArgsList)+""]

        # Do the work
        rsync = ['rsync'] + self.rsyncOpts + job.rsyncArgs + \
            linkTargetOpts + rsyncSshArgs + \
                [job.source.rsyncPath(''), job.dest.rsyncPath(self.today + dbackup.incomplete.suffix)]
        
        logging.debug('Remote command: "'+'" "'.join(rsync)+'"')
        backupOk = self.invokeRSync(rsync)
        if backupOk:
            try:
                self.finalizeBackup(job.dest)
                logging.debug('Finalized backup %s@%s', job, self.today)
            except Exception as e:
                # Ignore errors
                logging.warning(f'Failed to finalize backup {str(job)}')
                print(e)

        # Execute any post-tasks
        # Always, even if rsync failed
        if job.execAfter is not None:
            logging.info("Executing "+job.execAfter)
            os.system(job.execAfter)

        if backupOk :
            # Backup job completed successfully
            self.publishState(job, 'finished')
            self.publishLastGood(job, self.today)
            
            logging.debug('Updating local state tracker')
            if self._stateTracker is not None:
                self._stateTracker.update(job, self.today)

            logging.info('Backup job \"%s\" finished successfully', job)

            return dbackup.resultcodes.SUCCESS
        else:
            # Backup failed
            logging.info('Backup job \"%s\" failed', job)
            self.publishState(job, 'failed')
            return dbackup.resultcodes.RSYNC_FAILED
