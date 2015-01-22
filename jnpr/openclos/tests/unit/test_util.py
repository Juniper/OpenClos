'''
Created on Aug 21, 2014

@author: moloyc
'''
import os
import sys
sys.path.insert(0,os.path.abspath(os.path.dirname(__file__) + '/' + '../..')) #trick to make it run from CLI
import unittest

from jnpr.openclos.util import *

class TestFunctions(unittest.TestCase):

    def setUp(self):
        pass

    def tearDown(self):
        conf = None

    def testLoadDefaultConfig(self):
        self.assertIsNotNone(loadConfig())
    '''
    def testLoadNonExistingConfig(self):
        conf = None
        self.assertIsNone(loadConfig(confFile = 'non-existing.yaml'))
    '''
    def testGetPortNamesForDeviceFamilyNullConf(self):
        with self.assertRaises(ValueError) as ve:
            getPortNamesForDeviceFamily(None, None)

    def testGetPortNamesForDeviceFamilyUnknownFamily(self):
        with self.assertRaises(ValueError) as ve:
            getPortNamesForDeviceFamily('unknown', {'qfx-5100-24q-2p': {}})
        error = ve.exception.message
        self.assertTrue('unknown' in error)
        
    def testGetPortNamesForDeviceFamily24Q(self):
        portNames = getPortNamesForDeviceFamily('qfx-5100-24q-2p', {'qfx-5100-24q-2p': {'ports':'et-0/0/[0-23]'}})
        self.assertEqual(0, len(portNames['uplinkPorts']))
        self.assertEqual(0, len(portNames['downlinkPorts']))
        self.assertEqual(24, len(portNames['ports']))

    def testGetPortNamesForDeviceFamily48S(self):
        portNames = getPortNamesForDeviceFamily('qfx-5100-48s-6q', {'qfx-5100-48s-6q': {'uplinkPorts':'et-0/0/[48-53]', 'downlinkPorts': 'xe-0/0/[0-47]'}})
        self.assertEqual(6, len(portNames['uplinkPorts']))
        self.assertEqual(48, len(portNames['downlinkPorts']))
        self.assertEqual(0, len(portNames['ports']))
        
    def testGetPortNamesForDeviceFamily96S(self):
        portNames = getPortNamesForDeviceFamily('qfx5100-96s-8q', {'qfx5100-96s-8q': {'uplinkPorts':'et-0/0/[96-103]', 'downlinkPorts': 'xe-0/0/[0-95]'}})
        self.assertEqual(8, len(portNames['uplinkPorts']))
        self.assertEqual(96, len(portNames['downlinkPorts']))
        self.assertEqual(0, len(portNames['ports']))

    def testExpandPortNameBadRegex1(self):
        with self.assertRaises(ValueError) as ve:
            expandPortName('xe-0/0/[1-1000]')
    def testExpandPortNameBadRegex2(self):
        with self.assertRaises(ValueError) as ve:
            expandPortName('xe-0//[1-10]')
    def testExpandPortNameBadRegex3(self):
        with self.assertRaises(ValueError) as ve:
            expandPortName('-0/0/[1-10]')
    def testExpandPortNameEmpty(self):
        portNames = expandPortName('')
        self.assertEqual(0, len(portNames))
        portNames = expandPortName(None)
        self.assertEqual(0, len(portNames))

    def testExpandPortName(self):
        portNames = expandPortName('xe-0/0/[1-10]')
        self.assertEqual(10, len(portNames))
        self.assertEqual('xe-0/0/1', portNames[0])
        self.assertEqual('xe-0/0/10', portNames[9])        
        
    def testExpandPortNameList(self):
        portNames = expandPortName(['xe-0/0/[1-10]', 'et-0/0/[0-3]'])
        self.assertEqual(14, len(portNames))
        self.assertEqual('xe-0/0/1', portNames[0])
        self.assertEqual('xe-0/0/10', portNames[9])        
        self.assertEqual('et-0/0/0', portNames[10])        
        self.assertEqual('et-0/0/3', portNames[13])        

    def testFixSqlliteDbUrlForRelativePath(self):
        dbUrl = fixSqlliteDbUrlForRelativePath('sqlite:////absolute-path/sqllite3.db')
        self.assertEqual(5, dbUrl.count('/'))
        dbUrl = fixSqlliteDbUrlForRelativePath('sqlite:///relative-path/sqllite3.db')
        if isPlatformWindows():
            self.assertTrue("C:\\" in dbUrl)
        else:
            self.assertTrue(dbUrl.count('/') > 4)
            
    def testGetMgmtIps(self):
        mgmtIpList = ["1.2.3.1/24", "1.2.3.2/24", "1.2.3.3/24", "1.2.3.4/24", "1.2.3.5/24", "1.2.3.6/24"] 
        mgmtIps = getMgmtIps("1.2.3.1/24", None, None, 6)
        self.assertEqual(mgmtIpList, mgmtIps)

        mgmtIpList = ["192.168.48.216/25", "192.168.48.217/25", "192.168.48.218/25", "192.168.48.219/25", "192.168.48.220/25"] 
        mgmtIps = getMgmtIps("192.168.48.216/25", None, None, 5)
        self.assertEqual(mgmtIpList, mgmtIps)

    def testIsIntegratedWithNd(self):
        self.assertFalse(isIntegratedWithND(None))
        self.assertFalse(isIntegratedWithND({}))
        self.assertFalse(isIntegratedWithND({'deploymentMode': None}))
        self.assertFalse(isIntegratedWithND({'deploymentMode': {}}))
        self.assertFalse(isIntegratedWithND({'deploymentMode': {'ndIntegrated': False}}))
        self.assertTrue(isIntegratedWithND({'deploymentMode': {'ndIntegrated': True}}))
        
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

    def testModifyConfigTrapTarget(self):
        modifyConfigTrapTarget('99.99.99.99')
        conf1 = loadConfig()
        self.assertEquals('99.99.99.99', conf1['snmpTrap']['networkdirector_trap_group']['target'])

    def testGetSupportedDeviceFamily(self):
        deviceFamilyList = getSupportedDeviceFamily({'qfx5100-96s-8q': {}, 'qfx5100-48s-6q': {}})
        self.assertEqual(2, len(deviceFamilyList))
        
        with self.assertRaises(ValueError):
            getSupportedDeviceFamily(None)

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

    def testLoadLoggingConfig(self):
        loadLoggingConfig({}, appName='rest')
        import logging
        self.assertEquals(0, len(logging.getLogger('unknown').handlers))
        self.assertEquals(2, len(logging.getLogger('rest').handlers))
        self.assertTrue('openclos-rest.log' in logging.getLogger('rest').handlers[1].baseFilename)

    @unittest.skip("require root access")
    def testLoadLoggingConfigWithNd(self):
        if not os.path.exists('/var/log/openclos'):
            os.makedirs('/var/log/openclos')
        loadLoggingConfig({'deploymentMode': {'ndIntegrated' : True}}, appName='rest')
        import logging
        self.assertEquals(0, len(logging.getLogger('unknown').handlers))
        self.assertEquals(1, len(logging.getLogger('rest').handlers))
        shutil.rmtree(self.conf['outputDir'], ignore_errors=True)

    def testLoadLoggingForTest(self):
        loadLoggingConfig({})
        import logging
        self.assertEquals(0, len(logging.getLogger('unknown').handlers))
        self.assertEquals(1, len(logging.getLogger('rest').handlers))

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

    def testGetSnmpTrapTargets(self):
        self.assertEqual(0, len(getSnmpTrapTargets({})))
        self.assertEqual(0, len(getSnmpTrapTargets({'snmpTrap': {'networkdirector_trap_group': {'target': '0.0.0.0'}}})))
        self.assertEqual(1, len(getSnmpTrapTargets({'snmpTrap': {'networkdirector_trap_group': {'target': '1.2.3.4'}}})))
        self.assertEqual(1, len(getSnmpTrapTargets({'snmpTrap': {'openclos_trap_group': {'target': '1.2.3.4'}}})))
        self.assertEqual(2, len(getSnmpTrapTargets({'snmpTrap': {'networkdirector_trap_group': {'target': '1.2.3.4'}, 'openclos_trap_group': {'target': '1.2.3.5'}}})))
        
        
if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()
