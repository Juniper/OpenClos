'''
Created on Sep 2, 2014

@author: moloyc
'''

import os
import bottle
from sqlalchemy.orm import exc
import StringIO
import zipfile
import traceback
import json
import util
import logging

from bottle import error, request, response, PluginError, ServerAdapter
from exception import InvalidRequest, PodNotFound, CablingPlanNotFound, DeviceConfigurationNotFound, DeviceNotFound, ImageNotFound, CreatePodFailed, UpdatePodFailed
from model import Pod, Device
from dao import Dao
from report import ResourceAllocationReport, L2Report, L3Report
from l3Clos import L3ClosMediation
from ztp import ZtpServer
from loader import OpenClosProperty, DeviceSku, loadLoggingConfig

#moduleName = 'overlayRestRoutes'
#loadLoggingConfig(appName=moduleName)
#logger = logging.getLogger(moduleName)
logger = None

def install(context):
    global logger
    logger = context['logger']
    OverlayRestRoutes().install(context)

class OverlayRestRoutes():
    def install(self, context):
        self.baseUrl = context['baseUrl'] + '/overlay'
        self._conf = context['conf']
        self.__dao = context['dao']
        self.__daoClass = context['daoClass']
        self.app = context['app']
        
        # install index links
        context['restServer'].addIndexLink(self.baseUrl + '/fabrics')
        context['restServer'].addIndexLink(self.baseUrl + '/tenants')
        context['restServer'].addIndexLink(self.baseUrl + '/vrfs')
        context['restServer'].addIndexLink(self.baseUrl + '/networks')
        context['restServer'].addIndexLink(self.baseUrl + '/subnets')
        context['restServer'].addIndexLink(self.baseUrl + '/l3ports')
        context['restServer'].addIndexLink(self.baseUrl + '/l2ports')
        context['restServer'].addIndexLink(self.baseUrl + '/aes')
        context['restServer'].addIndexLink(self.baseUrl + '/status')
        
        # GET APIs
        self.app.route(self.baseUrl + '/fabrics', 'GET', self.getFabrics)
        self.app.route(self.baseUrl + '/fabrics/<fabricId>', 'GET', self.getFabric)
        self.app.route(self.baseUrl + '/tenants', 'GET', self.getTenants)
        self.app.route(self.baseUrl + '/tenants/<tenantId>', 'GET', self.getTenant)
        self.app.route(self.baseUrl + '/vrfs', 'GET', self.getVrfs)
        self.app.route(self.baseUrl + '/vrfs/<vrfId>', 'GET', self.getVrf)
        self.app.route(self.baseUrl + '/networks', 'GET', self.getNetworks)
        self.app.route(self.baseUrl + '/networks/<networkId>', 'GET', self.getNetwork)
        self.app.route(self.baseUrl + '/subnets', 'GET', self.getSubnets)
        self.app.route(self.baseUrl + '/subnets/<subnetId>', 'GET', self.getSubnet)
        self.app.route(self.baseUrl + '/l3ports', 'GET', self.getL3ports)
        self.app.route(self.baseUrl + '/l3ports/<l3portId>', 'GET', self.getL3port)
        self.app.route(self.baseUrl + '/l2ports', 'GET', self.getL2ports)
        self.app.route(self.baseUrl + '/l2ports/<l2portId>', 'GET', self.getL2port)
        self.app.route(self.baseUrl + '/aes', 'GET', self.getAes)
        self.app.route(self.baseUrl + '/aes/<aeId>', 'GET', self.getAe)
        self.app.route(self.baseUrl + '/status', 'GET', self.getStatus)

        # POST/PUT APIs
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
        self.app.route(self.baseUrl + '/aes', 'POST', self.createAe)
        self.app.route(self.baseUrl + '/aes/<aeId>', 'PUT', self.modifyAe)

        # DELETE APIs
        self.app.route(self.baseUrl + '/fabrics/<fabricId>', 'DELETE', self.deleteFabric)
        self.app.route(self.baseUrl + '/tenants/<tenantId>', 'DELETE', self.deleteTenant)
        self.app.route(self.baseUrl + '/vrfs/<vrfId>', 'DELETE', self.deleteVrf)
        self.app.route(self.baseUrl + '/networks/<networkId>', 'DELETE', self.deleteNetwork)
        self.app.route(self.baseUrl + '/subnets/<subnetId>', 'DELETE', self.deleteSubnet)
        self.app.route(self.baseUrl + '/l3ports/<l3portId>', 'DELETE', self.deleteL3port)
        self.app.route(self.baseUrl + '/l2ports/<l2portId>', 'DELETE', self.deleteL2port)
        self.app.route(self.baseUrl + '/aes/<aeId>', 'DELETE', self.deleteAe)

    def getFabrics(self, dbSession):
        logger.info('getFabrics')
        return {'fabrics': {'fabric': [], 'total': 0, 'url': ''}}

    def getFabric(self, dbSession, fabricId, requestUrl=None):
        logger.info('getFabric %s', fabricId)
        return {'fabric': {}}
        
    def createFabric(self, dbSession):  
        logger.info('createFabric')
        bottle.response.status = 201
        return {'fabric': {}}
        
    def modifyFabric(self, dbSession, fabricId):
        logger.info('modifyFabric %s', fabricId)
        return {'fabric': {}}

    def deleteFabric(self, dbSession, fabricId):
        logger.info('deleteFabric %s', fabricId)
        return bottle.HTTPResponse(status=204)

    def getTenants(self, dbSession):
        logger.info('getTenants')
        return {'tenants': {'tenant': [], 'total': 0, 'url': ''}}

    def getTenant(self, dbSession, tenantId, requestUrl=None):
        logger.info('getTenant %s', tenantId)
        return {'tenant': {}}
        
    def createTenant(self, dbSession):  
        logger.info('createTenant')
        bottle.response.status = 201
        return {'tenant': {}}
        
    def modifyTenant(self, dbSession, tenantId):
        logger.info('modifyTenant %s', tenantId)
        return {'tenant': {}}

    def deleteTenant(self, dbSession, tenantId):
        logger.info('deleteTenant %s', tenantId)
        return bottle.HTTPResponse(status=204)

    def getVrfs(self, dbSession):
        logger.info('getVrfs')
        return {'vrfs': {'vrf': [], 'total': 0, 'url': ''}}

    def getVrf(self, dbSession, vrfId, requestUrl=None):
        logger.info('getVrf %s', vrfId)
        return {'vrf': {}}
        
    def createVrf(self, dbSession):  
        logger.info('createVrf')
        bottle.response.status = 201
        return {'vrf': {}}
        
    def modifyVrf(self, dbSession, vrfId):
        logger.info('modifyVrf %s', vrfId)
        return {'vrf': {}}

    def deleteVrf(self, dbSession, vrfId):
        logger.info('deleteVrf %s', vrfId)
        return bottle.HTTPResponse(status=204)
        
    def getNetworks(self, dbSession):
        logger.info('getNetworks')
        return {'networks': {'network': [], 'total': 0, 'url': ''}}

    def getNetwork(self, dbSession, networkId, requestUrl=None):
        logger.info('getNetwork %s', networkId)
        return {'network': {}}
        
    def createNetwork(self, dbSession):  
        logger.info('createNetwork')
        bottle.response.status = 201
        return {'network': {}}
        
    def modifyNetwork(self, dbSession, networkId):
        logger.info('modifyNetwork %s', networkId)
        return {'network': {}}

    def deleteNetwork(self, dbSession, networkId):
        logger.info('deleteNetwork %s', networkId)
        return bottle.HTTPResponse(status=204)

    def getSubnets(self, dbSession):
        logger.info('getSubnets')
        return {'subnets': {'subnet': [], 'total': 0, 'url': ''}}

    def getSubnet(self, dbSession, subnetId, requestUrl=None):
        logger.info('getSubnet %s', subnetId)
        return {'subnet': {}}
        
    def createSubnet(self, dbSession):  
        logger.info('createSubnet')
        bottle.response.status = 201
        return {'subnet': {}}
        
    def modifySubnet(self, dbSession, subnetId):
        logger.info('modifySubnet %s', subnetId)
        return {'subnet': {}}

    def deleteSubnet(self, dbSession, subnetId):
        logger.info('deleteSubnet %s', subnetId)
        return bottle.HTTPResponse(status=204)

    def getL3ports(self, dbSession):
        logger.info('getL3ports')
        return {'l3ports': {'l3port': [], 'total': 0, 'url': ''}}

    def getL3port(self, dbSession, l3portId, requestUrl=None):
        logger.info('getL3port %s', l3portId)
        return {'l3port': {}}
        
    def createL3port(self, dbSession):  
        logger.info('createL3port')
        bottle.response.status = 201
        return {'l3port': {}}
        
    def modifyL3port(self, dbSession, l3portId):
        logger.info('modifyL3port %s', l3portId)
        return {'l3port': {}}

    def deleteL3port(self, dbSession, l3portId):
        logger.info('deleteL3port %s', l3portId)
        return bottle.HTTPResponse(status=204)

    def getL2ports(self, dbSession):
        logger.info('getL2ports')
        return {'l2ports': {'l2port': [], 'total': 0, 'url': ''}}

    def getL2port(self, dbSession, l2portId, requestUrl=None):
        logger.info('getL2port %s', l2portId)
        return {'l2port': {}}
        
    def createL2port(self, dbSession):  
        logger.info('createL2port')
        bottle.response.status = 201
        return {'l2port': {}}
        
    def modifyL2port(self, dbSession, l2portId):
        logger.info('modifyL2port %s', l2portId)
        return {'l2port': {}}

    def deleteL2port(self, dbSession, l2portId):
        logger.info('deleteL2port %s', l2portId)
        return bottle.HTTPResponse(status=204)
        
    def getAes(self, dbSession):
        logger.info('getAes')
        return {'aes': {'ae': [], 'total': 0, 'url': ''}}

    def getAe(self, dbSession, aeId, requestUrl=None):
        logger.info('getAe %s', aeId)
        return {'ae': {}}
        
    def createAe(self, dbSession):  
        logger.info('createAe')
        bottle.response.status = 201
        return {'ae': {}}
        
    def modifyAe(self, dbSession, aeId):
        logger.info('modifyAe %s', aeId)
        return {'ae': {}}

    def deleteAe(self, dbSession, aeId):
        logger.info('deleteAe %s', aeId)
        return bottle.HTTPResponse(status=204)

    def getStatus(self, dbSession, requestUrl=None):
        logger.info('getStatus %s', bottle.request.query.fabricId)
        return {'statusAll': {'statusDevice': [], 'total': 0, 'url': ''}}
        
