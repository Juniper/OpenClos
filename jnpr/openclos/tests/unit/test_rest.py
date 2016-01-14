'''
Created on Sep 6, 2014

@author: moloyc
'''
import unittest
import os
import shutil
import json
from webtest import TestApp, AppError

from jnpr.openclos.rest import RestServer
from test_dao import InMemoryDao 

class TestRest(unittest.TestCase):

    def setUp(self):
        self._dao = InMemoryDao.getInstance()
        self._conf = {'restServer': {'version': 1, 'protocol': 'http', 'ipAddr': '1.2.3.4', 'port': 9090}}
        self.restServer = RestServer(self._conf, InMemoryDao)
        self.restServer.initRest()
        self.restServer.installRoutes()
        self.restServerTestApp = TestApp(self.restServer.app)

    def tearDown(self):
        self.restServer._reset()
        InMemoryDao._destroy()

    def testInit(self):
        self.assertEqual(1, self.restServer.version)
        self.assertEqual('http', self.restServer.protocol)
        self.assertEqual('1.2.3.4', self.restServer.host)
        self.assertEqual(9090, self.restServer.port)

class TestRestHttps(unittest.TestCase):

    def setUp(self):
        shutil.rmtree('/tmp/test.pem', ignore_errors=True)
        self._dao = InMemoryDao.getInstance()
        self._conf = {'restServer': {'version': 1, 'protocol': 'https', 'ipAddr': '127.0.0.1', 'port': 20443, 'username': 'juniper', 'password': '$9$R9McrvxNboJDWLJDikTQEcy', 'certificate': '/tmp/test.pem'}}
        self.restServer = RestServer(self._conf, InMemoryDao)
        self.restServer.initRest()
        self.restServer.installRoutes()
        self.restServerTestApp = TestApp(self.restServer.app)

    def tearDown(self):
        self.restServer._reset()
        InMemoryDao._destroy()
        shutil.rmtree('/tmp/test.pem', ignore_errors=True)

    def testInit(self):
        self.assertEqual(1, self.restServer.version)
        self.assertEqual('https', self.restServer.protocol)
        self.assertEqual('127.0.0.1', self.restServer.host)
        self.assertEqual(20443, self.restServer.port)
        self.assertEqual('/tmp/test.pem', self.restServer.certificate)
        
    def testWrongPassword(self):
        self.restServerTestApp.authorization = ('Basic', ('juniper', 'foo'))
        with self.assertRaises(AppError) as e:
            self.restServerTestApp.get('/openclos')
        self.assertTrue('401 Unauthorized' in e.exception.message)
        
    def testRightPassword(self):
        self.restServerTestApp.authorization = ('Basic', ('juniper', 'juniper'))
        response = self.restServerTestApp.get('/openclos')
        self.assertEqual(200, response.status_int)


if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()
