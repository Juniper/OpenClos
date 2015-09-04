'''
Created on Aug 26, 2014

@author: moloyc
'''
import unittest
from sqlalchemy import exc
from flexmock import flexmock

import jnpr.openclos.util
from jnpr.openclos.model import Pod, Device, Interface, InterfaceDefinition, TrapGroup
from jnpr.openclos.dao import AbstractDao
from jnpr.openclos.exception import InvalidConfiguration

class TestAbstractDao(unittest.TestCase):
    def testInit(self):
        with self.assertRaises(NotImplementedError):
            AbstractDao()

class InMemoryDao(AbstractDao):
    def _getDbUrl(self):
        jnpr.openclos.propLoader.loadLoggingConfig(appName = 'unittest')
        return 'sqlite:///'

class TestDao(unittest.TestCase):
    def setUp(self):
        self.__dao = InMemoryDao.getInstance()
    def tearDown(self):
        InMemoryDao._destroy()
    

    def testInvalidConfig(self):
        class BadDao(AbstractDao):
            def _getDbUrl(self):
                return 'unknown://'
        with self.assertRaises(InvalidConfiguration):
            BadDao()

    def testCreateObjects(self):
        from test_model import createDevice

        with self.__dao.getReadWriteSession() as session:
            device = createDevice(session, "test")
            ifd1 = InterfaceDefinition('ifd1', device, 'downlink')
            ifd2 = InterfaceDefinition('ifd2', device, 'downlink')
            ifd3 = InterfaceDefinition('ifd3', device, 'downlink')
            ifd4 = InterfaceDefinition('ifd4', device, 'downlink')
            self.__dao.createObjects(session, [ifd1, ifd2, ifd3, ifd4])

        with self.__dao.getReadSession() as session:
            self.assertEqual(4, len(self.__dao.getAll(session, InterfaceDefinition)))
            self.assertEqual(1, len(self.__dao.getObjectsByName(session, InterfaceDefinition, 'ifd1')))
            self.assertEqual(1, len(self.__dao.getObjectsByName(session, InterfaceDefinition, 'ifd2')))
        
    def testDeleteNonExistingPod(self):
        dict = {'devicePassword': 'test'}
        pod = Pod('unknown', dict)
        with self.assertRaises(exc.InvalidRequestError):
            with self.__dao.getReadWriteSession() as session:
                self.__dao.deleteObject(session, pod)
        
    def testCascadeDeletePodDevice(self):
        from test_model import createDevice

        with self.__dao.getReadWriteSession() as session:
            device = createDevice(session, "test")

            self.assertEqual(1, len(self.__dao.getAll(session, Pod)))
            self.assertEqual(1, len(self.__dao.getAll(session, Device)))
            
            self.__dao.deleteObject(session, device.pod)
        
        with self.__dao.getReadSession() as session:
            self.assertEqual(0, len(self.__dao.getAll(session, Pod)))
            self.assertEqual(0, len(self.__dao.getAll(session, Device)))
        
    def testCascadeDeletePodDeviceInterface(self):
        from test_model import createInterface
        with self.__dao.getReadWriteSession() as session:
            interface = createInterface(session, "test")
            
            self.assertEqual(1, len(self.__dao.getAll(session, Pod)))
            self.assertEqual(1, len(self.__dao.getAll(session, Device)))
            self.assertEqual(1, len(self.__dao.getAll(session, Interface)))
    
            self.__dao.deleteObject(session, interface.device.pod)
        
        with self.__dao.getReadSession() as session:
            self.assertEqual(0, len(self.__dao.getAll(session, Pod)))
            self.assertEqual(0, len(self.__dao.getAll(session, Device)))
            self.assertEqual(0, len(self.__dao.getAll(session, Interface)))
        
    def testGetObjectById(self):
        from test_model import createPod
        with self.__dao.getReadWriteSession() as session:
            pod = createPod("test", session)

        with self.__dao.getReadSession() as session:
            self.assertEqual(1, len(self.__dao.getAll(session, Pod)))
        
    def testGetConnectedInterconnectIFDsFilterFakeOnes(self):
        from test_model import createDevice
        with self.__dao.getReadWriteSession() as session:
            device = createDevice(session, "test")
            fakeSession = flexmock(session)
            fakeSession.should_receive('query.filter.filter.filter.order_by.all').\
                and_return([InterfaceDefinition("et-0/1/0", None, 'uplink'), InterfaceDefinition("et-0/1/1", None, 'uplink'), 
                            InterfaceDefinition("uplink-2", None, 'uplink'), InterfaceDefinition("uplink-3", None, 'uplink')])
        
            filteredIfds = self.__dao.getConnectedInterconnectIFDsFilterFakeOnes(fakeSession, device)
            self.assertEqual(2, len(filteredIfds))

    @unittest.skip('manual test')        
    def testConnectionCleanup(self):
        import threading
        import time

        class MySqlDao(AbstractDao):
            def _getDbUrl(self):
                jnpr.openclos.propLoader.loadLoggingConfig(appName = 'unittest')
                return 'mysql://root:<password>@localhost/openclos'

        dao = MySqlDao.getInstance()

        def getPods():
            with dao.getReadWriteSession() as session:
                return dao.getAll(session, Pod)
        
        threads = []
        for i in xrange(10):
            threads.append(threading.Thread(target = getPods))
            threads[i].start()
        for thread in threads:
            thread.join()
        
        print 'done 10 threads'
        time.sleep(40)
        
        threads = []
        for i in xrange(10):
            threads.append(threading.Thread(target = getPods))
            threads[i].start()
        for thread in threads:
            thread.join()
        
        print 'done 10 threads'
        time.sleep(40)

        MySqlDao._destroy()
        print 'done final __dao destroy'
        time.sleep(30)
         
       
        
        