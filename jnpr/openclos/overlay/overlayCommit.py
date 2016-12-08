'''
Created on Feb 15, 2016

@author: yunli
'''

import traceback
import logging
from threading import Thread, Event, RLock
import concurrent.futures
import Queue
import re
from sqlalchemy.orm import exc

from jnpr.openclos.overlay.overlayModel import OverlayDeployStatus, OverlayL2ap, OverlayFabricPodClusterId
from jnpr.openclos.dao import Dao
from jnpr.openclos.loader import OpenClosProperty, loadLoggingConfig
from jnpr.openclos.common import SingletonBase
from jnpr.openclos.exception import DeviceRpcFailed, DeviceConnectFailed
from jnpr.openclos.deviceConnector import CachedConnectionFactory, NetconfConnection

DEFAULT_MAX_THREADS = 10
DEFAULT_DISPATCH_INTERVAL = 10
MAX_DBCLEANUP_INTERVAL = 10
DEFAULT_DAO_CLASS = Dao

moduleName = 'overlayCommit'
loadLoggingConfig(appName=moduleName)
logger = logging.getLogger(moduleName)

class OverlayCommitJob(object):
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
        self.objectUrl = deployStatusObject.object_url
        self.queueId = '%s:%s' % (self.deviceIp, self.deviceId)
        self._debugContext = '[%s %s@%s, job=%s]' % (self.operation, self.objectUrl, self.deviceIp, self.id)  
        
    def updateStatus(self, status, reason=None):
        try:
            with self.parent._dao.getReadWriteSession() as session:
                statusObject = session.query(OverlayDeployStatus).filter(OverlayDeployStatus.id == self.id).first()
                if statusObject is None:
                    logger.debug("OverlayDeployStatus %s no longer exists", self._debugContext)
                    return

                # Update status in all cases
                logger.debug("OverlayDeployStatus %s status changed to %s, %s", self._debugContext, status, reason)
                statusObject.update(status, reason)
                
                # If we are in progress, there is nothing else to do
                if status == 'progress':
                    return
                
                elif statusObject.operation == "create":
                    # Nothing else to do
                    pass
                    
                elif statusObject.operation == "delete":
                    # There are 3 cases: (It does not make sense to have a case of creation failure, delete success)
                    # 1. create/update success, delete success
                    # 2. create/update success, delete failure
                    # 3. create/update failure, delete failure
                    # For 1 it is safe to delete the object itself and all its status.
                    # For 2 and 3, we need to keep the object and its status in case someone fixes the OOB issue and 
                    # send another delete again.
                    
                    # Find all previous create/update/delete records for this object on this device
                    allPreviousStatusOnThisDevice = session.query(OverlayDeployStatus).filter(
                        OverlayDeployStatus.object_url == statusObject.object_url).filter(
                        OverlayDeployStatus.overlay_device_id == self.deviceId).filter(
                        OverlayDeployStatus.id != self.id).all()
                    if status == 'success':
                        # case 1
                        self.parent._dao.deleteObjects(session, allPreviousStatusOnThisDevice + [statusObject])
                    elif status == 'failure':
                        # case 2 or 3
                        self.parent._dao.deleteObjects(session, allPreviousStatusOnThisDevice)
                        
                elif statusObject.operation == "update":
                    # Find all previous create/update/delete records for this object on this device and delete them
                    # This will make sure we only have 1 latest record exist for this object on this device
                    allPreviousStatusOnThisDevice = session.query(OverlayDeployStatus).filter(
                        OverlayDeployStatus.object_url == statusObject.object_url).filter(
                        OverlayDeployStatus.overlay_device_id == self.deviceId).filter(
                        OverlayDeployStatus.id != self.id).all()
                    self.parent._dao.deleteObjects(session, allPreviousStatusOnThisDevice)

        except Exception as exc:
            logger.error("%s", exc)
            logger.error('StackTrace: %s', traceback.format_exc())

    def commit(self):
        try:
            # Note we don't want to hold the caller's session for too long since this function is potentially lengthy
            # that is why we don't ask caller to pass a dbSession to us. Instead we get the session inside this method
            # only long enough to update the status value
            logger.info("Job %s: starting commit", self._debugContext)

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
                logger.error("Failed config: %s", self.configlet)
            except Exception as exc:
                #logger.error("%s", exc)
                #logger.error('StackTrace: %s', traceback.format_exc())
                result = 'failure'
                reason = str(exc)
                logger.error("Failed config: %s", self.configlet)
            
            # commit is done so update the result
            self.updateStatus(result, reason)
                
            logger.info("Job %s: done", self._debugContext)
            # remove device id from cache
            self.parent.markDeviceIdle(self.queueId)
        except Exception as exc:
            logger.error("Job %s: error '%s'", self._debugContext, exc)
            logger.error('StackTrace: %s', traceback.format_exc())
            raise

class OverlayAggregatedL2portCommitJob(OverlayCommitJob):
    def __init__(self, parent, deployStatusObject):
        super(OverlayAggregatedL2portCommitJob, self).__init__(parent, deployStatusObject)
        self._deviceCountPattern = re.compile("\s*device-count\s+([0-9]+);\s*")

    def updateConfiglet(self, configlet):
        try:
            with self.parent._dao.getReadWriteSession() as session:
                statusObject = session.query(OverlayDeployStatus).filter(OverlayDeployStatus.id == self.id).first()
                if statusObject is None:
                    logger.debug("OverlayDeployStatus %s no longer exists", self._debugContext)
                    return

                # Update configlet
                statusObject.configlet = configlet
                
        except Exception as exc:
            logger.error("%s", exc)
            logger.error('StackTrace: %s', traceback.format_exc())

    def commit(self):
        try:
            # Note we don't want to hold the caller's session for too long since this function is potentially lengthy
            # that is why we don't ask caller to pass a dbSession to us. Instead we get the session inside this method
            # only long enough to update the status value
            logger.info("Job %s: starting commit", self._debugContext)

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
                                                                      
                    # Find the device-count on the device
                    deviceCountOnDevice = 0
                    deviceCountStanza = connector.runCommand("show configuration chassis aggregated-devices ethernet device-count")
                    if deviceCountStanza:
                        group = self._deviceCountPattern.search(deviceCountStanza)
                        if group:
                            deviceCountOnDevice = int(group.group(1))
                    
                    # Find the device-count in self.configlet
                    deviceCountOnFile = 0
                    group = self._deviceCountPattern.search(self.configlet)
                    if group:
                        deviceCountOnFile = int(group.group(1))
                    
                    # If deviceCountOnDevice > deviceCountOnFile, this means the device has already a higher
                    # value, we should not change it to lower value. So set configlet to use deviceCountOnDevice which
                    # will result in a no-op when commit.
                    #
                    # Else if deviceCountOnDevice <= deviceCountOnFile, this means the device currently has a lower or equal 
                    # value, we should just go ahead commit because configlet contains the higher value.
                    logger.debug("deviceCountOnDevice=%d, deviceCountOnFile=%d", deviceCountOnDevice, deviceCountOnFile)
                    if deviceCountOnDevice > deviceCountOnFile:
                        logger.debug("device-count value on device is already bigger than what we are about to set. Probably due to OOB change, DO NOT modify device-count stanza")
                        self.configlet = self._deviceCountPattern.sub("device-count %d;" % deviceCountOnDevice, self.configlet)
                        self.updateConfiglet(self.configlet)
                    
                    # Now it is time to commit
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
                logger.error("Failed config: %s", self.configlet)
            except Exception as exc:
                #logger.error("%s", exc)
                #logger.error('StackTrace: %s', traceback.format_exc())
                result = 'failure'
                reason = str(exc)
                logger.error("Failed config: %s", self.configlet)
            
            # commit is done so update the result
            self.updateStatus(result, reason)
                
            logger.info("Job %s: done", self._debugContext)
            # remove device id from cache
            self.parent.markDeviceIdle(self.queueId)
        except Exception as exc:
            logger.error("Job %s: error '%s'", self._debugContext, exc)
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
        self.__tbdObjects = [] # [(url, force)] e.g. [('/vrfs/1234', True), ('/networks/2345', False), ...]
        self.maxDbCleanUpInterval = MAX_DBCLEANUP_INTERVAL
        
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
                    maxDbCleanUpInterval = plugin.get('maxDbCleanUpInterval')
                    if maxDbCleanUpInterval is not None:
                        self.maxDbCleanUpInterval = maxDbCleanUpInterval
                    break
        
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=self.maxWorkers)

    def addJobs(self, deployStatusObjects):
        jobs = []
        for deployStatusObject in deployStatusObjects:
            objectUrl = deployStatusObject.object_url
            # Special case: aggregatedL2port needs to read existing value from current config and push a new value
            if objectUrl.startswith('/aggregatedL2ports'): 
                job = OverlayAggregatedL2portCommitJob(self, deployStatusObject)
            else:
                job = OverlayCommitJob(self, deployStatusObject)
            jobs.append(job)
            logger.debug("Job %s: added", job._debugContext)
            
        with self.__lock:
            for job in jobs:
                if job.queueId not in self.__deviceQueues:
                    self.__deviceQueues[job.queueId] = Queue.Queue()
                self.__deviceQueues[job.queueId].put(job)

        return jobs
        
    def addDbCleanUp(self, objectUrl, force):
        with self.__lock:
            self.__tbdObjects.append((objectUrl, force))
        
    '''
    To be used by unit test only
    '''
    def _getDeviceQueues(self):
        return self.__deviceQueues

    '''
    To be used by unit test only
    '''
    def _getTbdObjects(self):
        return self.__tbdObjects
        
    def runJobs(self):
        # check device queues (round robin)
        # Note we only hold on to the lock long enough to retrieve the job from the queue.
        # Then we release the lock before we do the actual commit
        with self.__lock:
            for queueId, deviceQueue in self.__deviceQueues.iteritems():
                # find an idle device
                if queueId not in self.__devicesInProgress:
                    # logger.debug("Device [%s] has NO commit in progress", queueId)
                    # retrieve the job
                    try:
                        job = deviceQueue.get_nowait()
                        self.__devicesInProgress.add(queueId)
                        # start commit progress 
                        self.executor.submit(job.commit)
                        deviceQueue.task_done()
                    except Queue.Empty as exc:
                        # logger.debug("Device [%s] job queue is empty", queueId)
                        pass
                # else:
                    # logger.debug("Device [%s] has commit in progress. Skipped", queueId)
    
    def markDeviceIdle(self, queueId):
        with self.__lock:
            self.__devicesInProgress.discard(queueId)
    
    def _deleteObjectAndFixL2ap(self, session, objectUrl, object):
        if object:
            # REVISIT: special case for overlayFabric
            if objectUrl.startswith("/fabrics"):
                logger.debug("cleanUpDb: special case for overlayFabric")
                for clusterId in session.query(OverlayFabricPodClusterId).filter(OverlayFabricPodClusterId.overlay_fabric_id == object.id).all():
                    session.delete(clusterId)
                    
            session.delete(object)
            logger.debug("cleanUpDb: Object %s deleted", objectUrl)
            
        # REVISIT: We have to check if overlayL2ap table has any row that does not have a network
        for l2ap in session.query(OverlayL2ap).all():
            if len(l2ap.overlay_networks) == 0:
                session.delete(l2ap)
                logger.debug("cleanUpDb: Orphan OverlayL2ap %s deleted", l2ap.getUrl())
    
    def cleanUpDb(self):
        tbdObjectsCopy = None
        with self.__lock:
            if len(self.__tbdObjects) == 0:
                return
                
            tbdObjectsCopy = self.__tbdObjects[:]
            
        # Go through all to-be-deleted objects. If there is no status for that object, we can
        # safely delete it from db.
        # logger.debug("cleanUpDb: tbdObjects = %s", tbdObjectsCopy)
        with self._dao.getReadWriteSession() as session:
            for objectUrl, force in tbdObjectsCopy:
                # Get the object
                objectTypeId = OverlayDeployStatus.getObjectTypeAndId(objectUrl)
                obj = session.query(objectTypeId[0]).filter_by(id=objectTypeId[1]).first()
                # Get the object deploy status
                statusOnAllDevices = session.query(OverlayDeployStatus).filter(
                    OverlayDeployStatus.object_url == objectUrl).all()
                    
                if force:
                    # Delete object and all status
                    self._dao.deleteObjects(session, statusOnAllDevices)
                    self._deleteObjectAndFixL2ap(session, objectUrl, obj)
                    with self.__lock:
                        self.__tbdObjects.remove((objectUrl, force))
                else:
                    if len(statusOnAllDevices) == 0:
                        logger.debug("cleanUpDb: Deploy status not found. Deleting object %s...", objectUrl)
                        # Now check if the object has children
                        if not OverlayDeployStatus.hasChildren(obj):
                            self._deleteObjectAndFixL2ap(session, objectUrl, obj)
                            with self.__lock:
                                self.__tbdObjects.remove((objectUrl, force))
                        else:
                            logger.debug("cleanUpDb: Object %s not deleted because it has children", objectUrl)
                    else:
                        logger.debug("cleanUpDb: Deploy status found. Object %s not deleted", objectUrl)
                        
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
        # Calculate how often dbCleanUp runs over every dispatch
        dbCleanUpRunLimit, dummy = divmod(self.maxDbCleanUpInterval, self.dispatchInterval)
        if dbCleanUpRunLimit == 0:
            dbCleanUpRunLimit = 1
        dbCleanUpRunCounter = 0
        
        try:
            while True:
                self.stopEvent.wait(self.dispatchInterval)
                if not self.stopEvent.is_set():
                    self.runJobs()
                    
                    # Dilute the dbCleanUp run
                    # logger.debug("dbCleanUpRunLimit = %d, dbCleanUpRunCounter = %d", dbCleanUpRunLimit, dbCleanUpRunCounter)
                    if dbCleanUpRunCounter >= dbCleanUpRunLimit:
                        self.cleanUpDb()
                        dbCleanUpRunCounter = 0
                    else:
                        dbCleanUpRunCounter = dbCleanUpRunCounter + 1
                else:
                    logger.debug("OverlayCommitQueue: stopEvent is set")
                    return
                
        except Exception as exc:
            logger.error("Encounted error '%s' on OverlayCommitQueue", exc)
            raise

# def main():        
    # from jnpr.openclos.overlay.overlayModel import OverlayDevice, OverlayFabric, OverlayTenant, OverlayVrf, OverlayNetwork, OverlaySubnet, OverlayL2port, OverlayAggregatedL2port
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
        # f1 = overlay.createFabric(session, 'f1', '', 65001, '2.2.2.0/24', [d1, d2])
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
