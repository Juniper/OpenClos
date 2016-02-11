FROM phusion/baseimage:0.9.17
MAINTAINER Damien Garros <dgarros@gmail.com>

RUN     apt-get -y update && \
        apt-get -y upgrade

# INstall dependencies
RUN     apt-get -y --force-yes install \
        wget curl build-essential git python-dev \
        libxml2-dev libxslt-dev python-pip isc-dhcp-server zlib1g-dev

RUN     pip install pyyaml jinja2 pydot bottle junos-eznc futures pysnmp \
        netifaces paste nose coverage webtest flexmock

## Copy project into the container
RUN     mkdir /root/openclos
ADD     jnpr  /root/openclos/jnpr
ADD     requirements.txt /root/openclos/requirements.txt
ADD     setup.py /root/openclos/setup.py
ADD     MANIFEST.in /root/openclos/MANIFEST.in

## Install Openclos from source
WORKDIR /root/openclos
RUN     python setup.py install

## Cleanup container
RUN     apt-get clean && \
        rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

ENV HOME /root
RUN chmod -R 777 /var/log/

VOLUME ["/data"]
CMD ["/sbin/my_init"]
