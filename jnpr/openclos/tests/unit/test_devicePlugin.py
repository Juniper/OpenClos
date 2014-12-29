'''
Created on Oct 30, 2014

@author: moloyc
'''
import unittest
#from flexmock import flexmock

import jnpr.openclos.util
from jnpr.openclos.devicePlugin import DeviceDataCollectorNetconf, L2DataCollector, DeviceOperationInProgressCache, TwoStageConfigurator 
from jnpr.openclos.exception import DeviceError
from jnpr.openclos.model import Device, InterfaceDefinition
from jnpr.openclos.dao import Dao
from jnpr.junos.exception import ConnectError

from flexmock import flexmock

class TestDeviceDataCollectorNetconf(unittest.TestCase):


    def setUp(self):
        self.conf = {'dbUrl': 'sqlite:///'}
        self.dao = Dao(self.conf)
        jnpr.openclos.util.loadLoggingConfigForTest()

    def tearDown(self):
        pass

    @unittest.skip("need physical device to test")
    def testConnectToDevice(self):
        flexmock(self.dao).should_receive('getObjectById').and_return(Device("test", "qfx5100-48s-6q", "root", "Embe1mpls", "leaf", "", "192.168.48.182", None))

        dataCollector = DeviceDataCollectorNetconf('1234', self.conf)
        dataCollector.dao = self.dao
        dataCollector.manualInit()
        
        dataCollector.connectToDevice()

    def testConnectToDeviceValueError(self):
        flexmock(self.dao).should_receive('getObjectById').and_return(Device("test", "qfx5100-48s-6q", None, "Embe1mpls", "leaf", "", "0.0.0.0", None))

        dataCollector = DeviceDataCollectorNetconf('1234', self.conf)
        dataCollector.dao = self.dao
        dataCollector.manualInit()

        with self.assertRaises(ValueError) as ve:
            dataCollector.connectToDevice()
        
        self.assertEquals(ValueError, type(ve.exception))

    def testConnectToDeviceConnectError(self):
        flexmock(self.dao).should_receive('getObjectById').and_return(Device("test", "qfx5100-48s-6q", "root", "Embe1mpls", "leaf", "", "0.0.0.0", None))

        dataCollector = DeviceDataCollectorNetconf('1234', self.conf)
        dataCollector.dao = self.dao
        dataCollector.manualInit()

        with self.assertRaises(DeviceError) as de:
            dataCollector.connectToDevice()
        
        self.assertIsNotNone(de.exception.cause)
        self.assertTrue(issubclass(type(de.exception.cause), ConnectError))



class TestL2DataCollector(unittest.TestCase):

    def setUp(self):
        self.conf = {'dbUrl': 'sqlite:///'}
        self.dao = Dao(self.conf)
        self.session = self.dao.Session()
        jnpr.openclos.util.loadLoggingConfigForTest()
        
    def tearDown(self):
        pass

    @unittest.skip("need physical device to test")
    def testCollectLldpFromDevice(self):
        flexmock(self.dao).should_receive('getObjectById').and_return(Device("test", "qfx5100-96s-8q", "root", "Embe1mpls", "leaf", "", "192.168.48.219", None))

        dataCollector = L2DataCollector('1234', self.conf)
        dataCollector.dao = self.dao
        dataCollector.manualInit()

        dataCollector.connectToDevice("Embe1mpls")
        dataCollector.collectLldpFromDevice()

    def testProcessLlDpData(self):
        from test_model import createDevice
        spine = createDevice(self.session, 'spine')
        leaf = createDevice(self.session, 'leaf')
        
        dataCollector = L2DataCollector(leaf.id, self.conf)
        dataCollector.dao = self.dao
        dataCollector.manualInit()

        IFDs = [InterfaceDefinition('et-0/0/0', spine, 'downlink'), InterfaceDefinition('et-0/0/1', spine, 'downlink'), 
                InterfaceDefinition('et-0/0/2', spine, 'downlink'), InterfaceDefinition('et-0/0/3', spine, 'downlink'), 
                InterfaceDefinition('et-0/0/48', leaf, 'uplink'), InterfaceDefinition('et-0/0/49', leaf, 'uplink'),
                InterfaceDefinition('et-0/0/50', leaf, 'uplink'), InterfaceDefinition('et-0/0/51', leaf, 'uplink'),
                InterfaceDefinition('xe-0/0/0', leaf, 'downlink'), InterfaceDefinition('xe-0/0/1', leaf, 'downlink')]
        self.session.add_all(IFDs)
        
        IFDs[0].peer = IFDs[4]
        IFDs[4].peer = IFDs[0]
        IFDs[1].peer = IFDs[5]
        IFDs[5].peer = IFDs[1]
        
        self.session.commit()

        dataCollector.processLlDpData([
           {'device1': '', 'port1': 'et-0/0/48', 'device2': 'spine', 'port2': 'et-0/0/0'},
           {'device1': '', 'port1': 'et-0/0/49', 'device2': 'spine', 'port2': 'et-0/0/1'},
           {'device1': '', 'port1': 'et-0/0/50', 'device2': 'spine-unknown', 'port2': 'et-0/0/0'}, # bad connection 
           {'device1': '', 'port1': 'xe-0/0/0', 'device2': 'server', 'port2': 'eth0'},
           {'device1': '', 'port1': 'xe-0/0/1', 'device2': 'server', 'port2': 'eth1'},
        ])
        
        self.assertEqual('good', self.session.query(InterfaceDefinition).filter(InterfaceDefinition.id == IFDs[0].id).one().lldpStatus)
        self.assertEqual('good', self.session.query(InterfaceDefinition).filter(InterfaceDefinition.id == IFDs[1].id).one().lldpStatus)
        self.assertEqual('unknown', self.session.query(InterfaceDefinition).filter(InterfaceDefinition.id == IFDs[2].id).one().lldpStatus)
        self.assertEqual('unknown', self.session.query(InterfaceDefinition).filter(InterfaceDefinition.id == IFDs[3].id).one().lldpStatus)

        self.assertEqual('good', self.session.query(InterfaceDefinition).filter(InterfaceDefinition.id == IFDs[4].id).one().lldpStatus)
        self.assertEqual('good', self.session.query(InterfaceDefinition).filter(InterfaceDefinition.id == IFDs[5].id).one().lldpStatus)
        self.assertEqual('error', self.session.query(InterfaceDefinition).filter(InterfaceDefinition.id == IFDs[6].id).one().lldpStatus)
        self.assertEqual('unknown', self.session.query(InterfaceDefinition).filter(InterfaceDefinition.id == IFDs[7].id).one().lldpStatus)

    def testUpdateDeviceL2StatusProcessing(self):
        from test_model import createDevice
        leaf = createDevice(self.session, 'leaf')
        dataCollector = L2DataCollector(leaf.id, self.conf)
        dataCollector.dao = self.dao
        dataCollector.manualInit()

        dataCollector.updateDeviceL2Status("processing")
        self.assertEqual(leaf.l2Status, "processing")
        self.assertIsNone(leaf.l2StatusReason)

    def testUpdateDeviceL2StatusWithException(self):
        from test_model import createDevice
        leaf = createDevice(self.session, 'leaf')
        dataCollector = L2DataCollector(leaf.id, self.conf)
        dataCollector.dao = self.dao
        dataCollector.manualInit()

        dataCollector.updateDeviceL2Status(None, error = DeviceError(ValueError("test error")))
        self.assertEqual("error", leaf.l2Status)
        self.assertEqual("test error", leaf.l2StatusReason)

    def testUpdateDeviceL2StatusWithErrorMessage(self):
        from test_model import createDevice
        leaf = createDevice(self.session, 'leaf')
        dataCollector = L2DataCollector(leaf.id, self.conf)
        dataCollector.dao = self.dao
        dataCollector.manualInit()

        dataCollector.updateDeviceL2Status("error", "test reason")
        self.assertEqual("error", leaf.l2Status)
        self.assertEqual("test reason", leaf.l2StatusReason)

class TestDataCollectorInProgressCache(unittest.TestCase):
    def setUp(self):
        jnpr.openclos.util.loadLoggingConfigForTest()

    def testSingleton(self):
        cache1 = DeviceOperationInProgressCache.getInstance()
        cache2 = DeviceOperationInProgressCache.getInstance()
        
        self.assertEqual(cache1, cache2)

    def testIsDeviceInProgress(self):
        cache = DeviceOperationInProgressCache.getInstance()
        self.assertTrue(cache.checkAndAddDevice("1234"))
        self.assertFalse(cache.checkAndAddDevice("1234"))
        self.assertTrue(cache.isDeviceInProgress("1234"))
        self.assertFalse(cache.isDeviceInProgress("5678"))
        self.assertIsNotNone(cache.doneDevice("1234"))
        self.assertTrue(cache.checkAndAddDevice("1234"))

class TestTwoStageConfigurator(unittest.TestCase):

    def setUp(self):
        self.conf = {'dbUrl': 'sqlite:///'}
        self.conf['deviceFamily'] = {"qfx5100-48s-6q": {"uplinkPorts": 'et-0/0/[48-53]', "downlinkPorts": 'xe-0/0/[0-47]'}}
        jnpr.openclos.util.loadLoggingConfigForTest()
        self.dao = Dao(self.conf)
        self.session = self.dao.Session()

        self.configurator = TwoStageConfigurator('192.168.48.219', self.conf)
        self.configurator.dao = self.dao
        self.configurator.manualInit()
    def tearDown(self):
        pass

    @unittest.skip("need physical device to test")
    def testCollectLldpAndMatchDevice(self):
        self.configurator.collectLldpAndMatchDevice()

    def createTwoSpineTwoLeaf(self):
        from test_model import createPod
        pod = createPod('pod1', self.session)
        from test_model import createPodDevice
        spine1 = createPodDevice(self.session, 'spine1', pod)
        spine2 = createPodDevice(self.session, 'spine2', pod)
        leaf1 = createPodDevice(self.session, 'leaf1', pod)
        leaf1.role = 'leaf'
        leaf1.family = 'qfx5100-48s-6q'
        leaf2 = createPodDevice(self.session, 'leaf2', pod)
        leaf2.role = 'leaf'
        leaf2.family = 'qfx5100-48s-6q'

        IFDs = [InterfaceDefinition('et-0/0/0', spine1, 'downlink'), InterfaceDefinition('et-0/0/1', spine1, 'downlink'), 
                InterfaceDefinition('et-0/0/0', spine2, 'downlink'), InterfaceDefinition('et-0/0/1', spine2, 'downlink'), 
                InterfaceDefinition('et-0/0/48', leaf1, 'uplink'), InterfaceDefinition('et-0/0/49', leaf1, 'uplink'),
                InterfaceDefinition('et-0/0/48', leaf2, 'uplink'), InterfaceDefinition('et-0/0/49', leaf2, 'uplink')]
        self.session.add_all(IFDs)
        
        IFDs[4].peer = IFDs[0]
        IFDs[0].peer = IFDs[4]
        IFDs[5].peer = IFDs[2]
        IFDs[2].peer = IFDs[5]
        
        IFDs[6].peer = IFDs[1]
        IFDs[1].peer = IFDs[6]
        IFDs[7].peer = IFDs[3]
        IFDs[3].peer = IFDs[7]
        
        return IFDs
        
    def getLldpDataFromLeaf1(self):
        return [
           {'device1': None, 'port1': 'et-0/0/48', 'device2': 'spine1', 'port2': 'et-0/0/0'},
           {'device1': None, 'port1': 'et-0/0/49', 'device2': 'spine2', 'port2': 'et-0/0/0'},
           {'device1': None, 'port1': 'xe-0/0/0', 'device2': 'server1', 'port2': 'eth0'},
           {'device1': None, 'port1': 'xe-0/0/1', 'device2': 'server2', 'port2': 'eth1'}
        ]

    def testFilterRemotePortIfdInDb(self):
        IFDs = self.createTwoSpineTwoLeaf()
        uplinksWithIfd = self.configurator.filterRemotePortIfdInDb(self.getLldpDataFromLeaf1(), 'qfx5100-48s-6q')
        
        self.assertEqual(2, len(uplinksWithIfd))
        self.assertIsNotNone(uplinksWithIfd[0]['ifd2'])
        self.assertEqual(IFDs[0], uplinksWithIfd[0]['ifd2'])
        self.assertIsNotNone(uplinksWithIfd[1]['ifd2'])
        self.assertEqual(IFDs[2], uplinksWithIfd[1]['ifd2'])

    def createTwoSpineTwoLeafPlugNPlay(self):
        from test_model import createPod
        pod = createPod('pod1', self.session)
        from test_model import createPodDevice
        spine1 = createPodDevice(self.session, 'spine1', pod)
        spine2 = createPodDevice(self.session, 'spine2', pod)
        leaf1 = createPodDevice(self.session, 'leaf1', pod)
        leaf1.role = 'leaf'
        leaf1.family = 'qfx5100-48s-6q'
        leaf2 = createPodDevice(self.session, 'leaf2', pod)
        leaf2.role = 'leaf'

        IFDs = [InterfaceDefinition('et-0/0/0', spine1, 'downlink'), InterfaceDefinition('et-0/0/1', spine1, 'downlink'), 
                InterfaceDefinition('et-0/0/0', spine2, 'downlink'), InterfaceDefinition('et-0/0/1', spine2, 'downlink'), 
                InterfaceDefinition('et-0/0/48', leaf1, 'uplink'), InterfaceDefinition('et-0/0/49', leaf1, 'uplink'),
                InterfaceDefinition('uplink-1', leaf2, 'uplink'), InterfaceDefinition('uplink-2', leaf2, 'uplink')]
        self.session.add_all(IFDs)
        
        IFDs[4].peer = IFDs[0]
        IFDs[0].peer = IFDs[4]
        IFDs[5].peer = IFDs[2]
        IFDs[2].peer = IFDs[5]
        
        IFDs[6].peer = IFDs[1]
        IFDs[1].peer = IFDs[6]
        IFDs[7].peer = IFDs[3]
        IFDs[3].peer = IFDs[7]
        
        return IFDs
        
    def testFfixUplinkPorts(self):
        IFDs = self.createTwoSpineTwoLeafPlugNPlay()
        lldpUplinksWithIfdFromLeaf2 = [
           {'device1': None, 'port1': 'et-0/0/48', 'device2': 'spine1', 'port2': 'et-0/0/1', 'ifd2':IFDs[1]},
           {'device1': None, 'port1': 'et-0/0/49', 'device2': 'spine2', 'port2': 'et-0/0/1', 'ifd2':IFDs[3]}
        ]
        self.assertEqual('uplink-1', self.session.query(InterfaceDefinition).filter(InterfaceDefinition.id == IFDs[6].id).one().name)
        self.assertEqual('uplink-2', self.session.query(InterfaceDefinition).filter(InterfaceDefinition.id == IFDs[7].id).one().name)

        self.configurator.fixUplinkPorts(lldpUplinksWithIfdFromLeaf2)

        self.assertEqual('et-0/0/48', self.session.query(InterfaceDefinition).filter(InterfaceDefinition.id == IFDs[6].id).one().name)
        self.assertEqual('et-0/0/49', self.session.query(InterfaceDefinition).filter(InterfaceDefinition.id == IFDs[7].id).one().name)

    @unittest.skip("")
    def testMatchDevice(self):
        self.configurator.findMatchedDevice(self.getLldpData(), 'qfx5100-96s-8q')


if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()