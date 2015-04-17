'''
Created on Apr 16, 2015

@author: moloy
'''

import os
import yaml
import re

from crypt import Cryptic
import util

propertyFileLocation = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'conf')
currentWorkingDir = os.getcwd()

class PropertyLoader:
    
    def getFileNameWithPath(self, fileName):
        '''
        File location search path - 
        1. current working directory
        2. <openclos install dir>/jnpr/openclos/conf
        '''
        
        if os.path.isfile(os.path.join(currentWorkingDir, fileName)):
            return os.path.join(currentWorkingDir, fileName)
        elif os.path.isfile(os.path.join(propertyFileLocation, fileName)):
            return os.path.join(propertyFileLocation, fileName)
        else:
            print 'file: "%s" not found at 1. %s, 2. %s' % (fileName, propertyFileLocation, currentWorkingDir)            

    def loadProperty(self, fileName):
        if not file:
            return

        try:    
            with open(fileName, 'r') as fStream:
                return yaml.load(fStream)
        except (OSError, IOError) as e:
            print "File error:", e
        except (yaml.scanner.ScannerError) as e:
            print "YAML error:", e

    
class OpenClosProperty(PropertyLoader):
    def __init__(self, fileName = 'openclos.yaml', appName = None):
        fileNameWithPath = os.path.join(propertyFileLocation, fileName)
        self._properties = self.loadProperty(fileNameWithPath)
        
        if self._properties is not None:
            if 'dbUrl' in self._properties:
                if 'dbDialect' in self._properties:
                    print "Warning: dbUrl and dbDialect both exist. dbDialect ignored"
                # dbUrl is used by sqlite only
                self._properties['dbUrl'] = self.fixSqlliteDbUrlForRelativePath(self._properties['dbUrl'])
            elif 'dbDialect' in self._properties:
                dbPass = Cryptic ().decrypt ( self._properties['dbPassword'] )
                self._properties['dbUrl'] = self._properties['dbDialect'] + '://' + self._properties['dbUser'] + ':' + dbPass + '@' + self._properties['dbHost'] + '/' + self._properties['dbName'] 
            if 'outputDir' in self._properties:
                self._properties['outputDir'] = self.fixOutputDirForRelativePath(self._properties['outputDir'])
        util.loadLoggingConfig(appName = appName)

    def getProperties(self):
        return self._properties
                    
    def getDbUrl(self):
        if self._properties.get('dbUrl') is None or self._properties.get('dbUrl')  == '':
            raise ValueError('DB Url is empty')
        
        return self._properties['dbUrl'] 

    def fixSqlliteDbUrlForRelativePath(self, dbUrl):
        # sqlite:////absolute-path/sqllite3.db
        # sqlite:///relative-path/sqllite3.db
        match = re.match(r"sqlite:(\/+)(.*)\/(.*)", dbUrl)
        if match is not None:
            isRelative = (len(match.group(1)) == 3)
            if isRelative:
                relativeDir = match.group(2)
                absoluteDir = os.path.join(os.path.dirname(os.path.abspath(__file__)), relativeDir)
                dbUrl = 'sqlite:///' + absoluteDir + os.path.sep + match.group(3)
    
        return dbUrl

    def fixOutputDirForRelativePath(self, outputDir):
        # /absolute-path/out
        # relative-path/out
        if (os.path.abspath(outputDir) != outputDir):
            return os.path.join(os.path.dirname(os.path.abspath(__file__)), outputDir)
        else:
            return outputDir



class DeviceSku(PropertyLoader):
    def __init__(self, fileName = 'deviceFamily.yaml'):
        fileNameWithPath = super.getFileNameWithPath(fileName)


