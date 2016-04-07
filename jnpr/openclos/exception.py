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
        self.openClosException = True

    def __repr__(self):
        return "{0} errorCode: {1}, errorMessage: {2}, cause: {3}".format(
            self.__class__.__name__,
            self.code,
            self.message,
            self.cause)

    __str__ = __repr__

def isOpenClosException(ex):
    try:
        return ex.openClosException
    except AttributeError as e:
        return False    

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
            
class InvalidDeviceFamily(BaseError):
    '''
    Description of the error
    '''
    def __init__(self, reason, cause=None):
        super(InvalidDeviceFamily, self).__init__(error.EC_INVALID_DEVICE_FAMILY,
            error.getErrorMessage(error.EC_INVALID_DEVICE_FAMILY) % (reason), 
            cause)
            
class InvalidDeviceRole(BaseError):
    '''
    Description of the error
    '''
    def __init__(self, reason, cause=None):
        super(InvalidDeviceRole, self).__init__(error.EC_INVALID_DEVICE_ROLE,
            error.getErrorMessage(error.EC_INVALID_DEVICE_ROLE) % (reason), 
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

class OverlayFabricNotFound(BaseError):
    '''
    Description of the error
    '''
    def __init__(self, reason, cause=None):
        super(OverlayFabricNotFound, self).__init__(error.EC_OVERLAY_FABRIC_NOT_FOUND,
            error.getErrorMessage(error.EC_OVERLAY_FABRIC_NOT_FOUND) % (reason), 
            cause)

class OverlayTenantNotFound(BaseError):
    '''
    Description of the error
    '''
    def __init__(self, reason, cause=None):
        super(OverlayTenantNotFound, self).__init__(error.EC_OVERLAY_TENANT_NOT_FOUND,
            error.getErrorMessage(error.EC_OVERLAY_TENANT_NOT_FOUND) % (reason), 
            cause)

class OverlayVrfNotFound(BaseError):
    '''
    Description of the error
    '''
    def __init__(self, reason, cause=None):
        super(OverlayVrfNotFound, self).__init__(error.EC_OVERLAY_VRF_NOT_FOUND,
            error.getErrorMessage(error.EC_OVERLAY_VRF_NOT_FOUND) % (reason), 
            cause)

class OverlayDeviceNotFound(BaseError):
    '''
    Description of the error
    '''
    def __init__(self, reason, cause=None):
        super(OverlayDeviceNotFound, self).__init__(error.EC_OVERLAY_DEVICE_NOT_FOUND,
            error.getErrorMessage(error.EC_OVERLAY_DEVICE_NOT_FOUND) % (reason), 
            cause)

class OverlayNetworkNotFound(BaseError):
    '''
    Description of the error
    '''
    def __init__(self, reason, cause=None):
        super(OverlayNetworkNotFound, self).__init__(error.EC_OVERLAY_NETWORK_NOT_FOUND,
            error.getErrorMessage(error.EC_OVERLAY_NETWORK_NOT_FOUND) % (reason), 
            cause)

class OverlaySubnetNotFound(BaseError):
    '''
    Description of the error
    '''
    def __init__(self, reason, cause=None):
        super(OverlaySubnetNotFound, self).__init__(error.EC_OVERLAY_SUBNET_NOT_FOUND,
            error.getErrorMessage(error.EC_OVERLAY_SUBNET_NOT_FOUND) % (reason), 
            cause)

class OverlayL3portNotFound(BaseError):
    '''
    Description of the error
    '''
    def __init__(self, reason, cause=None):
        super(OverlayL3portNotFound, self).__init__(error.EC_OVERLAY_L3PORT_NOT_FOUND,
            error.getErrorMessage(error.EC_OVERLAY_L3PORT_NOT_FOUND) % (reason), 
            cause)

class OverlayL2portNotFound(BaseError):
    '''
    Description of the error
    '''
    def __init__(self, reason, cause=None):
        super(OverlayL2portNotFound, self).__init__(error.EC_OVERLAY_L2PORT_NOT_FOUND,
            error.getErrorMessage(error.EC_OVERLAY_L2PORT_NOT_FOUND) % (reason), 
            cause)

class OverlayAggregatedL2portNotFound(BaseError):
    '''
    Description of the error
    '''
    def __init__(self, reason, cause=None):
        super(OverlayAggregatedL2portNotFound, self).__init__(error.EC_OVERLAY_AGGREGATED_L2PORT_NOT_FOUND,
            error.getErrorMessage(error.EC_OVERLAY_AGGREGATED_L2PORT_NOT_FOUND) % (reason), 
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
        
class CreateOverlayFabricFailed(BaseError):
    '''
    Description of the error
    '''
    def __init__(self, reason, cause=None):
        super(CreateOverlayFabricFailed, self).__init__(error.EC_CREATE_OVERLAY_FABRIC_FAILED,
            error.getErrorMessage(error.EC_CREATE_OVERLAY_FABRIC_FAILED) % (reason), 
            cause)

class CreateOverlayTenantFailed(BaseError):
    '''
    Description of the error
    '''
    def __init__(self, reason, cause=None):
        super(CreateOverlayTenantFailed, self).__init__(error.EC_CREATE_OVERLAY_TENANT_FAILED,
            error.getErrorMessage(error.EC_CREATE_OVERLAY_TENANT_FAILED) % (reason), 
            cause)

class CreateOverlayVrfFailed(BaseError):
    '''
    Description of the error
    '''
    def __init__(self, reason, cause=None):
        super(CreateOverlayVrfFailed, self).__init__(error.EC_CREATE_OVERLAY_VRF_FAILED,
            error.getErrorMessage(error.EC_CREATE_OVERLAY_VRF_FAILED) % (reason), 
            cause)

class CreateOverlayDeviceFailed(BaseError):
    '''
    Description of the error
    '''
    def __init__(self, reason, cause=None):
        super(CreateOverlayDeviceFailed, self).__init__(error.EC_CREATE_OVERLAY_DEVICE_FAILED,
            error.getErrorMessage(error.EC_CREATE_OVERLAY_DEVICE_FAILED) % (reason), 
            cause)

class CreateOverlayNetworkFailed(BaseError):
    '''
    Description of the error
    '''
    def __init__(self, reason, cause=None):
        super(CreateOverlayNetworkFailed, self).__init__(error.EC_CREATE_OVERLAY_NETWORK_FAILED,
            error.getErrorMessage(error.EC_CREATE_OVERLAY_NETWORK_FAILED) % (reason), 
            cause)

class CreateOverlaySubnetFailed(BaseError):
    '''
    Description of the error
    '''
    def __init__(self, reason, cause=None):
        super(CreateOverlaySubnetFailed, self).__init__(error.EC_CREATE_OVERLAY_SUBNET_FAILED,
            error.getErrorMessage(error.EC_CREATE_OVERLAY_SUBNET_FAILED) % (reason), 
            cause)

class CreateOverlayL3portFailed(BaseError):
    '''
    Description of the error
    '''
    def __init__(self, reason, cause=None):
        super(CreateOverlayL3portFailed, self).__init__(error.EC_CREATE_OVERLAY_L3PORT_FAILED,
            error.getErrorMessage(error.EC_CREATE_OVERLAY_L3PORT_FAILED) % (reason), 
            cause)

class CreateOverlayL2portFailed(BaseError):
    '''
    Description of the error
    '''
    def __init__(self, reason, cause=None):
        super(CreateOverlayL2portFailed, self).__init__(error.EC_CREATE_OVERLAY_L2PORT_FAILED,
            error.getErrorMessage(error.EC_CREATE_OVERLAY_L2PORT_FAILED) % (reason), 
            cause)

class CreateOverlayAggregatedL2portFailed(BaseError):
    '''
    Description of the error
    '''
    def __init__(self, reason, cause=None):
        super(CreateOverlayAggregatedL2portFailed, self).__init__(error.EC_CREATE_OVERLAY_AGGREGATED_L2PORT_FAILED,
            error.getErrorMessage(error.EC_CREATE_OVERLAY_AGGREGATED_L2PORT_FAILED) % (reason), 
            cause)
            
class PlatformError(BaseError):
    '''
    Description of the error
    '''
    def __init__(self, reason, cause=None):
        super(PlatformError, self).__init__(error.EC_PLATFORM_ERROR,
            error.getErrorMessage(error.EC_PLATFORM_ERROR) % (reason), 
            cause)

class ConfigurationCommitFailed(BaseError):
    '''
    Description of the error
    '''
    def __init__(self, reason, cause=None):
        super(ConfigurationCommitFailed, self).__init__(error.EC_CONFIGURATION_COMMIT_FAILED,
            error.getErrorMessage(error.EC_CONFIGURATION_COMMIT_FAILED) % (reason), 
            cause)
            
