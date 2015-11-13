'''
Created on Oct 30, 2014

@author: moloyc
'''
import unittest

from jnpr.openclos.devicePlugin import DeviceDataCollectorNetconf, L2DataCollector, L3DataCollector, DeviceOperationInProgressCache, TwoStageConfigurator 
from jnpr.openclos.exception import DeviceConnectFailed, DeviceRpcFailed
from jnpr.openclos.model import Device, InterfaceDefinition, InterfaceLogical, BgpLink
from jnpr.openclos import loader
from test_dao import InMemoryDao 

from jnpr.junos.exception import ConnectError

from flexmock import flexmock

class TestDeviceDataCollectorNetconf(unittest.TestCase):
    def setUp(self):
        self._dao = InMemoryDao.getInstance()
        self.dataCollector = DeviceDataCollectorNetconf('1234', {}, InMemoryDao)

    def tearDown(self):
        InMemoryDao._destroy()
    
    @unittest.skip("need physical device to test")
    def testConnectToDevice(self):
        flexmock(self._dao).should_receive('getObjectById').and_return(Device("test", "qfx5100-48s-6q", "root", "Embe1mpls", "leaf", "", "192.168.48.182", None))

        dataCollector = DeviceDataCollectorNetconf('1234', {}, InMemoryDao)
        dataCollector._dao = self._dao
        dataCollector.manualInit()
        
        dataCollector.connectToDevice()
        
    def testConnectToDeviceValueError(self):
        flexmock(self._dao).should_receive('getObjectById').and_return(Device("test", "qfx5100-48s-6q", None, "Embe1mpls", "leaf", "", "0.0.0.0", None))
        self.dataCollector.manualInit()
        
        with self.assertRaises(DeviceConnectFailed) as ve:
            self.dataCollector.connectToDevice()

    def testConnectToDeviceConnectError(self):
        flexmock(self._dao).should_receive('getObjectById').and_return(Device("test", "qfx5100-48s-6q", "root", "Embe1mpls", "leaf", "", "0.0.0.0", None))
        self.dataCollector.manualInit()

        with self.assertRaises(DeviceConnectFailed) as de:
            self.dataCollector.connectToDevice()
        
        self.assertIsNotNone(de.exception.cause)
        self.assertTrue(issubclass(type(de.exception.cause), ConnectError))

class TestL2DataCollector(unittest.TestCase):

    def setUp(self):
        self.__conf = {'deviceFamily': {"qfx5100-48s-6q": {"uplinkPorts": 'et-0/0/[48-53]', "downlinkPorts": 'xe-0/0/[0-47]'}}}
        self._dao = InMemoryDao.getInstance()
        
    def tearDown(self):
        self._dao = None
        InMemoryDao._destroy()

    @unittest.skip("need physical device to test")
    def testCollectLldpFromDevice(self):
        flexmock(self._dao).should_receive('getObjectById').and_return(Device("test", "qfx5100-96s-8q", "root", "Embe1mpls", "leaf", "", "192.168.48.219", None))

        dataCollector = L2DataCollector('1234', self.__conf, InMemoryDao)
        dataCollector._dao = self._dao
        dataCollector.manualInit()

        dataCollector.connectToDevice()
        dataCollector.collectLldpFromDevice()

    def testUpdateDeviceL2StatusProcessing(self):
        from test_model import createDevice
        with self._dao.getReadSession() as session:
            leaf = createDevice(session, 'leaf')
            dataCollector = L2DataCollector(leaf.id, {}, InMemoryDao)
            dataCollector.manualInit()
            dataCollector._session = session

            dataCollector.updateDeviceL2Status("processing")
            self.assertEqual(leaf.l2Status, "processing")
            self.assertIsNone(leaf.l2StatusReason)

    def testUpdateDeviceL2StatusWithException(self):
        from test_model import createDevice
        with self._dao.getReadSession() as session:
            leaf = createDevice(session, 'leaf')
            dataCollector = L2DataCollector(leaf.id, {}, InMemoryDao)
            dataCollector.manualInit()
            dataCollector._session = session

            dataCollector.updateDeviceL2Status(None, error = DeviceRpcFailed("", cause=ValueError("test error")))
            self.assertEqual("error", leaf.l2Status)
            self.assertEqual("test error", leaf.l2StatusReason)

    def testUpdateDeviceL2StatusWithErrorMessage(self):
        from test_model import createDevice
        with self._dao.getReadSession() as session:
            leaf = createDevice(session, 'leaf')
            dataCollector = L2DataCollector(leaf.id, {}, InMemoryDao)
            dataCollector.manualInit()
            dataCollector._session = session

            dataCollector.updateDeviceL2Status("error", "test reason")
            self.assertEqual("error", leaf.l2Status)
            self.assertEqual("test reason", leaf.l2StatusReason)

    def createTwoSpineTwoLeaf(self, session):
        from test_model import createPod
        pod = createPod('pod1', session)
        from test_model import createPodDevice
        spine1 = createPodDevice(session, 'spine1', pod)
        spine2 = createPodDevice(session, 'spine2', pod)
        leaf1 = createPodDevice(session, 'leaf1', pod)
        leaf1.role = 'leaf'
        leaf1.family = 'qfx5100-48s-6q'
        leaf2 = createPodDevice(session, 'leaf2', pod)
        leaf2.role = 'leaf'
        leaf2.family = 'qfx5100-48s-6q'

        IFDs = [InterfaceDefinition('et-0/0/0', spine1, 'downlink'), InterfaceDefinition('et-0/0/1', spine1, 'downlink'), 
                InterfaceDefinition('et-0/0/0', spine2, 'downlink'), InterfaceDefinition('et-0/0/1', spine2, 'downlink'), 
                InterfaceDefinition('et-0/0/48', leaf1, 'uplink'), InterfaceDefinition('et-0/0/49', leaf1, 'uplink'),
                InterfaceDefinition('et-0/0/48', leaf2, 'uplink'), InterfaceDefinition('et-0/0/49', leaf2, 'uplink')]
        session.add_all(IFDs)
        
        IFDs[4].peer = IFDs[0]
        IFDs[0].peer = IFDs[4]
        IFDs[5].peer = IFDs[2]
        IFDs[2].peer = IFDs[5]
        
        IFDs[6].peer = IFDs[1]
        IFDs[1].peer = IFDs[6]
        IFDs[7].peer = IFDs[3]
        IFDs[3].peer = IFDs[7]
        
        return IFDs
        
    def testUpdateSpineStatusFromLldpData(self):
        with self._dao.getReadSession() as session:
            IFDs = self.createTwoSpineTwoLeaf(session)
            dataCollector = L2DataCollector(IFDs[4].device.id, {}, InMemoryDao)
            dataCollector.manualInit()
            dataCollector._session = session
            
            uplinkData = [IFDs[0], IFDs[2], IFDs[6]]
            dataCollector.updateSpineStatusFromLldpData(uplinkData)
            
            spine = IFDs[0].device
            self.assertEqual('deploy', spine.deployStatus)
            self.assertEqual('good', spine.configStatus)
            self.assertEqual('good', spine.l2Status)
            
            spine = IFDs[2].device
            self.assertEqual('deploy', spine.deployStatus)
            self.assertEqual('good', spine.configStatus)
            self.assertEqual('good', spine.l2Status)
    
            spine = IFDs[6].device
            self.assertEqual('provision', spine.deployStatus)
            self.assertEqual('unknown', spine.configStatus)
            self.assertEqual('unknown', spine.l2Status)

    def testFilterUplinkAppendRemotePortIfd(self):
        with self._dao.getReadSession() as session:
            IFDs = self.createTwoSpineTwoLeaf(session)
            dataCollector = L2DataCollector(IFDs[4].device.id, {}, InMemoryDao)
            dataCollector.manualInit()
            dataCollector._session = session
        
            lldpDataFromLeaf1 = {
               'et-0/0/48': {'device1': None, 'port1': 'et-0/0/48', 'device2': 'spine1', 'port2': 'et-0/0/0'},
               'et-0/0/49': {'device1': None, 'port1': 'et-0/0/49', 'device2': 'spine2', 'port2': 'et-0/0/0'},
               'xe-0/0/0': {'device1': None, 'port1': 'xe-0/0/0', 'device2': 'server1', 'port2': 'eth0'},
               'xe-0/0/1': {'device1': None, 'port1': 'xe-0/0/1', 'device2': 'server2', 'port2': 'eth1'},
               'mo': {}
            }
    
            uplinks = dataCollector.filterUplinkFromLldpData(lldpDataFromLeaf1, 'qfx5100-48s-6q')
            
            self.assertEqual(2, len(uplinks))
            self.assertIsNotNone(uplinks['et-0/0/48'])
            self.assertIsNotNone(uplinks['et-0/0/49'])

    def testGetAllocatedConnectedUplinkIfds(self):
        from test_model import createDevice
        with self._dao.getReadSession() as session:
            leaf = createDevice(session, 'leaf')
            dataCollector = L2DataCollector(leaf.id, {}, InMemoryDao)
            dataCollector.manualInit()
            dataCollector._session = session
            flexmock(session).should_receive('query.filter.filter.filter.order_by.all').\
            and_return([InterfaceDefinition("et-0/0/48", None, 'uplink'), InterfaceDefinition("et-0/0/49", None, 'uplink'), InterfaceDefinition("et-0/0/50", None, 'uplink')])

            ifds = dataCollector.getAllocatedConnectedUplinkIfds()
            self.assertIsNotNone(ifds['et-0/0/48'])
            self.assertTrue(isinstance(ifds['et-0/0/48'], InterfaceDefinition))
            self.assertIsNotNone(ifds['et-0/0/49'])
            self.assertIsNotNone(ifds['et-0/0/50'])

    def testUpdateBadIfdStatus(self):
        with self._dao.getReadSession() as session:
            IFDs = self.createTwoSpineTwoLeaf(session)
            dataCollector = L2DataCollector(IFDs[4].device.id, {}, InMemoryDao)
            dataCollector.manualInit()
            dataCollector._session = session
        
            dataCollector.updateBadIfdStatus([IFDs[4], IFDs[5]])
    
            self.assertEqual('error', session.query(InterfaceDefinition).filter(InterfaceDefinition.id == IFDs[4].id).one().status)
            self.assertEqual('error', session.query(InterfaceDefinition).filter(InterfaceDefinition.id == IFDs[5].id).one().status)
            self.assertEqual('unknown', session.query(InterfaceDefinition).filter(InterfaceDefinition.id == IFDs[6].id).one().status)

    def testUpdateGoodIfdStatus(self):
        with self._dao.getReadSession() as session:
            IFDs = self.createTwoSpineTwoLeaf(session)
            dataCollector = L2DataCollector(IFDs[4].device.id, {}, InMemoryDao)
            dataCollector.manualInit()
            dataCollector._session = session
            dataCollector.device = IFDs[4].device
        
            dataCollector.updateGoodIfdStatus([IFDs[4], IFDs[5]])
    
            self.assertEqual('good', session.query(InterfaceDefinition).filter(InterfaceDefinition.id == IFDs[4].id).one().status)
            self.assertEqual('good', session.query(InterfaceDefinition).filter(InterfaceDefinition.id == IFDs[5].id).one().status)
            self.assertEqual('good', session.query(InterfaceDefinition).filter(InterfaceDefinition.id == IFDs[0].id).one().status)
            self.assertEqual('good', session.query(InterfaceDefinition).filter(InterfaceDefinition.id == IFDs[2].id).one().status)
            self.assertEqual('unknown', session.query(InterfaceDefinition).filter(InterfaceDefinition.id == IFDs[6].id).one().status)
            
            spine = IFDs[0].device
            self.assertEqual('deploy', spine.deployStatus)
            self.assertEqual('good', spine.configStatus)
            self.assertEqual('good', spine.l2Status)

    def createTwoSpineTwoLeafWithDummyUplinksForEx4300(self, session):
        from test_model import createPod
        pod = createPod('pod1', session)
        from test_model import createPodDevice
        spine1 = createPodDevice(session, 'spine1', pod)
        spine2 = createPodDevice(session, 'spine2', pod)
        spine3 = createPodDevice(session, 'spine3', pod)
        leaf1 = createPodDevice(session, 'leaf1', pod)
        leaf1.role = 'leaf'
        leaf1.family = 'qfx5100-48s-6q'
        leaf2 = createPodDevice(session, 'leaf2', pod)
        leaf2.role = 'leaf'
        leaf2.family = 'qfx5100-48s-6q'

        IFDs = [
            InterfaceDefinition('et-0/0/0', spine1, 'downlink'), InterfaceDefinition('et-0/0/1', spine1, 'downlink'), 
            InterfaceDefinition('et-0/0/0', spine2, 'downlink'), InterfaceDefinition('et-0/0/1', spine2, 'downlink'),
            InterfaceDefinition('et-0/0/0', spine3, 'downlink'), InterfaceDefinition('et-0/0/1', spine3, 'downlink'),
            InterfaceDefinition('et-0/0/48', leaf1, 'uplink'), InterfaceDefinition('et-0/0/49', leaf1, 'uplink'), InterfaceDefinition('et-0/0/50', leaf2, 'uplink'),
            InterfaceDefinition('et-0/0/48', leaf2, 'uplink'), InterfaceDefinition('et-0/0/49', leaf2, 'uplink'), InterfaceDefinition('dummy', leaf2, 'uplink')]

        session.add_all(IFDs)
        
        IFDs[6].peer = IFDs[0]
        IFDs[0].peer = IFDs[6]
        IFDs[7].peer = IFDs[2]
        IFDs[2].peer = IFDs[7]
        IFDs[8].peer = IFDs[4]
        IFDs[4].peer = IFDs[8]
        
        IFDs[9].peer = IFDs[1]
        IFDs[1].peer = IFDs[9]
        IFDs[10].peer = IFDs[3]
        IFDs[3].peer = IFDs[10]
        IFDs[11].peer = IFDs[5]
        IFDs[5].peer = IFDs[11]
        
        return IFDs

    def testProcessLlDpData(self):
        with self._dao.getReadSession() as session:
            IFDs = self.createTwoSpineTwoLeafWithDummyUplinksForEx4300(session)
            dataCollector = L2DataCollector(IFDs[11].device.id, {}, InMemoryDao)
            dataCollector.manualInit()
            dataCollector._session = session
            dataCollector.device = IFDs[11].device
            
            lldpDataFromLeaf2 = {
               'et-0/0/48': {'device1': None, 'port1': 'et-0/0/48', 'device2': 'spine1', 'port2': 'et-0/0/1'}, # perfect match
               'et-0/0/49': {'device1': None, 'port1': 'et-0/0/49', 'device2': 'spine2', 'port2': 'et-0/0/99'}, # bad connect
               'et-0/0/51': {'device1': None, 'port1': 'et-0/0/51', 'device2': 'spine9', 'port2': 'et-0/0/99'}, # additional
            }
            
            flexmock(dataCollector).should_receive('persistAdditionalLinks').with_args([lldpDataFromLeaf2['et-0/0/51']]).times(1)
            flexmock(dataCollector).should_receive('updateGoodIfdStatus').with_args([IFDs[9]]).times(1)
            flexmock(dataCollector).should_receive('updateBadIfdStatus').with_args([IFDs[11], IFDs[10]]).times(1)
            #flexmock(dataCollector).should_receive('resetSpineStatus').with_args(IFDs[11].device.pod).times(1)
    
            counts = dataCollector.processLlDpData(lldpDataFromLeaf2, {'et-0/0/48': IFDs[9], 'et-0/0/49': IFDs[10], 'dummy': IFDs[11]})
            
            self.assertEqual(1, counts['goodUplinkCount'])
            self.assertEqual(2, counts['badUplinkCount'])
            self.assertEqual(1, counts['additionalLinkCount'])

class TestDataCollectorInProgressCache(unittest.TestCase):
    def setUp(self):
        loader.loadLoggingConfig(appName = 'unittest')

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

class TestTwoStageConfigurator(TestL2DataCollector):

    def setUp(self):
        self.__conf = {'deviceFamily': {"qfx5100-48s-6q": {"uplinkPorts": 'et-0/0/[48-53]', "downlinkPorts": 'xe-0/0/[0-47]'},
                                     "ex4300-24p": {"uplinkPorts": 'et-0/1/[0-3]', "downlinkPorts": 'ge-0/0/[0-23]'}}}
        self._dao = InMemoryDao.getInstance()
        self.configurator = TwoStageConfigurator('192.168.48.219', self.__conf, InMemoryDao)
        self.configurator.manualInit()

    def tearDown(self):
        self._dao = None
        self.configurator = None
        InMemoryDao._destroy()

    @unittest.skip("need physical device to test")
    def testCollectLldpAndMatchDevice(self):
        self.configurator.collectLldpAndMatchDevice()

    def testFilterUplinkAppendRemotePortIfd(self):
        with self._dao.getReadSession() as session:
            IFDs = self.createTwoSpineTwoLeaf(session)
            self.configurator._session = session

            lldpDataFromLeaf1 = {
               'et-0/0/48': {'device1': None, 'port1': 'et-0/0/48', 'device2': 'spine1', 'port2': 'et-0/0/0'},
               'et-0/0/49': {'device1': None, 'port1': 'et-0/0/49', 'device2': 'spine2', 'port2': 'et-0/0/0'},
               'xe-0/0/0': {'device1': None, 'port1': 'xe-0/0/0', 'device2': 'server1', 'port2': 'eth0'},
               'xe-0/0/1': {'device1': None, 'port1': 'xe-0/0/1', 'device2': 'server2', 'port2': 'eth1'}
            }
    
            uplinksWithIfd = self.configurator.filterUplinkAppendRemotePortIfd(lldpDataFromLeaf1, 'qfx5100-48s-6q')
            
            self.assertEqual(2, len(uplinksWithIfd))
            self.assertIsNotNone(uplinksWithIfd[0]['ifd2'])
            self.assertIsNotNone(uplinksWithIfd[1]['ifd2'])

    def createIfls(self, session, ifds):
        IFLs = []
        for ifd in ifds:
            ifl = InterfaceLogical(ifd.name + '.0', ifd.device)
            ifd.layerAboves.append(ifl) 
            IFLs.append(ifl)
        session.add_all(IFLs)
        return IFLs
    
    def createSixSpineOneLeafUnknownPlugNPlay(self, session):
        from test_model import createPod
        pod = createPod('pod1', session)
        from test_model import createPodDevice
        spine1 = createPodDevice(session, 'spine1', pod)
        spine2 = createPodDevice(session, 'spine2', pod)
        spine3 = createPodDevice(session, 'spine3', pod)
        spine4 = createPodDevice(session, 'spine4', pod)
        spine5 = createPodDevice(session, 'spine5', pod)
        spine6 = createPodDevice(session, 'spine6', pod)
        leaf1 = createPodDevice(session, 'leaf1', pod)
        leaf1.role = 'leaf'
        leaf1.family = 'unknown'

        IFDs = [InterfaceDefinition('et-0/0/0', spine1, 'downlink'), InterfaceDefinition('et-0/0/0', spine2, 'downlink'), 
                InterfaceDefinition('et-0/0/0', spine3, 'downlink'), InterfaceDefinition('et-0/0/0', spine4, 'downlink'), 
                InterfaceDefinition('et-0/0/0', spine5, 'downlink'), InterfaceDefinition('et-0/0/0', spine6, 'downlink'), 
                InterfaceDefinition('uplink-0', leaf1, 'uplink'), InterfaceDefinition('uplink-1', leaf1, 'uplink'),
                InterfaceDefinition('uplink-2', leaf1, 'uplink'), InterfaceDefinition('uplink-3', leaf1, 'uplink'),
                InterfaceDefinition('uplink-4', leaf1, 'uplink'), InterfaceDefinition('uplink-5', leaf1, 'uplink')]
        session.add_all(IFDs)

        IFLs = self.createIfls(session, IFDs)
        
        IFDs[6].peer = IFDs[0]
        IFDs[0].peer = IFDs[6]
        IFDs[7].peer = IFDs[1]
        IFDs[1].peer = IFDs[7]
        IFDs[8].peer = IFDs[2]
        IFDs[2].peer = IFDs[8]
        IFDs[9].peer = IFDs[3]
        IFDs[3].peer = IFDs[9]
        IFDs[10].peer = IFDs[4]
        IFDs[4].peer = IFDs[10]
        IFDs[11].peer = IFDs[5]
        IFDs[5].peer = IFDs[11]
        
        return {'ifds': IFDs, 'ifls': IFLs}

    def testFixUplinkPortsUnknownToEx4300SpineCount2(self):
        with self._dao.getReadSession() as session:
            ifdIfl = self.createSixSpineOneLeafUnknownPlugNPlay(session)
            IFDs = ifdIfl['ifds']
            IFLs = ifdIfl['ifls']
            self.configurator._session = session
            lldpUplinksWithIfdFromLeaf2 = [
               {'device1': None, 'port1': 'et-0/1/0', 'device2': 'spine1', 'port2': 'et-0/0/0', 'ifd2':IFDs[0]},
               {'device1': None, 'port1': 'et-0/1/1', 'device2': 'spine2', 'port2': 'et-0/0/0', 'ifd2':IFDs[1]}
            ]
            self.assertEqual('uplink-0', session.query(InterfaceDefinition).filter(InterfaceDefinition.id == IFDs[6].id).one().name)
            self.assertEqual('uplink-1', session.query(InterfaceDefinition).filter(InterfaceDefinition.id == IFDs[7].id).one().name)
            self.assertEqual('uplink-0.0', session.query(InterfaceLogical).filter(InterfaceLogical.id == IFLs[6].id).one().name)
            self.assertEqual('uplink-1.0', session.query(InterfaceLogical).filter(InterfaceLogical.id == IFLs[7].id).one().name)
    
            IFDs[6].device.family = 'ex4300-24p'
            self.configurator.fixUplinkPorts(IFDs[6].device, lldpUplinksWithIfdFromLeaf2)
    
            IFDs = session.query(InterfaceDefinition).filter(InterfaceDefinition.device_id == IFDs[6].device.id).filter(InterfaceDefinition.role == 'uplink').all()
            self.assertEqual('et-0/1/0', IFDs[0].name)
            self.assertEqual('et-0/1/1', IFDs[1].name)
            self.assertEqual('et-0/1/0.0', IFDs[0].layerAboves[0].name)
            self.assertEqual('et-0/1/1.0', IFDs[1].layerAboves[0].name)
    
            self.assertEqual('et-0/1/2', IFDs[2].name)
            self.assertEqual('et-0/1/3', IFDs[3].name)
            self.assertEqual('uplink-4', IFDs[4].name)
            self.assertEqual('uplink-5', IFDs[5].name)

    def testFixUplinkPortsUnknownToEx4300SpineCount2RandomPorts(self):
        with self._dao.getReadSession() as session:
            ifdIfl = self.createSixSpineOneLeafUnknownPlugNPlay(session)
            IFDs = ifdIfl['ifds']
            IFLs = ifdIfl['ifls']
            self.configurator._session = session
            lldpUplinksWithIfdFromLeaf2 = [
               {'device1': None, 'port1': 'et-0/1/1', 'device2': 'spine1', 'port2': 'et-0/0/0', 'ifd2':IFDs[0]},
               {'device1': None, 'port1': 'et-0/1/3', 'device2': 'spine2', 'port2': 'et-0/0/0', 'ifd2':IFDs[1]}
            ]
            self.assertEqual('uplink-1', session.query(InterfaceDefinition).filter(InterfaceDefinition.id == IFDs[7].id).one().name)
            self.assertEqual('uplink-3', session.query(InterfaceDefinition).filter(InterfaceDefinition.id == IFDs[9].id).one().name)
            self.assertEqual('uplink-1.0', session.query(InterfaceLogical).filter(InterfaceLogical.id == IFLs[7].id).one().name)
            self.assertEqual('uplink-3.0', session.query(InterfaceLogical).filter(InterfaceLogical.id == IFLs[9].id).one().name)
    
            IFDs[6].device.family = 'ex4300-24p'
            self.configurator.fixUplinkPorts(IFDs[6].device, lldpUplinksWithIfdFromLeaf2)
    
            IFDs = session.query(InterfaceDefinition).filter(InterfaceDefinition.device_id == IFDs[6].device.id).filter(InterfaceDefinition.role == 'uplink').all()
            self.assertEqual('et-0/1/1', IFDs[1].name)
            self.assertEqual('et-0/1/3', IFDs[3].name)
            self.assertEqual('et-0/1/1.0', IFDs[1].layerAboves[0].name)
            self.assertEqual('et-0/1/3.0', IFDs[3].layerAboves[0].name)
    
            self.assertEqual('et-0/1/0', IFDs[0].name)
            self.assertEqual('et-0/1/2', IFDs[2].name)
            self.assertEqual('uplink-4', IFDs[4].name)
            self.assertEqual('uplink-5', IFDs[5].name)

    def testFixUplinkPortsUnknownToEx4300SpineCount4RandomPorts(self):
        with self._dao.getReadSession() as session:
            ifdIfl = self.createSixSpineOneLeafUnknownPlugNPlay(session)
            IFDs = ifdIfl['ifds']
            self.configurator._session = session

            lldpUplinksWithIfdFromLeaf2 = [
               {'device1': None, 'port1': 'et-0/1/0', 'device2': 'spine1', 'port2': 'et-0/0/3', 'ifd2':IFDs[3]},
               {'device1': None, 'port1': 'et-0/1/1', 'device2': 'spine2', 'port2': 'et-0/0/2', 'ifd2':IFDs[2]},
               {'device1': None, 'port1': 'et-0/1/2', 'device2': 'spine1', 'port2': 'et-0/0/1', 'ifd2':IFDs[1]},
               {'device1': None, 'port1': 'et-0/1/3', 'device2': 'spine2', 'port2': 'et-0/0/0', 'ifd2':IFDs[0]}
            ]
            self.assertEqual('uplink-1', session.query(InterfaceDefinition).filter(InterfaceDefinition.id == IFDs[7].id).one().name)
            self.assertEqual('uplink-2', session.query(InterfaceDefinition).filter(InterfaceDefinition.id == IFDs[8].id).one().name)
            self.assertEqual('uplink-3', session.query(InterfaceDefinition).filter(InterfaceDefinition.id == IFDs[9].id).one().name)
            self.assertEqual('uplink-4', session.query(InterfaceDefinition).filter(InterfaceDefinition.id == IFDs[10].id).one().name)
    
            IFDs[6].device.family = 'ex4300-24p'
            self.configurator.fixUplinkPorts(IFDs[6].device, lldpUplinksWithIfdFromLeaf2)
    
            IFDs = session.query(InterfaceDefinition).filter(InterfaceDefinition.device_id == IFDs[6].device.id).filter(InterfaceDefinition.role == 'uplink').all()
            self.assertEqual('et-0/1/0', IFDs[0].name)
            self.assertEqual('et-0/1/1', IFDs[1].name)
            self.assertEqual('et-0/1/2', IFDs[2].name)
            self.assertEqual('et-0/1/3', IFDs[3].name)
            self.assertEqual('uplink-4', IFDs[4].name)
            self.assertEqual('uplink-5', IFDs[5].name)
        
    def createSixSpineOneLeafEx4300_24pPlugNPlay(self, session):
        from test_model import createPod
        pod = createPod('pod1', session)
        from test_model import createPodDevice
        spine1 = createPodDevice(session, 'spine1', pod)
        spine2 = createPodDevice(session, 'spine2', pod)
        spine3 = createPodDevice(session, 'spine3', pod)
        spine4 = createPodDevice(session, 'spine4', pod)
        spine5 = createPodDevice(session, 'spine5', pod)
        spine6 = createPodDevice(session, 'spine6', pod)
        leaf1 = createPodDevice(session, 'leaf1', pod)
        leaf1.role = 'leaf'
        leaf1.family = 'ex4300-24p'

        IFDs = [InterfaceDefinition('et-0/0/0', spine1, 'downlink'), InterfaceDefinition('et-0/0/0', spine2, 'downlink'), 
                InterfaceDefinition('et-0/0/0', spine3, 'downlink'), InterfaceDefinition('et-0/0/0', spine4, 'downlink'), 
                InterfaceDefinition('et-0/0/0', spine5, 'downlink'), InterfaceDefinition('et-0/0/0', spine6, 'downlink'), 
                InterfaceDefinition('et-0/1/0', leaf1, 'uplink'), InterfaceDefinition('et-0/1/1', leaf1, 'uplink'),
                InterfaceDefinition('et-0/1/2', leaf1, 'uplink'), InterfaceDefinition('et-0/1/3', leaf1, 'uplink'),
                InterfaceDefinition('uplink-4', leaf1, 'uplink'), InterfaceDefinition('uplink-5', leaf1, 'uplink')]
        session.add_all(IFDs)

        IFLs = self.createIfls(session, IFDs)
        
        IFDs[6].peer = IFDs[0]
        IFDs[0].peer = IFDs[6]
        IFDs[7].peer = IFDs[1]
        IFDs[1].peer = IFDs[7]
        IFDs[8].peer = IFDs[2]
        IFDs[2].peer = IFDs[8]
        IFDs[9].peer = IFDs[3]
        IFDs[3].peer = IFDs[9]
        IFDs[10].peer = IFDs[4]
        IFDs[4].peer = IFDs[10]
        IFDs[11].peer = IFDs[5]
        IFDs[5].peer = IFDs[11]
        
        return {'ifds': IFDs, 'ifls': IFLs}

    def testFixUplinkPortsEx4300ToQfx5100_48sSpineCount2RandomPorts(self):
        with self._dao.getReadSession() as session:
            ifdIfl = self.createSixSpineOneLeafEx4300_24pPlugNPlay(session)
            IFDs = ifdIfl['ifds']
            IFLs = ifdIfl['ifls']
            self.configurator._session = session

            lldpUplinksWithIfdFromLeaf2 = [
               {'device1': None, 'port1': 'et-0/0/49', 'device2': 'spine1', 'port2': 'et-0/0/0', 'ifd2':IFDs[0]},
               {'device1': None, 'port1': 'et-0/0/52', 'device2': 'spine2', 'port2': 'et-0/0/0', 'ifd2':IFDs[1]}
            ]
            self.assertEqual('et-0/1/1', session.query(InterfaceDefinition).filter(InterfaceDefinition.id == IFDs[7].id).one().name)
            self.assertEqual('uplink-4', session.query(InterfaceDefinition).filter(InterfaceDefinition.id == IFDs[10].id).one().name)
            self.assertEqual('et-0/1/1.0', session.query(InterfaceLogical).filter(InterfaceLogical.id == IFLs[7].id).one().name)
            self.assertEqual('uplink-4.0', session.query(InterfaceLogical).filter(InterfaceLogical.id == IFLs[10].id).one().name)
    
            IFDs[6].device.family = 'qfx5100-48s-6q'
            self.configurator.fixUplinkPorts(IFDs[6].device, lldpUplinksWithIfdFromLeaf2)
    
            IFDs = session.query(InterfaceDefinition).filter(InterfaceDefinition.device_id == IFDs[6].device.id).filter(InterfaceDefinition.role == 'uplink').all()
            self.assertEqual('et-0/0/49', IFDs[1].name)
            self.assertEqual('et-0/0/52', IFDs[4].name)
            self.assertEqual('et-0/0/49.0', IFDs[1].layerAboves[0].name)
            self.assertEqual('et-0/0/52.0', IFDs[4].layerAboves[0].name)
    
            self.assertEqual('et-0/0/48', IFDs[0].name)
            self.assertEqual('et-0/0/50', IFDs[2].name)
            self.assertEqual('et-0/0/51', IFDs[3].name)
            self.assertEqual('et-0/0/53', IFDs[5].name)

    def createSixSpineOneLeafqfx5100_48sPlugNPlay(self, session):
        from test_model import createPod
        pod = createPod('pod1', session)
        from test_model import createPodDevice
        spine1 = createPodDevice(session, 'spine1', pod)
        spine2 = createPodDevice(session, 'spine2', pod)
        spine3 = createPodDevice(session, 'spine3', pod)
        spine4 = createPodDevice(session, 'spine4', pod)
        spine5 = createPodDevice(session, 'spine5', pod)
        spine6 = createPodDevice(session, 'spine6', pod)
        leaf1 = createPodDevice(session, 'leaf1', pod)
        leaf1.role = 'leaf'
        leaf1.family = 'qfx5100-48s-6q'

        IFDs = [InterfaceDefinition('et-0/0/0', spine1, 'downlink'), InterfaceDefinition('et-0/0/0', spine2, 'downlink'), 
                InterfaceDefinition('et-0/0/0', spine3, 'downlink'), InterfaceDefinition('et-0/0/0', spine4, 'downlink'), 
                InterfaceDefinition('et-0/0/0', spine5, 'downlink'), InterfaceDefinition('et-0/0/0', spine6, 'downlink'), 
                InterfaceDefinition('et-0/0/48', leaf1, 'uplink'), InterfaceDefinition('et-0/0/49', leaf1, 'uplink'),
                InterfaceDefinition('et-0/0/50', leaf1, 'uplink'), InterfaceDefinition('et-0/0/51', leaf1, 'uplink'),
                InterfaceDefinition('et-0/0/52', leaf1, 'uplink'), InterfaceDefinition('et-0/0/53', leaf1, 'uplink')]
        session.add_all(IFDs)

        IFLs = self.createIfls(session, IFDs)
        
        IFDs[6].peer = IFDs[0]
        IFDs[0].peer = IFDs[6]
        IFDs[7].peer = IFDs[1]
        IFDs[1].peer = IFDs[7]
        IFDs[8].peer = IFDs[2]
        IFDs[2].peer = IFDs[8]
        IFDs[9].peer = IFDs[3]
        IFDs[3].peer = IFDs[9]
        IFDs[10].peer = IFDs[4]
        IFDs[4].peer = IFDs[10]
        IFDs[11].peer = IFDs[5]
        IFDs[5].peer = IFDs[11]
        
        return {'ifds': IFDs, 'ifls': IFLs}

    def testFixUplinkPortsQfx5100_48sToEx4300SpineCount2RandomPorts(self):
        with self._dao.getReadSession() as session:
            ifdIfl = self.createSixSpineOneLeafqfx5100_48sPlugNPlay(session)
            IFDs = ifdIfl['ifds']
            IFLs = ifdIfl['ifls']
            self.configurator._session = session

            lldpUplinksWithIfdFromLeaf2 = [
               {'device1': None, 'port1': 'et-0/1/3', 'device2': 'spine1', 'port2': 'et-0/0/0', 'ifd2':IFDs[0]},
               {'device1': None, 'port1': 'et-0/1/2', 'device2': 'spine2', 'port2': 'et-0/0/0', 'ifd2':IFDs[1]}
            ]
            self.assertEqual('et-0/0/51', session.query(InterfaceDefinition).filter(InterfaceDefinition.id == IFDs[9].id).one().name)
            self.assertEqual('et-0/0/50', session.query(InterfaceDefinition).filter(InterfaceDefinition.id == IFDs[8].id).one().name)
            self.assertEqual('et-0/0/51.0', session.query(InterfaceLogical).filter(InterfaceLogical.id == IFLs[9].id).one().name)
            self.assertEqual('et-0/0/50.0', session.query(InterfaceLogical).filter(InterfaceLogical.id == IFLs[8].id).one().name)
    
            IFDs[6].device.family = 'ex4300-24p'
            self.configurator.fixUplinkPorts(IFDs[6].device, lldpUplinksWithIfdFromLeaf2)
    
            IFDs = session.query(InterfaceDefinition).filter(InterfaceDefinition.device_id == IFDs[6].device.id).filter(InterfaceDefinition.role == 'uplink').all()
            self.assertEqual('et-0/1/3', IFDs[3].name)
            self.assertEqual('et-0/1/2', IFDs[2].name)
            self.assertEqual('et-0/1/3.0', IFDs[3].layerAboves[0].name)
            self.assertEqual('et-0/1/2.0', IFDs[2].layerAboves[0].name)
    
            self.assertEqual('et-0/1/0', IFDs[0].name)
            self.assertEqual('et-0/1/1', IFDs[1].name)
            self.assertEqual('uplink-4', IFDs[4].name)
            self.assertEqual('uplink-5', IFDs[5].name)

    def createTwoSpineTwoLeafPlugNPlay(self, session):
        from test_model import createPod
        pod = createPod('pod1', session)
        from test_model import createPodDevice
        spine1 = createPodDevice(session, 'spine1', pod)
        spine2 = createPodDevice(session, 'spine2', pod)
        leaf1 = createPodDevice(session, 'leaf1', pod)
        leaf1.role = 'leaf'
        leaf1.family = 'qfx5100-48s-6q'
        leaf2 = createPodDevice(session, 'leaf2', pod)
        leaf2.role = 'leaf'
        leaf2.family = 'unknown'

        IFDs = [InterfaceDefinition('et-0/0/0', spine1, 'downlink'), InterfaceDefinition('et-0/0/1', spine1, 'downlink'), 
                InterfaceDefinition('et-0/0/0', spine2, 'downlink'), InterfaceDefinition('et-0/0/1', spine2, 'downlink'), 
                InterfaceDefinition('et-0/0/48', leaf1, 'uplink'), InterfaceDefinition('et-0/0/49', leaf1, 'uplink'),
                InterfaceDefinition('uplink-1', leaf2, 'uplink'), InterfaceDefinition('uplink-2', leaf2, 'uplink')]
        session.add_all(IFDs)

        IFLs = self.createIfls(session, IFDs)
        
        IFDs[4].peer = IFDs[0]
        IFDs[0].peer = IFDs[4]
        IFDs[5].peer = IFDs[2]
        IFDs[2].peer = IFDs[5]
        
        IFDs[6].peer = IFDs[1]
        IFDs[1].peer = IFDs[6]
        IFDs[7].peer = IFDs[3]
        IFDs[3].peer = IFDs[7]
        
        return {'ifds': IFDs, 'ifls': IFLs}
        
    def testFixUplinkPortsUnknownToQfx5100_48s(self):
        with self._dao.getReadSession() as session:
            ifdIfl = self.createTwoSpineTwoLeafPlugNPlay(session)
            IFDs = ifdIfl['ifds']
            IFLs = ifdIfl['ifls']
            self.configurator._session = session

            lldpUplinksWithIfdFromLeaf2 = [
               {'device1': None, 'port1': 'et-0/0/48', 'device2': 'spine1', 'port2': 'et-0/0/1', 'ifd2':IFDs[1]},
               {'device1': None, 'port1': 'et-0/0/49', 'device2': 'spine2', 'port2': 'et-0/0/1', 'ifd2':IFDs[3]}
            ]
            self.assertEqual('uplink-1', session.query(InterfaceDefinition).filter(InterfaceDefinition.id == IFDs[6].id).one().name)
            self.assertEqual('uplink-2', session.query(InterfaceDefinition).filter(InterfaceDefinition.id == IFDs[7].id).one().name)
            self.assertEqual('uplink-1.0', session.query(InterfaceLogical).filter(InterfaceLogical.id == IFLs[6].id).one().name)
            self.assertEqual('uplink-2.0', session.query(InterfaceLogical).filter(InterfaceLogical.id == IFLs[7].id).one().name)
    
            IFDs[6].device.family = 'qfx5100-48s-6q'
            self.configurator.fixUplinkPorts(IFDs[6].device, lldpUplinksWithIfdFromLeaf2)
    
            self.assertEqual('et-0/0/48', session.query(InterfaceDefinition).filter(InterfaceDefinition.id == IFDs[6].id).one().name)
            self.assertEqual('et-0/0/49', session.query(InterfaceDefinition).filter(InterfaceDefinition.id == IFDs[7].id).one().name)
            self.assertEqual('et-0/0/48.0', session.query(InterfaceLogical).filter(InterfaceLogical.id == IFLs[6].id).one().name)
            self.assertEqual('et-0/0/49.0', session.query(InterfaceLogical).filter(InterfaceLogical.id == IFLs[7].id).one().name)

    @unittest.skip("")
    def testMatchDevice(self):
        self.configurator.findMatchedDevice(self.getLldpData(), 'qfx5100-96s-8q')

class TestL3DataCollector(unittest.TestCase):

    def setUp(self):
        self.__conf = {'deviceFamily': {"qfx5100-48s-6q": {"uplinkPorts": 'et-0/0/[48-53]', "downlinkPorts": 'xe-0/0/[0-47]'}}}
        self._dao = InMemoryDao.getInstance()
        
    def tearDown(self):
        self._dao = None
        InMemoryDao._destroy()

    @unittest.skip("need physical device to test")
    def testCollectBgpFromDevice(self):
        flexmock(self._dao).should_receive('getObjectById').and_return(Device("test", "qfx5100-96s-8q", "root", "Embe1mpls", "leaf", "", "192.168.48.219", None))

        dataCollector = L3DataCollector('1234', self.__conf, InMemoryDao)
        dataCollector._dao = self._dao
        dataCollector.manualInit()

        dataCollector.connectToDevice()
        dataCollector.collectBgpFromDevice()

    def testUpdateDeviceL3StatusProcessing(self):
        from test_model import createDevice
        with self._dao.getReadSession() as session:
            leaf = createDevice(session, 'leaf')
            dataCollector = L3DataCollector(leaf.id, {}, InMemoryDao)
            dataCollector.manualInit()
            dataCollector._session = session

            dataCollector.updateDeviceL3Status("processing")
            self.assertEqual(leaf.l3Status, "processing")
            self.assertIsNone(leaf.l3StatusReason)

    def testUpdateDeviceL2StatusWithException(self):
        from test_model import createDevice
        with self._dao.getReadSession() as session:
            leaf = createDevice(session, 'leaf')
            dataCollector = L3DataCollector(leaf.id, {}, InMemoryDao)
            dataCollector.manualInit()
            dataCollector._session = session

            dataCollector.updateDeviceL3Status(None, error = DeviceRpcFailed("", cause=ValueError("test error")))
            self.assertEqual("error", leaf.l3Status)
            self.assertEqual("test error", leaf.l3StatusReason)

    def testUpdateDeviceL3StatusWithErrorMessage(self):
        from test_model import createDevice
        with self._dao.getReadSession() as session:
            leaf = createDevice(session, 'leaf')
            dataCollector = L3DataCollector(leaf.id, {}, InMemoryDao)
            dataCollector.manualInit()
            dataCollector._session = session

            dataCollector.updateDeviceL3Status("error", "test reason")
            self.assertEqual("error", leaf.l3Status)
            self.assertEqual("test reason", leaf.l3StatusReason)

    def testStoreBgpLinks(self):
        device_id = None
        with self._dao.getReadWriteSession() as session:
            from test_model import createPod
            pod = createPod('pod1', session)
            session.add(pod)
            device = Device("leaf1", "qfx5100-48s-6q", "", "", "leaf", "11:12:13:14:15:16", "1.2.3.4/24", pod)
            device_id = device.id
            session.add(device)
            
        with self._dao.getReadSession() as session:
            dataCollector = L3DataCollector(device_id, {}, InMemoryDao)
            dataCollector.manualInit()
            dataCollector._session = session
            
            bgpLinks = [{'device1': 'leaf1', 'device1as1': 401, 'device1Ip': '192.169.0.3+179', 'device2': None, 'device2as': 300, 'device2Ip': '192.169.0.2+57574', 'inputMsgCount': 16764, 'outputMsgCount': 16811, 'outQueueCount': 0 , 'linkState' : 'Established', 'active/receive/acceptCount': '3/3/3'},
                        {'device1': 'leaf1', 'device1as1': 401, 'device1Ip': '192.169.0.11+179', 'device2': None, 'device2as': 301, 'device2Ip': '192.169.0.10+49383','inputMsgCount': 16816, 'outputMsgCount': 16810, 'outQueueCount': 0 , 'linkState' : 'Established', 'active/receive/acceptCount': '2/2/2'}]
            dataCollector.persistBgpLinks(bgpLinks)

            bgpLinks = session.query(BgpLink).filter(BgpLink.device_id == device_id).all()
            self.assertEqual('192.169.0.3+179', bgpLinks[0].device1Ip)
            self.assertEqual('192.169.0.11+179', bgpLinks[1].device1Ip)

if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()
