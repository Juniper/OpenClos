'''
Created on Oct 2, 2014

@author: preethib
'''
from jnpr.openclos.l3Clos import L3ClosMediation
from jnpr.openclos.ztp import ZtpServer
from jnpr.openclos.rest import RestServer
import jnpr.openclos.util
import os

installedDhcpConf = "/etc/dhcp/dhcpd.conf"

# OpenClos generated dhcpd.conf file path. It is usually located at
# <OpenClos install dir>/jnpr/openclos/out/<pod id>-<pod name>/dhcpd.conf
# example for ubuntu - /usr/local/lib/python2.7/dist-packages/jnpr/openclos/out/<pod id>-<pod name>/dhcpd.conf
# example for centos - /usr/lib/python2.6/site-packages/jnpr/openclos/out/<pod id>-<pod name>/dhcpd.conf
generatedDhcpConf = "/home/regress/OpenClos-R1.0.dev1/jnpr/openclos/out/<pod id>-<pod name>/dhcpd.conf"

class sampleApplication:
    '''
    Sample Application for creating Layer-3 IP Fabric
    The script should be run with sudo privilege
    It installs dhcp server and run http server on port 80.
    '''
    def createConfigFilesForDevices(self):
        '''
         Create configuration for each leaf and spine in IP Fabric
        '''
        l3ClosMediation = L3ClosMediation()
        pods = l3ClosMediation.loadClosDefinition()
        pod = l3ClosMediation.createPod('anotherPod', pods['anotherPod'])
        l3ClosMediation.createCablingPlan(pod.id)
        l3ClosMediation.createDeviceConfig(pod.id)
        global generatedDhcpConf
        generatedDhcpConf = generatedDhcpConf.replace('<pod id>', pod.id)
        generatedDhcpConf = generatedDhcpConf.replace('<pod name>', pod.name)

    def setupZTP(self):
        '''
        Setup Zero Touch Provisioning
        Generate DHCP config file 
        Install and restart DHCP server with new dhcp configuration
        '''
        ztpServer = ZtpServer()
        ztpServer.createPodSpecificDhcpConfFile('anotherPod')
        print generatedDhcpConf

        if jnpr.openclos.util.isPlatformUbuntu():
            os.system('sudo apt-get -y install isc-dhcp-server')
            os.system('sudo cp ' + generatedDhcpConf + ' ' + installedDhcpConf)
            os.system("/etc/init.d/isc-dhcp-server restart")

        elif jnpr.openclos.util.isPlatformCentos():
            os.system('yum -y install dhcp')
            os.system('sudo cp ' + generatedDhcpConf + ' ' + installedDhcpConf)
            os.system("/etc/rc.d/init.d/dhcpd restart")

    def startHTTPserverForZTPFileTransferProtocol(self):
        '''
        start HTTP server to serve as file-transfer mechanism for ZTP/DHCP process
        '''
        restServer = RestServer()
        restServer.initRest()
        restServer.start()

if __name__ == '__main__':
    app = sampleApplication()
    app.createConfigFilesForDevices()
    app.setupZTP()
    app.startHTTPserverForZTPFileTransferProtocol()
