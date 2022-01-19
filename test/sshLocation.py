import unittest
from pathlib import Path

import dbackup
from dbackup.location.sshLocation import SshLocation
from dbackup.sshArgs import SshArgs

class TestSshLocation(unittest.TestCase):
    jobSpec = {
        'cert': str(Path(__file__).parent / 'data' / 'dummy_key.pub'),
        'source': 'gud@localhost:/tmp/source',
        'dest': '/tmp/dest',
        'ssharg': '-p 1234',
        'days': 10,
        'months': 5,
        'rsyncarg': '--fuzzy',
    }
    def test_sshCommand(self):
        sshArgs = SshArgs(self.jobSpec)
        src = SshLocation(self.jobSpec['source'], sshArgs, simulate=False)

        expectedSshCommand = [
            'ssh',
            '-i', '/home/david/git/dbackup/test/data/dummy_key.pub',
            '-l', 'gud',
            '-p', '1234',
            '-o', 'BatchMode=yes',
            'localhost',
            'test'
        ]

        self.assertEqual(src._buildSshCmd('test'), expectedSshCommand)
