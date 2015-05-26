'''
Created on May 11, 2015

@author: yunli
'''

#### ================================================================
#### ================================================================
####                    OpenClos Error Code
#### ================================================================
#### ================================================================

EC_INVALID_CONFIGURATION                = 1
EC_INVALID_REQUEST                      = 2
EC_VALIDATION_ERROR                     = 3
EC_POD_NOT_FOUND                        = 4
EC_CABLING_PLAN_NOT_FOUND               = 5
EC_CONFIGURATION_NOT_FOUND              = 6
EC_DEVICE_NOT_FOUND                     = 7
EC_IMAGE_NOT_FOUND                      = 8
EC_CREATE_POD_FAILED                    = 9
EC_UPDATE_POD_FAILED                    = 10
EC_DEVICE_CONNECT_FAILED                = 11
EC_DEVICE_RPC_FAILED                    = 12
EC_L2_DATA_COLLECTION_FAILED            = 13
EC_L3_DATA_COLLECTION_FAILED            = 14
EC_TWO_STAGE_CONFIGURATION_FAILED       = 15
EC_TRAP_DAEMON_ERROR                    = 16

dictErrorCode = {
    EC_INVALID_CONFIGURATION:           "Invalid configuration: %s",
    EC_INVALID_REQUEST:                 "Invalid request: %s",
    EC_VALIDATION_ERROR:                "Validation error: %s",
    EC_POD_NOT_FOUND:                   "Pod not found: %s",
    EC_CABLING_PLAN_NOT_FOUND:          "Cabling plan not found: %s",
    EC_CONFIGURATION_NOT_FOUND:         "Configuration not found: %s",
    EC_DEVICE_NOT_FOUND:                "Device not found: %s",
    EC_IMAGE_NOT_FOUND:                 "Image not found: %s",
    EC_CREATE_POD_FAILED:               "Failed to create pod: %s",
    EC_UPDATE_POD_FAILED:               "Failed to update pod: %s",
    EC_DEVICE_CONNECT_FAILED:           "Failed to connect to device: %s",
    EC_DEVICE_RPC_FAILED:               "Failed to execute RPC command on device: %s",
    EC_L2_DATA_COLLECTION_FAILED:       "Failed to collect L2 data: %s",
    EC_L3_DATA_COLLECTION_FAILED:       "Failed to collect L3 data: %s",
    EC_TWO_STAGE_CONFIGURATION_FAILED:  "Failed to execute two stage configuration: %s",
    EC_TRAP_DAEMON_ERROR:               "Trap daemon error: %s", 
}

def getErrorMessage(errorCode):
    assert errorCode in dictErrorCode.keys()
    return dictErrorCode[errorCode]
