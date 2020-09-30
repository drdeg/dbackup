#!/usr/bin/python3
#
# ALGORITHM DESCRIPTION
#
#   
# CONFIG FILE
#
# [common]
# remote_host = lovlund.dyndns.org
# remote_root = /srv/user1/mirror
# remote_user = root
# remote_url = ${remote_user}@${remote_host}:${remote_root}
# local_dest = /srv/b1/fs/mirror
#
# [DEFAULT]
# ; Special section that can be overridden in each section
# cert = /etc/dtools/mirror/id_rsa
#
# [david]
# source = /home/david
# dest = ${common:remote_url}/home/newdavid
#
# [karin]
# source = /srv/b1/fs/home/karin
# dest = ${common:remote_url}/home/karin
#
# [KoD]
# source = /srv/b1/fs/KoD
# dest = ${common:remote_url}/groups/KoD
#
# [der]
# source = ${common:remote_user}@${common:remote_host}:/home/mirror-daemon
# dest = ${common:local_dest}/home/mirror-daemon
#
# [software]
# source = /srv/b1/fs/share/Software
# dest = ${common:remote_url}/share/Software
#
# [MyckleBilder]
# dynamichost = http://www.varukulla.se/reportip.php?query=myckle
# source = root@dynamichost:/volume1/photo
# dest = ${common:local_dest}/myckle/photo
# rsyncarg = -z
#
# MQTT messages
# backup/[job]/state
# backup/[job]/lastgood
#
# DONE
#
# - Parse argument
# - Parse config file
# - Support local -> remote backups
# - Support remote -> local backups
# - Handle logging to files 
# - Support .rsync-filter files in source
# - BUG: Check permissions when running as root (Causes havoc with root)
# - Global log file
# - Support cleaning of old backups locally
# - Rewrite backup to handle both ways in same method
# - Backups should be made to a temp folder (date.incomplete) and renamed after success
# - Clean should not care about incomplete backups
# - Clean should support remote destinations
# - Clean supports --job option to clean a single job
# - Backup should parse directory instead of reading statefile and igonre incomplete backups
# - Backup should support --job switch to only run single job
# - BUG: FinalizeBackup doesn't overwrite existing directory
# - Add --clean option to automatically clean after backup job is finished
# - Clean should remove incomplete backups
# - BUG: dynamichost failed
# - BUG: when remote host IP changed, the host key was unknown and ssh failed.
# - Add support to add per backup job rsync options, such as -c or -Z for compression
# - BUG: Failed to create remote directory for new backups
# - BUG: Crashed when no previous backups were found on remote
# - Add support to verify that the source and destinations exist
#
# TODO
#
# - Lock file
#

import time
import subprocess
import os
import sys
import re
import configparser
import argparse
import urllib.request
import logging
import ipaddress
import datetime
import shutil
import collections

import fasteners

from datetime import datetime
from os.path import expanduser

from helpers.errors import *
from helpers import Location
from helpers import getDynamicHost
from helpers import checkAge
from helpers import Publisher

defaultStateFileName = '.mirror_state'
incompleteSuffix = '.incomplete'

# Arguments used for all ssh requests


class DBackup:
    """ The big DBackup application """

    defaultLocalStateFilename = '/var/local/backup.state'

    sshOpts = ['-o', 'PubkeyAuthentication=yes', '-o', 'PreferredAuthentications=publickey']

    def __init__(self):
        # Create a map of command handlers
        self.__commands = {
            'clean': self.commandClean,
            'check': self.commandCheck,
            'report': self.commandReport,
            'backup': self.commandBackup,
            }
        self.__today = time.strftime( "%Y-%m-%d")

        self.publisher = None

    @property
    def today(self):
        return self.__today

    def initPublisher(self):
        self.publisher = Publisher(simulate=self.args.simulate)
        logging.debug(f'Connecting to {self.args.mqtt}:{self.args.port}')
        self.publisher.connect(self.args.mqtt, self.args.port)

    def checkJobAge(self, jobspec = None ):
        """ Checks the age of job(s)

        Iterates over all jobs and checks if they are too old. Output
        is simply printed to stdout

        """
        localState = configparser.ConfigParser()
        logging.debug(f'Reading states from {self.localStateFileName}')
        localState.read(self.localStateFileName)

        goodJobs = []
        badJobs = []
        if jobspec is None:
            # Iterate over all jobs in the config
            for job in self.config.sections():
                if 'dest' in self.config[job] and 'source' in self.config[job]:
                    logging.debug('Checking job %s', job)
                    try:
                        state, _ = checkAge(localState['LastGood'][job])
                            
                        if state:
                            
                            goodJobs.append(job)
                        else:
                            badJobs.append(job)
                    except KeyError:
                        logging.warning('No backup found for job %s', job)
                        badJobs.append(job)
        else:
            try:
                logging.debug('Checking job %s', jobspec)
                state, _ = checkAge(localState['LastGood'][jobspec])
                if state:
                    goodJobs.append(jobspec)
                else:
                    badJobs.append(jobspec)
            except:
                badJobs.append(jobspec)
                
        if badJobs:
            logging.warning('Bad jobs detected: ' + str(badJobs))
            print('BAD: ' + ', '.join(badJobs))
            return False
        else:   # No bad jobs
            logging.info('All jobs are OK: ' + str(goodJobs))
            print('OK: ' + ', '.join(goodJobs))
            return True

    def reportJobStatus(self):
        """ Reports the current state of all jobs 
        
        Iterates over all jobs in the config and publishes
        the current state

        """
        localState = configparser.ConfigParser()
        localState.read(self.localStateFileName)

        if not self.args.mqtt:
            logging.warning('Pointless with report if mqtt broker is not specified')
        
        # Connect to MQTT and other publication receivers
        self.initPublisher()

        jobList = self.config.sections() if self.args.job is None else [self.args.job]

        for job in jobList:
            if 'dest' in self.config[job] and 'source' in self.config[job]:
                logging.debug('Checking job %s', job)
                try:
                    state, lastDate = checkAge(localState['LastGood'][job])
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

    def getLinkTargetOpts(self, location, sshArgs):
        """ Get rsync options for link target

        Scans the destination for suitable link-targets

        Agruments:
            location (str) : The destination location of backups
            sshArgs (list of str) : SSH arguments

        Returns a list of RSYNC aruments needed to use the detected link target
        """
        # Get list of backups exculding incomplete
        try:
            backups = self.getBackups(location, False)
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

    def invokeRSync(self, rsync):
        result = False
        if self.args.simulate:
            logging.info("Simulating rsync!")
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

    def finalizeBackup(self, location, sshArgs, name=None):
        """ Finalize backup removes incomplete suffix from dest 
        
        """

        if name is None:
            name = self.today

        if location.isLocal:
            toName = os.path.join(location.path, name)
            fromName = toName+incompleteSuffix
            logging.debug('Moving %s to %s', fromName, toName)
            if os.path.exists(toName):
                # Remove old instance if it already exists
                logging.debug('Replacing backup %s', toName)
                shutil.rmtree(toName)
            os.rename(fromName, toName)
        elif location.isRemote:
            # Create the state file
            toName =  location.path+'/'+name
            fromName = toName+incompleteSuffix
            cmd = sshArgs + location.sshUserHostArgs() + ['rm -rf "'+toName+'";mv "'+fromName+'" "'+toName+'"']
            logging.debug('Remote command: '+ ' '.join(cmd))
            try:
                output = subprocess.check_output(cmd, stderr=subprocess.PIPE)
                logging.debug('ssh output: ' + output.decode("utf-8").rstrip())

            except subprocess.CalledProcessError as e:
                logging.debug('ssh failed %d: %s' %(e.returncode, e.stderr.decode("utf-8").rstrip()))
                logging.error('Could not finalize backup')
                raise SshError('ssh failed %d: %s' %(e.returncode, e.stderr.decode("utf-8").rstrip()))
        else:
            logging.error('FinalizeBackup: Unexpected location type %s'%location.type)
            raise ArgumentError('Unexpected location type %s'%str(location.type))

    def getSshArgs(self, job):
        """ Compiles the argument list for ssh 
        
        Appends ssh key argument and any options defined in self.sshOpts
        Arguments:
          job (str) : ID of the particular job
        """
        cert = self.config[job].get('cert', None)
        sshArgs = ['ssh']
        if cert is not None:
            sshArgs += ['-i', cert]
            
        return sshArgs + self.sshOpts

    def backup(self):
        
        rsyncOpts = ['--delete', '-avhF', '--numeric-ids']

        self.initPublisher()

        for job in self.config.sections() if self.args.job is None else self.args.job.split(','):
            source = None
            dest = None

            if 'source' in self.config[job]:
                # TODO: Check if source has a valid format
                source = self.config[job]['source']
                
            if 'dest' in self.config[job]:
                dest = self.config[job]['dest']
                logging.debug('configparser reported that job ' +job + ' has a dest: ' + dest)
                # TODO: Check if dest is a valid format
            else:
                if job != 'common':
                    logging.error('No destination defined for job %s', job)
            
            if dest is not None and source is not None:
                logging.info('Starting backup job \"%s\"', job)
                logging.debug('Source is %s', source)
                logging.debug('Destination is %s', dest)        # Check that certificat exists
                self.publisher.publishState(job, 'running')

                # BUG: If cert is not defined, sshArgs will be crap
                cert = self.config[job].get('cert', None)
                if cert is None or not os.path.isfile(cert):
                    logging.error('Missing SSH certificate')
                    self.publisher.publishState(job, 'failed')
                    continue
                #sshArgs = ['ssh','-i',cert] + self.sshOpts
                sshArgs = self.getSshArgs(job)
                
                # Determine source and dest locations
                dynamichost = getDynamicHost(self.config[job])
                sourceLoc = Location(source, dynamichost, sshArgs=sshArgs)
                destLoc = Location(dest, dynamichost, sshArgs=sshArgs)
                
                # Verify connection to source and destination
                if sourceLoc.validateConnection():
                    logging.debug('Source location %s is validated', source)
                else:
                    logging.error('Invalid source location %s', source)
                    self.publisher.publishState(job, 'failed')
                    continue
                if destLoc.validateConnection():
                    logging.debug('Destination location %s is validated', dest)
                else:
                    logging.error('Destination location %s is not found. Tryin to create it.', dest)
                    # Try to create target directory if validation failed
                    if self.args.simulate:
                        if not destLoc.create():
                            logging.error('Failed to create destination path %s', destLoc)
                            self.publisher.publishState(job, 'failed')
                            continue
                    else:
                        logging.info(f'Simulated creation of {dest}')
                
                # Determine last backup for LinkTarget
                linkTargetOpts = self.getLinkTargetOpts(destLoc, sshArgs)

                # Assemble rsync arguments
                # TODO: Refactor this!!
                rsyncSshArgs = []
                if sourceLoc.isRemote or destLoc.isRemote:
                    cert = self.config[job].get('cert', None)
                    assert cert is not None, "A certificate is required for remote locations"
                    rsyncSshArgsList = ['-i',cert] + self.sshOpts
                    if sourceLoc.isRemote:
                        rsyncSshArgsList += ['-l', sourceLoc.user]
                    elif destLoc.isRemote:
                        rsyncSshArgsList += ['-l', destLoc.user]

                    # The ssh arguments are specified as a string where each argument is separated with a space
                    rsyncSshArgs = ["--rsh=ssh "+' '.join(rsyncSshArgsList)+""]


                # Execute any pre-backup tasks
                if self.config.has_option(job, 'exec before'):
                    logging.info("Executing "+self.config[job]['exec before'])
                    os.system(self.config[job]['exec before'])

                # Extra rsync arguments
                rsyncExtraArgs = [] if not 'rsyncarg' in self.config[job] else self.config[job]['rsyncarg'].split(' ')
                
                # Do the work
                rsync = ['rsync'] + rsyncOpts + rsyncExtraArgs + linkTargetOpts + rsyncSshArgs + [sourceLoc.rsyncPath(''), destLoc.rsyncPath(self.today+incompleteSuffix)]
                
                logging.debug('Remote command: '+'_'.join(rsync))
                backupOk = self.invokeRSync(rsync)
                if not backupOk:
                    self.publisher.publishState(job, 'failed')

                # Execute any post-tasks
                # Always, even if rsync failed
                if self.config.has_option(job, 'exec after'):
                    logging.info("Executing "+self.config[job]['exec after'])
                    os.system(self.config[job]['exec after'])

                # Create state file
                if self.args.simulate :
                    self.publisher.publishState(job, 'finished')
                    self.publisher.publishLastGood(job, self.today)
                elif backupOk :
                    try:
                        self.finalizeBackup(destLoc, sshArgs)
                        logging.debug('Finalized backup %s@%s', job, self.today)
                    except:
                        # Ignore errors
                        pass

                    # Backup job completed successfully
                    logging.info('Backup job \"%s\" finished successfully', job)
                    self.publisher.publishState(job, 'finished')
                    
                    if self.args.clean:
                        logging.debug('Clean after backup')
                        self.Clean(job)
                    
                    logging.debug('Updating local state tracker')
                    self.updateStateTracker(job, self.today)
    
    def updateStateTracker(self, job, lastGood = None):
        """ Updates the local state of a job and publishes it 
        
        Arguments:
            job (str) : Job identifier
            lastGood (str) : Date string of last good backup date or None
                to specify self.today
        """
        localState = configparser.ConfigParser()
        # Read current state from file
        localState.read(self.localStateFileName)

        # Init the state if it is empty
        if not 'LastGood' in localState:
            localState['LastGood'] = {}
        
        if lastGood is None:
            lastGood = self.today

        # Set last good date for the specified job
        localState['LastGood'][job] = lastGood

        # Save the statefile
        with open(self.localStateFileName, 'w') as stateFile:
            localState.write(stateFile)

        # Publish new state
        if self.publisher is not None:
            self.publisher.publishLastGood(job, lastGood)

    def getBackups(self, location, includeAll = False):
        """ Get alist of backups in a location
        
        Normally, incomplete backups are excluded from the list
        unless includeAll is set to true

        Returns a list of backups or Non if no backups are found. 
        If an error occured, like ssh failure, False is returned
        """

        # List all files in dest folder
        folderList = location.listDirs()

        if folderList is not None:
            # Filter out backup names
            if includeAll:
                dirNameRegex = re.compile(r'^\d{4}-\d{2}-\d{2}('+incompleteSuffix+'|)$')
            else:
                dirNameRegex = re.compile(r'^\d{4}-\d{2}-\d{2}$')
            return list(filter(dirNameRegex.match, folderList))
        else:
            return None

    def CleanJob(self, job):
        """ Cleans old backups from a job

        Arguments:
            job, str : The config section that describes the backup job to clean

        """

        # Determine dynamichost
        dynamichost = getDynamicHost(self.config[job])
        location = Location(self.config[job]['dest'], dynamichost, sshArgs=self.getSshArgs(job))
        logging.debug('Destination location path is ' + location.path)
        
        # Define variables for correct scoping
        sshArgs = self.getSshArgs(job) if location.isRemote else []
        
        """
        if location.isRemote:
            # Init SSH settings
            cert = self.config[job].get('cert', None)
            if cert is None or not os.path.isfile(cert):
                logging.error('Missing SSH certificate')
                return False
            sshArgs = ['ssh','-i',cert] + self.sshOpts
        """
            
        # List all files in dest folder
        backups = self.getBackups(location, True)
        
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
            
    def Clean(self, jobspec):
        """ Cleans a job, i.e. removes outdated backups
        Arguments
        ---------
            jobspec is either a list of jobs or a single job
        """
        for job in self.config.sections() if jobspec is None else [jobspec]:
            if job in self.config.sections():
                logging.info('Cleaning %s', job)
                self.CleanJob(job)
            else:
                raise ArgumentError(f'Job {job} is not found in the configuration')

    def parseArguments(self):
        parser = argparse.ArgumentParser(description='Backup tool based on RSYNC')
        parser.add_argument('command', help='What to do',choices=['backup','check','clean','report'],default='backup',nargs='?')
        parser.add_argument('-c', '--configfile', help='Full path of config file', default='/etc/dtools/backup.ini')
        parser.add_argument('--logfile', help='Full path of log file', default=None)
        parser.add_argument('--log', help='Log level (DEBUG,INFO,WARNING,ERROR,CRITICAL)',default='INFO')
        parser.add_argument('-j', '--job', help='Specify which jobs to run, e.g. kalle,pelle,olle', default=None)
        parser.add_argument('-s', '--statefile', help='Full path of local state file', default=self.defaultLocalStateFilename)
        parser.add_argument('--clean', help='Clean after successfull backup', action='store_true')
        parser.add_argument('--mqtt', help='Publish state to MQTT broker with address', default='')
        parser.add_argument('-p', '--port', help='Port number of MQTT broker', default=1883)
        parser.add_argument('--simulate', help='Don''t do the actual copy and update states', action='store_true')

        self.args = parser.parse_args()
        self.parser = parser

    def initLogging(self):
        if self.args.logfile is None:
            logging.basicConfig(format='%(asctime)s:%(levelname)s:%(message)s', level=getattr(logging, self.args.log.upper()))
        else:
            logging.basicConfig(format='%(asctime)s:%(levelname)s:%(message)s', filename=self.args.logfile, level=getattr(logging, self.args.log.upper()))


    def parseConfiguration(self):
        self.config = configparser.ConfigParser(interpolation=configparser.ExtendedInterpolation())
        self.config.read(self.args.configfile)

    def commandClean(self):
        logging.debug('Clean requested')
        if self.Clean(self.args.job):
            return 0
        else:
            return 1

    def commandCheck(self):
        if self.args.job is None:
            logging.debug('Checkall requested')
            if self.checkJobAge():
                return 0
            else:
                return 1
        else:
            logging.debug('State check of %s requested', self.args.job)
            if self.checkJobAge( self.args.job):
                return 0
            else:
                return 1

    def commandReport(self):
        logging.debug('Report requested')
        return self.reportJobStatus()
    
    def commandBackup(self):
        logging.debug('Backup requested')
        # Create lock file for backups
        with fasteners.InterProcessLock("/tmp/backup.lock"):
            return self.backup()

    def executeCommand(self, command):
        if command is None:
            return self.commandBackup()
        else:
            return self.__commands[command]()

    def run(self):

        # Parse arguments
        self.parseArguments()

        # Init logging
        self.initLogging()

        # Parse the configuration file
        logging.debug('Using config file %s', self.args.configfile)
        self.parseConfiguration()

        # Init the state file
        self.localStateFileName = self.args.statefile

        # Execute the command and then exit
        try:
            sys.exit(self.executeCommand(self.args.command))
        except ArgumentError as e:
            logging.critical(e.message)
        
        sys.exit(9)



if __name__ == '__main__':
    app = DBackup()
    app.run()
