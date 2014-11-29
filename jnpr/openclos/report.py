'''
Created on Sep 5, 2014

@author: moloyc
'''
import logging
from sqlalchemy.orm import exc
import concurrent.futures

import util
from dao import Dao
from model import Pod
from devicePlugin import L2DataCollector
from writer import CablingPlanWriter

moduleName = 'report'
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(moduleName)
logger.setLevel(logging.DEBUG)
maxThreads = 10

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
            pod['devicePassword'] = podObject[i].getCleartextPassword()
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
        
        if self.conf.get('report') and self.conf['report'].get('threadCount'):
            self.executor = concurrent.futures.ThreadPoolExecutor(max_workers = self.conf['report']['threadCount'])
        else:
            self.executor = concurrent.futures.ThreadPoolExecutor(max_workers = maxThreads)
        
    def generateReport(self, podId, cachedData = True, writeToFile = False):
        pod = self.getIpFabric(podId)
        if pod is None: 
            logger.error('No pod found for podId: %s' % (podId))
            raise ValueError('No pod found for podId: %s' % (podId)) 
        
        if cachedData == False:
            logger.info('Generating L2Report from real data')
            futureList = []
            for device in pod.devices:
                if device.role == 'leaf':
                    l2DataCollector = L2DataCollector(device.id, self.conf, self.dao) 
                    futureList.append(self.executor.submit(l2DataCollector.startL2Report))
            logger.info('Submitted processing all devices')
            concurrent.futures.wait(futureList)
            # At this point multiple threads, ie multiple db sessions
            # have updated device, so we need to refresh pod data. 
            # Rather than refresh, better option is expire, which
            # would trigger lazy load.
            self.dao.Session.expire(pod)
            logger.info('Done processing all devices')
        else:
            logger.info('Generating L2Report from cached data')
        cablingPlanWriter = CablingPlanWriter(self.conf, pod, self.dao)
        if writeToFile:
            return cablingPlanWriter.writeThreeStageL2ReportJson()
        else:
            return cablingPlanWriter.getThreeStageL2ReportJson()

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
        print l2Report.generateReport(pod.id, False, True)
