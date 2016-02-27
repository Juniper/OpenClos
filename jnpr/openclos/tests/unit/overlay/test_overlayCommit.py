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
        self._conf = {}
        self._conf['plugin'] = [{'name': 'overlay', 'package': 'jnpr.openclos.overlay'}]
        self._dao = TempFileDao.getInstance()
        self._overlay = Overlay(self._conf, self._dao)
        self.helper = TestOverlayHelper(self._conf, self._dao)
    
    def tearDown(self):
        ''' Deletes 'out' folder under test dir'''
        if os.path.isfile('/tmp/sqllite3.db'):
            os.remove('/tmp/sqllite3.db')
        self.helper = None
        self._overlay = None
        TempFileDao._destroy()
    
    def testAddJob(self):
        commitQueue = OverlayCommitQueue(self._overlay, 10, 1)
        with self._dao.getReadWriteSession() as session:
            device = self.helper._createDevice(session)
            vrf = self.helper._createVrf(session)
            status = self.helper._createDeployStatus(session, device, vrf)
            job = commitQueue.addJob(status)
            deviceQueues = commitQueue._getDeviceQueues()
            self.assertEqual(status.id, job.id)
            self.assertEqual(job, deviceQueues[device.id].get_nowait())
            
    def testRunJobs(self):
        commitQueue = OverlayCommitQueue(self._overlay, 10, 1)
        
        with self._dao.getReadWriteSession() as session:
            vrf = self.helper._createVrf(session)
            device = session.query(OverlayDevice).one()
            status = self.helper._createDeployStatus(session, device, vrf)
            job = commitQueue.addJob(status)
        
        commitQueue.runJobs()
        
        import time
        time.sleep(5)
        
        deviceQueues = commitQueue._getDeviceQueues()
        self.assertEqual(0, len(deviceQueues))
            
    def testStartStop(self):
        commitQueue = OverlayCommitQueue(self._overlay, 10, 1)
        commitQueue.start()
        commitQueue.stop()
        self.assertFalse(commitQueue.thread.isAlive())
        
if __name__ == '__main__':
    unittest.main()
