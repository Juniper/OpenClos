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
        
if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()
