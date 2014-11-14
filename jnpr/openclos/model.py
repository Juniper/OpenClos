'''
Created on Jul 8, 2014

@author: moloyc

'''
import uuid
import math
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, ForeignKey, Enum, BLOB
from sqlalchemy.orm import relationship, backref
from netaddr import IPAddress, IPNetwork, AddrFormatError
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
    description = Column(String(256))
    spineCount = Column(Integer)
    spineDeviceType = Column(String(100))
    leafUplinkcountMustBeUp = Column(Integer) 
    leafCount = Column(Integer)
    leafDeviceType = Column(String(100))
    hostOrVmCountPerLeaf = Column(Integer)
    interConnectPrefix = Column(String(32))
    vlanPrefix = Column(String(32))
    loopbackPrefix = Column(String(32))
    managementPrefix = Column(String(32))
    spineAS = Column(Integer)
    leafAS = Column(Integer)
    topologyType = Column(Enum('threeStage', 'fiveStageRealEstate', 'fiveStagePerformance'))
    outOfBandAddressList = Column(String(512))  # comma separated values
    outOfBandGateway =  Column(String(32))
    spineJunosImage = Column(String(126))
    leafJunosImage = Column(String(126))
    allocatedInterConnectBlock = Column(String(32))
    allocatedIrbBlock = Column(String(32))
    allocatedLoopbackBlock = Column(String(32))
    allocatedSpineAS = Column(Integer)
    allocatefLeafAS = Column(Integer)
    inventoryData = Column(String(2048))
    leafGenericConfig = Column(BLOB)
    state = Column(Enum('unknown', 'created', 'updated', 'cablingDone', 'deviceConfigDone', 'ztpConfigDone', 'deployed', 'L2Verified', 'L3Verified'))

    def __init__(self, name, **kwargs):
        '''
        Creates a Pod object from dict, if following fields are missing, it throws ValueError
        interConnectPrefix, vlanPrefix, loopbackPrefix, spineAS, leafAS
        '''
        super(Pod, self).__init__(**kwargs)
        self.update(None, name, **kwargs)
        
    def update(self, id, name, **kwargs):
        '''
        Updates a Pod ORM object from dict, it updates only following fields.
        spineCount, leafCount
        '''
        if id is not None:
            self.id = id
        elif kwargs.has_key('id'):
            self.id = kwargs.get('id')
        else:
            self.id = str(uuid.uuid4())
        
        if name is not None:
            self.name = name
        elif kwargs.has_key('name'):
            self.name = kwargs.get('name')
        
        if kwargs.has_key('description'):
            self.description = kwargs.get('description')
        if kwargs.has_key('spineCount'):
            self.spineCount = kwargs.get('spineCount')
        if kwargs.has_key('spineDeviceType'):
            self.spineDeviceType = kwargs.get('spineDeviceType')
        if kwargs.has_key('leafCount'):
            self.leafCount = kwargs.get('leafCount')
        if kwargs.has_key('leafDeviceType'):
            self.leafDeviceType = kwargs.get('leafDeviceType')
        if kwargs.has_key('leafUplinkcountMustBeUp'):
            self.leafUplinkcountMustBeUp = kwargs.get('leafUplinkcountMustBeUp')
        else:
            self.leafUplinkcountMustBeUp = self.calculateLeafUplinkcountMustBeUp()
        if kwargs.has_key('hostOrVmCountPerLeaf'):
            self.hostOrVmCountPerLeaf = kwargs.get('hostOrVmCountPerLeaf')
        if kwargs.has_key('interConnectPrefix'):
            self.interConnectPrefix = kwargs.get('interConnectPrefix')
        if kwargs.has_key('vlanPrefix'):
            self.vlanPrefix = kwargs.get('vlanPrefix')
        if kwargs.has_key('loopbackPrefix'):
            self.loopbackPrefix = kwargs.get('loopbackPrefix')
        if kwargs.has_key('managementPrefix'):
            self.managementPrefix = kwargs.get('managementPrefix')
        if kwargs.has_key('spineAS'):
            self.spineAS = int(kwargs.get('spineAS'))
        if kwargs.has_key('leafAS'):
            self.leafAS = int(kwargs.get('leafAS'))
        if kwargs.has_key('topologyType'):
            self.topologyType = kwargs.get('topologyType')
        if kwargs.has_key('outOfBandAddressList'):
            addressList = kwargs.get('outOfBandAddressList')
            self.outOfBandAddressList = ','.join(addressList)
            kwargs.pop('outOfBandAddressList')
        if kwargs.has_key('outOfBandGateway'):
            self.outOfBandGateway = kwargs.get('outOfBandGateway')
        if kwargs.has_key('spineJunosImage'):
            self.spineJunosImage = kwargs.get('spineJunosImage')
        if kwargs.has_key('leafJunosImage'):
            self.leafJunosImage = kwargs.get('leafJunosImage')
        
        if self.state is None:
            self.state = 'unknown'

    def calculateLeafUplinkcountMustBeUp(self):
        if self.spineCount is not None:
            count = int(math.ceil(float(self.spineCount)/2))
            if count < 2:
                count = 2
            return count
        
    '''
    Additional validations - 
    1. Spine ASN less then leaf ASN
    2. Add range check
    '''        
    def validate(self):
        self.validateRequiredFields()
        self.validateIPaddr()  
        if self.leafUplinkcountMustBeUp < 2 or self.leafUplinkcountMustBeUp > self.spineCount:
            raise ValueError('leafUplinkcountMustBeUp(%s) should be between 2 and spineCount(%s)' \
                % (self.leafUplinkcountMustBeUp, self.spineCount))
        
    def validateRequiredFields(self):
        
        error = ''
        if self.spineCount is None:
            error += 'spineCount, '
        if self.spineDeviceType is None:
            error += 'spineDeviceType, '
        if self.leafCount is None:
            error += 'leafCount, '
        if self.leafDeviceType is None:
            error += 'leafDeviceType, '
        if self.hostOrVmCountPerLeaf is None:
            error += 'hostOrVmCountPerLeaf, '
        if self.interConnectPrefix is None:
            error += 'interConnectPrefix, '
        if self.vlanPrefix is None:
            error += 'vlanPrefix, '
        if self.loopbackPrefix is None:
            error += 'loopbackPrefix, '
        if self.managementPrefix is None:
            error += 'managementPrefix, '
        if self.spineAS is None:
            error += 'spineAS,'
        if self.leafAS is None:
            error += 'leafAS, '
        if self.topologyType is None:
            error += 'topologyType'
        if error != '':
            raise ValueError('Missing required fields: ' + error)
        
    def validateIPaddr(self):   
        error = ''     
 
        try:
            IPAddress(self.interConnectPrefix)  
        except AddrFormatError:
                error += 'interConnectPrefix, ' 
        try:
            IPAddress(self.vlanPrefix)  
        except AddrFormatError:
                error += 'vlanPrefix, '
        try:
            IPAddress(self.loopbackPrefix)  
        except AddrFormatError:
                error += 'loopbackPrefix'
        try:
            IPNetwork(self.managementPrefix)  
        except AddrFormatError:
                error += 'managementPrefix'
        if error != '':
            raise ValueError('invalid IP format: ' + error)
        
class Device(ManagedElement, Base):
    __tablename__ = 'device'
    id = Column(String(60), primary_key=True)
    name = Column(String(100))
    username = Column(String(100))
    password = Column(String(100))
    role = Column(String(32))
    macAddress = Column(String(32))
    managementIp = Column(String(32))
    family = Column(String(100))
    asn = Column(Integer)
    l2Status = Column(Enum('unknown', 'processing', 'good', 'error'), default = 'unknown')
    l2StatusReason = Column(String(256)) # will be populated only when status is error
    l3Status = Column(Enum('unknown', 'processing', 'good', 'error'), default = 'unknown')
    l3StatusReason = Column(String(256)) # will be populated only when status is error
    configStatus = Column(Enum('unknown', 'processing', 'good', 'error'), default = 'unknown')
    configStatusReason = Column(String(256)) # will be populated only when status is error
    config = Column(BLOB)
    pod_id = Column(String(60), ForeignKey('pod.id'), nullable = False)
    pod = relationship("Pod", backref=backref('devices', order_by=name, cascade='all, delete, delete-orphan'))
        
    def __init__(self, name, family, username, password, role, mac, mgmtIp, pod):
        '''
        Creates Device object.
        '''
        self.id = str(uuid.uuid4())
        self.name = name
        self.family = family
        self.username = username
        self.password = password
        self.role = role
        self.macAddress = mac
        self.managementIp = mgmtIp
        self.pod = pod
               
class Interface(ManagedElement, Base):
    __tablename__ = 'interface'
    id = Column(String(60), primary_key=True)
    # getting list of interface order by name returns 
    # et-0/0/0, et-0/0/1, et-0/0/11, et/0/0/12, to fix this sequencing
    # adding order_number, so that the list would be et-0/0/0, et-0/0/1, et-0/0/2, et/0/0/3    
    name = Column(String(100))
    name_order_num = Column(Integer)
    type = Column(String(100))
    device_id = Column(String(60), ForeignKey('device.id'), nullable = False)
    device = relationship("Device",backref=backref('interfaces', order_by=name, cascade='all, delete, delete-orphan'))
    peer_id = Column(String(60), ForeignKey('interface.id'))
    peer = relationship('Interface', foreign_keys=[peer_id], uselist=False, post_update=True, )
    layer_below_id = Column(String(60), ForeignKey('interface.id'))
    layerAboves = relationship('Interface', foreign_keys=[layer_below_id])

    __mapper_args__ = {
        'polymorphic_identity':'interface',
        'polymorphic_on':type
    }
        
    def __init__(self, name, device):
        self.id = str(uuid.uuid4())
        self.name = name
        self.device = device
        if name.split('/')[-1].isdigit():
            self.name_order_num = int(name.split('/')[-1])
        
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
    role = Column(String(60))
    mtu = Column(Integer)
    lldpStatus = Column(Enum('unknown', 'good', 'error'), default = 'unknown') 
        
    __mapper_args__ = {
        'polymorphic_identity':'physical',
    }

    def __init__(self, name, device, role, mtu=0):
        super(InterfaceDefinition, self).__init__(name, device)
        self.mtu = mtu
        self.role = role
