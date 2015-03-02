'''
Created on Oct 2, 2014

@author: preethib
'''
from jnpr.openclos.l3Clos import L3ClosMediation
from jnpr.openclos.ztp import ZtpServer
from jnpr.openclos.rest import RestServer
from jnpr.openclos.trapd import TrapReceiver
import jnpr.openclos.util
import os
import signal
import sys

trapReceiver = None
restServer = None

installedDhcpConf = "/etc/dhcp/dhcpd.conf"

# OpenClos generated dhcpd.conf file path. It is usually located at
# <OpenClos install dir>/jnpr/openclos/out/<pod id>-<pod name>/dhcpd.conf
generatedDhcpConf = os.path.join(os.path.dirname(os.path.abspath(jnpr.openclos.l3Clos.__file__)), 
                                 'out', '<pod id>-<pod name>', 'dhcpd.conf')


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
        self.pod = l3ClosMediation.createPod('anotherPod', pods['anotherPod'])
        l3ClosMediation.createCablingPlan(self.pod.id)
        l3ClosMediation.createDeviceConfig(self.pod.id)
        global generatedDhcpConf
        generatedDhcpConf = generatedDhcpConf.replace('<pod id>', self.pod.id)
        generatedDhcpConf = generatedDhcpConf.replace('<pod name>', self.pod.name)

    def setupZTP(self):
        '''
        Setup Zero Touch Provisioning
        Generate DHCP config file 
        Install and restart DHCP server with new dhcp configuration
        '''
        ztpServer = ZtpServer()
        with ztpServer._dao.getReadSession() as session:
            ztpServer.createPodSpecificDhcpConfFile(session, self.pod.id)
            print generatedDhcpConf

        if jnpr.openclos.util.isPlatformUbuntu():
            os.system('sudo apt-get -y install isc-dhcp-server')
            os.system('sudo cp ' + generatedDhcpConf + ' ' + installedDhcpConf)
            os.system('sudo /usr/sbin/service isc-dhcp-server restart')

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
        return restServer

    def startTrapReceiver(self):
        '''
        start trap receiver to listen on traps from devices
        '''
        global trapReceiver
        trapReceiver = TrapReceiver()
        trapReceiver.start()
        return trapReceiver

def signal_handler(signal, frame):
    print("received signal %d" % signal)
    trapReceiver.stop()
    # TODO find how to cleanly stop rest server
    #restServer.stop()
    sys.exit(0)
        
if __name__ == '__main__':
    app = sampleApplication()

    newpid = os.fork()
    if newpid == 0: # child
        app.createConfigFilesForDevices()
        app.setupZTP()
        restServer = app.startHTTPserverForZTPFileTransferProtocol()
    
    else: # parent

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        app.startTrapReceiver()

        # Note we have to do this in order for signal to be properly caught by main thread
        # We need to do the similar thing when we integrate this into sampleApplication.py
        while True:
            signal.pause()
