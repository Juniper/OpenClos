'''
Created on Apr 16, 2015

@author: moloy
'''
import unittest
import os
import shutil

from jnpr.openclos.propLoader import PropertyLoader, OpenClosProperty

class TestPropertyLoader(unittest.TestCase):

    def setUp(self):
        self.propertyLoader = PropertyLoader()

    def tearDown(self):
        pass

    def testGetFileNameWithPathPwd(self):
        self.assertIsNone(self.propertyLoader.getFileNameWithPath('unknown'))
        open('testFile', 'a')
        self.assertEquals(os.path.join(os.getcwd(), 'testFile'), 
                          self.propertyLoader.getFileNameWithPath('testFile'))
        os.remove('testFile')
        
    def testGetFileNameWithPathConf(self):
        from jnpr.openclos.propLoader import propertyFileLocation
        self.assertEquals(os.path.join(propertyFileLocation, 'openclos.yaml'), 
                          self.propertyLoader.getFileNameWithPath('openclos.yaml'))
        self.assertEquals(os.path.join(propertyFileLocation, 'deviceFamily.yaml'), 
                          self.propertyLoader.getFileNameWithPath('deviceFamily.yaml'))


class TestOpenClosProperty(unittest.TestCase):

    def setUp(self):
        self.openClosProperty = OpenClosProperty()

    def tearDown(self):
        pass

    def testFixSqlliteDbUrlForRelativePath(self):
        import jnpr.openclos.util
        dbUrl = self.openClosProperty.fixSqlliteDbUrlForRelativePath('sqlite:////absolute-path/sqllite3.db')
        self.assertEqual(5, dbUrl.count('/'))
        dbUrl = self.openClosProperty.fixSqlliteDbUrlForRelativePath('sqlite:///relative-path/sqllite3.db')
        if jnpr.openclos.util.isPlatformWindows():
            self.assertTrue("C:\\" in dbUrl)
        else:
            self.assertTrue(dbUrl.count('/') > 4)
            
    def testLoadDefaultConfig(self):
        self.assertIsNotNone(self.openClosProperty.getProperties())

    def testGetDbUrl(self):
        self.assertTrue('sqlite:' in self.openClosProperty.getDbUrl())


if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()