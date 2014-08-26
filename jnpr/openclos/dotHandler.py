'''
Created on Aug 14, 2014

@author: preethi
'''
import pydot
import yaml
import sys
import os
from jnpr.openclos.model import Pod, Device, Interface, InterfaceDefinition



def loadConfig(confFile = 'openclos.yaml'):
    '''
    Loads global configuration and creates hash 'conf'

    '''
    configLocation = 'conf/'
    junosTemplateLocation = configLocation + 'junosTemplates/'
    try:
        confStream = open(configLocation + confFile, 'r')
        conf = yaml.load(confStream)
        
    except (OSError, IOError) as e:
        print "File error:", e
    except (yaml.scanner.ScannerError) as e:
        print "YAML error:", e
        confStream.close()
    finally:
        pass
    return conf

def createLabelForDevices(devices):
    conf = loadConfig()
    ranksep = conf['DOT']['ranksep']
    topology = pydot.Dot(graph_type='graph', splines='polyline', ranksep=ranksep)
    for device in devices:
        label = createLabelForDevice(device)
        createDeviceInGraph(label, device, topology)
    return topology

def createDOTFile(devices):
    topology = createLabelForDevices(devices)
    conf = loadConfig()
    colors = conf['DOT']['colors']
    i =0
    for device in devices:
        linkLabel = createLabelForLinks(device)
        if(i == len(colors)): 
            i=0
            createLinksInGraph(linkLabel, topology, colors[i])
            i+=1
        else:
            createLinksInGraph(linkLabel, topology, colors[i])
            i+=1
        
    topology.write_raw('l3closDOT.dot')
    print("wrote l3closDOT.dot")
       
def createLabelForDevice(device):
    label = '{'
  
    label = label + '{'
    for ifd in device.interfaces: 
        if type(ifd) is InterfaceDefinition: 
            if ifd.role == 'uplink':
                if ifd.peer is not None:
                    label += '<'+ifd.id+'>'+ ifd.name+'|'
                
    if label.endswith('|'):
        label = label[:-1]
        label += '}|{' + device.name + '}|{'
    else:
        label += device.name + '}|{'
        
    for ifd in device.interfaces:
        if type(ifd) is InterfaceDefinition:
            if ifd.role == 'downlink':
                if ifd.peer is not None:
                    label += '<'+ifd.id+'>'+ ifd.name+'|'
                
    if label.endswith('|'):
        label = label[:-1]
        label += '}}'
    else:
        label = label[:-2]
        label += '}'
        
    return label

def createDeviceInGraph(labelStrs, device, testDeviceLabel):
    testDeviceLabel.add_node(pydot.Node(device.id, shape='record', label= labelStrs))

def createLabelForLinks(device):
    links = {}
                  
    for ifd in device.interfaces:
        if type(ifd) is InterfaceDefinition:
            if ifd.role == 'downlink':
                if ifd.peer is not None: 
                    interface =  '"'+ device.id +'"'+ ':' +'"'+ ifd.id +'"'
                    peer = '"'+ifd.peer.device.id +'"' + ':' +'"'+ ifd.peer.id +'"'
                    links[interface] = peer
                   
    return links

def createLinksInGraph(links, linksInTopology, color):
    for interface, peer in links.iteritems():
        linksInTopology.add_edge(pydot.Edge(interface, peer,color=color))
        

       
    







































