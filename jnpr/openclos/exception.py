'''
Created on Nov 1, 2014

@author: moloyc
'''

#### ================================================================
#### ================================================================
####                    OpenClos Exceptions
#### ================================================================
#### ================================================================


class BaseError(Exception):
    """
    Parent class for all OpenClos exceptions
    Workaround to handle exception chaining
    """

    @property
    def cause(self):
        """ root cause """
        return self.__cause__

    def __init__(self, cause):
        self.__cause__ = cause

    def __repr__(self):
        return "{0} cause: {1}".format(
            self.__class__.__name__,
            self.__cause__)

    __str__ = __repr__

class DeviceError(BaseError):
    """
    Device communication error
    """