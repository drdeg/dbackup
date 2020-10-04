import configparser
import logging
import os
import shutil
import subprocess

from dbackup.helpers import Location
from dbackup.helpers import getDynamicHost
from dbackup.helpers import SshError, ArgumentError
from dbackup.helpers import StateTracker

class Backup:

    sshOpts = ['-o', 'PubkeyAuthentication=yes', '-o', 'PreferredAuthentications=publickey']
    rsyncOpts = ['--delete', '-avhF', '--numeric-ids']

    incompleteSuffix = '.incomplete'

    def __init__(self, parent, publisher):
        self.parent = parent
        self.config = parent.config
        self.args = parent.args
        self.today = parent.today

        self.publisher = publisher

        # Create a state tracker
        if self.args.statefile is None:
            self._stateTracker = None
        else:
            self._stateTracker = StateTracker(self.args.statefile)

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

    def finalizeBackup(self, location, sshArgs, name=None):
        """ Finalize backup removes incomplete suffix from dest 
        
        """

        if name is None:
            name = self.today

        if location.isLocal:
            toName = os.path.join(location.path, name)
            fromName = toName + self.incompleteSuffix
            logging.debug('Moving %s to %s', fromName, toName)
            if os.path.exists(toName):
                # Remove old instance if it already exists
                logging.debug('Replacing backup %s', toName)
                shutil.rmtree(toName)
            os.rename(fromName, toName)
        elif location.isRemote:
            # Create the state file
            toName =  location.path+'/'+name
            fromName = toName + self.incompleteSuffix
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

    def invokeRSync(self, rsync):
        """ Make the rsync call """

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

    def execute(self):
        
        #self.parent.initPublisher()
        #self.publisher = self.parent.publisher

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
                sshArgs = self.parent.getSshArgs(job)
                
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
                rsync = ['rsync'] + self.rsyncOpts + rsyncExtraArgs + linkTargetOpts + rsyncSshArgs + [sourceLoc.rsyncPath(''), destLoc.rsyncPath(self.today+incompleteSuffix)]
                
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
                    self.publisher.publishLastGood(job, self.today)
                    
                    logging.debug('Updating local state tracker')
                    if self._stateTracker is not None:
                        self._stateTracker.update(job, self.today)

                    if self.args.clean:
                        logging.debug('Clean after backup')
                        self.Clean(job)
