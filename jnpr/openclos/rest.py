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
from exception import InvalidRequest, PodNotFound, CablingPlanNotFound, DeviceConfigurationNotFound, DeviceNotFound, ImageNotFound, CreatePodFailed, UpdatePodFailed
from model import Pod, Device
from dao import Dao
from report import ResourceAllocationReport, L2Report, L3Report
from l3Clos import L3ClosMediation
from ztp import ZtpServer
from propLoader import OpenClosProperty, DeviceSku, loadLoggingConfig

moduleName = 'rest'
loadLoggingConfig(appName = moduleName)
logger = logging.getLogger(moduleName)

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
        if any(conf) == False:
            self._conf = OpenClosProperty(appName = moduleName).getProperties()

            global webServerRoot
            webServerRoot = self._conf['outputDir']
        else:
            self._conf = conf
        
        self.__daoClass = daoClass
        self.__dao = daoClass.getInstance()
        self.openclosDbSessionPlugin = OpenclosDbSessionPlugin(daoClass)
        
        if 'httpServer' in self._conf and 'ipAddr' in self._conf['httpServer'] and self._conf['httpServer']['ipAddr'] is not None:
            self.host = self._conf['httpServer']['ipAddr']
        else:
            self.host = 'localhost'

        if 'httpServer' in self._conf and 'port' in self._conf['httpServer']:
            self.port = self._conf['httpServer']['port']
        else:
            self.port = 8080
        self.baseUrl = 'http://%s:%d' % (self.host, self.port)

        self.report = ResourceAllocationReport(self._conf, daoClass)
        # Create a single instance of l2Report as it holds thread-pool
        # for device connection. Don't create l2Report multiple times 
        self.l2Report = L2Report(self._conf, daoClass)
        # Create a single instance of l3Report as it holds thread-pool
        # for device connection. Don't create l3Report multiple times 
        self.l3Report = L3Report(self._conf, daoClass)
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

        if util.isSqliteUsed(self._conf):
            bottle.run(self.app, host=self.host, port=self.port, debug=debugRest)
        else:
            bottle.run(self.app, host=self.host, port=self.port, debug=debugRest, server='paste')


    @staticmethod
    @error(400)
    def error400(error):
        bottle.response.headers['Content-Type'] = 'application/json'
        if error.exception is not None:
            return json.dumps({'errorCode': error.exception.code , 'errorMessage' : error.exception.message})
        else:
            return json.dumps({'errorCode': 0, 'errorMessage' : 'A generic error occurred'})
        
    @staticmethod
    @error(404)
    def error404(error):
        bottle.response.headers['Content-Type'] = 'application/json'
        if error.exception is not None:
            return json.dumps({'errorCode': error.exception.code , 'errorMessage' : error.exception.message})
        else:
            return json.dumps({'errorCode': 0, 'errorMessage' : 'A generic error occurred'})
        
    def addRoutes(self, baseUrl):
        self.indexLinks = []

        # GET APIs
        bottle.route('/', 'GET', self.getIndex)
        bottle.route('/openclos', 'GET', self.getIndex)
        bottle.route('/openclos/conf', 'GET', self.getOpenClosConfigParams)
        bottle.route('/openclos/pods', 'GET', self.getPods)
        bottle.route('/openclos/images/<junosImageName>', 'GET', self.getJunosImage)
        bottle.route('/openclos/pods/<podId>', 'GET', self.getPod)
        bottle.route('/openclos/pods/<podId>/cabling-plan', 'GET', self.getCablingPlan)
        bottle.route('/openclos/pods/<podId>/ztp-configuration','GET', self.getZtpConfig)
        bottle.route('/openclos/pods/<podId>/device-configuration', 'GET', self.getDeviceConfigsInZip)
        bottle.route('/openclos/pods/<podId>/leaf-generic-configurations/<deviceModel>', 'GET', self.getLeafGenericConfiguration)
        bottle.route('/openclos/pods/<podId>/l2-report', 'GET', self.getL2Report)
        bottle.route('/openclos/pods/<podId>/l3-report', 'GET', self.getL3Report)
        bottle.route('/openclos/pods/<podId>/devices', 'GET', self.getDevices)
        bottle.route('/openclos/pods/<podId>/devices/<deviceId>', 'GET', self.getDevice)
        bottle.route('/openclos/pods/<podId>/devices/<deviceId>/config', 'GET', self.getDeviceConfig)

        # POST/PUT APIs
        bottle.route('/openclos/pods', 'POST', self.createPod)
        bottle.route('/openclos/pods/<podId>/cabling-plan', 'PUT', self.createCablingPlan)
        bottle.route('/openclos/pods/<podId>/device-configuration', 'PUT', self.createDeviceConfiguration)
        bottle.route('/openclos/pods/<podId>/ztp-configuration', 'PUT', self.createZtpConfiguration)
        bottle.route('/openclos/pods/<podId>', 'PUT', self.reconfigPod)
        bottle.route('/openclos/conf/', 'PUT', self.setOpenClosConfigParams)

        # DELETE APIs
        bottle.route('/openclos/pods/<podId>', 'DELETE', self.deletePod)

        self.createLinkForConfigs()

    def createLinkForConfigs(self):
        # index page should show all top level URLs
        # users whould be able to drill down through navigation
        self.indexLinks.append(ResourceLink(self.baseUrl, '/openclos/pods'))
        self.indexLinks.append(ResourceLink(self.baseUrl, '/openclos/conf'))
    
    def getIndex(self, dbSession=None):
        if 'openclos' not in bottle.request.url:
            bottle.redirect(str(bottle.request.url).translate(None, ',') + 'openclos')

        jsonLinks = []
        for link in self.indexLinks:
            jsonLinks.append({'link': link.toDict()})

        jsonBody = \
            {'href': str(bottle.request.url).translate(None, ','),
             'links': jsonLinks
             }

        return jsonBody
    
    def getPods(self, dbSession):
        
        url = str(bottle.request.url).translate(None, ',')
        podsData = {}
        listOfIpFbarics = []
        pods = self.report.getPods(dbSession)
        logger.debug("count of pods: %d", len(pods))
        if not pods :   
            logger.debug("There are no pods in the system ")
        
        for i in range(len(pods)):
            pod = {}
            pod['uri'] = url +'/'+ pods[i]['id']
            pod['id'] = pods[i]['id']
            pod['name'] = pods[i]['name']
            pod['spineDeviceType'] = pods[i]['spineDeviceType']
            pod['spineCount'] = pods[i]['spineCount']
            pod['leafSettings'] = pods[i]['leafSettings']
            pod['leafCount'] = pods[i]['leafCount']
            pod['devicePassword'] = pods[i]['devicePassword']
            listOfIpFbarics.append(pod)
        podsData['pod'] =  listOfIpFbarics
        podsData['total'] = len(listOfIpFbarics)
        podsData['uri'] = url 
        return {'pods' : podsData}
    
    def getPodFieldListToCopy(self):
        return ['id', 'name', 'description', 'spineAS', 'spineDeviceType', 'spineCount', 'leafAS', 'leafCount', 
                'leafUplinkcountMustBeUp', 'loopbackPrefix', 'vlanPrefix', 'interConnectPrefix', 'managementPrefix', 
                'outOfBandAddressList', 'outOfBandGateway', 'topologyType', 'spineJunosImage', 'hostOrVmCountPerLeaf']
    
    def getPod(self, dbSession, podId, requestUrl = None):
        if requestUrl is None:
            requestUrl = str(bottle.request.url).translate(None, ',')
        pod = self.report.getPod(dbSession, podId)
        if pod is not None:
            outputDict = {} 
            devices = pod.devices
            for field in self.getPodFieldListToCopy():
                outputDict[field] = pod.__dict__.get(field)
            
            '''
            outputDict['id'] = pod.id
            outputDict['name'] = pod.name
            outputDict['description'] = pod.description 
            outputDict['spineAS'] = pod.spineAS
            outputDict['spineDeviceType'] = pod.spineDeviceType
            outputDict['spineCount'] = pod.spineCount
            outputDict['leafAS'] = pod.leafAS
            outputDict['leafCount'] = pod.leafCount
            outputDict['loopbackPrefix'] = pod.loopbackPrefix 
            outputDict['vlanPrefix'] = pod.vlanPrefix
            outputDict['interConnectPrefix'] = pod.interConnectPrefix 
            outputDict['managementPrefix'] = pod.managementPrefix
            outputDict['outOfBandAddressList'] = pod.outOfBandAddressList
            outputDict['outOfBandGateway'] = pod.outOfBandGateway 
            outputDict['topologyType'] = pod.topologyType
            outputDict['spineJunosImage'] = pod.spineJunosImage
            outputDict['hostOrVmCountPerLeaf'] = pod.hostOrVmCountPerLeaf
            '''
            outputDict['leafSettings'] = []
            for leafSetting in pod.leafSettings:
                outputDict['leafSettings'].append({'deviceType': leafSetting.deviceFamily, 'junosImage': leafSetting.junosImage})

            outputDict['devicePassword'] = pod.getCleartextPassword()
            outputDict['uri'] = requestUrl
            outputDict['devices'] = {'uri': requestUrl + '/devices', 'total':len(devices)}
            outputDict['cablingPlan'] = {'uri': requestUrl + '/cabling-plan'}
            outputDict['deviceConfiguration'] = {'uri': requestUrl + '/device-configuration'}
            outputDict['ztpConfiguration'] = {'uri': requestUrl + '/ztp-configuration'}
            outputDict['l2Report'] = {'uri': requestUrl + '/l2-report'}
            outputDict['l3Report'] = {'uri': requestUrl + '/l3-report'}
            
            logger.debug('getPod: %s' % (podId))
     
            return {'pod': outputDict}

        else:
            raise bottle.HTTPError(404, exception = PodNotFound(podId))
    
    def getCablingPlan(self, dbSession, podId):
        
        header =  bottle.request.get_header('Accept')
        logger.debug('Accept header before processing: %s' % (header))
        # hack to remove comma character, must be a bug on Bottle
        header = header.translate(None, ',')
        logger.debug('Accept header after processing: %s' % (header))

        pod = self.report.getPod(dbSession, podId)
        if pod is not None:
            logger.debug('Pod name: %s' % (pod.name))
            
            if header == 'application/json':
                cablingPlan = pod.cablingPlan
                if cablingPlan is not None and cablingPlan.json is not None:
                    logger.debug('CablingPlan found in DB')
                    return cablingPlan.json
                else:
                    raise bottle.HTTPError(404, exception = CablingPlanNotFound(pod.id))
                    
            else:
                podFolder = pod.id + '-' + pod.name
                fileName = os.path.join(podFolder, 'cablingPlan.dot')
                logger.debug('webServerRoot: %s, fileName: %s, exists: %s' % (webServerRoot, fileName, os.path.exists(os.path.join(webServerRoot, fileName))))
                logger.debug('Cabling file name: %s' % (fileName))                
                cablingPlan = bottle.static_file(fileName, root=webServerRoot)

                if isinstance(cablingPlan, bottle.HTTPError):
                    raise bottle.HTTPError(404, exception = CablingPlanNotFound(podFolder))
                return cablingPlan
        
        else:
            raise bottle.HTTPError(404, exception = PodNotFound(podId))

    def getLeafGenericConfiguration(self, dbSession, podId, deviceModel):
        pod = self.report.getPod(dbSession, podId)
        if pod is None:
            raise bottle.HTTPError(404, exception = PodNotFound(podId))
        
        logger.debug('Pod name: %s, id: %s' % (pod.name, podId))
        
        leafSetting = self.__dao.getLeafSetting(dbSession, podId, deviceModel)
        if leafSetting is None or leafSetting.config is None:
            raise bottle.HTTPError(404, exception = DeviceConfigurationNotFound("Pod exists but no leaf generic config found, probably configuration \
                was not created. deviceModel: %s, pod name: '%s', id: '%s'" % (deviceModel, pod.name, podId)))
        
        bottle.response.headers['Content-Type'] = 'application/json'
        return leafSetting.config

    def getDeviceConfigsInZip(self, dbSession, podId):
        pod = self.report.getPod(dbSession, podId)
        if pod is None:
            raise bottle.HTTPError(404, exception = PodNotFound(podId))
        
        logger.debug('Pod name: %s' % (pod.name))

        zippedConfigFiles = self.createZipArchive(pod)
        if zippedConfigFiles is not None:
            bottle.response.headers['Content-Type'] = 'application/zip'
            return zippedConfigFiles
        else:
            raise bottle.HTTPError(404, exception = DeviceConfigurationNotFound("Pod exists but no configs for devices.'%s " % (pod.name)))

    def createZipArchive(self, pod):

        buff = StringIO.StringIO()
        zipArchive = zipfile.ZipFile(buff, mode='w')
        for device in pod.devices:
            fileName = device.id + '__' + device.name + '.conf'
            if device.config is not None:
                zipArchive.writestr(fileName, device.config.config)
                
        if pod.leafSettings is not None:
            for leafSetting in pod.leafSettings:
                if leafSetting.config is not None:
                    zipArchive.writestr(leafSetting.deviceFamily + '.conf', leafSetting.config)
        
        zipArchive.close()
        logger.debug('zip file content:\n' + str(zipArchive.namelist()))
        return buff.getvalue()

    def copyAdditionalDeviceFields(self, dict, device):
        '''
        Hook to enhance Device object
        '''
    def getDevices(self, dbSession, podId):
        
        devices = {}
        listOfDevices = []
        pod = self.report.getPod(dbSession, podId)
        if pod is not None:
            for device in pod.devices:
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
                outputDict['uri'] = str(bottle.request.url).translate(None, ',') + '/' +device.id
                self.copyAdditionalDeviceFields(outputDict, device)

                listOfDevices.append(outputDict)
            devices['device'] = listOfDevices
            devices['uri'] = str(bottle.request.url).translate(None, ',')
            devices['total'] = len(pod.devices)
            return {'devices' : devices}
        else:
            raise bottle.HTTPError(404, exception = PodNotFound(podId))
        
    def getDevice(self, dbSession, podId, deviceId):
        
        device = self.isDeviceExists(dbSession, podId, deviceId)
        #podUri is constructed from url
        url = str(bottle.request.url).translate(None, ',')
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
            outputDict['uri'] = str(bottle.request.url).translate(None, ',')
            outputDict['pod'] = {'uri': ipFbaricUri }
            outputDict['config'] = {'uri': str(bottle.request.url).translate(None, ',') + '/config' }
            self.copyAdditionalDeviceFields(outputDict, device)
            
            return {'device': outputDict}
        else:
            raise bottle.HTTPError(404, exception = DeviceNotFound("No device found with podId: '%s', deviceId: '%s'" % (podId, deviceId)))
        
         
    def getDeviceConfig(self, dbSession, podId, deviceId):
        
        device = self.isDeviceExists(dbSession, podId, deviceId)
        if device is None:
            raise bottle.HTTPError(404, exception = DeviceNotFound("No device found with podId: '%s', deviceId: '%s'" % (podId, deviceId)))

        config = device.config
        if config is None:
            raise bottle.HTTPError(404, exception = DeviceConfigurationNotFound("Device exists but no config found, probably fabric script is not ran. podId: '%s', deviceId: '%s'" % (podId, deviceId)))
        
        bottle.response.headers['Content-Type'] = 'application/json'
        return config.config

    
    def getZtpConfig(self, dbSession, podId):
        
        pod = self.report.getPod(dbSession, podId)
        if pod is not None:
            logger.debug('pod name: %s' % (pod.name))
            
            podFolder = pod.id + '-' + pod.name
            fileName = os.path.join(podFolder, "dhcpd.conf")
            logger.debug('webServerRoot: %s, fileName: %s, exists: %s' % (webServerRoot, fileName, os.path.exists(os.path.join(webServerRoot, fileName))))         
            ztpConf = bottle.static_file(fileName, root=webServerRoot)
            if isinstance(ztpConf, bottle.HTTPError):
                raise bottle.HTTPError(404, exception = DeviceConfigurationNotFound("Pod exists but no ztp Config found. Pod name: '%s " % (pod.name)))
            return ztpConf
        else:
            raise bottle.HTTPError(404, exception = PodNotFound(podId))
    

    def isDeviceExists(self, dbSession, podId, deviceId):
        try:
            device = dbSession.query(Device).join(Pod).filter(Device.id == deviceId).filter(Pod.id == podId).one()
            return device
        except (exc.NoResultFound):
            raise bottle.HTTPError(404, exception = DeviceNotFound("No device found with podId: '%s', deviceId: '%s'" % (podId, deviceId)))

    def getJunosImage(self, dbSession, junosImageName):
           
        fileName = os.path.join(junosImageRoot, junosImageName)
        logger.debug('junosImageRoot: %s, image: %s, exists: %s' % (junosImageRoot, junosImageName, os.path.exists(fileName)))

        config = bottle.static_file(junosImageName, root=junosImageRoot)
        if isinstance(config, bottle.HTTPError):
            raise bottle.HTTPError(404, exception = ImageNotFound("Junos image file not found. name: '%s'" % (junosImageName)))
        return config
    
    def getOpenClosConfigParams(self, dbSession):
        supportedDevices = []
        
        for deviceFamily, value in self.deviceSku.skuDetail.iteritems():
            for role, ports in value.iteritems():
                uplinks = ports.get('uplinkPorts')
                downlinks = ports.get('downlinkPorts')
                deviceDetail = {'family': deviceFamily, 'role': role, 'uplinkPorts': uplinks, 'downlinkPorts': downlinks}                
                supportedDevices.append(deviceDetail)
            
        confValues = {}
        confValues.update({'dbUrl': self._conf['dbUrl']})
        confValues.update({'supportedDevices' :  supportedDevices})
        confValues.update({'dotColors': self._conf['DOT']['colors'] })
        confValues.update({'httpServer' : self._conf['httpServer']})
        confValues.update({'snmpTrap' : self._conf['snmpTrap']})

        return {'OpenClosConf' : confValues }
                    
    def createPod(self, dbSession):  
        if bottle.request.json is None:
            raise bottle.HTTPError(400, exception = InvalidRequest("No json in request object"))
        else:
            pod = bottle.request.json.get('pod')
            if pod is None:
                raise bottle.HTTPError(400, exception = InvalidRequest("POST body cannot be empty"))

        l3ClosMediation = L3ClosMediation(self._conf, self.__daoClass)
        podDevices = self.getDevDictFromDict(pod)
        pod = self.getPodFromDict(pod)
        podName = pod.pop('name')
        try:
            createdPod =  l3ClosMediation.createPod(podName, pod, podDevices)
            url = str(bottle.request.url).translate(None, ',') + '/' + createdPod.id
            pod = self.getPod(dbSession, createdPod.id, url)
        except Exception as e:
            logger.debug('StackTrace: %s' % (traceback.format_exc()))
            raise bottle.HTTPError(400, exception = CreatePodFailed(podName, e))
        bottle.response.set_header('Location', url)
        bottle.response.status = 201

        return pod
        
    def createCablingPlan(self, dbSession, podId):
        try:
            l3ClosMediation = L3ClosMediation(self._conf, self.__daoClass)
            if l3ClosMediation.createCablingPlan(podId) is True:
                return bottle.HTTPResponse(status=200)
        except Exception as e:
            raise bottle.HTTPError(404, exception = PodNotFound(podId, e))

    def createDeviceConfiguration(self, dbSession, podId):
        try:
            l3ClosMediation = L3ClosMediation(self._conf, self.__daoClass)
            if l3ClosMediation.createDeviceConfig(podId) is True:
                return bottle.HTTPResponse(status=200)
        except Exception as e:
            raise bottle.HTTPError(404, exception = PodNotFound(podId, e))
            
    def createZtpConfiguration(self, dbSession, podId):
        try:
            ZtpServer.createPodSpecificDhcpConfFile(self, podId)
        except Exception as e:
            raise bottle.HTTPError(404, exception = PodNotFound(podId, e))

    def reconfigPod(self, dbSession, podId):
        if bottle.request.json is None:
            raise bottle.HTTPError(400, exception = InvalidRequest("No json in request object"))
        else:
            inPod = bottle.request.json.get('pod')
            if inPod is None:
                raise bottle.HTTPError(400, exception = InvalidRequest("POST body cannot be empty"))

        l3ClosMediation = L3ClosMediation(self._conf, self.__daoClass)
        pod = self.getPodFromDict(inPod)
        #pod['id'] = podId
        #pod['uri'] = str(bottle.request.url).translate(None, ',')
        podDevices = self.getDevDictFromDict(inPod)
        # Pass the pod and podDevices dictionaries to config/update API, then return
        try:
            updatedPod = l3ClosMediation.updatePod(podId, pod, podDevices)
            url = str(bottle.request.url).translate(None, ',') + '/' + updatedPod.id
            return self.getPod(dbSession, podId, url)
        except Exception as e:
            raise bottle.HTTPError(400, exception = UpdatePodFailed(podId, e))
    
    def setOpenClosConfigParams(self):
        return bottle.HTTPResponse(status=200)
    
    def deletePod(self, dbSession, podId):
        pod = self.report.getPod(dbSession, podId)
        if pod is not None:
            self.__dao.deleteObject(dbSession, pod)
            util.deleteOutFolder(self._conf, pod)
            logger.debug("Pod with id: %s deleted" % (podId))
        else:
            raise bottle.HTTPError(404, exception = PodNotFound(podId))
        return bottle.HTTPResponse(status=204)

    def getPodFromDict(self, podDict):
        pod = {}
        '''
        # Need to revisit later on to make thing works as below.
        podDict.pop('devices')
        pod = Pod(**inPod)
        '''
        if podDict is None:
            raise bottle.HTTPError(400, exception = InvalidRequest("Invalid value in request body."))
        
        for field in self.getPodFieldListToCopy():
            pod[field] = podDict.get(field)
        
        '''
        pod['name'] = podDict.get('name')
        pod['description'] = podDict.get('description')
        pod['spineAS'] = podDict.get('spineAS')
        pod['spineDeviceType'] = podDict.get('spineDeviceType')
        pod['spineCount'] = podDict.get('spineCount')
        pod['leafAS'] = podDict.get('leafAS')
        pod['leafCount'] = podDict.get('leafCount')
        pod['leafUplinkcountMustBeUp'] = podDict.get('leafUplinkcountMustBeUp')
        pod['loopbackPrefix'] = podDict.get('loopbackPrefix')
        pod['vlanPrefix'] = podDict.get('vlanPrefix')
        pod['interConnectPrefix'] = podDict.get('interConnectPrefix')
        pod['managementPrefix'] = podDict.get('managementPrefix')
        pod['outOfBandAddressList'] = podDict.get('outOfBandAddressList')
        pod['outOfBandGateway'] = podDict.get('outOfBandGateway')
        pod['topologyType'] = podDict.get('topologyType')
        pod['topologyType'] = podDict.get('topologyType')
        pod['spineJunosImage'] = podDict.get('spineJunosImage')
        pod['hostOrVmCountPerLeaf'] = podDict.get('hostOrVmCountPerLeaf')
        '''

        pod['leafSettings'] = podDict.get('leafSettings')
        pod['devicePassword'] = podDict.get('devicePassword')

        return pod


    def getDevDictFromDict(self, podDict):
        if podDict is not None:
            devices = podDict.get('devices')
        else:
            raise bottle.HTTPError(400, exception = InvalidRequest("Invalid value in request body."))

        podDevices = {}
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
                raise bottle.HTTPError(400, exception = InvalidRequest("Unexpected role value in device inventory list"))
            podDevices['spines'] = spines
            podDevices['leafs'] = leaves

        return podDevices

    def getL2Report(self, dbSession, podId):
        try:
            cached = bottle.request.query.get('cached', '1')
            if cached == '1':
                cachedData = True
            else:
                cachedData = False
            bottle.response.headers['Content-Type'] = 'application/json'
            return self.l2Report.generateReport(podId, cachedData)

        except Exception as e:
            raise bottle.HTTPError(404, exception = PodNotFound(podId, e))
    
    def getL3Report(self, dbSession, podId):
        try:
            cached = bottle.request.query.get('cached', '1')
            if cached == '1':
                cachedData = True
            else:
                cachedData = False
            bottle.response.headers['Content-Type'] = 'application/json'
            return self.l3Report.generateReport(podId, cachedData)

        except Exception as e:
            raise bottle.HTTPError(404, exception = PodNotFound(podId, e))

def main():
    restServer = RestServer()
    restServer.initRest()
    restServer.start()
    
if __name__ == '__main__':
    main()
