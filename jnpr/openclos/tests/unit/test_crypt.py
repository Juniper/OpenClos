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
        self.assertEqual('abcd1234', cryptic.decrypt(cryptic.encrypt('abcd1234')))

    def testHashPassword(self):
        cryptic = Cryptic()
        hash_text = cryptic.hashify ('abcd1234')
        self.assertEqual(True, cryptic.authenticate_hash('abcd1234', hash_text))
        hash_text = cryptic.hashify ('Juniper123')
        self.assertEqual(True, cryptic.authenticate_hash('Juniper123', hash_text))
        hash_text = cryptic.hashify ('abcd1234')
        self.assertEqual(False, cryptic.authenticate_hash('Juniper123', hash_text))
        
if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()
