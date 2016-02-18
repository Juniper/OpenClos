'''
Created on Nov 23, 2015

@author: yunli
'''
import os
import sys
sys.path.insert(0,os.path.abspath(os.path.dirname(__file__) + '/' + '../../..')) #trick to make it run from CLI

import unittest
import shutil
from jnpr.openclos.overlay.overlay import Overlay
from jnpr.openclos.overlay.overlayModel import OverlayFabric, OverlayTenant, OverlayVrf, OverlayNetwork, OverlaySubnet, OverlayDevice, OverlayL3port, OverlayL2port, OverlayAe, OverlayDeployStatus
from jnpr.openclos.loader import loadLoggingConfig
from jnpr.openclos.dao import Dao

class InMemoryDao(Dao):
    def _getDbUrl(self):
        loadLoggingConfig(appName = 'unittest')
        return 'sqlite:///'
        
class TestOverlayHelper:
    def __init__(self, conf, dao):
        self.overlay = Overlay(conf, dao)
    
    def _createDevice(self, dbSession):
        deviceDict = {
            "name": "d1",
            "description": "description for d1",
            "role": "spine",
            "address": "1.2.3.4",
            "routerId": "1.1.1.1"
        }
        return self.overlay.createDevice(dbSession, deviceDict['name'], deviceDict.get('description'), 
                                         deviceDict['role'], deviceDict['address'], deviceDict['routerId'])
        
    def _createFabric(self, dbSession):
        fabricDict = {
            "name": "f1",
            "description": "description for f1",
            "overlayAsn": 65001,
            "routeReflectorAddress": "2.2.2.2"
        }
        deviceObject = self._createDevice(dbSession)
        return self.overlay.createFabric(dbSession, fabricDict['name'], fabricDict.get('description'), 
                    fabricDict['overlayAsn'], fabricDict['routeReflectorAddress'], [deviceObject])
    
    def _createTenant(self, dbSession):
        tenantDict = {
            "name": "t1",
            "description": "description for t1"
        }
        fabricObject = self._createFabric(dbSession)
        return self.overlay.createTenant(dbSession, tenantDict['name'], tenantDict.get('description'), fabricObject)
        
    def _createVrf(self, dbSession):
        vrfDict = {
            "name": "v1",
            "description": "description for v1",
            "routedVnid": 100,
            "loopbackAddress": "1.1.1.1"
        }
        tenantObject = self._createTenant(dbSession)
        return self.overlay.createVrf(dbSession, vrfDict['name'], vrfDict.get('description'), vrfDict.get('routedVnid'), vrfDict.get('loopbackAddress'), tenantObject)
        
    def _createNetwork(self, dbSession):
        networkDict = {
            "name": "n1",
            "description": "description for n1",
            "vlanid": 1000,
            "vnid": 100,
            "pureL3Int": False
        }
        vrfObject = self._createVrf(dbSession)
        return self.overlay.createNetwork(dbSession, networkDict['name'], networkDict.get('description'), vrfObject, 
                networkDict.get('vlanid'), networkDict.get('vnid'), networkDict.get('pureL3Int'))
        
    def _createSubnet(self, dbSession):
        subnetDict = {
            "name": "s1",
            "description": "description for s1",
            "cidr": "1.2.3.4/24"
        }
        networkObject = self._createNetwork(dbSession)
        return self.overlay.createSubnet(dbSession, subnetDict['name'], subnetDict.get('description'), networkObject, subnetDict['cidr'])
        
    def _createL3port(self, dbSession):
        l3portDict = {
            "name": "l3port1",
            "description": "description for l3port1"
        }
        subnetObject = self._createSubnet(dbSession)
        return self.overlay.createL3port(dbSession, l3portDict['name'], l3portDict.get('description'), subnetObject)
        
    def _createL2port(self, dbSession):
        l2portDict = {
            "name": "l2port1",
            "description": "description for l2port1",
            "interface": "xe-0/0/1"
        }
        networkObject = self._createNetwork(dbSession)
        deviceObject = networkObject.overlay_vrf.overlay_tenant.overlay_fabric.overlay_devices[0]
        return self.overlay.createL2port(dbSession, l2portDict['name'], l2portDict['description'], l2portDict['interface'], networkObject, deviceObject)
        
    def _createAe(self, dbSession):
        aeDict = {
            "name": "ae1",
            "description": "description for ae1",
            "esi": "00:01:01:01:01:01:01:01:01:01",
            "lacp": "00:00:00:01:01:01"
        }
        return self.overlay.createAe(dbSession, aeDict['name'], aeDict.get('description'), aeDict.get('esi'), aeDict.get('lacp'))
        
    def _createDeployStatus(self, dbSession, deviceObject, vrfObject):
        deployStatusDict = {
            "configlet": "v1_config",
            "object_url": "http://host:port/openclos/v1/overlay/vrfs/%s" % (vrfObject.id),
            "status": "failure",
            "statusReason": "conflict",
            "source": "POST"
        }
        configlet = deployStatusDict['configlet']
        object_url = deployStatusDict['object_url']
        status = deployStatusDict['status']
        statusReason = deployStatusDict.get('statusReason')
        source = deployStatusDict.get('source')
        return self.overlay.createDeployStatus(dbSession, configlet, object_url, deviceObject, vrfObject, status, statusReason, source)
        
    
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
        with self._dao.getReadSession() as session:
            self.helper._createDevice(session)
            self.assertEqual(1, session.query(OverlayDevice).count())
            
    def testUpdateDevice(self):        
        with self._dao.getReadWriteSession() as session:        
            deviceObject = self.helper._createDevice(session)
            deviceObject.update('d2', 'description for d2', 'leaf', '1.2.3.5', '1.1.1.2')
            self._dao.updateObjects(session, [deviceObject])
            
        with self._dao.getReadSession() as session:
            self.assertEqual(1, session.query(OverlayDevice).count())
            deviceObjectFromDb = session.query(OverlayDevice).one()
            self.assertEqual('d2', deviceObjectFromDb.name)
            self.assertEqual('description for d2', deviceObjectFromDb.description)
            self.assertEqual('leaf', deviceObjectFromDb.role)
            self.assertEqual('1.2.3.5', deviceObjectFromDb.address)
            self.assertEqual('1.1.1.2', deviceObjectFromDb.routerId)
            
    def testCreateFabric(self):
        with self._dao.getReadSession() as session:
            self.helper._createFabric(session)
            self.assertEqual(1, session.query(OverlayFabric).count())

    def testUpdateFabric(self):
        with self._dao.getReadWriteSession() as session:   
            fabricObject = self.helper._createFabric(session)
            fabricObjectFromDb = session.query(OverlayFabric).one()
            fabricObjectFromDb.clearDevices()
            self._dao.updateObjects(session, [fabricObjectFromDb])
            fabricObjectFromDb.update('f2', 'description for f2', 65002, '3.3.3.3', [])
            self._dao.updateObjects(session, [fabricObjectFromDb])
            
        with self._dao.getReadSession() as session:
            self.assertEqual(1, session.query(OverlayFabric).count())
            fabricObjectFromDb = session.query(OverlayFabric).one()
            self.assertEqual('f2', fabricObjectFromDb.name)
            self.assertEqual('description for f2', fabricObjectFromDb.description)
            self.assertEqual(65002, fabricObjectFromDb.overlayAS)
            self.assertEqual('3.3.3.3', fabricObjectFromDb.routeReflectorAddress)
    
    def testCreateTenant(self):
        with self._dao.getReadSession() as session:
            self.helper._createTenant(session)
            self.assertEqual(1, session.query(OverlayTenant).count())

    def testUpdateTenant(self):
        with self._dao.getReadWriteSession() as session:        
            tenantObject = self.helper._createTenant(session)
            tenantObject.update('t2', 'description for t2')
            self._dao.updateObjects(session, [tenantObject])
            
        with self._dao.getReadSession() as session:
            self.assertEqual(1, session.query(OverlayTenant).count())
            tenantObjectFromDb = session.query(OverlayTenant).one()
            self.assertEqual('t2', tenantObjectFromDb.name)
            self.assertEqual('description for t2', tenantObjectFromDb.description)
            
    def testCreateVrf(self):        
        with self._dao.getReadWriteSession() as session:
            self.helper._createVrf(session)
            self.assertEqual(1, session.query(OverlayVrf).count())

    def testUpdateVrf(self):
        with self._dao.getReadWriteSession() as session:        
            vrfObject = self.helper._createVrf(session)
            vrfObject.update('v2', 'description for v2', 101, '1.1.1.2')
            self._dao.updateObjects(session, [vrfObject])
            
        with self._dao.getReadSession() as session:
            self.assertEqual(1, session.query(OverlayVrf).count())
            vrfObjectFromDb = session.query(OverlayVrf).one()
            self.assertEqual('v2', vrfObjectFromDb.name)
            self.assertEqual('description for v2', vrfObjectFromDb.description)
            self.assertEqual(101, vrfObjectFromDb.routedVnid)
            self.assertEqual('1.1.1.2', vrfObjectFromDb.loopbackAddress)
            
    def testCreateNetwork(self):        
        with self._dao.getReadSession() as session:
            self.helper._createNetwork(session)
            self.assertEqual(1, session.query(OverlayNetwork).count())

    def testUpdateNetwork(self):
        with self._dao.getReadWriteSession() as session:        
            networkObject = self.helper._createNetwork(session)
            networkObject.update('n2', 'description for n2', 1001, 101, True)
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
        with self._dao.getReadSession() as session:
            self.helper._createSubnet(session)
            self.assertEqual(1, session.query(OverlaySubnet).count())

    def testUpdateSubnet(self):
        with self._dao.getReadWriteSession() as session:        
            subnetObject = self.helper._createSubnet(session)
            subnetObject.update('s2', 'description for s2', '1.2.3.5/16')
            self._dao.updateObjects(session, [subnetObject])
            
        with self._dao.getReadSession() as session:
            self.assertEqual(1, session.query(OverlaySubnet).count())
            subnetObjectFromDb = session.query(OverlaySubnet).one()
            self.assertEqual('s2', subnetObjectFromDb.name)
            self.assertEqual('description for s2', subnetObjectFromDb.description)
            self.assertEqual('1.2.3.5/16', subnetObjectFromDb.cidr)
            
    def testCreateL3port(self):
        with self._dao.getReadSession() as session:
            self.helper._createL3port(session)
            self.assertEqual(1, session.query(OverlayL3port).count())
            
    def testUpdateL3port(self):
        with self._dao.getReadWriteSession() as session:        
            l3portObject = self.helper._createL3port(session)
            l3portObject.update('l3port2', 'description for l3port2')
            self._dao.updateObjects(session, [l3portObject])
            
        with self._dao.getReadSession() as session:
            self.assertEqual(1, session.query(OverlayL3port).count())
            l3portObjectFromDb = session.query(OverlayL3port).one()
            self.assertEqual('l3port2', l3portObjectFromDb.name)
            self.assertEqual('description for l3port2', l3portObjectFromDb.description)
            
    def testCreateL2port(self):        
        with self._dao.getReadSession() as session:
            self.helper._createL2port(session)
            self.assertEqual(1, session.query(OverlayL2port).count())
            
    def testUpdateL2port(self):        
        with self._dao.getReadWriteSession() as session:        
            l2portObject = self.helper._createL2port(session)
            l2portObject.update('l2port2', 'description for l2port2', 'xe-1/0/0')
            self._dao.updateObjects(session, [l2portObject])
            
        with self._dao.getReadSession() as session:
            self.assertEqual(1, session.query(OverlayL2port).count())
            l2portObjectFromDb = session.query(OverlayL2port).one()
            self.assertEqual('l2port2', l2portObjectFromDb.name)
            self.assertEqual('description for l2port2', l2portObjectFromDb.description)
            self.assertEqual('xe-1/0/0', l2portObjectFromDb.interface)
            
    def testCreateAe(self):
        with self._dao.getReadSession() as session:
            self.helper._createAe(session)
            self.assertEqual(1, session.query(OverlayAe).count())
            
    def testUpdateAe(self):
        with self._dao.getReadWriteSession() as session:        
            aeObject = self.helper._createAe(session)
            aeObject.update('ae2', 'description for ae2', '11:01:01:01:01:01:01:01:01:01', '11:00:00:01:01:01')
            self._dao.updateObjects(session, [aeObject])
            
        with self._dao.getReadSession() as session:
            self.assertEqual(1, session.query(OverlayAe).count())
            aeObjectFromDb = session.query(OverlayAe).one()
            self.assertEqual('ae2', aeObjectFromDb.name)
            self.assertEqual('description for ae2', aeObjectFromDb.description)
            self.assertEqual('11:01:01:01:01:01:01:01:01:01', aeObjectFromDb.esi)
            self.assertEqual('11:00:00:01:01:01', aeObjectFromDb.lacp)
            
    def testCreateDeployStatus(self):
        with self._dao.getReadSession() as session:
            vrfObject = self.helper._createVrf(session)
            deviceObject = vrfObject.overlay_tenant.overlay_fabric.overlay_devices[0]
            self.helper._createDeployStatus(session, deviceObject, vrfObject)
            self.assertEqual(1, session.query(OverlayDeployStatus).count())

    def testUpdateDeployStatus(self):        
        with self._dao.getReadWriteSession() as session:        
            vrfObject = self.helper._createVrf(session)
            deviceObject = vrfObject.overlay_tenant.overlay_fabric.overlay_devices[0]
            deployStatusObject = self.helper._createDeployStatus(session, deviceObject, vrfObject)
            deployStatusObject.update('progress', 'in progress', 'PUT')
            self._dao.updateObjects(session, [deployStatusObject])
            
        with self._dao.getReadSession() as session:
            self.assertEqual(1, session.query(OverlayDeployStatus).count())
            deployStatusObjectFromDb = session.query(OverlayDeployStatus).one()
            self.assertEqual('progress', deployStatusObjectFromDb.status)
            self.assertEqual('in progress', deployStatusObjectFromDb.statusReason)
            self.assertEqual('PUT', deployStatusObjectFromDb.source)
           
if __name__ == '__main__':
    unittest.main()
