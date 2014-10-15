'''
Created on Sep 2, 2014

@author: moloyc
'''

import os
import logging
import bottle
from sqlalchemy.orm import exc, Session
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
        bottle.route('/openclos/ip-fabrics', 'GET', self.getIpFabrics)
        bottle.route('/<junosImageName>', 'GET', self.getJunosImage)
        bottle.route('/pods/<podName>/devices/<deviceName>/config', 'GET', self.getDeviceConfig)
        bottle.route('/openclos/ip-fabrics/<ipFabricId>', 'GET', self.getIpFabric)

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
    
    def getIpFabrics(self):
        url = request.url
        ipFabricsData = {}
        listOfIpFbarics = []
        report = self.getReport()
        IpFabrics = report.getPods()
        logger.debug("count of ipFabrics: %d", len(IpFabrics))
        if not IpFabrics :   
            logger.debug("There are no ipFabrics in the system ")
        
        for i in range(len(IpFabrics)):
            ipFabric = {}
            ipFabric['uri'] = url +'/'+ IpFabrics[i]['id']
            ipFabric['id'] = IpFabrics[i]['id']
            ipFabric['name'] = IpFabrics[i]['name']
            ipFabric['spineDeviceType'] = IpFabrics[i]['spineDeviceType']
            ipFabric['spineCount'] = IpFabrics[i]['spineCount']
            ipFabric['leafDeviceType'] = IpFabrics[i]['leafDeviceType']
            ipFabric['leafCount'] = IpFabrics[i]['leafCount']
            listOfIpFbarics.append(ipFabric)
        ipFabricsData['ipFabric'] =  listOfIpFbarics
        ipFabricsData['total'] = len(listOfIpFbarics)
        ipFabricsData['uri'] = url 
        return {'ipFabrics' : ipFabricsData}
    
    def getIpFabric(self, ipFabricId):
        tmp = bottle.request.url
        report = ResourceAllocationReport(dao = self.dao)
        ipFabric = report.getIpFabric(ipFabricId)
        if ipFabric is not None:
            devices = ipFabric.devices

            session = Session.object_session(ipFabric)
            session.expunge(ipFabric)
            ipFabric.__dict__.pop('_sa_instance_state')
            ipFabric.__dict__.pop('devices')
            ipFabric.__dict__.pop('spineJunosImage')
            ipFabric.__dict__.pop('leafJunosImage')
            ipFabric.__dict__['devices'] = {'uri': bottle.request.url + '/devices', 'total':len(devices)}
            ipFabric.__dict__['cablingPlan'] = {'uri': bottle.request.url + '/cabling-plan'}
            logger.debug('getIpFabric: %s' % (ipFabricId))
            #return json.dumps(ipFabric.__dict__)
            return {'ipFabric': ipFabric.__dict__}
        else:
            logger.debug("IpFabric with id: %s not found" % (ipFabricId))
            raise bottle.HTTPError(404, "IpFabric with id: %s not found" % (ipFabricId))
    
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