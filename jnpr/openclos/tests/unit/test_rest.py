'''
Created on Sep 6, 2014

@author: moloyc
'''
import unittest
import os
import shutil
import json
from webtest import TestApp, AppError

from jnpr.openclos.rest import RestServer, webServerRoot, junosImageRoot
import jnpr.openclos.util

configLocation = webServerRoot
imageLocation = junosImageRoot

class TestRest(unittest.TestCase):

    def setUp(self):
        '''Creates with in-memory DB'''
        self.conf = {}
        self.conf['dbUrl'] = 'sqlite:///'
        
        if not os.path.exists(configLocation):
            os.makedirs(configLocation)
        jnpr.openclos.util.loadLoggingConfig()


    def tearDown(self):
        shutil.rmtree(os.path.join(configLocation, 'test1'), ignore_errors=True)


    def testInit(self):
        self.conf['httpServer'] = {}
        self.conf['httpServer']['ipAddr'] = '1.2.3.4'
        self.conf['httpServer']['port'] = 9090
        restServer = RestServer(self.conf)
        
        self.assertEqual('1.2.3.4', restServer.host)
        self.assertEqual(9090, restServer.port)
        self.assertEqual('http://1.2.3.4:9090', restServer.baseUrl)
        
    def testGetIndexNoPodNoDevice(self):
        restServer = RestServer(self.conf)
        restServer.initRest()
        restServerTestApp = TestApp(restServer.app)

        response = restServerTestApp.get('/openclos')
        self.assertEqual(200, response.status_int)
        self.assertEqual(2, len(response.json['links']))
        
    def testGetIpFabricsNoPod(self):
        restServer = RestServer(self.conf)
        restServer.initRest()
        restServerTestApp = TestApp(restServer.app)
    
        response = restServerTestApp.get('/openclos/ip-fabrics')
        self.assertEqual(200, response.status_int)
        self.assertEqual(0, len(response.json['ipFabrics']['ipFabric']))
    
    def testGetIpFabrics(self):
        restServerTestApp = self.setupRestWithTwoDevices()
                
        response = restServerTestApp.get('/openclos/ip-fabrics')
        self.assertEqual(200, response.status_int) 
        self.assertEqual(2, len(response.json['ipFabrics']['ipFabric']))
        self.assertTrue("/openclos/ip-fabrics/"+self.device1.pod_id in response.json['ipFabrics']['ipFabric'][0]['uri'])
        self.assertTrue("/openclos/ip-fabrics/"+self.device2.pod_id in response.json['ipFabrics']['ipFabric'][1]['uri'])
        
    def testGetDevicesNonExistingIpFabric(self):
        restServer = RestServer(self.conf)
        restServer.initRest()
        restServerTestApp = TestApp(restServer.app)
    
        with self.assertRaises(AppError) as e:
            restServerTestApp.get('/openclos/ip-fabrics/' + 'nonExisting'+'/devices')
        self.assertTrue('404 Not Found' in e.exception.message)
    
    def testGetDevices(self):
        restServerTestApp = self.setupRestWithTwoDevices()
        podId = self.device1.pod_id
        response = restServerTestApp.get('/openclos/ip-fabrics/'+self.device1.pod_id+'/devices')
        self.assertEqual(200, response.status_int) 
        self.assertEqual(1, len(response.json['devices']['device']))
        self.assertTrue("/openclos/ip-fabrics/"+podId+"/devices/"+self.device1.id in response.json['devices']['device'][0]['uri'])
    
    def testGetDeviceNonExistingDevice(self):
        restServerTestApp = self.setupRestWithTwoPods()
    
        with self.assertRaises(AppError) as e:
            restServerTestApp.get('/openclos/ip-fabrics/' +self.ipFabric1.id+'/devices/'+'nonExisting')
        self.assertTrue('404 Not Found' in e.exception.message)
    
    def testGetDevice(self):
        restServerTestApp = self.setupRestWithTwoDevices()
        self.podId =  self.device1.pod_id
        response = restServerTestApp.get('/openclos/ip-fabrics/'+self.podId+'/devices/'+self.device1.id)
        self.assertEqual(200, response.status_int)         
        self.assertEqual(self.device1.name, response.json['device']['name'])
        self.assertEqual(self.device1.family, response.json['device']['family'])
        self.assertTrue('/openclos/ip-fabrics/' + self.podId in response.json['device']['pod']['uri']) 
    
    def setupRestWithTwoDevices(self):
        from test_model import createDevice
        restServer = RestServer(self.conf)
        session = restServer.dao.Session()
        self.device1 = createDevice(session, "test1")
        self.device2 = createDevice(session, "test2")
        restServer.initRest()
        return TestApp(restServer.app)
    
    def setupRestWithTwoPods(self):
        from test_model import createPod
        restServer = RestServer(self.conf)
        session = restServer.dao.Session()
        self.ipFabric1 = createPod("test1", session)
        self.ipFabric2 = createPod("test2", session)
        restServer.initRest()
        return TestApp(restServer.app)
           
    def testGetIndex(self):
        restServerTestApp = self.setupRestWithTwoDevices()

        response = restServerTestApp.get('/')
        self.assertEqual(302, response.status_int)
        
    
    def testGetConfigNoDevice(self):
        restServerTestApp = self.setupRestWithTwoDevices()

        with self.assertRaises(AppError) as e:
            restServerTestApp.get('/openclos/ip-fabrics/'+self.device1.pod_id+'/devices/'+'nonExisting'+'/config')
        self.assertTrue('404 Not Found' in e.exception.message)
        self.assertTrue('No device found' in e.exception.message)

    def testGetConfigNoConfigFile(self):
        restServerTestApp = self.setupRestWithTwoDevices()
       
        with self.assertRaises(AppError) as e:
            restServerTestApp.get('/openclos/ip-fabrics/'+self.device1.pod_id+'/devices/'+self.device1.id+'/config')
        self.assertTrue('404 Not Found' in e.exception.message)
        self.assertTrue('Device exists but no config found' in e.exception.message)

    def testGetConfig(self):
        restServerTestApp = self.setupRestWithTwoDevices()
        
        self.device1.config = "testconfig"
        response = restServerTestApp.get('/openclos/ip-fabrics/'+self.device1.pod_id+'/devices/'+self.device1.id+'/config')
        self.assertEqual(200, response.status_int)
        
    def testGetDeviceConfigsInZip(self):
        restServerTestApp = self.setupRestWithTwoDevices()

        self.device1.config = "testconfig"
        response = restServerTestApp.get('/openclos/ip-fabrics/'+self.device1.pod_id+'/device-configuration')
        self.assertEqual(200, response.status_int)
        self.assertEqual('application/zip', response.headers.get('Content-Type'))
        
        import StringIO
        import zipfile
        buff = StringIO.StringIO(response.body)
        archive = zipfile.ZipFile(buff, "r")
        self.assertEqual(1, len(archive.namelist()))

    def testGetDeviceConfigsInZipUnknownIpFabric(self):
        restServerTestApp = self.setupRestWithTwoDevices()
        podDir = os.path.join(configLocation, self.device1.pod_id+'-test1')
        if not os.path.exists(podDir):
            os.makedirs(podDir)

        open(os.path.join(podDir, self.device1.id+'-test1.conf'), "a") 
        with self.assertRaises(AppError) as e:
            restServerTestApp.get('/openclos/ip-fabrics/UNOKNOWN/device-configuration')
        self.assertTrue('404 Not Found' in e.exception.message)
        shutil.rmtree(podDir, ignore_errors=True)

    def testGetJunosImage404(self):
        restServerTestApp = self.setupRestWithTwoDevices()

        with self.assertRaises(AppError) as e:
            restServerTestApp.get('/openclos/images/abcd.tgz')
        self.assertTrue('404 Not Found' in e.exception.message)

    def testGetJunosImage(self):
        restServerTestApp = self.setupRestWithTwoDevices()

        open(os.path.join(imageLocation, 'efgh.tgz'), "a") 
        
        response = restServerTestApp.get('/openclos/images/efgh.tgz')
        self.assertEqual(200, response.status_int)
        os.remove(os.path.join(imageLocation, 'efgh.tgz'))
        
    def testGetIpFabric(self):
        restServerTestApp = self.setupRestWithTwoPods()

        response = restServerTestApp.get('/openclos/ip-fabrics/' + self.ipFabric1.id)
        self.assertEqual(200, response.status_int)
        self.assertEqual(self.ipFabric1.name, response.json['ipFabric']['name'])
        self.assertEqual(self.ipFabric1.spineDeviceType, response.json['ipFabric']['spineDeviceType'])
        self.assertTrue('/openclos/ip-fabrics/' + self.ipFabric1.id + '/cabling-plan' in response.json['ipFabric']['cablingPlan']['uri'])
        self.assertTrue('/openclos/ip-fabrics/' + self.ipFabric1.id + '/devices' in response.json['ipFabric']['devices']['uri'])

    def testGetgetNonExistingIpFabric(self):
        restServer = RestServer(self.conf)
        restServer.initRest()
        restServerTestApp = TestApp(restServer.app)

        with self.assertRaises(AppError) as e:
            restServerTestApp.get('/openclos/ip-fabrics/' + 'nonExisting')
        self.assertTrue('404 Not Found' in e.exception.message)
        
    def testGetNonExistingCablingPlan(self):
        restServerTestApp = self.setupRestWithTwoPods()
        with self.assertRaises(AppError) as e:
            restServerTestApp.get('/openclos/ip-fabrics/'+self.ipFabric1.id+'/cabling-plan',headers = {'Accept':'application/json'})
        self.assertTrue('404 Not Found' in e.exception.message)
    
    def testGetCablingPlanJson(self):
        from jnpr.openclos.model import CablingPlan
        restServerTestApp = self.setupRestWithTwoPods()
        cablingPlan = CablingPlan(self.ipFabric1.id, 'cabling json')
        self.ipFabric1.cablingPlan = cablingPlan

        response = restServerTestApp.get('/openclos/ip-fabrics/'+self.ipFabric1.id+'/cabling-plan',headers = {'Accept':'application/json'})
        self.assertEqual(200, response.status_int)
        self.assertEqual('cabling json', response.body)
        
    def testGetCablingPlanDot(self):
        restServerTestApp = self.setupRestWithTwoPods()
        cablingPlanLocation = os.path.join(configLocation, self.ipFabric1.id+'-'+self.ipFabric1.name)
        if not os.path.exists(os.path.join(cablingPlanLocation)):
            os.makedirs((os.path.join(cablingPlanLocation)))
        ls = open(os.path.join(cablingPlanLocation, 'cablingPlan.dot'), "a+")
       
        response = restServerTestApp.get('/openclos/ip-fabrics/'+self.ipFabric1.id+'/cabling-plan',headers = {'Accept':'application/dot'})
        self.assertEqual(200, response.status_int)
        ls.close()
        shutil.rmtree(cablingPlanLocation, ignore_errors=True)
        
    def testGetZtpConfig(self):
        restServerTestApp = self.setupRestWithTwoPods()
        ztpConfigLocation = os.path.join(configLocation, self.ipFabric1.id+'-'+self.ipFabric1.name)
        if not os.path.exists(os.path.join(ztpConfigLocation)):
            os.makedirs((os.path.join(ztpConfigLocation)))
        ls = open(os.path.join(ztpConfigLocation, 'dhcpd.conf'), "a+")
       
        response = restServerTestApp.get('/openclos/ip-fabrics/'+self.ipFabric1.id+'/ztp-configuration')
        self.assertEqual(200, response.status_int)
        ls.close()
        shutil.rmtree(ztpConfigLocation, ignore_errors=True)
        
    def testGetNonExistingZtpConfig(self):
        restServerTestApp = self.setupRestWithTwoPods()
        with self.assertRaises(AppError) as e:
            restServerTestApp.get('/openclos/ip-fabrics/'+self.ipFabric1.id+'/ztp-configuration')
        self.assertTrue('404 Not Found' in e.exception.message)
        
    def testgetOpenClosConfigParams(self):
        conf = {}
        restServer = RestServer(conf)
        restServer.initRest()
        restServerTestApp = TestApp(restServer.app)
        
        response = restServerTestApp.get('/openclos/conf')
        self.assertEqual(200, response.status_int)
        self.assertTrue(response.json['OpenClosConf']['httpServer'].has_key('port'))
        self.assertTrue(response.json['OpenClosConf']['snmpTrap']['networkdirector_trap_group'].has_key('port'))
        self.assertTrue(response.json['OpenClosConf']['snmpTrap']['openclos_trap_group'].has_key('port'))       
        
    def testdeleteIpFabric(self):
        restServerTestApp = self.setupRestWithTwoPods()
        
        response = restServerTestApp.delete('/openclos/ip-fabrics/'+self.ipFabric1.id)
        self.assertEqual(204, response.status_int)
        response = restServerTestApp.get('/openclos/ip-fabrics')
        self.assertEqual(1, response.json['ipFabrics']['total'])
          
    def testDeleteNonExistingIpFabric(self):
        restServer = RestServer(self.conf)
        restServer.initRest()
        restServerTestApp = TestApp(restServer.app)
        
        with self.assertRaises(AppError) as e:
            restServerTestApp.delete('/openclos/ip-fabrics/' + 'nonExisting')
        self.assertTrue('404 Not Found', e.exception.message)
        
    def testCreateIpFabricWithPostBodyEmpty(self):
        restServer = RestServer(self.conf)
        restServer.initRest()
        restServerTestApp = TestApp(restServer.app)
        
        response = restServerTestApp.post('/openclos/ip-fabrics', headers = {'Content-Type':'application/json'}, expect_errors = True)
        self.assertEqual(400, response.status_int)
        self.assertTrue('No json in request object' in response.json['errorMessage'] )

    def testCreateIpFabricWithPost(self):
        self.conf['deviceFamily'] = {
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

        restServer = RestServer(self.conf)
        restServer.initRest()
        restServerTestApp = TestApp(restServer.app)
        
        ipFabric = {
            "ipFabric": {
                "name": "test12321",
                "spineDeviceType": "qfx5100-24q-2p",
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
                "devicePassword": "viren123",
                "outOfBandGateway": "192.168.2.1",
                "devices": [
                  {"role": "spine", "family": "qfx5100-24q-2p", "name": "test12321-spine-0", "username": "root", "password": "viren123", "deployStatus": "deploy"},
                  {"role": "spine", "family": "qfx5100-24q-2p", "name": "test12321-spine-1"},
                  {"role": "leaf", "family": "qfx5100-48s-6q", "name": "test12321-leaf-0", "deployStatus": "deploy"},
                  {"role": "leaf", "family": "qfx5100-48s-6q", "name": "test12321-leaf-1", "deployStatus": "deploy"},
                  {"role": "leaf", "name": "test12321-leaf-2"}
                ]
            }
        }

        response = restServerTestApp.post('/openclos/ip-fabrics', headers = {'Content-Type':'application/json'}, params=json.dumps(ipFabric))
        self.assertEqual(201, response.status_int)

    def testReconfigureIpFabricWithPostBodyEmpty(self):
        restServerTestApp = self.setupRestWithTwoPods()
        
        response = restServerTestApp.put('/openclos/ip-fabrics/'+self.ipFabric1.id, headers = {'Content-Type':'application/json'}, expect_errors = True)
        self.assertEqual(400, response.status_int)
        self.assertTrue('No json in request object' in response.json['errorMessage'] )
        
    def testCreateIpFabricWithInvalidRole(self):
        restServerTestApp = self.setupRestWithTwoPods()
        
        ipFabricDetails = {
            "ipFabric": {
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
                    "password": "Test123!"
                    },
                ]
            }
        }
        response = restServerTestApp.put('/openclos/ip-fabrics/'+self.ipFabric1.id, params=json.dumps(ipFabricDetails), headers = {'Content-Type':'application/json'}, expect_errors = True)
        self.assertEqual(400, response.status_int)
        self.assertTrue('Unexpected role value' in response.json['errorMessage'] )         

    def testGetLeafGenericConfiguration404(self):
        restServerTestApp = self.setupRestWithTwoPods()
        podId = self.ipFabric1.id
        
        with self.assertRaises(AppError) as e:
            restServerTestApp.get('/openclos/ip-fabrics/'+podId+'/leaf-generic-configurations/qfx5100-48s-6q')
        self.assertTrue('404 Not Found' in e.exception.message)
        self.assertTrue('IpFabric exists but no leaf generic config' in e.exception.message)
        self.assertTrue('qfx5100-48s-6q' in e.exception.message)

    def setupRestWithPodAndGenericConfig(self):
        from test_model import createPod
        from jnpr.openclos.model import LeafSetting

        restServer = RestServer(self.conf)
        session = restServer.dao.Session()
        self.ipFabric1 = createPod("test1", session)
        leafSetting = LeafSetting('qfx5100-48s-6q', self.ipFabric1.id, config = "testConfig abcd")
        self.ipFabric1.leafSettings = [leafSetting]
        session.merge(self.ipFabric1)
        session.commit()

        restServer.initRest()
        return TestApp(restServer.app)

    def testGetLeafGenericConfiguration(self):
        restServerTestApp = self.setupRestWithPodAndGenericConfig()
        podId = self.ipFabric1.id
        
        response = restServerTestApp.get('/openclos/ip-fabrics/'+podId+'/leaf-generic-configurations/qfx5100-48s-6q')
        self.assertEqual(200, response.status_int) 
        self.assertTrue('testConfig abcd' in response.body)
        
if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()
