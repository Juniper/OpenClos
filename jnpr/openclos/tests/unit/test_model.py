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
from jnpr.openclos.model import ManagedElement, Pod, LeafSetting, Device, Interface, InterfaceLogical, InterfaceDefinition, Base, AdditionalLink, CablingPlan, TrapGroup
from jnpr.openclos.exception import InvalidUplinkThreshold

def createPodObj(name):  
    pod = {}
    pod['spineCount'] = '2'
    pod['spineDeviceType'] = 'qfx-5100-24q-2p'
    pod['leafCount'] = '2'
    pod['leafSettings'] = [{'deviceType':'qfx-5100-48s-6q'}]
    pod['interConnectPrefix'] = '1.2.0.0'
    pod['vlanPrefix'] = '1.3.0.0'
    pod['hostOrVmCountPerLeaf'] = 100
    pod['loopbackPrefix'] = '1.4.0.0'
    pod['managementPrefix'] = '172.32.30.101/24'
    pod['spineAS'] = '100'
    pod['leafAS'] = '100'
    pod['topologyType'] = 'threeStage'
    pod['inventory'] = 'inventoryAnotherPod.json'
    pod['devicePassword'] = 'test'
    return Pod(name, pod)

def createPod(name, session):  
    pod = createPodObj(name)
    session.add(pod)
    session.commit()
    return pod

def createDevice(session, name):
    device = Device(name, "", "", "", "spine", "11:12:13:14:15:16", "1.2.3.4/24", createPod(name, session))
    session.add(device)
    session.commit()
    return device

def createPodDevice(session, name, pod):
    device = Device(name, "", "", "", "spine", "11:12:13:14:15:16", "1.2.3.4", pod)
    session.add(device)
    session.commit()
    return device

def createInterface(session, name):
    interface = Interface(name, createDevice(session, name))
    session.add(interface)
    session.commit()
    return interface
    
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
    
    def testPodValidateSuccess(self):
        pod = {}
        pod['spineCount'] = '2'
        pod['spineDeviceType'] = 'qfx-5100-24q-2p'
        pod['leafCount'] = '2'
        pod['leafSettings'] = [{'deviceType':'qfx-5100-48s-6q'}]
        pod['hostOrVmCountPerLeaf'] = 100
        pod['interConnectPrefix'] = '1.2.0.0'
        pod['vlanPrefix'] = '1.3.0.0'
        pod['loopbackPrefix'] = '1.4.0.0'
        pod['managementPrefix'] = '172.32.30.101/24'
        pod['spineAS'] = '100'
        pod['leafAS'] = '100'
        pod['topologyType'] = 'threeStage'
        pod['inventory'] = 'inventoryUnitTest.json'
        pod['devicePassword'] = 'test'
        pod = Pod("test", pod)
        
        pod.validate()
  
    #def testPodValidateMisingAllRequiredFields(self):
    #    pod = {}
    #    with self.assertRaises(ValueError) as ve:
    #        pod = Pod('testPod', pod)
    #        pod.validateRequiredFields()
    #    error = ve.exception.message
    #    self.assertEqual(11, error.count(','))

    #def testPodValidateMisingFewRequiredFields(self):
    #    pod = {}
    #    pod['interConnectPrefix'] = '1.2.0.0'
    #    pod['leafAS'] = '100'
    #    with self.assertRaises(ValueError) as ve:
    #        pod = Pod('testPod', pod)
    #        pod.validateRequiredFields()
    #    error = ve.exception.message
    #    self.assertEqual(9, error.count(','), 'Number of missing field is not correct')

    #def testPodValidateMisingBadIpAddress(self):
    #    pod = {}
    #    pod['interConnectPrefix'] = '1.2.0.0.0'
    #    pod['vlanPrefix'] = '1.2.0.257'
    #    pod['managementPrefix'] = '172.32.30.101/24'
    #    pod['loopbackPrefix'] = None
    #    with self.assertRaises(ValueError) as ve:
    #        pod = Pod('testPod', pod)
    #        pod.validateIPaddr()
    #    error = ve.exception.message
    #    self.assertEqual(2, error.count(','), 'Number of bad Ip address format field is not correct')

    def testPodVaidateLeafUplinkcountMustBeUp(self):
        pod = createPodObj('name')
        with self.assertRaises(InvalidUplinkThreshold) as ve:
            pod.leafUplinkcountMustBeUp = 1
            pod.validate()
        error = ve.exception.message
        self.assertTrue('leafUplinkcountMustBeUp' in error and 'should be between 2 and spineCount' in error)

        pod = createPodObj('name')
        self.assertEqual(2, pod.leafUplinkcountMustBeUp)

    def testConstructorPass(self):
        pod = {}
        pod['spineCount'] = '2'
        pod['spineDeviceType'] = 'qfx-5100-24q-2p'
        pod['leafCount'] = '2'
        pod['leafSettings'] = [{'deviceType':'qfx-5100-48s-6q'}]
        pod['interConnectPrefix'] = '1.2.0.0'
        pod['vlanPrefix'] = '1.3.0.0'
        pod['loopbackPrefix'] = '1.4.0.0'
        pod['managementPrefix'] = '172.32.30.101/24'
        pod['spineAS'] = '100'
        pod['leafAS'] = '4294967295'
        pod['topologyType'] = 'threeStage'
        pod['inventory'] = 'inventoryUnitTest.json'
        pod['outOfBandAddressList'] = ['1.2.3.4', '5.6.7.8']
        pod['outOfBandGateway'] = '1.3.5.254'
        pod['devicePassword'] = 'test'
        
        constructedPod = Pod('testPod', pod) 
        self.assertTrue(constructedPod is not None)
        self.assertEqual(','.join(['1.2.3.4', '5.6.7.8']), constructedPod.outOfBandAddressList)
        self.assertEqual('1.3.5.254', constructedPod.outOfBandGateway)
        self.assertEqual(4294967295, constructedPod.leafAS)


    def testOrm(self):
        pod = {}
        pod['spineCount'] = '2'
        pod['spineDeviceType'] = 'qfx-5100-24q-2p'
        pod['leafCount'] = '2'
        pod['leafSettings'] = [{'deviceType':'qfx-5100-48s-6q'}]
        pod['interConnectPrefix'] = '1.2.0.0'
        pod['vlanPrefix'] = '1.3.0.0'
        pod['loopbackPrefix'] = '1.4.0.0'
        pod['managementPrefix'] = '172.32.30.101/24'
        pod['spineAS'] = '100'
        pod['leafAS'] = '100'
        pod['topologyType'] = 'threeStage'
        pod['inventory'] = 'inventoryLabKurt.json'
        pod['outOfBandAddressList'] = ['1.2.3.4', '5.6.7.8']
        pod['devicePassword'] = 'test'
        podOne = Pod('testPod', pod)
        self.session.add(podOne)
        self.session.commit()
        
        fetched = self.session.query(Pod).one()
        self.assertEqual(podOne, fetched)
        #delete object
        self.session.delete(podOne)
        self.session.commit()
        self.assertEqual(0, self.session.query(Pod).count())

class TestLeafSetting(TestOrm):
    def testConstructorPass(self):
        podOne = createPod('testpod', self.session)
        self.assertTrue(LeafSetting('qfx5100-48s-6q', podOne.id) is not None)    

    def testOrm(self):
        podOne = createPod('testpod', self.session)
        leafSetting = LeafSetting('qfx5100-48s-6q', podOne.id)
        podOne.leafSettings = [leafSetting]
        self.session.merge(podOne)
        self.session.commit()
        
        fetched = self.session.query(LeafSetting).one()
        self.assertEqual(leafSetting, fetched)
        
        fetched = self.session.query(Pod).one()
        self.assertEqual(1, len(fetched.leafSettings))

        #delete object
        self.session.delete(podOne)
        self.session.commit()
        self.assertEqual(0, self.session.query(LeafSetting).count())

class TestCablingPlan(TestOrm):
    def testConstructorPass(self):
        podOne = createPod('testpod', self.session)
        self.assertTrue(CablingPlan(podOne.id, 'cabling json', 'cabling dot') is not None)    

    def testOrm(self):
        podOne = createPod('testpod', self.session)
        cablingPlan = CablingPlan(podOne.id, 'cabling json', 'cabling dot')
        podOne.cablingPlan = cablingPlan
        self.session.merge(podOne)
        self.session.commit()
        
        fetched = self.session.query(CablingPlan).one()
        self.assertEqual(cablingPlan, fetched)
        
        fetched = self.session.query(Pod).one()
        self.assertIsNotNone(fetched.cablingPlan)

        #delete object
        self.session.delete(podOne)
        self.session.commit()
        self.assertEqual(0, self.session.query(CablingPlan).count())

class TestDevice(TestOrm):
    def testConstructorPass(self):
        podOne = createPod('testpod', self.session)
        self.assertTrue(Device('testdevice', 'qfx-5100-48s-6q', 'admin', 'admin', "spine", "", "", podOne) is not None)    

    def testOrm(self):
        podOne = createPod('testpod', self.session)
        device = Device('testdevice', 'qfx-5100-48s-6q', 'admin', 'admin', "spine", "", "", podOne, "provision", "VB1234567890")
        self.session.add(device)
        self.session.commit()  
        fetched = self.session.query(Device).one()
        self.assertEqual(device, fetched)
        
        #delete object
        self.session.delete(device)
        self.session.commit()
        self.assertEqual(0, self.session.query(Device).count())
    
    def testLargeAsn(self):
        podOne = createPod('testpod', self.session)
        device = Device('testdevice', 'qfx-5100-48s-6q', 'admin', 'admin', "spine", "", "", podOne)
        device.asn = 4294967295
        self.session.add(device)
        self.session.commit()  
        fetched = self.session.query(Device).one()
        self.assertEqual(device, fetched)        
        
    def testRelationPodDevice(self):
        podOne = createPod('testpodOne', self.session)
        deviceOne = Device('testDeviceOne', 'qfx-5100-48s-6q', 'admin', 'admin',  "spine", "", "", podOne)
        self.session.add(deviceOne)
           
        podTwo = createPod('testpodTwo', self.session)
        deviceTwo = Device('testDeviceTwo', 'qfx-5100-48s-6q', 'admin', 'admin',  "spine", "", "", podTwo)
        self.session.add(deviceTwo)
        deviceThree = Device('testDeviceThree', 'qfx-5100-48s-6q', 'admin', 'admin',  "spine", "", "", podTwo)
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
        self.assertTrue(Interface('et-0/0/0', deviceOne))
                        
    def testOrm(self):       
        deviceOne = createDevice(self.session, 'testdevice')
        IF = Interface('et-0/0/0', deviceOne)
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
        IFLone = Interface('et-0/0/0', deviceOne )
        self.session.add(IFLone)
             
        deviceTwo = createDevice(self.session, 'testdevice')
        IFLtwo = Interface('et-0/0/0', deviceTwo)
        self.session.add(IFLtwo)
        IFLthree = Interface('et-0/0/1', deviceTwo)
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
        IFLone = Interface('et-0/0/0', deviceOne)
        self.session.add(IFLone)
        
        deviceTwo = createDevice(self.session, 'testdevice')
        IFLtwo = Interface('et-0/0/0', deviceTwo )
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
        self.assertTrue(InterfaceLogical('et-0/0/0', deviceOne) is not None)
        self.assertTrue(InterfaceLogical('et-0/0/1', deviceOne, '1.2.3.4') is not None)
        self.assertTrue(InterfaceLogical('et-0/0/2', deviceOne, '1.2.3.4', 9000) is not None)


    def testOrm(self):
        
        deviceOne = createDevice(self.session, 'testdevice')
        IFL = InterfaceLogical('et-0/0/0', deviceOne, '1.2.3.4', 9000)
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
        self.assertTrue(InterfaceDefinition('et-0/0/0', deviceOne, 'downlink') is not None)
        self.assertTrue(InterfaceDefinition('et-0/0/1', deviceOne, 'uplink', 9000) is not None)
        
    def testOrm(self):
        deviceOne = createDevice(self.session, 'testdevice')
        IFD = InterfaceDefinition('et-0/0/0', deviceOne, 'uplink')
        self.session.add(IFD)
        self.session.commit()
        
        fetched = self.session.query(InterfaceDefinition).one()
        self.assertEqual(IFD, fetched)
        self.assertEqual("physical", fetched.type)
        
        #delete object
        self.session.delete(IFD)
        self.session.commit()
        self.assertEqual(0, self.session.query(InterfaceDefinition).count())
         
    def testQueryOrderBy(self):
        deviceOne = createDevice(self.session, 'testdevice')
        IFDs = [InterfaceDefinition('et-0/0/0', deviceOne, 'uplink'), InterfaceDefinition('et-0/0/1', deviceOne, 'uplink'), 
                InterfaceDefinition('et-0/0/2', deviceOne, 'uplink'), InterfaceDefinition('et-0/0/3', deviceOne, 'uplink'), 
                InterfaceDefinition('et-0/0/10', deviceOne, 'uplink'), InterfaceDefinition('et-0/0/11', deviceOne, 'uplink'),
                InterfaceDefinition('et-0/0/12', deviceOne, 'uplink'), InterfaceDefinition('et-0/0/13', deviceOne, 'uplink'),
                InterfaceDefinition('et-0/1/0', deviceOne, 'uplink'), InterfaceDefinition('et-0/1/1', deviceOne, 'uplink'),
                InterfaceDefinition('et-0/1/2', deviceOne, 'uplink'), InterfaceDefinition('et-0/1/3', deviceOne, 'uplink')]
        self.session.add_all(IFDs)
        self.session.commit()
        
        fetchedIfds = self.session.query(InterfaceDefinition).order_by(InterfaceDefinition.sequenceNum).all()
        self.assertEqual('et-0/0/0', fetchedIfds[0].name)
        self.assertEqual('et-0/0/1', fetchedIfds[1].name)
        self.assertEqual('et-0/0/2', fetchedIfds[2].name)
        self.assertEqual('et-0/0/3', fetchedIfds[3].name)
        self.assertEqual('et-0/0/10', fetchedIfds[4].name)
        self.assertEqual('et-0/0/11', fetchedIfds[5].name)
        self.assertEqual('et-0/0/12', fetchedIfds[6].name)
        self.assertEqual('et-0/0/13', fetchedIfds[7].name)
        self.assertEqual('et-0/1/0', fetchedIfds[8].name)
        self.assertEqual('et-0/1/1', fetchedIfds[9].name)
        self.assertEqual('et-0/1/2', fetchedIfds[10].name)
        self.assertEqual('et-0/1/3', fetchedIfds[11].name)

        
class TestAdditionalLink(TestOrm):
    
    def testConstructorPass(self):
        self.assertTrue(AdditionalLink('device1', 'et-0/0/0', "device2", 'et-0/0/1'))
                        
    def testOrm(self):       
        IF = AdditionalLink('device1', 'et-0/0/0', "device2", 'et-0/0/1')
        self.session.add(IF)
        self.session.commit()
        
        self.assertEqual(1, self.session.query(AdditionalLink).count())
        fetched = self.session.query(AdditionalLink).one()
        self.assertEqual(IF, fetched)
        
        #delete object
        self.session.delete(IF)
        self.session.commit()
        self.assertEqual(0, self.session.query(AdditionalLink).count())
        
    def testRelationDeviceAdditionalLink(self):
        # create pod
        # create device
        #create AdditionalLink
        IFLone = AdditionalLink('device1', 'et-0/0/1', "device2", 'et-0/0/2')
        IFLtwo = AdditionalLink('device3', 'et-0/0/3', "device4", 'et-0/0/4')
        self.session.add(IFLone)
        self.session.add(IFLtwo)
        self.session.commit()
        
        self.assertEqual(2, self.session.query(AdditionalLink).count())
        # check relation navigation from additionalLink device
        additionalLinks = self.session.query(AdditionalLink).all()
        self.assertEqual("device1", additionalLinks[0].device1)
        self.assertEqual("device2", additionalLinks[0].device2)
        self.assertEqual("device3", additionalLinks[1].device1)
        self.assertEqual("device4", additionalLinks[1].device2)
        
           
    def testRelationAdditionalLinkPeer(self):
        # create pod
        # create device
        #create AdditionalLink
        IFLone = AdditionalLink('device1', 'et-0/0/1', "device2", 'et-0/0/2')
        IFLtwo = AdditionalLink('device3', 'et-0/0/3', "device4", 'et-0/0/4')
        self.session.add(IFLone)
        self.session.add(IFLtwo)
        self.session.commit()
        
        self.assertEqual(2, self.session.query(AdditionalLink).count())
        # check relation navigation from additionalLink device
        additionalLinks = self.session.query(AdditionalLink).all()
        self.assertEqual("et-0/0/1", additionalLinks[0].port1)
        self.assertEqual("et-0/0/2", additionalLinks[0].port2)
        self.assertEqual("et-0/0/3", additionalLinks[1].port1)
        self.assertEqual("et-0/0/4", additionalLinks[1].port2)
               
class TestTrapGroup(TestOrm):
    
    def testConstructorPass(self):
        self.assertTrue(TrapGroup('openClos', '1.2.3.4', 20162))
                        
    def testOrm(self):       
        group = TrapGroup('openClos', '1.2.3.4', 20162)
        self.session.add(group)
        self.session.commit()
        
        self.assertEqual(1, self.session.query(TrapGroup).count())
        fetched = self.session.query(TrapGroup).one()
        self.assertEqual(group, fetched)
        
        #delete object
        self.session.delete(group)
        self.session.commit()
        self.assertEqual(0, self.session.query(AdditionalLink).count())

if __name__ == '__main__':
    unittest.main()
