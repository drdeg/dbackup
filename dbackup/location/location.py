import re
import os
import logging
import subprocess
from abc import abstractmethod

from ..helpers.errors import SshError

from .. import incomplete

class Location:
    """ Location is a class that handles local and remote RSYNC locations
    
        user@host:path/to/location

    """
    def __init__(self, spec, dynamichost = None, typeName = None, simulate = False):
        self.spec = spec
        #self.type = 'remote' if re.match(r'^[^@:]*@[^@:]*:.*$', spec) is not None else 'local'
        self.typeName = typeName

        self.simulate = simulate

    @property
    def isLocal(self):
        return self.typeName == 'local'
        
    @property
    def isRemote(self):
        return self.typeName == 'remote'

    @property
    def path(self):
        return self._path

    @path.setter
    def path(self, path):
        self._path = path

    @abstractmethod
    def rsyncPath(self, subpath = None):
        return None

    @abstractmethod
    def _createLocal(self) -> bool:
        """ Creates local location """
        return False

    @abstractmethod
    def create(self) -> bool:
        """ Creates the location """
        return False

    @abstractmethod
    def validate(self) -> bool:
        return False

    @abstractmethod
    def listDir(self):
        """ List directories in the location 
        
        Returns:
            A list of folder names: [ str ]
        """
        assert False, 'This method should be overloaded'
        return []

    def getBackups(self, includeAll = False):
        """ Get alist of backups in the location
        
        Normally, incomplete backups are excluded from the list
        unless includeAll is set to true

        Returns a list of backups or Non if no backups are found. 
        If an error occured, like ssh failure, False is returned
        """

        # List all files in dest folder
        folderList = self.listDir()

        if folderList is not None:
            # Filter out backup names
            if includeAll:
                dirNameRegex = re.compile(r'^\d{4}-\d{2}-\d{2}(' + incomplete.suffix + '|)$')
            else:
                dirNameRegex = re.compile(r'^\d{4}-\d{2}-\d{2}$')
            return list(filter(dirNameRegex.match, folderList))
        else:
            return None


    @abstractmethod
    def renameChild(self, oldName, newName):
        pass

    @abstractmethod
    def deleteChild(self, name):
        """ Removes a file/dir in the location and all sub-files/folders
        """
        pass