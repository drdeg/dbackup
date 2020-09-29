import datetime
import logging

def checkAge(dateStr, okLimitDays = 2):
    """ Checks if the age of a date is smaller than a limit
    
    Arguments:
        dateStr (str) : the date of interest
        okLimitDays (int, optional) : Maximum age in days to be considered OK

    Returns
        (state, lastDate)
    """
    try:
        lastDate = datetime.strptime(dateStr, '%Y-%m-%d')
        logging.debug('lastDate ' + lastDate.isoformat())
        logging.debug('today is ' + datetime.now().isoformat())
        lastAge = datetime.now() - lastDate
        logging.debug('Age is ' + str(lastAge.days) + ' days')
    
        if lastAge.days < okLimitDays:
            #logging.info('Backup is OK, age is ' + str(lastAge.seconds/3600/24) + ' days');
            return (True, lastDate)
        else:
            #logging.warning('Backup is outdated, age is ' + str(lastAge.seconds/3600/24) + ' days');
            return (False, lastDate)

    except:
        logging.debug('Unexpected exception')
        return (False, None)
