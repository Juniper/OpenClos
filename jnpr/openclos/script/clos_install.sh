#!/bin/bash

OPENCLOS_PKG="openclos.tgz"
PYTHON_PKG="python.tgz"
OPENCLOS_DIR=$HOME
PYTHON_DIR="/opt"

TAG="OPENCLOS_INSTALL"
TS=`date | cut -d ' ' -f 1- --output-delimiter='_'`
LOG=/tmp/openclos_install_$TS.log

OPENCLOS_EGG=/opt/python2.7/lib/python2.7/site-packages/OpenClos-*.egg/jnpr/openclos/
REST_SCRIPT=openclos_rest.sh
TRAP_SCRIPT=openclos_trap.sh
CONFIG_SCRIPT=$OPENCLOS_EGG/configure_for_ND.py

REST_SERVICE=openclos_rest
TRAP_SERVICE=openclos_trap

SCL_UTILS="scl-utils-20120927-9.el5.i386"
MYSQL_RUNTIME="mysql51-runtime-1-9.el5.i386"
MYSQL_LIBS="mysql51-mysql-libs-5.1.70-1.el5.i386"

MYSQL_LIB_LOC=/opt/rh/mysql51/root/usr/lib/mysql/

cleanup_slate() {
    echo "[$TAG:INFO] Performing post-install cleanup"
    /bin/rm -rf /opt/$PYTHON_PKG
}

pre_cleanup() {
    if [ -f /opt/configure_for_ND.py ]; then
        /bin/rm -rf /opt/configure_for_ND.py
    fi

    if [ -f /usr/lib/libmysqlclient_r.so.15 ]; then
        /bin/rm -rf /usr/lib/libmysqlclient_r.so.15
    fi

    if [ -f /usr/lib/libmysqlclient_r.so.15.0.0 ]; then
        /bin/rm -rf /usr/lib/libmysqlclient_r.so.15.0.0
    fi

    if [ -f /usr/lib/libmysqlclient.so.15 ]; then
        /bin/rm -rf /usr/lib/libmysqlclient.so.15
    fi

    if [ -f /usr/lib/libmysqlclient.so.15.0.0 ]; then
        /bin/rm -rf /usr/lib/libmysqlclient.so.15.0.0
    fi
}

main() {
    echo "[$TAG:INFO] Logging current session at $LOG"
    echo "[$TAG:INFO] Checking files"

    if [ ! -f /opt/$PYTHON_PKG ]; then
        echo "[$TAG:ERROR] $PYTHON_PKG not found. Please install the OpenClos rpm using \"rpm -ivh <rpm file>\" command."
        exit 1
    fi

    if [ -d $PYTHON_DIR/python2.7 ]; then
        echo "[$TAG:INFO] Removing previous installation of Python2.7."
        /bin/rm -rf $PYTHON_DIR/python2.7
    fi

    echo "[$TAG:INFO] Removing any files leftover from previous installations"
    pre_cleanup

    tar xvzf /opt/$PYTHON_PKG -C $PYTHON_DIR
    if [ $? -ne 0 ]; then
        echo "[$TAG:ERROR] Untar of $PYTHON_PKG failed. Please check access privileges and then try installation again. You may have to uninstall OpenClos first using \"rpm -ev <OpenClos rpm name without .rpm extension>\"."
        exit 1
    fi

    if [ -x /usr/bin/python2.7 ]; then
        /bin/rm /usr/bin/python2.7
    fi
    ln -s /opt/python2.7/bin/python2.7 /usr/bin/python2.7

    echo "[$TAG:INFO] Removing services added by previous installs"
    chkconfig --level 3 $REST_SERVICE off > /dev/null
    chkconfig --del $REST_SERVICE > /dev/null
    /bin/rm /etc/init.d/$REST_SERVICE > /dev/null
    
    chkconfig --level 3 $TRAP_SERVICE off > /dev/null
    chkconfig --del $TRAP_SERVICE > /dev/null
    /bin/rm /etc/init.d/$TRAP_SERVICE > /dev/null

    /bin/sync

    if [ -f $OPENCLOS_EGG/script/$REST_SCRIPT ]; then
        echo "[$TAG:INFO] Adding OpenCLOS REST Service"
        ln -s $OPENCLOS_EGG/script/$REST_SCRIPT /etc/init.d/$REST_SERVICE
        chmod +x $OPENCLOS_EGG/script/$REST_SCRIPT
        chmod +x /etc/init.d/$REST_SERVICE
        /bin/sync
        chkconfig --add $REST_SERVICE
        chkconfig --level 3 $REST_SERVICE on
    fi

    if [ -f $OPENCLOS_EGG/script/$TRAP_SCRIPT ]; then
        echo "[$TAG:INFO] Adding OpenCLOS TRAP Service"
        ln -s $OPENCLOS_EGG/script/$TRAP_SCRIPT /etc/init.d/$TRAP_SERVICE
        chmod +x $OPENCLOS_EGG/script/$TRAP_SCRIPT
        chmod +x /etc/init.d/$TRAP_SERVICE
        /bin/sync
        chkconfig --add $TRAP_SERVICE
        chkconfig --level 3 $TRAP_SERVICE on
    fi

    if [ -f $CONFIG_SCRIPT ]; then
        ln -s $CONFIG_SCRIPT /opt/configure_for_ND.py
        /bin/sync
    fi

    if [ ! -f $MYSQL_LIB_LOC/libmysqlclient.so.1016.0.0 ]; then
        echo "[$TAG:ERROR] Could not find libmysqlclient.so.1016.0.0"
        exit 1
    fi

    if [ ! -f $MYSQL_LIB_LOC/libmysqlclient_r.so.1016.0.0 ]; then
        echo "[$TAG:ERROR] Could not find libmysqlclient_r.so.1016.0.0"
        exit 1
    fi

    ln -s $MYSQL_LIB_LOC/libmysqlclient_r.so.1016.0.0 /usr/lib/libmysqlclient_r.so.15
    ln -s $MYSQL_LIB_LOC/libmysqlclient_r.so.1016.0.0 /usr/lib/libmysqlclient_r.so.15.0.0
    ln -s $MYSQL_LIB_LOC/libmysqlclient.so.1016.0.0 /usr/lib/libmysqlclient.so.15
    ln -s $MYSQL_LIB_LOC/libmysqlclient.so.1016.0.0 /usr/lib/libmysqlclient.so.15.0.0
    /bin/sync

    if [ ! -d /var/log/openclos ]; then
        echo "[$TAG:INFO] Create Log directory in /var/log for OpenClos"
        /bin/mkdir -p /var/log/openclos/
        chmod 777 /var/log/openclos/
        /bin/sync
    fi
    
    echo "[$TAG:INFO] OpenClos installation complete using Python2.7"
    cleanup_slate
}

main 2>&1 | tee -a "$LOG" | grep "\[$TAG"
