'''
Created on Nov 23, 2015

@author: yunli
'''

import logging
import os
import itertools
from netaddr import IPNetwork

from jnpr.openclos.overlay.overlayModel import OverlayFabric, OverlayTenant, OverlayVrf, OverlayNetwork, OverlaySubnet, OverlayDevice, OverlayL3port, OverlayL2port, OverlayAe, OverlayDeployStatus
from jnpr.openclos.loader import loadLoggingConfig
from jnpr.openclos.dao import Dao
from jnpr.openclos.templateLoader import TemplateLoader

moduleName = 'overlay'
loadLoggingConfig(appName=moduleName)
logger = logging.getLogger(moduleName)
esiRouteTarget = "9999:9999"

class Overlay():
    def __init__(self, conf, dao):
        self._conf = conf
        self._dao = dao
        self._configEngine = ConfigEngine(conf, dao)
    def createDevice(self, dbSession, name, description, role, address, routerId, podName, username=None, password=None):
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
        vrf.loopbackCounter = self._dao.incrementAndGetCounter("OverlayVrf.loopbackCounter")

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

    def createL2port(self, dbSession, name, description, interface, overlay_networks, overlay_device, overlay_ae=None):
        '''
        Create a new L2port
        '''
        l2port = OverlayL2port(name, description, interface, overlay_networks, overlay_device, overlay_ae)

        self._dao.createObjects(dbSession, [l2port])
        logger.info("OverlayL2port[id: '%s', name: '%s']: created", l2port.id, l2port.name)
        self._configEngine.configureL2Port(dbSession, l2port)
        return l2port

    def createAe(self, dbSession, name, description, esi, lacp):
        '''
        Create a new Ae
        '''
        ae = OverlayAe(name, description, esi, lacp)

        self._dao.createObjects(dbSession, [ae])
        logger.info("OverlayAe[id: '%s', name: '%s']: created", ae.id, ae.name)
        return ae

class ConfigEngine():
    def __init__(self, conf, dao):
        self._conf = conf
        self._dao = dao
        self._templateLoader = TemplateLoader(junosTemplatePackage="jnpr.openclos.overlay")
        

    def configureFabric(self, dbSession, fabric):
        '''
        Generate iBGP config
        '''

        spineIps = []
        leafIps = []
        for device in fabric.overlay_devices:
            if device.role == 'spine':
                spineIps.append(device.address)
            elif device.role == 'leaf':
                leafIps.append(device.address)
            else:
                logger.error("configureFabric: unknown device role, name: %s, ip: %s, role: %s", 
                             device.name, device.address, device.role)
        
        template = self._templateLoader.getTemplate('olAddProtocolBgp.txt')
        deployments = []        
        for device in fabric.overlay_devices:
            if device.role == 'spine':
                routeReflector = fabric.routeReflectorAddress
            elif device.role == 'leaf':
                routeReflector = None

            config = self.configureRoutingOptions(device)
            config += template.render(routeReflector=routeReflector, routerId=device.routerId, asn=fabric.overlayAS, 
                            neighbors=self.getNeighborList(device.address, device.role, spineIps, leafIps))
            config += self.configureSwitchOptions(device.routerId)
            config += self.configurePolicyOptions()
            
            deployments.append(OverlayDeployStatus(config, fabric.getUrl(), "create", device))    

        self._dao.createObjects(dbSession, deployments)
        # TODO: add all deployments to job queue
        logger.info("configureFabric [id: '%s', name: '%s']: configured", fabric.id, fabric.name)
        
    def getNeighborList(self, ip, role, spines, leaves):
        neighbors = []
        if role == 'spine':
            neighbors = [s for s in spines if s != ip]
            neighbors += leaves
        elif role == 'leaf':
            neighbors += spines
        return neighbors
    
    def configureRoutingOptions(self, device):
        if device.role == 'spine':
            template = self._templateLoader.getTemplate('olAddRoutingOptions.txt')
            return template.render(routerId=device.routerId)
        else:
            return ""
    def configureSwitchOptions(self, routerId):
        template = self._templateLoader.getTemplate('olAddSwitchOptions.txt')
        return template.render(routerId=routerId, esiRouteTarget=esiRouteTarget)

    def configurePolicyOptions(self, vni=None, asn=None):
        template = self._templateLoader.getTemplate('olAddPolicyOptions.txt')
        return template.render(vni=vni, esiRTarget=esiRouteTarget, asn=asn)

    def configureVrf(self, dbSession, vrf):
        deployments = []
        loopbackIps = self.getLoopbackIps(vrf.loopbackAddress)
        spines = vrf.getSpines()
        
        if len(loopbackIps) < len(spines):
            logger.error("configureVrf [id: '%s', name: '%s']: loopback IPs count: %d less than spine count: %d", 
                         vrf.id, vrf.name, len(loopbackIps), len(spines))
            
        template = self._templateLoader.getTemplate('olAddVrf.txt')
        for spine, loopback in itertools.izip(spines, loopbackIps):
            config = self.configureLoopback(loopback, vrf.loopbackCounter)
            
            config += template.render(vrfName=vrf.overlay_tenant.name, vrfLoopbackName="lo0." + str(vrf.loopbackCounter), 
                routerId=spine.routerId, asn=vrf.overlay_tenant.overlay_fabric.overlayAS)
            deployments.append(OverlayDeployStatus(config, vrf.getUrl(), "create", spine, vrf))    

        self._dao.createObjects(dbSession, deployments)
        # TODO: add all deployments to job queue
        logger.info("configureVrf [id: '%s', name: '%s']: configured", vrf.id, vrf.name)

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


    def configureNetwork(self, dbSession):
        '''
        IRB needs address, so do not configure network till subnet is added
        '''
        pass
    
    def configureSubnet(self, dbSession, subnet):
        '''
        Create IRB, BD, update VRF, update evpn, update policy
        '''
        deployments = []        
        network = subnet.overlay_network
        vrf = network.overlay_vrf
        spines = vrf.getSpines()
        firstNetwork = vrf.overlay_networks[0]
        asn = vrf.overlay_tenant.overlay_fabric.overlayAS

        irbIps = self.getSubnetIps(subnet.cidr)
        irbVirtualGateway = irbIps.pop(0)
        
        if len(irbIps) < len(spines):
            logger.error("configureSubnet [vrf id: '%s', network id: '%s']: subnet IPs count: %d less than spine count: %d", 
                         vrf.id, network.id, len(irbIps), len(spines))

        irbTemplate = self._templateLoader.getTemplate("olAddIrb.txt")
        vrfTemplate = self._templateLoader.getTemplate("olAddVrf.txt")
        bdTemplate = self._templateLoader.getTemplate("olAddBridgeDomain.txt")
        
        for spine, irbIp in itertools.izip(spines, irbIps):            
            
            config = irbTemplate.render(firstIpFromSubnet=irbVirtualGateway, secondOrThirdIpFromSubnet=irbIp, 
                vlanId=network.vlanid)
            
            config += vrfTemplate.render(vrfName=vrf.overlay_tenant.name, irbName="irb." + str(network.vlanid),
                routerId=spine.routerId, asn=vrf.overlay_tenant.overlay_fabric.overlayAS, vni0=firstNetwork.vnid)
            
            config += self.configureEvpn(network.vnid, asn)
            config += self.configurePolicyOptions(network.vnid, asn)
            config += bdTemplate.render(vlanId=network.vlanid, vxlanId=network.vnid)
            
            deployments.append(OverlayDeployStatus(config, network.getUrl(), "create", spine, vrf))    

        for leaf in vrf.getLeafs():            
            
            config = self.configureEvpn(network.vnid, asn)
            config += self.configurePolicyOptions(network.vnid, asn)
            config += bdTemplate.render(vlanId=network.vlanid, vxlanId=network.vnid)

            deployments.append(OverlayDeployStatus(config, network.getUrl(), "create", leaf, vrf))    

        self._dao.createObjects(dbSession, deployments)
        # TODO: add all deployments to job queue
        logger.info("configureSubnet [network id: '%s', network name: '%s']: configured", network.id, network.name)

        
    def configureEvpn(self, vni=None, asn=None):
        template = self._templateLoader.getTemplate('olAddProtocolEvpn.txt')
        return template.render(vni=vni, asn=asn)
        
            
    def getSubnetIps(self, subnetBlock):
        '''
        returns all usable IPs in CIRD format (1.2.3.4/24) excluding network and broadcast
        '''
        cidr = subnetBlock.split("/")[1]
        ips = [str(ip) + "/" + cidr for ip in IPNetwork(subnetBlock).iter_hosts()]
        return ips        
        
    def configureL2Port(self, dbSession, l2Port):
        '''
        Create access port interface
        '''
        networks = [(net.vlanid, net.vnid) for net in l2Port.overlay_networks]
        vrf = l2Port.overlay_networks[0].overlay_vrf
        template = self._templateLoader.getTemplate('olAddInterface.txt')
        config = template.render(interfaceName=l2Port.interface, networks=networks)

        self._dao.createObjects(dbSession, [OverlayDeployStatus(config, l2Port.getUrl(), "create", l2Port.overlay_device, vrf)])
        # TODO: add all deployments to job queue
        logger.info("configureL2Port [l2Port id: '%s', l2Port name: '%s']: configured", l2Port.id, l2Port.interface)

        

        
        
# def main():        
    # conf = {}
    # conf['outputDir'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'out')
    # conf['plugin'] = [{'name': 'overlay', 'package': 'jnpr.openclos.overlay'}]
    # dao = Dao.getInstance()
    # overlay = Overlay(conf, dao)

    # with dao.getReadWriteSession() as session:
        # d1 = overlay.createDevice(session, 'd1', 'description for d1', 'spine', '1.2.3.4', '1.1.1.1', 'pod1')
        # d2 = overlay.createDevice(session, 'd2', 'description for d2', 'spine', '1.2.3.5', '1.1.1.2', 'pod1', 'test', 'foobar')
        # d1_id = d1.id
        # d2_id = d2.id
        # f1 = overlay.createFabric(session, 'f1', '', 65001, '2.2.2.2', [d1, d2])
        # f1_id = f1.id
        # f2 = overlay.createFabric(session, 'f2', '', 65002, '3.3.3.3', [d1, d2])
        # f2_id = f2.id
        # t1 = overlay.createTenant(session, 't1', '', f1)
        # t1_id = t1.id
        # t2 = overlay.createTenant(session, 't2', '', f2)
        # t2_id = t2.id
        # v1 = overlay.createVrf(session, 'v1', '', 100, '1.1.1.1', t1)
        # v1_id = v1.id
        # v2 = overlay.createVrf(session, 'v2', '', 101, '1.1.1.2', t2)
        # v2_id = v2.id
        # n1 = overlay.createNetwork(session, 'n1', '', v1, 1000, 100, False)
        # n1_id = n1.id
        # n2 = overlay.createNetwork(session, 'n2', '', v1, 1001, 101, False)
        # n2_id = n2.id
        # s1 = overlay.createSubnet(session, 's1', '', n1, '1.2.3.4/24')
        # s1_id = s1.id
        # s2 = overlay.createSubnet(session, 's2', '', n1, '1.2.3.5/24')
        # s2_id = s2.id
        # ae1 = overlay.createAe(session, 'ae1', '', '00:11', '11:00')
        # ae1_id = ae1.id
        # l2port1 = overlay.createL2port(session, 'l2port1', '', 'xe-0/0/1', n1, d1, ae1)
        # l2port1_id = l2port1.id
        # l2port2 = overlay.createL2port(session, 'l2port2', '', 'xe-0/0/1', n1, d2, ae1)
        # l2port2_id = l2port2.id
        
    # with dao.getReadSession() as session:
        # devices = session.query(OverlayDevice).all()
        # for device in devices:
            # print 'device %s: username = %s, encrypted password = %s, cleartext password = %s, hash password = %s' % (device.id, device.username, device.encryptedPassword, device.getCleartextPassword(), device.getHashPassword())
            
    # with dao.getReadSession() as session:
        # v1 = dao.getObjectById(session, OverlayVrf, v1_id)
        # print 'v1.deploy_status = %s' % (v1.deploy_status)
        # v2 = dao.getObjectById(session, OverlayVrf, v2_id)
        # print 'v2.deploy_status = %s' % (v2.deploy_status)
        # d1 = dao.getObjectById(session, OverlayDevice, d1_id)
        # print 'd1.deploy_status = %s' % (d1.deploy_status)
        # d2 = dao.getObjectById(session, OverlayDevice, d2_id)
        # print 'd2.deploy_status = %s' % (d2.deploy_status)
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
        
# if __name__ == '__main__':
    # main()
