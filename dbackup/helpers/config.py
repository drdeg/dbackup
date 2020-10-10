import logging
import urllib.request
import ipaddress

def getDynamicHost(jobConfig):
    if 'dynamichost' in jobConfig:
        try:
            logging.debug('Fetching dynamic host from ' + jobConfig['dynamichost'])
            page = urllib.request.urlopen(jobConfig['dynamichost'])
            dynamichost = page.read().decode("utf-8").strip()
            # Check if the IP can be resolved
            dynamicIP = ipaddress.ip_address(dynamichost) # Throws ValueError if dynamichost is not a valid IP number
            logging.info('Dynamic ip address in %s is %s', jobConfig.name, dynamichost)
            return dynamichost
        except ValueError:
            logging.error('Dynamichost failed')
    return None