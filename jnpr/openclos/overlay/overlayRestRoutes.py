'''
Created on Nov 23, 2015

@author: yunli
'''

import bottle
from sqlalchemy.orm import exc
import traceback
import json

from jnpr.openclos.exception import InvalidRequest, OverlayFabricNotFound, OverlayTenantNotFound, OverlayVrfNotFound, OverlayDeviceNotFound, OverlayNetworkNotFound, OverlaySubnetNotFound, OverlayL3portNotFound, OverlayL2portNotFound, OverlayAggregatedL2portNotFound, PlatformError
from jnpr.openclos.overlay.overlayModel import OverlayFabric, OverlayTenant, OverlayVrf, OverlayDevice, OverlayNetwork, OverlaySubnet, OverlayL3port, OverlayL2port, OverlayAggregatedL2port, OverlayDeployStatus
from jnpr.openclos.overlay.overlay import Overlay
from jnpr.openclos.overlay.overlayCommit import OverlayCommitQueue

logger = None
routes = None

def install(context):
    global logger
    logger = context['logger']
    global routes
    routes = OverlayRestRoutes()
    routes.install(context)

def uninstall():
    if routes:
        routes.uninstall()
    
class OverlayRestRoutes():
    def install(self, context):
        self.baseUrl = context['baseUrl'] + '/overlay'
        self._conf = context['conf']
        self.__dao = context['dao']
        self.app = context['app']
        self.uriPrefix = None
        self._overlay = Overlay(self._conf, self.__dao)

        # commit engine
        self.commitQueue = OverlayCommitQueue.getInstance()
        self.commitQueue.start()
        
        # install index links
        context['restServer'].addIndexLink(self.baseUrl + '/devices')
        context['restServer'].addIndexLink(self.baseUrl + '/fabrics')
        context['restServer'].addIndexLink(self.baseUrl + '/tenants')
        context['restServer'].addIndexLink(self.baseUrl + '/vrfs')
        context['restServer'].addIndexLink(self.baseUrl + '/networks')
        context['restServer'].addIndexLink(self.baseUrl + '/subnets')
        context['restServer'].addIndexLink(self.baseUrl + '/l3ports')
        context['restServer'].addIndexLink(self.baseUrl + '/l2ports')
        context['restServer'].addIndexLink(self.baseUrl + '/aggregatedL2ports')
        
        # GET APIs
        self.app.route(self.baseUrl + '/devices', 'GET', self.getDevices)
        self.app.route(self.baseUrl + '/devices/<deviceId>', 'GET', self.getDevice)
        self.app.route(self.baseUrl + '/fabrics', 'GET', self.getFabrics)
        self.app.route(self.baseUrl + '/fabrics/<fabricId>', 'GET', self.getFabric)
        self.app.route(self.baseUrl + '/tenants', 'GET', self.getTenants)
        self.app.route(self.baseUrl + '/tenants/<tenantId>', 'GET', self.getTenant)
        self.app.route(self.baseUrl + '/vrfs', 'GET', self.getVrfs)
        self.app.route(self.baseUrl + '/vrfs/<vrfId>', 'GET', self.getVrf)
        self.app.route(self.baseUrl + '/vrfs/<vrfId>/status', 'GET', self.getVrfStatus)
        self.app.route(self.baseUrl + '/networks', 'GET', self.getNetworks)
        self.app.route(self.baseUrl + '/networks/<networkId>', 'GET', self.getNetwork)
        self.app.route(self.baseUrl + '/subnets', 'GET', self.getSubnets)
        self.app.route(self.baseUrl + '/subnets/<subnetId>', 'GET', self.getSubnet)
        self.app.route(self.baseUrl + '/l3ports', 'GET', self.getL3ports)
        self.app.route(self.baseUrl + '/l3ports/<l3portId>', 'GET', self.getL3port)
        self.app.route(self.baseUrl + '/l2ports', 'GET', self.getL2ports)
        self.app.route(self.baseUrl + '/l2ports/<l2portId>', 'GET', self.getL2port)
        self.app.route(self.baseUrl + '/aggregatedL2ports', 'GET', self.getAggregatedL2ports)
        self.app.route(self.baseUrl + '/aggregatedL2ports/<aggregatedL2portId>', 'GET', self.getAggregatedL2port)

        # POST/PUT APIs
        self.app.route(self.baseUrl + '/devices', 'POST', self.createDevice)
        self.app.route(self.baseUrl + '/devices/<deviceId>', 'PUT', self.modifyDevice)
        self.app.route(self.baseUrl + '/fabrics', 'POST', self.createFabric)
        self.app.route(self.baseUrl + '/fabrics/<fabricId>', 'PUT', self.modifyFabric)
        self.app.route(self.baseUrl + '/tenants', 'POST', self.createTenant)
        self.app.route(self.baseUrl + '/tenants/<tenantId>', 'PUT', self.modifyTenant)
        self.app.route(self.baseUrl + '/vrfs', 'POST', self.createVrf)
        self.app.route(self.baseUrl + '/vrfs/<vrfId>', 'PUT', self.modifyVrf)
        self.app.route(self.baseUrl + '/networks', 'POST', self.createNetwork)
        self.app.route(self.baseUrl + '/networks/<networkId>', 'PUT', self.modifyNetwork)
        self.app.route(self.baseUrl + '/subnets', 'POST', self.createSubnet)
        self.app.route(self.baseUrl + '/subnets/<subnetId>', 'PUT', self.modifySubnet)
        self.app.route(self.baseUrl + '/l3ports', 'POST', self.createL3port)
        self.app.route(self.baseUrl + '/l3ports/<l3portId>', 'PUT', self.modifyL3port)
        self.app.route(self.baseUrl + '/l2ports', 'POST', self.createL2port)
        self.app.route(self.baseUrl + '/l2ports/<l2portId>', 'PUT', self.modifyL2port)
        self.app.route(self.baseUrl + '/aggregatedL2ports', 'POST', self.createAggregatedL2port)
        self.app.route(self.baseUrl + '/aggregatedL2ports/<aggregatedL2portId>', 'PUT', self.modifyAggregatedL2port)

        # DELETE APIs
        self.app.route(self.baseUrl + '/devices/<deviceId>', 'DELETE', self.deleteDevice)
        self.app.route(self.baseUrl + '/fabrics/<fabricId>', 'DELETE', self.deleteFabric)
        self.app.route(self.baseUrl + '/tenants/<tenantId>', 'DELETE', self.deleteTenant)
        self.app.route(self.baseUrl + '/vrfs/<vrfId>', 'DELETE', self.deleteVrf)
        self.app.route(self.baseUrl + '/networks/<networkId>', 'DELETE', self.deleteNetwork)
        self.app.route(self.baseUrl + '/subnets/<subnetId>', 'DELETE', self.deleteSubnet)
        self.app.route(self.baseUrl + '/l3ports/<l3portId>', 'DELETE', self.deleteL3port)
        self.app.route(self.baseUrl + '/l2ports/<l2portId>', 'DELETE', self.deleteL2port)
        self.app.route(self.baseUrl + '/aggregatedL2ports/<aggregatedL2portId>', 'DELETE', self.deleteAggregatedL2port)

    def uninstall(self):
        self.commitQueue.stop()
    
    def _getUriPrefix(self):
        if self.uriPrefix is None:
            self.uriPrefix = '%s://%s%s' % (bottle.request.urlparts[0], bottle.request.urlparts[1], self.baseUrl)
        return self.uriPrefix

    def _populateDevice(self, deviceObject):
        device = {}      
        device['id'] = deviceObject.id
        device['name'] = deviceObject.name
        device['description'] = deviceObject.description
        device['role'] = deviceObject.role
        device['address'] = deviceObject.address
        device['routerId'] = deviceObject.routerId
        device['podName'] = deviceObject.podName
        device['uri'] = '%s/devices/%s' % (self._getUriPrefix(), deviceObject.id)
        fabrics = []
        for fabric in deviceObject.overlay_fabrics:
            fabrics.append({'uri': '%s/fabrics/%s' % (self._getUriPrefix(), fabric.id)})
        device['fabrics'] = {'fabric': fabrics, 'total': len(deviceObject.overlay_fabrics)}
        return device
    
    def getDevices(self, dbSession):
            
        deviceObjects = self.__dao.getAll(dbSession, OverlayDevice)
        devices = []
        for deviceObject in deviceObjects:
            devices.append(self._populateDevice(deviceObject))
        
        logger.debug("getDevices: count %d", len(devices))
        
        outputDict = {}
        outputDict['device'] = devices
        outputDict['total'] = len(devices)
        outputDict['uri'] = '%s/devices' % (self._getUriPrefix())
        return {'devices': outputDict}

    def getDevice(self, dbSession, deviceId):
            
        try:
            deviceObject = self.__dao.getObjectById(dbSession, OverlayDevice, deviceId)
            logger.debug('getDevice: %s', deviceId)
        except (exc.NoResultFound) as ex:
            logger.debug("No Overlay Device found with Id: '%s', exc.NoResultFound: %s", deviceId, ex.message)
            raise bottle.HTTPError(404, exception=OverlayDeviceNotFound(deviceId))
        except Exception as ex:
            logger.debug('StackTrace: %s', traceback.format_exc())
            raise bottle.HTTPError(500, exception=PlatformError(ex.message))
        
        return {'device': self._populateDevice(deviceObject)}
        
    def createDevice(self, dbSession):  
            
        if bottle.request.json is None:
            raise bottle.HTTPError(400, exception=InvalidRequest("No json in request object"))
        else:
            deviceDict = bottle.request.json.get('device')
            if deviceDict is None:
                raise bottle.HTTPError(400, exception=InvalidRequest("POST body cannot be empty"))

        try:
            name = deviceDict['name']
            description = deviceDict.get('description')
            role = deviceDict['role']
            address = deviceDict['address']
            routerId = deviceDict['routerId']
            podName = deviceDict['podName']
            username = deviceDict['username']
            password = deviceDict['password']
            
            deviceObject = self._overlay.createDevice(dbSession, name, description, role, address, routerId, podName, username, password)
            device = {'device': self._populateDevice(deviceObject)}
            
        except KeyError as ex:
            logger.debug('Bad request: %s', ex.message)
            raise bottle.HTTPError(400, exception=InvalidRequest(ex.message))
        except ValueError as ex:
            logger.debug('Bad request: %s', ex.message)
            raise bottle.HTTPError(400, exception=InvalidRequest(ex.message))
        except Exception as ex:
            logger.debug('StackTrace: %s', traceback.format_exc())
            raise bottle.HTTPError(500, exception=PlatformError(ex.message))
        bottle.response.set_header('Location', self.baseUrl + '/devices/' + deviceObject.id)
        bottle.response.status = 201

        return device
        
    def modifyDevice(self, dbSession, deviceId):
            
        if bottle.request.json is None:
            raise bottle.HTTPError(400, exception=InvalidRequest("No json in request object"))
        else:
            deviceDict = bottle.request.json.get('device')
            if deviceDict is None:
                raise bottle.HTTPError(400, exception=InvalidRequest("POST body cannot be empty"))

        try:
            name = deviceDict['name']
            description = deviceDict.get('description')
            role = deviceDict['role']
            address = deviceDict['address']
            routerId = deviceDict['routerId']
            podName = deviceDict['podName']
            username = deviceDict['username']
            password = deviceDict['password']
            
            deviceObject = self.__dao.getObjectById(dbSession, OverlayDevice, deviceId)
            deviceObject.update(name, description, role, address, routerId, podName, username, password)
            self.__dao.updateObjects(dbSession, [deviceObject])
            logger.info("OverlayDevice[id='%s', name='%s']: modified", deviceObject.id, deviceObject.name)
            
            device = {'device': self._populateDevice(deviceObject)}
            
        except (exc.NoResultFound) as ex:
            logger.debug("No Overlay Device found with Id: '%s', exc.NoResultFound: %s", deviceId, ex.message)
            raise bottle.HTTPError(404, exception=OverlayDeviceNotFound(deviceId))
        except KeyError as ex:
            logger.debug('Bad request: %s', ex.message)
            raise bottle.HTTPError(400, exception=InvalidRequest(ex.message))
        except ValueError as ex:
            logger.debug('Bad request: %s', ex.message)
            raise bottle.HTTPError(400, exception=InvalidRequest(ex.message))
        except Exception as ex:
            logger.debug('StackTrace: %s', traceback.format_exc())
            raise bottle.HTTPError(500, exception=PlatformError(ex.message))

        return device

    def deleteDevice(self, dbSession, deviceId):
            
        try:
            deviceObject = self.__dao.getObjectById(dbSession, OverlayDevice, deviceId)
            self.__dao.deleteObject(dbSession, deviceObject)
            logger.info("OverlayDevice[id='%s', name='%s']: deleted", deviceObject.id, deviceObject.name)
        except (exc.NoResultFound) as ex:
            logger.debug("No Overlay Device found with Id: '%s', exc.NoResultFound: %s", deviceId, ex.message)
            raise bottle.HTTPError(404, exception=OverlayDeviceNotFound(deviceId))
        except Exception as ex:
            logger.debug('StackTrace: %s', traceback.format_exc())
            raise bottle.HTTPError(500, exception=PlatformError(ex.message))

        return bottle.HTTPResponse(status=204)
        
    def _populateFabric(self, fabricObject):
        fabric = {}
        fabric['id'] = fabricObject.id
        fabric['name'] = fabricObject.name
        fabric['description'] = fabricObject.description
        fabric['overlayAsn'] = fabricObject.overlayAS
        fabric['routeReflectorAddress'] = fabricObject.routeReflectorAddress
        fabric['uri'] = '%s/fabrics/%s' % (self._getUriPrefix(), fabricObject.id)
        devices = []
        for device in fabricObject.overlay_devices:
            devices.append({'uri': '%s/devices/%s' % (self._getUriPrefix(), device.id)})
        fabric['devices'] = {'device': devices, 'total': len(fabricObject.overlay_devices)}
        tenants = []
        for tenant in fabricObject.overlay_tenants:
            tenants.append({'uri': '%s/tenants/%s' % (self._getUriPrefix(), tenant.id)})
        fabric['tenants'] = {'tenant': tenants, 'total': len(fabricObject.overlay_tenants)}
        return fabric
    
    def getFabrics(self, dbSession):
            
        fabricObjects = self.__dao.getAll(dbSession, OverlayFabric)
        fabrics = []
        for fabricObject in fabricObjects:
            fabrics.append(self._populateFabric(fabricObject))
        
        logger.debug("getFabrics: count %d", len(fabrics))
        
        outputDict = {}
        outputDict['fabric'] = fabrics
        outputDict['total'] = len(fabrics)
        outputDict['uri'] = '%s/fabrics' % (self._getUriPrefix())
        return {'fabrics': outputDict}

    def getFabric(self, dbSession, fabricId):
            
        try:
            fabricObject = self.__dao.getObjectById(dbSession, OverlayFabric, fabricId)
            logger.debug('getFabric: %s', fabricId)
        except (exc.NoResultFound) as ex:
            logger.debug("No Overlay Fabric found with Id: '%s', exc.NoResultFound: %s", fabricId, ex.message)
            raise bottle.HTTPError(404, exception=OverlayFabricNotFound(fabricId))
        except Exception as ex:
            logger.debug('StackTrace: %s', traceback.format_exc())
            raise bottle.HTTPError(500, exception=PlatformError(ex.message))
            
        return {'fabric': self._populateFabric(fabricObject)}
        
    def createFabric(self, dbSession):  
            
        if bottle.request.json is None:
            raise bottle.HTTPError(400, exception=InvalidRequest("No json in request object"))
        else:
            fabricDict = bottle.request.json.get('fabric')
            if fabricDict is None:
                raise bottle.HTTPError(400, exception=InvalidRequest("POST body cannot be empty"))

        try:
            name = fabricDict['name']
            description = fabricDict.get('description')
            overlayAsn = fabricDict['overlayAsn']
            routeReflectorAddress = fabricDict['routeReflectorAddress']
            devices = fabricDict['devices']
            deviceObjects = []
            for device in devices:
                try:
                    deviceId = device.split('/')[-1]
                    deviceObject = self.__dao.getObjectById(dbSession, OverlayDevice, deviceId)
                    logger.debug("Overlay Device '%s' found", deviceId)
                    deviceObjects.append(deviceObject)
                except (exc.NoResultFound) as ex:
                    logger.debug("No Overlay Device found with Id: '%s', exc.NoResultFound: %s", deviceId, ex.message)
                    raise bottle.HTTPError(404, exception=OverlayDeviceNotFound(deviceId))

            fabricObject = self._overlay.createFabric(dbSession, name, description, overlayAsn, routeReflectorAddress, deviceObjects)
            logger.info("OverlayFabric[id='%s', name='%s']: created", fabricObject.id, fabricObject.name)

            fabric = {'fabric': self._populateFabric(fabricObject)}
            
        except KeyError as ex:
            logger.debug('Bad request: %s', ex.message)
            raise bottle.HTTPError(400, exception=InvalidRequest(ex.message))
        except Exception as ex:
            logger.debug('StackTrace: %s', traceback.format_exc())
            raise bottle.HTTPError(500, exception=PlatformError(ex.message))
        bottle.response.set_header('Location', self.baseUrl + '/fabrics/' + fabricObject.id)
        bottle.response.status = 201

        return fabric
        
    def modifyFabric(self, dbSession, fabricId):
            
        if bottle.request.json is None:
            raise bottle.HTTPError(400, exception=InvalidRequest("No json in request object"))
        else:
            fabricDict = bottle.request.json.get('fabric')
            if fabricDict is None:
                raise bottle.HTTPError(400, exception=InvalidRequest("POST body cannot be empty"))

        try:
            name = fabricDict['name']
            description = fabricDict.get('description')
            overlayAsn = fabricDict['overlayAsn']
            routeReflectorAddress = fabricDict['routeReflectorAddress']
            devices = fabricDict['devices']
            fabricObject = self.__dao.getObjectById(dbSession, OverlayFabric, fabricId)
            deviceObjects = []
            for device in devices:
                try:
                    deviceId = device.split('/')[-1]
                    deviceObject = self.__dao.getObjectById(dbSession, OverlayDevice, deviceId)
                    logger.debug("Overlay Device '%s' found", deviceId)
                    deviceObjects.append(deviceObject)
                except (exc.NoResultFound) as ex:
                    logger.debug("No Overlay Device found with Id: '%s', exc.NoResultFound: %s", deviceId, ex.message)
                    raise bottle.HTTPError(404, exception=OverlayDeviceNotFound(deviceId))

            fabricObject.clearDevices()
            fabricObject.update(name, description, overlayAsn, routeReflectorAddress, deviceObjects)
            self.__dao.updateObjects(dbSession, [fabricObject])
            logger.info("OverlayFabric[id='%s', name='%s']: modified", fabricObject.id, fabricObject.name)

            fabric = {'fabric': self._populateFabric(fabricObject)}

        except (exc.NoResultFound) as ex:
            logger.debug("No Overlay Fabric found with Id: '%s', exc.NoResultFound: %s", fabricId, ex.message)
            raise bottle.HTTPError(404, exception=OverlayFabricNotFound(fabricId))
        except KeyError as ex:
            logger.debug('Bad request: %s', ex.message)
            raise bottle.HTTPError(400, exception=InvalidRequest(ex.message))
        except Exception as ex:
            logger.debug('StackTrace: %s', traceback.format_exc())
            raise bottle.HTTPError(500, exception=PlatformError(ex.message))
            
        return fabric
        
    def deleteFabric(self, dbSession, fabricId):
            
        try:
            fabricObject = self.__dao.getObjectById(dbSession, OverlayFabric, fabricId)
            logger.info("OverlayFabric[id='%s', name='%s']: delete request is submitted", fabricObject.id, fabricObject.name)
            self._overlay.deleteFabric(dbSession, fabricObject)
        except (exc.NoResultFound) as ex:
            logger.debug("No Overlay Fabric found with Id: '%s', exc.NoResultFound: %s", fabricId, ex.message)
            raise bottle.HTTPError(404, exception=OverlayFabricNotFound(fabricId))
        except Exception as ex:
            logger.debug('StackTrace: %s', traceback.format_exc())
            raise bottle.HTTPError(500, exception=PlatformError(ex.message))

        return bottle.HTTPResponse(status=204)

    def _populateTenant(self, tenantObject):
        tenant = {}      
        tenant['id'] = tenantObject.id
        tenant['name'] = tenantObject.name
        tenant['description'] = tenantObject.description
        tenant['uri'] = '%s/tenants/%s' % (self._getUriPrefix(), tenantObject.id)
        tenant['fabric'] = '%s/fabrics/%s' % (self._getUriPrefix(), tenantObject.overlay_fabric.id)
        vrfs = []
        for vrf in tenantObject.overlay_vrfs:
            vrfs.append({'uri': '%s/vrfs/%s' % (self._getUriPrefix(), vrf.id)})
        tenant['vrfs'] = {'vrf': vrfs, 'total': len(tenantObject.overlay_vrfs)}
        return tenant
    
    def getTenants(self, dbSession):
            
        tenantObjects = self.__dao.getAll(dbSession, OverlayTenant)
        tenants = []
        for tenantObject in tenantObjects:
            tenants.append(self._populateTenant(tenantObject))
        
        logger.debug("getTenants: count %d", len(tenants))
        
        outputDict = {}
        outputDict['tenant'] = tenants
        outputDict['total'] = len(tenants)
        outputDict['uri'] = '%s/tenants' % (self._getUriPrefix())
        return {'tenants': outputDict}

    def getTenant(self, dbSession, tenantId):
            
        try:
            tenantObject = self.__dao.getObjectById(dbSession, OverlayTenant, tenantId)
            logger.debug('getTenant: %s', tenantId)
        except (exc.NoResultFound) as ex:
            logger.debug("No Overlay Tenant found with Id: '%s', exc.NoResultFound: %s", tenantId, ex.message)
            raise bottle.HTTPError(404, exception=OverlayTenantNotFound(tenantId))
        except Exception as ex:
            logger.debug('StackTrace: %s', traceback.format_exc())
            raise bottle.HTTPError(500, exception=PlatformError(ex.message))
        
        return {'tenant': self._populateTenant(tenantObject)}
        
    def createTenant(self, dbSession):  
            
        if bottle.request.json is None:
            raise bottle.HTTPError(400, exception=InvalidRequest("No json in request object"))
        else:
            tenantDict = bottle.request.json.get('tenant')
            if tenantDict is None:
                raise bottle.HTTPError(400, exception=InvalidRequest("POST body cannot be empty"))

        try:
            name = tenantDict['name']
            description = tenantDict.get('description')
            fabricId = tenantDict['fabric'].split('/')[-1]
            try:
                fabricObject = self.__dao.getObjectById(dbSession, OverlayFabric, fabricId)
                logger.debug("Overlay Fabric '%s' found", fabricId)
            except (exc.NoResultFound) as ex:
                logger.debug("No Overlay Fabric found with Id: '%s', exc.NoResultFound: %s", fabricId, ex.message)
                raise bottle.HTTPError(404, exception=OverlayFabricNotFound(fabricId))
                
            tenantObject = self._overlay.createTenant(dbSession, name, description, fabricObject)
            logger.info("OverlayTenant[id='%s', name='%s']: created", tenantObject.id, tenantObject.name)

            tenant = {'tenant': self._populateTenant(tenantObject)}
            
        except KeyError as ex:
            logger.debug('Bad request: %s', ex.message)
            raise bottle.HTTPError(400, exception=InvalidRequest(ex.message))
        except Exception as ex:
            logger.debug('StackTrace: %s', traceback.format_exc())
            raise bottle.HTTPError(500, exception=PlatformError(ex.message))
        bottle.response.set_header('Location', self.baseUrl + '/tenants/' + tenantObject.id)
        bottle.response.status = 201

        return tenant
        
    def modifyTenant(self, dbSession, tenantId):
            
        if bottle.request.json is None:
            raise bottle.HTTPError(400, exception=InvalidRequest("No json in request object"))
        else:
            tenantDict = bottle.request.json.get('tenant')
            if tenantDict is None:
                raise bottle.HTTPError(400, exception=InvalidRequest("POST body cannot be empty"))

        try:
            name = tenantDict['name']
            description = tenantDict.get('description')
            
            tenantObject = self.__dao.getObjectById(dbSession, OverlayTenant, tenantId)
            tenantObject.update(name, description)
            self.__dao.updateObjects(dbSession, [tenantObject])
            logger.info("OverlayTenant[id='%s', name='%s']: modified", tenantObject.id, tenantObject.name)

            tenant = {'tenant': self._populateTenant(tenantObject)}
            
        except (exc.NoResultFound) as ex:
            logger.debug("No Overlay Tenant found with Id: '%s', exc.NoResultFound: %s", tenantId, ex.message)
            raise bottle.HTTPError(404, exception=OverlayTenantNotFound(tenantId))
        except KeyError as ex:
            logger.debug('Bad request: %s', ex.message)
            raise bottle.HTTPError(400, exception=InvalidRequest(ex.message))
        except Exception as ex:
            logger.debug('StackTrace: %s', traceback.format_exc())
            raise bottle.HTTPError(500, exception=PlatformError(ex.message))

        return tenant
        
    def deleteTenant(self, dbSession, tenantId):
            
        try:
            tenantObject = self.__dao.getObjectById(dbSession, OverlayTenant, tenantId)
            self.__dao.deleteObject(dbSession, tenantObject)
            logger.info("OverlayTenant[id='%s', name='%s']: deleted", tenantObject.id, tenantObject.name)
        except (exc.NoResultFound) as ex:
            logger.debug("No Overlay Tenant found with Id: '%s', exc.NoResultFound: %s", tenantId, ex.message)
            raise bottle.HTTPError(404, exception=OverlayTenantNotFound(tenantId))
        except Exception as ex:
            logger.debug('StackTrace: %s', traceback.format_exc())
            raise bottle.HTTPError(500, exception=PlatformError(ex.message))

        return bottle.HTTPResponse(status=204)

    def _populateVrf(self, vrfObject):
        vrf = {}      
        vrf['id'] = vrfObject.id
        vrf['name'] = vrfObject.name
        vrf['description'] = vrfObject.description
        vrf['routedVnid'] = vrfObject.routedVnid
        vrf['loopbackAddress'] = vrfObject.loopbackAddress
        vrf['uri'] = '%s/vrfs/%s' % (self._getUriPrefix(), vrfObject.id)
        vrf['tenant'] = '%s/tenants/%s' % (self._getUriPrefix(), vrfObject.overlay_tenant.id)
        networks = []
        for network in vrfObject.overlay_networks:
            networks.append({'uri': '%s/networks/%s' % (self._getUriPrefix(), network.id)})
        vrf['networks'] = {'network': networks, 'total': len(vrfObject.overlay_networks)}
        vrf['status'] = {}
        vrf['status']['brief'] = '%s/vrfs/%s/status?mode=brief' % (self._getUriPrefix(), vrfObject.id)
        vrf['status']['detail'] = '%s/vrfs/%s/status?mode=detail' % (self._getUriPrefix(), vrfObject.id)
        return vrf
    
    def getVrfs(self, dbSession):
            
        vrfObjects = self.__dao.getAll(dbSession, OverlayVrf)
        vrfs = []
        for vrfObject in vrfObjects:
            vrfs.append(self._populateVrf(vrfObject))
        
        logger.debug("getVrfs: count %d", len(vrfs))
        
        outputDict = {}
        outputDict['vrf'] = vrfs
        outputDict['total'] = len(vrfs)
        outputDict['uri'] = '%s/vrfs' % (self._getUriPrefix())
        return {'vrfs': outputDict}

    def getVrf(self, dbSession, vrfId):
            
        try:
            vrfObject = self.__dao.getObjectById(dbSession, OverlayVrf, vrfId)
            logger.debug('getVrf: %s', vrfId)
        except (exc.NoResultFound) as ex:
            logger.debug("No Overlay Vrf found with Id: '%s', exc.NoResultFound: %s", vrfId, ex.message)
            raise bottle.HTTPError(404, exception=OverlayVrfNotFound(vrfId))
        except Exception as ex:
            logger.debug('StackTrace: %s', traceback.format_exc())
            raise bottle.HTTPError(500, exception=PlatformError(ex.message))
        
        return {'vrf': self._populateVrf(vrfObject)}
        
    def _getVrfStatusBrief(self, dbSession, vrfId):
        try:
            # get all object status under this VRF
            # XXX when inserting into OverlayDeployStatus table, make sure to insert a row for OverlayFabric too
            # so the same OverlayFabric configlet would be inserted NxM times if we have <N> devices and <M> VRFs under
            # this OverlayFabric
            # a little trade-off between normalization and simple schema for OverlayDeployStatus table
            statusAll = dbSession.query(OverlayDeployStatus).filter(OverlayDeployStatus.overlay_vrf_id == vrfId).all()
        except Exception as ex:
            logger.debug('StackTrace: %s', traceback.format_exc())
            raise bottle.HTTPError(500, exception=PlatformError(ex.message))
        
        logger.debug("getVrfStatusBrief: count %d", len(statusAll))
        
        unknownObjects = 0
        successObjects = 0
        failureObjects = 0
        progressObjects = 0
        for status in statusAll:
            if status.status == 'unknown':
                unknownObjects += 1
            elif status.status == 'success':
                successObjects += 1
            elif status.status == 'failure':
                failureObjects += 1
            elif status.status == 'progress':
                progressObjects += 1
                
        # aggregated status will be progress only if there is no failure
        if failureObjects > 0:
            aggregatedStatus = 'failure'
        elif progressObjects > 0:
            aggregatedStatus = 'progress'
        elif unknownObjects > 0:
            aggregatedStatus = 'unknown'
        else:
            aggregatedStatus = 'success'
        
        outputDict = {}
        outputDict['status'] = aggregatedStatus
        outputDict['uri'] = '%s/vrfs/%s/status?mode=brief' % (self._getUriPrefix(), vrfId)
        return {'statusBrief': outputDict}
        
    def _populateObjectDetail(self, objectUrl, objectDevices):
        objectDetail = {}
        configletOnDevice = []
        
        for status in objectDevices:
            configletOnDevice.append({'device': status.overlay_device.name, 'configlet': status.configlet, 'reason': status.statusReason})
        
        objectDetail['uri'] = objectUrl
        objectDetail['configs'] = configletOnDevice
        objectDetail['total'] = len(configletOnDevice)
        
        return objectDetail
        
    def _getVrfStatusDetail(self, dbSession, vrfId):
        try:
            # get all object status under this VRF
            # XXX when caller wants to insert an object into OverlayDeployStatus table, caller should also manually 
            # insert a row to represent the owner OverlayFabric object as well.
            # so the same OverlayFabric configlet would be inserted NxM times if we have <N> devices and <M> VRFs under
            # this OverlayFabric.
            # This is where we trade-off normalization for simple schema for OverlayDeployStatus table
            statusAll = dbSession.query(OverlayDeployStatus, OverlayDevice).\
                filter(OverlayDeployStatus.overlay_device_id == OverlayDevice.id).\
                filter(OverlayDeployStatus.overlay_vrf_id == vrfId).\
                order_by(OverlayDeployStatus.status, OverlayDeployStatus.object_url, OverlayDevice.name).all()
        except Exception as ex:
            logger.debug('StackTrace: %s', traceback.format_exc())
            raise bottle.HTTPError(500, exception=PlatformError(ex.message))
        
        logger.debug("getVrfStatusDetail: count %d", len(statusAll))
        
        unknownObjects = []
        unknownObjectDict = {}
        successObjects = []
        successObjectDict = {}
        failureObjects = []
        failureObjectDict = {}
        progressObjects = []
        progressObjectDict = {}
        
        # Note following code relies on the fact that the query result is ordered by status first, then by object_url, 
        # lastly by device name.
        for status, device in statusAll:
            if status.status == 'unknown':
                if status.object_url not in unknownObjectDict:
                    unknownObjectDict[status.object_url] = []
                unknownObjectDevices = unknownObjectDict[status.object_url]
                unknownObjectDevices.append(status)
            elif status.status == 'success':
                if status.object_url not in successObjectDict:
                    successObjectDict[status.object_url] = []
                successObjectDevices = successObjectDict[status.object_url]
                successObjectDevices.append(status)
            elif status.status == 'failure':
                if status.object_url not in failureObjectDict:
                    failureObjectDict[status.object_url] = []
                failureObjectDevices = failureObjectDict[status.object_url]
                failureObjectDevices.append(status)
            elif status.status == 'progress':
                if status.object_url not in progressObjectDict:
                    progressObjectDict[status.object_url] = []
                progressObjectDevices = progressObjectDict[status.object_url]
                progressObjectDevices.append(status)
                
        for unknownObjectUrl, unknownObjectDevices in unknownObjectDict.iteritems():
            unknownObjects.append(self._populateObjectDetail(unknownObjectUrl, unknownObjectDevices))
        for successObjectUrl, successObjectDevices in successObjectDict.iteritems():
            successObjects.append(self._populateObjectDetail(successObjectUrl, successObjectDevices))
        for failureObjectUrl, failureObjectDevices in failureObjectDict.iteritems():
            failureObjects.append(self._populateObjectDetail(failureObjectUrl, failureObjectDevices))
        for progressObjectUrl, progressObjectDevices in progressObjectDict.iteritems():
            progressObjects.append(self._populateObjectDetail(progressObjectUrl, progressObjectDevices))
                
        # aggregated status will be progress only if there is no failure
        if len(failureObjects) > 0:
            aggregatedStatus = 'failure'
        elif len(progressObjects) > 0:
            aggregatedStatus = 'progress'
        elif len(unknownObjects) > 0:
            aggregatedStatus = 'unknown'
        else:
            aggregatedStatus = 'success'
        
        outputDict = {}
        outputDict['status'] = aggregatedStatus
        outputDict['uri'] = '%s/vrfs/%s/status?mode=detail' % (self._getUriPrefix(), vrfId)
        outputDict['unknown'] = {'objects': unknownObjects, 'total': len(unknownObjects)}
        outputDict['success'] = {'objects': successObjects, 'total': len(successObjects)}
        outputDict['failure'] = {'objects': failureObjects, 'total': len(failureObjects)}
        outputDict['progress'] = {'objects': progressObjects, 'total': len(progressObjects)}
        return {'statusDetail': outputDict}
        
    def getVrfStatus(self, dbSession, vrfId):
            
        if bottle.request.query.mode == 'brief':
            return self._getVrfStatusBrief(dbSession, vrfId)
        elif bottle.request.query.mode == 'detail':
            return self._getVrfStatusDetail(dbSession, vrfId)
        else:
            raise bottle.HTTPError(400, exception=InvalidRequest("Invalid mode '%s'" % bottle.request.query.mode))
    
    def createVrf(self, dbSession):  
            
        if bottle.request.json is None:
            raise bottle.HTTPError(400, exception=InvalidRequest("No json in request object"))
        else:
            vrfDict = bottle.request.json.get('vrf')
            if vrfDict is None:
                raise bottle.HTTPError(400, exception=InvalidRequest("POST body cannot be empty"))

        try:
            name = vrfDict['name']
            description = vrfDict.get('description')
            routedVnid = vrfDict.get('routedVnid')
            loopbackAddress = vrfDict.get('loopbackAddress')
            tenantId = vrfDict['tenant'].split('/')[-1]
            try:
                tenantObject = self.__dao.getObjectById(dbSession, OverlayTenant, tenantId)
            except (exc.NoResultFound) as ex:
                logger.debug("No Overlay Tenant found with Id: '%s', exc.NoResultFound: %s", tenantId, ex.message)
                raise bottle.HTTPError(404, exception=OverlayTenantNotFound(tenantId))
                
            vrfObject = self._overlay.createVrf(dbSession, name, description, routedVnid, loopbackAddress, tenantObject)
            logger.info("OverlayVrf[id='%s', name='%s']: created", vrfObject.id, vrfObject.name)
            vrf = {'vrf': self._populateVrf(vrfObject)}
            
        except KeyError as ex:
            logger.debug('Bad request: %s', ex.message)
            raise bottle.HTTPError(400, exception=InvalidRequest(ex.message))
        except Exception as ex:
            logger.debug('StackTrace: %s', traceback.format_exc())
            raise bottle.HTTPError(500, exception=PlatformError(ex.message))
        bottle.response.set_header('Location', self.baseUrl + '/vrfs/' + vrfObject.id)
        bottle.response.status = 201

        return vrf
        
    def modifyVrf(self, dbSession, vrfId):
            
        if bottle.request.json is None:
            raise bottle.HTTPError(400, exception=InvalidRequest("No json in request object"))
        else:
            vrfDict = bottle.request.json.get('vrf')
            if vrfDict is None:
                raise bottle.HTTPError(400, exception=InvalidRequest("POST body cannot be empty"))

        try:
            name = vrfDict['name']
            description = vrfDict.get('description')
            routedVnid = vrfDict['routedVnid']
            loopbackAddress = vrfDict.get('loopbackAddress')
            
            vrfObject = self.__dao.getObjectById(dbSession, OverlayVrf, vrfId)
            vrfObject.update(name, description, routedVnid, loopbackAddress)
            self.__dao.updateObjects(dbSession, [vrfObject])
            logger.info("OverlayVrf[id='%s', name='%s']: modified", vrfObject.id, vrfObject.name)
            
            vrf = {'vrf': self._populateVrf(vrfObject)}
            
        except (exc.NoResultFound) as ex:
            logger.debug("No Overlay Vrf found with Id: '%s', exc.NoResultFound: %s", vrfId, ex.message)
            raise bottle.HTTPError(404, exception=OverlayVrfNotFound(vrfId))
        except KeyError as ex:
            logger.debug('Bad request: %s', ex.message)
            raise bottle.HTTPError(400, exception=InvalidRequest(ex.message))
        except Exception as ex:
            logger.debug('StackTrace: %s', traceback.format_exc())
            raise bottle.HTTPError(500, exception=PlatformError(ex.message))

        return vrf

    def deleteVrf(self, dbSession, vrfId):
            
        try:
            vrfObject = self.__dao.getObjectById(dbSession, OverlayVrf, vrfId)
            logger.info("OverlayVrf[id='%s', name='%s']: delete request is submitted", vrfObject.id, vrfObject.name)
            self._overlay.deleteVrf(dbSession, vrfObject)
        except (exc.NoResultFound) as ex:
            logger.debug("No Overlay Vrf found with Id: '%s', exc.NoResultFound: %s", vrfId, ex.message)
            raise bottle.HTTPError(404, exception=OverlayVrfNotFound(vrfId))
        except Exception as ex:
            logger.debug('StackTrace: %s', traceback.format_exc())
            raise bottle.HTTPError(500, exception=PlatformError(ex.message))

        return bottle.HTTPResponse(status=204)
        
    def _populateNetwork(self, networkObject):
        network = {}      
        network['id'] = networkObject.id
        network['name'] = networkObject.name
        network['description'] = networkObject.description
        network['vlanid'] = networkObject.vlanid
        network['vnid'] = networkObject.vnid
        network['pureL3Int'] = networkObject.pureL3Int
        network['uri'] = '%s/networks/%s' % (self._getUriPrefix(), networkObject.id)
        network['vrf'] = '%s/vrfs/%s' % (self._getUriPrefix(), networkObject.overlay_vrf.id)
        subnets = []
        for subnet in networkObject.overlay_subnets:
            subnets.append({'uri': '%s/subnets/%s' % (self._getUriPrefix(), subnet.id)})
        network['subnets'] = {'subnet': subnets, 'total': len(networkObject.overlay_subnets)}
        l2aps = []
        for l2ap in networkObject.overlay_l2aps:
            l2aps.append({'uri': '%s%s' % (self._getUriPrefix(), l2ap.getUrl()), 'type': '%s' % (l2ap.type)})
        network['l2aps'] = {'l2ap': l2aps, 'total': len(networkObject.overlay_l2aps)}
        return network
        
    def getNetworks(self, dbSession):
            
        networkObjects = self.__dao.getAll(dbSession, OverlayNetwork)
        networks = []
        for networkObject in networkObjects:
            networks.append(self._populateNetwork(networkObject))
        
        logger.debug("getNetworks: count %d", len(networks))
        
        outputDict = {}
        outputDict['network'] = networks
        outputDict['total'] = len(networks)
        outputDict['uri'] = '%s/networks' % (self._getUriPrefix())
        return {'networks': outputDict}

    def getNetwork(self, dbSession, networkId):
            
        try:
            networkObject = self.__dao.getObjectById(dbSession, OverlayNetwork, networkId)
            logger.debug('getNetwork: %s', networkId)
        except (exc.NoResultFound) as ex:
            logger.debug("No Overlay Network found with Id: '%s', exc.NoResultFound: %s", networkId, ex.message)
            raise bottle.HTTPError(404, exception=OverlayNetworkNotFound(networkId))
        except Exception as ex:
            logger.debug('StackTrace: %s', traceback.format_exc())
            raise bottle.HTTPError(500, exception=PlatformError(ex.message))
        
        return {'network': self._populateNetwork(networkObject)}
        
    def createNetwork(self, dbSession):  
            
        if bottle.request.json is None:
            raise bottle.HTTPError(400, exception=InvalidRequest("No json in request object"))
        else:
            networkDict = bottle.request.json.get('network')
            if networkDict is None:
                raise bottle.HTTPError(400, exception=InvalidRequest("POST body cannot be empty"))

        try:
            name = networkDict['name']
            description = networkDict.get('description')
            vlanid = networkDict.get('vlanid')
            vnid = networkDict.get('vnid')
            pureL3Int = networkDict.get('pureL3Int', False)
            vrfId = networkDict['vrf'].split('/')[-1]
            try:
                vrfObject = self.__dao.getObjectById(dbSession, OverlayVrf, vrfId)
            except (exc.NoResultFound) as ex:
                logger.debug("No Overlay Vrf found with Id: '%s', exc.NoResultFound: %s", vrfId, ex.message)
                raise bottle.HTTPError(404, exception=OverlayVrfNotFound(vrfId))
                
            networkObject = self._overlay.createNetwork(dbSession, name, description, vrfObject, vlanid, vnid, pureL3Int)
            logger.info("OverlayNetwork[id='%s', name='%s']: created", networkObject.id, networkObject.name)

            network = {'network': self._populateNetwork(networkObject)}
            
        except KeyError as ex:
            logger.debug('Bad request: %s', ex.message)
            raise bottle.HTTPError(400, exception=InvalidRequest(ex.message))
        except Exception as ex:
            logger.debug('StackTrace: %s', traceback.format_exc())
            raise bottle.HTTPError(500, exception=PlatformError(ex.message))
        bottle.response.set_header('Location', self.baseUrl + '/networks/' + networkObject.id)
        bottle.response.status = 201

        return network
        
    def modifyNetwork(self, dbSession, networkId):
            
        if bottle.request.json is None:
            raise bottle.HTTPError(400, exception=InvalidRequest("No json in request object"))
        else:
            networkDict = bottle.request.json.get('network')
            if networkDict is None:
                raise bottle.HTTPError(400, exception=InvalidRequest("POST body cannot be empty"))

        try:
            name = networkDict['name']
            description = networkDict.get('description')
            vlanid = networkDict.get('vlanid')
            vnid = networkDict.get('vnid')
            pureL3Int = networkDict.get('pureL3Int', False)
            
            networkObject = self.__dao.getObjectById(dbSession, OverlayNetwork, networkId)
            networkObject.update(name, description, vlanid, vnid, pureL3Int)
            self.__dao.updateObjects(dbSession, [networkObject])
            logger.info("OverlayNetwork[id='%s', name='%s']: modified", networkObject.id, networkObject.name)
            
            network = {'network': self._populateNetwork(networkObject)}
            
        except (exc.NoResultFound) as ex:
            logger.debug("No Overlay Network found with Id: '%s', exc.NoResultFound: %s", networkId, ex.message)
            raise bottle.HTTPError(404, exception=OverlayNetworkNotFound(networkId))
        except KeyError as ex:
            logger.debug('Bad request: %s', ex.message)
            raise bottle.HTTPError(400, exception=InvalidRequest(ex.message))
        except Exception as ex:
            logger.debug('StackTrace: %s', traceback.format_exc())
            raise bottle.HTTPError(500, exception=PlatformError(ex.message))

        return network

    def deleteNetwork(self, dbSession, networkId):
            
        try:
            networkObject = self.__dao.getObjectById(dbSession, OverlayNetwork, networkId)
            logger.info("OverlayNetwork[id='%s', name='%s']: delete request is submitted", networkObject.id, networkObject.name)
            self._overlay.deleteNetwork(dbSession, networkObject)
        except (exc.NoResultFound) as ex:
            logger.debug("No Overlay Network found with Id: '%s', exc.NoResultFound: %s", networkId, ex.message)
            raise bottle.HTTPError(404, exception=OverlayNetworkNotFound(networkId))
        except Exception as ex:
            logger.debug('StackTrace: %s', traceback.format_exc())
            raise bottle.HTTPError(500, exception=PlatformError(ex.message))

        return bottle.HTTPResponse(status=204)

    def _populateSubnet(self, subnetObject):
        subnet = {}      
        subnet['id'] = subnetObject.id
        subnet['name'] = subnetObject.name
        subnet['description'] = subnetObject.description
        subnet['cidr'] = subnetObject.cidr
        subnet['uri'] = '%s/subnets/%s' % (self._getUriPrefix(), subnetObject.id)
        subnet['network'] = '%s/networks/%s' % (self._getUriPrefix(), subnetObject.overlay_network.id)
        l3ports = []
        for l3port in subnetObject.overlay_l3ports:
            l3ports.append({'uri': '%s/l3ports/%s' % (self._getUriPrefix(), l3port.id)})
        subnet['l3ports'] = {'l3port': l3ports, 'total': len(subnetObject.overlay_l3ports)}
        return subnet
        
    def getSubnets(self, dbSession):
            
        subnetObjects = self.__dao.getAll(dbSession, OverlaySubnet)
        subnets = []
        for subnetObject in subnetObjects:
            subnets.append(self._populateSubnet(subnetObject))
        
        logger.debug("getSubnets: count %d", len(subnets))
        
        outputDict = {}
        outputDict['subnet'] = subnets
        outputDict['total'] = len(subnets)
        outputDict['uri'] = '%s/subnets' % (self._getUriPrefix())
        return {'subnets': outputDict}

    def getSubnet(self, dbSession, subnetId):
            
        try:
            subnetObject = self.__dao.getObjectById(dbSession, OverlaySubnet, subnetId)
            logger.debug('getSubnet: %s', subnetId)
        except (exc.NoResultFound) as ex:
            logger.debug("No Overlay Subnet found with Id: '%s', exc.NoResultFound: %s", subnetId, ex.message)
            raise bottle.HTTPError(404, exception=OverlaySubnetNotFound(subnetId))
        except Exception as ex:
            logger.debug('StackTrace: %s', traceback.format_exc())
            raise bottle.HTTPError(500, exception=PlatformError(ex.message))
        
        return {'subnet': self._populateSubnet(subnetObject)}
        
    def createSubnet(self, dbSession):  
            
        if bottle.request.json is None:
            raise bottle.HTTPError(400, exception=InvalidRequest("No json in request object"))
        else:
            subnetDict = bottle.request.json.get('subnet')
            if subnetDict is None:
                raise bottle.HTTPError(400, exception=InvalidRequest("POST body cannot be empty"))

        try:
            name = subnetDict['name']
            description = subnetDict.get('description')
            cidr = subnetDict['cidr']
            networkId = subnetDict['network'].split('/')[-1]
            try:
                networkObject = self.__dao.getObjectById(dbSession, OverlayNetwork, networkId)
            except (exc.NoResultFound) as ex:
                logger.debug("No Overlay Network found with Id: '%s', exc.NoResultFound: %s", networkId, ex.message)
                raise bottle.HTTPError(404, exception=OverlayNetworkNotFound(networkId))
                
            subnetObject = self._overlay.createSubnet(dbSession, name, description, networkObject, cidr)
            logger.info("OverlaySubnet[id='%s', name='%s']: created", subnetObject.id, subnetObject.name)

            subnet = {'subnet': self._populateSubnet(subnetObject)}
            
        except KeyError as ex:
            logger.debug('Bad request: %s', ex.message)
            raise bottle.HTTPError(400, exception=InvalidRequest(ex.message))
        except Exception as ex:
            logger.debug('StackTrace: %s', traceback.format_exc())
            raise bottle.HTTPError(500, exception=PlatformError(ex.message))
        bottle.response.set_header('Location', self.baseUrl + '/subnets/' + subnetObject.id)
        bottle.response.status = 201

        return subnet
        
    def modifySubnet(self, dbSession, subnetId):
            
        if bottle.request.json is None:
            raise bottle.HTTPError(400, exception=InvalidRequest("No json in request object"))
        else:
            subnetDict = bottle.request.json.get('subnet')
            if subnetDict is None:
                raise bottle.HTTPError(400, exception=InvalidRequest("POST body cannot be empty"))

        try:
            name = subnetDict['name']
            description = subnetDict.get('description')
            cidr = subnetDict['cidr']
            
            subnetObject = self.__dao.getObjectById(dbSession, OverlaySubnet, subnetId)
            subnetObject.update(name, description, cidr)
            self.__dao.updateObjects(dbSession, [subnetObject])
            logger.info("OverlaySubnet[id='%s', name='%s']: modified", subnetObject.id, subnetObject.name)
            
            subnet = {'subnet': self._populateSubnet(subnetObject)}
            
        except (exc.NoResultFound) as ex:
            logger.debug("No Overlay Subnet found with Id: '%s', exc.NoResultFound: %s", subnetId, ex.message)
            raise bottle.HTTPError(404, exception=OverlaySubnetNotFound(subnetId))
        except KeyError as ex:
            logger.debug('Bad request: %s', ex.message)
            raise bottle.HTTPError(400, exception=InvalidRequest(ex.message))
        except Exception as ex:
            logger.debug('StackTrace: %s', traceback.format_exc())
            raise bottle.HTTPError(500, exception=PlatformError(ex.message))

        return subnet

    def deleteSubnet(self, dbSession, subnetId):
            
        try:
            subnetObject = self.__dao.getObjectById(dbSession, OverlaySubnet, subnetId)
            logger.info("OverlaySubnet[id='%s', cidr='%s']: delete request is submitted", subnetObject.id, subnetObject.cidr)
            self._overlay.deleteSubnet(dbSession, subnetObject)
        except (exc.NoResultFound) as ex:
            logger.debug("No Overlay Subnet found with Id: '%s', exc.NoResultFound: %s", subnetId, ex.message)
            raise bottle.HTTPError(404, exception=OverlaySubnetNotFound(subnetId))
        except Exception as ex:
            logger.debug('StackTrace: %s', traceback.format_exc())
            raise bottle.HTTPError(500, exception=PlatformError(ex.message))

        return bottle.HTTPResponse(status=204)

    def _populateL3port(self, l3portObject):
        l3port = {}      
        l3port['id'] = l3portObject.id
        l3port['name'] = l3portObject.name
        l3port['description'] = l3portObject.description
        l3port['uri'] = '%s/l3ports/%s' % (self._getUriPrefix(), l3portObject.id)
        l3port['subnet'] = '%s/subnets/%s' % (self._getUriPrefix(), l3portObject.overlay_subnet.id)
        return l3port
        
    def getL3ports(self, dbSession):
            
        l3portObjects = self.__dao.getAll(dbSession, OverlayL3port)
        l3ports = []
        for l3portObject in l3portObjects:
            l3ports.append(self._populateL3port(l3portObject))
        
        logger.debug("getL3ports: count %d", len(l3ports))
        
        outputDict = {}
        outputDict['l3port'] = l3ports
        outputDict['total'] = len(l3ports)
        outputDict['uri'] = '%s/l3ports' % (self._getUriPrefix())
        return {'l3ports': outputDict}

    def getL3port(self, dbSession, l3portId):
            
        try:
            l3portObject = self.__dao.getObjectById(dbSession, OverlayL3port, l3portId)
            logger.debug('getL3port: %s', l3portId)
        except (exc.NoResultFound) as ex:
            logger.debug("No Overlay L3port found with Id: '%s', exc.NoResultFound: %s", l3portId, ex.message)
            raise bottle.HTTPError(404, exception=OverlayL3portNotFound(l3portId))
        except Exception as ex:
            logger.debug('StackTrace: %s', traceback.format_exc())
            raise bottle.HTTPError(500, exception=PlatformError(ex.message))
        
        return {'l3port': self._populateL3port(l3portObject)}
        
    def createL3port(self, dbSession):  
            
        if bottle.request.json is None:
            raise bottle.HTTPError(400, exception=InvalidRequest("No json in request object"))
        else:
            l3portDict = bottle.request.json.get('l3port')
            if l3portDict is None:
                raise bottle.HTTPError(400, exception=InvalidRequest("POST body cannot be empty"))

        try:
            name = l3portDict['name']
            description = l3portDict.get('description')
            subnetId = l3portDict['subnet'].split('/')[-1]
            try:
                subnetObject = self.__dao.getObjectById(dbSession, OverlaySubnet, subnetId)
            except (exc.NoResultFound) as ex:
                logger.debug("No Overlay Subnet found with Id: '%s', exc.NoResultFound: %s", subnetId, ex.message)
                raise bottle.HTTPError(404, exception=OverlaySubnetNotFound(subnetId))
                
            l3portObject = self._overlay.createL3port(dbSession, name, description, subnetObject)
            logger.info("OverlayL3port[id='%s', name='%s']: created", l3portObject.id, l3portObject.name)

            l3port = {'l3port': self._populateL3port(l3portObject)}
            
        except KeyError as ex:
            logger.debug('Bad request: %s', ex.message)
            raise bottle.HTTPError(400, exception=InvalidRequest(ex.message))
        except Exception as ex:
            logger.debug('StackTrace: %s', traceback.format_exc())
            raise bottle.HTTPError(500, exception=PlatformError(ex.message))
        bottle.response.set_header('Location', self.baseUrl + '/l3ports/' + l3portObject.id)
        bottle.response.status = 201

        return l3port
        
    def modifyL3port(self, dbSession, l3portId):
            
        if bottle.request.json is None:
            raise bottle.HTTPError(400, exception=InvalidRequest("No json in request object"))
        else:
            l3portDict = bottle.request.json.get('l3port')
            if l3portDict is None:
                raise bottle.HTTPError(400, exception=InvalidRequest("POST body cannot be empty"))

        try:
            name = l3portDict['name']
            description = l3portDict.get('description')
            
            l3portObject = self.__dao.getObjectById(dbSession, OverlayL3port, l3portId)
            l3portObject.update(name, description)
            self.__dao.updateObjects(dbSession, [l3portObject])
            logger.info("OverlayL3port[id='%s', name='%s']: modified", l3portObject.id, l3portObject.name)
            
            l3port = {'l3port': self._populateL3port(l3portObject)}
            
        except (exc.NoResultFound) as ex:
            logger.debug("No Overlay L3port found with Id: '%s', exc.NoResultFound: %s", l3portId, ex.message)
            raise bottle.HTTPError(404, exception=OverlayL3portNotFound(l3portId))
        except KeyError as ex:
            logger.debug('Bad request: %s', ex.message)
            raise bottle.HTTPError(400, exception=InvalidRequest(ex.message))
        except Exception as ex:
            logger.debug('StackTrace: %s', traceback.format_exc())
            raise bottle.HTTPError(500, exception=PlatformError(ex.message))

        return l3port

    def deleteL3port(self, dbSession, l3portId):
            
        try:
            l3portObject = self.__dao.getObjectById(dbSession, OverlayL3port, l3portId)
            self.__dao.deleteObject(dbSession, l3portObject)
            logger.info("OverlayL3port[id='%s', name='%s']: deleted", l3portObject.id, l3portObject.name)
        except (exc.NoResultFound) as ex:
            logger.debug("No Overlay L3port found with Id: '%s', exc.NoResultFound: %s", l3portId, ex.message)
            raise bottle.HTTPError(404, exception=OverlayL3portNotFound(l3portId))
        except Exception as ex:
            logger.debug('StackTrace: %s', traceback.format_exc())
            raise bottle.HTTPError(500, exception=PlatformError(ex.message))

        return bottle.HTTPResponse(status=204)

    def _populateL2port(self, l2portObject):
        l2port = {}      
        l2port['id'] = l2portObject.id
        l2port['name'] = l2portObject.name
        l2port['description'] = l2portObject.description
        l2port['uri'] = '%s/l2ports/%s' % (self._getUriPrefix(), l2portObject.id)
        networks = []
        for network in l2portObject.overlay_networks:
            networks.append({'uri': '%s/networks/%s' % (self._getUriPrefix(), network.id)})
        l2port['networks'] = {'network': networks, 'total': len(l2portObject.overlay_networks)}
        l2port['interface'] = l2portObject.interface
        l2port['device'] = '%s/devices/%s' % (self._getUriPrefix(), l2portObject.overlay_device.id)
        return l2port
        
    def getL2ports(self, dbSession):
            
        l2portObjects = self.__dao.getAll(dbSession, OverlayL2port)
        
        l2ports = []
        for l2portObject in l2portObjects:
            l2ports.append(self._populateL2port(l2portObject))
        
        logger.debug("getL2ports: count %d", len(l2ports))
        
        outputDict = {}
        outputDict['l2port'] = l2ports
        outputDict['total'] = len(l2ports)
        outputDict['uri'] = '%s/l2ports' % (self._getUriPrefix())
        return {'l2ports': outputDict}

    def getL2port(self, dbSession, l2portId):
            
        try:
            l2portObject = self.__dao.getObjectById(dbSession, OverlayL2port, l2portId)
            logger.debug('getL2port: %s', l2portId)
        except (exc.NoResultFound) as ex:
            logger.debug("No Overlay L2port found with Id: '%s', exc.NoResultFound: %s", l2portId, ex.message)
            raise bottle.HTTPError(404, exception=OverlayL2portNotFound(l2portId))
        except Exception as ex:
            logger.debug('StackTrace: %s', traceback.format_exc())
            raise bottle.HTTPError(500, exception=PlatformError(ex.message))
        
        return {'l2port': self._populateL2port(l2portObject)}
    
    def getIdFromUri(self, uri):
        return uri.split("/")[-1]
        
    def getNetworkObjects(self, dbSession, networkUris):
        networkObjects = []
        for networkUri in networkUris:
            id = self.getIdFromUri(networkUri)
            try:
                networkObjects.append(self.__dao.getObjectById(dbSession, OverlayNetwork, id))
            except (exc.NoResultFound) as ex:
                logger.debug("No Overlay Network found with Id: '%s', exc.NoResultFound: %s", id, ex.message)
                raise bottle.HTTPError(404, exception=OverlayNetworkNotFound(id))
        return networkObjects
        
    def createL2port(self, dbSession):  
            
        if bottle.request.json is None:
            raise bottle.HTTPError(400, exception=InvalidRequest("No json in request object"))
        else:
            l2portDict = bottle.request.json.get('l2port')
            if l2portDict is None:
                raise bottle.HTTPError(400, exception=InvalidRequest("POST body cannot be empty"))

        try:
            name = l2portDict['name']
            description = l2portDict.get('description')
            interface = l2portDict['interface']
            networkObjects = self.getNetworkObjects(dbSession, l2portDict['networks'])                
            deviceId = self.getIdFromUri(l2portDict['device'])
            try:
                deviceObject = self.__dao.getObjectById(dbSession, OverlayDevice, deviceId)
            except (exc.NoResultFound) as ex:
                logger.debug("No Overlay Device found with Id: '%s', exc.NoResultFound: %s", deviceId, ex.message)
                raise bottle.HTTPError(404, exception=OverlayDeviceNotFound(deviceId))
                
            l2portObject = self._overlay.createL2port(dbSession, name, description, networkObjects, interface, deviceObject)
            logger.info("OverlayL2port[id='%s', name='%s']: created", l2portObject.id, l2portObject.name)

            l2port = {'l2port': self._populateL2port(l2portObject)}
            
        except KeyError as ex:
            logger.debug('Bad request: %s', ex.message)
            raise bottle.HTTPError(400, exception=InvalidRequest(ex.message))
        except Exception as ex:
            logger.debug('StackTrace: %s', traceback.format_exc())
            raise bottle.HTTPError(500, exception=PlatformError(ex.message))
        bottle.response.set_header('Location', self.baseUrl + '/l2ports/' + l2portObject.id)
        bottle.response.status = 201

        return l2port
        
    def modifyL2port(self, dbSession, l2portId):
            
        if bottle.request.json is None:
            raise bottle.HTTPError(400, exception=InvalidRequest("No json in request object"))
        else:
            l2portDict = bottle.request.json.get('l2port')
            if l2portDict is None:
                raise bottle.HTTPError(400, exception=InvalidRequest("POST body cannot be empty"))

        try:
            name = l2portDict['name']
            description = l2portDict.get('description')
            interface = l2portDict['interface']
            l2portObject = self.__dao.getObjectById(dbSession, OverlayL2port, l2portId)
            networkObjects = self.getNetworkObjects(dbSession, l2portDict['networks'])                
            deviceId = self.getIdFromUri(l2portDict['device'])
            try:
                deviceObject = self.__dao.getObjectById(dbSession, OverlayDevice, deviceId)
            except (exc.NoResultFound) as ex:
                logger.debug("No Overlay Device found with Id: '%s', exc.NoResultFound: %s", deviceId, ex.message)
                raise bottle.HTTPError(404, exception=OverlayDeviceNotFound(deviceId))
            
            l2portObject.clearNetworks()
            l2portObject.update(name, description, networkObjects, interface, deviceObject)
            self.__dao.updateObjects(dbSession, [l2portObject])
            logger.info("OverlayL2port[id='%s', name='%s']: modified", l2portObject.id, l2portObject.name)

            l2port = {'l2port': self._populateL2port(l2portObject)}
            
        except (exc.NoResultFound) as ex:
            logger.debug("No Overlay L2port found with Id: '%s', exc.NoResultFound: %s", l2portId, ex.message)
            raise bottle.HTTPError(404, exception=OverlayL2portNotFound(l2portId))
        except KeyError as ex:
            logger.debug('Bad request: %s', ex.message)
            raise bottle.HTTPError(400, exception=InvalidRequest(ex.message))
        except Exception as ex:
            logger.debug('StackTrace: %s', traceback.format_exc())
            raise bottle.HTTPError(500, exception=PlatformError(ex.message))

        return l2port

    def deleteL2port(self, dbSession, l2portId):
            
        try:
            l2portObject = self.__dao.getObjectById(dbSession, OverlayL2port, l2portId)
            self._overlay.deleteL2port(dbSession, l2portObject)
            logger.info("OverlayL2port[id='%s', name='%s']: delete request is submitted", l2portObject.id, l2portObject.name)
        except (exc.NoResultFound) as ex:
            logger.debug("No Overlay L2port found with Id: '%s', exc.NoResultFound: %s", l2portId, ex.message)
            raise bottle.HTTPError(404, exception=OverlayL2portNotFound(l2portId))
        except Exception as ex:
            logger.debug('StackTrace: %s', traceback.format_exc())
            raise bottle.HTTPError(500, exception=PlatformError(ex.message))

        return bottle.HTTPResponse(status=204)
        
    def _populateAggregatedL2port(self, aggregatedL2portObject):
        aggregatedL2port = {}      
        aggregatedL2port['id'] = aggregatedL2portObject.id
        aggregatedL2port['name'] = aggregatedL2portObject.name
        aggregatedL2port['description'] = aggregatedL2portObject.description
        aggregatedL2port['esi'] = aggregatedL2portObject.esi
        aggregatedL2port['lacp'] = aggregatedL2portObject.lacp
        aggregatedL2port['uri'] = '%s/aggregatedL2ports/%s' % (self._getUriPrefix(), aggregatedL2portObject.id)
        networks = []
        for network in aggregatedL2portObject.overlay_networks:
            networks.append({'uri': '%s/networks/%s' % (self._getUriPrefix(), network.id)})
        aggregatedL2port['networks'] = {'network': networks, 'total': len(aggregatedL2portObject.overlay_networks)}
        members = []
        for member in aggregatedL2portObject.members:
            members.append({'device': '%s/devices/%s' % (self._getUriPrefix(), member.overlay_device_id), 'interface': member.interface})
        aggregatedL2port['members'] = {'member': members, 'total': len(aggregatedL2portObject.members)}
        return aggregatedL2port
        
    def getAggregatedL2ports(self, dbSession):
            
        aggregatedL2portObjects = self.__dao.getAll(dbSession, OverlayAggregatedL2port)
        aggregatedL2ports = []
        for aggregatedL2portObject in aggregatedL2portObjects:
            aggregatedL2ports.append(self._populateAggregatedL2port(aggregatedL2portObject))
        
        logger.debug("getAggregatedL2ports: count %d", len(aggregatedL2ports))
        
        outputDict = {}
        outputDict['aggregatedL2port'] = aggregatedL2ports
        outputDict['total'] = len(aggregatedL2ports)
        outputDict['uri'] = '%s/aggregatedL2ports' % (self._getUriPrefix())
        return {'aggregatedL2ports': outputDict}

    def getAggregatedL2port(self, dbSession, aggregatedL2portId):
            
        try:
            aggregatedL2portObject = self.__dao.getObjectById(dbSession, OverlayAggregatedL2port, aggregatedL2portId)
            logger.debug('getAggregatedL2port: %s', aggregatedL2portId)
        except (exc.NoResultFound) as ex:
            logger.debug("No Overlay AggregatedL2port found with Id: '%s', exc.NoResultFound: %s", aggregatedL2portId, ex.message)
            raise bottle.HTTPError(404, exception=OverlayAggregatedL2portNotFound(aggregatedL2portId))
        except Exception as ex:
            logger.debug('StackTrace: %s', traceback.format_exc())
            raise bottle.HTTPError(500, exception=PlatformError(ex.message))
        
        return {'aggregatedL2port': self._populateAggregatedL2port(aggregatedL2portObject)}

    def _getAggregatedL2portMembers(self, dbSession, dictMembers):
        members = []
        for dictMember in dictMembers:
            id = self.getIdFromUri(dictMember['device'])
            try:
                members.append({'device': self.__dao.getObjectById(dbSession, OverlayDevice, id), 'interface': dictMember['interface']})
            except (exc.NoResultFound) as ex:
                logger.debug("No Overlay Device found with Id: '%s', exc.NoResultFound: %s", id, ex.message)
                raise OverlayDeviceNotFound(deviceId)
        return members
                
    def createAggregatedL2port(self, dbSession):  
            
        if bottle.request.json is None:
            raise bottle.HTTPError(400, exception=InvalidRequest("No json in request object"))
        else:
            aggregatedL2portDict = bottle.request.json.get('aggregatedL2port')
            if aggregatedL2portDict is None:
                raise bottle.HTTPError(400, exception=InvalidRequest("POST body cannot be empty"))

        try:
            name = aggregatedL2portDict['name']
            description = aggregatedL2portDict.get('description')
            esi = aggregatedL2portDict.get('esi')
            lacp = aggregatedL2portDict.get('lacp')
            networkObjects = self.getNetworkObjects(dbSession, aggregatedL2portDict['networks'])      
            members = self._getAggregatedL2portMembers(dbSession, aggregatedL2portDict['members'])
            
            aggregatedL2portObject = self._overlay.createAggregatedL2port(dbSession, name, description, networkObjects, members, esi, lacp)
            logger.info("OverlayAggregatedL2port[id='%s', name='%s']: created", aggregatedL2portObject.id, aggregatedL2portObject.name)

            aggregatedL2port = {'aggregatedL2port': self._populateAggregatedL2port(aggregatedL2portObject)}
            
        except KeyError as ex:
            logger.debug('Bad request: %s', ex.message)
            raise bottle.HTTPError(400, exception=InvalidRequest(ex.message))
        except OverlayDeviceNotFound as ex:
            logger.debug('Bad request: %s', ex.message)
            raise bottle.HTTPError(400, exception=InvalidRequest(ex.message))
        except Exception as ex:
            logger.debug('StackTrace: %s', traceback.format_exc())
            raise bottle.HTTPError(500, exception=PlatformError(ex.message))
        bottle.response.set_header('Location', self.baseUrl + '/aggregatedL2ports/' + aggregatedL2portObject.id)
        bottle.response.status = 201

        return aggregatedL2port
        
    def modifyAggregatedL2port(self, dbSession, aggregatedL2portId):
            
        if bottle.request.json is None:
            raise bottle.HTTPError(400, exception=InvalidRequest("No json in request object"))
        else:
            aggregatedL2portDict = bottle.request.json.get('aggregatedL2port')
            if aggregatedL2portDict is None:
                raise bottle.HTTPError(400, exception=InvalidRequest("POST body cannot be empty"))

        try:
            name = aggregatedL2portDict['name']
            description = aggregatedL2portDict.get('description')
            esi = aggregatedL2portDict.get('esi')
            lacp = aggregatedL2portDict.get('lacp')
            aggregatedL2portObject = self.__dao.getObjectById(dbSession, OverlayAggregatedL2port, aggregatedL2portId)
            networkObjects = self.getNetworkObjects(dbSession, aggregatedL2portDict['networks'])      
            members = self._getAggregatedL2portMembers(dbSession, aggregatedL2portDict['members'])

            aggregatedL2portObject.clearNetworks()
            aggregatedL2portObject.clearMembers()
            self._overlay.modifyAggregatedL2port(dbSession, aggregatedL2portObject, name, description, networkObjects, members, esi, lacp)

            self.__dao.updateObjects(dbSession, [aggregatedL2portObject])
            logger.info("OverlayAggregatedL2port[id='%s', name='%s']: modified", aggregatedL2portObject.id, aggregatedL2portObject.name)
            
            aggregatedL2port = {'aggregatedL2port': self._populateAggregatedL2port(aggregatedL2portObject)}
            
        except (exc.NoResultFound) as ex:
            logger.debug("No Overlay AggregatedL2port found with Id: '%s', exc.NoResultFound: %s", aggregatedL2portId, ex.message)
            raise bottle.HTTPError(404, exception=OverlayAggregatedL2portNotFound(aggregatedL2portId))
        except KeyError as ex:
            logger.debug('Bad request: %s', ex.message)
            raise bottle.HTTPError(400, exception=InvalidRequest(ex.message))
        except OverlayDeviceNotFound as ex:
            logger.debug('Bad request: %s', ex.message)
            raise bottle.HTTPError(400, exception=InvalidRequest(ex.message))
        except Exception as ex:
            logger.debug('StackTrace: %s', traceback.format_exc())
            raise bottle.HTTPError(500, exception=PlatformError(ex.message))

        return aggregatedL2port
        
    def deleteAggregatedL2port(self, dbSession, aggregatedL2portId):
            
        try:
            aggregatedL2portObject = self.__dao.getObjectById(dbSession, OverlayAggregatedL2port, aggregatedL2portId)
            self._overlay.deleteAggregatedL2port(dbSession, aggregatedL2portObject)
            logger.info("OverlayAggregatedL2port[id='%s', name='%s']: delete request is submitted", OverlayAggregatedL2port.id, OverlayAggregatedL2port.name)
        except (exc.NoResultFound) as ex:
            logger.debug("No Overlay AggregatedL2port found with Id: '%s', exc.NoResultFound: %s", aggregatedL2portId, ex.message)
            raise bottle.HTTPError(404, exception=OverlayAggregatedL2portNotFound(aggregatedL2portId))
        except Exception as ex:
            logger.debug('StackTrace: %s', traceback.format_exc())
            raise bottle.HTTPError(500, exception=PlatformError(ex.message))

        return bottle.HTTPResponse(status=204)
