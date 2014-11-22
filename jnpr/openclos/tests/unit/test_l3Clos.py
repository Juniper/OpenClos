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
                'writer' : 'INFO',
                'devicePlugin' : 'INFO',
                'trapd' : 'INFO',
                'dao' : 'INFO'
        }
        self.conf['DOT'] = {'ranksep' : '5 equally', 'colors': ['red', 'green', 'blue']}
        self.conf['deviceFamily'] = {
            "qfx5100-24q-2p": {
                "ports": 'et-0/0/[0-23]'
            },
            "qfx5100-48s-6q": {
                "uplinkPorts": 'et-0/0/[48-53]', 
                "downlinkPorts": 'xe-0/0/[0-47]'
            }
        }
    
    def tearDown(self):
        ''' Deletes 'out' folder under test dir'''
        shutil.rmtree(self.conf['outputDir'], ignore_errors=True)

    def createPod(self, l3ClosMediation):
        podDict = {"devicePassword": "Embe1mpls", "hostOrVmCountPerLeaf": 254, "leafDeviceType": "qfx5100-48s-6q", "spineAS": 100, "spineDeviceType": "qfx5100-24q-2p", "leafCount": 2, "interConnectPrefix": "192.168.0.0", "spineCount": 2, "vlanPrefix": "172.16.0.0", "topologyType": "threeStage", "loopbackPrefix": "10.0.0.0", "leafAS": 200, "managementPrefix": "172.32.30.101/24", "inventory" : "inventoryUnitTest.json"}
        pod = l3ClosMediation.createPod('pod1', podDict)
        return (pod, podDict)

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

        (pod, podDict) = self.createPod(l3ClosMediation)
        self.assertEqual(1, session.query(Pod).count())

    def testUpdatePod(self):
        l3ClosMediation = L3ClosMediation(self.conf)
        session = l3ClosMediation.dao.Session()
        
        (pod, podDict) = self.createPod(l3ClosMediation)
        inventoryDict = {
            "spines" : [
               { "name" : "spine-01", "macAddress" : "10:0e:7e:af:35:41", "username": "root", "password": "Embe1mpls", "deployStatus": "deploy" },
               { "name" : "spine-02", "macAddress" : "10:0e:7e:af:50:c1", "username": "root", "password": "Embe1mpls", "deployStatus": "provision" }
            ],
            "leafs" : [
               { "name" : "leaf-01", "macAddress" : "88:e0:f3:1c:d6:01", "username": "root", "password": "Embe1mpls", "deployStatus": "deploy" },
               { "name" : "leaf-02", "macAddress" : "10:0e:7e:b8:9d:01", "username": "root", "password": "Embe1mpls", "deployStatus": "provision" }
            ]
        }
        l3ClosMediation.updatePod(pod.id, podDict, inventoryDict)

        self.assertEqual(4, len(pod.devices))
        deployCount = 0
        for device in pod.devices:
            if device.deployStatus == "deploy":
                deployCount += 1
        self.assertEqual(2, deployCount)
                

    def testUpdatePodInvalidId(self):
        l3ClosMediation = L3ClosMediation(self.conf)
        
        with self.assertRaises(ValueError) as ve:
            l3ClosMediation.updatePod("invalid_id", None)

    def testCablingPlanAndDeviceConfig(self):
        l3ClosMediation = L3ClosMediation(self.conf)
        (pod, podDict) = self.createPod(l3ClosMediation)
        self.assertEqual(True, l3ClosMediation.createCablingPlan(pod.id))
        self.assertEqual(True, l3ClosMediation.createDeviceConfig(pod.id))

    def createPodSpineLeaf(self, l3ClosMediation):
        (pod, podDict) = self.createPod(l3ClosMediation)
        return pod
    
    def testCreateLinks(self):
        l3ClosMediation = L3ClosMediation(self.conf)
        pod = self.createPodSpineLeaf(l3ClosMediation)
        
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
    
        ifl = session.query(InterfaceLogical).join(Device).filter(InterfaceLogical.name == 'lo0.0').filter(Device.name == 'leaf-01').filter(Device.pod_id == pod.id).one()
        self.assertEqual('10.0.0.1/32', ifl.ipaddress)
        ifl = session.query(InterfaceLogical).join(Device).filter(InterfaceLogical.name == 'lo0.0').filter(Device.name == 'spine-02').filter(Device.pod_id == pod.id).one()
        self.assertEqual('10.0.0.4/32', ifl.ipaddress)
        self.assertEqual('10.0.0.0/29', pod.allocatedLoopbackBlock)

    def testAllocateIrb(self):
        l3ClosMediation = L3ClosMediation(self.conf)
        pod = self.createPodSpineLeaf(l3ClosMediation)
        session = l3ClosMediation.dao.Session()
        
        ifl = session.query(InterfaceLogical).join(Device).filter(InterfaceLogical.name == 'irb.1').filter(Device.name == 'leaf-01').filter(Device.pod_id == pod.id).one()
        self.assertEqual('172.16.0.1/24', ifl.ipaddress)
        self.assertEqual('172.16.0.0/23', pod.allocatedIrbBlock)

    def testAllocateInterconnect(self):
        l3ClosMediation = L3ClosMediation(self.conf)
        pod = self.createPodSpineLeaf(l3ClosMediation)
        session = l3ClosMediation.dao.Session()

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
        pod = self.createPodSpineLeaf(l3ClosMediation)
        session = l3ClosMediation.dao.Session()

        self.assertEqual(100, session.query(Device).filter(Device.role == 'spine').all()[0].asn)
        self.assertEqual(201, session.query(Device).filter(Device.role == 'leaf').all()[1].asn)
        
    def testCreatePolicyOptionSpine(self):
        l3ClosMediation = L3ClosMediation(self.conf)
        (pod, podDict) = self.createPod(l3ClosMediation)
        device = Device("test", "qfx5100-24q-2p", "user", "pwd", "spine", "mac", "mgmtIp", pod)
        device.pod.allocatedIrbBlock = '10.0.0.0/28'
        device.pod.allocatedLoopbackBlock = '11.0.0.0/28'
        configlet = l3ClosMediation.createPolicyOption(device)
        
        self.assertTrue('irb_in' not in configlet and '10.0.0.0/28' in configlet)
        self.assertTrue('lo0_in' not in configlet and '11.0.0.0/28' in configlet)
        self.assertTrue('lo0_out' not in configlet)
        self.assertTrue('irb_out' not in configlet)

    def testCreatePolicyOptionLeaf(self):
        l3ClosMediation = L3ClosMediation(self.conf)
        (pod, podDict) = self.createPod(l3ClosMediation)
        device = Device("test", "qfx5100-48s-6q", "user", "pwd", "leaf", "mac", "mgmtIp", pod)
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
        self.assertIsNotNone(l3ClosMediation.templateEnv.get_template('protocolBgp.txt'))
        with self.assertRaises(TemplateNotFound) as e:
            l3ClosMediation.templateEnv.get_template('unknown-template')
        self.assertTrue('unknown-template' in e.exception.message)

    def testCreateSnmpTrapAndEventNoNdSpine(self):
        self.conf['snmpTrap'] = {'networkdirector_trap_group': {'port': 10162, 'target': '1.2.3.4'},
                                 'openclos_trap_group': {'port': 20162, 'target': '1.2.3.4'}}
        l3ClosMediation = L3ClosMediation(self.conf)
        
        device = Device("test", "qfx5100-48s-6q", "user", "pwd", "spine", "mac", "mgmtIp", None)
        configlet = l3ClosMediation.createSnmpTrapAndEvent(device)

        self.assertEqual('', configlet)
  
    def testCreateSnmpTrapAndEventNoNdLeaf(self):
        self.conf['snmpTrap'] = {'networkdirector_trap_group': {'port': 10162, 'target': '1.2.3.4'},
                                 'openclos_trap_group': {'port': 20162, 'target': '5.6.7.8'}}
        l3ClosMediation = L3ClosMediation(self.conf)
        
        device = Device("test", "qfx5100-48s-6q", "user", "pwd", "leaf", "mac", "mgmtIp", None)
        configlet = l3ClosMediation.createSnmpTrapAndEvent(device)
        
        self.assertTrue('' != configlet)
        self.assertTrue('event-options' in configlet)
        self.assertTrue('trap-group openclos_trap_group' in configlet)
        self.assertFalse('trap-group networkdirector_trap_group' in configlet)

    def testCreateSnmpTrapAndEventWithNdSpine(self):
        self.conf['snmpTrap'] = {'networkdirector_trap_group': {'port': 10162, 'target': '1.2.3.4'},
                                 'openclos_trap_group': {'port': 20162, 'target': '5.6.7.8'}}
        self.conf['deploymentMode'] = {'ndIntegrated': True}
        l3ClosMediation = L3ClosMediation(self.conf)
        
        device = Device("test", "qfx5100-48s-6q", "user", "pwd", "spine", "mac", "mgmtIp", None)
        configlet = l3ClosMediation.createSnmpTrapAndEvent(device)

        self.assertTrue('' != configlet)
        self.assertTrue('event-options' in configlet)
        self.assertFalse('trap-group openclos_trap_group' in configlet)
        self.assertTrue('trap-group networkdirector_trap_group' in configlet)

    def testCreateSnmpTrapAndEventWithNdLeaf(self):
        self.conf['snmpTrap'] = {'networkdirector_trap_group': {'port': 10162, 'target': '1.2.3.4'},
                                 'openclos_trap_group': {'port': 20162, 'target': '5.6.7.8'}}
        self.conf['deploymentMode'] = {'ndIntegrated': True}
        l3ClosMediation = L3ClosMediation(self.conf)
        
        device = Device("test", "qfx5100-48s-6q", "user", "pwd", "leaf", "mac", "mgmtIp", None)
        configlet = l3ClosMediation.createSnmpTrapAndEvent(device)

        self.assertTrue('' != configlet)
        self.assertTrue('event-options' in configlet)
        self.assertTrue('trap-group openclos_trap_group' in configlet)
        self.assertTrue('trap-group networkdirector_trap_group' in configlet)

    def testCreateSnmpTrapAndEventForLeafFor2ndStage(self):
        self.conf['snmpTrap'] = {'networkdirector_trap_group': {'port': 10162, 'target': '1.2.3.4'},
                                 'openclos_trap_group': {'port': 20162, 'target': '5.6.7.8'}}
        self.conf['deploymentMode'] = {'ndIntegrated': True}
        l3ClosMediation = L3ClosMediation(self.conf)
        
        device = Device("test", "qfx5100-48s-6q", "user", "pwd", "leaf", "mac", "mgmtIp", None)
        configlet = l3ClosMediation.createSnmpTrapAndEventForLeafFor2ndStage(device)
        print configlet
        self.assertTrue('' != configlet)
        self.assertTrue('event-options' in configlet)
        self.assertTrue('trap-group openclos_trap_group' in configlet)
        self.assertTrue('trap-group networkdirector_trap_group' in configlet)
        self.assertEquals(1, configlet.count('destination-port'))
        self.assertEquals(1, configlet.count('targets'))

    def testCreateRoutingOptionsStatic(self):
        l3ClosMediation = L3ClosMediation(self.conf)
        (pod, podDict) = self.createPod(l3ClosMediation)
        device = Device("test", "qfx5100-48s-6q", "user", "pwd", "leaf", "mac", "mgmtIp", pod)
        device.pod.outOfBandGateway = '10.0.0.254'
        device.pod.outOfBandAddressList = '10.0.10.5/32, 10.0.20.5/32'

        configlet = l3ClosMediation.createRoutingOptionsStatic(device)
        self.assertEquals(1, configlet.count('static'))
        self.assertEquals(2, configlet.count('route'))

    def testCreateRoutingOptionsBgp(self):
        pass

    def testCreateLeafGenericConfigNoNd(self):
        self.conf['snmpTrap'] = {'networkdirector_trap_group': {'port': 10162, 'target': '1.2.3.4'},
                                 'openclos_trap_group': {'port': 20162, 'target': '5.6.7.8'}}
        #self.conf['deploymentMode'] = {'ndIntegrated': True}
        l3ClosMediation = L3ClosMediation(self.conf)
        (pod, podDict) = self.createPod(l3ClosMediation)
        pod.outOfBandGateway = '10.0.0.254'
        pod.outOfBandAddressList = '10.0.10.5/32'
        
        configlet = l3ClosMediation.createLeafGenericConfigFor2Stage(pod)
        self.assertTrue('' != configlet)
        self.assertTrue('trap-group openclos_trap_group' in configlet)
        self.assertEquals(1, configlet.count('static'))
        self.assertEquals(1, configlet.count('route'))

    def testCreateLeafGenericConfigWithNd(self):
        self.conf['snmpTrap'] = {'networkdirector_trap_group': {'port': 10162, 'target': '1.2.3.4'},
                                 'openclos_trap_group': {'port': 20162, 'target': '5.6.7.8'}}
        self.conf['deploymentMode'] = {'ndIntegrated': True}
        l3ClosMediation = L3ClosMediation(self.conf)
        (pod, podDict) = self.createPod(l3ClosMediation)
        pod.outOfBandGateway = '10.0.0.254'
        pod.outOfBandAddressList = '10.0.10.5/32'
        
        configlet = l3ClosMediation.createLeafGenericConfigFor2Stage(pod)
        self.assertTrue('' != configlet)
        self.assertTrue('vendor-id Juniper-qfx5100-48s-6q' in configlet)
        self.assertTrue('trap-group openclos_trap_group' in configlet)
        self.assertTrue('trap-group networkdirector_trap_group' in configlet)
        self.assertEquals(1, configlet.count('static'))
        self.assertEquals(1, configlet.count('route'))

if __name__ == '__main__':
    unittest.main()