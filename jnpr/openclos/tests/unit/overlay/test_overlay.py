'''
Created on Nov 23, 2015

@author: yunli
'''
import os
import sys
sys.path.insert(0,os.path.abspath(os.path.dirname(__file__) + '/' + '../../..')) #trick to make it run from CLI

import unittest
from jnpr.openclos.overlay.overlayModel import OverlayFabric, OverlayTenant, OverlayVrf, OverlayNetwork, OverlaySubnet, OverlayDevice, OverlayL3port, OverlayL2port, OverlayAe, OverlayDeployStatus
from jnpr.openclos.tests.unit.test_dao import InMemoryDao
from jnpr.openclos.overlay.overlayCommit import OverlayCommitQueue
from jnpr.openclos.overlay.overlay import ConfigEngine
        
class TestOverlayHelper:
    def __init__(self, conf, dao, commitQueue=None):
        if not commitQueue:
            commitQueue = OverlayCommitQueue(type(dao))
        import jnpr.openclos.overlay.overlay
        self.overlay = jnpr.openclos.overlay.overlay.Overlay(conf, dao, commitQueue)
    
    def _createDevice(self, dbSession, offset="1", role="spine", podName="pod1"):
        deviceDict = {
            "name": "d" + offset,
            "description": "description for d" + offset,
            "role": role,
            "address": "1.2.3." + offset,
            "routerId": "1.1.1." + offset,
            "podName": podName
        }
        return self.overlay.createDevice(dbSession, deviceDict['name'], deviceDict.get('description'), 
                                         deviceDict['role'], deviceDict['address'], deviceDict['routerId'], deviceDict['podName'])
        
    def _createFabric(self, dbSession, offset="1"):
        fabricDict = {
            "name": "f" + offset,
            "description": "description for f" + offset,
            "overlayAsn": 65001,
            "routeReflectorAddress": "2.2.2." + offset
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
            "routeReflectorAddress": "2.2.2.2"
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
            "routeReflectorAddress": "2.2.2.2"
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
        
    def _createSubnetOn2By3Fabric(self, dbSession):
        fabric = self._createFabric2Spine3Leaf(dbSession)
        tenant = self._createTenant(dbSession, fabricObject=fabric)
        vrf = self._createVrf(dbSession, tenantObject=tenant)
        network = self._createNetwork(dbSession, vrfObject=vrf)
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
        
    def _createL2port(self, dbSession):
        l2portDict = {
            "name": "l2port1",
            "description": "description for l2port1",
            "interface": "xe-0/0/1"
        }
        networkObject = self._createNetwork(dbSession)
        deviceObject = networkObject.overlay_vrf.overlay_tenant.overlay_fabric.overlay_devices[0]
        return self.overlay.createL2port(dbSession, l2portDict['name'], l2portDict['description'], l2portDict['interface'], [networkObject], deviceObject)

    def _create2Network4L2port(self, dbSession):
        networkObject1 = self._createNetwork(dbSession, offset="1")
        networkObject2 = self._createNetwork(dbSession, offset="2", vrfObject=networkObject1.overlay_vrf)
        deviceObject = networkObject1.overlay_vrf.overlay_tenant.overlay_fabric.overlay_devices[0]
        
        port1 = self.overlay.createL2port(dbSession, "l2port1", "description for l2port1", "xe-0/0/1", [networkObject1], deviceObject)
        port2 = self.overlay.createL2port(dbSession, "l2port2", "description for l2port2", "xe-0/0/2", [networkObject2], deviceObject)
        port3 = self.overlay.createL2port(dbSession, "l2port3", "description for l2port3", "xe-0/0/3", [networkObject1, networkObject2], deviceObject)
        port4 = self.overlay.createL2port(dbSession, "l2port4", "description for l2port4", "xe-0/0/4", [networkObject1], deviceObject)
        return [port1, port2, port3, port4]

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
            "operation": "create"
        }
        status = OverlayDeployStatus(deployStatusDict['configlet'], deployStatusDict['object_url'], 
            deployStatusDict['operation'], deviceObject, vrfObject, deployStatusDict['status'], deployStatusDict['statusReason'])
        dbSession.add_all([status])
        dbSession.commit()
        return status
    
class TestOverlay(unittest.TestCase):
    def setUp(self):
        self._dao = InMemoryDao.getInstance()
        self.helper = TestOverlayHelper({}, self._dao)
    
    def tearDown(self):
        InMemoryDao._destroy()
        self.helper = None

    def testCreateDevice(self):
        with self._dao.getReadWriteSession() as session:
            self.helper._createDevice(session)
            self.assertEqual(1, session.query(OverlayDevice).count())
            
    def testUpdateDevice(self):        
        with self._dao.getReadWriteSession() as session:        
            deviceObject = self.helper._createDevice(session)
            deviceObject.update('d2', 'description for d2', 'leaf', '1.2.3.5', '1.1.1.2', 'pod2', 'test', 'foobar')
            self._dao.updateObjects(session, [deviceObject])
            
        with self._dao.getReadSession() as session:
            self.assertEqual(1, session.query(OverlayDevice).count())
            deviceObjectFromDb = session.query(OverlayDevice).one()
            self.assertEqual('d2', deviceObjectFromDb.name)
            self.assertEqual('description for d2', deviceObjectFromDb.description)
            self.assertEqual('leaf', deviceObjectFromDb.role)
            self.assertEqual('1.2.3.5', deviceObjectFromDb.address)
            self.assertEqual('1.1.1.2', deviceObjectFromDb.routerId)
            self.assertEqual('pod2', deviceObjectFromDb.podName)
            self.assertEqual('test', deviceObjectFromDb.username)
            self.assertEqual('foobar', deviceObjectFromDb.getCleartextPassword())
            
    def testCreateFabric(self):
        with self._dao.getReadWriteSession() as session:
            self.helper._createFabric(session)
            self.assertEqual(1, session.query(OverlayFabric).count())

    def testUpdateFabric(self):
        with self._dao.getReadWriteSession() as session:   
            fabricObject = self.helper._createFabric(session)
            fabricObjectFromDb = session.query(OverlayFabric).one()
            fabricObjectFromDb.clearDevices()
            fabricObjectFromDb.update('f2', 'description for f2', 65002, '3.3.3.3', [])
            self._dao.updateObjects(session, [fabricObjectFromDb])
            
        with self._dao.getReadSession() as session:
            self.assertEqual(1, session.query(OverlayFabric).count())
            fabricObjectFromDb = session.query(OverlayFabric).one()
            self.assertEqual('f2', fabricObjectFromDb.name)
            self.assertEqual('description for f2', fabricObjectFromDb.description)
            self.assertEqual(65002, fabricObjectFromDb.overlayAS)
            self.assertEqual('3.3.3.3', fabricObjectFromDb.routeReflectorAddress)
            self.assertEqual(0, len(fabricObjectFromDb.overlay_devices))
    
    def testCreateTenant(self):
        with self._dao.getReadWriteSession() as session:
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

    def testCreateVrfLoopbackCounter(self):
        with self._dao.getReadWriteSession() as session:
            self.helper._createVrf(session, "1")
            self.helper._createVrf(session, "2")
            self.helper._createVrf(session, "3")
            self.helper._createVrf(session, "4")
            self.helper._createVrf(session, "5")
            vrfs = session.query(OverlayVrf).all()
            self.assertEquals(5, len(vrfs))
            self.assertEquals(1, vrfs[0].vrfCounter)
            self.assertEquals(2, vrfs[1].vrfCounter)
            self.assertEquals(3, vrfs[2].vrfCounter)
            self.assertEquals(5, vrfs[4].vrfCounter)

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
        with self._dao.getReadWriteSession() as session:
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
        with self._dao.getReadWriteSession() as session:
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
        with self._dao.getReadWriteSession() as session:
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
            self.assertEqual(3, len(ports[0].overlay_networks[0].overlay_l2ports))
            self.assertEqual(2, len(ports[1].overlay_networks[0].overlay_l2ports))

    def testUpdateL2port(self):        
        with self._dao.getReadWriteSession() as session:        
            self.helper._create2Network4L2port(session)
            ports = session.query(OverlayL2port).all()
            ports[0].clearNetworks()
            ports[0].update('l2port.changed', 'description changed', 'xe-1/0/0', ports[2].overlay_networks, ports[0].overlay_device, ports[0].overlay_ae)
            self._dao.updateObjects(session, ports)
            
        with self._dao.getReadSession() as session:
            ports = session.query(OverlayL2port).all()
            self.assertEqual('l2port.changed', ports[0].name)
            self.assertEqual('description changed', ports[0].description)
            self.assertEqual('xe-1/0/0', ports[0].interface)
            self.assertEqual(2, len(ports[0].overlay_networks))
            
    def testCreateAe(self):
        with self._dao.getReadWriteSession() as session:
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
        self._dao = InMemoryDao.getInstance()
        self.helper = TestOverlayHelper({}, self._dao)
    
    def tearDown(self):
        InMemoryDao._destroy()
        self.helper = None

    def testConfigureFabric(self):
        with self._dao.getReadWriteSession() as session:
            fabric= self.helper._createFabric(session)
            # overlay.createXYZ would also call required configure
            #self.configEngine.configureFabric(session, fabric)
            
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
            #self.configEngine.configureFabric(session, fabric)
            
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

    def testConfigureFabric2Pods(self):
        import re
        regex = re.compile(".*(group\soverlay-evpn\s\{.*?}).*(group\soverlay-evpn-rr\s\{.*?}).*", re.DOTALL)
        with self._dao.getReadWriteSession() as session:
            fabric= self.helper._createFabric2Pods(session)
            # overlay.createXYZ would also call required configure
            #self.configEngine.configureFabric(session, fabric)
            
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

        ips = configEngine.getLoopbackIps("192.168.48.0/30")
        self.assertEquals(['192.168.48.0/32', '192.168.48.1/32', '192.168.48.2/32', '192.168.48.3/32'], ips)
        ips = configEngine.getLoopbackIps("192.168.48.0/31")
        self.assertEquals(['192.168.48.0/32', '192.168.48.1/32'], ips)
        ips = configEngine.getLoopbackIps("192.168.48.0/32")
        self.assertEquals(['192.168.48.0/32'], ips)

    def testConfigureVrf(self):
        with self._dao.getReadWriteSession() as session:
            vrf = self.helper._createVrf(session)
            # overlay.createXYZ would also call required configure
            #self.configEngine.configureVrf(session, vrf)
            
            # 2 deployments fabric and vrf
            self.assertEqual(2, session.query(OverlayDeployStatus).count())
            config = session.query(OverlayDeployStatus).filter_by(overlay_vrf_id=vrf.id).one().configlet
            print "spine1:\n" + config
            self.assertIn("lo0 {", config)
            self.assertIn("routing-instances {", config)
            self.assertIn("instance-type vrf;", config)
            self.assertIn("route-distinguisher", config)

    def testConfigureSubnet(self):
        with self._dao.getReadWriteSession() as session:
            subnet = self.helper._createSubnetOn2By3Fabric(session)
            # overlay.createXYZ would also call required configure
            #self.configEngine.configureSubnet(session, subnet)

            # 11 deployments 5 fabric, 2 vrf and 5 subnet            
            self.assertEqual(12, session.query(OverlayDeployStatus).count())
            deployments = session.query(OverlayDeployStatus).all()

            config = deployments[7].configlet
            print "spine1:\n" + config
            self.assertIn("irb {", config)
            self.assertIn("address 1.2.3.2/24 {", config)
            self.assertIn("virtual-gateway-address 1.2.3.1", config)
            self.assertIn("vrf-target", config)
            self.assertIn("encapsulation vxlan", config)
            self.assertIn("policy-statement LEAF-IN", config)
                        
            config = deployments[8].configlet
            print "spine2:\n" + config
            self.assertIn("irb {", config)
            self.assertIn("address 1.2.3.3/24 {", config)
            self.assertIn("virtual-gateway-address 1.2.3.1", config)
            self.assertIn("vrf-target", config)
            self.assertIn("encapsulation vxlan", config)
            self.assertIn("policy-statement LEAF-IN", config)
                
            config = deployments[9].configlet
            print "leaf1:\n" + config
            self.assertIn("encapsulation vxlan", config)
            self.assertIn("policy-statement LEAF-IN", config)
            self.assertIn("bd1001", config)

    def testConfigure2Subnet(self):
        with self._dao.getReadWriteSession() as session:
            subnets = self.helper._create2NetworkOn2By3Fabric(session)
            # overlay.createXYZ would also call required configure
            #self.configEngine.configureSubnet(session, subnets[0])
            #self.configEngine.configureSubnet(session, subnets[1])
            
            # 11 deployments 5 fabric, 2 vrf and 5+5 subnet            
            self.assertEqual(17, session.query(OverlayDeployStatus).count())
            deployments = session.query(OverlayDeployStatus).all()

            config = deployments[7].configlet
            print "spine1 net1:\n" + config
            self.assertIn("address 1.2.3.2/24 {", config)
            self.assertIn("virtual-gateway-address 1.2.3.1", config)
            self.assertIn("vlan-id 101", config)
            self.assertIn("vni 1001", config)
                        
            config = deployments[8].configlet
            print "spine2 net1:\n" + config
            self.assertIn("address 1.2.3.3/24 {", config)
            self.assertIn("virtual-gateway-address 1.2.3.1", config)
            self.assertIn("vlan-id 101", config)
            self.assertIn("vni 1001", config)

            config = deployments[12].configlet
            print "spine1 net2:\n" + config
            self.assertIn("address 2.2.3.2/24 {", config)
            self.assertIn("virtual-gateway-address 2.2.3.1", config)
            self.assertIn("vlan-id 102", config)
            self.assertIn("vni 1002", config)
                        
            config = deployments[13].configlet
            print "spine2 net2:\n" + config
            self.assertIn("address 2.2.3.3/24 {", config)
            self.assertIn("virtual-gateway-address 2.2.3.1", config)
            self.assertIn("vlan-id 102", config)
            self.assertIn("vni 1002", config)

    def testConfigureL2Port(self):
        import re
        with self._dao.getReadWriteSession() as session:
            ports = self.helper._create2Network4L2port(session)
            
            # 6 deployments 1 fabric, 1 vrf and 4 ports. As there is no subnet, network was not deployed            
            deployments = session.query(OverlayDeployStatus).all()
            self.assertEqual(6, len(deployments))
            
            print deployments[2].configlet
            print deployments[4].configlet
            self.assertEquals(1, deployments[2].configlet.count("interface "))
            self.assertEquals(2, deployments[4].configlet.count("interface "))

    def testDeleteL2Port(self):
        with self._dao.getReadWriteSession() as session:
            port = self.helper._createL2port(session)
            configEngine = self.helper.overlay._configEngine
            configEngine.deleteL2Port(session, port)
            # 4 deployments 1 fabric, 1 vrf and 1 port add, 1 port delete            
            deployments = session.query(OverlayDeployStatus).all()
            print deployments[-1].configlet
            self.assertEquals(1, deployments[-1].configlet.count("interfaces "))
            self.assertEquals(1, deployments[-1].configlet.count("vlans "))
            self.assertEquals(2, deployments[-1].configlet.count("delete:"))

if __name__ == '__main__':
    unittest.main()
