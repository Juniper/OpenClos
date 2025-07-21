'''
Created on Nov. 06, 2014

@author: yunli
'''

from pysnmp.carrier.asyncio.dispatch import AsyncioDispatcher
from pysnmp.carrier.asyncio.dgram import udp
from pyasn1.codec.ber import decoder
from pysnmp.proto import api
from threading import Thread, Event
import logging
from jnpr.openclos import util
import signal
import sys
import subprocess
import concurrent.futures
from jnpr.openclos.devicePlugin import TwoStageConfigurator 
from jnpr.openclos.loader import OpenClosProperty, loadLoggingConfig
from jnpr.openclos.exception import TrapDaemonError
from jnpr.openclos.deviceConnector import CachedConnectionFactory

moduleName = 'trapd'
loadLoggingConfig(appName=moduleName)
logger = logging.getLogger(moduleName)

DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 20162
DEFAULT_MAX_THREADS = 10

trapReceiver = None

def onTrap(transportDispatcher, transportDomain, transportAddress, wholeMsg):
    # don't even log the trap PDU unless we are at DEBUG level
    if logger.isEnabledFor(logging.DEBUG):
        while wholeMsg:
            msgVer = int(api.decodeMessageVersion(wholeMsg))
            if msgVer in api.protoModules:
                pMod = api.protoModules[msgVer]
            else:
                logger.error('Unsupported SNMP version %s', msgVer)
                return
            reqMsg, wholeMsg = decoder.decode(
                wholeMsg, asn1Spec=pMod.Message(),
                )
            logger.info('Notification message from %s:%s ', transportAddress[0], transportAddress[1])
            reqPDU = pMod.apiMessage.getPDU(reqMsg)
            if reqPDU.isSameTypeWith(pMod.TrapPDU()):
                if msgVer == api.protoVersion1:
                    logger.debug('Enterprise: %s', pMod.apiTrapPDU.getEnterprise(reqPDU).prettyPrint())
                    logger.debug('Agent Address: %s', pMod.apiTrapPDU.getAgentAddr(reqPDU).prettyPrint())
                    logger.debug('Generic Trap: %s', pMod.apiTrapPDU.getGenericTrap(reqPDU).prettyPrint())
                    logger.debug('Specific Trap: %s', pMod.apiTrapPDU.getSpecificTrap(reqPDU).prettyPrint())
                    logger.debug('Uptime: %s', pMod.apiTrapPDU.getTimeStamp(reqPDU).prettyPrint())
                    varBinds = pMod.apiTrapPDU.getVarBindList(reqPDU)
                else:
                    varBinds = pMod.apiPDU.getVarBindList(reqPDU)
                logger.debug('Var-binds:')
                for oid, val in varBinds:
                    logger.debug('%s = %s', oid.prettyPrint(), val.prettyPrint())
                    
    
    # start the 2-stage configuration in a separate thread
    if trapReceiver is not None:
        # execute 2-stage configuration callback if there is one configured in openclos.yaml
        callback = trapReceiver.twoStageConfigurationCallback
        if callback is not None and len(callback) > 0: 
            proc = subprocess.Popen(callback, shell=True)
            returnValue = proc.wait()
            if returnValue != 0:
                # 2-stage configuration callback returns non-zero value indicating we SHOULD NOT continue
                logger.debug('twoStageConfigurationCallback "%s" returns %d, trap ignored', callback, returnValue)
                return
            
        configurator = TwoStageConfigurator(deviceIp=transportAddress[0], stopEvent=trapReceiver.stopEvent)
        trapReceiver.executor.submit(configurator.start2StageConfiguration)        

class TrapReceiver():
    def __init__(self, conf={}):
        if conf is None or any(conf) == False:
            self.__conf = OpenClosProperty(appName=moduleName).getProperties()
        else:
            self.__conf = conf

        # default value
        self.target = DEFAULT_HOST
        self.port = DEFAULT_PORT
        
        # validate required parameter
        if 'snmpTrap' in self.__conf and 'openclos_trap_group' in self.__conf['snmpTrap'] and 'target' in self.__conf['snmpTrap']['openclos_trap_group']:
            self.target = self.__conf['snmpTrap']['openclos_trap_group']['target']
        else:
            logger.info("snmpTrap:openclos_trap_group:target is missing from configuration. using %s", self.target)

        if 'snmpTrap' in self.__conf and 'openclos_trap_group' in self.__conf['snmpTrap'] and 'port' in self.__conf['snmpTrap']['openclos_trap_group']:
            self.port = int(self.__conf['snmpTrap']['openclos_trap_group']['port'])
        else:
            logger.info("snmpTrap:openclos_trap_group:port is missing from configuration. using %d", self.port)
            
        if 'snmpTrap' in self.__conf and 'threadCount' in self.__conf['snmpTrap']:
            self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=self.__conf['snmpTrap']['threadCount'])
        else:
            self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=DEFAULT_MAX_THREADS)

        # event to stop from sleep
        self.stopEvent = Event()
        
        self.twoStageConfigurationCallback = util.getTwoStageConfigurationCallback(self.__conf)
       
    def threadFunction(self):
        import asyncio
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.transportDispatcher = AsyncioDispatcher()
        self.transportDispatcher.register_recv_callback(onTrap)
        
        # UDP/IPv4
        self.transportDispatcher.register_transport(
            udp.domainName, udp.UdpAsyncioTransport().open_server_mode((self.target, self.port))
        )

        self.transportDispatcher.jobStarted(1)

        try:
            # Dispatcher will never finish as job#1 never reaches zero
            self.transportDispatcher.run_dispatcher()
            #self.loop.run_until_complete(self.transportDispatcher.runDispatcher())
        except Exception as exc:
            logger.error("Encounted error '%s' on trap receiver %s:%d", exc, self.target, self.port)
            self.transportDispatcher.close_dispatcher()
            raise TrapDaemonError("Trap receiver %s:%d" % (self.target, self.port), exc)
        finally:
            self.transportDispatcher.close_dispatcher()

    def start(self):
        logger.info("Starting trap receiver...")
        self.thread = Thread(target=self.threadFunction, args=())
        self.thread.start()
        logger.info("Trap receiver started on %s:%d", self.target, self.port)

    '''def stop(self):
        if self.stopEvent.is_set():
            # in the middle of shutting down
            return
        breakpoint()
        logger.info("Stopping trap receiver...")

        # shutdown all live connections
        CachedConnectionFactory.getInstance()._stop()
        
        self.stopEvent.set()
        self.executor.shutdown()
        self.transportDispatcher.jobFinished(1)  
        self.loop.call_soon_threadsafe(self.loop.stop)
        #self.thread.join()
        logger.info("Trap receiver stopped")'''

    def stop(self):
        if self.stopEvent.is_set():
            return

        logger.info("Stopping trap receiver...")

        # shutdown all live connections
        CachedConnectionFactory.getInstance()._stop()

        self.stopEvent.set()

        self.loop.call_soon_threadsafe(self.loop.stop)
        # Close dispatcher cleanly
        if self.transportDispatcher:
            self.transportDispatcher.jobFinished(1)
            self.transportDispatcher.close_dispatcher()

        # Shutdown executor
        if self.executor:
            self.executor.shutdown(wait=True)

        # Wait for thread to exit
        if self.thread.is_alive():
            self.thread.join()

        logger.info("Trap receiver stopped now")

        
def trap_receiver_signal_handler(signal, frame):
    logger.debug("received signal %d", signal)
    trapReceiver.stop()
    sys.exit(0)

def main():
    signal.signal(signal.SIGINT, trap_receiver_signal_handler)
    signal.signal(signal.SIGTERM, trap_receiver_signal_handler)
    global trapReceiver
    trapReceiver = TrapReceiver()
    trapReceiver.start()
    # Note we have to do this in order for signal to be properly caught by main thread
    # We need to do the similar thing when we integrate this into sampleApplication.py
    while True:
        signal.pause()
    
if __name__ == '__main__':
    main()
