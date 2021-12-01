#!/bin/bash

dspace="/opt/dspace/repo/bin/dspace"
mapscontainer="/opt/dspace/repo/infrastructure/ojs_omp/map"
mapsvolume="./volumes/infrastructure/ojs_omp/map"
container=dspace2_dspace_1

for mf in "$mapsvolume"/*
   do
     mapfilename=$(basename "$mf")
     mapcontainer=$mapscontainer/$mapfilename
     echo delete Item with Handel in "$mapcontainer"
     docker exec --user dspace $container $dspace import --delete --eperson axel.bauer@bibliothek.uni-halle.de --mapfile "$mapcontainer"
   done

rm -vf ./volumes/infrastructure/ojs_omp/doi/*
rm -vf ./volumes/infrastructure/ojs_omp/map/*
rm -vf ./volumes/infrastructure/ojs_omp/source/*

# script ojs server loescht alle remote_url
ssh ojs ./delete_remote_url.sh