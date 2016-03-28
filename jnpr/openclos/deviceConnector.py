'''
Created on Nov 16, 2015

@author: moloyc
'''

import logging
import traceback
import os
from threading import RLock, Event, Thread
from contextlib import contextmanager
import time

from jnpr.junos import Device as DeviceConnection
from jnpr.junos.factory import loadyaml
from jnpr.junos.exception import ConnectError, RpcError, CommitError, LockError
from jnpr.junos.utils.config import Config

from loader import loadLoggingConfig, OpenClosProperty
from exception import DeviceConnectFailed, DeviceRpcFailed
from common import SingletonBase

moduleName = 'deviceConnector'
loadLoggingConfig(appName=moduleName)
logger = logging.getLogger(moduleName)

DEFAULT_KEEP_ALIVE_TIMEOUT = 90
DEFAULT_CLEANER_THREAD_WAIT_TIME = 60
DEFAULT_AUTO_PROBE = 15

class AbstractConnection(object):
    def __init__(self, ip):
        self._ip = ip
        self._debugContext = 'Device: ' + self._ip + ':'

    def close(self):
        raise NotImplementedError()

    def isActive(self):
        raise NotImplementedError()
        
    def getDeviceFamily(self):
        raise NotImplementedError()

    def getDeviceSerialNumber(self):
        raise NotImplementedError()
    
    def getL2Neighbors(self, brief=True):
        raise NotImplementedError()

    def getL3Neighbors(self, brief=True):
        raise NotImplementedError()

    def updateConfig(self, config):
        raise NotImplementedError()

class CachedConnectionFactory(SingletonBase):
    """
    Similar to Http 1.1 style keep-alive connection.
    Any connection object created through this factory 
    will be available for reuse until keep-alive timeout. 
    """
    def __init__(self):
        self.__cache = {}
        self.__cacheLock = RLock()
        self.__event = Event()

        # find configurable parameters
        self._waitTime = DEFAULT_CLEANER_THREAD_WAIT_TIME
        self._keepAliveTimeout = DEFAULT_KEEP_ALIVE_TIMEOUT
        # iterate relevant section of openclos.yaml
        conf = OpenClosProperty().getProperties()
        deviceConnectorDict = conf.get('deviceConnector')
        if deviceConnectorDict is not None:
            CachedConnectionFactoryDict = deviceConnectorDict.get('CachedConnectionFactory')
            if CachedConnectionFactoryDict is not None:
                if 'keepAliveTimeout' in CachedConnectionFactoryDict:
                    self._keepAliveTimeout = CachedConnectionFactoryDict['keepAliveTimeout']
                if 'cleanerThreadWaitTime' in CachedConnectionFactoryDict:
                    self._waitTime = CachedConnectionFactoryDict['cleanerThreadWaitTime']

        self._thread = Thread(target=self.closeOldConnections)
        self._thread.start()

    @contextmanager
    def connection(self, connectionClass, ip, *args, **kwargs):
        """
        finds a connection object in cache, otherwise creates one,
        once user is done using connection, it goes back to cache.
        Example how to use -
        
        with CachedConnectionFactory.getInstance().connection(NetconfConnection, "1.2.3.4", ..) as conn:
            print conn

        :param ip: device ip
        :returns connectionClass: connection object of type connectionClass, subclass of AbstractConnection
        """
        connection = None
        with self.__cacheLock:
            if not self.__cache.has_key(ip):
                self.__cache[ip] = []
            if self.__cache.get(ip):
                connection = self.__cache.get(ip).pop()[0]

        if not connection:
            connection = connectionClass(ip, *args, **kwargs)

        try:
            yield connection
        finally:
            if connection.isActive():
                with self.__cacheLock:
                    if not self.__cache.has_key(ip):
                        self.__cache[ip] = []
                    self.__cache[ip].append((connection, time.time()))
        
    def closeOldConnections(self):
        try:
            while True:
                self.__event.wait(self._waitTime)
                if not self.__event.is_set():
                    try:
                        with self.__cacheLock:
                            for ip, connections in self.__cache.items():
                                liveConnections = []
                                for connection in connections:
                                    if (time.time() - connection[1] > self._keepAliveTimeout):
                                        connection[0].close()
                                    else:
                                        liveConnections.append(connection)
                                if liveConnections:
                                    self.__cache[ip] = liveConnections
                                else:
                                    del self.__cache[ip]
                    except Exception as exc:
                        logger.debug('closeOldConnections failed, %s', exc)
                    finally:
                        pass
                else:
                    logger.debug('closeOldConnections exited')
                    return
        except Exception:
            # not safe to log anything at this point
            return

    def _stop(self):
        if self.__event.is_set():
            # in the middle of shutting down
            return
            
        self.__event.set()
        # Note we don't join the self._thread because there might be delays when closing all connections.
        #self._thread.join()
        try:
            with self.__cacheLock:
                for ip, connections in self.__cache.items():
                    for connection in connections:
                        connection[0].close()
                self.__cache = {}
        except Exception:
            pass

    def __del__(self):
        self._stop()
        
class NetconfConnection(AbstractConnection):
    def __init__(self, ip, *args, **kwargs):
        
        super(NetconfConnection, self).__init__(ip)
        self._username = kwargs.pop("username", None)
        self._password = kwargs.pop("password", None)
        
        # find configurable parameters
        self._autoProbe = DEFAULT_AUTO_PROBE
        conf = OpenClosProperty().getProperties()
        # iterate relevant section of openclos.yaml
        deviceConnectorDict = conf.get('deviceConnector')
        if deviceConnectorDict is not None:
            NetconfConnectionDict = deviceConnectorDict.get('NetconfConnection')
            if NetconfConnectionDict is not None:
                if 'autoProbe' in NetconfConnectionDict:
                    self._autoProbe = NetconfConnectionDict['autoProbe']
        
        if not self._username :
            raise DeviceConnectFailed('%s username is None' % (self._debugContext))
        if not self._password:
            raise DeviceConnectFailed('%s, password is None' % (self._debugContext))        
        
        self._collectedFacts = False
        self._deviceConnection = None
        
        try:
            DeviceConnection.auto_probe = self._autoProbe
            deviceConnection = DeviceConnection(host=self._ip, user=self._username, password=self._password, port=22, gather_facts=False)
            deviceConnection.open()
            logger.info('%s connected', self._debugContext)
            self._deviceConnection = deviceConnection
        except ConnectError as exc:
            logger.error('%s connection failure, %s', self._debugContext, exc)
            raise DeviceConnectFailed(self._ip, exc)
        except Exception as exc:
            logger.error('%s unknown error, %s', self._debugContext, exc)
            logger.debug('StackTrace: %s', traceback.format_exc())
            raise DeviceConnectFailed(self._ip, exc)
    
    def isActive(self):
        if self._deviceConnection:
            return self._deviceConnection.connected
        return False

    def close(self):
        if self._deviceConnection:
            try:
                self._deviceConnection.close()
            except Exception as ex:
                logger.debug('%s close connection error, %s', self._debugContext, ex)
                
            self._deviceConnection = None
            logger.info('%s connection closed', self._debugContext)
                        
    def getDeviceFamily(self):
        if self._collectedFacts:
            return self._deviceConnection.facts['model'].lower()
        else:
            self._deviceConnection.facts_refresh()
            self._collectedFacts = True
            return self._deviceConnection.facts['model'].lower()

    def getDeviceSerialNumber(self):
        if self._collectedFacts:
            return self._deviceConnection.facts['serialnumber']
        else:
            self._deviceConnection.facts_refresh()
            self._collectedFacts = True
            return self._deviceConnection.facts['serialnumber']
    
    def getL2Neighbors(self, brief=True):
        logger.debug('%s getL2Neighbors started', self._debugContext)
        junosEzTableLocation = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'conf', 'junosEznc')

        try:
            lldpTable = loadyaml(os.path.join(junosEzTableLocation, 'lldp.yaml'))['LLDPNeighborTable'] 
            table = lldpTable(self._deviceConnection)
            lldpData = table.get()
            links = {}
            for link in lldpData:
                # TODO: replace device1 with self name
                links[link.port1] = {'device1': None, 'port1': link.port1, 'device2': link.device2, 'port2': link.port2}
                
            logger.debug('%s LLDP: %s', self._debugContext, links)
            return links
        except RpcError as exc:
            logger.error('%s LLDP failure, %s', self._debugContext, exc)
            raise DeviceRpcFailed("device '%s': LLDPNeighborTable" % (self._ip), exc)
        except Exception as exc:
            logger.error('%s LLDP unknown error, %s', self._debugContext, exc)
            logger.debug('StackTrace: %s', traceback.format_exc())
            raise DeviceRpcFailed("device '%s': LLDPNeighborTable" % (self._ip), exc)
        finally:
            logger.debug('%s getL2Neighbors ended', self._debugContext)

    def getL3Neighbors(self, brief=True):
        logger.debug('%s getL3Neighbors started', self._debugContext)
        junosEzTableLocation = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'conf', 'junosEznc')

        try:
            bgpTable = loadyaml(os.path.join(junosEzTableLocation, 'BGP.yaml'))['BGPNeighborTable']
            table = bgpTable(self._deviceConnection)
            bgpData = table.get()
            links = []
            for link in bgpData:
                # strip ip
                device1Ip = stripPlusSignFromIpString(link.local_add)
                device2Ip = stripPlusSignFromIpString(link.peer_add)
                
                # TODO: replace device1/device2 with device name 
                if brief:
                    links.append({'device1': None, 'device1Ip': device1Ip, 'device1as': link.local_as, 'device2': None, 'device2Ip': device2Ip, 'device2as': link.peer_as, 'linkState': link.state})
                else:
                    links.append({'device1': None, 'device1Ip': device1Ip, 'device1as': link.local_as, 'device2': None, 'device2Ip': device2Ip, 'device2as': link.peer_as, 'inputMsgCount': link.in_msg,
                                  'outputMsgCount': link.out_msg, 'outQueueCount': link.out_queue, 'linkState': link.state, 'activeReceiveAcceptCount': (str(link.act_count) +'/' + str(link.rx_count) + '/' + str(link.acc_count)), 'flapCount': link.flap_count})
                    
            logger.debug('%s BGP: %s', self._debugContext, links)
            return links
        except RpcError as exc:
            logger.error('%s BGP Neighbor failure, %s', self._debugContext, exc)
            raise DeviceRpcFailed("device '%s': BGPNeighborTable" % (self._ip), exc)
        except Exception as exc:
            logger.error('%s BGP Neighbor unknown error, %s', self._debugContext, exc)
            logger.debug('StackTrace: %s', traceback.format_exc())
            raise DeviceRpcFailed("device '%s': BGPNeighborTable" % (self._ip), exc)
        finally:
            logger.debug('%s getL3Neighbors ended', self._debugContext)

    def updateConfig(self, config):
        logger.debug('%s updateConfig started', self._debugContext)

        configurationUnit = Config(self._deviceConnection)

        try:
            configurationUnit.lock()
            logger.debug('%s Locked config', self._debugContext)
        except LockError as exc:
            logger.error('%s updateConfig failed, LockError: %s, %s, %s', self._debugContext, exc, exc.errs, exc.rpc_error)
            raise DeviceRpcFailed('%s updateConfig failed' % (self._debugContext), exc)

        try:
            # make sure no changes are taken from CLI candidate config left over
            configurationUnit.rollback() 
            logger.debug('%s Rollbacked any other config', self._debugContext)
            configurationUnit.load(config, format='text')
            logger.debug('%s Load config as candidate', self._debugContext)

            #print configurationUnit.diff()
            #print configurationUnit.commit_check()

            configurationUnit.commit()
            logger.info('%s Committed config', self._debugContext)
        except CommitError as exc:
            logger.error('updateDeviceConfiguration failed for %s, CommitError: %s, %s, %s', self._debugContext, exc, exc.errs, exc.rpc_error)
            configurationUnit.rollback() 
            raise DeviceRpcFailed('updateDeviceConfiguration failed for %s' % (self._debugContext), exc)
        except Exception as exc:
            logger.error('updateDeviceConfiguration failed for %s, %s', self._debugContext, exc)
            logger.debug('StackTrace: %s', traceback.format_exc())
            configurationUnit.rollback() 
            raise DeviceRpcFailed('updateDeviceConfiguration failed for %s' % (self._debugContext), exc)
        finally:
            configurationUnit.unlock()
            logger.debug('%s updateConfig ended', self._debugContext)

    def createVCPort(self, slotPorts):
        '''
        :param slotPorts: list of touple, each containing slot and port
        '''
        for slot, port in slotPorts:
            rsp = self._deviceConnection.rpc.request_virtual_chassis_vc_port_set_pic_slot(pic_slot=str(slot), port=str(port))            
            error = rsp.find('../error/message')

            if error is not None:
                logger.debug('%s failed create vcp slot: %s, port: %d', self._debugContext,slot, port)
            else:
                logger.debug('%s created vcp slot: %s, port: %d', self._debugContext,slot, port)

    def deleteVCPort(self, slotPorts):
        '''
        :param slotPorts: list of touple, each containing slot and port
        '''
        for slot, port in slotPorts:
            rsp = self._deviceConnection.rpc.request_virtual_chassis_vc_port_delete_pic_slot(pic_slot=str(slot), port=str(port))            
            error = rsp.find('../error/message')

            if error is not None:
                logger.debug('%s failed delete vcp slot: %s, port: %d', self._debugContext,slot, port)
            else:
                logger.debug('%s deleted vcp slot: %s, port: %d', self._debugContext,slot, port)

def stripPlusSignFromIpString(ipString):
    pos = ipString.find('+')
    if pos != -1:
        return ipString[:pos]
    else:
        return ipString
