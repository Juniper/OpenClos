'''
Created on Aug 26, 2014

@author: preethi
'''
import os
import sys
sys.path.insert(0,os.path.abspath(os.path.dirname(__file__) + '/' + '../..')) #trick to make it run from CLI

import unittest
import sqlalchemy
from sqlalchemy.orm import sessionmaker
import pydot
import shutil
from jnpr.openclos.l3Clos import configLocation
from jnpr.openclos.model import ManagedElement, Pod, Device, Interface, InterfaceLogical, InterfaceDefinition, Base
from jnpr.openclos.dotHandler import createDeviceInGraph, createLinksInGraph, createDOTFile
from tests.unit.test_model import createPod, createDevice

class TestOrm(unittest.TestCase):
    def setUp(self):
        
        ''' Deletes 'conf' folder under test dir'''
        shutil.rmtree('./conf', ignore_errors=True)
        ''' Copies 'conf' folder under test dir, to perform tests'''
        shutil.copytree(configLocation, './conf')
        '''
        Change echo=True to troubleshoot ORM issue
        '''
        engine = sqlalchemy.create_engine('sqlite:///:memory:', echo=False)  
        Base.metadata.create_all(engine) 
        Session = sessionmaker(bind=engine)
        self.session = Session()

    def tearDown(self):
        ''' Deletes 'conf' folder under test dir'''
        shutil.rmtree('./conf', ignore_errors=True)
        ''' Deletes 'out' folder under test dir'''
        shutil.rmtree('out', ignore_errors=True)
        self.session.close_all()
        
class testGenerateDOTFile(TestOrm):
    
    def testCreateDeviceInGraph(self):
        # create topology obj
        testDeviceTopology = pydot.Dot(graph_type='graph', )
        device = createDevice(self.session, 'Preethi')
        device.id = 'preethi-1'
        createDeviceInGraph(device.name, device, testDeviceTopology)
        testDeviceTopology.write_raw('testDevicelabel.dot')
        data = open("testDevicelabel.dot", 'r').read()
        self.assertTrue('"preethi-1" [shape=record, label=Preethi];' in data)

    def testcreateLinksInGraph(self):
        testLinksInTopology = pydot.Dot(graph_type='graph')
        podOne = createPod('testpodOne', self.session)
        deviceOne = Device('spine01', 'admin', 'admin',  'spine', "", podOne)
        deviceOne.id = 'spine01'
        IF1 = InterfaceDefinition('IF1', deviceOne, 'downlink')
        IF1.id = 'IF1'
        
        deviceTwo = Device('leaf01', 'admin', 'admin',  'leaf', "", podOne)
        deviceTwo.id = 'leaf01'
        IF21 = InterfaceDefinition('IF1', deviceTwo, 'uplink')
        IF21.id = 'IF21'
        
        IF1.peer = IF21
        IF21.peer = IF1
        linkLabel = {deviceOne.id + ':' + IF1.id : deviceTwo.id + ':' + IF21.id}
        createLinksInGraph(linkLabel, testLinksInTopology, 'red')
        testLinksInTopology.write_raw('testLinklabel.dot')
        data = open("testLinklabel.dot", 'r').read()
        self.assertTrue('spine01:IF1 -- leaf01:IF21  [color=red];' in data)
        
    def testcreateDOTFile(self):
        
        podOne = createPod('testpodOne', self.session)
        self.session.add(podOne)
        deviceOne = Device('spine01', 'admin', 'admin',  'spine', "", podOne)
        self.session.add(deviceOne)
        IF1 = InterfaceDefinition('IF1', deviceOne, 'downlink')
        self.session.add(IF1)
        IF2 = InterfaceDefinition('IF2', deviceOne, 'downlink')
        self.session.add(IF2)
        
        deviceTwo = Device('leaf01', 'admin', 'admin',  'leaf', "", podOne)
        self.session.add(deviceTwo)
        IF21 = InterfaceDefinition('IF1', deviceTwo, 'uplink')
        self.session.add(IF21)
        IF22 = InterfaceDefinition('IF2', deviceTwo, 'uplink')
        self.session.add(IF22)
        IF23 = InterfaceDefinition('IF3', deviceTwo, 'downlink')
        self.session.add(IF23)
        IF24 = InterfaceDefinition('IF3', deviceTwo, 'downlink')
        self.session.add(IF24)
        
        deviceThree = Device('Access01', 'admin', 'admin',  'leaf', "", podOne)
        self.session.add(deviceThree)
        IF31 = InterfaceDefinition('IF1', deviceThree, 'uplink')
        self.session.add(IF31)
        IF32 = InterfaceDefinition('IF2', deviceThree, 'uplink')
        self.session.add(IF32)
        
        IF1.peer = IF21
        IF2.peer = IF22
        IF21.peer = IF1
        IF22.peer = IF2
        IF23.peer = IF31
        IF31.peer = IF23
        IF24.peer = IF32
        IF32.peer = IF24   
        
        self.session.commit()
        devices = self.session.query(Device).all()
        createDOTFile(devices)