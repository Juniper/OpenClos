'''
Created on Aug 26, 2014

@author: moloyc
'''
import sqlalchemy
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.orm import exc
import logging 
import contextlib
import importlib

from model import Base, Device, InterfaceDefinition, LeafSetting, Counter
from loader import DeviceSku
from common import SingletonBase
from loader import loadLoggingConfig
from exception import InvalidConfiguration

moduleName = 'dao'
loadLoggingConfig(appName=moduleName)
logger = logging.getLogger(moduleName)


class AbstractDao(SingletonBase):
    def __init__(self):
        debugSql = False
        if logger.isEnabledFor(logging.DEBUG):
            debugSql = True
            
        self.__engine = None
        self.__sessionFactory = None
        dbUrl = self._getDbUrl()
        
        # load plugin data models so create_all will create all tables defined in plugins
        self.loadPluginDataModels()
        
        if 'sqlite:' in dbUrl:
            self.__engine = sqlalchemy.create_engine(dbUrl, echo=debugSql)
        elif 'mysql:' in dbUrl:
            self.__engine = sqlalchemy.create_engine(dbUrl, echo=debugSql,
                         pool_recycle=7200, isolation_level="READ COMMITTED")
        else:
            logger.error('Unsupported DB dialect: %s' % dbUrl)
            raise InvalidConfiguration('Unsupported DB dialect: %s' % dbUrl)
        
        Base.metadata.create_all(self.__engine) 
        self.__sessionFactory = sessionmaker(bind=self.__engine)
        logger.debug('Dao is initialized with Engine')

    def __del__(self):
        if self.__engine:
            self.__sessionFactory.close_all()
            self.__engine.dispose()
    
    @contextlib.contextmanager
    def getReadSession(self):
        try:
            session = scoped_session(self.__sessionFactory)
            yield session
        except Exception as ex:
            logger.error(ex)
            raise
        finally:
            session.remove()

    @contextlib.contextmanager
    def getReadWriteSession(self):
        try:
            session = scoped_session(self.__sessionFactory)
            yield session
            session.commit()
        except Exception as ex:
            session.rollback()
            logger.error(ex)
            raise
        finally:
            session.remove()
    
    def _getRawSession(self):
        return scoped_session(self.__sessionFactory)
    
    def _getDbUrl(self):
        raise NotImplementedError

    def loadPluginDataModels(self):
        pass
    
    def createObjects(self, session, objects):
        session.add_all(objects)
    
    def createObjectsAndCommitNow(self, session, objects):
        try:
            session.add_all(objects)
            session.commit()
        except Exception as ex:
            logger.error(ex)
            session.rollback()
            #raise

    def deleteObject(self, session, obj):
        session.delete(obj)

    def deleteObjects(self, session, objects):
        for obj in objects:
            session.delete(obj)

    def updateObjects(self, session, objects):
        for obj in objects:
            session.merge(obj)

    def updateObjectsAndCommitNow(self, session, objects):
        try:
            for obj in objects:
                session.merge(obj)
            session.commit()
        except Exception as ex:
            logger.error(ex)
            session.rollback()
            #raise

    def getAll(self, session, objectType):
        return session.query(objectType).order_by(objectType.name).all()
    
    def getObjectById(self, session, objectType, id):
        return session.query(objectType).filter_by(id=id).one()

    def getUniqueObjectByName(self, session, objectType, name):
        try:
            return session.query(objectType).filter_by(name=name).one()
        except (exc.NoResultFound, exc.MultipleResultsFound) as ex:
            logger.info(str(ex))

    def getObjectsByName(self, session, objectType, name):
        return session.query(objectType).filter_by(name=name).all()

    def getIfdByDeviceNamePortName(self, session, deviceName, portName):
        try:
            device = session.query(Device).filter_by(name=deviceName).one()
            return session.query(InterfaceDefinition).filter_by(device_id=device.id).filter_by(name=portName).one()
        except (exc.NoResultFound, exc.MultipleResultsFound) as ex:
            logger.info(str(ex))

    def getLeafSetting(self, session, podId, deviceFamily):
        try:
            return session.query(LeafSetting).filter_by(pod_id=podId).filter_by(deviceFamily=deviceFamily).one()
        except (exc.NoResultFound) as ex:
            logger.info(str(ex))

    def getConnectedInterconnectIFDsFilterFakeOnes(self, session, device):
        '''
        Get interconnect IFDs except following ..
        1. no peer configured
        2. port name is uplink-* for device with known family 
        '''
        interconnectPorts = session.query(InterfaceDefinition).filter(InterfaceDefinition.device_id == device.id)\
            .filter(InterfaceDefinition.peer != None)\
            .filter((InterfaceDefinition.role == 'uplink') | (InterfaceDefinition.role == 'downlink'))\
            .order_by(InterfaceDefinition.sequenceNum).all()

        ports = []        
        for port in interconnectPorts:
            if device.family != 'unknown' and 'uplink-' in port.name:
                continue
            ports.append(port)
        return ports

    def getPortNamesForCustomizedDeviceSku(self, session, device):
        if device.role == 'spine' and device.pod.spineDownlinkRegex:
            return {'uplinkPorts': DeviceSku.portRegexCsvListToList(device.pod.spineUplinkRegex), 
                    'downlinkPorts': DeviceSku.portRegexCsvListToList(device.pod.spineDownlinkRegex)}            

        if device.role == 'leaf':
            leafSetting = self.getLeafSetting(session, device.pod.id, device.family)
            if leafSetting and leafSetting.uplinkRegex and leafSetting.downlinkRegex:
                return {'uplinkPorts': DeviceSku.portRegexCsvListToList(leafSetting.uplinkRegex), 
                        'downlinkPorts': DeviceSku.portRegexCsvListToList(leafSetting.downlinkRegex)}

        return {'uplinkPorts': [], 'downlinkPorts': []}

    def incrementAndGetCounter(self, counterName):
        count = 1
        with self.getReadWriteSession() as session:
            try:
                count = session.query(Counter).filter(Counter.name == counterName).one().count + 1
                session.merge(Counter(counterName, count))
            except (exc.NoResultFound):
                session.add(Counter(counterName, count))
            session.commit()
        return count

class Dao(AbstractDao):
    def _getDbUrl(self):
        from loader import OpenClosProperty
        return OpenClosProperty().getDbUrl()
    
    def loadPluginDataModels(self):
        from loader import OpenClosProperty
        conf = OpenClosProperty().getProperties()
        # iterate 'plugin' section of openclos.yaml and install routes on all plugins
        if 'plugin' in conf:
            plugins = conf['plugin']
            for plugin in plugins:
                moduleName = plugin['package'] + '.' + plugin['name'] + 'Model'
                logger.info("loading plugin data model '%s'", moduleName) 
                try:
                    pluginModule = importlib.import_module(moduleName)
                except (AttributeError, ImportError) as err:
                    logger.error("Failed to load plugin data model '%s'. Error: %s", moduleName, err) 
