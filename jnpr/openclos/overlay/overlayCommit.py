'''
Created on Feb 15, 2016

@author: yunli
'''

import os
import uuid
import logging
from threading import Thread, Event, RLock
import subprocess
import concurrent.futures
import Queue
from sqlalchemy.orm import exc
import time

from jnpr.openclos.overlay.overlay import Overlay
from jnpr.openclos.overlay.overlayModel import OverlayFabric, OverlayTenant, OverlayVrf, OverlayNetwork, OverlaySubnet, OverlayDevice, OverlayL3port, OverlayL2port, OverlayAe, OverlayDeployStatus
from jnpr.openclos.dao import Dao
from jnpr.openclos.loader import defaultPropertyLocation, OpenClosProperty, DeviceSku, loadLoggingConfig
from jnpr.openclos.common import SingletonBase
from jnpr.openclos.exception import ConfigurationCommitFailed

DEFAULT_MAX_THREADS = 10
DEFAULT_DISPATCH_INTERVAL = 10

moduleName = 'overlayCommit'
loadLoggingConfig(appName=moduleName)
logger = logging.getLogger(moduleName)

class OverlayCommitJob():
    def __init__(self, parent, deployStatusObject):
        self.parent = parent
        self.id = deployStatusObject.id
        self.deviceId = deployStatusObject.overlay_device_id
        self.configlet = deployStatusObject.configlet
        self.operation = deployStatusObject.operation

    def commit(self):
        try:
            # Note we don't want to hold the caller's session for too long since this function is potentially lengthy
            # that is why we don't ask caller to pass a dbSession to us. Instead we get the session inside this method
            # only long enough to update the status value
            logger.info("Job %s: starting commit on device %s", self.id, self.deviceId)

            # first update the status to 'progress'
            with self.parent.overlay._dao.getReadWriteSession() as session:
                statusObject = session.query(OverlayDeployStatus).filter(OverlayDeployStatus.id == self.id).one()
                statusObject.update('progress', 'commit in progress', self.operation)

            ######################################################
            #
            # TODO: do the actual commit
            #
            ######################################################
            result = 'success' # or 'failure'
            reason = ''
            time.sleep(3)
            
            # upon succeess, remove device id from cache
            with self.parent.overlay._dao.getReadWriteSession() as session:
                statusObject = session.query(OverlayDeployStatus).filter(OverlayDeployStatus.id == self.id).one()
                statusObject.update(result, reason, self.operation)
                
            logger.info("Job %s: done with device %s", self.id, self.deviceId)
            self.parent.markDeviceIdle(self.deviceId)
        except Exception as exc:
            logger.error("Job %s: encounted error '%s'", self.id, exc)
            raise

class OverlayCommitQueue(SingletonBase):
    def __init__(self, overlay, maxWorkers=DEFAULT_MAX_THREADS, dispatchInterval=DEFAULT_DISPATCH_INTERVAL):
        self.dispatchInterval = dispatchInterval
        self.overlay = overlay
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=maxWorkers)
        # event to stop from sleep
        self.stopEvent = Event()
        self.__lock = RLock()
        self.__devicesInProgress = set()
        self.__deviceQueues = {}

    def addJob(self, deployStatusObject):
        job = OverlayCommitJob(self, deployStatusObject)
        logger.debug("Job %s: added to device %s", job.id, job.deviceId)
        with self.__lock:
            if job.deviceId not in self.__deviceQueues:
                self.__deviceQueues[job.deviceId] = Queue.Queue()
            self.__deviceQueues[job.deviceId].put(job)
        return job
    
    '''
    To be used by unit test only
    '''
    def _getDeviceQueues(self):
        return self.__deviceQueues
        
    def runJobs(self):
        # check device queues (round robin)
        # Note we only hold on to the lock long enough to retrieve the job from the queue.
        # Then we release the lock before we do the actual commit
        with self.__lock:
            toBeDeleted = []
            for deviceId, deviceQueue in self.__deviceQueues.iteritems():
                # find an idle device
                if deviceId not in self.__devicesInProgress:
                    self.__devicesInProgress.add(deviceId)
                    logger.debug("Device %s has NO commit in progress. Prepare for commit", deviceId)
                    # retrieve the job
                    try:
                        job = deviceQueue.get_nowait()
                        # start commit progress 
                        self.executor.submit(job.commit)
                        deviceQueue.task_done()
                        if deviceQueue.empty():
                            logger.debug("Device %s job queue is empty", deviceId)
                            # Note don't delete the empty job queues within the iteration.
                            toBeDeleted.append(deviceId)
                    except Queue.Empty as exc:
                        logger.debug("Device %s job queue is empty", deviceId)
                        # Note don't delete the empty job queues within the iteration.
                        toBeDeleted.append(deviceId)
                else:
                    logger.debug("Device %s has commit in progress. Skipped", deviceId)
            
            # Now it is safe to delete all empty job queues
            for deviceId in toBeDeleted:
                logger.debug("Deleting job queue for device %s", deviceId)
                del self.__deviceQueues[deviceId]
    
    def markDeviceIdle(self, deviceId):
        with self.__lock:
            self.__devicesInProgress.discard(deviceId)
    
    def start(self):
        logger.info("Starting OverlayCommitQueue...")
        self.thread = Thread(target=self.dispatchThreadFunction, args=())
        self.thread.start()
        logger.info("OverlayCommitQueue started")
   
    def stop(self):
        logger.info("Stopping OverlayCommitQueue...")
        self.stopEvent.set()
        self.executor.shutdown()
        self.thread.join()
        logger.info("OverlayCommitQueue stopped")
    
    def dispatchThreadFunction(self):
        try:
            while True:
                self.stopEvent.wait(self.dispatchInterval)
                if not self.stopEvent.is_set():
                    self.runJobs()
                else:
                    logger.debug("OverlayCommitQueue: stopEvent is set")
                    return
                
        except Exception as exc:
            logger.error("Encounted error '%s' on OverlayCommitQueue", exc)
            raise

# def main():        
    # conf = {}
    # conf['outputDir'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'out')
    # conf['plugin'] = [{'name': 'overlay', 'package': 'jnpr.openclos.overlay'}]
    # dao = Dao.getInstance()
    # overlay = Overlay(conf, dao)

    # commitQueue = OverlayCommitQueue(overlay, 10, 1)
    # commitQueue.start()
    
    # with dao.getReadWriteSession() as session:
        # d1 = overlay.createDevice(session, 'd1', 'description for d1', 'spine', '1.2.3.4', '1.1.1.1')
        # d2 = overlay.createDevice(session, 'd2', 'description for d2', 'spine', '1.2.3.5', '1.1.1.2')
        # d1_id = d1.id
        # d2_id = d2.id
        # f1 = overlay.createFabric(session, 'f1', '', 65001, '2.2.2.2', [d1, d2])
        # f1_id = f1.id
        # f2 = overlay.createFabric(session, 'f2', '', 65002, '3.3.3.3', [d1, d2])
        # f2_id = f2.id
        # t1 = overlay.createTenant(session, 't1', '', f1)
        # t1_id = t1.id
        # t2 = overlay.createTenant(session, 't2', '', f2)
        # t2_id = t2.id
        # v1 = overlay.createVrf(session, 'v1', '', 100, '1.1.1.1', t1)
        # v1_id = v1.id
        # v2 = overlay.createVrf(session, 'v2', '', 101, '1.1.1.2', t2)
        # v2_id = v2.id
        # n1 = overlay.createNetwork(session, 'n1', '', v1, 1000, 100, False)
        # n1_id = n1.id
        # n2 = overlay.createNetwork(session, 'n2', '', v1, 1001, 101, False)
        # n2_id = n2.id
        # s1 = overlay.createSubnet(session, 's1', '', n1, '1.2.3.4/24')
        # s1_id = s1.id
        # s2 = overlay.createSubnet(session, 's2', '', n1, '1.2.3.5/24')
        # s2_id = s2.id
        # ae1 = overlay.createAe(session, 'ae1', '', '00:11', '11:00')
        # ae1_id = ae1.id
        # l2port1 = overlay.createL2port(session, 'l2port1', '', 'xe-0/0/1', n1, d1, ae1)
        # l2port1_id = l2port1.id
        # l2port2 = overlay.createL2port(session, 'l2port2', '', 'xe-0/0/1', n1, d2, ae1)
        # l2port2_id = l2port2.id
        
        # statusList = []
        # object_url = '/openclos/v1/overlay/fabrics/' + f1_id
        # statusList.append(OverlayDeployStatus('f1config', object_url, 'POST', d1, None))
        # statusList.append(OverlayDeployStatus('f1config', object_url, 'POST', d2, None))
        # object_url = '/openclos/v1/overlay/vrfs/' + v1_id
        # statusList.append(OverlayDeployStatus('v1config', object_url, 'POST', d1, v1))
        # statusList.append(OverlayDeployStatus('v1config', object_url, 'POST', d2, v1))
        # object_url = '/openclos/v1/overlay/networks/' + n1_id
        # statusList.append(OverlayDeployStatus('n1config', object_url, 'POST', d1, v1))
        # statusList.append(OverlayDeployStatus('n1config', object_url, 'POST', d2, v1))
        # object_url = '/openclos/v1/overlay/aes/' + ae1_id
        # statusList.append(OverlayDeployStatus('ae1config', object_url, 'POST', d1, v1))
        # statusList.append(OverlayDeployStatus('ae1config', object_url, 'POST', d2, v1))
        # object_url = '/openclos/v1/overlay/l2ports/' + l2port1_id
        # statusList.append(OverlayDeployStatus('l2port1config', object_url, 'POST', d1, v1))
        # statusList.append(OverlayDeployStatus('l2port1config', object_url, 'POST', d2, v1))
        # object_url = '/openclos/v1/overlay/l2ports/' + l2port2_id
        # statusList.append(OverlayDeployStatus('l2port2config', object_url, 'POST', d1, v1))
        # statusList.append(OverlayDeployStatus('l2port2config', object_url, 'POST', d2, v1))
        # dao.createObjects(session, statusList)

    # with dao.getReadWriteSession() as session:
        # status_db = session.query(OverlayDeployStatus).all()
        # for s in status_db:
            # commitQueue.addJob(s)
            
    # raw_input("Press any key to stop...")
    # commitQueue.stop()

# if __name__ == '__main__':
    # main()
