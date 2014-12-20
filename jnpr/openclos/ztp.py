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
from sqlalchemy.orm import exc


moduleName = 'ztp'
logger = None

ztpTemplateLocation = os.path.join('conf', 'ztp')


class ZtpServer():
    def __init__(self, conf = {}, templateEnv = None):
        global logger
        logger = util.getLogger(moduleName)
        if any(conf) == False:
            self.conf = util.loadConfig()

        else:
            self.conf = conf
        self.dao = Dao(self.conf)

        if templateEnv is None:
            self.templateEnv = Environment(loader=PackageLoader('jnpr.openclos', ztpTemplateLocation))

    
    def dcpServerReloadConfig(self):
        #TODO: sudo service isc-dhcp-server force-reload
        # Not needed as of now
        pass
    
    ''' TODO: for 2.0, Not needed as of now
    def createSingleDhcpConfFile(self):
        pods = self.dao.getAll(Pod)

        if len(pods) > 0:
            confWriter = DhcpConfWriter(self.conf, pods[0], self.dao)
            confWriter.writeSingle(self.generateSingleDhcpConf())
    '''
   
    def generateSingleDhcpConf(self):
        if util.isPlatformUbuntu():
            ztp = self.populateDhcpGlobalSettings()
            dhcpTemplate = self.templateEnv.get_template('ubuntu.1stage.dhcp.conf')
            return dhcpTemplate.render(ztp = self.populateDhcpDeviceSpecificSettingForAllPods(ztp))

    def createPodSpecificDhcpConfFile(self, podId):
        if podId is not None:
            try:
                pod = self.dao.getObjectById(Pod, podId)
            except (exc.NoResultFound):
                raise ValueError("Pod[id='%s']: not found" % (podId)) 
            confWriter = DhcpConfWriter(self.conf, pod, self.dao)
            confWriter.write(self.generatePodSpecificDhcpConf(pod.id))
        else:
            raise ValueError("Pod id can't be None")

    def getTemplate(self):
        ''' 
        Finds template based on o/s on which OpenClos is running
        and 1stage/2stage ZTP process
        returns: jinja2 template 
        '''
        if util.isPlatformUbuntu():
            if util.isZtpStaged(self.conf):
                return self.templateEnv.get_template('ubuntu.2stage.dhcp.conf')
            else:
                return self.templateEnv.get_template('ubuntu.1stage.dhcp.conf')
        elif util.isPlatformCentos():
            if util.isZtpStaged(self.conf):
                return self.templateEnv.get_template('centos.2stage.dhcp.conf')
            else:
                return self.templateEnv.get_template('centos.1stage.dhcp.conf')
        elif util.isPlatformWindows():
            ''' 
            this code is for testing only, generated dhcpd.conf would not work on windows  
            '''
            if util.isZtpStaged(self.conf):
                return self.templateEnv.get_template('ubuntu.2stage.dhcp.conf')
            else:
                return self.templateEnv.get_template('ubuntu.1stage.dhcp.conf')
        
    def generatePodSpecificDhcpConf(self, podId):
        ztp = self.populateDhcpGlobalSettings()
        
        dhcpTemplate = self.getTemplate()
        ztp = self.populateDhcpDeviceSpecificSetting(podId, ztp)
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
        ztp['httpServerIp'] = self.conf['httpServer']['ipAddr']
        if ztpGlobalSettings.get('junosImage') is not None:
            # don't start url as /openclos/... first / causes ZTP problem
            ztp['imageUrl'] = 'openclos/images/' + ztpGlobalSettings.get('junosImage')

        return ztp
    
    def populateDhcpDeviceSpecificSettingForAllPods(self, ztp = {}):
        pods = self.dao.getAll(Pod)
        for pod in pods:
            ztp = self.populateDhcpDeviceSpecificSetting(pod.id, ztp)
        return ztp

    def populateDhcpDeviceSpecificSetting(self, podId, ztp = {}):
        '''
        don't start any url as /openclos/... first / causes ZTP problem
        '''
        imageUrlPrefix =  'openclos/images/'       
        imageUrl = None
        
        if ztp.get('devices') is None:
            ztp['devices'] = []
        
        pod = self.dao.getObjectById(Pod, podId)
        for device in pod.devices:
            if device.role == 'spine':
                if pod.spineJunosImage is not None:
                    imageUrl = imageUrlPrefix + pod.spineJunosImage
            elif device.role == 'leaf':
                if util.isZtpStaged(self.conf):
                    continue
                if pod.spineJunosImage is not None:
                    imageUrl = imageUrlPrefix + pod.leafJunosImage
            else:
                logger.error('PodId: %s, Pod: %s, Device: %s with unknown role: %s' % (pod.id, pod.name, device.name, device.role))
                continue
            
            deviceMgmtIp = str(IPNetwork(device.managementIp).ip)
            ztp['devices'].append({'name': device.name, 'mac': device.macAddress,
            # don't start url as /openclos/ip-fabrics, first / causes ZTP problem
            'configUrl': 'openclos/ip-fabrics/' + pod.id + '/devices/' + device.id + '/config',
            'imageUrl': imageUrl, 'mgmtIp': deviceMgmtIp})
        
        if util.isZtpStaged(self.conf):
            ztp['leafDeviceFamily'] = pod.leafDeviceType
            ztp['leafImageUrl'] = imageUrlPrefix + pod.leafJunosImage
            # don't start url as /openclos/ip-fabrics/..., first / causes ZTP problem
            ztp['leafGenericConfigUrl'] = 'openclos/ip-fabrics/' + pod.id + '/leaf-generic-configuration'
            '''
            ztp['substringLength'] is the last argument of substring on dhcpd.conf, 
            should not be hardcoded, as it would change based on device family
            match if substring (option vendor-class-identifier, 0,21) = "Juniper-qfx5100-48s-6q"

            '''
            ztp['substringLength'] = len('Juniper-' + pod.leafDeviceType)
        return ztp

if __name__ == '__main__':
    util.loadLoggingConfig(moduleName)
    
    ztpServer = ZtpServer()
    pods = ztpServer.dao.getAll(Pod)
    ztpServer.createPodSpecificDhcpConfFile(pods[0].id)
    #ztpServer.createSingleDhcpConfFile()
