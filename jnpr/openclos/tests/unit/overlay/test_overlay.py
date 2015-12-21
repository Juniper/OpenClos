'''
Created on Nov 23, 2015

@author: yunli
'''
import os
import sys
sys.path.insert(0,os.path.abspath(os.path.dirname(__file__) + '/' + '../../..')) #trick to make it run from CLI

import unittest
import shutil
from flexmock import flexmock
from jnpr.openclos.overlay.overlay import Overlay
from jnpr.openclos.overlay.overlayModel import OverlayFabric, OverlayTenant, OverlayVrf, OverlayNetwork, OverlaySubnet, OverlayDevice, OverlayL3port, OverlayL2port, OverlayAe, OverlayDeployStatus
from jnpr.openclos.loader import defaultPropertyLocation, OpenClosProperty, DeviceSku, loadLoggingConfig
from jnpr.openclos.dao import Dao

class InMemoryDao(Dao):
    def _getDbUrl(self):
        loadLoggingConfig(appName = 'unittest')
        return 'sqlite:///'
        
class TestOverlayHelper:
    def __init__(self, conf, dao):
        self.overlay = Overlay(conf, dao)
    
    def _createDevice(self):
        deviceDict = {
            "name": "d1",
            "description": "description for d1",
            "role": "spine",
            "address": "1.2.3.4"
        }
        name = deviceDict['name']
        description = deviceDict.get('description')
        role = deviceDict['role']
        address = deviceDict['address']
        return self.overlay.createDevice(name, description, role, address)
        
    def _createFabric(self, deviceObjects):
        fabricDict = {
            "name": "f1",
            "description": "description for f1",
            "overlayAsn": 65001
        }
        name = fabricDict['name']
        description = fabricDict.get('description')
        overlayAsn = fabricDict['overlayAsn']
        return self.overlay.createFabric(name, description, overlayAsn, deviceObjects)
    
    def _createTenant(self, fabricObject):
        tenantDict = {
            "name": "t1",
            "description": "description for t1"
        }
        name = tenantDict['name']
        description = tenantDict.get('description')
        return self.overlay.createTenant(name, description, fabricObject)
        
    def _createVrf(self, tenantObject):
        vrfDict = {
            "name": "v1",
            "description": "description for v1",
            "routedVnid": 100
        }
        name = vrfDict['name']
        description = vrfDict.get('description')
        routedVnid = vrfDict.get('routedVnid')
        return self.overlay.createVrf(name, description, routedVnid, tenantObject)
        
    def _createNetwork(self, vrfObject):
        networkDict = {
            "name": "n1",
            "description": "description for n1",
            "vlanid": 1000,
            "vnid": 100,
            "pureL3Int": False
        }
        name = networkDict['name']
        description = networkDict.get('description')
        vlanid = networkDict.get('vlanid')
        vnid = networkDict.get('vnid')
        pureL3Int = networkDict.get('pureL3Int')
        return self.overlay.createNetwork(name, description, vrfObject, vlanid, vnid, pureL3Int)
        
    def _createSubnet(self, networkObject):
        subnetDict = {
            "name": "s1",
            "description": "description for s1",
            "cidr": "1.2.3.4/24"
        }
        name = subnetDict['name']
        description = subnetDict.get('description')
        cidr = subnetDict['cidr']
        return self.overlay.createSubnet(name, description, networkObject, cidr)
        
    def _createL3port(self, subnetObject):
        l3portDict = {
            "name": "l3port1",
            "description": "description for l3port1"
        }
        name = l3portDict['name']
        description = l3portDict.get('description')
        return self.overlay.createL3port(name, description, subnetObject)
        
    def _createL2port(self, aeObject, networkObject, deviceObject):
        l2portDict = {
            "name": "l2port1",
            "description": "description for l2port1",
            "interface": "xe-0/0/1"
        }
        name = l2portDict['name']
        description = l2portDict.get('description')
        interface = l2portDict['interface']
        return self.overlay.createL2port(name, description, interface, aeObject, networkObject, deviceObject)
        
    def _createAe(self):
        aeDict = {
            "name": "ae1",
            "description": "description for ae1",
            "esi": "00:01:01:01:01:01:01:01:01:01",
            "lacp": "00:00:00:01:01:01"
        }
        name = aeDict['name']
        description = aeDict.get('description')
        esi = aeDict.get('esi')
        lacp = aeDict.get('lacp')
        return self.overlay.createAe(name, description, esi, lacp)
        
    def _createDeployStatus(self, deviceObject, vrfObject):
        deployStatusDict = {
            "configlet": "v1_config",
            "object_url": "http://host:port/openclos/v1/overlay/vrfs/%s" % (vrfObject.id),
            "status": "failure",
            "statusReason": "conflict"
        }
        configlet = deployStatusDict['configlet']
        object_url = deployStatusDict['object_url']
        status = deployStatusDict['status']
        statusReason = deployStatusDict.get('statusReason')
        return self.overlay.createDeployStatus(configlet, object_url, deviceObject, vrfObject, status, statusReason)
        
    
class TestOverlay(unittest.TestCase):
    def setUp(self):
        self._conf = {}
        self._conf['outputDir'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'out')
        self._conf['plugin'] = [{'name': 'overlay', 'package': 'jnpr.openclos.overlay'}]
        self._dao = InMemoryDao.getInstance()
        self.helper = TestOverlayHelper(self._conf, self._dao)
    
    def tearDown(self):
        ''' Deletes 'out' folder under test dir'''
        shutil.rmtree(self._conf['outputDir'], ignore_errors=True)
        InMemoryDao._destroy()
        self.helper = None

    def testCreateDevice(self):
        deviceObject = self.helper._createDevice()
        
        with self._dao.getReadSession() as session:
            self.assertEqual(1, session.query(OverlayDevice).count())
            
    def testUpdateDevice(self):
        deviceObject = self.helper._createDevice()
        deviceObject.update('d2', 'description for d2', 'leaf', '1.2.3.5')
        
        with self._dao.getReadWriteSession() as session:        
            self._dao.updateObjects(session, [deviceObject])
            
        with self._dao.getReadSession() as session:
            self.assertEqual(1, session.query(OverlayDevice).count())
            deviceObjectFromDb = session.query(OverlayDevice).one()
            self.assertEqual('d2', deviceObjectFromDb.name)
            self.assertEqual('description for d2', deviceObjectFromDb.description)
            self.assertEqual('leaf', deviceObjectFromDb.role)
            self.assertEqual('1.2.3.5', deviceObjectFromDb.address)
            
    def testCreateFabric(self):
        deviceObject = self.helper._createDevice()
        fabricObject = self.helper._createFabric([deviceObject])
        
        with self._dao.getReadSession() as session:
            self.assertEqual(1, session.query(OverlayFabric).count())

    def testUpdateFabric(self):
        deviceObject = self.helper._createDevice()
        fabricObject = self.helper._createFabric([deviceObject])
        with self._dao.getReadWriteSession() as session:   
            fabricObjectFromDb = session.query(OverlayFabric).one()
            fabricObjectFromDb.clearDevices()
            self._dao.updateObjects(session, [fabricObjectFromDb])
            fabricObjectFromDb.update('f2', 'description for f2', 65002, [deviceObject])
            self._dao.updateObjects(session, [fabricObjectFromDb])
            
        with self._dao.getReadSession() as session:
            self.assertEqual(1, session.query(OverlayFabric).count())
            fabricObjectFromDb = session.query(OverlayFabric).one()
            self.assertEqual('f2', fabricObjectFromDb.name)
            self.assertEqual('description for f2', fabricObjectFromDb.description)
            self.assertEqual(65002, fabricObjectFromDb.overlayAS)
    
    def testCreateTenant(self):
        deviceObject = self.helper._createDevice()
        fabricObject = self.helper._createFabric([deviceObject])
        tenantObject = self.helper._createTenant(fabricObject)
        
        with self._dao.getReadSession() as session:
            self.assertEqual(1, session.query(OverlayTenant).count())

    def testUpdateTenant(self):
        deviceObject = self.helper._createDevice()
        fabricObject = self.helper._createFabric([deviceObject])
        tenantObject = self.helper._createTenant(fabricObject)
        tenantObject.update('t2', 'description for t2')
        
        with self._dao.getReadWriteSession() as session:        
            self._dao.updateObjects(session, [tenantObject])
            
        with self._dao.getReadSession() as session:
            self.assertEqual(1, session.query(OverlayTenant).count())
            tenantObjectFromDb = session.query(OverlayTenant).one()
            self.assertEqual('t2', tenantObjectFromDb.name)
            self.assertEqual('description for t2', tenantObjectFromDb.description)
            
    def testCreateVrf(self):
        deviceObject = self.helper._createDevice()
        fabricObject = self.helper._createFabric([deviceObject])
        tenantObject = self.helper._createTenant(fabricObject)
        vrfObject = self.helper._createVrf(tenantObject)
        
        with self._dao.getReadSession() as session:
            self.assertEqual(1, session.query(OverlayVrf).count())

    def testUpdateVrf(self):
        deviceObject = self.helper._createDevice()
        fabricObject = self.helper._createFabric([deviceObject])
        tenantObject = self.helper._createTenant(fabricObject)
        vrfObject = self.helper._createVrf(tenantObject)
        vrfObject.update('v2', 'description for v2', 101)
        
        with self._dao.getReadWriteSession() as session:        
            self._dao.updateObjects(session, [vrfObject])
            
        with self._dao.getReadSession() as session:
            self.assertEqual(1, session.query(OverlayVrf).count())
            vrfObjectFromDb = session.query(OverlayVrf).one()
            self.assertEqual('v2', vrfObjectFromDb.name)
            self.assertEqual('description for v2', vrfObjectFromDb.description)
            self.assertEqual(101, vrfObjectFromDb.routedVnid)
            
    def testCreateNetwork(self):
        deviceObject = self.helper._createDevice()
        fabricObject = self.helper._createFabric([deviceObject])
        tenantObject = self.helper._createTenant(fabricObject)
        vrfObject = self.helper._createVrf(tenantObject)
        networkObject = self.helper._createNetwork(vrfObject)
        
        with self._dao.getReadSession() as session:
            self.assertEqual(1, session.query(OverlayNetwork).count())

    def testUpdateNetwork(self):
        deviceObject = self.helper._createDevice()
        fabricObject = self.helper._createFabric([deviceObject])
        tenantObject = self.helper._createTenant(fabricObject)
        vrfObject = self.helper._createVrf(tenantObject)
        networkObject = self.helper._createNetwork(vrfObject)
        networkObject.update('n2', 'description for n2', 1001, 101, True)
        
        with self._dao.getReadWriteSession() as session:        
            self._dao.updateObjects(session, [networkObject])
            
        with self._dao.getReadSession() as session:
            self.assertEqual(1, session.query(OverlayNetwork).count())
            networkObjectFromDb = session.query(OverlayNetwork).one()
            self.assertEqual('n2', networkObjectFromDb.name)
            self.assertEqual('description for n2', networkObjectFromDb.description)
            self.assertEqual(1001, networkObjectFromDb.vlanid)
            self.assertEqual(101, networkObjectFromDb.vnid)
            self.assertEqual(True, networkObjectFromDb.pureL3Int)
            
    def testCreateSubnet(self):
        deviceObject = self.helper._createDevice()
        fabricObject = self.helper._createFabric([deviceObject])
        tenantObject = self.helper._createTenant(fabricObject)
        vrfObject = self.helper._createVrf(tenantObject)
        networkObject = self.helper._createNetwork(vrfObject)
        subnetObject = self.helper._createSubnet(networkObject)
        
        with self._dao.getReadSession() as session:
            self.assertEqual(1, session.query(OverlaySubnet).count())

    def testUpdateSubnet(self):
        deviceObject = self.helper._createDevice()
        fabricObject = self.helper._createFabric([deviceObject])
        tenantObject = self.helper._createTenant(fabricObject)
        vrfObject = self.helper._createVrf(tenantObject)
        networkObject = self.helper._createNetwork(vrfObject)
        subnetObject = self.helper._createSubnet(networkObject)
        subnetObject.update('s2', 'description for s2', '1.2.3.5/16')
        
        with self._dao.getReadWriteSession() as session:        
            self._dao.updateObjects(session, [subnetObject])
            
        with self._dao.getReadSession() as session:
            self.assertEqual(1, session.query(OverlaySubnet).count())
            subnetObjectFromDb = session.query(OverlaySubnet).one()
            self.assertEqual('s2', subnetObjectFromDb.name)
            self.assertEqual('description for s2', subnetObjectFromDb.description)
            self.assertEqual('1.2.3.5/16', subnetObjectFromDb.cidr)
            
    def testCreateL3port(self):
        deviceObject = self.helper._createDevice()
        fabricObject = self.helper._createFabric([deviceObject])
        tenantObject = self.helper._createTenant(fabricObject)
        vrfObject = self.helper._createVrf(tenantObject)
        networkObject = self.helper._createNetwork(vrfObject)
        subnetObject = self.helper._createSubnet(networkObject)
        l3portObject = self.helper._createL3port(subnetObject)
        
        with self._dao.getReadSession() as session:
            self.assertEqual(1, session.query(OverlayL3port).count())
            
    def testUpdateL3port(self):
        deviceObject = self.helper._createDevice()
        fabricObject = self.helper._createFabric([deviceObject])
        tenantObject = self.helper._createTenant(fabricObject)
        vrfObject = self.helper._createVrf(tenantObject)
        networkObject = self.helper._createNetwork(vrfObject)
        subnetObject = self.helper._createSubnet(networkObject)
        l3portObject = self.helper._createL3port(subnetObject)
        l3portObject.update('l3port2', 'description for l3port2')
        
        with self._dao.getReadWriteSession() as session:        
            self._dao.updateObjects(session, [l3portObject])
            
        with self._dao.getReadSession() as session:
            self.assertEqual(1, session.query(OverlayL3port).count())
            l3portObjectFromDb = session.query(OverlayL3port).one()
            self.assertEqual('l3port2', l3portObjectFromDb.name)
            self.assertEqual('description for l3port2', l3portObjectFromDb.description)
            
    def testCreateL2port(self):
        deviceObject = self.helper._createDevice()
        fabricObject = self.helper._createFabric([deviceObject])
        tenantObject = self.helper._createTenant(fabricObject)
        vrfObject = self.helper._createVrf(tenantObject)
        networkObject = self.helper._createNetwork(vrfObject)
        deviceObject = self.helper._createDevice()
        aeObject = self.helper._createAe()
        l2portObject = self.helper._createL2port(aeObject, networkObject, deviceObject)
        
        with self._dao.getReadSession() as session:
            self.assertEqual(1, session.query(OverlayL2port).count())
            
    def testUpdateL2port(self):
        deviceObject = self.helper._createDevice()
        fabricObject = self.helper._createFabric([deviceObject])
        tenantObject = self.helper._createTenant(fabricObject)
        vrfObject = self.helper._createVrf(tenantObject)
        networkObject = self.helper._createNetwork(vrfObject)
        deviceObject = self.helper._createDevice()
        aeObject = self.helper._createAe()
        l2portObject = self.helper._createL2port(aeObject, networkObject, deviceObject)
        l2portObject.update('l2port2', 'description for l2port2', 'xe-1/0/0')
        
        with self._dao.getReadWriteSession() as session:        
            self._dao.updateObjects(session, [l2portObject])
            
        with self._dao.getReadSession() as session:
            self.assertEqual(1, session.query(OverlayL2port).count())
            l2portObjectFromDb = session.query(OverlayL2port).one()
            self.assertEqual('l2port2', l2portObjectFromDb.name)
            self.assertEqual('description for l2port2', l2portObjectFromDb.description)
            self.assertEqual('xe-1/0/0', l2portObjectFromDb.interface)
            
    def testCreateAe(self):
        aeObject = self.helper._createAe()
        
        with self._dao.getReadSession() as session:
            self.assertEqual(1, session.query(OverlayAe).count())
            
    def testUpdateAe(self):
        aeObject = self.helper._createAe()
        aeObject.update('ae2', 'description for ae2', '11:01:01:01:01:01:01:01:01:01', '11:00:00:01:01:01')
        
        with self._dao.getReadWriteSession() as session:        
            self._dao.updateObjects(session, [aeObject])
            
        with self._dao.getReadSession() as session:
            self.assertEqual(1, session.query(OverlayAe).count())
            aeObjectFromDb = session.query(OverlayAe).one()
            self.assertEqual('ae2', aeObjectFromDb.name)
            self.assertEqual('description for ae2', aeObjectFromDb.description)
            self.assertEqual('11:01:01:01:01:01:01:01:01:01', aeObjectFromDb.esi)
            self.assertEqual('11:00:00:01:01:01', aeObjectFromDb.lacp)
            
    def testCreateDeployStatus(self):
        deviceObject = self.helper._createDevice()
        fabricObject = self.helper._createFabric([deviceObject])
        tenantObject = self.helper._createTenant(fabricObject)
        vrfObject = self.helper._createVrf(tenantObject)
        deployStatusObject = self.helper._createDeployStatus(deviceObject, vrfObject)
        
        with self._dao.getReadSession() as session:
            self.assertEqual(1, session.query(OverlayDeployStatus).count())

    def testUpdateDeployStatus(self):
        deviceObject = self.helper._createDevice()
        fabricObject = self.helper._createFabric([deviceObject])
        tenantObject = self.helper._createTenant(fabricObject)
        vrfObject = self.helper._createVrf(tenantObject)
        deployStatusObject = self.helper._createDeployStatus(deviceObject, vrfObject)
        deployStatusObject.update('progress', 'in progress')
        
        with self._dao.getReadWriteSession() as session:        
            self._dao.updateObjects(session, [deployStatusObject])
            
        with self._dao.getReadSession() as session:
            self.assertEqual(1, session.query(OverlayDeployStatus).count())
            deployStatusObjectFromDb = session.query(OverlayDeployStatus).one()
            self.assertEqual('progress', deployStatusObjectFromDb.status)
            self.assertEqual('in progress', deployStatusObjectFromDb.statusReason)
           
if __name__ == '__main__':
    unittest.main()