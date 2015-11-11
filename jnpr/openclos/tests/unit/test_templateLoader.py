'''
Created on Nov 10, 2015

@author: moloyc
'''
import unittest
import os
from jnpr.openclos.templateLoader import TemplateLoader

class TestTemplateLoader(unittest.TestCase):

    def setUp(self):
        self.templateLoader = TemplateLoader()
    def tearDown(self):
        pass

    def testLoadTemplate(self):
        self.assertIsNotNone(self.templateLoader.getTemplate('vlans.txt'))

    def testLoadPropertyOverride(self):
        overridePath = os.path.join(os.path.expanduser('~'), 'vlans.txt')
        with open(overridePath, 'w') as fStream:
            fStream.write('test vlan')
        config = self.templateLoader.getTemplate('vlans.txt').render()
        self.assertEquals('test vlan', config)
        os.remove(overridePath)
