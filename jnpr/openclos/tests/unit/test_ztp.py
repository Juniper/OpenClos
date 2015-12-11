'''
Created on Sep 11, 2014

@author: moloyc
'''
import unittest
from flexmock import flexmock

from jnpr.openclos.ztp import ZtpServer
from test_model import createPod, createDevice, createPodDevice, LeafSetting
from test_dao import InMemoryDao 

class TestZtp(unittest.TestCase):

    def setUp(self):
        self.__conf = {}
        self.__conf['restServer'] = {'ipAddr': '127.0.0.1', 'version': 1}

        self.ztpServer = ZtpServer(self.__conf, daoClass = InMemoryDao)
        self._dao = InMemoryDao.getInstance()

    def tearDown(self):
        InMemoryDao._destroy()
    
    def testGenerateDhcpConfWithNoPodDevice(self):
        from jnpr.openclos.l3Clos import util
        flexmock(util, isPlatformUbuntu = True)
        with self._dao.getReadWriteSession() as session:
            dhcpConf = self.ztpServer.generateSingleDhcpConf(session)
        self.assertFalse('{{' in dhcpConf)
        self.assertFalse('}}' in dhcpConf)
        self.assertEquals(1, dhcpConf.count('host-name')) # 1 global + 0 device

    def testGenerateSingleDhcpConf(self):
        from jnpr.openclos.l3Clos import util
        flexmock(util, isPlatformUbuntu = True)

        with self._dao.getReadWriteSession() as session:
            createDevice(session, 'dev1')
            createDevice(session, 'dev2')
            dhcpConf = self.ztpServer.generateSingleDhcpConf(session)

        self.assertFalse('{{' in dhcpConf)
        self.assertFalse('}}' in dhcpConf)
        self.assertEquals(3, dhcpConf.count('host-name')) # 1 global + 2 device
         
    def testGeneratePodSpecificDhcpConf(self):
        from jnpr.openclos.l3Clos import util
        flexmock(util, isPlatformUbuntu = True)
        
        with self._dao.getReadWriteSession() as session:
            pod = createPod('pod1', session)
            pod.spineJunosImage = 'testSpineImage'
            
            createPodDevice(session, 'dev1', pod)
            dev2 = createPodDevice(session, 'dev2', pod)
            dev3 = createPodDevice(session, 'dev3', pod)
            dev3.role = 'leaf'
          
            dhcpConf = self.ztpServer.generatePodSpecificDhcpConf(session, pod.id)

        self.assertEquals(2, dhcpConf.count('testSpineImage'))
        self.assertFalse('{{' in dhcpConf)
        self.assertFalse('}}' in dhcpConf)
        self.assertFalse('None' in dhcpConf)
        self.assertEquals(4, dhcpConf.count('host-name')) # 1 global + 3 device

    def testGeneratePodSpecificDhcpConfWithSerial(self):
        from jnpr.openclos.l3Clos import util
        flexmock(util, isPlatformUbuntu = True)
        
        with self._dao.getReadWriteSession() as session:
            pod = createPod('pod1', session)
            pod.spineJunosImage = 'testSpineImage'
            
            createPodDevice(session, 'dev1', pod)
            dev2 = createPodDevice(session, 'dev2', pod)
            dev2.macAddress = None
            dev2.serialNumber = 'VB1234567890'
            dev3 = createPodDevice(session, 'dev3', pod)
            dev3.role = 'leaf'
            dev3.serialNumber = 'VB1234567891'
          
            dhcpConf = self.ztpServer.generatePodSpecificDhcpConf(session, pod.id)
            print dhcpConf
        self.assertEquals(2, dhcpConf.count('testSpineImage'))
        self.assertFalse('{{' in dhcpConf)
        self.assertFalse('}}' in dhcpConf)
        self.assertFalse('None' in dhcpConf)
        self.assertTrue('VB1234567890' in dhcpConf)
        self.assertTrue('VB1234567891' not in dhcpConf)
        self.assertEquals(5, dhcpConf.count('host-name')) # 1 global class + 1 subnet + 2 device mac + 1 device serial

    def testGeneratePodSpecificDhcpConfFor2StageZtp(self):
        from jnpr.openclos.l3Clos import util
        flexmock(util, isPlatformUbuntu = True)
        flexmock(util, isZtpStaged = True)
        with self._dao.getReadWriteSession() as session:
            pod = createPod('pod1', session)
            pod.spineJunosImage = 'testSpineImage'
            pod.leafSettings.append(LeafSetting('ex4300-24p', pod.id))
            
            dev1 = createPodDevice(session, 'dev1', pod)
            dev2 = createPodDevice(session, 'dev2', pod)
            dev3 = createPodDevice(session, 'dev3', pod)
            dev3.role = 'leaf'
            dev4 = createPodDevice(session, 'dev4', pod)
            dev4.role = 'leaf'
          
            dhcpConf = self.ztpServer.generatePodSpecificDhcpConf(session, pod.id)

        self.assertEquals(2, dhcpConf.count('testSpineImage'))

        self.assertFalse('{{' in dhcpConf)
        self.assertFalse('}}' in dhcpConf)
        self.assertFalse('None' in dhcpConf)
        self.assertEquals(3, dhcpConf.count('host-name')) # 1 global + 2 spine device
        self.assertEquals(1, dhcpConf.count('pool'))
        self.assertEquals(2, dhcpConf.count('class '))
        self.assertEquals(4, dhcpConf.count('vendor-class-identifier'))

    def testPopulateDhcpGlobalSettings(self):
        from jnpr.openclos.l3Clos import loader
        globalZtpConf = {'ztp': {'dhcpSubnet': '10.20.30.0/25', 'dhcpOptionRoute': '10.20.30.254', 'dhcpOptionRangeStart': '10.20.30.15','dhcpOptionRangeEnd': '10.20.30.20'}}
        flexmock(loader, loadClosDefinition = globalZtpConf)
        globalSetting = self.ztpServer.populateDhcpGlobalSettings()
        
        self.assertEquals('10.20.30.0', globalSetting['network'])
        self.assertEquals('255.255.255.128', globalSetting['netmask'])
        self.assertEquals('10.20.30.254', globalSetting['defaultRoute'])
        self.assertEquals('10.20.30.15', globalSetting['rangeStart'])
        self.assertEquals('10.20.30.20', globalSetting['rangeEnd'])

        globalZtpConf = {'ztp': {'dhcpSubnet': '10.20.30.0/25'}}
        flexmock(loader, loadClosDefinition = globalZtpConf)
        globalSetting = self.ztpServer.populateDhcpGlobalSettings()
        
        self.assertEquals('10.20.30.1', globalSetting['defaultRoute'])
        self.assertEquals('10.20.30.2', globalSetting['rangeStart'])
        self.assertEquals('10.20.30.126', globalSetting['rangeEnd'])
        
if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()