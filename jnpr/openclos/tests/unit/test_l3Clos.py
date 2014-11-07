'''
Created on Jul 22, 2014

@author: moloyc
'''
import os
import sys
sys.path.insert(0,os.path.abspath(os.path.dirname(__file__) + '/' + '../..')) #trick to make it run from CLI

import unittest
import shutil
import json
from flexmock import flexmock
from jnpr.openclos.l3Clos import L3ClosMediation
from jnpr.openclos.model import Pod, Device, InterfaceLogical, InterfaceDefinition
from jnpr.openclos.util import configLocation

class TestL3Clos(unittest.TestCase):
    def setUp(self):
        '''Creates Dao with in-memory DB'''
        self.conf = {}
        self.conf['outputDir'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'out')
        self.conf['dbUrl'] = 'sqlite:///'
        self.conf['writeConfigInFile'] = 'false'
        self.conf['logLevel'] = { 
                'fabric' : 'INFO',
                'reporting' : 'INFO',
                'ztp' : 'INFO',
                'rest' : 'INFO',
                'writer' : 'INFO'
        }
        self.conf['DOT'] = {'ranksep' : '5 equally', 'colors': ['red', 'green', 'blue']}
        self.conf['deviceFamily'] = {
            "QFX5100-24Q": {
                "ports": 'et-0/0/[0-23]'
            },
            "QFX5100-48S": {
                "uplinkPorts": 'et-0/0/[48-53]', 
                "downlinkPorts": 'xe-0/0/[0-47]'
            }
        }
    
    def tearDown(self):
        ''' Deletes 'out' folder under test dir'''
        shutil.rmtree(self.conf['outputDir'], ignore_errors=True)

    def testLoadClosDefinition(self):
        l3ClosMediation = L3ClosMediation(self.conf)

        pods = l3ClosMediation.loadClosDefinition()
        self.assertEqual(2, len(pods))

    def testLoadNonExistingClosDefinition(self):
        l3ClosMediation = L3ClosMediation(self.conf)
        dao = l3ClosMediation.dao

        l3ClosMediation.loadClosDefinition('non-existing.yaml')
        self.assertEqual(0, len(dao.getAll(Pod)))

    def testCreatePod(self):
        l3ClosMediation = L3ClosMediation(self.conf)
        session = l3ClosMediation.dao.Session()

        pod = self.createPod(l3ClosMediation)
        self.assertEqual(1, session.query(Pod).count())

    def testUpdatePod(self):
        l3ClosMediation = L3ClosMediation(self.conf)
        session = l3ClosMediation.dao.Session()
        
        pod = self.createPodWithoutInventory(l3ClosMediation)
        podDict = {"spineAS": 101}
        inventoryDict = {"spines" : [{ "name" : "spine-11", "macAddress" : "aa:bb:cc:dd:ee:b1", "managementIp" : "172.32.32.201/24" }], \
                         "leafs" : [{ "name" : "leaf-11", "macAddress" : "aa:bb:cc:dd:ee:a1", "managementIp" : "172.32.32.101/24" }]}
        l3ClosMediation.updatePod(pod.id, podDict, inventoryDict)

        self.assertEqual(2, session.query(Device).count())
        self.assertEqual(101, pod.spineAS)

    def testUpdatePodInvalidId(self):
        podDict = {"hostOrVmCountPerLeaf": 254, "leafDeviceType": "QFX5100-48S", "spineAS": 100, "spineDeviceType": "QFX5100-24Q", "leafCount": 6, "interConnectPrefix": "192.168.0.0", "spineCount": 4, "vlanPrefix": "172.16.0.0", "topologyType": "threeStage", "loopbackPrefix": "10.0.0.0", "leafAS": 200}
        l3ClosMediation = L3ClosMediation(self.conf)
        
        with self.assertRaises(ValueError) as ve:
            l3ClosMediation.updatePod("invalid_id", podDict, None)

    def testCablingPlanAndDeviceConfig(self):
        l3ClosMediation = L3ClosMediation(self.conf)
        pod = self.createPod(l3ClosMediation)
        self.assertEqual(True, l3ClosMediation.createCablingPlan(pod.id))
        self.assertEqual(True, l3ClosMediation.createDeviceConfig(pod.id))

    def testCablingPlanNoInventory(self):
        l3ClosMediation = L3ClosMediation(self.conf)
        pod = self.createPodWithoutInventory(l3ClosMediation)

        with self.assertRaises(ValueError) as ve:
            l3ClosMediation.createCablingPlan(pod.id)
        
    def createPodWithoutInventory(self, l3ClosMediation):
        podDict = {"hostOrVmCountPerLeaf": 254, "leafDeviceType": "QFX5100-48S", "spineAS": 100, "spineDeviceType": "QFX5100-24Q", "leafCount": 6, "interConnectPrefix": "192.168.0.0", "spineCount": 4, "vlanPrefix": "172.16.0.0", "topologyType": "threeStage", "loopbackPrefix": "10.0.0.0", "leafAS": 200, "managementPrefix": "172.32.30.101/24"}
        pod = l3ClosMediation.createPod('pod1', podDict)
        return pod
        
    def createPod(self, l3ClosMediation):
        podDict = {"hostOrVmCountPerLeaf": 254, "leafDeviceType": "QFX5100-48S", "spineAS": 100, "spineDeviceType": "QFX5100-24Q", "leafCount": 6, "interConnectPrefix": "192.168.0.0", "spineCount": 4, "vlanPrefix": "172.16.0.0", "topologyType": "threeStage", "loopbackPrefix": "10.0.0.0", "leafAS": 200, "managementPrefix": "172.32.30.101/24", "inventory" : "inventoryLabLeafSpine.json"}
        pod = l3ClosMediation.createPod('pod1', podDict)
        return pod

    def testCreateSpines(self):
        from jnpr.openclos.l3Clos import util
        flexmock(util, getPortNamesForDeviceFamily={'ports': ['et-0/0/0', 'et-0/0/1']})
        self.conf['deviceFamily'] = {}
        
        l3ClosMediation = L3ClosMediation(self.conf)
        dao = l3ClosMediation.dao
        pod = self.createPodWithoutInventory(l3ClosMediation)

        spineString = u'[{ "name" : "spine-01", "macAddress" : "aa:bb:cc:dd:ee:f1", "managementIp" : "172.32.32.201/24", "user" : "root", "password" : "Embe1mpls" }, { "name" : "spine-02", "macAddress" : "aa:bb:cc:dd:ee:f2", "managementIp" : "172.32.32.202/24", "user" : "root", "password" : "Embe1mpls" }]'
        l3ClosMediation.createSpineIFDs(pod, json.loads(spineString))

        self.assertEqual(2, len(dao.getAll(Device)))
        self.assertEqual(0, len(dao.getAll(InterfaceLogical)))
        self.assertEqual(4, len(dao.getAll(InterfaceDefinition)))
        self.assertEqual(2, len(dao.getObjectsByName(InterfaceDefinition, 'et-0/0/0')))
        self.assertEqual(2, len(dao.getObjectsByName(InterfaceDefinition, 'et-0/0/1')))

    def testCreateLeafs(self):
        from jnpr.openclos.l3Clos import util
        flexmock(util, getPortNamesForDeviceFamily={'uplinkPorts': ['et-0/0/48'], 'downlinkPorts': ['xe-0/0/0', 'xe-0/0/1']})
        self.conf['deviceFamily'] = {}

        l3ClosMediation = L3ClosMediation(self.conf)
        dao = l3ClosMediation.dao
        pod = self.createPodWithoutInventory(l3ClosMediation)

        leafString = u'[{ "name" : "leaf-01", "macAddress" : "aa:bb:cc:dd:ee:f1", "managementIp" : "172.32.32.201/24", "user" : "root", "password" : "Embe1mpls" }, { "name" : "leaf-02", "macAddress" : "aa:bb:cc:dd:ee:f2", "managementIp" : "172.32.32.202/24", "user" : "root", "password" : "Embe1mpls" }]'
        l3ClosMediation.createLeafIFDs(pod, json.loads(leafString))

        self.assertEqual(2, len(dao.getAll(Device)))
        self.assertEqual(0, len(dao.getAll(InterfaceLogical)))
        self.assertEqual(6, len(dao.getAll(InterfaceDefinition)))
        self.assertEqual(2, len(dao.getObjectsByName(InterfaceDefinition, 'et-0/0/48')))
        self.assertEqual(2, len(dao.getObjectsByName(InterfaceDefinition, 'xe-0/0/0')))

    def createPodSpineLeaf(self, l3ClosMediation):
        from jnpr.openclos.l3Clos import util
        flexmock(util, getPortNamesForDeviceFamily={'ports': ['et-0/0/0', 'et-0/0/1'], 'uplinkPorts': ['et-0/0/48', 'et-0/0/49'], 'downlinkPorts': ['xe-0/0/0', 'xe-0/0/1']})
        self.conf['deviceFamily'] = {}

        pod = self.createPodWithoutInventory(l3ClosMediation)
        spineString = u'[{ "name" : "spine-01", "macAddress" : "aa:bb:cc:dd:ee:f1", "managementIp" : "172.32.32.201/24", "user" : "root", "password" : "Embe1mpls" }, { "name" : "spine-02", "macAddress" : "aa:bb:cc:dd:ee:f2", "managementIp" : "172.32.32.202/24", "user" : "root", "password" : "Embe1mpls" }]'
        l3ClosMediation.createSpineIFDs(pod, json.loads(spineString))
        leafString = u'[{ "name" : "leaf-01", "macAddress" : "aa:bb:cc:dd:ee:f1", "managementIp" : "172.32.32.201/24", "user" : "root", "password" : "Embe1mpls" }, { "name" : "leaf-02", "macAddress" : "aa:bb:cc:dd:ee:f2", "managementIp" : "172.32.32.202/24", "user" : "root", "password" : "Embe1mpls" }]'
        l3ClosMediation.createLeafIFDs(pod, json.loads(leafString))
        return pod
    
    def testCreateLinks(self):
        l3ClosMediation = L3ClosMediation(self.conf)
        pod = self.createPodSpineLeaf(l3ClosMediation)
        l3ClosMediation.createLinkBetweenIfds(pod)

        # force close current session and get new session to make sure merge and flush took place properly
        podId = pod.id
        l3ClosMediation.dao.Session.remove()                
        session = l3ClosMediation.dao.Session()

        spine01Port0 = session.query(InterfaceDefinition).join(Device).filter(InterfaceDefinition.name == 'et-0/0/0').filter(Device.name == 'spine-01').filter(Device.pod_id == podId).one()
        self.assertIsNotNone(spine01Port0.peer)
        self.assertEqual('et-0/0/48', spine01Port0.peer.name)
        self.assertEqual('leaf-01', spine01Port0.peer.device.name)
        
        spine02Port1 = session.query(InterfaceDefinition).join(Device).filter(InterfaceDefinition.name == 'et-0/0/1').filter(Device.name == 'spine-02').filter(Device.pod_id == podId).one()
        self.assertIsNotNone(spine02Port1.peer)
        self.assertEqual('et-0/0/49', spine02Port1.peer.name)
        self.assertEqual('leaf-02', spine02Port1.peer.device.name)

    def testGetLeafSpineFromPod(self):
        l3ClosMediation = L3ClosMediation(self.conf)
        pod = self.createPodSpineLeaf(l3ClosMediation)

        leafSpineDict = l3ClosMediation.getLeafSpineFromPod(pod)
        self.assertEqual(2, len(leafSpineDict['leafs']))
        self.assertEqual(2, len(leafSpineDict['spines']))
        
    def testAllocateLoopback(self):
        l3ClosMediation = L3ClosMediation(self.conf)
        pod = self.createPodSpineLeaf(l3ClosMediation)
        session = l3ClosMediation.dao.Session()
    
        l3ClosMediation.allocateLoopback(pod, "10.0.0.0", pod.devices)
        
        self.assertEqual(4, len(l3ClosMediation.dao.getObjectsByName(InterfaceLogical, 'lo0.0')))
        ifl = session.query(InterfaceLogical).join(Device).filter(InterfaceLogical.name == 'lo0.0').filter(Device.name == 'leaf-01').filter(Device.pod_id == pod.id).one()
        self.assertEqual('10.0.0.1/32', ifl.ipaddress)
        ifl = session.query(InterfaceLogical).join(Device).filter(InterfaceLogical.name == 'lo0.0').filter(Device.name == 'spine-02').filter(Device.pod_id == pod.id).one()
        self.assertEqual('10.0.0.4/32', ifl.ipaddress)
        self.assertEqual('10.0.0.0/29', pod.allocatedLoopbackBlock)

    def testAllocateIrb(self):
        l3ClosMediation = L3ClosMediation(self.conf)
        pod = self.createPodSpineLeaf(l3ClosMediation)
        session = l3ClosMediation.dao.Session()
    
        l3ClosMediation.allocateIrb(pod, '172.16.0.0', pod.devices)

        self.assertEqual(4, len(l3ClosMediation.dao.getObjectsByName(InterfaceLogical, 'irb.1')))
        ifl = session.query(InterfaceLogical).join(Device).filter(InterfaceLogical.name == 'irb.1').filter(Device.name == 'leaf-01').filter(Device.pod_id == pod.id).one()
        self.assertEqual('172.16.0.1/24', ifl.ipaddress)
        ifl = session.query(InterfaceLogical).join(Device).filter(InterfaceLogical.name == 'irb.1').filter(Device.name == 'spine-02').filter(Device.pod_id == pod.id).one()
        self.assertEqual('172.16.3.1/24', ifl.ipaddress)
        self.assertEqual('172.16.0.0/22', pod.allocatedIrbBlock)

    def createPodSpineLeafLink(self, l3ClosMediation):
        pod = self.createPodSpineLeaf(l3ClosMediation)
        l3ClosMediation.createLinkBetweenIfds(pod)
        return pod
        
    def testAllocateInterconnect(self):
        l3ClosMediation = L3ClosMediation(self.conf)
        pod = self.createPodSpineLeafLink(l3ClosMediation)
        session = l3ClosMediation.dao.Session()

        leafSpineDict = l3ClosMediation.getLeafSpineFromPod(pod)
        l3ClosMediation.allocateInterconnect('192.168.0.0', leafSpineDict['spines'], leafSpineDict['leafs'] )

        self.assertEqual(8, len(l3ClosMediation.dao.getAll(InterfaceLogical)))
        ifl = session.query(InterfaceLogical).join(Device).filter(InterfaceLogical.name == 'et-0/0/0.0').filter(Device.name == 'spine-01').filter(Device.pod_id == pod.id).one()
        belowIfd = session.query(InterfaceDefinition).filter(InterfaceDefinition.id == ifl.layer_below_id).one()
        self.assertEqual('et-0/0/0', belowIfd.name)
        self.assertEqual('192.168.0.0/31', ifl.ipaddress)
        ifl = session.query(InterfaceLogical).join(Device).filter(InterfaceLogical.name == 'et-0/0/48.0').filter(Device.name == 'leaf-01').filter(Device.pod_id == pod.id).one()
        belowIfd = session.query(InterfaceDefinition).filter(InterfaceDefinition.id == ifl.layer_below_id).one()
        self.assertEqual('et-0/0/48', belowIfd.name)
        self.assertEqual('192.168.0.1/31', ifl.ipaddress)

    def testAllocateAsNumber(self):
        l3ClosMediation = L3ClosMediation(self.conf)
        pod = self.createPodSpineLeafLink(l3ClosMediation)
        session = l3ClosMediation.dao.Session()

        leafSpineDict = l3ClosMediation.getLeafSpineFromPod(pod)
        l3ClosMediation.allocateAsNumber(100, 200, leafSpineDict['spines'], leafSpineDict['leafs'] )
        
        self.assertEqual(100, session.query(Device).filter(Device.role == 'spine').all()[0].asn)
        self.assertEqual(201, session.query(Device).filter(Device.role == 'leaf').all()[1].asn)
        
    def testCreatePolicyOptionSpine(self):
        l3ClosMediation = L3ClosMediation(self.conf)
        device = Device("test", "QFX5100-24Q", "user", "pwd", "spine", "mac", "mgmtIp", self.createPod(l3ClosMediation))
        device.pod.allocatedIrbBlock = '10.0.0.0/28'
        device.pod.allocatedLoopbackBlock = '11.0.0.0/28'
        configlet = l3ClosMediation.createPolicyOption(device)
        
        self.assertTrue('irb_in' not in configlet and '10.0.0.0/28' in configlet)
        self.assertTrue('lo0_in' not in configlet and '11.0.0.0/28' in configlet)
        self.assertTrue('lo0_out' not in configlet)
        self.assertTrue('irb_out' not in configlet)

    def testCreatePolicyOptionLeaf(self):
        l3ClosMediation = L3ClosMediation(self.conf)
        device = Device("test", "QFX5100-48S", "user", "pwd", "leaf", "mac", "mgmtIp", self.createPod(l3ClosMediation))
        device.pod.allocatedIrbBlock = '10.0.0.0/28'
        device.pod.allocatedLoopbackBlock = '11.0.0.0/28'        
        flexmock(l3ClosMediation.dao.Session).should_receive('query.join.filter.filter.one').and_return(InterfaceLogical("test", device, '12.0.0.0/28'))

        configlet = l3ClosMediation.createPolicyOption(device)
        self.assertTrue('irb_in' not in configlet and '10.0.0.0/28' in configlet)
        self.assertTrue('lo0_in' not in configlet and '11.0.0.0/28' in configlet)
        self.assertTrue('lo0_out' not in configlet and '12.0.0.0/28' in configlet)
        self.assertTrue('irb_out' not in configlet)
  
    def testInitWithTemplate(self):
        from jinja2 import TemplateNotFound
        l3ClosMediation = L3ClosMediation(self.conf)
        self.assertIsNotNone(l3ClosMediation.templateEnv.get_template('protocolBgpLldp.txt'))
        with self.assertRaises(TemplateNotFound) as e:
            l3ClosMediation.templateEnv.get_template('unknown-template')
        self.assertTrue('unknown-template' in e.exception.message)
  
if __name__ == '__main__':
    unittest.main()