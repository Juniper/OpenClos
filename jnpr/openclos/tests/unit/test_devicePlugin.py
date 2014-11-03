'''
Created on Oct 30, 2014

@author: moloyc
'''
import unittest
#from flexmock import flexmock


from jnpr.openclos.devicePlugin import Netconf 
from jnpr.openclos.exception import DeviceError

from jnpr.junos.exception import ConnectError

class TestNetconf(unittest.TestCase):


    def setUp(self):
        self.conf = {'dbUrl': 'sqlite:///'}

    def tearDown(self):
        pass

    @unittest.skip("need device")
    def testConnectToDevice(self):
        netconf = Netconf(self.conf)
        netconf.connectToDevice({'ip': '192.168.48.182', 'username': 'root', 'password': 'Embe1mpls'})

    def testConnectToDeviceFailure(self):
        netconf = Netconf(self.conf)
        with self.assertRaises(DeviceError) as de:
            netconf.connectToDevice({'ip': '0.0.0.0', 'username': 'root', 'password': 'Embe1mpls'})
        
        self.assertIsNotNone(de.exception.cause)
        self.assertTrue(issubclass(type(de.exception.cause), ConnectError))
        
    @unittest.skip("need device")
    def testCollectLldpFromDevice(self):
        netconf = Netconf(self.conf)
        netconf.collectLldpFromDevice({'ip': '192.168.48.219', 'username': 'root', 'password': 'Embe1mpls'})

if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()