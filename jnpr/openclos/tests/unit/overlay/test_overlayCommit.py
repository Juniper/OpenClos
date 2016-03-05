'''
Created on Feb 23, 2016

@author: yunli
'''
import os
import os.path
import sys
sys.path.insert(0,os.path.abspath(os.path.dirname(__file__) + '/' + '../../..')) #trick to make it run from CLI

import unittest
import shutil
from jnpr.openclos.overlay.overlay import Overlay
from jnpr.openclos.overlay.overlayCommit import OverlayCommitJob, OverlayCommitQueue
from jnpr.openclos.overlay.overlayModel import OverlayFabric, OverlayTenant, OverlayVrf, OverlayNetwork, OverlaySubnet, OverlayDevice, OverlayL3port, OverlayL2port, OverlayAe, OverlayDeployStatus
from jnpr.openclos.loader import loadLoggingConfig
from jnpr.openclos.dao import Dao
from jnpr.openclos.tests.unit.overlay.test_overlay import TestOverlayHelper
from jnpr.openclos.deviceConnector import CachedConnectionFactory

# Note: Please don't use MemoryDao. Use following TempFileDao to test threadpoolexecutor
# sqlite in-memory db does not support scoped_session well. Every connection is a new one:
# Quote From http://sqlite.org/inmemorydb.html
# When this is done, no disk file is opened. Instead, a new database is created purely in memory. 
# The database ceases to exist as soon as the database connection is closed. Every :memory: database is distinct from every other. 
# So, opening two database connections each with the filename ":memory:" will create two independent in-memory databases.
class TempFileDao(Dao):
    def _getDbUrl(self):
        loadLoggingConfig(appName = 'unittest')
        return 'sqlite:////tmp/sqllite3.db'
        
class TestOverlayCommitQueue(unittest.TestCase):
    def setUp(self):
        if os.path.isfile('/tmp/sqllite3.db'):
            os.remove('/tmp/sqllite3.db')
        from jnpr.openclos import deviceConnector
        deviceConnector.DEFAULT_AUTO_PROBE = 1
        self._dao = TempFileDao.getInstance()
        self.helper = TestOverlayHelper(None, self._dao)
        self.commitQueue = OverlayCommitQueue.getInstance()
        self.commitQueue.dao = self._dao
        self.commitQueue.dispatchInterval = 1
        
    def tearDown(self):
        # shutdown all live connections
        CachedConnectionFactory.getInstance()._stop()
        ''' Deletes 'out' folder under test dir'''
        if os.path.isfile('/tmp/sqllite3.db'):
            os.remove('/tmp/sqllite3.db')
        self.helper = None
        TempFileDao._destroy()
        self.commitQueue = None
    
    def testAddJob(self):
        with self.commitQueue.dao.getReadWriteSession() as session:
            vrf = self.helper._createVrf(session)
            device = session.query(OverlayDevice).one()
            status = self.helper._createDeployStatus(session, device, vrf)
            job = self.commitQueue.addJob(status)
            deviceQueues = self.commitQueue._getDeviceQueues()
            self.assertEqual(status.id, job.id)
            self.assertEqual(job, deviceQueues[job.queueId].get_nowait())
            
    def testRunJobs(self):
        self.commitQueue.start()
        
        with self.commitQueue.dao.getReadWriteSession() as session:
            vrf = self.helper._createVrf(session)
            device = session.query(OverlayDevice).one()
            status = self.helper._createDeployStatus(session, device, vrf)
            job = self.commitQueue.addJob(status)
        import time
        time.sleep(5)
        self.commitQueue.stop()
        
        deviceQueues = self.commitQueue._getDeviceQueues()
        self.assertEqual(0, len(deviceQueues))
        self.assertFalse(self.commitQueue.thread.isAlive())
        
if __name__ == '__main__':
    unittest.main()
