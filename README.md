OpenCLOS
========
OpneCLOS is a python library to automate Layer-3 IP Fabric design, deploy and maintainance. It performs following to create the IP Fabric.

* **Interface Assignments**
  * IP addressing
  * Loopback addressing
  * Subnet masks
  * PTP Links
  * Server VLAN
  * RVI assignment

* **Control Plane**
  * BGP ASN assignments
  * BGP import policy
  * BGP export policy
  * BGP peer group design
  * BGP next-hop self

* **High Availability**
  * BFD intervals
  * BFD multipliers
  * Ethernet OAM


Install
-------

    curl -L -u '<username>:<password>' -o OpenClos.zip https://github.com/Juniper/OpenClos/archive/<branch or tag>.zip
    sudo pip install OpenClos.zip


**Install in development mode**  

    curl -L -u '<username>:<password>' -o OpenClos.zip https://github.com/Juniper/OpenClos/archive/<branch or tag>.zip     
    unzip OpenClos.zip  
    cd OpenClos-xyz  
    sudo python setup.py develop  


Configuration
-------------
**junos image**  
Copy desired junos image file to OpenClos-xyz/jnpr/openclos/conf/ztp/
example - OpenClos-R1.0.dev1/jnpr/openclos/conf/ztp/jinstall-qfx-5-13.2X51-D20.2-domestic-signed.tgz

**junos template**  
Update management interface name in junosTemplates/mgmt_interface.txt  
The detault management interface name in template is 'vme'. Please change it to 'em0' if needed.   

**Global configuration openclos.yaml**   
If intend to perform ZTP process, please update REST ipaddress with the server's external ip address.  
example - ipAddr : 192.168.48.201  

**Pod specific configuration closTemplate.yaml**      
please make sure to update following settings as per the deployment environment  

* junosImage : jinstall-qfx-5-13.2X51-D20.2-domestic-signed.tgz
* dhcpSubnet : 192.168.48.128/25
* dhcpOptionRoute : 192.168.48.254
* spineCount : 4
* spineDeviceType : QFX5100-24Q
* leafCount : 6
* leafDeviceType : QFX5100-48S
* outOfBandAddressList: 


Run
---
Please refer to /path/to/OpenClos/jnpr/openclos/tests/sampleApplication.py

Run tests
---

    cd /path/to/OpenClos/jnpr/openclos/tests
    nosetests --exe --with-coverage --cover-package=jnpr.openclos --cover-erase
