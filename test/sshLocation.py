import unittest
from pathlib import Path

import dbackup

class TestSshLocation(unittest.TestCase):

    userHostsFile = str(Path(__file__).parent / 'data' / 'known_hosts')

    jobSpec = {
        'cert': str(Path(__file__).parent / 'data' / 'dummy_key.pub'),
        'source': 'gud@localhost:/tmp/source',
        'dest': '/tmp/dest',
        'ssharg': '-p 1234 -o UserKnownHostsFile=' + userHostsFile,
        'days': 10,
        'months': 5,
        'rsyncarg': '--fuzzy',
    }

    def test_hostKeyFile(self):
        job = dbackup.Job('testJob', self.jobSpec)
        self.assertTrue('UserKnownHostsFile='+self.userHostsFile in job.sshArgs)
        self.assertEqual(job.source.hostKeyFile, self.userHostsFile)

    def test_sshPort(self):
        job = dbackup.Job('testJob', self.jobSpec)
        self.assertTrue('-p' in job.sshArgs)
        self.assertEqual(job.source.sshPort, 1234)

    def test_noHostKeyFile(self):
        jobSpec = self.jobSpec.copy()
        jobSpec['ssharg'] = '-p 1234'
        job = dbackup.Job('testJob', jobSpec)
        self.assertIsNone(job.source.hostKeyFile)
        self.assertEqual(job.source.sshPort, 1234)
