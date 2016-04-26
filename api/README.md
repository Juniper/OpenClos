This README is to describe the process of creating REST API documentation for OpenClos.

**Install REST API creation tool**  

    curl -L -u '<username>:<password>' -o /tmp/OpenClos.zip https://github.com/Juniper/OpenClos/archive/<branch or tag>.zip     
    cd /tmp 
    unzip /tmp/OpenClos.zip
    chmod 777 -R /tmp/OpenClos-devR3.0/api/swagger-render-1.6.0
    cd /tmp/OpenClos-devR3.0/api/swagger-render-1.6.0
    sudo pip install --egg -e .  


Run the script
--------------

    swagger-render /tmp/OpenClos-devR3.0/api/overlay/openclos_overlay_api.yaml -o /tmp/OpenClos-devR3.0/api/overlay/openclos_overlay_api.html

    swagger-render /tmp/OpenClos-devR3.0/api/underlay/openclos_underlay_api.yaml -o /tmp/OpenClos-devR3.0/api/underlay/openclos_underlay_api.html

Input
------
Full path of the REST API in yaml format.

Output
------
-o Full path of generated HTML version of the REST API.

 
License
-------

Apache 2.0

This script is modified from swagger-render-1.6.0. Please refer to api/swagger-render-1.6.0/README.rst for details.


Support
-------

If you find an issue with the software, please open a bug report on the OpenClos repository.

The Juniper Networks Technical Assistance Center (JTAC) does not provide support for OpenClos software. You can obtain support for OpenClos by visiting the [OpenClos Google Group](https://groups.google.com/forum/#!forum/openclos)

