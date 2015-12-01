'''
Created on Nov 17, 2015

@author: moloyc
'''
import unittest
import time
from flexmock import flexmock

from jnpr.openclos.deviceConnector import NetconfConnection, CachedConnectionFactory
from jnpr.openclos.exception import DeviceConnectFailed
from jnpr.junos.exception import ConnectError

@unittest.skip("need physical device to test")
class TestNetconfConnector(unittest.TestCase):
    
    def testConnectToDevice(self):
        connector = NetconfConnection('192.168.48.216', username='root', password='Embe1mpls')
        self.assertIsNotNone(connector)
        self.assertTrue(connector._deviceConnectionHandle.connected)
        
    def testGetDeviceFamily(self):
        connector = NetconfConnection('192.168.48.216', username='root', password='Embe1mpls')
        self.assertEquals('qfx5100-24q-2p', connector.getDeviceFamily())

    def testGetDeviceSerialNumber(self):
        connector = NetconfConnection('192.168.48.216', username='root', password='Embe1mpls')
        self.assertEquals('VG3714070310', connector.getDeviceSerialNumber())

    def testConnectToDeviceConnectError(self):
        with self.assertRaises(DeviceConnectFailed) as de:
            NetconfConnection('192.168.48.217', username='root', password='Embe1mpls')
        
        self.assertIsNotNone(de.exception.cause)
        self.assertTrue(issubclass(type(de.exception.cause), ConnectError))

    def testGetL2Neighbors(self):
        connector = NetconfConnection('192.168.48.216', username='root', password='Embe1mpls')
        connector.getL2Neighbors()

    def testGetL3Neighbors(self):
        connector = NetconfConnection('192.168.48.216', username='root', password='Embe1mpls')
        connector.getL3Neighbors(brief=False)

    def testUpdateConfig(self):
        connector = NetconfConnection('192.168.48.216', username='root', password='Embe1mpls')
        config = '''
        routing-options {
            static {
                route 192.168.55.139/32 next-hop 192.168.48.254;
            }
        }
        '''
        connector.updateConfig(config)

class TestCachedConnectionFactory(unittest.TestCase):
    def setUp(self):
        from jnpr.junos import Device
        self.fakeDevice = flexmock(connected=True)
        self.fakeDevice.should_receive('open').and_return(None)
        self.fakeDevice.should_receive('close').and_return(None)
        flexmock(Device).new_instances(self.fakeDevice)
        
        from jnpr.openclos import deviceConnector
        deviceConnector.connectionCleanerThreadWaitTimeSec = 4
        deviceConnector.connectionKeepAliveTimeoutSec = 2
        print 'setup'

    def tearDown(self):
        CachedConnectionFactory.getInstance()._stop()
        CachedConnectionFactory._destroy()
        print 'tearDown'
    def testConnectionCached(self):
        conn1 = None
        conn2 = None
        conn3 = None
        print CachedConnectionFactory.getInstance()
        with CachedConnectionFactory.getInstance().connection(NetconfConnection, "1.2.3.4") as connector:
            conn1 = str(connector)
            self.assertIsNotNone(connector)
            self.assertTrue(connector.isActive())
        with CachedConnectionFactory.getInstance().connection(NetconfConnection, "1.2.3.4") as connector:
            conn2 = str(connector)
            self.assertIsNotNone(connector)
            self.assertTrue(connector.isActive())
        with CachedConnectionFactory.getInstance().connection(NetconfConnection, "1.2.3.5") as connector:
            conn3 = str(connector)
            self.assertIsNotNone(connector)
            self.assertTrue(connector.isActive())

        self.assertEquals(conn1, conn2)
        self.assertNotEquals(conn1, conn3)

    def testBadConnectionNotCached(self):
        from jnpr.junos import Device
        self.fakeDevice = flexmock(connected=False)
        self.fakeDevice.should_receive('open').and_return(None)
        self.fakeDevice.should_receive('close').and_return(None)
        flexmock(Device).new_instances(self.fakeDevice)

        conn1 = None
        conn2 = None
        print CachedConnectionFactory.getInstance()
        with CachedConnectionFactory.getInstance().connection(NetconfConnection, "1.2.3.6") as connector:
            conn1 = str(connector)
            self.assertIsNotNone(connector)
            self.assertFalse(connector.isActive())
        
        with CachedConnectionFactory.getInstance().connection(NetconfConnection, "1.2.3.6") as connector:
            conn2 = str(connector)
            self.assertIsNotNone(connector)
            self.assertFalse(connector.isActive())

        self.assertNotEquals(conn1, conn2)

    def testConnectionKeepAlive(self):
        conn1 = None
        conn2 = None
        print CachedConnectionFactory.getInstance()
        # waiting for conn1 to get closed, so closed will be called once.
        self.fakeDevice.should_receive('close').times(1) 
        with CachedConnectionFactory.getInstance().connection(NetconfConnection, "1.2.3.7") as connector:
            conn1 = str(connector)
            self.assertIsNotNone(connector)
            self.assertTrue(connector.isActive())
        time.sleep(6)
        
        with CachedConnectionFactory.getInstance().connection(NetconfConnection, "1.2.3.7") as connector:
            conn2 = str(connector)
            self.assertIsNotNone(connector)
            self.assertTrue(connector.isActive())

        self.assertNotEquals(conn1, conn2)

if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()