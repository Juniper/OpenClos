'''
Created on Sep 9, 2014

@author: moloyc
'''
import unittest

from jnpr.openclos.report import ResourceAllocationReport, L2Report

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

if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()