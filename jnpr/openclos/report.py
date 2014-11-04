'''
Created on Sep 5, 2014

@author: moloyc
'''
import logging
from sqlalchemy.orm import exc
import concurrent.futures
import traceback

import util
from dao import Dao
from model import Pod, InterfaceDefinition
from devicePlugin import Netconf
from writer import CablingPlanWriter
from exception import DeviceError

moduleName = 'report'
logging.basicConfig()
logger = logging.getLogger(moduleName)
logger.setLevel(logging.DEBUG)

class Report(object):
    def __init__(self, conf = {}, dao = None):
        if any(conf) == False:
            self.conf = util.loadConfig()
            logger.setLevel(logging.getLevelName(self.conf['logLevel'][moduleName]))
        else:
            self.conf = conf

        if dao is None:
            self.dao = Dao(self.conf)
        else:
            self.dao = dao

    def getPod(self, podName):
        try:
            return self.dao.getUniqueObjectByName(Pod, podName)
        except (exc.NoResultFound) as e:
            logger.debug("No Pod found with pod name: '%s', exc.NoResultFound: %s" % (podName, e.message))

    def getIpFabric(self, ipFabricId):
        try:
            return self.dao.getObjectById(Pod, ipFabricId)
        except (exc.NoResultFound) as e:
            logger.debug("No IpFabric found with Id: '%s', exc.NoResultFound: %s" % (ipFabricId, e.message)) 
            
class ResourceAllocationReport(Report):
    def __init__(self, conf = {}, dao = None):
        super(ResourceAllocationReport, self).__init__(conf, dao)
        
    def getPods(self):
        podObject = self.dao.getAll(Pod)
        pods = []
        
        for i in range(len(podObject)):
            pod = {}      
            pod['id'] = podObject[i].id
            pod['name'] = podObject[i].name
            pod['spineDeviceType'] = podObject[i].spineDeviceType
            pod['spineCount'] = podObject[i].spineCount
            pod['leafDeviceType'] = podObject[i].leafDeviceType
            pod['leafCount'] = podObject[i].leafCount
            pod['topologyType'] = podObject[i].topologyType        
            pods.append(pod)
            
        return pods
    
    def getInterconnectAllocation(self, podName):
        pod = self.getPod(podName)
        if pod is None: return {}
        
        interconnectAllocation = {}
        interconnectAllocation['block'] = pod.interConnectPrefix
        interconnectAllocation['allocated'] = pod.allocatedInterConnectBlock
        return interconnectAllocation
    
    def getLoopbackAllocation(self, podName):
        pod = self.getPod(podName)
        if pod is None: return {}

        loopbackAllocation = {}
        loopbackAllocation['block'] = pod.loopbackPrefix
        loopbackAllocation['allocated'] = pod.allocatedLoopbackBlock
        return loopbackAllocation
    
    def getIrbAllocation(self, podName):
        pod = self.getPod(podName)
        if pod is None: return {}

        irbAllocation = {}
        irbAllocation['block'] = pod.vlanPrefix
        irbAllocation['allocated'] = pod.allocatedIrbBlock
        return irbAllocation
    
    def getAsnAllocation(self, podName):
        pod = self.getPod(podName)
        if pod is None: return {}

        asnAllocation = {}
        asnAllocation['spineBlockStart'] = pod.spineAS
        asnAllocation['spineBlockEnd'] = pod.leafAS - 1
        asnAllocation['leafBlockStart'] = pod.leafAS
        asnAllocation['leafBlockEnd'] = 65535
        asnAllocation['spineAllocatedStart'] = pod.spineAS
        asnAllocation['spineAllocatedEnd'] = pod.allocatedSpineAS
        asnAllocation['leafAllocatedStart'] = pod.leafAS
        asnAllocation['leafAllocatedEnd'] = pod.allocatefLeafAS
        return asnAllocation

class L2Report(Report):
    def __init__(self, conf = {}, dao = None):
        super(L2Report, self).__init__(conf, dao)
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers = 5)
        self.futureList = []
        
    def generateReport(self, podId):
        pod = self.getIpFabric(podId)
        if pod is None: return
        
        for device in pod.devices:
            if device.role == 'leaf':
                self.futureList.append(self.executor.submit(self.collectAndProcessLldpData, device))
        
        logger.info('Submitted processing all devices')
        concurrent.futures.wait(self.futureList)
        logger.info('Done processing all devices')
        self.executor.shutdown()
        cablingPlanWriter = CablingPlanWriter(self.conf, pod, self.dao)
        cablingPlanWriter.writeL2ReportJson()


    
    def collectAndProcessLldpData(self, device):
        deviceIp = device.managementIp.split('/')[0]
        deviceLog = 'device id: %s, name: %s, ip: %s' % (device.id, device.name, deviceIp)
        try:
            lldpData = Netconf(self.conf).collectLldpFromDevice({'ip': deviceIp, 
                'username': device.username, 'password': device.password})
            logger.debug('Collected LLDP data for %s' % (deviceLog))
            self.updateDeviceStatus(device, None)
            self.updateIfdLldpStatusForUplinks(lldpData, device)
        except DeviceError as exc:
            logger.error('Collect LLDP data failed for %s, %s' % (deviceLog, exc))
            logger.debug('StackTrace: %s' % (traceback.format_exc()))
            self.updateDeviceStatus(device, exc)
    
    def updateDeviceStatus(self, device, error):
        if error is None:
            device.status = 'good'
        else:
            device.status = 'bad'
            device.statusReason = str(error.cause)
        self.dao.updateObjects([device])
        
    def updateIfdLldpStatusForUplinks(self, lldpData, device):
        '''
        :param dict lldpData:
            deivce1: local device (on which lldp was run)
            port1: local interface (on device1)
            device2: remote device
            port2: remote interface
        '''
        uplinkPorts = self.dao.Session().query(InterfaceDefinition).filter(InterfaceDefinition.device_id == device.id).\
            filter(InterfaceDefinition.role == 'uplink').order_by(InterfaceDefinition.name_order_num).all()

        uplinkPortsDict = {}
        for port in uplinkPorts:
            uplinkPortsDict[port.name] = port
        
        modifiedObjects = []
        for link in lldpData:
            uplinkPort = uplinkPortsDict.get(link['port1'])
            if uplinkPort is None:
                continue
            
            peerPort = uplinkPort.peer
            if peerPort is not None and peerPort.name == link['port2'] and peerPort.device.name == link['device2']:
                uplinkPort.lldpStatus = 'good'
                peerPort.lldpStatus = 'good'
                modifiedObjects.append(uplinkPort)
                modifiedObjects.append(peerPort)
            else:
                uplinkPort.lldpStatus = 'bad'
                modifiedObjects.append(uplinkPort)
        
        self.dao.updateObjects(modifiedObjects)

    
class L3Report(Report):
    def __init__(self, conf = {}, dao = None):
        super(L3Report, self).__init__(conf, dao)
    

if __name__ == '__main__':
    report = ResourceAllocationReport()
    print report.getPods();
    print report.getInterconnectAllocation('labLeafSpine')
    print report.getLoopbackAllocation('labLeafSpine')
    print report.getIrbAllocation('labLeafSpine')
    print report.getAsnAllocation('labLeafSpine')

    l2Report = L2Report()
    pod = l2Report.getPod('anotherPod')
    if pod is not None:
        l2Report.generateReport(pod.id)
