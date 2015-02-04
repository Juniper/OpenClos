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
logger = None
maxThreads = 10

class Report(object):
    def __init__(self, conf = {}, daoClass = Dao):
        global logger
        if any(conf) == False:
            self._conf = util.loadConfig(appName = moduleName)
        else:
            self._conf = conf

        logger = logging.getLogger(moduleName)
        self._dao = daoClass.getInstance()

    def getPod(self, session, podName):
        return self._dao.getUniqueObjectByName(session, Pod, podName)

    def getIpFabric(self, session, ipFabricId):
        try:
            return self._dao.getObjectById(session, Pod, ipFabricId)
        except (exc.NoResultFound) as e:
            logger.debug("No IpFabric found with Id: '%s', exc.NoResultFound: %s" % (ipFabricId, e.message)) 
            
class ResourceAllocationReport(Report):
    def __init__(self, conf = {}, daoClass = Dao):
        super(ResourceAllocationReport, self).__init__(conf, daoClass)
        
    def getPods(self, session):
        podObject = self._dao.getAll(session, Pod)
        pods = []
        
        for i in range(len(podObject)):
            pod = {}      
            pod['id'] = podObject[i].id
            pod['name'] = podObject[i].name
            pod['spineDeviceType'] = podObject[i].spineDeviceType
            pod['spineCount'] = podObject[i].spineCount
            pod['leafSettings'] = []
            for leafSetting in podObject[i].leafSettings:
                pod['leafSettings'].append({'deviceType': leafSetting.deviceFamily, 'junosImage': leafSetting.junosImage})
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
    def __init__(self, conf = {},  daoClass = Dao):
        super(L2Report, self).__init__(conf, daoClass)
        
        if self._conf.get('report') and self._conf['report'].get('threadCount'):
            self.executor = concurrent.futures.ThreadPoolExecutor(max_workers = self._conf['report']['threadCount'])
        else:
            self.executor = concurrent.futures.ThreadPoolExecutor(max_workers = maxThreads)
        
    def generateReport(self, podId, cachedData = True, writeToFile = False):
        with self._dao.getReadSession() as session:
            pod = self.getIpFabric(session, podId)
            if pod is None: 
                logger.error('No pod found for podId: %s' % (podId))
                raise ValueError('No pod found for podId: %s' % (podId)) 
            
            if cachedData == False:
                logger.info('Generating L2Report from real data')
                futureList = []
                for device in pod.devices:
                    if device.role == 'leaf':
                        l2DataCollector = L2DataCollector(device.id, self._conf, self._dao) 
                        futureList.append(self.executor.submit(l2DataCollector.startL2Report))
                logger.info('Submitted processing all devices')
                concurrent.futures.wait(futureList)
                # At this point multiple threads, ie multiple db sessions
                # have updated device, so we need to refresh pod data. 
                # Rather than refresh, better option is expire, which
                # would trigger lazy load.
                session.expire(pod)
                logger.info('Done processing all devices')
            else:
                logger.info('Generating L2Report from cached data')
            cablingPlanWriter = CablingPlanWriter(self._conf, pod, self._dao)
            if writeToFile:
                return cablingPlanWriter.writeThreeStageL2ReportJson()
            else:
                return cablingPlanWriter.getThreeStageL2ReportJson()

class L3Report(Report):
    def __init__(self, conf = {},  daoClass = Dao):
        super(L3Report, self).__init__(conf, daoClass)
    

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
