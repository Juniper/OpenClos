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
        self.assertEqual(100000, interfaceNameToUniqueSequenceNumber('et-0/0/0'))
        self.assertEqual(100001, interfaceNameToUniqueSequenceNumber('et-0/0/1'))
        self.assertEqual(100002, interfaceNameToUniqueSequenceNumber('et-0/0/2'))
        self.assertEqual(100011, interfaceNameToUniqueSequenceNumber('et-0/0/11'))
        self.assertEqual(100100, interfaceNameToUniqueSequenceNumber('et-0/0/100'))
        self.assertEqual(101000, interfaceNameToUniqueSequenceNumber('et-0/1/0'))
        self.assertEqual(101100, interfaceNameToUniqueSequenceNumber('et-0/1/100'))
        self.assertEqual(110000, interfaceNameToUniqueSequenceNumber('et-1/0/0'))
        
        self.assertEqual(10000000, interfaceNameToUniqueSequenceNumber('et-0/0/0.0'))
        self.assertEqual(10000001, interfaceNameToUniqueSequenceNumber('et-0/0/0.1'))
        self.assertEqual(10010000, interfaceNameToUniqueSequenceNumber('et-0/0/100.0'))
        self.assertEqual(10010001, interfaceNameToUniqueSequenceNumber('et-0/0/100.1'))
        self.assertEqual(10100000, interfaceNameToUniqueSequenceNumber('et-0/1/0.0'))
        self.assertEqual(10100001, interfaceNameToUniqueSequenceNumber('et-0/1/0.1'))
        self.assertEqual(11000001, interfaceNameToUniqueSequenceNumber('et-1/0/0.1'))

        self.assertEqual(200000, interfaceNameToUniqueSequenceNumber('xe-0/0/0'))
        self.assertEqual(200001, interfaceNameToUniqueSequenceNumber('xe-0/0/1'))
        self.assertEqual(300000, interfaceNameToUniqueSequenceNumber('ge-0/0/0'))
        self.assertEqual(300001, interfaceNameToUniqueSequenceNumber('ge-0/0/1'))

        self.assertEqual(90000000, interfaceNameToUniqueSequenceNumber('uplink-0'))
        self.assertEqual(90000001, interfaceNameToUniqueSequenceNumber('uplink-1'))
        self.assertEqual(91000000, interfaceNameToUniqueSequenceNumber('uplink-0.0'))
        self.assertEqual(91000001, interfaceNameToUniqueSequenceNumber('uplink-0.1'))
        self.assertEqual(91000100, interfaceNameToUniqueSequenceNumber('uplink-1.0'))
        self.assertEqual(91000101, interfaceNameToUniqueSequenceNumber('uplink-1.1'))

        self.assertEqual(92000000, interfaceNameToUniqueSequenceNumber('access-0'))
        self.assertEqual(92000001, interfaceNameToUniqueSequenceNumber('access-1'))
        self.assertEqual(93000000, interfaceNameToUniqueSequenceNumber('access-0.0'))
        self.assertEqual(93000001, interfaceNameToUniqueSequenceNumber('access-0.1'))
        self.assertEqual(93000100, interfaceNameToUniqueSequenceNumber('access-1.0'))
        self.assertEqual(93000101, interfaceNameToUniqueSequenceNumber('access-1.1'))

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

    def testReplaceFpcNumberOfInterface(self):
        self.assertEquals('et-2/0/10', replaceFpcNumberOfInterface('et-0/0/10', '2'))
        self.assertEquals('et-5/0/10.0', replaceFpcNumberOfInterface('et-0/0/10.0', '5'))
        
        
if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()
