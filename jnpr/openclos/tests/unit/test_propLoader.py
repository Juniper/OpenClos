'''
Created on Apr 16, 2015

@author: moloy
'''
import unittest
import os

from jnpr.openclos.propLoader import PropertyLoader, OpenClosProperty, DeviceSku, loadLoggingConfig
from jnpr.openclos.exception import InvalidConfiguration

class TestPropertyLoader(unittest.TestCase):

    def setUp(self):
        self.propertyLoader = PropertyLoader()

    def tearDown(self):
        pass

    def testGetFileNameWithPathPwd(self):
        self.assertIsNone(self.propertyLoader.getFileNameWithPath('unknown'))
        open('testFile', 'a')
        self.assertEquals(os.path.join(os.getcwd(), 'testFile'), 
                          self.propertyLoader.getFileNameWithPath('testFile'))
        os.remove('testFile')
        
    def testGetFileNameWithPathConf(self):
        from jnpr.openclos.propLoader import propertyFileLocation
        self.assertEquals(os.path.join(propertyFileLocation, 'openclos.yaml'), 
                          self.propertyLoader.getFileNameWithPath('openclos.yaml'))
        self.assertEquals(os.path.join(propertyFileLocation, 'deviceFamily.yaml'), 
                          self.propertyLoader.getFileNameWithPath('deviceFamily.yaml'))


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
    def testExpandPortNameEmpty(self):
        portNames = self.deviceSku.portRegexToList('')
        self.assertEqual(0, len(portNames))
        portNames = self.deviceSku.portRegexToList(None)
        self.assertEqual(0, len(portNames))

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
        
    def testGetSupportedDeviceFamilyBadInputFile(self):
        self.deviceSku = DeviceSku('')
        with self.assertRaises(InvalidConfiguration):
            self.deviceSku.getSupportedDeviceFamily()

    def testGetSupportedDeviceFamily(self):
        deviceFamilyList = self.deviceSku.getSupportedDeviceFamily()
        self.assertEqual(11, len(deviceFamilyList))


class TestMethod(unittest.TestCase):
    def testLoadLoggingConfig(self):
        loadLoggingConfig(appName = 'unittest')
        import logging
        self.assertEquals(0, len(logging.getLogger('unknown').handlers))
        self.assertEquals(2, len(logging.getLogger('rest').handlers))
        self.assertTrue('openclos-unittest.log' in logging.getLogger('rest').handlers[1].baseFilename)



if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()
