![OpenClos](openClosLogo.jpeg)
==============================

[![UnitTest Status](https://travis-ci.org/Juniper/OpenClos.svg?branch=devR2.5)](https://travis-ci.org/Juniper/OpenClos)

OpenClos is a Python script library that helps you automate the design, deployment, and maintenance
of a Layer 3 IP fabric built on Border Gateway Protocol (BGP).

To create an IP fabric that uses a spine and leaf architecture, the script generates configuration files for the devices
in the fabric and uses zero-touch provisioning (ZTP) to push the configuration files to the devices. You can tailor the IP fabric
to your network environment by adjusting values in the template files that are associated with the script.

Note: Fabric devices must be placed in a factory-default or zeroized state to participate in an OpenClos-generated IP fabric.

When you execute the script, it automatically generates values for the following device configuration settings within the IP fabric:


* **Interface Assignments**
  * IP addressing
  * Loopback addressing
  * Subnet masks and prefixes
  * Point-to-point (PTP) links
  * Server VLAN ID
  * Integrated routing and bridging (IRB) interface assignment

* **Control Plane**
  * BGP autonomous system numbers (ASN)
  * BGP import policy
  * BGP export policy
  * BGP peer group design
  * BGP next-hop self

* **High Availability**
  * Bidirectional Forwarding Detection (BFD) intervals
  * BFD multipliers
  * Ethernet operations, administration, and management (OAM)

Supported Devices and Software
------------------------------

* Management Server - Python 2.7.x running on an Ubuntu 14.04 or CentOS 6.x based server
* Spine Devices - QFX5100-24Q switches running Junos OS Release 14.1X53-D15 or later
* Leaf Devices - QFX5100-48S, QFX5100-96S, EX4300-48T switches running Junos OS Release 14.1X53-D15 or later, maximum of 8 spine connections


Install OpenClos on the Management Server
-----------------------------------------

    curl -L -u '<username>:<password>' -o OpenClos.zip https://github.com/Juniper/OpenClos/archive/<branch or tag>.zip
    sudo pip install --egg OpenClos.zip


**Install in development mode**  

    curl -L -u '<username>:<password>' -o OpenClos.zip https://github.com/Juniper/OpenClos/archive/<branch or tag>.zip     
    unzip OpenClos.zip  
    cd OpenClos-<version>  
    sudo pip install --egg -e .  

**CentOS Installation Issues**  

* Error: Unable to execute gcc: No such file or directory
* Error: bin/sh: xslt-config: command not found, make sure the development packages of libxml2 and libxslt are installed
* Error:  #error Python headers needed to compile C extensions, please install development version of Python

For all the above errors, install the following packages and reinstall OpenClos.
  
    sudo yum install -y python-devel libxml2-devel libxslt-devel gcc openssl

* Error: error_name, '.'.join(version), '.'.join(min_version))), TypeError: sequence item 0: expected string, int found

In CentOS 5.7, if the installation of lxml 3.4 causes a problem, manually install lxml 3.3.6 and then install OpenClos
    sudo pip install lxml==3.3.6 --egg
    
    
**Ubuntu Installation Issues**  

* Error: fatal error: pyconfig.h: No such file or directory
* Error: bin/sh: xslt-config: command not found, make sure the development packages of libxml2 and libxslt are installed

For all the above errors, install the following packages and reinstall OpenClos
  
    sudo apt-get install -y python-dev libxml2-dev libxslt-dev


**Windows Installation Issues**  

* Error: "Unable to find vcvarsall.bat"
  
One of the OpenClos dependent modules uses PyCrypto. If the installation generates an error message, use the platform-specific prebuilt PyCrypto software from http://www.voidspace.org.uk/python/modules.shtml#pycrypto, and then reinstall OpenClos.


Configuration on the Management Server
--------------------------------------

**Database**  

* sqlite3 is the default database that uses a file-based database. For better performance, use a traditional database.
* To install the mysql database: issue the 'sudo apt-get install -y python-mysqldb' command, and then set the database connection parameters in openclos.yaml file.

**Junos OS image**
Copy the Junos OS image file to OpenClos-<version>/jnpr/openclos/conf/ztp/
This image is pushed to the fabric devices in addition to the auto-generated configuration.

Example - OpenClos-R1.0.dev1/jnpr/openclos/conf/ztp/jinstall-qfx-5-13.2X51-D20.2-domestic-signed.tgz

**Global configuration for the openclos.yaml file**
To configure ZTP, update the REST API IP address with the server's external IP address.

Example - ipAddr : 192.168.48.201

**POD specific configuration for the closTemplate.yaml file**

Please update the following settings per your own specific deployment environment:
* junosImage
* dhcpSubnet
* dhcpOptionRoute
* spineCount
* spineDeviceType
* leafCount
* leafDeviceType
* outOfBandAddressList

Example - based on a 10-member IP Fabric:
* junosImage : jinstall-qfx-5-13.2X51-D20.2-domestic-signed.tgz
* dhcpSubnet : 192.168.48.128/25
* dhcpOptionRoute : 192.168.48.254
* spineCount : 4
* spineDeviceType : QFX5100-24Q
* leafCount : 6
* leafDeviceType : QFX5100-48S
* outOfBandAddressList:
            - 10.94.185.18/32
            - 10.94.185.19/32
            - 172.16.0.0/12


For more examples, see <path-to-OpenClos>/jnpr/openclos/conf/closTemplate.yaml


Run the script
--------------

The script is available at <path-to-OpenClos>/jnpr/openclos/tests/sampleApplication.py

**Runtime issues**

* Error: ImportError: No module named openclos.model
* Error: ImportError: No module named openclos.l3Clos
* Error: ImportError: No module named openclos.rest
  
OpenClos and its dependent module junos-eznc both use the same 'jnpr' namespace. If junos-eznc was already installed with pip, uninstall this module by issuing the "pip uninstall junos-eznc" command and then install OpenClos by issuing the "pip install OpenClos.zip --egg" command. Be sure to use '--egg' flag to avoid a 'flat' installation, which causes an import error.


Run tests
---------

    cd <path-to-OpenClos>/jnpr/openclos/tests
    nosetests --exe --with-coverage --cover-package=jnpr.openclos --cover-erase


Output
------
The script generates the device configuration files and uses ZTP to send them to the devices.

It also generates a cabling plan in two formats:
* DOT file - cablingPlan.dot (this file can be viewed with an application like GraphViz)
* JSON file - cablingPlan.json

All generated configurations (device and ZTP configurations) are stored in the /jnpr/openclos/out/PODID-PODNAME directory

* Ubuntu standard install - "/usr/local/lib/python2.7/dist-packages/jnpr/openclos/out/PODID-PODNAME"
* Centos standard install - "/usr/lib/python2.6/site-packages/jnpr/openclos/out/PODID-PODNAME"


License
-------

Apache 2.0


Support
-------

If you find an issue with the software, please open a bug report on the OpenClos repository.

The Juniper Networks Technical Assistance Center (JTAC) does not provide support for OpenClos software. You can obtain support for OpenClos by visiting the [OpenClos Google Group](https://groups.google.com/forum/#!forum/openclos)

