import unittest
from pathlib import Path

import dbackup
import configparser

from dbackup.job import Job

class TestJob(unittest.TestCase):
    jobSpec = {
        'cert': str(Path(__file__).parent / 'data' / 'dummy_key.pub'),
        'source': 'gud@localhost:/tmp/source',
        'dest': '/tmp/dest',
        'ssharg': '-p 1234',
        'days': 10,
        'months': 5,
        'rsyncarg': '--fuzzy',
        'sshhostkeyfile': str(Path(__file__).parent / 'data' / 'known_hosts'),
    }

    def generateConfig(self):
        config = configparser.ConfigParser(interpolation=configparser.ExtendedInterpolation())
        config['DEFAULT'] = {
            'cert': str(Path(__file__).parent / 'data' / 'dummy_key.pub'),
            'days': 10,
            'months': 6,
            'rsyncarg': '--fuzzy',
            'sshhostkeyfile': str(Path(__file__).parent / 'data' / 'known_hosts')
        }
        config['test'] = {
            'source': 'gud@localhost:/tmp/source',
            'dest': '/tmp/dest',
            'ssharg': '-p 1234'
        }
        return config

    def test_config(self):
        config = self.generateConfig()

        # Create a job
        job = Job('test', config['test'])

    def test_instances(self):
        config = self.generateConfig()
        job = Job('test', config['test'])
        
        self.assertIsInstance(job.source, dbackup.location.SshLocation)
        self.assertIsInstance(job.dest, dbackup.location.LocalLocation)


    def test_SshArgs(self):
        expectedSshArgs = [
            '-i', str(Path(__file__).parent / 'data' / 'dummy_key.pub'),
            '-o', 'UserKnownHostsFile='+str(Path(__file__).parent / 'data' / 'known_hosts'),
            '-l', 'gud',
            '-p', '1234',
            '-o', 'BatchMode=yes',
        ]

        # Create a job
        config = self.generateConfig()
        job = Job('test', config['test'])
        self.assertListEqual(list(job.sshArgs), expectedSshArgs)

        return True

    def test_defaultSshPort(self):
        job = dbackup.Job('testJob', self.jobSpec)
        self.assertEqual(job.sshArgs.port, 1234)

        altSpec = self.jobSpec.copy()

        # Test that extra args is used
        altSpec['ssharg'] = ''
        jobd = dbackup.Job('testJob', altSpec)
        self.assertEqual(jobd.sshArgs.port, 22)

        # Test to use sshport argument
        altSpec['sshport'] = 222
        jobd = dbackup.Job('testJob', altSpec)
        self.assertEqual(jobd.sshArgs.port, 222)