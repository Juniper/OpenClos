'''
Created on Nov 23, 2015

@author: yunli
'''

import yaml
import os
import json
import math
import zlib
import base64
import itertools
import logging

from netaddr import IPNetwork
from sqlalchemy.orm import exc

from jnpr.openclos.overlay.overlayModel import OverlayFabric, OverlayTenant, OverlayVrf, OverlayNetwork, OverlaySubnet, OverlayDevice, OverlayL3port, OverlayL2port, OverlayAe, OverlayDeployStatus
from jnpr.openclos.dao import Dao
from jnpr.openclos.loader import defaultPropertyLocation, OpenClosProperty, DeviceSku, loadLoggingConfig

moduleName = 'overlay'
loadLoggingConfig(appName=moduleName)
logger = logging.getLogger(moduleName)

class Overlay():
    def __init__(self, conf, dao):
        self._conf = conf
        self._dao = dao

    def createDevice(self, name, description, role, address, routerId):
        '''
        Create a new Device
        '''
        device = OverlayDevice(name, description, role, address, routerId)

        with self._dao.getReadWriteSession() as session:
            self._dao.createObjects(session, [device])
            logger.info("OverlayDevice[id='%s', name='%s']: created", device.id, device.name)
            deviceId = device.id
        
        #Hack sqlalchemy: access object is REQUIRED after commit as session has expire_on_commit=True.
        with self._dao.getReadSession() as session:
            device = self._dao.getObjectById(session, OverlayDevice, deviceId)
        return device

    def createFabric(self, name, description, overlayAsn, routeReflectorAddress, devices):
        '''
        Create a new Fabric
        '''
        fabric = OverlayFabric(name, description, overlayAsn, routeReflectorAddress, devices)

        with self._dao.getReadWriteSession() as session:
            self._dao.createObjects(session, [fabric])
            logger.info("OverlayFabric[id='%s', name='%s']: created", fabric.id, fabric.name)
            fabricId = fabric.id
        
        #Hack sqlalchemy: access object is REQUIRED after commit as session has expire_on_commit=True.
        with self._dao.getReadSession() as session:
            fabric = self._dao.getObjectById(session, OverlayFabric, fabricId)
        return fabric

    def createTenant(self, name, description, overlay_fabric):
        '''
        Create a new Tenant
        '''
        tenant = OverlayTenant(name, description, overlay_fabric)

        with self._dao.getReadWriteSession() as session:
            self._dao.createObjects(session, [tenant])
            logger.info("OverlayTenant[id='%s', name='%s']: created", tenant.id, tenant.name)
            tenantId = tenant.id
        
        #Hack sqlalchemy: access object is REQUIRED after commit as session has expire_on_commit=True.
        with self._dao.getReadSession() as session:
            tenant = self._dao.getObjectById(session, OverlayTenant, tenantId)
        return tenant

    def createVrf(self, name, description, routedVnid, overlay_tenant):
        '''
        Create a new Vrf
        '''
        vrf = OverlayVrf(name, description, routedVnid, overlay_tenant)

        with self._dao.getReadWriteSession() as session:
            self._dao.createObjects(session, [vrf])
            logger.info("OverlayVrf[id='%s', name='%s']: created", vrf.id, vrf.name)
            vrfId = vrf.id
        
        #Hack sqlalchemy: access object is REQUIRED after commit as session has expire_on_commit=True.
        with self._dao.getReadSession() as session:
            vrf = self._dao.getObjectById(session, OverlayVrf, vrfId)
        return vrf

    def createNetwork(self, name, description, overlay_vrf, vlanid, vnid, pureL3Int):
        '''
        Create a new Network
        '''
        network = OverlayNetwork(name, description, overlay_vrf, vlanid, vnid, pureL3Int)

        with self._dao.getReadWriteSession() as session:
            self._dao.createObjects(session, [network])
            logger.info("OverlayNetwork[id='%s', name='%s']: created", network.id, network.name)
            networkId = network.id
        
        #Hack sqlalchemy: access object is REQUIRED after commit as session has expire_on_commit=True.
        with self._dao.getReadSession() as session:
            network = self._dao.getObjectById(session, OverlayNetwork, networkId)
        return network

    def createSubnet(self, name, description, overlay_network, cidr):
        '''
        Create a new Subnet
        '''
        subnet = OverlaySubnet(name, description, overlay_network, cidr)

        with self._dao.getReadWriteSession() as session:
            self._dao.createObjects(session, [subnet])
            logger.info("OverlaySubnet[id='%s', name='%s']: created", subnet.id, subnet.name)
            subnetId = subnet.id
        
        #Hack sqlalchemy: access object is REQUIRED after commit as session has expire_on_commit=True.
        with self._dao.getReadSession() as session:
            subnet = self._dao.getObjectById(session, OverlaySubnet, subnetId)
        return subnet

    def createL3port(self, name, description, overlay_subnet):
        '''
        Create a new L3port
        '''
        l3port = OverlayL3port(name, description, overlay_subnet)

        with self._dao.getReadWriteSession() as session:
            self._dao.createObjects(session, [l3port])
            logger.info("OverlayL3port[id='%s', name='%s']: created", l3port.id, l3port.name)
            l3portId = l3port.id
        
        #Hack sqlalchemy: access object is REQUIRED after commit as session has expire_on_commit=True.
        with self._dao.getReadSession() as session:
            l3port = self._dao.getObjectById(session, OverlayL3port, l3portId)
        return l3port

    def createL2port(self, name, description, interface, overlay_ae, overlay_network, overlay_device):
        '''
        Create a new L2port
        '''
        l2port = OverlayL2port(name, description, interface, overlay_ae, overlay_network, overlay_device)

        with self._dao.getReadWriteSession() as session:
            self._dao.createObjects(session, [l2port])
            logger.info("OverlayL2port[id='%s', name='%s']: created", l2port.id, l2port.name)
            l2portId = l2port.id
        
        #Hack sqlalchemy: access object is REQUIRED after commit as session has expire_on_commit=True.
        with self._dao.getReadSession() as session:
            l2port = self._dao.getObjectById(session, OverlayL2port, l2portId)
        return l2port

    def createAe(self, name, description, esi, lacp):
        '''
        Create a new Ae
        '''
        ae = OverlayAe(name, description, esi, lacp)

        with self._dao.getReadWriteSession() as session:
            self._dao.createObjects(session, [ae])
            logger.info("OverlayAe[id='%s', name='%s']: created", ae.id, ae.name)
            aeId = ae.id
        
        #Hack sqlalchemy: access object is REQUIRED after commit as session has expire_on_commit=True.
        with self._dao.getReadSession() as session:
            ae = self._dao.getObjectById(session, OverlayAe, aeId)
        return ae

    def createDeployStatus(self, configlet, object_url, overlay_device, overlay_vrf, status, statusReason, source):
        '''
        Create a new deploy status
        '''
        status = OverlayDeployStatus(configlet, object_url, overlay_device, overlay_vrf, status, statusReason, source)

        with self._dao.getReadWriteSession() as session:
            self._dao.createObjects(session, [status])
            logger.info("OverlayDeployStatus[id='%s', object_url='%s', device='%s, vrf='%s', status='%s', statusReason='%s']: created", status.id, status.object_url, status.overlay_device.name, status.overlay_vrf.name, status.status, status.statusReason)
            statusId = status.id
        
        #Hack sqlalchemy: access object is REQUIRED after commit as session has expire_on_commit=True.
        with self._dao.getReadSession() as session:
            status = self._dao.getObjectById(session, OverlayDeployStatus, statusId)
        return status
        
# def main():        
    # conf = {}
    # conf['outputDir'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'out')
    # conf['plugin'] = [{'name': 'overlay', 'package': 'jnpr.openclos.overlay'}]
    # dao = Dao.getInstance()
    # overlay = Overlay(conf, dao)

    # d1 = overlay.createDevice('d1', 'description for d1', 'spine', '1.2.3.4', '1.1.1.1')
    # d2 = overlay.createDevice('d2', 'description for d2', 'spine', '1.2.3.5', '1.1.1.2')
    # d1_id = d1.id
    # d2_id = d2.id
    # f1 = overlay.createFabric('f1', '', 65001, '2.2.2.2', [d1, d2])
    # f1_id = f1.id
    # f2 = overlay.createFabric('f2', '', 65002, '3.3.3.3', [d1, d2])
    # f2_id = f2.id
    # t1 = overlay.createTenant('t1', '', f1)
    # t1_id = t1.id
    # t2 = overlay.createTenant('t2', '', f2)
    # t2_id = t2.id
    # v1 = overlay.createVrf('v1', '', 100, t1)
    # v1_id = v1.id
    # v2 = overlay.createVrf('v2', '', 101, t2)
    # v2_id = v2.id
    # n1 = overlay.createNetwork('n1', '', v1, 1000, 100, False)
    # n1_id = n1.id
    # n2 = overlay.createNetwork('n2', '', v1, 1001, 101, False)
    # n2_id = n2.id
    # s1 = overlay.createSubnet('s1', '', n1, '1.2.3.4/24')
    # s1_id = s1.id
    # s2 = overlay.createSubnet('s2', '', n1, '1.2.3.5/24')
    # s2_id = s2.id
    # ae1 = overlay.createAe('ae1', '', '00:11', '11:00')
    # ae1_id = ae1.id
    # l2port1 = overlay.createL2port('l2port1', '', 'xe-0/0/1', ae1, n1, d1)
    # l2port1_id = l2port1.id
    # l2port2 = overlay.createL2port('l2port2', '', 'xe-0/0/1', ae1, n1, d2)
    # l2port2_id = l2port2.id
    
    # object_url = '/openclos/v1/overlay/fabrics/' + f1_id
    # overlay.createDeployStatus('f1config', object_url, d1, v1, 'success', 'f1config on d1', 'POST')
    # overlay.createDeployStatus('f1config', object_url, d2, v1, 'success', 'f1config on d2', 'POST')
    # object_url = '/openclos/v1/overlay/vrfs/' + v1_id
    # overlay.createDeployStatus('v1config', object_url, d1, v1, 'success', 'v1config on d1', 'POST')
    # overlay.createDeployStatus('v1config', object_url, d2, v1, 'success', 'v1config on d2', 'POST')
    # object_url = '/openclos/v1/overlay/networks/' + n1_id
    # overlay.createDeployStatus('n1config', object_url, d1, v1, 'success', 'n1config on d1', 'POST')
    # overlay.createDeployStatus('n1config', object_url, d2, v1, 'success', 'n1config on d2', 'POST')
    # object_url = '/openclos/v1/overlay/aes/' + ae1_id
    # overlay.createDeployStatus('ae1config', object_url, d1, v1, 'success', 'ae1config on d1', 'POST')
    # overlay.createDeployStatus('ae1config', object_url, d2, v1, 'success', 'ae1config on d2', 'POST')
    # object_url = '/openclos/v1/overlay/l2ports/' + l2port1_id
    # overlay.createDeployStatus('l2port1config', object_url, d1, v1, 'success', 'l2port1config on d1', 'POST')
    # overlay.createDeployStatus('l2port1config', object_url, d2, v1, 'success', 'l2port1config on d2', 'POST')
    # object_url = '/openclos/v1/overlay/l2ports/' + l2port2_id
    # overlay.createDeployStatus('l2port2config', object_url, d1, v1, 'success', 'l2port2config on d1', 'POST')
    # overlay.createDeployStatus('l2port2config', object_url, d2, v1, 'success', 'l2port2config on d2', 'POST')
    # # object_url = '/openclos/v1/overlay/vrfs/' + v2_id
    # # overlay.createDeployStatus('v2config', object_url, d1, v2, 'success', 'v2config on d1', 'POST')
    # # overlay.createDeployStatus('v2config', object_url, d2, v2, 'success', 'v2config on d2', 'POST')
    
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
        # # status_db = session.query(OverlayDeployStatus).filter(OverlayDeployStatus.overlay_device_id == d1_id).all()
        # # for s in status_db:
            # # s.update('progress', 'd1 in progress', 'POST')
        # # status_db = session.query(OverlayDeployStatus).filter(OverlayDeployStatus.overlay_device_id == d2_id).all()
        # # for s in status_db:
            # # s.update('failure', 'd2 failed', 'POST')
        # object_url = '/openclos/v1/overlay/l2ports/' + l2port2_id
        # status_db = session.query(OverlayDeployStatus).filter(OverlayDeployStatus.object_url == object_url).all()
        # for s in status_db:
            # s.update('failure', 'l2port2 failed', 'POST')
        # object_url = '/openclos/v1/overlay/networks/' + n1_id
        # status_db = session.query(OverlayDeployStatus).filter(OverlayDeployStatus.object_url == object_url).all()
        # for s in status_db:
            # s.update('progress', 'n1 progress', 'POST')
    # raw_input("2 Press Enter to continue...")
    # # with dao.getReadWriteSession() as session:
        # # dao.deleteObject(session, d1)
    # # raw_input("3 Press Enter to continue...")
    # # with dao.getReadSession() as session:
        # # v1 = dao.getObjectById(session, OverlayVrf, v1_id)
        # # print 'v1.deploy_status = %s' % (v1.deploy_status)
        # # v2 = dao.getObjectById(session, OverlayVrf, v2_id)
        # # print 'v2.deploy_status = %s' % (v2.deploy_status)
    # # raw_input("4 Press Enter to continue...")
        
# if __name__ == '__main__':
    # main()
