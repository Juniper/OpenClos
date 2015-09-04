'''
Created on Nov 1, 2014

@author: moloyc
'''

#### ================================================================
#### ================================================================
####                    OpenClos Exceptions
#### ================================================================
#### ================================================================

import error

class BaseError(Exception):
    '''
    Parent class for all OpenClos exceptions
    Workaround to handle exception chaining
    '''

    def __init__(self, errorCode, errorMessage=None, cause=None):
        self.code = errorCode
        self.message = errorMessage
        self.cause = cause

    def __repr__(self):
        return "{0} errorCode: {1}, errorMessage: {2}, cause: {1}".format(
            self.__class__.__name__,
            self.code,
            self.message,
            self.cause)

    __str__ = __repr__

class InvalidConfiguration(BaseError):
    '''
    Description of the error
    '''
    def __init__(self, reason, cause=None):
        super(InvalidConfiguration, self).__init__(error.EC_INVALID_CONFIGURATION,
            error.getErrorMessage(error.EC_INVALID_CONFIGURATION) % (reason), 
            cause)
            
class InvalidRequest(BaseError):
    '''
    Description of the error
    '''
    def __init__(self, reason, cause=None):
        super(InvalidRequest, self).__init__(error.EC_INVALID_REQUEST,
            error.getErrorMessage(error.EC_INVALID_REQUEST) % (reason), 
            cause)
            
class MissingMandatoryAttribute(BaseError):
    '''
    Description of the error
    '''
    def __init__(self, reason, cause=None):
        super(MissingMandatoryAttribute, self).__init__(error.EC_MISSING_MANDATORY_ATTRIBUTE,
            error.getErrorMessage(error.EC_MISSING_MANDATORY_ATTRIBUTE) % (reason), 
            cause)

class InsufficientLoopbackIp(BaseError):
    '''
    Description of the error
    '''
    def __init__(self, reason, cause=None):
        super(InsufficientLoopbackIp, self).__init__(error.EC_INSUFFICIENT_LOOPBACK_IP,
            error.getErrorMessage(error.EC_INSUFFICIENT_LOOPBACK_IP) % (reason), 
            cause)

class InsufficientVlanIp(BaseError):
    '''
    Description of the error
    '''
    def __init__(self, reason, cause=None):
        super(InsufficientVlanIp, self).__init__(error.EC_INSUFFICIENT_VLAN_IP,
            error.getErrorMessage(error.EC_INSUFFICIENT_VLAN_IP) % (reason), 
            cause)

class InsufficientInterconnectIp(BaseError):
    '''
    Description of the error
    '''
    def __init__(self, reason, cause=None):
        super(InsufficientInterconnectIp, self).__init__(error.EC_INSUFFICIENT_INTERCONNECT_IP,
            error.getErrorMessage(error.EC_INSUFFICIENT_INTERCONNECT_IP) % (reason), 
            cause)

class InsufficientManagementIp(BaseError):
    '''
    Description of the error
    '''
    def __init__(self, reason, cause=None):
        super(InsufficientManagementIp, self).__init__(error.EC_INSUFFICIENT_MANAGEMENT_IP,
            error.getErrorMessage(error.EC_INSUFFICIENT_MANAGEMENT_IP) % (reason), 
            cause)

class CapacityCannotChange(BaseError):
    '''
    Description of the error
    '''
    def __init__(self, reason, cause=None):
        super(CapacityCannotChange, self).__init__(error.EC_CAPACITY_CANNOT_CHANGE,
            error.getErrorMessage(error.EC_CAPACITY_CANNOT_CHANGE) % (reason), 
            cause)

class CapacityMismatch(BaseError):
    '''
    Description of the error
    '''
    def __init__(self, reason, cause=None):
        super(CapacityMismatch, self).__init__(error.EC_CAPACITY_MISMATCH,
            error.getErrorMessage(error.EC_CAPACITY_MISMATCH) % (reason), 
            cause)

class EnumerationMismatch(BaseError):
    '''
    Description of the error
    '''
    def __init__(self, reason, cause=None):
        super(EnumerationMismatch, self).__init__(error.EC_ENUMERATION_MISMATCH,
            error.getErrorMessage(error.EC_ENUMERATION_MISMATCH) % (reason), 
            cause)

class InvalidUplinkThreshold(BaseError):
    '''
    Description of the error
    '''
    def __init__(self, reason, cause=None):
        super(InvalidUplinkThreshold, self).__init__(error.EC_INVALID_UPLINK_THRESHOLD,
            error.getErrorMessage(error.EC_INVALID_UPLINK_THRESHOLD) % (reason), 
            cause)

class InvalidIpFormat(BaseError):
    '''
    Description of the error
    '''
    def __init__(self, reason, cause=None):
        super(InvalidIpFormat, self).__init__(error.EC_INVALID_IP_FORMAT,
            error.getErrorMessage(error.EC_INVALID_IP_FORMAT) % (reason), 
            cause)
            
class PodNotFound(BaseError):
    '''
    Description of the error
    '''
    def __init__(self, reason, cause=None):
        super(PodNotFound, self).__init__(error.EC_POD_NOT_FOUND,
            error.getErrorMessage(error.EC_POD_NOT_FOUND) % (reason), 
            cause)

class CablingPlanNotFound(BaseError):
    '''
    Description of the error
    '''
    def __init__(self, reason, cause=None):
        super(CablingPlanNotFound, self).__init__(error.EC_CABLING_PLAN_NOT_FOUND,
            error.getErrorMessage(error.EC_CABLING_PLAN_NOT_FOUND) % (reason), 
            cause)

class DeviceConfigurationNotFound(BaseError):
    '''
    Description of the error
    '''
    def __init__(self, reason, cause=None):
        super(DeviceConfigurationNotFound, self).__init__(error.EC_DEVICE_CONFIGURATION_NOT_FOUND,
            error.getErrorMessage(error.EC_DEVICE_CONFIGURATION_NOT_FOUND) % (reason), 
            cause)

class DeviceNotFound(BaseError):
    '''
    Description of the error
    '''
    def __init__(self, reason, cause=None):
        super(DeviceNotFound, self).__init__(error.EC_DEVICE_NOT_FOUND,
            error.getErrorMessage(error.EC_DEVICE_NOT_FOUND) % (reason), 
            cause)

class ImageNotFound(BaseError):
    '''
    Description of the error
    '''
    def __init__(self, reason, cause=None):
        super(ImageNotFound, self).__init__(error.EC_IMAGE_NOT_FOUND,
            error.getErrorMessage(error.EC_IMAGE_NOT_FOUND) % (reason), 
            cause)

class CreatePodFailed(BaseError):
    '''
    Description of the error
    '''
    def __init__(self, reason, cause=None):
        super(CreatePodFailed, self).__init__(error.EC_CREATE_POD_FAILED,
            error.getErrorMessage(error.EC_CREATE_POD_FAILED) % (reason), 
            cause)

class UpdatePodFailed(BaseError):
    '''
    Description of the error
    '''
    def __init__(self, reason, cause=None):
        super(UpdatePodFailed, self).__init__(error.EC_UPDATE_POD_FAILED,
            error.getErrorMessage(error.EC_UPDATE_POD_FAILED) % (reason), 
            cause)

class DeviceConnectFailed(BaseError):
    '''
    Description of the error
    '''
    def __init__(self, reason, cause=None):
        super(DeviceConnectFailed, self).__init__(error.EC_DEVICE_CONNECT_FAILED,
            error.getErrorMessage(error.EC_DEVICE_CONNECT_FAILED) % (reason), 
            cause)

class DeviceRpcFailed(BaseError):
    '''
    Description of the error
    '''
    def __init__(self, reason, cause=None):
        super(DeviceRpcFailed, self).__init__(error.EC_DEVICE_RPC_FAILED,
            error.getErrorMessage(error.EC_DEVICE_RPC_FAILED) % (reason), 
            cause)

class L2DataCollectionFailed(BaseError):
    '''
    Description of the error
    '''
    def __init__(self, reason, cause=None):
        super(L2DataCollectionFailed, self).__init__(error.EC_L2_DATA_COLLECTION_FAILED,
            error.getErrorMessage(error.EC_L2_DATA_COLLECTION_FAILED) % (reason), 
            cause)

class L3DataCollectionFailed(BaseError):
    '''
    Description of the error
    '''
    def __init__(self, reason, cause=None):
        super(L3DataCollectionFailed, self).__init__(error.EC_L3_DATA_COLLECTION_FAILED,
            error.getErrorMessage(error.EC_L3_DATA_COLLECTION_FAILED) % (reason), 
            cause)

class TwoStageConfigurationFailed(BaseError):
    '''
    Description of the error
    '''
    def __init__(self, reason, cause=None):
        super(TwoStageConfigurationFailed, self).__init__(error.EC_TWO_STAGE_CONFIGURATION_FAILED,
            error.getErrorMessage(error.EC_TWO_STAGE_CONFIGURATION_FAILED) % (reason), 
            cause)

class TrapDaemonError(BaseError):
    '''
    Description of the error
    '''
    def __init__(self, reason, cause=None):
        super(TrapDaemonError, self).__init__(error.EC_TRAP_DAEMON_ERROR,
            error.getErrorMessage(error.EC_TRAP_DAEMON_ERROR) % (reason), 
            cause)

class SkipCommit(BaseError):
    '''
    Dummy error to indicate skip device commit
    '''
    def __init__(self, reason=None, cause=None):
        super(SkipCommit, self).__init__(error.EC_OK, reason, cause)
    
    
