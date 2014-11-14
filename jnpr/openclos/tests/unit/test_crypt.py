'''
Created on Nov. 14, 2014

@author: yunli
'''
import unittest
import os
import sys

from jnpr.openclos.crypt import Cryptic

class TestCryptic(unittest.TestCase):

    def testInitDefaultValue(self):
        cryptic = Cryptic()
        self.assertEqual('Embe1mpls', cryptic.decrypt(cryptic.encrypt('Embe1mpls')))
        
if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()