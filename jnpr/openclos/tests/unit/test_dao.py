'''
Created on Aug 26, 2014

@author: moloyc
'''
import unittest
from sqlalchemy import exc

from jnpr.openclos.dao import Dao
from jnpr.openclos.model import Pod, Device, Interface, InterfaceLogical, InterfaceDefinition

class TestDao(unittest.TestCase):
    def setUp(self):
        
        '''Creates Dao with in-memory DB'''
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

