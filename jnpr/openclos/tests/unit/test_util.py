'''
Created on Aug 21, 2014

@author: moloyc
'''
import os
import sys
sys.path.insert(0,os.path.abspath(os.path.dirname(__file__) + '/' + '../..')) #trick to make it run from CLI
import unittest

import jnpr
from jnpr.openclos.util import *

class TestFunctions(unittest.TestCase):

    def setUp(self):
        pass

    def tearDown(self):
        conf = None

    def testGetMgmtIps(self):
        mgmtIpList = ["1.2.3.1/24", "1.2.3.2/24", "1.2.3.3/24", "1.2.3.4/24", "1.2.3.5/24", "1.2.3.6/24"] 
        mgmtIps = getMgmtIps("1.2.3.1/24", None, None, 6)
        self.assertEqual(mgmtIpList, mgmtIps)

        mgmtIpList = ["192.168.48.216/25", "192.168.48.217/25", "192.168.48.218/25", "192.168.48.219/25", "192.168.48.220/25"] 
        mgmtIps = getMgmtIps("192.168.48.216/25", None, None, 5)
        self.assertEqual(mgmtIpList, mgmtIps)

    def testIsZtpStaged(self):
        self.assertFalse(isZtpStaged(None))
        self.assertFalse(isZtpStaged({}))
        self.assertFalse(isZtpStaged({'deploymentMode': None}))
        self.assertFalse(isZtpStaged({'deploymentMode': {}}))
        self.assertFalse(isZtpStaged({'deploymentMode': {'ztpStaged': False}}))
        self.assertTrue(isZtpStaged({'deploymentMode': {'ztpStaged': True}}))

    def testEnumerateRoutableIpv4Addresses(self):
        addrList = enumerateRoutableIpv4Addresses()
        self.assertTrue(len(addrList) > 0)

    def testInterfaceNameToUniqueSequenceNumber(self):
        self.assertEqual(0, interfaceNameToUniqueSequenceNumber('et-0/0/0'))
        self.assertEqual(1, interfaceNameToUniqueSequenceNumber('et-0/0/1'))
        self.assertEqual(2, interfaceNameToUniqueSequenceNumber('et-0/0/2'))
        self.assertEqual(11, interfaceNameToUniqueSequenceNumber('et-0/0/11'))
        self.assertEqual(100, interfaceNameToUniqueSequenceNumber('et-0/0/100'))
        self.assertEqual(1000, interfaceNameToUniqueSequenceNumber('et-0/1/0'))
        self.assertEqual(1100, interfaceNameToUniqueSequenceNumber('et-0/1/100'))
        self.assertEqual(10000, interfaceNameToUniqueSequenceNumber('et-1/0/0'))
        
        self.assertEqual(10000000, interfaceNameToUniqueSequenceNumber('et-0/0/0.0'))
        self.assertEqual(10000001, interfaceNameToUniqueSequenceNumber('et-0/0/0.1'))
        self.assertEqual(10010000, interfaceNameToUniqueSequenceNumber('et-0/0/100.0'))
        self.assertEqual(10010001, interfaceNameToUniqueSequenceNumber('et-0/0/100.1'))
        self.assertEqual(10100000, interfaceNameToUniqueSequenceNumber('et-0/1/0.0'))
        self.assertEqual(10100001, interfaceNameToUniqueSequenceNumber('et-0/1/0.1'))
        self.assertEqual(11000001, interfaceNameToUniqueSequenceNumber('et-1/0/0.1'))

        self.assertEqual(20000000, interfaceNameToUniqueSequenceNumber('uplink-0'))
        self.assertEqual(20000001, interfaceNameToUniqueSequenceNumber('uplink-1'))
        self.assertEqual(21000000, interfaceNameToUniqueSequenceNumber('uplink-0.0'))
        self.assertEqual(21000001, interfaceNameToUniqueSequenceNumber('uplink-0.1'))
        self.assertEqual(21000100, interfaceNameToUniqueSequenceNumber('uplink-1.0'))
        self.assertEqual(21000101, interfaceNameToUniqueSequenceNumber('uplink-1.1'))

    def testLo0IrbVmeToUniqueSequenceNumber(self):
        seqNumSet = set()
        
        seqNumSet.add(interfaceNameToUniqueSequenceNumber('lo0'))
        seqNumSet.add(interfaceNameToUniqueSequenceNumber('lo0.0'))
        seqNumSet.add(interfaceNameToUniqueSequenceNumber('vme'))
        seqNumSet.add(interfaceNameToUniqueSequenceNumber('vme.0'))
        seqNumSet.add(interfaceNameToUniqueSequenceNumber('irb'))
        seqNumSet.add(interfaceNameToUniqueSequenceNumber('irb.1'))
        
        self.assertEqual(6, len(seqNumSet))

    def testGetOutFolderPath(self):
        from test_model import createPodObj
        pod = createPodObj('testPod')
        path = getOutFolderPath({}, pod)
        
        self.assertEquals('out/'+pod.id+'-'+pod.name, path)
        
    def testGetOutFolderPathFromConf(self):
        from test_model import createPodObj
        pod = createPodObj('testPod')
        path = getOutFolderPath({'outputDir': '/var/lib/openclos'}, pod)
        
        self.assertEquals('/var/lib/openclos/'+pod.id+'-'+pod.name, path)
        
if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()
