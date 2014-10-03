'''
Created on Sep 6, 2014

@author: moloyc
'''
import unittest
import os
import shutil
from webtest import TestApp, AppError

from jnpr.openclos.rest import RestServer, webServerRoot, junosImageRoot

configLocation = webServerRoot
imageLocation = junosImageRoot

class TestRest(unittest.TestCase):

    def setUp(self):
        '''Creates with in-memory DB'''
        self.conf = {}
        self.conf['dbUrl'] = 'sqlite:///'
        
        if not os.path.exists(configLocation):
            os.makedirs(configLocation)


    def tearDown(self):
        shutil.rmtree(os.path.join(configLocation, 'test1'), ignore_errors=True)


    def testInit(self):
        self.conf['httpServer'] = {}
        self.conf['httpServer']['ipAddr'] = '1.2.3.4'
        self.conf['httpServer']['port'] = 9090
        restServer = RestServer(self.conf)
        
        self.assertEqual('1.2.3.4', restServer.host)
        self.assertEqual(9090, restServer.port)
        self.assertEqual('http://1.2.3.4:9090', restServer.baseUrl)
        
    def testGetIndexNoPodNoDevice(self):
        restServer = RestServer(self.conf)
        restServer.initRest()
        restServerTestApp = TestApp(restServer.app)

        response = restServerTestApp.get('/')
        self.assertEqual(200, response.status_int)
        self.assertEqual('http://localhost:8080', response.json['href'])
        self.assertEqual(0, len(response.json['links']))

    def setupRestWithTwoDevices(self):
        from test_model import createDevice
        restServer = RestServer(self.conf)
        session = restServer.dao.Session()
        device1 = createDevice(session, "test1")
        device2 = createDevice(session, "test2")
        restServer.initRest()
        return TestApp(restServer.app)
        
    def testGetIndex(self):
        restServerTestApp = self.setupRestWithTwoDevices()

        response = restServerTestApp.get('/')
        self.assertEqual(200, response.status_int)
        self.assertEqual('http://localhost:8080', response.json['href'])
        self.assertEqual(2, len(response.json['links']))

    def testGetConfigNoDevice(self):
        restServerTestApp = self.setupRestWithTwoDevices()

        with self.assertRaises(AppError) as e:
            restServerTestApp.get('/pods/test1/devices/unknown/config')
        self.assertTrue('404 Not Found' in e.exception.message)
        self.assertTrue('No device found' in e.exception.message)

    def testGetConfigNoConfigFile(self):
        restServerTestApp = self.setupRestWithTwoDevices()

        with self.assertRaises(AppError) as e:
            restServerTestApp.get('/pods/test1/devices/test1/config')
        self.assertTrue('404 Not Found' in e.exception.message)
        self.assertTrue('Device exists but no config found' in e.exception.message)

    def testGetConfig(self):
        restServerTestApp = self.setupRestWithTwoDevices()
        podDir = os.path.join(configLocation, 'test1')
        if not os.path.exists(podDir):
            os.makedirs(podDir)

        open(os.path.join(podDir, 'test1.conf'), "a") 
        response = restServerTestApp.get('/pods/test1/devices/test1/config')
        self.assertEqual(200, response.status_int)

    def testGetJunosImage404(self):
        restServerTestApp = self.setupRestWithTwoDevices()

        with self.assertRaises(AppError) as e:
            restServerTestApp.get('/abcd.tgz')
        self.assertTrue('404 Not Found' in e.exception.message)

    def testGetJunosImage(self):
        restServerTestApp = self.setupRestWithTwoDevices()

        open(os.path.join(imageLocation, 'efgh.tgz'), "a") 
        
        response = restServerTestApp.get('/efgh.tgz')
        self.assertEqual(200, response.status_int)
        os.remove(os.path.join(imageLocation, 'efgh.tgz'))
        
if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()