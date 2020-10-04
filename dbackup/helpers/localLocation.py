from . import Location
import os
import logging
import shutil

class LocalLocation(Location):

    def __init__(self, spec, dynamichost = None, sshArgs = None):
        """

        Arguments:
            spec (str) :  path to location

        """
        #self.type = 'remote' if re.match(r'^[^@:]*@[^@:]*:.*$', spec) is not None else 'local'

        super().__init__(spec, dynamichost, sshArgs)

        self.path = spec

    #overload
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
                os.makedirs(self.path)
                return True
            except:
                logging.error('ERROR: Could not create directory '+self.path)
            return False


    def listDirs(self):
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
            shutil.rmtree(toPath)
        os.rename(fromPath, toPath)
