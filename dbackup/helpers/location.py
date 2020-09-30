import re
import os
import logging
import subprocess

from .errors import SshError

class Location:
    """ Location is a class that handles local and remote RSYNC locations
    
        user@host:path/to/location
    
    """
    def __init__(self, spec, dynamichost = None, sshArgs = None):
        self.spec = spec
        self.type = 'remote' if re.match(r'^[^@:]*@[^@:]*:.*$', spec) is not None else 'local'
    
        if self.type == 'remote':
            self.__DecodeRemoteLocation(spec, dynamichost)
        if self.type == 'local':
            self.path = spec

        self.__sshArgs = sshArgs
            
    @property
    def sshArgs(self):
        return self.__sshArgs

    def __DecodeRemoteLocation(self, spec, dynamichost):
        logging.debug('Decoding remote location %s', spec)
        try:
            m = re.match(r"^([^@:]*)@([^@:]*):(.*)$", spec)
            self.user = m.group(1)
            self.host = m.group(2)
            self.path = m.group(3)
            logging.debug('host is "%s"', self.host)
            if self.host == 'dynamichost':
                if dynamichost is None:
                    logging.warning('Dynamic host is used but not defined')
                else:
                    logging.debug('Replacing dynamichost with %s', dynamichost)
                    self.host = dynamichost
                
            logging.debug("Location is decoded as " + self.user+" at " + self.host + " in " + self.path)
        except:
            logging.error('Invalid format of location: '+spec)    
    
    @property
    def isLocal(self):
        return self.type == 'local'
        
    def sshUserHostArgs(self):
        return ['-l', self.user, self.host]
    
    @property
    def isRemote(self):
        return self.type == 'remote'
        
    def rsyncPath(self, subpath = None):
        if self.isLocal:
            return self.path if subpath is None else os.path.join(self.path, subpath)
        elif self.isRemote:
            return self.host+':' + (self.path if subpath is None else os.path.join(self.path, subpath))
        else:
            return None
    

    def _createLocal(self) -> bool:
        """ Creates local location """
        # Use os to create path recursively

        assert self.isLocal

        if os.path.exists(self.path):
            return True
        else:
            logging.info("Creating local folder "+self.path)
            try:
                os.makedirs(self.path)
                return True
            except:
                logging.error('ERROR: Could not create directory '+self.path)
            return False

    def _createRemote(self) -> bool:
        """ Creates a remote location """
        # Ensure that the remote target directory exists
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

    def create(self) -> bool:
        """ Creates the path """
        if self.isLocal:
            return self._createLocal()
        elif self.isRemote:
            return self._createRemote()
        else:
            return False

    def _validateSshConnection(self) -> bool:
        """ Validates ssh connection to the location

        - Checks that the remote host is knowns
        - SSHs to the remote
        - Checks that the directory exists on the remote.
        - Creates remote folder if it doesn't
        """

        sshKnownHostArgs = []
    
        # Check if the host is already known
        cmd = ['ssh-keygen', '-l', '-F', self.host]
        logging.debug('ssh-keygen command: '+' '.join(cmd))
        try:
            output = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            logging.debug('ssh-keygen result code is %d'%(output.returncode))
            if output.returncode != 0:
                logging.info('SSH host key not known for %s. Adding it to the known_hosts file.'%(self.host))
                sshKnownHostArgs += [ '-o', 'StrictHostKeyChecking=no']
            else:
                logging.debug('SSH host %s is already known'%(self.host))
        except subprocess.CalledProcessError as e:
                logging.error('Failed ssh-keygen %d: %s'%(e.returncode, e.stderr.decode("utf-8").rstrip()))
                                
        # Verify connection to remote host using ssh
        cmd = self.sshArgs + sshKnownHostArgs + self.sshUserHostArgs() + ['hostname']
        logging.debug('Remote command: '+' '.join(cmd))
        try:
            output = subprocess.check_output(cmd, stderr=subprocess.PIPE)
            logging.debug('ssh output: ' + output.decode("utf-8").rstrip())
        except subprocess.CalledProcessError as e:
            logging.error('SSH failed %d: %s' %(e.returncode, e.stderr.decode("utf-8").rstrip()))
            return False

        try:
            # TODO: Check if remote folder exists
            # test -d path returns 0 if is directory, and 1 if it isn't a dir or doesn't exist
            cmd = self.sshArgs + sshKnownHostArgs + self.sshUserHostArgs() + ['test -d %s'%(self.path)]
            output = subprocess.check_output(cmd, stderr=subprocess.PIPE)

            # subprocess.check_output raises CalledProcessError if return code of cmd is nonzero, so if
            # execution continues here, the folder exists
            logging.debug('Target directory %s on remote host %s exists'%(self.path, self.host))
            return True

        except subprocess.CalledProcessError as e:
            # The dest folder doesn't exist
            logging.info('Target directory %s doesn''t exist on remote host %s'%(self.path, self.host))
            return False

        return False

    def validateConnection(self) -> bool:
        """Checks that it is possible to connect to the specified location"""

        if self.isLocal:
            return os.path.isdir(self.spec)
            
        elif self.isRemote:
            return self._validateSshConnection()

        else:
            logging.error('ValidateConnection: This should not be possible')
        return False

    def _listDirLocal(self):
        """ List directories in the local location """
        assert self.isLocal

        try:
            # List files and filter out directories
            folderList = [o for o in os.listdir(self.path) if os.path.isdir(os.path.join(self.path, o)) ]
            return folderList if folderList else None
        except FileNotFoundError:
            logging.warning('No backups found at %s', self.path)
            return None

    def _listDirSsh(self):
        """ List directories in the remote location """
        assert self.isRemote

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

    def listDirs(self):
        """ List directories in the location """
        return self._listDirLocal() if self.isLocal else self._listDirSsh()
