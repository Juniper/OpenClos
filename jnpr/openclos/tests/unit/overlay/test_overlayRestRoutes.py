'''
Created on Nov 23, 2015

@author: yunli
'''
import os
import sys
sys.path.insert(0,os.path.abspath(os.path.dirname(__file__) + '/' + '../../..')) #trick to make it run from CLI

import unittest
import shutil
import json
from webtest import TestApp, AppError

from jnpr.openclos.rest import RestServer
from jnpr.openclos.dao import Dao
from jnpr.openclos.loader import loadLoggingConfig
from jnpr.openclos.tests.unit.overlay.test_overlay import TestOverlayHelper

webServerRoot = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'out')
configLocation = webServerRoot

class InMemoryDao(Dao):
    def _getDbUrl(self):
        loadLoggingConfig(appName = 'unittest')
        return 'sqlite:///'

registry = set([
    'GET /openclos/v1/overlay/fabrics',
    'GET /openclos/v1/overlay/fabrics/<fabricId>',
    'GET /openclos/v1/overlay/tenants',
    'GET /openclos/v1/overlay/tenants/<tenantId>',
    'GET /openclos/v1/overlay/vrfs',
    'GET /openclos/v1/overlay/vrfs/<vrfId>',
    'GET /openclos/v1/overlay/vrfs/<vrfId>/status',
    'GET /openclos/v1/overlay/devices',
    'GET /openclos/v1/overlay/devices/<deviceId>',
    'GET /openclos/v1/overlay/networks',
    'GET /openclos/v1/overlay/networks/<networkId>',
    'GET /openclos/v1/overlay/subnets',
    'GET /openclos/v1/overlay/subnets/<subnetId>',
    'GET /openclos/v1/overlay/l3ports',
    'GET /openclos/v1/overlay/l3ports/<l3portId>',
    'GET /openclos/v1/overlay/l2ports',
    'GET /openclos/v1/overlay/l2ports/<l2portId>',
    'GET /openclos/v1/overlay/aes',
    'GET /openclos/v1/overlay/aes/<aeId>',
    'POST /openclos/v1/overlay/fabrics',
    'POST /openclos/v1/overlay/tenants',
    'POST /openclos/v1/overlay/vrfs',
    'POST /openclos/v1/overlay/devices',
    'POST /openclos/v1/overlay/networks',
    'POST /openclos/v1/overlay/subnets',
    'POST /openclos/v1/overlay/l3ports',
    'POST /openclos/v1/overlay/l2ports',
    'POST /openclos/v1/overlay/aes',
    'PUT /openclos/v1/overlay/fabrics/<fabricId>',
    'PUT /openclos/v1/overlay/tenants/<tenantId>',
    'PUT /openclos/v1/overlay/vrfs/<vrfId>',
    'PUT /openclos/v1/overlay/devices/<deviceId>',
    'PUT /openclos/v1/overlay/networks/<networkId>',
    'PUT /openclos/v1/overlay/subnets/<subnetId>',
    'PUT /openclos/v1/overlay/l3ports/<l3portId>',
    'PUT /openclos/v1/overlay/l2ports/<l2portId>',
    'PUT /openclos/v1/overlay/aes/<aeId>',
    'DELETE /openclos/v1/overlay/fabrics/<fabricId>',
    'DELETE /openclos/v1/overlay/tenants/<tenantId>',
    'DELETE /openclos/v1/overlay/vrfs/<vrfId>',
    'DELETE /openclos/v1/overlay/devices/<deviceId>',
    'DELETE /openclos/v1/overlay/networks/<networkId>',
    'DELETE /openclos/v1/overlay/subnets/<subnetId>',
    'DELETE /openclos/v1/overlay/l3ports/<l3portId>',
    'DELETE /openclos/v1/overlay/l2ports/<l2portId>',
    'DELETE /openclos/v1/overlay/aes/<aeId>',
])    
    
class TestOverlayRestRoutes(unittest.TestCase):

    def setUp(self):
        if not os.path.exists(configLocation):
            os.makedirs(configLocation)
        self._dao = InMemoryDao.getInstance()
        self._conf = {}
        self._conf['restServer'] = {'version': 1, 'protocol': 'http', 'ipAddr': '0.0.0.0', 'port': 20080}
        self._conf['plugin'] = [{'name': 'overlay', 'package': 'jnpr.openclos.overlay'}]
        self.restServer = RestServer(self._conf, InMemoryDao)
        self.restServer.initRest()
        self.restServer.installRoutes()
        self.restServerTestApp = TestApp(self.restServer.app)
        self.helper = TestOverlayHelper(self._conf, self._dao)
        
    def tearDown(self):
        shutil.rmtree(os.path.join(configLocation, 'test1'), ignore_errors=True)
        self.restServer.stop()
        InMemoryDao._destroy()
        self.helper = None

    def testInstall(self):
        routes = set()
        for route in self.restServer.app.routes:
            if route.rule.startswith('/openclos/v1/overlay/'):
                routes.add('%s %s' % (route.method, route.rule))
        self.assertEqual(routes, registry)

    def testGetDevices(self):
        with self._dao.getReadWriteSession() as session:
            deviceObject = self.helper._createDevice(session)
            deviceId = deviceObject.id
                    
        response = self.restServerTestApp.get('/openclos/v1/overlay/devices')
        self.assertEqual(200, response.status_int) 
        self.assertEqual(1, len(response.json['devices']['device']))
        self.assertTrue("/openclos/v1/overlay/devices/" + deviceId in response.json['devices']['device'][0]['uri'])
        
    def testGetDevice(self):
        with self._dao.getReadWriteSession() as session:
            deviceObject = self.helper._createDevice(session)
            deviceId = deviceObject.id
            deviceName = deviceObject.name
                    
        response = self.restServerTestApp.get('/openclos/v1/overlay/devices/' + deviceId)
        self.assertEqual(200, response.status_int) 
        self.assertEqual(deviceName, response.json['device']['name'])
        self.assertTrue("/openclos/v1/overlay/devices/" + deviceId in response.json['device']['uri'])
        
    def testGetDeviceNotFound(self):
        with self.assertRaises(AppError) as e:
            self.restServerTestApp.get('/openclos/v1/overlay/devices/12345')
        self.assertTrue('404 Not Found' in e.exception.message)
        self.assertTrue('1108' in e.exception.message)
        
    def testCreateDevice(self):
        deviceDict = {
            "device": {
                "name": "d1",
                "description": "description for d1",
                "role": "spine",
                "address": "1.2.3.4",
                "routerId": "1.1.1.1",
                "podName": "pod1"
            }
        }
        response = self.restServerTestApp.post('/openclos/v1/overlay/devices', 
                                               headers = {'Content-Type':'application/json'}, 
                                               params=json.dumps(deviceDict))
        self.assertEqual(201, response.status_int)
        response = self.restServerTestApp.get('/openclos/v1/overlay/devices/' + response.json['device']['id'])
        self.assertEqual(200, response.status_int) 

    def testModifyDevice(self):
        with self._dao.getReadWriteSession() as session:
            deviceObject = self.helper._createDevice(session)
            deviceId = deviceObject.id
        deviceDict = {
            "device": {
                "name": "d1",
                "description": "changed",
                "role": "spine",
                "address": "1.2.3.5",
                "routerId": "1.1.1.2",
                "podName": "pod2"
            }
        }
        response = self.restServerTestApp.put('/openclos/v1/overlay/devices/' + deviceId, 
                                               headers = {'Content-Type':'application/json'}, 
                                               params=json.dumps(deviceDict))
        self.assertEqual(200, response.status_int)
        self.assertEqual('changed', response.json['device']['description'])
        self.assertEqual('1.2.3.5', response.json['device']['address'])
        self.assertEqual('1.1.1.2', response.json['device']['routerId'])
        self.assertEqual('pod2', response.json['device']['podName'])
        
    def testModifyDeviceNotFound(self):
        deviceDict = {
            "device": {
                "id": '12345',
                "name": "d1",
                "description": "changed",
                "role": "spine",
                "address": "1.2.3.5",
                "routerId": "1.1.1.2",
                "podName": "pod1"
            }
        }
        with self.assertRaises(AppError) as e:
            self.restServerTestApp.put('/openclos/v1/overlay/devices/12345',
                                       headers = {'Content-Type':'application/json'}, 
                                       params=json.dumps(deviceDict))
        self.assertTrue('404 Not Found' in e.exception.message)
        self.assertTrue('1108' in e.exception.message)
        
    def testDeleteDevice(self):
        with self._dao.getReadWriteSession() as session:
            deviceObject = self.helper._createDevice(session)
            deviceId = deviceObject.id

        response = self.restServerTestApp.delete('/openclos/v1/overlay/devices/' + deviceId)
        self.assertEqual(204, response.status_int) 
        
    def testDeleteDeviceNotFound(self):
        with self.assertRaises(AppError) as e:
            self.restServerTestApp.delete('/openclos/v1/overlay/devices/12345')
        self.assertTrue('404 Not Found' in e.exception.message)
        self.assertTrue('1108' in e.exception.message)
        
    def testGetFabrics(self):
        with self._dao.getReadWriteSession() as session:   
            fabricObject = self.helper._createFabric(session)
            fabricId = fabricObject.id
                    
        response = self.restServerTestApp.get('/openclos/v1/overlay/fabrics')
        self.assertEqual(200, response.status_int) 
        self.assertEqual(1, len(response.json['fabrics']['fabric']))
        self.assertTrue("/openclos/v1/overlay/fabrics/" + fabricId in response.json['fabrics']['fabric'][0]['uri'])
        
    def testGetFabric(self):
        with self._dao.getReadWriteSession() as session:   
            fabricObject = self.helper._createFabric(session)
            fabricId = fabricObject.id
            fabricName = fabricObject.name
            fabricAS = fabricObject.overlayAS
                    
        response = self.restServerTestApp.get('/openclos/v1/overlay/fabrics/' + fabricId)
        self.assertEqual(200, response.status_int) 
        self.assertEqual(fabricName, response.json['fabric']['name'])
        self.assertEqual(fabricAS, response.json['fabric']['overlayAsn'])
        self.assertTrue("/openclos/v1/overlay/fabrics/" + fabricId in response.json['fabric']['uri'])
        
    def testGetFabricNotFound(self):
        with self.assertRaises(AppError) as e:
            self.restServerTestApp.get('/openclos/v1/overlay/fabrics/12345')
        self.assertTrue('404 Not Found' in e.exception.message)
        self.assertTrue('1105' in e.exception.message)
        
    def testCreateFabric(self):
        with self._dao.getReadWriteSession() as session:
            deviceObject = self.helper._createDevice(session)
            deviceId = deviceObject.id
        fabricDict = {
            "fabric": {
                "name": "f1",
                "description": "description for f1",
                "overlayAsn": 65001,
                "routeReflectorAddress": "2.2.2.2"
            }
        }
        fabricDict['fabric']['devices'] = [deviceId]
        response = self.restServerTestApp.post('/openclos/v1/overlay/fabrics', 
                                               headers = {'Content-Type':'application/json'}, 
                                               params=json.dumps(fabricDict))
        self.assertEqual(201, response.status_int)
        response = self.restServerTestApp.get('/openclos/v1/overlay/fabrics/' + response.json['fabric']['id'])
        self.assertEqual(200, response.status_int) 

    def testModifyFabric(self):
        with self._dao.getReadWriteSession() as session:   
            fabricObject = self.helper._createFabric(session)
            fabricId = fabricObject.id
            deviceId = fabricObject.overlay_devices[0].id

        fabricDict = {
            "fabric": {
                "name": "f1",
                "description": "description for f1",
                "overlayAsn": 65002,
                "routeReflectorAddress": "3.3.3.3"
            }
        }
        fabricDict['fabric']['devices'] = [deviceId]
        fabricDict['fabric']['id'] = fabricId
        response = self.restServerTestApp.put('/openclos/v1/overlay/fabrics/' + fabricId, 
                                               headers = {'Content-Type':'application/json'}, 
                                               params=json.dumps(fabricDict))
        self.assertEqual(200, response.status_int)
        self.assertEqual(65002, response.json['fabric']['overlayAsn'])
        self.assertEqual('3.3.3.3', response.json['fabric']['routeReflectorAddress'])
        
    def testModifyFabricNotFound(self):
        with self._dao.getReadWriteSession() as session:
            deviceObject = self.helper._createDevice(session)
            deviceId = deviceObject.id
        fabricDict = {
            "fabric": {
                "id": '12345',
                "name": "f1",
                "description": "description for f1",
                "overlayAsn": 65001,
                "routeReflectorAddress": "3.3.3.3"
            }
        }
        fabricDict['fabric']['devices'] = [deviceId]
        with self.assertRaises(AppError) as e:
            self.restServerTestApp.put('/openclos/v1/overlay/fabrics/12345',
                                       headers = {'Content-Type':'application/json'}, 
                                       params=json.dumps(fabricDict))
        self.assertTrue('404 Not Found' in e.exception.message)
        self.assertTrue('1105' in e.exception.message)
        
    def testDeleteFabric(self):
        with self._dao.getReadWriteSession() as session:   
            fabricObject = self.helper._createFabric(session)
            fabricId = fabricObject.id

        response = self.restServerTestApp.delete('/openclos/v1/overlay/fabrics/' + fabricId)
        self.assertEqual(204, response.status_int) 
        
    def testDeleteFabricNotFound(self):
        with self.assertRaises(AppError) as e:
            self.restServerTestApp.delete('/openclos/v1/overlay/fabrics/12345')
        self.assertTrue('404 Not Found' in e.exception.message)
        self.assertTrue('1105' in e.exception.message)
        
    def testGetTenants(self):
        with self._dao.getReadWriteSession() as session:   
            tenantObject = self.helper._createTenant(session)
            tenantId = tenantObject.id
                    
        response = self.restServerTestApp.get('/openclos/v1/overlay/tenants')
        self.assertEqual(200, response.status_int) 
        self.assertEqual(1, len(response.json['tenants']['tenant']))
        self.assertTrue("/openclos/v1/overlay/tenants/" + tenantId in response.json['tenants']['tenant'][0]['uri'])
        
    def testGetTenant(self):
        with self._dao.getReadWriteSession() as session:   
            tenantObject = self.helper._createTenant(session)
            tenantId = tenantObject.id
            tenantName = tenantObject.name
                    
        response = self.restServerTestApp.get('/openclos/v1/overlay/tenants/' + tenantId)
        self.assertEqual(200, response.status_int) 
        self.assertEqual(tenantName, response.json['tenant']['name'])
        self.assertTrue("/openclos/v1/overlay/tenants/" + tenantId in response.json['tenant']['uri'])
        
    def testGetTenantNotFound(self):
        with self.assertRaises(AppError) as e:
            self.restServerTestApp.get('/openclos/v1/overlay/tenants/12345')
        self.assertTrue('404 Not Found' in e.exception.message)
        self.assertTrue('1106' in e.exception.message)
        
    def testCreateTenant(self):
        with self._dao.getReadWriteSession() as session:   
            fabricObject = self.helper._createFabric(session)
            fabricId = fabricObject.id
        tenantDict = {
            "tenant": {
                "name": "t1",
                "description": "description for t1"
            }
        }
        tenantDict['tenant']['fabric'] = fabricId
        response = self.restServerTestApp.post('/openclos/v1/overlay/tenants', 
                                               headers = {'Content-Type':'application/json'}, 
                                               params=json.dumps(tenantDict))
        self.assertEqual(201, response.status_int)
        response = self.restServerTestApp.get('/openclos/v1/overlay/tenants/' + response.json['tenant']['id'])
        self.assertEqual(200, response.status_int) 

    def testModifyTenant(self):
        with self._dao.getReadWriteSession() as session:   
            tenantObject = self.helper._createTenant(session)
            tenantId = tenantObject.id
            fabricId = tenantObject.overlay_fabric_id
        tenantDict = {
            "tenant": {
                "name": "t1",
                "description": "changed",
            }
        }
        tenantDict['tenant']['id'] = tenantId
        tenantDict['tenant']['fabric'] = fabricId
        response = self.restServerTestApp.put('/openclos/v1/overlay/tenants/' + tenantId, 
                                               headers = {'Content-Type':'application/json'}, 
                                               params=json.dumps(tenantDict))
        self.assertEqual(200, response.status_int)
        self.assertEqual('changed', response.json['tenant']['description'])
        
    def testModifyTenantNotFound(self):
        tenantDict = {
            "tenant": {
                "id": '12345',
                "name": "f1",
                "description": "description for f1",
                "fabric": '12345'
            }
        }
        with self.assertRaises(AppError) as e:
            self.restServerTestApp.put('/openclos/v1/overlay/tenants/12345',
                                       headers = {'Content-Type':'application/json'}, 
                                       params=json.dumps(tenantDict))
        self.assertTrue('404 Not Found' in e.exception.message)
        self.assertTrue('1106' in e.exception.message)
        
    def testDeleteTenant(self):
        with self._dao.getReadWriteSession() as session:   
            tenantObject = self.helper._createTenant(session)
            tenantId = tenantObject.id
                    
        response = self.restServerTestApp.delete('/openclos/v1/overlay/tenants/' + tenantId)
        self.assertEqual(204, response.status_int) 
        
    def testDeleteTenantNotFound(self):
        with self.assertRaises(AppError) as e:
            self.restServerTestApp.delete('/openclos/v1/overlay/tenants/12345')
        self.assertTrue('404 Not Found' in e.exception.message)
        self.assertTrue('1106' in e.exception.message)
        
    def testGetVrfs(self):
        with self._dao.getReadWriteSession() as session:        
            vrfObject = self.helper._createVrf(session)
            vrfId = vrfObject.id
                    
        response = self.restServerTestApp.get('/openclos/v1/overlay/vrfs')
        self.assertEqual(200, response.status_int) 
        self.assertEqual(1, len(response.json['vrfs']['vrf']))
        self.assertTrue("/openclos/v1/overlay/vrfs/" + vrfId in response.json['vrfs']['vrf'][0]['uri'])
        
    def testGetVrf(self):
        with self._dao.getReadWriteSession() as session:        
            vrfObject = self.helper._createVrf(session)
            vrfId = vrfObject.id
            vrfName = vrfObject.name
                    
        response = self.restServerTestApp.get('/openclos/v1/overlay/vrfs/' + vrfId)
        self.assertEqual(200, response.status_int) 
        self.assertEqual(vrfName, response.json['vrf']['name'])
        self.assertTrue("/openclos/v1/overlay/vrfs/" + vrfId in response.json['vrf']['uri'])
        
    def testGetVrfNotFound(self):
        with self.assertRaises(AppError) as e:
            self.restServerTestApp.get('/openclos/v1/overlay/vrfs/12345')
        self.assertTrue('404 Not Found' in e.exception.message)
        self.assertTrue('1107' in e.exception.message)
        
    def testCreateVrf(self):
        with self._dao.getReadWriteSession() as session:        
            tenantObject = self.helper._createTenant(session)
            tenantId = tenantObject.id

        vrfDict = {
            "vrf": {
                "name": "v1",
                "description": "description for v1",
                "routedVnid": 100,
                "loopbackAddress": "1.1.1.1"
            }
        }
        vrfDict['vrf']['tenant'] = tenantId
        print vrfDict['vrf']['tenant']
        response = self.restServerTestApp.post('/openclos/v1/overlay/vrfs', 
                                               headers = {'Content-Type':'application/json'}, 
                                               params=json.dumps(vrfDict))
        self.assertEqual(201, response.status_int)
        response = self.restServerTestApp.get('/openclos/v1/overlay/vrfs/' + response.json['vrf']['id'])
        self.assertEqual(200, response.status_int) 

    def testModifyVrf(self):
        with self._dao.getReadWriteSession() as session:        
            vrfObject = self.helper._createVrf(session)
            vrfId = vrfObject.id
            tenantId = vrfObject.overlay_tenant.id

        vrfDict = {
            "vrf": {
                "name": "v1",
                "description": "changed",
                "routedVnid": 101,
                "loopbackAddress": "1.1.1.2"
            }
        }
        vrfDict['vrf']['tenant'] = tenantId
        vrfDict['vrf']['id'] = vrfId
        response = self.restServerTestApp.put('/openclos/v1/overlay/vrfs/' + vrfId, 
                                               headers = {'Content-Type':'application/json'}, 
                                               params=json.dumps(vrfDict))
        self.assertEqual(200, response.status_int)
        self.assertEqual('changed', response.json['vrf']['description'])
        self.assertEqual(101, response.json['vrf']['routedVnid'])
        self.assertEqual('1.1.1.2', response.json['vrf']['loopbackAddress'])
        
    def testModifyVrfNotFound(self):
        vrfDict = {
            "vrf": {
                "id": '12345',
                "name": "v1",
                "description": "description for v1",
                "routedVnid": 101,
                "loopbackAddress": "1.1.1.2",
                "tenant": '12345'
            }
        }
        with self.assertRaises(AppError) as e:
            self.restServerTestApp.put('/openclos/v1/overlay/vrfs/12345',
                                       headers = {'Content-Type':'application/json'}, 
                                       params=json.dumps(vrfDict))
        self.assertTrue('404 Not Found' in e.exception.message)
        self.assertTrue('1107' in e.exception.message)
        
    def testDeleteVrf(self):
        with self._dao.getReadWriteSession() as session:        
            vrfObject = self.helper._createVrf(session)
            vrfId = vrfObject.id
                    
        response = self.restServerTestApp.delete('/openclos/v1/overlay/vrfs/' + vrfId)
        self.assertEqual(204, response.status_int) 
        
    def testDeleteVrfNotFound(self):
        with self.assertRaises(AppError) as e:
            self.restServerTestApp.delete('/openclos/v1/overlay/vrfs/12345')
        self.assertTrue('404 Not Found' in e.exception.message)
        self.assertTrue('1107' in e.exception.message)
        
    def testGetNetworks(self):
        with self._dao.getReadWriteSession() as session:        
            networkObject = self.helper._createNetwork(session)
            networkId = networkObject.id
                    
        response = self.restServerTestApp.get('/openclos/v1/overlay/networks')
        self.assertEqual(200, response.status_int) 
        self.assertEqual(1, len(response.json['networks']['network']))
        self.assertTrue("/openclos/v1/overlay/networks/" + networkId in response.json['networks']['network'][0]['uri'])
        
    def testGetNetwork(self):
        with self._dao.getReadWriteSession() as session:        
            networkObject = self.helper._createNetwork(session)
            networkId = networkObject.id
            networkName = networkObject.name
                    
        response = self.restServerTestApp.get('/openclos/v1/overlay/networks/' + networkId)
        self.assertEqual(200, response.status_int) 
        self.assertEqual(networkName, response.json['network']['name'])
        self.assertTrue("/openclos/v1/overlay/networks/" + networkId in response.json['network']['uri'])
        
    def testGetNetworkNotFound(self):
        with self.assertRaises(AppError) as e:
            self.restServerTestApp.get('/openclos/v1/overlay/networks/12345')
        self.assertTrue('404 Not Found' in e.exception.message)
        self.assertTrue('1109' in e.exception.message)
        
    def testCreateNetwork(self):
        with self._dao.getReadWriteSession() as session:        
            vrfObject = self.helper._createVrf(session)
            vrfId = vrfObject.id
        
        networkDict = {
            "network": {
                "name": "n1",
                "description": "description for n1",
                "vlanid": 1000,
                "vnid": 100,
                "pureL3Int": False
            }
        }
        networkDict['network']['vrf'] = vrfId
        response = self.restServerTestApp.post('/openclos/v1/overlay/networks', 
                                               headers = {'Content-Type':'application/json'}, 
                                               params=json.dumps(networkDict))
        self.assertEqual(201, response.status_int)
        response = self.restServerTestApp.get('/openclos/v1/overlay/networks/' + response.json['network']['id'])
        self.assertEqual(200, response.status_int) 

    def testModifyNetwork(self):
        with self._dao.getReadWriteSession() as session:        
            networkObject = self.helper._createNetwork(session)
            networkId = networkObject.id
            vrfId = networkObject.overlay_vrf.id

        networkDict = {
            "network": {
                "name": "n1",
                "description": "changed",
                "vlanid": 1001,
                "vnid": 101,
                "pureL3Int": True
            }
        }
        networkDict['network']['vrf'] = vrfId
        networkDict['network']['id'] = networkId
        response = self.restServerTestApp.put('/openclos/v1/overlay/networks/' + networkId, 
                                               headers = {'Content-Type':'application/json'}, 
                                               params=json.dumps(networkDict))
        self.assertEqual(200, response.status_int)
        self.assertEqual('changed', response.json['network']['description'])
        self.assertEqual(1001, response.json['network']['vlanid'])
        self.assertEqual(101, response.json['network']['vnid'])
        self.assertEqual(True, response.json['network']['pureL3Int'])
        
    def testModifyNetworkNotFound(self):
        networkDict = {
            "network": {
                "id": '12345',
                "name": "n1",
                "description": "description for n1",
                "vlanid": 1000,
                "vnid": 100,
                "pureL3Int": False
            }
        }
        with self.assertRaises(AppError) as e:
            self.restServerTestApp.put('/openclos/v1/overlay/networks/12345',
                                       headers = {'Content-Type':'application/json'}, 
                                       params=json.dumps(networkDict))
        self.assertTrue('404 Not Found' in e.exception.message)
        self.assertTrue('1109' in e.exception.message)
        
    def testDeleteNetwork(self):
        with self._dao.getReadWriteSession() as session:        
            networkObject = self.helper._createNetwork(session)
            networkId = networkObject.id
                    
        response = self.restServerTestApp.delete('/openclos/v1/overlay/networks/' + networkId)
        self.assertEqual(204, response.status_int) 
        
    def testDeleteNetworkNotFound(self):
        with self.assertRaises(AppError) as e:
            self.restServerTestApp.delete('/openclos/v1/overlay/networks/12345')
        self.assertTrue('404 Not Found' in e.exception.message)
        self.assertTrue('1109' in e.exception.message)
        
    def testGetSubnets(self):
        with self._dao.getReadWriteSession() as session:        
            subnetObject = self.helper._createSubnet(session)
            subnetId = subnetObject.id
                    
        response = self.restServerTestApp.get('/openclos/v1/overlay/subnets')
        self.assertEqual(200, response.status_int) 
        self.assertEqual(1, len(response.json['subnets']['subnet']))
        self.assertTrue("/openclos/v1/overlay/subnets/" + subnetId in response.json['subnets']['subnet'][0]['uri'])
        
    def testGetSubnet(self):
        with self._dao.getReadWriteSession() as session:        
            subnetObject = self.helper._createSubnet(session)
            subnetId = subnetObject.id
            subnetName = subnetObject.name
            
        response = self.restServerTestApp.get('/openclos/v1/overlay/subnets/' + subnetId)
        self.assertEqual(200, response.status_int) 
        self.assertEqual(subnetName, response.json['subnet']['name'])
        self.assertTrue("/openclos/v1/overlay/subnets/" + subnetId in response.json['subnet']['uri'])
        
    def testGetSubnetNotFound(self):
        with self.assertRaises(AppError) as e:
            self.restServerTestApp.get('/openclos/v1/overlay/subnets/12345')
        self.assertTrue('404 Not Found' in e.exception.message)
        self.assertTrue('1110' in e.exception.message)
        
    def testCreateSubnet(self):
        with self._dao.getReadWriteSession() as session:        
            networkObject = self.helper._createNetwork(session)
            networkId = networkObject.id

        subnetDict = {
            "subnet": {
                "name": "s1",
                "description": "description for s1",
                "cidr": "1.2.3.4/24"
            }
        }
        subnetDict['subnet']['network'] = networkId
        response = self.restServerTestApp.post('/openclos/v1/overlay/subnets', 
                                               headers = {'Content-Type':'application/json'}, 
                                               params=json.dumps(subnetDict))
        self.assertEqual(201, response.status_int)
        response = self.restServerTestApp.get('/openclos/v1/overlay/subnets/' + response.json['subnet']['id'])
        self.assertEqual(200, response.status_int) 

    def testModifySubnet(self):
        with self._dao.getReadWriteSession() as session:        
            subnetObject = self.helper._createSubnet(session)
            subnetId = subnetObject.id
            networkId = subnetObject.overlay_network.id

        subnetDict = {
            "subnet": {
                "name": "s1",
                "description": "changed",
                "cidr": "1.2.3.5/24"
            }
        }
        subnetDict['subnet']['network'] = networkId
        subnetDict['subnet']['id'] = subnetId
        response = self.restServerTestApp.put('/openclos/v1/overlay/subnets/' + subnetId, 
                                               headers = {'Content-Type':'application/json'}, 
                                               params=json.dumps(subnetDict))
        self.assertEqual(200, response.status_int)
        self.assertEqual('changed', response.json['subnet']['description'])
        self.assertEqual('1.2.3.5/24', response.json['subnet']['cidr'])
        
    def testModifySubnetNotFound(self):
        subnetDict = {
            "subnet": {
                "id": '12345',
                "name": "s1",
                "description": "description for s1",
                "cidr": "1.2.3.5/24"
            }
        }
        with self.assertRaises(AppError) as e:
            self.restServerTestApp.put('/openclos/v1/overlay/subnets/12345',
                                       headers = {'Content-Type':'application/json'}, 
                                       params=json.dumps(subnetDict))
        self.assertTrue('404 Not Found' in e.exception.message)
        self.assertTrue('1110' in e.exception.message)
        
    def testDeleteSubnet(self):
        with self._dao.getReadWriteSession() as session:        
            subnetObject = self.helper._createSubnet(session)
            subnetId = subnetObject.id
                    
        response = self.restServerTestApp.delete('/openclos/v1/overlay/subnets/' + subnetId)
        self.assertEqual(204, response.status_int) 
        
    def testDeleteSubnetNotFound(self):
        with self.assertRaises(AppError) as e:
            self.restServerTestApp.delete('/openclos/v1/overlay/subnets/12345')
        self.assertTrue('404 Not Found' in e.exception.message)
        self.assertTrue('1110' in e.exception.message)
        
    def testGetL3ports(self):
        with self._dao.getReadWriteSession() as session:        
            l3portObject = self.helper._createL3port(session)
            l3portId = l3portObject.id
                    
        response = self.restServerTestApp.get('/openclos/v1/overlay/l3ports')
        self.assertEqual(200, response.status_int) 
        self.assertEqual(1, len(response.json['l3ports']['l3port']))
        self.assertTrue("/openclos/v1/overlay/l3ports/" + l3portId in response.json['l3ports']['l3port'][0]['uri'])
        
    def testGetL3port(self):
        with self._dao.getReadWriteSession() as session:        
            l3portObject = self.helper._createL3port(session)
            l3portId = l3portObject.id
            l3portName = l3portObject.name
                    
        response = self.restServerTestApp.get('/openclos/v1/overlay/l3ports/' + l3portId)
        self.assertEqual(200, response.status_int) 
        self.assertEqual(l3portName, response.json['l3port']['name'])
        self.assertTrue("/openclos/v1/overlay/l3ports/" + l3portId in response.json['l3port']['uri'])
        
    def testGetL3portNotFound(self):
        with self.assertRaises(AppError) as e:
            self.restServerTestApp.get('/openclos/v1/overlay/l3ports/12345')
        self.assertTrue('404 Not Found' in e.exception.message)
        self.assertTrue('1111' in e.exception.message)
        
    def testCreateL3port(self):
        with self._dao.getReadWriteSession() as session:        
            subnetObject = self.helper._createSubnet(session)
            subnetId = subnetObject.id

        l3portDict = {
            "l3port": {
                "name": "l3port1",
                "description": "description for l3port1"
            }
        }
        l3portDict['l3port']['subnet'] = subnetId
        response = self.restServerTestApp.post('/openclos/v1/overlay/l3ports', 
                                               headers = {'Content-Type':'application/json'}, 
                                               params=json.dumps(l3portDict))
        self.assertEqual(201, response.status_int)
        response = self.restServerTestApp.get('/openclos/v1/overlay/l3ports/' + response.json['l3port']['id'])
        self.assertEqual(200, response.status_int) 

    def testModifyL3port(self):
        with self._dao.getReadWriteSession() as session:        
            l3portObject = self.helper._createL3port(session)
            l3portId = l3portObject.id
            subnetId = l3portObject.overlay_subnet.id

        l3portDict = {
            "l3port": {
                "name": "l3port1",
                "description": "changed"
            }
        }
        l3portDict['l3port']['subnet'] = subnetId
        l3portDict['l3port']['id'] = l3portId
        response = self.restServerTestApp.put('/openclos/v1/overlay/l3ports/' + l3portId, 
                                               headers = {'Content-Type':'application/json'}, 
                                               params=json.dumps(l3portDict))
        self.assertEqual(200, response.status_int)
        self.assertEqual('changed', response.json['l3port']['description'])
        
    def testModifyL3portNotFound(self):
        l3portDict = {
            "l3port": {
                "id": '12345',
                "name": "l3port1",
                "description": "description for l3port1"
            }
        }
        with self.assertRaises(AppError) as e:
            self.restServerTestApp.put('/openclos/v1/overlay/l3ports/12345',
                                       headers = {'Content-Type':'application/json'}, 
                                       params=json.dumps(l3portDict))
        self.assertTrue('404 Not Found' in e.exception.message)
        self.assertTrue('1111' in e.exception.message)
        
    def testDeleteL3port(self):
        with self._dao.getReadWriteSession() as session:        
            l3portObject = self.helper._createL3port(session)
            l3portId = l3portObject.id
                    
        response = self.restServerTestApp.delete('/openclos/v1/overlay/l3ports/' + l3portId)
        self.assertEqual(204, response.status_int) 
        
    def testDeleteL3portNotFound(self):
        with self.assertRaises(AppError) as e:
            self.restServerTestApp.delete('/openclos/v1/overlay/l3ports/12345')
        self.assertTrue('404 Not Found' in e.exception.message)
        self.assertTrue('1111' in e.exception.message)
        
    def testGetL2ports(self):
        with self._dao.getReadWriteSession() as session:        
            l2portObject = self.helper._createL2port(session)
            l2portId = l2portObject.id
                    
        response = self.restServerTestApp.get('/openclos/v1/overlay/l2ports')
        self.assertEqual(200, response.status_int) 
        self.assertEqual(1, len(response.json['l2ports']['l2port']))
        self.assertTrue("/openclos/v1/overlay/l2ports/" + l2portId in response.json['l2ports']['l2port'][0]['uri'])
        
    def testGetL2port(self):
        with self._dao.getReadWriteSession() as session:        
            l2portObject = self.helper._createL2port(session)
            l2portId = l2portObject.id
            l2portName = l2portObject.name
                    
        response = self.restServerTestApp.get('/openclos/v1/overlay/l2ports/' + l2portId)
        self.assertEqual(200, response.status_int) 
        self.assertEqual(l2portName, response.json['l2port']['name'])
        self.assertIsNotNone(response.json['l2port']['networks'][0])
        self.assertTrue("/openclos/v1/overlay/l2ports/" + l2portId in response.json['l2port']['uri'])
        
    def testGetL2portNotFound(self):
        with self.assertRaises(AppError) as e:
            self.restServerTestApp.get('/openclos/v1/overlay/l2ports/12345')
        self.assertTrue('404 Not Found' in e.exception.message)
        self.assertTrue('1112' in e.exception.message)
        
    def testCreateL2port(self):
        with self._dao.getReadWriteSession() as session:        
            networkObject = self.helper._createNetwork(session)
            networkId = networkObject.id
            deviceId = networkObject.overlay_vrf.overlay_tenant.overlay_fabric.overlay_devices[0].id
        l2portDict = {
            "l2port": {
                "name": "l2port1",
                "description": "description for l2port1",
                "interface": "xe-0/0/0"
            }
        }
        l2portDict['l2port']['networks'] = [networkId]
        l2portDict['l2port']['device'] = deviceId
        response = self.restServerTestApp.post('/openclos/v1/overlay/l2ports', 
                                               headers = {'Content-Type':'application/json'}, 
                                               params=json.dumps(l2portDict))
        self.assertEqual(201, response.status_int)
        response = self.restServerTestApp.get('/openclos/v1/overlay/l2ports/' + response.json['l2port']['id'])
        self.assertEqual(200, response.status_int) 

    def testModifyL2port(self):
        with self._dao.getReadWriteSession() as session:        
            l2portObject = self.helper._createL2port(session)
            l2portId = l2portObject.id
            networkId = l2portObject.overlay_networks[0].id
            deviceId = l2portObject.overlay_device.id

        l2portDict = {
            "l2port": {
                "name": "l2port1",
                "description": "changed",
                "interface": "xe-0/0/0"
            }
        }
        l2portDict['l2port']['networks'] = [networkId]
        l2portDict['l2port']['device'] = deviceId
        l2portDict['l2port']['id'] = l2portId
        response = self.restServerTestApp.put('/openclos/v1/overlay/l2ports/' + l2portId, 
                                               headers = {'Content-Type':'application/json'}, 
                                               params=json.dumps(l2portDict))
        self.assertEqual(200, response.status_int)
        self.assertEqual('changed', response.json['l2port']['description'])
        
    def testModifyL2portNotFound(self):
        l2portDict = {
            "l2port": {
                "id": '12345',
                "name": "l2port1",
                "description": "description for l2port1",
                "interface": "xe-0/0/0"
            }
        }
        with self.assertRaises(AppError) as e:
            self.restServerTestApp.put('/openclos/v1/overlay/l2ports/12345',
                                       headers = {'Content-Type':'application/json'}, 
                                       params=json.dumps(l2portDict))
        self.assertTrue('404 Not Found' in e.exception.message)
        self.assertTrue('1112' in e.exception.message)
        
    def testDeleteL2port(self):
        with self._dao.getReadWriteSession() as session:        
            l2portObject = self.helper._createL2port(session)
            l2portId = l2portObject.id
                    
        response = self.restServerTestApp.delete('/openclos/v1/overlay/l2ports/' + l2portId)
        self.assertEqual(204, response.status_int) 
        
    def testDeleteL2portNotFound(self):
        with self.assertRaises(AppError) as e:
            self.restServerTestApp.delete('/openclos/v1/overlay/l2ports/12345')
        self.assertTrue('404 Not Found' in e.exception.message)
        self.assertTrue('1112' in e.exception.message)
        
    def testGetAes(self):
        with self._dao.getReadWriteSession() as session:        
            aeObject = self.helper._createAe(session)
            aeId = aeObject.id
                    
        response = self.restServerTestApp.get('/openclos/v1/overlay/aes')
        self.assertEqual(200, response.status_int) 
        self.assertEqual(1, len(response.json['aes']['ae']))
        self.assertTrue("/openclos/v1/overlay/aes/" + aeId in response.json['aes']['ae'][0]['uri'])
        
    def testGetAe(self):
        with self._dao.getReadWriteSession() as session:        
            aeObject = self.helper._createAe(session)
            aeId = aeObject.id
            aeName = aeObject.name
                    
        response = self.restServerTestApp.get('/openclos/v1/overlay/aes/' + aeId)
        self.assertEqual(200, response.status_int) 
        self.assertEqual(aeName, response.json['ae']['name'])
        self.assertTrue("/openclos/v1/overlay/aes/" + aeId in response.json['ae']['uri'])
        
    def testGetAeNotFound(self):
        with self.assertRaises(AppError) as e:
            self.restServerTestApp.get('/openclos/v1/overlay/aes/12345')
        self.assertTrue('404 Not Found' in e.exception.message)
        self.assertTrue('1113' in e.exception.message)
        
    def testCreateAe(self):
        aeDict = {
            "ae": {
                "name": "ae1",
                "description": "description for ae1",
                "esi": "00:01:01:01:01:01:01:01:01:01",
                "lacp": "00:00:00:01:01:01"
            }
        }
        response = self.restServerTestApp.post('/openclos/v1/overlay/aes', 
                                               headers = {'Content-Type':'application/json'}, 
                                               params=json.dumps(aeDict))
        self.assertEqual(201, response.status_int)
        response = self.restServerTestApp.get('/openclos/v1/overlay/aes/' + response.json['ae']['id'])
        self.assertEqual(200, response.status_int) 

    def testModifyAe(self):
        with self._dao.getReadWriteSession() as session:        
            aeObject = self.helper._createAe(session)
            aeId = aeObject.id
        aeDict = {
            "ae": {
                "name": "ae1",
                "description": "changed",
                "esi": "11:01:01:01:01:01:01:01:01:01",
                "lacp": "11:00:00:01:01:01"
            }
        }
        aeDict['ae']['id'] = aeId
        response = self.restServerTestApp.put('/openclos/v1/overlay/aes/' + aeId, 
                                               headers = {'Content-Type':'application/json'}, 
                                               params=json.dumps(aeDict))
        self.assertEqual(200, response.status_int)
        self.assertEqual('changed', response.json['ae']['description'])
        self.assertEqual('11:01:01:01:01:01:01:01:01:01', response.json['ae']['esi'])
        self.assertEqual('11:00:00:01:01:01', response.json['ae']['lacp'])
        
    def testModifyAeNotFound(self):
        aeDict = {
            "ae": {
                "id": '12345',
                "name": "ae1",
                "description": "changed",
                "esi": "11:01:01:01:01:01:01:01:01:01",
                "lacp": "11:00:00:01:01:01"
            }
        }
        with self.assertRaises(AppError) as e:
            self.restServerTestApp.put('/openclos/v1/overlay/aes/12345',
                                       headers = {'Content-Type':'application/json'}, 
                                       params=json.dumps(aeDict))
        self.assertTrue('404 Not Found' in e.exception.message)
        self.assertTrue('1113' in e.exception.message)
        
    def testDeleteAe(self):
        with self._dao.getReadWriteSession() as session:        
            aeObject = self.helper._createAe(session)
            aeId = aeObject.id
                    
        response = self.restServerTestApp.delete('/openclos/v1/overlay/aes/' + aeId)
        self.assertEqual(204, response.status_int) 
        
    def testDeleteAeNotFound(self):
        with self.assertRaises(AppError) as e:
            self.restServerTestApp.delete('/openclos/v1/overlay/aes/12345')
        self.assertTrue('404 Not Found' in e.exception.message)
        self.assertTrue('1113' in e.exception.message)
        
    def testGetDeployStatusBrief(self):
        with self._dao.getReadWriteSession() as session:        
            vrfObject = self.helper._createVrf(session)
            vrfId = vrfObject.id
            deviceObject = vrfObject.overlay_tenant.overlay_fabric.overlay_devices[0]
            deployStatusObject = self.helper._createDeployStatus(session, deviceObject, vrfObject)
                    
        response = self.restServerTestApp.get('/openclos/v1/overlay/vrfs/' + vrfId + '/status?mode=brief')
        self.assertEqual(200, response.status_int) 
        self.assertEqual('failure', response.json['statusBrief']['status'])
        self.assertTrue('/openclos/v1/overlay/vrfs/' + vrfId + '/status?mode=brief' in response.json['statusBrief']['uri'])
        
    def testGetDeployStatusDetail(self):
        with self._dao.getReadWriteSession() as session:        
            vrfObject = self.helper._createVrf(session)
            vrfId = vrfObject.id
            deviceObject = vrfObject.overlay_tenant.overlay_fabric.overlay_devices[0]
            deviceName = deviceObject.name
            deployStatusObject = self.helper._createDeployStatus(session, deviceObject, vrfObject)
                    
        response = self.restServerTestApp.get('/openclos/v1/overlay/vrfs/' + vrfId + '/status?mode=detail')
        self.assertEqual(200, response.status_int) 
        self.assertEqual('failure', response.json['statusDetail']['status'])
        self.assertTrue('/openclos/v1/overlay/vrfs/' + vrfId + '/status?mode=detail' in response.json['statusDetail']['uri'])
        self.assertEqual(1, response.json['statusDetail']['failure']['total'])
        self.assertTrue('/openclos/v1/overlay/vrfs/' + vrfId in response.json['statusDetail']['failure']['objects'][0]['uri'])
        self.assertEqual(1, response.json['statusDetail']['failure']['objects'][0]['total'])
        self.assertEqual('v1_config', response.json['statusDetail']['failure']['objects'][0]['configs'][0]['configlet'])
        self.assertEqual('conflict', response.json['statusDetail']['failure']['objects'][0]['configs'][0]['reason'])
        self.assertEqual(deviceName, response.json['statusDetail']['failure']['objects'][0]['configs'][0]['device'])
        
if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()
