'''
Created on Nov 12, 2014

@author: moloyc
'''

import threading

class SingletonBase(object):
    __singletonInstance = None
    __singletonLock = threading.Lock() 
    
    @classmethod
    def getInstance(clazz):
        if clazz.__singletonInstance is None:
            with clazz.__singletonLock:
                if clazz.__singletonInstance is None:
                    clazz.__singletonInstance = clazz()
        return clazz.__singletonInstance

    @classmethod
    def _destroy(clazz):
        '''
        Do not use, should be used by unit tests only
        '''
        clazz.__singletonInstance.__del__()
        clazz.__singletonInstance = None
    
    
