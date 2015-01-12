'''
Created on Sep 11, 2014

@author: moloyc
'''
import unittest
from flexmock import flexmock

from jnpr.openclos.ztp import ZtpServer
import jnpr.openclos.util
from test_model import createPod, createDevice, createPodDevice, LeafSetting


class TestZtp(unittest.TestCase):

    def setUp(self):
        '''Creates with in-memory DB'''
        self.conf = {}
        self.conf['dbUrl'] = 'sqlite:///'
        self.conf['httpServer'] = {'ipAddr': '127.0.0.1'}
        jnpr.openclos.util.loadLoggingConfigForTest()

        self.ztpServer = ZtpServer(self.conf)
        
        self.session = self.ztpServer.dao.Session()

    def tearDown(self):
        pass
    
    def testGenerateDhcpConfWithNoPodDevice(self):
        from jnpr.openclos.l3Clos import util
        flexmock(util, isPlatformUbuntu = True)

        dhcpConf = self.ztpServer.generateSingleDhcpConf()
        self.assertFalse('{{' in dhcpConf)
        self.assertFalse('}}' in dhcpConf)
        self.assertEquals(1, dhcpConf.count('host-name')) # 1 global + 0 device

    def testGenerateSingleDhcpConf(self):
        from jnpr.openclos.l3Clos import util
        flexmock(util, isPlatformUbuntu = True)

        createDevice(self.session, 'dev1')
        createDevice(self.session, 'dev2')

        dhcpConf = self.ztpServer.generateSingleDhcpConf()
        self.assertFalse('{{' in dhcpConf)
        self.assertFalse('}}' in dhcpConf)
        self.assertEquals(3, dhcpConf.count('host-name')) # 1 global + 2 device
         
    def testGeneratePodSpecificDhcpConf(self):
        from jnpr.openclos.l3Clos import util
        flexmock(util, isPlatformUbuntu = True)
        
        pod = createPod('pod1', self.session)
        pod.spineJunosImage = 'testSpineImage'
        
        createPodDevice(self.session, 'dev1', pod)
        dev2 = createPodDevice(self.session, 'dev2', pod)
        dev3 = createPodDevice(self.session, 'dev3', pod)
        dev3.role = 'leaf'
      
        dhcpConf = self.ztpServer.generatePodSpecificDhcpConf(pod.id)
        self.assertEquals(2, dhcpConf.count('testSpineImage'))

        self.assertFalse('{{' in dhcpConf)
        self.assertFalse('}}' in dhcpConf)
        self.assertFalse('None' in dhcpConf)
        self.assertEquals(4, dhcpConf.count('host-name')) # 1 global + 3 device

    def testGeneratePodSpecificDhcpConfFor2StageZtp(self):
        from jnpr.openclos.l3Clos import util
        flexmock(util, isPlatformUbuntu = True)
        flexmock(util, isZtpStaged = True)
        
        pod = createPod('pod1', self.session)
        pod.spineJunosImage = 'testSpineImage'
        pod.leafSettings.append(LeafSetting('ex4300-24p', pod.id))
        
        dev1 = createPodDevice(self.session, 'dev1', pod)
        dev2 = createPodDevice(self.session, 'dev2', pod)
        dev3 = createPodDevice(self.session, 'dev3', pod)
        dev3.role = 'leaf'
        dev4 = createPodDevice(self.session, 'dev4', pod)
        dev4.role = 'leaf'
      
        dhcpConf = self.ztpServer.generatePodSpecificDhcpConf(pod.id)
        self.assertEquals(2, dhcpConf.count('testSpineImage'))

        self.assertFalse('{{' in dhcpConf)
        self.assertFalse('}}' in dhcpConf)
        self.assertFalse('None' in dhcpConf)
        self.assertEquals(3, dhcpConf.count('host-name')) # 1 global + 2 spine device
        self.assertEquals(1, dhcpConf.count('pool'))
        self.assertEquals(2, dhcpConf.count('class '))
        self.assertEquals(4, dhcpConf.count('vendor-class-identifier'))

    def testPopulateDhcpGlobalSettings(self):
        from jnpr.openclos.l3Clos import util
        globalZtpConf = {'ztp': {'dhcpSubnet': '10.20.30.0/25', 'dhcpOptionRoute': '10.20.30.254', 'dhcpOptionRangeStart': '10.20.30.15','dhcpOptionRangeEnd': '10.20.30.20'}}
        flexmock(util, loadClosDefinition = globalZtpConf)
        globalSetting = self.ztpServer.populateDhcpGlobalSettings()
        
        self.assertEquals('10.20.30.0', globalSetting['network'])
        self.assertEquals('255.255.255.128', globalSetting['netmask'])
        self.assertEquals('10.20.30.254', globalSetting['defaultRoute'])
        self.assertEquals('10.20.30.15', globalSetting['rangeStart'])
        self.assertEquals('10.20.30.20', globalSetting['rangeEnd'])

        globalZtpConf = {'ztp': {'dhcpSubnet': '10.20.30.0/25'}}
        flexmock(util, loadClosDefinition = globalZtpConf)
        globalSetting = self.ztpServer.populateDhcpGlobalSettings()
        
        self.assertEquals('10.20.30.1', globalSetting['defaultRoute'])
        self.assertEquals('10.20.30.2', globalSetting['rangeStart'])
        self.assertEquals('10.20.30.126', globalSetting['rangeEnd'])
        
if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()