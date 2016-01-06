'''
Created on Nov 23, 2015

@author: yunli

'''
import uuid
import math
from sqlalchemy import Column, Integer, BigInteger, String, ForeignKey, Enum, UniqueConstraint, Index, Boolean
from sqlalchemy.orm import relationship, backref
from netaddr import IPAddress, IPNetwork, AddrFormatError

from jnpr.openclos.loader import OpenClosProperty
if OpenClosProperty().isSqliteUsed():
    from sqlalchemy import BLOB
else:
    from sqlalchemy.dialects.mysql import MEDIUMBLOB as BLOB
from jnpr.openclos.model import ManagedElement, Base

class OverlayDevice(ManagedElement, Base):
    __tablename__ = 'overlayDevice'
    id = Column(String(60), primary_key=True)
    name = Column(String(255), nullable=False)
    description = Column(String(256))
    role = Column(Enum('spine', 'leaf'))
    address = Column(String(60))
    overlay_fabrics = relationship(
        'OverlayFabric',
        secondary='overlayFabricOverlayDeviceLink'
    )

    def __init__(self, name, description, role, address):
        '''
        Creates device object.
        '''
        self.id = str(uuid.uuid4())
        self.name = name
        self.description = description
        self.role = role
        self.address = address
        
    def update(self, name, description, role, address):
        '''
        Updates device object.
        '''
        self.name = name
        self.description = description
        self.role = role
        self.address = address
    
class OverlayFabric(ManagedElement, Base):
    __tablename__ = 'overlayFabric'
    id = Column(String(60), primary_key=True)
    name = Column(String(255), index=True, nullable=False)
    description = Column(String(256))
    overlayAS = Column(BigInteger)
    overlay_devices = relationship(
        'OverlayDevice',
        secondary='overlayFabricOverlayDeviceLink'
    )
    
    def __init__(self, name, description, overlayAS, devices):
        '''
        Creates Fabric object.
        '''
        self.id = str(uuid.uuid4())
        self.name = name
        self.description = description
        self.overlayAS = overlayAS
        for device in devices:
            self.overlay_devices.append(device)
        
    def update(self, name, description, overlayAS, devices):
        '''
        Updates Fabric object.
        '''
        self.name = name
        self.description = description
        self.overlayAS = overlayAS
        for device in devices:
            self.overlay_devices.append(device)
    
    def clearDevices(self):
        '''
        Remove existing devices
        '''
        del self.overlay_devices[:]
    
class OverlayFabricOverlayDeviceLink(ManagedElement, Base):
    __tablename__ = 'overlayFabricOverlayDeviceLink'
    overlay_fabric_id = Column(String(60), ForeignKey('overlayFabric.id'), primary_key=True)
    overlay_device_id = Column(String(60), ForeignKey('overlayDevice.id'), primary_key=True)

class OverlayTenant(ManagedElement, Base):
    __tablename__ = 'overlayTenant'
    id = Column(String(60), primary_key=True)
    name = Column(String(255), nullable=False)
    description = Column(String(256))
    overlay_fabric_id = Column(String(60), ForeignKey('overlayFabric.id'), nullable=False)
    overlay_fabric = relationship("OverlayFabric", backref=backref('overlay_tenants', order_by=name, cascade='all, delete, delete-orphan'))
    #__table_args__ = (
    #    Index('fabric_id_name_uindex', 'fabric_id', 'name', unique=True),
    #)

    def __init__(self, name, description, overlay_fabric):
        '''
        Creates Tenant object.
        '''
        self.id = str(uuid.uuid4())
        self.name = name
        self.description = description
        self.overlay_fabric = overlay_fabric
        
    def update(self, name, description):
        '''
        Updates Tenant object.
        '''
        self.name = name
        self.description = description
    
class OverlayVrf(ManagedElement, Base):
    __tablename__ = 'overlayVrf'
    id = Column(String(60), primary_key=True)
    name = Column(String(255), nullable=False)
    description = Column(String(256))
    routedVnid = Column(Integer)
    overlay_tenant_id = Column(String(60), ForeignKey('overlayTenant.id'), nullable=False)
    overlay_tenant = relationship("OverlayTenant", backref=backref('overlay_vrfs', order_by=name, cascade='all, delete, delete-orphan'))
    #__table_args__ = (
    #    Index('tenant_id_name_uindex', 'tenant_id', 'name', unique=True),
    #)

    def __init__(self, name, description, routedVnid, overlay_tenant):
        '''
        Creates VRF object.
        '''
        self.id = str(uuid.uuid4())
        self.name = name
        self.description = description
        self.routedVnid = routedVnid
        self.overlay_tenant = overlay_tenant
        
    def update(self, name, description, routedVnid):
        '''
        Updates VRF object.
        '''
        self.name = name
        self.description = description
        self.routedVnid = routedVnid
    
class OverlayNetwork(ManagedElement, Base):
    __tablename__ = 'overlayNetwork'
    id = Column(String(60), primary_key=True)
    name = Column(String(255), nullable=False)
    description = Column(String(256))
    vlanid = Column(Integer)
    vnid = Column(Integer)
    pureL3Int = Column(Boolean)
    overlay_vrf_id = Column(String(60), ForeignKey('overlayVrf.id'), nullable=False)
    overlay_vrf = relationship("OverlayVrf", backref=backref('overlay_networks', order_by=name, cascade='all, delete, delete-orphan'))
    #__table_args__ = (
    #    Index('vrf_id_name_uindex', 'vrf_id', 'name', unique=True),
    #)

    def __init__(self, name, description, overlay_vrf, vlanid, vnid, pureL3Int):
        '''
        Creates network object.
        '''
        self.id = str(uuid.uuid4())
        self.name = name
        self.description = description
        self.overlay_vrf = overlay_vrf
        self.vlanid = vlanid
        self.vnid = vnid
        self.pureL3Int = pureL3Int
        
    def update(self, name, description, vlanid, vnid, pureL3Int):
        '''
        Updates network object.
        '''
        self.name = name
        self.description = description
        self.vlanid = vlanid
        self.vnid = vnid
        self.pureL3Int = pureL3Int
    
class OverlaySubnet(ManagedElement, Base):
    __tablename__ = 'overlaySubnet'
    id = Column(String(60), primary_key=True)
    name = Column(String(255), nullable=False)
    description = Column(String(256))
    cidr = Column(String(60))
    overlay_network_id = Column(String(60), ForeignKey('overlayNetwork.id'), nullable=False)
    overlay_network = relationship("OverlayNetwork", backref=backref('overlay_subnets', order_by=name, cascade='all, delete, delete-orphan'))
    #__table_args__ = (
    #    Index('network_id_name_uindex', 'network_id', 'name', unique=True),
    #)

    def __init__(self, name, description, overlay_network, cidr):
        '''
        Creates subnet object.
        '''
        self.id = str(uuid.uuid4())
        self.name = name
        self.description = description
        self.overlay_network = overlay_network
        self.cidr = cidr
        
    def update(self, name, description, cidr):
        '''
        Updates subnet object.
        '''
        self.name = name
        self.description = description
        self.cidr = cidr
    
class OverlayL3port(ManagedElement, Base):
    __tablename__ = 'overlayL3port'
    id = Column(String(60), primary_key=True)
    name = Column(String(255), nullable=False)
    description = Column(String(256))
    overlay_subnet_id = Column(String(60), ForeignKey('overlaySubnet.id'), nullable=False)
    overlay_subnet = relationship("OverlaySubnet", backref=backref('overlay_l3ports', order_by=name, cascade='all, delete, delete-orphan'))
    #__table_args__ = (
    #    Index('subnet_id_name_uindex', 'subnet_id', 'name', unique=True),
    #)

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
    
class OverlayL2port(ManagedElement, Base):
    __tablename__ = 'overlayL2port'
    id = Column(String(60), primary_key=True)
    name = Column(String(255), nullable=False)
    description = Column(String(256))
    interface = Column(String(100), nullable=False)
    overlay_ae_id = Column(String(60), ForeignKey('overlayAe.id'), nullable=False)
    overlay_ae = relationship("OverlayAe", backref=backref('overlay_members', order_by=name, cascade='all, delete, delete-orphan'))
    overlay_network_id = Column(String(60), ForeignKey('overlayNetwork.id'), nullable=False)
    overlay_network = relationship("OverlayNetwork", backref=backref('overlay_l2ports', order_by=name, cascade='all, delete, delete-orphan'))
    overlay_device_id = Column(String(60), ForeignKey('overlayDevice.id'), nullable=False)
    overlay_device = relationship("OverlayDevice", backref=backref('overlay_l2ports', order_by=name, cascade='all, delete, delete-orphan'))
    #__table_args__ = (
    #    Index('ae_id_name_uindex', 'ae_id', 'name', unique=True),
    #    Index('network_id_name_uindex', 'network_id', 'name', unique=True),
    #    Index('device_id_name_uindex', 'device_id', 'name', unique=True),
    #)

    def __init__(self, name, description, interface, overlay_ae, overlay_network, overlay_device):
        '''
        Creates L2 port object.
        '''
        self.id = str(uuid.uuid4())
        self.name = name
        self.description = description
        self.interface = interface
        self.overlay_ae = overlay_ae
        self.overlay_network = overlay_network
        self.overlay_device = overlay_device
        
    def update(self, name, description, interface):
        '''
        Updates L2 port object.
        '''
        self.name = name
        self.description = description
        self.interface = interface
    
class OverlayAe(ManagedElement, Base):
    __tablename__ = 'overlayAe'
    id = Column(String(60), primary_key=True)
    name = Column(String(255), nullable=False)
    description = Column(String(256))
    esi = Column(String(60), nullable=False)
    lacp = Column(String(60), nullable=False)
    #__table_args__ = (
    #    Index('network_id_name_uindex', 'network_id', 'name', unique=True),
    #)

    def __init__(self, name, description, esi, lacp):
        '''
        Creates aggregated interface object.
        '''
        self.id = str(uuid.uuid4())
        self.name = name
        self.description = description
        self.esi = esi
        self.lacp = lacp
        
    def update(self, name, description, esi, lacp):
        '''
        Updates L2 port object.
        '''
        self.name = name
        self.description = description
        self.esi = esi
        self.lacp = lacp

class OverlayDeployStatus(ManagedElement, Base):
    __tablename__ = 'overlayDeployStatus'
    id = Column(String(60), primary_key=True)
    configlet = Column(BLOB)
    object_url = Column(String(1024), nullable=False)
    overlay_device_id = Column(String(60), ForeignKey('overlayDevice.id'), nullable=False)
    overlay_device = relationship("OverlayDevice", backref=backref('deploy_status', cascade='all, delete, delete-orphan'))
    overlay_vrf_id = Column(String(60), ForeignKey('overlayVrf.id'), nullable=False)
    overlay_vrf = relationship("OverlayVrf", backref=backref('deploy_status', cascade='all, delete, delete-orphan'))
    status = Column(Enum('unknown', 'progress', 'success', 'failure'))
    statusReason = Column(String(1024))
    source = Column(String(60))
    __table_args__ = (
        Index('object_url_overlay_device_id_uindex', 'object_url', 'overlay_device_id', unique=True),
    )
    
    def __init__(self, configlet, object_url, overlay_device, overlay_vrf, status, statusReason, source):
        '''
        Creates status object.
        '''
        self.id = str(uuid.uuid4())
        self.configlet = configlet
        self.object_url = object_url
        self.overlay_device = overlay_device
        self.overlay_vrf = overlay_vrf
        self.status = status
        self.statusReason = statusReason
        self.source = source
        
    def update(self, status, statusReason, source):
        '''
        Update status object.
        '''
        self.status = status
        self.statusReason = statusReason
        self.source = source
        