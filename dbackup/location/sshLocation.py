from . import Location
import logging
import subprocess
import os
import re

from ..helpers import SshError

class SshLocation(Location):
    """ SSH based locations

    Location specification has the form [user]@[host]:(path)
    """

    def __init__(self, spec, dynamichost = None,  sshArgs = None, simulate = False):
        super().__init__(spec, dynamichost, typeName='remote', simulate = simulate)

        # sshArgs contains -p [port] -i userCert -o UserHostKey and so on. 
        # There is no need to append them to the sshArgs list

        self.dynamicHost = dynamichost
        self.sshArgs = sshArgs
        assert sshArgs is not None

        self.hostKeyFile = self._determineHostKeyFile(sshArgs)      # Can be None if not specified in arguments
        self.sshPort = self._determineSshPort(sshArgs)

        # Decode user, host and path from spec
        self.__DecodeRemoteLocation(spec, dynamichost)

    def __str__(self):
        return f'SshLocation:{self.user}@{self.host}:{self.path}'

    def __DecodeRemoteLocation(self, spec, dynamichost):
        logging.debug('Decoding remote location %s', spec)
        try:
            m = re.match(r"^([^@:]*)@([^@:]*):(.*)$", spec)
            self.user = m.group(1)
            self.host = m.group(2)
            self.path = m.group(3)
            logging.debug(f'user={self.user}, host={self.host}, path={self.path}')
            if self.host == 'dynamichost':
                if dynamichost is None:
                    logging.warning('Dynamic host is used but not defined')
                else:
                    logging.debug('Replacing dynamichost with %s', dynamichost)
                    self.host = dynamichost
                
            logging.debug("Location is decoded as " + self.user+" at " + self.host + " in " + self.path)
        except Exception as e:
            logging.error('Invalid format of location: '+spec)
            print(e)

    def _determineHostKeyFile(self, sshArgs) -> str:
        """ Parses the ssh argument list and tries to find
        """
        # Check if UserHostKey is defined in arguments
        r = re.compile("UserKnownHostsFile=(.*)")
        fa = list(filter(r.match, sshArgs))
        if fa:
            m = r.match(fa[0])
            hostKeyFile = m[1]
            logging.debug(f"Identified UserKnownHostsFile={hostKeyFile}")
            return hostKeyFile
        else:
            return None

    def _determineSshPort(self, sshArgs : list) -> int:

        try:
            # Take the argument following '-p' in argument list
            sshPort = int(sshArgs[ sshArgs.index('-p') + 1])
        except:
            logging.debug("Using default ssh port")
            sshPort = 22

        return sshPort

    def _buildSshArgs(self) -> list:
        """ Builds the ssh argument list
        
        """

        # Assumes that the object owner (job) already has added -o UserHostKey

        assert '-p' in self.sshArgs, 'Expected -p to be in the ssh argument list'
        cmd = []
        if self.user and self.host and '-l' not in self.sshArgs:
            cmd +=  ['-l', self.user]
        if self.sshKnownHostArgs:
            cmd += self._sshKnownHostArgs
        

    def rsyncPath(self, subpath = None):
        return self.host + ':' + (self.path if subpath is None else os.path.join(self.path, subpath))

    def sshUserHostArgs(self):
        """ Returns arguments needed for user and host arguments to SSH as a list"""
        if self.user is not None and self.host is not None:
            return ['-l', self.user, self.host]
        else:
            logging.warning("Username and host is not specified")
            return []

    def _checkKnownHost(self):

        # Check if the host is already known
        cmd = ['ssh-keygen', '-l', '-F', self.host]
        if self.hostKeyFile:
            cmd += ['-f', self.hostKeyFile]

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
        cmd = ['ssh'] + self._buildSshArgs() + ['hostname']
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
            cmd = ['ssh'] + self._buildSshArgs() + ['test -d %s'%(folderPath)]
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

        - Checks that the remote host is knowns
        - SSHs to the remote
        - Checks that the directory exists on the remote.
        - Creates remote folder if it doesn't
        """


        # BUG: ssh uses the option -o UserKnownHostsFile=/etc/dbackup/known_hosts, but ssh-keygen
        # uses -f /etc/dbackup/known_hosts. Need to scan ssh_args to implement this or refactor
        # with more argument support

        # Updates the sshKnownHostArgs
        self._checkKnownHost()

        self._checkConnection()

        return self.testFolder(self.path)

    def create(self):
        """ Greates the location on the remote """
        
        assert self.sshArgs is not None

        cmd = self.sshArgs + self.sshUserHostArgs() + ['[ -d "' + self.path + '" ] || mkdir -p "' + self.path + '"']
        logging.debug('Remote command: '+ ' '.join(cmd))
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

        assert self.sshArgs is not None
        assert self.sshUserHostArgs() is not None

        cmd = self.sshArgs + self.sshUserHostArgs() + ['ls -d "'+self.path+'/"*/ | xargs -r -L 1 basename']
        logging.debug('Remote command: '+ ' '.join(cmd))
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

        cmd = self.sshArgs + self.sshUserHostArgs() + ['rm -rf "'+toPath+'";mv "'+fromPath+'" "'+toPath+'"']
        logging.debug('Remote command: '+ ' '.join(cmd))
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
        cmd = self.sshArgs + self.sshUserHostArgs() + ['rm -rf '+rmString]
        logging.debug('Remote command: '+ ' '.join(cmd))

        try:
            if not self.simulate:
                subprocess.check_output(cmd, stderr=subprocess.PIPE)
            return True
        except subprocess.CalledProcessError as e:
            logging.debug('ssh failed %d: %s' %(e.returncode, e.stderr.decode("utf-8").rstrip()))
        return False
