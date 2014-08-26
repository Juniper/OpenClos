'''
Created on May 23, 2014

@author: moloyc
'''

import yaml
import os
import json
import math
from netaddr import IPNetwork
from jnpr.openclos.model import Pod, Device, Interface, InterfaceLogical, InterfaceDefinition, Base
import sqlalchemy
from sqlalchemy.orm import sessionmaker, scoped_session, exc
from jinja2 import Environment, PackageLoader
from jnpr.openclos.dotHandler import createDOTFile

configLocation = os.path.dirname(os.path.abspath(__file__)) + '/conf/'
#configLocation =  'conf/'
junosTemplateLocation = configLocation + 'junosTemplates/'

def loadConfig(confFile = 'openclos.yaml'):
    '''
    Loads global configuration and creates hash 'conf'
    '''
    try:
        confStream = open(configLocation + confFile, 'r')
        conf = yaml.load(confStream)
        
    except (OSError, IOError) as e:
        print "File error:", e
        return None
    except (yaml.scanner.ScannerError) as e:
        print "YAML error:", e
        confStream.close()
        return None
    finally:
        pass
    return conf

class Dao:
    def __init__(self, conf):
        if conf is not None and 'dbUrl' in conf:
            #Change "echo=True" to troubleshoot ORM issue
            engine = sqlalchemy.create_engine(conf['dbUrl'], echo=False)  
            Base.metadata.create_all(engine) 
            session_factory = sessionmaker(bind=engine)
            self.Session = scoped_session(session_factory)
        else:
            raise ValueError("Missing configuration parameter:'dbUrl'")
        
    # Don't remove session after each operation, it detaches the object from ORM,
    # which disables further operations on the object like lazy load of collection.
    # When thread dies, it gets GCed automatically
    def createObjects(self, objects):
        session = self.Session()
        try:
            session.add_all(objects)
            session.commit()
        finally:
            #self.Session.remove()
            pass
    
    def updateObjects(self, objects):
        session = self.Session()
        try:
            for obj in objects:
                session.merge(obj)
            session.commit()
        finally:
            #self.Session.remove()
            pass
    def getAll(self, objectType):
        session = self.Session()
        try:
            return session.query(objectType).order_by(objectType.name).all()
        finally:
            #self.Session.remove()
            pass

    def getUniqueObjectByName(self, objectType, name):
        session = self.Session()
        try:
            return session.query(objectType).filter_by(name = name).one()
        finally:
            #self.Session.remove()
            pass

    def getObjectsByName(self, objectType, name):
        session = self.Session()
        try:
            return session.query(objectType).filter_by(name = name).all()
        finally:
            #self.Session.remove()
            pass

class FileOutputHandler():
    def __init__(self, conf, pod):
        if 'outputDir' in conf:
            self.outputDir = conf['outputDir'] + '/' + pod.name
        else:
            self.outputDir = 'out/' + pod.name
        if not os.path.exists(self.outputDir):
            os.makedirs(self.outputDir)

    def handle(self, pod, device, config):
        print "Writing config for device: %s" % (device.name)
        with open(self.outputDir + "/" + device.name + '.conf', 'w') as f:
                f.write(config)

class L3ClosMediation():
    def __init__(self, conf = {}, templateEnv = None):
        if any(conf) == False:
            self.conf = loadConfig()
        else:
            self.conf = conf
        self.dao = Dao(self.conf)
        if templateEnv is None:
            self.templateEnv = Environment(loader=PackageLoader('jnpr.openclos', junosTemplateLocation))
        
        
    def loadClosDefinition(self, closDefination = configLocation + 'closTemplate.yaml'):
        '''
        Loads clos definition from yaml file and creates pod object
        '''
        try:
            stream = open(closDefination, 'r')
            yamlStream = yaml.load(stream)
            
            self.createPods(yamlStream['pods'])
        except (OSError, IOError) as e:
            print "File error:", e
        except (yaml.scanner.ScannerError) as e:
            print "YAML error:", e
            stream.close()
        finally:
            pass
       
    def createPods(self, podsDict):
        pods = []
        for name, pod in podsDict.iteritems():
            localPod = Pod(name, **pod)
            localPod.validate()
            pods.append(localPod)
        self.dao.createObjects(pods)

    def processTopology(self, podName):
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
 
        if pod.topology is not None:
            json_data = open(configLocation + pod.topology)
            data = json.load(json_data)
            json_data.close()    
            
            self.createSpineIFDs(pod, data['spines'])
            self.createLeafIFDs(pod, data['leafs'])
            self.createLinkBetweenIFDs(pod, data['links'])
            self.allocateResource(pod)
            self.output = FileOutputHandler(self.conf, pod)
            self.generateConfig(pod)
            self.generateDOTFile(pod)

        else:
            raise ValueError("No topology found for pod name: '%s'", (podName))

    def createSpineIFDs(self, pod, spines):
        devices = []
        interfaces = []
        for spine in spines:
            device = Device(spine['name'], spine['user'], spine['password'], 'spine', spine['mgmt_ip'], pod)
            devices.append(device)
            # all downlink IFDs towards leaf
            # TODO: range value and idfname should come from property file
            for num in range(0, 24):
                ifd = InterfaceDefinition("et-0/0/" + str(num), device, 'downlink')
                interfaces.append(ifd)
        self.dao.createObjects(devices)
        self.dao.createObjects(interfaces)

    def createLeafIFDs(self, pod, leafs):
        devices = []
        interfaces = []
        for leaf in leafs:
            device = Device(leaf['name'], leaf['user'], leaf['password'], 'leaf', leaf['mgmt_ip'], pod)
            devices.append(device)
            # TODO: range value and idfname should come from property file
            # all uplink IFDs towards spine
            for num in range(48, 54):
                ifd = InterfaceDefinition("et-0/0/" + str(num), device, 'uplink')
                interfaces.append(ifd)
            # all downlink IFDs towards server
            for num in range(0, 48):
                ifd = InterfaceDefinition("xe-0/0/" + str(num), device, 'downlink')
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
        numOfHostIpsPerSwitch = 254     #TODO: should come from property file
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
        for leaf in leafs:
            leaf.asn = leafAsn
            leafAsn += 1
            devices.append(leaf)
        self.dao.updateObjects(devices)

    def generateConfig(self, pod):
        for device in pod.devices:
            config = self.createBaseConfig(device)
            config += self.createInterfaces(device)
            config += self.createRoutingOption(device)
            config += self.createProtocols(device)
            config += self.createPolicyOption(device)
            config += self.createVlan(device)
            self.output.handle(pod, device, config)
            
    def generateDOTFile(self, pod): 
        createDOTFile(pod.devices)
            
    def createBaseConfig(self, device):
        with open(junosTemplateLocation + 'baseTemplate.txt', 'r') as f:
            baseTemplate = f.read()
            f.close()
            return baseTemplate

    def createInterfaces(self, device): 
        with open(junosTemplateLocation + 'interface_stanza.txt', 'r') as f:
            interfaceStanza = f.read()
            f.close()
        
        with open(junosTemplateLocation + 'lo0_stanza.txt', 'r') as f:
            lo0Stanza = f.read()
            f.close()
            
        with open(junosTemplateLocation + 'mgmt_interface.txt', 'r') as f:
            mgmtStanza = f.read()
            f.close()

        with open(junosTemplateLocation + 'rvi_stanza.txt', 'r') as f:
            rviStanza = f.read()
            f.close()
            
        with open(junosTemplateLocation + 'server_interface_stanza.txt', 'r') as f:
            serverInterfaceStanza = f.read()
            f.close()
            
        config = "interfaces {" + "\n" 
        # management interface
        candidate = mgmtStanza.replace("<<<mgmt_address>>>", device.managementIp)
        config += candidate
                
        #loopback interface
        loopbackIfl = self.dao.Session.query(InterfaceLogical).join(Device).filter(InterfaceLogical.name == 'lo0.0').filter(Device.id == device.id).one()
        candidate = lo0Stanza.replace("<<<address>>>", loopbackIfl.ipaddress)
        config += candidate

        # For Leaf add IRB and server facing interfaces        
        if device.role == 'leaf':
            irbIfl = self.dao.Session.query(InterfaceLogical).join(Device).filter(InterfaceLogical.name == 'irb.1').filter(Device.id == device.id).one()
            candidate = rviStanza.replace("<<<address>>>", irbIfl.ipaddress)
            config += candidate
            config += serverInterfaceStanza

        # Interconnect interfaces
        deviceInterconnectIfds = self.dao.Session.query(InterfaceDefinition).join(Device).filter(InterfaceDefinition.peer != None).filter(Device.id == device.id).order_by(InterfaceDefinition.name).all()
        for interconnectIfd in deviceInterconnectIfds:
            peerDevice = interconnectIfd.peer.device
            interconnectIfl = interconnectIfd.layerAboves[0]
            namePlusUnit = interconnectIfl.name.split('.')  # example et-0/0/0.0
            candidate = interfaceStanza.replace("<<<ifd_name>>>", namePlusUnit[0])
            candidate = candidate.replace("<<<unit>>>", namePlusUnit[1])
            candidate = candidate.replace("<<<description>>>", "facing_" + peerDevice.name)
            candidate = candidate.replace("<<<address>>>", interconnectIfl.ipaddress)
            config += candidate
                
        config += "}\n"
        return config

    def createRoutingOption(self, device):
        with open(junosTemplateLocation + 'routing_options_stanza.txt', 'r') as f:
            routingOptionStanza = f.read()

        loopbackIfl = self.dao.Session.query(InterfaceLogical).join(Device).filter(InterfaceLogical.name == 'lo0.0').filter(Device.id == device.id).one()
        loopbackIpWithNoCidr = loopbackIfl.ipaddress.split('/')[0]
        
        candidate = routingOptionStanza.replace("<<<routerId>>>", loopbackIpWithNoCidr)
        candidate = candidate.replace("<<<asn>>>", str(device.asn))
        
        return candidate

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
    l3ClosMediation.loadClosDefinition()
    l3ClosMediation.processTopology('labLeafSpine')

