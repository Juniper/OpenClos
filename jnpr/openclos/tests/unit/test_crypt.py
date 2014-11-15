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

    def testHashPassword(self):
        cryptic = Cryptic()
        hash_text = cryptic.hashify ('Embe1mpls')
        self.assertEqual(0, cryptic.authenticate_hash('Embe1mpls', hash_text))
        
if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()
