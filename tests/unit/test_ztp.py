'''
Created on Sep 11, 2014

@author: moloyc
'''
import unittest
from flexmock import flexmock

from jnpr.openclos.ztp import ZtpServer
from test_model import createDevice


class Test(unittest.TestCase):


    def setUp(self):
        '''Creates with in-memory DB'''
        self.conf = {}
        self.conf['dbUrl'] = 'sqlite:///'
        self.conf['httpServer'] = {'ipAddr': '127.0.0.1'}
        self.ztpServer = ZtpServer(self.conf)
        
        self.session = self.ztpServer.dao.Session()
        dev1 = createDevice(self.session, 'dev1')
        dev2 = createDevice(self.session, 'dev2')
        dev3 = createDevice(self.session, 'dev3')
        dev4 = createDevice(self.session, 'dev4')
        dev4.pod.junosImage = 'testImage'

    def tearDown(self):
        pass
    
    def testPopulateDhcpDeviceSpecificSetting(self):
        ztpDict = self.ztpServer.populateDhcpDeviceSpecificSetting()
        self.assertEquals(4, len(ztpDict['devices']))
    
    def testDhcpConfigForUbuntu(self):
        from jnpr.openclos.l3Clos import util
        flexmock(util, isPlatformUbuntu = True)
        dhcpConf = self.ztpServer.generateDhcpConf()
        self.assertFalse('{{' in dhcpConf)
        self.assertFalse('}}' in dhcpConf)
        self.assertEquals(5, dhcpConf.count('host-name')) # 1 global + 3 device
        

    def testDhcpConfigWithImagePerPod(self):
        from jnpr.openclos.l3Clos import util
        flexmock(util, isPlatformUbuntu = True)
        dhcpConf = self.ztpServer.generateDhcpConf()
        self.assertEquals(1, dhcpConf.count('testImage'))
        
        
if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()