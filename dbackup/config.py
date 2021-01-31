import configparser
from .job import Job

class Config:

    def __init__(self, filePath, simulate = False):
        self._config = configparser.ConfigParser(interpolation=configparser.ExtendedInterpolation())
        self._config.read(filePath)

        # Include only jobs that have botha source and dest field. This is to
        # skip the common seciton
        self.jobNames = filter(lambda job: 'dest' in self._config[job] and 'source' in self._config[job], self._config.sections())

        # Iterate over all configuration files
        self._jobs = [ Job(job, self._config[job], simulate=simulate) for job in self.jobNames ]

        self.__stateTracker = None

    def __getitem__(self, key) -> Job:
        """ Finds the job with name key and returns it"""
        for job in self._jobs:
            if job.name == key:
                return job
        return None

    def jobs(self):
        """ Get a list of the jobs 
        
        Returns a list of [ Job ] objects
        """

        for job in self._jobs:
            yield job