import os
import re
from . import location
#from .location.factory import Factory
from pathlib import Path
from .sshArgs import SshArgs

class Job:
    """ Defines a single backup job 
    
    Job configuration contains the following options:
        source
        dest
        sshport
        sshhostkeyfile
        rsyncarg
        ssharg
        days
        months
        exec before
        exec after


    Attributes:
        cert (str) : Full path to certificate or None
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


    def __init__(self, name : str, jobConfig, simulate = False):

        assert 'source' in jobConfig
        assert 'dest' in jobConfig

        self.name = name

        self.cert = jobConfig['cert'] if 'cert' in jobConfig else None

        self.rsyncArgs = jobConfig['rsyncarg'].split(' ') if 'rsyncarg' in jobConfig else []
        self.extraSshArgs =  jobConfig['ssharg'].split(' ') if 'ssharg' in jobConfig else []
        self.sshArgs = SshArgs(jobConfig)

        self.daysToKeep = int(jobConfig['days']) if 'days' in jobConfig else 3
        self.monthsToKeep = int(jobConfig['months']) if 'months' in jobConfig else 3

        # Generate locations for source and dest. sshArgs are assembled below
        self.source = location.Factory(jobConfig['source'], sshArgs=self.sshArgs, simulate=simulate)
        self.dest   = location.Factory(jobConfig['dest'],   sshArgs=self.sshArgs, simulate=simulate)

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

