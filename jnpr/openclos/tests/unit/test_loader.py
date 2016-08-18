'''
Created on Apr 16, 2015

@author: moloy
'''
import unittest
import os

from jnpr.openclos.loader import *
from jnpr.openclos.exception import InvalidConfiguration

class TestPropertyLoader(unittest.TestCase):

    def setUp(self):
        self.propertyLoader = PropertyLoader(None)
    def tearDown(self):
        pass
        
    def testMergetDictNestedList(self):
        prop = {'DOT' : {'colors' : ['blue', 'green'], 'ranksep' : '5 equally'}}
        override = {'DOT' : {'colors' : ['green', 'violet']}}
        merged = {'DOT' : {'colors' : ['blue', 'green', 'violet'], 'ranksep' : '5 equally'}}
        #print PropertyLoader.mergeDict(prop, override)
        self.assertDictEqual(merged, self.propertyLoader.mergeDict(prop, override))
       
    def testMergetDictNestedDict(self):
        prop = {'snmpTrap' : {'openclos_trap_group' : {'port' : 20162, 'target' : '0.0.0.0'}, 'threadCount' : 10}}
        override = {'snmpTrap' : {'openclos_trap_group' : {'target' : '1.1.1.1'}}}
        merged = {'snmpTrap' : {'openclos_trap_group' : {'port' : 20162, 'target' : '1.1.1.1'}, 'threadCount' : 10}}
        #print PropertyLoader.mergeDict(prop, override)
        self.assertDictEqual(merged, self.propertyLoader.mergeDict(prop, override))

    def testMergetListNestedDict(self):
        prop = {'plugin': [{'name': 'overlay', 'package': 'jnpr.openclos.overlay'}]}
        override = {'plugin': [{'name': 'overlay', 'package': 'jnpr.openclos.overlay'}]}
        merged = {'plugin': [{'name': 'overlay', 'package': 'jnpr.openclos.overlay'}]}
        self.assertDictEqual(merged, self.propertyLoader.mergeDict(prop, override))

        prop = {'plugin': [{'name': 'overlay', 'package': 'jnpr.openclos.overlay'}]}
        override = {'plugin': [{'sample': 'fooo', 'bar': 'hoge'}]}
        merged = {'plugin': [{'name': 'overlay', 'package': 'jnpr.openclos.overlay'}, {'sample': 'fooo', 'bar': 'hoge'}]}
        self.assertDictEqual(merged, self.propertyLoader.mergeDict(prop, override))

    def testLoadProperty(self):
        self.propertyLoader = PropertyLoader('openclos.yaml', False)
        self.assertIsNot({}, self.propertyLoader._properties)
        self.assertEquals("out", self.propertyLoader._properties['outputDir'])
        self.assertEquals(1, len(self.propertyLoader._properties['plugin']))

    def testLoadPropertyOverride(self):
        overridePath = os.path.join(os.path.expanduser('~'), 'openclos.yaml')
        with open(overridePath, 'w') as fStream:
            fStream.write('outputDir : /tmp')
        self.propertyLoader = PropertyLoader('openclos.yaml')
        self.assertIsNot({}, self.propertyLoader._properties)
        self.assertEquals("/tmp", self.propertyLoader._properties['outputDir'])
        self.assertEquals(1, len(self.propertyLoader._properties['plugin']))
        os.remove(overridePath)
        

class TestOpenClosProperty(unittest.TestCase):

    def setUp(self):
        self.openClosProperty = OpenClosProperty()

    def tearDown(self):
        pass

    def testFixSqlliteDbUrlForRelativePath(self):
        import jnpr.openclos.util
        dbUrl = self.openClosProperty.fixSqlliteDbUrlForRelativePath('sqlite:////absolute-path/sqllite3.db')
        self.assertEqual(5, dbUrl.count('/'))
        dbUrl = self.openClosProperty.fixSqlliteDbUrlForRelativePath('sqlite:///relative-path/sqllite3.db')
        if jnpr.openclos.util.isPlatformWindows():
            self.assertTrue("C:\\" in dbUrl)
        else:
            self.assertTrue(dbUrl.count('/') > 4)
            
    def testLoadDefaultConfig(self):
        self.assertIsNotNone(self.openClosProperty.getProperties())

    def testGetDbUrl(self):
        self.assertTrue('sqlite:' in self.openClosProperty.getDbUrl())



class TestDeviceSku(unittest.TestCase):
    def setUp(self):
        #loadLoggingConfig(appName = 'unittest')
        self.deviceSku = DeviceSku()

    def tearDown(self):
        pass

    def testExpandPortNameBadRegex1(self):
        with self.assertRaises(InvalidConfiguration) as ve:
            self.deviceSku.portRegexToList('xe-0/0/[1-1000]')
    def testExpandPortNameBadRegex2(self):
        with self.assertRaises(InvalidConfiguration) as ve:
            self.deviceSku.portRegexToList('xe-0//[1-10]')
    def testExpandPortNameBadRegex3(self):
        with self.assertRaises(InvalidConfiguration) as ve:
            self.deviceSku.portRegexToList('-0/0/[1-10]')
    def testExpandPortNameBadRegex4(self):
        with self.assertRaises(InvalidConfiguration) as ve:
            self.deviceSku.portRegexToList('xe-0/0/[10-1]')
    def testExpandPortNameEmpty(self):
        portNames = self.deviceSku.portRegexToList('')
        self.assertEqual(0, len(portNames))
        portNames = self.deviceSku.portRegexToList(None)
        self.assertEqual(0, len(portNames))

    def testExpandPortNameSinglePort(self):
        portNames = self.deviceSku.portRegexToList('xe-0/0/[1-1]')
        self.assertEqual(1, len(portNames))
        self.assertEqual('xe-0/0/1', portNames[0])

    def testExpandPortName(self):
        portNames = self.deviceSku.portRegexToList('xe-0/0/[1-10]')
        self.assertEqual(10, len(portNames))
        self.assertEqual('xe-0/0/1', portNames[0])
        self.assertEqual('xe-0/0/10', portNames[9])        
        
    def testExpandPortNameList(self):
        portNames = self.deviceSku.portRegexListToList(['xe-0/0/[1-10]', 'et-0/0/[0-3]'])
        self.assertEqual(14, len(portNames))
        self.assertEqual('xe-0/0/1', portNames[0])
        self.assertEqual('xe-0/0/10', portNames[9])        
        self.assertEqual('et-0/0/0', portNames[10])        
        self.assertEqual('et-0/0/3', portNames[13])        
        
    def testGetPortNamesForDeviceFamilyBadInputFile(self):
        self.deviceSku = DeviceSku('')
        ports = self.deviceSku.getPortNamesForDeviceFamily('qfx5100-24q-2p', 'fabric')
        self.assertEqual(0, len(ports['uplinkPorts']))
        self.assertEqual(0, len(ports['downlinkPorts']))

    def testGetPortNamesForDeviceFamilyBadInput(self):
        ports = self.deviceSku.getPortNamesForDeviceFamily(None, 'fabric')
        self.assertEqual(0, len(ports['uplinkPorts']))
        self.assertEqual(0, len(ports['downlinkPorts']))

        ports = self.deviceSku.getPortNamesForDeviceFamily('unknown', 'spine')
        self.assertEqual(0, len(ports['uplinkPorts']))
        self.assertEqual(0, len(ports['downlinkPorts']))

        ports = self.deviceSku.getPortNamesForDeviceFamily('qfx5100-24q-2p', None)
        self.assertEqual(0, len(ports['uplinkPorts']))
        self.assertEqual(0, len(ports['downlinkPorts']))

    def testGetPortNamesForDeviceFamily(self):
        ports = self.deviceSku.getPortNamesForDeviceFamily('qfx5100-24q-2p', 'fabric')
        self.assertEqual(0, len(ports['uplinkPorts']))
        self.assertEqual(32, len(ports['downlinkPorts']))
        
        ports = self.deviceSku.getPortNamesForDeviceFamily('qfx5100-24q-2p', 'spine')
        self.assertEqual(0, len(ports['uplinkPorts']))
        self.assertEqual(32, len(ports['downlinkPorts']))
        
        ports = self.deviceSku.getPortNamesForDeviceFamily('qfx5100-24q-2p', 'spine', '5-Stage')
        self.assertEqual(16, len(ports['uplinkPorts']))
        self.assertEqual(16, len(ports['downlinkPorts']))

        ports = self.deviceSku.getPortNamesForDeviceFamily('qfx10002-36q', 'fabric')
        self.assertEqual(0, len(ports['uplinkPorts']))
        self.assertEqual(36, len(ports['downlinkPorts']))
        
        ports = self.deviceSku.getPortNamesForDeviceFamily('qfx10002-36q', 'spine')
        self.assertEqual(0, len(ports['uplinkPorts']))
        self.assertEqual(36, len(ports['downlinkPorts']))
        
        ports = self.deviceSku.getPortNamesForDeviceFamily('qfx10002-36q', 'spine', '5-Stage')
        self.assertEqual(18, len(ports['uplinkPorts']))
        self.assertEqual(18, len(ports['downlinkPorts']))

        ports = self.deviceSku.getPortNamesForDeviceFamily('qfx5100-24q-2p', 'leaf')
        self.assertEqual(0, len(ports['uplinkPorts']))
        self.assertEqual(0, len(ports['downlinkPorts']))
        
        ports = self.deviceSku.getPortNamesForDeviceFamily('qfx5100-48s-6q', 'fabric')
        self.assertEqual(0, len(ports['uplinkPorts']))
        self.assertEqual(0, len(ports['downlinkPorts']))

        ports = self.deviceSku.getPortNamesForDeviceFamily('qfx5100-48s-6q', 'spine')
        self.assertEqual(0, len(ports['uplinkPorts']))
        self.assertEqual(0, len(ports['downlinkPorts']))

        ports = self.deviceSku.getPortNamesForDeviceFamily('qfx5100-48s-6q', 'leaf')
        self.assertEqual(6, len(ports['uplinkPorts']))
        self.assertEqual(96, len(ports['downlinkPorts']))   # 48 xe and 48 ge ports

        ports=self.deviceSku.getPortNamesForDeviceFamily('qfx5200-32c-32q','spine')
        self.assertEqual(0, len(ports['uplinkPorts']))
        self.assertEqual(32, len(ports['downlinkPorts']))
        
        ports=self.deviceSku.getPortNamesForDeviceFamily('qfx5200-32c-32q','leaf')
        self.assertEqual(8, len(ports['uplinkPorts']))
        self.assertEqual(28, len(ports['downlinkPorts']))

    def testGetSupportedDeviceFamilyBadInputFile(self):
        self.deviceSku = DeviceSku('')
        with self.assertRaises(InvalidConfiguration):
            self.deviceSku.getSupportedDeviceFamily()

    def testGetSupportedDeviceFamily(self):
        deviceFamilyList = self.deviceSku.getSupportedDeviceFamily()
        self.assertEqual(13, len(deviceFamilyList))

    def testOverrideDeviceSku(self):
        overridePath = os.path.join(os.path.expanduser('~'), 'deviceFamily.yaml')
        with open(overridePath, 'w') as fStream:
            override = """deviceFamily:
                            qfx5100-48s-6q:
                                leaf:
                                    downlinkPorts: ['xe-0/0/[0-29]', 'ge-0/0/[0-39]']"""
            fStream.write(override)
        self.deviceSku = DeviceSku()

        ports = self.deviceSku.getPortNamesForDeviceFamily('qfx5100-48s-6q', 'leaf')
        self.assertEqual(6, len(ports['uplinkPorts']))
        self.assertEqual(70, len(ports['downlinkPorts']))   # 30 xe and 40 ge ports

        os.remove(overridePath)

class TestMethod(unittest.TestCase):
    def testGetOverrideFileWithPathHome(self):
        self.assertIsNone(getAlternateFileWithPath('homeFile'))
        filePath = os.path.join(os.path.expanduser('~'), 'homeFile')
        open(filePath, 'a')
        self.assertTrue(getAlternateFileWithPath('homeFile').endswith('/homeFile'))
        os.remove(filePath)

    def testGetOverrideFileWithPathPwd(self):
        self.assertIsNone(getAlternateFileWithPath('pwdFile'))
        filePath = os.path.join(os.getcwd(), 'pwdFile')
        open(filePath, 'a')
        self.assertTrue(getAlternateFileWithPath('pwdFile').startswith(os.getcwd()))
        os.remove(filePath)

    def testLoadClosDefinition(self):
        pods = loadPodsFromClosDefinition(False)
        self.assertEqual(3, len(pods))

    def testLoadNonExistingClosDefinition(self):
        closDef = loadClosDefinition('non-existing.yaml')
        self.assertIsNone(closDef)

    def testLoadLoggingConfig(self):
        loadLoggingConfig(appName = 'unittest')
        import logging
        self.assertEquals(0, len(logging.getLogger('unknown').handlers))
        self.assertEquals(2, len(logging.getLogger('rest').handlers))
        self.assertTrue('openclos-unittest.log' in logging.getLogger('rest').handlers[1].baseFilename)



if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()
