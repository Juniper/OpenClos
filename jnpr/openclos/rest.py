'''
Created on Sep 2, 2014

@author: moloyc
'''

import os
import logging
import bottle
from sqlalchemy.orm import exc, Session
import StringIO
import zipfile

import util
from model import Pod, Device
from dao import Dao
from report import ResourceAllocationReport
from l3Clos import L3ClosMediation
from ztp import ZtpServer

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

        # GET APIs
        bottle.route('/', 'GET', self.getIndex)
        bottle.route('/openclos', 'GET', self.getIndex)
        bottle.route('/openclos/ip-fabrics', 'GET', self.getIpFabrics)
        bottle.route('/openclos/images/<junosImageName>', 'GET', self.getJunosImage)
        bottle.route('/openclos/ip-fabrics/<ipFabricId>', 'GET', self.getIpFabric)
        bottle.route('/openclos/ip-fabrics/<ipFabricId>/cabling-plan', 'GET', self.getCablingPlan)
        bottle.route('/openclos/ip-fabrics/<ipFabricId>/ztp-configuration','GET', self.getZtpConfig)
        bottle.route('/openclos/ip-fabrics/<ipFabricId>/device-configuration', 'GET', self.getDeviceConfigsInZip)
        bottle.route('/openclos/ip-fabrics/<ipFabricId>/devices', 'GET', self.getDevices)
        bottle.route('/openclos/ip-fabrics/<ipFabricId>/devices/<deviceId>', 'GET', self.getDevice)
        bottle.route('/openclos/ip-fabrics/<ipFabricId>/devices/<deviceId>/config', 'GET', self.getDeviceConfig)

        # POST/PUT APIs
        bottle.route('/openclos/ip-fabrics', 'POST', self.createIpFabric)
        bottle.route('/openclos/ip-fabrics/<ipFabricId>/cabling-plan', 'POST', self.createCablingPlan)
        bottle.route('/openclos/ip-fabrics/<ipFabricId>/device-configuration', 'POST', self.createDeviceConfiguration)
        bottle.route('/openclos/ip-fabrics/<ipFabricId>/ztp-configuration', 'POST', self.createZtpConfiguration)
        bottle.route('/openclos/ip-fabrics/<ipFabricId>', 'PUT', self.reconfigIpFabric)
        bottle.route('/openclos/conf/', 'PUT', self.setOpenClosConfigParams)

        # DELETE APIs
        bottle.route('/openclos/ip-fabrics/<ipFabricId>', 'DELETE', self.deleteIpFabric)

        self.createLinkForConfigs()

    def createLinkForConfigs(self):
        # index page should show all top level URLs
        # users whould be able to drill down through navigation
        self.indexLinks.append(ResourceLink(self.baseUrl, '/openclos/ip-fabrics'))
    
    def getIndex(self):
        if 'openclos' not in bottle.request.url:
            bottle.redirect(bottle.request.url + 'openclos')

        jsonLinks = []
        for link in self.indexLinks:
            jsonLinks.append({'link': link.toDict()})

        jsonBody = \
            {'href': bottle.request.url,
             'links': jsonLinks
             }

        return jsonBody
    
    def getReport(self):
        report = ResourceAllocationReport(self.conf, self.dao)
        return report
    
    def getIpFabrics(self):
        
        url = bottle.request.url
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
        report = ResourceAllocationReport(dao = self.dao)
        
        ipFabric = report.getIpFabric(ipFabricId)
        if ipFabric is not None:
            devices = ipFabric.devices
            
            #Detaching the object from session
            session = Session.object_session(ipFabric)
            session.expunge(ipFabric)
            ipFabric.__dict__.pop('_sa_instance_state')
            ipFabric.__dict__.pop('inventoryData')
            ipFabric.__dict__['devices'] = {'uri': bottle.request.url + '/devices', 'total':len(devices)}
            ipFabric.__dict__['cablingPlan'] = {'uri': bottle.request.url + '/cabling-plan'}
            ipFabric.__dict__['deviceConfiguration'] = {'uri': bottle.request.url + '/device-configuration'}
            ipFabric.__dict__['ztpConfiguration'] = {'uri': bottle.request.url + '/ztp-configuration'}

            logger.debug('getIpFabric: %s' % (ipFabricId))
            #return json.dumps(ipFabric.__dict__)
         
            return {'ipFabric': ipFabric.__dict__}
        else:
            logger.debug("IpFabric with id: %s not found" % (ipFabricId))
            raise bottle.HTTPError(404, "IpFabric with id: %s not found" % (ipFabricId))
    
    def getCablingPlan(self, ipFabricId):
        
        header =  bottle.request.get_header('Accept')
        logger.debug('Accept header: %s' % (header))

        report = self.getReport()
        ipFabric = report.getIpFabric(ipFabricId)
        if ipFabric is not None:
            logger.debug('IpFabric name: %s' % (ipFabric.name))
            ipFabricFolder = ipFabric.id + '-' + ipFabric.name
            if header == 'application/json':
                fileName = os.path.join(ipFabricFolder, "cablingPlan.json")
                logger.debug('webServerRoot: %s, fileName: %s, exists: %s' % (webServerRoot, fileName, os.path.exists(os.path.join(webServerRoot, fileName))))
            else:
                fileName = os.path.join(ipFabricFolder, 'cablingPlan.dot')
                logger.debug('webServerRoot: %s, fileName: %s, exists: %s' % (webServerRoot, fileName, os.path.exists(os.path.join(webServerRoot, fileName))))
            logger.debug('Cabling file name: %s' % (fileName))                

            cablingPlan = bottle.static_file(fileName, root=webServerRoot)
            if isinstance(cablingPlan, bottle.HTTPError):
                logger.debug("IpFabric exists but no CablingPlan found. IpFabric: '%s" % (ipFabricFolder))
                raise bottle.HTTPError(404, "IpFabric exists but no CablingPlan found. IpFabric: '%s " % (ipFabricFolder))
            return cablingPlan
        else:
            logger.debug("IpFabric with id: %s not found" % (ipFabricId))
            raise bottle.HTTPError(404, "IpFabric with id: %s not found" % (ipFabricId))

    def getDeviceConfigsInZip(self, ipFabricId):
        ipFabric = self.getReport().getIpFabric(ipFabricId)
        if ipFabric is None:
            logger.debug("IpFabric with id: %s not found" % (ipFabricId))
            raise bottle.HTTPError(404, "IpFabric with id: %s not found" % (ipFabricId))
        
        logger.debug('IpFabric name: %s' % (ipFabric.name))
        ipFabricFolderName = ipFabric.id + '-' + ipFabric.name
        ipFabricFolderWithPath = os.path.join(webServerRoot, ipFabricFolderName)
        if os.path.exists(ipFabricFolderWithPath):
            bottle.response.headers['Content-Type'] = 'application/zip'
            return self.createZipArchive(ipFabric, ipFabricFolderWithPath)
        else:
            raise bottle.HTTPError(404, "IpFabric exists but no folder with configs. ipFabricFolderWithPath: '%s " % (ipFabricFolderWithPath))

    def createZipArchive(self, ipFabric, ipFabricFolder):

        buff = StringIO.StringIO()
        zipArchive = zipfile.ZipFile(buff, mode='w')

        for device in ipFabric.devices:
            fileName = device.id + '-' + device.name + '.conf'
            fileNameWithPath = os.path.join(ipFabricFolder, device.id + '-' + device.name + '.conf')
            logger.debug('fileName: %s, exists: %s' % (fileNameWithPath, os.path.exists(os.path.join(webServerRoot, fileNameWithPath))))
            with open (fileNameWithPath, "r") as confFile:
                config = confFile.read()
            zipArchive.writestr(fileName, config)
        
        zipArchive.close()
        logger.debug('zip file content:\n' + str(zipArchive.namelist()))
        return buff.getvalue()

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
            device.__dict__['config'] = {'uri': bottle.request.url + '/config' }
         
            return {'device': device.__dict__}
        else:
            logger.debug("device with id: %s not found" % (deviceId))
            raise bottle.HTTPError(404, "device with id: %s not found" % (deviceId))  
        
         
    def getDeviceConfig(self, ipFabricId, deviceId):
        
        device = self.isDeviceExists(ipFabricId, deviceId)
        pod = device.pod
        
        if device is None:
            raise bottle.HTTPError(404, "No device found with ipFabricId: '%s', deviceId: '%s'" % (ipFabricId, deviceId))
        
        fileName = os.path.join(pod.id+'-'+pod.name, device.id + '-' + device.name + '.conf')
        logger.debug('webServerRoot: %s, fileName: %s, exists: %s' % (webServerRoot, fileName, os.path.exists(os.path.join(webServerRoot, fileName))))

        config = bottle.static_file(fileName, root=webServerRoot)
        if isinstance(config, bottle.HTTPError):
            logger.debug("Device exists but no config found. ipFabricId: '%s', deviceId: '%s'" % (ipFabricId, deviceId))
            raise bottle.HTTPError(404, "Device exists but no config found, probably fabric script is not ran. ipFabricId: '%s', deviceId: '%s'" % (ipFabricId, deviceId))
        return config
    
    def getZtpConfig(self, ipFabricId):
        
        report = self.getReport()
        ipFabric = report.getIpFabric(ipFabricId)
        if ipFabric is not None:
            logger.debug('Fabric name: %s' % (ipFabric.name))
            
            ipFabricFolder = ipFabric.id + '-' + ipFabric.name
            fileName = os.path.join(ipFabricFolder, "dhcpd.conf")
            logger.debug('webServerRoot: %s, fileName: %s, exists: %s' % (webServerRoot, fileName, os.path.exists(os.path.join(webServerRoot, fileName))))         
            ztpConf = bottle.static_file(fileName, root=webServerRoot)
            if isinstance(ztpConf, bottle.HTTPError):
                logger.debug("Pod exists but no ztp Config found. Pod name: '%s" % (ipFabric.name))
                raise bottle.HTTPError(404, "Pod exists but no ztp Config found. Pod name: '%s " % (ipFabric.name))
            return ztpConf
        else:
            logger.debug("IpFabric with id: %s not found" % (ipFabricId))
            raise bottle.HTTPError(404, "IpFabric with id: %s not found" % (ipFabricId))
    

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
        
        
    def createIpFabric(self):  
        l3ClosMediation = L3ClosMediation(self.conf)
        try:
            pod = bottle.request.json['ipFabric']
            if pod is None:
                raise bottle.HTTPError(400, "Invalid value in POST body.")
        except ValueError:
            raise bottle.HTTPError(400, "POST body can not be empty.")

        ipFabric = self.getPodFromDict(pod)
        fabricDevices = self.getDevDictFromDict(pod)
        fabricId =  l3ClosMediation.createPod(ipFabric['name'], ipFabric, fabricDevices).id
        return self.getIpFabrics(fabricId)
        
    def createCablingPlan(self, ipFabricId):
        try:
            if L3ClosMediation(self.conf).createCablingPlan(ipFabricId) is True:
                return bottle.HTTPResponse(status=200)
        except ValueError:
            raise bottle.HTTPError(404, "Fabric with id[%s] not found" % (ipFabricId))

    def createDeviceConfiguration(self, ipFabricId):
        try:
            if L3ClosMediation(self.conf).createDeviceConfig(ipFabricId) is True:
                return bottle.HTTPResponse(status=200)
        except ValueError:
            raise bottle.HTTPError(404, "Fabric with id[%s] not found" % (ipFabricId))
            
    def createZtpConfiguration(self, ipFabric):
        ZtpServer.createPodSpecificDhcpConfFile(self, ipFabric)
        return bottle.HTTPResponse(status=200)
    
    def reconfigIpFabric(self, ipFabricId):
        l3ClosMediation = L3ClosMediation(self.conf)

        try:
            inPod = bottle.request.json['ipFabric']
            if inPod is None:
                raise bottle.HTTPError(404, "Invalid value in POST body.")
        except ValueError:
            raise bottle.HTTPError(404, "POST body can not be empty.")

        ipFabric = self.getPodFromDict(inPod)
        ipFabric['id'] = ipFabricId
        ipFabric['uri'] = bottle.request.url
        fabricDevices = self.getDevDictFromDict(inPod)
        # Pass the ipFabric and fabricDevices dictionaries to config/update API, then return
        l3ClosMediation.updatePod(ipFabricId, ipFabric, fabricDevices)
        return {'ipFabric': ResourceAllocationReport(dao = self.dao).getIpFabric(ipFabric['id']).__dict__}
    
    def setOpenClosConfigParams(self):
        return bottle.HTTPResponse(status=200)
    
    def setNdConfigParams(self):
        return bottle.HTTPResponse(status=200)

    def deleteIpFabric(self, ipFabricId):
        report = ResourceAllocationReport(dao = self.dao)
        ipFabric = report.getIpFabric(ipFabricId)
        if ipFabric is not None:
            report.dao.deleteObject(ipFabric)
            logger.debug("IpFabric with id: %s deleted" % (ipFabricId))
        else:
            logger.debug("IpFabric with id: %s not found" % (ipFabricId))
            raise bottle.HTTPError(404, "IpFabric with id: %s not found" % (ipFabricId))
        return bottle.HTTPResponse(status=204)

    def getPodFromDict(self, podDict):
        ipFabric = {}
        '''
        # Need to revisit later on to make thing works as below.
        podDict.pop('devices')
        ipFabric = Pod(**inPod)
        '''
        if podDict is None:
            logger.debug("Invalid empty podDict")
            raise bottle.HTTPError(400, "Invalid value in POST/PUT body.")
        ipFabric['name'] = podDict.get('name')
        ipFabric['fabricDeviceType'] = podDict.get('fabricDeviceType')
        ipFabric['fabricDeviceCount'] = podDict.get('fabricDeviceCount')
        ipFabric['spineCount'] = podDict.get('spineCount')
        ipFabric['spineDeviceType'] = podDict.get('spineDeviceType')
        ipFabric['leafCount'] = podDict.get('leafCount')
        ipFabric['leafDeviceType'] = podDict.get('leafDeviceType')
        ipFabric['interConnectPrefix'] = podDict.get('interConnectPrefix')
        ipFabric['vlanPrefix'] = podDict.get('vlanPrefix')
        ipFabric['loopbackPrefix'] = podDict.get('loopbackPrefix')
        ipFabric['spineAS'] = podDict.get('spineAS')
        ipFabric['leafAS'] = podDict.get('leafAS')
        ipFabric['topologyType'] = podDict.get('topologyType')
        ipFabric['outOfBandAddressList'] = podDict.get('outOfBandAddressList')
        ipFabric['managementPrefix'] = podDict.get('managementPrefix')
        ipFabric['description'] = podDict.get('description')

        return ipFabric


    def getDevDictFromDict(self, podDict):
        if podDict is not None:
            devices = podDict.get('devices')
        else:
            raise bottle.HTTPError(400, "Invalid value in POST body.")

        fabricDevices = {}
        spines = []
        leaves = []
        for device in devices:
            temp = {}
            temp['name'] = device.get('name')
            temp['macAddress'] = device.get('macAddress')
            temp['role'] = device.get('role')
            temp['username'] = device.get('username')
            temp['password'] = device.get('username')
            if temp['role'] == 'spine':
                spines.append(temp)
            elif temp['role'] == 'leaf':
                leaves.append(temp)
            else:
                raise bottle.HTTPError(422, "Unexpected role value in device inventory list")
            fabricDevices['spines'] = spines
            fabricDevices['leafs'] = leaves

        return fabricDevices

if __name__ == '__main__':
    restServer = RestServer()
    restServer.initRest()
    restServer.start()
