'''
Created on Jan 5, 2015

@author: moloyc

Before running this test install locust - 'pip install locustio'
Running the test:
  1. locust -f stressRest.py
  2. Open browser http://localhost:8089/
  3. Start stress test
  4. Once done, download the csv file and save as locust.csv in this directory
  5. python postProcess.py 
  6. The result is in 'out.csv'

'''

from jnpr.openclos.rest import moduleName
from jnpr.openclos.util import loadLoggingConfig

from locust import HttpLocust, TaskSet, task
import json
import random
import time
import logging


def getFabricPostBody():
    fabric = random.choice(ipFabrics)
    fabric['ipFabric']['name'] = 'fabric-'+str(time.time())
    return fabric

class MyTaskSet(TaskSet):
    def on_start(self):
        loadLoggingConfig()
        self.logger = logging.getLogger(moduleName)
        self.fabricCount = 0
        '''
        restServer = RestServer()
        restServer.host = 'localhost'
        restServer.port = 9090
        restServer.initRest()
        t = threading.Thread(target=restServer.start)
        t.daemon = True
        t.start()
        '''
    
    @task(5)
    def getIpFabrics(self):
        response = self.client.get('/openclos/ip-fabrics')
        if response._content is not None:
            jsonContent = json.loads(response._content)
            self.fabricIds = [f['id'] for f in jsonContent['ipFabrics']['ipFabric']]
        #self.logger.info(self.fabricIds)

    @task(5)
    def getIpFabric(self):
        if self.fabricIds:
            id = random.choice(self.fabricIds)
            #self.logger.info('GET /openclos/ip-fabrics/%s' % (id))
            self.client.get('/openclos/ip-fabrics/%s' % (id))
            
    @task(2)
    def createCabling(self):
        if self.fabricIds:
            id = random.choice(self.fabricIds)
            self.client.put('/openclos/ip-fabrics/%s/cabling-plan' % (id))
            
    @task(2)
    def createConfigs(self):
        if self.fabricIds:
            id = random.choice(self.fabricIds)
            self.client.put('/openclos/ip-fabrics/%s/device-configuration' % (id))
            
    @task(5)
    def getDevices(self):
        if self.fabricIds:
            id = random.choice(self.fabricIds)
            response = self.client.get('/openclos/ip-fabrics/%s/devices' % (id))
            #self.logger.info("RESPONSE: " + str(response.status_code) + ' ' + response.reason)
    
    @task(2)
    def createIpFabric(self):
        if self.fabricCount > 10:
            return
        self.fabricCount += 1
        kwargs = {}
        kwargs['headers'] = {'Content-Type':'application/json'}
        response = self.client.post('/openclos/ip-fabrics', json.dumps(getFabricPostBody()), **kwargs)
        #self.logger.info("RESPONSE: " + str(response.status_code) + ' ' + response.reason)

    @task(1)
    def getConf(self):
        self.client.get('/openclos/conf')

ipFabrics = [
    {"ipFabric": {
        "name": "name",
        "spineDeviceType": "qfx5100-24q-2p",
        "spineCount": 2,
        "spineAS": 5,
        "leafSettings": [{"deviceType": "ex4300-24p"},{"deviceType": "qfx5100-48s-6q"}],
        "leafCount": 6,
        "leafAS": 10,
        "topologyType": "threeStage",
        "loopbackPrefix": "12.1.1.1/21",
        "vlanPrefix": "15.1.1.1/20",
        "interConnectPrefix": "14.1.1.1/21",
        "outOfBandAddressList": "10.204.244.95",
        "managementPrefix": "192.168.2.1/24",
        "description": "test",
        "hostOrVmCountPerLeaf": 254,
        "devicePassword": "password",
        "outOfBandGateway": "192.168.2.1",
        "devices": [
          {"role": "spine", "family": "qfx5100-24q-2p", "name": "test-spine-01", "username": "root", "password": "password", "deployStatus": "deploy"},
          {"role": "spine", "family": "qfx5100-24q-2p", "name": "test-spine-02"},
          {"role": "leaf", "family": "qfx5100-48s-6q", "name": "test-leaf-01", "deployStatus": "deploy"},
          {"role": "leaf", "family": "qfx5100-48s-6q", "name": "test-leaf-02", "deployStatus": "deploy"},
          {"role": "leaf", "name": "test-leaf-03"},
          {"role": "leaf", "name": "test-leaf-04"},
          {"role": "leaf", "name": "test-leaf-05"},
          {"role": "leaf", "name": "test-leaf-06"}
        ]
    }},
    {"ipFabric": {
        "name": "name",
        "spineDeviceType": "qfx5100-24q-2p",
        "spineCount": 4,
        "spineAS": 5,
        "leafSettings": [{"deviceType": "ex4300-24p"},{"deviceType": "qfx5100-48s-6q"}],
        "leafCount": 10,
        "leafAS": 10,
        "topologyType": "threeStage",
        "loopbackPrefix": "12.1.1.1/21",
        "vlanPrefix": "15.1.1.1/20",
        "interConnectPrefix": "14.1.1.1/21",
        "outOfBandAddressList": "10.204.244.95",
        "managementPrefix": "192.168.2.1/24",
        "description": "test",
        "hostOrVmCountPerLeaf": 254,
        "devicePassword": "password",
        "outOfBandGateway": "192.168.2.1",
        "devices": [
          {"role": "spine", "family": "qfx5100-24q-2p", "name": "test-spine-01", "username": "root", "password": "password", "deployStatus": "deploy"},
          {"role": "spine", "family": "qfx5100-24q-2p", "name": "test-spine-02"},
          {"role": "spine", "family": "qfx5100-24q-2p", "name": "test-spine-03"},
          {"role": "spine", "family": "qfx5100-24q-2p", "name": "test-spine-04"},
          {"role": "leaf", "family": "qfx5100-48s-6q", "name": "test-leaf-01", "deployStatus": "deploy"},
          {"role": "leaf", "family": "qfx5100-48s-6q", "name": "test-leaf-02", "deployStatus": "deploy"},
          {"role": "leaf", "name": "test-leaf-03"},
          {"role": "leaf", "name": "test-leaf-04"},
          {"role": "leaf", "name": "test-leaf-05"},
          {"role": "leaf", "name": "test-leaf-06"},
          {"role": "leaf", "name": "test-leaf-07"},
          {"role": "leaf", "name": "test-leaf-08"},
          {"role": "leaf", "name": "test-leaf-09"},
          {"role": "leaf", "name": "test-leaf-10"}
        ]
    }},
    {"ipFabric": {
        "name": "name",
        "spineDeviceType": "qfx5100-24q-2p",
        "spineCount": 8,
        "spineAS": 5,
        "leafSettings": [{"deviceType": "ex4300-24p"},{"deviceType": "qfx5100-48s-6q"}],
        "leafCount": 20,
        "leafAS": 10,
        "topologyType": "threeStage",
        "loopbackPrefix": "12.1.1.1/21",
        "vlanPrefix": "15.1.1.1/16",
        "interConnectPrefix": "14.1.1.1/21",
        "outOfBandAddressList": "10.204.244.95",
        "managementPrefix": "192.168.2.1/24",
        "description": "test",
        "hostOrVmCountPerLeaf": 254,
        "devicePassword": "password",
        "outOfBandGateway": "192.168.2.1",
        "devices": [
          {"role": "spine", "family": "qfx5100-24q-2p", "name": "test-spine-01", "username": "root", "password": "password", "deployStatus": "deploy"},
          {"role": "spine", "family": "qfx5100-24q-2p", "name": "test-spine-02"},
          {"role": "spine", "family": "qfx5100-24q-2p", "name": "test-spine-03"},
          {"role": "spine", "family": "qfx5100-24q-2p", "name": "test-spine-04"},
          {"role": "spine", "family": "qfx5100-24q-2p", "name": "test-spine-05"},
          {"role": "spine", "family": "qfx5100-24q-2p", "name": "test-spine-06"},
          {"role": "spine", "family": "qfx5100-24q-2p", "name": "test-spine-07"},
          {"role": "spine", "family": "qfx5100-24q-2p", "name": "test-spine-08"},
          {"role": "leaf", "family": "qfx5100-48s-6q", "name": "test-leaf-01", "deployStatus": "deploy"},
          {"role": "leaf", "family": "qfx5100-48s-6q", "name": "test-leaf-02", "deployStatus": "deploy"},
          {"role": "leaf", "family": "qfx5100-48s-6q", "name": "test-leaf-03"},
          {"role": "leaf", "family": "qfx5100-48s-6q", "name": "test-leaf-04"},
          {"role": "leaf", "family": "qfx5100-48s-6q", "name": "test-leaf-05"},
          {"role": "leaf", "family": "qfx5100-48s-6q", "name": "test-leaf-06"},
          {"role": "leaf", "name": "test-leaf-07"},
          {"role": "leaf", "name": "test-leaf-08"},
          {"role": "leaf", "name": "test-leaf-09"},
          {"role": "leaf", "name": "test-leaf-10"},
          {"role": "leaf", "name": "test-leaf-11"},
          {"role": "leaf", "name": "test-leaf-12"},
          {"role": "leaf", "name": "test-leaf-13"},
          {"role": "leaf", "name": "test-leaf-14"},
          {"role": "leaf", "name": "test-leaf-15"},
          {"role": "leaf", "name": "test-leaf-16"},
          {"role": "leaf", "name": "test-leaf-17"},
          {"role": "leaf", "name": "test-leaf-18"},
          {"role": "leaf", "name": "test-leaf-19"},
          {"role": "leaf", "name": "test-leaf-20"}
        ]
    }}
]


class MyLocust(HttpLocust):
    host = "http://localhost:80"
    min_wait = 250
    max_wait = 500
    stop_timeout = 15000
    task_set = MyTaskSet

