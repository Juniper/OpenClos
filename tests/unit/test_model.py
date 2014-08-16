'''
Created on Jul 8, 2014

@author: moloyc
'''


import os
import sys
sys.path.insert(0,os.path.abspath(os.path.dirname(__file__) + '/' + '../..')) #trick to make it run from CLI

import unittest
import sqlalchemy
from sqlalchemy.orm import sessionmaker

from jnpr.openclos.model import ManagedElement, Pod, Device, Interface, InterfaceLogical, InterfaceDefinition, Base

def createPod(name, session):  
    pod = {}
    pod['spineCount'] = '3'
    pod['spineDeviceType'] = 'esx-switch'
    pod['leafCount'] = '5'
    pod['leafDeviceType'] = 'esx-switch'
    pod['interConnectPrefix'] = '1.2.0.0'
    pod['vlanPrefix'] = '1.3.0.0'
    pod['loopbackPrefix'] = '1.4.0.0'
    pod['spineAS'] = '100'
    pod['leafAS'] = '100'
    pod['topologyType'] = 'pod-dev-IF'
    pod = Pod(name, **pod)
    session.add(pod)
    session.commit()
    return pod

def createDevice(session, name):
    device = Device(name, "", "", "spine", "", createPod(name, session))
    session.add(device)
    session.commit()
    return device

def createInterface(session, name):
    IF = Interface(name, createDevice(session, name))
    session.add(IF)
    session.commit()
    
class TestManagedElement(unittest.TestCase):
    def test__str__(self):
        elem = {}
        elem['foo'] = 'bar'
        element = ManagedElement(**elem)
        self.assertEqual(element.__str__(), "{'foo': 'bar'}")
    def test__repr__(self):
        elem = {}
        elem['foo'] = 'bar'
        element = ManagedElement(**elem)
        self.assertEqual(element.__repr__(), "{'foo': 'bar'}")
              
class TestOrm(unittest.TestCase):
    def setUp(self):
        '''
        Change echo=True to troubleshoot ORM issue
        '''
        engine = sqlalchemy.create_engine('sqlite:///:memory:', echo=False)  
        Base.metadata.create_all(engine) 
        Session = sessionmaker(bind=engine)
        self.session = Session()

    def tearDown(self):
        self.session.close_all()

class TestPod(TestOrm):
  
    def testValidateEnum(self):
        with self.assertRaises(ValueError) as ve:
            Pod.validateEnum('Pod.TopologyTypeEnum', 'abcd', Pod.TopologyTypeEnum)
        with self.assertRaises(ValueError) as ve:
            Pod.validateEnum('Pod.TopologyTypeEnum', ['abcd'], Pod.TopologyTypeEnum)

    def testConstructorMisingAllRequiredFields(self):
        pod = {}
        with self.assertRaises(ValueError) as ve:
            Pod('testPod', **pod)
        error = ve.exception.message
        self.assertEqual(9, error.count(','))

    def testConstructorMisingFewRequiredFields(self):
        pod = {}
        pod['interConnectPrefix'] = '1.2.0.0'
        pod['leafAS'] = '100'
        with self.assertRaises(ValueError) as ve:
            Pod('testPod', **pod)
        error = ve.exception.message
        self.assertEqual(7, error.count(','), 'Number of missing field is not correct')
    
    def testConstructorPass(self):
        pod = {}
        pod['spineCount'] = '3'
        pod['spineDeviceType'] = 'esx-switch'
        pod['leafCount'] = '5'
        pod['leafDeviceType'] = 'esx-switch'
        pod['interConnectPrefix'] = '1.2.0.0'
        pod['vlanPrefix'] = '1.3.0.0'
        pod['loopbackPrefix'] = '1.4.0.0'
        pod['spineAS'] = '100'
        pod['leafAS'] = '100'
        pod['topologyType'] = 'pod-dev-IF' 
        self.assertTrue(Pod('testPod', **pod) is not None)

    def testOrm(self):
        pod = {}
        pod['spineCount'] = '3'
        pod['spineDeviceType'] = 'esx-switch'
        pod['leafCount'] = '5'
        pod['leafDeviceType'] = 'esx-switch'
        pod['interConnectPrefix'] = '1.2.0.0'
        pod['vlanPrefix'] = '1.3.0.0'
        pod['loopbackPrefix'] = '1.4.0.0'
        pod['spineAS'] = '100'
        pod['leafAS'] = '100'
        pod['topologyType'] = 'pod-dev-IF' 
        podOne = Pod('testPod', **pod)
        self.session.add(podOne)
        self.session.commit()
        
        fetched = self.session.query(Pod).one()
        self.assertEqual(podOne, fetched)
        #delete object
        self.session.delete(podOne)
        self.session.commit()
        self.assertEqual(0, self.session.query(Pod).count())

class TestDevice(TestOrm):
    def testConstructorPass(self):
        podOne = createPod('testpod', self.session)
        self.assertTrue(Device('testdevice', 'admin', 'admin', "spine", "", podOne) is not None)    

    def testOrm(self):
        podOne = createPod('testpod', self.session)
        device = Device('testdevice', 'admin', 'admin', "spine", "", podOne)
        self.session.add(device)
        self.session.commit()  
        fetched = self.session.query(Device).one()
        self.assertEqual(device, fetched)
        
        #delete object
        self.session.delete(device)
        self.session.commit()
        self.assertEqual(0, self.session.query(Device).count())
        
    def testRelationPodDevice(self):
        podOne = createPod('testpodOne', self.session)
        deviceOne = Device('testDeviceOne', 'admin', 'admin',  "spine", "", podOne)
        self.session.add(deviceOne)
           
        podTwo = createPod('testpodTwo', self.session)
        deviceTwo = Device('testDeviceOne', 'admin', 'admin',  "spine", "", podTwo)
        self.session.add(deviceTwo)
        deviceThree = Device('testDeviceOne', 'admin', 'admin',  "spine", "", podTwo)
        self.session.add(deviceThree)
        self.session.commit()

        self.assertEqual(2, self.session.query(Pod).count())
        pods = self.session.query(Pod).all()
        self.assertEqual(1, len(pods[0].devices))
        self.assertEqual(2, len(pods[1].devices))
        
        # check relation navigation from device to Pod
        devices = self.session.query(Device).all()
        self.assertIsNotNone(devices[0].pod)
        self.assertIsNotNone(devices[1].pod)
        self.assertEqual(podOne.id, devices[0].pod_id)
        self.assertEqual(podTwo.id, devices[1].pod_id)
    
            
        
class TestInterface(TestOrm):
    
    def testConstructorPass(self):
        deviceOne = createDevice(self.session, 'testdevice')
        self.assertTrue(Interface('testintf', deviceOne))
                        
    def testOrm(self):       
        deviceOne = createDevice(self.session, 'testdevice')
        IF = Interface('testintf', deviceOne)
        self.session.add(IF)
        self.session.commit()
        
        fetched = self.session.query(Interface).one()
        self.assertEqual(IF, fetched)
        
        #delete object
        self.session.delete(IF)
        self.session.commit()
        self.assertEqual(0, self.session.query(Interface).count())
        
    def testRelationDeviceInterface(self):
        # create pod
        # create device
        #create interface
        deviceOne = createDevice(self.session, 'testdevice')
        IFLone = Interface('testintf', deviceOne )
        self.session.add(IFLone)
             
        deviceTwo = createDevice(self.session, 'testdevice')
        IFLtwo = Interface('testintf', deviceTwo)
        self.session.add(IFLtwo)
        IFLthree = Interface('testintf', deviceTwo)
        self.session.add(IFLthree)
        self.session.commit()
        
        self.assertEqual(3, self.session.query(Interface).count())
        devices = self.session.query(Device).all()
        self.assertEqual(1, len(devices[0].interfaces))
        self.assertEqual(2, len(devices[1].interfaces))
        
        # check relation navigation from interface device
        
        interfaces = self.session.query(Interface).all()
        self.assertIsNotNone(interfaces[0].device)
        self.assertIsNotNone(interfaces[1].device)
        self.assertEqual(deviceOne.id, interfaces[0].device_id)
        self.assertEqual(deviceTwo.id, interfaces[1].device_id)
        
           
    def testRelationInterfacePeer(self):
        
        deviceOne = createDevice(self.session, 'testdevice')
        IFLone = Interface('testintf', deviceOne)
        self.session.add(IFLone)
        
        deviceTwo = createDevice(self.session, 'testdevice')
        IFLtwo = Interface('testintf', deviceTwo )
        self.session.add(IFLtwo)
        
        IFLone.peer = IFLtwo
        IFLtwo.peer = IFLone
        
        self.session.commit()

        interfaces = self.session.query(Interface).all()
        self.assertEqual(IFLtwo.id, interfaces[0].peer_id)
        self.assertEqual(IFLone.id, interfaces[1].peer_id)
               
       

class TestInterfaceLogical(TestOrm):
    
    def testConstructorPass(self):
        deviceOne = createDevice(self.session, 'testdevice')
        self.assertTrue(InterfaceLogical('testIntf', deviceOne) is not None)
        self.assertTrue(InterfaceLogical('testIntf', deviceOne, '1.2.3.4') is not None)
        self.assertTrue(InterfaceLogical('testIntf', deviceOne, '1.2.3.4', 9000) is not None)


    def testOrm(self):
        
        deviceOne = createDevice(self.session, 'testdevice')
        IFL = InterfaceLogical('testIntf', deviceOne, '1.2.3.4', 9000)
        self.session.add(IFL)
        self.session.commit()

        fetched = self.session.query(InterfaceLogical).one()
        self.assertEqual(IFL, fetched)
        self.assertEqual("logical", fetched.type)
        
        #delete object
        self.session.delete(IFL)
        self.session.commit()
        self.assertEqual(0, self.session.query(InterfaceLogical).count())
        
class TestInterfaceDefinition(TestOrm):
    
    
    def testConstructorPass(self):
        deviceOne = createDevice(self.session, 'testdevice')
        self.assertTrue(InterfaceDefinition('testIntf', deviceOne) is not None)
        self.assertTrue(InterfaceDefinition('testIntf', deviceOne, 9000) is not None)
        
    def testOrm(self):
        deviceOne = createDevice(self.session, 'testdevice')
        IFD = InterfaceDefinition('testIntfdef', deviceOne, 9000)
        self.session.add(IFD)
        self.session.commit()
        
        fetched = self.session.query(InterfaceDefinition).one()
        self.assertEqual(IFD, fetched)
        self.assertEqual("physical", fetched.type)
        
        #delete object
        self.session.delete(IFD)
        self.session.commit()
        self.assertEqual(0, self.session.query(InterfaceDefinition).count())
         
if __name__ == '__main__':
    unittest.main()
