#! /bin/bash

docker rm juniper/openclos_con
docker rmi -f juniper/openclos
docker build -t juniper/openclos .
