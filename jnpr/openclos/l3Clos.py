'''
Created on May 23, 2014

@author: moloyc
'''

import yaml
import os
import json
import math
import logging

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
       
    def isRecreateFabric(self, podInDb, podDict):
        '''
        If any device type/family, ASN range or IP block changed, that would require 
        re-generation of the fabric, causing new set of IP and ASN assignment per device
        '''
        if (podInDb.spineDeviceType != podDict['spineDeviceType'] or \
            podInDb.leafDeviceType != podDict['leafDeviceType'] or \
            podInDb.interConnectPrefix != podDict['interConnectPrefix'] or \
            podInDb.vlanPrefix != podDict['vlanPrefix'] or \
            podInDb.loopbackPrefix != podDict['loopbackPrefix'] or \
            podInDb.spineAS != podDict['spineAS'] or \
            podInDb.leafAS != podDict['leafAS']): 
            return True
        return False
        
    def processFabric(self, podName, pod, reCreateFabric = False):
        # REVISIT use of reCreateFabric
        try:
            podInDb = self.dao.getUniqueObjectByName(Pod, podName)
        except (exc.NoResultFound) as e:
            logger.debug("No Pod found with pod name: '%s', exc.NoResultFound: %s" % (podName, e.message)) 
        else:
            logger.debug("Deleted existing pod name: '%s'" % (podName))     
            self.dao.deleteObject(podInDb)
            
        podInDb = Pod(podName, **pod)
        podInDb.validate()
        self.dao.createObjects([podInDb])
        logger.info("Created pod name: '%s'" % (podName))     
        self.processTopology(podName, reCreateFabric)

        # backup current database
        util.backupDatabase(self.conf)
           
        return podInDb
    
    def processTopology(self, podName, reCreateFabric = False):
        '''
        Finds Pod object by name and process topology
        It also creates the output folders for pod
        '''
        try:
            pod = self.dao.getUniqueObjectByName(Pod, podName)
        except (exc.NoResultFound) as e:
            raise ValueError("No Pod found with pod name: '%s', exc.NoResultFound: %s" % (podName, e.message))
        except (exc.MultipleResultsFound) as e:
            raise ValueError("Multiple Pods found with pod name: '%s', exc.MultipleResultsFound: %s" % (podName, e.message))
 
        if pod.inventory is not None:
            # topology handling is divided into 3 steps:
            # 1. load inventory
            # 2. create cabling plan 
            # 3. create configuration files

            # 1. load inventory
            json_inventory = open(os.path.join(util.configLocation, pod.inventory))
            inventory = json.load(json_inventory)
            json_inventory.close()    
            self.createSpineIFDs(pod, inventory['spines'])
            self.createLeafIFDs(pod, inventory['leafs'])

            # 2. create cabling plan in JSON format
            cablingPlanWriter = CablingPlanWriter(self.conf, pod, self.dao)
            cablingPlanJSON = cablingPlanWriter.writeJSON()
            # 2. create cabling plan in DOT format
            cablingPlanWriter.writeDOT()
            
            # 3. create configuration files
            self.createLinkBetweenIFDs(pod, cablingPlanJSON['links'])
            self.allocateResource(pod)
            self.generateConfig(pod);
            
            return True
        else:
            raise ValueError("No topology found for pod name: '%s'", (podName))

    def createSpineIFDs(self, pod, spines):
        devices = []
        interfaces = []
        for spine in spines:
            user = spine.get('user')
            password = spine.get('pass')
            device = Device(spine['name'], pod.spineDeviceType, user, password, 'spine', spine['mac_address'], spine['mgmt_ip'], pod)
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
            user = leaf.get('user')
            password = leaf.get('pass')
            device = Device(leaf['name'], pod.leafDeviceType, user, password, 'leaf', leaf['mac_address'], leaf['mgmt_ip'], pod)
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

    def createLinkBetweenIFDs(self, pod, links):
        # Caching all interfaces by deviceName...interfaceName for easier lookup
        interfaces = {}
        modifiedObjects = []
        for device in pod.devices:
            for interface in device.interfaces:
                name = device.name + '...' + interface.name
                interfaces[name] = interface

        for link in links:
            spineIntf = interfaces[link['s_name'] + '...' + link['s_port']]
            leafIntf = interfaces[link['l_name'] + '...' + link['l_port']]
            # hack to add relation from both sides as on ORM it is oneway one-to-one relation
            spineIntf.peer = leafIntf
            leafIntf.peer = spineIntf
            modifiedObjects.append(spineIntf)
            modifiedObjects.append(leafIntf)
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
            ifdsHasPeer = self.dao.Session().query(InterfaceDefinition).filter(InterfaceDefinition.device_id == spine.id).filter(InterfaceDefinition.peer != None).order_by(InterfaceDefinition.name).all()
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
        for device in pod.devices:
            config = self.createBaseConfig(device)
            config += self.createInterfaces(device)
            config += self.createRoutingOption(device)
            config += self.createProtocols(device)
            config += self.createPolicyOption(device)
            config += self.createVlan(device)
            configWriter.write(device, config)
            
    def createBaseConfig(self, device):
        with open(os.path.join(junosTemplateLocation, 'baseTemplate.txt'), 'r') as f:
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
        deviceInterconnectIfds = self.dao.Session.query(InterfaceDefinition).join(Device).filter(InterfaceDefinition.peer != None).filter(Device.id == device.id).order_by(InterfaceDefinition.name).all()
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
        
        return routingOptionStanza.render(routerId=loopbackIpWithNoCidr, asn=str(device.asn))

    def createProtocols(self, device):
        template = self.templateEnv.get_template('protocolBgpLldp.txt')

        neighborList = []
        deviceInterconnectIfds = self.dao.Session.query(InterfaceDefinition).join(Device).filter(InterfaceDefinition.peer != None).filter(Device.id == device.id).order_by(InterfaceDefinition.name).all()
        for ifd in deviceInterconnectIfds:
            peerIfd = ifd.peer
            peerDevice = peerIfd.device
            peerInterconnectIfl = peerIfd.layerAboves[0]
            peerInterconnectIpNoCidr = peerInterconnectIfl.ipaddress.split('/')[0]
            neighborList.append({'peer_ip': peerInterconnectIpNoCidr, 'peer_asn': peerDevice.asn})

        return template.render(neighbors=neighborList)        
         
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
        
if __name__ == '__main__':
    l3ClosMediation = L3ClosMediation()
    pods = l3ClosMediation.loadClosDefinition()
    l3ClosMediation.processFabric('labLeafSpine', pods['labLeafSpine'], reCreateFabric = True)
    l3ClosMediation.processFabric('anotherPod', pods['anotherPod'], reCreateFabric = True)

