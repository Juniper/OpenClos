'''
Created on Jan 28, 2015

@author: ubuntu
'''
import unittest


class Test(unittest.TestCase):


    def setUp(self):
        print 'setup()'


    def tearDown(self):
        print 'tearDown()'

    @classmethod
    def setUpClass(self):
        print 'setUpClass()'
    @classmethod
    def tearDownClass(self):
        print 'tearDownClass()'

    def testName1(self):
        pass
    def testName2(self):
        pass
    def testName3(self):
        pass
    def testName4(self):
        pass


if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName1']
    unittest.main()