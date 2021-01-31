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

    def __init__(self, spec, dynamichost = None, sshArgs = None, simulate = False):
        super().__init__(spec, dynamichost, typeName='remote', simulate = simulate)

        self.dynamicHost = dynamichost
        self.sshArgs = sshArgs
        assert sshArgs is not None

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

    def rsyncPath(self, subpath = None):
        return self.host + ':' + (self.path if subpath is None else os.path.join(self.path, subpath))

    def sshUserHostArgs(self):
        """ Returns arguments needed for user and host arguments to SSH as a list"""
        if self.user is not None and self.host is not None:
            return ['-l', self.user, self.host]
        else:
            logging.warning("Username and host is not specified")
            return []

    def validate(self) -> bool:
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
            #logging.error('SSH failed %d: %s' %(e.returncode, e.stderr.decode("utf-8").rstrip()))
            raise SshError('SSH failed %d: %s' %(e.returncode, e.stderr.decode("utf-8").rstrip()))

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
