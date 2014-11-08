'''
Created on Nov. 06, 2014

@author: yunli
'''

from pysnmp.carrier.asynsock.dispatch import AsynsockDispatcher
from pysnmp.carrier.asynsock.dgram import udp
from pyasn1.codec.ber import decoder
from pysnmp.proto import api
from threading import Thread
import logging
import util
import signal
import sys

moduleName = 'trapd'
logging.basicConfig()
logger = logging.getLogger(moduleName)
logger.setLevel(logging.DEBUG)

DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 20162

trapReceiver = None

def onTrap(transportDispatcher, transportDomain, transportAddress, wholeMsg):
    while wholeMsg:
        msgVer = int(api.decodeMessageVersion(wholeMsg))
        if msgVer in api.protoModules:
            pMod = api.protoModules[msgVer]
        else:
            logger.debug('Unsupported SNMP version %s' % msgVer)
            return
        reqMsg, wholeMsg = decoder.decode(
            wholeMsg, asn1Spec=pMod.Message(),
            )
        logger.debug('Notification message from %s:%s: ' % (
            transportDomain, transportAddress
            )
        )
        reqPDU = pMod.apiMessage.getPDU(reqMsg)
        if reqPDU.isSameTypeWith(pMod.TrapPDU()):
            if msgVer == api.protoVersion1:
                logger.debug('Enterprise: %s' % (
                    pMod.apiTrapPDU.getEnterprise(reqPDU).prettyPrint()
                    )
                )
                logger.debug('Agent Address: %s' % (
                    pMod.apiTrapPDU.getAgentAddr(reqPDU).prettyPrint()
                    )
                )
                logger.debug('Generic Trap: %s' % (
                    pMod.apiTrapPDU.getGenericTrap(reqPDU).prettyPrint()
                    )
                )
                logger.debug('Specific Trap: %s' % (
                    pMod.apiTrapPDU.getSpecificTrap(reqPDU).prettyPrint()
                    )
                )
                logger.debug('Uptime: %s' % (
                    pMod.apiTrapPDU.getTimeStamp(reqPDU).prettyPrint()
                    )
                )
                varBinds = pMod.apiTrapPDU.getVarBindList(reqPDU)
            else:
                varBinds = pMod.apiPDU.getVarBindList(reqPDU)
            logger.debug('Var-binds:')
            for oid, val in varBinds:
                logger.debug('%s = %s' % (oid.prettyPrint(), val.prettyPrint()))
    return wholeMsg

class TrapReceiver():
    def __init__(self, conf = {}):
        if conf is None or any(conf) == False:
            self.conf = util.loadConfig()
        else:
            self.conf = conf
        if 'logLevel' in self.conf:
            logger.setLevel(logging.getLevelName(self.conf['logLevel'][moduleName])) 

        # default value
        self.target = DEFAULT_HOST
        self.port = DEFAULT_PORT
        
        # validate required parameter
        if 'snmpTrap' in self.conf and 'openclos_trap_group' in self.conf['snmpTrap'] and 'target' in self.conf['snmpTrap']['openclos_trap_group']:
            self.target = self.conf['snmpTrap']['openclos_trap_group']['target']
        else:
            logger.info("snmpTrap:openclos_trap_group:target is missing from configuration. using %s" % (self.target))                

        if 'snmpTrap' in self.conf and 'openclos_trap_group' in self.conf['snmpTrap'] and 'port' in self.conf['snmpTrap']['openclos_trap_group']:
            self.port = int(self.conf['snmpTrap']['openclos_trap_group']['port'])
        else:
            logger.info("snmpTrap:openclos_trap_group:port is missing from configuration. using %d" % (self.port))                
       
    def threadFunction(self):
        self.transportDispatcher = AsynsockDispatcher()

        self.transportDispatcher.registerRecvCbFun(onTrap)
        
        # UDP/IPv4
        self.transportDispatcher.registerTransport(
            udp.domainName, udp.UdpSocketTransport().openServerMode((self.target, self.port))
        )

        self.transportDispatcher.jobStarted(1)

        try:
            # Dispatcher will never finish as job#1 never reaches zero
            self.transportDispatcher.runDispatcher()
        except:
            self.transportDispatcher.closeDispatcher()
            raise
        else:
            self.transportDispatcher.closeDispatcher()

    def start(self):
        logger.info("Starting trap receiver...")
        self.thread = Thread(target=self.threadFunction, args=())
        self.thread.start()
        logger.info("Trap receiver started on %s:%d" % (self.target, self.port))

    def stop(self):
        logger.info("Stopping trap receiver...")
        self.transportDispatcher.jobFinished(1)  
        self.thread.join()
        logger.info("Trap receiver stopped")

        
def trap_receiver_signal_handler(signal, frame):
    logger.debug("received signal %d" % signal)
    trapReceiver.stop()
    sys.exit(0)
        
if __name__ == '__main__':
    signal.signal(signal.SIGINT, trap_receiver_signal_handler)
    signal.signal(signal.SIGTERM, trap_receiver_signal_handler)
    trapReceiver = TrapReceiver()
    trapReceiver.start()
    # Note we have to do this in order for signal to be properly caught by main thread
    # We need to do the similar thing when we integrate this into sampleApplication.py
    while True:
        signal.pause()
