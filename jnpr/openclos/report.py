'''
Created on Sep 5, 2014

@author: moloyc
'''
import logging
from sqlalchemy.orm import exc
import concurrent.futures

from dao import Dao
from model import Pod, Device
from devicePlugin import L2DataCollector, L3DataCollector
from writer import L2ReportWriter, L3ReportWriter
from propLoader import OpenClosProperty, loadLoggingConfig
from exception import PodNotFound

moduleName = 'report'
loadLoggingConfig(appName = moduleName)
logger = logging.getLogger(moduleName)
maxThreads = 10

class Report(object):
    def __init__(self, conf = {}, daoClass = Dao):
        if any(conf) == False:
            self._conf = OpenClosProperty(appName = moduleName).getProperties()
        else:
            self._conf = conf

        self._dao = daoClass.getInstance()

    def getPod(self, session, podId):
        try:
            return self._dao.getObjectById(session, Pod, podId)
        except (exc.NoResultFound) as e:
            logger.debug("No IpFabric found with Id: '%s', exc.NoResultFound: %s" % (podId, e.message)) 
            
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
    
class L2Report(Report):
    def __init__(self, conf = {},  daoClass = Dao):
        super(L2Report, self).__init__(conf, daoClass)
        
        if self._conf.get('report') and self._conf['report'].get('threadCount'):
            self.executor = concurrent.futures.ThreadPoolExecutor(max_workers = self._conf['report']['threadCount'])
        else:
            self.executor = concurrent.futures.ThreadPoolExecutor(max_workers = maxThreads)
        
    def resetSpineL2Status(self, devices):
        with self._dao.getReadWriteSession() as session:
            devicesToBeUpdated = set()
            for device in devices:
                if device.role == 'spine':
                    device.l2Status = 'unknown'
                    device.l2StatusReason = None
                    device.configStatus = 'unknown'
                    device.configStatusReason = None
                    devicesToBeUpdated.add(device)
                
            if len(devicesToBeUpdated) > 0:
                self._dao.updateObjects(session, devicesToBeUpdated)
            
    def generateReport(self, podId, cachedData = True, writeToFile = False):
        with self._dao.getReadSession() as session:
            pod = self.getPod(session, podId)
            if pod is None: 
                logger.error('No pod found for podId: %s' % (podId))
                raise PodNotFound('No pod found for podId: %s' % (podId)) 
            
            if cachedData == False:
                logger.info('Generating L2Report from real data')
                
                # reset all spines l2 status
                self.resetSpineL2Status(pod.devices)
                
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
            l2ReportWriter = L2ReportWriter(self._conf, pod, self._dao)
            if writeToFile:
                return l2ReportWriter.writeThreeStageL2ReportJson()
            else:
                return l2ReportWriter.getThreeStageL2ReportJson()

class L3Report(Report):
    def __init__(self, conf = {},  daoClass = Dao):
        super(L3Report, self).__init__(conf, daoClass)
        
        if self._conf.get('report') and self._conf['report'].get('threadCount'):
            self.executor = concurrent.futures.ThreadPoolExecutor(max_workers = self._conf['report']['threadCount'])
        else:
            self.executor = concurrent.futures.ThreadPoolExecutor(max_workers = maxThreads)
        
    def resetSpineL3Status(self, devices):
        with self._dao.getReadWriteSession() as session:
            devicesToBeUpdated = set()
            for device in devices:
                if device.role == 'spine':
                    device.l3Status = 'unknown'
                    device.l3StatusReason = None
                    devicesToBeUpdated.add(device)
                
            if len(devicesToBeUpdated) > 0:
                self._dao.updateObjects(session, devicesToBeUpdated)
            
    def getDeviceAsn2NameMap(self, podId, session):
        map = {}
        logger.debug("Building device AS -> device name map...")
        devices = session.query(Device).filter(Device.pod_id == podId).all()
        for device in devices:
            if device.asn is not None:
                logger.debug("[%d]->[%s]" %(device.asn, device.name))
                map[device.asn] = device
        return map
        
    def generateReport(self, podId, cachedData = True, writeToFile = False):
        with self._dao.getReadSession() as session:
            pod = self.getPod(session, podId)
            if pod is None: 
                logger.error('No pod found for podId: %s' % (podId))
                raise PodNotFound('No pod found for podId: %s' % (podId)) 
            
            if cachedData == False:
                logger.info('Generating L3Report from real data')
                
                # Note this map is static so we only intialize it once for entire L3 report
                deviceAsn2NameMap = self.getDeviceAsn2NameMap(podId, session)
                
                # reset all spines l3 status
                self.resetSpineL3Status(pod.devices)
               
                futureList = []
                for device in pod.devices:
                    if device.role == 'leaf':
                        l3DataCollector = L3DataCollector(device.id, self._conf, self._dao, deviceAsn2NameMap) 
                        futureList.append(self.executor.submit(l3DataCollector.startL3Report))
                logger.info('Submitted processing all devices')
                concurrent.futures.wait(futureList)
                # At this point multiple threads, ie multiple db sessions
                # have updated device, so we need to refresh pod data. 
                # Rather than refresh, better option is expire, which
                # would trigger lazy load.
                session.expire(pod)
                logger.info('Done processing all devices')
            else:
                logger.info('Generating L3Report from cached data')
            l3ReportWriter = L3ReportWriter(self._conf, pod, self._dao)
            if writeToFile:
                return l3ReportWriter.writeThreeStageL3ReportJson()
            else:
                return l3ReportWriter.getThreeStageL3ReportJson()

if __name__ == '__main__':
    report = ResourceAllocationReport()
    with report._dao.getReadSession() as session:
        pods = report.getPods(session)
        print pods

    l2Report = L2Report()
    with l2Report._dao.getReadSession() as session:
        pods = l2Report._dao.getAll(session, Pod)
        pod = [x for x in pods if x.name == 'anotherPod'][0]
        if pod is not None:
            print l2Report.generateReport(pod.id, False, True)

    l3Report = L3Report()
    with l3Report._dao.getReadSession() as session:
        pods = l3Report._dao.getAll(session, Pod)
        pod = [x for x in pods if x.name == 'anotherPod'][0]
        if pod is not None:
            print l3Report.generateReport(pod.id, False, True)
