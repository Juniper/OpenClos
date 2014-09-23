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

moduleName = 'ztp'
logging.basicConfig()
logger = logging.getLogger(moduleName)
logger.setLevel(logging.DEBUG)

ztpTemplateLocation = os.path.join('conf', 'ztp')


class ZtpServer():
    def __init__(self, conf = {}, templateEnv = None):
        if any(conf) == False:
            self.conf = util.loadConfig()
            logger.setLevel(logging.getLevelName(self.conf['logLevel'][moduleName]))

        else:
            self.conf = conf
        self.dao = Dao(self.conf)

        if templateEnv is None:
            self.templateEnv = Environment(loader=PackageLoader('jnpr.openclos', ztpTemplateLocation))

    
    def dcpServerReloadConfig(self):
        #TODO: sudo service isc-dhcp-server force-reload
        # Not needed as of now
        pass
    
    def createSingleDhcpConfFile(self):
        pods = self.dao.getAll(Pod)

        if len(pods) > 0:
            confWriter = DhcpConfWriter(self.conf, pods[0], self.dao)
            confWriter.writeSingle(self.generateSingleDhcpConf())

    def generateSingleDhcpConf(self):
        if util.isPlatformUbuntu():
            ztp = self.populateDhcpGlobalSettings()
            dhcpTemplate = self.templateEnv.get_template('dhcp.conf.ubuntu')
            return dhcpTemplate.render(ztp = self.populateDhcpDeviceSpecificSettingForAllPods(ztp))

    def createPodSpecificDhcpConfFile(self, podName):
        pod = self.dao.getUniqueObjectByName(Pod, podName)

        confWriter = DhcpConfWriter(self.conf, pod, self.dao)
        confWriter.write(self.generatePodSpecificDhcpConf(pod.name))

    def generatePodSpecificDhcpConf(self, podName):
        if util.isPlatformUbuntu():
            ztp = self.populateDhcpGlobalSettings()
            dhcpTemplate = self.templateEnv.get_template('dhcp.conf.ubuntu')
            conf = dhcpTemplate.render(ztp = self.populateDhcpDeviceSpecificSetting(podName, ztp))
            logger.debug('dhcpd.conf\n%s' % (conf))
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
        ztp['imageUrl'] = ztpGlobalSettings.get('junosImage')

        return ztp
    
    def populateDhcpDeviceSpecificSettingForAllPods(self, ztp = {}):
        pods = self.dao.getAll(Pod)
        for pod in pods:
            ztp = self.populateDhcpDeviceSpecificSetting(pod.name, ztp)
        return ztp

    def populateDhcpDeviceSpecificSetting(self, podName, ztp = {}):
        
        if ztp.get('devices') is None:
            ztp['devices'] = []
        
        pod = self.dao.getUniqueObjectByName(Pod, podName)
        for device in pod.devices:
            if device.role == 'spine':
                image = pod.spineJunosImage
            elif device.role == 'leaf':
                image = pod.leafJunosImage
            else:
                image = None
                logger.error('Pod: %s, Device: %s with unknown role: %s' % (pod.name, device.name, device.role))
                
            ztp['devices'].append({'name': device.name, 'mac': device.macAddress,
            'configUrl': 'pods/' + pod.name + '/devices/' + device.name + '/config',
            'imageUrl': image})
                
        return ztp

if __name__ == '__main__':
    ztpServer = ZtpServer()
    ztpServer.createPodSpecificDhcpConfFile('labLeafSpine')
    ztpServer.createPodSpecificDhcpConfFile('anotherPod')
    ztpServer.createSingleDhcpConfFile()
