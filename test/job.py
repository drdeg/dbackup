import unittest
from pathlib import Path

import dbackup

class TestJob(unittest.TestCase):
    jobSpec = {
        'cert': str(Path(__file__).parent / 'data' / 'dummy_key.pub'),
        'source': 'gud@localhost:/tmp/source',
        'dest': '/tmp/dest',
        'ssharg': '-p 1234',
        'days': 10,
        'months': 5,
        'rsyncarg': '--fuzzy',
    }

    def test_instances(self):
        job = dbackup.Job('testJob', self.jobSpec)
        self.assertIsInstance(job.source, dbackup.location.SshLocation)
        self.assertIsInstance(job.dest, dbackup.location.LocalLocation)


    def test_SshArgs(self):
        expectedSshArgs = [
            '-i', str(Path(__file__).parent / 'data' / 'dummy_key.pub'),
            '-p', '1234',
            '-o', 'PubkeyAuthentication=yes',
            '-o', 'PreferredAuthentications=publickey'
        ]

        # Create a job
        job = dbackup.Job('testJob', self.jobSpec)
        self.assertListEqual(job.sshArgs, expectedSshArgs)

        return True

    def test_defaultSshPort(self):
        job = dbackup.Job('testJob', self.jobSpec)
        self.assertEqual(job.sshPort, 1234)

        altSpec = self.jobSpec.copy()

        # Test that extra args is used
        altSpec['ssharg'] = ''
        jobd = dbackup.Job('testJob', altSpec)
        self.assertEqual(jobd.sshPort, 22)

        # Test to use sshport argument
        altSpec['sshport'] = 222
        jobd = dbackup.Job('testJob', altSpec)
        self.assertEqual(jobd.sshPort, 222)
