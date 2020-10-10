from . import Location
import os
import logging
import shutil

class LocalLocation(Location):

    def __init__(self, spec, dynamichost = None, sshArgs = None, simulate = False):
        """
        Arguments:
            spec (str) :  path to location

        """
        #self.type = 'remote' if re.match(r'^[^@:]*@[^@:]*:.*$', spec) is not None else 'local'

        super().__init__(spec, dynamichost, typeName='local', simulate=simulate)

        self.path = spec

    def __str__(self):
        return f'LocalLocation:{self.path}'

    def rsyncPath(self, subpath = None):
        return self.path if subpath is None else os.path.join(self.path, subpath)

    def validate(self):
        """ Validates that the location exists and is reachable """

        return os.path.isdir(self.spec)

    def create(self):

        if os.path.exists(self.path):
            return True
        else:
            logging.info("Creating local folder "+self.path)
            try:
                if not self.simulate:
                    os.makedirs(self.path)
                return True
            except:
                logging.error('ERROR: Could not create directory '+self.path)
            return False


    def listDir(self):
        """ Lists the directories in the location 

        Returns a list of the subdirectory names
        """
        try:
            # List files and filter out directories
            folderList = [o for o in os.listdir(self.path) if os.path.isdir(os.path.join(self.path, o)) ]
            return folderList if folderList else None
        except FileNotFoundError:
            logging.warning('No folders found at %s', self.path)
            return None


    def renameChild(self, fromName, toName):
        """ Renames a file/folder in location
        """
        
        assert fromName != toName

        fromPath = os.path.join(self.path, fromName)
        toPath = os.path.join(self.path, toName)
        logging.debug('Moving %s to %s', fromName, toName)
        if os.path.exists(toPath):
            # Remove old instance if it already exists
            logging.debug('Replacing backup %s', toPath)
            if not self.simulate:
                shutil.rmtree(toPath)
        if not self.simulate:
            os.rename(fromPath, toPath)

    def deleteChild(self, name):
        """ Removes a file/folder in the location """

        if isinstance(name, str):
            name = [name]
        try:
            for n in name:
                filePath = os.path.join(self.path, n)
                logging.debug('Removing ' + filePath)
                if not self.simulate:
                    shutil.rmtree(filePath)
            return True
        except PermissionError as e:
            logging.error('Permission denied: %s', e.filename)
        return False