'''
Created on Sep 10, 2014

@author: moloyc
'''

import os
import logging
from jinja2 import Environment, PackageLoader
from netaddr import IPNetwork

import util
from model import Pod
from dao import Dao
from writer import DhcpConfWriter
from propLoader import OpenClosProperty, loadLoggingConfig

from sqlalchemy.orm import exc
from exception import PodNotFound

moduleName = 'ztp'
loadLoggingConfig(appName = moduleName)
logger = logging.getLogger(moduleName)

ztpTemplateLocation = os.path.join('conf', 'ztp')


class ZtpServer():
    def __init__(self, conf = {}, templateEnv = None, daoClass = Dao):
        if any(conf) == False:
            self.__conf = OpenClosProperty(appName = moduleName).getProperties()
        else:
            self.__conf = conf

        self._dao = daoClass.getInstance()

        if templateEnv is None:
            self.templateEnv = Environment(loader=PackageLoader('jnpr.openclos', ztpTemplateLocation))
            self.templateEnv.lstrip_blocks = True
            self.templateEnv.trim_blocks = True

    
    def dcpServerReloadConfig(self):
        #TODO: sudo service isc-dhcp-server force-reload
        # Not needed as of now
        pass
    
    ''' TODO: for 2.0, Not needed as of now
    def createSingleDhcpConfFile(self):
        pods = self._dao.getAll(Pod)

        if len(pods) > 0:
            confWriter = DhcpConfWriter(self.__conf, pods[0], self._dao)
            confWriter.writeSingle(self.generateSingleDhcpConf())
    '''
   
    def generateSingleDhcpConf(self, session):
        if util.isPlatformUbuntu():
            ztp = self.populateDhcpGlobalSettings()
            dhcpTemplate = self.templateEnv.get_template('ubuntu.1stage.dhcp.conf')
            return dhcpTemplate.render(ztp = self.populateDhcpDeviceSpecificSettingForAllPods(session, ztp))

    def createPodSpecificDhcpConfFile(self, session, podId):
        if podId is not None:
            try:
                pod = self._dao.getObjectById(session, Pod, podId)
            except (exc.NoResultFound):
                raise PodNotFound("Pod[id='%s']: not found" % (podId)) 
            confWriter = DhcpConfWriter(self.__conf, pod, self._dao)
            confWriter.write(self.generatePodSpecificDhcpConf(session, pod.id))
        else:
            raise PodNotFound("Pod id can't be None")

    def getTemplate(self):
        ''' 
        Finds template based on o/s on which OpenClos is running
        and 1stage/2stage ZTP process
        returns: jinja2 template 
        '''
        if util.isPlatformUbuntu():
            if util.isZtpStaged(self.__conf):
                return self.templateEnv.get_template('ubuntu.2stage.dhcp.conf')
            else:
                return self.templateEnv.get_template('ubuntu.1stage.dhcp.conf')
        elif util.isPlatformCentos():
            if util.isZtpStaged(self.__conf):
                return self.templateEnv.get_template('centos.2stage.dhcp.conf')
            else:
                return self.templateEnv.get_template('centos.1stage.dhcp.conf')
        elif util.isPlatformWindows():
            ''' 
            this code is for testing only, generated dhcpd.conf would not work on windows  
            '''
            if util.isZtpStaged(self.__conf):
                return self.templateEnv.get_template('ubuntu.2stage.dhcp.conf')
            else:
                return self.templateEnv.get_template('ubuntu.1stage.dhcp.conf')
        
    def generatePodSpecificDhcpConf(self, session, podId):
        ztp = self.populateDhcpGlobalSettings()
        
        dhcpTemplate = self.getTemplate()
        ztp = self.populateDhcpDeviceSpecificSetting(session, podId, ztp)
        conf = dhcpTemplate.render(ztp = ztp)
            
        #logger.debug('dhcpd.conf\n%s' % (conf))
        return conf

    def populateDhcpGlobalSettings(self):
        ztp = {}
        ztpGlobalSettings = util.loadClosDefinition()['ztp']
        subnet = ztpGlobalSettings['dhcpSubnet']
        dhcpBlock = IPNetwork(subnet)
        ipList = list(dhcpBlock.iter_hosts())
        ztp['network'] = str(dhcpBlock.network)
        ztp['netmask'] = str(dhcpBlock.netmask)

        ztp['defaultRoute'] = ztpGlobalSettings.get('dhcpOptionRoute')
        if  ztp['defaultRoute'] is None or ztp['defaultRoute'] == '': 
            ztp['defaultRoute'] = str(ipList[0])

        ztp['rangeStart'] = ztpGlobalSettings.get('dhcpOptionRangeStart')
        if  ztp['rangeStart'] is None or ztp['rangeStart'] == '': 
            ztp['rangeStart'] = str(ipList[1])

        ztp['rangeEnd'] = ztpGlobalSettings.get('dhcpOptionRangeEnd')
        if  ztp['rangeEnd'] is None or ztp['rangeEnd'] == '': 
            ztp['rangeEnd'] = str(ipList[-1])

        ztp['broadcast'] = str(dhcpBlock.broadcast)
        ztp['httpServerIp'] = self.__conf['httpServer']['ipAddr']
        if ztpGlobalSettings.get('junosImage') is not None:
            # don't start url as /openclos/... first / causes ZTP problem
            ztp['imageUrl'] = 'openclos/images/' + ztpGlobalSettings.get('junosImage')

        return ztp
    
    def populateDhcpDeviceSpecificSettingForAllPods(self, session, ztp = {}):
        pods = self._dao.getAll(session, Pod)
        for pod in pods:
            ztp = self.populateDhcpDeviceSpecificSetting(session, pod.id, ztp)
        return ztp

    def populateDhcpDeviceSpecificSetting(self, session, podId, ztp = {}):
        '''
        don't start any url as /openclos/... first / causes ZTP problem
        '''
        imageUrlPrefix =  'openclos/images/'       
        
        if ztp.get('devices') is None:
            ztp['devices'] = []
        
        pod = self._dao.getObjectById(session, Pod, podId)
        for device in pod.devices:
            if device.family == 'unknown':
                continue
            
            if device.role == 'spine':
                imageName = util.getImageNameForDevice(pod, device)
                if imageName is not None:
                    imageUrl = imageUrlPrefix + imageName
                else:
                    imageUrl = None
            elif device.role == 'leaf':
                if util.isZtpStaged(self.__conf):
                    continue
                imageName = util.getImageNameForDevice(pod, device)
                if imageName is not None:
                    imageUrl = imageUrlPrefix + imageName
                else:
                    imageUrl = None
            else:
                logger.error('PodId: %s, Pod: %s, Device: %s with unknown role: %s' % (pod.id, pod.name, device.name, device.role))
                continue
            
            deviceMgmtIp = str(IPNetwork(device.managementIp).ip)
            if device.macAddress :
                ztp['devices'].append({'name': device.name, 'mac': device.macAddress,
                # don't start url as /openclos/pods, first / causes ZTP problem
                'configUrl': 'openclos/pods/' + pod.id + '/devices/' + device.id + '/config',
                'imageUrl': imageUrl, 'mgmtIp': deviceMgmtIp})
                logger.info('Device: %s, %s used MAC to map in dhcpd.conf' % (device.name, deviceMgmtIp))
            elif device.serialNumber:
                ztp['devices'].append({'name': device.name, 'serial': device.serialNumber,
                # don't start url as /openclos/pods, first / causes ZTP problem
                'configUrl': 'openclos/pods/' + pod.id + '/devices/' + device.id + '/config',
                'imageUrl': imageUrl, 'mgmtIp': deviceMgmtIp})
                logger.info('Device: %s, %s used Serial to map in dhcpd.conf' % (device.name, deviceMgmtIp))
            else:
                logger.error('Device: %s, %s does not have MAC or SerialNumber, not added in dhcpd.conf' % (device.name, deviceMgmtIp))
                
        if util.isZtpStaged(self.__conf):
            ztp['leafs'] = []
            for leafSetting in pod.leafSettings:
                setting = {}
                setting['leafDeviceFamily'] = leafSetting.deviceFamily
                if leafSetting.junosImage is not None:
                    setting['leafImageUrl'] = imageUrlPrefix + leafSetting.junosImage
                else:
                    setting['leafImageUrl'] = None
                # don't start url as /openclos/pods/..., first / causes ZTP problem
                setting['leafGenericConfigUrl'] = 'openclos/pods/' + pod.id + '/leaf-generic-configurations/' + leafSetting.deviceFamily
                '''
                setting['substringLength'] is the last argument of substring on dhcpd.conf, 
                should not be hardcoded, as it would change based on device family
                match if substring (option vendor-class-identifier, 0,21) = "Juniper-qfx5100-48s-6q"
    
                '''
                setting['substringLength'] = len('Juniper-' + leafSetting.deviceFamily)
                ztp['leafs'].append(setting)
                
        return ztp

if __name__ == '__main__':
    ztpServer = ZtpServer()
    with ztpServer._dao.getReadSession() as session:
    
        pods = ztpServer._dao.getAll(session, Pod)
        ztpServer.createPodSpecificDhcpConfFile(session, pods[0].id)
        ztpServer.createPodSpecificDhcpConfFile(session, pods[1].id)
        #ztpServer.createSingleDhcpConfFile()
