#! /bin/bash
ssh -i insecure_key root@$(docker inspect  --format '{{ .NetworkSettings.IPAddress }}' openclos_con)
