import configparser
from dbackup.job import Job

class Config:

    def __init__(self, filePath):
        self._config = configparser.ConfigParser(interpolation=configparser.ExtendedInterpolation())
        self._config.read(filePath)

        # Include only jobs that have botha source and dest field. This is to
        # skip the common seciton
        jobs = filter(lambda job: 'dest' in self._config[job] and 'source' in self._config[job], self._config.sections())

        # Iterate over all configuration files
        self.jobs = [ Job(job, self._config[job]) for job in jobs ]
