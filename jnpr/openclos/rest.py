'''
Created on Sep 2, 2014

@author: moloyc
'''

import os
import bottle
from sqlalchemy.orm import exc
import StringIO
import zipfile
import traceback
import json
import util
import logging

from bottle import error, request, response, PluginError
from exception import RestError
from model import Pod, Device
from dao import Dao
from report import ResourceAllocationReport, L2Report, L3Report
from l3Clos import L3ClosMediation
from ztp import ZtpServer
from propLoader import OpenClosProperty, DeviceSku

moduleName = 'rest'
logger = None

webServerRoot = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'out')
junosImageRoot = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'conf', 'ztp')

def loggingPlugin(callback):
    def wrapper(*args, **kwargs):
        msg = '"{} {} {}"'.format(request.method, request.path,
                                        request.environ.get('SERVER_PROTOCOL', ''))
        
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug('%s REQUEST: %s' % (msg, request._get_body_string()))
        else:
            logger.info('%s REQUEST:' % (msg))
        
        try:
            responseBody = callback(*args, **kwargs)
        except bottle.HTTPError as exc:
            logger.error('HTTPError: status: %s, body: %s, exception: %s' % (exc.status, exc.body, exc.exception))
            raise
        except Exception as exc:
            logger.error('Unknown error: %s' % (exc))
            logger.info('StackTrace: %s' % (traceback.format_exc()))
            raise
       
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug('%s RESPONSE %s: %s' % (msg, response.status_code, responseBody))
        else:
            logger.info('%s RESPONSE %s:' % (msg, response.status_code))
            
        return responseBody
    return wrapper


class OpenclosDbSessionPlugin(object):
    name = 'OpenclosDbSessionPlugin'

    def __init__(self, daoClass = Dao):
        self.__dao = daoClass.getInstance()

    def setup(self, app):
        ''' Make sure that other installed plugins don't affect the same keyword argument.'''
        for plugin in app.plugins:
            if not isinstance(plugin, OpenclosDbSessionPlugin): 
                continue
            else:
                raise PluginError("Found another OpenclosDbSessionPlugin already installed")

    def apply(self, callback, context):
        def wrapper(*args, **kwargs):
            if request.method == 'POST' or request.method == 'PUT' or request.method == 'DELETE':
                with self.__dao.getReadWriteSession() as dbSession:
                    kwargs['dbSession'] = dbSession
                    responseBody = callback(*args, **kwargs)
            else:
                with self.__dao.getReadSession() as dbSession:
                    kwargs['dbSession'] = dbSession
                    responseBody = callback(*args, **kwargs)
            return responseBody

        # Replace the route callback with the wrapped one.
        return wrapper
    
class ResourceLink():
    def __init__(self, baseUrl, path):
        self.baseUrl = baseUrl
        self.path = path
    def toDict(self):
        return {'href': self.baseUrl + self.path}

class RestServer():
    def __init__(self, conf = {}, daoClass = Dao):
        global logger
        if any(conf) == False:
            self.__conf = OpenClosProperty(appName = moduleName).getProperties()

            global webServerRoot
            webServerRoot = self.__conf['outputDir']
        else:
            self.__conf = conf
        logger = logging.getLogger(moduleName)
        
        self.__daoClass = daoClass
        self.__dao = daoClass.getInstance()
        self.openclosDbSessionPlugin = OpenclosDbSessionPlugin(daoClass)
        
        if 'httpServer' in self.__conf and 'ipAddr' in self.__conf['httpServer'] and self.__conf['httpServer']['ipAddr'] is not None:
            self.host = self.__conf['httpServer']['ipAddr']
        else:
            self.host = 'localhost'

        if 'httpServer' in self.__conf and 'port' in self.__conf['httpServer']:
            self.port = self.__conf['httpServer']['port']
        else:
            self.port = 8080
        self.baseUrl = 'http://%s:%d' % (self.host, self.port)

        self.report = ResourceAllocationReport(self.__conf, daoClass)
        # Create a single instance of l2Report as it holds thread-pool
        # for device connection. Don't create l2Report multiple times 
        self.l2Report = L2Report(self.__conf, daoClass)
        # Create a single instance of l3Report as it holds thread-pool
        # for device connection. Don't create l3Report multiple times 
        self.l3Report = L3Report(self.__conf, daoClass)
        self.deviceSku = DeviceSku()
        
    def initRest(self):
        self.addRoutes(self.baseUrl)
        self.app = bottle.app()
        self.app.install(loggingPlugin)
        self.app.install(self.openclosDbSessionPlugin)
        logger.info('RestServer initRest() done')

    def _reset(self):
        """
        Resets the state of the rest server and application
        Used for Test only
        """
        self.app.uninstall(loggingPlugin)
        self.app.uninstall(OpenclosDbSessionPlugin)


    def start(self):
        logger.info('REST server starting at %s:%d' % (self.host, self.port))
        debugRest = False
        if logger.isEnabledFor(logging.DEBUG):
            debugRest = True

        if util.isSqliteUsed(self.__conf):
            bottle.run(self.app, host=self.host, port=self.port, debug=debugRest)
        else:
            bottle.run(self.app, host=self.host, port=self.port, debug=debugRest, server='paste')


    @staticmethod
    @error(400)
    def error400(error):
        bottle.response.headers['Content-Type'] = 'application/json'
        if error.exception is not None:
            return json.dumps({'errorCode': error.exception.errorId , 'errorMessage' : error.exception.errorMessage})
        else:
            return json.dumps({'errorCode': 0, 'errorMessage' : 'A generic error occurred'})
        
    def addRoutes(self, baseUrl):
        self.indexLinks = []

        # GET APIs
        bottle.route('/', 'GET', self.getIndex)
        bottle.route('/openclos', 'GET', self.getIndex)
        bottle.route('/openclos/conf', 'GET', self.getOpenClosConfigParams)
        bottle.route('/openclos/ip-fabrics', 'GET', self.getIpFabrics)
        bottle.route('/openclos/images/<junosImageName>', 'GET', self.getJunosImage)
        bottle.route('/openclos/ip-fabrics/<ipFabricId>', 'GET', self.getIpFabric)
        bottle.route('/openclos/ip-fabrics/<ipFabricId>/cabling-plan', 'GET', self.getCablingPlan)
        bottle.route('/openclos/ip-fabrics/<ipFabricId>/ztp-configuration','GET', self.getZtpConfig)
        bottle.route('/openclos/ip-fabrics/<ipFabricId>/device-configuration', 'GET', self.getDeviceConfigsInZip)
        bottle.route('/openclos/ip-fabrics/<ipFabricId>/leaf-generic-configurations/<deviceModel>', 'GET', self.getLeafGenericConfiguration)
        bottle.route('/openclos/ip-fabrics/<ipFabricId>/l2-report', 'GET', self.getL2Report)
        bottle.route('/openclos/ip-fabrics/<ipFabricId>/l3-report', 'GET', self.getL3Report)
        bottle.route('/openclos/ip-fabrics/<ipFabricId>/devices', 'GET', self.getDevices)
        bottle.route('/openclos/ip-fabrics/<ipFabricId>/devices/<deviceId>', 'GET', self.getDevice)
        bottle.route('/openclos/ip-fabrics/<ipFabricId>/devices/<deviceId>/config', 'GET', self.getDeviceConfig)

        # POST/PUT APIs
        bottle.route('/openclos/ip-fabrics', 'POST', self.createIpFabric)
        bottle.route('/openclos/ip-fabrics/<ipFabricId>/cabling-plan', 'PUT', self.createCablingPlan)
        bottle.route('/openclos/ip-fabrics/<ipFabricId>/device-configuration', 'PUT', self.createDeviceConfiguration)
        bottle.route('/openclos/ip-fabrics/<ipFabricId>/ztp-configuration', 'PUT', self.createZtpConfiguration)
        bottle.route('/openclos/ip-fabrics/<ipFabricId>', 'PUT', self.reconfigIpFabric)
        bottle.route('/openclos/conf/', 'PUT', self.setOpenClosConfigParams)

        # DELETE APIs
        bottle.route('/openclos/ip-fabrics/<ipFabricId>', 'DELETE', self.deleteIpFabric)

        self.createLinkForConfigs()

    def createLinkForConfigs(self):
        # index page should show all top level URLs
        # users whould be able to drill down through navigation
        self.indexLinks.append(ResourceLink(self.baseUrl, '/openclos/ip-fabrics'))
        self.indexLinks.append(ResourceLink(self.baseUrl, '/openclos/conf'))
    
    def getIndex(self, dbSession=None):
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
    
    def getIpFabrics(self, dbSession):
        
        url = bottle.request.url
        ipFabricsData = {}
        listOfIpFbarics = []
        IpFabrics = self.report.getPods(dbSession)
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
            ipFabric['leafSettings'] = IpFabrics[i]['leafSettings']
            ipFabric['leafCount'] = IpFabrics[i]['leafCount']
            ipFabric['devicePassword'] = IpFabrics[i]['devicePassword']
            listOfIpFbarics.append(ipFabric)
        ipFabricsData['ipFabric'] =  listOfIpFbarics
        ipFabricsData['total'] = len(listOfIpFbarics)
        ipFabricsData['uri'] = url 
        return {'ipFabrics' : ipFabricsData}
    
    def getIpFabric(self, dbSession, ipFabricId, requestUrl = None):
        if requestUrl is None:
            requestUrl = bottle.request.url
        ipFabric = self.report.getIpFabric(dbSession, ipFabricId)
        if ipFabric is not None:
            outputDict = {} 
            devices = ipFabric.devices
            outputDict['id'] = ipFabric.id
            outputDict['name'] = ipFabric.name
            outputDict['description'] = ipFabric.description 
            outputDict['spineAS'] = ipFabric.spineAS
            outputDict['spineDeviceType'] = ipFabric.spineDeviceType
            outputDict['spineCount'] = ipFabric.spineCount
            outputDict['leafAS'] = ipFabric.leafAS
            outputDict['leafSettings'] = []
            for leafSetting in ipFabric.leafSettings:
                outputDict['leafSettings'].append({'deviceType': leafSetting.deviceFamily, 'junosImage': leafSetting.junosImage})
            outputDict['leafCount'] = ipFabric.leafCount
            outputDict['loopbackPrefix'] = ipFabric.loopbackPrefix 
            outputDict['vlanPrefix'] = ipFabric.vlanPrefix
            outputDict['interConnectPrefix'] = ipFabric.interConnectPrefix 
            outputDict['managementPrefix'] = ipFabric.managementPrefix
            outputDict['outOfBandAddressList'] = ipFabric.outOfBandAddressList
            outputDict['outOfBandGateway'] = ipFabric.outOfBandGateway 
            outputDict['topologyType'] = ipFabric.topologyType
            outputDict['spineJunosImage'] = ipFabric.spineJunosImage
            outputDict['devicePassword'] = ipFabric.getCleartextPassword()
            outputDict['uri'] = requestUrl
            outputDict['devices'] = {'uri': requestUrl + '/devices', 'total':len(devices)}
            outputDict['cablingPlan'] = {'uri': requestUrl + '/cabling-plan'}
            outputDict['deviceConfiguration'] = {'uri': requestUrl + '/device-configuration'}
            outputDict['ztpConfiguration'] = {'uri': requestUrl + '/ztp-configuration'}
            outputDict['l2Report'] = {'uri': requestUrl + '/l2-report'}
            outputDict['l3Report'] = {'uri': requestUrl + '/l3-report'}
            
            logger.debug('getIpFabric: %s' % (ipFabricId))
         
            return {'ipFabric': outputDict}
        else:
            raise bottle.HTTPError(404, "IpFabric with id: %s not found" % (ipFabricId))
    
    def getCablingPlan(self, dbSession, ipFabricId):
        
        header =  bottle.request.get_header('Accept')
        logger.debug('Accept header: %s' % (header))

        ipFabric = self.report.getIpFabric(dbSession, ipFabricId)
        if ipFabric is not None:
            logger.debug('IpFabric name: %s' % (ipFabric.name))
            
            if header == 'application/json':
                cablingPlan = ipFabric.cablingPlan
                if cablingPlan is not None and cablingPlan.json is not None:
                    logger.debug('CablingPlan found in DB')
                    return cablingPlan.json
                else:
                    raise bottle.HTTPError(404, "IpFabric: %s exists but no CablingPlan found in DB" % (ipFabric.id))
                    
            else:
                ipFabricFolder = ipFabric.id + '-' + ipFabric.name
                fileName = os.path.join(ipFabricFolder, 'cablingPlan.dot')
                logger.debug('webServerRoot: %s, fileName: %s, exists: %s' % (webServerRoot, fileName, os.path.exists(os.path.join(webServerRoot, fileName))))
                logger.debug('Cabling file name: %s' % (fileName))                
                cablingPlan = bottle.static_file(fileName, root=webServerRoot)

                if isinstance(cablingPlan, bottle.HTTPError):
                    raise bottle.HTTPError(404, "IpFabric exists but no CablingPlan found. IpFabric: '%s " % (ipFabricFolder))
                return cablingPlan
        
        else:
            raise bottle.HTTPError(404, "IpFabric with id: %s not found" % (ipFabricId))

    def getLeafGenericConfiguration(self, dbSession, ipFabricId, deviceModel):
        ipFabric = self.report.getIpFabric(dbSession, ipFabricId)
        if ipFabric is None:
            raise bottle.HTTPError(404, "IpFabric with id: %s not found" % (ipFabricId))
        
        logger.debug('IpFabric name: %s, id: %s' % (ipFabric.name, ipFabricId))
        
        leafSetting = self.__dao.getLeafSetting(dbSession, ipFabricId, deviceModel)
        if leafSetting is None or leafSetting.config is None:
            raise bottle.HTTPError(404, "IpFabric exists but no leaf generic config found, probably configuration \
                was not created. deviceModel: %s, ipFabric name: '%s', id: '%s'" % (deviceModel, ipFabric.name, ipFabricId))
        
        bottle.response.headers['Content-Type'] = 'application/json'
        return leafSetting.config

    def getDeviceConfigsInZip(self, dbSession, ipFabricId):
        ipFabric = self.report.getIpFabric(dbSession, ipFabricId)
        if ipFabric is None:
            raise bottle.HTTPError(404, "IpFabric with id: %s not found" % (ipFabricId))
        
        logger.debug('IpFabric name: %s' % (ipFabric.name))

        zippedConfigFiles = self.createZipArchive(ipFabric)
        if zippedConfigFiles is not None:
            bottle.response.headers['Content-Type'] = 'application/zip'
            return zippedConfigFiles
        else:
            raise bottle.HTTPError(404, "IpFabric exists but no configs for devices.'%s " % (ipFabric.name))

    def createZipArchive(self, ipFabric):

        buff = StringIO.StringIO()
        zipArchive = zipfile.ZipFile(buff, mode='w')
        for device in ipFabric.devices:
            fileName = device.id + '__' + device.name + '.conf'
            if device.config is not None:
                zipArchive.writestr(fileName, device.config.config)
                
        if ipFabric.leafSettings is not None:
            for leafSetting in ipFabric.leafSettings:
                if leafSetting.config is not None:
                    zipArchive.writestr(leafSetting.deviceFamily + '.conf', leafSetting.config)
        
        zipArchive.close()
        logger.debug('zip file content:\n' + str(zipArchive.namelist()))
        return buff.getvalue()

    def getDevices(self, dbSession, ipFabricId):
        
        devices = {}
        listOfDevices = []
        ipFabric = self.report.getIpFabric(dbSession, ipFabricId)
        if ipFabric is not None:
            for device in ipFabric.devices:
                outputDict = {}
                outputDict['id'] = device.id
                outputDict['name'] = device.name
                outputDict['role'] = device.role
                outputDict['family'] = device.family
                outputDict['macAddress'] = device.macAddress
                outputDict['managementIp'] = device.managementIp
                outputDict['serialNumber'] = device.serialNumber
                outputDict['deployStatus'] = device.deployStatus
                outputDict['configStatus'] = device.configStatus
                outputDict['l2Status'] = device.l2Status
                outputDict['l3Status'] = device.l3Status
                outputDict['uri'] = bottle.request.url + '/' +device.id
                listOfDevices.append(outputDict)
            devices['device'] = listOfDevices
            devices['uri'] = bottle.request.url
            devices['total'] = len(ipFabric.devices)
            return {'devices' : devices}
        else:
            raise bottle.HTTPError(404, "IpFabric with id: %s not found" % (ipFabricId))
        
    def getDevice(self, dbSession, ipFabricId, deviceId):
        
        device = self.isDeviceExists(dbSession, ipFabricId, deviceId)
        #ipFabricUri is constructed from url
        url = bottle.request.url
        uri = url.split("/")
        uri.pop()
        uri.pop()
        ipFbaricUri = "/".join(uri)
               
        if device is not None:
            outputDict = {}
            outputDict['id'] = device.id
            outputDict['name'] = device.name
            outputDict['role'] = device.role
            outputDict['family'] = device.family
            outputDict['username'] = device.username
            outputDict['password'] = device.getCleartextPassword()
            outputDict['macAddress'] = device.macAddress
            outputDict['managementIp'] = device.managementIp
            outputDict['asn'] = device.asn
            outputDict['configStatus'] = device.configStatus
            outputDict['configStatusReason'] = device.configStatusReason
            outputDict['l2Status'] = device.l2Status
            outputDict['l2StatusReason'] = device.l2StatusReason
            outputDict['l3Status'] = device.l3Status
            outputDict['l3StatusReason'] = device.l3StatusReason
            outputDict['serialNumber'] = device.serialNumber
            outputDict['deployStatus'] = device.deployStatus
            outputDict['uri'] = bottle.request.url
            outputDict['pod'] = {'uri': ipFbaricUri }
            outputDict['config'] = {'uri': bottle.request.url + '/config' }
            
            return {'device': outputDict}
        else:
            raise bottle.HTTPError(404, "device with id: %s not found" % (deviceId))  
        
         
    def getDeviceConfig(self, dbSession, ipFabricId, deviceId):
        
        device = self.isDeviceExists(dbSession, ipFabricId, deviceId)
        if device is None:
            raise bottle.HTTPError(404, "No device found with ipFabricId: '%s', deviceId: '%s'" % (ipFabricId, deviceId))

        config = device.config
        if config is None:
            raise bottle.HTTPError(404, "Device exists but no config found, probably fabric script is not ran. ipFabricId: '%s', deviceId: '%s'" % (ipFabricId, deviceId))
        
        bottle.response.headers['Content-Type'] = 'application/json'
        return config.config

    
    def getZtpConfig(self, dbSession, ipFabricId):
        
        ipFabric = self.report.getIpFabric(dbSession, ipFabricId)
        if ipFabric is not None:
            logger.debug('Fabric name: %s' % (ipFabric.name))
            
            ipFabricFolder = ipFabric.id + '-' + ipFabric.name
            fileName = os.path.join(ipFabricFolder, "dhcpd.conf")
            logger.debug('webServerRoot: %s, fileName: %s, exists: %s' % (webServerRoot, fileName, os.path.exists(os.path.join(webServerRoot, fileName))))         
            ztpConf = bottle.static_file(fileName, root=webServerRoot)
            if isinstance(ztpConf, bottle.HTTPError):
                raise bottle.HTTPError(404, "Pod exists but no ztp Config found. Pod name: '%s " % (ipFabric.name))
            return ztpConf
        else:
            raise bottle.HTTPError(404, "IpFabric with id: %s not found" % (ipFabricId))
    

    def isDeviceExists(self, dbSession, ipFabricId, deviceId):
        try:
            device = dbSession.query(Device).join(Pod).filter(Device.id == deviceId).filter(Pod.id == ipFabricId).one()
            return device
        except (exc.NoResultFound):
            raise bottle.HTTPError(404, "No device found with ipFabricId: '%s', deviceId: '%s'" % (ipFabricId, deviceId))

    def getJunosImage(self, dbSession, junosImageName):
           
        fileName = os.path.join(junosImageRoot, junosImageName)
        logger.debug('junosImageRoot: %s, image: %s, exists: %s' % (junosImageRoot, junosImageName, os.path.exists(fileName)))

        config = bottle.static_file(junosImageName, root=junosImageRoot)
        if isinstance(config, bottle.HTTPError):
            raise bottle.HTTPError(404, "Junos image file not found. name: '%s'" % (junosImageName))
        return config
    
    def getOpenClosConfigParams(self, dbSession):
        confValues = {}
        confValues.update({'dbUrl': self.__conf['dbUrl']})
        confValues.update({'supportedDevices' : self.deviceSku.skuDetail })
        confValues.update({'dotColors': self.__conf['DOT']['colors'] })
        confValues.update({'httpServer' : self.__conf['httpServer']})
        confValues.update({'snmpTrap' : self.__conf['snmpTrap']})

        return {'OpenClosConf' : confValues }
                    
    def createIpFabric(self, dbSession):  
        if bottle.request.json is None:
            raise bottle.HTTPError(400, exception = RestError(0, "No json in request object"))
        else:
            pod = bottle.request.json.get('ipFabric')
            if pod is None:
                raise bottle.HTTPError(400, exception = RestError(0, "POST body can not be empty"))

        l3ClosMediation = L3ClosMediation(self.__conf, self.__daoClass)
        ipFabric = self.getPodFromDict(pod)
        ipFabricName = ipFabric.pop('name')
        fabricDevices = self.getDevDictFromDict(pod)
        try:
            fabric =  l3ClosMediation.createPod(ipFabricName, ipFabric, fabricDevices)
            url = bottle.request.url + '/' + fabric.id
            ipFabric = self.getIpFabric(dbSession, fabric.id, url)
        except ValueError as e:
            logger.debug('StackTrace: %s' % (traceback.format_exc()))
            raise bottle.HTTPError(400, exception = RestError(0, e.message))
        bottle.response.set_header('Location', url)
        bottle.response.status = 201

        return ipFabric
        
    def createCablingPlan(self, dbSession, ipFabricId):
        try:
            l3ClosMediation = L3ClosMediation(self.__conf, self.__daoClass)
            if l3ClosMediation.createCablingPlan(ipFabricId) is True:
                return bottle.HTTPResponse(status=200)
        except ValueError:
            raise bottle.HTTPError(404, "Fabric with id[%s] not found" % (ipFabricId))

    def createDeviceConfiguration(self, dbSession, ipFabricId):
        try:
            l3ClosMediation = L3ClosMediation(self.__conf, self.__daoClass)
            if l3ClosMediation.createDeviceConfig(ipFabricId) is True:
                return bottle.HTTPResponse(status=200)
        except ValueError:
            raise bottle.HTTPError(404, "Fabric with id[%s] not found" % (ipFabricId))
            
    def createZtpConfiguration(self, dbSession, ipFabricId):
        try:
            ZtpServer.createPodSpecificDhcpConfFile(self, ipFabricId)
        except ValueError:
            raise bottle.HTTPError(404, "Fabric with id[%s] not found" % (ipFabricId))

    def reconfigIpFabric(self, dbSession, ipFabricId):
        if bottle.request.json is None:
            raise bottle.HTTPError(400, exception = RestError(0, "No json in request object"))
        else:
            inPod = bottle.request.json.get('ipFabric')
            if inPod is None:
                raise bottle.HTTPError(400, exception = RestError(0, "POST body can not be empty"))

        l3ClosMediation = L3ClosMediation(self.__conf, self.__daoClass)
        ipFabric = self.getPodFromDict(inPod)
        #ipFabric['id'] = ipFabricId
        #ipFabric['uri'] = bottle.request.url
        fabricDevices = self.getDevDictFromDict(inPod)
        # Pass the ipFabric and fabricDevices dictionaries to config/update API, then return
        try:
            updatedFabric = l3ClosMediation.updatePod(ipFabricId, ipFabric, fabricDevices)
            url = bottle.request.url + '/' + updatedFabric.id
            return self.getIpFabric(dbSession, ipFabricId, url)
        except ValueError as e:
            raise bottle.HTTPError(400, exception = RestError(0, e.message))
    
    def setOpenClosConfigParams(self):
        return bottle.HTTPResponse(status=200)
    
    def deleteIpFabric(self, dbSession, ipFabricId):
        ipFabric = self.report.getIpFabric(dbSession, ipFabricId)
        if ipFabric is not None:
            self.__dao.deleteObject(dbSession, ipFabric)
            util.deleteOutFolder(self.__conf, ipFabric)
            logger.debug("IpFabric with id: %s deleted" % (ipFabricId))
        else:
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
            raise bottle.HTTPError(400, exception = RestError(0, "Invalid value in POST/PUT body."))
        ipFabric['name'] = podDict.get('name')
        ipFabric['fabricDeviceType'] = podDict.get('fabricDeviceType')
        ipFabric['fabricDeviceCount'] = podDict.get('fabricDeviceCount')
        ipFabric['spineCount'] = podDict.get('spineCount')
        ipFabric['spineDeviceType'] = podDict.get('spineDeviceType')
        ipFabric['leafCount'] = podDict.get('leafCount')
        ipFabric['leafSettings'] = podDict.get('leafSettings')
        ipFabric['leafUplinkcountMustBeUp'] = podDict.get('leafUplinkcountMustBeUp')
        ipFabric['interConnectPrefix'] = podDict.get('interConnectPrefix')
        ipFabric['vlanPrefix'] = podDict.get('vlanPrefix')
        ipFabric['loopbackPrefix'] = podDict.get('loopbackPrefix')
        ipFabric['spineAS'] = podDict.get('spineAS')
        ipFabric['leafAS'] = podDict.get('leafAS')
        ipFabric['topologyType'] = podDict.get('topologyType')
        ipFabric['outOfBandAddressList'] = podDict.get('outOfBandAddressList')
        ipFabric['outOfBandGateway'] = podDict.get('outOfBandGateway')
        ipFabric['managementPrefix'] = podDict.get('managementPrefix')
        ipFabric['hostOrVmCountPerLeaf'] = podDict.get('hostOrVmCountPerLeaf')
        ipFabric['description'] = podDict.get('description')
        ipFabric['devicePassword'] = podDict.get('devicePassword')

        return ipFabric


    def getDevDictFromDict(self, podDict):
        if podDict is not None:
            devices = podDict.get('devices')
        else:
            raise bottle.HTTPError(400, exception = RestError(0, "Invalid value in POST body."))

        fabricDevices = {}
        spines = []
        leaves = []
        for device in devices:
            temp = {}
            temp['name'] = device.get('name')
            temp['macAddress'] = device.get('macAddress')
            temp['role'] = device.get('role')
            temp['username'] = device.get('username')
            temp['password'] = device.get('password')
            temp['family'] = device.get('family')
            temp['serialNumber'] = device.get('serialNumber')
            temp['deployStatus'] = device.get('deployStatus')
            if temp['role'] == 'spine':
                spines.append(temp)
            elif temp['role'] == 'leaf':
                leaves.append(temp)
            else:
                raise bottle.HTTPError(400, exception = RestError(0, "Unexpected role value in device inventory list"))
            fabricDevices['spines'] = spines
            fabricDevices['leafs'] = leaves

        return fabricDevices

    def getL2Report(self, dbSession, ipFabricId):
        try:
            cached = bottle.request.query.get('cached', '1')
            if cached == '1':
                cachedData = True
            else:
                cachedData = False
            bottle.response.headers['Content-Type'] = 'application/json'
            return self.l2Report.generateReport(ipFabricId, cachedData)

        except ValueError:
            raise bottle.HTTPError(404, "Fabric with id: %s not found" % (ipFabricId))
    
    def getL3Report(self, dbSession, ipFabricId):
        try:
            cached = bottle.request.query.get('cached', '1')
            if cached == '1':
                cachedData = True
            else:
                cachedData = False
            bottle.response.headers['Content-Type'] = 'application/json'
            return self.l3Report.generateReport(ipFabricId, cachedData)

        except ValueError:
            raise bottle.HTTPError(404, "Fabric with id: %s not found" % (ipFabricId))

def main():
    restServer = RestServer()
    restServer.initRest()
    restServer.start()
    
if __name__ == '__main__':
    main()