OpenClos
========

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
* Spine Devices - QFX5100-24Q switches running Junos OS Release 13.2X51-D20 or later
* Leaf Devices - QFX5100-48S switches running Junos OS Release 13.2X51-D20 or later, maximum of 6 spine connections


Install OpenClos on the Management Server
-----------------------------------------

    curl -L -u '<username>:<password>' -o OpenClos.zip https://github.com/Juniper/OpenClos/archive/<branch or tag>.zip
    sudo pip install OpenClos.zip


**Install in development mode**  

    curl -L -u '<username>:<password>' -o OpenClos.zip https://github.com/Juniper/OpenClos/archive/<branch or tag>.zip     
    unzip OpenClos.zip  
    cd OpenClos-<version>  
    sudo python setup.py develop  


Configuration on the Management Server
--------------------------------------

**Junos OS image**  
Copy the Junos OS image file to OpenClos-<version>/jnpr/openclos/conf/ztp/
This image is pushed to the fabric devices in addition to the auto-generated configuration.

Example - OpenClos-R1.0.dev1/jnpr/openclos/conf/ztp/jinstall-qfx-5-13.2X51-D20.2-domestic-signed.tgz

**Junos OS template**  
Update the management interface name in the junosTemplates/mgmt_interface.txt file. 
The default management interface name in the template is 'vme'. Please change it to 'em0' as needed.   

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


Run tests
---------

    cd /path/to/OpenClos/jnpr/openclos/tests
    nosetests --exe --with-coverage --cover-package=jnpr.openclos --cover-erase


Output
------

The script generates the device configuration files and uses ZTP to send them to the devices.

It also generates a cabling plan in two formats:
* DOT file - cablingPlan.dot (this file can be viewed with an application like GraphViz)
* JSON file - cablingPlan.json

The cabling plan files are available in the <path-to-OpenClos>/jnpr/openclos/out directory.


Support
-----------

If you find an issue with the software, please open a bug report on the OpenClos repository.
For general questions and support, send e-mail to openclos-support@juniper.net.