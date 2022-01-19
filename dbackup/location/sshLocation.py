from . import Location
import logging
import subprocess
import os
import re

from ..helpers import SshError
from ..sshArgs import SshArgs

class SshLocation(Location):
    """ SSH based locations

    Location specification has the form [user]@[host]:(path)
    """

    def __init__(self, spec,  sshArgs : SshArgs, simulate = False):
        super().__init__(spec, typeName='remote', simulate = simulate)

        # sshArgs contains -p [port] -i userCert -o UserHostKey and so on. 
        # There is no need to append them to the sshArgs list

        # Decode user, host and path from spec
        self.__DecodeRemoteLocation(spec)

        self.sshArgs = sshArgs
        self.sshArgs.user = self.user

        self._sshKnownHostArgs = None

    def __str__(self):
        return f'SshLocation:{self.user}@{self.host}:{self.path}'

    def __DecodeRemoteLocation(self, spec):
        logging.debug('Decoding remote location %s', spec)
        try:
            m = re.match(r"^([^@:]*)@([^@:]*):(.*)$", spec)
            self.user = m.group(1)
            self.host = m.group(2)
            self.path = m.group(3)
            logging.debug(f'user={self.user}, host={self.host}, path={self.path}')
            logging.debug("Location is decoded as " + self.user+" at " + self.host + " in " + self.path)
        except Exception as e:
            logging.error('Invalid format of location: '+spec)
            print(e)

    def _buildSshCmd(self, command : str , extraArgs : list = None) -> list:
        """ Builds the ssh command list

        Assembled a ssh command honoring all arguments in sshArgs and sshKnownHostArg.

        Arguments
        ---------

        command (str): the command that should be executed on the remote host
        extraArgs (list[str]): Any extra arguments for ssh that should be included

        """

        # Assumes that the object owner (job) already has added -o UserHostKey
        assert '-p' in self.sshArgs, 'Expected -p to be in the ssh argument list'
        cmd = ['ssh']
        cmd += list(self.sshArgs)
        if extraArgs:
            cmd += extraArgs

        # Append hostname
        cmd += [self.host]

        # Finally, add the command
        cmd += [command]

        logging.debug('Build ssh command: '+ ' '.join(cmd))
        return cmd

    def rsyncPath(self, subpath = None):
        return self.host + ':' + (self.path if subpath is None else os.path.join(self.path, subpath))

    #def sshUserHostArgs(self):
    #    """ Returns arguments needed for user and host arguments to SSH as a list"""
    #    if self.user is not None and self.host is not None:
    #        return ['-l', self.user, self.host]
    #    else:
    #        logging.warning("Username and host is not specified")
    #        return []

    def _checkKnownHost(self):
        """ ** DEPRECATED - DO NOT USE** """

        assert False, 'Deprecated'

        # Check if the host is already known
        cmd = ['ssh-keygen', '-l', '-F', self.host]
        if self.sshArgs.hostKeyFile:
            cmd += ['-f', str(self.sshArgs.hostKeyFile)]

        logging.debug('ssh-keygen command: '+' '.join(cmd))
        try:
            output = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            logging.debug('ssh-keygen result code is %d'%(output.returncode))
            if output.returncode != 0:
                logging.info('SSH host key not known for %s. Consider adding it to the known_hosts file.'%(self.host))
                # TODO: Automate this!
                self._sshKnownHostArgs += [ '-o', 'StrictHostKeyChecking=no']
            else:
                logging.debug('SSH host %s is already known'%(self.host))
                self._sshKnownHostArgs = None
        except subprocess.CalledProcessError as e:
                logging.error('Failed ssh-keygen %d: %s'%(e.returncode, e.stderr.decode("utf-8").rstrip()))

    def _checkConnection(self):
        """ Tries to connect to the location """
        # Verify connection to remote host using ssh
        cmd = self._buildSshCmd('hostname')
        logging.debug('Remote command: '+' '.join(cmd))
        try:
            output = subprocess.check_output(cmd, stderr=subprocess.PIPE)
            logging.debug('ssh output: ' + output.decode("utf-8").rstrip())
        except subprocess.CalledProcessError as e:
            raise SshError('SSH failed %d: %s' %(e.returncode, e.stderr.decode("utf-8").rstrip()))

    def testFolder(self, folderPath) -> bool:
        """ Test if the specified folder exists"""

        try:
            # TODO: Check if remote folder exists
            # test -d path returns 0 if is directory, and 1 if it isn't a dir or doesn't exist
            cmd = self._buildSshCmd('test -d %s'%(folderPath))
            output = subprocess.check_output(cmd, stderr=subprocess.PIPE)

            # subprocess.check_output raises CalledProcessError if return code of cmd is nonzero, so if
            # execution continues here, the folder exists
            logging.debug('Directory %s on remote host %s exists'%(folderPath, self.host))
            return True

        except subprocess.CalledProcessError as e:
            # The dest folder doesn't exist
            logging.info('Directory %s doesn''t exist on remote host %s'%(folderPath, self.host))
            return False

        return False

    def validate(self) -> bool:
        """ Validates ssh connection to the location

        - SSHs to the remote
        - Checks that the directory exists on the remote.
        - Creates remote folder if it doesn't
        """

        self._checkConnection()

        return self.testFolder(self.path)

    def create(self):
        """ Greates the location on the remote """
        
        cmd = self._buildSshCmd('[ -d "' + self.path + '" ] || mkdir -p "' + self.path + '"')

        try:
            output = subprocess.check_output(cmd, stderr=subprocess.PIPE)
            logging.debug('ssh output: ' + output.decode("utf-8").rstrip())
            return True
        except subprocess.CalledProcessError as e:
            logging.debug('SSH failed %d: %s' %(e.returncode, e.stderr.decode("utf-8").rstrip()))
            logging.error('Remote directory %s does not exist.', self.path)
        return False

    def listDir(self):
        """ List directories in the remote location """

        cmd = self._buildSshCmd('ls -d "'+self.path+'/"*/ | xargs -r -L 1 basename')
        try:
            output = subprocess.check_output(cmd, stderr=subprocess.PIPE)
            folderList = output.decode("utf-8").splitlines()
            if not folderList:
                logging.info('Remote is empty')
                return None
            logging.debug('Remote files: ' + ', '.join(folderList))
            return folderList
        except subprocess.CalledProcessError as e:
            logging.debug('ssh failed %d: %s' %(e.returncode, e.stderr.decode("utf-8").rstrip()))
            raise SshError('ssh failed %d: %s' %(e.returncode, e.stderr.decode("utf-8").rstrip()))
            
        return None

    def renameChild(self, fromName, toName):
        """ Renames an item in the location 
        
        Replaces destination if it already exists
        
        """

        assert fromName != toName

        fromPath = os.path.join(self.path, fromName)
        toPath = os.path.join(self.path, toName)

        cmd = self._buildSshCmd('rm -rf "'+toPath+'";mv "'+fromPath+'" "'+toPath+'"')
        try:
            if not self.simulate:
                output = subprocess.check_output(cmd, stderr=subprocess.PIPE)
                logging.debug('ssh output: ' + output.decode("utf-8").rstrip())
            else:
                logging.debug('simulated')

        except subprocess.CalledProcessError as e:
            logging.debug('ssh failed %d: %s' %(e.returncode, e.stderr.decode("utf-8").rstrip()))
            logging.error('Could not rename folder')
            raise SshError('ssh failed %d: %s' %(e.returncode, e.stderr.decode("utf-8").rstrip()))

    def deleteChild(self, name):
        """
        Deletes items in the location

        Arguments:
            name (list of str): The names of the items to remove
        """

        if isinstance(name, list):
            rmString = '"'+'" "'.join([self.path +'/'+ n for n in name])+'"'
        else:
            rmString = '"'+self.path+'/'+name+'"'
        cmd = self._buildSshCmd('rm -rf '+rmString)
        try:
            if not self.simulate:
                subprocess.check_output(cmd, stderr=subprocess.PIPE)
            return True
        except subprocess.CalledProcessError as e:
            logging.debug('ssh failed %d: %s' %(e.returncode, e.stderr.decode("utf-8").rstrip()))
        return False
