import configparser
import logging
from datetime import datetime, timedelta

from . import time

class StateTracker:
    """ Tracks the current state of each backup

    The state is stored in a ini-like file. The default location is
    /var/local/backup.state

    [LastGood]
    job1 = 2020-10-03
    job2 = 2020-10-03

    """

    defaultStateFilePath = '/var/local/backup.state'
    
    def __init__(self, filePath = defaultStateFilePath):
        self.filePath = filePath
        self.today = time.today
        self.state = configparser.ConfigParser()

        # Might fail if the file doesn't exist
        self._read()

        self._dirty = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if self._dirty:
            self._write()

    def _read(self):
        """ Reads the current state from the file """
        logging.debug(f'Reading states from {self.filePath}')
        self.state.read(self.filePath)

    def _write(self):
        logging.info(f'Saving state to {self.filePath}')
        with open(self.filePath, 'w') as stateFile:
            self.state.write(stateFile)

    def getJobAge(self, job):
        """ Get the job age in days """

        try:
            dateStr = self.state['LastGood'][str(job)]
            lastDate = datetime.strptime(dateStr, '%Y-%m-%d')
            logging.debug('lastDate ' + lastDate.isoformat())
            logging.debug('today is ' + datetime.now().isoformat())
            lastAge = datetime.now() - lastDate
            logging.debug('Age is ' + str(lastAge.days) + ' days')
            return lastAge
        except KeyError:
            logging.error(f'No history of job {str(job)} found')
            return None

    def checkJobAge(self, job : str, okLimitDays = 2):
        """ Check if a job is older than a given number of days """
        jobAgeDays = self.getJobAge(str(job))
        if jobAgeDays is None:
            return None
        else:
            return (jobAgeDays <= timedelta(days = okLimitDays), jobAgeDays)

    def update(self, job : str, lastGood = None):
        """ Updates the local state of a job
        
        Arguments:
            job (str) : Job identifier
            lastGood (str) : Date string of last good backup date or None
                to specify self.today
        """

        # Init the state if it is empty
        if not 'LastGood' in self.state:
            self.state['LastGood'] = {}
        
        # Set last good date for the specified job
        self.state['LastGood'][str(job)] = lastGood if lastGood is not None else self.today

        self._dirty = True
