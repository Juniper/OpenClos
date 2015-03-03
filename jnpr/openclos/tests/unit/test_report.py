'''
Created on Sep 9, 2014

@author: moloyc
'''
import unittest
import os

from jnpr.openclos.report import ResourceAllocationReport, L2Report, L3Report
from test_dao import InMemoryDao 

class Test(unittest.TestCase):


    def setUp(self):
        '''Creates with in-memory DB'''
        self.__conf = {}
        self.__conf['outputDir'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'out')
        self.__conf['dbUrl'] = 'sqlite:///'
        self.__conf['writeConfigInFile'] = 'false'
        self.__conf['logLevel'] = { 
                'fabric' : 'INFO',
                'reporting' : 'INFO',
                'ztp' : 'INFO',
                'rest' : 'INFO',
                'writer' : 'INFO',
                'devicePlugin' : 'INFO',
                'trapd' : 'INFO',
                'dao' : 'INFO'
        }
        self.__conf['DOT'] = {'ranksep' : '5 equally', 'colors': ['red', 'green', 'blue']}
        self.__conf['deviceFamily'] = {
            "qfx5100-24q-2p": {
                "ports": 'et-0/0/[0-23]'
            },
            "qfx5100-48s-6q": {
                "uplinkPorts": 'et-0/0/[48-53]', 
                "downlinkPorts": 'xe-0/0/[0-47]'
            }
        }
        self._dao = InMemoryDao.getInstance()
        #self.report = ResourceAllocationReport(self.__conf, InMemoryDao)

    def tearDown(self):
        self._dao = None
        InMemoryDao._destroy()
        
    '''
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
    ''' 
    
    def testGenerateL2Report(self):
        l2Report = L2Report(self.__conf, self._dao)
        from test_model import createPod
        with self._dao.getReadSession() as session:
            pod = createPod("test", session)
            l2Report.generateReport(pod.id, True, False)
            
    def testGenerateL3Report(self):
        l3Report = L3Report(self.__conf, self._dao)
        from test_model import createPod
        with self._dao.getReadSession() as session:
            pod = createPod("test", session)
            l3Report.generateReport(pod.id, True, False)

if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()