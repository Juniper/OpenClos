OpenCLOS
========
OpneCLOS is a python library to automate Layer-3 IP Fabric design, deploy and maintenance. It performs following to create the IP Fabric.

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
    sudo pip install --egg OpenClos.zip


**Install in development mode**  

    curl -L -u '<username>:<password>' -o OpenClos.zip https://github.com/Juniper/OpenClos/archive/<branch or tag>.zip     
    unzip OpenClos.zip  
    cd OpenClos-xyz  
    sudo pip install --egg -e .  

**Centos install issues**  

* Error: Unable to execute gcc: No such file or directory
* Error: bin/sh: xslt-config: command not found, make sure the development packages of libxml2 and libxslt are installed
* Error:  #error Python headers needed to compile C extensions, please install development version of Python

For all above errors install following packages and re-try installing openclos  
  
    sudo yum install -y python-devel libxml2-devel libxslt-devel gcc openssl

* Error: error_name, '.'.join(version), '.'.join(min_version))), TypeError: sequence item 0: expected string, int found

Centos 5.7, install lxml 3.4 causes problem, manually install lxml 3.3.6 followed by openclos
    sudo pip install lxml==3.3.6 --egg
    
    
**Ubunu install issues**  

* Error: fatal error: pyconfig.h: No such file or directory
* Error: bin/sh: xslt-config: command not found, make sure the development packages of libxml2 and libxslt are installed

For all above errors install following packages and re-try installing openclos  
  
    sudo apt-get install -y python-dev libxml2-dev libxslt-dev


**Windows install issues**  

* Error: "Unable to find vcvarsall.bat"
  
One of the Openclos dependent module uses PyCrypto, if installation gives error use platform specific pre-built PyCrypto 
from - http://www.voidspace.org.uk/python/modules.shtml#pycrypto, then install openclos again.


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
* spineDeviceType : qfx5100-24q-2p
* leafCount : 6
* leafDeviceType : qfx5100-48s-6q
* outOfBandAddressList: 


Run
---
Please refer to /path/to/OpenClos/jnpr/openclos/tests/sampleApplication.py

**Runtime issues**

* Error: ImportError: No module named openclos.model
* Error: ImportError: No module named openclos.l3Clos
* Error: ImportError: No module named openclos.rest
  
openclos and dependent module junos-eznc both uses same namespace 'jnpr'. If junos-eznc was already installed with pip, 
uninstall (pip uninstall junos-eznc) then install openclos (pip install OpenClos.zip --egg). Make sure 
to use '--egg' flag to avoid 'flat' install, which causes import error.


Run tests
---------

    cd /path/to/OpenClos/jnpr/openclos/tests
    nosetests --exe --with-coverage --cover-package=jnpr.openclos --cover-erase


Output
------
All generated configurations (device configuration and ZTP configuration) are located at "out/PODID-PODNAME"

* Ubuntu standard install - "/usr/local/lib/python2.7/dist-packages/jnpr/openclos/out/PODID-PODNAME"
* Centos standard install - "/usr/lib/python2.6/site-packages/jnpr/openclos/out/PODID-PODNAME"
* Any platform, development install - "<openclos install folder>/out/PODID-PODNAME"
