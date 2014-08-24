'''
Created on Aug 21, 2014

@author: moloyc
'''

import re

__all__ = ['getPortNamesForDeviceFamily', 'expandPortName']

def getPortNamesForDeviceFamily(deviceFamily, conf):
    '''
    returns all port names for a device family grouped by uplink/downlink
    ex - xe-0/0/0, xe-0/0/1 ... xe-0/0/47
    For some device family (QFX5100-24Q) there is no specific uplink/downlink, 
    for those it is just a list in the dict.
    
    Keyword arguments:
    deviceFamily -- example QFX5100-24Q
    conf -- device family configuration in dict format, example in openclos.yaml
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
