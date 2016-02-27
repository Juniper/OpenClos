'''
Created on Sep 6, 2014

@author: moloyc
'''
import unittest
import os
import shutil
import json
from threading import Thread
from webtest import TestApp, AppError

from jnpr.openclos.rest import RestServer
from jnpr.openclos.underlayRestRoutes import webServerRoot, junosImageRoot
from test_dao import InMemoryDao 


configLocation = webServerRoot
imageLocation = junosImageRoot

class TestUnderlayRestRoutes(unittest.TestCase):

    def setUp(self):
        if not os.path.exists(configLocation):
            os.makedirs(configLocation)
        self._dao = InMemoryDao.getInstance()
        self._conf = {'restServer': {'version': 1, 'protocol': 'http', 'ipAddr': '1.2.3.4', 'port': 9090}}
        self.restServer = RestServer(self._conf, InMemoryDao)
        self.restServer.initRest()
        self.restServer.installRoutes()
        self.restServerTestApp = TestApp(self.restServer.app)

    def tearDown(self):
        shutil.rmtree(os.path.join(configLocation, 'test1'), ignore_errors=True)
        self.restServer.stop()
        InMemoryDao._destroy()

    def testInit(self):
        self.assertEqual(1, self.restServer.version)
        self.assertEqual('http', self.restServer.protocol)
        self.assertEqual('1.2.3.4', self.restServer.host)
        self.assertEqual(9090, self.restServer.port)
        
    def testGetIndexNoPodNoDevice(self):
        response = self.restServerTestApp.get('/openclos')
        self.assertEqual(200, response.status_int)
        self.assertEqual(2, len(response.json['links']))

    def testGetIndexNoPodNoDevice(self):
        response = self.restServerTestApp.get('/openclos/v1')
        self.assertEqual(200, response.status_int)
        self.assertEqual(2, len(response.json['links']))

    def testGetPodsNoPod(self):
        response = self.restServerTestApp.get('/openclos/v1/underlay/pods')
        self.assertEqual(200, response.status_int)
        self.assertEqual(0, len(response.json['pods']['pod']))

    def setupRestWithTwoDevices(self, session):
        from test_model import createDevice
        self.device1 = createDevice(session, "test1")
        self.device2 = createDevice(session, "test2")
    
    def setupRestWithTwoPods(self, session):
        from test_model import createPod
        self.pod1 = createPod("test1", session)
        self.pod2 = createPod("test2", session)

    def testGetPods(self):
        with self._dao.getReadWriteSession() as session:
            self.setupRestWithTwoDevices(session)
            device1PodId = self.device1.pod_id
            device2PodId = self.device2.pod_id
                    
        response = self.restServerTestApp.get('/openclos/v1/underlay/pods')
        self.assertEqual(200, response.status_int) 
        self.assertEqual(2, len(response.json['pods']['pod']))
        self.assertTrue("/openclos/v1/underlay/pods/"+device1PodId in response.json['pods']['pod'][0]['uri'])
        self.assertTrue("/openclos/v1/underlay/pods/"+device2PodId in response.json['pods']['pod'][1]['uri'])

    def testGetDevicesNonExistingPod(self):
        with self.assertRaises(AppError) as e:
            self.restServerTestApp.get('/openclos/v1/underlay/pods/' + 'nonExisting'+'/devices')
        self.assertTrue('404 Not Found' in e.exception.message)
    
    def testGetDevices(self):
        with self._dao.getReadWriteSession() as session:
            self.setupRestWithTwoDevices(session)
            device1PodId = self.device1.pod_id
            device1Id = self.device1.id

        response = self.restServerTestApp.get('/openclos/v1/underlay/pods/'+device1PodId+'/devices')
        self.assertEqual(200, response.status_int) 
        self.assertEqual(1, len(response.json['devices']['device']))
        self.assertTrue("/openclos/v1/underlay/pods/"+device1PodId+"/devices/"+device1Id in response.json['devices']['device'][0]['uri'])
    
    def testGetDeviceNonExistingDevice(self):
        with self._dao.getReadWriteSession() as session:
            self.setupRestWithTwoPods(session)
            pod1Id = self.pod1.id
            
        with self.assertRaises(AppError) as e:
            self.restServerTestApp.get('/openclos/v1/underlay/pods/' +pod1Id+'/devices/'+'nonExisting')
        self.assertTrue('404 Not Found' in e.exception.message)
    
    def testGetDevice(self):
        with self._dao.getReadWriteSession() as session:
            self.setupRestWithTwoDevices(session)
            device1PodId = self.device1.pod_id
            device1Id = self.device1.id
            deviceName = self.device1.name
            deviceFamily = self.device1.family

        response = self.restServerTestApp.get('/openclos/v1/underlay/pods/'+device1PodId+'/devices/'+device1Id)
        self.assertEqual(200, response.status_int)         
        self.assertEqual(deviceName, response.json['device']['name'])
        self.assertEqual(deviceFamily, response.json['device']['family'])
        self.assertTrue('/openclos/v1/underlay/pods/' + device1PodId in response.json['device']['pod']['uri']) 

    def testGetIndex(self):
        response = self.restServerTestApp.get('/')
        self.assertEqual(302, response.status_int)
        
    def testGetConfigNoDevice(self):
        with self._dao.getReadWriteSession() as session:
            self.setupRestWithTwoDevices(session)
            device1PodId = self.device1.pod_id

        with self.assertRaises(AppError) as e:
            self.restServerTestApp.get('/openclos/v1/underlay/pods/'+device1PodId+'/devices/'+'nonExisting'+'/config')
        self.assertTrue('404 Not Found' in e.exception.message)
        self.assertTrue('No device found' in e.exception.message)

    def testGetConfigNoConfigFile(self):
        with self._dao.getReadWriteSession() as session:
            self.setupRestWithTwoDevices(session)
            podId = self.device1.pod_id
            deviceId = self.device1.id
       
        with self.assertRaises(AppError) as e:
            self.restServerTestApp.get('/openclos/v1/underlay/pods/'+podId+'/devices/'+deviceId+'/config')
        self.assertTrue('404 Not Found' in e.exception.message)
        self.assertTrue('Device exists but no config found' in e.exception.message)

    def testGetConfig(self):
        from jnpr.openclos.model import DeviceConfig
        with self._dao.getReadWriteSession() as session:
            self.setupRestWithTwoDevices(session)
            self.device1.config = DeviceConfig(self.device1.id, "testconfig")
            podId = self.device1.pod_id
            deviceId = self.device1.id
            
        response = self.restServerTestApp.get('/openclos/v1/underlay/pods/'+podId+'/devices/'+deviceId+'/config')
        self.assertEqual(200, response.status_int)
        self.assertEqual("testconfig", response.body)
        
    def testGetDeviceConfigsInZip(self):
        from jnpr.openclos.model import DeviceConfig
        with self._dao.getReadWriteSession() as session:
            self.setupRestWithTwoDevices(session)
            self.device1.config = DeviceConfig(self.device1.id, "testconfig")
            podId = self.device1.pod_id
            deviceId = self.device1.id
            
        response = self.restServerTestApp.get('/openclos/v1/underlay/pods/'+podId+'/device-configuration')
        self.assertEqual(200, response.status_int)
        self.assertEqual('application/zip', response.headers.get('Content-Type'))
        
        import StringIO
        import zipfile
        buff = StringIO.StringIO(response.body)
        archive = zipfile.ZipFile(buff, "r")
        self.assertEqual(1, len(archive.namelist()))

    def testGetDeviceConfigsInZipUnknownPod(self):
        with self._dao.getReadWriteSession() as session:
            self.setupRestWithTwoDevices(session)
            podDir = os.path.join(configLocation, self.device1.pod_id+'-test1')
            if not os.path.exists(podDir):
                os.makedirs(podDir)
            open(os.path.join(podDir, self.device1.id+'-test1.conf'), "a") 

        with self.assertRaises(AppError) as e:
            self.restServerTestApp.get('/openclos/v1/underlay/pods/UNOKNOWN/device-configuration')
        self.assertTrue('404 Not Found' in e.exception.message)
        shutil.rmtree(podDir, ignore_errors=True)

    def testGetJunosImage404(self):
        with self.assertRaises(AppError) as e:
            self.restServerTestApp.get('/openclos/v1/underlay/images/abcd.tgz')
        self.assertTrue('404 Not Found' in e.exception.message)

    def testGetJunosImage(self):
        open(os.path.join(imageLocation, 'efgh.tgz'), "a") 
        
        response = self.restServerTestApp.get('/openclos/v1/underlay/images/efgh.tgz')
        self.assertEqual(200, response.status_int)
        os.remove(os.path.join(imageLocation, 'efgh.tgz'))
        
    def testGetPod(self):
        with self._dao.getReadWriteSession() as session:
            self.setupRestWithTwoPods(session)
            pod1Id = self.pod1.id
            pod1Name = self.pod1.name
            pod1SpineDeviceType = self.pod1.spineDeviceType
            pod1SpineUplinkPorts = self.pod1.spineUplinkRegex
            pod1LeafUplinkPorts = self.pod1.leafSettings[0].uplinkRegex

        response = self.restServerTestApp.get('/openclos/v1/underlay/pods/' + pod1Id)
        self.assertEqual(200, response.status_int)
        self.assertEqual(pod1Id, response.json['pod']['id'])
        self.assertEqual(pod1Name, response.json['pod']['name'])
        self.assertEqual(pod1SpineDeviceType, response.json['pod']['spineSettings'][0]['deviceType'])
        self.assertEqual(pod1SpineUplinkPorts, response.json['pod']['spineSettings'][0]['uplinkPorts'])
        self.assertEqual(pod1LeafUplinkPorts, response.json['pod']['leafSettings'][0]['uplinkPorts'])
        self.assertTrue('/openclos/v1/underlay/pods/' + pod1Id + '/cabling-plan' in response.json['pod']['cablingPlan']['uri'])
        self.assertTrue('/openclos/v1/underlay/pods/' + pod1Id + '/devices' in response.json['pod']['devices']['uri'])

    def testGetgetNonExistingPod(self):
        with self.assertRaises(AppError) as e:
            self.restServerTestApp.get('/openclos/v1/underlay/pods/' + 'nonExisting')
        self.assertTrue('404 Not Found' in e.exception.message)
        
    def testGetNonExistingCablingPlan(self):
        with self._dao.getReadWriteSession() as session:
            self.setupRestWithTwoPods(session)
            pod1Id = self.pod1.id
        with self.assertRaises(AppError) as e:
            self.restServerTestApp.get('/openclos/v1/underlay/pods/'+pod1Id+'/cabling-plan',headers = {'Accept':'application/json'})
        self.assertTrue('404 Not Found' in e.exception.message)
    
    def testGetCablingPlanJson(self):
        from jnpr.openclos.model import CablingPlan
        with self._dao.getReadWriteSession() as session:
            self.setupRestWithTwoPods(session)
            cablingPlan = CablingPlan(self.pod1.id, 'cabling json')
            self.pod1.cablingPlan = cablingPlan
            
            pod1Id = self.pod1.id

        response = self.restServerTestApp.get('/openclos/v1/underlay/pods/'+pod1Id+'/cabling-plan',headers = {'Accept':'application/json'})
        self.assertEqual(200, response.status_int)
        self.assertEqual('cabling json', response.body)
        
    def testGetCablingPlanDot(self):
        with self._dao.getReadWriteSession() as session:
            self.setupRestWithTwoPods(session)
            cablingPlanLocation = os.path.join(configLocation, self.pod1.id+'-'+self.pod1.name)
            if not os.path.exists(os.path.join(cablingPlanLocation)):
                os.makedirs((os.path.join(cablingPlanLocation)))
            ls = open(os.path.join(cablingPlanLocation, 'cablingPlan.dot'), "a+")
            pod1Id = self.pod1.id
       
        response = self.restServerTestApp.get('/openclos/v1/underlay/pods/'+pod1Id+'/cabling-plan',headers = {'Accept':'application/dot'})
        self.assertEqual(200, response.status_int)
        ls.close()
        shutil.rmtree(cablingPlanLocation, ignore_errors=True)
        
    def testGetZtpConfig(self):
        with self._dao.getReadWriteSession() as session:
            self.setupRestWithTwoPods(session)
            ztpConfigLocation = os.path.join(configLocation, self.pod1.id+'-'+self.pod1.name)
            if not os.path.exists(os.path.join(ztpConfigLocation)):
                os.makedirs((os.path.join(ztpConfigLocation)))
            ls = open(os.path.join(ztpConfigLocation, 'dhcpd.conf'), "a+")
            pod1Id = self.pod1.id
       
        response = self.restServerTestApp.get('/openclos/v1/underlay/pods/'+pod1Id+'/ztp-configuration')
        self.assertEqual(200, response.status_int)
        ls.close()
        shutil.rmtree(ztpConfigLocation, ignore_errors=True)
        
    def testGetNonExistingZtpConfig(self):
        with self._dao.getReadWriteSession() as session:
            self.setupRestWithTwoPods(session)
            pod1Id = self.pod1.id

        with self.assertRaises(AppError) as e:
            self.restServerTestApp.get('/openclos/v1/underlay/pods/'+pod1Id+'/ztp-configuration')
        self.assertTrue('404 Not Found' in e.exception.message)
        
    def testgetOpenClosConfigParams(self):
        self.restServer._conf['dbUrl'] = InMemoryDao.getInstance()._getDbUrl()
        self.restServer._conf['DOT'] = {'colors': []}
        self.restServer._conf['restServer'] = {'version': 1, 'protocol': 'http', 'ipAddr': '0.0.0.0', 'port': 20080}
        self.restServer._conf['snmpTrap'] = {'openclos_trap_group': {'port': 20162, 'target': '0.0.0.0'}}
        
        response = self.restServerTestApp.get('/openclos/v1/underlay/conf')
        self.assertEqual(200, response.status_int)
        self.assertTrue(response.json['OpenClosConf']['restServer'].has_key('port'))
        self.assertTrue(response.json['OpenClosConf']['snmpTrap']['openclos_trap_group'].has_key('port'))   
        self.assertEquals(19, len(response.json['OpenClosConf']['supportedDevices']))
        
    def testdeletePod(self):
        with self._dao.getReadWriteSession() as session:
            self.setupRestWithTwoPods(session)
            pod1Id = self.pod1.id
        
        response = self.restServerTestApp.delete('/openclos/v1/underlay/pods/'+pod1Id)
        self.assertEqual(204, response.status_int)
        response = self.restServerTestApp.get('/openclos/v1/underlay/pods')
        self.assertEqual(1, response.json['pods']['total'])
          
    def testDeleteNonExistingPod(self):
        with self.assertRaises(AppError) as e:
            self.restServerTestApp.delete('/openclos/v1/underlay/pods/' + 'nonExisting')
        self.assertTrue('404 Not Found', e.exception.message)
        
    def testCreatePodWithPostBodyEmpty(self):
        response = self.restServerTestApp.post('/openclos/v1/underlay/pods', headers = {'Content-Type':'application/json'}, expect_errors = True)
        self.assertEqual(400, response.status_int)
        self.assertTrue('No json in request object' in response.json['errorMessage'] )

    def testCreatePodWithPost(self):
        self.tearDown()
        self._conf['deviceFamily'] = {
            "qfx5100-24q-2p": {
                "ports": 'et-0/0/[0-23]'
            },
            "qfx5100-48s-6q": {
                "uplinkPorts": 'et-0/0/[48-53]', 
                "downlinkPorts": 'xe-0/0/[0-47]'
            },
            "ex4300-24p": {
                "uplinkPorts": 'et-0/1/[0-3]', 
                "downlinkPorts": 'ge-0/0/[0-23]'
            }
        }

        restServer = RestServer(self._conf, InMemoryDao)
        restServer.initRest()
        restServer.installRoutes()
        self.restServerTestApp = TestApp(restServer.app)
        
        pod = {
            "pod": {
                "name": "test12321",
                "spineSettings": [{"deviceType": "qfx5100-24q-2p"}],
                "spineCount": 2,
                "spineAS": 5,
                "leafSettings": [{"deviceType": "ex4300-24p"},{"deviceType": "qfx5100-48s-6q"}],
                "leafCount": 3,
                "leafAS": 10,
                "topologyType": "threeStage",
                "loopbackPrefix": "12.1.1.1/21",
                "vlanPrefix": "15.1.1.1/21",
                "interConnectPrefix": "14.1.1.1/21",
                "outOfBandAddressList": "10.204.244.95",
                "managementPrefix": "192.168.2.1/24",
                "description": "test12321",
                "hostOrVmCountPerLeaf": 254,
                "devicePassword": "test123",
                "outOfBandGateway": "192.168.2.1",
                "devices": [
                  {"role": "spine", "family": "qfx5100-24q-2p", "name": "test12321-spine-0", "username": "root", "password": "viren123", "serialNumber":"1234567", "deployStatus": "deploy"},
                  {"role": "spine", "family": "qfx5100-24q-2p", "name": "test12321-spine-1", "serialNumber":"JNPR-1234" },
                  {"role": "leaf", "family": "qfx5100-48s-6q", "name": "test12321-leaf-0", "serialNumber":"JNPR-3456", "deployStatus": "deploy"},
                  {"role": "leaf", "family": "qfx5100-48s-6q", "name": "test12321-leaf-1", "serialNumber":"JNPR-5678", "deployStatus": "deploy"},
                  {"role": "leaf", "name": "test12321-leaf-2"}
                ]
            }
        }

        response = self.restServerTestApp.post('/openclos/v1/underlay/pods', headers = {'Content-Type':'application/json'}, params=json.dumps(pod))
        self.assertEqual(201, response.status_int)
        response = self.restServerTestApp.get('/openclos/v1/underlay/pods')
        self.assertEqual(200, response.status_int) 
        self.assertEqual(1, len(response.json['pods']['pod']))

    def testReconfigurePodWithPostBodyEmpty(self):
        with self._dao.getReadWriteSession() as session:
            self.setupRestWithTwoPods(session)
            pod1Id = self.pod1.id
        
        response = self.restServerTestApp.put('/openclos/v1/underlay/pods/'+pod1Id, headers = {'Content-Type':'application/json'}, expect_errors = True)
        self.assertEqual(400, response.status_int)
        self.assertTrue('No json in request object' in response.json['errorMessage'] )
        
    def testUpdatePodWithInvalidRole(self):
        with self._dao.getReadWriteSession() as session:
            self.setupRestWithTwoPods(session)
            pod1Id = self.pod1.id
        
        podDetails = {
            "pod": {
                "name": "moloy1",
                "spineDeviceType": "qfx5100-24q-2p",
                "spineCount": 2,
                "spineAS": 100,
                "deviceType": "qfx5100-48s-6q",
                "leafCount": 1,
                "leafAS": 200,
                "topologyType": "threeStage",
                "loopbackPrefix": "1.1.1.1",
                "vlanPrefix": "3.3.3.3",
                "interConnectPrefix": "2.2.2.2",
                "outOfBandAddressList": "10.204.244.95",
                "outOfBandGateway": "10.204.244.254",
                "managementPrefix": "4.4.4.0/24",
                "description": "moloy 11111111",
                "hostOrVmCountPerLeaf": 254,
                "devices": [
                    {
                    "role": "test",
                    "name": "pparam_Test1-spine-0",
                    "username": "root",
                    "password": "Test123!",
                    "serialNumber":"JNPR-1234567"
                    },
                ]
            }
        }
        response = self.restServerTestApp.put('/openclos/v1/underlay/pods/'+pod1Id, params=json.dumps(podDetails), headers = {'Content-Type':'application/json'}, expect_errors = True)
        self.assertEqual(400, response.status_int)
        self.assertTrue('Unexpected role value' in response.json['errorMessage'] )         

    def testGetLeafGenericConfiguration404(self):
        with self._dao.getReadWriteSession() as session:
            self.setupRestWithTwoPods(session)
            pod1Id = self.pod1.id
        
        with self.assertRaises(AppError) as e:
            self.restServerTestApp.get('/openclos/v1/underlay/pods/'+pod1Id+'/leaf-generic-configurations/qfx5100-48s-6q')
        self.assertTrue('404 Not Found' in e.exception.message)
        self.assertTrue('Pod exists but no leaf generic config' in e.exception.message)
        self.assertTrue('qfx5100-48s-6q' in e.exception.message)

    def setupRestWithPodAndGenericConfig(self, session):
        from test_model import createPod
        from jnpr.openclos.model import LeafSetting
        self.pod1 = createPod("test1", session)
        leafSetting = LeafSetting('qfx5100-48s-6q', self.pod1.id, config = "testConfig abcd")
        self.pod1.leafSettings = [leafSetting]
        session.merge(self.pod1)


    def testGetLeafGenericConfiguration(self):
        with self._dao.getReadWriteSession() as session:
            self.setupRestWithPodAndGenericConfig(session)
            pod1Id = self.pod1.id
        
        response = self.restServerTestApp.get('/openclos/v1/underlay/pods/'+pod1Id+'/leaf-generic-configurations/qfx5100-48s-6q')
        self.assertEqual(200, response.status_int) 
        self.assertTrue('testConfig abcd' in response.body)

if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()
