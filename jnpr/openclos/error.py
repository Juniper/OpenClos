#pylint: disable=C0326
'''
Created on May 11, 2015

@author: yunli
'''

#### ================================================================
#### ================================================================
####                    OpenClos Error Code
#### ================================================================
#### ================================================================

EC_OK                                       = 0

# client side 
# validation error at 1000 level
EC_INVALID_CONFIGURATION                    = 1000
EC_INVALID_REQUEST                          = 1001
EC_MISSING_MANDATORY_ATTRIBUTE              = 1002
EC_INSUFFICIENT_LOOPBACK_IP                 = 1003
EC_INSUFFICIENT_VLAN_IP                     = 1004
EC_INSUFFICIENT_INTERCONNECT_IP             = 1005
EC_INSUFFICIENT_MANAGEMENT_IP               = 1006
EC_CAPACITY_CANNOT_CHANGE                   = 1007
EC_CAPACITY_MISMATCH                        = 1008
EC_ENUMERATION_MISMATCH                     = 1009
EC_INVALID_UPLINK_THRESHOLD                 = 1010
EC_INVALID_IP_FORMAT                        = 1011
# "not found" error at 1100 level 
EC_POD_NOT_FOUND                            = 1100
EC_CABLING_PLAN_NOT_FOUND                   = 1101
EC_DEVICE_CONFIGURATION_NOT_FOUND           = 1102
EC_DEVICE_NOT_FOUND                         = 1103
EC_IMAGE_NOT_FOUND                          = 1104

# server side 
# error at 2000 level
EC_CREATE_POD_FAILED                        = 2000
EC_UPDATE_POD_FAILED                        = 2001
EC_DEVICE_CONNECT_FAILED                    = 2002
EC_DEVICE_RPC_FAILED                        = 2003
EC_L2_DATA_COLLECTION_FAILED                = 2004
EC_L3_DATA_COLLECTION_FAILED                = 2005
EC_TWO_STAGE_CONFIGURATION_FAILED           = 2006
EC_TRAP_DAEMON_ERROR                        = 2007

dictErrorCode = {
    EC_OK                                       :   "Success",
    EC_INVALID_CONFIGURATION                    :   "Invalid configuration: %s",
    EC_INVALID_REQUEST                          :   "Invalid request: %s",
    EC_MISSING_MANDATORY_ATTRIBUTE              :   "Missing mandatory attribute: %s",
    EC_INSUFFICIENT_LOOPBACK_IP                 :   "Insufficient loopback ip: %s",
    EC_INSUFFICIENT_VLAN_IP                     :   "Insufficient vlan ip: %s",
    EC_INSUFFICIENT_INTERCONNECT_IP             :   "Insufficient interconnect ip: %s",
    EC_INSUFFICIENT_MANAGEMENT_IP               :   "Insufficient management ip: %s",
    EC_CAPACITY_CANNOT_CHANGE                   :   "Capacity cannot be changed: %s",
    EC_CAPACITY_MISMATCH                        :   "Device count does not match capacity: %s", 
    EC_ENUMERATION_MISMATCH                     :   "Invalid enumeration value: %s",
    EC_INVALID_UPLINK_THRESHOLD                 :   "Invalid uplink threshold: %s",
    EC_INVALID_IP_FORMAT                        :   "Invalid ip format: %s",
    EC_POD_NOT_FOUND                            :   "Pod not found: %s",
    EC_CABLING_PLAN_NOT_FOUND                   :   "Cabling plan not found: %s",
    EC_DEVICE_NOT_FOUND                         :   "Device not found: %s",
    EC_DEVICE_CONFIGURATION_NOT_FOUND           :   "Device configuration not found: %s",
    EC_IMAGE_NOT_FOUND                          :   "Image not found: %s",
    EC_CREATE_POD_FAILED                        :   "Failed to create pod: %s",
    EC_UPDATE_POD_FAILED                        :   "Failed to update pod: %s",
    EC_DEVICE_CONNECT_FAILED                    :   "Failed to connect to device: %s",
    EC_DEVICE_RPC_FAILED                        :   "Failed to execute RPC command on device: %s",
    EC_L2_DATA_COLLECTION_FAILED                :   "Failed to collect L2 data: %s",
    EC_L3_DATA_COLLECTION_FAILED                :   "Failed to collect L3 data: %s",
    EC_TWO_STAGE_CONFIGURATION_FAILED           :   "Failed to execute two stage configuration: %s",
    EC_TRAP_DAEMON_ERROR                        :   "Trap daemon error: %s", 
}

def getErrorMessage(errorCode):
    assert errorCode in dictErrorCode.keys()
    return dictErrorCode[errorCode]
