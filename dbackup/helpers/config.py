import logging
import urllib.request
import ipaddress

def getDynamicHost(jobConfig):
    if 'dynamichost' in jobConfig:
        try:
            logging.debug('Fetching dynamic host from ' + jobConfig['dynamichost'])
            page = urllib.request.urlopen(jobConfig['dynamichost'])
            dynamichost = page.read().decode("utf-8").strip()
            dynamicIP = ipaddress.ip_address(dynamichost) # Throws ValueError if dynamichost is not a valid IP number
            logging.info('Dynamic ip address in %s is %s', jobConfig.name, dynamichost)
            return dynamichost
        except ValueError as e:
            logging.error('Dynamichost failed')
    return None