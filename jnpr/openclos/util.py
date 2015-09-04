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
from propLoader import propertyFileLocation

TWO_STAGE_CONFIGURATOR_DEFAULT_ATTEMPT=5
TWO_STAGE_CONFIGURATOR_DEFAULT_INTERVAL=30 # in seconds
TWO_STAGE_CONFIGURATOR_DEFAULT_VCP_LLDP_DELAY=40 # in seconds

    
def loadClosDefinition(closDefination = os.path.join(propertyFileLocation, 'closTemplate.yaml')):
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

def getImageNameForDevice(pod, device):
    if device.role == 'spine':
        return pod.spineJunosImage
    elif device.role == 'leaf':
        for leafSetting in pod.leafSettings:
            if leafSetting.deviceFamily == device.family:
                return leafSetting.junosImage
    
    return None

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
    
    sequenceNum = _matchFpcPicPort(interfaceName)
    if sequenceNum != None:
        return sequenceNum
    sequenceNum = _matchFakeName(interfaceName)
    if sequenceNum != None:
        return sequenceNum

    match = otherPortRegx.match(interfaceName)
    if match is not None:
        return int(interfaceName.encode('hex'), 16)

fpcPicPortRegx = re.compile(r"([a-z]+)-(\d)\/(\d)\/(\d{1,3})\.?(\d{0,2})")
def _matchFpcPicPort(interfaceName):
    match = fpcPicPortRegx.match(interfaceName)
    if match is not None:
        speed = match.group(1)
        fpc = match.group(2)
        pic = match.group(3)
        port = match.group(4)
        unit = match.group(5)
        if not unit:
            unit = 0
            
        if 'et' in speed:
            speedInt = 1
        elif 'xe' in speed:
            speedInt = 2
        elif 'ge' in speed:
            speedInt = 3
        else:
            speedInt = 4
        
        sequenceNum = 100000 * speedInt + 10000 * int(fpc) + 1000 * int(pic) + int(port)
        
        if unit != 0:
            sequenceNum = 100 * sequenceNum + int(unit)
        
        return sequenceNum
    
fakeNameRegxList = [(re.compile(r"uplink-(\d{1,3})\.?(\d{0,2})"), 90000000, 91000000),
                    (re.compile(r"access-(\d{1,3})\.?(\d{0,2})"), 92000000, 93000000)
                    ]
def _matchFakeName(interfaceName):
    for fakeNameRegx, intfStart, subIntfStart in fakeNameRegxList:
        match = fakeNameRegx.match(interfaceName)
        if match is not None:
            port = match.group(1)
            unit = match.group(2)
            if not unit:
                unit = 0
            
            sequenceNum = intfStart + int(port)
            
            if unit != 0:
                sequenceNum = subIntfStart + 100 * int(port) + int(unit)
            
            return sequenceNum

def getPortNumberFromName(interfaceName):
    match = fpcPicPortRegx.match(interfaceName)
    if match is not None:
        return match.group(4)

def replaceFpcNumberOfInterfaces(interfaceNames, newFpc):
    fixedInterfaceNames = []
    for interfaceName in interfaceNames:
        match = fpcRegx.match(interfaceName)
        if match is not None:
            fixedInterfaceNames.append(match.group(1) + '-' + newFpc + '/' + match.group(3))
    return fixedInterfaceNames

fpcRegx = re.compile(r"([a-z]+)-(\d)\/(.*)")
def replaceFpcNumberOfInterface(interfaceName, newFpc):
    match = fpcRegx.match(interfaceName)
    if match is not None:
        return match.group(1) + '-' + newFpc + '/' + match.group(3)
    
    
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
    
def stripNetmaskFromIpString(ipString):
    pos = ipString.find('/')
    if pos != -1:
        return ipString[:pos]
    else:
        return ipString

def stripPlusSignFromIpString(ipString):
    pos = ipString.find('+')
    if pos != -1:
        return ipString[:pos]
    else:
        return ipString
