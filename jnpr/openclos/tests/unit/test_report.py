'''
Created on Sep 9, 2014

@author: moloyc
'''
import unittest

from jnpr.openclos.report import ResourceAllocationReport, L2Report
from jnpr.openclos.model import InterfaceDefinition

class Test(unittest.TestCase):


    def setUp(self):
        '''Creates with in-memory DB'''
        self.conf = {}
        self.conf['dbUrl'] = 'sqlite:///'
        self.report = ResourceAllocationReport(self.conf)
        self.session = self.report.dao.Session()

    def tearDown(self):
        pass

    def testGetInterconnectAllocation(self):
        from test_model import createPod
        pod = createPod("test", self.session)
        pod.allocatedInterConnectBlock = '1.2.3.4/24'
        pod.interConnectPrefix = '1.2.0.0'
        
        interconnectAllocation = self.report.getInterconnectAllocation("test")
        self.assertEqual('1.2.0.0', interconnectAllocation['block'])
        self.assertEqual('1.2.3.4/24', interconnectAllocation['allocated'])

    def testGetInterconnectAllocationNoPod(self):
        interconnectAllocation = self.report.getInterconnectAllocation("test")
        self.assertEqual({}, interconnectAllocation)

class TestL2Report(unittest.TestCase):

    def setUp(self):
        self.conf = {}
        self.conf['dbUrl'] = 'sqlite:///'
        self.report = L2Report(self.conf)
        self.session = self.report.dao.Session()

    def tearDown(self):
        pass

    def testUpdateIfdLldpStatusForUplinks(self):
        from test_model import createDevice
        spine = createDevice(self.session, 'spine')
        leaf = createDevice(self.session, 'leaf')
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

        self.report.updateIfdLldpStatusForUplinks([{'device1': '', 'port1': 'et-0/0/48', 'device2': 'spine', 'port2': 'et-0/0/0'},
                                                   {'device1': '', 'port1': 'et-0/0/49', 'device2': 'spine', 'port2': 'et-0/0/1'},
                                                   {'device1': '', 'port1': 'et-0/0/50', 'device2': 'spine-unknown', 'port2': 'et-0/0/0'}, # bad connection 
                                                   {'device1': '', 'port1': 'xe-0/0/0', 'device2': 'server', 'port2': 'eth0'},
                                                   {'device1': '', 'port1': 'xe-0/0/1', 'device2': 'server', 'port2': 'eth1'},
                                                ], leaf)
        
        self.assertEqual('good', self.session.query(InterfaceDefinition).filter(InterfaceDefinition.id == IFDs[0].id).one().lldpStatus)
        self.assertEqual('good', self.session.query(InterfaceDefinition).filter(InterfaceDefinition.id == IFDs[1].id).one().lldpStatus)
        self.assertIsNone(self.session.query(InterfaceDefinition).filter(InterfaceDefinition.id == IFDs[2].id).one().lldpStatus)
        self.assertIsNone(self.session.query(InterfaceDefinition).filter(InterfaceDefinition.id == IFDs[3].id).one().lldpStatus)

        self.assertEqual('good', self.session.query(InterfaceDefinition).filter(InterfaceDefinition.id == IFDs[4].id).one().lldpStatus)
        self.assertEqual('good', self.session.query(InterfaceDefinition).filter(InterfaceDefinition.id == IFDs[5].id).one().lldpStatus)
        self.assertEqual('bad', self.session.query(InterfaceDefinition).filter(InterfaceDefinition.id == IFDs[6].id).one().lldpStatus)
        self.assertIsNone(self.session.query(InterfaceDefinition).filter(InterfaceDefinition.id == IFDs[7].id).one().lldpStatus)

if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()