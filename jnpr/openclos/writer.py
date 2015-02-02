'''
Created on Aug 14, 2014

@author: preethi
'''
import pydot
import os
import logging
from jinja2 import Environment, PackageLoader

from model import InterfaceDefinition, AdditionalLink
import util

cablingPlanTemplateLocation = os.path.join('conf', 'cablingPlanTemplates')

moduleName = 'writer'
logger = None

class WriterBase():
    def __init__(self, conf, pod, dao):
        global logger
        logger = logging.getLogger(moduleName)
       
        self._dao = dao
        # this writer is specific for this pod
        self._pod = pod
        self._conf = conf
        self.outputDir = util.createOutFolder(self._conf, self._pod)       
        
class ConfigWriter(WriterBase):
    def __init__(self, conf, pod, dao):
        WriterBase.__init__(self, conf, pod, dao)
        self.writeInFile = self._conf.get('writeConfigInFile', False)
        
    def write(self, device):
        if not self.writeInFile:
            return
        
        fileName = device.id + '__' + device.name
        logger.info('Writing config file for device: %s' % (fileName))
        with open(os.path.join(self.outputDir, fileName + '.conf'), 'w') as f:
            f.write(device.config.config)
            
    def writeGenericLeaf(self, pod):
        if not self.writeInFile:
            return
        
        for leafConfig in pod.leafSettings:
            fileName =  leafConfig.deviceFamily + '.conf'
            logger.info('Writing leaf generic config file for : %s' % (fileName))
            with open(os.path.join(self.outputDir, fileName), 'w') as f:
                f.write(leafConfig.config)            

class DhcpConfWriter(WriterBase):
    def __init__(self, conf, pod, dao):
        WriterBase.__init__(self, conf, pod, dao)

    def write(self, dhcpConf):
        if dhcpConf is not None:
            logger.info('Writing dhcpd.conf for pod: %s' % (self._pod.name))
            with open(os.path.join(self.outputDir, 'dhcpd.conf'), 'w') as f:
                    f.write(dhcpConf)
        else:
            logger.error('No content, skipping writing dhcpd.conf for pod: %s' % (self._pod.name))

    def writeSingle(self, dhcpConf):
        if dhcpConf is not None:
            logger.info('Writing single dhcpd.conf for all pods')
            with open(os.path.join(self.outputDir, '..', 'dhcpd.conf'), 'w') as f:
                    f.write(dhcpConf)
        else:
            logger.error('No content, skipping writing single dhcpd.conf for all pods')

class CablingPlanWriter(WriterBase):
    def __init__(self, conf, pod, dao):
        WriterBase.__init__(self, conf, pod, dao)
        self.templateEnv = Environment(loader=PackageLoader('jnpr.openclos', cablingPlanTemplateLocation))
        #self.templateEnv.trim_blocks = True
        self.templateEnv.lstrip_blocks = True
        # load cabling plan template
        self.template = self.templateEnv.get_template(self._pod.topologyType + '.txt')
        # load L2Report template
        self.l2ReportTemplate = self.templateEnv.get_template(self._pod.topologyType + 'L2Report.json')
        # validity check
        if 'deviceFamily' not in self._conf:
            raise ValueError("No deviceFamily found in configuration file")

    def writeJSON(self):
        if self._pod.topologyType == 'threeStage':
            return self.writeThreeStageCablingJson()
        elif self._pod.topologyType == 'fiveStageRealEstate':
            return self.writeJSONFiveStageRealEstate()
        elif self._pod.topologyType == 'fiveStagePerformance':
            return self.writeJSONFiveStagePerformance()

    def getDataFor3StageCablingPlan(self):            
        devices = []
        links = []
        for device in self._pod.devices:
            devices.append({'id': device.id, 'name': device.name, 'family': device.family, 'role': device.role, 'status': device.l2Status, 'reason': device.l2StatusReason, 'deployStatus': device.deployStatus})
            if device.role == 'spine':
                continue
            with self._dao.getReadSession() as session:
                leafPeerPorts = self._dao.getConnectedInterconnectIFDsFilterFakeOnes(session, device)
                for port in leafPeerPorts:
                    leafInterconnectIp = port.layerAboves[0].ipaddress #there is single IFL as layerAbove, so picking first one
                    spinePeerPort = port.peer
                    spineInterconnectIp = spinePeerPort.layerAboves[0].ipaddress #there is single IFL as layerAbove, so picking first one
                    links.append({'device1': device.name, 'port1': port.name, 'ip1': leafInterconnectIp, 
                                  'device2': spinePeerPort.device.name, 'port2': spinePeerPort.name, 'ip2': spineInterconnectIp, 'lldpStatus': port.lldpStatus})

        return {'devices': devices, 'links': links}
    
    def getThreeStageCablingJson(self):
        '''
        This method will be called by REST layer
        :returns str:cablingPlan in json format.
        '''
        data = self.getDataFor3StageCablingPlan()
        cablingPlanJson = self.template.render(devices = data['devices'], links = data['links'])
        return cablingPlanJson
    
    def writeThreeStageCablingJson(self):
        cablingPlanJson = self.getThreeStageCablingJson()

        path = os.path.join(self.outputDir, 'cablingPlan.json')
        logger.info('Writing cabling plan: %s' % (path))
        with open(path, 'w') as f:
                f.write(cablingPlanJson)
        
        return cablingPlanJson

    def getDataFor3StageL2Report(self):            
        devices = []
        links = []
        for device in self._pod.devices:
            if device.deployStatus == 'deploy':
                devices.append({'id': device.id, 'name': device.name, 'family': device.family, 'role': device.role, 'status': device.l2Status, 'reason': device.l2StatusReason, 'deployStatus': device.deployStatus})
                if device.role == 'spine':
                    continue
                with self._dao.getReadSession() as session:
                    leafPeerPorts = self._dao.getConnectedInterconnectIFDsFilterFakeOnes(session, device)
                    for port in leafPeerPorts:
                        leafInterconnectIp = port.layerAboves[0].ipaddress #there is single IFL as layerAbove, so picking first one
                        spinePeerPort = port.peer
                        spineInterconnectIp = spinePeerPort.layerAboves[0].ipaddress #there is single IFL as layerAbove, so picking first one
                        if spinePeerPort.device.deployStatus == 'deploy':
                            links.append({'device1': device.name, 'port1': port.name, 'ip1': leafInterconnectIp, 
                                          'device2': spinePeerPort.device.name, 'port2': spinePeerPort.name, 'ip2': spineInterconnectIp, 'lldpStatus': port.lldpStatus})

        with self._dao.getReadSession() as session:
            # additional links
            additionalLinkList = []
            additionalLinks = session.query(AdditionalLink).all()
            if additionalLinks is not None:
                for link in additionalLinks:
                    additionalLinkList.append({'device1': link.device1, 'port1': link.port1, 'ip1': '', 
                                               'device2': link.device2, 'port2': link.port2, 'ip2': '', 
                                               'lldpStatus': link.lldpStatus})

        return {'devices': devices, 'links': links, 'additionalLinks': additionalLinkList}
        
    def getThreeStageL2ReportJson(self):
        '''
        This method will be called by REST layer
        :returns str: l2Report in json format.
        '''
        data = self.getDataFor3StageL2Report()
        l2ReportJson = self.l2ReportTemplate.render(devices = data['devices'], links = data['links'], additionalLinks = data['additionalLinks'])
        return l2ReportJson
    
    def writeThreeStageL2ReportJson(self):
        l2ReportJson = self.getThreeStageL2ReportJson()
        path = os.path.join(self.outputDir, 'l2Report.json')
        logger.info('Writing L2Report: %s' % (path))
        with open(path, 'w') as f:
                f.write(l2ReportJson)
        return l2ReportJson

    def writeJSONFiveStageRealEstate(self):
        pass

    def writeJSONFiveStagePerformance(self):
        pass
        
    def writeDOT(self):
        if self._pod.topologyType == 'threeStage':
            return self.writeDOTThreeStage()
        elif self._pod.topologyType == 'fiveStageRealEstate':
            return self.writeDOTFiveStageRealEstate()
        elif self._pod.topologyType == 'fiveStagePerformance':
            return self.writeDOTFiveStagePerformance()
    
    def writeDOTThreeStage(self):
        '''
        creates DOT file for devices in topology which has peers
        '''
       
        topology = self.createLabelForDevices(self._pod.devices, self._conf['DOT'])
        colors = self._conf['DOT']['colors']
        i =0
        for device in self._pod.devices:
            linkLabel = self.createLabelForLinks(device)
            if(i == len(colors)): 
                i=0
                self.createLinksInGraph(linkLabel, topology, colors[i])
                i+=1
            else:
                self.createLinksInGraph(linkLabel, topology, colors[i])
                i+=1
            
        path = os.path.join(self.outputDir, 'cablingPlan.dot')
        logger.info('Writing cabling plan: %s' % (path))
        topology.write_raw(path)

    def createLabelForDevices(self, devices, conf):
        #create the graph 
        ranksep = conf['ranksep']
        topology = pydot.Dot(graph_type='graph', splines='polyline', ranksep=ranksep)
        for device in devices:
            label = self.createLabelForDevice(device)
            self.createDeviceInGraph(label, device, topology)
        return topology    
                
    def createLabelForDevice(self, device):
        label = '{'
      
        label = label + '{'
        for ifd in device.interfaces: 
            if type(ifd) is InterfaceDefinition: 
                if ifd.role == 'uplink':
                    if ifd.peer is not None:
                        label += '<'+ifd.id+'>'+ ifd.name+"\<" + ifd.layerAboves[0].ipaddress +"\>"+'|'
                    
        if label.endswith('|'):
            label = label[:-1]
            if device.deployStatus == 'deploy':
                label += '}|{' + device.name + "\{" +device.family + "\}" + '}|{'
            else:
                label += '}|{' + device.name + '}|{'
        else:
            if device.deployStatus == 'deploy':
                label += device.name + "\{" +device.family + "\}" + '}|{'
            else:
                label += device.name + '}|{'
            
        for ifd in device.interfaces:
            if type(ifd) is InterfaceDefinition:
                if ifd.role == 'downlink':
                    if ifd.peer is not None:
                        label += '<'+ifd.id+'>'+ ifd.name+ "\<" + ifd.layerAboves[0].ipaddress +"\>"+'|'
                    
        if label.endswith('|'):
            label = label[:-1]
            label += '}}'
        else:
            label = label[:-2]
            label += '}'
            
        return label

    def createDeviceInGraph(self, labelStrs, device, testDeviceLabel):
        #create device in DOT graph
        if device.deployStatus == 'deploy':
            deviceColor = 'green'
        else:
            deviceColor = 'red'
        testDeviceLabel.add_node(pydot.Node(device.id, shape='record', style='filled', color=deviceColor,  label= labelStrs))
        
    def createLabelForLinks(self, device):
        links = {}
                      
        for ifd in device.interfaces:
            if type(ifd) is InterfaceDefinition:
                if ifd.role == 'downlink':
                    if ifd.peer is not None: 
                        interface =  '"'+ device.id +'"'+ ':' +'"'+ ifd.id +'"'
                        peer = '"'+ifd.peer.device.id +'"' + ':' +'"'+ ifd.peer.id +'"'
                        links[interface] = peer
                       
        return links

    def createLinksInGraph(self, links, linksInTopology, color):
        #create peer links between the devices in DOT graph
        for interface, peer in links.iteritems():
            linksInTopology.add_edge(pydot.Edge(interface, peer,color=color))

    def writeDOTFiveStageRealEstate(self):
        pass
        
    def writeDOTFiveStagePerformance(self):
        pass
        
