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
EC_INVALID_DEVICE_FAMILY                    = 1012
EC_INVALID_DEVICE_ROLE                      = 1013

# "not found" error at 1100 level 
EC_POD_NOT_FOUND                            = 1100
EC_CABLING_PLAN_NOT_FOUND                   = 1101
EC_DEVICE_CONFIGURATION_NOT_FOUND           = 1102
EC_DEVICE_NOT_FOUND                         = 1103
EC_IMAGE_NOT_FOUND                          = 1104
EC_OVERLAY_FABRIC_NOT_FOUND                 = 1105
EC_OVERLAY_TENANT_NOT_FOUND                 = 1106
EC_OVERLAY_VRF_NOT_FOUND                    = 1107
EC_OVERLAY_DEVICE_NOT_FOUND                 = 1108
EC_OVERLAY_NETWORK_NOT_FOUND                = 1109
EC_OVERLAY_SUBNET_NOT_FOUND                 = 1110
EC_OVERLAY_L3PORT_NOT_FOUND                 = 1111
EC_OVERLAY_L2PORT_NOT_FOUND                 = 1112
EC_OVERLAY_AE_NOT_FOUND                     = 1113

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
EC_CREATE_OVERLAY_FABRIC_FAILED             = 2008
EC_CREATE_OVERLAY_TENANT_FAILED             = 2009
EC_CREATE_OVERLAY_VRF_FAILED                = 2010
EC_CREATE_OVERLAY_DEVICE_FAILED             = 2011
EC_CREATE_OVERLAY_NETWORK_FAILED            = 2012
EC_CREATE_OVERLAY_SUBNET_FAILED             = 2013
EC_CREATE_OVERLAY_L3PORT_FAILED             = 2014
EC_CREATE_OVERLAY_L2PORT_FAILED             = 2015
EC_CREATE_OVERLAY_AE_FAILED                 = 2016
EC_PLATFORM_ERROR                           = 2017
EC_CONFIGURATION_COMMIT_FAILED              = 2018

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
    EC_INVALID_DEVICE_FAMILY                    :   "Invalid device family: %s",
    EC_INVALID_DEVICE_ROLE                      :   "Invalid device role: %s",
    EC_POD_NOT_FOUND                            :   "Pod not found: %s",
    EC_CABLING_PLAN_NOT_FOUND                   :   "Cabling plan not found: %s",
    EC_DEVICE_NOT_FOUND                         :   "Device not found: %s",
    EC_DEVICE_CONFIGURATION_NOT_FOUND           :   "Device configuration not found: %s",
    EC_IMAGE_NOT_FOUND                          :   "Image not found: %s",
    EC_OVERLAY_FABRIC_NOT_FOUND                 :   "Overlay fabric not found: %s", 
    EC_OVERLAY_TENANT_NOT_FOUND                 :   "Overlay tenant not found: %s", 
    EC_OVERLAY_VRF_NOT_FOUND                    :   "Overlay vrf not found: %s", 
    EC_OVERLAY_DEVICE_NOT_FOUND                 :   "Overlay device not found: %s", 
    EC_OVERLAY_NETWORK_NOT_FOUND                :   "Overlay network not found: %s", 
    EC_OVERLAY_SUBNET_NOT_FOUND                 :   "Overlay subnet not found: %s", 
    EC_OVERLAY_L3PORT_NOT_FOUND                 :   "Overlay L3 port not found: %s", 
    EC_OVERLAY_L2PORT_NOT_FOUND                 :   "Overlay L2 port not found: %s", 
    EC_OVERLAY_AE_NOT_FOUND                     :   "Overlay aggregated interface not found: %s", 
    EC_CREATE_POD_FAILED                        :   "Failed to create pod: %s",
    EC_UPDATE_POD_FAILED                        :   "Failed to update pod: %s",
    EC_DEVICE_CONNECT_FAILED                    :   "Failed to connect to device: %s",
    EC_DEVICE_RPC_FAILED                        :   "Failed to execute RPC command on device: %s",
    EC_L2_DATA_COLLECTION_FAILED                :   "Failed to collect L2 data: %s",
    EC_L3_DATA_COLLECTION_FAILED                :   "Failed to collect L3 data: %s",
    EC_TWO_STAGE_CONFIGURATION_FAILED           :   "Failed to execute two stage configuration: %s",
    EC_TRAP_DAEMON_ERROR                        :   "Trap daemon error: %s", 
    EC_CREATE_OVERLAY_FABRIC_FAILED             :   "Failed to create overlay fabric: %s",
    EC_CREATE_OVERLAY_TENANT_FAILED             :   "Failed to create overlay tenant: %s",
    EC_CREATE_OVERLAY_VRF_FAILED                :   "Failed to create overlay vrf: %s",
    EC_CREATE_OVERLAY_DEVICE_FAILED             :   "Failed to create overlay device: %s",
    EC_CREATE_OVERLAY_NETWORK_FAILED            :   "Failed to create overlay network: %s",
    EC_CREATE_OVERLAY_SUBNET_FAILED             :   "Failed to create overlay subnet: %s",
    EC_CREATE_OVERLAY_L3PORT_FAILED             :   "Failed to create overlay L3 port: %s",
    EC_CREATE_OVERLAY_L2PORT_FAILED             :   "Failed to create overlay L2 port: %s",
    EC_CREATE_OVERLAY_AE_FAILED                 :   "Failed to create overlay aggregated interface: %s",
    EC_PLATFORM_ERROR                           :   "Platform error: %s",
    EC_CONFIGURATION_COMMIT_FAILED              :   "Failed to commit configuration: %s",
}

def getErrorMessage(errorCode):
    assert errorCode in dictErrorCode.keys()
    return dictErrorCode[errorCode]
