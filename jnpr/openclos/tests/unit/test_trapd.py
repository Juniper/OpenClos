'''
Created on Nov. 6, 2014

@author: yunli
'''
import unittest
import os
import sys
from time import sleep

from jnpr.openclos.trapd import TrapReceiver

class TestTrapReceiver(unittest.TestCase):

    def testInit(self):
        self.__conf = {}
        self.__conf['snmpTrap'] = {}
        self.__conf['snmpTrap']['openclos_trap_group'] = {}
        self.__conf['snmpTrap']['openclos_trap_group']['target'] = "1.1.1.1"
        self.__conf['snmpTrap']['openclos_trap_group']['port'] = 20163
        trapReceiver = TrapReceiver(self.__conf)
        self.assertEqual('1.1.1.1', trapReceiver.target)
        self.assertEqual(20163, trapReceiver.port)
    
    def testInitDefaultValue(self):
        self.__conf = {}
        self.__conf['snmpTrap'] = {}
        trapReceiver = TrapReceiver(self.__conf)
        self.assertEqual('0.0.0.0', trapReceiver.target)
        self.assertEqual(20162, trapReceiver.port)
        
    def isPortOpen(self, port):
        cmd = "netstat -an | grep " + str(port)
        result = os.popen(cmd).read()
        if result.find(str(port)) != -1:
            return True
        else:
            return False

    @unittest.skipIf(sys.platform.startswith("win") or os.getenv('TRAVIS') == 'true', "Don't run on Windows or Travis")
    def testStart(self):
        self.__conf = {}
        self.__conf['snmpTrap'] = {}
        self.__conf['snmpTrap']['openclos_trap_group'] = {}
        self.__conf['snmpTrap']['openclos_trap_group']['target'] = "0.0.0.0"
        self.__conf['snmpTrap']['openclos_trap_group']['port'] = 20162
        trapReceiver = TrapReceiver(self.__conf)
        trapReceiver.start()
        sleep(2)
        self.assertEqual(True, self.isPortOpen(20162))
        trapReceiver.stop()
        sleep(2)
        self.assertEqual(False, self.isPortOpen(20162))
        
        
if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()