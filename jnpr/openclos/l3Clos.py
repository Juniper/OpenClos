'''
Created on May 23, 2014

@author: moloyc
'''

import yaml
import os
import json
import math
import logging
import zlib
import base64

from netaddr import IPNetwork
from sqlalchemy.orm import exc

from model import Pod, Device, InterfaceLogical, InterfaceDefinition
from dao import Dao
import util
from writer import ConfigWriter, CablingPlanWriter
from jinja2 import Environment, PackageLoader

junosTemplateLocation = os.path.join('conf', 'junosTemplates')

moduleName = 'fabric'
logging.basicConfig()
logger = logging.getLogger(moduleName)
logger.setLevel(logging.DEBUG)

class L3ClosMediation():
    def __init__(self, conf = {}):
        if any(conf) == False:
            self.conf = util.loadConfig()
            logger.setLevel(logging.getLevelName(self.conf['logLevel'][moduleName]))
        else:
            self.conf = conf

        self.dao = Dao(self.conf)
        self.templateEnv = Environment(loader=PackageLoader('jnpr.openclos', junosTemplateLocation))
        self.templateEnv.keep_trailing_newline = True
        
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
        pod = Pod(podName, **podDict)
        #pod.validate()
        self.dao.createObjects([pod])
        logger.info("Pod[id='%s', name='%s']: created" % (pod.id, podName)) 
        # update status
        pod.state = 'created'
        self.dao.updateObjects([pod])

        # shortcut for updating in createPod
        # this use case is typical in script invocation but not in ND REST invocation
        self.updatePodData(pod, podDict, inventoryDict)
        
        return pod

    def updatePodData(self, pod, podDict, inventoryDict):
        if podDict is None and inventoryDict is None:
            return 
            
        dirty = False
        # inventoryDict is the typical use case for ND REST invocation
        # podDict['inventory'] is the typical use case for script invocation
        inventoryData = None
        if inventoryDict is not None:
            inventoryData = inventoryDict
        elif 'inventory' in podDict and podDict['inventory'] is not None:
            json_inventory = open(os.path.join(util.configLocation, podDict['inventory']))
            inventoryData = json.load(json_inventory)
            json_inventory.close()

        # get current inventory stored in database
        # Note if user does not provide inventory, don't consider it is dirty
        if inventoryData is not None:
            # user provides an inventory. now check the inventory we already have in database
            if pod.inventoryData is not None:
                inventoryDataInDb = json.loads(zlib.decompress(base64.b64decode(pod.inventoryData)))
                if inventoryData != inventoryDataInDb:
                    dirty = True
                    logger.info("Pod[id='%s', name='%s']: inventory changed" % (pod.id, pod.name))
                else:
                    logger.info("Pod[id='%s', name='%s']: inventory not changed" % (pod.id, pod.name))
            else:
                dirty = True
                logger.info("Pod[id='%s', name='%s']: inventory changed" % (pod.id, pod.name))
                
        if 'spineDeviceType' in podDict and pod.spineDeviceType != podDict['spineDeviceType']:
            dirty = True
            logger.info("Pod[id='%s', name='%s']: spineDeviceType changed" % (pod.id, pod.name))
            
        if 'leafDeviceType' in podDict and pod.leafDeviceType != podDict['leafDeviceType']:
            dirty = True
            logger.info("Pod[id='%s', name='%s']: leafDeviceType changed" % (pod.id, pod.name))
            
        if 'interConnectPrefix' in podDict and pod.interConnectPrefix != podDict['interConnectPrefix']:
            dirty = True
            logger.info("Pod[id='%s', name='%s']: interConnectPrefix changed" % (pod.id, pod.name))
            
        if 'vlanPrefix' in podDict and pod.vlanPrefix != podDict['vlanPrefix']:
            dirty = True
            logger.info("Pod[id='%s', name='%s']: vlanPrefix changed" % (pod.id, pod.name))
            
        if 'loopbackPrefix' in podDict and pod.loopbackPrefix != podDict['loopbackPrefix']:
            dirty = True
            logger.info("Pod[id='%s', name='%s']: loopbackPrefix changed" % (pod.id, pod.name))
            
        if 'spineAS' in podDict and pod.spineAS != podDict['spineAS']:
            dirty = True
            logger.info("Pod[id='%s', name='%s']: spineAS changed" % (pod.id, pod.name))
            
        if 'leafAS' in podDict and pod.leafAS != podDict['leafAS']:
            dirty = True
            logger.info("Pod[id='%s', name='%s']: leafAS changed" % (pod.id, pod.name))
            
        if dirty == True:
            # update pod itself
            pod.update(pod.id, pod.name, **podDict)
            pod.inventoryData = base64.b64encode(zlib.compress(json.dumps(inventoryData)))
            
            # clear existing inventory because user wants to rebuild inventory
            self.dao.deleteObjects(pod.devices)
            
            # 1. Build inventory
            spineCount = len(inventoryData['spines'])
            leafCount = len(inventoryData['leafs'])
            managementIps = util.getMgmtIps(pod.managementPrefix, spineCount + leafCount)
            for spine, managementIp in zip(inventoryData['spines'], managementIps[:spineCount]):
                spine['managementIp'] = managementIp
            for leaf, managementIp in zip(inventoryData['leafs'], managementIps[spineCount:]):
                leaf['managementIp'] = managementIp
            self.createSpineIFDs(pod, inventoryData['spines'])
            self.createLeafIFDs(pod, inventoryData['leafs'])

            # 2. Create inter-connect
            self.createLinkBetweenIfds(pod)
            
            # 3. allocate resource, ip-blocks, ASN
            self.allocateResource(pod)

            # update status
            pod.state = 'updated'
            self.dao.updateObjects([pod])

            # TODO move the backup operation to CLI 
            # backup current database
            util.backupDatabase(self.conf)
        else:
            # update pod itself
            name =  podDict.get('name')
            if name is not None:
                podDict.pop('name')
            pod.update(pod.id, name, **podDict)
            self.dao.updateObjects([pod])

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
            raise ValueError("Pod id can't be None")
            
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
            raise ValueError("Pod id can't be None")

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
                cablingPlanWriter.writeJSON()
                # create cabling plan in DOT format
                cablingPlanWriter.writeDOT()
                
                # update status
                pod.state = 'cablingDone'
                self.dao.updateObjects([pod])
    
                return True
            else:
                raise ValueError("Pod[id='%s', name='%s']: inventory is empty" % (pod.id, pod.name)) 
            
        else:
            raise ValueError("Pod id can't be None") 
            
    def createDeviceConfig(self, podId):
        '''
        Finds Pod object by id and create device configurations
        It also creates the output folders for pod
        '''
        writeConfigInFile = self.conf.get('writeConfigInFile', False)
            
        if podId is not None:
            try:
                pod = self.dao.getObjectById(Pod, podId)
            except (exc.NoResultFound):
                raise ValueError("Pod[id='%s']: not found" % (podId)) 
 
            if len(pod.devices) > 0:
                # create configuration files
                self.generateConfig(pod, writeConfigInFile)

                # update status
                pod.state = 'deviceConfigDone'
                self.dao.updateObjects([pod])
        
                return True
            else:
                raise ValueError("Pod[id='%s', name='%s']: inventory is empty" % (pod.id, pod.name)) 
        else:
            raise ValueError("Pod id can't be None") 
            
    def createSpineIFDs(self, pod, spines):
        devices = []
        interfaces = []
        for spine in spines:
            username = spine.get('username')
            password = spine.get('password')
            macAddress = spine.get('macAddress')
            managementIp = spine.get('managementIp')
            device = Device(spine['name'], pod.spineDeviceType, username, password, 'spine', macAddress, managementIp, pod)
            devices.append(device)
            
            portNames = util.getPortNamesForDeviceFamily(device.family, self.conf['deviceFamily'])
            for name in portNames['ports']:     # spine does not have any uplink/downlink marked, it is just ports
                ifd = InterfaceDefinition(name, device, 'downlink')
                interfaces.append(ifd)
        self.dao.createObjects(devices)
        self.dao.createObjects(interfaces)

    def createLeafIFDs(self, pod, leafs):
        devices = []
        interfaces = []
        for leaf in leafs:
            username = leaf.get('username')
            password = leaf.get('password')
            macAddress = leaf.get('macAddress')
            managementIp = leaf.get('managementIp')
            device = Device(leaf['name'], pod.leafDeviceType, username, password, 'leaf', macAddress, managementIp, pod)
            devices.append(device)

            portNames = util.getPortNamesForDeviceFamily(device.family, self.conf['deviceFamily'])
            for name in portNames['uplinkPorts']:   # all uplink IFDs towards spine
                ifd = InterfaceDefinition(name, device, 'uplink')
                interfaces.append(ifd)

            for name in portNames['downlinkPorts']:   # all downlink IFDs towards Access/Server
                ifd = InterfaceDefinition(name, device, 'downlink')
                interfaces.append(ifd)
        
        self.dao.createObjects(devices)
        self.dao.createObjects(interfaces)

    def createLinkBetweenIfds(self, pod):
        leaves = []
        spines = []
        for device in pod.devices:
            if (device.role == 'leaf'):
                leafUplinkPorts = self.dao.Session().query(InterfaceDefinition).filter(InterfaceDefinition.device_id == device.id).filter(InterfaceDefinition.role == 'uplink').order_by(InterfaceDefinition.name_order_num).all()
                leaves.append({'leaf': device, 'leafUplinkPorts': leafUplinkPorts})
            elif (device.role == 'spine'):
                spinePorts = self.dao.Session().query(InterfaceDefinition).filter(InterfaceDefinition.device_id == device.id).order_by(InterfaceDefinition.name_order_num).all()
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
        
    def allocateLoopback(self, pod, loopbackPrefix, devices):
        numOfIps = len(devices) + 2 # +2 for network and broadcast
        numOfBits = int(math.ceil(math.log(numOfIps, 2))) 
        cidr = 32 - numOfBits
        lo0Block = IPNetwork(loopbackPrefix + "/" + str(cidr))
        lo0Ips = list(lo0Block.iter_hosts())
        
        interfaces = []
        pod.allocatedLoopbackBlock = str(lo0Block.cidr)
        for device in devices:
            ifl = InterfaceLogical('lo0.0', device, str(lo0Ips.pop(0)) + '/32')
            interfaces.append(ifl)
        self.dao.createObjects(interfaces)

    def allocateIrb(self, pod, irbPrefix, leafs):
        numOfHostIpsPerSwitch = pod.hostOrVmCountPerLeaf
        numOfSubnets = len(leafs)
        bitsPerSubnet = int(math.ceil(math.log(numOfHostIpsPerSwitch + 2, 2)))  # +2 for network and broadcast
        cidrForEachSubnet = 32 - bitsPerSubnet

        numOfIps = (numOfSubnets * (numOfHostIpsPerSwitch + 2)) # +2 for network and broadcast
        numOfBits = int(math.ceil(math.log(numOfIps, 2))) 
        cidr = 32 - numOfBits
        irbBlock = IPNetwork(irbPrefix + "/" + str(cidr))
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
        numOfIpsPerInterconnect = 2
        numOfSubnets = len(spines) * len(leafs)
        # no need to add +2 for network and broadcast, as junos supports /31
        # TODO: it should be configurable and come from property file
        bitsPerSubnet = int(math.ceil(math.log(numOfIpsPerInterconnect, 2)))    # value is 1  
        cidrForEachSubnet = 32 - bitsPerSubnet  # value is 31 as junos supports /31

        numOfIps = (numOfSubnets * (numOfIpsPerInterconnect)) # no need to add +2 for network and broadcast
        numOfBits = int(math.ceil(math.log(numOfIps, 2))) 
        cidr = 32 - numOfBits
        interconnectBlock = IPNetwork(interConnectPrefix + "/" + str(cidr))
        interconnectSubnets = list(interconnectBlock.subnet(cidrForEachSubnet))

        interfaces = [] 
        spines[0].pod.allocatedInterConnectBlock = str(interconnectBlock.cidr)

        for spine in spines:
            ifdsHasPeer = self.dao.Session().query(InterfaceDefinition).filter(InterfaceDefinition.device_id == spine.id).filter(InterfaceDefinition.peer != None).order_by(InterfaceDefinition.name_order_num).all()
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
        
    def generateConfig(self, pod, writeConfigInFile = False):
        
        if writeConfigInFile:
            configWriter = ConfigWriter(self.conf, pod, self.dao)
        
        modifiedObjects = []

        for device in pod.devices:
            config = self.createBaseConfig(device)
            config += self.createInterfaces(device)
            config += self.createRoutingOption(device)
            config += self.createProtocolBgp(device)
            config += self.createProtocolLldp(device)
            config += self.createPolicyOption(device)
            config += self.createSnmpTrapAndEvent(device)
            config += self.createVlan(device)
            device.config = config
            modifiedObjects.append(device)
            logger.debug('Generated config for device id: %s, name: %s, storing in DB' % (device.id, device.name))
            
            if writeConfigInFile:
                configWriter.write(device)

        self.dao.updateObjects(modifiedObjects)
            
    def createBaseConfig(self, device):
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), junosTemplateLocation, 'baseTemplate.txt'), 'r') as f:
            baseTemplate = f.read()
            f.close()
            return baseTemplate

    def createInterfaces(self, device): 
        interfaceStanza = self.templateEnv.get_template('interface_stanza.txt')
        lo0Stanza = self.templateEnv.get_template('lo0_stanza.txt')
        mgmtStanza = self.templateEnv.get_template('mgmt_interface.txt')
        rviStanza = self.templateEnv.get_template('rvi_stanza.txt')
        serverInterfaceStanza = self.templateEnv.get_template('server_interface_stanza.txt')
            
        config = "interfaces {" + "\n" 
        # management interface
        config += mgmtStanza.render(mgmt_address=device.managementIp)
                
        #loopback interface
        loopbackIfl = self.dao.Session.query(InterfaceLogical).join(Device).filter(InterfaceLogical.name == 'lo0.0').filter(Device.id == device.id).one()
        config += lo0Stanza.render(address=loopbackIfl.ipaddress)
        
        # For Leaf add IRB and server facing interfaces        
        if device.role == 'leaf':
            irbIfl = self.dao.Session.query(InterfaceLogical).join(Device).filter(InterfaceLogical.name == 'irb.1').filter(Device.id == device.id).one()
            config += rviStanza.render(address=irbIfl.ipaddress)
            config += serverInterfaceStanza.render()

        # Interconnect interfaces
        deviceInterconnectIfds = self.dao.Session.query(InterfaceDefinition).join(Device).filter(InterfaceDefinition.peer != None).filter(Device.id == device.id).order_by(InterfaceDefinition.name_order_num).all()
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

    def createRoutingOption(self, device):
        routingOptionStanza = self.templateEnv.get_template('routing_options_stanza.txt')

        loopbackIfl = self.dao.Session.query(InterfaceLogical).join(Device).filter(InterfaceLogical.name == 'lo0.0').filter(Device.id == device.id).one()
        loopbackIpWithNoCidr = loopbackIfl.ipaddress.split('/')[0]
        
        oobNetworks = device.pod.outOfBandAddressList
        if oobNetworks is not None:
            oobNetworkList = oobNetworks.split(',')
        else:
            oobNetworkList = []
        gateway = util.loadClosDefinition()['ztp']['dhcpOptionRoute']
        
        return routingOptionStanza.render(routerId=loopbackIpWithNoCidr, asn=str(device.asn), oobNetworks=oobNetworkList, gateway=gateway)

    def createProtocolBgp(self, device):
        template = self.templateEnv.get_template('protocolBgp.txt')

        neighborList = []
        deviceInterconnectIfds = self.dao.Session.query(InterfaceDefinition).join(Device).filter(InterfaceDefinition.peer != None).filter(Device.id == device.id).order_by(InterfaceDefinition.name_order_num).all()
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
            deviceLoopbackIfl = self.dao.Session.query(InterfaceLogical).join(Device).filter(InterfaceLogical.name == 'lo0.0').filter(Device.id == device.id).one()
            deviceIrbIfl = self.dao.Session.query(InterfaceLogical).join(Device).filter(InterfaceLogical.name == 'irb.1').filter(Device.id == device.id).one()
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
        if (util.isIntegratedWithND(self.conf)):
            ndSnmpTrapConf = snmpTrapConf.get('networkdirector_trap_group') 
            if ndSnmpTrapConf is None:
                logger.error('No SNMP Trap setting found for ND')
                return
            
            return {'name': 'networkdirector_trap_group', 'port': ndSnmpTrapConf['port'], 'targetIp': ndSnmpTrapConf['target'] }
        return
    
    def createSnmpTrapAndEvent(self, device):
        snmpTrapConf = self.conf.get('snmpTrap')
        if snmpTrapConf is None:
            logger.error('No SNMP Trap setting found on openclos.yaml')
            return ''
        
        snmpTemplate = self.templateEnv.get_template('snmpTrap.txt')
        trapEventTemplate = self.templateEnv.get_template('eventOptionForTrap.txt')
        
        configlet = trapEventTemplate.render()
        
        if device.role == 'leaf':
            openclosSnmpTrapConf = snmpTrapConf.get('openclos_trap_group') 
            if openclosSnmpTrapConf is None:
                logger.error('No SNMP Trap setting found for OpenClos')

            openClosGroup = {'name': 'openclos_trap_group', 'port': openclosSnmpTrapConf['port'], 'targetIp': openclosSnmpTrapConf['target'] }
            groups = [openClosGroup]
            
            ndGroup = self.getNdTrapGroupSettings()
            if ndGroup is not None:
                groups.append(ndGroup)
                
            configlet += snmpTemplate.render(trapGroups = groups)
            return configlet

        elif device.role == 'spine':
            ndGroup = self.getNdTrapGroupSettings()
            if ndGroup is not None:
                configlet += snmpTemplate.render(trapGroups = [ndGroup])
                return configlet

        return ''
        
if __name__ == '__main__':
    l3ClosMediation = L3ClosMediation()
    pods = l3ClosMediation.loadClosDefinition()

    pod1 = l3ClosMediation.createPod('labLeafSpine', pods['labLeafSpine'])
    l3ClosMediation.createCablingPlan(pod1.id)
    l3ClosMediation.createDeviceConfig(pod1.id)

    pod2 = l3ClosMediation.createPod('anotherPod', pods['anotherPod'])
    l3ClosMediation.createCablingPlan(pod2.id)
    l3ClosMediation.createDeviceConfig(pod2.id)
