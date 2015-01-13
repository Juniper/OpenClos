#!/bin/bash

TAG=OPENCLOS_UNINSTALL

echo "[$TAG:INFO] Stopping OpenClos services"
service openclos_rest stop &> /dev/null
sleep 2
service openclos_trap stop &> /dev/null
sleep 2

echo "[$TAG:INFO] Removing OpenClos services"
chkconfig --del openclos_rest
chkconfig --del openclos_trap

echo "[$TAG:INFO] Removing Python2.7 packages"
/bin/rm -rf /opt/python2.7
/bin/rm -rf /opt/configure_for_ND.py

echo "[$TAG:INFO] Removing any persistent files"
/bin/rm -rf /usr/lib/libmysqlclient_r.so.15
/bin/rm -rf /usr/lib/libmysqlclient_r.so.15.0.0
/bin/rm -rf /usr/lib/libmysqlclient.so.15
/bin/rm -rf /usr/lib/libmysqlclient.so.15.0.0

echo "[$TAG:INFO] OpenClos uninstallation complete"
