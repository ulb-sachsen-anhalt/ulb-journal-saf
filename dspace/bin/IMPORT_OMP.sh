#!/bin/bash

# Lockfile handling inside the docker
docker exec -it -u dspace dspace_dspace_1 /bin/bash /opt/dspace/repo/bin/ojs_omp/journals_import.sh omp
