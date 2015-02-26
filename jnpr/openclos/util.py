'''
Created on Aug 21, 2014

@author: moloyc
'''

import re
import os
import yaml
import platform
import datetime
import shutil
from netaddr import IPNetwork
import netifaces
import logging.config
from crypt import Cryptic

#__all__ = ['getPortNamesForDeviceFamily', 'expandPortName']
configLocation = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'conf')

TWO_STAGE_CONFIGURATOR_DEFAULT_ATTEMPT=5
TWO_STAGE_CONFIGURATOR_DEFAULT_INTERVAL=30 # in seconds
TWO_STAGE_CONFIGURATOR_DEFAULT_VCP_LLDP_DELAY=40 # in seconds

conf = None

def loadConfig(confFile = 'openclos.yaml', appName = None):
    '''
    Loads global configuration and creates hash 'conf'
    '''
    global conf
    
    if conf:
        return conf
    
    try:
        confStream = open(os.path.join(configLocation, confFile), 'r')
        conf = yaml.load(confStream)
        if conf is not None:
            if 'dbUrl' in conf:
                if 'dbDialect' in conf:
                    print "Warning: dbUrl and dbDialect both exist. dbDialect ignored"
                # dbUrl is used by sqlite only
                conf['dbUrl'] = fixSqlliteDbUrlForRelativePath(conf['dbUrl'])
            elif 'dbDialect' in conf:
                db_pass = Cryptic ().decrypt ( conf['dbPassword'] )
                conf['dbUrl'] = conf['dbDialect'] + '://' + conf['dbUser'] + ':' + db_pass + '@' + conf['dbHost'] + '/' + conf['dbName'] 
            if 'outputDir' in conf:
                conf['outputDir'] = fixOutputDirForRelativePath(conf['outputDir'])
        
    except (OSError, IOError) as e:
        print "File error:", e
        return None
    except (yaml.scanner.ScannerError) as e:
        print "YAML error:", e
        confStream.close()
        return None
    finally:
        pass
    
    loadLoggingConfig(appName = appName)
    return conf

def fixOutputDirForRelativePath(outputDir):
    # /absolute-path/out
    # relative-path/out
    if (os.path.abspath(outputDir) != outputDir):
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), outputDir)
    else:
        return outputDir

def fixSqlliteDbUrlForRelativePath(dbUrl):
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

def loadClosDefinition(closDefination = os.path.join(configLocation, 'closTemplate.yaml')):
    '''
    Loads clos definition from yaml file
    '''
    try:
        stream = open(closDefination, 'r')
        yamlStream = yaml.load(stream)
        
        return yamlStream
    except (OSError, IOError) as e:
        print "File error:", e
    except (yaml.scanner.ScannerError) as e:
        print "YAML error:", e
        stream.close()
    finally:
        pass


def getSupportedDeviceFamily(conf):
    '''
    :param dict: conf -- device family configuration in dict format, not the whole conf, conf['deviceFamily']
    :returns list: device model/family (exactly as it is appeared on junos)

    '''
    if conf is None:
        raise ValueError("Missing configuration data")
    return conf.keys()
    

def getPortNamesForDeviceFamily(deviceFamily, conf):
    '''
    returns all port names for a device family grouped by uplink/downlink
    ex - xe-0/0/0, xe-0/0/1 ... xe-0/0/47
    For some device family (qfx5100-24q-2p) there is no specific uplink/downlink, 
    for those it is just a list in the dict.
    
    :param str: deviceFamily -- example qfx5100-24q-2p
    :param dict: conf -- device family configuration in dict format, example in openclos.yaml
    :returns dict: portNames
        uplinkPorts: 
        downlinkPorts:
        ports: list of ports that are not tagged, example qfx5100-24q-2p 
    '''

    if conf is None:
        raise ValueError("Missing configuration data")
    
    if deviceFamily not in conf:
        raise ValueError("Unknown device family: %s" % (deviceFamily))
    
    portMapping = conf[deviceFamily]
    portNames = {'uplinkPorts': [], 'downlinkPorts': [], 'ports': []}
    if 'uplinkPorts' in portMapping:
        portNames['uplinkPorts'] = expandPortName(portMapping['uplinkPorts'])
    if 'downlinkPorts' in portMapping:
        portNames['downlinkPorts'] = expandPortName(portMapping['downlinkPorts'])
    if 'ports' in portMapping:
        portNames['ports'] = expandPortName(portMapping['ports'])
    return portNames


portNameRegx = re.compile(r"([a-z]+-\d\/\d\/\[)(\d{1,3})-(\d{1,3})(\])")
def expandPortName(portName):
    '''    
    Expands portname regular expression to a list
    ex - [xe-0/0/0, xe-0/0/1 ... xe-0/0/47]
    Currently it does not expands all junos regex, only few limited 

    Keyword arguments:
    portName -- port name in junos regular expression. 
                it could be a single string in format: xe-0/0/[0-10]
                or it could be a list of strings where each string is in format: ['xe-0/0/[0-10]', 'et-0/0/[0-3]']
    '''
    if not portName or portName == '':
        return []
    
    portList = []
    if isinstance(portName, list) == True:
        portList = portName
    else:
        portList.append(portName)
    
    portNames = []
    for port in portList:
        match = portNameRegx.match(port)
        if match is None:
            raise ValueError("Port name regular expression is not formatted properly: %s, example: xe-0/0/[0-10]" % (port))
        
        preRegx = match.group(1)    # group index starts with 1, NOT 0
        postRegx = match.group(4)
        startNum = int(match.group(2))
        endNum = int(match.group(3))
        
        for id in range(startNum, endNum + 1):
            portNames.append(preRegx[:-1] + str(id) + postRegx[1:])
        
    return portNames

def isPlatformUbuntu():
    #return 'ubuntu' in platform.platform().lower()
    result = os.popen("grep -i ubuntu /etc/*-release").read()
    return result is not None and len(result) > 0

def isPlatformCentos():
    #return 'centos' in platform.platform().lower()
    result = os.popen("grep -i centos /etc/*-release").read()
    return result is not None and len(result) > 0

def isPlatformWindows():
    return 'windows' in platform.platform().lower()

def backupDatabase(conf):
    if conf is not None and 'dbUrl' in conf:
        match = re.match(r"sqlite:\/\/\/(.*)", conf['dbUrl'])
        if match is not None:
            dbFileName = match.group(1)
            if dbFileName != '':
                timestamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
                backupDbFileName = dbFileName + '.' + timestamp
                shutil.copyfile(dbFileName, backupDbFileName)

def getMgmtIps(prefix, startingIP, mask, count):
    '''
    returns list of management IP for given number of devices
    
    Keyword arguments:
    prefix -- ip prefix, example 1.2.3.4/24
    count -- number of devices
    '''
    mgmtIps = []
    cidr = None
    if startingIP is not None and mask is not None:
        cidr = startingIP + '/' + str(mask)
    else:
        cidr = prefix
        
    if cidr is not None:
        ipNetwork = IPNetwork(cidr)
        ipNetworkList = list(ipNetwork)
        start = ipNetworkList.index(ipNetwork.ip)
        end = start + count
        ipList = ipNetworkList[start:end]
        for ip in ipList:
            mgmtIps.append(str(ip) + '/' + str(ipNetwork.prefixlen))

    return mgmtIps

def getMgmtIpsForLeaf():
    return []

def isZtpStaged(conf):
    if conf is not None and conf.get('deploymentMode') is not None:
        return conf['deploymentMode'].get('ztpStaged', False)
    return False

def getZtpStagedInterval(conf):
    if isZtpStaged(conf) == True:
        return conf['deploymentMode'].get('ztpStagedInterval', TWO_STAGE_CONFIGURATOR_DEFAULT_INTERVAL)
    else:
        return None
        
def getZtpStagedAttempt(conf):
    if isZtpStaged(conf) == True:
        return conf['deploymentMode'].get('ztpStagedAttempt', TWO_STAGE_CONFIGURATOR_DEFAULT_ATTEMPT)
    else:
        return None

def getTwoStageConfigurationCallback(conf):
    if isZtpStaged(conf) == True:
        return conf.get('twoStageConfigurationCallback')
    else:
        return None

def getVcpLldpDelay(conf):
    if isZtpStaged(conf) == True:
        return conf['deploymentMode'].get('ztpVcpLldpDelay', TWO_STAGE_CONFIGURATOR_DEFAULT_VCP_LLDP_DELAY)
    else:
        return None
    
def enumerateRoutableIpv4Addresses():
    addrs = []
    intfs = netifaces.interfaces()
    for intf in intfs:
        if intf != 'lo':
            addrDict = netifaces.ifaddresses(intf)
            ipv4AddrInfoList = addrDict.get(netifaces.AF_INET)
            if ipv4AddrInfoList is not None:
                for ipv4AddrInfo in ipv4AddrInfoList:
                    addrs.append(ipv4AddrInfo['addr'])
    return addrs

def loadLoggingConfig(logConfFile = 'logging.yaml', appName = None):
    logConf = getLoggingHandlers(logConfFile, appName)
    if logConf is not None:
        logging.config.dictConfig(logConf)
    
def getLoggingHandlers(logConfFile = 'logging.yaml', appName = None):
    '''
    Loads global configuration and creates hash 'logConf'
    '''
    try:
        logConfStream = open(os.path.join(configLocation, logConfFile), 'r')
        logConf = yaml.load(logConfStream)

        if logConf is not None:
            handlers = logConf.get('handlers')
            if handlers is not None:
                
                if appName is None:
                    removeLoggingHandler('file', logConf)
                                                        
                for handlerName, handlerDict in handlers.items():
                    filename = handlerDict.get('filename')
                    if filename is not None:
                        filename = filename.replace('%(appName)', appName)
                        handlerDict['filename'] = filename
                            
            return logConf
    except (OSError, IOError) as e:
        print "File error:", e
    except (yaml.scanner.ScannerError) as e:
        print "YAML error:", e
    finally:
        logConfStream.close()
    
    
def removeLoggingHandler(name, logConf):
    for key, logger in logConf['loggers'].iteritems():
        logger['handlers'].remove(name)

    logConf['handlers'].pop(name)

def getImageNameForDevice(pod, device):
    if device.role == 'spine':
        return pod.spineJunosImage
    elif device.role == 'leaf':
        for leafSetting in pod.leafSettings:
            if leafSetting.deviceFamily == device.family:
                return leafSetting.junosImage
    
    return None

def isSqliteUsed(conf):
    return 'sqlite' in conf.get('dbUrl')


fpcPicPortRegx = re.compile(r"[a-z]+-(\d)\/(\d)\/(\d{1,3})\.?(\d{0,2})")
fakeNameRegx = re.compile(r"uplink-(\d{1,3})\.?(\d{0,2})")
otherPortRegx = re.compile(r"[0-9A-Za-z]+\.?(\d{0,2})")

def interfaceNameToUniqueSequenceNumber(interfaceName):
    '''    
    :param str: name, examples: 
        IFD: et-0/0/1, et-0/0/0, et-0/0/101, lo0, irb, vme
        IFL: et-0/0/1.0, et-0/0/0.0, et-0/0/0.99, lo0.0
        IFD with fake name: uplink-0, uplink-1
        IFL with fake name: uplink-0.0, uplink-1.0, uplink-1.99
    '''
    if interfaceName is None or interfaceName == '':
        return None
    
    match = fpcPicPortRegx.match(interfaceName)
    if match is not None:
        fpc = match.group(1)
        pic = match.group(2)
        port = match.group(3)
        unit = match.group(4)
        if not unit:
            unit = 0
        
        sequenceNum = 10000 * int(fpc) + 1000 * int(pic) + int(port)
        
        if unit != 0:
            sequenceNum = 10000000 + 100 * sequenceNum + int(unit)
        
        return sequenceNum

    match = fakeNameRegx.match(interfaceName)
    if match is not None:
        port = match.group(1)
        unit = match.group(2)
        if not unit:
            unit = 0
        
        sequenceNum = 20000000 + int(port)
        
        if unit != 0:
            sequenceNum = 21000000 + 100 * int(port) + int(unit)
        
        return sequenceNum

    match = otherPortRegx.match(interfaceName)
    if match is not None:
        return int(interfaceName.encode('hex'), 16)
    
    
def getOutFolderPath(conf, ipFabric):
    if 'outputDir' in conf:
        outputDir = os.path.join(conf['outputDir'], ipFabric.id+'-'+ipFabric.name)
    else:
        outputDir = os.path.join('out', ipFabric.id+'-'+ipFabric.name)
    
    return outputDir

def createOutFolder(conf, ipFabric):
    path = getOutFolderPath(conf, ipFabric)
    if not os.path.exists(path):
        os.makedirs(path)
    
    return path

def deleteOutFolder(conf, ipFabric):
    path = getOutFolderPath(conf, ipFabric)
    shutil.rmtree(path, ignore_errors=True)

def getDbUrl():
    if conf is None:
        raise ValueError('Configuration is not loaded using "util.loadConfig"')
    elif conf.get('dbUrl') is None or conf.get('dbUrl')  == '':
        raise ValueError('DB Url is empty')
    
    return conf['dbUrl'] 

