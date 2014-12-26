'''
Created on Oct 29, 2014

@author: moloyc
'''
import logging
import os
import traceback
from threading import RLock, Event
import time

from jnpr.junos import Device as DeviceConnection
from jnpr.junos.factory import loadyaml
from jnpr.junos.exception import ConnectError, RpcError, CommitError, LockError
from jnpr.junos.utils.config import Config

from dao import Dao
from model import Pod, Device, InterfaceDefinition, AdditionalLink
from exception import DeviceError
from common import SingletonBase
from l3Clos import L3ClosMediation
import util
from netaddr import IPAddress, IPNetwork

moduleName = 'devicePlugin'
logger = None

junosEzTableLocation = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'conf', 'junosEznc')

class DeviceOperationInProgressCache(SingletonBase):
    def __init__(self):
        self.__cache = {}
        self.__lock = RLock()
        
    def isDeviceInProgress(self, deviceId):
        with self.__lock:
            return (self.__cache.has_key(deviceId))

    def doneDevice(self, deviceId):
        with self.__lock:
            return self.__cache.pop(deviceId, None)
    
    def checkAndAddDevice(self, deviceId):
        with self.__lock:
            if (self.__cache.has_key(deviceId)):
                return False
            else:
                self.__cache[deviceId] = time.time()
                return True 

class L2DataCollectorInProgressCache(DeviceOperationInProgressCache):
    ''' singleton class use class.getInstance()'''
    
class L3DataCollectorInProgressCache(DeviceOperationInProgressCache):
    ''' singleton class use class.getInstance()'''

class TwoStageConfigInProgressCache(DeviceOperationInProgressCache):
    ''' singleton class use class.getInstance()'''
    
class DeviceDataCollectorNetconf(object):
    '''
    Base class for any device data collector based on NetConf 
    Uses junos-eznc to connect to device
    '''
    def __init__(self, deviceId, conf = {}):
        global logger
        logger = util.getLogger(moduleName)
        if any(conf) == False:
            self.conf = util.loadConfig()
        else:
            self.conf = conf

        self.dao = None
        self.deviceId = deviceId
        self.deviceConnectionHandle = None

    def manualInit(self):
        if self.dao is None:
            self.dao = Dao(self.conf)
        if self.deviceId is not None:
            self.device = self.dao.getObjectById(Device, self.deviceId)
            self.deviceLogStr = 'device name: %s, ip: %s, id: %s' % (self.device.name, self.device.managementIp, self.device.id)
    
    def connectToDevice(self):
        '''
        :param dict deviceInfo:
            ip: ip address of the device
            username: device credential username
        :returns Device: Device, handle to device connection.
        '''
        if self.device.managementIp == None or self.device.username == None:
            raise ValueError('Device: %s, ip: %s, username: %s' % (self.device.id, self.device.managementIp, self.device.username))
        if self.device.encryptedPassword == None:
            raise ValueError('Device: %s, , ip: %s, password is None' % (self.device.id, self.device.managementIp))
        
        try:
            deviceIp = self.device.managementIp.split('/')[0]
            devicePassword = self.device.getCleartextPassword()
            deviceConnection = DeviceConnection(host=deviceIp, user=self.device.username, password=devicePassword)
            deviceConnection.open()
            logger.debug('Connected to device: %s' % (self.device.managementIp))
            self.deviceConnectionHandle = deviceConnection
            return deviceConnection
        except ConnectError as exc:
            logger.error('Device connection failure, %s' % (exc))
            self.deviceConnectionHandle = None
            raise DeviceError(exc)
        except Exception as exc:
            logger.error('Unknown error, %s' % (exc))
            logger.debug('StackTrace: %s' % (traceback.format_exc()))
            self.deviceConnectionHandle = None
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

    def startL2Report(self):
        try:
            self.manualInit()
            self.startCollectAndProcessLldp()
        except Exception as exc:
            logger.error('L2 data collection failed for %s, %s' % (self.deviceId, exc))
            raise
    
    def startCollectAndProcessLldp(self):
        if (self.collectionInProgressCache.checkAndAddDevice(self.device.id)):
            logger.debug('Started L2 data collection for %s' % (self.deviceLogStr))
            try:
                self.updateDeviceL2Status('processing')
                # use device level password for leaves that already went through staged configuration
                self.connectToDevice()
                lldpData = self.collectLldpFromDevice()
                goodBadCount = self.processLlDpData(lldpData) 

                self.validateDeviceL2Status(goodBadCount)
            except DeviceError as exc:
                logger.error('Collect LLDP data failed for %s, %s' % (self.deviceLogStr, exc))
                self.updateDeviceL2Status(None, error = exc)
            except Exception as exc:
                logger.error('Collect LLDP data failed for %s, %s' % (self.deviceLogStr, exc))
                self.updateDeviceL2Status('error', str(exc))
            finally:
                self.collectionInProgressCache.doneDevice(self.deviceId)
                logger.debug('Ended L2 data collection for %s' % (self.deviceLogStr))
                
        else:
            logger.debug('L2 data collection is already in progress for %s', (self.deviceLogStr))
            
    def validateDeviceL2Status(self, goodBadCount):
        effectiveLeafUplinkcountMustBeUp = self.device.pod.calculateEffectiveLeafUplinkcountMustBeUp()
        if (goodBadCount['goodUplinkCount'] < effectiveLeafUplinkcountMustBeUp):
            errorStr = 'Good uplink count: %d is less than required limit: %d' % \
                (goodBadCount['goodUplinkCount'], effectiveLeafUplinkcountMustBeUp)
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
            devicesToBeUpdated = []
            for link in lldpData:
                logger.debug('device1: %s, port1: %s, device2: %s, port2: %s' % (link.device1, link.port1, link.device2, link.port2))
                links.append({'device1': link.device1, 'port1': link.port1, 'device2': link.device2, 'port2': link.port2})
                
                device2 = self.dao.getUniqueObjectByName(Device, link.device2)
                if device2 is not None:
                    device2.deployStatus = 'deploy'
                    # only update l2Status for spine because leaf will get updated when we collect its L2 data
                    if device2.role == 'spine':
                        device2.l2Status = 'good'
                        device2.configStatus = 'good'
                    devicesToBeUpdated.append(device2)
                    
            logger.debug('End LLDP data collector for %s' % (self.deviceLogStr))

            if len(devicesToBeUpdated) > 0:
                self.dao.updateObjects(devicesToBeUpdated)

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

        modifiedObjects = []
        goodUplinkCount = 0
        badUplinkCount = 0
        additionalLinkCount = 0
        
        # check all the uplink ports connecting to spines according to cabling plan against lldp data.
        for uplinkPort in uplinkPorts:
            found = False
            peerPort = uplinkPort.peer
            lldpDataRemaining = []
            for link in lldpData:
                if link['port1'] == uplinkPort.name:
                    found = True
                    # case 1 (normal case): lldp agrees with cabling plan about the peer port
                    if peerPort is not None and peerPort.name == link['port2'] and peerPort.device.name == link['device2']:
                        goodUplinkCount += 1
                        uplinkPort.lldpStatus = 'good'
                        peerPort.lldpStatus = 'good'
                        modifiedObjects.append(uplinkPort)
                        modifiedObjects.append(peerPort)
                    # case 2: lldp says this port is connected to another port but cabling plan does not show this port connected to another port.
                    else:
                        badUplinkCount += 1
                        uplinkPort.lldpStatus = 'error'
                        modifiedObjects.append(uplinkPort)
                else:
                    # remove this found record because at the end of the outer loop
                    # we need to count how many orphaned records are left. Those are "extra links"
                    lldpDataRemaining.append(link)
            # candidate for next iteration
            lldpData = lldpDataRemaining
            
            # case 3: lldp does not have this port but cabling plan shows this port connected to another port.
            if found == False and peerPort is not None:
                badUplinkCount += 1
                uplinkPort.lldpStatus = 'error'
                modifiedObjects.append(uplinkPort)
            # case 4 (no-op): lldp does not have this port and cabling plan does not show this port is connected to another port.
            else:
                pass
                
        self.dao.updateObjects(modifiedObjects)
        
        # case 5: lldp has this port but cabling plan does not have this port. this is the case of "additional links"
        self.dao.Session().query(AdditionalLink).filter(AdditionalLink.device1 == self.device.name).delete()
        self.dao.Session().commit()
        additionalLinks = []
        for link in lldpData:
            additionalLinkCount += 1
            additionalLinks.append(AdditionalLink(self.device.name, link['port1'], link['device2'], link['port2'], 'error'))
        self.dao.createObjects(additionalLinks)
        
        logger.debug('Total uplink count: %d, good: %d, error: %d, additionalLink: %d', len(uplinkPorts), goodUplinkCount, badUplinkCount, additionalLinkCount)
        return {'goodUplinkCount': goodUplinkCount, 'badUplinkCount': badUplinkCount, 'additionalLinkCount': additionalLinkCount};

class L3DataCollector(DeviceDataCollectorNetconf):
    pass


class TwoStageConfigurator(L2DataCollector):
    '''
    In most of the cases configurator would execute in multi-tread env, so cannot use
    Dao created from parent thread. So no point in doing "init" from parent process.
    Perform manual "init" from  start2StageZtpConfig/startL2Report to make sure it is done 
    from child thread's context
    '''
    def __init__(self, deviceIp, conf = {}, dao = None, stopEvent = None):
        self.configurationInProgressCache = TwoStageConfigInProgressCache.getInstance()
        super(TwoStageConfigurator, self).__init__(None, conf)
        self.deviceIp = deviceIp
        self.deviceLogStr = 'device ip: %s' % (self.deviceIp)
        # at this point self.conf is initialized
        self.interval = util.getZtpStagedInterval(self.conf)
        self.attempt = util.getZtpStagedAttempt(self.conf)
        if stopEvent is not None:
            self.stopEvent = stopEvent
        else:
            self.stopEvent = Event()
            
    def manualInit(self):
        super(TwoStageConfigurator, self).manualInit()

    def updateSelfDeviceContext(self, device):
        self.device = device
        self.deviceId = self.device.id
        self.deviceLogStr = 'device name: %s, ip: %s, id: %s' % (self.device.name, self.device.managementIp, self.device.id)

    def updateDeviceConfigStatus(self, status, reason = None, error = None):
        '''Possible status values are  'processing', 'good', 'error' '''
        if error is None:
            self.device.configStatus = status
            self.device.configStatusReason = reason
        else:
            self.device.configStatus = 'error'
            self.device.configStatusReason = str(error.cause)
        self.dao.updateObjects([self.device])
        
    def start2StageConfiguration(self):
        try:
            # sanity check
            if self.interval is None or self.attempt is None:
                logger.error("ztpStagedInterval or ztpStagedAttempt is None: two stage configuration is disabled")
                return
                
            # sanity check
            if self.attempt == 0:
                logger.info("ztpStagedAttempt is 0: two stage configuration is disabled")
                return
                
            self.manualInit()
            self.collectLldpAndMatchDevice()
        except Exception as exc:
            logger.error('Two stage configuration failed for %s, %s' % (self.deviceIp, exc))
            raise
            
    def findPodByMgmtIp(self, deviceIp):
        logger.debug("Checking all pods for ip %s" % (deviceIp))
        pods = self.dao.getAll(Pod)
        for pod in pods:
            logger.debug("Checking pod[id='%s', name='%s']: %s" % (pod.id, pod.name, pod.managementPrefix))
            ipNetwork = IPNetwork(pod.managementPrefix)
            ipNetworkList = list(ipNetwork)
            start = ipNetworkList.index(ipNetwork.ip)
            end = start + len(pod.devices)
            ipList = ipNetworkList[start:end]
            deviceIpAddr = IPAddress(deviceIp)
            if deviceIpAddr in ipList:
                logger.debug("Found pod[id='%s', name='%s']" % (pod.id, pod.name))
                return pod
        
    def collectLldpAndMatchDevice(self):
        if (self.configurationInProgressCache.checkAndAddDevice(self.deviceIp)):
            # for real device the password is coming from pod
            pod = self.findPodByMgmtIp(self.deviceIp)
            if pod is None:
                logger.error("Couldn't find any pod containing %s" % (self.deviceLogStr))
                self.configurationInProgressCache.doneDevice(self.deviceIp)
                return
                
            tmpDevice = Device(self.deviceIp, None, 'root', pod.getCleartextPassword(), 'leaf', None, self.deviceIp, None)
            tmpDevice.id = self.deviceIp
            self.updateSelfDeviceContext(tmpDevice)
            
            logger.debug('Started two stage configuration for %s' % (self.deviceIp))
            
            for i in range(1, self.attempt+1):
                # wait first: this will replace the original delay design 
                logger.debug('Wait for %d seconds...' % (self.interval))
                # don't do unnecessary context switch
                if self.interval > 0:
                    self.stopEvent.wait(self.interval)
                    if self.stopEvent.is_set():
                        return
                        
                logger.debug('Connecting to %s: attempt %d' % (self.deviceIp, i))
                try:
                    self.connectToDevice()
                    logger.debug('Connected to %s' % (self.deviceIp))
                    break
                except Exception as exc:
                    pass

            if self.deviceConnectionHandle is None:
                logger.error('All %d attempts failed for %s' % (self.attempt, self.deviceIp))
                self.configurationInProgressCache.doneDevice(self.deviceIp)
                return
                
            try:
                self.device.family = self.deviceConnectionHandle.facts['model'].lower()
                lldpData = self.collectLldpFromDevice()
            except DeviceError as exc:
                logger.error('Collect LLDP data failed for %s, %s' % (self.deviceIp, exc))
            except Exception as exc:
                logger.error('Collect LLDP data failed for %s, %s' % (self.deviceIp, exc))

            device = self.findMatchedDevice(lldpData, self.device.family)
            if device is None:
                logger.info('Did not find good enough match for %s' % (self.deviceIp))
                self.configurationInProgressCache.doneDevice(self.deviceIp)
                return
            
            try:
                self.updateDeviceConfigStatus('processing')
                self.updateDeviceConfiguration()
                self.updateDeviceConfigStatus('good')
            except DeviceError as exc:
                logger.error('Two stage configuration failed for %s, %s' % (self.deviceLogStr, exc))
                self.updateDeviceConfigStatus(None, error = exc)
            except Exception as exc:
                logger.error('Two stage configuration failed for %s, %s' % (self.deviceLogStr, exc))
                self.updateDeviceConfigStatus('error', str(exc))
            finally:
                self.configurationInProgressCache.doneDevice(self.deviceIp)
                logger.debug('Ended two stage configuration for %s' % (self.deviceLogStr))
        else:
            logger.debug('Two stage configuration is already in progress for %s', (self.deviceLogStr))

    def filterRemotePortIfdInDb(self,lldpData, deviceFamily):
        ''' filter only remote ports that are  IFD configured in the DB '''
        uplinkNames = util.getPortNamesForDeviceFamily(deviceFamily, self.conf['deviceFamily'])['uplinkPorts']
        IfdLinks = []
        devicesToBeUpdated = []
        for link in lldpData:
            if link['port1'] in uplinkNames:
                ifd2 = self.dao.getIfdByDeviceNamePortName(link['device2'], link['port2'])
                if ifd2 is not None:
                    link['ifd2'] = ifd2
                    IfdLinks.append(link)
                    logger.debug('Found IFD deviceName: %s, portName: %s' % (link['device2'], link['port2']))
                    # in case remote is a plug-and-play leaf, we want to automatically turn its deployStatus to 'deploy'
                    ifd2.device.deployStatus = 'deploy'
                    # only update l2Status for spine because leaf will get updated when we collect its L2 data
                    if ifd2.device.role == 'spine':
                        ifd2.device.l2Status = 'good'
                        ifd2.device.configStatus = 'good'
                    devicesToBeUpdated.append(ifd2.device)
        logger.debug('Number of IFDs found from LLDP data is %d' % (len(IfdLinks)))

        if len(devicesToBeUpdated) > 0:
            self.dao.updateObjects(devicesToBeUpdated)

        return IfdLinks
        
    def findMatchedDevice(self, lldpData, deviceFamily):
        '''
        Process the raw LLDP data from device and match to a IpFabric and a Device
        :param dict lldpData:
            deivce1: local device (on which lldp was run)
            port1: local interface (on device1)
            device2: remote device
            port2: remote interface
        :param str deviceFamily: deviceFamily (qfx5100-96s-8q)
        :returns Device: 
        '''
        if lldpData is None:
            return
            
        matchedIfds = self.filterRemotePortIfdInDb(lldpData, deviceFamily)
        if len(matchedIfds) < 2:
            logger.info('Device: %s, number of matched IFD count is %d (too less), skipping findMatchedDevice' % (self.deviceIp, len(matchedIfds)))
            return
        
        # check if they belong to same IpFabric same Device
        # dict of probable fabric and device
        # key <device id> : value count of IFD found
        tentativeFabricDevice = {}
        for link in matchedIfds:
            remoteIfd = link['ifd2']
            # sanity check against links that are not according to the cabling plan
            if remoteIfd.peer is None:
                continue
            tentativeSelfDeviceId = remoteIfd.peer.device.id
            count = tentativeFabricDevice.get(tentativeSelfDeviceId)
            if count is not None:
                tentativeFabricDevice[tentativeSelfDeviceId] = count + 1
            else:
                tentativeFabricDevice[tentativeSelfDeviceId] = 1
        
        # Take max count as BEST match
        keyForMaxCount = max(tentativeFabricDevice.iterkeys(), key=lambda k: tentativeFabricDevice[k])
        maxCount = tentativeFabricDevice[keyForMaxCount]
        logger.debug('Best match device id: %s, matched uplink count: %d' % (keyForMaxCount, maxCount))
        if maxCount < 2:
            logger.info('Device: %s, number of matched uplink count is %d (too less), skipping findMatchedDevice' % (self.deviceIp, maxCount))
            return

        device = self.dao.getObjectById(Device, keyForMaxCount)
        mgmtNetwork = IPNetwork(device.pod.managementPrefix)
        device.managementIp = self.deviceIp + '/' + str(mgmtNetwork.prefixlen)
        # mark as 'deploy' automatically because this is a plug-and-play leaf
        device.deployStatus = 'deploy'
        self.dao.updateObjects([device])
        
        # Is BEST match good enough match
        effectiveLeafUplinkcountMustBeUp = device.pod.calculateEffectiveLeafUplinkcountMustBeUp()
        if maxCount >= effectiveLeafUplinkcountMustBeUp:
            self.updateSelfDeviceContext(device)
            return self.device
        else:
            logger.info('Number of matched uplink count: %s, is less than required effectiveLeafUplinkcountMustBeUp: %d' % (maxCount, effectiveLeafUplinkcountMustBeUp))
        

    def updateDeviceConfiguration(self):
        '''
        Device Connection should be open by now, no need to connect again 
        '''
        logger.debug('updateDeviceConfiguration for %s' % (self.deviceLogStr))
        l3ClosMediation = L3ClosMediation(conf = self.conf, dao = self.dao)
        config = l3ClosMediation.createLeafConfigFor2Stage(self.device)
        
        configurationUnit = Config(self.deviceConnectionHandle)

        try:
            configurationUnit.lock()
            logger.debug('Lock config for %s' % (self.deviceLogStr))

        except LockError as exc:
            logger.error('updateDeviceConfiguration failed for %s, LockError: %s, %s, %s' % (self.deviceLogStr, exc, exc.errs, exc.rpc_error))
            raise DeviceError(exc)

        try:
            # make sure no changes are taken from CLI candidate config left over
            configurationUnit.rollback() 
            logger.debug('Rollback any other config for %s' % (self.deviceLogStr))
            configurationUnit.load(config, format='text', overwrite=True)
            logger.debug('Load generated config as candidate, for %s' % (self.deviceLogStr))

            #print configurationUnit.diff()
            #print configurationUnit.commit_check()
            configurationUnit.commit()
            logger.info('Committed twoStage config for %s' % (self.deviceLogStr))
        except CommitError as exc:
            #TODO: eznc Error handling is not giving helpful error message
            logger.error('updateDeviceConfiguration failed for %s, CommitError: %s, %s, %s' % (self.deviceLogStr, exc, exc.errs, exc.rpc_error))
            configurationUnit.rollback() 
            raise DeviceError(exc)
        except Exception as exc:
            logger.error('updateDeviceConfiguration failed for %s, %s' % (self.deviceLogStr, exc))
            logger.debug('StackTrace: %s' % (traceback.format_exc()))
            configurationUnit.rollback() 
            raise DeviceError(exc)

        finally:
            configurationUnit.unlock()
            logger.debug('Unlock config for %s' % (self.deviceLogStr))



if __name__ == "__main__":
    #TODO: need to add integration test, hard to write unit tests
    #### TEST CODE, should not be executed
    #### .219 is the only device we have on which we can test
    #### please rollback changes from CLI after running this test
    #configurator = TwoStageConfigurator('192.168.48.219')
    #configurator.start2StageConfiguration()
    #### TEST CODE, should not be executed
    util.loadLoggingConfig(moduleName)
    
    l3ClosMediation = L3ClosMediation()
    pods = l3ClosMediation.loadClosDefinition()
    pod = l3ClosMediation.createPod('anotherPod', pods['anotherPod'])
    raw_input("pause...")
    leaf1 = l3ClosMediation.dao.Session.query(Device).filter(Device.name == 'clos-leaf-01').one()
    c = L2DataCollector(leaf1.id)
    c.startL2Report()
        
