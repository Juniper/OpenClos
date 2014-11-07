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
from netaddr import IPAddress, IPNetwork, AddrFormatError

#__all__ = ['getPortNamesForDeviceFamily', 'expandPortName']
configLocation = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'conf')

def loadConfig(confFile = 'openclos.yaml'):
    '''
    Loads global configuration and creates hash 'conf'
    '''
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
                conf['dbUrl'] = conf['dbDialect'] + '://' + conf['dbUser'] + ':' + conf['dbPassword'] + '@' + conf['dbHost'] + '/' + conf['dbName'] 
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

def getPortNamesForDeviceFamily(deviceFamily, conf):
    '''
    returns all port names for a device family grouped by uplink/downlink
    ex - xe-0/0/0, xe-0/0/1 ... xe-0/0/47
    For some device family (QFX5100-24Q) there is no specific uplink/downlink, 
    for those it is just a list in the dict.
    
    :param str: deviceFamily -- example QFX5100-24Q
    :param dict: conf -- device family configuration in dict format, example in openclos.yaml
    :returns dict: portNames
        uplinkPorts: 
        downlinkPorts:
        ports: list of ports that are not tagged, example QFX5100-24Q 
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

def expandPortName(portName):
    '''    
    Expands portname regular expression to a list
    ex - [xe-0/0/0, xe-0/0/1 ... xe-0/0/47]
    Currently it does not expands all junos regex, only few limited 

    Keyword arguments:
    portName -- port name in junos regular expression, example: xe-0/0/[0-10]
    '''
    if portName is None or portName == '':
        return []
    
    error = "Port name regular expression is not formatted properly: %s, example: xe-0/0/[0-10]" % (portName)
    match = re.match(r"([a-z]+-\d\/\d\/\[)(\d{1,3})-(\d{1,3})(\])", portName)
    if match is None:
        raise ValueError(error)
    
    portNames = []
    preRegx = match.group(1)    # group index starts with 1, NOT 0
    postRegx = match.group(4)
    startNum = int(match.group(2))
    endNum = int(match.group(3))
    
    for id in range(startNum, endNum + 1):
        portNames.append(preRegx[:-1] + str(id) + postRegx[1:])
        
    return portNames

def isPlatformUbuntu():
    return 'ubuntu' in platform.platform().lower()

def isPlatformCentos():
    return 'centos' in platform.platform().lower()

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

def getMgmtIps(prefix, count):
    '''
    returns list of management IP for given number of devices
    
    Keyword arguments:
    prefix -- ip prefix, example 1.2.3.4/24
    count -- number of devices
    '''
    mgmtIps = []
    ipNetwork = IPNetwork(prefix)
    ipNetworkList = list(ipNetwork)
    start = ipNetworkList.index(ipNetwork.ip)
    end = start + count
    ipList = ipNetworkList[start:end]
    for ip in ipList:
        mgmtIps.append(str(ip) + '/' + str(ipNetwork.prefixlen))

    return mgmtIps
