'''
Created on Apr 16, 2015

@author: moloy
'''

import os
import yaml
import re
import logging.config

from crypt import Cryptic
from exception import InvalidConfiguration

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
            logger.error('file: "%s" not found at 1. %s, 2. %s' % (fileName, propertyFileLocation, currentWorkingDir))            

    def loadProperty(self, fileName):
        if not fileName:
            return

        try:    
            with open(fileName, 'r') as fStream:
                return yaml.load(fStream)
        except (OSError, IOError) as e:
            logger.error("File error: %s" % (e))
        except (yaml.scanner.ScannerError) as e:
            logger.error("YAML error: %s" % (e))

    
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

    def getProperties(self):
        return self._properties
                    
    def getDbUrl(self):
        if self._properties.get('dbUrl') is None or self._properties.get('dbUrl')  == '':
            raise InvalidConfiguration('DB Url is empty')
        
        return self._properties['dbUrl'] 

    def isSqliteUsed(self):
        return 'sqlite' in self._properties.get('dbUrl')

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



portNameRegx = re.compile(r"([a-z]+-\d\/\d\/\[)(\d{1,3})-(\d{1,3})(\])")
class DeviceSku(PropertyLoader):
    def __init__(self, fileName = 'deviceFamily.yaml'):
        self.skuDetail = {}
        self.threeStageSkuDetail = {}
        self.fiveStageSkuDetail = {}
        
        fileNameWithPath = self.getFileNameWithPath(fileName)
        skuDetail = self.loadProperty(fileNameWithPath)
        
        if skuDetail is not None and skuDetail.get('deviceFamily') is not None:
            self.skuDetail = skuDetail.get('deviceFamily')
            self.populateDeviceFamily(self.skuDetail)
            
        if skuDetail is not None and skuDetail.get('3Stage') is not None:
            self.threeStageSkuDetail = skuDetail.get('3Stage')
            self.populate3StageOverride(self.threeStageSkuDetail)

        if skuDetail is not None and skuDetail.get('5Stage') is not None:
            self.fiveStageSkuDetail = skuDetail.get('5Stage')
            self.populate5StageOverride(self.fiveStageSkuDetail)

    def populateDeviceFamily(self, skuDetail):
        for deviceFamily, value in skuDetail.iteritems():
            logger.debug(deviceFamily)
            for role, ports in value.iteritems():
                uplink = ports.get('uplinkPorts')
                if isinstance(uplink, list):
                    ports['uplinkPorts'] = self.portRegexListToList(uplink)
                else:
                    ports['uplinkPorts'] = self.portRegexToList(uplink)

                downlink = ports.get('downlinkPorts')
                if isinstance(downlink, list):
                    ports['downlinkPorts'] = self.portRegexListToList(downlink)
                else:
                    ports['downlinkPorts'] = self.portRegexToList(downlink)

                #logger.debug("\t%s" % (role))
                #logger.debug("\t\t%s" % (ports.get('uplinkPorts')))
                #logger.debug("\t\t%s" % (ports.get('downlinkPorts')))
        
    def populate3StageOverride(self, threeStage):
        self.populateDeviceFamily(threeStage)
    
    def populate5StageOverride(self, fiveStage):
        self.populateDeviceFamily(fiveStage)

    def getPortNamesForDeviceFamily(self, deviceFamily, role, topology = '3Stage'):
        if self.skuDetail is None:
            logger.error('deviceFamily.yaml was not loaded properly')
            return {'uplinkPorts': [], 'downlinkPorts': []}
        
        if deviceFamily is None or role is None:
            logger.error("No ports found, deviceFamily: %s, role: %s, topology: %s" % (deviceFamily, role, topology))
            return {'uplinkPorts': [], 'downlinkPorts': []}
        
        try:
            try:
                if topology == '3Stage':
                    return self.threeStageSkuDetail[deviceFamily][role]
            except KeyError as ke:
                pass
            return self.skuDetail[deviceFamily][role]
        except KeyError as ke:
            logger.error("No ports found, deviceFamily: %s, role: %s, topology: %s. KeyError: %s" % (deviceFamily, role, topology, ke))
        return {'uplinkPorts': [], 'downlinkPorts': []}

    def getSupportedDeviceFamily(self):
        '''
        :returns list: device model/family (exactly as it is appeared on junos)
    
        '''
        if not self.skuDetail:
            logger.error('deviceFamily.yaml was not loaded properly')
            raise InvalidConfiguration('deviceFamily.yaml was not loaded properly')
        return self.skuDetail.keys()

    def portRegexToList(self, portRegex):
        '''    
        Expands port regular expression to a list of port names
        :param string: 'et-0/0/[0-15]'
        :returns list: [xe-0/0/0, xe-0/0/1 ... xe-0/0/15]

        Currently it does not expands regex for fpc/pic, only port is expanded
        '''
        if not portRegex:
            return []
        
        portNames = []
        match = portNameRegx.match(portRegex)
        if match is None:
            raise InvalidConfiguration("Port name regular expression is not formatted properly: %s, example: xe-0/0/[0-10]" % (portRegex))
        
        preRegx = match.group(1)    # group index starts with 1, NOT 0
        postRegx = match.group(4)
        startNum = int(match.group(2))
        endNum = int(match.group(3))
        
        for id in range(startNum, endNum + 1):
            portNames.append(preRegx[:-1] + str(id) + postRegx[1:])
            
        return portNames
  
    def portRegexListToList(self, portRegexList):
        '''    
        Expands list of port regular expression to a list of port names
        :param list: ['xe-0/0/[0-10]', 'et-0/0/[0-3]']
        :returns list: [xe-0/0/0, xe-0/0/1 ... xe-0/0/10, et-0/0/0, et-0/0/1, et-0/0/2, et-0/0/3]

        Currently it does not expands regex for fpc/pic, only port is expanded
        '''

        portNames = []
        for portRegex in portRegexList:
            portNames += self.portRegexToList(portRegex)
            
        return portNames


'''
If you run OpenClos as integrated with ND, prior to calling loadLoggingConfig, you will call setFileHandlerFullPath 
to have logs stored in a non-default location. 
If you run OpenClos as standalone application, you don't need to call setFileHandlerFullPath. The logs are stored in 
default location which is the current directory where l3Clos.py/rest.py/trapd.py is called from.
'''
fileHandlerFullPath = ''
def setFileHandlerFullPath(fullPath):
    global fileHandlerFullPath
    fileHandlerFullPath = fullPath
    
def loadLoggingConfig(logConfFile = 'logging.yaml', appName = ''):
    logConf = getLoggingHandlers(logConfFile, appName)
    if logConf is not None:
        logging.config.dictConfig(logConf)
    
def getLoggingHandlers(logConfFile = 'logging.yaml', appName = ''):
    '''
    Loads global configuration and creates hash 'logConf'
    '''
    try:
        logConfStream = open(os.path.join(propertyFileLocation, logConfFile), 'r')
        logConf = yaml.load(logConfStream)

        if logConf is not None:
            handlers = logConf.get('handlers')
            if handlers is not None:
                for handlerName, handlerDict in handlers.items():
                    filename = handlerDict.get('filename')
                    if filename is not None:
                        global fileHandlerFullPath
                        # sanity check in case caller sets fileHandlerFullPath to None
                        # default location is the current directory where appName module is called from
                        if fileHandlerFullPath is None:
                            fileHandlerFullPath = ''
                        filename = filename.replace('%(fullPath)', fileHandlerFullPath)
                        filename = filename.replace('%(appName)', appName)
                        handlerDict['filename'] = filename
                            
            return logConf
    except (OSError, IOError) as e:
        print "File error:", e
    except (yaml.scanner.ScannerError) as e:
        print "YAML error:", e
    finally:
        logConfStream.close()
    
moduleName = 'propLoader'
loadLoggingConfig(appName = moduleName)
logger = logging.getLogger(moduleName)
