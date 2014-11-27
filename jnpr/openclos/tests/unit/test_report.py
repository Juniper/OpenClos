'''
Created on Sep 9, 2014

@author: moloyc
'''
import unittest
import os

from jnpr.openclos.report import ResourceAllocationReport, L2Report

class Test(unittest.TestCase):


    def setUp(self):
        '''Creates with in-memory DB'''
        self.conf = {}
        self.conf['outputDir'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'out')
        self.conf['dbUrl'] = 'sqlite:///'
        self.conf['writeConfigInFile'] = 'false'
        self.conf['logLevel'] = { 
                'fabric' : 'INFO',
                'reporting' : 'INFO',
                'ztp' : 'INFO',
                'rest' : 'INFO',
                'writer' : 'INFO',
                'devicePlugin' : 'INFO',
                'trapd' : 'INFO',
                'dao' : 'INFO'
        }
        self.conf['DOT'] = {'ranksep' : '5 equally', 'colors': ['red', 'green', 'blue']}
        self.conf['deviceFamily'] = {
            "qfx5100-24q-2p": {
                "ports": 'et-0/0/[0-23]'
            },
            "qfx5100-48s-6q": {
                "uplinkPorts": 'et-0/0/[48-53]', 
                "downlinkPorts": 'xe-0/0/[0-47]'
            }
        }
        self.report = ResourceAllocationReport(self.conf)
        self.session = self.report.dao.Session()

    def tearDown(self):
        pass

    def testGetInterconnectAllocation(self):
        from test_model import createPod
        pod = createPod("test", self.session)
        pod.allocatedInterConnectBlock = '1.2.3.4/24'
        pod.interConnectPrefix = '1.2.0.0/24'
        
        interconnectAllocation = self.report.getInterconnectAllocation("test")
        self.assertEqual('1.2.0.0/24', interconnectAllocation['block'])
        self.assertEqual('1.2.3.4/24', interconnectAllocation['allocated'])

    def testGetInterconnectAllocationNoPod(self):
        interconnectAllocation = self.report.getInterconnectAllocation("test")
        self.assertEqual({}, interconnectAllocation)
        
    def testGenerateReport(self):
        l2Report = L2Report()
        from test_model import createPod
        pod = createPod("test", l2Report.dao.Session())
        l2Report.generateReport(pod.id, True, False)

if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()