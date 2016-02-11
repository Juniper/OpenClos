#! /bin/bash

docker stop openclos_con
docker rm openclos_con

docker run --rm -t \
        --publish 8080:20080 \
        -i juniper/openclos /sbin/my_init -- bash -l
