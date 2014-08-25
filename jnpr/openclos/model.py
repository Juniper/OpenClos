'''
Created on Jul 8, 2014

@author: moloyc

'''
import uuid
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship, backref
Base = declarative_base()

class ManagedElement(object):
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)
    def __str__(self):
        return str(self.__dict__)
    def __repr__(self):
        return self.__str__()
    @staticmethod
    def validateEnum(enumName, value, enumList):
        # Validate enumerated value, a restriction on string.
        error = False
        if isinstance(value, list):
            error = set(value) - set(enumList)
        else:
            error = value not in enumList
        if error:
            raise ValueError("%s('%s') must be one of %s" % (enumName, value, enumList))
    
class Pod(ManagedElement, Base):
    __tablename__ = 'pod'
    id = Column(String(60), primary_key=True)
    name = Column(String(100))
    spineCount = Column(Integer)
    spineDeviceType = Column(String(100))
    leafCount = Column(Integer)
    leafDeviceType = Column(String(100))
    interConnectPrefix = Column(String(32))
    vlanPrefix = Column(String(32))
    loopbackPrefix = Column(String(32))
    spineAS = Column(Integer)
    leafAS = Column(Integer)
    topologyType = Column(String(100))
    topology = Column(String(100))
    allocatedInterConnectBlock = Column(String(32))
    allocatedIrbBlock = Column(String(32))
    allocatedLoopbackBlock = Column(String(32))

    TopologyTypeEnum = ['3Stage', '5Stage', 'Pod']
  
    def __init__(self, name, **kwargs):
        '''
        Creates a Pod object from dict, if following fields are missing, it throws ValueError
        interConnectPrefix, vlanPrefix, loopbackPrefix, spineAS, leafAS
        '''
        self.id = str(uuid.uuid4())
        self.name = name
                   
        error = ''
        self.spineCount = kwargs.get('spineCount')
        if self.spineCount is None:
            error += 'spineCount, '
        self.spineDeviceType = kwargs.get('spineDeviceType')
        if self.spineDeviceType is None:
            error += 'spineDeviceType, '
        self.leafCount = kwargs.get('leafCount')
        if self.leafCount is None:
            error += 'leafCount, '
        self.leafDeviceType = kwargs.get('spineDeviceType')
        if self.leafDeviceType is None:
            error += 'leafDeviceType, '
        self.interConnectPrefix = kwargs.get('interConnectPrefix')
        if self.interConnectPrefix is None:
            error += 'interConnectPrefix, '
        self.vlanPrefix = kwargs.get('vlanPrefix')
        if self.vlanPrefix is None:
            error += 'vlanPrefix, '
        self.loopbackPrefix = kwargs.get('loopbackPrefix')
        if self.loopbackPrefix is None:
            error += 'loopbackPrefix, '
        if kwargs.has_key('spineAS'):
            self.spineAS = int(kwargs.get('spineAS'))
        else:
            error += 'spineAS, '
        if kwargs.has_key('leafAS'):
            self.leafAS = int(kwargs.get('leafAS'))
        else:
            error += 'leafAS, '
        self.topologyType = kwargs.get('topologyType')
        if self.topologyType is None:
            error += 'topologyType, '
        self.topology = kwargs.get('topology')
        
        if error != '':
            raise ValueError('Missing required fields: ' + error[:-2])
        super(Pod, self).__init__(**kwargs)
        
class Device(ManagedElement, Base):
    __tablename__ = 'device'
    id = Column(String(60), primary_key=True)
    name = Column(String(100))
    username = Column(String(100))
    pwd = Column(String(100))
    role = Column(String(32))
    managementIp = Column(String(32))
    family = Column(String(100))
    asn = Column(Integer)
    pod_id = Column(Integer, ForeignKey('pod.id'), nullable = False)
    pod = relationship("Pod", backref=backref('devices', order_by=name))
        
    def __init__(self, name, family, username, pwd, role, mgmtIp, pod):
        '''
        Creates Device object.
        '''
        self.id = str(uuid.uuid4())
        self.name = name
        self.family = family
        self.username = username
        self.pwd = pwd
        self.role = role
        self.managementIp = mgmtIp
        self.pod = pod
     
               
class Interface(Base):
    __tablename__ = 'interface'
    id = Column(String(60), primary_key=True)
    name = Column(String(100))
    type = Column(String(100))
    device_id = Column(Integer, ForeignKey('device.id'), nullable = False)
    device = relationship("Device",backref=backref('interfaces', order_by=name))
    peer_id = Column(Integer, ForeignKey('interface.id'))
    peer = relationship('Interface', foreign_keys=[peer_id], uselist=False, post_update=True, )
    layer_below_id = Column(Integer, ForeignKey('interface.id'))
    layerAboves = relationship('Interface', foreign_keys=[layer_below_id])

    __mapper_args__ = {
        'polymorphic_identity':'interface',
        'polymorphic_on':type
    }
        
    def __init__(self, name, device):
        self.id = str(uuid.uuid4())
        self.name = name
        self.device = device
        
class InterfaceLogical(Interface):
    __tablename__ = 'IFL'
    id = Column(String(60), ForeignKey('interface.id' ), primary_key=True)
    ipaddress = Column(String(40))
    mtu = Column(Integer)
    
    __mapper_args__ = {
        'polymorphic_identity':'logical',
    }
    
    def __init__(self, name, device, ipaddress=None, mtu=0):
        '''
        Creates Logical Interface object.
        ipaddress is optional so that it can be allocated later
        mtu is optional, default value is taken from global setting
        '''
        super(InterfaceLogical, self).__init__(name, device)
        self.ipaddress = ipaddress
        self.mtu = mtu

class InterfaceDefinition(Interface):
    __tablename__ = 'IFD'
    id = Column(String(60), ForeignKey('interface.id' ), primary_key=True)
    mtu = Column(Integer)
        
    __mapper_args__ = {
        'polymorphic_identity':'physical',
    }

    def __init__(self, name, device,  mtu=0):
        
        super(InterfaceDefinition, self).__init__(name, device)
        self.mtu = mtu
        
