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
from devicePlugin import L2DataCollector, L3DataCollector
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
                logger.info('Generating L3Report from real data')
                futureList = []
                for device in pod.devices:
                    if device.role == 'leaf':
                        l3DataCollector = L3DataCollector(device.id, self._conf, self._dao) 
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
            cablingPlanWriter = CablingPlanWriter(self._conf, pod, self._dao)
            if writeToFile:
                return cablingPlanWriter.writeThreeStageL3ReportJson()
            else:
                return cablingPlanWriter.getThreeStageL3ReportJson()

if __name__ == '__main__':
    report = ResourceAllocationReport()
    with report._dao.getReadSession() as session:
        pods = report.getPods(session);
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
