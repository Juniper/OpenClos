'''
Created on Sep 2, 2014

@author: moloyc
'''

import os
import logging
import bottle
from sqlalchemy.orm import exc, Session
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
        bottle.route('/openclos/ip-fabrics/<ipFabricId>/devices/<deviceId>/config', 'GET', self.getDeviceConfig)
        bottle.route('/openclos/ip-fabrics/<ipFabricId>', 'GET', self.getIpFabric)
        bottle.route('/openclos/ip-fabrics/<ipFabricId>/cabling-plan', 'GET', self.getCablingPlan)
        bottle.route('/openclos/ip-fabrics/<ipFabricId>/devices', 'GET', self.getDevices)
        bottle.route('/openclos/ip-fabrics/<ipFabricId>/devices/<deviceId>', 'GET', self.getDevice)

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
                    '/openclos/ip-fabrics/%s/devices/%s/config' % (pod.id, device.id)))
    
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
        report = self.getReport()
        ipFabric = report.getIpFabric(ipFabricId)
        if ipFabric is not None:
            devices = ipFabric.devices
            
            #Detaching the object from session
            session = Session.object_session(ipFabric)
            session.expunge(ipFabric)
            ipFabric.__dict__.pop('_sa_instance_state')
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
    
    def getCablingPlan(self, ipFabricId):
        
        report = self.getReport()
        ipFabric = report.getIpFabric(ipFabricId)
        logger.debug('Fabric name: %s' % (ipFabric.name))
        header =  request.get_header('Accept')
        logger.debug('Accept header: %s' % (header))
        if ipFabric is not None:
            ipFabricName = ipFabric.name
            if header == 'application/json':
                fileName = os.path.join(ipFabricName, "cablingPlan.json")
                logger.debug('webServerRoot: %s, fileName: %s, exists: %s' % (webServerRoot, fileName, os.path.exists(os.path.join(webServerRoot, fileName))))
            else:
                fileName = os.path.join(ipFabricName, 'cablingPlan.dot')
                logger.debug('webServerRoot: %s, fileName: %s, exists: %s' % (webServerRoot, fileName, os.path.exists(os.path.join(webServerRoot, fileName))))
            logger.debug('Cabling file name: %s' % (fileName))                

            cablingPlan = bottle.static_file(fileName, root=webServerRoot)
            if isinstance(cablingPlan, bottle.HTTPError):
                logger.debug("Pod exists but no CablingPlan found. Pod name: '%s" % (ipFabricName))
                raise bottle.HTTPError(404, "Pod exists but no CablingPlan found. Pod name: '%s " % (ipFabricName))
            return cablingPlan
        else:
            logger.debug("IpFabric with id: %s not found" % (ipFabricId))
            raise bottle.HTTPError(404, "IpFabric with id: %s not found" % (ipFabricId))
        
    def getDevices(self, ipFabricId):
        
        devices = {}
        listOfDevices = []
        report = self.getReport()
        ipFabric = report.getIpFabric(ipFabricId)
        if ipFabric is not None:
            #devicesObject = ipFabric.devices
            
            session = Session.object_session(ipFabric)
            for device in ipFabric.devices:
                session.expunge(device)
                device.__dict__.pop('_sa_instance_state')
                device.__dict__.pop('username')
                device.__dict__.pop('family')
                device.__dict__.pop('asn')
                device.__dict__.pop('pwd')
                device.__dict__.pop('pod_id')
                device.__dict__['uri'] = bottle.request.url + '/' +device.id
                listOfDevices.append(device.__dict__)
            devices['device'] = listOfDevices
            devices['uri'] = bottle.request.url
            devices['total'] = len(ipFabric.devices)
            return {'devices' : devices}
        else:
            logger.debug("IpFabric with id: %s not found" % (ipFabricId))
            raise bottle.HTTPError(404, "IpFabric with id: %s not found" % (ipFabricId))
        
    def getDevice(self, ipFabricId, deviceId):
        
        device = self.isDeviceExists(ipFabricId, deviceId)
        #ipFabricUri is constructed from url
        url = bottle.request.url
        uri = url.split("/")
        uri.pop()
        uri.pop()
        ipFbaricUri = "/".join(uri)
               
        if device is not None:
            
            session = Session.object_session(device)
            session.expunge(device)
            device.__dict__.pop('_sa_instance_state')
            device.__dict__.pop('pod_id')
            device.__dict__['uri'] = bottle.request.url
            device.__dict__['pod'] = {'uri': ipFbaricUri }
         
            return {'device': device.__dict__}
        else:
            logger.debug("device with id: %s not found" % (deviceId))
            raise bottle.HTTPError(404, "device with id: %s not found" % (deviceId))  
        
         
    def getDeviceConfig(self, ipFabricId, deviceId):
        
        device = self.isDeviceExists(ipFabricId, deviceId)
        pod = device.pod
        
        if device is None:
            raise bottle.HTTPError(404, "No device found with ipFabricId: '%s', deviceId: '%s'" % (ipFabricId, deviceId))
        
        fileName = os.path.join(pod.name, device.name+'.conf')
        logger.debug('webServerRoot: %s, fileName: %s, exists: %s' % (webServerRoot, fileName, os.path.exists(os.path.join(webServerRoot, fileName))))

        config = bottle.static_file(fileName, root=webServerRoot)
        if isinstance(config, bottle.HTTPError):
            logger.debug("Device exists but no config found. ipFabricId: '%s', deviceId: '%s'" % (ipFabricId, deviceId))
            raise bottle.HTTPError(404, "Device exists but no config found, probably fabric script is not ran. ipFabricId: '%s', deviceId: '%s'" % (ipFabricId, deviceId))
        return config
    

    def isDeviceExists(self, ipFabricId, deviceId):
        try:
            device = self.dao.Session.query(Device).join(Pod).filter(Device.id == deviceId).filter(Pod.id == ipFabricId).one()
            return device
        except (exc.NoResultFound):
            logger.debug("No device found with IpFabricId: '%s', deviceId: '%s'" % (ipFabricId, deviceId))
            raise bottle.HTTPError(404, "No device found with ipFabricId: '%s', deviceId: '%s'" % (ipFabricId, deviceId))

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