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

moduleName = 'ztp'
ztpTemplateLocation = os.path.join('conf', 'ztp')
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(moduleName)

class ZtpServer():
    def __init__(self, conf = {}, templateEnv = None):
        if any(conf) == False:
            self.conf = util.loadConfig()
            logging.basicConfig(level=logging.getLevelName(self.conf['logLevel'][moduleName]))
            logger = logging.getLogger(moduleName)
        else:
            self.conf = conf
        self.dao = Dao(self.conf)

        if templateEnv is None:
            self.templateEnv = Environment(loader=PackageLoader('jnpr.openclos', ztpTemplateLocation))

    
    def dcpServerReloadConfig(self):
        #TODO: sudo service isc-dhcp-server force-reload
        pass
    
    def createDhcpconfFile(self):
        #TODO: reuse the FileOutputHandler
        pass
    
                
    def generateDhcpConf(self):
        if util.isPlatformUbuntu():
            dhcpTemplate = self.templateEnv.get_template('dhcp.conf.ubuntu')
            return dhcpTemplate.render(ztp = self.populateDhcpSettings())

    def populateDhcpSettings(self):
        ztp = self.populateDhcpGlobalSettings()
        return self.populateDhcpDeviceSpecificSetting(ztp)
                
    def populateDhcpGlobalSettings(self, ztp = {}):
        ztpGlobalSettings = util.loadClosDefinition()['ztp']
        subnet = ztpGlobalSettings['dhcpSubnet']
        dhcpBlock = IPNetwork(subnet)
        ipList = list(dhcpBlock.iter_hosts())
        ztp['network'] = str(dhcpBlock.network)
        ztp['netmask'] = str(dhcpBlock.netmask)
        ztp['rangeStart'] = str(ipList[1])
        ztp['rangeEnd'] = str(ipList[-1])

        ztp['defaultRoute'] = ztpGlobalSettings['defaultRoute']
        if  ztp['defaultRoute'] is None or ztp['defaultRoute'] == '': 
            ztp['defaultRoute'] = str(ipList[0])
        
        ztp['broadcast'] = str(dhcpBlock.broadcast)
        ztp['httpServerIp'] = self.conf['httpServer']['ipAddr']
        ztp['imageUrl'] = '/' + ztpGlobalSettings['junosImage']

        return ztp
    
    def populateDhcpDeviceSpecificSetting(self, ztp = {}):
        ztp['devices'] = []
        
        pods = self.dao.getAll(Pod)
        for pod in pods:
            for device in pod.devices:
                ztp['devices'].append({'name': device.name, 'mac': device.macAddress,
                'configUrl': '/pods/' + pod.name + '/devices/' + device.name + '/config',
                'imageUrl': pod.junosImage})
                
        return ztp

if __name__ == '__main__':
    ztpServer = ZtpServer()
    dhcpConf = ztpServer.generateDhcpConf()
    print dhcpConf