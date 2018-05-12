'''
Created on Nov 23, 2015

@author: yunli
'''
import os
import sys
import re
sys.path.insert(0,os.path.abspath(os.path.dirname(__file__) + '/' + '../../..')) #trick to make it run from CLI

import unittest
from jnpr.openclos.overlay.overlayModel import OverlayFabric, OverlayTenant, OverlayVrf, OverlayNetwork, OverlaySubnet, OverlayDevice, OverlayL3port, OverlayL2port, OverlayAggregatedL2port, OverlayDeployStatus
from jnpr.openclos.tests.unit.test_dao import InMemoryDao
from jnpr.openclos.overlay.overlayCommit import OverlayCommitQueue
from jnpr.openclos.overlay.overlay import ConfigEngine
from jnpr.openclos.loader import loadLoggingConfig
from jnpr.openclos.dao import Dao

class TempFileDao(Dao):
    def _getDbUrl(self):
        loadLoggingConfig(appName = 'unittest')
        return 'sqlite:////tmp/sqllite3.db'
        
class TestOverlayHelper:
    def __init__(self, conf, dao, overlay=None):
        if overlay is not None:
            self.overlay = overlay
        else:
            import jnpr.openclos.overlay.overlay
            self.overlay = jnpr.openclos.overlay.overlay.Overlay(conf, dao)
    
    def _createDevice(self, dbSession, offset="1", role="spine", podName="pod1"):
        deviceDict = {
            "name": "d" + offset,
            "description": "description for d" + offset,
            "role": role,
            "address": "1.2.3." + offset,
            "routerId": "1.1.1." + offset,
            "podName": podName,
            "username": "root",
            "password": "testing123"
        }
        return self.overlay.createDevice(dbSession, deviceDict['name'], deviceDict.get('description'), 
                                         deviceDict['role'], deviceDict['address'], deviceDict['routerId'], deviceDict['podName'], deviceDict['username'], deviceDict['password'])
        
    def _createFabric(self, dbSession, offset="1"):
        fabricDict = {
            "name": "f" + offset,
            "description": "description for f" + offset,
            "overlayAsn": 65001,
            "routeReflectorAddress": "2.2." + offset + ".0/24"
        }
        deviceObject = self._createDevice(dbSession, offset)
        return self.overlay.createFabric(dbSession, fabricDict['name'], fabricDict.get('description'), 
                    fabricDict['overlayAsn'], fabricDict['routeReflectorAddress'], [deviceObject])
    
    def _createFabric2Spine3Leaf(self, dbSession):
        devices = []
        devices.append(self._createDevice(dbSession, "1", "spine"))
        devices.append(self._createDevice(dbSession, "2", "spine"))
        devices.append(self._createDevice(dbSession, "3", "leaf"))
        devices.append(self._createDevice(dbSession, "4", "leaf"))
        devices.append(self._createDevice(dbSession, "5", "leaf"))
        fabricDict = {
            "name": "f1",
            "description": "description for f1",
            "overlayAsn": 65001,
            "routeReflectorAddress": "2.2.1.0/24"
        }
        return self.overlay.createFabric(dbSession, fabricDict['name'], fabricDict.get('description'), 
                    fabricDict['overlayAsn'], fabricDict['routeReflectorAddress'], devices)

    def _createFabric2Pods(self, dbSession):
        devices = []
        devices.append(self._createDevice(dbSession, "1", "spine", "pod1"))
        devices.append(self._createDevice(dbSession, "2", "spine", "pod1"))
        devices.append(self._createDevice(dbSession, "3", "leaf", "pod1"))
        devices.append(self._createDevice(dbSession, "4", "leaf", "pod1"))
        devices.append(self._createDevice(dbSession, "5", "leaf", "pod1"))

        devices.append(self._createDevice(dbSession, "6", "spine", "pod2"))
        devices.append(self._createDevice(dbSession, "7", "spine", "pod2"))
        devices.append(self._createDevice(dbSession, "8", "leaf", "pod2"))
        devices.append(self._createDevice(dbSession, "9", "leaf", "pod2"))

        fabricDict = {
            "name": "f1",
            "description": "description for f1",
            "overlayAsn": 65001,
            "routeReflectorAddress": "2.2.1.0/24"
        }
        return self.overlay.createFabric(dbSession, fabricDict['name'], fabricDict.get('description'), 
                    fabricDict['overlayAsn'], fabricDict['routeReflectorAddress'], devices)

    def _createTenant(self, dbSession, offset="1", fabricObject=None):
        tenantDict = {
            "name": "t" + offset,
            "description": "description for t" + offset
        }
        if not fabricObject:
            fabricObject = self._createFabric(dbSession, offset)
        return self.overlay.createTenant(dbSession, tenantDict['name'], tenantDict.get('description'), fabricObject)
        
    def _createVrf(self, dbSession, offset="1", tenantObject=None):
        vrfDict = {
            "name": "v" + offset,
            "description": "description for v" + offset,
            "routedVnid": 100,
            "loopbackAddress": "1.1.1." + offset + "/30"
        }
        if not tenantObject:
            tenantObject = self._createTenant(dbSession, offset)
        return self.overlay.createVrf(dbSession, vrfDict['name'], vrfDict.get('description'), vrfDict.get('routedVnid'), vrfDict.get('loopbackAddress'), tenantObject)
        
    def _createNetwork(self, dbSession, offset="1", vrfObject=None):
        networkDict = {
            "name": "n" + offset,
            "description": "description for n" + offset,
            "vlanid": 100 + int(offset),
            "vnid": 1000 + int(offset),
            "pureL3Int": False
        }
        if not vrfObject:
            vrfObject = self._createVrf(dbSession, offset)
        return self.overlay.createNetwork(dbSession, networkDict['name'], networkDict.get('description'), vrfObject, 
                networkDict.get('vlanid'), networkDict.get('vnid'), networkDict.get('pureL3Int'))
        
    def _createSubnet(self, dbSession, offset="1", networkObject=None):
        subnetDict = {
            "name": "s" + offset,
            "description": "description for s" + offset,
            "cidr": offset+".2.3.4/24"
        }
        if not networkObject:
            networkObject = self._createNetwork(dbSession, offset)
        return self.overlay.createSubnet(dbSession, subnetDict['name'], subnetDict.get('description'), networkObject, subnetDict['cidr'])
        
    def _createNetworkOn2By3Fabric(self, dbSession):
        fabric = self._createFabric2Spine3Leaf(dbSession)
        tenant = self._createTenant(dbSession, fabricObject=fabric)
        vrf = self._createVrf(dbSession, tenantObject=tenant)
        return self._createNetwork(dbSession, vrfObject=vrf)
        
    def _createSubnetOn2By3Fabric(self, dbSession):
        network = self._createNetworkOn2By3Fabric(dbSession)
        return self._createSubnet(dbSession, networkObject=network)
        
    def _create2NetworkOn2By3Fabric(self, dbSession):
        fabric = self._createFabric2Spine3Leaf(dbSession)
        tenant = self._createTenant(dbSession, fabricObject=fabric)
        vrf = self._createVrf(dbSession, tenantObject=tenant)
        network1 = self._createNetwork(dbSession, offset="1", vrfObject=vrf)
        network2 = self._createNetwork(dbSession, offset="2", vrfObject=vrf)
        return [self._createSubnet(dbSession, offset="1", networkObject=network1),
                self._createSubnet(dbSession, offset="2", networkObject=network2)]

    def _createL3port(self, dbSession):
        l3portDict = {
            "name": "l3port1",
            "description": "description for l3port1"
        }
        subnetObject = self._createSubnet(dbSession)
        return self.overlay.createL3port(dbSession, l3portDict['name'], l3portDict.get('description'), subnetObject)
        
    def _createL2port(self, dbSession, networkObject=None):
        l2portDict = {
            "name": "l2port1",
            "description": "description for l2port1",
            "interface": "xe-0/0/1",
            "enterprise": False
        }
        if not networkObject:
            networkObject = self._createNetwork(dbSession)
        deviceObject = networkObject.overlay_vrf.overlay_tenant.overlay_fabric.overlay_devices[0]
        return self.overlay.createL2port(dbSession, l2portDict['name'], l2portDict['description'], [networkObject], l2portDict['interface'], deviceObject,l2portDict['enterprise'])

    def _create2Network4L2port(self, dbSession):
        networkObject1 = self._createNetwork(dbSession, offset="1")
        networkObject2 = self._createNetwork(dbSession, offset="2", vrfObject=networkObject1.overlay_vrf)
        deviceObject = networkObject1.overlay_vrf.overlay_tenant.overlay_fabric.overlay_devices[0]
        
        port1 = self.overlay.createL2port(dbSession, "l2port1", "description for l2port1", [networkObject1], "xe-0/0/1", deviceObject,False)
        port2 = self.overlay.createL2port(dbSession, "l2port2", "description for l2port2", [networkObject2], "xe-0/0/2", deviceObject,False)
        port3 = self.overlay.createL2port(dbSession, "l2port3", "description for l2port3", [networkObject1, networkObject2], "xe-0/0/3", deviceObject,False)
        port4 = self.overlay.createL2port(dbSession, "l2port4", "description for l2port4", [networkObject1], "xe-0/0/4", deviceObject,False)
        return [port1, port2, port3, port4]

    def _createAggregatedL2port(self, dbSession):
        aggregatedL2portDict = {
            "name": "ae0",
            "description": "description for ae0",
            "esi": "00:01:01:01:01:01:01:01:01:01",
            "lacp": "00:00:00:01:01:01",
            "enterprise": False
        }
        networkObject = self._createNetwork(dbSession)
        deviceObject = networkObject.overlay_vrf.overlay_tenant.overlay_fabric.overlay_devices[0]
        aggregatedL2portMembers = [{ "interface": "xe-0/0/11", "device": deviceObject }]
        aggregatedL2portObject = self.overlay.createAggregatedL2port(dbSession, aggregatedL2portDict['name'], aggregatedL2portDict.get('description'), [networkObject], aggregatedL2portMembers, aggregatedL2portDict.get('esi'), aggregatedL2portDict.get('lacp'), aggregatedL2portDict.get('enterprise'))
        return aggregatedL2portObject
        
    def _create2Network3AggregatedL2port(self, dbSession):
        networkObject1 = self._createNetwork(dbSession, offset="1")
        networkObject2 = self._createNetwork(dbSession, offset="2", vrfObject=networkObject1.overlay_vrf)
        deviceObject = networkObject1.overlay_vrf.overlay_tenant.overlay_fabric.overlay_devices[0]
        
        members1 = [{ "interface": "xe-0/0/11", "device": deviceObject }]
        ae0 = self.overlay.createAggregatedL2port(dbSession, "ae0", "description for ae0", [networkObject1], members1, "00:01:01:01:01:01:01:01:01:01", "00:00:00:01:01:01",False)
        members2 = [{ "interface": "xe-0/0/12", "device": deviceObject }]
        ae1 = self.overlay.createAggregatedL2port(dbSession, "ae1", "description for ae1", [networkObject2], members2, "00:01:01:01:01:01:01:01:01:02", "00:00:00:01:01:02",False)
        members3 = [{ "interface": "xe-0/0/13", "device": deviceObject }]
        ae2 = self.overlay.createAggregatedL2port(dbSession, "ae2", "description for ae2", [networkObject1, networkObject2], members3, "00:01:01:01:01:01:01:01:01:03", "00:00:00:01:01:03",False)
        return [ae0, ae1, ae2]

    def _createDeployStatus(self, dbSession, deviceObject, vrfObject):
        deployStatusDict = {
            "configlet": "v1_config",
            "object_url": "http://host:port/openclos/v1/overlay/vrfs/%s" % (vrfObject.id),
            "status": "failure",
            "statusReason": "conflict",
            "operation": "create"
        }
        status = OverlayDeployStatus(deployStatusDict['configlet'], deployStatusDict['object_url'], 
            deployStatusDict['operation'], deviceObject, vrfObject.overlay_tenant.overlay_fabric, deployStatusDict['status'], deployStatusDict['statusReason'])
        dbSession.add_all([status])
        dbSession.commit()
        return status
    
class TestOverlay(unittest.TestCase):
    def setUp(self):
        if os.path.isfile('/tmp/sqllite3.db'):
            os.remove('/tmp/sqllite3.db')
        from jnpr.openclos import deviceConnector
        deviceConnector.DEFAULT_AUTO_PROBE = 3
        self._dao = TempFileDao.getInstance()
        from jnpr.openclos.tests.unit.overlay.test_overlay import TestOverlayHelper
        self.helper = TestOverlayHelper({}, self._dao)
        self.helper.overlay._configEngine._commitQueue.dbCleanUpInterval = 1
        self.helper.overlay._configEngine._commitQueue.deviceInterval = 1
        self.helper.overlay.startCommitQueue()
    
    def tearDown(self):
        self.helper.overlay.stopCommitQueue()
        self.helper = None
        TempFileDao._destroy()
        if os.path.isfile('/tmp/sqllite3.db'):
            os.remove('/tmp/sqllite3.db')

    def testCreateDevice(self):
        with self._dao.getReadWriteSession() as session:
            self.helper._createDevice(session)
            
        with self._dao.getReadSession() as session:
            self.assertEqual(1, session.query(OverlayDevice).count())
            deviceObjectFromDb = session.query(OverlayDevice).one()
            self.assertEqual('d1', deviceObjectFromDb.name)
            self.assertEqual('description for d1', deviceObjectFromDb.description)
            self.assertEqual('spine', deviceObjectFromDb.role)
            self.assertEqual('1.2.3.1', deviceObjectFromDb.address)
            self.assertEqual('1.1.1.1', deviceObjectFromDb.routerId)
            self.assertEqual('pod1', deviceObjectFromDb.podName)
            self.assertEqual('root', deviceObjectFromDb.username)
            self.assertEqual('testing123', deviceObjectFromDb.getCleartextPassword())
            
    def testCreateDuplicateDevice(self):
        with self.assertRaises(Exception) as e:
            with self._dao.getReadWriteSession() as session:
                self.helper._createDevice(session)
                self.helper._createDevice(session)
        import sqlalchemy
        self.assertTrue(type(e.exception) is sqlalchemy.exc.IntegrityError)
            
    def testUpdateDevice(self):        
        with self._dao.getReadWriteSession() as session:        
            deviceObject = self.helper._createDevice(session)
            self.helper.overlay.modifyDevice(session, deviceObject, 'test', 'foobar')
            
        with self._dao.getReadSession() as session:
            self.assertEqual(1, session.query(OverlayDevice).count())
            deviceObjectFromDb = session.query(OverlayDevice).one()
            self.assertEqual('test', deviceObjectFromDb.username)
            self.assertEqual('foobar', deviceObjectFromDb.getCleartextPassword())
            
    def testCreateFabric(self):
        with self._dao.getReadWriteSession() as session:
            self.helper._createFabric(session)
            self.assertEqual(1, session.query(OverlayFabric).count())
            self.assertEqual(1, session.query(OverlayDeployStatus).count())

    def testCreateDuplicateFabric(self):
        with self.assertRaises(Exception) as e:
            with self._dao.getReadWriteSession() as session:
                self.helper._createFabric(session)
                self.helper._createFabric(session)
        import sqlalchemy
        self.assertTrue(type(e.exception) is sqlalchemy.exc.IntegrityError)
            
    def testUpdateFabric(self):
        with self._dao.getReadWriteSession() as session:   
            fabricObject = self.helper._createFabric(session)
            self.helper.overlay.modifyFabric(session, fabricObject, 65002, '2.2.1.0/24', [])
            
        with self._dao.getReadSession() as session:
            self.assertEqual(1, session.query(OverlayFabric).count())
            fabricObjectFromDb = session.query(OverlayFabric).one()
            self.assertEqual(65002, fabricObjectFromDb.overlayAS)
            self.assertEqual('2.2.1.0/24', fabricObjectFromDb.routeReflectorAddress)
            self.assertEqual(0, len(fabricObjectFromDb.overlay_devices))
    
    def testCreateTenant(self):
        with self._dao.getReadWriteSession() as session:
            self.helper._createTenant(session)
            self.assertEqual(1, session.query(OverlayTenant).count())

    def testCreateVrf(self):        
        with self._dao.getReadWriteSession() as session:
            self.helper._createVrf(session)
            self.assertEqual(1, session.query(OverlayVrf).count())

    def testCreateVrfLoopbackCounter(self):
        with self._dao.getReadWriteSession() as session:
            vrf1 = self.helper._createVrf(session, "1")
            self.helper._createVrf(session, "2", tenantObject=vrf1.overlay_tenant)
            self.helper._createVrf(session, "3", tenantObject=vrf1.overlay_tenant)
            self.helper._createVrf(session, "4", tenantObject=vrf1.overlay_tenant)
            self.helper._createVrf(session, "5", tenantObject=vrf1.overlay_tenant)
            vrfs = session.query(OverlayVrf).all()
            self.assertEquals(5, len(vrfs))
            self.assertEquals(1, vrfs[0].vrfCounter)
            self.assertEquals(2, vrfs[1].vrfCounter)
            self.assertEquals(3, vrfs[2].vrfCounter)
            self.assertEquals(5, vrfs[4].vrfCounter)

    def testUpdateVrf(self):
        with self._dao.getReadWriteSession() as session:        
            vrfObject = self.helper._createVrf(session)
            self.helper.overlay.modifyVrf(session, vrfObject, '1.1.1.2')
            
        with self._dao.getReadSession() as session:
            self.assertEqual(1, session.query(OverlayVrf).count())
            vrfObjectFromDb = session.query(OverlayVrf).one()
            self.assertEqual('1.1.1.2', vrfObjectFromDb.loopbackAddress)
            
    def testCreateNetwork(self):        
        with self._dao.getReadWriteSession() as session:
            self.helper._createNetwork(session)
            self.assertEqual(1, session.query(OverlayNetwork).count())

    def testUpdateNetwork(self):
        with self._dao.getReadWriteSession() as session:        
            networkObject = self.helper._createNetwork(session)
            self.helper.overlay.modifyNetwork(session, networkObject, 1001, 101)
            
        with self._dao.getReadSession() as session:
            self.assertEqual(1, session.query(OverlayNetwork).count())
            networkObjectFromDb = session.query(OverlayNetwork).one()
            self.assertEqual(1001, networkObjectFromDb.vlanid)
            self.assertEqual(101, networkObjectFromDb.vnid)
            
    def testCreateSubnet(self):        
        with self._dao.getReadWriteSession() as session:
            self.helper._createSubnet(session)
            self.assertEqual(1, session.query(OverlaySubnet).count())

    def testUpdateSubnet(self):
        with self._dao.getReadWriteSession() as session:        
            subnetObject = self.helper._createSubnet(session)
            self.helper.overlay.modifySubnet(session, subnetObject, '1.2.3.5/16')
            
        with self._dao.getReadSession() as session:
            self.assertEqual(1, session.query(OverlaySubnet).count())
            subnetObjectFromDb = session.query(OverlaySubnet).one()
            self.assertEqual('1.2.3.5/16', subnetObjectFromDb.cidr)
            
    def testCreateL3port(self):
        with self._dao.getReadWriteSession() as session:
            self.helper._createL3port(session)
            self.assertEqual(1, session.query(OverlayL3port).count())
            
    def testCreateL2port(self):        
        with self._dao.getReadWriteSession() as session:
            self.helper._createL2port(session)
            self.assertEqual(1, session.query(OverlayL2port).count())
            
    def testCreateL2portManyToManyNetwork(self):        
        with self._dao.getReadWriteSession() as session:
            self.helper._create2Network4L2port(session)
            ports = session.query(OverlayL2port).all()
            self.assertEqual(4, len(ports))
            self.assertEqual(1, len(ports[0].overlay_networks))
            self.assertEqual(2, len(ports[2].overlay_networks))
            self.assertEqual(3, len(ports[0].overlay_networks[0].overlay_l2aps))
            self.assertEqual(2, len(ports[1].overlay_networks[0].overlay_l2aps))

    def testUpdateL2port(self):        
        with self._dao.getReadWriteSession() as session:        
            self.helper._create2Network4L2port(session)
            ports = session.query(OverlayL2port).all()
            self.helper.overlay.modifyL2port(session, ports[0], ports[2].overlay_networks)
            
        with self._dao.getReadSession() as session:
            ports = session.query(OverlayL2port).all()
            self.assertEqual(2, len(ports[0].overlay_networks))
            
    def testCreateAggregatedL2port(self):
        with self._dao.getReadWriteSession() as session:
            self.helper._createAggregatedL2port(session)
            self.assertEqual(1, session.query(OverlayAggregatedL2port).count())
            
    def testUpdateAggregatedL2port(self):
        with self._dao.getReadWriteSession() as session:        
            aggregatedL2portObject = self.helper._createAggregatedL2port(session)
            aggregatedL2ports = session.query(OverlayAggregatedL2port).all()
            networkObjects = session.query(OverlayNetwork).all()
            self.helper.overlay.modifyAggregatedL2port(session, aggregatedL2ports[0], networkObjects, '11:01:01:01:01:01:01:01:01:01', '11:00:00:01:01:01')
            
        with self._dao.getReadSession() as session:
            self.assertEqual(1, session.query(OverlayAggregatedL2port).count())
            aggregatedL2portObjectFromDb = session.query(OverlayAggregatedL2port).one()
            self.assertEqual('11:01:01:01:01:01:01:01:01:01', aggregatedL2portObjectFromDb.esi)
            self.assertEqual('11:00:00:01:01:01', aggregatedL2portObjectFromDb.lacp)
            self.assertEqual(1, len(aggregatedL2portObjectFromDb.overlay_networks))
       
    def testCreateDeployStatus(self):
        with self._dao.getReadWriteSession() as session:
            vrfObject = self.helper._createVrf(session)
            deviceObject = vrfObject.overlay_tenant.overlay_fabric.overlay_devices[0]
            deployStatus = self.helper._createDeployStatus(session, deviceObject, vrfObject)
            deployStatusObjectFromDb = session.query(OverlayDeployStatus).filter_by(id = deployStatus.id).one()
            self.assertIsNotNone(deployStatusObjectFromDb)

    def testUpdateDeployStatus(self):        
        with self._dao.getReadWriteSession() as session:        
            vrfObject = self.helper._createVrf(session)
            deviceObject = vrfObject.overlay_tenant.overlay_fabric.overlay_devices[0]
            deployStatusObject = self.helper._createDeployStatus(session, deviceObject, vrfObject)
            deployStatusObject.update('progress', 'in progress')
            self._dao.updateObjects(session, [deployStatusObject])
            id = deployStatusObject.id
            
        with self._dao.getReadSession() as session:
            deployStatusObjectFromDb = session.query(OverlayDeployStatus).filter_by(id = id).one()
            self.assertEqual('progress', deployStatusObjectFromDb.status)
            self.assertEqual('in progress', deployStatusObjectFromDb.statusReason)
            self.assertEqual('create', deployStatusObjectFromDb.operation)

class TestConfigEngine(unittest.TestCase):
    def setUp(self):
        if os.path.isfile('/tmp/sqllite3.db'):
            os.remove('/tmp/sqllite3.db')
        from jnpr.openclos import deviceConnector
        deviceConnector.DEFAULT_AUTO_PROBE = 3
        self._dao = TempFileDao.getInstance()
        from jnpr.openclos.tests.unit.overlay.test_overlay import TestOverlayHelper
        self.helper = TestOverlayHelper({}, self._dao)
        self.helper.overlay._configEngine._commitQueue.dbCleanUpInterval = 1
        self.helper.overlay._configEngine._commitQueue.deviceInterval = 1
        self.helper.overlay.startCommitQueue()
    
    def tearDown(self):
        self.helper.overlay.stopCommitQueue()
        self.helper = None
        TempFileDao._destroy()
        if os.path.isfile('/tmp/sqllite3.db'):
            os.remove('/tmp/sqllite3.db')

    def testConfigureFabric(self):
        with self._dao.getReadWriteSession() as session:
            fabric= self.helper._createFabric(session)
            # overlay.createXYZ would also call required configure
            #self.configEngine.configureFabric(session, "create", fabric)
            
        with self._dao.getReadSession() as session:
            self.assertEqual(1, session.query(OverlayDeployStatus).count())
            config = session.query(OverlayDeployStatus).one().configlet
            print config
            self.assertIn("bgp", config)
            self.assertIn("group overlay-evpn ", config)
            self.assertIn("group overlay-evpn-rr", config)
            self.assertIn("cluster", config)
            self.assertIn("routing-options {", config)
            self.assertIn("router-id", config)

    def testConfigureFabric2Spine3Leaf(self):
        with self._dao.getReadWriteSession() as session:
            fabric= self.helper._createFabric2Spine3Leaf(session)
            # overlay.createXYZ would also call required configure
            #self.configEngine.configureFabric(session, "create", fabric)
            
        with self._dao.getReadSession() as session:
            self.assertEqual(5, session.query(OverlayDeployStatus).count())
            deployments = session.query(OverlayDeployStatus).all()
            spine1Config = deployments[0].configlet
            print "spine:\n" + spine1Config
            self.assertIn("routing-options {", spine1Config)
            self.assertIn("bgp", spine1Config)
            self.assertIn("group overlay", spine1Config)
            self.assertIn("cluster", spine1Config)
            self.assertEquals(4, spine1Config.count("neighbor"))
            self.assertIn("switch-options", spine1Config)
            self.assertIn("policy-options", spine1Config)
            self.assertNotIn("policy-statement OVERLAY-IN", spine1Config)
            
            leaf1Config = deployments[2].configlet
            print "leaf:\n" + leaf1Config
            self.assertNotIn("routing-options {", leaf1Config)
            self.assertIn("bgp", leaf1Config)
            self.assertIn("group overlay", leaf1Config)
            self.assertNotIn("cluster", leaf1Config)
            self.assertEquals(2, leaf1Config.count("neighbor"))
            self.assertNotIn("import OVERLAY-IN", leaf1Config)   
            self.assertIn("switch-options", leaf1Config)
            self.assertIn("policy-options", leaf1Config)
            self.assertNotIn("policy-statement OVERLAY-IN", leaf1Config)

    def test_allocateClusterId(self):
        regex = re.compile("\s*cluster\s+(.+);\s*") 
        with self._dao.getReadWriteSession() as session:
            fabric= self.helper._createFabric2Pods(session)
            # overlay.createXYZ would also call required configure
            #self.configEngine.configureFabric(session, "create", fabric)
            
        with self._dao.getReadSession() as session:
            self.assertEqual(9, session.query(OverlayDeployStatus).count())
            deployments = session.query(OverlayDeployStatus).all()

            spine1Config = deployments[0].configlet
            print "spine1 pod1:\n" + spine1Config
            clusterId = regex.search(spine1Config).group(1)
            self.assertEquals('2.2.1.1', clusterId)

            spine2Config = deployments[1].configlet
            print "spine2 pod1:\n" + spine2Config
            clusterId = regex.search(spine2Config).group(1)
            self.assertEquals('2.2.1.1', clusterId)
            
            spine6Config = deployments[5].configlet
            print "spine6 pod2:\n" + spine6Config
            clusterId = regex.search(spine6Config).group(1)
            self.assertEquals('2.2.1.2', clusterId)

            spine7Config = deployments[6].configlet
            print "spine7 pod2:\n" + spine7Config
            clusterId = regex.search(spine7Config).group(1)
            self.assertEquals('2.2.1.2', clusterId)
            
    def testConfigureFabric2Pods(self):
        regex = re.compile(".*(group\soverlay-evpn\s\{.*?}).*(group\soverlay-evpn-rr\s\{.*?}).*", re.DOTALL)
        with self._dao.getReadWriteSession() as session:
            fabric= self.helper._createFabric2Pods(session)
            # overlay.createXYZ would also call required configure
            #self.configEngine.configureFabric(session, "create", fabric)
            
        with self._dao.getReadSession() as session:
            self.assertEqual(9, session.query(OverlayDeployStatus).count())
            deployments = session.query(OverlayDeployStatus).all()
            spine1Config = deployments[0].configlet
            print "spine1 pod1:\n" + spine1Config
            
            evpn = regex.match(spine1Config).group(1)
            evpnRr = regex.match(spine1Config).group(2)
            self.assertIn("cluster", evpn)
            self.assertEquals(3, evpn.count("neighbor"))
            self.assertEquals(3, evpnRr.count("neighbor"))
            self.assertNotIn("policy-statement OVERLAY-IN", spine1Config)

            leaf3Config = deployments[2].configlet
            print "leaf1 pod1:\n" + leaf3Config
            self.assertIn("group overlay-evpn {", leaf3Config)
            self.assertNotIn("cluster", leaf3Config)
            self.assertEquals(2, leaf3Config.count("neighbor"))            
            self.assertIn("import OVERLAY-IN", leaf3Config)   
            self.assertIn("policy-statement OVERLAY-IN", leaf3Config)
            
            spine6Config = deployments[5].configlet
            print "spine6 pod2:\n" + spine6Config
            evpn = regex.match(spine6Config).group(1)
            evpnRr = regex.match(spine6Config).group(2)
            self.assertIn("cluster", evpn)
            self.assertEquals(2, evpn.count("neighbor"))
            self.assertEquals(3, evpnRr.count("neighbor"))
            self.assertNotIn("policy-statement OVERLAY-IN", spine6Config)

            leaf8Config = deployments[7].configlet
            print "leaf8 pod2:\n" + leaf8Config
            self.assertIn("group overlay-evpn {", leaf8Config)
            self.assertNotIn("cluster", leaf8Config)
            self.assertEquals(2, leaf8Config.count("neighbor"))
            self.assertIn("import OVERLAY-IN", leaf8Config)   
            self.assertIn("policy-statement OVERLAY-IN", leaf8Config)


    def testGetLoopbackIps(self):
        configEngine = self.helper.overlay._configEngine

        ips = configEngine.getLoopbackIps("192.168.48.0/30", 0)
        self.assertEquals(['192.168.48.0/32', '192.168.48.1/32', '192.168.48.2/32', '192.168.48.3/32'], ips)
        ips = configEngine.getLoopbackIps("192.168.48.0/31", 0)
        self.assertEquals(['192.168.48.0/32', '192.168.48.1/32'], ips)
        ips = configEngine.getLoopbackIps("192.168.48.0/32", 0)
        self.assertEquals(['192.168.48.0/32'], ips)

    def testConfigureVrf(self):
        with self._dao.getReadWriteSession() as session:
            vrf = self.helper._createVrf(session)
            vrfObjectUrl = '/vrfs/%s' % (vrf.id)
            # overlay.createXYZ would also call required configure
            #self.configEngine.configureVrf(session, "create", vrf)
            
        with self._dao.getReadSession() as session:
            # 2 deployments fabric and vrf
            self.assertEqual(2, session.query(OverlayDeployStatus).count())
            config = session.query(OverlayDeployStatus).filter_by(object_url=vrfObjectUrl).one().configlet
            print "spine1:\n" + config
            self.assertIn("lo0 {", config)
            self.assertIn("routing-instances {", config)
            self.assertIn("instance-type vrf;", config)
            self.assertIn("route-distinguisher", config)

    def testConfigureNetwork(self):
        with self._dao.getReadWriteSession() as session:
            network = self.helper._createNetworkOn2By3Fabric(session)

        with self._dao.getReadSession() as session:
            # 12 deployments 5 fabric, 2 vrf and 5 network            
            self.assertEqual(7, session.query(OverlayDeployStatus).count())
            deployments = session.query(OverlayDeployStatus).all()

            config = deployments[6].configlet
            print "spine1:\n" + config
            self.assertNotIn("irb {", config)
            self.assertIn("vrf-target", config)
            self.assertNotIn("encapsulation vxlan", config)
            self.assertNotIn("policy-statement LEAF-IN", config)
            self.assertNotIn("n1", config)
            self.assertNotIn("l3-interface irb.101", config)
            self.assertNotIn("interface irb.101", config)
                        
            config = deployments[6].configlet
            print "spine2:\n" + config
            self.assertNotIn("irb {", config)
            self.assertIn("vrf-target", config)
            self.assertNotIn("encapsulation vxlan", config)
            self.assertNotIn("policy-statement LEAF-IN", config)
            self.assertNotIn("n1", config)
            self.assertNotIn("l3-interface irb.101", config)
            self.assertNotIn("interface irb.101", config)
                
            config = deployments[6].configlet
            print "leaf1:\n" + config
            self.assertNotIn("encapsulation vxlan", config)
            self.assertNotIn("policy-statement LEAF-IN", config)
            self.assertNotIn("n1", config)
            self.assertNotIn("l3-interface irb.", config)

    def testConfigureSubnet(self):
        with self._dao.getReadWriteSession() as session:
            subnet = self.helper._createSubnetOn2By3Fabric(session)

        with self._dao.getReadSession() as session:
            # 14 deployments 5 fabric, 2 vrf, 5 network and 2 subnet            
            self.assertEqual(9, session.query(OverlayDeployStatus).count())
            deployments = session.query(OverlayDeployStatus).all()

            config = deployments[-2].configlet
            print "spine1:\n" + config
            self.assertIn("irb {", config)
            self.assertIn("address 1.2.3.2/24 {", config)
            self.assertIn("virtual-gateway-address 1.2.3.1", config)
                        
            config = deployments[-1].configlet
            print "spine2:\n" + config
            self.assertIn("irb {", config)
            self.assertIn("address 1.2.3.3/24 {", config)
            self.assertIn("virtual-gateway-address 1.2.3.1", config)

    def testConfigure2Subnet(self):
        with self._dao.getReadWriteSession() as session:
            subnets = self.helper._create2NetworkOn2By3Fabric(session)
            
        with self._dao.getReadSession() as session:
            # 21 deployments 5 fabric, 2 vrf and 5+5 network, 2+2 subnet            
            self.assertEqual(11, session.query(OverlayDeployStatus).count())
            deployments = session.query(OverlayDeployStatus).all()

            config = deployments[7].configlet
            print "spine1 net1:\n" + config
            self.assertNotIn("vlan-id 101", config)
            self.assertNotIn("vni 1001", config)
            config = deployments[-4].configlet
            print "\n" + config
            self.assertIn("address 1.2.3.2/24 {", config)
            self.assertIn("virtual-gateway-address 1.2.3.1", config)
                        
            config = deployments[8].configlet
            print "spine2 net1:\n" + config
            self.assertNotIn("vlan-id 101", config)
            self.assertNotIn("vni 1001", config)
            config = deployments[-3].configlet
            print "\n" + config
            self.assertIn("address 1.2.3.3/24 {", config)
            self.assertIn("virtual-gateway-address 1.2.3.1", config)

            config = deployments[10].configlet
            print "spine1 net2:\n" + config
            self.assertNotIn("vlan-id 102", config)
            self.assertNotIn("vni 1002", config)
            config = deployments[-2].configlet
            print "\n" + config
            self.assertIn("address 2.2.3.2/24 {", config)
            self.assertIn("virtual-gateway-address 2.2.3.1", config)
                        
            config = deployments[10].configlet
            print "spine2 net2:\n" + config
            self.assertNotIn("vlan-id 102", config)
            self.assertNotIn("vni 1002", config)
            config = deployments[-1].configlet
            print "\n" + config
            self.assertIn("address 2.2.3.3/24 {", config)
            self.assertIn("virtual-gateway-address 2.2.3.1", config)

    def testConfigureL2Port(self):
        with self._dao.getReadWriteSession() as session:
            ports = self.helper._create2Network4L2port(session)
            
        with self._dao.getReadSession() as session:
            # 8 deployments 1 fabric, 1 vrf, 2 network and 4 ports            
            deployments = session.query(OverlayDeployStatus).all()
            self.assertEqual(2, len(deployments))
            
            print deployments[1].configlet
            print deployments[1].configlet
            self.assertEquals(1, deployments[1].configlet.count("interface "))
            self.assertEquals(1, deployments[1].configlet.count("interface "))

    def testDeleteL2Port(self):
        with self._dao.getReadWriteSession() as session:
            port = self.helper._createL2port(session)
            self.assertEqual(1, session.query(OverlayFabric).count())
            self.assertEqual(1, session.query(OverlayVrf).count())
            self.assertEqual(1, session.query(OverlayNetwork).count())
            self.assertEqual(1, session.query(OverlayL2port).count())
            # 4 deployments 1 fabric, 1 vrf, 1 network and 1 port add
            self.assertEqual(2, session.query(OverlayDeployStatus).count())
            
            configEngine = self.helper.overlay._configEngine
            configEngine.deleteL2port(session, port, True)
            
        with self._dao.getReadWriteSession() as session:
            configEngine._commitQueue.cleanUpDb()
            self.assertEqual(1, session.query(OverlayFabric).count())
            self.assertEqual(1, session.query(OverlayVrf).count())
            self.assertEqual(1, session.query(OverlayNetwork).count())
            self.assertEqual(0, session.query(OverlayL2port).count())
            self.assertEqual(2, session.query(OverlayDeployStatus).count())

    def testDeleteL2PortWithTwoNetworks(self):
        with self._dao.getReadWriteSession() as session:
            ports = self.helper._create2Network4L2port(session)
            self.assertEqual(1, session.query(OverlayFabric).count())
            self.assertEqual(1, session.query(OverlayVrf).count())
            self.assertEqual(2, session.query(OverlayNetwork).count())
            self.assertEqual(4, session.query(OverlayL2port).count())
            # 4 deployments 1 fabric, 1 vrf, 2 network and 4 port add
            self.assertEqual(2, session.query(OverlayDeployStatus).count())

            configEngine = self.helper.overlay._configEngine
            configEngine.deleteL2port(session, ports[2], True)
            
        with self._dao.getReadWriteSession() as session:
            configEngine._commitQueue.cleanUpDb()
            self.assertEqual(1, session.query(OverlayFabric).count())
            self.assertEqual(1, session.query(OverlayVrf).count())
            self.assertEqual(2, session.query(OverlayNetwork).count())
            self.assertEqual(3, session.query(OverlayL2port).count())
            self.assertEqual(2, session.query(OverlayDeployStatus).count())

    def testDeleteSubnet(self):
        with self._dao.getReadWriteSession() as session:
            subnet = self.helper._createSubnetOn2By3Fabric(session)
            self.assertEqual(1, session.query(OverlayFabric).count())
            self.assertEqual(1, session.query(OverlayVrf).count())
            self.assertEqual(1, session.query(OverlayNetwork).count())
            self.assertEqual(1, session.query(OverlaySubnet).count())
            # 14 deployments 5 fabric, 2 vrf, 5 network and 2 subnet add
            self.assertEqual(9, session.query(OverlayDeployStatus).count())
            
            configEngine = self.helper.overlay._configEngine
            configEngine.deleteSubnet(session, subnet, True)
            
        with self._dao.getReadWriteSession() as session:
            configEngine._commitQueue.cleanUpDb()
            self.assertEqual(1, session.query(OverlayFabric).count())
            self.assertEqual(1, session.query(OverlayVrf).count())
            self.assertEqual(1, session.query(OverlayNetwork).count())
            self.assertEqual(0, session.query(OverlaySubnet).count())
            self.assertEqual(7, session.query(OverlayDeployStatus).count())

    def testDeleteNetwork(self):
        with self._dao.getReadWriteSession() as session:
            subnet = self.helper._createSubnetOn2By3Fabric(session)
            self.assertEqual(1, session.query(OverlayFabric).count())
            self.assertEqual(1, session.query(OverlayVrf).count())
            self.assertEqual(1, session.query(OverlayNetwork).count())
            self.assertEqual(1, session.query(OverlaySubnet).count())
            # 14 deployments 5 fabric, 2 vrf, 5 network and 2 subnet add
            self.assertEqual(9, session.query(OverlayDeployStatus).count())
            
            configEngine = self.helper.overlay._configEngine
            configEngine.deleteNetwork(session, subnet.overlay_network, True)
            
        with self._dao.getReadWriteSession() as session:
            configEngine._commitQueue.cleanUpDb()
            self.assertEqual(1, session.query(OverlayFabric).count())
            self.assertEqual(1, session.query(OverlayVrf).count())
            self.assertEqual(0, session.query(OverlayNetwork).count())
            self.assertEqual(0, session.query(OverlaySubnet).count())
            self.assertEqual(9, session.query(OverlayDeployStatus).count())

    def testDeleteNetworkRecursive(self):
        with self._dao.getReadWriteSession() as session:
            subnet = self.helper._createSubnetOn2By3Fabric(session)
            port = self.helper._createL2port(session, subnet.overlay_network)
            self.assertEqual(1, session.query(OverlayFabric).count())
            self.assertEqual(1, session.query(OverlayVrf).count())
            self.assertEqual(1, session.query(OverlayNetwork).count())
            self.assertEqual(1, session.query(OverlaySubnet).count())
            self.assertEqual(1, session.query(OverlayL2port).count())
            # 15 deployments 5 fabric, 2 vrf and 5 network, 2 subnet, 1 port add
            self.assertEqual(9, session.query(OverlayDeployStatus).count())
            
            self.helper.overlay.deleteNetwork(session, subnet.overlay_network, True)
            
        with self._dao.getReadWriteSession() as session:
            self.helper.overlay._configEngine._commitQueue.cleanUpDb()
            self.assertEqual(1, session.query(OverlayFabric).count())
            self.assertEqual(1, session.query(OverlayVrf).count())
            self.assertEqual(0, session.query(OverlayNetwork).count())
            self.assertEqual(0, session.query(OverlaySubnet).count())
            self.assertEqual(0, session.query(OverlayL2port).count())
            self.assertEqual(9, session.query(OverlayDeployStatus).count())

    def testGetCurrentLagNumber(self):
        with self._dao.getReadWriteSession() as session:
            ports = self.helper._create2Network3AggregatedL2port(session)
            lagNumber = self.helper.overlay._configEngine._getCurrentLagNumber(session)
            self.assertEqual(2, lagNumber)
        
    def testConfigureAggregatedL2Port(self):
        with self._dao.getReadWriteSession() as session:
            ports = self.helper._create2Network3AggregatedL2port(session)
            
        with self._dao.getReadSession() as session:
            # 7 deployments 1 fabric, 1 vrf, 2 network and 3 aggregateL2port          
            deployments = session.query(OverlayDeployStatus).all()
            self.assertEqual(5, len(deployments))
            
            print deployments[4].configlet
            print deployments[4].configlet
            print deployments[4].configlet
            self.assertFalse('device-count 1;' in deployments[4].configlet)
            self.assertFalse('device-count 2;' in deployments[4].configlet)
            self.assertTrue('device-count 3;' in deployments[4].configlet)
            self.assertEquals(2, deployments[4].configlet.count(" vlan-id "))
            self.assertEquals(2, deployments[4].configlet.count(" vlan-id "))
            self.assertEquals(2, deployments[4].configlet.count(" vlan-id "))

    def testDeleteAggregatedL2Port(self):
        with self._dao.getReadWriteSession() as session:
            ports = self.helper._create2Network3AggregatedL2port(session)
            self.assertEqual(1, session.query(OverlayFabric).count())
            self.assertEqual(1, session.query(OverlayVrf).count())
            self.assertEqual(2, session.query(OverlayNetwork).count())
            self.assertEqual(3, session.query(OverlayAggregatedL2port).count())
            # 7 deployments 1 fabric, 1 vrf, 2 network and 3 aggregateL2port add
            self.assertEqual(5, session.query(OverlayDeployStatus).count())
            self.helper.overlay._configEngine.deleteAggregatedL2port(session, ports[2], True)
            
        with self._dao.getReadWriteSession() as session:
            self.helper.overlay._configEngine._commitQueue.cleanUpDb()
            self.assertEqual(1, session.query(OverlayFabric).count())
            self.assertEqual(1, session.query(OverlayVrf).count())
            self.assertEqual(2, session.query(OverlayNetwork).count())
            self.assertEqual(2, session.query(OverlayAggregatedL2port).count())
            self.assertEqual(4, session.query(OverlayDeployStatus).count())

    def testDeleteVrf(self):
        with self._dao.getReadWriteSession() as session:
            vrf = self.helper._createVrf(session)
            self.assertEqual(1, session.query(OverlayFabric).count())
            self.assertEqual(1, session.query(OverlayVrf).count())
            # 2 deployments 1 fabric, 1 vrf
            self.assertEqual(2, session.query(OverlayDeployStatus).count())

            self.helper.overlay._configEngine.deleteVrf(session, vrf, True)
            
        with self._dao.getReadWriteSession() as session:
            self.helper.overlay._configEngine._commitQueue.cleanUpDb()

            self.assertEqual(1, session.query(OverlayFabric).count())
            self.assertEqual(0, session.query(OverlayVrf).count())
            self.assertEqual(1, session.query(OverlayDeployStatus).count())

    def testDeleteVrfRecursive(self):
        with self._dao.getReadWriteSession() as session:
            network = self.helper._createNetworkOn2By3Fabric(session)
            self.assertEqual(1, session.query(OverlayFabric).count())
            self.assertEqual(1, session.query(OverlayVrf).count())
            self.assertEqual(1, session.query(OverlayNetwork).count())
            # 12 deployments 5 fabric, 2 vrf and 5 network add
            self.assertEqual(7, session.query(OverlayDeployStatus).count())
            
            self.helper.overlay.deleteVrf(session, network.overlay_vrf, True)
            
        with self._dao.getReadWriteSession() as session:
            self.helper.overlay._configEngine._commitQueue.cleanUpDb()
            self.assertEqual(1, session.query(OverlayFabric).count())
            self.assertEqual(0, session.query(OverlayVrf).count())
            self.assertEqual(0, session.query(OverlayNetwork).count())
            self.assertEqual(5, session.query(OverlayDeployStatus).count())

    def testDeleteFabric2Spine3Leaf(self):
        with self._dao.getReadWriteSession() as session:
            fabric= self.helper._createFabric2Spine3Leaf(session)
            self.assertEqual(1, session.query(OverlayFabric).count())
            # 12 deployments 5 fabric
            self.assertEqual(5, session.query(OverlayDeployStatus).count())
            
            self.helper.overlay._configEngine.deleteFabric(session, fabric, True)
            
        with self._dao.getReadWriteSession() as session:
            self.helper.overlay._configEngine._commitQueue.cleanUpDb()
            
            self.assertEqual(0, session.query(OverlayFabric).count())
            self.assertEqual(0, session.query(OverlayDeployStatus).count())

    def testDeleteFabric2Pods(self):
        with self._dao.getReadWriteSession() as session:
            fabric= self.helper._createFabric2Pods(session)
            self.assertEqual(1, session.query(OverlayFabric).count())
            # 12 deployments 9 fabric
            self.assertEqual(9, session.query(OverlayDeployStatus).count())

            self.helper.overlay._configEngine.deleteFabric(session, fabric, True)
            
        with self._dao.getReadWriteSession() as session:
            self.helper.overlay._configEngine._commitQueue.cleanUpDb()
            
            self.assertEqual(0, session.query(OverlayFabric).count())
            self.assertEqual(0, session.query(OverlayDeployStatus).count())

if __name__ == '__main__':
    unittest.main()
