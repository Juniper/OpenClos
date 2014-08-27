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
from jnpr.openclos.l3Clos import loadConfig, configLocation, L3ClosMediation, FileOutputHandler
from jnpr.openclos.model import Pod, Device, InterfaceLogical, InterfaceDefinition


class TestFunctions(unittest.TestCase):
    def testLoadDefaultConfig(self):
        self.assertIsNotNone(loadConfig())
    def testLoadNonExistingConfig(self):
        self.assertIsNone(loadConfig('non-existing.yaml'))

class TestFileOutputHandler(unittest.TestCase):
    def tearDown(self):
        ''' Deletes 'out' and 'out2' folder under test dir'''
        shutil.rmtree('out', ignore_errors=True)
        shutil.rmtree('out2', ignore_errors=True)

    def createPod(self):
        pod = {}
        pod['spineCount'] = '3'
        pod['spineDeviceType'] = 'esx-switch'
        pod['leafCount'] = '5'
        pod['leafDeviceType'] = 'esx-switch'
        pod['interConnectPrefix'] = '1.2.0.0'
        pod['vlanPrefix'] = '1.3.0.0'
        pod['loopbackPrefix'] = '1.4.0.0'
        pod['spineAS'] = '100'
        pod['leafAS'] = '100'
        pod['topologyType'] = 'pod-dev-IF'
        return Pod("TestPod", **pod)

    def testDefaultInit(self):
        pod = self.createPod()
            
        FileOutputHandler({}, pod)
        dirName = 'out/' + pod.name
        self.assertTrue(os.path.exists(dirName))

    def testInitFromConfig(self):
        pod = self.createPod()
            
        FileOutputHandler({'outputDir':'out2'}, pod)
        dirName = 'out2/' + pod.name
        self.assertTrue(os.path.exists(dirName))

    def testHandle(self):
        pod = self.createPod()
            
        out = FileOutputHandler({}, pod)
        out.handle(pod, Device("TestDevice", "", "", "", "spine", "", pod), '')
        self.assertTrue(os.path.exists(out.outputDir + '/TestDevice.conf'))            

class TestL3Clos(unittest.TestCase):
    def setUp(self):
        ''' Deletes 'conf' folder under test dir'''
        shutil.rmtree('./conf', ignore_errors=True)
        ''' Copies 'conf' folder under test dir, to perform tests'''
        shutil.copytree(configLocation, './conf')
        
        '''Creates Dao with in-memory DB'''
        self.conf = {}
        self.conf['dbUrl'] = 'sqlite:///'
    
    def tearDown(self):
        ''' Deletes 'conf' folder under test dir'''
        shutil.rmtree('./conf', ignore_errors=True)
        ''' Deletes 'out' folder under test dir'''
        shutil.rmtree('out', ignore_errors=True)

    def testInitWithTemplate(self):
        from jinja2 import TemplateNotFound
        l3ClosMediation = L3ClosMediation(self.conf)
        self.assertIsNotNone(l3ClosMediation.templateEnv.get_template('protocolBgpLldp.txt'))
        with self.assertRaises(TemplateNotFound) as e:
            l3ClosMediation.templateEnv.get_template('unknown-template')
        self.assertTrue('unknown-template' in e.exception.message)

    def testLoadClosDefinition(self):
        l3ClosMediation = L3ClosMediation(self.conf)
        dao = l3ClosMediation.dao

        l3ClosMediation.loadClosDefinition()
        self.assertEqual(2, len(dao.getAll(Pod)))

    def testLoadNonExistingClosDefinition(self):
        l3ClosMediation = L3ClosMediation(self.conf)
        dao = l3ClosMediation.dao

        l3ClosMediation.loadClosDefinition('non-existing.yaml')
        self.assertEqual(0, len(dao.getAll(Pod)))

    def testCreatePods(self):
        l3ClosMediation = L3ClosMediation(self.conf)
        dao = l3ClosMediation.dao

        podString = u'{"barclaysL3Clos" : {"leafDeviceType": "QFX5100", "spineAS": 100, "spineDeviceType": "QFX5100", "leafCount": 6, "interConnectPrefix": "192.168.0.0", "spineCount": 4, "vlanPrefix": "172.16.0.0", "topologyType": "leaf-spine", "loopbackPrefix": "10.0.0.0", "leafAS": 200}, "testL3Clos" : {"leafDeviceType": "QFX5100", "spineAS": 100, "spineDeviceType": "QFX5100", "leafCount": 6, "interConnectPrefix": "192.168.0.0", "spineCount": 4, "vlanPrefix": "172.16.0.0", "topologyType": "leaf-spine", "loopbackPrefix": "10.0.0.0", "leafAS": 200}}'
        l3ClosMediation.createPods(json.loads(podString))
        self.assertEqual(2, len(dao.getAll(Pod)))

    def testProcessTopologyNoPodFound(self):
        l3ClosMediation = L3ClosMediation(self.conf)
        
        with self.assertRaises(ValueError) as ve:
            l3ClosMediation.processTopology("anyName")
        error = ve.exception.message
        self.assertEqual(1, error.count('NoResultFound'))

    def testProcessTopologyMultiplePods(self):
        l3ClosMediation = L3ClosMediation(self.conf)

        podString = u'{"pod1" : {"leafDeviceType": "QFX5100-24Q", "spineAS": 100, "spineDeviceType": "QFX5100", "leafCount": 6, "interConnectPrefix": "192.168.0.0", "spineCount": 4, "vlanPrefix": "172.16.0.0", "topologyType": "leaf-spine", "loopbackPrefix": "10.0.0.0", "leafAS": 200}}'
        l3ClosMediation.createPods(json.loads(podString))

        podString = u'{"pod1" : {"leafDeviceType": "QFX5100-48S", "spineAS": 100, "spineDeviceType": "QFX5100", "leafCount": 6, "interConnectPrefix": "192.168.0.0", "spineCount": 4, "vlanPrefix": "172.16.0.0", "topologyType": "leaf-spine", "loopbackPrefix": "10.0.0.0", "leafAS": 200}}'
        l3ClosMediation.createPods(json.loads(podString))
        
        with self.assertRaises(ValueError) as ve:
            l3ClosMediation.processTopology("pod1")
        error = ve.exception.message
        self.assertEqual(1, error.count('MultipleResultsFound'))

    def testProcessTopologyNoTopology(self):
        l3ClosMediation = L3ClosMediation(self.conf)

        podString = u'{"pod1" : {"leafDeviceType": "QFX5100-24Q", "spineAS": 100, "spineDeviceType": "QFX5100", "leafCount": 6, "interConnectPrefix": "192.168.0.0", "spineCount": 4, "vlanPrefix": "172.16.0.0", "topologyType": "leaf-spine", "loopbackPrefix": "10.0.0.0", "leafAS": 200}}'
        l3ClosMediation.createPods(json.loads(podString))

        with self.assertRaises(ValueError):
            l3ClosMediation.processTopology("pod1")

    def testProcessTopology(self):
        l3ClosMediation = L3ClosMediation(self.conf)
        l3ClosMediation.loadClosDefinition()
        
        l3ClosMediation = flexmock(l3ClosMediation)
        l3ClosMediation.should_receive('createSpineIFDs').once()
        l3ClosMediation.should_receive('createLeafIFDs').once()
        l3ClosMediation.should_receive('createLinkBetweenIFDs').once()
        l3ClosMediation.should_receive('generateConfig').once()
        l3ClosMediation.should_receive('allocateResource').once()

        l3ClosMediation.processTopology('labLeafSpine')
        self.assertIsNotNone(l3ClosMediation.output)
            
    def createPod(self, l3ClosMediation):
        podString = u'{"pod1" : {"leafDeviceType": "QFX5100-48S", "spineAS": 100, "spineDeviceType": "QFX5100-24Q", "leafCount": 6, "interConnectPrefix": "192.168.0.0", "spineCount": 4, "vlanPrefix": "172.16.0.0", "topologyType": "leaf-spine", "loopbackPrefix": "10.0.0.0", "leafAS": 200}}'
        l3ClosMediation.createPods(json.loads(podString))
        return l3ClosMediation.dao.getUniqueObjectByName(Pod, 'pod1')

    def testCreateSpines(self):
        from jnpr.openclos.l3Clos import util
        flexmock(util, getPortNamesForDeviceFamily={'ports': ['et-0/0/0', 'et-0/0/1']})
        self.conf['deviceFamily'] = {}
        #self.conf['debugSql'] = True

        l3ClosMediation = L3ClosMediation(self.conf)
        dao = l3ClosMediation.dao
        pod = self.createPod(l3ClosMediation)

        spineString = u'[{ "name" : "spine-01", "mac_address" : "aa:bb:cc:dd:ee:f1", "mgmt_ip" : "172.32.32.201/24", "user" : "root", "password" : "Embe1mpls" }, { "name" : "spine-02", "mac_address" : "aa:bb:cc:dd:ee:f2", "mgmt_ip" : "172.32.32.202/24", "user" : "root", "password" : "Embe1mpls" }]'
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
        pod = self.createPod(l3ClosMediation)

        leafString = u'[{ "name" : "leaf-01", "mac_address" : "aa:bb:cc:dd:ee:f1", "mgmt_ip" : "172.32.32.201/24", "user" : "root", "password" : "Embe1mpls" }, { "name" : "leaf-02", "mac_address" : "aa:bb:cc:dd:ee:f2", "mgmt_ip" : "172.32.32.202/24", "user" : "root", "password" : "Embe1mpls" }]'
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

        pod = self.createPod(l3ClosMediation)
        spineString = u'[{ "name" : "spine-01", "mac_address" : "aa:bb:cc:dd:ee:f1", "mgmt_ip" : "172.32.32.201/24", "user" : "root", "password" : "Embe1mpls" }, { "name" : "spine-02", "mac_address" : "aa:bb:cc:dd:ee:f2", "mgmt_ip" : "172.32.32.202/24", "user" : "root", "password" : "Embe1mpls" }]'
        l3ClosMediation.createSpineIFDs(pod, json.loads(spineString))
        leafString = u'[{ "name" : "leaf-01", "mac_address" : "aa:bb:cc:dd:ee:f1", "mgmt_ip" : "172.32.32.201/24", "user" : "root", "password" : "Embe1mpls" }, { "name" : "leaf-02", "mac_address" : "aa:bb:cc:dd:ee:f2", "mgmt_ip" : "172.32.32.202/24", "user" : "root", "password" : "Embe1mpls" }]'
        l3ClosMediation.createLeafIFDs(pod, json.loads(leafString))
        return pod
    
    def testCreateLinks(self):
        l3ClosMediation = L3ClosMediation(self.conf)
        pod = self.createPodSpineLeaf(l3ClosMediation)
        
        '''
        [{ "s_name" : "spine-01", "s_port" : "et-0/0/0", "l_name" : "leaf-01", "l_port" : "et-0/0/48" },
        { "s_name" : "spine-01", "s_port" : "et-0/0/1", "l_name" : "leaf-02", "l_port" : "et-0/0/48" },
        { "s_name" : "spine-02", "s_port" : "et-0/0/0", "l_name" : "leaf-01", "l_port" : "et-0/0/49" },
        { "s_name" : "spine-02", "s_port" : "et-0/0/1", "l_name" : "leaf-02", "l_port" : "et-0/0/49" }]
        '''
        linkString = u'[{ "s_name" : "spine-01", "s_port" : "et-0/0/0", "l_name" : "leaf-01", "l_port" : "et-0/0/48" }, { "s_name" : "spine-01", "s_port" : "et-0/0/1", "l_name" : "leaf-02", "l_port" : "et-0/0/48" }, { "s_name" : "spine-02", "s_port" : "et-0/0/0", "l_name" : "leaf-01", "l_port" : "et-0/0/49" }, { "s_name" : "spine-02", "s_port" : "et-0/0/1", "l_name" : "leaf-02", "l_port" : "et-0/0/49" }]'
        l3ClosMediation.createLinkBetweenIFDs(pod, json.loads(linkString))

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
        linkString = u'[{ "s_name" : "spine-01", "s_port" : "et-0/0/0", "l_name" : "leaf-01", "l_port" : "et-0/0/48" }, { "s_name" : "spine-01", "s_port" : "et-0/0/1", "l_name" : "leaf-02", "l_port" : "et-0/0/48" }, { "s_name" : "spine-02", "s_port" : "et-0/0/0", "l_name" : "leaf-01", "l_port" : "et-0/0/49" }, { "s_name" : "spine-02", "s_port" : "et-0/0/1", "l_name" : "leaf-02", "l_port" : "et-0/0/49" }]'
        l3ClosMediation.createLinkBetweenIFDs(pod, json.loads(linkString))
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
        device = Device("test", "QFX5100-24Q", "user", "pwd", "spine", "mgmtIp", self.createPod(l3ClosMediation))
        device.pod.allocatedIrbBlock = '10.0.0.0/28'
        device.pod.allocatedLoopbackBlock = '11.0.0.0/28'
        configlet = l3ClosMediation.createPolicyOption(device)
        
        self.assertTrue('irb_in' not in configlet and '10.0.0.0/28' in configlet)
        self.assertTrue('lo0_in' not in configlet and '11.0.0.0/28' in configlet)
        self.assertTrue('lo0_out' not in configlet)
        self.assertTrue('irb_out' not in configlet)

    def testCreatePolicyOptionLeaf(self):
        l3ClosMediation = L3ClosMediation(self.conf)
        device = Device("test", "QFX5100-48S", "user", "pwd", "leaf", "mgmtIp", self.createPod(l3ClosMediation))
        device.pod.allocatedIrbBlock = '10.0.0.0/28'
        device.pod.allocatedLoopbackBlock = '11.0.0.0/28'        
        flexmock(l3ClosMediation.dao.Session).should_receive('query.join.filter.filter.one').and_return(InterfaceLogical("test", device, '12.0.0.0/28'))

        configlet = l3ClosMediation.createPolicyOption(device)
        self.assertTrue('irb_in' not in configlet and '10.0.0.0/28' in configlet)
        self.assertTrue('lo0_in' not in configlet and '11.0.0.0/28' in configlet)
        self.assertTrue('lo0_out' not in configlet and '12.0.0.0/28' in configlet)
        self.assertTrue('irb_out' not in configlet)
        
if __name__ == '__main__':
    unittest.main()