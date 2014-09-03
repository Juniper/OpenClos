'''
Created on Aug 26, 2014

@author: moloyc
'''
import sqlalchemy
from sqlalchemy.orm import sessionmaker, scoped_session

from model import Base

class Dao:
    def __init__(self, conf):
        if conf is not None and 'dbUrl' in conf:
            engine = sqlalchemy.create_engine(conf['dbUrl'], echo = conf.get('debugSql', False))  
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

    def getUniqueObjectByName(self, objectType, name):
        session = self.Session()
        try:
            return session.query(objectType).filter_by(name = name).one()
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

