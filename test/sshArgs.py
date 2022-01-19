import unittest
from pathlib import Path

import dbackup
from dbackup.sshArgs import SshArgs

class TestSshArgs(unittest.TestCase):

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
        sshArgs = SshArgs(self.jobSpec)
        self.assertTrue('UserKnownHostsFile='+self.userHostsFile in sshArgs)
        self.assertEqual(str(sshArgs.hostKeyFile), self.userHostsFile)

    def test_sshPort(self):
        sshArgs = SshArgs(self.jobSpec)
        self.assertTrue('-p' in sshArgs)
        self.assertEqual(sshArgs.port, 1234)

    def test_noHostKeyFile(self):
        jobSpec = self.jobSpec.copy()
        jobSpec['ssharg'] = '-p 1234'
        sshArgs = SshArgs(jobSpec)
        self.assertIsNone(sshArgs.hostKeyFile)
        self.assertEqual(sshArgs.port, 1234)
