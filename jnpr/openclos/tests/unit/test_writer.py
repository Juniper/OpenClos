'''
Created on Aug 26, 2014

@author: preethi
'''
import os
import sys
import shutil
sys.path.insert(0,os.path.abspath(os.path.dirname(__file__) + '/' + '../..')) #trick to make it run from CLI

import unittest
import pydot
from jnpr.openclos.model import Device, InterfaceDefinition
from jnpr.openclos.writer import ConfigWriter, CablingPlanWriter
from jnpr.openclos.dao import Dao
from test_model import createPod, createPodDevice

class TestWriterBase(unittest.TestCase):

    def setUp(self):
        self.conf = {}
        self.conf['outputDir'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'out')
        self.conf['dbUrl'] = 'sqlite:///'
        self.conf['DOT'] = {'ranksep' : '5 equally', 'colors': ['red', 'green', 'blue']}
        self.conf['deviceFamily'] = {
            "qfx-5100-24q-2p": {
                "ports": 'et-0/0/[0-23]'
            },
            "qfx-5100-48s-6q": {
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
        self.conf['writeConfigInFile'] = True
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
        self.assertTrue('"preethi-1"' in data and 'label=Preethi' in data)

    def testcreateLinksInGraph(self):
        testLinksInTopology = pydot.Dot(graph_type='graph')
        pod = createPod('pod1', self.dao.Session())
        cablingPlanWriter = CablingPlanWriter(self.conf, pod, self.dao)
        deviceOne = Device('spine01','qfx-5100-24q-2p', 'admin', 'admin',  'spine', "", "", pod)
        deviceOne.id = 'spine01'
        IF1 = InterfaceDefinition('IF1', deviceOne, 'downlink')
        IF1.id = 'IF1'
        
        deviceTwo = Device('leaf01','qfx-5100-48s-6q', 'admin', 'admin',  'leaf', "", "", pod)
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
        #check the DOT file is generated
        cablingPlanWriter.writeDOT()
        data = open(cablingPlanWriter.outputDir + '/cablingPlan.dot', 'r').read()
        #check generated label for links
        self.assertTrue('splines=polyline;' in data)
        