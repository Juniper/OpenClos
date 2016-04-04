'''
Created on Feb 23, 2016

@author: yunli
'''
import os.path
import sys
sys.path.insert(0,os.path.abspath(os.path.dirname(__file__) + '/' + '../../..')) #trick to make it run from CLI

import unittest
from jnpr.openclos.overlay.overlayCommit import OverlayCommitQueue, OverlayCommitJob
from jnpr.openclos.overlay.overlayModel import OverlayDeployStatus, OverlayL2port
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
                            
    def testAddJobs(self):
        with self._dao.getReadWriteSession() as session:
            # create VRF creates DeployStatus and adds to commit queue
            self.helper._createVrf(session)
            statuss = session.query(OverlayDeployStatus).all()
            deviceQueues = self.commitQueue._getDeviceQueues()
            self.assertEqual(1, len(deviceQueues))
            self.assertEqual(statuss[0].id, deviceQueues.values()[0].get_nowait().id)
            self.assertEqual(statuss[1].id, deviceQueues.values()[0].get_nowait().id)
            
    

    def testRunJobs(self):
        self.commitQueue.start()
        
        import time
        with self._dao.getReadWriteSession() as session:
            vrf = self.helper._createFabric(session)
        time.sleep(1)
        with self._dao.getReadSession() as session:
            deployStatus = session.query(OverlayDeployStatus).one()
            self.assertEqual("progress", deployStatus.status)
        time.sleep(2)
        self.commitQueue.stop()
        
        deviceQueues = self.commitQueue._getDeviceQueues()
        self.assertEqual(0, len(deviceQueues))
        self.assertFalse(self.commitQueue.thread.isAlive())
        with self._dao.getReadSession() as session:
            deployStatus = session.query(OverlayDeployStatus).one()
            self.assertEqual("failure", deployStatus.status)


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
            deployment = OverlayDeployStatus("", portUrl, "delete", port.overlay_device, port.overlay_networks[0].overlay_vrf)
            self._dao.createObjects(session, [deployment])
            session.commit()
            commitJob = OverlayCommitJob(self, deployment)
            commitJob.updateStatus("success")
            self.assertEqual([], session.query(OverlayL2port).all())
            self.assertEqual([], session.query(OverlayDeployStatus).filter(OverlayDeployStatus.object_url == portUrl).all())
        
    def testUpdateStatusDeleteFailure(self):
        with self._dao.getReadWriteSession() as session:
            port = self.helper._createL2port(session)
            portUrl = port.getUrl()
            deployment = OverlayDeployStatus("", portUrl, "delete", port.overlay_device, port.overlay_networks[0].overlay_vrf)
            self._dao.createObjects(session, [deployment])
            session.commit()
            commitJob = OverlayCommitJob(self, deployment)
            commitJob.updateStatus("failure")
            self.assertIsNotNone(session.query(OverlayL2port).one())
            self.assertEqual(2, len(session.query(OverlayDeployStatus).filter(OverlayDeployStatus.object_url == portUrl).all()))
        
    def testUpdateStatusDeleteProgress(self):
        with self._dao.getReadWriteSession() as session:
            port = self.helper._createL2port(session)
            portUrl = port.getUrl()
            deployment = OverlayDeployStatus("", portUrl, "delete", port.overlay_device, port.overlay_networks[0].overlay_vrf)
            self._dao.createObjects(session, [deployment])
            session.commit()
            commitJob = OverlayCommitJob(self, deployment)
            commitJob.updateStatus("progress")
            self.assertIsNotNone(session.query(OverlayL2port).one())
            self.assertEqual(2, len(session.query(OverlayDeployStatus).filter(OverlayDeployStatus.object_url == portUrl).all()))

if __name__ == '__main__':
    unittest.main()
