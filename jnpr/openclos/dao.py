'''
Created on Aug 26, 2014

@author: moloyc
'''
import sqlalchemy
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.orm import exc
import util

from model import Base, Device, InterfaceDefinition, LeafSetting

moduleName = 'dao'
logger = None

class Dao:
    def __init__(self, conf):
        global logger
        logger = util.getLogger(moduleName)
            
        if conf is not None and 'dbUrl' in conf:
            if util.isSqliteUsed(conf):
                engine = sqlalchemy.create_engine(conf['dbUrl'], connect_args={}, echo = conf.get('debugSql', False))
            else:
                engine = sqlalchemy.create_engine(conf['dbUrl'], connect_args={}, echo = conf.get('debugSql', False),
                        isolation_level="READ COMMITTED")  
            Base.metadata.create_all(engine) 
            session_factory = sessionmaker(bind=engine)
            self.Session = scoped_session(session_factory)
        else:
            raise ValueError("Missing configuration parameter:'dbUrl'")
        
    # Don't remove session after each operation, it detaches the object from ORM,
    # which disables further operations on the object like lazy load of collection.
    # When thread dies, it gets GCed automatically
    def createObjects(self, objects):
        session = self.Session()
        try:
            session.add_all(objects)
            session.commit()
        finally:
            #self.Session.remove()
            pass
    
    def deleteObject(self, obj):
        session = self.Session()
        try:
            session.delete(obj)
            session.commit()
        finally:
            #self.Session.remove()
            pass

    def deleteObjects(self, objects):
        session = self.Session()
        try:
            for obj in objects:
                session.delete(obj)
            session.commit()
        finally:
            #self.Session.remove()
            pass

    def updateObjects(self, objects):
        session = self.Session()
        try:
            for obj in objects:
                session.merge(obj)
            session.commit()
        finally:
            #self.Session.remove()
            pass
    def getAll(self, objectType):
        session = self.Session()
        try:
            return session.query(objectType).order_by(objectType.name).all()
        finally:
            #self.Session.remove()
            pass
    
    def getObjectById(self, objectType, id):
        session = self.Session()
        try:
            return session.query(objectType).filter_by(id = id).one()
        finally:
            #self.Session.remove()
            pass


    def getUniqueObjectByName(self, objectType, name):
        session = self.Session()
        try:
            return session.query(objectType).filter_by(name = name).one()
        except (exc.NoResultFound, exc.MultipleResultsFound) as ex:
            logger.info(str(ex))
        finally:
            #self.Session.remove()
            pass

    def getObjectsByName(self, objectType, name):
        session = self.Session()
        try:
            return session.query(objectType).filter_by(name = name).all()
        finally:
            #self.Session.remove()
            pass

    def getIfdByDeviceNamePortName(self, deviceName, portName):
        session = self.Session()
        try:
            device = session.query(Device).filter_by(name = deviceName).one()
            return session.query(InterfaceDefinition).filter_by(device_id = device.id).filter_by(name = portName).one()
        except (exc.NoResultFound, exc.MultipleResultsFound) as ex:
            logger.info(str(ex))
        finally:
            #self.Session.remove()
            pass

    def getLeafSetting(self, podId, deviceFamily):
        session = self.Session()
        try:
            return session.query(LeafSetting).filter_by(pod_id = podId).filter_by(deviceFamily = deviceFamily).one()
        except (exc.NoResultFound) as ex:
            logger.info(str(ex))

    def getConnectedInterconnectIFDsFilterFakeOnes(self, device):
        '''
        Get interconnect IFDs except following ..
        1. no peer configured
        2. port name is uplink-* for device with known family 
        '''
        interconnectPorts = self.Session.query(InterfaceDefinition).filter(InterfaceDefinition.device_id == device.id)\
            .filter(InterfaceDefinition.peer != None).order_by(InterfaceDefinition.name_order_num).all()

        ports = []        
        for port in interconnectPorts:
            if device.family != 'unknown' and 'uplink-' in port.name:
                continue
            ports.append(port)
        return ports
