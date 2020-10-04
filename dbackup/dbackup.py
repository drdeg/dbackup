#!/usr/bin/python3
#
# ALGORITHM DESCRIPTION
#
#   
# CONFIG FILE
#
# [common]
# remote_host = lovlund.dyndns.org
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
# dynamichost = http://www.varukulla.se/reportip.php?query=myckle
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
#
# TODO
#
# - Lock file
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

from datetime import datetime
from os.path import expanduser

from .helpers.errors import *
from .helpers import getDynamicHost
from .helpers import checkAge
from .helpers import Publisher

defaultStateFileName = '.mirror_state'

import dbackup.commands
from dbackup.config import Config, Job

# Arguments used for all ssh requests


class DBackup:
    """ The big DBackup application """

    defaultLocalStateFilename = '/var/local/backup.state'

    sshOpts = ['-o', 'PubkeyAuthentication=yes', '-o', 'PreferredAuthentications=publickey']

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
        self.publisher = Publisher(simulate=self.args.simulate)
        logging.debug(f'Connecting to {self.args.mqtt}:{self.args.port}')
        self.publisher.connect(self.args.mqtt, self.args.port)

    def getSshArgs(self, job):
        """ Compiles the argument list for ssh 
        
        Appends ssh key argument and any options defined in self.sshOpts
        Arguments:
          job (str) : ID of the particular job
        """
        cert = self.config[job].get('cert', None)
        sshArgs = ['ssh']
        if cert is not None:
            sshArgs += ['-i', cert]
            
        return sshArgs + self.sshOpts


    def parseArguments(self):
        parser = argparse.ArgumentParser(description='Backup tool based on RSYNC')
        parser.add_argument('command', help='What to do',choices=['backup','check','clean','report'],default='backup',nargs='1')
        parser.add_argument('job', help='Specify which jobs to run, e.g. kalle pelle olle', default=None, nargs='*')
        parser.add_argument('-c', '--configfile', help='Full path of config file', default='/etc/dtools/backup.ini')
        parser.add_argument('--logfile', help='Full path of log file', default=None)
        parser.add_argument('--log', help='Log level (DEBUG,INFO,WARNING,ERROR,CRITICAL)',default='INFO')
        parser.add_argument('-s', '--statefile', help='Full path of local state file', default=self.defaultLocalStateFilename)
        parser.add_argument('--clean', help='Clean after successfull backup', action='store_true')
        parser.add_argument('--mqtt', help='Publish state to MQTT broker with address', default='')
        parser.add_argument('-p', '--port', help='Port number of MQTT broker', default=1883)
        parser.add_argument('--simulate', help='Don''t do the actual copy and update states', action='store_true')

        self.args = parser.parse_args()
        self.parser = parser

    def initLogging(self):
        if self.args.logfile is None:
            logging.basicConfig(format='%(asctime)s:%(levelname)s:%(message)s', level=getattr(logging, self.args.log.upper()))
        else:
            logging.basicConfig(format='%(asctime)s:%(levelname)s:%(message)s', filename=self.args.logfile, level=getattr(logging, self.args.log.upper()))

    def commandClean(self):
        logging.debug('Clean requested')
        cmdClean = dbackup.commands.Clean(self.config)
        return cmdClean.execute(self.args.job)

    def commandCheck(self):
        cmdCheck = dbackup.commands.CheckJob(self)
        return cmdCheck.execute()

    def commandReport(self):
        logging.debug('Report requested')
        self.initPublisher()
        cmdReport = dbackup.commands.Report(self, publisher = self.publisher)
        return cmdReport.execute()
    
    def commandBackup(self):
        logging.debug('Backup requested')
        # Create lock file for backups
        with fasteners.InterProcessLock("/tmp/backup.lock"):
            self.initPublisher()
            cmdBackup = dbackup.commands.Backup(self, self.publisher)
            return cmdBackup.execute()

    def executeCommand(self, command) -> int:
        if command is None:
            return self.commandBackup()
        else:
            return self.__commands[command]()

    def run(self):

        # Parse arguments
        self.parseArguments()

        # Init logging
        self.initLogging()

        # Parse the configuration file
        logging.debug('Using config file %s', self.args.configfile)
        self.config = Config(self.args.configfile)

        # Init the state file
        self.localStateFileName = self.args.statefile

        # Execute the command and then exit
        try:
            sys.exit(self.executeCommand(self.args.command))
        except ArgumentError as e:
            logging.critical(e.message)
        
        sys.exit(9)



if __name__ == '__main__':
    app = DBackup()
    app.run()
