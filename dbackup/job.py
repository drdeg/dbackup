from dbackup.helpers.location import Location


class Job:
    """ Defines a single job """

    sshOpts = ['-o', 'PubkeyAuthentication=yes', '-o', 'PreferredAuthentications=publickey']

    def __init__(self, name, jobConfig):

        assert 'source' in jobConfig
        assert 'dest' in jobConfig

        self.name = name

        self.cert = jobConfig['cert'] if 'cert' in jobConfig else None

        self.dynamicHost = jobConfig['dynamichost'] if 'dynamichost' in jobConfig else None

        self.rsyncArgs = jobConfig['rsyncarg'].split(' ') if 'rsyncarg' in jobConfig else None

        self.daysToKeep = int(jobConfig['days']) if 'days' in jobConfig else 3
        self.monthsToKeep = int(jobConfig['months']) if 'months' in jobConfig else 3

        self.source = Location(jobConfig['source'], dynamichost=self.dynamicHost)
        self.dest = Location(jobConfig['dest'], dynamichost=self.dynamicHost)


    @property
    def sshArgs(self):
        """ Compiles the argument list for ssh 
        
        Appends ssh key argument and any options defined in self.sshOpts
        """
        sshArgs = ['ssh']
        if self.cert is not None:
            sshArgs += ['-i', self.cert]
            
        return sshArgs + self.sshOpts
