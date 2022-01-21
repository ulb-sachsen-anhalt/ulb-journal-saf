#!/bin/bash

if [ -z "$1" ]
  then
    echo "need argument 'omp' or 'ojs'"
    exit
fi


dspace="/opt/dspace/repo/bin/dspace"
mapscontainer="/opt/dspace/repo/infrastructure/$1/map"
mapsvolume="./volumes/infrastructure/$1/map"
container=dspace2_dspace_1

for mf in "$mapsvolume"/*
   do
     mapfilename=$(basename "$mf")
     mapcontainer=$mapscontainer/$mapfilename
     echo delete Item with Handel in "$mapcontainer" --> "$mapfilename"
     docker exec --user dspace $container $dspace import --delete --eperson axel.bauer@bibliothek.uni-halle.de --mapfile "$mapcontainer"
   done

rm -vf ./volumes/infrastructure/$1/doi/*
rm -vf ./volumes/infrastructure/$1/map/*
rm -vf ./volumes/infrastructure/$1/source/*

# script ojs/omp server loescht alle remote_url
ssh $1 ./delete_remote_url.sh
