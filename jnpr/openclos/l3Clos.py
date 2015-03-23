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

from model import Pod, Device, InterfaceLogical, InterfaceDefinition, CablingPlan, DeviceConfig, TrapGroup
from dao import Dao
import util
from writer import ConfigWriter, CablingPlanWriter
from jinja2 import Environment, PackageLoader
import logging

junosTemplateLocation = os.path.join('conf', 'junosTemplates')

moduleName = 'l3Clos'
logger = None

class L3ClosMediation():
    def __init__(self, conf = {}, daoClass = Dao):
        global logger
        if any(conf) == False:
            self._conf = util.loadConfig(appName = moduleName)
        else:
            self._conf = conf

        logger = logging.getLogger(moduleName)
        self._dao = daoClass.getInstance()

        self._templateEnv = Environment(loader=PackageLoader('jnpr.openclos', junosTemplateLocation))
        self._templateEnv.keep_trailing_newline = True
        self.isZtpStaged = util.isZtpStaged(self._conf)

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
        Create a new Pod
        :returns str: Pod identifier

        '''
        pod = Pod(podName, podDict)
        pod.validate()
        # inventory can come from either podDict or inventoryDict
        inventoryData = self._resolveInventory(podDict, inventoryDict)
        # check inventory contains correct number of devices
        self._validatePod(pod, podDict, inventoryData)

        with self._dao.getReadWriteSession() as session:
            self._dao.createObjects(session, [pod])
            # shortcut for updating in createPod
            # this use case is typical in script invocation but not in ND REST invocation
            self._updatePodData(session, pod, podDict, inventoryData)
            logger.info("Pod[id='%s', name='%s']: created" % (pod.id, pod.name)) 
            podId = pod.id
        
        #Hack sqlalchemy: access object is REQUIRED after commit as session has expire_on_commit=True.
        with self._dao.getReadSession() as session:
            pod = self._dao.getObjectById(session, Pod, podId)
        return pod
    
    def _createSpineIfds(self, session, pod, spines):
        devices = []
        interfaces = []
        for spine in spines:
            username = spine.get('username')    #default is 'root' set on DB
            password = spine.get('password')
            macAddress = spine.get('macAddress')
            deployStatus = spine.get('deployStatus')    #default is 'provision' set on DB
            serialNumber = spine.get('serialNumber')
            device = Device(spine['name'], pod.spineDeviceType, username, password, 'spine', macAddress, None, pod, deployStatus, serialNumber)
            devices.append(device)
            
            portNames = util.getPortNamesForDeviceFamily(device.family, self._conf['deviceFamily'])
            for name in portNames['ports']:     # spine does not have any uplink/downlink marked, it is just ports
                ifd = InterfaceDefinition(name, device, 'downlink')
                interfaces.append(ifd)
        self._dao.createObjects(session, devices)
        self._dao.createObjects(session, interfaces)
        
    def _createLeafIfds(self, session, pod, leaves):
        devices = []
        interfaces = []
        for leaf in leaves:
            username = leaf.get('username')
            password = leaf.get('password') #default is Pod level pass, set on constructor
            macAddress = leaf.get('macAddress')
            family = leaf.get('family') #default is 'unknown' set on DB
            deployStatus = leaf.get('deployStatus') #default is 'provision' set on DB
            serialNumber = leaf.get('serialNumber')
            device = Device(leaf['name'], family, username, password, 'leaf', macAddress, None, pod, deployStatus, serialNumber)
            devices.append(device)
            
            if family is None or family == 'unknown':
                # temporary uplink ports, names will get fixed after 2-stage ztp
                for i in xrange(0, pod.spineCount):
                    interfaces.append(InterfaceDefinition('uplink-' + str(i), device, 'uplink'))

            else:
                portNames = util.getPortNamesForDeviceFamily(device.family, self._conf['deviceFamily'])
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
        
        self._dao.createObjects(session, devices)
        self._dao.createObjects(session, interfaces)
    
    def _deployInventory(self, pod, inventory, role):
        for inv in inventory:
            for device in pod.devices:
                # find match by role/id/name
                if device.role == role and (device.id == inv.get('id') or device.name == inv['name']):
                    if device.deployStatus == inv.get('deployStatus'):
                        logger.debug("Pod[id='%s', name='%s']: %s device '%s' deploy status unchanged" % (pod.id, pod.name, device.role, device.name))
                    elif device.deployStatus == 'deploy' and (inv.get('deployStatus') is None or inv.get('deployStatus') == 'provision'):
                        logger.debug("Pod[id='%s', name='%s']: %s device '%s' provisioned" % (pod.id, pod.name, device.role, device.name))
                    elif device.deployStatus == 'provision' and inv.get('deployStatus') == 'deploy':
                        logger.debug("Pod[id='%s', name='%s']: %s device '%s' deployed" % (pod.id, pod.name, device.role, device.name))
                    device.update(inv['name'], inv.get('username'), inv.get('password'), inv.get('macAddress'), inv.get('deployStatus'), inv.get('serialNumber'))
                       
    def _resolveInventory(self, podDict, inventoryDict):
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

    def _validateAttribute(self, pod, attr, dct):
        if dct.get(attr) is None:
            raise ValueError("Pod[id='%s', name='%s']: device '%s' attribute '%s' cannot be None" % (pod.id, pod.name, dct.get('name'), attr))
    
    def _validateLoopbackPrefix(self, pod, podDict, inventoryData):
        inventoryDeviceCount = len(inventoryData['spines']) + len(inventoryData['leafs'])
        lo0Block = IPNetwork(podDict['loopbackPrefix'])
        lo0Ips = list(lo0Block.iter_hosts())
        availableIps = len(lo0Ips)
        if availableIps < inventoryDeviceCount:
            raise ValueError("Pod[id='%s', name='%s']: loopbackPrefix available IPs %d not enough: required %d" % (pod.id, pod.name, availableIps, inventoryDeviceCount))

    def _validateVlanPrefix(self, pod, podDict, inventoryData):
        vlanBlock = IPNetwork(podDict['vlanPrefix'])
        numOfHostIpsPerSwitch = podDict['hostOrVmCountPerLeaf']
        numOfSubnets = len(inventoryData['leafs'])
        numOfIps = (numOfSubnets * (numOfHostIpsPerSwitch + 2)) # +2 for network and broadcast
        numOfBits = int(math.ceil(math.log(numOfIps, 2))) 
        cidr = 32 - numOfBits
        if vlanBlock.prefixlen > cidr:
            raise ValueError("Pod[id='%s', name='%s']: vlanPrefix avaiable block /%d not enough: required /%d" % (pod.id, pod.name, vlanBlock.prefixlen, cidr))
    
    def _validateInterConnectPrefix(self, pod, podDict, inventoryData):
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
    
    def _validateManagementPrefix(self, pod, podDict, inventoryData):
        inventoryDeviceCount = len(inventoryData['spines']) + len(inventoryData['leafs'])
        managementIps = util.getMgmtIps(podDict.get('managementPrefix'), podDict.get('managementStartingIP'), podDict.get('managementMask'), inventoryDeviceCount)
        availableIps = len(managementIps)
        if availableIps < inventoryDeviceCount:
            raise ValueError("Pod[id='%s', name='%s']: managementPrefix avaiable IPs %d not enough: required %d" % (pod.id, pod.name, availableIps, inventoryDeviceCount))
    
    def _validatePod(self, pod, podDict, inventoryData):
        if inventoryData is None:
            raise ValueError("Pod[id='%s', name='%s']: inventory cannot be empty" % (pod.id, pod.name))
        
        # if following data changed we need to reallocate resource
        if pod.spineCount != podDict['spineCount'] or pod.leafCount != podDict['leafCount']:
            raise ValueError("Pod[id='%s', name='%s']: capacity cannot be changed" % (pod.id, pod.name))

        for spine in inventoryData['spines']:
            self._validateAttribute(pod, 'name', spine)
            #self._validateAttribute(pod, 'role', spine)
            #self._validateAttribute(pod, 'family', spine)
            #self._validateAttribute(pod, 'deployStatus', spine)
            
        for leaf in inventoryData['leafs']:
            self._validateAttribute(pod, 'name', leaf)
            #self._validateAttribute(pod, 'role', leaf)
            #self._validateAttribute(pod, 'family', leaf)
            #self._validateAttribute(pod, 'deployStatus', leaf)
                
        # inventory should contain exact same number of devices as capacity
        expectedDeviceCount = int(podDict['spineCount']) + int(podDict['leafCount'])
        inventoryDeviceCount = len(inventoryData['spines']) + len(inventoryData['leafs'])
        if expectedDeviceCount != inventoryDeviceCount:
            raise ValueError("Pod[id='%s', name='%s']: inventory device count %d does not match capacity %d" % (pod.id, pod.name, inventoryDeviceCount, expectedDeviceCount))

        # validate loopbackPrefix is big enough
        self._validateLoopbackPrefix(pod, podDict, inventoryData)

        # validate vlanPrefix is big enough
        self._validateVlanPrefix(pod, podDict, inventoryData)
        
        # validate interConnectPrefix is big enough
        self._validateInterConnectPrefix(pod, podDict, inventoryData)
        
        # validate managementPrefix is big enough
        self._validateManagementPrefix(pod, podDict, inventoryData)
                
        
    def _diffInventory(self, pod, inventoryData):
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
            self._deployInventory(pod, inventoryData['spines'], 'spine')
            self._deployInventory(pod, inventoryData['leafs'], 'leaf')
        else:
            logger.debug("Pod[id='%s', name='%s']: inventory not changed" % (pod.id, pod.name))

    def _needToRebuild(self, pod, podDict):
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
            
    def _updatePodData(self, session, pod, podDict, inventoryData):
        # if following data changed we need to reallocate resource
        if self._needToRebuild(pod, podDict) == True:
            logger.debug("Pod[id='%s', name='%s']: rebuilding required" % (pod.id, pod.name))
            if len(pod.devices) > 0:
                self._dao.deleteObjects(session, pod.devices)

        # first time
        if len(pod.devices) == 0:
            logger.debug("Pod[id='%s', name='%s']: building inventory and resource..." % (pod.id, pod.name))
            self._createSpineIfds(session, pod, inventoryData['spines'])
            self._createLeafIfds(session, pod, inventoryData['leafs'])
            self._createLinkBetweenIfds(session, pod)
            pod.devices.sort(key=lambda dev: dev.name) # Hack to order lists by name
            self._allocateResource(session, pod)
        else:        
            # compare new inventory that user provides against old inventory that we stored in the database
            self._diffInventory(pod, inventoryData)
                
        # update pod itself
        pod.update(pod.id, pod.name, podDict)
        self._dao.updateObjects(session, [pod])
            
        # TODO move the backup operation to CLI 
        # backup current database
        util.backupDatabase(self._conf)

    def updatePod(self, podId, podDict, inventoryDict = None):
        '''
        Modify an existing POD. As a sanity check, if we don't find the POD
        by UUID, a ValueException is thrown
        '''
        if podId is None: 
            raise ValueError("Pod id cannot be None")

        with self._dao.getReadWriteSession() as session:        
            try:
                pod = self._dao.getObjectById(session, Pod, podId)
            except (exc.NoResultFound):
                raise ValueError("Pod[id='%s']: not found" % (podId)) 

            # inventory can come from either podDict or inventoryDict
            inventoryData = self._resolveInventory(podDict, inventoryDict)
            # check inventory contains correct number of devices
            self._validatePod(pod, podDict, inventoryData)
    
            # update other fields
            self._updatePodData(session, pod, podDict, inventoryData)
            logger.info("Pod[id='%s', name='%s']: updated" % (pod.id, pod.name)) 
            podId = pod.id
        
        #Hack sqlalchemy: access object is REQUIRED after commit as session has expire_on_commit=True.
        with self._dao.getReadSession() as session:
            pod = self._dao.getObjectById(session, Pod, podId)
        return pod
    
    def deletePod(self, podId):
        '''
        Delete an existing POD. As a sanity check, if we don't find the POD
        by UUID, a ValueException is thrown
        '''
        if podId is None: 
            raise ValueError("Pod id cannot be None")

        with self._dao.getReadWriteSession() as session:        
            try:
                pod = self._dao.getObjectById(session, Pod, podId)
            except (exc.NoResultFound):
                raise ValueError("Pod[id='%s']: not found" % (podId)) 

            self._dao.deleteObject(session, pod)
            logger.info("Pod[id='%s', name='%s']: deleted" % (pod.id, pod.name)) 

    def createCablingPlan(self, podId):
        '''
        Finds Pod object by id and create cabling plan
        It also creates the output folders for pod
        '''
        if podId is None: 
            raise ValueError("Pod id cannot be None")

        with self._dao.getReadWriteSession() as session:        
            try:
                pod = self._dao.getObjectById(session, Pod, podId)
            except (exc.NoResultFound):
                raise ValueError("Pod[id='%s']: not found" % (podId)) 
 
            if len(pod.devices) > 0:
                cablingPlanWriter = CablingPlanWriter(self._conf, pod, self._dao)
                # create cabling plan in JSON format
                cablingPlanJson = cablingPlanWriter.writeJSON()
                pod.cablingPlan = CablingPlan(pod.id, cablingPlanJson)
                # create cabling plan in DOT format
                cablingPlanWriter.writeDOT()
                self._dao.updateObjects(session, [pod])
                
                return True
            else:
                raise ValueError("Pod[id='%s', name='%s']: inventory is empty" % (pod.id, pod.name)) 
            
    def createDeviceConfig(self, podId):
        '''
        Finds Pod object by id and create device configurations
        It also creates the output folders for pod
        '''
        if podId is None: 
            raise ValueError("Pod id cannot be None")

        with self._dao.getReadWriteSession() as session:        
            try:
                pod = self._dao.getObjectById(session, Pod, podId)
            except (exc.NoResultFound):
                raise ValueError("Pod[id='%s']: not found" % (podId)) 
 
            if len(pod.devices) > 0:
                # create configuration
                self.generateConfig(session, pod)
        
                return True
            else:
                raise ValueError("Pod[id='%s', name='%s']: inventory is empty" % (pod.id, pod.name)) 

    def _createLinkBetweenIfds(self, session, pod):
        leaves = []
        spines = []
        for device in pod.devices:
            if (device.role == 'leaf'):
                leafUplinkPorts = session.query(InterfaceDefinition).filter(InterfaceDefinition.device_id == device.id).filter(InterfaceDefinition.role == 'uplink').order_by(InterfaceDefinition.sequenceNum).all()
                leaves.append({'leaf': device, 'leafUplinkPorts': leafUplinkPorts})
            elif (device.role == 'spine'):
                spinePorts = session.query(InterfaceDefinition).filter(InterfaceDefinition.device_id == device.id).order_by(InterfaceDefinition.sequenceNum).all()
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
        self._dao.updateObjects(session, modifiedObjects)
        
    def _getLeafSpineFromPod(self, pod):
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
    
    def _allocateResource(self, session, pod):
        self._allocateLoopback(session, pod, pod.loopbackPrefix, pod.devices)
        leafSpineDict = self._getLeafSpineFromPod(pod)
        self._allocateIrb(session, pod, pod.vlanPrefix, leafSpineDict['leafs'])
        self._allocateInterconnect(session, pod.interConnectPrefix, leafSpineDict['spines'], leafSpineDict['leafs'])
        self._allocateAsNumber(session, pod.spineAS, pod.leafAS, leafSpineDict['spines'], leafSpineDict['leafs'])
        self._allocateManagement(session, pod.managementPrefix, pod.managementStartingIP, pod.managementMask, leafSpineDict['spines'], leafSpineDict['leafs'])
        
    def _allocateManagement(self, session, managementPrefix, managementStartingIP, managementMask, spines, leaves):
        deviceCount = len(spines)+len(leaves)
        managementIps = util.getMgmtIps(managementPrefix, managementStartingIP, managementMask, deviceCount)
        # don't do partial allocation
        if len(managementIps) == deviceCount:
            for spine, managementIp in zip(spines, managementIps[:len(spines)]):
                spine.managementIp = managementIp
            self._dao.updateObjects(session, spines)
            
            # for 2stage and leaf, don' fill in management ip
            if self.isZtpStaged == False:
                for leaf, managementIp in zip(leaves, managementIps[len(spines):]):
                    leaf.managementIp = managementIp
                self._dao.updateObjects(session, leaves)
        
    def _allocateLoopback(self, session, pod, loopbackPrefix, devices):
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
        self._dao.createObjects(session, interfaces)

    def _allocateIrb(self, session, pod, irbPrefix, leafs):
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
        self._dao.createObjects(session, interfaces)

    def _allocateInterconnect(self, session, interConnectPrefix, spines, leafs):
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
            ifdsHasPeer = session.query(InterfaceDefinition).filter(InterfaceDefinition.device_id == spine.id).filter(InterfaceDefinition.peer != None).order_by(InterfaceDefinition.sequenceNum).all()
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
        self._dao.createObjects(session, interfaces)

    def _allocateAsNumber(self, session, spineAsn, leafAsn, spines, leafs):
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

        self._dao.updateObjects(session, devices)
        
    def generateConfig(self, session, pod):
        configWriter = ConfigWriter(self._conf, pod, self._dao)
        modifiedObjects = []
        
        for device in pod.devices:
            if device.role == 'leaf' and (self.isZtpStaged or device.family == 'unknown'):
                # leaf configs will get created when they are plugged in after 2Stage ztp
                continue
            
            config = self._createBaseConfig(device)
            config += self._createInterfaces(session, device)
            config += self._createRoutingOptionsStatic(session, device)
            config += self._createRoutingOptionsBgp(session, device)
            config += self._createProtocolBgp(session, device)
            config += self._createProtocolLldp(device)
            config += self._createPolicyOption(session, device)
            config += self._createSnmpTrapAndEvent(session, device)
            config += self._createVlan(device)
            device.config = DeviceConfig(device.id, config)
            modifiedObjects.append(device)
            logger.debug('Generated config for device name: %s, id: %s, storing in DB' % (device.name, device.id))
            configWriter.write(device)

        if self.isZtpStaged:
            pod.leafSettings = self._createLeafGenericConfigsFor2Stage(session, pod)
            modifiedObjects.append(pod)
            logger.debug('Generated %d leaf generic configs for pod: %s, storing in DB' % (len(pod.leafSettings), pod.name))
            configWriter.writeGenericLeaf(pod)
        
        self._dao.updateObjects(session, modifiedObjects)

    def _createBaseConfig(self, device):
        baseTemplate = self._templateEnv.get_template('baseTemplate.txt')
        return baseTemplate.render(hostName=device.name, hashedPassword=device.getHashPassword())

    def _createInterfaces(self, session, device): 
        interfaceStanza = self._templateEnv.get_template('interface_stanza.txt')
        lo0Stanza = self._templateEnv.get_template('lo0_stanza.txt')
        mgmtStanza = self._templateEnv.get_template('mgmt_interface.txt')
        rviStanza = self._templateEnv.get_template('rvi_stanza.txt')
            
        config = "interfaces {" + "\n" 
        # management interface
        config += mgmtStanza.render(mgmt_address=device.managementIp)
                
        #loopback interface
        loopbackIfl = session.query(InterfaceLogical).join(Device).filter(Device.id == device.id).filter(InterfaceLogical.name == 'lo0.0').one()
        config += lo0Stanza.render(address=loopbackIfl.ipaddress)
        
        # For Leaf add IRB and server facing interfaces        
        if device.role == 'leaf':
            irbIfl = session.query(InterfaceLogical).join(Device).filter(Device.id == device.id).filter(InterfaceLogical.name == 'irb.1').one()
            config += rviStanza.render(address=irbIfl.ipaddress)
            config += self._createAccessPortInterfaces(device.family)

        # Interconnect interfaces
        deviceInterconnectIfds = self._dao.getConnectedInterconnectIFDsFilterFakeOnes(session, device)
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

    def _createAccessPortInterfaces(self, deviceFamily):
        accessInterface = self._templateEnv.get_template('accessInterface.txt')
        ifdNames = []

        for ifdName in util.getPortNamesForDeviceFamily(deviceFamily, self._conf['deviceFamily'])['downlinkPorts']:
            ifdNames.append(ifdName)

        return accessInterface.render(ifdNames=ifdNames)

    def _getOpenclosTrapTargetIpFromConf(self):
        snmpTrapConf = self._conf.get('snmpTrap')
        if snmpTrapConf is not None:
            openclosSnmpTrapConf = snmpTrapConf.get('openclos_trap_group') 
            if openclosSnmpTrapConf is not None:
                target = snmpTrapConf.get('openclos_trap_group').get('target')
                if target is not None:
                    return [target]
        return []

    def _getSnmpTrapTargets(self, session):
        if self.isZtpStaged:
            return self._getOpenclosTrapTargetIpFromConf()
        else:
            return []

    def _getParamsForOutOfBandNetwork(self, session, pod):
        '''
        add all trap-target to the OOB list
        '''
        oobList = self._getSnmpTrapTargets(session)
        oobNetworks = pod.outOfBandAddressList
        if oobNetworks is not None and len(oobNetworks) > 0:
            oobList += oobNetworks.split(',')

        # hack to make sure all address has cidr notation
        for i in xrange(len(oobList)):
            if '/' not in oobList[i]:
                oobList[i] += '/32'

        gateway = pod.outOfBandGateway
        if gateway is None:
            gateway = util.loadClosDefinition()['ztp']['dhcpOptionRoute']
       
        oobList = set(oobList)
        if oobList:
            return {'networks': oobList, 'gateway': gateway}
        else:
            return {}
    
    def _createRoutingOptionsStatic(self, session, device):
        routingOptions = self._templateEnv.get_template('routingOptionsStatic.txt')
        return routingOptions.render(oob = self._getParamsForOutOfBandNetwork(session, device.pod))

    def _createRoutingOptionsBgp(self, session, device):
        routingOptions = self._templateEnv.get_template('routingOptionsBgp.txt')

        loopbackIfl = session.query(InterfaceLogical).join(Device).filter(Device.id == device.id).filter(InterfaceLogical.name == 'lo0.0').one()
        loopbackIpWithNoCidr = loopbackIfl.ipaddress.split('/')[0]
        
        return routingOptions.render(routerId=loopbackIpWithNoCidr, asn=str(device.asn))

    def _createProtocolBgp(self, session, device):
        template = self._templateEnv.get_template('protocolBgp.txt')

        neighborList = []
        deviceInterconnectIfds = self._dao.getConnectedInterconnectIFDsFilterFakeOnes(session, device)
        for ifd in deviceInterconnectIfds:
            peerIfd = ifd.peer
            peerDevice = peerIfd.device
            peerInterconnectIfl = peerIfd.layerAboves[0]
            peerInterconnectIpNoCidr = peerInterconnectIfl.ipaddress.split('/')[0]
            neighborList.append({'peer_ip': peerInterconnectIpNoCidr, 'peer_asn': peerDevice.asn})

        return template.render(neighbors=neighborList)        
         
    def _createProtocolLldp(self, device):
        template = self._templateEnv.get_template('protocolLldp.txt')
        return template.render()        

    def _createPolicyOption(self, session, device):
        pod = device.pod
        
        template = self._templateEnv.get_template('policyOptions.txt')
        subnetDict = {}
        subnetDict['lo0_in'] = pod.allocatedLoopbackBlock
        subnetDict['irb_in'] = pod.allocatedIrbBlock
        
        if device.role == 'leaf':
            deviceLoopbackIfl = session.query(InterfaceLogical).join(Device).filter(Device.id == device.id).filter(InterfaceLogical.name == 'lo0.0').one()
            deviceIrbIfl = session.query(InterfaceLogical).join(Device).filter(Device.id == device.id).filter(InterfaceLogical.name == 'irb.1').one()
            subnetDict['lo0_out'] = deviceLoopbackIfl.ipaddress
            subnetDict['irb_out'] = deviceIrbIfl.ipaddress
        else:
            subnetDict['lo0_out'] = pod.allocatedLoopbackBlock
            subnetDict['irb_out'] = pod.allocatedIrbBlock
         
        return template.render(subnet=subnetDict)
        
    def _createVlan(self, device):
        if device.role == 'leaf':
            template = self._templateEnv.get_template('vlans.txt')
            return template.render()
        else:
            return ''

    def _getOpenclosTrapGroupSettings(self, session):
        '''
        :returns list: list of trap group settings
        '''
        if not self.isZtpStaged:
            return []
        
        trapGroups = []
        
        targets = self._dao.getObjectsByName(session, TrapGroup, 'openclos_trap_group')
        if targets:
            targetAddressList = [target.targetAddress for target in targets]
            trapGroups.append({'name': targets[0].name, 'port': targets[0].port, 'targetIp': targetAddressList })
            logger.debug('Added SNMP Trap setting for openclos_trap_group (from DB) with %d targets' % (len(targets)))
        else:
            snmpTrapConf = self._conf.get('snmpTrap')
            if snmpTrapConf is not None:
                openclosSnmpTrapConf = snmpTrapConf.get('openclos_trap_group') 
                if openclosSnmpTrapConf is not None:
                    targetList = self._getOpenclosTrapTargetIpFromConf()
                    trapGroups.append({'name': 'openclos_trap_group', 'port': openclosSnmpTrapConf['port'], 'targetIp': targetList })
                else:
                    logger.error('No SNMP Trap setting found for openclos_trap_group in openclos.yaml')
            else:
                logger.error('No SNMP Trap setting found for openclos_trap_group in openclos.yaml')
        
        return trapGroups

    def _getLeafTrapGroupSettings(self, session, generic = False):
        '''
        :param session: database session
        :param boolean: generic flag indicated if it is for leafGeneric config or leaf 2nd-stage config
        '''
        if self.isZtpStaged:
            if generic:
                return self._getOpenclosTrapGroupSettings(session)
            else:
                return []
        else:
            return []
        
    def _getSpineTrapGroupSettings(self, session):
        return []
    
    def _createSnmpTrapAndEvent(self, session, device):
        snmpTemplate = self._templateEnv.get_template('snmpTrap.txt')
        trapEventTemplate = self._templateEnv.get_template('eventOptionForTrap.txt')
        
        configlet = trapEventTemplate.render()
        
        if device.role == 'leaf':
            trapGroups = self._getLeafTrapGroupSettings(session)
            if trapGroups:
                configlet += snmpTemplate.render(trapGroups = trapGroups)
                return configlet

        elif device.role == 'spine':
            trapGroups = self._getSpineTrapGroupSettings(session)
            if trapGroups:
                configlet += snmpTemplate.render(trapGroups = trapGroups)
                return configlet

        return ''

    def _createSnmpTrapAndEventForLeafFor2ndStage(self, session, device):
        snmpTemplate = self._templateEnv.get_template('snmpTrap.txt')
        trapEventTemplate = self._templateEnv.get_template('eventOptionForTrap.txt')
        disableSnmpTemplate = self._templateEnv.get_template('snmpTrapDisable.txt')
        
        configlet = trapEventTemplate.render()
        
        if device.role == 'leaf':
            trapGroups = self._getOpenclosTrapGroupSettings(session)
            if trapGroups:
                configlet += disableSnmpTemplate.render(trapGroups = trapGroups)
            trapGroups = self._getLeafTrapGroupSettings(session)
            if trapGroups:
                configlet += snmpTemplate.render(trapGroups = trapGroups)
                
            return configlet

        elif device.role == 'spine':
            logger.debug('Device: %s, id: %s, role: spine, no 2ndStage trap/event connfig generated' % (device.name, device.id))
        return ''

    def _createLeafGenericConfigsFor2Stage(self, session, pod):
        '''
        :param Pod: pod
        :returns list: list of PodConfigs
        '''
        leafTemplate = self._templateEnv.get_template('leafGenericTemplate.txt')
        leafSettings = {}
        for leafSetting in pod.leafSettings:
            leafSettings[leafSetting.deviceFamily] = leafSetting

        trapGroups = self._getLeafTrapGroupSettings(session, True)

        outOfBandNetworkParams = self._getParamsForOutOfBandNetwork(session, pod)
        
        for deviceFamily in leafSettings.keys():
            if deviceFamily == 'qfx5100-24q-2p':
                continue
            
            ifdNames = []
            for ifdName in util.getPortNamesForDeviceFamily(deviceFamily, self._conf['deviceFamily'])['downlinkPorts']:
                ifdNames.append(ifdName)

            leafSettings[deviceFamily].config = leafTemplate.render(deviceFamily = deviceFamily, oob = outOfBandNetworkParams, 
                trapGroups = trapGroups, hashedPassword=pod.getHashPassword(), ifdNames=ifdNames)
            
        return leafSettings.values()

    def createLeafConfigFor2Stage(self, device):
        configWriter = ConfigWriter(self._conf, device.pod, self._dao)
        
        with self._dao.getReadWriteSession() as session:
            config = self._createBaseConfig(device)
            config += self._createInterfaces(session, device)
            config += self._createRoutingOptionsStatic(session, device)
            config += self._createRoutingOptionsBgp(session, device)
            config += self._createProtocolBgp(session, device)
            config += self._createProtocolLldp(device)
            config += self._createPolicyOption(session, device)
            config += self._createSnmpTrapAndEventForLeafFor2ndStage(session, device)
            config += self._createVlan(device)
            device.config = DeviceConfig(device.id, config)
            self._dao.updateObjects(session, [device])
        logger.debug('Generated config for device name: %s, id: %s, storing in DB' % (device.name, device.id))
        configWriter.write(device)
        return config

def main():        
    l3ClosMediation = L3ClosMediation()
    pods = l3ClosMediation.loadClosDefinition()

    pod1 = l3ClosMediation.createPod('labLeafSpine', pods['labLeafSpine'])
    l3ClosMediation.createCablingPlan(pod1.id)
    l3ClosMediation.createDeviceConfig(pod1.id)

    pod2 = l3ClosMediation.createPod('anotherPod', pods['anotherPod'])
    l3ClosMediation.createCablingPlan(pod2.id)
    l3ClosMediation.createDeviceConfig(pod2.id)

if __name__ == '__main__':
    main()
    
    