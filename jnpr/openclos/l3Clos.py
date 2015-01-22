'''
Created on May 23, 2014

@author: moloyc
'''

import yaml
import os
import json
import math
import zlib
import base64

from netaddr import IPNetwork
from sqlalchemy.orm import exc

from model import Pod, Device, InterfaceLogical, InterfaceDefinition, CablingPlan, DeviceConfig
from dao import Dao
import util
from writer import ConfigWriter, CablingPlanWriter
from jinja2 import Environment, PackageLoader
import logging

junosTemplateLocation = os.path.join('conf', 'junosTemplates')

moduleName = 'l3Clos'
logger = None

class L3ClosMediation():
    def __init__(self, conf = {}, dao = None):
        global logger
        if any(conf) == False:
            self.conf = util.loadConfig(appName = moduleName)
        else:
            self.conf = conf

        logger = logging.getLogger(moduleName)
        if dao is None:
            self.dao = Dao(self.conf)
        else:
            self.dao = dao

        self.templateEnv = Environment(loader=PackageLoader('jnpr.openclos', junosTemplateLocation))
        self.templateEnv.keep_trailing_newline = True
        self.isZtpStaged = util.isZtpStaged(self.conf)
        
    def loadClosDefinition(self, closDefination = os.path.join(util.configLocation, 'closTemplate.yaml')):
        '''
        Loads clos definition from yaml file and creates pod object
        '''
        try:
            stream = open(closDefination, 'r')
            yamlStream = yaml.load(stream)
            
            return yamlStream['pods']
        except (OSError, IOError) as e:
            print "File error:", e
        except (yaml.scanner.ScannerError) as e:
            print "YAML error:", e
            stream.close()
        finally:
            pass
       
    def createPod(self, podName, podDict, inventoryDict = None):
        '''
        Create a new POD
        '''
        pod = Pod(podName, podDict)
        pod.validate()
        self.dao.createObjects([pod])
        logger.info("Pod[id='%s', name='%s']: created" % (pod.id, podName)) 

        # shortcut for updating in createPod
        # this use case is typical in script invocation but not in ND REST invocation
        self.updatePodData(pod, podDict, inventoryDict)
        
        return pod

    def createSpineIfds(self, pod, spines):
        devices = []
        interfaces = []
        for spine in spines:
            username = spine.get('username')    #default is 'root' set on DB
            password = spine.get('password')
            macAddress = spine.get('macAddress')
            deployStatus = spine.get('deployStatus')    #default is 'provision' set on DB
            device = Device(spine['name'], pod.spineDeviceType, username, password, 'spine', macAddress, None, pod, deployStatus)
            devices.append(device)
            
            portNames = util.getPortNamesForDeviceFamily(device.family, self.conf['deviceFamily'])
            for name in portNames['ports']:     # spine does not have any uplink/downlink marked, it is just ports
                ifd = InterfaceDefinition(name, device, 'downlink')
                interfaces.append(ifd)
        self.dao.createObjects(devices)
        self.dao.createObjects(interfaces)
        
    def createLeafIfds(self, pod, leaves):
        devices = []
        interfaces = []
        for leaf in leaves:
            username = leaf.get('username')
            password = leaf.get('password') #default is Pod level pass, set on constructor
            macAddress = leaf.get('macAddress')
            family = leaf.get('family') #default is 'unknown' set on DB
            deployStatus = leaf.get('deployStatus') #default is 'provision' set on DB
            device = Device(leaf['name'], family, username, password, 'leaf', macAddress, None, pod, deployStatus)
            devices.append(device)
            
            if family is None or family == 'unknown':
                # temporary uplink ports, names will get fixed after 2-stage ztp
                for i in xrange(0, pod.spineCount):
                    interfaces.append(InterfaceDefinition('uplink-' + str(i), device, 'uplink'))

            else:
                portNames = util.getPortNamesForDeviceFamily(device.family, self.conf['deviceFamily'])
                interfaceCount = 0
                for name in portNames['uplinkPorts']:   # all uplink IFDs towards spine
                    interfaces.append(InterfaceDefinition(name, device, 'uplink'))
                    interfaceCount += 1
                
                # Hack plugNPlay-mixedLeaf: Create additional uplinks when spine count is more than available uplink ports
                # example: spine count=5, device=ex4300-24p
                while interfaceCount < pod.spineCount:
                    interfaces.append(InterfaceDefinition('uplink-' + str(interfaceCount), device, 'uplink'))
                    interfaceCount += 1
                
                
                # leaf access/downlink ports are not used in app so far, no need to create them    
                #for name in portNames['downlinkPorts']:   # all downlink IFDs towards Access/Server
                #    interfaces.append(InterfaceDefinition(name, device, 'downlink'))
        
        self.dao.createObjects(devices)
        self.dao.createObjects(interfaces)
    
    def deployInventory(self, pod, inventory, role):
        for inv in inventory:
            for device in pod.devices:
                # find match by role/id/name
                if device.role == role and (device.id == inv.get('id') or device.name == inv['name']):
                    if device.deployStatus == inv.get('deployStatus'):
                        logger.debug("Pod[id='%s', name='%s']: %s device '%s' unchanged" % (pod.id, pod.name, device.role, device.name))
                    elif device.deployStatus == 'deploy' and inv.get('deployStatus') is None:
                        logger.debug("Pod[id='%s', name='%s']: %s device '%s' provisioned" % (pod.id, pod.name, device.role, device.name))
                        device.update(inv['name'], inv.get('username'), inv.get('password'), inv.get('macAddress'), inv.get('deployStatus', 'provision'))
                    elif device.deployStatus == 'provision' and inv.get('deployStatus') == 'deploy':
                        logger.debug("Pod[id='%s', name='%s']: %s device '%s' deployed" % (pod.id, pod.name, device.role, device.name))
                        device.update(inv['name'], inv.get('username'), inv.get('password'), inv.get('macAddress'), inv.get('deployStatus'))
                       
    def resolveInventory(self, podDict, inventoryDict):
        if podDict is None:
            raise ValueError("podDict cannot be None")
            
        # typical use case for ND REST invocation is to provide an non-empty inventoryDict
        # typical use case for script invocation is to provide an non-empty podDict['inventory']
        inventoryData = None
        if inventoryDict is not None:
            inventoryData = inventoryDict
        elif 'inventory' in podDict and podDict['inventory'] is not None:
            json_inventory = open(os.path.join(util.configLocation, podDict['inventory']))
            inventoryData = json.load(json_inventory)
            json_inventory.close()

        return inventoryData

    def validateAttribute(self, pod, attr, dct):
        if dct.get(attr) is None:
            raise ValueError("Pod[id='%s', name='%s']: device '%s' attribute '%s' cannot be None" % (pod.id, pod.name, dct.get('name'), attr))
    
    def validateLoopbackPrefix(self, pod, podDict, inventoryData):
        inventoryDeviceCount = len(inventoryData['spines']) + len(inventoryData['leafs'])
        lo0Block = IPNetwork(podDict['loopbackPrefix'])
        lo0Ips = list(lo0Block.iter_hosts())
        availableIps = len(lo0Ips)
        if availableIps < inventoryDeviceCount:
            raise ValueError("Pod[id='%s', name='%s']: loopbackPrefix available IPs %d not enough: required %d" % (pod.id, pod.name, availableIps, inventoryDeviceCount))

    def validateVlanPrefix(self, pod, podDict, inventoryData):
        vlanBlock = IPNetwork(podDict['vlanPrefix'])
        numOfHostIpsPerSwitch = podDict['hostOrVmCountPerLeaf']
        numOfSubnets = len(inventoryData['leafs'])
        numOfIps = (numOfSubnets * (numOfHostIpsPerSwitch + 2)) # +2 for network and broadcast
        numOfBits = int(math.ceil(math.log(numOfIps, 2))) 
        cidr = 32 - numOfBits
        if vlanBlock.prefixlen > cidr:
            raise ValueError("Pod[id='%s', name='%s']: vlanPrefix avaiable block /%d not enough: required /%d" % (pod.id, pod.name, vlanBlock.prefixlen, cidr))
    
    def validateInterConnectPrefix(self, pod, podDict, inventoryData):
        interConnectBlock = IPNetwork(podDict['interConnectPrefix'])
        numOfIpsPerInterconnect = 2
        numOfSubnets = len(inventoryData['spines']) * len(inventoryData['leafs'])
        # no need to add +2 for network and broadcast, as junos supports /31
        # TODO: it should be configurable and come from property file
        bitsPerSubnet = int(math.ceil(math.log(numOfIpsPerInterconnect, 2)))    # value is 1  
        cidrForEachSubnet = 32 - bitsPerSubnet  # value is 31 as junos supports /31

        numOfIps = (numOfSubnets * (numOfIpsPerInterconnect)) # no need to add +2 for network and broadcast
        numOfBits = int(math.ceil(math.log(numOfIps, 2))) 
        cidr = 32 - numOfBits
        if interConnectBlock.prefixlen > cidr:
            raise ValueError("Pod[id='%s', name='%s']: interConnectPrefix avaiable block /%d not enough: required /%d" % (pod.id, pod.name, interConnectBlock.prefixlen, cidr))
    
    def validateManagementPrefix(self, pod, podDict, inventoryData):
        inventoryDeviceCount = len(inventoryData['spines']) + len(inventoryData['leafs'])
        managementIps = util.getMgmtIps(podDict.get('managementPrefix'), podDict.get('managementStartingIP'), podDict.get('managementMask'), inventoryDeviceCount)
        availableIps = len(managementIps)
        if availableIps < inventoryDeviceCount:
            raise ValueError("Pod[id='%s', name='%s']: managementPrefix avaiable IPs %d not enough: required %d" % (pod.id, pod.name, availableIps, inventoryDeviceCount))
    
    def validatePod(self, pod, podDict, inventoryData):
        if inventoryData is None:
            raise ValueError("Pod[id='%s', name='%s']: inventory cannot be empty" % (pod.id, pod.name))
        
        # if following data changed we need to reallocate resource
        if pod.spineCount != podDict['spineCount'] or pod.leafCount != podDict['leafCount']:
            raise ValueError("Pod[id='%s', name='%s']: capacity cannot be changed" % (pod.id, pod.name))

        for spine in inventoryData['spines']:
            self.validateAttribute(pod, 'name', spine)
            #self.validateAttribute(pod, 'role', spine)
            #self.validateAttribute(pod, 'family', spine)
            #self.validateAttribute(pod, 'deployStatus', spine)
            
        for leaf in inventoryData['leafs']:
            self.validateAttribute(pod, 'name', leaf)
            #self.validateAttribute(pod, 'role', leaf)
            #self.validateAttribute(pod, 'family', leaf)
            #self.validateAttribute(pod, 'deployStatus', leaf)
                
        # inventory should contain exact same number of devices as capacity
        expectedDeviceCount = int(podDict['spineCount']) + int(podDict['leafCount'])
        inventoryDeviceCount = len(inventoryData['spines']) + len(inventoryData['leafs'])
        if expectedDeviceCount != inventoryDeviceCount:
            raise ValueError("Pod[id='%s', name='%s']: inventory device count %d does not match capacity %d" % (pod.id, pod.name, inventoryDeviceCount, expectedDeviceCount))

        # validate loopbackPrefix is big enough
        self.validateLoopbackPrefix(pod, podDict, inventoryData)

        # validate vlanPrefix is big enough
        self.validateVlanPrefix(pod, podDict, inventoryData)
        
        # validate interConnectPrefix is big enough
        self.validateInterConnectPrefix(pod, podDict, inventoryData)
        
        # validate managementPrefix is big enough
        self.validateManagementPrefix(pod, podDict, inventoryData)
                
        
    def diffInventory(self, pod, inventoryData):
        # Compare new inventory that user provides against old inventory that we stored in the database.
        inventoryChanged = True
        
        # user provides an inventory. now check the inventory we already have in database
        if pod.inventoryData is not None:
            # restored to cleartext JSON format
            inventoryDataInDb = json.loads(zlib.decompress(base64.b64decode(pod.inventoryData)))
            if inventoryData == inventoryDataInDb:
                inventoryChanged = False
            
        if inventoryChanged == True:
            logger.debug("Pod[id='%s', name='%s']: inventory changed" % (pod.id, pod.name))
            # save the new inventory to database
            pod.inventoryData = base64.b64encode(zlib.compress(json.dumps(inventoryData)))

            # deploy the new devices and undeploy deleted devices
            self.deployInventory(pod, inventoryData['spines'], 'spine')
            self.deployInventory(pod, inventoryData['leafs'], 'leaf')
        else:
            logger.debug("Pod[id='%s', name='%s']: inventory not changed" % (pod.id, pod.name))

    def needToRebuild(self, pod, podDict):
        if pod.spineDeviceType != podDict.get('spineDeviceType') or \
           pod.spineCount != podDict.get('spineCount') or \
           pod.leafCount != podDict.get('leafCount') or \
           pod.interConnectPrefix != podDict.get('interConnectPrefix') or \
           pod.vlanPrefix != podDict.get('vlanPrefix') or \
           pod.loopbackPrefix != podDict.get('loopbackPrefix') or \
           pod.managementPrefix != podDict.get('managementPrefix'):
            return True
        else:
            return False
            
    def updatePodData(self, pod, podDict, inventoryDict):
        # inventory can come from either podDict or inventoryDict
        inventoryData = self.resolveInventory(podDict, inventoryDict)
        
        # check inventory contains correct number of devices
        self.validatePod(pod, podDict, inventoryData)
        
        # if following data changed we need to reallocate resource
        if self.needToRebuild(pod, podDict) == True:
            logger.debug("Pod[id='%s', name='%s']: rebuilding required" % (pod.id, pod.name))
            if len(pod.devices) > 0:
                self.dao.deleteObjects(pod.devices)

        # first time
        if len(pod.devices) == 0:
            logger.debug("Pod[id='%s', name='%s']: building inventory and resource..." % (pod.id, pod.name))
            self.createSpineIfds(pod, inventoryData['spines'])
            self.createLeafIfds(pod, inventoryData['leafs'])
            self.createLinkBetweenIfds(pod)
            self.allocateResource(pod)
        else:        
            # compare new inventory that user provides against old inventory that we stored in the database
            self.diffInventory(pod, inventoryData)
                
        # update pod itself
        pod.update(pod.id, pod.name, podDict)
        self.dao.updateObjects([pod])
            
        # TODO move the backup operation to CLI 
        # backup current database
        util.backupDatabase(self.conf)

    def updatePod(self, podId, podDict, inventoryDict = None):
        '''
        Modify an existing POD. As a sanity check, if we don't find the POD
        by UUID, a ValueException is thrown
        '''
        if podId is not None: 
            try:
                pod = self.dao.getObjectById(Pod, podId)
            except (exc.NoResultFound):
                raise ValueError("Pod[id='%s']: not found" % (podId)) 
            else:
                # update other fields
                self.updatePodData(pod, podDict, inventoryDict)
                logger.info("Pod[id='%s', name='%s']: updated" % (pod.id, pod.name)) 
        else:
            raise ValueError("Pod id cannot be None")
            
        return pod
    
    def deletePod(self, podId):
        '''
        Delete an existing POD. As a sanity check, if we don't find the POD
        by UUID, a ValueException is thrown
        '''
        if podId is not None: 
            try:
                pod = self.dao.getObjectById(Pod, podId)
            except (exc.NoResultFound):
                raise ValueError("Pod[id='%s']: not found" % (podId)) 
            else:
                logger.info("Pod[id='%s', name='%s']: deleted" % (pod.id, pod.name)) 
                self.dao.deleteObject(pod)
        else:
            raise ValueError("Pod id cannot be None")

    def createCablingPlan(self, podId):
        '''
        Finds Pod object by id and create cabling plan
        It also creates the output folders for pod
        '''
        if podId is not None: 
            try:
                pod = self.dao.getObjectById(Pod, podId)
            except (exc.NoResultFound):
                raise ValueError("Pod[id='%s']: not found" % (podId)) 
 
            if len(pod.devices) > 0:
                cablingPlanWriter = CablingPlanWriter(self.conf, pod, self.dao)
                # create cabling plan in JSON format
                cablingPlanJson = cablingPlanWriter.writeJSON()
                pod.cablingPlan = CablingPlan(pod.id, cablingPlanJson)
                # create cabling plan in DOT format
                cablingPlanWriter.writeDOT()
                self.dao.updateObjects([pod])
                
                return True
            else:
                raise ValueError("Pod[id='%s', name='%s']: inventory is empty" % (pod.id, pod.name)) 
            
        else:
            raise ValueError("Pod id cannot be None") 
            
    def createDeviceConfig(self, podId):
        '''
        Finds Pod object by id and create device configurations
        It also creates the output folders for pod
        '''
        if podId is not None:
            try:
                pod = self.dao.getObjectById(Pod, podId)
            except (exc.NoResultFound):
                raise ValueError("Pod[id='%s']: not found" % (podId)) 
 
            if len(pod.devices) > 0:
                # create configuration
                self.generateConfig(pod)
        
                return True
            else:
                raise ValueError("Pod[id='%s', name='%s']: inventory is empty" % (pod.id, pod.name)) 
        else:
            raise ValueError("Pod id cannot be None") 

    def createLinkBetweenIfds(self, pod):
        leaves = []
        spines = []
        for device in pod.devices:
            if (device.role == 'leaf'):
                leafUplinkPorts = self.dao.Session().query(InterfaceDefinition).filter(InterfaceDefinition.device_id == device.id).filter(InterfaceDefinition.role == 'uplink').order_by(InterfaceDefinition.sequenceNum).all()
                leaves.append({'leaf': device, 'leafUplinkPorts': leafUplinkPorts})
            elif (device.role == 'spine'):
                spinePorts = self.dao.Session().query(InterfaceDefinition).filter(InterfaceDefinition.device_id == device.id).order_by(InterfaceDefinition.sequenceNum).all()
                spines.append({'spine': device, 'ports': spinePorts})
        
        leafIndex = 0
        spineIndex = 0
        modifiedObjects = []
        for leaf in leaves:
            for spine in spines:
                spinePort = spine['ports'][spineIndex]
                leafPort = leaf['leafUplinkPorts'][leafIndex]
                spinePort.peer = leafPort
                leafPort.peer = spinePort
                modifiedObjects.append(spinePort)
                modifiedObjects.append(leafPort)
                leafIndex += 1
            leafIndex = 0
            spineIndex += 1
        self.dao.updateObjects(modifiedObjects)
        
    def getLeafSpineFromPod(self, pod):
        '''
        utility method to get list of spines and leafs of a pod
        returns dict with list for 'spines' and 'leafs'
        '''
        deviceDict = {}
        deviceDict['leafs'] = []
        deviceDict['spines'] = []
        for device in pod.devices:
            if (device.role == 'leaf'):
                deviceDict['leafs'].append(device)
            elif (device.role == 'spine'):
                deviceDict['spines'].append(device)
        return deviceDict
    
    def allocateResource(self, pod):
        self.allocateLoopback(pod, pod.loopbackPrefix, pod.devices)
        leafSpineDict = self.getLeafSpineFromPod(pod)
        self.allocateIrb(pod, pod.vlanPrefix, leafSpineDict['leafs'])
        self.allocateInterconnect(pod.interConnectPrefix, leafSpineDict['spines'], leafSpineDict['leafs'])
        self.allocateAsNumber(pod.spineAS, pod.leafAS, leafSpineDict['spines'], leafSpineDict['leafs'])
        self.allocateManagement(pod.managementPrefix, pod.managementStartingIP, pod.managementMask, leafSpineDict['spines'], leafSpineDict['leafs'])
        
    def allocateManagement(self, managementPrefix, managementStartingIP, managementMask, spines, leaves):
        deviceCount = len(spines)+len(leaves)
        managementIps = util.getMgmtIps(managementPrefix, managementStartingIP, managementMask, deviceCount)
        # don't do partial allocation
        if len(managementIps) == deviceCount:
            for spine, managementIp in zip(spines, managementIps[:len(spines)]):
                spine.managementIp = managementIp
            self.dao.updateObjects(spines)
            
            # for 2stage and leaf, don' fill in management ip
            if self.isZtpStaged == False:
                for leaf, managementIp in zip(leaves, managementIps[len(spines):]):
                    leaf.managementIp = managementIp
                self.dao.updateObjects(leaves)
        
    def allocateLoopback(self, pod, loopbackPrefix, devices):
        loopbackIp = IPNetwork(loopbackPrefix).network
        numOfIps = len(devices) + 2 # +2 for network and broadcast
        numOfBits = int(math.ceil(math.log(numOfIps, 2))) 
        cidr = 32 - numOfBits
        lo0Block = IPNetwork(str(loopbackIp) + "/" + str(cidr))
        lo0Ips = list(lo0Block.iter_hosts())
        
        interfaces = []
        pod.allocatedLoopbackBlock = str(lo0Block.cidr)
        for device in devices:
            ifl = InterfaceLogical('lo0.0', device, str(lo0Ips.pop(0)) + '/32')
            interfaces.append(ifl)
        self.dao.createObjects(interfaces)

    def allocateIrb(self, pod, irbPrefix, leafs):
        irbIp = IPNetwork(irbPrefix).network
        numOfHostIpsPerSwitch = pod.hostOrVmCountPerLeaf
        numOfSubnets = len(leafs)
        bitsPerSubnet = int(math.ceil(math.log(numOfHostIpsPerSwitch + 2, 2)))  # +2 for network and broadcast
        cidrForEachSubnet = 32 - bitsPerSubnet

        numOfIps = (numOfSubnets * (2 ** bitsPerSubnet))
        numOfBits = int(math.ceil(math.log(numOfIps, 2))) 
        cidr = 32 - numOfBits
        irbBlock = IPNetwork(str(irbIp) + "/" + str(cidr))
        irbSubnets = list(irbBlock.subnet(cidrForEachSubnet))
        
        interfaces = [] 
        pod.allocatedIrbBlock = str(irbBlock.cidr)
        for leaf in leafs:
            ipAddress = list(irbSubnets.pop(0).iter_hosts())[0]
            # TODO: would be better to get irb.1 from property file as .1 is VLAN ID
            ifl = InterfaceLogical('irb.1', leaf, str(ipAddress) + '/' + str(cidrForEachSubnet)) 
            interfaces.append(ifl)
        self.dao.createObjects(interfaces)

    def allocateInterconnect(self, interConnectPrefix, spines, leafs):
        interConnectIp = IPNetwork(interConnectPrefix).network
        numOfIpsPerInterconnect = 2
        numOfSubnets = len(spines) * len(leafs)
        # no need to add +2 for network and broadcast, as junos supports /31
        # TODO: it should be configurable and come from property file
        bitsPerSubnet = int(math.ceil(math.log(numOfIpsPerInterconnect, 2)))    # value is 1  
        cidrForEachSubnet = 32 - bitsPerSubnet  # value is 31 as junos supports /31

        numOfIps = (numOfSubnets * (numOfIpsPerInterconnect)) # no need to add +2 for network and broadcast
        numOfBits = int(math.ceil(math.log(numOfIps, 2))) 
        cidr = 32 - numOfBits
        interconnectBlock = IPNetwork(str(interConnectIp) + "/" + str(cidr))
        interconnectSubnets = list(interconnectBlock.subnet(cidrForEachSubnet))

        interfaces = [] 
        spines[0].pod.allocatedInterConnectBlock = str(interconnectBlock.cidr)

        for spine in spines:
            ifdsHasPeer = self.dao.Session().query(InterfaceDefinition).filter(InterfaceDefinition.device_id == spine.id).filter(InterfaceDefinition.peer != None).order_by(InterfaceDefinition.sequenceNum).all()
            for spineIfdHasPeer in ifdsHasPeer:
                subnet =  interconnectSubnets.pop(0)
                ips = list(subnet)
                
                spineEndIfl= InterfaceLogical(spineIfdHasPeer.name + '.0', spine, str(ips.pop(0)) + '/' + str(cidrForEachSubnet))
                spineIfdHasPeer.layerAboves.append(spineEndIfl)
                interfaces.append(spineEndIfl)
                
                leafEndIfd = spineIfdHasPeer.peer
                leafEndIfl= InterfaceLogical(leafEndIfd.name + '.0', leafEndIfd.device, str(ips.pop(0)) + '/' + str(cidrForEachSubnet))
                leafEndIfd.layerAboves.append(leafEndIfl)
                interfaces.append(leafEndIfl)
        self.dao.createObjects(interfaces)

    def allocateAsNumber(self, spineAsn, leafAsn, spines, leafs):
        devices = []
        for spine in spines:
            spine.asn = spineAsn
            spineAsn += 1
            devices.append(spine)
        spines[0].pod.allocatedSpineAS = spineAsn - 1
        
        for leaf in leafs:
            leaf.asn = leafAsn
            leafAsn += 1
            devices.append(leaf)
        leafs[0].pod.allocatefLeafAS = leafAsn - 1

        self.dao.updateObjects(devices)
        
    def generateConfig(self, pod):
        configWriter = ConfigWriter(self.conf, pod, self.dao)
        modifiedObjects = []
        
        for device in pod.devices:
            if device.role == 'leaf' and (self.isZtpStaged or device.family == 'unknown'):
                # leaf configs will get created when they are plugged in after 2Stage ztp
                continue
            
            config = self.createBaseConfig(device)
            config += self.createInterfaces(device)
            config += self.createRoutingOptionsStatic(device)
            config += self.createRoutingOptionsBgp(device)
            config += self.createProtocolBgp(device)
            config += self.createProtocolLldp(device)
            config += self.createPolicyOption(device)
            config += self.createSnmpTrapAndEvent(device)
            config += self.createVlan(device)
            device.config = DeviceConfig(device.id, config)
            modifiedObjects.append(device)
            logger.debug('Generated config for device name: %s, id: %s, storing in DB' % (device.name, device.id))
            configWriter.write(device)

        if self.isZtpStaged:
            pod.leafSettings = self.createLeafGenericConfigsFor2Stage(pod)
            modifiedObjects.append(pod)
            logger.debug('Generated %d leaf generic configs for pod: %s, storing in DB' % (len(pod.leafSettings), pod.name))
            configWriter.writeGenericLeaf(pod)
        
        self.dao.updateObjects(modifiedObjects)

    def createBaseConfig(self, device):
        baseTemplate = self.templateEnv.get_template('baseTemplate.txt')
        return baseTemplate.render(hostName=device.name, hashedPassword=device.getHashPassword())

    def createInterfaces(self, device): 
        interfaceStanza = self.templateEnv.get_template('interface_stanza.txt')
        lo0Stanza = self.templateEnv.get_template('lo0_stanza.txt')
        mgmtStanza = self.templateEnv.get_template('mgmt_interface.txt')
        rviStanza = self.templateEnv.get_template('rvi_stanza.txt')
            
        config = "interfaces {" + "\n" 
        # management interface
        config += mgmtStanza.render(mgmt_address=device.managementIp)
                
        #loopback interface
        loopbackIfl = self.dao.Session.query(InterfaceLogical).join(Device).filter(Device.id == device.id).filter(InterfaceLogical.name == 'lo0.0').one()
        config += lo0Stanza.render(address=loopbackIfl.ipaddress)
        
        # For Leaf add IRB and server facing interfaces        
        if device.role == 'leaf':
            irbIfl = self.dao.Session.query(InterfaceLogical).join(Device).filter(Device.id == device.id).filter(InterfaceLogical.name == 'irb.1').one()
            config += rviStanza.render(address=irbIfl.ipaddress)
            config += self.createAccessPortInterfaces(device.family)

        # Interconnect interfaces
        deviceInterconnectIfds = self.dao.getConnectedInterconnectIFDsFilterFakeOnes(device)
        for interconnectIfd in deviceInterconnectIfds:
            peerDevice = interconnectIfd.peer.device
            interconnectIfl = interconnectIfd.layerAboves[0]
            namePlusUnit = interconnectIfl.name.split('.')  # example et-0/0/0.0
            config += interfaceStanza.render(ifd_name=namePlusUnit[0],
                                             unit=namePlusUnit[1],
                                             description="facing_" + peerDevice.name,
                                             address=interconnectIfl.ipaddress)
                
        config += "}\n"
        return config

    def createAccessPortInterfaces(self, deviceFamily):
        accessInterface = self.templateEnv.get_template('accessInterface.txt')
        ifdNames = []

        for ifdName in util.getPortNamesForDeviceFamily(deviceFamily, self.conf['deviceFamily'])['downlinkPorts']:
            ifdNames.append(ifdName)

        return accessInterface.render(ifdNames=ifdNames)

    def getParamsForOutOfBandNetwork(self, pod):
        '''
        add all trap-target to the OOB list
        '''
        oobList = util.getSnmpTrapTargets(self.conf)
        gateway = None
        
        oobNetworks = pod.outOfBandAddressList
        if oobNetworks is not None and len(oobNetworks) > 0:
            oobList += oobNetworks.split(',')

            gateway = pod.outOfBandGateway
            if gateway is None:
                gateway = util.loadClosDefinition()['ztp']['dhcpOptionRoute']
       
        oobList = set(oobList)
        if len(oobList) > 0:
            return {'networks': oobList, 'gateway': gateway}
        else:
            return {}
    
    def createRoutingOptionsStatic(self, device):
        routingOptions = self.templateEnv.get_template('routingOptionsStatic.txt')
        return routingOptions.render(oob = self.getParamsForOutOfBandNetwork(device.pod))

    def createRoutingOptionsBgp(self, device):
        routingOptions = self.templateEnv.get_template('routingOptionsBgp.txt')

        loopbackIfl = self.dao.Session.query(InterfaceLogical).join(Device).filter(Device.id == device.id).filter(InterfaceLogical.name == 'lo0.0').one()
        loopbackIpWithNoCidr = loopbackIfl.ipaddress.split('/')[0]
        
        return routingOptions.render(routerId=loopbackIpWithNoCidr, asn=str(device.asn))

    def createProtocolBgp(self, device):
        template = self.templateEnv.get_template('protocolBgp.txt')

        neighborList = []
        deviceInterconnectIfds = self.dao.getConnectedInterconnectIFDsFilterFakeOnes(device)
        for ifd in deviceInterconnectIfds:
            peerIfd = ifd.peer
            peerDevice = peerIfd.device
            peerInterconnectIfl = peerIfd.layerAboves[0]
            peerInterconnectIpNoCidr = peerInterconnectIfl.ipaddress.split('/')[0]
            neighborList.append({'peer_ip': peerInterconnectIpNoCidr, 'peer_asn': peerDevice.asn})

        return template.render(neighbors=neighborList)        
         
    def createProtocolLldp(self, device):
        template = self.templateEnv.get_template('protocolLldp.txt')
        return template.render()        

    def createPolicyOption(self, device):
        pod = device.pod
        
        template = self.templateEnv.get_template('policyOptions.txt')
        subnetDict = {}
        subnetDict['lo0_in'] = pod.allocatedLoopbackBlock
        subnetDict['irb_in'] = pod.allocatedIrbBlock
        
        if device.role == 'leaf':
            deviceLoopbackIfl = self.dao.Session.query(InterfaceLogical).join(Device).filter(Device.id == device.id).filter(InterfaceLogical.name == 'lo0.0').one()
            deviceIrbIfl = self.dao.Session.query(InterfaceLogical).join(Device).filter(Device.id == device.id).filter(InterfaceLogical.name == 'irb.1').one()
            subnetDict['lo0_out'] = deviceLoopbackIfl.ipaddress
            subnetDict['irb_out'] = deviceIrbIfl.ipaddress
        else:
            subnetDict['lo0_out'] = pod.allocatedLoopbackBlock
            subnetDict['irb_out'] = pod.allocatedIrbBlock
         
        return template.render(subnet=subnetDict)
        
    def createVlan(self, device):
        if device.role == 'leaf':
            template = self.templateEnv.get_template('vlans.txt')
            return template.render()
        else:
            return ''

    def getNdTrapGroupSettings(self):
        snmpTrapConf = self.conf.get('snmpTrap')
        if snmpTrapConf is None:
            logger.error('No SNMP Trap setting found on openclos.yaml')
            return
        if (util.isIntegratedWithND(self.conf)):
            ndSnmpTrapConf = snmpTrapConf.get('networkdirector_trap_group') 
            if ndSnmpTrapConf is None:
                logger.error('No SNMP Trap setting found for ND')
                return
            targetList = []
            if isinstance(ndSnmpTrapConf['target'], list) == True:
                targetList = ndSnmpTrapConf['target']
            else:
                targetList.append(ndSnmpTrapConf['target'])
            return {'name': 'networkdirector_trap_group', 'port': ndSnmpTrapConf['port'], 'targetIp': targetList }
        return
    
    def getOpenclosTrapGroupSettings(self):
        snmpTrapConf = self.conf.get('snmpTrap')
        if snmpTrapConf is None:
            logger.error('No SNMP Trap setting found on openclos.yaml')
            return
        openclosSnmpTrapConf = snmpTrapConf.get('openclos_trap_group') 
        if openclosSnmpTrapConf is None:
            logger.error('No SNMP Trap setting found for OpenClos')
            return
        targetList = util.enumerateRoutableIpv4Addresses()
        return {'name': 'openclos_trap_group', 'port': openclosSnmpTrapConf['port'], 'targetIp': targetList }

    def createSnmpTrapAndEvent(self, device):
        snmpTemplate = self.templateEnv.get_template('snmpTrap.txt')
        trapEventTemplate = self.templateEnv.get_template('eventOptionForTrap.txt')
        
        configlet = trapEventTemplate.render()
        
        if device.role == 'leaf':
            groups = []
            openclosTrapGroup = self.getOpenclosTrapGroupSettings()
            if openclosTrapGroup is not None:
                groups.append(openclosTrapGroup)
                
            ndTrapGroup = self.getNdTrapGroupSettings()
            if ndTrapGroup is not None:
                groups.append(ndTrapGroup)
                
            configlet += snmpTemplate.render(trapGroups = groups)
            return configlet

        elif device.role == 'spine':
            ndTrapGroup = self.getNdTrapGroupSettings()
            if ndTrapGroup is not None:
                configlet += snmpTemplate.render(trapGroups = [ndTrapGroup])
                return configlet

        return ''

    def createSnmpTrapAndEventForLeafFor2ndStage(self, device):
        snmpTemplate = self.templateEnv.get_template('snmpTrap.txt')
        trapEventTemplate = self.templateEnv.get_template('eventOptionForTrap.txt')
        
        configlet = trapEventTemplate.render()
        
        if device.role == 'leaf':
            ndTrapGroup = self.getNdTrapGroupSettings()
            if ndTrapGroup is not None:
                configlet += snmpTemplate.render(trapGroups = [ndTrapGroup])
                
            return configlet

        elif device.role == 'spine':
            logger.debug('Device: %s, id: %s, role: spine, no 2ndStage trap/event connfig generated' % (device.name, device.id))
        return ''

    def createLeafGenericConfigsFor2Stage(self, pod):
        '''
        :param Pod: pod
        :returns list: list of PodConfigs
        '''
        leafTemplate = self.templateEnv.get_template('leafGenericTemplate.txt')
        leafSettings = {}
        for leafSetting in pod.leafSettings:
            leafSettings[leafSetting.deviceFamily] = leafSetting

        groups = []
        openclosTrapGroup = self.getOpenclosTrapGroupSettings()
        if openclosTrapGroup is not None:
            groups.append(openclosTrapGroup)
            
        ndTrapGroup = self.getNdTrapGroupSettings()
        if ndTrapGroup is not None:
            groups.append(ndTrapGroup)
            
        outOfBandNetworkParams = self.getParamsForOutOfBandNetwork(pod)
        
        for deviceFamily in leafSettings.keys():
            if deviceFamily == 'qfx5100-24q-2p':
                continue
            
            ifdNames = []
            for ifdName in util.getPortNamesForDeviceFamily(deviceFamily, self.conf['deviceFamily'])['downlinkPorts']:
                ifdNames.append(ifdName)

            leafSettings[deviceFamily].config = leafTemplate.render(deviceFamily = deviceFamily, oob = outOfBandNetworkParams, 
                trapGroups = groups, hashedPassword=pod.getHashPassword(), ifdNames=ifdNames)
            
        return leafSettings.values()

    def createLeafConfigFor2Stage(self, device):
        configWriter = ConfigWriter(self.conf, device.pod, self.dao)
        
        config = self.createBaseConfig(device)
        config += self.createInterfaces(device)
        config += self.createRoutingOptionsStatic(device)
        config += self.createRoutingOptionsBgp(device)
        config += self.createProtocolBgp(device)
        config += self.createProtocolLldp(device)
        config += self.createPolicyOption(device)
        config += self.createSnmpTrapAndEventForLeafFor2ndStage(device)
        config += self.createVlan(device)
        device.config = DeviceConfig(device.id, config)
        self.dao.updateObjects([device])
        logger.debug('Generated config for device name: %s, id: %s, storing in DB' % (device.name, device.id))
        configWriter.write(device)
        return config
        
if __name__ == '__main__':
    l3ClosMediation = L3ClosMediation()
    pods = l3ClosMediation.loadClosDefinition()

    pod1 = l3ClosMediation.createPod('labLeafSpine', pods['labLeafSpine'])
    l3ClosMediation.createCablingPlan(pod1.id)
    l3ClosMediation.createDeviceConfig(pod1.id)

    pod2 = l3ClosMediation.createPod('anotherPod', pods['anotherPod'])
    l3ClosMediation.createCablingPlan(pod2.id)
    l3ClosMediation.createDeviceConfig(pod2.id)
