'''
Created on Feb 23, 2016

@author: yunli
'''
import os.path
import sys
sys.path.insert(0,os.path.abspath(os.path.dirname(__file__) + '/' + '../../..')) #trick to make it run from CLI

import unittest
from jnpr.openclos.overlay.overlayCommit import OverlayCommitQueue, OverlayCommitJob
from jnpr.openclos.overlay.overlayModel import OverlayDeployStatus, OverlayL2port, OverlayFabric, OverlayVrf
from jnpr.openclos.deviceConnector import CachedConnectionFactory
from jnpr.openclos.loader import loadLoggingConfig
from jnpr.openclos.dao import Dao

# Note: Please don't use MemoryDao. Use following TempFileDao to test threadpoolexecutor
# sqlite in-memory db does not support scoped_session well.
class TempFileDao(Dao):
    def _getDbUrl(self):
        loadLoggingConfig(appName = 'unittest')
        return 'sqlite:////tmp/sqllite3.db'
            
class TestOverlayCommitQueue(unittest.TestCase):
    def setUp(self):
        if os.path.isfile('/tmp/sqllite3.db'):
            os.remove('/tmp/sqllite3.db')
        from jnpr.openclos import deviceConnector
        deviceConnector.DEFAULT_AUTO_PROBE = 3
        self._dao = TempFileDao.getInstance()
        self.commitQueue = OverlayCommitQueue(self._dao)
        self.commitQueue.dbCleanUpInterval = 1
        self.commitQueue.deviceInterval = 1
        from jnpr.openclos.tests.unit.overlay.test_overlay import TestOverlayHelper
        self.helper = TestOverlayHelper({}, self._dao, self.commitQueue)
        
    def tearDown(self):
        # shutdown all live connections
        CachedConnectionFactory.getInstance()._stop()
        self.helper = None
        self.commitQueue = None
        TempFileDao._destroy()
        if os.path.isfile('/tmp/sqllite3.db'):
            os.remove('/tmp/sqllite3.db')
                            
    def testAddJobs(self):
        with self._dao.getReadWriteSession() as session:
            # create VRF creates DeployStatus and adds to commit queue
            self.helper._createVrf(session)
            statuss = session.query(OverlayDeployStatus).all()
            deviceQueues = self.commitQueue._getDeviceQueues()
            self.assertEqual(1, len(deviceQueues))
            # self.assertEqual(statuss[0].id, deviceQueues.values()[0].queue.get_nowait().id)
            # self.assertEqual(statuss[1].id, deviceQueues.values()[0].queue.get_nowait().id)
            
    def testAddDbCleanUp(self):
        with self._dao.getReadWriteSession() as session:
            # create VRF creates DeployStatus and adds to commit queue
            vrf = self.helper._createVrf(session)
            self.commitQueue.addDbCleanUp(vrf.getUrl(), True)
            tbdObjects = self.commitQueue._getTbdObjects()
            self.assertEqual(1, len(tbdObjects))
            self.assertEqual(tbdObjects[0], (vrf.getUrl(), True))

    def testRunJobs(self):
        self.commitQueue.start()
        
        import time
        with self._dao.getReadWriteSession() as session:
            self.helper._createFabric(session)
        time.sleep(1)
        # with self._dao.getReadSession() as session:
            # deployStatus = session.query(OverlayDeployStatus).one()
            # self.assertEqual("progress", deployStatus.status)
        time.sleep(2)
        self.commitQueue.stop()
        
        deviceQueues = self.commitQueue._getDeviceQueues()
        self.assertEqual(1, len(deviceQueues))
        self.assertTrue(self.commitQueue.thread is None)
        with self._dao.getReadSession() as session:
            deployStatus = session.query(OverlayDeployStatus).one()
            self.assertEqual("failure", deployStatus.status)

    def testCleanUpDb(self):
        with self._dao.getReadWriteSession() as session:
            fabric = self.helper._createFabric(session)
            url = fabric.getUrl()
            
        with self._dao.getReadWriteSession() as session:
            self.assertEqual(1, session.query(OverlayFabric).count())

        self.commitQueue.addDbCleanUp(url, True)
        self.commitQueue.cleanUpDb()
        
        with self._dao.getReadSession() as session:
            self.assertEqual(0, session.query(OverlayFabric).count())

class TestOverlayCommitJob(unittest.TestCase):
    def setUp(self):
        if os.path.isfile('/tmp/sqllite3.db'):
            os.remove('/tmp/sqllite3.db')
        self._dao = TempFileDao.getInstance()
        self.commitQueue = OverlayCommitQueue(self._dao)
        self.commitQueue.dispatchInterval = 1
        from jnpr.openclos.tests.unit.overlay.test_overlay import TestOverlayHelper
        self.helper = TestOverlayHelper({}, self._dao, self.commitQueue)
        
    def tearDown(self):
        # shutdown all live connections
        CachedConnectionFactory.getInstance()._stop()
        self.helper = None
        self.commitQueue = None
        TempFileDao._destroy()
        if os.path.isfile('/tmp/sqllite3.db'):
            os.remove('/tmp/sqllite3.db')
    
    def testUpdateStatusDeleteSuccess(self):
        with self._dao.getReadWriteSession() as session:
            port = self.helper._createL2port(session)
            portUrl = port.getUrl()
            deployment = OverlayDeployStatus("", portUrl, "delete", port.overlay_device, port.overlay_networks[0].overlay_vrf.overlay_tenant.overlay_fabric)
            deploy_id = deployment.id
            self._dao.createObjects(session, [deployment])
            session.commit()
            commitJob = OverlayCommitJob(self, deployment)
            commitJob.updateStatus("success")
            
        with self._dao.getReadWriteSession() as session:
            self.assertEqual(0, session.query(OverlayDeployStatus).filter(OverlayDeployStatus.id == deploy_id).count())
        
    def testUpdateStatusDeleteFailure(self):
        with self._dao.getReadWriteSession() as session:
            port = self.helper._createL2port(session)
            portUrl = port.getUrl()
            deployment = OverlayDeployStatus("", portUrl, "delete", port.overlay_device, port.overlay_networks[0].overlay_vrf.overlay_tenant.overlay_fabric)
            deploy_id = deployment.id
            self._dao.createObjects(session, [deployment])
            session.commit()
            commitJob = OverlayCommitJob(self, deployment)
            commitJob.updateStatus("failure")
            
        with self._dao.getReadWriteSession() as session:
            deployment = session.query(OverlayDeployStatus).filter(OverlayDeployStatus.id == deploy_id).one()
            self.assertEqual("failure", deployment.status)
        
    def testUpdateStatusDeleteProgress(self):
        with self._dao.getReadWriteSession() as session:
            port = self.helper._createL2port(session)
            portUrl = port.getUrl()
            deployment = OverlayDeployStatus("", portUrl, "delete", port.overlay_device, port.overlay_networks[0].overlay_vrf.overlay_tenant.overlay_fabric)
            deploy_id = deployment.id
            self._dao.createObjects(session, [deployment])
            session.commit()
            commitJob = OverlayCommitJob(self, deployment)
            commitJob.updateStatus("progress")
            
        with self._dao.getReadWriteSession() as session:
            deployment = session.query(OverlayDeployStatus).filter(OverlayDeployStatus.id == deploy_id).one()
            self.assertEqual("progress", deployment.status)
        
if __name__ == '__main__':
    unittest.main()
