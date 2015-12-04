'''
Created on Oct 29, 2014

@author: moloyc
'''
import os
from threading import RLock, Event
import time
import logging

from dao import Dao
from model import Pod, Device, InterfaceDefinition, AdditionalLink, BgpLink
from exception import DeviceConnectFailed, DeviceRpcFailed, L2DataCollectionFailed, L3DataCollectionFailed, TwoStageConfigurationFailed
from common import SingletonBase
from l3Clos import L3ClosMediation
from loader import OpenClosProperty, DeviceSku, loadLoggingConfig
import loader
import util
from exception import SkipCommit
from deviceConnector import CachedConnectionFactory, NetconfConnection

from netaddr import IPAddress, IPNetwork

moduleName = 'devicePlugin'
loadLoggingConfig(appName=moduleName)
logger = logging.getLogger(moduleName)

junosEzTableLocation = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'conf', 'junosEznc')

class DeviceOperationInProgressCache(SingletonBase):
    def __init__(self):
        self.__cache = {}
        self.__lock = RLock()
        
    def isDeviceInProgress(self, deviceId):
        with self.__lock:
            return self.__cache.has_key(deviceId)

    def doneDevice(self, deviceId):
        with self.__lock:
            return self.__cache.pop(deviceId, None)
    
    def checkAndAddDevice(self, deviceId):
        with self.__lock:
            if self.__cache.has_key(deviceId):
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
    def __init__(self, deviceId, conf={}, daoClass=Dao):
        if any(conf) == False:
            self._conf = OpenClosProperty(appName=moduleName).getProperties()
        else:
            self._conf = conf

        self.daoClass = daoClass
        self.pod = None
        self.deviceId = deviceId
        self.deviceSku = DeviceSku()


    def manualInit(self):
        self._dao = self.daoClass.getInstance()
        self._session = self._dao._getRawSession()
        
        if self.deviceId is not None:
            self.device = self._dao.getObjectById(self._session, Device, self.deviceId)
            self.deviceLogStr = 'device name: %s, ip: %s, id: %s' % (self.device.name, self.device.managementIp, self.device.id)
            self.pod = self.device.pod
    
class L2DataCollector(DeviceDataCollectorNetconf):
    '''
    In most of the cases collector would execute in multi-tread env, so cannot use
    Dao created from parent thread. So no point in doing "init" from parent process.
    Perform manual "init" from  start2StageZtpConfig/startL2Report to make sure it is done 
    from child thread's context
    '''
    def __init__(self, deviceId, conf={}, daoClass=Dao):
        self.collectionInProgressCache = L2DataCollectorInProgressCache.getInstance()
        super(L2DataCollector, self).__init__(deviceId, conf, daoClass)

    def manualInit(self):
        super(L2DataCollector, self).manualInit()

    def startL2Report(self):
        try:
            self.manualInit()
            self.startCollectAndProcessLldp()
        except Exception as exc:
            logger.error('L2 data collection failed for %s, %s', self.deviceId, exc)
            raise L2DataCollectionFailed(self.deviceId, exc)
        finally:
            if self._session:
                self._session.commit()
                self._session.remove()
    
    def startCollectAndProcessLldp(self):
        if self.collectionInProgressCache.checkAndAddDevice(self.device.id):
            logger.debug('Started L2 data collection for %s', self.deviceLogStr)
            try:
                if self.device.managementIp is not None:
                    self.updateDeviceL2Status('processing')
                    with CachedConnectionFactory.getInstance().connection(NetconfConnection,
                                                                          self.device.managementIp.split('/')[0],
                                                                          username=self.device.username,
                                                                          password=self.device.getCleartextPassword()) as connector:
                        lldpData = connector.getL2Neighbors()
                        
                    uplinkLdpData = self.filterUplinkFromLldpData(lldpData, self.device.family)
                    goodBadCount = self.processLlDpData(uplinkLdpData, self.getAllocatedConnectedUplinkIfds()) 
                    self.validateDeviceL2Status(goodBadCount)
                else:
                    # for some reason, we can't match the plug-n-play leaf to our inventory. so inventory doesn't have
                    # ip address for this leaf. in this case the leaf and all its links should be marked 'unknown'
                    self.updateDeviceL2Status('unknown')
                    self.updateUnknownIfdStatus(self.device.interfaces)
            except DeviceConnectFailed as exc:
                logger.error('Encountered device connect error for %s, %s', self.deviceLogStr, exc)
                self.updateDeviceL2Status(None, error=exc)
                # when we can't connect, mark the links 'unknown' because it is possible the data network is 
                # still working so we can't mark the links 'error'
                self.updateUnknownIfdStatus(self.device.interfaces)
                raise
            except DeviceRpcFailed as exc:
                logger.error('Encountered device RPC error for %s, %s', self.deviceLogStr, exc)
                self.updateDeviceL2Status('error', str(exc))
                self.updateBadIfdStatus(self.device.interfaces)
                raise
            except Exception as exc:
                logger.error('Collect LLDP data failed for %s, %s', self.deviceLogStr, exc)
                self.updateDeviceL2Status('error', str(exc))
                self.updateBadIfdStatus(self.device.interfaces)
                raise
            finally:
                self.collectionInProgressCache.doneDevice(self.deviceId)
                logger.debug('Ended L2 data collection for %s', self.deviceLogStr)
                
        else:
            logger.debug('L2 data collection is already in progress for %s', (self.deviceLogStr))
            
    def validateDeviceL2Status(self, goodBadCount):
        effectiveLeafUplinkcountMustBeUp = self.device.pod.calculateEffectiveLeafUplinkcountMustBeUp()
        if goodBadCount['goodUplinkCount'] < effectiveLeafUplinkcountMustBeUp:
            errorStr = 'Good uplink count: %d is less than required limit: %d' % \
                (goodBadCount['goodUplinkCount'], effectiveLeafUplinkcountMustBeUp)
            self.updateDeviceL2Status('error', errorStr)
        else:
            self.updateDeviceL2Status('good')

    def updateDeviceL2Status(self, status, reason=None, error=None):
        '''Possible status values are  'processing', 'good', 'error' '''
        if error is None:
            self.device.l2Status = status
            self.device.l2StatusReason = reason
        else:
            self.device.l2Status = 'error'
            self.device.l2StatusReason = str(error.cause)
        self._dao.updateObjectsAndCommitNow(self._session, [self.device])

    def updateDeviceConfigStatus(self, status, reason=None, error=None):
        '''Possible status values are  'processing', 'good', 'error' '''
        if error is None:
            self.device.configStatus = status
            self.device.configStatusReason = reason
        else:
            self.device.configStatus = 'error'
            self.device.configStatusReason = str(error.cause)
        self._dao.updateObjectsAndCommitNow(self._session, [self.device])
        
    def updateSpineStatusFromLldpData(self, spineIfds):
        devicesToBeUpdated = set()
        for spineIfd in spineIfds:
            spineDevice = spineIfd.device
            if spineDevice is not None and spineDevice.role == 'spine':
                spineDevice.deployStatus = 'deploy'
                spineDevice.l2Status = 'good'
                spineDevice.configStatus = 'good'
                devicesToBeUpdated.add(spineDevice)

        if len(devicesToBeUpdated) > 0:
            self._dao.updateObjectsAndCommitNow(self._session, devicesToBeUpdated)

    def getAllocatedConnectedUplinkIfds(self):
        uplinkIfds = self._session.query(InterfaceDefinition).filter(InterfaceDefinition.device_id == self.device.id).\
            filter(InterfaceDefinition.role == 'uplink').filter(InterfaceDefinition.peer != None).order_by(InterfaceDefinition.sequenceNum).all()
        
        allocatedUplinks = {}
        for uplink in uplinkIfds:
            # Hack plugNPlay-mixedLeaf:
            if self.device.family != 'unknown' and 'uplink-' in uplink.name:
                continue
            allocatedUplinks[uplink.name] = uplink
            
        logger.debug('%s, configured connected uplink count %s', self.deviceLogStr, len(allocatedUplinks.keys()))
        return allocatedUplinks
        
    def filterUplinkFromLldpData(self, lldpData, deviceFamily):
        ''' 
        On local device find uplink port names, filter only uplink ports, 
        :param dict lldpData:
            deivce1: local device (on which lldp was run)
            port1: local interface (on device1)
            device2: remote device
            port2: remote interface
        :param str deviceFamily: deviceFamily (qfx5100-96s-8q)
        '''
        
        if not lldpData:
            return lldpData
        
        uplinkNames = self.deviceSku.getPortNamesForDeviceFamily(deviceFamily, 'leaf')['uplinkPorts']

        filteredNames = set(uplinkNames).intersection(set(lldpData.keys()))
        filteredUplinks = {name:lldpData[name] for name in filteredNames}
        logger.debug('Number of uplink IFDs found from LLDP data is %d', len(filteredUplinks))
        return filteredUplinks

    def processLlDpData(self, uplinkLldpData, allocatedConnectedUplinkIfds):
        '''
        Process LLDP data from device and updates IFD lldp status for each uplink
        :param dict uplinksWithIfd:
            deivce1: local device (on which lldp was run)
            port1: local interface (on device1)
            device2: remote device
            port2: remote interface
            ifd2: remote IFD
        :returns dict: 
            goodUplinkCount: 
            badUplinkCount:
            additionalLinkCount
        '''

        lldpPortNames = set(uplinkLldpData.keys())
        allocatedConnectedPortNames = set(allocatedConnectedUplinkIfds.keys())
        logger.debug('lldpPortNames: %s', lldpPortNames)
        logger.debug('allocatedConnectedPortNames: %s', allocatedConnectedPortNames)
        
        goodIfds = []
        badIfds = []
        
        #case 1: link in lldp is not in allocatedConnected
        additional = lldpPortNames.difference(allocatedConnectedPortNames)
        self.persistAdditionalLinks([uplinkLldpData[name] for name in additional])
        logger.debug('additional: %s', additional)
        
        #case 2: ifd in allocatedConnected is not in lldp
        notConnected = allocatedConnectedPortNames.difference(lldpPortNames)
        logger.debug('not connected: %s', notConnected)
        badIfds += [allocatedConnectedUplinkIfds[name] for name in notConnected]
        
        connected = lldpPortNames.intersection(allocatedConnectedPortNames)
        for name in connected:
            link = uplinkLldpData[name]
            ifd = allocatedConnectedUplinkIfds[name]
            
            if link['device2'] == ifd.peer.device.name and link['port2'] == ifd.peer.name:
                #case 3: perfect match, connected as allocation logic
                logger.debug('connected: good: remote peer match: (%s, %s)', link['device2'], link['port2'])
                goodIfds.append(ifd)
            else:
                #case 4: bad connected, lldp and allocatedConnected portName match, but remote ports does not
                logger.debug('connected: bad: remote peer mismatch: (%s, %s) vs (%s, %s)', link['device2'], link['port2'], ifd.peer.device.name, ifd.peer.name)
                badIfds.append(ifd)
        
        self.updateGoodIfdStatus(goodIfds)
        self.updateBadIfdStatus(badIfds)
        
        logger.debug('Total uplink count: %d, good: %d, error: %d, additionalLink: %d', 
                     len(allocatedConnectedUplinkIfds), len(goodIfds), len(badIfds), len(additional))
        return {'goodUplinkCount': len(goodIfds), 'badUplinkCount': len(badIfds), 'additionalLinkCount': len(additional)}

    def updateGoodIfdStatus(self, ifds):
        modifiedObjects = []
        goodSpines = []
        for ifd in ifds:
            ifd.status = 'good'
            ifd.peer.status = 'good'
            goodSpines.append(ifd.peer)
            modifiedObjects.append(ifd)
            modifiedObjects.append(ifd.peer)

        self._dao.updateObjectsAndCommitNow(self._session, modifiedObjects)
        self.updateSpineStatusFromLldpData(goodSpines)
    
    def updateIfdStatus(self, ifds, status):
        modifiedObjects = []
        for ifd in ifds:
            ifd.status = status
            modifiedObjects.append(ifd)

        self._dao.updateObjectsAndCommitNow(self._session, modifiedObjects)

    def updateBadIfdStatus(self, ifds):
        self.updateIfdStatus(ifds, 'error')

    def updateUnknownIfdStatus(self, ifds):
        self.updateIfdStatus(ifds, 'unknown')

    def persistAdditionalLinks(self, links):
        '''
        lldp has this port but cabling plan does not have this port.
        '''
        self._session.query(AdditionalLink).filter(AdditionalLink.device1 == self.device.name).delete()
        additionalLinks = []
        for link in links:
            additionalLinks.append(AdditionalLink(self.device.name, link['port1'], link['device2'], link['port2'], 'error'))
        self._dao.createObjectsAndCommitNow(self._session, additionalLinks)

class L3DataCollector(DeviceDataCollectorNetconf):
    '''
    In most of the cases collector would execute in multi-tread env, so cannot use
    Dao created from parent thread. So no point in doing "init" from parent process.
    Perform manual "init" from startL3Report to make sure it is done
    from child thread's context.
    '''
    def __init__(self, deviceId, conf={}, daoClass=Dao, deviceAsn2NameMap={}):
        self.collectionInProgressCache = L3DataCollectorInProgressCache.getInstance()
        self.deviceAsn2NameMap = deviceAsn2NameMap
        super(L3DataCollector, self).__init__(deviceId, conf, daoClass)

    def manualInit(self):
        super(L3DataCollector, self).manualInit()

    def startL3Report(self):
        try:
            self.manualInit()
            self.startCollectAndProcessBgp()
        except Exception as exc:
            logger.error('L3 data collection failed for %s, %s', self.deviceId, exc)
            raise L3DataCollectionFailed(self.deviceId, exc)
        finally:
            if self._session:
                self._session.commit()
                self._session.remove()

    def startCollectAndProcessBgp(self):
        if self.collectionInProgressCache.checkAndAddDevice(self.device.id):
            logger.debug('Started L3 data collection for %s', self.deviceLogStr)
            try:
                if self.device.managementIp is not None:
                    self.updateDeviceL3Status('processing')

                    with CachedConnectionFactory.getInstance().connection(NetconfConnection,
                                                                          self.device.managementIp.split('/')[0],
                                                                          username=self.device.username,
                                                                          password=self.device.getCleartextPassword()) as connector:
                        bgpLinks = connector.getL3Neighbors()
                    #logger.debug(self.deviceAsn2NameMap)
                    self.processBgpData(bgpLinks)
                    self.updateDeviceL3Status('good')
                else:
                    # for some reason, we can't match the plug-n-play leaf to our inventory. so inventory doesn't have
                    # ip address for this leaf. in this case the leaf and all its links should be marked 'unknown'
                    self.updateDeviceL3Status('unknown')
                    self.updateBgpLinkStatus('unknown')
            except DeviceConnectFailed as exc:
                logger.error('Encountered device connect error for %s, %s', self.deviceLogStr, exc)
                self.updateDeviceL3Status(None, error=exc)
                # when we can't connect, mark the links 'unknown' because it is possible the data network is 
                # still working so we can't mark the links 'error'
                self.updateBgpLinkStatus('unknown')
                raise
            except DeviceRpcFailed as exc:
                logger.error('Encountered device RPC error for %s, %s', self.deviceLogStr, exc)
                self.updateDeviceL3Status('error', str(exc))
                self.updateBgpLinkStatus('bad')
                raise
            except Exception as exc:
                logger.error('Collect BGP data failed for %s, %s', self.deviceLogStr, exc)
                self.updateDeviceL3Status('error', str(exc))
                self.updateBgpLinkStatus('bad')
                raise
            finally:
                self.collectionInProgressCache.doneDevice(self.deviceId)
                logger.debug('Ended L3 data collection for %s', self.deviceLogStr)
        else:
            logger.debug('L3 data collection is already in progress for %s', self.deviceLogStr)

    def processBgpData(self, bgpLinks):
        for link in bgpLinks:
            link['device1'] = self.device.name
            # find device2's name by AS
            device2Obj = self.deviceAsn2NameMap.get(int(link['device2as']))
            #logger.debug("device2AS: %s, device2: %s",link['device2as'], device2Obj)

            if device2Obj is not None:
                link['device2'] = device2Obj.name
                link['device2Obj'] = device2Obj

        self.persistBgpLinks(bgpLinks)
        self.updateSpineStatusFromBgpData(bgpLinks)
        
    def persistBgpLinks(self, bgpLinks):
        # storing bgp data into database
        self._session.query(BgpLink).filter(BgpLink.device_id == self.device.id).delete()
        bgpObjects = []
        for link in bgpLinks:
            bgpObjects.append(BgpLink(self.device.pod.id, self.device.id, link))
        self._dao.createObjectsAndCommitNow(self._session, bgpObjects)

    def updateSpineStatusFromBgpData(self, bgpLinks):
        devicesToBeUpdated = set()
        for link in bgpLinks:
            device2 = link.get('device2Obj')
            if device2 is not None and device2.role == 'spine':
                device2.l3Status = 'good'
                device2.l3StatusReason = None
                devicesToBeUpdated.add(device2)
                
        if len(devicesToBeUpdated) > 0:
            self._dao.updateObjectsAndCommitNow(self._session, devicesToBeUpdated)
            
    def updateDeviceL3Status(self, status, reason=None, error=None):
        '''Possible status values are  'processing', 'good', 'error' '''
        if error is None:
            self.device.l3Status = status
            self.device.l3StatusReason = reason
        else:
            self.device.l3Status = 'error'
            self.device.l3StatusReason = str(error.cause)
        self._dao.updateObjectsAndCommitNow(self._session, [self.device])

    def updateBgpLinkStatus(self, status):
        self._session.query(BgpLink).filter(BgpLink.device_id == self.device.id).update({'link_state': status})

class TwoStageConfigurator(L2DataCollector):
    '''
    In most of the cases configurator would execute in multi-tread env, so cannot use
    Dao created from parent thread. So no point in doing "init" from parent process.
    Perform manual "init" from  start2StageZtpConfig/startL2Report to make sure it is done 
    from child thread's context
    '''
    def __init__(self, deviceIp, conf={}, daoClass=Dao, stopEvent=None):
        self.configurationInProgressCache = TwoStageConfigInProgressCache.getInstance()
        super(TwoStageConfigurator, self).__init__(None, conf, daoClass)
        self.deviceIp = deviceIp
        self.deviceLogStr = 'device ip: %s' % (self.deviceIp)
        # at this point self._conf is initialized
        self.interval = util.getZtpStagedInterval(self._conf)
        self.attempt = util.getZtpStagedAttempt(self._conf)
        self.vcpLldpDelay = util.getVcpLldpDelay(self._conf)
        
        if stopEvent is not None:
            self.stopEvent = stopEvent
        else:
            self.stopEvent = Event()
        
    def manualInit(self):
        super(TwoStageConfigurator, self).manualInit()
        
        self.pod = self.findPodByMgmtIp(self.deviceIp)
        if self.pod is None:
            logger.error("Couldn't find any pod containing %s", self.deviceLogStr)
            self.configurationInProgressCache.doneDevice(self.deviceIp)
            return False
        return True

    def updateSelfDeviceContext(self, device):
        self.device = device
        self.deviceId = self.device.id
        self.deviceLogStr = 'device name: %s, ip: %s, id: %s' % (self.device.name, self.device.managementIp, self.device.id)

    def updateDeviceConfigStatus(self, status, reason=None, error=None):
        '''Possible status values are  'processing', 'good', 'error' '''
        if error is None:
            self.device.configStatus = status
            self.device.configStatusReason = reason
        else:
            self.device.configStatus = 'error'
            self.device.configStatusReason = str(error.cause)
        self._dao.updateObjectsAndCommitNow(self._session, [self.device])
        
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
                
            if self.manualInit():
                self.collectLldpAndMatchDevice()
        except Exception as exc:
            logger.error('Two stage configuration failed for %s, %s', self.deviceIp, exc)
            raise TwoStageConfigurationFailed(self.deviceId, exc)
        finally:
            if self._session:
                self._session.commit()
                self._session.remove()
            
    def findPodByMgmtIp(self, deviceIp):
        logger.debug("Checking all pods for ip %s", deviceIp)
        pods = self._dao.getAll(self._session, Pod)
        for pod in pods:
            logger.debug("Checking pod[id='%s', name='%s']: %s", pod.id, pod.name, pod.managementPrefix)
            ipNetwork = IPNetwork(pod.managementPrefix)
            ipNetworkList = list(ipNetwork)
            start = ipNetworkList.index(ipNetwork.ip)
            end = start + len(pod.devices)
            ipList = ipNetworkList[start:end]
            deviceIpAddr = IPAddress(deviceIp)
            if deviceIpAddr in ipList:
                logger.debug("Found pod[id='%s', name='%s']", pod.id, pod.name)
                return pod
        
    def filterUplinkAppendRemotePortIfd(self, lldpData, deviceFamily):
        ''' 
        On local device find uplink port names, filter only uplink ports, 
        get remote ports that has Device + IFD configured in the DB 
        :returns list of dict: lldpData for uplinks only
            deivce1: local device (on which lldp was run)
            port1: local interface (on device1)
            device2: remote device
            port2: remote interface
            ifd2: remote IFD from db
        '''
        if not lldpData:
            logger.debug('NO LLDP data found for device: %s', self.deviceIp)
            return lldpData

        uplinkNames = self.deviceSku.getPortNamesForDeviceFamily(deviceFamily, 'leaf')['uplinkPorts']
        upLinks = []
        for link in lldpData.values():
            if link['port1'] in uplinkNames:
                ifd2 = self._dao.getIfdByDeviceNamePortName(self._session, link['device2'], link['port2'])
                if ifd2 is not None:
                    link['ifd2'] = ifd2
                    upLinks.append(link)
                    logger.debug('Found IFD deviceName: %s, portName: %s', link['device2'], link['port2'])
        logger.debug('Number of uplink IFDs found from LLDP data is %d', len(upLinks))
        return upLinks

    def collectLldpAndMatchDevice(self):
        if self.configurationInProgressCache.checkAndAddDevice(self.deviceIp):
            # for real device the password is coming from pod
            tmpDevice = Device(self.deviceIp, None, 'root', self.pod.getCleartextPassword(), 'leaf', None, self.deviceIp, None)
            tmpDevice.id = self.deviceIp
            self.updateSelfDeviceContext(tmpDevice)
            
            logger.debug('Started two stage configuration for %s', self.deviceIp)
            
            for i in range(1, self.attempt+1):
                # wait first: this will replace the original delay design 
                logger.debug('Wait for %d seconds...', self.interval)
                # don't do unnecessary context switch
                if self.interval > 0:
                    self.stopEvent.wait(self.interval)
                    if self.stopEvent.is_set():
                        return
                        
                logger.debug('Connecting to %s: attempt %d', self.deviceIp, i)
                try:
                    with CachedConnectionFactory.getInstance().connection(NetconfConnection,
                        self.device.managementIp.split('/')[0], username=self.device.username,
                        password=self.device.getCleartextPassword()) as connector:
                        # not using the connection, just making sure connection succeeds
                        # eventually it will be put in to cache for later use
                        pass
                    logger.debug('Connected to %s', self.deviceIp)
                    break
                except Exception as exc:
                    if i == self.attempt:
                        logger.error('All %d attempts failed for %s', self.attempt, self.deviceIp)
                        self.configurationInProgressCache.doneDevice(self.deviceIp)
                        raise DeviceConnectFailed('All %d attempts failed for %s' % (self.attempt, self.deviceIp))
                
            try:
                with CachedConnectionFactory.getInstance().connection(NetconfConnection,
                    self.device.managementIp.split('/')[0], username=self.device.username,
                    password=self.device.getCleartextPassword()) as connector:

                    self.device.family = connector.getDeviceFamily()
                    self.device.serialNumber = connector.getDeviceSerialNumber()
                    self.runPreLldpCommands(connector)
                    lldpData = connector.getL2Neighbors()

            except Exception as exc:
                logger.error('Failed to execute deleteVcpPorts for %s, %s', self.deviceIp, exc)
                raise DeviceRpcFailed('Failed to execute deleteVcpPorts %s' % (self.deviceIp), exc)

            uplinksWithIfds = self.filterUplinkAppendRemotePortIfd(lldpData, self.device.family)
            self.updateSpineStatusFromLldpData([x['ifd2'] for x in uplinksWithIfds])

            device = self.findMatchedDevice(uplinksWithIfds)
            if device is None:
                logger.info('Did not find good enough match for %s', self.deviceIp)
                self.configurationInProgressCache.doneDevice(self.deviceIp)
                return
            
            self.fixInterfaces(device, self.device.family, uplinksWithIfds)
            # persist serialNumber
            device.serialNumber = self.device.serialNumber
            self._dao.updateObjectsAndCommitNow(self._session, [device])
            self.updateSelfDeviceContext(device)

            try:
                with CachedConnectionFactory.getInstance().connection(NetconfConnection,
                    self.device.managementIp.split('/')[0], username=self.device.username,
                    password=self.device.getCleartextPassword()) as connector:
                    try:
                        self.runPostLldpCommands(connector)
                    except SkipCommit:
                        self.updateDeviceConfigStatus('good')
                        return
                self.updateDeviceConfigStatus('processing')
                self.updateDeviceConfiguration()
                self.updateDeviceConfigStatus('good')
            except DeviceRpcFailed as exc:
                logger.error('Two stage configuration failed for %s, %s', self.deviceLogStr, exc)
                self.updateDeviceConfigStatus(None, error=exc)
                raise
            except Exception as exc:
                logger.error('Two stage configuration failed for %s, %s', self.deviceLogStr, exc)
                self.updateDeviceConfigStatus('error', str(exc))
                raise
            finally:
                self.releaseConfigurationInProgressLock(self.deviceIp)
                logger.debug('Ended two stage configuration for %s', self.deviceLogStr)
        else:
            logger.debug('Two stage configuration is already in progress for %s', (self.deviceLogStr))
    
    def releaseConfigurationInProgressLock(self, deviceIp):
        self.configurationInProgressCache.doneDevice(deviceIp)
        
    def runPreLldpCommands(self, deviceConnection):
        self.deleteVcpPortForEx(self.device.family, deviceConnection)
        
    def runPostLldpCommands(self, deviceConnection):
        pass
    
    def deleteVcpPortForEx(self, deviceFamily, deviceConnection):
        if 'ex4300-' not in deviceFamily:
            return

        deviceConnection.deleteVCPort([(1, 0), (1, 1), (1, 2), (1, 3)])
        # Wait for some time get lldp advertisement on et-* ports
        # default advertisement interval 30secs
        logger.debug('Wait for vcpLldpDelay: %d seconds...', self.vcpLldpDelay)
        self.stopEvent.wait(self.vcpLldpDelay)        

    def fixInterfaces(self, device, deviceFamily, uplinksWithIfd):
        '''
        Fix all plug-n-play leaf stuff, not needed if deviceFamily is unchanged
        :param Device device: matched device found in db
        :param str deviceFamily: deviceFamily (qfx5100-96s-8q)
        :param dict uplinksWithIfd: lldp links for uplink
        '''
        if device.family == deviceFamily:
            logger.debug('DeviceFamily(%s) is not changed, nothing to fix', deviceFamily)
            return
        
        logger.info('DeviceFamily is changed, from: %s, to: %s', device.family, deviceFamily)
        device.family = deviceFamily
        self._dao.updateObjectsAndCommitNow(self._session, [device])
        self.fixAccessPorts(device)
        self.fixUplinkPorts(device, uplinksWithIfd)

    def fixAccessPorts(self, device):
        # While leaf devices are created access ports are not created to save resources 
        pass
        
    def fixUplinkPorts(self, device, lldpUplinksWithIfd):
        '''
        :param dict lldpUplinksWithIfd: lldp links for uplink
            deivce1: local device (on which lldp was run)
            port1: local interface (on device1)
            device2: remote device
            port2: remote interface
            ifd2: remote IFD from db
        '''
        if lldpUplinksWithIfd is None or len(lldpUplinksWithIfd) == 0:
            logger.warn('NO LLDP lldpUplinksWithIfd, skipping fixUplinkPorts')
            return

        updateList = []
        uplinkNamesBasedOnDeviceFamily = self.deviceSku.getPortNamesForDeviceFamily(device.family, 'leaf')['uplinkPorts']
        # hack :( needed to keep the sequence proper in case2, if device changed from ex to qfx
        self.markAllUplinkIfdsToUplink(device)
        
        # case1: fix IFDs based on lldp data
        fixedIfdIds = {}
        for link in lldpUplinksWithIfd:
            spineIfd = link['ifd2']
            peerLeafIfd = spineIfd.peer 
            # sanity check against links that are not according to the cabling plan
            if peerLeafIfd is None:
                continue
            updateList += self.fixIfdIflName(peerLeafIfd, link['port1'])
            fixedIfdIds[peerLeafIfd.id] = True 
            uplinkNamesBasedOnDeviceFamily.remove(peerLeafIfd.name)
            
        # case2: fix remaining IFDs based on device family
        allocatedUplinkIfds = self._session.query(InterfaceDefinition).filter(InterfaceDefinition.device_id == device.id).\
            filter(InterfaceDefinition.role == 'uplink').filter(InterfaceDefinition.peer != None).order_by(InterfaceDefinition.sequenceNum).all()
        
        listIndex = 0
        for allocatedIfd in allocatedUplinkIfds:
            if not fixedIfdIds.get(allocatedIfd.id):
                if uplinkNamesBasedOnDeviceFamily:
                    updateList += self.fixIfdIflName(allocatedIfd, uplinkNamesBasedOnDeviceFamily.pop(0))
                else:
                    updateList += self.fixIfdIflName(allocatedIfd, 'uplink-' + str(listIndex))
            listIndex += 1
        
        logger.debug('Number of uplink IFD + IFL fixed: %d', len(updateList))
        self._dao.updateObjectsAndCommitNow(self._session, updateList)

    def markAllUplinkIfdsToUplink(self, device):
        if device is None:
            return
        uplinkIfds = self._session.query(InterfaceDefinition).filter(InterfaceDefinition.device_id == device.id).\
            filter(InterfaceDefinition.role == 'uplink').order_by(InterfaceDefinition.sequenceNum).all()
        
        listIndex = 0
        for allocatedIfd in uplinkIfds:
            allocatedIfd.updateName('uplink-' + str(listIndex))
            listIndex += 1
            
    def fixIfdIflName(self, ifd, name):
        if ifd is None:
            return []
        ifd.updateName(name)
        logger.debug("Fixed device: %s, uplink port: %s", ifd.device.name, ifd.name)
        updateList = [ifd]

        for ifl in ifd.layerAboves:
            ifl.updateName(ifd.name + '.0')
            updateList.append(ifl)
            logger.debug("Fixed device: %s, uplink port: %s", ifd.device.name, ifl.name)
        
        return updateList
        
    def findMatchedDevice(self, uplinksWithIfd):
        '''
        Process LLDP data from device and match to a Device
        :param dict uplinksWithIfd:
            deivce1: local device (on which lldp was run)
            port1: local interface (on device1)
            device2: remote device
            port2: remote interface
            ifd2: remote IFD
        :returns Device: 
        '''
            
        if uplinksWithIfd is None:
            logger.error('Device: %s, no matched uplink IFD, skipping findMatchedDevice', self.deviceIp, len(uplinksWithIfd))
            return
        elif len(uplinksWithIfd) < 2:
            logger.error('Device: %s, number of matched uplink IFD count: %d, too less to continue findMatchedDevice, skipping', self.deviceIp, len(uplinksWithIfd))
            return
        
        # check if they belong to same IpFabric same Device
        # dict of probable fabric and device
        # key <device id> : value count of IFD found
        tentativeFabricDevice = {}
        for link in uplinksWithIfd:
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
        logger.debug('Best match device id: %s, matched uplink count: %d', keyForMaxCount, maxCount)
        if maxCount < 2:
            logger.info('Device: %s, number of matched uplink count is %d (too less), skipping findMatchedDevice', self.deviceIp, maxCount)
            return

        device = self._dao.getObjectById(self._session, Device, keyForMaxCount)
        mgmtNetwork = IPNetwork(device.pod.managementPrefix)
        device.managementIp = self.deviceIp + '/' + str(mgmtNetwork.prefixlen)
        # mark as 'deploy' automatically because this is a plug-and-play leaf
        device.deployStatus = 'deploy'
        self._dao.updateObjectsAndCommitNow(self._session, [device])
        logger.debug('updated deployStatus for name: %s, id:%s, deployStatus: %s', device.name, device.id, device.deployStatus)
        
        # Is BEST match good enough match
        effectiveLeafUplinkcountMustBeUp = device.pod.calculateEffectiveLeafUplinkcountMustBeUp()
        if maxCount >= effectiveLeafUplinkcountMustBeUp:
            return device
        else:
            logger.info('Number of matched uplink count: %s, is less than required effectiveLeafUplinkcountMustBeUp: %d', maxCount, effectiveLeafUplinkcountMustBeUp)
        

    def getDeviceConfig(self):
        l3ClosMediation = L3ClosMediation(conf=self._conf)
        config = l3ClosMediation.createLeafConfigFor2Stage(self.device)
        # l3ClosMediation used seperate db sessions to create device config
        # expire device from current session for lazy load with committed data
        self._session.expire(self.device)
        return config
        
    def updateDeviceConfiguration(self):
        logger.debug('updateDeviceConfiguration for %s', self.deviceLogStr)
        config = self.getDeviceConfig()
        with CachedConnectionFactory.getInstance().connection(NetconfConnection,
                                                              self.device.managementIp.split('/')[0],
                                                              username=self.device.username,
                                                              password=self.device.getCleartextPassword()) as connector:
            connector.updateConfig(config)


if __name__ == "__main__":
    #TODO: need to add integration test, hard to write unit tests
    #### TEST CODE, should not be executed
    #### .219 is the only device we have on which we can test
    #### please rollback changes from CLI after running this test
    #configurator = TwoStageConfigurator('192.168.48.219')
    #configurator.start2StageConfiguration()
    #### TEST CODE, should not be executed
    
    l3ClosMediation = L3ClosMediation()
    pods = loader.loadPodsFromClosDefinition()
    pod = l3ClosMediation.createPod('anotherPod', pods['anotherPod'])
    raw_input("pause...")
    leaf1 = l3ClosMediation.__dao.Session.query(Device).filter(Device.name == 'clos-leaf-01').one()
    collector = L2DataCollector(leaf1.id)
    collector.startL2Report()
        
