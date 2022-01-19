
from ..sshArgs import SshArgs
from . import LocalLocation, SshLocation
import re

# TODO: Refactor so that the entire job specification is available to the factory
def Factory( spec, sshArgs : SshArgs = None, simulate = False):

    if re.match(r'^[^@:]*@[^@:]*:.*$', spec) is not None:
        return SshLocation(spec, sshArgs = sshArgs, simulate = simulate)
    else:
        return LocalLocation(spec, simulate = simulate)