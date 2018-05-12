'''
Created on Nov 23, 2015

@author: yunli

'''
import uuid
from sqlalchemy import Column, Integer, BigInteger, String, ForeignKey, Enum, UniqueConstraint, Index, Boolean, Table
from sqlalchemy.orm import relationship, backref

from jnpr.openclos.loader import OpenClosProperty
if OpenClosProperty().isSqliteUsed():
    from sqlalchemy import BLOB
else:
    from sqlalchemy.dialects.mysql import MEDIUMBLOB as BLOB
from jnpr.openclos.model import ManagedElement, Base
from jnpr.openclos.crypt import Cryptic

class OverlayDevice(ManagedElement, Base):
    __tablename__ = 'overlayDevice'
    id = Column(String(60), primary_key=True)
    name = Column(String(255), nullable=False)
    description = Column(String(256))
    role = Column(Enum('spine', 'leaf'))
    address = Column(String(60), unique=True)
    routerId = Column(String(60), unique=True)
    podName = Column(String(60))
    username = Column(String(100))
    encryptedPassword = Column(String(100)) # 2-way encrypted
    cryptic = Cryptic()
    overlay_fabrics = relationship(
        'OverlayFabric',
        secondary='overlayFabricOverlayDeviceLink'
    )
    enumRole = frozenset(['spine', 'leaf'])
    
    def __init__(self, name, description, role, address, routerId, podName, username, password):
        '''
        Creates device object.
        '''
        if username is None or username == '':
            raise ValueError("username cannot be None or empty")
        if password is None or password == '':
            raise ValueError("password cannot be None or empty")

        # Note in MySQL non-strict mode, inserting an invalid role will not throw error.
        # So we will validate role ourselves.
        if role not in self.enumRole:
            raise ValueError("invalid role '%s'" % role)
        
        self.id = str(uuid.uuid4())
        self.name = name
        self.description = description
        self.role = role
        self.address = address
        self.routerId = routerId
        self.podName = podName
        self.username = username
        self.encryptedPassword = self.cryptic.encrypt(password)
        
    def update(self, username, password):
        '''
        Updates device object.
        '''
        if username is not None:
            self.username = username
        if password is not None:
            self.encryptedPassword = self.cryptic.encrypt(password)
    
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

    def getUrl(self):
        return "/devices/" + self.id
    
class OverlayFabric(ManagedElement, Base):
    __tablename__ = 'overlayFabric'
    id = Column(String(60), primary_key=True)
    name = Column(String(255), index=True, nullable=False)
    description = Column(String(256))
    overlayAS = Column(BigInteger, nullable=False, unique=True)
    routeReflectorAddress = Column(String(60), nullable=False, unique=True)
  
    overlay_devices = relationship(
        'OverlayDevice',
        secondary='overlayFabricOverlayDeviceLink'
    )
    
    def __init__(self, name, description, overlayAS, routeReflectorAddress, devices):
        '''
        Creates Fabric object.
        '''
        if overlayAS is None or overlayAS == '':
            raise ValueError("overlayAS cannot be None or empty")
            
        if routeReflectorAddress is None or routeReflectorAddress == '':
            raise ValueError("routeReflectorAddress cannot be None or empty")
        
        self.id = str(uuid.uuid4())
        self.name = name
        self.description = description
        self.overlayAS = int(overlayAS)
        self.routeReflectorAddress = routeReflectorAddress
        for device in devices:
            self.overlay_devices.append(device)

    def getUrl(self):
        return "/fabrics/" + self.id
    
    def update(self, overlayAS, routeReflectorAddress, devices):
        '''
        Updates Fabric object.
        '''
        if overlayAS is not None:
            self.overlayAS = int(overlayAS)
        if routeReflectorAddress is not None:
            self.routeReflectorAddress = routeReflectorAddress
        if devices is not None:
            deleted = [device for device in self.overlay_devices if device not in devices]
            self.overlay_devices = devices
            return deleted
        else:
            return []

    def getSpines(self):
        return [dev for dev in self.overlay_devices if dev.role == "spine"]
    def getLeafs(self):
        return [dev for dev in self.overlay_devices if dev.role == "leaf"]
    def getPodSpines(self, podName):
        return [dev for dev in self.overlay_devices if dev.role == "spine" and dev.podName == podName]
    def getPodLeafs(self, podName):
        return [dev for dev in self.overlay_devices if dev.role == "leaf" and dev.podName == podName]
    
class OverlayFabricOverlayDeviceLink(ManagedElement, Base):
    __tablename__ = 'overlayFabricOverlayDeviceLink'
    overlay_fabric_id = Column(String(60), ForeignKey('overlayFabric.id'), primary_key=True)
    overlay_device_id = Column(String(60), ForeignKey('overlayDevice.id'), primary_key=True)
    __table_args__ = (
        # NOTE currently we do not support multiple overlay over same underlay. In another word, 
        # overlayDevice is not shared by multiple overlayFabrics. 
        # When we do support multiple overlay over same underlay in the future, disable 
        # overlay_device_id_uindex and re-enable overlay_fabric_id_overlay_device_id_uindex
        #
        # Index('overlay_fabric_id_overlay_device_id_uindex', 'overlay_fabric_id', 'overlay_device_id', unique=True),
        Index('overlay_device_id_uindex', 'overlay_device_id', unique=True),
    )

class OverlayFabricPodClusterId(ManagedElement, Base):
    __tablename__ = 'overlayFabricPodCluster'
    overlay_fabric_id = Column(String(60), ForeignKey('overlayFabric.id'), primary_key=True)
    podName = Column(String(60), nullable=False, primary_key=True)
    clusterId = Column(String(60), nullable=False)

    def __init__(self, overlay_fabric_id, podName, clusterId):
        '''
        Creates OverlayFabricPodClusterId object.
        '''
        self.overlay_fabric_id = overlay_fabric_id
        self.podName = podName
        self.clusterId = clusterId
    
    def update(self, clusterId):
        '''
        Updates OverlayFabricPodClusterId object.
        '''
        self.clusterId = clusterId
    
    def key(self):
        return self.overlay_fabric_id + ':' + self.podName
        
class OverlayTenant(ManagedElement, Base):
    __tablename__ = 'overlayTenant'
    id = Column(String(60), primary_key=True)
    name = Column(String(255), nullable=False)
    description = Column(String(256))
    overlay_fabric_id = Column(String(60), ForeignKey('overlayFabric.id'), nullable=False)
    overlay_fabric = relationship("OverlayFabric", backref=backref('overlay_tenants', order_by=name, cascade='all, delete, delete-orphan'))
    # __table_args__ = (
        # Index('overlay_fabric_id_overlay_tenant_name_uindex', 'overlay_fabric_id', 'name', unique=True),
    # )

    def __init__(self, name, description, overlay_fabric):
        '''
        Creates Tenant object.
        '''
        self.id = str(uuid.uuid4())
        self.name = name
        self.description = description
        self.overlay_fabric = overlay_fabric
    
    def getUrl(self):
        return "/tenants/" + self.id
        
class OverlayVrf(ManagedElement, Base):
    __tablename__ = 'overlayVrf'
    id = Column(String(60), primary_key=True)
    name = Column(String(255), nullable=False, unique=True)
    description = Column(String(256))
    routedVnid = Column(Integer)
    loopbackAddress = Column(String(60))
    vrfCounter = Column(Integer)
    overlay_tenant_id = Column(String(60), ForeignKey('overlayTenant.id'), nullable=False)
    overlay_tenant = relationship("OverlayTenant", backref=backref('overlay_vrfs', order_by=name, cascade='all, delete, delete-orphan'))
    # __table_args__ = (
        # Index('overlay_tenant_id_overlay_vrf_name_uindex', 'overlay_tenant_id', 'name', unique=True),
    # )

    def __init__(self, name, description, routedVnid, loopbackAddress, overlay_tenant):
        '''
        Creates VRF object.
        '''
        self.id = str(uuid.uuid4())
        self.name = name
        self.description = description
        if routedVnid is not None:
            self.routedVnid = int(routedVnid)
        self.loopbackAddress = loopbackAddress
        self.overlay_tenant = overlay_tenant
        
    def getUrl(self):
        return "/vrfs/" + self.id
    
    def update(self, loopbackAddress):
        '''
        Updates VRF object.
        '''
        old = { 
            "loopbackAddress": self.loopbackAddress
        }
        
        if loopbackAddress is not None:
            self.loopbackAddress = loopbackAddress
        
        return old
        
    def getDevices(self, role=None):
        if self.overlay_tenant and self.overlay_tenant.overlay_fabric:
            if not role:
                return self.overlay_tenant.overlay_fabric.overlay_devices
            else:
                return [dev for dev in self.overlay_tenant.overlay_fabric.overlay_devices if dev.role == role]
        
        return []
    def getSpines(self):
        return self.getDevices("spine")
    def getLeafs(self):
        return self.getDevices("leaf")

class OverlayNetworkOverlayL2apTable(ManagedElement, Base):
    __tablename__ = 'overlayNetworkOverlayL2apTable'
    overlay_network_id = Column(String(60), ForeignKey('overlayNetwork.id'), primary_key=True)
    overlay_l2ap_id = Column(String(60), ForeignKey('overlayL2ap.id'), primary_key=True)
    __table_args__ = (
        Index('overlay_network_id_overlay_l2ap_id_uindex', 'overlay_network_id', 'overlay_l2ap_id', unique=True),
    )

class OverlayNetwork(ManagedElement, Base):
    __tablename__ = 'overlayNetwork'
    id = Column(String(60), primary_key=True)
    name = Column(String(255), nullable=False)
    description = Column(String(256))
    vlanid = Column(Integer, nullable=False) # Allow same vlan-id on different overlay fabrics. Programmatically check vlan-id uniqueness wihtin the same overlay fabric.
    vnid = Column(Integer, unique=True, nullable=False) # for current release, vnid has to be globally unique
    pureL3Int = Column(Boolean)
    overlay_vrf_id = Column(String(60), ForeignKey('overlayVrf.id'), nullable=False)
    overlay_vrf = relationship("OverlayVrf", backref=backref('overlay_networks', order_by=name, cascade='all, delete, delete-orphan'))
    overlay_l2aps = relationship("OverlayL2ap", secondary='overlayNetworkOverlayL2apTable', back_populates="overlay_networks")
    # __table_args__ = (
        # Index('overlay_vrf_id_overlay_network_name_uindex', 'overlay_vrf_id', 'name', unique=True),
    # )

    def __init__(self, name, description, overlay_vrf, vlanid, vnid, pureL3Int):
        '''
        Creates network object.
        '''
        if vlanid < 1 or vlanid > 4096:
            raise ValueError("vlanid %s out of range (1-4096)" % vlanid)

        # Make sure vlan-id is unique within same overlay fabric
        fabric = overlay_vrf.overlay_tenant.overlay_fabric
        for tenant in fabric.overlay_tenants:
            for vrf in tenant.overlay_vrfs:
                for network in vrf.overlay_networks:
                    if vlanid == network.vlanid:
                        raise ValueError("vlanid %s is not unique within overlayFabric[id: '%s', name: '%s']" % (vlanid, fabric.id, fabric.name)) 
        
        self.id = str(uuid.uuid4())
        self.name = name
        self.description = description
        self.overlay_vrf = overlay_vrf
        self.vlanid = int(vlanid)
        self.vnid = int(vnid)
        self.pureL3Int = pureL3Int
        
    def getUrl(self):
        return "/networks/" + self.id
    
    def update(self, vlanid, vnid):
        '''
        Updates network object.
        '''
        old = { 
            "vlanid": self.vlanid, 
            "vnid": self.vnid
        }
        
        if vlanid is not None:
            self.vlanid = int(vlanid)
        if vnid is not None:
            self.vnid = int(vnid)
            
        return old
    
class OverlaySubnet(ManagedElement, Base):
    __tablename__ = 'overlaySubnet'
    id = Column(String(60), primary_key=True)
    name = Column(String(255), nullable=False)
    description = Column(String(256))
    cidr = Column(String(60), nullable=False)
    overlay_network_id = Column(String(60), ForeignKey('overlayNetwork.id'), nullable=False)
    overlay_network = relationship("OverlayNetwork", backref=backref('overlay_subnets', order_by=name, cascade='all, delete, delete-orphan'))
    __table_args__ = (
        # Index('overlay_network_id_overlay_subnet_name_uindex', 'overlay_network_id', 'name', unique=True),
        Index('overlay_network_id_overlay_subnet_cidr_uindex', 'overlay_network_id', 'cidr', unique=True),
    )

    def __init__(self, name, description, overlay_network, cidr):
        '''
        Creates subnet object.
        '''
        self.id = str(uuid.uuid4())
        self.name = name
        self.description = description
        self.overlay_network = overlay_network
        self.cidr = cidr
        
    def getUrl(self):
        return "/subnets/" + self.id

    def update(self, cidr):
        '''
        Updates subnet object.
        '''
        old = { 
            "cidr": self.cidr
        }
        
        if cidr is not None:
            self.cidr = cidr
            
        return old
    
class OverlayL3port(ManagedElement, Base):
    __tablename__ = 'overlayL3port'
    id = Column(String(60), primary_key=True)
    name = Column(String(255), nullable=False)
    description = Column(String(256))
    overlay_subnet_id = Column(String(60), ForeignKey('overlaySubnet.id'), nullable=False)
    overlay_subnet = relationship("OverlaySubnet", backref=backref('overlay_l3ports', order_by=name, cascade='all, delete, delete-orphan'))
    # __table_args__ = (
        # Index('overlay_subnet_id_overlay_l3port_name_uindex', 'overlay_subnet_id', 'name', unique=True),
    # )

    def __init__(self, name, description, overlay_subnet):
        '''
        Creates L3 port object.
        '''
        self.id = str(uuid.uuid4())
        self.name = name
        self.description = description
        self.overlay_subnet = overlay_subnet
        
    def update(self, name, description):
        '''
        Updates L3 port object.
        '''
        self.name = name
        self.description = description

class OverlayL2ap(ManagedElement, Base):
    __tablename__ = 'overlayL2ap'
    id = Column(String(60), primary_key=True)
    name = Column(String(255), nullable=False)
    description = Column(String(256))
    enterprise  = Column(Boolean,default=0)
    overlay_networks = relationship("OverlayNetwork", secondary='overlayNetworkOverlayL2apTable', back_populates="overlay_l2aps")
    type = Column(String(20), nullable=False) # l2ap/l2port/aggregatedL2port 
    __mapper_args__ = {
        'polymorphic_identity': 'l2ap',
        'polymorphic_on':type
    }
        
    def __init__(self, name, description, overlay_networks,enterprise):
        '''
        Creates L2 attach point object.
        '''
        self.enterprise = enterprise
        self.id = str(uuid.uuid4())
        self.name = name
        self.description = description
        for network in overlay_networks:
            self.overlay_networks.append(network)
        
    def update(self, overlay_networks):
        '''
        Updates L2 attach point object.
        '''
        if overlay_networks is not None:
            deleted = [network for network in self.overlay_networks if network not in overlay_networks]
            self.overlay_networks = overlay_networks
            return deleted
        else:
            return []
    
    def configName(self):
        '''
        Returns the name used in config stanza on device.
        In case of l2port, it shall be the OverlayL2port.interface.
        In case of aggregatedL2port, it shall be OverlayAggregatedL2port.name.
        '''
        return self.name
        
class OverlayL2port(OverlayL2ap):
    __tablename__ = 'overlayL2port'
    id = Column(String(60), ForeignKey('overlayL2ap.id'), primary_key=True)
    interface = Column(String(100), nullable=False)
    overlay_device_id = Column(String(60), ForeignKey('overlayDevice.id'), nullable=False)
    overlay_device = relationship("OverlayDevice", backref=backref('overlay_l2ports', order_by='OverlayL2ap.name', cascade='all, delete, delete-orphan'))
    __mapper_args__ = {
        'polymorphic_identity': 'l2port'
    }
    
    def __init__(self, name, description, overlay_networks, interface, overlay_device,enterprise):
        '''
        Creates L2 port object.
        '''
        super(OverlayL2port, self).__init__(name, description, overlay_networks,enterprise)
        self.interface = interface
        self.overlay_device = overlay_device
        
    def getUrl(self):
        return "/l2ports/" + self.id
    
    def update(self, overlay_networks):
        '''
        Updates L2 port object.
        '''
        return super(OverlayL2port, self).update(overlay_networks)
        
    def configName(self):
        '''
        Returns the name used in config stanza on device.
        In case of l2port, it shall be the OverlayL2port.interface.
        In case of aggregatedL2port, it shall be OverlayAggregatedL2port.name.
        '''
        return self.interface
    
class OverlayAggregatedL2portMember(ManagedElement, Base):
    __tablename__ = 'overlayAggregatedL2portMember'
    id = Column(String(60), primary_key=True)
    interface = Column(String(100), nullable=False)
    overlay_device_id = Column(String(60), ForeignKey('overlayDevice.id'), nullable=False)
    overlay_aggregatedL2port_id = Column(String(60), ForeignKey('overlayAggregatedL2port.id'))
    overlay_device = relationship("OverlayDevice", backref=backref('aggregatedL2port_members', order_by=overlay_aggregatedL2port_id, cascade='all, delete, delete-orphan'))
    overlay_aggregatedL2port = relationship("OverlayAggregatedL2port", backref=backref('members', order_by=overlay_device_id, cascade='all, delete, delete-orphan'))
    # __table_args__ = (
        # Index('overlay_device_id_interface_uindex', 'overlay_device_id', 'interface', unique=True),
    # )
    
    def __init__(self, interface, overlay_device, overlay_aggregatedL2port):
        '''
        Creates aggregated interface member object.
        '''
        self.id = str(uuid.uuid4())
        self.interface = interface
        self.overlay_device = overlay_device
        self.overlay_aggregatedL2port = overlay_aggregatedL2port
        
    def update(self, interface, overlay_device, overlay_aggregatedL2port):
        '''
        Updates aggregated interface member object.
        '''
        self.interface = interface
        self.overlay_device = overlay_device
        self.overlay_aggregatedL2port = overlay_aggregatedL2port
    
class OverlayAggregatedL2port(OverlayL2ap):
    __tablename__ = 'overlayAggregatedL2port'
    id = Column(String(60), ForeignKey('overlayL2ap.id'), primary_key=True)
    esi = Column(String(60), nullable=False, unique=True)
    lacp = Column(String(60), nullable=False)
    __mapper_args__ = {
        'polymorphic_identity': 'aggregatedL2port'
    }

    def __init__(self, name, description, overlay_networks, esi, lacp,enterprise):
        '''
        Creates aggregated interface object.
        '''
        super(OverlayAggregatedL2port, self).__init__(name, description, overlay_networks,enterprise)
        self.esi = esi
        self.lacp = lacp
        
    def getUrl(self):
        return "/aggregatedL2ports/" + self.id
    
    def update(self, overlay_networks, esi, lacp):
        '''
        Updates aggregated interface object.
        '''
        if esi is not None:
            self.esi = esi
        if lacp is not None:
            self.lacp = lacp
        return super(OverlayAggregatedL2port, self).update(overlay_networks)
        
    def configName(self):
        '''
        Returns the name used in config stanza on device.
        In case of l2port, it shall be the OverlayL2port.interface.
        In case of aggregatedL2port, it shall be OverlayAggregatedL2port.name.
        '''
        return self.name
 
class OverlayDeployStatus(ManagedElement, Base):
    __tablename__ = 'overlayDeployStatus'
    id = Column(String(60), primary_key=True)
    configlet = Column(BLOB)
    object_url = Column(String(1024), nullable=False)
    operation = Column(Enum('create', 'update', 'delete'))
    overlay_device_id = Column(String(60), ForeignKey('overlayDevice.id'), nullable=False)
    overlay_device = relationship("OverlayDevice", backref=backref('deploy_status', cascade='all, delete, delete-orphan'))
    overlay_fabric_id = Column(String(60), ForeignKey('overlayFabric.id'))
    overlay_fabric = relationship("OverlayFabric", backref=backref('deploy_status', cascade='all, delete, delete-orphan'))
    status = Column(Enum('unknown', 'progress', 'success', 'failure'), default='unknown')
    statusReason = Column(String(4096))
    # REVISIT: This constraint seems wrong. If we configure 2 subnets under the same network, 2 rows will be created. 
    # Both rows will have the same object_url which is the network object's url and the same device id.
    # __table_args__ = (
        # Index('object_url_overlay_device_id_uindex', 'object_url', 'overlay_device_id', unique=True),
    # )
    enumStatus = frozenset(['unknown', 'progress', 'success', 'failure'])
    enumOperation = frozenset(['create', 'update', 'delete'])
    
    def __init__(self, configlet, object_url, operation, overlay_device, overlay_fabric, status=None, statusReason=None):
        '''
        Creates status object.
        '''
        # Note in MySQL non-strict mode, inserting an invalid operation will not throw error.
        # So we will validate operation ourselves.
        if operation not in self.enumOperation:
            raise ValueError("invalid operation '%s'" % operation)
        
        # Note in MySQL non-strict mode, inserting an invalid status will not throw error.
        # So we will status operation ourselves.
        if status is not None and status not in self.enumStatus: 
            raise ValueError("invalid status '%s'" % status)
            
        self.id = str(uuid.uuid4())
        self.configlet = configlet
        self.object_url = object_url
        self.operation = operation
        self.overlay_device = overlay_device
        self.overlay_fabric = overlay_fabric
        self.status = status
        self.statusReason = statusReason
        
    def update(self, status, statusReason=None):
        '''
        Update status object.
        '''
        # Note in MySQL non-strict mode, inserting an invalid status will not throw error.
        # So we will status operation ourselves.
        if status is not None and status not in self.enumStatus: 
            raise ValueError("invalid status '%s'" % status)
            
        self.status = status
        self.statusReason = statusReason
        
    @staticmethod
    def getObjectTypeAndId(objectUrl):
        '''
        returns tuple with objectType and objectId
        '''
        objectUrlSplit = objectUrl.split("/")
        if objectUrlSplit[1] == "fabrics":
            return(OverlayFabric, objectUrlSplit[2])
        elif objectUrlSplit[1] == "tenants":
            return(OverlayTenant, objectUrlSplit[2])
        elif objectUrlSplit[1] == "vrfs":
            return(OverlayVrf, objectUrlSplit[2])
        elif objectUrlSplit[1] == "networks":
            return(OverlayNetwork, objectUrlSplit[2])
        elif objectUrlSplit[1] == "subnets":
            return(OverlaySubnet, objectUrlSplit[2])
        elif objectUrlSplit[1] == "l2ports":
            return(OverlayL2port, objectUrlSplit[2])
        elif objectUrlSplit[1] == "aggregatedL2ports":
            return(OverlayAggregatedL2port, objectUrlSplit[2])
        elif objectUrlSplit[1] == "devices":
            return(OverlayDevice, objectUrlSplit[2])

    @staticmethod
    def hasChildren(object):
        '''
        returns True if object has children
        '''
        if object is None:
            return False
        elif isinstance(object, OverlayFabric):
            return len(object.overlay_tenants) > 0
        elif isinstance(object, OverlayTenant):
            return len(object.overlay_vrfs) > 0
        elif isinstance(object, OverlayVrf):
            return len(object.overlay_networks) > 0
        elif isinstance(object, OverlayNetwork):
            #return (len(object.overlay_l2aps) > 0) or (len(object.overlay_subnets) > 0)
            return len(object.overlay_subnets) > 0
        elif isinstance(object, OverlaySubnet):
            return False
        elif isinstance(object, OverlayL3port):
            return False
        elif isinstance(object, OverlayL2port):
            return False
        elif isinstance(object, OverlayAggregatedL2port):
            return False
        elif isinstance(object, OverlayDevice):
            return (len(object.overlay_fabrics) > 0 or len(object.overlay_l2ports) > 0 or len(object.aggregatedL2port_members) > 0) 
        else:
            return False
