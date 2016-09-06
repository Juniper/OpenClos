'''
Created on Nov 23, 2015

@author: yunli
'''

import logging
import os
import itertools
from netaddr import IPNetwork, valid_ipv4, valid_ipv6
from netaddr.core import AddrFormatError, INET_PTON

from jnpr.openclos.exception import OverlayDeviceNotFound
from jnpr.openclos.overlay.overlayModel import OverlayFabric, OverlayTenant, OverlayVrf, OverlayNetwork, OverlaySubnet, OverlayDevice, OverlayL3port, OverlayL2port, OverlayAggregatedL2port, OverlayAggregatedL2portMember, OverlayDeployStatus, OverlayL2ap
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

    def modifyDevice(self, dbSession, device, username, password):
        '''
        Modify an existing Device
        '''
        device.update(username, password)

        self._dao.updateObjects(dbSession, [device])
        logger.info("OverlayDevice[id: '%s', name: '%s']: modified", device.id, device.name)
        return device

    def createFabric(self, dbSession, name, description, overlayAsn, routeReflectorAddress, devices):
        '''
        Create a new Fabric
        '''
        if not Overlay.isValidIpAddress(routeReflectorAddress):
            raise ValueError('Invalid routeReflectorAddress value %s' % routeReflectorAddress)
        
        fabric = OverlayFabric(name, description, overlayAsn, routeReflectorAddress, devices)

        self._dao.createObjects(dbSession, [fabric])
        logger.info("OverlayFabric[id: '%s', name: '%s']: created", fabric.id, fabric.name)
        self._configEngine.configureFabric(dbSession, "create", fabric)
        return fabric

    def modifyFabric(self, dbSession, fabric, overlayAsn, routeReflectorAddress, devices):
        '''
        Modify an existing Fabric
        '''
        (added, deleted, deviceChangeOnly) = fabric.update(overlayAsn, routeReflectorAddress, devices)

        self._dao.updateObjects(dbSession, [fabric])
        logger.info("OverlayFabric[id: '%s', name: '%s']: modified", fabric.id, fabric.name)
        
        # Apply changes to all devices
        self._configEngine.configureFabric(dbSession, "update", fabric)
        for tenant in fabric.overlay_tenants:
            for vrf in tenant.overlay_vrfs:
                self._configEngine.configureVrf(dbSession, "update", vrf)
                for network in vrf.overlay_networks:
                    self._configEngine.configureNetwork(dbSession, "update", network)
                    for subnet in network.overlay_subnets:
                        self._configEngine.configureSubnet(dbSession, "update", subnet)
                    for l2ap in network.overlay_l2aps:
                        if l2ap.type == 'l2port':
                            self._configEngine.configureL2port(dbSession, "update", l2ap)
                        elif l2ap.type == 'aggregatedL2port':
                            self._configEngine.configureAggregatedL2port(dbSession, "update", l2ap)

        # TODO: Optionally delete ALL configs from deleted devices (?)
                    
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
        if loopbackAddress is not None and not Overlay.isValidIpBlock(loopbackAddress):
            raise ValueError('Invalid loopbackAddress value %s' % loopbackAddress)
        
        vrf = OverlayVrf(name, description, routedVnid, loopbackAddress, overlayTenant)
        vrf.vrfCounter = self._dao.incrementAndGetCounter("OverlayVrf.vrfCounter")

        self._dao.createObjects(dbSession, [vrf])
        logger.info("OverlayVrf[id: '%s', name: '%s']: created", vrf.id, vrf.name)
        self._configEngine.configureVrf(dbSession, "create", vrf)
        return vrf

    def modifyVrf(self, dbSession, vrf, loopbackAddress):
        '''
        Modify an existing Vrf
        '''
        if loopbackAddress is not None and not Overlay.isValidIpBlock(loopbackAddress):
            raise ValueError('Invalid loopbackAddress value %s' % loopbackAddress)
        
        vrf.update(loopbackAddress)

        self._dao.updateObjects(dbSession, [vrf])
        logger.info("OverlayVrf[id: '%s', name: '%s']: modified", vrf.id, vrf.name)
        self._configEngine.configureVrf(dbSession, "update", vrf)
        return vrf

    def createNetwork(self, dbSession, name, description, overlay_vrf, vlanid, vnid, pureL3Int):
        '''
        Create a new Network
        '''
        network = OverlayNetwork(name, description, overlay_vrf, vlanid, vnid, pureL3Int)

        self._dao.createObjects(dbSession, [network])
        logger.info("OverlayNetwork[id: '%s', name: '%s']: created", network.id, network.name)
        self._configEngine.configureNetwork(dbSession, "create", network)
        return network

    def modifyNetwork(self, dbSession, network, vlanid, vnid):
        '''
        Modify an existing Network
        '''
        old = network.update(vlanid, vnid)

        self._dao.updateObjects(dbSession, [network])
        logger.info("OverlayNetwork[id: '%s', name: '%s']: modified", network.id, network.name)
        self._configEngine.configureNetwork(dbSession, "update", network, old)
        return network

    def createSubnet(self, dbSession, name, description, overlay_network, cidr):
        '''
        Create a new Subnet
        '''
        if not Overlay.isValidIpBlock(cidr):
            raise ValueError('Invalid cidr value %s' % cidr)
            
        subnet = OverlaySubnet(name, description, overlay_network, cidr)

        self._dao.createObjects(dbSession, [subnet])
        logger.info("OverlaySubnet[id: '%s', name: '%s']: created", subnet.id, subnet.name)
        self._configEngine.configureSubnet(dbSession, "create", subnet)
        return subnet

    def modifySubnet(self, dbSession, subnet, cidr):
        '''
        Modify an existing Subnet
        '''
        old = subnet.update(cidr)

        self._dao.updateObjects(dbSession, [subnet])
        logger.info("OverlaySubnet[id: '%s', name: '%s']: modified", subnet.id, subnet.name)
        self._configEngine.configureSubnet(dbSession, "update", subnet, old)
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
        self._configEngine.configureL2port(dbSession, "create", l2port)
        return l2port

    def modifyL2port(self, dbSession, l2port, overlay_networks):
        '''
        Modify an existing L2port
        '''
        (addedNetworks, deletedNetworks) = l2port.update(overlay_networks)

        self._dao.updateObjects(dbSession, [l2port])
        logger.info("OverlayL2port[id: '%s', name: '%s']: modified", l2port.id, l2port.name)
        self._configEngine.configureL2port(dbSession, "update", l2port, deletedNetworks)
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
        self._configEngine.configureAggregatedL2port(dbSession, "create", aggregatedL2port)
        
        return aggregatedL2port
        
    def modifyAggregatedL2port(self, dbSession, aggregatedL2port, overlay_networks, esi, lacp):
        '''
        Modify an existing AggregatedL2port
        '''
        (addedNetworks, deletedNetworks) = aggregatedL2port.update(overlay_networks, esi, lacp)

        self._dao.updateObjects(dbSession, [aggregatedL2port])
        logger.info("OverlayAggregatedL2port[id: '%s', name: '%s']: modified", aggregatedL2port.id, aggregatedL2port.name)
        self._configEngine.configureAggregatedL2port(dbSession, "update", aggregatedL2port, deletedNetworks)
        return aggregatedL2port
        
    def deleteL2port(self, dbSession, l2port, force=False):
        '''
        Delete L2port from device, if success then from DB
        '''
        self._configEngine.deleteL2port(dbSession, l2port, force)

    def deleteAggregatedL2port(self, dbSession, aggregatedL2port, force=False):
        '''
        Delete Aggregated L2 port from device, if success then from DB
        '''
        self._configEngine.deleteAggregatedL2port(dbSession, aggregatedL2port, force)

    def deleteSubnet(self, dbSession, subnet, force=False):
        '''
        Delete subnet from device
        '''
        self._configEngine.deleteSubnet(dbSession, subnet, force)

    def deleteNetwork(self, dbSession, network, force=False):
        '''
        Delete network from device, also delete subnet and all l2ports attached to the network
        '''
        self._configEngine.deleteNetwork(dbSession, network, force)

    def deleteVrf(self, dbSession, vrf, force=False):
        '''
        Delete vrf rom device, also delete network, subnet ports etc.
        '''
        self._configEngine.deleteVrf(dbSession, vrf, force)

    def deleteTenant(self, dbSession, tenant, force=False):
        '''
        Delete tenant from device, also vrf, delete network, subnet ports etc.
        '''
        self._configEngine.deleteTenant(dbSession, tenant, force)
        
    def deleteFabric(self, dbSession, fabric, force=False):
        '''
        Delete fabric from device, also vrf, delete network, subnet ports etc.
        '''
        self._configEngine.deleteFabric(dbSession, fabric, force)

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

    def deleteDevice(self, dbSession, device, force=False):
        # Validate if there is l2port or aggregatedL2port active on this device.
        # If there is, this request will fail with 500. User needs to delete l2port/aggregatedL2port explicitly 
        # and then try to delete device again.
        if not force:
            self._checkDeviceDependency(dbSession, device)
        self._dao.deleteObject(dbSession, device)
        logger.info("OverlayDevice[id: '%s', name: '%s']: deleted", device.id, device.name)
            
    @staticmethod
    def isValidIpAddress(value):
        try:
            return valid_ipv4(value, INET_PTON) or valid_ipv6(value, INET_PTON)
        except AddrFormatError as exc:
            logger.error("%s", exc)
        return False
    
    @staticmethod
    def isValidIpBlock(value):
        try:
            block = IPNetwork(value)
            return True
        except AddrFormatError as exc:
            logger.error("%s", exc)
        return False
        
class ConfigEngine():
    def __init__(self, conf, dao, commitQueue=None):
        self._conf = conf
        self._dao = dao
        if commitQueue:
            self._commitQueue = commitQueue
        else:
            self._commitQueue = OverlayCommitQueue.getInstance()
        # Preload all templates
        self._templateLoader = TemplateLoader(junosTemplatePackage="jnpr.openclos.overlay")
        self._olAddProtocolBgpSpine = self._templateLoader.getTemplate('olAddProtocolBgpSpine.txt')
        self._olAddProtocolBgpLeaf = self._templateLoader.getTemplate('olAddProtocolBgpLeaf.txt')
        self._olAddRoutingOptions = self._templateLoader.getTemplate('olAddRoutingOptions.txt')
        self._olAddSwitchOptions = self._templateLoader.getTemplate('olAddSwitchOptions.txt')
        self._olAddPolicyOptions = self._templateLoader.getTemplate('olAddPolicyOptions.txt')
        self._olAddLoopback = self._templateLoader.getTemplate('olAddLoopback.txt')
        self._olAddIrb = self._templateLoader.getTemplate("olAddIrb.txt")
        self._olAddVrf = self._templateLoader.getTemplate("olAddVrf.txt")
        self._olAddBridgeDomain = self._templateLoader.getTemplate("olAddBridgeDomain.txt")
        self._olAddProtocolEvpn = self._templateLoader.getTemplate('olAddProtocolEvpn.txt')
        self._olAddInterface = self._templateLoader.getTemplate('olAddInterface.txt')
        self._olAddLag = self._templateLoader.getTemplate('olAddLag.txt')
        self._olDelInterface = self._templateLoader.getTemplate('olDelInterface.txt')
        self._olDelSubnetFromIrb = self._templateLoader.getTemplate("olDelSubnetFromIrb.txt")
        self._olDelIrb = self._templateLoader.getTemplate("olDelIrb.txt")
        self._olDelIrbFromVrf = self._templateLoader.getTemplate("olDelIrbFromVrf.txt")
        self._olDelBridgeDomain = self._templateLoader.getTemplate("olDelBridgeDomain.txt")
        self._olDelNetworkFromEvpn = self._templateLoader.getTemplate('olDelNetworkFromEvpn.txt')
        self._olDelNetworkPolicyOptions = self._templateLoader.getTemplate('olDelNetworkPolicyOptions.txt')
        self._olDelNetworkFromInterfaces = self._templateLoader.getTemplate('olDelNetworkFromInterfaces.txt')
        self._olDelLag = self._templateLoader.getTemplate('olDelLag.txt')
        self._olDelVrf = self._templateLoader.getTemplate("olDelVrf.txt")
        self._olDelLoopback = self._templateLoader.getTemplate("olDelLoopback.txt")
        self._olDelSwitchOptions = self._templateLoader.getTemplate('olDelSwitchOptions.txt')
        self._olDelProtocolBgp = self._templateLoader.getTemplate('olDelProtocolBgp.txt')
        self._olDelPolicyOptions = self._templateLoader.getTemplate('olDelPolicyOptions.txt')
        self._olDelProtocolEvpn = self._templateLoader.getTemplate('olDelProtocolEvpn.txt')
        self._olDelVnidFromProtocolEvpn = self._templateLoader.getTemplate('olDelVnidFromProtocolEvpn.txt')
        self._olDelVnidFromPolicyOptions = self._templateLoader.getTemplate('olDelVnidFromPolicyOptions.txt')

    def configureFabric(self, dbSession, operation, fabric):
        '''
        Generate iBGP config
        '''
        
        deployments = []        
        for device in fabric.overlay_devices:
            config = self.configureRoutingOptions(device)
            config += self.configureSwitchOptions(device.routerId)

            if device.role == 'spine':
                config += self._olAddProtocolBgpSpine.render(routerId=device.routerId, asn=fabric.overlayAS, 
                            podLeafs=[l.routerId for l in fabric.getPodLeafs(device.podName)], 
                            allSpines=[s.routerId for s in fabric.getSpines() if s != device], 
                            routeReflector=fabric.routeReflectorAddress)
            elif device.role == 'leaf':
                config += self._olAddProtocolBgpLeaf.render(routerId=device.routerId, asn=fabric.overlayAS, 
                            podSpines=[s.routerId for s in fabric.getPodSpines(device.podName)],
                            remoteGateways=self.getRemoteGateways(fabric, device.podName))
            config += self.configureFabricPolicyOptions(fabric, device)
            config += self.configureEvpn()
            
            deployments.append(OverlayDeployStatus(config, fabric.getUrl(), operation, device, fabric))    

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
            return self._olAddRoutingOptions.render(routerId=device.routerId)
        else:
            return ""
        
    def configureSwitchOptions(self, routerId):
        return self._olAddSwitchOptions.render(routerId=routerId, esiRouteTarget=esiRouteTarget)

    def configureFabricPolicyOptions(self, fabric, device):
        if device.role == 'spine':
            return self._olAddPolicyOptions.render(esiRTarget=esiRouteTarget)
        else:
            return self._olAddPolicyOptions.render(remoteGateways=self.getRemoteGateways(fabric, device.podName), esiRTarget=esiRouteTarget)
        
    def configureNetworkPolicyOptions(self, vni=None, asn=None):
        return self._olAddPolicyOptions.render(vni=vni, asn=ConfigEngine.formatASN(asn))

    @staticmethod
    def formatASN(value):
        if value is None:
            return None
        elif int(value) < 65536:
            return str(value)
        elif int(value) >= 65536:
            return str(value) + "L"
        else:
            return value

    def configureVrf(self, dbSession, operation, vrf):
        deployments = []
        spines = vrf.getSpines()
        if vrf.loopbackAddress is not None:
            loopbackIps = self.getLoopbackIps(vrf.loopbackAddress)
        else:
            # In case user hasn't set loopback address block yet, create an artificial list of Nones 
            # so the izip loop below will work
            loopbackIps = [None for spine in spines]
        
        if len(loopbackIps) < len(spines):
            logger.error("configureVrf [id: '%s', name: '%s']: loopback IPs count: %d less than spine count: %d", 
                         vrf.id, vrf.name, len(loopbackIps), len(spines))
        
        for spine, loopback in itertools.izip(spines, loopbackIps):
            if loopback is not None:
                config = self.configureLoopback(loopback, vrf.vrfCounter)
                config += self._olAddVrf.render(vrfName=vrf.name,  vrfCounter=vrf.vrfCounter,
                    routerId=spine.routerId, asn=ConfigEngine.formatASN(vrf.overlay_tenant.overlay_fabric.overlayAS), loopback=loopback)
            else:
                # If user hasn't set loopback address block yet, do not configure lo.<vrfCounter> interface
                config = self._olAddVrf.render(vrfName=vrf.name,  vrfCounter=vrf.vrfCounter,
                    routerId=spine.routerId, asn=ConfigEngine.formatASN(vrf.overlay_tenant.overlay_fabric.overlayAS))
            
            deployments.append(OverlayDeployStatus(config, vrf.getUrl(), operation, spine, vrf.overlay_tenant.overlay_fabric))    

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
        return self._olAddLoopback.render(loopbackUnit=loopbackUnit, loopbackAddress=loopbackIp)

    def configureNetwork(self, dbSession, operation, network, old=None):
        '''
        Create IRB, BD, update VRF, update evpn, update policy
        '''
        deployments = []        
        vrf = network.overlay_vrf
        asn = vrf.overlay_tenant.overlay_fabric.overlayAS
        
        for spine in vrf.getSpines():
        
            config = self._olAddIrb.render(vlanId=network.vlanid)
            
            config += self._olAddVrf.render(vrfName=vrf.name, irbName="irb." + str(network.vlanid))
            config += self.configureEvpn(network.vnid, asn)
            config += self.configureNetworkPolicyOptions(network.vnid, asn)
            config += self._olAddBridgeDomain.render(networkName=network.name, vlanId=network.vlanid, vxlanId=network.vnid, role="spine")
            
            # If this is a modify, remove existing vlanid/vnid config
            if old is not None:
                if old["vnid"] != network.vnid:
                    config += self._olDelVnidFromProtocolEvpn.render(vxlanId=old["vnid"])
                    config += self._olDelVnidFromPolicyOptions.render(vni=old["vnid"])
                if old["vlanid"] != network.vlanid:
                    config += self._olDelIrb.render(vlanId=old["vlanid"])
                
            deployments.append(OverlayDeployStatus(config, network.getUrl(), operation, spine, vrf.overlay_tenant.overlay_fabric))    

        for leaf in vrf.getLeafs():            
            
            config = self.configureEvpn(network.vnid, asn)
            config += self.configureNetworkPolicyOptions(network.vnid, asn)
            config += self._olAddBridgeDomain.render(networkName=network.name, vlanId=network.vlanid, vxlanId=network.vnid)

            # If this is a modify, remove existing vnid config
            if old is not None:
                if old["vnid"] != network.vnid:
                    config += self._olDelVnidFromProtocolEvpn.render(vxlanId=old["vnid"])
                    config += self._olDelVnidFromPolicyOptions.render(vni=old["vnid"])
                
            deployments.append(OverlayDeployStatus(config, network.getUrl(), operation, leaf, vrf.overlay_tenant.overlay_fabric))    

        self._dao.createObjects(dbSession, deployments)
        logger.info("configureNetwork [network id: '%s', network name: '%s']: configured", network.id, network.name)
        self._commitQueue.addJobs(deployments)
    
    def configureSubnet(self, dbSession, operation, subnet, old=None):
        '''
        Add subnet address to IRB
        '''
        deployments = []        
        network = subnet.overlay_network
        vrf = network.overlay_vrf
        spines = vrf.getSpines()

        irbIps = self.getSubnetIps(subnet.cidr)
        irbVirtualGateway = irbIps.pop(0).split("/")[0]
        
        # If this is a modify, remove existing irb config
        oldIrbIps = None
        oldIrbVirtualGateway = None
        if old is not None:
            if old["cidr"] != subnet.cidr:
                oldIrbIps = self.getSubnetIps(old["cidr"])
                oldIrbVirtualGateway = oldIrbIps.pop(0).split("/")[0]
            
        if len(irbIps) < len(spines):
            logger.error("configureSubnet [vrf id: '%s', network id: '%s']: subnet IPs count: %d less than spine count: %d", 
                         vrf.id, network.id, len(irbIps), len(spines))

        if oldIrbIps is None:
            for spine, irbIp, in itertools.izip(spines, irbIps):
                config = self._olAddIrb.render(firstIpFromSubnet=irbVirtualGateway, secondOrThirdIpFromSubnet=irbIp, vlanId=network.vlanid)
                deployments.append(OverlayDeployStatus(config, subnet.getUrl(), operation, spine, vrf.overlay_tenant.overlay_fabric))    
        else:
            for spine, irbIp, oldIrbIp in itertools.izip(spines, irbIps, oldIrbIps):
                config = self._olAddIrb.render(firstIpFromSubnet=irbVirtualGateway, secondOrThirdIpFromSubnet=irbIp, vlanId=network.vlanid)
                config += self._olDelSubnetFromIrb.render(secondOrThirdIpFromSubnet=oldIrbIp, vlanId=network.vlanid)
                deployments.append(OverlayDeployStatus(config, subnet.getUrl(), operation, spine, vrf.overlay_tenant.overlay_fabric))    

        self._dao.createObjects(dbSession, deployments)
        logger.info("configureSubnet [id: '%s', ip: '%s']: configured", subnet.id, subnet.cidr)
        self._commitQueue.addJobs(deployments)
        
    def configureEvpn(self, vni=None, asn=None):
        return self._olAddProtocolEvpn.render(vxlanId=vni, asn=ConfigEngine.formatASN(asn))
        
            
    def getSubnetIps(self, subnetBlock):
        '''
        returns all usable IPs in CIRD format (1.2.3.4/24) excluding network and broadcast
        '''
        cidr = subnetBlock.split("/")[1]
        ips = [str(ip) + "/" + cidr for ip in IPNetwork(subnetBlock).iter_hosts()]
        return ips        
        
    def configureL2port(self, dbSession, operation, l2port, deletedNetworks=None):
        '''
        Create access port interface
        '''
        deployments = []
        networks = [(net.vlanid, net.vnid, net.name) for net in l2port.overlay_networks]
        vrf = l2port.overlay_networks[0].overlay_vrf
        config = self._olAddInterface.render(interfaceName=l2port.interface, networks=networks)
        if deletedNetworks is not None:
            deletedNetworks = [(net.vlanid, net.vnid, net.name) for net in deletedNetworks]
            config += self._olDelInterface.render(interfaceName=l2port.interface, networks=deletedNetworks)
        deployments.append(OverlayDeployStatus(config, l2port.getUrl(), operation, l2port.overlay_device, vrf.overlay_tenant.overlay_fabric))
        self._dao.createObjects(dbSession, deployments)
        logger.info("configureL2port [l2port id: '%s', l2port name: '%s']: configured", l2port.id, l2port.interface)
        self._commitQueue.addJobs(deployments)

    def configureAggregatedL2port(self, dbSession, operation, aggregatedL2port, deletedNetworks=None):
        '''
        Create Aggregated L2 Port
        '''
        deployments = []
        networks = [(net.vlanid, net.vnid, net.name) for net in aggregatedL2port.overlay_networks]
        vrf = aggregatedL2port.overlay_networks[0].overlay_vrf
        membersByDevice = {}
        # Normalize members based on device ids 
        # Note we need to do this so in Single-Homed use case, we only create one commit push
        for member in aggregatedL2port.members:
            if member.overlay_device.id not in membersByDevice:
                membersByDevice[member.overlay_device.id] = {'members': [], 'device': member.overlay_device}
            membersByDevice[member.overlay_device.id]['members'].append(member.interface)
                
        for deviceId, deviceMembers in membersByDevice.iteritems():
            lagCount = len(deviceMembers['device'].aggregatedL2port_members)
            config = self._olAddLag.render(memberInterfaces=deviceMembers['members'], networks=networks, lagName=aggregatedL2port.name, ethernetSegmentId=aggregatedL2port.esi, systemId=aggregatedL2port.lacp, lagCount=lagCount)
            if deletedNetworks is not None:
                deletedNetworks2 = [(net.vlanid, net.vnid, net.name) for net in deletedNetworks]
                # NOTE we are using _olDelInterface template instead of _olDelLag template because
                # we just need to remove the "unit" from "interfaces" stanza and "interface" from "vlans" stanza.
                # We don't have to deal with other part of _olDelLag template.
                config += self._olDelInterface.render(interfaceName=aggregatedL2port.name, networks=deletedNetworks2)
            deployments.append(OverlayDeployStatus(config, aggregatedL2port.getUrl(), operation, deviceMembers['device'], vrf.overlay_tenant.overlay_fabric))
            
        self._dao.createObjects(dbSession, deployments)
        logger.info("configureAggregatedL2port [aggregatedL2port id: '%s', aggregatedL2port name: '%s']: configured", aggregatedL2port.id, aggregatedL2port.name)
        self._commitQueue.addJobs(deployments)

    def _deleteCheck(self, dbSession, force, objectUrl, object):
        # Get only successfully deployed devices
        successStatusOnAllDevices = dbSession.query(OverlayDeployStatus).filter(
            OverlayDeployStatus.object_url == objectUrl).filter(
            OverlayDeployStatus.status == 'success').all()
        if len(successStatusOnAllDevices) == 0:
            logger.debug("_deleteCheck: Object %s not deployed at any device", objectUrl)
            # Get status from all devices
            statusOnAllDevices = dbSession.query(OverlayDeployStatus).filter(
                OverlayDeployStatus.object_url == objectUrl).all()
            # Delete all status
            self._dao.deleteObjects(dbSession, statusOnAllDevices)
            logger.debug("Object %s all deploy status deleted", objectUrl)
            # Now schedule deletion of the object itself
            self._commitQueue.addDbCleanUp(objectUrl, force)
            return []
        else:
            logger.debug("_deleteCheck: Object %s deployed at devices: %s", objectUrl, [status.overlay_device.name for status in successStatusOnAllDevices])
            return [status.overlay_device for status in successStatusOnAllDevices]
        
    def deleteL2port(self, dbSession, l2port, force):
        '''
        Delete L2port from device
        '''
        deployedDevices = self._deleteCheck(dbSession, force, l2port.getUrl(), l2port)
        if len(deployedDevices) == 0:
            # Shortcut: if we don't have any deployed device, we can safely delete the object without going to the devices.
            return
        
        logger.info("OverlayL2port[id: '%s', name: '%s']: delete request submitted", l2port.id, l2port.name)
        if l2port.overlay_device in deployedDevices:
            deployments = []
            networks = [(net.vlanid, net.vnid, net.name) for net in l2port.overlay_networks]
            vrf = l2port.overlay_networks[0].overlay_vrf
            config = self._olDelInterface.render(interfaceName=l2port.interface, networks=networks)

            deployments.append(OverlayDeployStatus(config, l2port.getUrl(), "delete", l2port.overlay_device, vrf.overlay_tenant.overlay_fabric))
            self._dao.createObjects(dbSession, deployments)
            logger.info("deleteL2port [l2port id: '%s', l2port name: '%s']: configured", l2port.id, l2port.interface)
            self._commitQueue.addJobs(deployments)
            self._commitQueue.addDbCleanUp(l2port.getUrl(), force)

    def deleteSubnet(self, dbSession, subnet, force):
        deployedDevices = self._deleteCheck(dbSession, force, subnet.getUrl(), subnet)
        if len(deployedDevices) == 0:
            # Shortcut: if we don't have any deployed device, we can safely delete the object without going to the devices.
            return

        logger.info("OverlaySubnet[id: '%s', cidr: '%s']: delete request submitted", subnet.id, subnet.name)
        deployments = []        
        network = subnet.overlay_network
        vrf = network.overlay_vrf
        spines = vrf.getSpines()

        irbIps = self.getSubnetIps(subnet.cidr)
        irbVirtualGateway = irbIps.pop(0).split("/")[0]
        
        if len(irbIps) < len(spines):
            logger.error("deleteSubnet [vrf id: '%s', network id: '%s']: subnet IPs count: %d less than spine count: %d", 
                         vrf.id, network.id, len(irbIps), len(spines))

        for spine, irbIp in itertools.izip(spines, irbIps):      
            if spine in deployedDevices:
                config = self._olDelSubnetFromIrb.render(secondOrThirdIpFromSubnet=irbIp, vlanId=network.vlanid)
                deployments.append(OverlayDeployStatus(config, subnet.getUrl(), "delete", spine, vrf.overlay_tenant.overlay_fabric))    

        self._dao.createObjects(dbSession, deployments)
        logger.info("deleteSubnet [id: '%s', ip: '%s']: configured", subnet.id, subnet.cidr)
        self._commitQueue.addJobs(deployments)
        self._commitQueue.addDbCleanUp(subnet.getUrl(), force)

    def deleteNetwork(self, dbSession, network, force):
        '''
        Delete IRB, BD, update VRF, update evpn, update policy
        '''
        deployedDevices = self._deleteCheck(dbSession, force, network.getUrl(), network)
        if len(deployedDevices) == 0:
            # Shortcut: if we don't have any deployed device, we can safely delete the object without going to the devices.
            return
            
        logger.info("OverlayNetwork[id: '%s', name: '%s']: delete request submitted", network.id, network.name)
        # NOTE deleting l2port/aggregatedL2port from network is done in ConfigEngine.deleteNetwork()
        deployments = []
        vrf = network.overlay_vrf
        asn = vrf.overlay_tenant.overlay_fabric.overlayAS

        for spine in vrf.getSpines():
            if spine in deployedDevices:
                config = ""
                config += self._olDelIrb.render(vlanId=network.vlanid)
                config += self._olDelIrbFromVrf.render(vrfName=vrf.name, vlanId=network.vlanid)
                config += self._olDelBridgeDomain.render(networkName=network.name)
                config += self._olDelNetworkFromEvpn.render(vxlanId=network.vnid)
                config += self._olDelNetworkPolicyOptions.render(vxlanId=network.vnid)
                deployments.append(OverlayDeployStatus(config, network.getUrl(), "delete", spine, vrf.overlay_tenant.overlay_fabric))
                # logger.debug("deleteNetwork: spine: %s, object: %s, config: %s", spine.address, network.getUrl(), config)
        
        for leaf in vrf.getLeafs():
            if leaf in deployedDevices:
                config = ""
                config += self._olDelBridgeDomain.render(networkName=network.name)
                config += self._olDelNetworkFromEvpn.render(vxlanId=network.vnid)
                config += self._olDelNetworkPolicyOptions.render(vxlanId=network.vnid)
                interfaces = [l2ap.configName() for l2ap in network.overlay_l2aps]
                config += self._olDelNetworkFromInterfaces.render(interfaces=interfaces, vlanId=network.vlanid)
                deployments.append(OverlayDeployStatus(config, network.getUrl(), "delete", leaf, vrf.overlay_tenant.overlay_fabric))
                # logger.debug("deleteNetwork: leaf: %s, object: %s, config: %s", leaf.address, network.getUrl(), config)

        self._dao.createObjects(dbSession, deployments)
        logger.info("deleteNetwork [id: '%s', name: '%s']: configured", network.id, network.name)
        self._commitQueue.addJobs(deployments)
        self._commitQueue.addDbCleanUp(network.getUrl(), force)

    def deleteAggregatedL2port(self, dbSession, aggregatedL2port, force):
        '''
        Delete Aggregated L2 Port from device
        '''
        deployedDevices = self._deleteCheck(dbSession, force, aggregatedL2port.getUrl(), aggregatedL2port)
        if len(deployedDevices) == 0:
            # Shortcut: if we don't have any deployed device, we can safely delete the object without going to the devices.
            return
            
        logger.info("OverlayAggregatedL2port[id: '%s', name: '%s']: delete request submitted", aggregatedL2port.id, aggregatedL2port.name)
        deployments = []
        vrf = aggregatedL2port.overlay_networks[0].overlay_vrf
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
            config = self._olDelLag.render(memberInterfaces=deviceMembers['members'], lagName=aggregatedL2port.name, lagCount=lagCount)
            deployments.append(OverlayDeployStatus(config, aggregatedL2port.getUrl(), "delete", deviceMembers['device'], vrf.overlay_tenant.overlay_fabric))
        self._dao.createObjects(dbSession, deployments)
        logger.info("deleteAggregatedL2port [aggregatedL2port id: '%s', aggregatedL2port name: '%s']: configured", aggregatedL2port.id, aggregatedL2port.name)
        self._commitQueue.addJobs(deployments)
        self._commitQueue.addDbCleanUp(aggregatedL2port.getUrl(), force)

    def deleteVrf(self, dbSession, vrf, force):
        '''
        Delete VRF and vrf-loopback interface        
        '''
        deployedDevices = self._deleteCheck(dbSession, force, vrf.getUrl(), vrf)
        if len(deployedDevices) == 0:
            # Shortcut: if we don't have any deployed device, we can safely delete the object without going to the devices.
            return
            
        logger.info("OverlayVrf[id: '%s', name: '%s']: delete request submitted", vrf.id, vrf.name)
        deployments = []
        for spine in vrf.getSpines():
            if spine in deployedDevices:
                config = ""
                if vrf.loopbackAddress is not None:
                    config += self._olDelLoopback.render(loopbackUnit=vrf.vrfCounter)
                config += self._olDelVrf.render(vrfName=vrf.name)
                deployments.append(OverlayDeployStatus(config, vrf.getUrl(), "delete", spine, vrf.overlay_tenant.overlay_fabric))

        self._dao.createObjects(dbSession, deployments)
        logger.info("deleteVrf [id: '%s', name: '%s']: configured", vrf.id, vrf.name)
        self._commitQueue.addJobs(deployments)
        self._commitQueue.addDbCleanUp(vrf.getUrl(), force)
    
    def deleteTenant(self, dbSession, tenant, force):
        '''
        Delete tenant
        '''
        logger.info("deleteTenant [id: '%s', name: '%s']: configured", tenant.id, tenant.name)
        self._commitQueue.addDbCleanUp(tenant.getUrl(), force)
    
    def deleteFabric(self, dbSession, fabric, force):
        '''
        Delete Fabric, iBGP         
        '''
        deployedDevices = self._deleteCheck(dbSession, force, fabric.getUrl(), fabric)
        if len(deployedDevices) == 0:
            # Shortcut: if we don't have any deployed device, we can safely delete the object without going to the devices.
            return
            
        logger.info("OverlayFabric[id: '%s', name: '%s']: delete request submitted", fabric.id, fabric.name)
        deployments = []
        for device in fabric.overlay_devices:
            if device in deployedDevices:
                config = self._olDelSwitchOptions.render()

                if device.role == 'spine':
                    config += self._olDelProtocolBgp.render(role="spine")
                    config += self._olDelPolicyOptions.render()
                elif device.role == 'leaf':
                    config += self._olDelProtocolBgp.render(role="leaf")
                    config += self._olDelPolicyOptions.render(remoteGateways=self.getRemoteGateways(fabric, device.podName))
                config += self._olDelProtocolEvpn.render()
                
                deployments.append(OverlayDeployStatus(config, fabric.getUrl(), "delete", device, fabric))

        self._dao.createObjects(dbSession, deployments)
        logger.info("deleteFabric [id: '%s', name: '%s']: configured", fabric.id, fabric.name)
        self._commitQueue.addJobs(deployments)
        self._commitQueue.addDbCleanUp(fabric.getUrl(), force)

# def main():
    # conf = {}
    # conf['outputDir'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'out')
    # conf['plugin'] = [{'name': 'overlay', 'package': 'jnpr.openclos.overlay'}]
    # dao = Dao.getInstance()
    # overlay = Overlay(conf, dao)

    # with dao.getReadWriteSession() as session:
        # d1 = overlay.createDevice(session, 'd1', '', 'spine', '10.92.82.10', '10.92.82.10', 'pod1', 'root', 'Embe1mpls')
        # d2 = overlay.createDevice(session, 'd2', '', 'leaf', '10.92.82.12', '10.92.82.12', 'pod1', 'root', 'Embe1mpls')
        # d3 = overlay.createDevice(session, 'd3', '', 'leaf', '10.92.82.13', '10.92.82.13', 'pod1', 'root', 'Embe1mpls')
        # d4 = overlay.createDevice(session, 'd4', '', 'leaf', '10.92.82.14', '10.92.82.14', 'pod1', 'root', 'Embe1mpls')
        # d1_id = d1.id
        # d2_id = d2.id
        # d3_id = d3.id
        # d4_id = d4.id
        # f1 = overlay.createFabric(session, 'f1', '', 65001, '2.2.2.2', [d1, d2, d3, d4])
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
        # l2port1 = overlay.createL2port(session, 'l2port1', '', [n1], 'xe-0/0/1', d2)
        # l2port1_id = l2port1.id
        # l2port2 = overlay.createL2port(session, 'l2port2', '', [n1, n2, n3], 'xe-0/0/1', d2)
        # l2port2_id = l2port2.id
        # members = [ {'interface': 'xe-0/0/11', 'device': d2}, {'interface': 'xe-0/0/11', 'device': d3} ]
        # aggregatedL2port1 = overlay.createAggregatedL2port(session, 'aggregatedL2port1', '', [n1, n2], members, '00:01:01:01:01:01:01:01:01:01', '00:00:00:01:01:01')
        # aggregatedL2port1_id = aggregatedL2port1.id
        # members = [ {'interface': 'xe-0/0/12', 'device': d2}, {'interface': 'xe-0/0/12', 'device': d4} ]
        # aggregatedL2port2 = overlay.createAggregatedL2port(session, 'aggregatedL2port2', '', [n1, n2], members, '00:02:02:02:02:02:02:02:02:02', '00:00:00:02:02:02')
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
