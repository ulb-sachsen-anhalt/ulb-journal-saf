#!/bin/bash

export_folder=/opt/dspace/volumes/shared_kitodo/migration/working/
lockfile="$export_folder/STOP_FOR_OMP_IMPORT"

echo "put lock file $lockfile"
touch $lockfile
sleep 3

while [ "$(ls -l $export_folder | wc -l)" -gt 2 ]
do
        echo $(date +%H:%M:%S)
        echo "wait further 5 seconds"
        sleep  5
done;

echo "ok, folder is empty --> start import"

docker exec -it -u dspace dspace_dspace_1 /bin/bash /opt/dspace/repo/bin/ojs_omp/journals_import.sh omp

sleep 3
echo "delete $lockfile"
rm $lockfile
echo "done..."