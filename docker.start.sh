#! /bin/bash

docker stop openclos_con
docker rm openclos_con

docker run -d --restart always \
              --publish 8080:20080
              --name openclos_con juniper/openclos /sbin/my_init
