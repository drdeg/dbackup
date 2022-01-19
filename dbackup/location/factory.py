
from . import LocalLocation, SshLocation
import re

# TODO: Refactor so that the entire job specification is available to the factory
def factory( spec, dynamichost = None, sshArgs = None, simulate = False):

    if re.match(r'^[^@:]*@[^@:]*:.*$', spec) is not None:
        return SshLocation(spec, dynamichost, sshArgs = sshArgs, simulate = simulate)
    else:
        return LocalLocation(spec,simulate = simulate)