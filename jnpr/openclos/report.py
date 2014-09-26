'''
Created on Sep 5, 2014

@author: moloyc
'''
import logging
from sqlalchemy.orm import exc

import util
from dao import Dao
from model import Pod

moduleName = 'report'
logging.basicConfig()
logger = logging.getLogger(moduleName)
logger.setLevel(logging.DEBUG)

class ResourceAllocationReport:
    def __init__(self, conf = {}):
        if any(conf) == False:
            self.conf = util.loadConfig()
            logger.setLevel(logging.getLevelName(self.conf['logLevel'][moduleName]))

        else:
            self.conf = conf
        self.dao = Dao(self.conf)
        
    def getPods(self):
        podObject = self.dao.getAll(Pod)
        pods = {'id':[], 'name':[], 'spineDeviceType':[], 'spineCount':[],'leafDeviceType':[],'leafCount':[],'topologyType':[]}
        for i in range(len(podObject)):
            pods['id'].append(podObject[i].id)
            pods['name'].append(podObject[i].name)
            pods['spineDeviceType'].append(podObject[i].spineDeviceType)
            pods['spineCount'].append(podObject[i].spineCount)
            pods['leafDeviceType'].append(podObject[i].leafDeviceType)
            pods['leafCount'].append(podObject[i].leafCount)
            pods['topologyType'].append(podObject[i].topologyType)  
        return pods
    
    def getPod(self, podName):
        try:
            return self.dao.getUniqueObjectByName(Pod, podName)
        except (exc.NoResultFound) as e:
            logger.debug("No Pod found with pod name: '%s', exc.NoResultFound: %s" % (podName, e.message)) 
            
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

if __name__ == '__main__':
    report = ResourceAllocationReport()
    print report.getPods();
    print report.getInterconnectAllocation('labLeafSpine')
    print report.getLoopbackAllocation('labLeafSpine')
    print report.getIrbAllocation('labLeafSpine')
    print report.getAsnAllocation('labLeafSpine')