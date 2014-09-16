'''
Created on Sep 11, 2014

@author: moloyc
'''
import unittest
from flexmock import flexmock

from jnpr.openclos.ztp import ZtpServer
from test_model import createPod, createDevice, createPodDevice


class TestZtp(unittest.TestCase):

    def setUp(self):
        '''Creates with in-memory DB'''
        self.conf = {}
        self.conf['dbUrl'] = 'sqlite:///'
        self.conf['httpServer'] = {'ipAddr': '127.0.0.1'}
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
        pod.leafJunosImage = 'testLeafImage'
        
        createPodDevice(self.session, 'dev1', pod)
        dev2 = createPodDevice(self.session, 'dev2', pod)
        dev3 = createPodDevice(self.session, 'dev3', pod)
        dev3.role = 'leaf'
        dev4 = createPodDevice(self.session, 'dev4', pod)
        dev4.role = 'unknown'
        
        dhcpConf = self.ztpServer.generatePodSpecificDhcpConf('pod1')
        self.assertEquals(2, dhcpConf.count('testSpineImage'))
        self.assertEquals(1, dhcpConf.count('testLeafImage'))

        self.assertFalse('{{' in dhcpConf)
        self.assertFalse('}}' in dhcpConf)
        self.assertEquals(5, dhcpConf.count('host-name')) # 1 global + 4 device


        
if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()