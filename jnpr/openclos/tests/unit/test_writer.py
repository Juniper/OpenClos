'''
Created on Aug 26, 2014

@author: preethi
'''
import os
import sys
import shutil
sys.path.insert(0,os.path.abspath(os.path.dirname(__file__) + '/' + '../..')) #trick to make it run from CLI

import unittest
import sqlalchemy
from sqlalchemy.orm import sessionmaker
import pydot
from jnpr.openclos.model import Pod, Device, InterfaceDefinition, InterfaceLogical, Interface, Base
from jnpr.openclos.writer import WriterBase, ConfigWriter, CablingPlanWriter
from jnpr.openclos.util import configLocation
from jnpr.openclos.dao import Dao
from test_model import createPod, createPodDevice
from flexmock import flexmock

class TestWriterBase(unittest.TestCase):

    def setUp(self):
        self.conf = {}
        self.conf['outputDir'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'out')
        self.conf['dbUrl'] = 'sqlite:///'
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
        self.dao = Dao(self.conf)
        ''' Deletes 'out' folder under test dir'''
        shutil.rmtree(self.conf['outputDir'], ignore_errors=True)

    def tearDown(self):
        ''' Deletes 'out' folder under test dir'''
        shutil.rmtree(self.conf['outputDir'], ignore_errors=True)
        
class TestConfigWriter(TestWriterBase):

    def testWriteConfigInFile(self):
        pod = createPod('pod1', self.dao.Session())
        device = Device('test_device', "",'admin', 'admin', 'spine', "", "", pod)
        device.config = "dummy config"
        configWriter = ConfigWriter(self.conf, pod, self.dao)
        configWriter.write(device)
        self.assertTrue(os.path.exists(os.path.join(configWriter.outputDir, device.id+'__test_device.conf')))
        
class TestCablingPlanWriter(TestWriterBase):
    
    def testInitWithTemplate(self):
        from jinja2 import TemplateNotFound
        pod = createPod('pod1', self.dao.Session())
        cablingPlanWriter = CablingPlanWriter(self.conf, pod, self.dao)
        self.assertIsNotNone(cablingPlanWriter.template)
        with self.assertRaises(TemplateNotFound) as e:
            cablingPlanWriter.templateEnv.get_template('unknown-template')
        self.assertTrue('unknown-template' in e.exception.message)
        
    def testCreateDeviceInGraph(self):
        testDeviceTopology = pydot.Dot(graph_type='graph', )
        pod = createPod('pod1', self.dao.Session())
        cablingPlanWriter = CablingPlanWriter(self.conf, pod, self.dao)
        device = createPodDevice(self.dao.Session(), 'Preethi', pod)
        device.id = 'preethi-1'
        cablingPlanWriter.createDeviceInGraph(device.name, device, testDeviceTopology)
        path = cablingPlanWriter.outputDir + '/testDevicelabel.dot'
        testDeviceTopology.write_raw(path)
        data = open(path, 'r').read()
        #check the generated label for device
        self.assertTrue('"preethi-1" [shape=record, label=Preethi];' in data)

    def testcreateLinksInGraph(self):
        testLinksInTopology = pydot.Dot(graph_type='graph')
        pod = createPod('pod1', self.dao.Session())
        cablingPlanWriter = CablingPlanWriter(self.conf, pod, self.dao)
        deviceOne = Device('spine01','QFX5100-24Q', 'admin', 'admin',  'spine', "", "", pod)
        deviceOne.id = 'spine01'
        IF1 = InterfaceDefinition('IF1', deviceOne, 'downlink')
        IF1.id = 'IF1'
        
        deviceTwo = Device('leaf01','QFX5100-48S', 'admin', 'admin',  'leaf', "", "", pod)
        deviceTwo.id = 'leaf01'
        IF21 = InterfaceDefinition('IF1', deviceTwo, 'uplink')
        IF21.id = 'IF21'
        
        IF1.peer = IF21
        IF21.peer = IF1
        linkLabel = {deviceOne.id + ':' + IF1.id : deviceTwo.id + ':' + IF21.id}
        cablingPlanWriter.createLinksInGraph(linkLabel, testLinksInTopology, 'red')
        path = cablingPlanWriter.outputDir + '/testLinklabel.dot'
        testLinksInTopology.write_raw(path)
        data = open(path, 'r').read()
        #check generated label for links
        self.assertTrue('spine01:IF1 -- leaf01:IF21  [color=red];' in data)
        
    def testcreateDOTFile(self):
        # create pod
        # create device
        #create interface
        session = self.dao.Session()
        pod = createPod('pod1', session)
        cablingPlanWriter = CablingPlanWriter(self.conf, pod, self.dao)
        deviceOne = Device('spine01','QFX5100-24Q', 'admin', 'admin',  'spine', "", "", pod)
        session.add(deviceOne)
        IF1 = InterfaceDefinition('et-0/0/0', deviceOne, 'downlink')
        IFL1 = InterfaceLogical('et-0/0/0', deviceOne, '1.2.3.4', 9000)
        IF1.layerAboves.append(IFL1)
        session.add(IF1)
        session.add(IFL1)
        IF2 = InterfaceDefinition('et-0/0/1', deviceOne, 'downlink')
        IFL2 = InterfaceLogical('et-0/0/1', deviceOne, '1.2.3.4', 9000)
        IF2.layerAboves.append(IFL2)
        session.add(IF2)
        session.add(IFL1)
        
        deviceTwo = Device('leaf01','QFX5100-48S', 'admin', 'admin',  'leaf', "", "", pod)
        session.add(deviceTwo)
        IF21 = InterfaceDefinition('et-0/0/13', deviceTwo, 'uplink')
        IFL21 = InterfaceLogical('et-0/0/13', deviceTwo, '1.2.3.4', 9000)
        IF21.layerAboves.append(IFL21)
        session.add(IF21)
        session.add(IFL21)
        IF22 = InterfaceDefinition('et-0/0/13', deviceTwo, 'uplink')
        IFL22 = InterfaceLogical('et-0/0/14', deviceTwo, '1.2.3.4', 9000)
        IF22.layerAboves.append(IFL22)
        session.add(IF22)
        session.add(IFL22)
        IF23 = InterfaceDefinition('et-0/0/14', deviceTwo, 'downlink')
        IFL23 = InterfaceLogical('et-0/0/15', deviceTwo, '1.2.3.4', 9000)
        IF23.layerAboves.append(IFL23)
        session.add(IF23)
        session.add(IFL23)
        IF24 = InterfaceDefinition('et-0/0/15', deviceTwo, 'downlink')
        IFL24 = InterfaceLogical('et-0/0/15', deviceTwo, '1.2.3.4', 9000)
        IF24.layerAboves.append(IFL24)
        session.add(IF24)
        session.add(IFL24)
        
        deviceThree = Device('Access01', 'QFX5100-48S','admin', 'admin',  'leaf', "", "", pod)
        session.add(deviceThree)
        IF31 = InterfaceDefinition('et-0/0/1', deviceThree, 'uplink')
        IFL31 = InterfaceLogical('et-0/0/1', deviceThree, '1.2.3.4', 9000)
        IF31.layerAboves.append(IFL31)
        session.add(IF31)
        session.add(IFL31)
        IF32 = InterfaceDefinition('et-0/0/2', deviceThree, 'uplink')
        IFL32 = InterfaceLogical('et-0/0/2', deviceThree, '1.2.3.4', 9000)
        IF32.layerAboves.append(IFL32)
        session.add(IF32)
        session.add(IFL2)
        
        IF1.peer = IF21
        IF2.peer = IF22
        IF21.peer = IF1
        IF22.peer = IF2
        IF23.peer = IF31
        IF31.peer = IF23
        IF24.peer = IF32
        IF32.peer = IF24   
        
        session.commit()
        devices = session.query(Device).all()
        #check the DOT file is generated
        cablingPlanWriter.writeDOT()
        data = open(cablingPlanWriter.outputDir + '/cablingPlan.dot', 'r').read()
        #check generated label for links
        self.assertTrue('splines=polyline;' in data)
        