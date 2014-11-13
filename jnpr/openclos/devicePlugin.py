'''
Created on Oct 29, 2014

@author: moloyc
'''
import logging
import os
import traceback
import threading
import time

import util
from jnpr.junos import Device as DeviceConnection
from jnpr.junos.factory import loadyaml
from jnpr.junos.exception import ConnectError, RpcError

from dao import Dao
from model import Device, InterfaceDefinition
from exception import DeviceError
from common import SingletonBase

moduleName = 'devicePlugin'
logging.basicConfig()
logger = logging.getLogger(moduleName)
logger.setLevel(logging.DEBUG)

junosEzTableLocation = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'conf', 'junosEznc')

class DataCollectorInProgressCache(SingletonBase):
    def __init__(self):
        self.__cache = {}
        self.__lock = threading.RLock()
        
    def isDeviceInProgress(self, deviceId):
        return (self.__cache.has_key(deviceId))

    def doneDevice(self, deviceId):
        return self.__cache.pop(deviceId, None)
    
    def checkAndAddDevice(self, deviceId):
        with self.__lock:
            if (self.__cache.has_key(deviceId)):
                return False
            else:
                self.__cache[deviceId] = time.time()
                return True 

class L2DataCollectorInProgressCache(DataCollectorInProgressCache):
    ''' singleton class use class.getInstance()'''
    
class L3DataCollectorInProgressCache(DataCollectorInProgressCache):
    ''' singleton class use class.getInstance()'''
    
class DeviceDataCollectorNetconf(object):
    '''
    Base class for any device data collector based on NetConf 
    Uses junos-eznc to connect to device
    '''
    def __init__(self, deviceId, conf = {}):
        if any(conf) == False:
            self.conf = util.loadConfig()
            logger.setLevel(logging.getLevelName(self.conf['logLevel'][moduleName]))
        else:
            self.conf = conf

        self.dao = None
        self.deviceId = deviceId

    def manualInit(self):
        if self.dao is None:
            self.dao = Dao(self.conf)
        self.device = self.dao.getObjectById(Device, self.deviceId)
        self.deviceLogStr = 'device name: %s, ip: %s, id: %s' % (self.device.name, self.device.managementIp, self.device.id)
    
    def connectToDevice(self):
        '''
        :param dict deviceInfo:
            ip: ip address of the device
            username: device credential username
            password: clear-text password used by ncclient
        :returns Device: Device, handle to device connection.
        '''
        if self.device.managementIp == None or self.device.username == None:
            raise ValueError('Device: %s, ip: %s, username: %s' % (self.device.id, self.device.managementIp, self.device.username))
        if self.device.password == None:
            raise ValueError('Device: %s, password is None' % (self.device.id))
        
        try:
            deviceIp = self.device.managementIp.split('/')[0]
            deviceConnection = DeviceConnection(host=deviceIp, user=self.device.username, password=self.device.password)
            deviceConnection.open()
            logger.debug('Connected to device: %s' % (self.device.managementIp))
            self.deviceConnectionHandle = deviceConnection
            return deviceConnection
        except ConnectError as exc:
            logger.error('Device connection failure, %s' % (exc))
            raise DeviceError(exc)
        except Exception as exc:
            logger.error('Unknown error, %s' % (exc))
            logger.debug('StackTrace: %s' % (traceback.format_exc()))
            raise DeviceError(exc)

class L2DataCollector(DeviceDataCollectorNetconf):
    '''
    In most of the cases collector would execute in multi-tread env, so cannot use
    Dao created from parent thread. So no point in doing "init" from parent process.
    Perform manual "init" from  start2StageZtpConfig/startL2Report to make sure it is done 
    from child thread's context
    '''
    def __init__(self, deviceId, conf = {}, dao = None):
        self.collectionInProgressCache = L2DataCollectorInProgressCache.getInstance()
        super(L2DataCollector, self).__init__(deviceId, conf)

    def manualInit(self):
        super(L2DataCollector, self).manualInit()

    def start2StageZtpConfig(self):
        pass
    
    def startL2Report(self):
        self.manualInit()
        self.startCollectAndProcessLldp()
    
    def startCollectAndProcessLldp(self):
        if (self.collectionInProgressCache.isDeviceInProgress(self.device.id)):
            logger.trace('Data collection is in progress for %s', (self.deviceLogStr))
            return
        
        if (self.collectionInProgressCache.checkAndAddDevice(self.device.id)):
            logger.debug('Started CollectAndProcessLldp for %s' % (self.deviceLogStr))
            self.updateDeviceL2Status('processing')
            try:
                self.connectToDevice()
                lldpData = self.collectLldpFromDevice()
                goodBadCount = self.processLlDpData(lldpData) 

                self.validateDeviceL2Status(goodBadCount)
            except DeviceError as exc:
                logger.error('Collect LLDP data failed for %s, %s' % (self.deviceLogStr, exc))
                self.updateDeviceL2Status(None, error = exc)
            finally:
                logger.debug('Ended CollectAndProcessLldp for %s' % (self.deviceLogStr))
                
        else:
            logger.trace('Data collection is in progress for %s', (self.deviceLogStr))
            
    def validateDeviceL2Status(self, goodBadCount):
        if (goodBadCount['goodUplinkCount'] < self.device.pod.leafUplinkcountMustBeUp):
            errorStr = 'Good uplink count: %d is less than required limit: %d' % \
                (goodBadCount['goodUplinkCount'], self.device.pod.leafUplinkcountMustBeUp)
            self.updateDeviceL2Status('error', errorStr)
        else:
            self.updateDeviceL2Status('good')

    def collectLldpFromDevice(self):
        logger.debug('Start LLDP data collector for %s' % (self.deviceLogStr))

        try:
            lldpTable = loadyaml(os.path.join(junosEzTableLocation, 'lldp.yaml'))['LLDPNeighborTable'] 
            table = lldpTable(self.deviceConnectionHandle)
            lldpData = table.get()
            links = []
            for link in lldpData:
                logger.debug('device1: %s, port1: %s, device2: %s, port2: %s' % (link.device1, link.port1, link.device2, link.port2))
                links.append({'device1': link.device1, 'port1': link.port1, 'device2': link.device2, 'port2': link.port2})
            
            logger.debug('End LLDP data collector for %s' % (self.deviceLogStr))
            return links
        except RpcError as exc:
            logger.error('LLDP data collection failure, %s' % (exc))
            raise DeviceError(exc)
        except Exception as exc:
            logger.error('Unknown error, %s' % (exc))
            logger.debug('StackTrace: %s' % (traceback.format_exc()))
            raise DeviceError(exc)

    def updateDeviceL2Status(self, status, reason = None, error = None):
        '''Possible status values are  'processing', 'good', 'error' '''
        if error is None:
            self.device.l2Status = status
            self.device.l2StatusReason = reason
        else:
            self.device.l2Status = 'error'
            self.device.l2StatusReason = str(error.cause)
        self.dao.updateObjects([self.device])
        
    def processLlDpData(self, lldpData):
        '''
        Process the raw LLDP data from device and updates IFD lldp status for each uplink
        :param dict lldpData:
            deivce1: local device (on which lldp was run)
            port1: local interface (on device1)
            device2: remote device
            port2: remote interface
        :returns dict: 
            goodUplinkCount: 
            badUplinkCount:
        '''
        uplinkPorts = self.dao.Session().query(InterfaceDefinition).filter(InterfaceDefinition.device_id == self.device.id).\
            filter(InterfaceDefinition.role == 'uplink').order_by(InterfaceDefinition.name_order_num).all()

        uplinkPortsDict = {}
        for port in uplinkPorts:
            uplinkPortsDict[port.name] = port
        
        modifiedObjects = []
        goodUplinkCount = 0
        badUplinkCount = 0

        for link in lldpData:
            uplinkPort = uplinkPortsDict.get(link['port1'])
            if uplinkPort is None:
                continue
            
            peerPort = uplinkPort.peer
            if peerPort is not None and peerPort.name == link['port2'] and peerPort.device.name == link['device2']:
                goodUplinkCount += 1
                uplinkPort.lldpStatus = 'good'
                peerPort.lldpStatus = 'good'
                modifiedObjects.append(uplinkPort)
                modifiedObjects.append(peerPort)
            else:
                badUplinkCount += 1
                uplinkPort.lldpStatus = 'error'
                modifiedObjects.append(uplinkPort)
        
        self.dao.updateObjects(modifiedObjects)
        logger.debug('Total uplink count: %d, good: %d, error: %d', len(uplinkPorts), goodUplinkCount, badUplinkCount)
        return {'goodUplinkCount': goodUplinkCount, 'badUplinkCount': badUplinkCount};

class L3DataCollector(DeviceDataCollectorNetconf):
    pass
