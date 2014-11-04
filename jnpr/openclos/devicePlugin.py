'''
Created on Oct 29, 2014

@author: moloyc
'''
import logging
import os

import util
from jnpr.junos import Device as DeviceConnection
from jnpr.junos.factory import loadyaml
from jnpr.junos.exception import ConnectError, RpcError
from exception import DeviceError

moduleName = 'devicePlugin'
logging.basicConfig()
logger = logging.getLogger(moduleName)
logger.setLevel(logging.DEBUG)

junosEzTableLocation = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'conf', 'junosEznc')

class Netconf(object):
    '''
    Uses junos-eznc to connect to device
    '''

    def __init__(self, conf = {}):
        if any(conf) == False:
            self.conf = util.loadConfig()
            logger.setLevel(logging.getLevelName(self.conf['logLevel'][moduleName]))

        else:
            self.conf = conf
    
    def connectToDevice(self, deviceInfo):
        '''
        :param dict deviceInfo:
            ip: ip address of the device
            username: device credential username
            password: clear-text password used by ncclient
        :returns Device: Device, handle to device connection.
        '''
        if deviceInfo.get('ip') == None or deviceInfo.get('username') == None or deviceInfo.get('password') == None:
            raise ValueError('ip: %s, username: %s, password: xxxx' % (deviceInfo.get('ip'), deviceInfo.get('username')))
        
        try:
            device = DeviceConnection(host=deviceInfo['ip'], user=deviceInfo['username'], password=deviceInfo['password'])
            device.open()
            logger.debug('Connected to device: %s' % (deviceInfo['ip']))
            return device
        except ConnectError as exc:
            logger.error('Device connection failure, %s' % (exc))
            raise DeviceError(exc)
        except Exception as exc:
            logger.error('Unknown error, %s' % (exc))
            raise DeviceError(exc)
            
        
    def collectLldpFromDevice(self, deviceInfo):
        try:
            device = self.connectToDevice(deviceInfo)
            lldpTable = loadyaml(os.path.join(junosEzTableLocation, 'lldp.yaml'))['LLDPNeighborTable'] 
            table = lldpTable(device)
            lldpData = table.get()
            links = []
            for link in lldpData:
                logger.debug('device1: %s, port1: %s, device2: %s, port2: %s' % (link.device1, link.port1, link.device2, link.port2))
                links.append({'device1': link.device1, 'port1': link.port1, 'device2': link.device2, 'port2': link.port2})
            return links
        except RpcError as exc:
            logger.error('LLDP data collection failure, %s' % (exc))
            raise DeviceError(exc)
        except Exception as exc:
            logger.error('Unknown error, %s' % (exc))
            raise DeviceError(exc)
