'''
class ConfigError(Exception):
    """ Raised when a configuration error is detected """
    pass

'''
class ArgumentError(Exception):
    """ Raised when a configuration error is detected """
    def __init__(self, message):
        self.message = message

class SshError(Exception):
    """ Raised when SSH subprocess fucked up """
    def __init__(self, message):
        self.message = message
