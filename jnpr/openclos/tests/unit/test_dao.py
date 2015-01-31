'''
Created on Aug 26, 2014

@author: moloyc
'''
import unittest
from sqlalchemy import exc
from flexmock import flexmock

import jnpr.openclos.util
from jnpr.openclos.dao import Dao
from jnpr.openclos.model import Pod, Device, Interface, InterfaceDefinition, TrapGroup

class TestDao(unittest.TestCase):
    def setUp(self):
        '''Creates Dao with in-memory DB'''
        jnpr.openclos.util.loggingInitialized = True
        self.conf = {}
        self.conf['dbUrl'] = 'sqlite:///'
    
    def tearDown(self):
        pass    
    def testInvalidConfig(self):
        with self.assertRaises(ValueError):
            dao = Dao({})

    def testCreateObjects(self):
        from test_model import createDevice
        #self.conf['debugSql'] = True
        dao = Dao(self.conf)
        session = dao.Session()
        
        device = createDevice(session, "test")
        ifd1 = InterfaceDefinition('ifd1', device, 'downlink')
        ifd2 = InterfaceDefinition('ifd2', device, 'downlink')
        ifd3 = InterfaceDefinition('ifd3', device, 'downlink')
        ifd4 = InterfaceDefinition('ifd4', device, 'downlink')
        dao.createObjects([ifd1, ifd2, ifd3, ifd4])

        self.assertEqual(4, len(dao.getAll(InterfaceDefinition)))
        self.assertEqual(1, len(dao.getObjectsByName(InterfaceDefinition, 'ifd1')))
        self.assertEqual(1, len(dao.getObjectsByName(InterfaceDefinition, 'ifd2')))

    def testDeleteNonExistingPod(self):
        dao = Dao(self.conf)
        dict = {'devicePassword': 'test'}
        pod = Pod('unknown', dict)
        with self.assertRaises(exc.InvalidRequestError):
            dao.deleteObject(pod)

    def testCascadeDeletePodDevice(self):
        from test_model import createDevice
        #self.conf['debugSql'] = True
        dao = Dao(self.conf)
        session = dao.Session()
        device = createDevice(session, "test")

        self.assertEqual(1, len(dao.getAll(Pod)))
        self.assertEqual(1, len(dao.getAll(Device)))
        
        dao.deleteObject(device.pod)
        
        self.assertEqual(0, len(dao.getAll(Pod)))
        self.assertEqual(0, len(dao.getAll(Device)))

    def testCascadeDeletePodDeviceInterface(self):
        from test_model import createInterface
        #self.conf['debugSql'] = True
        dao = Dao(self.conf)
        session = dao.Session()
        interface = createInterface(session, "test")
        
        self.assertEqual(1, len(dao.getAll(Pod)))
        self.assertEqual(1, len(dao.getAll(Device)))
        self.assertEqual(1, len(dao.getAll(Interface)))

        dao.deleteObject(interface.device.pod)
        
        self.assertEqual(0, len(dao.getAll(Pod)))
        self.assertEqual(0, len(dao.getAll(Device)))
        self.assertEqual(0, len(dao.getAll(Interface)))
        
    def testGetObjectById(self):
        from test_model import createPod
        #self.conf['debugSql'] = True
        dao = Dao(self.conf)
        session = dao.Session()
        pod = createPod("test", session)

    def testGetConnectedInterconnectIFDsFilterFakeOnes(self):
        from test_model import createDevice
        dao = Dao(self.conf)
        device = createDevice(dao.Session, "test")
        flexmock(dao.Session).should_receive('query.filter.filter.order_by.all').\
            and_return([InterfaceDefinition("et-0/1/0", None, 'uplink'), InterfaceDefinition("et-0/1/1", None, 'uplink'), 
                        InterfaceDefinition("uplink-2", None, 'uplink'), InterfaceDefinition("uplink-3", None, 'uplink')])
        
        filteredIfds = dao.getConnectedInterconnectIFDsFilterFakeOnes(device)
        self.assertEqual(2, len(filteredIfds))

    def testConfigureTrapGroupFromInstaller ( self ):
        #self.conf['dbUrl'] = 'mysql://root:<pass>@localhost/openclos' 
        dao = Dao(self.conf)

        trapGroups = dao.getAll(TrapGroup)
        if trapGroups:
            dao.deleteObjects ( trapGroups )

        newtargets = []
        for newtarget in ['1.2.3.4', '1.2.3.5']:
            newtargets.append ( TrapGroup ( 'networkdirector_trap_group', newtarget, int('10162') ) )
            newtargets.append ( TrapGroup ( 'space', newtarget, None ) )
            newtargets.append ( TrapGroup ( 'openclos_trap_group', newtarget, 20162 ) )
        dao.createObjects(newtargets)

        self.assertEqual(6, len(dao.getAll(TrapGroup)))
        self.assertEqual(10162, dao.getAll(TrapGroup)[0].port)
        self.assertEqual(20162, dao.getAll(TrapGroup)[2].port)
        self.assertEqual(162, dao.getAll(TrapGroup)[4].port)

    @unittest.skip('manual test')        
    def testConnectionCleanup(self):
        import threading
        import time

        self.conf['dbUrl'] = 'mysql://root:<pass>@localhost/openclos' 
        dao = Dao(self.conf)

        def getPods():
            return dao.getAll(Pod)
        
        threads = []
        for i in xrange(10):
            threads.append(threading.Thread(target = getPods))
            threads[i].start()
            
        for thread in threads:
            thread.join()
        
        print 'done 10 threads'
        time.sleep(30)
        dao.cleanup()
        print 'done dao.cleanup()'
        time.sleep(30)
        getPods()
        print 'done fresh getPods()'
        time.sleep(30)
        dao.cleanup()
        print 'done final dao.cleanup()'
        time.sleep(30)
         
       
        
        