#!/bin/bash
#
# Copyright (c) 2014, Juniper Networks Inc
# All rights reserved
#
#
# This shell script takes care of starting and stopping OpenCLOS REST Server
#
# chkconfig: - 15 90
# description: OpenCLOS REST Server
# processname: rest
# pidfile: /var/run/openclos_rest.pid
### BEGIN INIT INFO
# Provides: openclos_rest
# Required-Start: $network
# Required-Stop: $network
# Default-Start: 3 4 5
# Default-Stop:  0 1 2 6
# Short-Description: OpenCLOS access for ND
### END INIT INFO

RETVAL=0
PID_FILE=/var/run/openclos_rest.pid
REST_PATH=/opt/python2.7/lib/python2.7/site-packages/OpenClos-*.egg/jnpr/openclos/

SERVICE_NAME=openclos_rest
LOG_FILE=/var/log/$SERVICE_NAME

PYTHON_BIN=/opt/python2.7/bin/python2.7

if [ ! -f $LOG_FILE ]; then
    touch $LOG_FILE
    sync
fi

echo_log() {
    logger -t "OpenCLOS REST" "$*"
    echo "$*" >> $LOG_FILE
    echo "$*"
}

do_sanity_checks() {
    # check if we are running in space platform
    /bin/cat /etc/redhat-release | grep -i "space"
    if [ $? -ne 0 ]; then
        echo_log "This OpenCLOS script can be run only in Junos Space servers"
        # exit 1
    fi

    # check if python2.7 is already installed
    if [ ! -x /opt/python2.7/bin/python2.7 ]; then
        echo_log "Python 2.7 is not installed yet"
        exit 1
    fi

    # check if OpenCLOS package is present
    if [ ! -d $REST_PATH ]; then
        echo_log "OpenClos is not installed yet"
        exit 1
    fi

    # check if rest code is present
    if [ ! -f $REST_PATH/rest.py ]; then
        echo_log "REST Server is not implemented in the current OpenCLOS pkg"
        exit 1
    fi

    # check if OpenCLOS has been configured for ND
    if [ -f $REST_PATH/conf/openclos.yaml ]; then
        cat $REST_PATH/conf/openclos.yaml | grep "ndIntegrated : true"
        if [ $? -ne 0 ]; then
            echo_log "OpenCLOS has not been configured for ND yet"
            exit 1
        fi
    else
        echo_log "openclos.yaml not found"
        exit 1
    fi
    
    echo_log "OpenCLOS sanity checks passed for REST"
}

start_rest() {
    echo_log "REQUEST - Start OpenCLOS REST Server"

    PID=`cat $PID_FILE 2>/dev/null `
    if [ -n "$PID" ]; then
        kill -0 $PID > /dev/null 2>&1
        if [ $? -eq 0 ]; then
            echo "OpenCLOS REST server is running already"
            return 0
        fi
    fi

    # check for orphaned process
    PID=`pgrep -f "rest.py" | head -n 1 `
    if [ -n "$PID" ]; then
        kill -0 $PID > /dev/null 2>&1
        if [ $? -eq 0 ]; then
            echo "$PID" > $PID_FILE
            echo "OpenCLOS REST server is running already"
            return 0
        fi
    fi

    # no running process
    /bin/rm -f $PID_FILE

    echo "Starting OpenCLOS Server"

    $PYTHON_BIN $REST_PATH/rest.py & > $LOG_FILE
    RETVAL=$?
    PID=$!

    if [ $RETVAL -eq 0 ]; then
        echo_log "OpenCLOS REST server process started with PID $PID"
        /bin/rm -f $PID_FILE
        echo "$PID" > $PID_FILE
        sync
        return 0
    else
        echo_log "OpenCLOS REST server could not start due to $RETVAL"
        exit 1
    fi
}

stop_rest() {
    echo_log "REQUEST - Stop OpenCLOS REST Server"

    MPID=`ps -ef | grep rest.py | grep -v grep | awk '{print $2}'`
    if [ "$MPID" != "" ]; then
        /bin/kill "$MPID"
    fi

    PID=`cat $PID_FILE 2>/dev/null `
    if [ ! -n "$PID" ]; then
        PID=`ps -ef | grep rest.py | grep -v grep | awk '{print $2}'`
    fi

    if [ -n "$PID" ]; then
        /bin/kill "$PID" > /dev/null 2>&1
        echo_log "Stopping OpenCLOS REST Server"
    else
        echo_log "OpenCLOS REST Server process not found"
    fi

    /bin/rm -f $PID_FILE > /dev/null 2>&1
    return 0
}

status_rest() {
    PID=`ps -ef | grep rest.py | grep -v grep | awk '{print $2}'`
    if [ -n "$PID" ]; then
        echo_log "OpenCLOS REST Server is running"
        return 0
    else
        echo_log "OpenCLOS REST Server is not running"
        return 1
    fi
}

case "$1" in
    start)
        do_sanity_checks
        start_rest
        RETVAL=$?
        ;;

    stop)
        stop_rest
        RETVAL=$?
        ;;

    status)
        status_rest
        RETVAL=$?
        ;;

    restart)
        echo_log "Restarting OpenCLOS REST Server"
        $0 stop
        sleep 5
        $0 start
        ;;

    *)
        echo "Usage: $0 {start|stop|status|restart}"
        RETVAL=1
        ;;
esac

exit $RETVAL
