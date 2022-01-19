import os
import re
from . import location
from pathlib import Path

class Job:
    """ Defines a single backup job 
    
    Job configuration contains the following options:
        source
        dest
        sshport
        sshhostkeyfile
        rsyncarg
        dynamichost (deprecated)
        ssharg
        days
        months
        exec before
        exec after


    Attributes:
        cert (str) : Full path to certificate or None
        dynamicHost (str) : The dynamic host name or None
        rsyncArgs (list(str)) : Extra arguments to rsync command
        daysToKeep (int) : Number of days to keep daily backups
        monthsToKeep (int) : Number of months to keep monthly backups
        sshPort (int) : The ssh port
        sshHostKeyFile (str) : path to the ssh host key file to use or None if not specified
        sshArgs (list(str)) : ssh arguments

        source (Location) : Source location (the files to backup)
        dest (Location) : Dest location (this is where the backups are stored)

        execBefore (str) : A command to execute before backup or None
        execAfter (str) : A command to execute after backup
    """

    sshOpts = ['-o', 'PubkeyAuthentication=yes', '-o', 'PreferredAuthentications=publickey']

    def __init__(self, name : str, jobConfig : dict, simulate = False):

        assert 'source' in jobConfig
        assert 'dest' in jobConfig

        self.name = name
        self.__rawConfig = jobConfig.copy()

        self.cert = jobConfig['cert'] if 'cert' in jobConfig else None

        self.dynamicHost = jobConfig['dynamichost'] if 'dynamichost' in jobConfig else None

        self.rsyncArgs = jobConfig['rsyncarg'].split(' ') if 'rsyncarg' in jobConfig else []
        self.extraSshArgs =  jobConfig['ssharg'].split(' ') if 'ssharg' in jobConfig else []
        #self.sshHostKeyFile = jobConfig['sshhostkeyfile'] if 'sshhostkeyfile' in jobConfig else None

        self.daysToKeep = int(jobConfig['days']) if 'days' in jobConfig else 3
        self.monthsToKeep = int(jobConfig['months']) if 'months' in jobConfig else 3

        # Generate locations for source and dest. sshArgs are assembled below
        self.source = location.factory(jobConfig['source'], dynamichost=self.dynamicHost, sshArgs=self.sshArgs, simulate=simulate)
        self.dest = location.factory(jobConfig['dest'], dynamichost=self.dynamicHost, sshArgs=self.sshArgs, simulate=simulate)

        self.execBefore = jobConfig['exec before'] if 'exec before' in jobConfig else None
        self.execAfter = jobConfig['exec after'] if 'exec after' in jobConfig else None

        assert isinstance(self.source, location.Location)
        assert isinstance(self.dest, location.Location)

    def __str__(self):
        """ Implicit conversion to string """
        return self.name

    @property
    def simulate(self):
        return self._simulate

    @simulate.setter
    def simulate(self, simulate):
        self.source.simulate = simulate
        self.dest.simulate = simulate
        self._simulate = simulate

    @property
    def cert(self):
        return self._cert

    @cert.setter
    def cert(self, cert):
        if cert is not None:
            assert os.path.isfile(cert)
        self._cert = cert

    @property
    def id(self) -> str:
        return self.name

    @property
    def sshPort(self):
        """ Determines the ssh port.
        
        Port is either specified as explicit argument but is overridden by
        estra arguments in sshargs
        """

        if '-p' in self.extraSshArgs:
            # -p flag is speficied in extra args, port is in next argument
            sshPort = int(self.extraSshArgs[self.extraSshArgs.index('-p') + 1])
        elif 'sshport' in self.__rawConfig:
            # Use the sshport argument
            sshPort = int(self.__rawConfig['sshport'])
        else:
            sshPort = 22
        return sshPort

    @property
    def sshHostKeyFile(self) -> Path:

        # Check if UserHostKey is defined in arguments
        r = re.compile("UserKnownHostsFile=(.*)")
        fa = list(filter(r.match, self.extraSshArgs))
        if fa:
            m = r.match(fa[0])
            hostKeyFile = m[1]
            return Path(hostKeyFile)
        elif 'sshhostkeyfile' in self.__rawConfig:
            return Path(self.__rawConfig['sshhostkeyfile'])
        else:
            return None

    @property
    def sshArgs(self):
        """ Compiles the argument list for ssh 
        
        Appends ssh key argument and any options defined in self.sshOpts

        First argument is ssh command (so full path can be specified)
        """
        sshArgs = []
        if '-p' not in self.extraSshArgs:
            sshArgs += ['-p', str(self.sshPort)]
        if self.cert is not None:
            sshArgs += ['-i', self.cert]
        if self.sshHostKeyFile:
            sshArgs += ['-o', 'UserKnownHostsFile='+str(self.sshHostKeyFile)]
        if self.extraSshArgs is not None:
            sshArgs += self.extraSshArgs

        return sshArgs + self.sshOpts
