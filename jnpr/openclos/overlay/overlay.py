'''
Created on Nov 23, 2015

@author: yunli
'''

import logging
import os
import itertools
from netaddr import IPNetwork

from jnpr.openclos.exception import OverlayDeviceNotFound
from jnpr.openclos.overlay.overlayModel import OverlayFabric, OverlayTenant, OverlayVrf, OverlayNetwork, OverlaySubnet, OverlayDevice, OverlayL3port, OverlayL2port, OverlayAggregatedL2port, OverlayAggregatedL2portMember, OverlayDeployStatus
from jnpr.openclos.loader import loadLoggingConfig
from jnpr.openclos.dao import Dao
from jnpr.openclos.templateLoader import TemplateLoader
from jnpr.openclos.overlay.overlayCommit import OverlayCommitQueue

moduleName = 'overlay'
loadLoggingConfig(appName=moduleName)
logger = logging.getLogger(moduleName)
esiRouteTarget = "9999:9999"

class Overlay():
    def __init__(self, conf, dao, commitQueue=None):
        self._conf = conf
        self._dao = dao
        self._configEngine = ConfigEngine(conf, dao, commitQueue)
    def createDevice(self, dbSession, name, description, role, address, routerId, podName, username, password):
        '''
        Create a new Device
        '''
        device = OverlayDevice(name, description, role, address, routerId, podName, username, password)

        self._dao.createObjects(dbSession, [device])
        logger.info("OverlayDevice[id: '%s', name: '%s']: created", device.id, device.name)
        return device

    def createFabric(self, dbSession, name, description, overlayAsn, routeReflectorAddress, devices):
        '''
        Create a new Fabric
        '''
        fabric = OverlayFabric(name, description, overlayAsn, routeReflectorAddress, devices)

        self._dao.createObjects(dbSession, [fabric])
        logger.info("OverlayFabric[id: '%s', name: '%s']: created", fabric.id, fabric.name)
        self._configEngine.configureFabric(dbSession, fabric)
        return fabric

    def createTenant(self, dbSession, name, description, overlay_fabric):
        '''
        Create a new Tenant
        '''
        tenant = OverlayTenant(name, description, overlay_fabric)

        self._dao.createObjects(dbSession, [tenant])
        logger.info("OverlayTenant[id: '%s', name: '%s']: created", tenant.id, tenant.name)
        return tenant

    def createVrf(self, dbSession, name, description, routedVnid, loopbackAddress, overlayTenant):
        '''
        Create a new Vrf
        '''
        vrf = OverlayVrf(name, description, routedVnid, loopbackAddress, overlayTenant)
        vrf.vrfCounter = self._dao.incrementAndGetCounter("OverlayVrf.vrfCounter")

        self._dao.createObjects(dbSession, [vrf])
        logger.info("OverlayVrf[id: '%s', name: '%s']: created", vrf.id, vrf.name)
        self._configEngine.configureVrf(dbSession, vrf)
        return vrf

    def createNetwork(self, dbSession, name, description, overlay_vrf, vlanid, vnid, pureL3Int):
        '''
        Create a new Network
        '''
        network = OverlayNetwork(name, description, overlay_vrf, vlanid, vnid, pureL3Int)

        self._dao.createObjects(dbSession, [network])
        logger.info("OverlayNetwork[id: '%s', name: '%s']: created", network.id, network.name)
        self._configEngine.configureNetwork(dbSession, network)
        return network

    def createSubnet(self, dbSession, name, description, overlay_network, cidr):
        '''
        Create a new Subnet
        '''
        subnet = OverlaySubnet(name, description, overlay_network, cidr)

        self._dao.createObjects(dbSession, [subnet])
        logger.info("OverlaySubnet[id: '%s', name: '%s']: created", subnet.id, subnet.name)
        self._configEngine.configureSubnet(dbSession, subnet)
        return subnet

    def createL3port(self, dbSession, name, description, overlay_subnet):
        '''
        Create a new L3port
        '''
        l3port = OverlayL3port(name, description, overlay_subnet)

        self._dao.createObjects(dbSession, [l3port])
        logger.info("OverlayL3port[id: '%s', name: '%s']: created", l3port.id, l3port.name)
        return l3port

    def createL2port(self, dbSession, name, description, overlay_networks, interface, overlay_device):
        '''
        Create a new L2port
        '''
        l2port = OverlayL2port(name, description, overlay_networks, interface, overlay_device)

        self._dao.createObjects(dbSession, [l2port])
        logger.info("OverlayL2port[id: '%s', name: '%s']: created", l2port.id, l2port.name)
        self._configEngine.configureL2port(dbSession, l2port)
        return l2port

    def _validateAggregatedL2port(self, dbSession, name, members):
        # We need to validate 2 cases:
        # 1. Reject if another aggregatedL2port with the same name already has member on the same device.
        #    E.g. If there is already an aggregatedL2port ae0 has a member on device1, you can't create another 
        #    ae0 with member on device1. The reason is the aggregatedL2port in OpenClos is used for dual-homing.
        #    So ae0 is supposed to have 1 member only on each device.
        # 2. Reject if the member is already being used.
        #    E.g. If device1:xe-0/0/1 is already a member of another aggregatedL2port or it has been
        #    configured as a l2port, we can't use device1:xe-0/0/1.
        
        # Check case 1
        existingObject = dbSession.query(OverlayAggregatedL2port).filter(OverlayAggregatedL2port.name == name).first()
        if existingObject is not None:
            for memberDict in members:
                for existingMember in existingObject.members:
                    if memberDict['device'].id == existingMember.overlay_device.id:
                        raise ValueError('Anoter aggregatedL2port %s already has member %s on device %s' % (name, existingMember.interface, existingMember.overlay_device.name))
                        
        # Check case 2
        for memberDict in members:
            if dbSession.query(OverlayAggregatedL2portMember).filter(
                OverlayAggregatedL2portMember.overlay_device_id == memberDict['device'].id).filter(
                OverlayAggregatedL2portMember.interface == memberDict['interface']).count() > 0:
                raise ValueError('Member %s:%s is in used in another aggregatedL2port' % (memberDict['device'].name, memberDict['interface']))
            if dbSession.query(OverlayL2port).filter(
                OverlayL2port.overlay_device_id == memberDict['device'].id).filter(
                OverlayL2port.interface == memberDict['interface']).count() > 0:
                raise ValueError('Member %s:%s is in used in another l2port' % (memberDict['device'].name, memberDict['interface']))
                
    def createAggregatedL2port(self, dbSession, name, description, overlay_networks, members, esi, lacp):
        '''
        Create a new AggregatedL2port
        '''
        self._validateAggregatedL2port(dbSession, name, members)
        
        aggregatedL2port = OverlayAggregatedL2port(name, description, overlay_networks, esi, lacp)

        self._dao.createObjects(dbSession, [aggregatedL2port])
        logger.info("OverlayAggregatedL2port[id: '%s', name: '%s']: created", aggregatedL2port.id, aggregatedL2port.name)
        
        # add members
        memberObjects = []
        for memberDict in members:
            memberObject = OverlayAggregatedL2portMember(memberDict['interface'], memberDict['device'], aggregatedL2port)
            logger.info("OverlayAggregatedL2portMember[id: '%s', device: '%s', interface: '%s']: created", memberObject.id, memberObject.overlay_device.name, memberObject.interface)
            memberObjects.append(memberObject)

        self._dao.createObjects(dbSession, memberObjects)
        self._configEngine.configureAggregatedL2port(dbSession, aggregatedL2port)
        
        return aggregatedL2port
        
    def modifyAggregatedL2port(self, dbSession, aggregatedL2port, name, description, overlay_networks, members, esi, lacp):
        '''
        Modify a new AggregatedL2port
        '''
        aggregatedL2port.update(name, description, overlay_networks, esi, lacp)

        # add members
        memberObjects = []
        for memberDict in members:
            memberObject = OverlayAggregatedL2portMember(memberDict['interface'], memberDict['device'], aggregatedL2port)
            logger.info("OverlayAggregatedL2portMember[id: '%s', device: '%s', interface: '%s']: created", memberObject.id, memberObject.overlay_device.name, memberObject.interface)
            memberObjects.append(memberObject)

        self._dao.createObjects(dbSession, memberObjects)
        
        return aggregatedL2port
        
    def deleteL2port(self, dbSession, l2Port):
        '''
        Delete L2port from device, if success then from DB
        '''
        logger.info("OverlayL2port[id: '%s', name: '%s']: delete request submitted", l2Port.id, l2Port.name)
        self._configEngine.deleteL2port(dbSession, l2Port)

    def deleteAggregatedL2port(self, dbSession, aggregatedL2port):
        '''
        Delete Aggregated L2 port from device, if success then from DB
        '''
        logger.info("OverlayAggregatedL2port[id: '%s', name: '%s']: delete request submitted", aggregatedL2port.id, aggregatedL2port.name)
        self._configEngine.deleteAggregatedL2port(dbSession, aggregatedL2port)

    def deleteSubnet(self, dbSession, subnet):
        '''
        Delete subnet from device
        '''
        logger.info("Subnet[id: '%s', cidr: '%s']: delete request submitted", subnet.id, subnet.name)
        self._configEngine.deleteSubnet(dbSession, subnet)

    def deleteNetwork(self, dbSession, network):
        '''
        Delete network from device, also delete subnet and all l2Ports attached to the network
        '''
        logger.info("Network[id: '%s', name: '%s']: delete request submitted", network.id, network.name)
        for port in network.overlay_l2aps:
            if type(port) is OverlayL2port:
                self.deleteL2port(dbSession, port)
            elif type(port) is OverlayAggregatedL2port:
                self.deleteAggregatedL2port(dbSession, port)
        for subnet in network.overlay_subnets:
            self.deleteSubnet(dbSession, subnet)
        self._configEngine.deleteNetwork(dbSession, network)

    def deleteVrf(self, dbSession, vrf):
        '''
        Delete vrf rom device, also delete network, subnet ports etc.
        '''
        logger.info("vrf[id: '%s', name: '%s']: delete request submitted", vrf.id, vrf.name)
        for network in vrf.overlay_networks:
            self.deleteNetwork(dbSession, network)
        self._configEngine.deleteVrf(dbSession, vrf)

    def deleteTenant(self, dbSession, tenant):
        '''
        Delete tenant from device, also vrf, delete network, subnet ports etc.
        '''
        logger.info("tenant[id: '%s', name: '%s']: delete request submitted", tenant.id, tenant.name)
        for vrf in tenant.overlay_vrfs:
            self.deleteVrf(dbSession, vrf)
        # Delete the tenant itself
        self._dao.deleteObject(dbSession, tenant)
        
    def deleteFabric(self, dbSession, fabric):
        '''
        Delete fabric from device, also vrf, delete network, subnet ports etc.
        '''
        logger.info("fabric[id: '%s', name: '%s']: delete request submitted", fabric.id, fabric.name)
        for tenant in fabric.overlay_tenants:
            for vrf in tenant.overlay_vrfs:
                self.deleteVrf(dbSession, vrf)
        self._configEngine.deleteFabric(dbSession, fabric)

    def _checkDeviceDependency(self, dbSession, deviceObject):
        # Find l2port or aggregatedL2port on this device and the VRF they belong to.
        vrfs = []
        l2portObject = dbSession.query(OverlayL2port).filter(OverlayL2port.overlay_device_id == deviceObject.id).first()
        if l2portObject is not None:
            vrfs.append(l2portObject.overlay_network.overlay_vrf)
        aggregatedL2portMemberObject = dbSession.query(OverlayAggregatedL2portMember).filter(OverlayAggregatedL2portMember.overlay_device_id == deviceObject.id).first()
        if aggregatedL2portMemberObject is not None:
            vrfs.append(aggregatedL2portMemberObject.overlay_aggregatedL2port.overlay_network.overlay_vrf)
        
        if deviceObject.role == 'spine':
            for vrf in vrfs:
                if deviceObject in vrf.overlay_tenant.overlay_fabric.overlay_devices:
                    raise ValueError('Spine device %s has a VRF which contains active L2 port or aggregated L2 port. Please delete L2 port/aggregated L2 port explicitly first' % deviceId)
        elif deviceObject.role == 'leaf':
            if len(vrfs) > 0:
                raise ValueError('Leaf device %s has active L2 port or aggregated L2 port. Please delete L2 port/aggregated L2 port explicitly first' % deviceId)

    def deleteDevice(self, dbSession, device):
        # Validate if there is l2port or aggregatedL2port active on this device.
        # If there is, this request will fail with 500. User needs to delete l2port/aggregatedL2port explicitly 
        # and then try to delete device again.
        self._checkDeviceDependency(dbSession, device)
        self._dao.deleteObject(dbSession, device)
        logger.info("device[id: '%s', name: '%s']: deleted", device.id, device.name)
            
class ConfigEngine():
    def __init__(self, conf, dao, commitQueue=None):
        self._conf = conf
        self._dao = dao
        self._templateLoader = TemplateLoader(junosTemplatePackage="jnpr.openclos.overlay")
        if commitQueue:
            self._commitQueue = commitQueue
        else:
            self._commitQueue = OverlayCommitQueue.getInstance()
        

    def configureFabric(self, dbSession, fabric):
        '''
        Generate iBGP config
        '''
        
        spineTemplate = self._templateLoader.getTemplate('olAddProtocolBgpSpine.txt')
        leafTemplate = self._templateLoader.getTemplate('olAddProtocolBgpLeaf.txt')
        deployments = []        
        for device in fabric.overlay_devices:
            config = self.configureRoutingOptions(device)
            config += self.configureSwitchOptions(device.routerId)

            if device.role == 'spine':
                config += spineTemplate.render(routerId=device.routerId, asn=fabric.overlayAS, 
                            podLeafs=[l.routerId for l in fabric.getPodLeafs(device.podName)], 
                            allSpines=[s.routerId for s in fabric.getSpines() if s != device], 
                            routeReflector=fabric.routeReflectorAddress)
            elif device.role == 'leaf':
                config += leafTemplate.render(routerId=device.routerId, asn=fabric.overlayAS, 
                            podSpines=[s.routerId for s in fabric.getPodSpines(device.podName)],
                            remoteGateways=self.getRemoteGateways(fabric, device.podName))
            config += self.configureFabricPolicyOptions(fabric, device)
            config += self.configureEvpn()
            
            deployments.append(OverlayDeployStatus(config, fabric.getUrl(), "create", device, fabric))    

        self._dao.createObjects(dbSession, deployments)
        logger.info("configureFabric [id: '%s', name: '%s']: configured", fabric.id, fabric.name)
        self._commitQueue.addJobs(deployments)
    
    def getRemoteGateways(self, fabric, podName):
        allSpines = set(fabric.getSpines())
        podSpines = set(fabric.getPodSpines(podName))
        remoteGatewayDevices = allSpines.difference(podSpines)
        if remoteGatewayDevices:
            return [d.routerId for d in remoteGatewayDevices]

    def configureRoutingOptions(self, device):
        if device.role == 'spine':
            template = self._templateLoader.getTemplate('olAddRoutingOptions.txt')
            return template.render(routerId=device.routerId)
        else:
            return ""
        
    def configureSwitchOptions(self, routerId):
        template = self._templateLoader.getTemplate('olAddSwitchOptions.txt')
        return template.render(routerId=routerId, esiRouteTarget=esiRouteTarget)

    def configureFabricPolicyOptions(self, fabric, device):
        template = self._templateLoader.getTemplate('olAddPolicyOptions.txt')
        if device.role == 'spine':
            return template.render(esiRTarget=esiRouteTarget)
        else:
            return template.render(remoteGateways=self.getRemoteGateways(fabric, device.podName), esiRTarget=esiRouteTarget)
        
    def configureNetworkPolicyOptions(self, vni=None, asn=None):
        template = self._templateLoader.getTemplate('olAddPolicyOptions.txt')
        return template.render(vni=vni, asn=asn)

    def configureVrf(self, dbSession, vrf):
        deployments = []
        loopbackIps = self.getLoopbackIps(vrf.loopbackAddress)
        spines = vrf.getSpines()
        
        if len(loopbackIps) < len(spines):
            logger.error("configureVrf [id: '%s', name: '%s']: loopback IPs count: %d less than spine count: %d", 
                         vrf.id, vrf.name, len(loopbackIps), len(spines))
            
        template = self._templateLoader.getTemplate('olAddVrf.txt')
        for spine, loopback in itertools.izip(spines, loopbackIps):
            config = self.configureLoopback(loopback, vrf.vrfCounter)
            
            config += template.render(vrfName=vrf.name,  vrfCounter=vrf.vrfCounter,
                routerId=spine.routerId, asn=vrf.overlay_tenant.overlay_fabric.overlayAS)
            deployments.append(OverlayDeployStatus(config, vrf.getUrl(), "create", spine, vrf.overlay_tenant.overlay_fabric))    

        self._dao.createObjects(dbSession, deployments)
        logger.info("configureVrf [id: '%s', name: '%s']: configured", vrf.id, vrf.name)
        self._commitQueue.addJobs(deployments)

    def getLoopbackIps(self, loopbackBlock):
        '''
        returns all IPs from the CIRD including network and broadcast
        '''
        loopback = IPNetwork(loopbackBlock)
        first = str(loopback.network) + "/32"
        last = str(loopback.broadcast) + "/32"
        hosts = [str(ip) + "/32" for ip in loopback.iter_hosts()]
        if loopback.size > 2:
            return [first] + hosts + [last]
        else:
            return hosts
        
    def configureLoopback(self, loopbackIp, loopbackUnit):
        template = self._templateLoader.getTemplate('olAddLoopback.txt')
        return template.render(loopbackUnit=loopbackUnit, loopbackAddress=loopbackIp)


    def configureNetwork(self, dbSession, network):
        '''
        Create IRB, BD, update VRF, update evpn, update policy
        '''
        deployments = []        
        vrf = network.overlay_vrf
        asn = vrf.overlay_tenant.overlay_fabric.overlayAS

        irbTemplate = self._templateLoader.getTemplate("olAddIrb.txt")
        vrfTemplate = self._templateLoader.getTemplate("olAddVrf.txt")
        bdTemplate = self._templateLoader.getTemplate("olAddBridgeDomain.txt")
        
        for spine in vrf.getSpines():            
            
            config = irbTemplate.render(vlanId=network.vlanid)
            
            config += vrfTemplate.render(vrfName=vrf.name, irbName="irb." + str(network.vlanid))
            config += self.configureEvpn(network.vnid, asn)
            config += self.configureNetworkPolicyOptions(network.vnid, asn)
            config += bdTemplate.render(vlanId=network.vlanid, vxlanId=network.vnid, role="spine")
            
            deployments.append(OverlayDeployStatus(config, network.getUrl(), "create", spine, vrf.overlay_tenant.overlay_fabric))    

        for leaf in vrf.getLeafs():            
            
            config = self.configureEvpn(network.vnid, asn)
            config += self.configureNetworkPolicyOptions(network.vnid, asn)
            config += bdTemplate.render(vlanId=network.vlanid, vxlanId=network.vnid)

            deployments.append(OverlayDeployStatus(config, network.getUrl(), "create", leaf, vrf.overlay_tenant.overlay_fabric))    

        self._dao.createObjects(dbSession, deployments)
        logger.info("configureNetwork [network id: '%s', network name: '%s']: configured", network.id, network.name)
        self._commitQueue.addJobs(deployments)
    
    def configureSubnet(self, dbSession, subnet):
        '''
        Add subnet address to IRB
        '''
        deployments = []        
        network = subnet.overlay_network
        vrf = network.overlay_vrf
        spines = vrf.getSpines()

        irbIps = self.getSubnetIps(subnet.cidr)
        irbVirtualGateway = irbIps.pop(0).split("/")[0]
        
        if len(irbIps) < len(spines):
            logger.error("configureSubnet [vrf id: '%s', network id: '%s']: subnet IPs count: %d less than spine count: %d", 
                         vrf.id, network.id, len(irbIps), len(spines))

        irbTemplate = self._templateLoader.getTemplate("olAddIrb.txt")
        
        for spine, irbIp in itertools.izip(spines, irbIps):            
            config = irbTemplate.render(firstIpFromSubnet=irbVirtualGateway, secondOrThirdIpFromSubnet=irbIp, 
                vlanId=network.vlanid)
            deployments.append(OverlayDeployStatus(config, subnet.getUrl(), "create", spine, vrf.overlay_tenant.overlay_fabric))    

        self._dao.createObjects(dbSession, deployments)
        logger.info("configureSubnet [id: '%s', ip: '%s']: configured", subnet.id, subnet.cidr)
        self._commitQueue.addJobs(deployments)
        
    def configureEvpn(self, vni=None, asn=None):
        template = self._templateLoader.getTemplate('olAddProtocolEvpn.txt')
        return template.render(vxlanId=vni, asn=asn)
        
            
    def getSubnetIps(self, subnetBlock):
        '''
        returns all usable IPs in CIRD format (1.2.3.4/24) excluding network and broadcast
        '''
        cidr = subnetBlock.split("/")[1]
        ips = [str(ip) + "/" + cidr for ip in IPNetwork(subnetBlock).iter_hosts()]
        return ips        
        
    def configureL2port(self, dbSession, l2Port):
        '''
        Create access port interface
        '''
        deployments = []
        networks = [(net.vlanid, net.vnid) for net in l2Port.overlay_networks]
        vrf = l2Port.overlay_networks[0].overlay_vrf
        template = self._templateLoader.getTemplate('olAddInterface.txt')
        config = template.render(interfaceName=l2Port.interface, networks=networks)

        deployments.append(OverlayDeployStatus(config, l2Port.getUrl(), "create", l2Port.overlay_device, vrf.overlay_tenant.overlay_fabric))
        self._dao.createObjects(dbSession, deployments)
        logger.info("configureL2port [l2Port id: '%s', l2Port name: '%s']: configured", l2Port.id, l2Port.interface)
        self._commitQueue.addJobs(deployments)

    def configureAggregatedL2port(self, dbSession, aggregatedL2port):
        '''
        Create Aggregated L2 Port
        '''
        deployments = []
        networks = [(net.vlanid, net.vnid) for net in aggregatedL2port.overlay_networks]
        vrf = aggregatedL2port.overlay_networks[0].overlay_vrf
        template = self._templateLoader.getTemplate('olAddLag.txt')
        membersByDevice = {}
        # Normalize members based on device ids 
        # Note we need to do this so in Single-Homed use case, we only create one commit push
        for member in aggregatedL2port.members:
            if member.overlay_device.id not in membersByDevice:
                membersByDevice[member.overlay_device.id] = {'members': [], 'device': member.overlay_device}
            membersByDevice[member.overlay_device.id]['members'].append(member.interface)
                
        for deviceId, deviceMembers in membersByDevice.iteritems():
            lagCount = len(deviceMembers['device'].aggregatedL2port_members)
            config = template.render(memberInterfaces=deviceMembers['members'], networks=networks, lagName=aggregatedL2port.name, ethernetSegmentId=aggregatedL2port.esi, systemId=aggregatedL2port.lacp, lagCount=lagCount)
            deployments.append(OverlayDeployStatus(config, aggregatedL2port.getUrl(), "create", deviceMembers['device'], vrf.overlay_tenant.overlay_fabric))
            
        self._dao.createObjects(dbSession, deployments)
        logger.info("configureAggregatedL2port [aggregatedL2port id: '%s', aggregatedL2port name: '%s']: configured", aggregatedL2port.id, aggregatedL2port.name)
        self._commitQueue.addJobs(deployments)

    def _getObjectDeployedDevices(self, dbSession, objectUrl):
        # Check OverlayDeployStatus table, return only successfully deployed devices
        statusOnAllDevices = dbSession.query(OverlayDeployStatus).filter(
            OverlayDeployStatus.object_url == objectUrl).filter(
            OverlayDeployStatus.operation == 'create').filter(
            OverlayDeployStatus.status == 'success').all()
        logger.debug("Found object %s deployed at devices: %s", objectUrl, [status.overlay_device.name for status in statusOnAllDevices])
        return [status.overlay_device for status in statusOnAllDevices]
        
    def _deleteObjectAndStatus(self, dbSession, object, objectUrl):
        logger.debug("_deleteObjectAndStatus: object %s and all its status deleted", objectUrl)
        # Delete status associated with the object
        statusOnAllDevices = dbSession.query(OverlayDeployStatus).filter(
            OverlayDeployStatus.object_url == objectUrl).all()
        self._dao.deleteObjects(dbSession, statusOnAllDevices)
        # Delete the object itself
        self._dao.deleteObject(dbSession, object)
            
    def deleteL2port(self, dbSession, l2Port):
        '''
        Delete L2port from device
        '''
        deployedDevices = self._getObjectDeployedDevices(dbSession, l2Port.getUrl())
        if len(deployedDevices) == 0:
            # Shortcut: if we don't have any deployed device, we can safely delete the object without going to the devices.
            self._deleteObjectAndStatus(dbSession, l2Port, l2Port.getUrl())
            return
        
        if l2Port.overlay_device in deployedDevices:
            deployments = []
            networks = [(net.vlanid, net.vnid) for net in l2Port.overlay_networks]
            vrf = l2Port.overlay_networks[0].overlay_vrf
            template = self._templateLoader.getTemplate('olDelInterface.txt')
            config = template.render(interfaceName=l2Port.interface, networks=networks)

            deployments.append(OverlayDeployStatus(config, l2Port.getUrl(), "delete", l2Port.overlay_device, vrf.overlay_tenant.overlay_fabric))
            self._dao.createObjects(dbSession, deployments)
            logger.info("deleteL2port [l2Port id: '%s', l2Port name: '%s']: configured", l2Port.id, l2Port.interface)
            self._commitQueue.addJobs(deployments)

        
    def deleteSubnet(self, dbSession, subnet):
        deployedDevices = self._getObjectDeployedDevices(dbSession, subnet.getUrl())
        if len(deployedDevices) == 0:
            # Shortcut: if we don't have any deployed device, we can safely delete the object without going to the devices.
            self._deleteObjectAndStatus(dbSession, subnet, subnet.getUrl())
            return

        deployments = []        
        network = subnet.overlay_network
        vrf = network.overlay_vrf
        spines = vrf.getSpines()

        irbIps = self.getSubnetIps(subnet.cidr)
        irbVirtualGateway = irbIps.pop(0).split("/")[0]
        
        if len(irbIps) < len(spines):
            logger.error("deleteSubnet [vrf id: '%s', network id: '%s']: subnet IPs count: %d less than spine count: %d", 
                         vrf.id, network.id, len(irbIps), len(spines))

        irbTemplate = self._templateLoader.getTemplate("olDelSubnetFromIrb.txt")
        
        for spine, irbIp in itertools.izip(spines, irbIps):      
            if spine in deployedDevices:
                config = irbTemplate.render(secondOrThirdIpFromSubnet=irbIp, vlanId=network.vlanid)
                deployments.append(OverlayDeployStatus(config, subnet.getUrl(), "delete", spine, vrf.overlay_tenant.overlay_fabric))    

        self._dao.createObjects(dbSession, deployments)
        logger.info("deleteSubnet [id: '%s', ip: '%s']: configured", subnet.id, subnet.cidr)
        self._commitQueue.addJobs(deployments)

    def deleteNetwork(self, dbSession, network):
        '''
        Delete IRB, BD, update VRF, update evpn, update policy
        '''
        deployedDevices = self._getObjectDeployedDevices(dbSession, network.getUrl())
        if len(deployedDevices) == 0:
            # Shortcut: if we don't have any deployed device, we can safely delete the object without going to the devices.
            self._deleteObjectAndStatus(dbSession, network, network.getUrl())
            return
            
        deployments = []
        vrf = network.overlay_vrf
        asn = vrf.overlay_tenant.overlay_fabric.overlayAS

        irbTemplate = self._templateLoader.getTemplate("olDelIrb.txt")
        vrfTemplate = self._templateLoader.getTemplate("olDelIrbFromVrf.txt")
        bdTemplate = self._templateLoader.getTemplate("olDelBridgeDomain.txt")
        evpnTemplate = self._templateLoader.getTemplate('olDelNetworkFromEvpn.txt')
        policyTemplate = self._templateLoader.getTemplate('olDelNetworkPolicyOptions.txt')
        
        for spine in vrf.getSpines():
            if spine in deployedDevices:
                config = ""
                config += irbTemplate.render(vlanId=network.vlanid)
                config += vrfTemplate.render(vrfName=vrf.name, vlanId=network.vlanid)
                config += bdTemplate.render(vxlanId=network.vnid)
                config += evpnTemplate.render(vxlanId=network.vnid)
                config += policyTemplate.render(vxlanId=network.vnid, asn=asn)
                deployments.append(OverlayDeployStatus(config, network.getUrl(), "delete", spine, vrf.overlay_tenant.overlay_fabric))
                logger.debug("deleteNetwork: device: %s, object: %s, config: %s", spine.address, network.getUrl(), config)
        
        for leaf in vrf.getLeafs():
            if leaf in deployedDevices:
                config = ""
                config += bdTemplate.render(vxlanId=network.vnid)
                config += evpnTemplate.render(vxlanId=network.vnid)
                config += policyTemplate.render(vxlanId=network.vnid, asn=asn)
                deployments.append(OverlayDeployStatus(config, network.getUrl(), "delete", leaf, vrf.overlay_tenant.overlay_fabric))
                logger.debug("deleteNetwork: device: %s, object: %s, config: %s", leaf.address, network.getUrl(), config)

        self._dao.createObjects(dbSession, deployments)
        logger.info("deleteNetwork [id: '%s', name: '%s']: configured", network.id, network.name)
        self._commitQueue.addJobs(deployments)

    def deleteAggregatedL2port(self, dbSession, aggregatedL2port):
        '''
        Delete Aggregated L2 Port from device
        '''
        deployedDevices = self._getObjectDeployedDevices(dbSession, aggregatedL2port.getUrl())
        if len(deployedDevices) == 0:
            # Shortcut: if we don't have any deployed device, we can safely delete the object without going to the devices.
            self._deleteObjectAndStatus(dbSession, aggregatedL2port, aggregatedL2port.getUrl())
            return
            
        deployments = []
        vrf = aggregatedL2port.overlay_networks[0].overlay_vrf
        template = self._templateLoader.getTemplate('olDelLag.txt')
        membersByDevice = {}
        # Normalize members based on device ids 
        # Note we need to do this so in Single-Homed use case, we only create one commit push
        for member in aggregatedL2port.members:
            if member.overlay_device in deployedDevices:
                if member.overlay_device.id not in membersByDevice:
                    membersByDevice[member.overlay_device.id] = {'members': [], 'device': member.overlay_device}
                membersByDevice[member.overlay_device.id]['members'].append(member.interface)
                
        for deviceId, deviceMembers in membersByDevice.iteritems():
            lagCount = len(deviceMembers['device'].aggregatedL2port_members) - len(deviceMembers['members'])
            if lagCount < 0:
                raise ValueError("deleteAggregatedL2port [aggregatedL2port id: '%s', aggregatedL2port name: '%s']: lagCount is already 0. It cannot be decreased." % (aggregatedL2port.id, aggregatedL2port.name))
            config = template.render(memberInterfaces=deviceMembers['members'], lagName=aggregatedL2port.name, lagCount=lagCount)
            deployments.append(OverlayDeployStatus(config, aggregatedL2port.getUrl(), "delete", deviceMembers['device'], vrf.overlay_tenant.overlay_fabric))
        self._dao.createObjects(dbSession, deployments)
        logger.info("deleteAggregatedL2port [aggregatedL2port id: '%s', aggregatedL2port name: '%s']: configured", aggregatedL2port.id, aggregatedL2port.name)
        self._commitQueue.addJobs(deployments)

    def deleteVrf(self, dbSession, vrf):
        '''
        Delete VRF and vrf-loopback interface        
        '''
        deployedDevices = self._getObjectDeployedDevices(dbSession, vrf.getUrl())
        if len(deployedDevices) == 0:
            # Shortcut: if we don't have any deployed device, we can safely delete the object without going to the devices.
            self._deleteObjectAndStatus(dbSession, vrf, vrf.getUrl())
            return
            
        deployments = []

        vrfTemplate = self._templateLoader.getTemplate("olDelVrf.txt")
        loopbackTemplate = self._templateLoader.getTemplate("olDelLoopback.txt")
        
        for spine in vrf.getSpines():
            if spine in deployedDevices:
                config = loopbackTemplate.render(loopbackUnit=vrf.vrfCounter)
                config += vrfTemplate.render(vrfName=vrf.name)
                deployments.append(OverlayDeployStatus(config, vrf.getUrl(), "delete", spine, vrf.overlay_tenant.overlay_fabric))

        self._dao.createObjects(dbSession, deployments)
        logger.info("deleteVrf [id: '%s', name: '%s']: configured", vrf.id, vrf.name)
        self._commitQueue.addJobs(deployments)
    
    def deleteFabric(self, dbSession, fabric):
        '''
        Delete Fabric, iBGP         
        '''
        deployedDevices = self._getObjectDeployedDevices(dbSession, fabric.getUrl())
        if len(deployedDevices) == 0:
            # Shortcut: if we don't have any deployed device, we can safely delete the object without going to the devices.
            self._deleteObjectAndStatus(dbSession, fabric, fabric.getUrl())
            return
            
        deployments = []

        switchTemplate = self._templateLoader.getTemplate('olDelSwitchOptions.txt')
        bgpTemplate = self._templateLoader.getTemplate('olDelProtocolBgp.txt')
        policyTemplate = self._templateLoader.getTemplate('olDelPolicyOptions.txt')
        evpnTemplate = self._templateLoader.getTemplate('olDelProtocolEvpn.txt')

        for device in fabric.overlay_devices:
            if device in deployedDevices:
                config = switchTemplate.render()

                if device.role == 'spine':
                    config += bgpTemplate.render(role="spine")
                    config += policyTemplate.render()
                elif device.role == 'leaf':
                    config += bgpTemplate.render(role="leaf")
                    config += policyTemplate.render(remoteGateways=self.getRemoteGateways(fabric, device.podName))
                config += evpnTemplate.render()
                
                deployments.append(OverlayDeployStatus(config, fabric.getUrl(), "delete", device, fabric))

        self._dao.createObjects(dbSession, deployments)
        logger.info("deleteFabric [id: '%s', name: '%s']: configured", fabric.id, fabric.name)
        self._commitQueue.addJobs(deployments)


# def main():
    # conf = {}
    # conf['outputDir'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'out')
    # conf['plugin'] = [{'name': 'overlay', 'package': 'jnpr.openclos.overlay'}]
    # dao = Dao.getInstance()
    # overlay = Overlay(conf, dao)

    # with dao.getReadWriteSession() as session:
        # d1 = overlay.createDevice(session, 'd1', 'description for d1', 'spine', '1.2.3.4', '1.1.1.1', 'pod1', 'test', 'foobar')
        # d2 = overlay.createDevice(session, 'd2', 'description for d2', 'spine', '1.2.3.5', '1.1.1.2', 'pod1', 'test', 'foobar')
        # d3 = overlay.createDevice(session, 'd3', 'description for d3', 'spine', '1.2.3.6', '1.1.1.3', 'pod1', 'test', 'foobar')
        # d1_id = d1.id
        # d2_id = d2.id
        # d3_id = d3.id
        # f1 = overlay.createFabric(session, 'f1', '', 65001, '2.2.2.2', [d1, d2])
        # f1_id = f1.id
        # t1 = overlay.createTenant(session, 't1', '', f1)
        # t1_id = t1.id
        # t2 = overlay.createTenant(session, 't2', '', f1)
        # t2_id = t2.id
        # v1 = overlay.createVrf(session, 'v1', '', 100, '1.1.1.1/30', t1)
        # v1_id = v1.id
        # v2 = overlay.createVrf(session, 'v2', '', 101, '1.1.1.2/30', t2)
        # v2_id = v2.id
        # n1 = overlay.createNetwork(session, 'n1', '', v1, 1000, 100, False)
        # n1_id = n1.id
        # n2 = overlay.createNetwork(session, 'n2', '', v1, 1001, 101, False)
        # n2_id = n2.id
        # n3 = overlay.createNetwork(session, 'n3', '', v2, 1002, 102, False)
        # n3_id = n3.id
        # s1 = overlay.createSubnet(session, 's1', '', n1, '1.2.3.4/24')
        # s1_id = s1.id
        # s2 = overlay.createSubnet(session, 's2', '', n1, '1.2.3.5/24')
        # s2_id = s2.id
        # l2port1 = overlay.createL2port(session, 'l2port1', '', [n1], 'xe-0/0/1', d1)
        # l2port1_id = l2port1.id
        # l2port2 = overlay.createL2port(session, 'l2port2', '', [n1, n2, n3], 'xe-0/0/1', d2)
        # l2port2_id = l2port2.id
        # members = [ {'interface': 'xe-0/0/11', 'device': d1}, {'interface': 'xe-0/0/11', 'device': d2} ]
        # aggregatedL2port1 = overlay.createAggregatedL2port(session, 'aggregatedL2port1', '', [n1, n2], members, '00:11', '11:00')
        # aggregatedL2port1_id = aggregatedL2port1.id
        # members = [ {'interface': 'xe-0/0/12', 'device': d1}, {'interface': 'xe-0/0/12', 'device': d3} ]
        # aggregatedL2port2 = overlay.createAggregatedL2port(session, 'aggregatedL2port2', '', [n1, n2], members, '00:22', '22:00')
        # aggregatedL2port2_id = aggregatedL2port2.id
        
    # with dao.getReadSession() as session:
        # devices = session.query(OverlayDevice).all()
        # for device in devices:
            # print 'device %s: username = %s, encrypted password = %s, cleartext password = %s, hash password = %s' % (device.id, device.username, device.encryptedPassword, device.getCleartextPassword(), device.getHashPassword())
            
    # raw_input("1 Press Enter to continue...")
    # with dao.getReadWriteSession() as session:
        # object_url = '/openclos/v1/overlay/l2ports/' + l2port2_id
        # status_db = session.query(OverlayDeployStatus).filter(OverlayDeployStatus.object_url == object_url).all()
        # for s in status_db:
            # s.update('failure', 'l2port2 failed', 'POST')
        # object_url = '/openclos/v1/overlay/networks/' + n1_id
        # status_db = session.query(OverlayDeployStatus).filter(OverlayDeployStatus.object_url == object_url).all()
        # for s in status_db:
            # s.update('progress', 'n1 progress', 'POST')
    # raw_input("2 Press Enter to continue...")
    # with dao.getReadSession() as session:
        # status_db = session.query(OverlayDeployStatus, OverlayDevice).\
            # filter(OverlayDeployStatus.overlay_device_id == OverlayDevice.id).\
            # filter(OverlayDeployStatus.overlay_vrf_id == v1_id).\
            # order_by(OverlayDeployStatus.status, OverlayDeployStatus.object_url, OverlayDevice.name).all()
        # for s, d in status_db:
            # print 'status %s: config "%s" in device %s' % (s.status, s.configlet, d.name)
    # raw_input("3 Press Enter to continue...")
    # with dao.getReadWriteSession() as session:
        # l2port2 = session.query(OverlayL2port).filter(OverlayL2port.id == l2port2_id).one()
        # l2port2.clearNetworks()
        # l2port2.update(l2port2.name, l2port2.description, [n2], l2port2.interface, l2port2.overlay_device)
    # raw_input("4 Press Enter to continue...")
    # with dao.getReadSession() as session:
        # networks = session.query(OverlayNetwork).all()
        # for network in networks:
            # for l2ap in network.overlay_l2aps:
                # print 'network %s: l2ap = [%s:%s]' % (network.id, l2ap.id, l2ap.type)
    # raw_input("5 Press Enter to continue...")
    # with dao.getReadSession() as session:
        # for member in session.query(OverlayAggregatedL2portMember).all():
            # print 'aggregatedL2port = %s: member = [%s:%s]' % (member.overlay_aggregatedL2port_id, member.overlay_device_id, member.interface)
    # raw_input("6 Press Enter to continue...")
    # with dao.getReadWriteSession() as session:
        # session.delete(session.query(OverlayDevice).first())
    # raw_input("7 Press Enter to continue...")
    # with dao.getReadSession() as session:
        # for member in session.query(OverlayAggregatedL2portMember).all():
            # print 'aggregatedL2port = %s: member = [%s:%s]' % (member.overlay_aggregatedL2port_id, member.overlay_device_id, member.interface)
    # raw_input("8 Press Enter to continue...")
    # with dao.getReadWriteSession() as session:
        # session.delete(session.query(OverlayAggregatedL2port).first())
    # raw_input("9 Press Enter to continue...")
    # with dao.getReadSession() as session:
        # for member in session.query(OverlayAggregatedL2portMember).all():
            # print 'aggregatedL2port = %s: member = [%s:%s]' % (member.overlay_aggregatedL2port_id, member.overlay_device_id, member.interface)
        
# if __name__ == '__main__':
    # main()
