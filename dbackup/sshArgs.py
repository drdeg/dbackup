from pathlib import Path
import re
import shlex

class SshArgs:
    """ Class that understands ssh arguments as specified
    in the job specification
    
        - Port
        - Known hosts key file
        - User Certificate (private key)
        - User name
    
    """

    mandatorySshArgs = ['-o', 'BatchMode=yes']
    #mandatorySshArgs = ['-o', 'PubkeyAuthentication=yes', '-o', 'PreferredAuthentications=publickey']

    def __init__(self, jobConfig):
        """
        
        jobConfig (dict or ConfigSection):
        """

        self.extraArgs = shlex.split(jobConfig['ssharg']) if 'ssharg' in jobConfig else []
        self._sshPort = self.__determinePort(jobConfig)
        self._hostKeyFile = self.__determineHostKeyFile(jobConfig)
        self._user = self.__determineUser(jobConfig)
        self._cert = Path(jobConfig['cert']) if 'cert' in jobConfig else None
        #self.__args = self.__buildSshArgs(jobConfig)

    def __determinePort(self, jobConfig : dict) -> int:
        
        if '-p' in self.extraArgs:
            # Port is specified in ssharg, overrides option
            return int(self.extraArgs[self.extraArgs.index('-p') + 1])
        elif 'sshport' in jobConfig:
            return int(jobConfig['sshport'])
        else:
            return 22

    def __determineHostKeyFile(self, jobConfig) -> Path:
        r = re.compile("UserKnownHostsFile=(.*)")
        fa = list(filter(r.match, self.extraArgs))
        if fa:
            m = r.match(fa[0])
            hostKeyFile = m[1]
            return Path(hostKeyFile)
        elif 'sshhostkeyfile' in jobConfig:
            return Path(jobConfig['sshhostkeyfile'])
        else:
            return None

    def __determineUser(self, jobConfig) -> str:
        if '-l' in self.extraArgs:
            return self.extraArgs[self.extraArgs.index('-p') + 1]
        else:
            return None

    def __buildSshArgs(self):
        """ Builds the ssh argument list """
        args = []
        if '-p' not in self.extraArgs:
            args += ['-p', str(self.port)]

        if self.cert:
            args += ['-i', str(self.cert)]

        r = re.compile("UserKnownHostsFile=(.*)")
        fa = list(filter(r.match, self.extraArgs))
        if not fa and self.hostKeyFile:
            args += ['-o', 'UserKnownHostsFile='+str(self.hostKeyFile)]

        if self.user and '-l' not in self.extraArgs:
            args += ['-l', self.user]

        args += self.extraArgs
        args += self.mandatorySshArgs

        return args

    @property
    def user(self) -> str:
        return self._user

    @user.setter
    def user(self, user):
        if '-l' not in self.extraArgs:
            self._user = user

    @property
    def cert(self) -> Path:
        return self._cert

    @property
    def port(self) -> int:
        return self._sshPort

    @property
    def hostKeyFile(self) -> Path:
        """ Full path to the host keys filed or None if not specified"""
        return self._hostKeyFile

    @property
    def argsList(self):
        return self.__buildSshArgs()

    def __iter__(self):
        args = self.__buildSshArgs()
        yield from args

