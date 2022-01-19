import unittest

import dbackup
from dbackup.location.factory import Factory
from dbackup.sshArgs import SshArgs
from pathlib import Path

class TestLocationFactory(unittest.TestCase):

    jobSpec = {
        'cert': str(Path(__file__).parent / 'data' / 'dummy_key.pub'),
        'source': 'gud@localhost:/tmp/source',
        'dest': '/tmp/dest',
        'ssharg': '-p 1234',
        'days': 10,
        'months': 5,
        'rsyncarg': '--fuzzy',
    }

    def test_FactorySsh(self):
        sshArgs = SshArgs(self.jobSpec)
        loc = Factory(self.jobSpec['source'], sshArgs)

        self.assertIsInstance(loc, dbackup.location.SshLocation)

    def test_FactoryLocal(self):
        sshArgs = SshArgs(self.jobSpec)
        loc = Factory(self.jobSpec['dest'], sshArgs)

        self.assertIsInstance(loc, dbackup.location.LocalLocation)