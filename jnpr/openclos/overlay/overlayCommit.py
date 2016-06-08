'''
Created on Feb 15, 2016

@author: yunli
'''

import traceback
import logging
from threading import Thread, Event, RLock
import concurrent.futures
import Queue
from sqlalchemy.orm import exc

from jnpr.openclos.overlay.overlayModel import OverlayDeployStatus
from jnpr.openclos.dao import Dao
from jnpr.openclos.loader import OpenClosProperty, loadLoggingConfig
from jnpr.openclos.common import SingletonBase
from jnpr.openclos.exception import DeviceRpcFailed, DeviceConnectFailed
from jnpr.openclos.deviceConnector import CachedConnectionFactory, NetconfConnection

DEFAULT_MAX_THREADS = 10
DEFAULT_DISPATCH_INTERVAL = 10
DEFAULT_DAO_CLASS = Dao

moduleName = 'overlayCommit'
loadLoggingConfig(appName=moduleName)
logger = logging.getLogger(moduleName)

class OverlayCommitJob():
    def __init__(self, parent, deployStatusObject):
        # Note we only hold on to the data from the deployStatusObject (deviceId, configlet, etc.). 
        # We are not holding reference to the deployStatusObject itself as it can become invalid when db session is out of scope
        self.parent = parent
        self.id = deployStatusObject.id
        self.deviceId = deployStatusObject.overlay_device.id
        self.deviceIp = deployStatusObject.overlay_device.address
        self.deviceUser = deployStatusObject.overlay_device.username
        self.devicePass = deployStatusObject.overlay_device.getCleartextPassword()
        self.configlet = deployStatusObject.configlet
        self.operation = deployStatusObject.operation
        self.queueId = '%s:%s' % (self.deviceIp, self.deviceId)

    def updateStatus(self, status, reason=None):
        try:
            with self.parent._dao.getReadWriteSession() as session:
                statusObject = session.query(OverlayDeployStatus).filter(OverlayDeployStatus.id == self.id).one()
                
                if statusObject.operation == "create":
                    statusObject.update(status, reason)
                elif statusObject.operation == "delete":
                    # There are 3 cases: (It does not make sense to have a case of creation failure, delete success)
                    # 1. create success, delete success
                    # 2. create success, delete failure
                    # 3. create failure, delete failure
                    # For 1 and 3, it is safe to delete the object itself and all its status.
                    # For 2, we need to keep the object and its status in case someone fixes the OOB issue and 
                    # send another delete again.
                    #
                    # Find all status for this object on this device. Typically there will be 2: one create and one delete.
                    relatedStatusOnThisDevice = session.query(OverlayDeployStatus).filter(
                        OverlayDeployStatus.object_url == statusObject.object_url).filter(
                        OverlayDeployStatus.overlay_device_id == self.deviceId).all()
                    if status == 'success':
                        # case 1
                        self.parent._dao.deleteObjects(session, relatedStatusOnThisDevice)
                    elif status == 'failure':
                        # case 2 or 3
                        for rs in relatedStatusOnThisDevice:
                            if rs.operation == 'create':
                                if rs.status == 'failure':
                                    # case 3
                                    self.parent._dao.deleteObjects(session, relatedStatusOnThisDevice)
                                elif rs.status == 'success':
                                    # case 2
                                    logger.debug("Object %s was created successfully but delete failed. Keep this status. There might be OOB changes on the device causing this failure", rs.object_url)
                        
                    # If all devices are done, then delete the object.
                    notSuccessCount = session.query(OverlayDeployStatus).filter(OverlayDeployStatus.object_url == statusObject.object_url).count()
                    if notSuccessCount == 0:
                        logger.debug("Config deleted on all devices. Object %s deleted", statusObject.object_url)
                        objectTypeId = statusObject.getObjectTypeAndId()
                        obj = session.query(objectTypeId[0]).filter_by(id=objectTypeId[1]).first()
                        if obj:
                            session.delete(obj)
                        
                elif statusObject.operation == "update":
                    statusObject.update(status, reason)
                    ## TODO: add hook to update the actual object

        except Exception as exc:
            logger.error("%s", exc)
            logger.error('StackTrace: %s', traceback.format_exc())

    def commit(self):
        try:
            # Note we don't want to hold the caller's session for too long since this function is potentially lengthy
            # that is why we don't ask caller to pass a dbSession to us. Instead we get the session inside this method
            # only long enough to update the status value
            logger.info("Job %s: starting commit on device [%s]", self.id, self.queueId)

            # first update the status to 'progress'
            self.updateStatus("progress")
                
            # now commit and set the result/reason accordingly
            result = 'success'
            reason = None
            try:
                with CachedConnectionFactory.getInstance().connection(NetconfConnection,
                                                                      self.deviceIp,
                                                                      username=self.deviceUser,
                                                                      password=self.devicePass) as connector:
                    connector.updateConfig(self.configlet)
            except DeviceConnectFailed as exc:
                #logger.error("%s", exc)
                #logger.error('StackTrace: %s', traceback.format_exc())
                result = 'failure'
                reason = exc.__repr__()
            except DeviceRpcFailed as exc:
                #logger.error("%s", exc)
                #logger.error('StackTrace: %s', traceback.format_exc())
                result = 'failure'
                reason = exc.__repr__()
            except Exception as exc:
                #logger.error("%s", exc)
                #logger.error('StackTrace: %s', traceback.format_exc())
                result = 'failure'
                reason = str(exc)
            
            # commit is done so update the result
            self.updateStatus(result, reason)
                
            logger.info("Job %s: done with device [%s]", self.id, self.queueId)
            # remove device id from cache
            self.parent.markDeviceIdle(self.queueId)
        except Exception as exc:
            logger.error("Job %s: error '%s'", self.id, exc)
            logger.error('StackTrace: %s', traceback.format_exc())
            raise

class OverlayCommitQueue(SingletonBase):
    def __init__(self, daoClass=DEFAULT_DAO_CLASS):
        self._dao = daoClass.getInstance()
        # event to stop from sleep
        self.stopEvent = Event()
        self.__lock = RLock()
        self.__devicesInProgress = set()
        self.__deviceQueues = {}
        self.maxWorkers = DEFAULT_MAX_THREADS
        self.dispatchInterval = DEFAULT_DISPATCH_INTERVAL
        self.thread = Thread(target=self.dispatchThreadFunction, args=())
        self.started = False
        
        conf = OpenClosProperty().getProperties()
        # iterate 'plugin' section of openclos.yaml and install routes on all plugins
        if 'plugin' in conf:
            plugins = conf['plugin']
            for plugin in plugins:
                if plugin['name'] == 'overlay':
                    maxWorkers = plugin.get('threadCount')
                    if maxWorkers is not None:
                        self.maxWorkers = maxWorkers
                    dispatchInterval = plugin.get('dispatchInterval')
                    if dispatchInterval is not None:
                        self.dispatchInterval = dispatchInterval
                    break
        
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=self.maxWorkers)

    def addJobs(self, deployStatusObjects):
        jobs = []
        for deployStatusObject in deployStatusObjects:
            jobs.append(OverlayCommitJob(self, deployStatusObject))
            logger.debug("Job %s: added to device [%s]", jobs[-1].id, jobs[-1].queueId)
            
        with self.__lock:
            for job in jobs:
                if job.queueId not in self.__deviceQueues:
                    self.__deviceQueues[job.queueId] = Queue.Queue()
                self.__deviceQueues[job.queueId].put(job)

        return jobs

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
            for queueId, deviceQueue in self.__deviceQueues.iteritems():
                # find an idle device
                if queueId not in self.__devicesInProgress:
                    self.__devicesInProgress.add(queueId)
                    logger.debug("Device [%s] has NO commit in progress. Prepare for commit", queueId)
                    # retrieve the job
                    try:
                        job = deviceQueue.get_nowait()
                        # start commit progress 
                        self.executor.submit(job.commit)
                        deviceQueue.task_done()
                        if deviceQueue.empty():
                            logger.debug("Device [%s] job queue is empty", queueId)
                            # Note don't delete the empty job queues within the iteration.
                            toBeDeleted.append(queueId)
                    except Queue.Empty as exc:
                        logger.debug("Device [%s] job queue is empty", queueId)
                        # Note don't delete the empty job queues within the iteration.
                        toBeDeleted.append(queueId)
                else:
                    logger.debug("Device [%s] has commit in progress. Skipped", queueId)
            
            # Now it is safe to delete all empty job queues
            for queueId in toBeDeleted:
                logger.debug("Deleting job queue for device [%s]", queueId)
                del self.__deviceQueues[queueId]
    
    def markDeviceIdle(self, queueId):
        with self.__lock:
            self.__devicesInProgress.discard(queueId)
    
    def start(self):
        with self.__lock:
            if self.started:
                return
            else:
                self.started = True
                
        logger.info("Starting OverlayCommitQueue...")
        self.thread.start()
        logger.info("OverlayCommitQueue started")
   
    def stop(self):
        logger.info("Stopping OverlayCommitQueue...")
        self.stopEvent.set()
        self.executor.shutdown()
        with self.__lock:
            if self.started:
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
    # from jnpr.openclos.overlay.overlayModel import OverlayDevice, OverlayFabric, OverlayAggregatedL2port
    # import time
    
    # conf = OpenClosProperty().getProperties()
    # dao = Dao.getInstance()
    # from jnpr.openclos.overlay.overlay import Overlay
    # overlay = Overlay(conf, Dao.getInstance())

    # # Note jnpr.openclos.overlay.overlayCommit.OverlayCommitQueue is different than just OverlayCommitQueue.
    # # If we don't do the import. python will treat those as 2 different classes so singleton behavior will fail.
    # from jnpr.openclos.overlay.overlayCommit import OverlayCommitQueue
    # commitQueue = OverlayCommitQueue.getInstance()
    # commitQueue.dispatchInterval = 1
    # commitQueue.start()
    
    # with dao.getReadWriteSession() as session:
        # d1 = overlay.createDevice(session, 'd1', 'description for d1', 'leaf', '10.92.82.12', '10.92.82.12', 'pod1', 'root', 'Embe1mpls')
        # d1_id = d1.id
        # d2 = overlay.createDevice(session, 'd2', 'description for d2', 'leaf', '10.92.82.13', '10.92.82.13', 'pod1', 'root', 'Embe1mpls')
        # d2_id = d2.id
        # f1 = overlay.createFabric(session, 'f1', '', 65001, '2.2.2.2', [d1, d2])
        # f1_id = f1.id
        # t1 = overlay.createTenant(session, 't1', '', f1)
        # t1_id = t1.id
        # v1 = overlay.createVrf(session, 'v1', '', 100, '1.1.1.1/30', t1)
        # v1_id = v1.id
        # n1 = overlay.createNetwork(session, 'n1', '', v1, 1000, 100, False)
        # n1_id = n1.id
        # s1 = overlay.createSubnet(session, 's1', '', n1, '1.2.3.4/24')
        # s1_id = s1.id
        # members = [ {'interface': 'xe-0/0/0', 'device': d1}, {'interface': 'xe-0/0/0', 'device': d2} ]
        # aggregatedL2port1 = overlay.createAggregatedL2port(session, 'ae0', '', [n1], members, '00:01:01:01:01:01:01:01:01:01', '00:00:00:01:01:01')
        # aggregatedL2port1_id = aggregatedL2port1.id 
        
    # time.sleep(20)
    
    # raw_input("press any key...")
    # with dao.getReadWriteSession() as session:
        # aggregatedL2port1 = dao.getObjectById(session, OverlayAggregatedL2port, aggregatedL2port1_id)
        # overlay.deleteAggregatedL2port(session, aggregatedL2port1)
    
    # # raw_input("press any key...")
    # # with dao.getReadWriteSession() as session:
        # # f1 = dao.getObjectById(session, OverlayFabric, f1_id)
        # # overlay.deleteFabric(session, f1)
    
    # raw_input("press any key...")
    # commitQueue.stop()

# if __name__ == '__main__':
    # main()
