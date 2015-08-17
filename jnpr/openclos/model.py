'''
Created on Jul 8, 2014

@author: moloyc

'''
import uuid
import math
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, BigInteger, String, ForeignKey, Enum, UniqueConstraint, Index

import propLoader
if propLoader.OpenClosProperty().isSqliteUsed():
    from sqlalchemy import BLOB
else:
    from sqlalchemy.dialects.mysql import MEDIUMBLOB as BLOB


from sqlalchemy.orm import relationship, backref
from netaddr import IPAddress, IPNetwork, AddrFormatError
from crypt import Cryptic
import util
from exception import EnumerationMismatch, InvalidUplinkThreshold, MissingMandatoryAttribute, InvalidIpFormat

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
            raise EnumerationMismatch("%s('%s') must be one of %s" % (enumName, value, enumList))
    
class Pod(ManagedElement, Base):
    __tablename__ = 'pod'
    id = Column(String(60), primary_key=True)
    name = Column(String(255), index=True, nullable = False)
    description = Column(String(256))
    spineCount = Column(Integer)
    spineDeviceType = Column(String(100))
    spineJunosImage = Column(String(126))
    leafCount = Column(Integer)
    leafUplinkcountMustBeUp = Column(Integer)
    leafSettings = relationship("LeafSetting", order_by='LeafSetting.deviceFamily', cascade='all, delete, delete-orphan')
    hostOrVmCountPerLeaf = Column(Integer)
    interConnectPrefix = Column(String(32))
    vlanPrefix = Column(String(32))
    loopbackPrefix = Column(String(32))
    managementPrefix = Column(String(32))
    managementStartingIP = Column(String(32))
    managementMask = Column(Integer)
    spineAS = Column(BigInteger)
    leafAS = Column(BigInteger)
    topologyType = Column(Enum('threeStage', 'fiveStageRealEstate', 'fiveStagePerformance'))
    outOfBandAddressList = Column(String(512))  # comma separated values
    outOfBandGateway =  Column(String(32))
    allocatedInterConnectBlock = Column(String(32))
    allocatedIrbBlock = Column(String(32))
    allocatedLoopbackBlock = Column(String(32))
    allocatedSpineAS = Column(BigInteger)
    allocatefLeafAS = Column(BigInteger)
    inventoryData = Column(String(2048))
    encryptedPassword = Column(String(100)) # 2-way encrypted
    cryptic = Cryptic()
    cablingPlan = relationship("CablingPlan", uselist=False, cascade='all, delete, delete-orphan')

    def __init__(self, name, podDict):
        '''
        Creates a Pod object from dict
        '''
        super(Pod, self).__init__()
        self.update(None, name, podDict)
    
    def copyAdditionalFields(self, podDict):
        '''
        Hook for enhancements, add additional fields 
        and get initialized
        '''
    
    def update(self, id, name, podDict):
        '''
        Updates a Pod ORM object from dict
        '''
        if id:
            self.id = id
        elif podDict.get('id'):
            self.id = podDict.get('id')
        else:
            self.id = str(uuid.uuid4())
        
        if name is not None:
            self.name = name
        elif 'name' in podDict:
            self.name = podDict.get('name')
        
        self.description = podDict.get('description')
        self.spineCount = podDict.get('spineCount')
        self.spineDeviceType = podDict.get('spineDeviceType')
        self.leafCount = podDict.get('leafCount')
        leafSettings = podDict.get('leafSettings')
        if leafSettings is not None:
            self.leafSettings = []
            for leafSetting in leafSettings:
                junosImage = leafSetting.get('junosImage')
                self.leafSettings.append(LeafSetting(leafSetting['deviceType'], self.id, junosImage = junosImage))
        
        self.leafUplinkcountMustBeUp = podDict.get('leafUplinkcountMustBeUp')
        if self.leafUplinkcountMustBeUp is None:
            self.leafUplinkcountMustBeUp = 2
        self.hostOrVmCountPerLeaf = podDict.get('hostOrVmCountPerLeaf')
        self.interConnectPrefix = podDict.get('interConnectPrefix')
        self.vlanPrefix = podDict.get('vlanPrefix')
        self.loopbackPrefix = podDict.get('loopbackPrefix')
        self.managementPrefix = podDict.get('managementPrefix')
        self.managementStartingIP = podDict.get('managementStartingIP')
        self.managementMask = podDict.get('managementMask')
        spineAS = podDict.get('spineAS')
        if spineAS is not None:
            self.spineAS = int(spineAS)
        leafAS = podDict.get('leafAS')
        if leafAS is not None:
            self.leafAS = int(leafAS)
        self.topologyType = podDict.get('topologyType')
        
        outOfBandAddressList = podDict.get('outOfBandAddressList')
        if outOfBandAddressList is not None and len(outOfBandAddressList) > 0:
            addressList = []
            if isinstance(outOfBandAddressList, list) == True:
                addressList = outOfBandAddressList
            else:
                addressList.append(outOfBandAddressList)
            self.outOfBandAddressList = ','.join(addressList)
        self.outOfBandGateway = podDict.get('outOfBandGateway')
        self.spineJunosImage = podDict.get('spineJunosImage')
            
        devicePassword = podDict.get('devicePassword')
        if devicePassword is not None and len(devicePassword) > 0:
            self.encryptedPassword = self.cryptic.encrypt(devicePassword)
        self.copyAdditionalFields(podDict)
        
    def calculateEffectiveLeafUplinkcountMustBeUp(self):
        # if user configured a value, use it always 
        if self.leafUplinkcountMustBeUp is not None and self.leafUplinkcountMustBeUp > 0:
            return self.leafUplinkcountMustBeUp

        deployedSpines = 0
        for device in self.devices:
            if device.role == 'spine' and device.deployStatus == 'deploy':
                deployedSpines += 1
                
        count = int(math.ceil(float(deployedSpines)/2))
        if count < 2:
            count = 2

        return count
        
    def getCleartextPassword(self):
        '''
        Return decrypted password
        '''
        if self.encryptedPassword is not None and len(self.encryptedPassword) > 0:
            return self.cryptic.decrypt(self.encryptedPassword)
        else:
            return None
            
    def getHashPassword(self):
        '''
        Return hashed password
        '''
        cleartext = self.getCleartextPassword()
        if cleartext is not None:
            return self.cryptic.hashify(cleartext)
        else:
            return None
            
    '''
    Additional validations - 
    1. Spine ASN less then leaf ASN
    2. Add range check
    '''        
    def validate(self):
        self.validateRequiredFields()
        self.validateIPaddr()  
        if self.leafUplinkcountMustBeUp < 2 or self.leafUplinkcountMustBeUp > self.spineCount:
            raise InvalidUplinkThreshold('leafUplinkcountMustBeUp(%s) should be between 2 and spineCount(%s)' % (self.leafUplinkcountMustBeUp, self.spineCount))
        
    def validateRequiredFields(self):
        
        error = ''
        if self.spineCount is None:
            error += 'spineCount, '
        if self.spineDeviceType is None:
            error += 'spineDeviceType, '
        if self.leafCount is None:
            error += 'leafCount, '
        if self.leafSettings is None or len(self.leafSettings) == 0:
            error += 'leafSettings, '
        if self.hostOrVmCountPerLeaf is None:
            error += 'hostOrVmCountPerLeaf, '
        if self.interConnectPrefix is None:
            error += 'interConnectPrefix, '
        if self.vlanPrefix is None:
            error += 'vlanPrefix, '
        if self.loopbackPrefix is None:
            error += 'loopbackPrefix, '
        if self.managementPrefix is None and (self.managementStartingIP is None or self.managementMask is None):
            error += 'managementPrefix or (managementStartingIP, managementMask), '
        if self.spineAS is None:
            error += 'spineAS, '
        if self.leafAS is None:
            error += 'leafAS, '
        if self.topologyType is None:
            error += 'topologyType, '
        if self.encryptedPassword is None:
            error += 'devicePassword'
        if error != '':
            raise MissingMandatoryAttribute('Missing required fields: ' + error)
        
    def validateIPaddr(self):   
        error = ''     
 
        try:
            IPNetwork(self.interConnectPrefix)  
        except AddrFormatError:
                error += 'interConnectPrefix, ' 
        try:
            IPNetwork(self.vlanPrefix)  
        except AddrFormatError:
                error += 'vlanPrefix, '
        try:
            IPNetwork(self.loopbackPrefix)  
        except AddrFormatError:
                error += 'loopbackPrefix'
        try:
            if self.managementPrefix is not None:
                IPNetwork(self.managementPrefix)  
        except AddrFormatError:
                error += 'managementPrefix'
        try:
            if self.managementStartingIP is not None:
                IPAddress(self.managementStartingIP)  
        except AddrFormatError:
                error += 'managementStartingIP'
        if error != '':
            raise InvalidIpFormat('invalid IP format: ' + error)

class LeafSetting(ManagedElement, Base):
    __tablename__ = 'leafSetting'
    deviceFamily = Column(String(100), primary_key=True)
    pod_id = Column(String(60), ForeignKey('pod.id'), nullable = False, primary_key=True)
    junosImage = Column(String(126))
    config = Column(BLOB)

    def __init__(self, deviceFamily, podId, junosImage = None, config = None):
        self.deviceFamily = deviceFamily
        self.pod_id = podId
        self.junosImage = junosImage
        self.config = config
    
class CablingPlan(ManagedElement, Base):
    __tablename__ = 'cablingPlan'
    pod_id = Column(String(60), ForeignKey('pod.id'), nullable = False, primary_key=True)
    json = Column(BLOB)
    dot = Column(BLOB)

    def __init__(self, podId, json = None, dot = None):
        self.pod_id = podId
        self.json = json
        self.dot = dot

class Device(ManagedElement, Base):
    __tablename__ = 'device'
    id = Column(String(60), primary_key=True)
    name = Column(String(255), nullable = False)
    username = Column(String(100), default = 'root')
    encryptedPassword = Column(String(100)) # 2-way encrypted
    role = Column(Enum('spine', 'leaf'))
    macAddress = Column(String(32))
    serialNumber = Column(String(32))
    managementIp = Column(String(32))
    family = Column(String(100), default = 'unknown')
    asn = Column(BigInteger)
    l2Status = Column(Enum('unknown', 'processing', 'good', 'error'), default = 'unknown')
    l2StatusReason = Column(String(256)) # will be populated only when status is error
    l3Status = Column(Enum('unknown', 'processing', 'good', 'error'), default = 'unknown')
    l3StatusReason = Column(String(256)) # will be populated only when status is error
    configStatus = Column(Enum('unknown', 'processing', 'good', 'error'), default = 'unknown')
    configStatusReason = Column(String(256)) # will be populated only when status is error
    config = relationship("DeviceConfig", uselist=False, cascade='all, delete, delete-orphan')
    pod_id = Column(String(60), ForeignKey('pod.id'), nullable = False)
    pod = relationship("Pod", backref=backref('devices', order_by=name, cascade='all, delete, delete-orphan'))
    deployStatus = Column(Enum('deploy', 'provision'), default = 'provision')
    cryptic = Cryptic()
    __table_args__ = (
        Index('pod_id_name_uindex', 'pod_id', 'name', unique=True),
    )
    
                
    def __init__(self, name, family, username, password, role, macAddress, managementIp, pod, deployStatus=None, serialNumber=None):
        '''
        Creates Device object.
        '''
        self.id = str(uuid.uuid4())
        self.name = name
        self.family = family
        self.username = username
        if password is not None and len(password) > 0:
            self.encryptedPassword = self.cryptic.encrypt(password)
        elif pod is not None:
            self.encryptedPassword = pod.encryptedPassword
        self.role = role
        self.macAddress = macAddress
        self.managementIp = managementIp
        self.pod = pod
        self.deployStatus = deployStatus
        self.serialNumber = serialNumber
        
    def update(self, name, family, username, password, macAddress, deployStatus, serialNumber):
        '''
        Updates Device object.
        '''
        self.name = name
        self.username = username
        self.family = family
        if password is not None and len(password) > 0:
            self.encryptedPassword = self.cryptic.encrypt(password)
        self.macAddress = macAddress
        self.deployStatus = deployStatus
        self.serialNumber = serialNumber
    
    def getCleartextPassword(self):
        '''
        Return decrypted password
        '''
        if self.encryptedPassword is not None and len(self.encryptedPassword) > 0:
            return self.cryptic.decrypt(self.encryptedPassword)
        else:
            return self.pod.getCleartextPassword()
            
    def getHashPassword(self):
        '''
        Return hashed password
        '''
        cleartext = self.getCleartextPassword()
        if cleartext is not None:
            return self.cryptic.hashify(cleartext)
        else:
            return None

class DeviceConfig(ManagedElement, Base):
    __tablename__ = 'deviceConfig'
    device_id = Column(String(60), ForeignKey('device.id'), nullable = False, primary_key=True)
    config = Column(BLOB)

    def __init__(self, deviceId, config):
        self.device_id = deviceId
        self.config = config
            
class Interface(ManagedElement, Base):
    __tablename__ = 'interface'
    id = Column(String(60), primary_key=True)
    # getting list of interface order by name returns 
    # et-0/0/0, et-0/0/1, et-0/0/11, et/0/0/12, to fix this sequencing
    # adding order_number, so that the list would be et-0/0/0, et-0/0/1, et-0/0/2, et/0/0/3    
    name = Column(String(100), nullable = False)
    sequenceNum = Column(BigInteger, nullable = False)
    type = Column(String(100))
    device_id = Column(String(60), ForeignKey('device.id'), nullable = False)
    device = relationship("Device",backref=backref('interfaces', order_by=sequenceNum, cascade='all, delete, delete-orphan'))
    peer_id = Column(String(60), ForeignKey('interface.id'))
    peer = relationship('Interface', foreign_keys=[peer_id], uselist=False, post_update=True, )
    layer_below_id = Column(String(60), ForeignKey('interface.id'))
    layerAboves = relationship('Interface', foreign_keys=[layer_below_id])
    deployStatus = Column(Enum('deploy', 'provision'), default = 'provision')
    __table_args__ = (
        Index('device_id_sequence_num_uindex', 'device_id', 'sequenceNum', unique=True),
    )

    __mapper_args__ = {
        'polymorphic_identity':'interface',
        'polymorphic_on':type
    }
        
    def __init__(self, name, device, deployStatus=None):
        self.id = str(uuid.uuid4())
        self.name = name
        self.device = device
        self.deployStatus = deployStatus
        self.sequenceNum = util.interfaceNameToUniqueSequenceNumber(self.name)

    def updateName(self, name):
        self.name = name
        self.sequenceNum = util.interfaceNameToUniqueSequenceNumber(self.name)
        
        
class InterfaceLogical(Interface):
    __tablename__ = 'IFL'
    id = Column(String(60), ForeignKey('interface.id' ), primary_key=True)
    ipaddress = Column(String(40))
    mtu = Column(Integer)
    
    __mapper_args__ = {
        'polymorphic_identity':'logical',
    }
    
    def __init__(self, name, device, ipaddress=None, mtu=0, deployStatus=None):
        '''
        Creates Logical Interface object.
        ipaddress is optional so that it can be allocated later
        mtu is optional, default value is taken from global setting
        '''
        super(InterfaceLogical, self).__init__(name, device, deployStatus)
        self.ipaddress = ipaddress
        self.mtu = mtu

class InterfaceDefinition(Interface):
    __tablename__ = 'IFD'
    id = Column(String(60), ForeignKey('interface.id' ), primary_key=True)
    role = Column(String(60))
    mtu = Column(Integer)
    status = Column(Enum('unknown', 'good', 'error'), default = 'unknown') 
        
    __mapper_args__ = {
        'polymorphic_identity':'physical',
    }

    def __init__(self, name, device, role, mtu=0, deployStatus=None):
        super(InterfaceDefinition, self).__init__(name, device, deployStatus)
        self.mtu = mtu
        self.role = role

class TrapGroup(ManagedElement, Base):
    __tablename__ = 'trapGroup'
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), index=True, nullable = False)
    targetAddress = Column(String(60))
    port = Column(Integer, default = 162)

    def __init__ (self, name, targetAddress, port):
        self.name = name
        self.targetAddress = targetAddress
        self.port = port
        
class AdditionalLink(ManagedElement, Base):
    __tablename__ = 'additionalLink'
    id = Column(String(60), primary_key=True)
    device1 = Column(String(60)) # free form in case device does not exist in device table
    port1 = Column(String(100))
    device2 = Column(String(60)) # free form in case device does not exist in device table
    port2 = Column(String(100))
    lldpStatus = Column(Enum('unknown', 'good', 'error'), default = 'unknown') 
    __table_args__ = (
        UniqueConstraint('device1', 'port1', name='device1_port1_uc'),
    )
        
    def __init__(self, device1, port1, device2, port2, lldpStatus='unknown'):
        self.id = str(uuid.uuid4())
        self.device1 = device1
        self.port1 = port1
        self.device2 = device2
        self.port2 = port2
        self.lldpStatus = lldpStatus

class BgpLink(ManagedElement, Base):
    __tablename__ = 'bgpLink'
    id = Column(String(60), primary_key=True)
    device_id=Column(String(60))
    pod_id=Column(String(60))
    device1 = Column(String(100)) # free form in case device does not exist in device table
    device1Ip = Column(String(60))
    device1As = Column(Integer)
    device2 = Column(String(100))# free form in case device does not exist in device table
    device2Ip = Column(String(60))
    device2As = Column(Integer)
    input_msg_count = Column(Integer)
    output_msg_count = Column(Integer)
    out_queue_count = Column(Integer)
    flap_count = Column(Integer)
    link_state = Column(String(100),default = 'unknown')
    act_rx_acc_route_count = Column(String(100))


    def __init__(self, podId, deviceId, linkDict):

        self.id = str(uuid.uuid4())
        self.pod_id= podId
        self.device_id=deviceId
        self.device1 = linkDict.get('device1')
        self.device1Ip = linkDict.get('device1Ip')
        self.device1As = linkDict.get('device1as')
        self.device2 = linkDict.get('device2')
        self.device2Ip = linkDict.get('device2Ip')
        self.device2As = linkDict.get('device2as')
        self.input_msg_count = linkDict.get('inputMsgCount')
        self.output_msg_count = linkDict.get('outputMsgCount')
        self.out_queue_count = linkDict.get('outQueueCount')
        self.flap_count = linkDict.get('flapCount')
        self.link_state = linkDict.get('linkState')
        self.act_rx_acc_route_count = linkDict.get('activeReceiveAcceptCount')
