#!/usr/bin/python3
#
# ALGORITHM DESCRIPTION
#
#   
# CONFIG FILE
#
# [common]
# remote_host = hostname.dyndns.org
# remote_root = /srv/user1/mirror
# remote_user = root
# remote_url = ${remote_user}@${remote_host}:${remote_root}
# local_dest = /srv/b1/fs/mirror
#
# [DEFAULT]
# ; Special section that can be overridden in each section
# cert = /etc/dtools/mirror/id_rsa
#
# [david]
# source = /home/david
# dest = ${common:remote_url}/home/newdavid
#
# [karin]
# source = /srv/b1/fs/home/karin
# dest = ${common:remote_url}/home/karin
#
# [KoD]
# source = /srv/b1/fs/KoD
# dest = ${common:remote_url}/groups/KoD
#
# [der]
# source = ${common:remote_user}@${common:remote_host}:/home/mirror-daemon
# dest = ${common:local_dest}/home/mirror-daemon
#
# [software]
# source = /srv/b1/fs/share/Software
# dest = ${common:remote_url}/share/Software
#
# [MyckleBilder]
# dynamichost = http://anotherhost.com/reportip.php?query=myckle
# source = root@dynamichost:/volume1/photo
# dest = ${common:local_dest}/myckle/photo
# rsyncarg = -z
#
# MQTT messages
# backup/[job]/state
# backup/[job]/lastgood
#
# DONE
#
# - Parse argument
# - Parse config file
# - Support local -> remote backups
# - Support remote -> local backups
# - Handle logging to files 
# - Support .rsync-filter files in source
# - BUG: Check permissions when running as root (Causes havoc with root)
# - Global log file
# - Support cleaning of old backups locally
# - Rewrite backup to handle both ways in same method
# - Backups should be made to a temp folder (date.incomplete) and renamed after success
# - Clean should not care about incomplete backups
# - Clean should support remote destinations
# - Clean supports --job option to clean a single job
# - Backup should parse directory instead of reading statefile and igonre incomplete backups
# - Backup should support --job switch to only run single job
# - BUG: FinalizeBackup doesn't overwrite existing directory
# - Add --clean option to automatically clean after backup job is finished
# - Clean should remove incomplete backups
# - BUG: dynamichost failed
# - BUG: when remote host IP changed, the host key was unknown and ssh failed.
# - Add support to add per backup job rsync options, such as -c or -Z for compression
# - BUG: Failed to create remote directory for new backups
# - BUG: Crashed when no previous backups were found on remote
# - Add support to verify that the source and destinations exist
# - Lock file for backup operation
#

import time
import subprocess
import os
import sys
import re
import configparser
import argparse
import urllib.request
import logging
import ipaddress
import datetime
import shutil
import collections

import fasteners

from typing import List

from datetime import datetime
from os.path import expanduser

from dbackup.helpers.errors import *
from dbackup.helpers import getDynamicHost
from dbackup.helpers import checkAge
from dbackup.helpers import Publisher
from dbackup.helpers import StateTracker

defaultStateFileName = '.mirror_state'

import dbackup.commands
import dbackup.resultcodes
from dbackup.config import Config, Job


class DBackup:
    """ The big DBackup application """

    defaultLocalStateFilename = '/var/local/backup.state'

    def __init__(self):
        # Create a map of command handlers
        self.__commands = {
            'clean': self.commandClean,
            'check': self.commandCheck,
            'report': self.commandReport,
            'backup': self.commandBackup,
            }
        self.__today = time.strftime( "%Y-%m-%d")

        self.publisher = None

    @property
    def today(self):
        return self.__today

    def initPublisher(self):
        """ Instantiates the MQTT publisher

        It checks the self.args for MQTT broker configuration
        """

        self.publisher = Publisher(simulate=self.args.simulate)
        logging.debug(f'Connecting to {self.args.mqtt}:{self.args.port}')
        self.publisher.connect(self.args.mqtt, self.args.port)

    def parseArguments(self):
        parser = argparse.ArgumentParser(description='Backup tool based on RSYNC')
        parser.add_argument('command', help='What to do',choices=['backup','check','clean','report'],default='backup')
        parser.add_argument('job', help='Specify which jobs to run, e.g. kalle pelle olle', default=None, nargs='*')
        parser.add_argument('-c', '--configfile', help='Full path of config file', default='/etc/dtools/backup.ini')
        parser.add_argument('--logfile', help='Full path of log file', default=None)
        parser.add_argument('--log', help='Log level (DEBUG,INFO,WARNING,ERROR,CRITICAL)',default='INFO')
        parser.add_argument('-s', '--statefile', help='Full path of local state file', default=self.defaultLocalStateFilename)
        parser.add_argument('--clean', help='Clean after successfull backup', action='store_true')
        parser.add_argument('--mqtt', help='Publish state to MQTT broker with address', default='')
        parser.add_argument('-p', '--port', help='Port number of MQTT broker', default=1883)
        parser.add_argument('--simulate', help='Don\'t do the actual copy and update states', action='store_true')

        self.args = parser.parse_args()
        self.parser = parser

    def initLogging(self):
        if self.args.logfile is None:
            logging.basicConfig(format='%(asctime)s:%(levelname)s:%(message)s', level=getattr(logging, self.args.log.upper()))
        else:
            logging.basicConfig(format='%(asctime)s:%(levelname)s:%(message)s', filename=self.args.logfile, level=getattr(logging, self.args.log.upper()))


    def commandClean(self, jobs) -> int:
        logging.debug('Clean requested')
        cmdClean = dbackup.commands.Clean(simulate = self.args.simulate)
        return cmdClean.execute(jobs)

    def commandCheck(self, jobs) -> int:
        cmdCheck = dbackup.commands.CheckJob( stateTracker = self.stateTracker )
        return cmdCheck.execute(jobs)

    def commandReport(self, jobs) -> int:
        logging.debug('Report requested')
        self.initPublisher()
        cmdReport = dbackup.commands.Report(publisher = self.publisher, stateTracker = self.stateTracker)
        return cmdReport.execute(jobs)
    
    def commandBackup(self, jobs) -> int:
        logging.debug('Backup requested')
        # Create lock file for backups
        with fasteners.InterProcessLock("/tmp/backup.lock"):
            self.initPublisher()
            cmdBackup = dbackup.commands.Backup(
                publisher = self.publisher,
                stateTracker = self.stateTracker,
                simulate = self.args.simulate)
            if self.args.clean:
                cmdClean = dbackup.commands.Clean(simulate = self.args.simulate)
            result = 0
            for job in jobs:
                result = max(result, cmdBackup.execute(job))
                if self.args.clean:
                    cmdClean.execute([job])

            return result



    def executeCommand(self, command, jobs) -> int:
        if command is None:
            return self.commandBackup(jobs)
        else:
            return self.__commands[command](jobs)

    def getJobs(self) -> List[ Job ]:
        """ Get a list of the jobs as specified by arguments """
        if not self.args.job:
            # No job is specified, use all
            return list(self.config.jobs())
        else:
            # User chose to specify a subset of jobs
            return list(map(lambda jobName : self.config[jobName], self.args.job))

    def run(self):

        # Parse arguments
        self.parseArguments()

        # Init logging
        self.initLogging()

        # Parse the configuration file
        logging.debug('Using config file %s', self.args.configfile)
        self.config = Config(self.args.configfile)

        # Init state tracker
        with StateTracker(self.args.statefile) as stateTracker:
            self.stateTracker = stateTracker

            # Get the list of jobs
            jobs = self.getJobs()

            # Execute the command and then exit
            try:
                sys.exit(self.executeCommand(self.args.command, jobs))
            except ArgumentError as e:
                logging.critical(e.message)
                sys.exit(dbackup.resultcodes.INVALID_ARGUMENT)
            except SshError as e:
                logging.critical(e.message)
                sys.exit(dbackup.resultcodes.SSH_ERROR)
            
            sys.exit(dbackup.resultcodes.UNEXPECTED_ERROR)

