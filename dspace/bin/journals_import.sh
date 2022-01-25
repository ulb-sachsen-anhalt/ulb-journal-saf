#!/bin/bash

#set -e

echo "------------------------------------------------------------------------------"
echo "Version 0.2.0"
####
#docker exec --user dspace  dspace2_dspace_1 /opt/dspace/repo/bin/dspace import --delete --eperson <email importer> --mapfile
#  run this script from host cli:
#  docker exec -i  dspace2 /opt/dspace/repo/bin/journals_import.sh
#  or via Curation Task 
####

if [ -z "$1" ]
  then
    echo "need argument 'omp' or 'ojs'"
    exit
fi

dspace="/opt/dspace/repo/bin/dspace"
safs="/opt/dspace/repo/infrastructure/$1/source/"
maps="/opt/dspace/repo/infrastructure/$1/map/"
dois="/opt/dspace/repo/infrastructure/$1/doi/"
eperson="axel.bauer@bibliothek.uni-halle.de"

function write_doi() {
        doifilename=$1
        doi=$2
        doifile=$dois$doifilename
        if test -f "$doifile"; then
            echo "exists: **$doifile**  proceed..."
        else
            echo "$doi" > "$doifile"
            echo "write doi file -> $doifile"
        fi
}

function get_doi() {
        HANDLE=$1
        mapfilename=$2
        echo got Handle: "$HANDLE"
        DOI=$(/opt/dspace/repo/bin/dspace doi-organiser --list | grep "$HANDLE")
        echo "DOI handle--> ${DOI}"
        # "set Internal Field Separator to ' '".
        IFS=' '
        # read part by part into array 'doiline' 
        read -r -a doiline <<< "${DOI}"
        doi=${doiline[0]}
        echo "extracted DOI: $doi"
        write_doi "$mapfilename".doi "$doi"
}

function get_handle() {
        if test -f "$1"; then
           echo "$1"
           zipfilename=$(basename -- "$1")
           mapfilename=${zipfilename%%.*}

           IFS=' ' read -r -a array <<< "$(cat "$1")"
           ISSUE=${array[0]}
           HANDLE=${array[1]}
           echo "the issue: $ISSUE"
           get_doi "$HANDLE" "$mapfilename"
        fi
}

function import_saf() {
        saffile=$1
        echo "import $saffile"
        cmd="$dspace import --add \
        --eperson $eperson \
        --source $safs \
        --zip $saffile \
        --mapfile $maps/$saffile.map\
        --disable_inheritance"
        echo "$cmd"
        $cmd
}


# we loop over zips in "$saf" folder and call import_saf function for every file
for saf in "$safs"/*
    do
        safname=$(basename -- "$saf")
        import_saf "$safname"
    done

# now we read all resulting map files and extract data in order to build 
# "doi files" which we place in dois-folder:  $dois 
for saf in "$safs"/*
    do
        safname=$(basename "$saf")
        mapfile=$maps$safname.map
        echo "open $mapfile"
        if test -f "$mapfile"; then
           get_handle "$mapfile"
        fi
    done