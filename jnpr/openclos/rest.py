'''
Created on Sep 2, 2014

@author: moloyc
'''

import os
import logging
import bottle
from sqlalchemy.orm import exc

import copy
import json
import util
from model import Pod, Device
from dao import Dao
from bottle import request
from report import ResourceAllocationReport

moduleName = 'rest'
logging.basicConfig()
logger = logging.getLogger(moduleName)
logger.setLevel(logging.DEBUG)

webServerRoot = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'out')
junosImageRoot = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'conf', 'ztp')

class ResourceLink():
    def __init__(self, baseUrl, path):
        self.baseUrl = baseUrl
        self.path = path
    def toDict(self):
        return {'href': self.baseUrl + self.path}

class RestServer():
    def __init__(self, conf = {}):
        if any(conf) == False:
            self.conf = util.loadConfig()
            logger.setLevel(logging.getLevelName(self.conf['logLevel'][moduleName]))
            global webServerRoot
            webServerRoot = self.conf['outputDir']
        else:
            self.conf = conf
        self.dao = Dao(self.conf)

        if 'httpServer' in self.conf and 'ipAddr' in self.conf['httpServer'] and self.conf['httpServer']['ipAddr'] is not None:
            self.host = self.conf['httpServer']['ipAddr']
        else:
            self.host = 'localhost'

        if 'httpServer' in self.conf and 'port' in self.conf['httpServer']:
            self.port = self.conf['httpServer']['port']
        else:
            self.port = 8080
        self.baseUrl = 'http://%s:%d' % (self.host, self.port)
        
    def initRest(self):
        self.addRoutes(self.baseUrl)
        self.app = bottle.app()

    def start(self):
        logger.info('REST server started at %s:%d' % (self.host, self.port))
        bottle.run(self.app, host=self.host, port=self.port)

    def addRoutes(self, baseUrl):
        self.indexLinks = []
        bottle.route('/openclos', 'GET', self.getIndex)
        bottle.route('/openclos/ip-fabrics', 'GET', self.getIPFabrics)
        bottle.route('/<junosImageName>', 'GET', self.getJunosImage)
        bottle.route('/pods/<podName>/devices/<deviceName>/config', 'GET', self.getDeviceConfig)
        # TODO: the resource lookup should hierarchical
        # /pods/*
        # /pods/{podName}/devices/*
        # /pods/{podName}/devices/{deviceName}/config
        self.createLinkForConfigs()

    def createLinkForConfigs(self):
        pods = self.dao.getAll(Pod)
        for pod in pods:
            for device in pod.devices:
                self.indexLinks.append(ResourceLink(self.baseUrl, 
                    '/pods/%s/devices/%s/config' % (pod.name, device.name)))
    
    def getIndex(self):
        jsonLinks = []
        for link in self.indexLinks:
            jsonLinks.append({'link': link.toDict()})

        jsonBody = \
            {'href': self.baseUrl,
             'links': jsonLinks
             }

        return jsonBody
    
    def getReport(self):
        report = ResourceAllocationReport(self.conf, self.dao)
        return report
    
    def getIPFabrics(self):
        url = request.url
        #print strUri
        ipFabrics = {}
        listOfIpFbarics = []
        ipFabrics['uri'] = url
        report = self.getReport()
        IpFbarics = report.getPods()
        for i in range(len(IpFbarics)):
            ipFabric = {}
            ipFabric['uri'] = url +'/'+ IpFbarics[i]['id']
            ipFabric['id'] = IpFbarics[i]['id']
            ipFabric['name'] = IpFbarics[i]['name']
            ipFabric['spineDeviceType'] = IpFbarics[i]['spineDeviceType']
            ipFabric['spineCount'] = IpFbarics[i]['spineCount']
            ipFabric['leafDeviceType'] = IpFbarics[i]['leafDeviceType']
            ipFabric['leafCount'] = IpFbarics[i]['leafCount']
            listOfIpFbarics.append(ipFabric)
        ipFabrics['ipFabric'] =  listOfIpFbarics
        ipFabrics['total'] = len(listOfIpFbarics)
        return ipFabrics 
    
    def getDeviceConfig(self, podName, deviceName):

        if not self.isDeviceExists(podName, deviceName):
            raise bottle.HTTPError(404, "No device found with pod name: '%s', device name: '%s'" % (podName, deviceName))
        
        fileName = os.path.join(podName, deviceName+'.conf')
        logger.debug('webServerRoot: %s, fileName: %s, exists: %s' % (webServerRoot, fileName, os.path.exists(os.path.join(webServerRoot, fileName))))

        config = bottle.static_file(fileName, root=webServerRoot)
        if isinstance(config, bottle.HTTPError):
            logger.debug("Device exists but no config found. Pod name: '%s', device name: '%s'" % (podName, deviceName))
            raise bottle.HTTPError(404, "Device exists but no config found, probably fabric script is not ran. Pod name: '%s', device name: '%s'" % (podName, deviceName))
        return config

    def isDeviceExists(self, podName, deviceName):
        try:
            self.dao.Session.query(Device).join(Pod).filter(Device.name == deviceName).filter(Pod.name == podName).one()
            return True
        except (exc.NoResultFound):
            logger.debug("No device found with pod name: '%s', device name: '%s'" % (podName, deviceName))
            return False

    def getJunosImage(self, junosImageName):

        fileName = os.path.join(junosImageRoot, junosImageName)
        logger.debug('junosImageRoot: %s, image: %s, exists: %s' % (junosImageRoot, junosImageName, os.path.exists(fileName)))

        config = bottle.static_file(junosImageName, root=junosImageRoot)
        if isinstance(config, bottle.HTTPError):
            logger.debug("Junos image file found. name: '%s'" % (junosImageName))
            raise bottle.HTTPError(404, "Junos image file not found. name: '%s'" % (junosImageName))
        return config
        
if __name__ == '__main__':
    restServer = RestServer()
    restServer.initRest()
    restServer.start()