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
        pass

    def testLoadDefaultConfig(self):
        self.assertIsNotNone(loadConfig())
    def testLoadNonExistingConfig(self):
        self.assertIsNone(loadConfig('non-existing.yaml'))

    def testGetPortNamesForDeviceFamilyNullConf(self):
        with self.assertRaises(ValueError) as ve:
            getPortNamesForDeviceFamily(None, None)

    def testGetPortNamesForDeviceFamilyUnknownFamily(self):
        with self.assertRaises(ValueError) as ve:
            getPortNamesForDeviceFamily('unknown', {'QFX5100-24Q': {}})
        error = ve.exception.message
        self.assertTrue('unknown' in error)
        
    def testGetPortNamesForDeviceFamily24Q(self):
        portNames = getPortNamesForDeviceFamily('QFX5100-24Q', {'QFX5100-24Q': {'ports':'et-0/0/[0-23]'}})
        self.assertEqual(0, len(portNames['uplinkPorts']))
        self.assertEqual(0, len(portNames['downlinkPorts']))
        self.assertEqual(24, len(portNames['ports']))

    def testGetPortNamesForDeviceFamily48S(self):
        portNames = getPortNamesForDeviceFamily('QFX5100-48S', {'QFX5100-48S': {'uplinkPorts':'et-0/0/[48-53]', 'downlinkPorts': 'xe-0/0/[0-47]'}})
        self.assertEqual(6, len(portNames['uplinkPorts']))
        self.assertEqual(48, len(portNames['downlinkPorts']))
        self.assertEqual(0, len(portNames['ports']))
        
    def testGetPortNamesForDeviceFamily96S(self):
        portNames = getPortNamesForDeviceFamily('QFX5100-96S', {'QFX5100-96S': {'uplinkPorts':'et-0/0/[96-103]', 'downlinkPorts': 'xe-0/0/[0-95]'}})
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
        mgmtIps = getMgmtIps("1.2.3.1/24", 6)
        self.assertEqual(mgmtIpList, mgmtIps)

if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()