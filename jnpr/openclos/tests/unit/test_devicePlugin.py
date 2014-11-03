'''
Created on Oct 30, 2014

@author: moloyc
'''
import unittest

from jnpr.openclos.devicePlugin import Netconf 

class TestNetconf(unittest.TestCase):


    def setUp(self):
        self.conf = {'dbUrl': 'sqlite:///'}

    def tearDown(self):
        pass

    @unittest.skip("need device")
    def testConnectToDevice(self):
        netconf = Netconf(self.conf)
        netconf.connectToDevice({'ip': '192.168.48.182', 'username': 'root', 'password': 'Embe1mpls'})

    @unittest.skip("need device")
    def testCollectLldpFromDevice(self):
        netconf = Netconf(self.conf)
        netconf.collectLldpFromDevice({'ip': '192.168.48.219', 'username': 'root', 'password': 'Embe1mpls'})

if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()